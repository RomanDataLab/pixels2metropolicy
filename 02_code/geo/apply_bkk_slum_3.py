# -*- coding: utf-8 -*-
"""Apply the curated bkk_slum_3.geojson (QGIS-cleaned, EPSG:32647) to the web data.

The 2026-10-28 QGIS export is the ground truth for site bkk_slum_3: manual
edits removed water/false detections and added new ones (1,527 features).
This script propagates it to:

  labeling/qgis_project/bkk_slum_3_wgs84.geojson   reprojected copy (4326)
  labeling/qgis_project/checkcadaster_roofs.geojson  site-3 subset replaced,
                                                    ov flag recomputed against
                                                    overture_bkk_sites.geojson
  labeling/qgis_project/checkcadaster_sites.json     site-3 counts/bbox updated

Run:  py -3.13 02_code/geo/apply_bkk_slum_3.py
"""
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
QGIS = ROOT / "labeling" / "qgis_project"

SRC = QGIS / "bkk_slum_3.geojson"            # UTM 32647, curated
OV = QGIS / "overture_bkk_sites.geojson"      # WGS84, near-site footprints
OUT_WGS = QGIS / "bkk_slum_3_wgs84.geojson"
ROOFS = QGIS / "checkcadaster_roofs.geojson"
SITES = QGIS / "checkcadaster_sites.json"

SITE = "bkk_slum_3"
T = Transformer.from_crs("EPSG:32647", "EPSG:4326", always_xy=True)


def r6(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 6), round(coords[1], 6)]
    return [r6(c) for c in coords]


def to_wgs(coords):
    if isinstance(coords[0], (int, float)):
        return T.transform(coords[0], coords[1])
    return [to_wgs(c) for c in coords]


def main() -> None:
    src = json.loads(SRC.read_text(encoding="utf-8"))
    feats = src["features"]
    print(f"curated site-3 detections: {len(feats)}")

    wgs = [{"type": "Feature", "properties": f["properties"],
            "geometry": {"type": f["geometry"]["type"], "coordinates": r6(to_wgs(f["geometry"]["coordinates"]))}}
           for f in feats]
    OUT_WGS.write_text(json.dumps({"type": "FeatureCollection", "features": wgs}, separators=(",", ":")), encoding="utf-8")
    print(f"written {OUT_WGS.name} (4326)")

    ov = json.loads(OV.read_text(encoding="utf-8"))["features"]
    geoms = [shape(f["geometry"]) for f in ov]
    tree = STRtree(geoms)

    out3, ov_hits = [], 0
    minx = miny = 1e9; maxx = maxy = -1e9
    for f in wgs:
        g = shape(f["geometry"])
        hit = any(geoms[i].intersects(g) for i in tree.query(g))
        ov_hits += hit
        xs, ys = g.bounds[0], g.bounds[1]
        b = g.bounds
        minx = min(minx, b[0]); miny = min(miny, b[1]); maxx = max(maxx, b[2]); maxy = max(maxy, b[3])
        out3.append({"type": "Feature",
                     "properties": {"site": SITE, "area_m2": f["properties"].get("area_m2"),
                                    "nb_20": None, "ov": 1 if hit else 0},
                     "geometry": f["geometry"]})
    print(f"ov overlap: {ov_hits}/{len(out3)}")

    roofs = json.loads(ROOFS.read_text(encoding="utf-8"))
    roofs["features"] = [f for f in roofs["features"] if f["properties"]["site"] != SITE] + out3
    ROOFS.write_text(json.dumps(roofs, separators=(",", ":")), encoding="utf-8")
    print(f"checkcadaster_roofs total: {len(roofs['features'])}")

    sites = json.loads(SITES.read_text(encoding="utf-8"))
    for s in sites:
        if s["site"] == SITE:
            s["roofs"] = len(out3)
            s["ov"] = ov_hits
            s["bbox"] = [minx, miny, maxx, maxy]
    SITES.write_text(json.dumps(sites, separators=(",", ":")), encoding="utf-8")
    print("sites.json updated")


if __name__ == "__main__":
    main()
