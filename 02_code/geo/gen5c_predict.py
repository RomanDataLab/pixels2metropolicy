# -*- coding: utf-8 -*-
"""Prediction-only from the surviving whu_ft.pt checkpoint (IoU 0.425).
Sliding 512/256 prob stitch, watershed, rectify, QA renders at:
  - user point 13.928059, 100.602973 (300 m)
  - dense slum crop (user screenshot 2 area)
"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import geopandas as gpd
import torch
from PIL import Image, ImageDraw

import segmentation_models_pytorch as smp

sys.path.insert(0, str(Path(__file__).parent))
from segment_core import SCENE, APP, ROOT, H, W, instances_from_prob, \
    polygons_from_labels, edge_weights
from gen3_fix import regularize

CKPT = ROOT / "05_models/whu_ft.pt"
torch.set_num_threads(8)

src = rasterio.open(SCENE)
arr = src.read().astype(np.float32)
rgb = np.stack([arr[2], arr[3], arr[1]])
mean = rgb.reshape(3, -1).mean(1)
std = rgb.reshape(3, -1).std(1) + 1e-6
rgbn = ((rgb - mean[:, None, None]) / std[:, None, None]).astype(np.float32)

model = smp.UnetPlusPlus(encoder_name="efficientnet-b4", encoder_weights=None,
                         in_channels=3, classes=2)
model.load_state_dict(torch.load(CKPT, weights_only=True))
model.eval()
print("loaded", flush=True)

C, STEP = 512, 256
acc = np.zeros((H, W), dtype=np.float32)
wsum = np.zeros((H, W), dtype=np.float32)
w = edge_weights(C, C)
with torch.no_grad():
    for r in range(0, H - C + 1, STEP):
        for c in range(0, W - C + 1, STEP):
            p = torch.sigmoid(model(torch.from_numpy(
                rgbn[:, r:r + C, c:c + C][None])))[0, 0].numpy()
            acc[r:r + C, c:c + C] += p * w
            wsum[r:r + C, c:c + C] += w
        print("row", r, flush=True)
prob = acc / np.maximum(wsum, 1e-9)
profile = src.profile.copy()
profile.update(count=1, dtype="float32")
with rasterio.open(APP / "whuft_prob.tif", "w", **profile) as ds:
    ds.write(prob, 1)
print("prob mean:", round(float(prob.mean()), 3), flush=True)

inst = instances_from_prob(prob, thr=0.5, close_px=3, min_m2=4.0)
recs = polygons_from_labels(inst, src.transform)
reg = [regularize(r["geometry"]) for r in recs]
reg = [g for g in reg if g is not None and g.area >= 4.0]
out = gpd.GeoDataFrame({"area_m2": [g.area for g in reg]}, geometry=reg,
                       crs=src.crs).to_crs(4326)
out.to_file(APP / "whuft_roofs.geojson", driver="GeoJSON")
print("whu-ft roofs:", len(out))

vis = np.stack([arr[2], arr[3], arr[1]])
lo, hi = np.percentile(vis, 2), np.percentile(vis, 98)
vis8 = (np.clip((vis - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
from pyproj import Transformer
from rasterio.transform import rowcol
tr_ = Transformer.from_crs(4326, src.crs, always_xy=True)
px, py = tr_.transform(100.602973, 13.928059)
pr, pc = rowcol(src.transform, px, py)
sub_u = out.to_crs(src.crs)
for name, (rr, cc) in {"point300": (pr, pc), "slum": (2100, 1500)}.items():
    r0 = max(rr - 320, 0); c0 = max(cc - 320, 0)
    crop = vis8[r0:r0 + 640, c0:c0 + 640].copy()
    im = Image.fromarray(crop)
    dr = ImageDraw.Draw(im)
    win = box(*rasterio.windows.bounds(
        rasterio.windows.Window(c0, r0, 640, 640), transform=src.transform))
    for g in sub_u[sub_u.intersects(win)].geometry:
        xs, ys = g.exterior.xy
        dr.polygon([(x - c0, y - r0) for x, y in zip(xs, ys)],
                   outline=(255, 0, 255))
    im.resize((760, 760)).save(APP / f"qa_ft_{name}.png")
    print("qa:", name, flush=True)
json.dump({"n_roofs": len(out)}, open(APP / "whuft_metrics.json", "w"))
src.close()
print("DONE")
