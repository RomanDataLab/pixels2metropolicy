"""social-economic sensing of slums step 8b — neighborhood (ชุมชน community) category-intensity choropleth.

Neighborhood polygons = the BMA community boundary layer already in the repo
(01_data/02_external_vector/bkk_community_boundaries/bkk_community_boundary.shp,
1,993 registered communities of all types; 626 are slums ชุมชนแออัด).
Intensity = count of extracted events per category per community (CMT_ID).
Khet outlines (geoBoundaries ADM2) + BMA risk-area pins (UTT fetch, TIS-620)
are optional reference layers.

Outputs (04_output/social_patterns/bangkok/):
  category_intensity_map.html          self-contained Leaflet map
  neighborhood_category_counts.csv     per-community counts

Run:  python make_intensity_map.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from shapely.geometry import mapping

import geopandas as gpd
import pandas as pd

from social_common import REPO, SOCIAL_OUT, SOCIAL_RAW, ensure_dirs

COMMUNITY_SHP = (REPO / "01_data" / "02_external_vector" / "bkk_community_boundaries"
                 / "bkk_community_boundary.shp")
KHER_GEOJSON = REPO / "05_scratch" / "social" / "bkk_khet.geojson"
RISK_CSV = REPO / "01_data" / "02_raw_imports" / "bma_risk_areas_15-2568.csv"
CATEGORIES = ["flooding", "fire", "env_hazard", "contamination", "basic_services",
              "housing_tenure_risk", "crime_security", "destitution",
              "informal_economy", "social_support"]
RAMP = ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c"]
SIMPLIFY_TOL = 0.0004
TYPE_EN = {"ชุมชนแออัด": "irregular neighborhood", "ชุมชนเมือง": "urban community",
           "ชุมชนชานเมือง": "suburban community", "ชุมชนอาคารสูง": "high-rise community",
           "ชุมชนรูปแบบพิเศษ": "special-form community", "ไม่ระบุ": "unspecified"}
TRANSLATE_CACHE = REPO / "05_scratch" / "social" / "translate_cache.json"


def translate_all(texts: list[str]) -> dict[str, str]:
    """Thai->English via DeepSeek (batch JSON), cached. gtx endpoint rate-blocks
    bulk use - see 05_scratch/social/translate_fill.py for the recovery story."""
    import requests
    cache: dict[str, str] = {}
    if TRANSLATE_CACHE.exists():
        cache = json.loads(TRANSLATE_CACHE.read_text(encoding="utf-8"))
    todo = [t for t in dict.fromkeys(texts) if t and not cache.get(t)]
    if not todo:
        return cache
    cfg_p = Path(r"G:\My Drive\J_Projects_Archive\config\config_deepseek.json")
    key = json.loads(cfg_p.read_text(encoding="utf-8"))["deepseek-code_api key"]
    print(f"translating {len(todo)} unique texts via DeepSeek (cache: {len(cache)})")
    import time
    B = 40
    for i in range(0, len(todo), B):
        chunk = todo[i:i + B]
        try:
            r = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": "deepseek-chat", "temperature": 0.1, "messages": [{
                    "role": "user",
                    "content": ("Translate each Thai news headline/community name to concise "
                                "English. Return ONLY a JSON array of strings, same length and "
                                "order. Input:\n" + json.dumps(chunk, ensure_ascii=False))}]},
                timeout=180)
            r.raise_for_status()
            out = r.json()["choices"][0]["message"]["content"].strip()
            arr = json.loads(out[out.index("["):out.rindex("]") + 1])
            if len(arr) == len(chunk):
                for t, tr in zip(chunk, arr):
                    cache[t] = str(tr)
        except Exception as exc:  # noqa: BLE001
            print(f"  batch {i//B}: {type(exc).__name__} {str(exc)[:60]}")
            time.sleep(2)
            continue
        TRANSLATE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TRANSLATE_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        time.sleep(0.5)
    return cache


def main() -> int:
    ensure_dirs()

    # ---------- neighborhoods: BMA community polygons ----------
    com = gpd.read_file(COMMUNITY_SHP)
    com.columns = [c.upper() if c != com.geometry.name else c for c in com.columns]
    com = com.set_geometry(com.geometry.name)
    com["geometry"] = com.geometry.buffer(0).simplify(SIMPLIFY_TOL)
    if com.crs and com.crs.to_epsg() != 4326:
        com = com.to_crs(4326)
    for col in ("CMT_NAME", "CMT_TYPE", "DNAME", "SNAME"):
        com[col] = com[col].map(lambda v: (v or "").strip() if isinstance(v, str) else "")
    print(f"community polygons: {len(com)}")

    # ---------- per-community event counts ----------
    ev = pd.read_parquet(SOCIAL_RAW / "events.parquet")
    ev = ev[ev["event_type"].notna() & ev["cmt_id"].notna()]
    counts = (ev.groupby(["cmt_id", "event_type"]).size().unstack(fill_value=0)
              .reindex(columns=CATEGORIES, fill_value=0))
    docs = ev.groupby("cmt_id")["doc_id"].nunique().rename("n_docs")
    # telegram-only counts (5000+-follower source policy) for map enrichment
    tg = ev[ev["source"] == "telegram"]
    tg_counts = (tg.groupby(["cmt_id", "event_type"]).size().unstack(fill_value=0)
                 .reindex(columns=CATEGORIES, fill_value=0))
    tg_total = tg.groupby("cmt_id").size().rename("tg_total")
    tab = counts.join(docs).fillna({"n_docs": 0})
    tab["n_docs"] = tab["n_docs"].astype(int)
    tab["total"] = counts.sum(axis=1)
    tab.index = tab.index.astype(str)   # CMT_ID as str: shapefile gives int, events give str
    print(f"communities with events: {len(tab)}")
    tab.to_csv(SOCIAL_OUT / "neighborhood_category_counts.csv", encoding="utf-8-sig")

    # ---------- risk-area pins (UTT fetch; TIS-620 mojibake) ----------
    risk = None
    if RISK_CSV.exists():
        try:
            rk = pd.read_csv(RISK_CSV, encoding="cp874")
            rk = rk.dropna(subset=["ALatitude", "ALongitude"])
            # translate risk fields (names/types/groups/characteristics) via shared cache
            r_tr = translate_all(
                [str(r.AName) for r in rk.itertuples()] +
                [str(r.AType) for r in rk.itertuples()] +
                [str(r.AGroup) for r in rk.itertuples()] +
                [str(r.characteristics)[:200] for r in rk.itertuples()])
            risk = [{"lat": float(r.ALatitude), "lon": float(r.ALongitude),
                     "name": str(r.AName), "en_name": r_tr.get(str(r.AName), "")[:100],
                     "type": str(r.AType), "en_type": r_tr.get(str(r.AType), ""),
                     "group": str(r.AGroup), "en_group": r_tr.get(str(r.AGroup), ""),
                     "chars": str(r.characteristics)[:120],
                     "en_chars": r_tr.get(str(r.characteristics)[:200], "")[:160]}
                    for r in rk.itertuples()]
            print(f"risk-area pins decoded: {len(risk)}")
        except Exception as exc:  # noqa: BLE001
            print(f"risk csv unreadable: {exc}")

    # per-community recent events for tooltips (texts + origins), capped for file size
    ev_for_tip = ev.sort_values("pubdate", ascending=False).groupby("cmt_id").head(6)
    # translate unique Thai texts once (header names + event titles), cached
    tr = translate_all(
        [str(r.title) for r in ev_for_tip.itertuples()] +
        [str(c) for c in com["CMT_NAME"].unique() if c])
    tip_events: dict[str, list[dict]] = {}
    for r in ev_for_tip.itertuples():
        t = str(r.title) or ""
        tip_events.setdefault(str(r.cmt_id), []).append({
            "t": t[:90],
            "en": tr.get(t, "")[:120],
            "src": str(r.publisher or r.source),
            "type": str(r.event_type),
            "date": str(r.pubdate)[:10],
        })

    rk = pd.read_csv(SOCIAL_OUT / "slum_rankings.csv", dtype={"cmt_id": str}, encoding="utf-8-sig").set_index("cmt_id")
    rk["name_en"] = [tr.get(str(n), "") for n in rk["CMT_NAME"]]
    rk = rk.reset_index()
    rk.to_csv(SOCIAL_OUT / "slum_rankings.csv", index=False, encoding="utf-8-sig")
    # per-community broken-norm details for the build-code ranking (code_risk.csv)
    cr = pd.read_csv(SOCIAL_OUT / "code_risk.csv", dtype={"cmt_id": str})
    cr = cr[~cr["cmt_id"].duplicated()].set_index("cmt_id")
    NORMS = [("water", "public waterway", 6.0,
              "Ministerial Regulation No. 55 (B.E. 2543) ข้อ 40: 3-6 m bank setback"),
             ("rail", "railway", 30.0,
              "Rail Transport Act practice: 30 m from track centreline"),
             ("highway", "public road", 6.0,
              "Ministerial Regulation No. 55 (B.E. 2543) ข้อ 41: 2-6 m setback by road width"),
             ("industrial", "industrial zone", 100.0,
              "comprehensive-plan nuisance buffer (policy proxy, not law)")]

    def code_vlist(cid: str) -> list[str]:
        if cid not in cr.index:
            return []
        row = cr.loc[cid]
        return [f"{name}: boundary {float(row[f'dist_{src}']):.0f} m away vs "
                f"{thr:.0f} m allowed — {law}"
                for src, name, thr, law in NORMS if int(row[f"viol_{src}"]) == 1]
    RK_DEFS = [("rank", "score", "Alkire-Foster composite"),
               ("rank_danger", "danger_rate", "most-dangerous events (severity-weighted/1k)"),
               ("rank_flood", "flood_score", "flooded blocks (GISTDA flood-frequency)"),
               ("rank_code", "code_risk", "broken build-code proximity (setback proxy)")]
    # rank_problem (all-events burden) dropped: same 30 communities as the
    # severity-weighted danger ranking over the 92-day window
    DESCS = {
        "rank": "Multidimensional deprivation score (Alkire-Foster method, as used by the "
                "WFP Multidimensional Deprivation Index): each of the 10 event domains counts "
                "as deprived when its rate per 1,000 residents exceeds the citywide P75 "
                "cutoff; the score is the mean of the 10 domain scores. Higher = more domains "
                "affected, more intensely. Communities with pop&lt;100 are unranked.",
        "rank_danger": "Events per 1,000 residents weighted by domain severity: fire 1.0, "
                       "flooding/crime 0.9, accidents 0.8, contamination/tenure 0.6, "
                       "services 0.5, destitution 0.4, informal economy 0.2, support 0.1.",
        "rank_flood": "Share of sampled community points that fall inside GISTDA "
                      "repeated-flood areas, multiplied by mean flood intensity "
                      "(flood_score from the Vallaris flood-frequency layer).",
        "rank_code": "Weighted count of legal setback bands the community touches: "
                     "water 6 m, railway 30 m, road 6 m, industrial 100 m. "
                     "Click a pin for the exact norms breached.",
    }
    rank_sets = {}
    for rk_col, v_col, label in RK_DEFS:
        rows = rk[rk[rk_col] > 0].sort_values(rk_col).head(30)
        items = [{"rank": int(r[rk_col]), "id": str(r["cmt_id"]),
                  "th": str(r["CMT_NAME"])[:34], "en": str(r["name_en"])[:44],
                  "sname": str(r["SNAME"]), "dname": str(r["DNAME"]),
                  "v": round(float(r[v_col]), 2)} for _, r in rows.iterrows()]
        if rk_col == "rank_code":
            for it in items:
                it["vlist"] = code_vlist(it["id"])
        rank_sets[rk_col] = {"label": label, "desc": DESCS[rk_col], "items": items}

    # ---------- geojson features ----------
    feats = []
    for c in com.itertuples():
        cid = str(getattr(c, "CMT_ID"))
        row = tab.loc[cid] if cid in tab.index else None
        props = {
            "id": cid,
            "name": getattr(c, "CMT_NAME", ""),
            "name_en": tr.get(getattr(c, "CMT_NAME", ""), "")[:70],
            "type": getattr(c, "CMT_TYPE", ""),
            "type_en": TYPE_EN.get(getattr(c, "CMT_TYPE", ""), ""),
            "dname": getattr(c, "DNAME", ""),
            "sname": getattr(c, "SNAME", ""),
            "pop": int(getattr(c, "POP_TOTAL") if pd.notna(getattr(c, "POP_TOTAL")) else 0),
            "n_docs": int(row["n_docs"]) if row is not None else 0,
            "total": int(row["total"]) if row is not None else 0,
            "counts": {k: int(row[k]) for k in CATEGORIES} if row is not None else {},
            "score": float(rk.loc[cid,"score"]) if cid in rk.index else 0,
            "rank": int(rk.loc[cid,"rank"]) if cid in rk.index else 0,
            "affected": int(rk.loc[cid,"affected_domains"]) if cid in rk.index else 0,
            "tg_total": int(tg_total.get(cid, 0)),
            "tg_counts": {k: int(tg_counts.loc[cid, k]) for k in CATEGORIES}
                         if cid in tg_counts.index else {},
            "events": tip_events.get(cid, []),
        }
        feats.append({"type": "Feature", "geometry": mapping(c.geometry),
                      "properties": props})

    com_xy = {str(c): (float(x), float(y)) for c, x, y in
              zip(com["CMT_ID"], com.geometry.centroid.x, com.geometry.centroid.y)}
    top30 = rk[rk["rank"] > 0].head(30)
    TOP30 = [{"rank": int(r["rank"]), "lat": com_xy[str(r["cmt_id"])][1],
              "lon": com_xy[str(r["cmt_id"])][0], "name_en": str(r["name_en"])[:60],
              "th": str(r["CMT_NAME"]), "sname": str(r["SNAME"]), "dname": str(r["DNAME"]),
              "score": float(r["score"]), "aff": int(r["affected_domains"]), "pop": int(r["pop"])}
             for _, r in top30.iterrows() if str(r["cmt_id"]) in com_xy]

    zones = json.loads(Path(REPO / "05_scratch/social/zones_simplified.geojson").read_text(encoding="utf-8"))
    # public-land / infrastructure coincidence (public_infra_overlap.py);
    # geometry comes from the slum profile geojson keyed by CMT_ID
    pub_tab = pd.read_csv(SOCIAL_OUT / "public_infra_slums.csv", dtype={"cmt_id": str}).fillna("")
    prof = {str(f["properties"].get("CMT_ID")): f for f in
            json.loads((SOCIAL_OUT / "slum_social_profile.geojson").read_text(encoding="utf-8"))["features"]}
    pub_feats = []
    for r in pub_tab.itertuples():
        f = prof.get(str(r.cmt_id))
        if not f:
            continue
        pub_feats.append({"type": "Feature",
                          "geometry": f["geometry"],
                          "properties": {"name": r.CMT_NAME,
                                         "en": tr.get(str(r.CMT_NAME), "")[:60],
                                         "pub": int(r.on_public_land),
                                         "zones_th": str(r.zones_th), "zones": str(r.zones_en),
                                         "infra": str(r.infra)}})

    khet = (json.loads(Path(KHER_GEOJSON).read_text(encoding="utf-8"))
            if KHER_GEOJSON.exists() else {"type": "FeatureCollection", "features": []})

    html = (HTML
            .replace("__RANKSETS__", json.dumps(rank_sets, ensure_ascii=False))
            .replace("__ZONES__", json.dumps(zones, ensure_ascii=False))
            .replace("__PUBFEATS__", json.dumps({"type": "FeatureCollection", "features": pub_feats}, ensure_ascii=False))
            .replace("__NPUB__", str(len(pub_feats)))
            .replace("__TOP30__", json.dumps(TOP30, ensure_ascii=False))
            .replace("__METHOD__", METHOD_HTML)
            .replace("__COMMUNITY_GEOJSON__", json.dumps({"type": "FeatureCollection",
                                                          "features": feats}, ensure_ascii=False))
            .replace("__KHET_GEOJSON__", json.dumps(khet, ensure_ascii=False))
            .replace("__RISK_PINS__", json.dumps(risk or [], ensure_ascii=False))
            .replace("__RAMP__", json.dumps(RAMP))
            .replace("__CATS__", json.dumps(CATEGORIES)))
    (SOCIAL_OUT / "category_intensity_map.html").write_text(html, encoding="utf-8")
    print(f"outputs: {SOCIAL_OUT}\\{{category_intensity_map.html, neighborhood_category_counts.csv}}")
    top = pd.DataFrame([f["properties"] for f in feats]).nlargest(8, "total")
    print(top[["name", "sname", "dname", "pop", "n_docs", "total"]].to_string(index=False))
    return 0


METHOD_HTML = """
<h3 style="margin:4px 0">social-economic sensing of irregular neighborhoods — methodology</h3>
<p>Social-signal layer geolocating news, official complaints and public social media
to Bangkok's 1,993 BMA-registered communities (626 irregular neighborhoods, ชุมชนแออัด).
92-day rolling window.</p>

