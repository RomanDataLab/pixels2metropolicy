# -*- coding: utf-8 -*-
"""Drop roofs whose centroid falls inside an OSM water polygon (river / lake).

Bangkok detections include false positives on the Chao Phraya and in lakes
(barges, raft structures). A roof centroid inside mapped open water is not a
slum house on land -> drop it.

Inputs:
  05_scratch/bkk_water_overpass.json   OSM natural=water (Overpass, out geom)
  labeling/qgis_project/checkcadaster_roofs.geojson
  labeling/qgis_project/checkcadaster_sites.json
  labeling/qgis_project/slum_roofs_red_v12.geojson  (for slum.html site layer)

Outputs (rewritten in place):
  checkcadaster_roofs.geojson   water roofs removed
  checkcadaster_sites.json      roof / ov counts updated
  bkk_slum_3_v12_wgs84.geojson  slum.html layer, water roofs removed

Run:  py -3.13 02_code/geo/drop_water_roofs.py
"""
import json
from pathlib import Path

from shapely.geometry import Polygon, MultiPolygon, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
QGIS = ROOT / "labeling" / "qgis_project"
WATER = ROOT / "05_scratch" / "bkk_water_overpass.json"

ROOFS = QGIS / "checkcadaster_roofs.geojson"
SITES = QGIS / "checkcadaster_sites.json"
V12 = QGIS / "slum_roofs_red_v12.geojson"
SITE3 = QGIS / "bkk_slum_3_v12_wgs84.geojson"


def water_polygons():
    d = json.loads(WATER.read_text(encoding="utf-8"))
    polys = []
    for e in d["elements"]:
        if e["type"] == "way" and "geometry" in e:
            ring = [(g["lon"], g["lat"]) for g in e["geometry"]]
            if len(ring) >= 4 and ring[0] == ring[-1]:
                p = Polygon(ring)
                if p.is_valid and p.area > 0:
                    polys.append(p)
        elif e["type"] == "relation" and "members" in e:
            rings = []
            for m in e["members"]:
                if m.get("type") == "way" and "geometry" in m:
                    ring = [(g["lon"], g["lat"]) for g in m["geometry"]]
                    if len(ring) >= 4 and ring[0] == ring[-1]:
                        rings.append(ring)
            if rings:
                try:
                    p = MultiPolygon([Polygon(r) for r in rings])
                    p = p.buffer(0)
                    if not p.is_empty:
                        polys.append(p)
                except Exception:
                    pass
    return [p for p in polys if p.area > 1e-7]  # >~1e-7 deg2 ~ 10 m2


def main() -> None:
    polys = water_polygons()
    print(f"water polygons: {len(polys)}")
    tree = STRtree(polys)

    def in_water(geom):
        c = geom.centroid
        return any(polys[i].covers(c) for i in tree.query(c))

    roofs = json.loads(ROOFS.read_text(encoding="utf-8"))
    feats = roofs["features"]
    kept, dropped = [], 0
    per_site_dropped = {}
    for f in feats:
        g = shape(f["geometry"])
        if in_water(g):
            dropped += 1
            s = f["properties"]["site"]
            per_site_dropped[s] = per_site_dropped.get(s, 0) + 1
        else:
            kept.append(f)
    print(f"checkcadaster roofs: {len(feats)} -> {len(kept)} (dropped {dropped})")
    print("dropped per site:", per_site_dropped)
    ROOFS.write_text(json.dumps({"type": "FeatureCollection", "features": kept}, separators=(",", ":")), encoding="utf-8")

    sites = json.loads(SITES.read_text(encoding="utf-8"))
    for s in sites:
        mine = [f for f in kept if f["properties"]["site"] == s["site"]]
        s["roofs"] = len(mine)
        s["ov"] = sum(1 for f in mine if f["properties"]["ov"])
    SITES.write_text(json.dumps(sites, separators=(",", ":")), encoding="utf-8")
    print("sites.json updated")

    v12 = json.loads(V12.read_text(encoding="utf-8"))
    sub = []
    d3 = 0
    for f in v12["features"]:
        if f["properties"].get("site") != "bkk_slum_3":
            continue
        if in_water(shape(f["geometry"])):
            d3 += 1
        else:
            sub.append(f)
    SITE3.write_text(json.dumps({"type": "FeatureCollection", "features": sub}, separators=(",", ":")), encoding="utf-8")
    print(f"bkk_slum_3_v12 layer: kept {len(sub)}, dropped {d3}")


if __name__ == "__main__":
    main()
