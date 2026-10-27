# -*- coding: utf-8 -*-
"""Gen 8 - hotosm/dinov3s-buildings zero-shot on THEOS true color.

Model: frozen DINOv3 ViT-S/16 + UperNet decoder (fAIr production model),
  self-contained ONNX. Three heads: mask logit, boundary logit, signed
  distance logit. Recipe mirrors kshitijrajsharma/dinov3-hot serve.py:
  - uint8 RGB / 255, HOT_MEAN/HOT_STD normalisation
  - 256 px window, 192 stride, Gaussian kernel stitch (sigma = 0.125 * 256)
  - mask prob = sigmoid(ch0); distance = tanh(ch2)
  - instance split: peak_local_max on distance for small blobs,
    h-maxima (depth 0.2) for blobs > 1500 px; watershed on -distance
  - catalog postprocess params (confidence_threshold 0.4371 etc.)
Input: THEOS true color (b3, b4, b2) at 0.5 m, p2/p98 stretch to uint8
  (same stretch as every QA render in this repo).

Writes: theos_block/dinov3_prob.tif, dinov3_roofs.geojson,
        dinov3_metrics.json, theos_block/qa_dinov3_{point300,slum}.png
"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import geopandas as gpd
import onnxruntime as ort
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.signal.windows import gaussian as gauss1d
from skimage.feature import peak_local_max
from skimage.morphology import h_maxima
from skimage.segmentation import watershed
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).parent))
from segment_core import SCENE, APP, ROOT, H, W, polygons_from_labels
from gen3_fix import regularize

HOT_MEAN = np.array([0.4296737853453577, 0.4001659668453235,
                     0.34333372802741474], dtype=np.float32)
HOT_STD = np.array([0.2056069389373208, 0.16738555558380538,
                    0.1598986422586595], dtype=np.float32)

# fAIr-models catalog defaults (models/dinov3s_buildings/pipeline.py)
THR = 0.4371
SEED_MIN_DISTANCE = 6
LARGE_BLOB_AREA_PX = 1500
H_MAXIMA_DEPTH = 0.2
MIN_AREA_M2 = 2.6465
WINDOW = 256
STRIDE = 192


def gaussian_kernel(size, sigma_frac=0.125):
    w = gauss1d(size, std=sigma_frac * size)
    k = np.outer(w, w)
    return (k / k.max()).astype(np.float32)


def instance_separate_fair(mask_prob, distance):
    """Verbatim port of dinov3_hot.infer.instance_separate."""
    fg = mask_prob > THR
    if not fg.any():
        return np.zeros_like(fg, dtype=np.uint32)
    components, _ = ndimage.label(fg)
    is_large = np.bincount(components.ravel()) > LARGE_BLOB_AREA_PX
    is_large[0] = False
    large_mask = is_large[components]
    small_mask = fg & ~large_mask

    seeds = np.zeros_like(fg, dtype=bool)
    coords = peak_local_max(distance, min_distance=SEED_MIN_DISTANCE,
                            labels=small_mask.astype(np.uint8),
                            exclude_border=False)
    if len(coords):
        seeds[tuple(coords.T)] = True
    if large_mask.any():
        large_distance = distance.astype(np.float32, copy=True)
        large_distance[~large_mask] = float(large_distance[large_mask].min())
        seeds |= h_maxima(large_distance, H_MAXIMA_DEPTH).astype(bool) & large_mask

    markers, n_markers = ndimage.label(seeds)
    if n_markers == 0:
        return ndimage.label(fg)[0].astype(np.uint32)
    return watershed(-distance, markers=markers, mask=fg).astype(np.uint32)


def main():
    model_path = Path(r"C:\Users\Real\.cache\huggingface\hub"
                      r"\models--hotosm--dinov3s-buildings\snapshots"
                      r"\f7254545dfbbf10a40594d5a5fb62136902000ae\model.onnx")
    so = ort.SessionOptions()
    so.intra_op_num_threads = 8
    sess = ort.InferenceSession(str(model_path), so,
                                providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name

    src = rasterio.open(SCENE)
    arr = src.read().astype(np.float32)
    vis = np.stack([arr[2], arr[3], arr[1]])
    lo, hi = np.percentile(vis, 2), np.percentile(vis, 98)
    img = (np.clip((vis - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    img_hwc = np.ascontiguousarray(img.transpose(1, 2, 0))

    mean_arr = HOT_MEAN.reshape(3, 1, 1)
    std_arr = HOT_STD.reshape(3, 1, 1)

    mask_acc = np.zeros((H, W), dtype=np.float32)
    dist_acc = np.zeros((H, W), dtype=np.float32)
    weight_acc = np.zeros((H, W), dtype=np.float32)
    kernel = gaussian_kernel(WINDOW)

    rows = list(range(0, H - WINDOW + 1, STRIDE))
    cols = list(range(0, W - WINDOW + 1, STRIDE))
    if rows[-1] + WINDOW < H:
        rows.append(H - WINDOW)
    if cols[-1] + WINDOW < W:
        cols.append(W - WINDOW)

    positions = [(r, c) for r in rows for c in cols]
    print(f"windows: {len(positions)}", flush=True)
    for n, (r, c) in enumerate(positions):
        tile = img_hwc[r:r + WINDOW, c:c + WINDOW]
        x = tile.astype(np.float32).transpose(2, 0, 1) / 255.0
        x = (x - mean_arr) / std_arr
        logits = sess.run(None, {iname: x[None]})[0][0]
        mask_acc[r:r + WINDOW, c:c + WINDOW] += \
            (1.0 / (1.0 + np.exp(-logits[0]))) * kernel
        dist_acc[r:r + WINDOW, c:c + WINDOW] += np.tanh(logits[2]) * kernel
        weight_acc[r:r + WINDOW, c:c + WINDOW] += kernel
        if n % 50 == 0:
            print(f"window {n}/{len(positions)} ({r},{c})", flush=True)

    prob = mask_acc / np.maximum(weight_acc, 1e-6)
    distance = dist_acc / np.maximum(weight_acc, 1e-6)

    profile = src.profile.copy()
    profile.update(count=1, dtype="float32")
    with rasterio.open(APP / "dinov3_prob.tif", "w", **profile) as ds:
        ds.write(prob, 1)
    print("prob range:", round(float(prob.min()), 3), round(float(prob.max()), 3),
          "| mean:", round(float(prob.mean()), 3),
          "| p99:", round(float(np.percentile(prob, 99)), 3), flush=True)

    inst = instance_separate_fair(prob, distance)
    print("instances:", int(inst.max()), flush=True)

    recs = polygons_from_labels(inst, src.transform, min_m2=MIN_AREA_M2)
    reg = [regularize(r["geometry"]) for r in recs]
    reg = [g for g in reg if g is not None and g.area >= 4.0]
    out = gpd.GeoDataFrame({"area_m2": [g.area for g in reg]}, geometry=reg,
                           crs=src.crs).to_crs(4326)
    out.to_file(APP / "dinov3_roofs.geojson", driver="GeoJSON")
    print("dinov3 roofs:", len(out), flush=True)

    # QA renders at the same crops as gen5c (user 300 m point + slum)
    from pyproj import Transformer
    from rasterio.transform import rowcol
    tr_ = Transformer.from_crs(4326, src.crs, always_xy=True)
    px, py = tr_.transform(100.602973, 13.928059)
    pr, pc = rowcol(src.transform, px, py)
    sub = out.to_crs(src.crs)
    inv = ~src.transform
    for name, (rr, cc) in {"point300": (pr, pc), "slum": (2100, 1500)}.items():
        r0 = max(int(rr) - 320, 0); c0 = max(int(cc) - 320, 0)
        im = Image.fromarray(img_hwc[r0:r0 + 640, c0:c0 + 640].copy())
        dr = ImageDraw.Draw(im)
        win = box(*rasterio.windows.bounds(
            rasterio.windows.Window(c0, r0, 640, 640),
            transform=src.transform))
        def draw(g):
            # map coords to crop pixels via the inverse geotransform
            if g.geom_type == "MultiPolygon":
                for p in g.geoms:
                    draw(p)
            elif g.geom_type == "Polygon":
                pts = [((inv * (x, y))[0] - c0, (inv * (x, y))[1] - r0)
                       for x, y in zip(*g.exterior.xy)]
                dr.polygon(pts, outline=(255, 0, 255))
        for g in sub[sub.intersects(win)].geometry:
            draw(g)
        im.resize((760, 760)).save(APP / f"qa_dinov3_{name}.png")
        print("qa:", name, flush=True)

    json.dump({"model": "hotosm/dinov3s-buildings (zero-shot, fAIr recipe)",
               "thr": THR, "stride": STRIDE, "n_roofs": len(out),
               "prob_mean": round(float(prob.mean()), 4),
               "prob_p99": round(float(np.percentile(prob, 99)), 4)},
              open(APP / "dinov3_metrics.json", "w"), indent=2)
    src.close()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
