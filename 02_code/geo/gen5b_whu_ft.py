# -*- coding: utf-8 -*-
"""WHU fine-tune per approved recipe, slum-aware labels.

Labels (no Overture inside slum zones):
  aligned Overture footprints OUTSIDE BMA-slum+100m buffers
  + SAM rebuilt roofs (image evidence) INSIDE those buffers
  + canopy (NIR>600) forced background
Recipe: 3 epochs encoder frozen (decoder + input only), then unfreeze all
  at lr 1e-5, 12 epochs. UNet++ EfficientNet-B4 from WHU checkpoint.
Inference: 512/256 prob stitch -> watershed -> rectify.
QA: same 300 m point + slum crop, rendered with outlines.
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
from PIL import Image, ImageDraw

import segmentation_models_pytorch as smp
torch.set_num_threads(8)

sys_path = Path(__file__).parent
import sys
sys.path.insert(0, str(sys_path))
from segment_core import SCENE, APP, ROOT, H, W, instances_from_prob, \
    polygons_from_labels, edge_weights
from gen3_fix import regularize

random.seed(0); np.random.seed(0); torch.manual_seed(0)
CHIP = 512
TEACHER = ROOT / "05_scratch/yolo/teacher_aligned.geojson"
COMB = ROOT / "05_scratch/yolo/teacher_slumaware.geojson"
PROB = ROOT / "05_scratch/whu_ft_prob.tif"


def build_labels(src, arr):
    if COMB.exists():
        g = gpd.read_file(COMB).to_crs(src.crs)
        print("labels cached:", len(g))
        return g
    ov = gpd.read_file(TEACHER).to_crs(src.crs)
    sam = gpd.read_file(APP / "gen1_roofs_rebuilt.geojson").to_crs(src.crs)
    bma = gpd.read_file(ROOT / "01_data/02_external_vector/"
                        "bkk_community_boundaries/bkk_community_boundary.shp"
                        ).to_crs(src.crs)
    bma["geometry"] = bma.geometry.buffer(0)
    slum = bma[bma["CMT_TYPE"] == "ชุมชนแออัด"]
    slum = slum[slum.intersects(box(*src.bounds))]
    zone = slum.geometry.buffer(100).union_all()

    ov_in_slum = ov[ov.geometry.within(zone)]
    ov_out = ov[~ov.geometry.within(zone)]
    sam_in = sam[sam.geometry.within(zone)]
    sam_in = sam_in[(sam_in.area >= 4) & (sam_in.area <= 300)]
    print(f"overture out-of-slum {len(ov_out)} (dropped in-slum {len(ov_in_slum)})"
          f" + sam in-slum {len(sam_in)}")
    import pandas as pd
    comb = gpd.GeoDataFrame(
        pd.concat([ov_out[["geometry"]], sam_in[["geometry"]]],
                  ignore_index=True), crs=src.crs)
    comb.to_crs(4326).to_file(COMB, driver="GeoJSON")
    return comb


def main():
    src = rasterio.open(SCENE)
    arr = src.read().astype(np.float32)
    rgb = np.stack([arr[2], arr[3], arr[1]])          # true color
    mean = rgb.reshape(3, -1).mean(1)
    std = rgb.reshape(3, -1).std(1) + 1e-6
    rgbn = ((rgb - mean[:, None, None]) / std[:, None, None]).astype(np.float32)
    canopy = arr[0] > 600

    comb = build_labels(src, arr)
    lab = rasterio.features.rasterize(
        [(g, 1) for g in comb.geometry], out_shape=src.shape,
        transform=src.transform, fill=0, dtype="uint8")
    lab[canopy] = 0
    lab = lab.astype(np.int64)
    print("label px:", int(lab.sum()))

    class DS:
        def __init__(self, chips, train):
            self.chips, self.train = chips, train
        def __len__(self):
            return len(self.chips)
        def __getitem__(self, i):
            r, c = self.chips[i]
            x = rgbn[:, r:r + CHIP, c:c + CHIP].copy()
            y = lab[r:r + CHIP, c:c + CHIP].copy()
            if self.train:
                if random.random() < 0.5:
                    x = np.rot90(x, random.randint(1, 3), axes=(1, 2)).copy()
                if random.random() < 0.5:
                    x = x[:, :, ::-1].copy()
                x = x * (1 + np.random.uniform(-0.08, 0.08))
            return (torch.from_numpy(x), torch.from_numpy(y))

    chips = [(r, c) for r in range(0, H - CHIP + 1, CHIP)
             for c in range(0, W - CHIP + 1, CHIP)]
    tr = [ch for ch in chips if (ch[1] // CHIP) % 5 != 4]
    va = [ch for ch in chips if (ch[1] // CHIP) % 5 == 4]
    heavy = [ch for ch in tr if lab[ch[0]:ch[0] + CHIP,
                                    ch[1]:ch[1] + CHIP].mean() > 0.15]
    tr = tr + heavy * 2
    print(f"chips train {len(tr)} val {len(va)}")

    dl_tr = DataLoader(DS(tr, True), batch_size=4, shuffle=True)
    dl_va = DataLoader(DS(va, False), batch_size=4)

    import huggingface_hub
    wpath = Path(huggingface_hub.hf_hub_download(
        "giswqs/whu-building-unetplusplus-efficientnet-b4", "model.pth"))
    sd = torch.load(wpath, map_location="cpu", weights_only=True)
    model = smp.UnetPlusPlus(encoder_name="efficientnet-b4",
                             encoder_weights=None, in_channels=3, classes=2)
    model.load_state_dict(sd.get("state_dict", sd))
    (ROOT / "05_models").mkdir(exist_ok=True)

    best = -1
    for phase, epochs, lr, freeze in (("frozen", 3, 1e-3, True),
                                      ("unfrozen", 12, 1e-5, False)):
        for p in model.encoder.parameters():
            p.requires_grad = not freeze
        opt = torch.optim.AdamW(
            [p for p in model.parameters() if p.requires_grad], lr=lr)
        ce = nn.CrossEntropyLoss(weight=torch.tensor([0.4, 1.0]))
        dice = smp.losses.DiceLoss(mode="multiclass")
        for ep in range(epochs):
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
            print(f"{phase} ep{ep+1}/{epochs} val-IoU {iou:.3f}", flush=True)
            if iou > best:
                best = iou
                torch.save(model.state_dict(),
                           ROOT / "05_models/whu_ft.pt")
    print("best val IoU:", round(best, 3))

    model.load_state_dict(torch.load(ROOT / "05_models/whu_ft.pt",
                                     weights_only=True))
    model.eval()
    acc = np.zeros((H, W), dtype=np.float32)
    wgt = edge_weights(CHIP, CHIP)
    wsum = np.zeros((H, W), dtype=np.float32)
    with torch.no_grad():
        for r in range(0, H - CHIP + 1, CHIP // 2):
            for c in range(0, W - CHIP + 1, CHIP // 2):
                p = torch.sigmoid(model(torch.from_numpy(
                    rgbn[:, r:r + CHIP, c:c + CHIP][None])))[0, 0].numpy()
                acc[r:r + CHIP, c:c + CHIP] += p * wgt
                wsum[r:r + CHIP, c:c + CHIP] += wgt
    prob = acc / np.maximum(wsum, 1e-9)
    profile = src.profile.copy()
    profile.update(count=1, dtype="float32")
    with rasterio.open(PROB, "w", **profile) as ds:
        ds.write(prob, 1)
    print("prob mean:", round(float(prob.mean()), 3))

    inst = instances_from_prob(prob, thr=0.5, close_px=3, min_m2=4.0)
    recs = polygons_from_labels(inst, src.transform)
    reg = [regularize(r["geometry"]) for r in recs]
    reg = [g for g in reg if g is not None and g.area >= 4.0]
    out = gpd.GeoDataFrame({"area_m2": [g.area for g in reg]}, geometry=reg,
                           crs=src.crs).to_crs(4326)
    out.to_file(APP / "whuft_roofs.geojson", driver="GeoJSON")
    print("whu-ft roofs:", len(out))

    # ---- QA renders: user point 300m + slum crop ----
    vis = np.stack([arr[2], arr[3], arr[1]])
    lo, hi = np.percentile(vis, 2), np.percentile(vis, 98)
    vis8 = (np.clip((vis - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    tr_ = __import__("pyproj").Transformer.from_crs(
        4326, src.crs, always_xy=True)
    px, py = tr_.transform(100.602973, 13.928059)
    from rasterio.transform import rowcol
    pr, pc = rowcol(src.transform, px, py)
    for name, (rr, cc) in {"point300": (pr, pc),
                           "slum": (2100, 1500)}.items():
        r0 = max(rr - 320, 0); c0 = max(cc - 320, 0)
        crop = vis8[r0:r0 + 640, c0:c0 + 640].copy()
        im = Image.fromarray(crop)
        dr = ImageDraw.Draw(im)
        sub = out.to_crs(src.crs)
        win = box(*rasterio.windows.bounds(
            rasterio.windows.Window(c0, r0, 640, 640),
            transform=src.transform))
        for g in sub[sub.intersects(win)].geometry:
            xs, ys = g.exterior.xy
            dr.polygon([(x - c0, y - r0) for x, y in zip(xs, ys)],
                       outline=(255, 0, 255))
        im.resize((760, 760)).save(APP / f"qa_{name}.png")
        print("qa saved:", name)
    json.dump({"val_iou": best, "n_roofs": len(out)},
              open(APP / "whuft_metrics.json", "w"), indent=2)
    src.close()
    print("DONE")


if __name__ == "__main__":
    main()
