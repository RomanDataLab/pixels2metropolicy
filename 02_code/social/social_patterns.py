"""slum_pulse step 8 — per-slum social/economic pattern aggregation.

Inputs:
  gazetteer/slum_polygons.parquet   (626 BMA slum polygons, POP_TOTAL)
  social/events.parquet             (tiered news/social events)
  social/traffy_reports.jsonl       (pin-level complaints)
  social/official/official_stats.parquet  (province-level covariates)
  open-stack communities_gee.csv    (DARK_IDX, optional, if open-stack step 6 ran)

Outputs (04_output/social_patterns/bangkok/):
  slum_social_profile.csv + .geojson   per-slum indicators, key CMT_ID
  event_timeseries_weekly.csv          weekly city-wide counts by event type
  match_quality_report.md              tier distribution + sample for human skim

Run:  python social_patterns.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from social_common import GAZETTEER_DIR, SOCIAL_OUT, SOCIAL_RAW, ensure_dirs, read_jsonl

NEAR_SLUM_M = 150  # pins this close to a polygon count as "near"


def main() -> int:
    ensure_dirs()
    poly = gpd.read_parquet(GAZETTEER_DIR / "slum_polygons.parquet").set_index("CMT_ID")
    poly["geometry"] = poly.geometry.buffer(0)

    # ---------- events ----------
    ev = pd.read_parquet(SOCIAL_RAW / "events.parquet")
    ev = ev[ev["event_type"].notna()]
    print(f"events rows (classified): {len(ev)}")
    ev["date"] = pd.to_datetime(ev["pubdate"], errors="coerce", utc=True)

    # per-doc weight so one article fanning out to N slums still weighs ~1 doc
    doc_slum_count = ev[ev["cmt_id"].notna()].groupby("doc_id")["cmt_id"].nunique()
    ev["doc_share"] = ev.apply(
        lambda r: 1.0 / doc_slum_count[r["doc_id"]]
        if r["cmt_id"] in doc_slum_count.index and r["cmt_id"] is not None else None, axis=1)

    # T1/T2/T4: cmt_id rows get confidence weight
    direct = ev[ev["cmt_id"].notna()].copy()
    direct["weight"] = direct["confidence"]

    # T3: distribute across slums of the khwaeng (or district) by population share
    t3 = ev[ev["tier"] == "T3"].copy()
    kpop = poly.groupby("SNAME")["POP_TOTAL"].sum()
    dpop = poly.groupby("DNAME")["POP_TOTAL"].sum()
    t3_rows = []
    for _, r in t3.iterrows():
        kw = r["khwaeng"] or None
        dist = r["district"] or None
        if kw and kw in kpop.index and kpop[kw] > 0:
            members = poly[poly["SNAME"] == kw]
            total = kpop[kw]
        elif dist and dist in dpop.index and dpop[dist] > 0:
            members = poly[poly["DNAME"] == dist]
            total = dpop[dist]
        else:
            continue
        for cid, pop in members["POP_TOTAL"].items():
            t3_rows.append({**r.to_dict(), "cmt_id": cid,
                            "weight": r["confidence"] * (pop / total)})
    t3w = pd.DataFrame(t3_rows)
    weighted = pd.concat([direct[["doc_id", "cmt_id", "event_type", "source", "publisher",
                                  "date", "tier", "weight", "doc_share"]],
                          t3w[["doc_id", "cmt_id", "event_type", "source", "publisher",
                               "date", "tier", "weight", "doc_share"]]], ignore_index=True)
    weighted = weighted[weighted["cmt_id"].isin(poly.index)]
    print(f"weighted event assignments: {len(weighted)} over {weighted['cmt_id'].nunique()} slums")

    piv = (weighted.pivot_table(index="cmt_id", columns="event_type",
                                values="weight", aggfunc="sum", fill_value=0)
           .rename(columns=lambda c: f"ev_{c}"))
    docs = (weighted.groupby("cmt_id")
            .agg(n_docs=("doc_id", "nunique"),
                 n_sources=("publisher", "nunique"),
                 mean_conf=("weight", "mean")))

    # ---------- traffy pins ----------
    pins = read_jsonl(SOCIAL_RAW / "traffy_reports.jsonl")
    tg = gpd.GeoDataFrame(
        [{"ts": p["ts"], "types": p["complaint_types"], "text": p["text"]}
         for p in pins],
        geometry=[Point(p["lon"], p["lat"]) for p in pins], crs=4326)
    joined = gpd.sjoin(tg, poly.reset_index()[["CMT_ID", "geometry"]],
                       how="inner", predicate="within")
    near = gpd.sjoin_nearest(tg.to_crs(32647),
                             poly.reset_index()[["CMT_ID", "geometry"]].to_crs(32647)
                             .assign(geometry=lambda g: g.geometry.buffer(NEAR_SLUM_M)),
                             how="inner", max_distance=NEAR_SLUM_M).to_crs(4326)
    near_ids = set(near["index_right"].astype(int)) | set(
        joined.index.astype(int))
    traffy_counts = joined.groupby("CMT_ID").size().rename("traffy_reports")
    joined["ctype"] = joined["types"].map(lambda t: t[0] if t else "other")
    traffy_piv = (joined.pivot_table(index="CMT_ID", columns="ctype",
                                     values="geometry", aggfunc="count", fill_value=0)
                  .rename(columns=lambda c: f"traffy_{c}"))
    # same-taxonomy segmentation of complaint types (event_lexicon.yaml traffy_map)
    import yaml
    from pathlib import Path as _P
    lex = yaml.safe_load(open(_P(__file__).resolve().parent / "event_lexicon.yaml", encoding="utf-8"))
    tmap = lex.get("traffy_map", {})

    def map_ctype(ct: str) -> str:
        for cat, kws in tmap.items():
            if any(k in ct for k in kws):
                return cat
        return "other"

    joined["ccat"] = joined["ctype"].map(map_ctype)
    traffy_cat_piv = (joined.pivot_table(index="CMT_ID", columns="ccat",
                                         values="geometry", aggfunc="count", fill_value=0)
                      .rename(columns=lambda c: f"traffy_cat_{c}"))
    print("traffy complaint categories:",
          joined["ccat"].value_counts().to_dict())
    print(f"traffy pins: {len(tg)} total, {joined['CMT_ID'].nunique()} slums w/ pin inside, "
          f"{len(near_ids)} pins within {NEAR_SLUM_M}m of any slum")

    # ---------- covariates ----------
    prof = poly[["CMT_NAME", "DNAME", "SNAME", "POP_TOTAL", "HOUSEHOLD", "AREA_SQM"]].copy()
    prof = prof.join(piv).join(docs).join(traffy_counts).join(traffy_piv).join(traffy_cat_piv)
    prof["traffy_reports"] = prof["traffy_reports"].fillna(0)

    off = SOCIAL_RAW / "official" / "official_stats.parquet"
    if off.exists():
        o = pd.read_parquet(off)
        bkk = o[o["geo_name"].astype(str).str.contains("กรุงเทพ")]
        for _, r in bkk.iterrows():
            col = f"off_{r['source'].split('/')[-1]}_{str(r['indicator'])[:30]}"
            prof[col] = r["value"]
        print(f"official covariates attached: {len(bkk)} bangkok rows")

    gee = SOCIAL_OUT.parent.parent / "open_stack" / "bangkok" / "communities_gee.csv"
    if gee.exists():
        g = pd.read_csv(gee)
        col = [c for c in g.columns if "DARK" in c.upper()]
        if col and "CMT_ID" in g.columns:
            prof = prof.join(g.set_index("CMT_ID")[col])
            print(f"DARK_IDX attached from open-stack: {col}")
    else:
        print("no open-stack communities_gee.csv yet (expected — pixel pipeline not run)")

    # rates per 1,000 population
    for c in list(prof.columns):
        if c.startswith(("ev_", "traffy")):
            prof[f"{c}_per1k"] = (prof[c] / prof["POP_TOTAL"].replace(0, pd.NA) * 1000).round(2)

    prof = prof.fillna({c: 0 for c in prof.columns if c.startswith(("ev_", "n_", "traffy"))})
    prof.round(3).to_csv(SOCIAL_OUT / "slum_social_profile.csv", encoding="utf-8-sig")

    out_geo = poly.join(prof.drop(columns=["CMT_NAME", "DNAME", "SNAME", "POP_TOTAL",
                                           "HOUSEHOLD", "AREA_SQM"], errors="ignore"))
    out_geo.to_file(SOCIAL_OUT / "slum_social_profile.geojson", driver="GeoJSON")

    # weekly time series (city-wide)
    wk = (weighted.dropna(subset=["date"])
          .assign(week=lambda d: d["date"].dt.strftime("%G-W%V"))
          .groupby(["week", "event_type"])["weight"].sum().reset_index())
    wk.pivot(index="week", columns="event_type", values="weight").fillna(0).round(2) \
      .to_csv(SOCIAL_OUT / "event_timeseries_weekly.csv", encoding="utf-8-sig")

    # ---------- match-quality report ----------
    tier_counts = ev.groupby("tier").size()
    rep = ["# slum_pulse match-quality report",
           f"generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
           "## tier distribution (classified events)", "",
           tier_counts.to_string(), "",
           f"## gates",
           f"1. gazetteer variants: built earlier, 30-variant manual check done at build time",
           f"2. human skim sample: 20 random T1/T2 matches below — precision target >= 0.6",
           f"3. lexicon per-category precision: category counts below, manual review pending",
           "", "## sample T1/T2 matches (human skim)", ""]
    sample = ev[ev["tier"].isin(["T1", "T2"])].sample(n=min(20, len(ev)), random_state=7)
    for r in sample.itertuples():
        rep.append(f"- [{r.tier}] {r.variant} -> {r.cmt_id} | {r.event_type} | {str(r.title)[:80]}")
    rep += ["", "## event_type counts", "", ev["event_type"].value_counts().to_string(), "",
            "## notes",
            "- T1/T2/T4 rows carry cmt_id directly; T3 distributed by khwaeng population share.",
            "- Traffy public endpoint gives rolling ~100 shared reports (2022-2026), not full history.",
            "- Google News items are snippet-only (JS redirects); titles carry the location signal.",
            "- BMA CKAN geo-blocked; official covariates from gdcatalog only."]
    (SOCIAL_OUT / "match_quality_report.md").write_text("\n".join(rep), encoding="utf-8")

    print(f"\nprofile rows: {len(prof)}, slums w/ any signal: "
          f"{(prof.filter(regex='^(ev_|traffy|n_)').sum(axis=1) > 0).sum()}")
    print(f"outputs: {SOCIAL_OUT}\\{{slum_social_profile.csv, .geojson, event_timeseries_weekly.csv, match_quality_report.md}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
