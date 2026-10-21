# -*- coding: utf-8 -*-
"""Gen 7 stage R - iterative SAM2 refinement against user polygons.

For each user roof:
  set_image once (192 px crop) -> prompt with 3 interior points + bbox corner
  hints -> up to 5 refinement rounds:
    - miss = user polygon minus mask  -> add POSITIVE points there (2)
    - spill = mask minus user polygon -> add NEGATIVE points there (2)
    - re-predict with all accumulated points; keep best-IoU mask
  accept if final IoU(user, mask) >= 0.55

Writes: labeling/qgis_project/sam2_refined.geojson + refine_report.csv
"""
import csv
import numpy as np
import rasterio
import geopandas as gpd
import torch
from rasterio.transform import rowcol
from rasterio.features import shapes as rshapes
from rasterio.transform import Affine
from shapely.geometry import box as sbox, shape as shs, Point
from shapely.ops import unary_union

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

SCENE = "../../05_scratch/theos/theos_block.tif"
ROOFS = "roofs_ai.geojson"
OUT_GJ = "sam2_refined.geojson"
OUT_CSV = "refine_report.csv"

ROUNDS = 5
ACCEPT_IOU = 0.55
HALF = 128

model = build_sam2("configs/sam2.1/sam2.1_hiera_b+.yaml",
                   "../../05_models/sam2.1_hiera_base_plus.pt", device="cpu")
predictor = SAM2ImagePredictor(model)

src = rasterio.open(SCENE)
arr = src.read().astype(np.float32)
rgb = np.stack([arr[2], arr[3], arr[1]])
lo, hi = np.percentile(rgb, 2), np.percentile(rgb, 98)
rgb8 = (np.clip((rgb - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
inv = ~src.transform
roofs = gpd.read_file(ROOFS).to_crs(src.crs)

def sample_points(geom_minus, k, negative_ok_area):
    """k interior points of the given (multi)polygon, spread out."""
    pts = []
    if geom_minus.is_empty or geom_minus.area <= 0:
        return pts
    parts = list(geom_minus.geoms) if geom_minus.geom_type == "MultiPolygon" \
        else [geom_minus]
    parts = sorted(parts, key=lambda p: -p.area)
    for i, part in enumerate(parts[:k]):
        p = part.representative_point()
        pts.append(p)
    while len(pts) < k and parts:
        pts.append(parts[0].representative_point())
        break
    return pts[:k]


def mask_to_geom(mask, c0, r0):
    sub = src.transform * Affine.translation(c0, r0)
    geoms = [shs(ge) for ge, v in rshapes(mask.astype("uint8"),
             mask=mask.astype(bool), transform=sub) if v == 1]
    return unary_union(geoms) if geoms else None


def iou(a, b):
    if a is None or b is None or a.is_empty or b.is_empty:
        return 0.0
    inter = a.intersection(b).area
    return inter / max(a.area + b.area - inter, 1e-9)


out_recs = []
rows = []
n_done = 0
for idx, g in enumerate(roofs.geometry):
    c = g.centroid
    pr, pc = rowcol(src.transform, c.x, c.y)
    r0 = max(min(pr - HALF, src.height - 2 * HALF), 0)
    c0 = max(min(pc - HALF, src.width - 2 * HALF), 0)
    crop = rgb8[:, r0:r0 + 2 * HALF, c0:c0 + 2 * HALF].transpose(1, 2, 0)
    predictor.set_image(crop)

    b = g.bounds
    pts = [g.representative_point(),
           Point(b[0] + (b[2] - b[0]) * 0.25, b[1] + (b[3] - b[1]) * 0.25),
           Point(b[0] + (b[2] - b[0]) * 0.75, b[1] + (b[3] - b[1]) * 0.75)]
    labels = [1, 1, 1]
    best_mask, best_iou, best_round = None, -1, 0

    for rnd in range(ROUNDS):
        ipt = np.array([[col - c0, row - r0]
                        for row, col in (inv * (p.x, p.y) for p in pts)])
        lab = np.array(labels)
        masks, scores, _ = predictor.predict(point_coords=ipt,
                                             point_labels=lab,
                                             multimask_output=True)
        geoms = [mask_to_geom(m.astype(np.uint8), c0, r0) for m in masks]
        ious = [iou(gm, g) for gm in geoms]
        bi = int(np.argmax(ious))
        if ious[bi] > best_iou:
            best_mask, best_iou, best_round = geoms[bi], ious[bi], rnd

        # refinement targets
        miss = g.difference(geoms[bi])       # true roof not in mask -> +
        spill = geoms[bi].difference(g)      # mask outside roof    -> -
        if rnd == ROUNDS - 1 or (miss.is_empty and spill.is_empty):
            break
        for p in sample_points(miss, 2, True):
            pts.append(p); labels.append(1)
        for p in sample_points(spill, 2, True):
            pts.append(p); labels.append(0)

    accepted = best_iou >= ACCEPT_IOU
    if accepted and best_mask is not None and not best_mask.is_empty:
        out_recs.append({"iou": round(best_iou, 3),
                         "geometry": best_mask})
    rows.append({"idx": idx, "iou": round(best_iou, 3),
                 "round": best_round, "accepted": accepted})
    n_done += 1
    if n_done % 20 == 0:
        acc = np.mean([r["accepted"] for r in rows])
        mi = np.median([r["iou"] for r in rows])
        print(f"{n_done}/{len(roofs)} accepted {acc:.0%} medIoU {mi:.2f}",
              flush=True)

import pandas as pd
gdf = gpd.GeoDataFrame(out_recs, crs=src.crs).to_crs(4326)
gdf.to_file(OUT_GJ, driver="GeoJSON")
pd.DataFrame(rows).to_csv(OUT_CSV, index=False)

acc = np.mean([r["accepted"] for r in rows])
med = np.median([r["iou"] for r in rows])
print(f"REFINED: {len(gdf)} accepted of {len(rows)} "
      f"({acc:.0%}) | median IoU {med:.2f}")
print("DONE")
