# -*- coding: utf-8 -*-
"""Gen 2c - U-Net retrained on a COMBINED teacher that covers slums.

Why: Overture misses informal shacks (user screenshots - dense slum with no
outlines), so a teacher-pure model inherits the blind spot and still passes
teacher-anchored gates. Fix: add SAM roofs (rebuilt gen1, prob-stitched)
INSIDE BMA slum buffers as extra positive labels - they come from image
evidence, exactly where Overture is blind.

Combined teacher = aligned Overture (all)  UNION  SAM roofs (in slum bufs).
Retrain (same chips/splits), predict, watershed instances, rectify.
Slum-recall gate: share of combined-teacher slum-area roofs recovered.
"""
import json
import random
from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import geopandas as gpd

import sys
sys.path.insert(0, str(Path(__file__).parent))
from segment_core import (SCENE, APP, ROOT, H, W, instances_from_prob,
                          polygons_from_labels, evaluate)
from gen3_fix import regularize

random.seed(0); np.random.seed(0)

CHIP = 256
TEACHER = ROOT / "05_scratch/yolo/teacher_aligned.geojson"
BMA = ROOT / "01_data/02_external_vector/bkk_community_boundaries/bkk_community_boundary.shp"
COMBINED = ROOT / "05_scratch/yolo/teacher_combined.geojson"
PROB_CACHE = ROOT / "05_scratch/gen2c_prob.tif"


def build_combined(src):
    if COMBINED.exists():
        g = gpd.read_file(COMBINED).to_crs(src.crs)
        print("combined teacher cached:", len(g))
        return g

    ov = gpd.read_file(TEACHER).to_crs(src.crs)
    sam = gpd.read_file(APP / "gen1_roofs_rebuilt.geojson").to_crs(src.crs)

    bma = gpd.read_file(BMA).to_crs(src.crs)
    bma["geometry"] = bma.geometry.buffer(0)
    slum = bma[bma["CMT_TYPE"] == "ชุมชนแออัด"]
    from shapely.geometry import box
    slum = slum[slum.intersects(box(*src.bounds))]
    zone = slum.geometry.buffer(100).union_all()
    sam_in = sam[sam.geometry.within(zone)]
    # quality filter: small shacks only, sane shapes
    sam_in = sam_in[(sam_in.area >= 4) & (sam_in.area <= 300)]
    sam_in = sam_in[sam_in.area / sam_in.minimum_rotated_rectangle.apply(lambda r: r.area) > 0.6]
    print(f"overture {len(ov)} + sam-in-slums {len(sam_in)}")

    # drop SAM roofs duplicating overture (>50% covered)
    from shapely import STRtree
    t = STRtree(ov.geometry)
    cand = t.query(sam_in.geometry, predicate="intersects")
    drop = set()
    for i, j in zip(cand[0].tolist(), cand[1].tolist()):
        g, o = sam_in.geometry.iloc[int(i)], ov.geometry.iloc[int(j)]
        if g.intersection(o).area / max(g.area, 1e-9) > 0.5:
            drop.add(int(i))
    sam_add = sam_in.drop(sam_in.index[list(drop)])
    print(f"sam added after dedupe: {len(sam_add)}")

    comb = gpd.GeoDataFrame(
        pd_concat([ov[["geometry"]], sam_add[["geometry"]]], ignore_index=True),
        crs=src.crs)
    comb.to_crs(4326).to_file(COMBINED, driver="GeoJSON")
    return comb


def pd_concat(a, b):
    import pandas as pd
    return pd.concat([a, b], ignore_index=True)


