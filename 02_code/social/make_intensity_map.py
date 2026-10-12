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
CATEGORIES = ["natural_disaster", "technical_disaster", "traffic_incident", "crime",
              "prostitution", "street_retail_popup", "begging_homeless"]
RAMP = ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c"]
SIMPLIFY_TOL = 0.0004
TYPE_EN = {"ชุมชนแออัด": "slum community", "ชุมชนเมือง": "urban community",
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
            "tg_total": int(tg_total.get(cid, 0)),
            "tg_counts": {k: int(tg_counts.loc[cid, k]) for k in CATEGORIES}
                         if cid in tg_counts.index else {},
            "events": tip_events.get(cid, []),
        }
        feats.append({"type": "Feature", "geometry": mapping(c.geometry),
                      "properties": props})

    khet = (json.loads(Path(KHER_GEOJSON).read_text(encoding="utf-8"))
            if KHER_GEOJSON.exists() else {"type": "FeatureCollection", "features": []})

    html = (HTML
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
<h3 style="margin:4px 0">social-economic sensing of slums methodology</h3>
<p>Social-signal layer geolocating news, official complaints and public social media
to Bangkok's 1,993 BMA-registered communities (626 slums). 92-day rolling window.</p>

<h4>Step 1 — Gazetteer (name-matching dictionary)</h4>
<p>Thai name variants built from the official BMA community polygons: full and
prefix-stripped slum names, landmarks (canals, roads, temples) mined from the
address and N/S/E/W adjacency text, khwaeng and district names, 46 romanized
district names (geoBoundaries ADM2 spatial match) and 37 famous-area aliases
(Sukhumvit, Khaosan, Klong Toey&hellip;). 5,120 variants over 626 slums.</p>

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
(one per khwaeng, top-40 slums by population). Article links resolved where
robots.txt allows; Google News items remain snippet-only (JavaScript redirects).
Headlines carry the location signal in Thai local reporting.</p>

<h4>Step 5 — Social media</h4>
<p>Pantip public search threads and Telegram public channel previews
(t.me/s/), Thai-language channels prioritized (Thai script matches the
gazetteer). Telegram policy: only channels with 5,000+ verified followers,
with an exemption for Thai-language channels; subscriber counts cross-checked
against independent crawlers because t.me serves decoy counts to scrapers.</p><p><b>Telegram chat groups (deferred):</b> the large Bangkok communities
(Бангкок Общение ~14K, Чат Бангкок B-G ~12K, Бангкок Таиланд Чат ~7.5K members,
Russian-language) are groups without public web previews. Ingestion is prepared
via the official MTProto API (Telethon, read-only, PII stripped —
fetch_telethon.py) and awaits account API credentials; group handles are
registered with status "deferred_telethon" in the source registry.</p>

<h4>Step 6 — Event extraction</h4>
<p>Open-source Thai NLP (pythainlp tokenization) plus a keyword lexicon
classifying texts into seven categories: natural disaster, technical disaster,
traffic incident, crime, adult industry, street retail &amp; popup markets,
begging &amp; homelessness. Thai texts machine-translated to English for display
(DeepSeek, batch).</p>

<h4>Step 7 — Geolocation tiers</h4>
<p>T1 slum name + khwaeng/district both in text (0.9) &middot; T2 slum name alone (0.7)
&middot; T3 khwaeng/district only, distributed across its slums by population share (0.4)
&middot; T4 landmark only (0.3). Known limit: headlines rarely name slums directly,
so T3 dominates; slum-level precision comes from Traffy GPS pins.</p>

<h4>Step 8 — Aggregation &amp; map</h4>
<p>Weighted event counts per community; color intensity = event count
(sqrt-scaled, 50% max opacity); white = no events. BMA risk-area registry
(fiscal year 2568) overlaid as reference pins. Grey-tone OSM basemap.</p>

<h4>References (Harvard)</h4>
<ol style="padding-left:16px;margin:4px 0">
<li>Bangkok Metropolitan Administration (2026) <i>ขอบเขตชุมชน (ตรวจสอบแล้ว) [Verified community boundaries]</i>. Available at: https://cpudgiapp.bangkok.go.th/arcgis/rest/services/Community/Service_Community/FeatureServer/14 (Accessed: 8 October 2026).</li>
<li>Bangkok Metropolitan Administration (2026) <i>บัญชีพื้นที่เสี่ยงและพื้นที่อันตราย กทม. ปีงบประมาณ 2568 [BMA risk and danger-area registry, FY 2568]</i>, สํานักเทศกิจ. Available at: https://data.bangkok.go.th/dataset/ced48 (Accessed: 8 October 2026).</li>
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
<li>PyThaiNLP (2024) <i>PyThaiNLP: Thai natural language processing toolkit</i>. Available at: https://pythainlp.github.io (Accessed: 8 October 2026).</li>
</ol>
"""


HTML = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>social-economic sensing of slums — neighborhood category intensity</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  body{margin:0;font-family:sans-serif}
  .leaflet-tile-pane{filter:grayscale(1)}   /* grey-tone OSM background */
  #map{position:absolute;top:0;bottom:0;right:0;left:0}
  .panel{position:absolute;top:10px;right:10px;z-index:1000;background:#fff;
         padding:10px 14px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.3);max-width:320px}
  h1{font-size:15px;margin:0 0 8px}
  .note{font-size:11px;color:#555;margin-top:6px}
  label{display:block;font-size:13px;margin-top:4px}
  .cats label{display:flex;align-items:center;gap:8px;font-size:13px;padding:2px 0;cursor:pointer}
  .sw{width:16px;height:12px;border:1px solid #666;flex:none}
</style>
</head>
<body>
<div id="map"></div>
<div class="panel">
  <h1>social-economic sensing of slums — events per neighborhood (ชุมชน)</h1>
  <div class="cats" id="cats"></div>
  <label><input type="checkbox" id="khet"/> khet (district) outlines</label>
  <label><input type="checkbox" id="slumonly"/> slum communities only</label>
  <label><input type="checkbox" id="risk"/> BMA risk areas (2568)</label>
  <button id="methbtn" type="button"
    style="margin-top:8px;width:100%;padding:4px 8px;border:1px solid #2b6cb0;border-radius:6px;
           background:#2b6cb0;color:#fff;cursor:pointer;font-size:13px">Methodology</button>
  <div id="meth" style="display:none;max-height:56vh;overflow:auto;margin-top:8px;
       border-top:1px solid #ccc;padding-top:6px;font-size:12px;line-height:1.45;text-align:left">
__METHOD__
  </div>
  <div class="note">Darker/more opaque = more events. White = no events.
  Fills at 50% transparency. 92-day window.</div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const N = __COMMUNITY_GEOJSON__;
const KH = __KHET_GEOJSON__;
const RISK = __RISK_PINS__;
const CATS = __CATS__;
const LABELS = { prostitution: 'adult industry' };
const COLORS = {
  natural_disaster:   '#1f78b4',
  technical_disaster: '#ff7f00',
  traffic_incident:   '#6a3d9a',
  crime:              '#e31a1c',
  prostitution:       '#c51b8a',
  street_retail_popup:'#33a02c',
  begging_homeless:   '#8c6d31'
};
const map = L.map('map').setView([13.75, 100.52], 12);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  {maxZoom:19, attribution:'&copy; OpenStreetMap contributors'}).addTo(map);

let layer=null, khetLayer=null, riskLayer=null, currentCat='natural_disaster';

const box=document.getElementById('cats');
CATS.forEach(c=>{
  const l=document.createElement('label');
  const r=document.createElement('input'); r.type='radio'; r.name='cat'; r.value=c;
  if(c===currentCat) r.checked=true;
  const sw=document.createElement('span'); sw.className='sw';
  sw.style.background=COLORS[c];
  const t=document.createElement('span'); t.textContent=LABELS[c]||c;
  l.append(r,sw,t); box.appendChild(l);
  r.onchange=()=>{currentCat=c; draw();};
});

function style(cat){
  const mx=Math.max(...N.features.map(f=>f.properties.counts[cat]||0),1);
  return f=>{
    const v=f.properties.counts[cat]||0;
    const slum=f.properties.type==='ชุมชนแออัด';
    if(v===0) return {color:'#999',weight:0.4,fillColor:'#ffffff',fillOpacity:0.25};
    const op=Math.min(0.5, 0.1+0.4*Math.sqrt(v/mx));   // max 50% opacity
    return {color:COLORS[cat],weight:0.8,fillColor:COLORS[cat],fillOpacity:op};
  };
}
function tipHtml(f){
  const p=f.properties, c=p.counts, cat=currentCat;
  if(!p.total) return null;                       // no hover on no-event polygons
  const en=p.name_en?`<div style="color:#0a5f73;font-size:11px">${p.name_en}</div>`:'';
  const head=`<b>${p.name}</b>${en}<span style="color:#666">(${p.type_en||p.type}) · ${p.sname} · ${p.dname}</span>`;
  const row=`${LABELS[cat]||cat}: <b>${c[cat]||0}</b> · total: <b>${p.total}</b> · docs: <b>${p.n_docs}</b>`;
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
  // tooltips only where events exist; content follows the selected category
  layer.eachLayer(l=>{
    const h=tipHtml(l.feature);
    if(h) l.setTooltipContent(h); else l.unbindTooltip();
  });
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
