# -*- coding: utf-8 -*-
"""Prep data for checkcadaster.html — red slum roofs vs Overture buildings.

Inputs:
  labeling/qgis_project/slum_roofs_red_v12.geojson       (red houses, all sites)
  01_data/03_derived_vector/buildings/bangkok_buildings_overture.parquet

Outputs (labeling/qgis_project/):
  checkcadaster_roofs.geojson   Bangkok-site red roofs + ov flag (1 = overlaps
                                an Overture footprint, 0 = no Overture overlap
                                -> potentially irregular)
  checkcadaster_sites.json      per-site: name, roof count, ov share, bbox

Overture buildings for the map view are emitted per site with the roofs file
parents in web/js? No - single layer file:
  overture_bkk_sites.geojson    Overture footprints clipped to site windows
                                (roof bbox + ~200 m buffer), 6-dp precision

Run:  py -3.13 02_code/geo/prep_checkcadaster.py
"""
import json
from pathlib import Path

import pyarrow.parquet as pq
from shapely import wkb as shp_wkb
from shapely.geometry import box
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
QGIS = ROOT / "labeling" / "qgis_project"
ROOFS = QGIS / "slum_roofs_red_v12.geojson"
OVERTURE = ROOT / "01_data/03_derived_vector/buildings/bangkok_buildings_overture.parquet"

OUT_ROOFS = QGIS / "checkcadaster_roofs.geojson"
OUT_SITES = QGIS / "checkcadaster_sites.json"
OUT_OVERTURE = QGIS / "overture_bkk_sites.geojson"

BUF_DEG = 0.002  # ~200 m around each site's roof bbox


def r6(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 6), round(coords[1], 6)]
    return [r6(c) for c in coords]


def main() -> None:
    print("loading red roofs...")
    red = json.loads(ROOFS.read_text(encoding="utf-8"))
    feats = [f for f in red["features"] if str(f.get("properties", {}).get("site", "")).startswith("bkk_")]
    print(f"  bangkok-site roofs: {len(feats)}")

    # per-site windows
    sites = {}
    for f in feats:
        geom = f["geometry"]
        xs, ys = [], []
        for poly in geom["coordinates"]:
            for ring in poly:
                for x, y in ring:
                    xs.append(x)
                    ys.append(y)
        p = f["properties"]
        s = sites.setdefault(p["site"], {"minx": 1e9, "miny": 1e9, "maxx": -1e9, "maxy": -1e9})
        s["minx"] = min(s["minx"], min(xs)); s["miny"] = min(s["miny"], min(ys))
        s["maxx"] = max(s["maxx"], max(xs)); s["maxy"] = max(s["maxy"], max(ys))
    windows = {name: box(v["minx"] - BUF_DEG, v["miny"] - BUF_DEG,
                         v["maxx"] + BUF_DEG, v["maxy"] + BUF_DEG) for name, v in sites.items()}
    print(f"  sites: {len(windows)}")

    # stream overture parquet, keep footprints hitting any window
    print("scanning overture parquet (3.1M rows)...")
    pf = pq.ParquetFile(OVERTURE)
    ov_geoms, ov_heights = [], []
    n = 0
    for batch in pf.iter_batches(batch_size=200_000, columns=["geometry", "height_m"]):
        gs = batch.column("geometry").to_pylist()
        hs = batch.column("height_m").to_pylist()
        for g, h in zip(gs, hs):
            n += 1
            if g is None:
                continue
            geom = shp_wkb.loads(bytes(g))
            for w in windows.values():
                if geom.intersects(w):
                    ov_geoms.append(geom)
                    ov_heights.append(h)
                    break
        if n % 600_000 == 0:
            print(f"  scanned {n}... kept {len(ov_geoms)}", flush=True)
    print(f"  overture near sites: {len(ov_geoms)}")

    tree = STRtree(ov_geoms)
    print("classifying roofs...")
    from shapely.geometry import shape
    out_roofs = []
    ov_hits = 0
    for f in feats:
        shp_geom = shape(f["geometry"])
        hit = len(tree.query(shp_geom, predicate="intersects")) > 0
        if hit:
            ov_hits += 1
        p = f["properties"]
        out_roofs.append({
            "type": "Feature",
            "properties": {
                "site": p.get("site"),
                "area_m2": p.get("area_m2"),
                "nb_20": p.get("nb_20"),
                "ov": 1 if hit else 0,
            },
            "geometry": {"type": "MultiPolygon", "coordinates": r6(f["geometry"]["coordinates"])},
        })
    total = len(out_roofs)
    print(f"  overlap: {ov_hits}/{total} ({100 * ov_hits / total:.1f}%) red houses on an Overture footprint")

    print("writing outputs...")
    OUT_ROOFS.write_text(json.dumps({"type": "FeatureCollection", "features": out_roofs}, separators=(",", ":")), encoding="utf-8")
    ov_feats = [{
        "type": "Feature",
        "properties": {"height_m": (round(h, 1) if h is not None else None)},
        "geometry": json.loads(json.dumps(g.__geo_interface__, separators=(",", ":"))),
    } for g, h in zip(ov_geoms, ov_heights)]
    for f in ov_feats:
        f["geometry"]["coordinates"] = r6(f["geometry"]["coordinates"])
    OUT_OVERTURE.write_text(json.dumps({"type": "FeatureCollection", "features": ov_feats}, separators=(",", ":")), encoding="utf-8")

    site_meta = []
    for name, v in sites.items():
        cnt = sum(1 for f in out_roofs if f["properties"]["site"] == name)
        ov = sum(1 for f in out_roofs if f["properties"]["site"] == name and f["properties"]["ov"])
        site_meta.append({"site": name, "roofs": cnt, "ov": ov,
                          "bbox": [v["minx"], v["miny"], v["maxx"], v["maxy"]]})
    OUT_SITES.write_text(json.dumps(site_meta, separators=(",", ":")), encoding="utf-8")

    mb = lambda p: p.stat().st_size / 1e6
    print(f"done. roofs {mb(OUT_ROOFS):.1f} MB · overture {mb(OUT_OVERTURE):.1f} MB · sites {len(site_meta)}")


if __name__ == "__main__":
    main()