<h4>Step 1 — Gazetteer (name-matching dictionary)</h4>
<p>Thai name variants built from the official BMA community polygons: full and
prefix-stripped irregular-neighborhood names, landmarks (canals, roads, temples) mined from the
address and N/S/E/W adjacency text, khwaeng and district names, 46 romanized
district names (geoBoundaries ADM2 spatial match) and 37 famous-area aliases
(Sukhumvit, Khaosan, Klong Toey&hellip;). 5,120 variants over 626 irregular neighborhoods.</p>

<h4>Step 2 — Official complaints (Traffy Fondue)</h4>
<p>Pin-level citizen reports from the public share API; GPS coordinates joined
directly to community polygons (no text matching needed). Limit: the public
endpoint exposes only a rolling ~100-report sample of ~550; the full traffy360
dataset requires a free API token.</p>

<h4>Step 3 — Official statistics (gdcatalog)</h4>
<p>Crime cases, crime arrests, drug cases and corrections statistics downloaded
as CSV from the Thai government open-data catalog. Province-level granularity:
used as calibration denominators, not pinned to communities.</p>

<h4>Step 4 — News ingestion</h4>
<p>RSS feeds (Thairath, Sanook, Prachatai) plus 158 Google News RSS queries
(one per khwaeng, top-40 irregular neighborhoods by population). Article links resolved where
robots.txt allows; Google News items remain snippet-only (JavaScript redirects).
Headlines carry the location signal in Thai local reporting.</p>

