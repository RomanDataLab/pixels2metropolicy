# -*- coding: utf-8 -*-
"""Teacher-free slum segmentation (NO Overture, NO footprints).

Supervision = BMA slum polygons ONLY (region-level, census-based):
  U-Net: slum-fabric probability (true-color bands b3,b4,b2)
  canopy (NIR>600) forced to background in labels AND masked at inference
Instances: SAM dense objects (gen1 rebuilt prob-stitch) accepted when
  mean slum-prob >= 0.5 AND area 4-225 m2 -> shack outlines
Blocks: clusters of accepted shacks (600 m gap) -> slum_blocks_v2.geojson

Writes: theos_block/slumnet_prob.tif, slumnet_shacks.geojson,
        slum_blocks_v2.geojson, slumnet_metrics.json
"""
import json
import random
from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import geopandas as gpd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from shapely.geometry import box
from shapely.ops import unary_union

import segmentation_models_pytorch as smp

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "05_scratch/theos/theos_block.tif"
BMA = ROOT / "01_data/02_external_vector/bkk_community_boundaries/bkk_community_boundary.shp"
SAM_ROOFS = ROOT / "theos_block/gen1_roofs_rebuilt.geojson"
APP = ROOT / "theos_block"

CHIP = 256
SEED = 0
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)


def true_color(arr):
    rgb = np.stack([arr[2], arr[3], arr[1]])   # b3,b4,b2 = R,G,B
    return ((rgb - rgb.reshape(3, -1).mean(1)[:, None, None]) /
            (rgb.reshape(3, -1).std(1)[:, None, None] + 1e-6)).astype(np.float32)


