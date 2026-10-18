# -*- coding: utf-8 -*-
"""Gen 3 - YOLOv8n-seg roof instance segmentation, taught by aligned Overture.

Teacher = Overture footprints with the affine alignment from gen3_fix
(Kabsch similarity, rot 0.05 deg, scale 0.9998). Dataset: 512 px chips,
stride 256, canopy painted green (NIR>470). Striped spatial val split.
Predict: sliding window 512/256, instance masks by confidence, dedupe,
regularize (straight edges) - same pipeline as the other generations.

Writes: theos_block/gen3_yolo_roofs.geojson (+ 05_scratch/yolo dataset)
"""
import json
import random
import shutil
from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import geopandas as gpd
from shapely.geometry import box
from shapely.ops import unary_union

import sys
sys.path.insert(0, str(Path(__file__).parent))
from gen3_fix import affine_teacher, regularize

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "05_scratch/theos/theos_block.tif"
APP = ROOT / "theos_block"
DS = ROOT / "05_scratch/yolo"

CHIP = 512
STRIDE = 256
EPOCHS = 20
SEED = 0
random.seed(SEED); np.random.seed(SEED)

ALIGNED_CACHE = ROOT / "05_scratch/yolo/teacher_aligned.geojson"


def aligned_teacher_geoms(src):
    ALIGNED_CACHE.parent.mkdir(parents=True, exist_ok=True)
    if ALIGNED_CACHE.exists():
        g = gpd.read_file(ALIGNED_CACHE).to_crs(src.crs)
        return list(g.geometry)
    geoms = affine_teacher(src)
    gpd.GeoDataFrame(geometry=geoms, crs=src.crs).to_crs(4326).to_file(
        ALIGNED_CACHE, driver="GeoJSON")
    return geoms


def chip_png(arr_rgb_chip, nir_chip):
    lo, hi = np.percentile(arr_rgb_chip, 1), np.percentile(arr_rgb_chip, 99)
    img = np.clip((arr_rgb_chip - lo) / max(hi - lo, 1), 0, 1)
    img = (img * 255).astype(np.uint8).transpose(1, 2, 0)
    img[nir_chip > 470] = [0, 60, 0]
    return img


