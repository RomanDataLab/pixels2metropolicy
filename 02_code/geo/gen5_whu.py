# -*- coding: utf-8 -*-
"""Gen 5 - PRETRAINED WHU building model (zero-shot) on THEOS true color.

Model: giswqs/whu-building-unetplusplus-efficientnet-b4 (HF Hub)
  UNet++ / EfficientNet-B4, trained on WHU building dataset (0.3 m RGB
  aerial, roof-boundary focused). Loaded via smp.from_pretrained.
Input: THEOS true color (b3, b4, b2) at 0.5 m - same RGB domain.
Inference: 512/256 sliding window, probability stitch (anti-seam weights),
  watershed instances, rectified outlines.

Writes: theos_block/whu_prob.tif, whu_roofs.geojson, whu_metrics.json
        05_scratch/whu_crops/*.png (visual QA crops)
"""
import sys
from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import geopandas as gpd
import torch
from scipy import ndimage

import segmentation_models_pytorch as smp

sys.path.insert(0, str(Path(__file__).parent))
from segment_core import SCENE, APP, ROOT, H, W, edge_weights, \
    instances_from_prob, polygons_from_labels
from gen3_fix import regularize

CROP_QA = ROOT / "05_scratch/whu_crops"


def main():
    CROP_QA.mkdir(parents=True, exist_ok=True)
    print("loading pretrained WHU model ...", flush=True)
    import torch, huggingface_hub
    repo = "giswqs/whu-building-unetplusplus-efficientnet-b4"
    # repo config: {"architecture":"unetplusplus","encoder_name":"efficientnet-b4",
    #               "num_channels":3,"num_classes":2} - saved without SMP hub
    # metadata, so construct explicitly and load the state dict
    wpath = Path(huggingface_hub.hf_hub_download(repo, "model.pth"))
    model = smp.UnetPlusPlus(encoder_name="efficientnet-b4",
                             encoder_weights=None,
                             in_channels=3, classes=2)
    sd = torch.load(wpath, map_location="cpu", weights_only=True)
    if "state_dict" in sd:
        sd = sd["state_dict"]
    missing, unexpected = model.load_state_dict(sd, strict=False)
    print("missing:", len(missing), "unexpected:", len(unexpected))
    if missing:
        print("  sample missing:", missing[:3])
    model.eval()
    print("loaded.")

    src = rasterio.open(SCENE)
    arr = src.read().astype(np.float32)
    rgb = np.stack([arr[2], arr[3], arr[1]])          # b3,b4,b2 true color
    rgb = ((rgb - rgb.reshape(3, -1).mean(1)[:, None, None]) /
           (rgb.reshape(3, -1).std(1)[:, None, None] + 1e-6)).astype(np.float32)

    acc = np.zeros((H, W), dtype=np.float32)
    wsum = np.zeros((H, W), dtype=np.float32)
    C, STEP = 512, 256
    w = edge_weights(C, C)
    n = 0
    with torch.no_grad():
        for r in range(0, H - C + 1, STEP):
            for c in range(0, W - C + 1, STEP):
                x = torch.from_numpy(rgb[:, r:r + C, c:c + C][None])
                p = torch.sigmoid(model(x))[0, 0].numpy()
                acc[r:r + C, c:c + C] += p * w
                wsum[r:r + C, c:c + C] += w
                n += 1
                if n % 30 == 0:
                    print(f"window {n} ({r},{c})", flush=True)
    prob = acc / np.maximum(wsum, 1e-9)

    profile = src.profile.copy()
    profile.update(count=1, dtype="float32")
    with rasterio.open(APP / "whu_prob.tif", "w", **profile) as ds:
        ds.write(prob, 1)
    print("prob range:", round(float(prob.min()), 3),
          round(float(prob.max()), 3),
          "| mean:", round(float(prob.mean()), 3))

    inst = instances_from_prob(prob, thr=0.5, close_px=3, min_m2=4.0)
    recs = polygons_from_labels(inst, src.transform)
    print("raw instances:", len(recs))
    reg = [regularize(r["geometry"]) for r in recs]
    reg = [g for g in reg if g is not None and g.area >= 4.0]
    out = gpd.GeoDataFrame({"area_m2": [g.area for g in reg]}, geometry=reg,
                           crs=src.crs).to_crs(4326)
    out.to_file(APP / "whu_roofs.geojson", driver="GeoJSON")
    print("whu roofs:", len(out))

    # visual QA crops: dense slum + warehouse row (user's two screenshots)
    from PIL import Image
    vis = np.stack([arr[2], arr[3], arr[1]])
    lo, hi = np.percentile(vis, 2), np.percentile(vis, 98)
    vis8 = (np.clip((vis - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    from shapely.geometry import box as sb
    for name, (x0, y0, x1, y1) in {
            "slum": (1000, 1800, 2000, 2800),
            "warehouse": (1600, 300, 2600, 1300)}.items():
        crop = vis8[y0:y1, x0:x1].copy()
        sub = out.to_crs(src.crs)
        sub = sub[sub.intersects(sb(*rasterio.windows.bounds(
            rasterio.windows.Window(x0, y0, x1 - x0, y1 - y0),
            transform=src.transform)))]
        from PIL import ImageDraw
        im = Image.fromarray(crop)
        dr = ImageDraw.Draw(im)
        for g in sub.geometry:
            xs, ys = g.exterior.xy
            pts = [(x - x0, y - y0) for x, y in zip(xs, ys)]
            dr.polygon(pts, outline=(255, 0, 255))
        im.save(CROP_QA / f"{name}.png")
    json.dump({"model": "giswqs/whu-building-unetplusplus-efficientnet-b4",
               "n_roofs": len(out)},
              open(APP / "whu_metrics.json", "w"), indent=2)
    src.close()
    print("DONE")


if __name__ == "__main__":
    main()
