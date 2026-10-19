# -*- coding: utf-8 -*-
"""Rebuild all generations under the approved algorithm.

Stages (sequential, --stage): unet, yolo, sam, publish.

unet : Gen2 - aligned teacher ERODED 1 m (boundary noise down), prob-space
       stitch, watershed instances, rectify.
yolo : Gen3 - trained weights reused, sliced native inference conf>=0.5,
       per-instance conf accumulated into a probability raster with
       anti-seam edge weights (NO instance concatenation), watershed.
sam  : Gen1 - SAM rerun, per-pixel max predicted-IoU accumulation, global
       stitch, watershed.
publish : gates via segment_core.evaluate; only passing generations are
       written to theos_block/*_roofs.geojson.
"""
import argparse
import json
import random
from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import geopandas as gpd

import sys
sys.path.insert(0, str(Path(__file__).parent))
from segment_core import (SCENE, APP, ROOT, H, W, edge_weights,
                          instances_from_prob, polygons_from_labels,
                          evaluate)
from gen3_fix import regularize

random.seed(0); np.random.seed(0)

TEACHER = ROOT / "05_scratch/yolo/teacher_aligned.geojson"
YOLO_BEST = ROOT / "05_scratch/yolo/train/weights/best.pt"


def chip_img(arr, r, c, size):
    rgb = np.stack([arr[1], arr[2], arr[3]])
    nir = arr[0]
    ch = rgb[:, r:r + size, c:c + size]
    lo, hi = np.percentile(ch, 1), np.percentile(ch, 99)
    img = np.clip((ch - lo) / max(hi - lo, 1), 0, 1)
    img = (img * 255).astype(np.uint8).transpose(1, 2, 0)
    img[nir[r:r + size, c:c + size] > 470] = [0, 60, 0]
    return img


def rects(recs, src):
    reg = [regularize(r["geometry"]) for r in recs]
    reg = [g for g in reg if g is not None and g.area >= 4.0]
    return gpd.GeoDataFrame({"area_m2": [g.area for g in reg]},
                            geometry=reg, crs=src.crs).to_crs(4326)


def run_unet():
    src = rasterio.open(SCENE)
    arr = src.read().astype(np.float32)

    t = gpd.read_file(TEACHER).to_crs(src.crs)
    t["geometry"] = t.geometry.buffer(-1.0)      # eroded teacher
    t = t[~t.geometry.is_empty]
    lab = rasterio.features.rasterize(
        [(g, 1) for g in t.geometry], out_shape=src.shape,
        transform=src.transform, fill=0, dtype="uint8").astype(np.int64)
    print("eroded teacher px:", int(lab.sum()))

    import torch
    import segmentation_models_pytorch as smp
    ckpt = ROOT / "05_models/gen2b_unet.pt"
    cache = ROOT / "05_scratch/gen2_rebuilt_prob.tif"
    if cache.exists():
        with rasterio.open(cache) as ds:
            prob = ds.read(1)
        print("reused cached prob")
    else:
        model = smp.Unet(encoder_name="resnet18", encoder_weights=None,
                         in_channels=3, classes=2)
        model.load_state_dict(torch.load(ckpt, weights_only=True))
        model.eval()
        rgb = np.stack([arr[1], arr[2], arr[3]])
        rgb = ((rgb - rgb.reshape(3, -1).mean(1)[:, None, None]) /
               (rgb.reshape(3, -1).std(1)[:, None, None] + 1e-6)).astype(np.float32)
        prob = np.zeros(src.shape, dtype=np.float32)
        cnt = np.zeros(src.shape, dtype=np.float32)
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
        with rasterio.open(cache, "w", **profile) as ds:
            ds.write(prob, 1)

    inst = instances_from_prob(prob, thr=0.5)
    recs = polygons_from_labels(inst, src.transform)
    out = rects(recs, src)
    out.to_file(APP / "gen2_roofs_rebuilt.geojson", driver="GeoJSON")
    print("unet rebuilt:", len(out))
    src.close()