<h4>Step 5 — Social media</h4>
<p>Pantip public search threads and Telegram public channel previews
(t.me/s/), Thai-language channels prioritized (Thai script matches the
gazetteer). Telegram policy: only channels with 5,000+ verified followers,
with an exemption for Thai-language channels; subscriber counts cross-checked
against independent crawlers because t.me serves decoy counts to scrapers.</p>

<h4>Step 6 — Event extraction</h4>
<p>Open-source Thai NLP (pythainlp tokenization) plus a keyword lexicon
classifying texts into ten domains grounded in the literature (Domains of
Deprivation Framework; UN-Habitat SDG 11.1.1; Slum Severity Index): flooding
and fire as first-class hazard domains, residual environmental hazards
(geo + accidents), contamination &amp; sanitation, basic services, housing
&amp; tenure risk, crime &amp; security, destitution, informal economy, social
support. Thai texts machine-translated to English for display
(DeepSeek, batch).</p>

<h4>Step 7 — Geolocation tiers</h4>
<p>T1 neighborhood name + khwaeng/district both in text (0.9) &middot; T2 neighborhood name alone (0.7)
&middot; T3 khwaeng/district only, distributed across its irregular neighborhoods by population share (0.4)
&middot; T4 landmark only (0.3). Known limit: headlines rarely name irregular neighborhoods directly,
so T3 dominates; neighborhood-level precision comes from Traffy GPS pins.</p>