def main():
    src = rasterio.open(SCENE)
    arr = src.read().astype(np.float32)
    rgb = true_color(arr)
    canopy = arr[0] > 600

    bma = gpd.read_file(BMA).to_crs(src.crs)
    bma["geometry"] = bma.geometry.buffer(0)
    blk = box(*src.bounds)
    bma = bma[bma.intersects(blk)].copy()
    bma["is_slum"] = bma["CMT_TYPE"] == "ชุมชนแออัด"
    bma["geometry"] = bma.geometry.buffer(-2.0)   # erode boundary mix
    bma = bma[~bma.geometry.is_empty].reset_index(drop=True)
    print("communities:", len(bma), "| slum:", int(bma.is_slum.sum()))

    gid = rasterio.features.rasterize(
        [(g, i + 1) for i, g in enumerate(bma.geometry)],
        out_shape=src.shape, transform=src.transform, fill=0, dtype="int32")
    slum_ids = set(np.flatnonzero(bma.is_slum.values) + 1)
    y = np.isin(gid, list(slum_ids)) & ~canopy
    inside = gid > 0

    chips = [(r, c) for r in range(0, src.height - CHIP + 1, CHIP)
             for c in range(0, src.width - CHIP + 1, CHIP)]
    tr = [ch for ch in chips if (ch[1] // CHIP) % 5 != 4]
    va = [ch for ch in chips if (ch[1] // CHIP) % 5 == 4]

    class DS:
        def __init__(self, chips, train):
            self.chips, self.train = chips, train
        def __len__(self):
            return len(self.chips)
        def __getitem__(self, i):
            r, c = self.chips[i]
            x = rgb[:, r:r + CHIP, c:c + CHIP].copy()
            # per-chip balanced sampling: half px from slum region if any
            ychip = y[r:r + CHIP, c:c + CHIP].copy()
            if self.train:
                if random.random() < 0.5:
                    x = np.rot90(x, random.randint(1, 3), axes=(1, 2)).copy()
                if random.random() < 0.5:
                    x = x[:, :, ::-1].copy()
                x = x * (1 + np.random.uniform(-0.1, 0.1))
            return (torch.from_numpy(x), torch.from_numpy(
                ychip.astype(np.int64)))

    # oversample chips overlapping slum polygons 4x
    slum_hits = [ch for ch in tr if y[ch[0]:ch[0] + CHIP,
                                      ch[1]:ch[1] + CHIP].any()]
    tr_full = tr + slum_hits * 3
    print(f"chips train {len(tr_full)} (slum x4: {len(slum_hits)}) val {len(va)}")

    dl_tr = DataLoader(DS(tr_full, True), batch_size=8, shuffle=True)
    dl_va = DataLoader(DS(va, False), batch_size=8)
    model = smp.Unet(encoder_name="resnet18", encoder_weights="imagenet",
                     in_channels=3, classes=2)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4)
    ce = nn.CrossEntropyLoss(weight=torch.tensor([0.3, 1.0]))
    dice = smp.losses.DiceLoss(mode="multiclass")
    best = -1
    (ROOT / "05_models").mkdir(exist_ok=True)
    for ep in range(18):
        model.train()
        for xb, yb in dl_tr:
            opt.zero_grad()
            out = model(xb)
            loss = 0.5 * ce(out, yb) + 0.5 * dice(out, yb)
            loss.backward()
            opt.step()
        model.eval()
        inter = un = 0
        with torch.no_grad():
            for xb, yb in dl_va:
                pred = model(xb).argmax(1)
                inter += int(((pred == 1) & (yb == 1)).sum())
                un += int(((pred == 1) | (yb == 1)).sum())
        iou = inter / max(un, 1)
        print(f"epoch {ep+1} val-slum-IoU {iou:.3f}", flush=True)
        if iou > best:
            best = iou
            torch.save(model.state_dict(), ROOT / "05_models/slumnet.pt")
    print("best slum IoU:", round(best, 3))

    model.load_state_dict(torch.load(ROOT / "05_models/slumnet.pt",
                                     weights_only=True))
    model.eval()
    prob = np.zeros(src.shape, dtype=np.float32)
    cnt = np.zeros(src.shape, dtype=np.float32)
    C = 256
    with torch.no_grad():
        for r in range(0, src.height - C + 1, C // 2):
            for c in range(0, src.width - C + 1, C // 2):
                p_ = torch.softmax(model(torch.from_numpy(
                    rgb[:, r:r + C, c:c + C][None])), 1)[0, 1]
                prob[r:r + C, c:c + C] += p_.numpy()
                cnt[r:r + C, c:c + C] += 1
    prob /= np.maximum(cnt, 1)
    profile = src.profile.copy()
    profile.update(count=1, dtype="float32")
    with rasterio.open(APP / "slumnet_prob.tif", "w", **profile) as ds:
        ds.write(prob, 1)
    print("prob written | slum-region mean:",
          round(float(prob[y].mean()), 3),
          "| non-slum-community mean:",
          round(float(prob[inside & ~y & ~canopy].mean()), 3),
          "| canopy mean:", round(float(prob[canopy].mean()), 3))

    # ---- SAM objects x slum probability = shacks (no footprints) ----
    sam = gpd.read_file(SAM_ROOFS).to_crs(src.crs)
    sam = sam[(sam.area >= 4) & (sam.area <= 225)]
    means = []
    from shapely import STRtree
    t = STRtree(sam.geometry)
    for g in sam.geometry:
        minx, miny, maxx, maxy = g.bounds
        win = rasterio.windows.from_bounds(minx, miny, maxx, maxy,
                                           transform=src.transform)
        r0 = max(int(win.row_off), 0); c0 = max(int(win.col_off), 0)
        r1 = min(int(win.row_off + win.height) + 1, src.height)
        c1 = min(int(win.col_off + win.width) + 1, src.width)
        if r1 <= r0 or c1 <= c0:
            means.append(0.0); continue
        sub_tr = src.transform * rasterio.transform.Affine.translation(c0, r0)
        m = rasterio.features.rasterize([(g, 1)],
            out_shape=(r1 - r0, c1 - c0), transform=sub_tr,
            fill=0, dtype="uint8").astype(bool)
        means.append(float(prob[r0:r1, c0:c1][m].mean())
                     if m.any() else 0.0)
    sam["p_slum"] = means
    shacks = sam[sam.p_slum >= 0.5]
    print(f"SAM objects in range: {len(sam)} | accepted shacks: {len(shacks)}")
    out = shacks.to_crs(4326)[["area_m2", "p_slum", "geometry"]]
    out.to_file(APP / "slumnet_shacks.geojson", driver="GeoJSON")

    # ---- blocks: cluster accepted shacks, 600 m gap ----
    from scipy import ndimage as ndi
    m2 = rasterio.features.rasterize(
        [(g, 1) for g in shacks.geometry], out_shape=src.shape,
        transform=src.transform, fill=0, dtype="uint8").astype(bool)
    m2 = ndi.binary_closing(m2, np.ones((60, 60)))   # 30 m gap
    lbl, n = ndi.label(m2)
    from shapely.geometry import shape
    recs = []
    for i in range(1, n + 1):
        m_ = lbl == i
        if m_.sum() * 0.25 < 300:
            continue
        gen = rasterio.features.shapes(m_.astype("uint8"), mask=m_,
                                       transform=src.transform)
        g = shape(next(iter(gen))[0])
        recs.append({"n_shacks": int(m_.sum()), "geometry": g})
    blocks = gpd.GeoDataFrame(recs, crs=src.crs).to_crs(4326)
    blocks.to_file(APP / "slum_blocks_v2.geojson", driver="GeoJSON")
    print("slum blocks v2:", len(blocks))

    json.dump({"val_slum_iou": best, "n_shacks": len(shacks),
               "n_blocks": len(blocks),
               "slum_region_mean_prob": float(prob[y].mean())},
              open(APP / "slumnet_metrics.json", "w"), indent=2)
    src.close()
    print("DONE")


if __name__ == "__main__":
    main()
