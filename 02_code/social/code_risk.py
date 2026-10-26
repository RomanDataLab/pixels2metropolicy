"""social-economic sensing step — construction-code proximity risk (proxy).

Thai building-code setbacks (Ministerial Regulation 55 B.E. 2543, ข้อ 40-42):
  - public waterways (คลองสาธารณะ): 3 m bank setback if <10 m wide, 6 m if >=10 m
  - public roads: 3-6 m by width (2 m if >20 m wide)
  - railways: 30 m from track centreline (Rail Transport Act practice)
Without per-building geometry we compute a COMMUNITY-LEVEL PROXY: polygon
distance to OSM railways/waterways/trunk roads + comprehensive-plan industrial
zones, and whether the community sits inside the setback band of each feature
class (polygon within threshold distance of the feature = buildings at the
community edge plausibly encroach).

Inputs : 05_scratch/overpass/{rail,water}_*.json (cached), Overpass (highways),
         cmp_landuse_plan.gpkg (industrial), slum_polygons.parquet
Output : 04_output/social_patterns/bangkok/code_risk.csv

Run:  python code_risk.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd

from social_common import GAZETTEER_DIR, REPO, SOCIAL_OUT, ensure_dirs, polite_get

OVERPASS = REPO / "05_scratch" / "overpass"
SETBACK = {"water": 6.0, "rail": 30.0, "highway": 6.0}   # metres (see docstring)
INDUSTRIAL_BUFFER = 100.0                                 # nuisance zone, not law
W = {"water": 0.35, "rail": 0.35, "highway": 0.15, "industrial": 0.15}


def osm_layer(name: str, overpass_query: str) -> gpd.GeoDataFrame:
    cache = OVERPASS / f"{name}_100.30_13.40_100.95_13.95.json"
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        import requests as _rq
        data = None
        for url in ("https://overpass-api.de/api/interpreter",
                    "https://overpass.kumi.systems/api/interpreter"):
            try:
                r = polite_get(url, params={"data": overpass_query}, timeout=180, retries=2)
                if r.status_code == 200 and r.text.lstrip().startswith("{"):
                    data = r.json()
                    break
            except Exception:
                continue
        if data is None:
            raise RuntimeError(f"overpass failed for {name}")
        time.sleep(2)
        cache.write_text(json.dumps(data), encoding="utf-8")
        time.sleep(1)
    feats = data.get("elements", [])
    geoms, ids = [], []
    for e in feats:
        if e.get("type") == "way" and "geometry" in e:
            from shapely.geometry import LineString
            geoms.append(LineString([(p["lon"], p["lat"]) for p in e["geometry"]]))
            ids.append(e.get("id"))
    g = gpd.GeoDataFrame({"id": ids}, geometry=geoms, crs=4326)
    return g


def main() -> int:
    ensure_dirs()
    poly = gpd.read_parquet(GAZETTEER_DIR / "slum_polygons.parquet")
    poly["cmt_id"] = poly["CMT_ID"].astype(str)
    poly = poly.set_index("cmt_id")
    pu = poly.to_crs(32647)
    pu["geometry"] = pu.geometry.buffer(0)

    rail = osm_layer("rail", """
[out:json][timeout:180];(way["railway"~"rail|light_rail"](13.40,100.30,13.95,100.95););out geom;""")
    water = osm_layer("water", """
[out:json][timeout:180];(way["waterway"~"canal|river|stream"](13.40,100.30,13.95,100.95););out geom;""")
    # highways: NGIS layer already in repo (Overpass is rate-limited today)
    import re as _re
    hw_js = (REPO / "02_code/app/data/highways.js").read_text(encoding="utf-8", errors="replace")
    m = _re.search(r'"type":"FeatureCollection","features":(\[.*\])\}', hw_js, _re.S)
    hw_fc = json.loads('{"type":"FeatureCollection","features":' + m.group(1) + '}')
    from shapely.geometry import shape
    hw_geoms = [shape(f["geometry"]).simplify(0.0005) for f in hw_fc["features"]
                if f.get("geometry")]
    highway = gpd.GeoDataFrame({"id": range(len(hw_geoms))},
                               geometry=hw_geoms, crs=4326)
    print(f"osm layers: rail={len(rail)} water={len(water)} highway={len(highway)}")

    ind = gpd.read_file(REPO / "01_data/03_derived_vector/cmp_landuse_plan/cmp_landuse_plan.gpkg")
    ind = ind[ind.to_crs(4326).geometry.notna()]
    ind_m = ind.to_crs(32647)

    def dists(layer: gpd.GeoDataFrame):
        u = layer.to_crs(32647)
        ugs = u.geometry.union_all()
        return pu.geometry.distance(ugs)

    d = pd.DataFrame(index=pu.index)
    for name, layer in (("water", water), ("rail", rail), ("highway", highway)):
        d[f"dist_{name}"] = dists(layer).round(1)
    ind_ugs = ind_m.geometry.union_all()
    d["dist_industrial"] = pu.geometry.distance(ind_ugs).round(1)

    # violation-adjacency flags + severity by inverse distance
    risk = pd.DataFrame(index=d.index)
    for name, thr in SETBACK.items():
        col = f"dist_{name}"
        band = d[col] <= thr                       # community inside setback band
        sev = (thr - d[col]).clip(lower=0) / thr   # 0..1 closer = higher
        risk[f"viol_{name}"] = band.astype(int)
        risk[f"sev_{name}"] = sev.round(3)
    risk["viol_industrial"] = (d["dist_industrial"] <= INDUSTRIAL_BUFFER).astype(int)
    risk["sev_industrial"] = ((INDUSTRIAL_BUFFER - d["dist_industrial"])
                              .clip(lower=0) / INDUSTRIAL_BUFFER).round(3)

    risk["code_risk"] = (risk["viol_water"] * W["water"] * (0.5 + 0.5 * risk["sev_water"])
                         + risk["viol_rail"] * W["rail"] * (0.5 + 0.5 * risk["sev_rail"])
                         + risk["viol_highway"] * W["highway"] * (0.5 + 0.5 * risk["sev_highway"])
                         + risk["viol_industrial"] * W["industrial"] * (0.5 + 0.5 * risk["sev_industrial"])
                         ).round(3)
    risk["viol_count"] = risk[["viol_water", "viol_rail", "viol_highway", "viol_industrial"]].sum(axis=1)

    out = risk.reset_index()
    for c in d.columns:
        out[c] = d[c].values
    out.to_csv(SOCIAL_OUT / "code_risk.csv", index=False, encoding="utf-8-sig")
    print(f"communities: {len(out)}; with >=1 setback band: {(out.viol_count>0).sum()}")
    print(out.sort_values("code_risk", ascending=False).head(8)
          [["cmt_id", "code_risk", "viol_count", "dist_water", "dist_rail", "dist_highway", "dist_industrial"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