<h4>Step 8 — Aggregation &amp; map</h4>
<p>Weighted event counts per community; color intensity = event count
(sqrt-scaled, 50% max opacity); white = no events. BMA risk-area registry
(fiscal year 2568) overlaid as reference pins. Grey-tone OSM basemap.</p>

<h4>Step 9 — Flood-frequency ranking</h4>
<p>Each community sampled at 5 points against the GISTDA Vallaris "repeated
flood areas" WMS (same live layer as the main map tab; z14 tiles cached);
pixel alpha encodes flood-frequency intensity. flood_score = flooded sample
fraction x mean intensity. 328 of 626 communities show flood signal.</p>
<h4>Step 10 — Build-code proximity ranking (proxy)</h4>
<p>Community polygons buffered against OSM railways/waterways, NGIS highways
and comprehensive-plan industrial zones. Setback thresholds per Ministerial
Regulation No. 55 (B.E. 2543), ข้อ 40-42: 3-6 m from public waterways/roads;
30 m railway practice band. code_risk = weighted count of setback bands the
community touches. Proxy at community level - not per-building compliance.</p>
<h4>Step 11 — Rankings</h4>
<p>Five rankings: Alkire-Foster composite; all-events burden (events/1,000
residents); most-dangerous events (domain severity weights: fire 1.0,
flooding/crime 0.9, accidents 0.8, contamination/tenure 0.6, services 0.5,
destitution 0.4, informal economy 0.2, support 0.1); flooded blocks;
build-code proximity. Pop&lt;100 unranked.</p>
<h4>Step 12 — Public-land / infrastructure coincidence</h4>
<p>Irregular-neighborhood polygons intersecting public-purpose comprehensive-plan zones
(ส government / public utility; ศ Thai cultural conservation; ก conservation
rural and agricultural) or infrastructure setback bands (public waterway 6 m,
public road 6 m, railway 30 m). 65 of 626 irregular neighborhoods sit on public-land zones;
446 fall inside at least one setback band (Bangkok's canal-side settlement
pattern); 53 hit both; 458 total flagged red.</p>
<h4>References (Harvard)</h4>
<ol style="padding-left:16px;margin:4px 0">
<li>Bangkok Metropolitan Administration (2026) <i>ขอบเขตชุมชน (ตรวจสอบแล้ว) [Verified community boundaries]</i>. Available at: https://cpudgiapp.bangkok.go.th/arcgis/rest/services/Community/Service_Community/FeatureServer/14 (Accessed: 8 October 2026).</li>
<li>Bangkok Metropolitan Administration (2026) <i>บัญชีพื้นที่เสี่ยงและพื้นที่อันตราย กทม. ปีงบประมาณ 2568 [BMA risk and danger-area registry, FY 2568]</i>. Available at: https://data.bangkok.go.th (Accessed: 8 October 2026).</li>
<li>geoBoundaries (2023) <i>Thitan ADM2 — geoBoundariesSimplified</i>. Available at: https://www.geoboundaries.org (Accessed: 8 October 2026).</li>
<li>Google (2026) <i>Google News RSS search</i>. Available at: https://news.google.com/rss/search (Accessed: 8 October 2026).</li>
<li>National Electronics and Computer Technology Center (NECTEC) (2026) <i>Traffy Fondue public share API</i>. Available at: https://publicapi.traffy.in.th/share/search (Accessed: 8 October 2026).</li>
<li>Pantip (2026) <i>Pantip search</i>. Available at: https://pantip.com/search (Accessed: 8 October 2026).</li>
<li>Royal Thai Government (2026) <i>gdcatalog: คดีอาชญากรรมที่เกิดขึ้น, การจับกุมผู้ก่อคดีอาชญากรรม, คดียาเสพติด, สถิติผู้ต้องราชทัณฑ์คดียาเสพติด</i>. Available at: https://gdcatalog.go.th (Accessed: 8 October 2026).</li>
<li>Prachatai (2026) <i>RSS feed</i>. Available at: https://prachatai.com/feed (Accessed: 8 October 2026).</li>
<li>Sanook (2026) <i>Sanook news RSS</i>. Available at: http://rssfeeds.sanook.com/rss/feeds/sanook/news.crime.xml (Accessed: 8 October 2026).</li>
<li>Telegram (2026) <i>Public channel web previews</i>. Available at: https://t.me/s/&lt;channel&gt; (Accessed: 8 October 2026).</li>
<li>Thairath (2026) <i>Thairath RSS</i>. Available at: https://www.thairath.co.th/rss/news (Accessed: 8 October 2026).</li>
<li>DeepSeek (2026) <i>DeepSeek API — machine translation (Thai to English)</i>. Available at: https://api.deepseek.com (Accessed: 11 October 2026).</li>
<li>GISTDA (2026) <i>Vallaris Maps WMS: flood frequency (พื้นที่น้ำท่วมซ้ำซาก)</i>. Available at: https://api-gateway.gistda.or.th/api/2.0/resources/maps/flood-freq/wms (Accessed: 25 October 2026).</li>
<li>Ministry of Interior, Thailand (2000) <i>Ministerial Regulation No. 55 (B.E. 2543) under the Building Control Act: building setbacks from public roads, waterways and railways, ข้อ 40-42</i>. Available at: https://www.bsa.or.th (Accessed: 25 October 2026).</li>
<li>OpenStreetMap contributors (2026) <i>OpenStreetMap railway, waterway and highway data (Overpass API)</i>. Available at: https://www.overpass-api.de (Accessed: 25 October 2026).</li>
<li>Abascal, J., Rothwell, N., Shonowo, A., Thomson, D.R., Elias, P., Elsey, H., Yeboah, G. and Kuffer, M. (2022) '&ldquo;Domains of deprivation&rdquo; framework for mapping slums, informal settlements, and other deprived areas in LMICs to improve urban planning and policy: a scoping review', <i>Habitat International</i>, 123, 102776. Available at: https://www.sciencedirect.com/science/article/pii/S019897152200014X (Accessed: 15 October 2026).</li>
<li>Roy, D., Bernal, D. and Lees, M. (2020) 'An exploratory factor analysis model for slum severity index in Mexico City', <i>Urban Studies</i>, 57(4), pp. 797&ndash;819. Available at: https://journals.sagepub.com/doi/10.1177/0042098019869769 (Accessed: 15 October 2026).</li>
<li>United Nations Statistics Division (2023) <i>SDG indicator 11.1.1 metadata: proportion of urban population living in slums, informal settlements or inadequate housing</i>. Available at: https://unstats.un.org/sdgs/metadata/files/Metadata-11-01-01.pdf (Accessed: 15 October 2026).</li>
<li>World Food Programme (2023) <i>Multidimensional Deprivation Index (MDDI): Alkire-Foster essential-needs counting &mdash; food, health, education, shelter, WASH, safety</i>. Available at: https://vamresources.manuals.wfp.org/docs/multidimensional-deprivation-index-mddi (Accessed: 15 October 2026).</li>
<li>PyThaiNLP (2024) <i>PyThaiNLP: Thai natural language processing toolkit</i>. Available at: https://pythainlp.github.io (Accessed: 8 October 2026).</li>
</ol>
"""


HTML = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>social-economic sensing of irregular neighborhoods — neighborhood category intensity</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  body{margin:0;font-family:sans-serif;background:#0d1216}
  .ranknum{background:transparent;font:700 11px sans-serif;color:#ffca28;text-shadow:0 0 3px #000;}   /* dark basemap */
  #map{position:absolute;top:0;bottom:0;right:0;left:0}
  .panel{position:absolute;top:10px;right:10px;z-index:1000;background:rgba(13,18,22,0.88);
         color:#cfd8dd;padding:10px 14px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.5);max-width:320px;
         max-height:92vh;overflow-y:auto}
  h1{font-size:15px;margin:0 0 8px;color:#fff}
  .note{font-size:11px;color:#8a979e;margin-top:6px}
  label{display:block;font-size:13px;margin-top:4px}
  .cats label{display:flex;align-items:center;gap:8px;font-size:13px;padding:2px 0;cursor:pointer}
  .sw{width:16px;height:12px;border:1px solid #8899a0;flex:none}
</style>
</head>
<body>
<div id="map"></div>
<div class="panel" id="legend">
  <button id="legendbtn" type="button"
    style="position:absolute;top:6px;right:8px;border:1px solid #55606a;border-radius:5px;
           background:#1d2830;color:#cfd8dd;cursor:pointer;font-size:12px;padding:1px 7px">&#9650;</button>
  <div id="legendbody">
  <h1>social-economic sensing of irregular neighborhoods — events per neighborhood (ชุมชน)</h1>
  <div class="cats" id="cats"></div>
  <label><input type="checkbox" id="khet"/> khet (district) outlines</label>
  <label><input type="checkbox" id="slumonly"/> irregular neighborhoods only</label>
  <label><input type="checkbox" id="risk"/> BMA risk areas (2568)</label>
  <label><input type="checkbox" id="top30"/> top-30 ranked communities</label>
  <label><input type="checkbox" id="floodwms"/> repeated flood areas (GISTDA WMS)</label>
  <label><input type="checkbox" id="zoning"/> Zoning of Bangkok (ผังเมืองรวม กทม.)</label>
  <label><input type="checkbox" id="publands"/> irregular neighborhoods on public land / infrastructure — red 50% (<span id="npub"></span>)</label>
  <div id="zonelegend" style="display:none;max-height:40vh;overflow:auto;margin-top:8px;
       border-top:1px solid #33424a;padding-top:6px;font-size:12px"></div>
  <button id="rankbtn" type="button"
    style="margin-top:8px;width:100%;padding:4px 8px;border:1px solid #1b5e20;border-radius:6px;
           background:#2e7d32;color:#fff;cursor:pointer;font-size:13px">Rankings (top 30)</button>
  <div id="rankpanel" style="display:none;margin-top:8px;
       border-top:1px solid #33424a;padding-top:6px;font-size:12px">
    <div style="color:#8a979e">pick a ranking — its top 30 light up on the map</div>
    <label style="display:block;margin-top:4px;cursor:pointer"><input type="checkbox" id="rankonly" checked/>
      rankings-only view (hide event choropleth)</label>
    <div id="rankopts" style="margin-top:4px"></div>
    <div id="rankdesc" style="display:none;margin-top:6px;border-top:1px solid #33424a;
         padding-top:5px;color:#b9c6cc;line-height:1.4"></div>
    <div style="color:#8a979e;margin-top:4px">click a highlighted neighborhood for its value</div>
  </div>
  <button id="methbtn" type="button"
    style="margin-top:8px;width:100%;padding:4px 8px;border:1px solid #2b6cb0;border-radius:6px;
           background:#2b6cb0;color:#fff;cursor:pointer;font-size:13px">Methodology</button>
  <div id="meth" style="display:none;max-height:56vh;overflow:auto;margin-top:8px;
       border-top:1px solid #33424a;padding-top:6px;font-size:12px;line-height:1.45;text-align:left">
__METHOD__
  </div>
  <div class="note">Light-to-dark shade = more events; lightest shade = no events.
  92-day window.</div>
  </div><!-- /legendbody -->
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const N = __COMMUNITY_GEOJSON__;
const KH = __KHET_GEOJSON__;
const RISK = __RISK_PINS__;
const TOP30 = __TOP30__;
const ZONES = __ZONES__;
const PUB = __PUBFEATS__;
document.getElementById('npub').textContent = PUB.features.length + ' communities';
const CATS = __CATS__;
const LABELS = {};   // display-name overrides for categories
const RAMPS = {
  flooding:           ['#e1f5fe','#b3e5fc','#4fc3f7','#039be5','#01579b'],
  fire:               ['#fbe9e7','#ffccbc','#ff8a65','#f4511e','#bf360c'],
  env_hazard:         ['#fffde7','#fff9c4','#fdd835','#f9a825','#f57f17'],
  contamination:      ['#f3e5f5','#ce93d8','#ab47bc','#7b1fa2','#4a148c'],
  basic_services:     ['#e0f2f1','#80cbc4','#26a69a','#00897b','#004d40'],
  housing_tenure_risk:['#fce4ec','#f8bbd0','#ec407a','#c2185b','#880e4f'],
  crime_security:     ['#ffebee','#ffcdd2','#ef5350','#c62828','#b71c1c'],
  destitution:        ['#f9fbe7','#e6ee9c','#d4e157','#9e9d24','#827717'],
  informal_economy:   ['#e8f5e9','#a5d6a7','#66bb6a','#2e7d32','#1b5e20'],
  social_support:     ['#e0f7fa','#b2ebf2','#4dd0e1','#00acc1','#006064']
};
// start view: fit all Bangkok communities, not the world
const BKK=L.latLngBounds([]);
function collect(g){
  if(!g) return;
  if(g.type==='Point'){BKK.extend([g.coordinates[1],g.coordinates[0]]);return;}
  if(!g.coordinates) return;
  (function w(c){ if(typeof c[0]==='number') BKK.extend([c[1],c[0]]); else c.forEach(w); })(g.coordinates);
}
N.features.forEach(f=>collect(f.geometry));
const map = L.map('map').fitBounds(BKK.pad(0.03), {animate:false});
(function refit(){                       // background-tab load: size 0 -> zoom 0; retry until real fit
  if(map.getZoom()>=8) return;
  map.invalidateSize();
  map.fitBounds(BKK.pad(0.03), {animate:false});
  setTimeout(refit, 400);
})();
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
  {maxZoom:19, maxNativeZoom:16,
   attribution:'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ'}).addTo(map);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
  {maxZoom:19, maxNativeZoom:16, opacity:0.8,
   attribution:''}).addTo(map);

let layer=null, khetLayer=null, riskLayer=null, currentCat='flooding';

const box=document.getElementById('cats');
CATS.forEach(c=>{
  const l=document.createElement('label');
  const r=document.createElement('input'); r.type='radio'; r.name='cat'; r.value=c;
  if(c===currentCat) r.checked=true;
  const sw=document.createElement('span'); sw.className='sw';
  sw.style.background=RAMPS[c][2];
  const t=document.createElement('span'); t.textContent=LABELS[c]||c;
  l.append(r,sw,t); box.appendChild(l);
  r.onchange=()=>{currentCat=c; draw();};
});

function style(cat){
  const mx=Math.max(...N.features.map(f=>f.properties.counts[cat]||0),1);
  return f=>{
    const v=f.properties.counts[cat]||0;
    const slum=f.properties.type==='ชุมชนแออัด';
    const r=RAMPS[cat];
    if(v===0) return {color:'#999',weight:0.5,fillColor:r[0],fillOpacity:0.55};   // lightest shade of the domain ramp
    const i=Math.min(4, Math.floor(Math.sqrt(v/mx)*5));   // light -> dark
    return {color:'#333',weight:0.8,fillColor:r[i],fillOpacity:0.85};
  };
}
function tipHtml(f){
  const p=f.properties, c=p.counts, cat=currentCat;
  const en=p.name_en?`<div style="color:#0a5f73;font-size:11px">${p.name_en}</div>`:'';
  const head=`<b>${p.name}</b>${en}<span style="color:#666">(${p.type_en||p.type}) · ${p.sname} · ${p.dname}</span>`;
  const row=`${LABELS[cat]||cat}: <b>${c[cat]||0}</b> · total: <b>${p.total}</b> · docs: <b>${p.n_docs}</b>`+
    (p.rank>0?`<br>score <b>${p.score}</b> · rank <b>#${p.rank}</b> · affected <b>${p.affected_domains}/10</b>`:'');
  if(!p.total) return `${head}<div style="margin-top:4px">${row}</div>`+
    `<div style="margin-top:4px;color:#666">no events in the 92-day window</div>`;
  const origins={};
  (p.events||[]).forEach(e=>origins[e.src]=(origins[e.src]||0)+1);
  const or=Object.entries(origins).map(([s,n])=>`${s} (${n})`).join(' · ');
  const texts=(p.events||[]).slice(0,4).map(e=>
     `<div style="margin-top:3px;border-top:1px solid #ccc;padding-top:2px">
        <span style="color:#666">${e.date} · ${e.src}</span><br>${e.t}
        ${e.en?`<div style="color:#0a5f73;font-size:11px">${e.en}</div>`:''}</div>`).join('');
  return `${head}<div style="margin-top:4px">${row}</div>
    <div style="margin-top:4px;color:#444"><b>origins:</b> ${or}</div>${texts}`;
}
function draw(){
  const onlySlum=document.getElementById('slumonly').checked;
  if(layer) map.removeLayer(layer);
  const feats=onlySlum?N.features.filter(f=>f.properties.type==='ชุมชนแออัด'):N.features;
  layer=L.geoJSON({type:'FeatureCollection',features:feats},{style:style(currentCat),
    onEachFeature:(f,lyr)=>{
      lyr.bindTooltip('',{sticky:true,direction:'top',opacity:0.95});
    }}).addTo(map);
  // every polygon gets a tooltip; content follows the selected category
  layer.eachLayer(l=>{ l.setTooltipContent(tipHtml(l.feature)); });
}
document.getElementById('slumonly').onchange=draw;
draw();

document.getElementById('khet').onchange=e=>{
  if(khetLayer){map.removeLayer(khetLayer); khetLayer=null;}
  if(e.target.checked){
    khetLayer=L.geoJSON(KH,{style:{color:'#555',weight:2,fill:false,dashArray:'4 3'},
      onEachFeature:(f,l)=>l.bindTooltip(f.properties.khet_thai||f.properties.khet,{sticky:true})})
      .addTo(map);
  }
};
document.getElementById('risk').onchange=e=>{
  if(riskLayer){map.removeLayer(riskLayer); riskLayer=null;}
  if(e.target.checked){
    riskLayer=L.layerGroup(RISK.map(p=>
      L.circleMarker([p.lat,p.lon],{radius:5,color:'#d22',weight:1,fillOpacity:0.6})
        .bindPopup(
          `<b>${p.name}</b>`+
          (p.en_name?`<div style="color:#0a5f73;font-size:11px">${p.en_name}</div>`:'')+
          `${p.type} · ${p.group}`+
          ((p.en_type||p.en_group)?`<div style="color:#0a5f73;font-size:11px">${[p.en_type,p.en_group].filter(Boolean).join(' · ')}</div>`:'')+
          (p.chars?`<div style="margin-top:4px">${p.chars}</div>`:'')+
          (p.en_chars?`<div style="color:#0a5f73;font-size:11px">${p.en_chars}</div>`:'')
        )))
      .addTo(map);
  }
};
let floodWms=null;
document.getElementById('floodwms').onchange=e=>{
  if(floodWms){map.removeLayer(floodWms); floodWms=null;}
  if(e.target.checked){
    floodWms=L.tileLayer.wms("https://api-gateway.gistda.or.th/api/2.0/resources/maps/flood-freq/wms",
      {layers:"6799ab8c6f832362f99030e6",format:"image/png",transparent:true,version:"1.1.1",
       api_key:"eEpbI0F7pN5cL1EPQoZcdUfKPJVyhQWjfsssUJjk8TelSFYYDU1gDUV30SLY6MPT",
       attribution:"GISTDA Vallaris Maps",opacity:0.6}).addTo(map);
  }
};
let zoneLayer=null, pubLayer=null;
const ZCAT = {
  'Government / public utility':      '#4daf4a',
  'Thai cultural conservation':       '#984ea3',
  'Conservation rural and agricultural':'#a65628',
  'Industrial':                       '#ff7f00',
  'Low-density residential':          '#fee08b',
  'Medium-density residential':       '#fdb863',
  'High-density residential':         '#f4a582',
  'Commercial':                       '#80cdc1',
  'Rural and agricultural':           '#c7eae5',
  'Warehousing':                      '#b8b8b8',
  'Not specified':                    '#dddddd'
};
document.getElementById('zoning').onchange=e=>{
  if(zoneLayer){map.removeLayer(zoneLayer); zoneLayer=null;}
  document.getElementById('zonelegend').style.display = e.target.checked?'block':'none';
  if(e.target.checked){
    const seen=new Set();
    const lg=document.getElementById('zonelegend');
    lg.innerHTML='<b>Zoning of Bangkok — ผังเมืองรวม กทม.</b><br>';
    zoneLayer=L.geoJSON(ZONES,{style:f=>({color:'#666',weight:0.4,
        fillColor:ZCAT[f.properties.en]||'#eee',fillOpacity:0.35}),
      onEachFeature:(f,l)=>l.bindTooltip(`<b>${f.properties.zone||'-'}</b> ${f.properties.th}<br>${f.properties.en}`,{sticky:true})
    }).addTo(map);
    ZONES.features.forEach(f=>{
      const en=f.properties.en;
      if(seen.has(en)) return; seen.add(en);
      lg.innerHTML+=`<i style="width:14px;height:10px;float:left;margin:2px 6px 0 0;background:${ZCAT[en]||'#eee'}"></i>`
        +`${f.properties.zone||'&nbsp;'} — ${f.properties.th} / ${en}<br>`;
    });
  }
};
document.getElementById('publands').onchange=e=>{
  if(pubLayer){map.removeLayer(pubLayer); pubLayer=null;}
  if(e.target.checked){
    pubLayer=L.geoJSON(PUB,{style:{color:'#d00',weight:1.5,fillColor:'#ff0000',fillOpacity:0.5},
      onEachFeature:(f,l)=>{
        const p=f.properties;
        l.bindTooltip(
          `<b>${p.name}</b>`+
          (p.en?`<div style="color:#8b0000;font-size:11px">${p.en}</div>`:'')+
          (p.pub?`<div style="margin-top:3px"><b>public land:</b> ${p.zones_th}<br>`+
            `<span style="color:#8b0000;font-size:11px">${p.zones}</span></div>`:'')+
          (p.infra?`<div style="margin-top:3px"><b>infrastructure:</b> ${p.infra}</div>`:''),
          {sticky:true});
      }
    }).addTo(map);
  }
};
document.getElementById('legendbtn').onclick=()=>{
  const b=document.getElementById('legendbody');
  const up=b.style.display!=='none';
  b.style.display= up?'none':'block';
  document.getElementById('legendbtn').innerHTML= up?'&#9660;':'&#9650;';
};
let topLayer=null;
document.getElementById('top30').onchange=e=>{
  if(topLayer){map.removeLayer(topLayer); topLayer=null;}
  if(e.target.checked){
    topLayer=L.layerGroup(TOP30.map(p=>
      L.circleMarker([p.lat,p.lon],{radius:11,color:'#1b5e20',weight:2,fillColor:'#66bb6a',fillOpacity:0.9})
        .bindTooltip('#'+p.rank,{permanent:true,direction:'center',className:'ranknum'})
        .bindPopup(`<b>#${p.rank} · ${p.name_en}</b><div style="color:#0a5f73;font-size:11px">${p.th}</div>
          ${p.sname} · ${p.dname}<br>score <b>${p.score}</b> · affected ${p.aff}/10 · pop ${p.pop}`)))
      .addTo(map);
  }
};
function applyRankOnly(){
  const only=document.getElementById('rankonly').checked;
  if(only && rankLayer){
    if(layer){map.removeLayer(layer); layer=null;}   // rankings-only view: basemap + pins
  } else if(!layer){
    draw();
  }
}
document.getElementById('rankonly').onchange=applyRankOnly;
document.getElementById('rankbtn').onclick=()=>{
  const m=document.getElementById('rankpanel');
  const show=m.style.display==='none';
  m.style.display= show?'block':'none';
  if(!show){
    if(rankLayer){map.removeLayer(rankLayer); rankLayer=null;}
    document.querySelectorAll('input[name=rankset]').forEach(r=>r.checked=false);
    const d=document.getElementById('rankdesc');
    d.style.display='none'; d.innerHTML='';
    if(!layer) draw();                              // bring the choropleth back
  }
};
const RANKSETS = __RANKSETS__;
let rankLayer=null;
const rbox=document.getElementById('rankopts');
Object.entries(RANKSETS).forEach(([key,set])=>{
  const l=document.createElement('label'); l.style.cssText='display:block;font-size:12px;margin-top:3px;cursor:pointer';
  const r=document.createElement('input'); r.type='radio'; r.name='rankset'; r.value=key;
  const t=document.createElement('span'); t.textContent=' '+set.label;
  l.append(r,t); rbox.appendChild(l);
  r.onchange=()=>{
    showRank(key);
    const d=document.getElementById('rankdesc');
    d.innerHTML=`<b>${set.label}</b> — ${set.desc}`;
    d.style.display='block';
  };
});
function showRank(key){
  if(rankLayer){map.removeLayer(rankLayer); rankLayer=null;}
  const set=RANKSETS[key];
  const feats=set.items.map(it=>{
    const f=N.features.find(n=>n.properties.id===it.id);
    if(!f) return null;
    const b=L.geoJSON(f.geometry).getBounds();
    return b.isValid()?{...it, ctr:b.getCenter()}:null;
  }).filter(Boolean);
  rankLayer=L.layerGroup(feats.map(it=>{
    const t=Math.min(1,(it.rank-1)/29);
    const col=`hsl(8,78%,${Math.round(22+40*t)}%)`;   // rank 1 dark red -> rank 30 light
    const icon=L.divIcon({className:'',iconSize:[30,43],iconAnchor:[15,43],popupAnchor:[0,-40],
      html:`<svg width="30" height="43" viewBox="0 0 30 43">`+
           `<path d="M15 42 C 10 33 4 22 4 13 a11 11 0 1 1 22 0 C 26 22 20 33 15 42 Z"`+
           ` fill="${col}" stroke="#fff" stroke-width="1.5"/>`+
           `<circle cx="15" cy="13" r="6.5" fill="#fff"/>`+
           `<text x="15" y="16.8" text-anchor="middle" font-family="sans-serif"`+
           ` font-weight="700" font-size="10" fill="${col}">${it.rank}</text></svg>`});
    return L.marker(it.ctr,{icon}).bindPopup(
      `<b>#${it.rank} · ${it.en}</b>`+
      `<div style="color:#0a5f73;font-size:11px">${it.th}</div>`+
      `${it.sname} · ${it.dname}<br>`+
      `${set.label}: <b>${it.v}</b>`+
      (it.vlist&&it.vlist.length
        ?`<div style="margin-top:4px;text-align:left"><b>norms breached:</b>`+
         it.vlist.map(v=>`<div style="margin-top:2px">&bull; ${v}</div>`).join('')+
         `<div style="margin-top:3px;color:#666">community-level proxy — not per-building compliance</div></div>`
        :''));
  })).addTo(map);
  map.fitBounds(L.latLngBounds(feats.map(it=>it.ctr)).pad(0.15));
  applyRankOnly();
}
document.getElementById('methbtn').onclick=()=>{
  const m=document.getElementById('meth');
  m.style.display = m.style.display==='none' ? 'block' : 'none';
};
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