def main():
    src = rasterio.open(SCENE)
    arr = src.read().astype(np.float32)
    comb = build_combined(src)

    lab = rasterio.features.rasterize(
        [(g, 1) for g in comb.geometry], out_shape=src.shape,
        transform=src.transform, fill=0, dtype="uint8").astype(np.int64)
    print("combined teacher px:", int(lab.sum()))

    # ---- train (same protocol as gen2b) ----
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader
    import segmentation_models_pytorch as smp
    sys_path = Path(__file__).parent
    from gen3_fix import ChipSet  # reuse

    rgb = np.stack([arr[2], arr[3], arr[1]])   # TRUE COLOR b3,b4,b2
    rgb = ((rgb - rgb.reshape(3, -1).mean(1)[:, None, None]) /
           (rgb.reshape(3, -1).std(1)[:, None, None] + 1e-6)).astype(np.float32)

    n_cols = (W - CHIP) // CHIP + 1
    chips_tr, chips_va = [], []
    for r in range(0, H - CHIP + 1, CHIP):
        for c in range(0, W - CHIP + 1, CHIP):
            (chips_va if (c // CHIP) % 5 == 4 else chips_tr).append((r, c))
    heavy = [ch for ch in chips_tr
             if lab[ch[0]:ch[0] + CHIP, ch[1]:ch[1] + CHIP].mean() > 0.10]
    chips_tr = chips_tr + heavy * 2
    print(f"chips train {len(chips_tr)} val {len(chips_va)}")

    dl_tr = DataLoader(ChipSet(rgb, lab, chips_tr, True), batch_size=8,
                       shuffle=True)
    dl_va = DataLoader(ChipSet(rgb, lab, chips_va, False), batch_size=8)
    model = smp.Unet(encoder_name="resnet18", encoder_weights="imagenet",
                     in_channels=3, classes=2)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4)
    ce = nn.CrossEntropyLoss(weight=torch.tensor([0.4, 1.0]))
    dice = smp.losses.DiceLoss(mode="multiclass")
    best_iou = -1
    (ROOT / "05_models").mkdir(exist_ok=True)
    for ep in range(15):
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
        print(f"epoch {ep+1} val-IoU {iou:.3f}", flush=True)
        if iou > best_iou:
            best_iou = iou
            torch.save(model.state_dict(), ROOT / "05_models/gen2c_unet.pt")
    print("best:", round(best_iou, 3))

    # ---- predict ----
    model.load_state_dict(torch.load(ROOT / "05_models/gen2c_unet.pt",
                                     weights_only=True))
    model.eval()
    prob = np.zeros((H, W), dtype=np.float32)
    cnt = np.zeros((H, W), dtype=np.float32)
    C = 256
    with torch.no_grad():
        for r in range(0, H - C + 1, C // 2):
            for c in range(0, W - C + 1, C // 2):
                p_ = torch.softmax(model(torch.from_numpy(
                    rgb[:, r:r + C, c:c + C][None])), 1)[0, 1]
                prob[r:r + C, c:c + C] += p_.numpy()
                cnt[r:r + C, c:c + C] += 1
    prob /= np.maximum(cnt, 1)
    profile = src.profile.copy()
    profile.update(count=1, dtype="float32")
    with rasterio.open(PROB_CACHE, "w", **profile) as ds:
        ds.write(prob, 1)

    inst = instances_from_prob(prob, thr=0.5)
    recs = polygons_from_labels(inst, src.transform)
    reg = [regularize(r["geometry"]) for r in recs]
    reg = [g for g in reg if g is not None and g.area >= 4.0]
    out = gpd.GeoDataFrame({"area_m2": [g.area for g in reg]}, geometry=reg,
                           crs=src.crs).to_crs(4326)
    out.to_file(APP / "gen2c_roofs.geojson", driver="GeoJSON")
    print("gen2c roofs:", len(out))

    # ---- slum-recall evaluation (THE gate that was missing) ----
    bma = gpd.read_file(BMA).to_crs(src.crs)
    bma["geometry"] = bma.geometry.buffer(0)
    from shapely.geometry import box
    slum = bma[(bma["CMT_TYPE"] == "ชุมชนแออัด") &
               bma.intersects(box(*src.bounds))]
    zone = slum.geometry.buffer(100).union_all()
    t_slum = comb[comb.geometry.within(zone) &
                  (comb.area <= 300)]          # combined-teacher slum roofs
    out_u = out.to_crs(src.crs)
    covered = 0.0
    if len(t_slum):
        u = out_u.geometry.union_all()
        hit = t_slum.geometry.apply(
            lambda g: g.intersection(u).area / max(g.area, 1e-9) > 0.4)
        covered = float(hit.mean())
    print(f"SLUM-RECALL: {covered:.2f} of {len(t_slum)} teacher slum roofs")
    json.dump({"val_iou": best_iou, "slum_recall": covered,
               "n_roofs": len(out)},
              open(APP / "gen2c_metrics.json", "w"), indent=2)
    src.close()
    print("DONE")


if __name__ == "__main__":
    main()
