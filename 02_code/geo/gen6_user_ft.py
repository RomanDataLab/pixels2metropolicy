# -*- coding: utf-8 -*-
"""Gen 6 - WHU fine-tuned on USER-DRAWN roof boundaries (165 roofs, 1 chip).

Boundary-true supervision: user drew roof outlines in QGIS at boundary
precision. Water bodies (user-drawn) forced to background with margin.
Protocol: fine-tune from whu_ft.pt (scene-adapted), all-unfrozen lr 1e-5,
30 epochs, random 256-crops + rot/flip/color jitter inside the labeled chip.
Then full-block inference, instances, rectify, QA renders.
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

import segmentation_models_pytorch as smp
from PIL import Image, ImageDraw

sys_p = Path(__file__).parent
import sys
sys.path.insert(0, str(sys_p))
from segment_core import SCENE, APP, ROOT, H, W, instances_from_prob, \
    polygons_from_labels, edge_weights
from gen3_fix import regularize

random.seed(0); np.random.seed(0); torch.manual_seed(0)
LABEL_DIR = ROOT / "labeling/qgis_project"
CKPT_IN = ROOT / "05_models/whu_ft.pt"
CKPT_OUT = ROOT / "05_models/whu_user.pt"
PROB_OUT = ROOT / "05_scratch/whu_user_prob.tif"


def main():
    src = rasterio.open(SCENE)
    arr = src.read().astype(np.float32)
    rgb = np.stack([arr[2], arr[3], arr[1]])
    mean = rgb.reshape(3, -1).mean(1)
    std = rgb.reshape(3, -1).std(1) + 1e-6
    rgbn = ((rgb - mean[:, None, None]) / std[:, None, None]).astype(np.float32)
    canopy = arr[0] > 600

    roofs = gpd.read_file(LABEL_DIR / "roofs_ai.geojson").to_crs(src.crs)
    water = gpd.read_file(LABEL_DIR / "water.geojson").to_crs(src.crs)
    union_r = roofs.geometry.union_all().buffer(0.5)   # +50 cm tolerance
    union_w = water.geometry.union_all().buffer(1.0)

    lab = np.zeros(src.shape, dtype=np.int64)
    tmp = rasterio.features.rasterize([(union_r, 1)], out_shape=src.shape,
                                      transform=src.transform, fill=0,
                                      dtype="uint8")
    lab[tmp == 1] = 1
    wm = rasterio.features.rasterize([(union_w, 1)], out_shape=src.shape,
                                     transform=src.transform, fill=0,
                                     dtype="uint8")
    lab[wm == 1] = 0
    lab[canopy] = 0

    # labeled chip = roofs bounds + 64 px margin
    minx, miny, maxx, maxy = roofs.total_bounds
    win = rasterio.windows.from_bounds(minx - 32, miny - 32, maxx + 32,
                                       maxy + 32, transform=src.transform)
    R0 = max(int(win.row_off), 0); C0 = max(int(win.col_off), 0)
    R1 = min(int(win.row_off + win.height), H)
    C1 = min(int(win.col_off + win.width), W)
    print("labeled region:", R1 - R0, "x", C1 - C0,
          "| roof px:", int(lab.sum()))

    model = smp.UnetPlusPlus(encoder_name="efficientnet-b4",
                             encoder_weights=None, in_channels=3, classes=2)
    model.load_state_dict(torch.load(CKPT_IN, weights_only=True))
    model.eval()

    def crop():
        r = random.randint(R0, R1 - 256)
        c = random.randint(C0, C1 - 256)
        x = rgbn[:, r:r + 256, c:c + 256].copy()
        y = lab[r:r + 256, c:c + 256].copy()
        if random.random() < 0.5:
            x = np.rot90(x, random.randint(1, 3), axes=(1, 2)).copy()
            y = np.rot90(y, random.randint(1, 3)).copy()
        if random.random() < 0.5:
            x = x[:, ::-1].copy(); y = y[:, ::-1].copy()
        x = x * (1 + np.random.uniform(-0.08, 0.08))
        return x, y

    opt = torch.optim.AdamW(model.parameters(), lr=1e-5)
    ce = nn.CrossEntropyLoss(weight=torch.tensor([0.3, 1.0]))
    dice = smp.losses.DiceLoss(mode="multiclass")
    model.train()
    for ep in range(30):
        tot = 0.0
        for _ in range(40):                       # 40 crops/epoch
            x, y = crop()
            opt.zero_grad()
            out = model(torch.from_numpy(x[None]))
            loss = 0.5 * ce(out, torch.from_numpy(y[None])) + \
                0.5 * dice(out, torch.from_numpy(y[None]))
            loss.backward()
            opt.step()
            tot += float(loss.detach())
        # in-region val IoU every 5 epochs
        if (ep + 1) % 5 == 0:
            model.eval()
            with torch.no_grad():
                x = rgbn[:, R0:R1, C0:C1]
                hh = (32 - x.shape[1] % 32) % 32
                ww = (32 - x.shape[2] % 32) % 32
                xp = np.pad(x, ((0, 0), (0, hh), (0, ww)))
                pred = model(torch.from_numpy(xp[None])).argmax(1)[0].numpy()[:x.shape[1], :x.shape[2]]
            yv = lab[R0:R1, C0:C1]
            inter = int(((pred == 1) & (yv == 1)).sum())
            un = int(((pred == 1) | (yv == 1)).sum())
            print(f"ep {ep+1} loss {tot/40:.3f} region-IoU {inter/max(un,1):.3f}",
                  flush=True)
            model.train()
        else:
            print(f"ep {ep+1} loss {tot/40:.3f}", flush=True)
    torch.save(model.state_dict(), CKPT_OUT)
    print("saved", CKPT_OUT.name)

    # full-block inference
    model.eval()
    acc = np.zeros((H, W), dtype=np.float32)
    wsum = np.zeros((H, W), dtype=np.float32)
    w = edge_weights(512, 512)
    with torch.no_grad():
        for r in range(0, H - 512 + 1, 256):
            for c in range(0, W - 512 + 1, 256):
                p = torch.sigmoid(model(torch.from_numpy(
                    rgbn[:, r:r + 512, c:c + 512][None])))[0, 1].numpy()
                acc[r:r + 512, c:c + 512] += p * w
                wsum[r:r + 512, c:c + 512] += w
    prob = acc / np.maximum(wsum, 1e-9)
    profile = src.profile.copy()
    profile.update(count=1, dtype="float32")
    with rasterio.open(PROB_OUT, "w", **profile) as ds:
        ds.write(prob, 1)

    inst = instances_from_prob(prob, thr=0.5, close_px=3, min_m2=4.0)
    recs = polygons_from_labels(inst, src.transform)
    reg = [regularize(r["geometry"]) for r in recs]
    reg = [g for g in reg if g is not None and g.area >= 4.0]
    out = gpd.GeoDataFrame({"area_m2": [g.area for g in reg]}, geometry=reg,
                           crs=src.crs).to_crs(4326)
    out.to_file(APP / "whu_user_roofs.geojson", driver="GeoJSON")
    print("gen6 roofs:", len(out))

    # QA: user chip + warehouse + dense slum
    vis = np.stack([arr[2], arr[3], arr[1]])
    lo, hi = np.percentile(vis, 2), np.percentile(vis, 98)
    vis8 = (np.clip((vis - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    tr = src.transform
    inv = ~tr
    from pyproj import Transformer
    from rasterio.transform import rowcol
    tr_ = Transformer.from_crs(4326, src.crs, always_xy=True)
    px, py = tr_.transform(100.602973, 13.928059)
    pr, pc = rowcol(src.transform, px, py)
    for name, (rr, cc) in {"userchip": (pr, pc), "slum": (2100, 1500),
                           "warehouse": (500, 1900)}.items():
        r0 = max(rr - 320, 0); c0 = max(cc - 320, 0)
        crop = vis8[:, r0:r0 + 640, c0:c0 + 640].transpose(1, 2, 0).copy()
        im = Image.fromarray(crop)
        dr = ImageDraw.Draw(im)
        winb = box(*rasterio.windows.bounds(
            rasterio.windows.Window(c0, r0, 640, 640), transform=tr))
        for g in out.to_crs(src.crs)[out.to_crs(src.crs).intersects(winb)].geometry:
            for part in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
                xs, ys = part.exterior.xy
                pts = [(col - c0, row - r0)
                       for col, row in (inv * (x, y) for x, y in zip(xs, ys))]
                dr.line(pts + [pts[0]], fill=(255, 255, 0), width=2)
        im.resize((760, 760)).save(APP / f"qa6_{name}.png")
        print("qa:", name, flush=True)
    src.close()
    print("DONE")


if __name__ == "__main__":
    main()