def build_dataset(src, arr, teacher):
    if (DS / "done.marker").exists():
        return
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (DS / sub).mkdir(parents=True, exist_ok=True)
    from PIL import Image
    rgb = np.stack([arr[1], arr[2], arr[3]])
    nir = arr[0]
    H, W = src.shape
    n_tr = n_va = 0
    for r in range(0, H - CHIP + 1, STRIDE):
        for c in range(0, W - CHIP + 1, STRIDE):
            win = box(*rasterio.windows.bounds(
                rasterio.windows.Window(c, r, CHIP, CHIP),
                transform=src.transform))
            hits = [t for t in teacher if t.intersects(win)]
            if not hits:
                continue
            is_val = ((c // CHIP) % 5 == 4)
            sub = "val" if is_val else "train"
            img = chip_png(rgb[:, r:r + CHIP, c:c + CHIP], nir[r:r + CHIP, c:c + CHIP])
            name = f"ch_{r}_{c}"
            Image.fromarray(img).save(DS / f"images/{sub}/{name}.png")
            lines = []
            for t in hits:
                inter = t.intersection(win)
                if inter.is_empty or inter.area < 4:
                    continue
                geoms = list(inter.geoms) if inter.geom_type == "MultiPolygon" else [inter]
                for g in geoms:
                    if g.area < 4:
                        continue
                    xs = (np.array(g.exterior.coords)[:, 0] - win.bounds[0]) / \
                        (win.bounds[2] - win.bounds[0])
                    ys = 1.0 - (np.array(g.exterior.coords)[:, 1] - win.bounds[1]) / \
                        (win.bounds[3] - win.bounds[1])
                    xs = np.clip(xs, 0, 1); ys = np.clip(ys, 0, 1)
                    if len(xs) < 4:
                        continue
                    # simplify to <= 40 pts
                    if len(xs) > 40:
                        idx = np.linspace(0, len(xs) - 1, 40).astype(int)
                        xs, ys = xs[idx], ys[idx]
                    lines.append("0 " + " ".join(f"{x:.4f} {y:.4f}"
                                                  for x, y in zip(xs, ys)))
            (DS / f"labels/{sub}/{name}.txt").write_text("\n".join(lines))
            if is_val:
                n_va += 1
            else:
                n_tr += 1
    (DS / "data.yaml").write_text(
        f"path: {DS.as_posix()}\ntrain: images/train\nval: images/val\n"
        "names:\n  0: roof\n")
    (DS / "done.marker").write_text("ok")
    print(f"dataset: train {n_tr} val {n_va} chips")


def train():
    from ultralytics import YOLO
    model = YOLO("yolov8n-seg.pt")
    model.train(data=str(DS / "data.yaml"), epochs=EPOCHS, imgsz=CHIP,
                batch=8, device="cpu", workers=0, project=str(DS),
                name="train", exist_ok=True, verbose=True,
                cache=False, plots=False)
    return model


def predict_full(src, arr, model):
    rgb = np.stack([arr[1], arr[2], arr[3]])
    nir = arr[0]
    H, W = src.shape
    from shapely.geometry import shape as shp_shape
    polys = []
    for r in range(0, H - CHIP + 1, STRIDE):
        for c in range(0, W - CHIP + 1, STRIDE):
            img = chip_png(rgb[:, r:r + CHIP, c:c + CHIP], nir[r:r + CHIP, c:c + CHIP])
            res = model.predict(img, imgsz=CHIP, conf=0.35, device="cpu",
                                verbose=False)[0]
            if res.masks is None:
                continue
            win_tr = src.transform * rasterio.transform.Affine.translation(c, r)
            for m in res.masks.data.cpu().numpy():
                # chip-local px coords -> world via window transform
                for geom, val in rasterio.features.shapes(
                        m.astype("uint8"), mask=m > 0.5, transform=win_tr):
                    g = shp_shape(geom)
                    if 4.0 <= g.area <= 5000.0:
                        polys.append(g)
    return polys


def main():
    src = rasterio.open(SCENE)
    arr = src.read().astype(np.float32)
    teacher = aligned_teacher_geoms(src)
    print("teacher buildings:", len(teacher))

    build_dataset(src, arr, teacher)
    best = DS / "train/weights/best.pt"
    if best.exists():
        from ultralytics import YOLO
        model = YOLO(str(best))
        print("reused trained weights")
    else:
        model = train()

    polys = predict_full(src, arr, model)
    print("raw yolo roofs:", len(polys))

    # dedupe overlaps (keep larger), like gen1
    polys = sorted(polys, key=lambda g: -g.area)
    kept, tree_g = [], []
    from shapely import STRtree
    for g in polys:
        if tree_g:
            t = STRtree(tree_g)
            cand = [tree_g[i] for i in
                    t.query(g, predicate="intersects").tolist()]
            if any(g.intersection(k).area / max(g.area, 1e-9) > 0.55
                   for k in cand[-500:]):
                continue
        tree_g.append(g)
        kept.append(g)
    print("after dedupe:", len(kept))

    reg = [regularize(g) for g in kept]
    reg = [g for g in reg if g is not None and g.area >= 4.0]
    out = gpd.GeoDataFrame({"area_m2": [g.area for g in reg]}, geometry=reg,
                           crs=src.crs).to_crs(4326)
    out.to_file(APP / "gen3_yolo_roofs.geojson", driver="GeoJSON")
    fills = [g.area / max(g.minimum_rotated_rectangle.area, 1e-9)
             for g in out.to_crs(src.crs).geometry[:500]]
    print("gen3 yolo regularized:", len(out),
          "| bbox-fill median:", round(float(np.median(fills)), 3))
    src.close()
    print("DONE")


if __name__ == "__main__":
    main()
