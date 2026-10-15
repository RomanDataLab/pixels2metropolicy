# -*- coding: utf-8 -*-
"""Gen 1 - SAM automatic roof segmentation over the THEOS block (samgeo).

Chips 1024 px, overlap 128. MobileSAM (vit_t) backend, CPU.
Masks filtered to roof-plausible size (4-5000 m2). No training, no prompts.

Usage:
  python gen1_samgeo_roofs.py --test     # one chip, API smoke test
  python gen1_samgeo_roofs.py            # full block
Writes: theos_block/gen1_roofs.geojson (+ chips/ scratch)
"""
import argparse
import tempfile
from pathlib import Path

import numpy as np
import rasterio
import rasterio.windows
import rasterio.features
from rasterio.transform import Affine
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "05_scratch/theos/theos_block.tif"
OUT = ROOT / "04_output/open_stack/bangkok/theos_block"
CHIP_DIR = OUT / "gen1_chips"

CHIP = 1024
OV = 128
MIN_M2, MAX_M2 = 4.0, 5000.0


def chip_png(arr_rgb):
    """uint8 RGB png bytes for SAM."""
    lo, hi = np.percentile(arr_rgb, 1), np.percentile(arr_rgb, 99)
    img = np.clip((arr_rgb - lo) / max(hi - lo, 1), 0, 1)
    return (img * 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    from samgeo import SamGeo
    # dense prompt grid: default 32 pts/side = one per 16 m - small roofs
    # never got a point and were skipped entirely (under-detection)
    sam = SamGeo(model_type="vit_b", automatic=True, sam_kwargs={
        "points_per_side": 48,
        "pred_iou_thresh": 0.84,
        "stability_score_thresh": 0.90,
        "min_mask_region_area": 16,
    })

    src = rasterio.open(SCENE)
    H, W = src.height, src.width
    arr = src.read().astype(np.float32)
    rgb = np.stack([arr[1], arr[2], arr[3]])   # R,G,B

    CHIP_DIR.mkdir(parents=True, exist_ok=True)
    import geopandas as gpd
    from shapely.geometry import shape

    rows = []
    if args.test:
        positions = [(0, 0)]
    else:
        positions = [(r, c)
                     for r in range(0, H - CHIP + 1, CHIP - OV)
                     for c in range(0, W - CHIP + 1, CHIP - OV)]

    for n, (r, c) in enumerate(positions, start=1):
        chip = rgb[:, r:r + CHIP, c:c + CHIP]
        png = chip_png(chip).transpose(1, 2, 0)   # HWC for PIL/masking
        nir = arr[0, r:r + CHIP, c:c + CHIP]
        png[nir > 470] = [0, 60, 0]               # canopy painted green: SAM skips

        f_png = CHIP_DIR / f"chip_{r}_{c}.png"
        from PIL import Image
        Image.fromarray(png).save(f_png)

        sam.generate(str(f_png))
        # samgeo 1.4 automatic mode: object array of {'segmentation': bool}
        raw = sam.masks
        masks = np.zeros((CHIP, CHIP), dtype=np.int32)
        n_ids = 0
        if raw is not None:
            for d in np.asarray(raw).ravel():
                seg = d["segmentation"]
                masks[seg] = n_ids + 1
                n_ids += 1
        print(f"chip {n}/{len(positions)} ({r},{c}) objects {n_ids}")

        win_tr = src.transform * Affine.translation(c, r)
        for geom, val in rasterio.features.shapes(
                masks.astype(np.int32), mask=masks > 0, transform=win_tr):
            g = shape(geom)
            a = g.area
            if MIN_M2 <= a <= MAX_M2:
                rows.append({"area_m2": float(a), "geometry": g})
        f_png.unlink(missing_ok=True)
        if args.test:
            break

    gdf = gpd.GeoDataFrame(rows, crs=src.crs)   # stay in UTM: areas are m2
    # de-overlap: keep larger polygons, drop duplicates from chip overlap
    if len(gdf):
        gdf = gdf.sort_values("area_m2", ascending=False)
        kept = []
        tree_geoms = []
        from shapely import STRtree
        for g in gdf.geometry:
            if tree_geoms and STRtree(tree_geoms).query(
                    g, predicate="intersects").size and any(
                    g.intersection(k).area / max(g.area, 1e-9) > 0.55
                    for k in tree_geoms[-500:]):
                continue
            tree_geoms.append(g)
            kept.append(g)
        gdf = gpd.GeoDataFrame(
            {"area_m2": [g.area for g in kept]}, geometry=kept, crs=src.crs)
    gdf = gdf.to_crs(4326)                      # single projection, at the end
    gdf.to_file(OUT / "gen1_roofs.geojson", driver="GeoJSON")
    print("gen1 roofs:", len(gdf))
    src.close()


if __name__ == "__main__":
    main()
