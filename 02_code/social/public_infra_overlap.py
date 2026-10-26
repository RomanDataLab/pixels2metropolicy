"""social-economic sensing of slums — public-land / infrastructure coincidence.

Which slum neighborhoods (ชุมชนแออัด) physically coincide with:
  - public lands: comprehensive-plan zones ส (government / public utility),
    ศ.๑-ศ.๒ (Thai cultural conservation), ก.๑-ก.๓ (conservation rural and
    agricultural) — polygon INTERSECTS the zone (supersedes the older
    centroid-in-zone join in public_land_slums.csv);
  - infrastructure setback bands: legal encroachment bands from code_risk.csv
    (Ministerial Regulation 55 B.E. 2543 ข้อ 40-42 — 6 m public waterway,
    6 m public road, 30 m railway).

Inputs : slum_polygons.parquet, cmp_landuse_plan.gpkg, code_risk.csv
Output : 04_output/social_patterns/bangkok/public_infra_slums.csv

Run:  python public_infra_overlap.py
"""
from __future__ import annotations

import sys

import geopandas as gpd
import pandas as pd

from social_common import GAZETTEER_DIR, REPO, SOCIAL_OUT, ensure_dirs

PUBLIC_CATS = ["Government / public utility", "Thai cultural conservation",
               "Conservation rural and agricultural"]
INFRA_FLAGS = {"viol_water": "public waterway 6 m band",
               "viol_rail": "railway 30 m band",
               "viol_highway": "public road 6 m band"}


def main() -> int:
    ensure_dirs()

    poly = gpd.read_parquet(GAZETTEER_DIR / "slum_polygons.parquet")
    poly["cmt_id"] = poly["CMT_ID"].astype(str)
    poly["geometry"] = poly.geometry.buffer(0)

    # ---------- public lands: polygon intersects public-purpose zones ----------
    lu = gpd.read_file(REPO / "01_data/03_derived_vector/cmp_landuse_plan/cmp_landuse_plan.gpkg")
    pub = lu[lu["LU_CAT_EN"].isin(PUBLIC_CATS)][["LUP_ZONE", "LU_CAT_TH", "LU_CAT_EN", "geometry"]]
    pub = pub.to_crs(4326)
    pub["geometry"] = pub.geometry.buffer(0)
    joined = gpd.sjoin(poly, pub, predicate="intersects", how="inner")
    zone_map: dict[str, list[dict]] = {}
    for r in joined.itertuples():
        zone_map.setdefault(r.cmt_id, []).append(
            {"zone": str(r.LUP_ZONE), "th": str(r.LU_CAT_TH), "en": str(r.LU_CAT_EN)})
    print(f"public-land slums (polygon intersects): {len(zone_map)}")

    # ---------- infrastructure: setback-band flags from code_risk ----------
    cr = pd.read_csv(SOCIAL_OUT / "code_risk.csv", dtype={"cmt_id": str}).set_index("cmt_id")
    infra_map: dict[str, list[str]] = {}
    for cid, row in cr.iterrows():
        hits = [label for flag, label in INFRA_FLAGS.items() if int(row[flag]) > 0]
        if hits:
            infra_map[cid] = hits
    print(f"infrastructure-band slums: {len(infra_map)} "
          f"(water {int(cr.viol_water.sum())}, rail {int(cr.viol_rail.sum())}, "
          f"road {int(cr.viol_highway.sum())})")

    # ---------- combined table ----------
    ids = sorted(set(zone_map) | set(infra_map))
    base = poly.drop_duplicates("cmt_id").set_index("cmt_id")
    out = pd.DataFrame({
        "cmt_id": ids,
        "CMT_NAME": [base.at[i, "CMT_NAME"] for i in ids],
        "SNAME": [base.at[i, "SNAME"] for i in ids],
        "DNAME": [base.at[i, "DNAME"] for i in ids],
        "POP_TOTAL": [int(base.at[i, "POP_TOTAL"]) for i in ids],
        "on_public_land": [int(i in zone_map) for i in ids],
        "zones_th": ["; ".join({z["th"] for z in zone_map.get(i, [])}) for i in ids],
        "zones_en": ["; ".join({z["en"] for z in zone_map.get(i, [])}) for i in ids],
        "zone_codes": ["; ".join({z["zone"] for z in zone_map.get(i, [])}) for i in ids],
        "in_infra_band": [int(i in infra_map) for i in ids],
        "infra": ["; ".join(infra_map.get(i, [])) for i in ids],
    })
    out.to_csv(SOCIAL_OUT / "public_infra_slums.csv", index=False, encoding="utf-8-sig")
    print(f"combined (public land OR infrastructure band): {len(out)} of {len(base)} slums")
    print(f"  both: {(out.on_public_land & out.in_infra_band).sum()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