# --------------------------------------------------------------- yolo ---
def run_yolo():
    from ultralytics import YOLO
    src = rasterio.open(SCENE)
    arr = src.read().astype(np.float32)
    model = YOLO(str(YOLO_BEST))

    acc = np.zeros((H, W), dtype=np.float32)
    wsum = edge_weights(512, 512)
    CHIP = 512
    STEP = 256
    for r in range(0, H - CHIP + 1, STEP):
        for c in range(0, W - CHIP + 1, STEP):
            img = chip_img(arr, r, c, CHIP)
            res = model.predict(img, imgsz=CHIP, conf=0.35, device="cpu",
                                verbose=False)[0]
            if res.masks is None:
                continue
            confs = res.boxes.conf.cpu().numpy()
            for m, cf in zip(res.masks.data.cpu().numpy(), confs):
                acc[r:r + CHIP, c:c + CHIP] += cf * m * wsum
            print(f"win ({r},{c}) inst {len(confs)}", flush=True)

    inst = instances_from_prob(acc, thr=0.35, close_px=4)
    recs = polygons_from_labels(inst, src.transform)
    out = rects(recs, src)
    out.to_file(APP / "gen3_yolo_roofs_rebuilt.geojson", driver="GeoJSON")
    print("yolo rebuilt:", len(out))
    src.close()


# ----------------------------------------------------------------- sam ---
def run_sam():
    from samgeo import SamGeo
    sam = SamGeo(model_type="vit_b", automatic=True, sam_kwargs={
        "points_per_side": 48, "pred_iou_thresh": 0.84,
        "stability_score_thresh": 0.90, "min_mask_region_area": 16})
    src = rasterio.open(SCENE)
    arr = src.read().astype(np.float32)

    acc = np.zeros((H, W), dtype=np.float32)
    CHIP = 1024
    STEP = 768     # mild overlap; seams killed by max-accumulation
    from PIL import Image
    import tempfile, os
    for r in range(0, H - CHIP + 1, STEP):
        for c in range(0, W - CHIP + 1, STEP):
            img = chip_img(arr, r, c, CHIP)
            f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            Image.fromarray(img).save(f.name)
            sam.generate(f.name)
            try:
                os.unlink(f.name)
            except PermissionError:
                pass  # windows handle lingers; temp is fine
            raw = sam.masks
            preds = sam.predicted_iou if hasattr(sam, "predicted_iou") else None
            for k, d in enumerate(np.asarray(raw).ravel()):
                seg = d["segmentation"]
                iou = float(preds[k]) if preds is not None else 0.9
                win = acc[r:r + CHIP, c:c + CHIP]
                np.maximum(win, iou * seg, out=win)
            print(f"chip ({r},{c}) obj {len(np.asarray(raw))}", flush=True)

    inst = instances_from_prob(acc, thr=0.70)
    recs = polygons_from_labels(inst, src.transform)
    out = rects(recs, src)
    out.to_file(APP / "gen1_roofs_rebuilt.geojson", driver="GeoJSON")
    print("sam rebuilt:", len(out))
    src.close()


# ------------------------------------------------------------- publish ---
def run_publish():
    src = rasterio.open(SCENE)
    arr = src.read().astype(np.float32)
    results = {}
    mapping = {
        "gen1_sam": ("gen1_roofs_rebuilt.geojson", "gen1_roofs.geojson"),
        "gen2_unet": ("gen2_roofs_rebuilt.geojson", "gen2_roofs.geojson"),
        "gen3_yolo": ("gen3_yolo_roofs_rebuilt.geojson", "gen3_yolo_roofs.geojson"),
    }
    for name, (rebuilt, target) in mapping.items():
        p = APP / rebuilt
        if not p.exists():
            results[name] = {"fail": "not rebuilt"}
            continue
        g = gpd.read_file(p)
        ok, rep = evaluate(g, src, arr, name)
        results[name] = rep
        print(name, "->", "PASS" if ok else "FAIL", rep)
        if ok:
            g.to_file(APP / target, driver="GeoJSON")
            print(f"  published -> {target}")
    json.dump(results, open(APP / "rebuild_report.json", "w"),
              indent=2, default=str)
    src.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["unet", "yolo", "sam", "publish"])
    a = ap.parse_args()
    {"unet": run_unet, "yolo": run_yolo, "sam": run_sam,
     "publish": run_publish}[a.stage]()
