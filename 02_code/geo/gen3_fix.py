# -*- coding: utf-8 -*-
"""Fix pass for both generations.

1. Teacher affine alignment: translation-only shift was insufficient (roofs
   crossing roads). Estimate SIMILARITY transform (rotation + scale + shift)
   via Kabsch on matched building centroids: Overture centroids vs SAM
   (gen1) centroids, matched nearest-neighbour < 15 m, RANSAC-refined.
2. Retrain gen2 U-Net with the affine-aligned teacher.
3. Regularize BOTH generations: "edge points connected by straight lines" -
   Douglas-Peucker 0.5 m, snap to dominant orientation (rectilinear),
   min-rectangle replacement when fill >= 0.75.

Outputs (app assets): theos_block/gen1_roofs.geojson, gen2_roofs.geojson
(overwritten with regular versions). Metrics printed.
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
from torch.utils.data import Dataset, DataLoader
from shapely.geometry import box
from shapely import affinity

import segmentation_models_pytorch as smp

ROOT = Path(__file__).resolve().parents[2]
(ROOT / "05_models").mkdir(exist_ok=True)
SCENE = ROOT / "05_scratch/theos/theos_block.tif"
OVERTURE = ROOT / "theos_block/overture_buildings.geojson"  # clipped, 12.5k
APP = ROOT / "theos_block"

CHIP = 256
EPOCHS = 15
BATCH = 8
SEED = 0
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)


# ---------------------------------------------------------------- affine ---
def affine_teacher(src):
    g1 = gpd.read_file(APP / "gen1_roofs.geojson").to_crs(src.crs)  # SAM, image-based
    ov = gpd.read_file(OVERTURE).to_crs(src.crs)
    ov = ov[ov.intersects(box(*src.bounds))].copy()
    print("overture:", len(ov), "| sam:", len(g1))

    oc = np.array([(g.centroid.x, g.centroid.y) for g in ov.geometry])
    sc = np.array([(g.centroid.x, g.centroid.y) for g in g1.geometry])

    # nearest-neighbour matching, both directions, < 15 m
    from scipy.spatial import cKDTree
    t = cKDTree(sc)
    d, idx = t.query(oc)
    pairs = [(i, j) for i, (dd, j) in enumerate(zip(d, idx)) if dd < 15.0]
    print("matched pairs:", len(pairs))
    P = np.array([oc[i] for i, _ in pairs])
    Q = np.array([sc[j] for _, j in pairs])

    def kabsch(P, Q):
        pc, qc = P.mean(0), Q.mean(0)
        H = (P - pc).T @ (Q - qc)
        U, _, Vt = np.linalg.svd(H)
        R = Vt.T @ U.T
        if np.linalg.det(R) < 0:
            Vt[-1] *= -1
            R = Vt.T @ U.T
        s = np.sqrt(((Q - qc) ** 2).sum() / ((P - pc) ** 2).sum())
        return R, s, pc, qc

    # RANSAC-lite: iterate Kabsch on inlier subsets
    best, best_res = None, 1e18
    rng = np.random.default_rng(0)
    for _ in range(40):
        samp = rng.choice(len(P), min(60, len(P)), replace=False)
        R, s, pc, qc = kabsch(P[samp], Q[samp])
        pred = (R @ ((P - pc) * s).T).T + qc
        res = np.linalg.norm(pred - Q, axis=1)
        inl = res < 3.0
        if inl.sum() < max(10, len(P) // 10):
            continue
        R, s, pc, qc = kabsch(P[inl], Q[inl])
        pred = (R @ ((P - pc) * s).T).T + qc
        r = float(np.median(np.linalg.norm(pred - Q, axis=1)[inl]))
        if r < best_res:
            best_res, best = r, (R, s, pc, qc, int(inl.sum()))

    R, s, pc, qc, n_in = best
    print(f"affine: rot {np.degrees(np.arctan2(R[1,0], R[0,0])):.3f} deg, "
          f"scale {s:.4f}, median residual {best_res:.2f} m, inliers {n_in}")

    # shapely [a,b,d,e,xoff,yoff]: (x,y) -> (a*x+b*y+xoff, d*x+e*y+yoff)
    # T(p) = s*R @ p + (qc - s*R @ pc)
    a, b = R[0, 0] * s, R[0, 1] * s
    d, e = R[1, 0] * s, R[1, 1] * s
    xoff = qc[0] - (a * pc[0] + b * pc[1])
    yoff = qc[1] - (d * pc[0] + e * pc[1])
    aligned = [affinity.affine_transform(g, [a, b, d, e, xoff, yoff])
               for g in ov.geometry]
    return aligned


# ------------------------------------------------------ roof dataset/train ---
class ChipSet(Dataset):
    def __init__(self, rgb, lab, chips, train):
        self.rgb, self.lab, self.chips, self.train = rgb, lab, chips, train

    def __len__(self):
        return len(self.chips)

    def __getitem__(self, i):
        r, c = self.chips[i]
        x = self.rgb[:, r:r + CHIP, c:c + CHIP].copy()
        y = self.lab[r:r + CHIP, c:c + CHIP].copy()
        if self.train:
            if random.random() < 0.5:
                x = np.rot90(x, random.randint(1, 3), axes=(1, 2)).copy()
            if random.random() < 0.5:
                x = x[:, :, ::-1].copy()
            x = x * (1 + np.random.uniform(-0.1, 0.1))
        return (torch.from_numpy(x.astype(np.float32)),
                torch.from_numpy(y.astype(np.int64)))


def train_gen2(src, lab):
    arr = src.read().astype(np.float32)
    rgb = np.stack([arr[1], arr[2], arr[3]])
    rgb = ((rgb - rgb.reshape(3, -1).mean(1)[:, None, None]) /
           (rgb.reshape(3, -1).std(1)[:, None, None] + 1e-6)).astype(np.float32)

    n_cols = (src.width - CHIP) // CHIP + 1
    chips_tr, chips_va = [], []
    for r in range(0, src.height - CHIP + 1, CHIP):
        for c in range(0, src.width - CHIP + 1, CHIP):
            (chips_va if (c // CHIP) % 5 == 4 else chips_tr).append((r, c))
    heavy = [ch for ch in chips_tr if lab[ch[0]:ch[0] + CHIP,
                                         ch[1]:ch[1] + CHIP].mean() > 0.10]
    chips_tr = chips_tr + heavy * 2
    print(f"chips train {len(chips_tr)} val {len(chips_va)}")

    dl_tr = DataLoader(ChipSet(rgb, lab, chips_tr, True), batch_size=BATCH,
                       shuffle=True)
    dl_va = DataLoader(ChipSet(rgb, lab, chips_va, False), batch_size=BATCH)
    model = smp.Unet(encoder_name="resnet18", encoder_weights="imagenet",
                     in_channels=3, classes=2)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4)
    ce = nn.CrossEntropyLoss(weight=torch.tensor([0.4, 1.0]))
    dice = smp.losses.DiceLoss(mode="multiclass")
    best_iou = -1
    for ep in range(EPOCHS):
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
        print(f"epoch {ep+1} val-roof-IoU {iou:.3f}")
        if iou > best_iou:
            best_iou = iou
            torch.save(model.state_dict(), ROOT / "05_models/gen2b_unet.pt")
    print("best IoU:", round(best_iou, 3))

    model.load_state_dict(torch.load(ROOT / "05_models/gen2b_unet.pt",
                                     weights_only=True))
    model.eval()
    prob = np.zeros(src.shape, dtype=np.float32)
    cnt = np.zeros(src.shape, dtype=np.float32)
    ov2 = CHIP // 2
    with torch.no_grad():
        for r in range(0, src.height - CHIP + 1, ov2):
            for c in range(0, src.width - CHIP + 1, ov2):
                p = torch.softmax(
                    model(torch.from_numpy(
                        rgb[:, r:r + CHIP, c:c + CHIP][None])), 1)[0, 1]
                prob[r:r + CHIP, c:c + CHIP] += p.numpy()
                cnt[r:r + CHIP, c:c + CHIP] += 1
    return prob / np.maximum(cnt, 1)


# --------------------------------------------------- regularization ---
def regularize(geom, simplify=0.5, snap=1.5):
    """Straight edges between corner points: simplify, snap to the dominant
    orientation, replace with min-rectangle when the shape already fills it."""
    from shapely.ops import transform as shp_transform
    g = geom.buffer(0).simplify(simplify)
    if g.is_empty:
        return None
    omr = g.minimum_rotated_rectangle
    if g.area / max(omr.area, 1e-9) >= 0.75:
        return omr.simplify(0.0)
    # dominant angle from OMR long edge
    cs = [(c[0], c[1]) for c in omr.exterior.coords]  # drop possible Z
    (x0, y0), (x1, y1) = cs[0], cs[1]
    ang = np.arctan2(y1 - y0, x1 - x0)
    rot = affinity.rotate(g, -np.degrees(ang), origin="centroid")
    # rectilinear snap: merge near-equal y then x on the exterior ring
    ring = list(rot.exterior.coords)
    ys_ = sorted(set(round(p[1], 1) for p in ring))
    def remap(vals, tol):
        """every input value -> group mean; groups are runs within tol"""
        out, grp = {}, [vals[0]]
        for v in vals[1:]:
            if v - grp[-1] <= tol:
                grp.append(v)
            else:
                m = sum(grp) / len(grp)
                for u in grp:
                    out[int(round(u * 10))] = m
                grp = [v]
        m = sum(grp) / len(grp)
        for u in grp:
            out[int(round(u * 10))] = m
        return out
    def key(v):
        return int(round(v * 10))
    ymap = remap(ys_, snap)
    pts = [(p[0], ymap[key(p[1])]) for p in ring]
    xs_ = sorted(set(round(p[0], 1) for p in pts))
    xmap = remap(xs_, snap)
    pts = [(xmap[key(p[0])], p[1]) for p in pts]
    from shapely.geometry import Polygon
    try:
        out = Polygon(pts).buffer(0)
    except Exception:
        return omr
    if not out.is_valid or out.is_empty:
        return omr
    out = affinity.rotate(out, np.degrees(ang), origin=out.centroid)
    return out if 0.5 < out.area / max(g.area, 1e-9) < 2.0 else omr


def main():
    src = rasterio.open(SCENE)

    # 1. affine-aligned teacher
    geoms = affine_teacher(src)
    lab = rasterio.features.rasterize(
        [(g, 1) for g in geoms], out_shape=src.shape, transform=src.transform,
        fill=0, dtype="uint8").astype(np.int64)
    print("aligned teacher px:", int(lab.sum()),
          f"({float(lab.mean()):.1%})")

    # 2. retrain + predict (reuse prob raster if present)
    if (APP / "gen2_prob.tif").exists():
        with rasterio.open(APP / "gen2_prob.tif") as ds:
            prob = ds.read(1)
        print("reused gen2_prob.tif")
    else:
        prob = train_gen2(src, lab)
    profile = src.profile.copy()
    profile.update(count=1, dtype="float32")
    with rasterio.open(APP / "gen2_prob.tif", "w", **profile) as dst:
        dst.write(prob, 1)

    from scipy import ndimage
    mask = prob >= 0.5
    mask = ndimage.binary_opening(mask, np.ones((2, 2)))
    from shapely.geometry import shape
    recs = []
    for geom, val in rasterio.features.shapes(mask.astype("uint8"), mask=mask,
                                              transform=src.transform):
        g = shape(geom)
        if 4.0 <= g.area <= 5000.0:
            recs.append({"area_m2": float(g.area), "geometry": g})
    raw2 = gpd.GeoDataFrame(recs, crs=src.crs)

    # 3. regularize both generations
    g1 = gpd.read_file(APP / "gen1_roofs.geojson").to_crs(src.crs)
    reg1 = [regularize(g) for g in g1.geometry]
    reg1 = [g for g in reg1 if g is not None and g.area >= 4.0]
    out1 = gpd.GeoDataFrame(
        {"area_m2": [g.area for g in reg1]}, geometry=reg1,
        crs=src.crs).to_crs(4326)
    out1.to_file(APP / "gen1_roofs.geojson", driver="GeoJSON")
    print("gen1 regularized:", len(out1))

    reg2 = [regularize(g) for g in raw2.geometry]
    reg2 = [g for g in reg2 if g is not None and g.area >= 4.0]
    out2 = gpd.GeoDataFrame(
        {"area_m2": [g.area for g in reg2]}, geometry=reg2,
        crs=src.crs).to_crs(4326)
    out2.to_file(APP / "gen2_roofs.geojson", driver="GeoJSON")
    print("gen2 regularized:", len(out2))

    fills = [g.area / max(g.minimum_rotated_rectangle.area, 1e-9)
             for g in out1.to_crs(src.crs).geometry[:500]]
    print("gen1 bbox-fill median after reg:",
          round(float(np.median(fills)), 3))
    src.close()
    print("DONE")


if __name__ == "__main__":
    main()
