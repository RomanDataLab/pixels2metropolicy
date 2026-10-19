# -*- coding: utf-8 -*-
"""Shared geometry core + publication gates for all generations.

Rules (per the approved algorithm):
  - inference accumulates PROBABILITIES in one global raster (weighted by
    window distance-from-edge); no per-window instance concatenation
  - instances extracted once globally: threshold -> morphology -> watershed
    split on the distance transform
  - gates decide publication; failing generations are not written to app
    assets at all
"""
from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import geopandas as gpd
from scipy import ndimage
from shapely.geometry import shape, box

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "05_scratch/theos/theos_block.tif"
APP = ROOT / "theos_block"
H, W = 4738, 5002


def edge_weights(h, w):
    """Triangular distance-from-edge weight, anti-seam."""
    yy = np.minimum(np.arange(h) + 1, h - np.arange(h))
    xx = np.minimum(np.arange(w) + 1, w - np.arange(w))
    return np.minimum.outer(yy, xx).astype(np.float32)


def instances_from_prob(prob, thr=0.5, close_px=4, min_m2=8.0):
    """Global instance extraction: threshold, close, watershed split."""
    binary = prob >= thr
    binary = ndimage.binary_closing(binary, np.ones((close_px, close_px)))
    binary = ndimage.binary_opening(binary, np.ones((2, 2)))
    dist = ndimage.distance_transform_edt(binary)
    # vectorized local-max markers (peak_local_max was O(N*d^2) python-loop
    # slow at 23.7M px - >90 min stall)
    mx = ndimage.maximum_filter(dist, size=9)
    peaks = (dist == mx) & (dist > 1.5) & binary
    markers, _ = ndimage.label(peaks)
    from skimage.segmentation import watershed
    lab = watershed(-dist, markers, mask=binary)
    # drop small instances via bincount (vectorized; per-label masking was
    # O(labels*N) and stalled for hours)
    counts = np.bincount(lab.ravel())
    keep = np.zeros(len(counts), dtype=bool)
    keep[1:] = counts[1:] * 0.25 >= min_m2
    return np.where(keep[lab], lab, 0)


def polygons_from_labels(lbl, transform, min_m2=4.0, max_m2=5000.0):
    # single C-level pass over the label raster (per-label loops were
    # quadratic and unusable at tens of thousands of instances)
    recs = []
    for geom, val in rasterio.features.shapes(lbl.astype("int32"),
                                              mask=lbl > 0,
                                              transform=transform):
        if val <= 0:
            continue
        g = shape(geom)
        if min_m2 <= g.area <= max_m2:
            recs.append({"area_m2": float(g.area), "geometry": g})
    return recs


# ---------------------------------------------------------------- gates ---
def _borders_mask(shape, transform, which):
    """Restore border layers from git (main branch) if absent on disk."""
    import subprocess, tempfile, os
    paths = {"water": "04_output/open_stack/bangkok/theos_block/borders_water.geojson",
             "highway": "04_output/open_stack/bangkok/theos_block/borders_highway.geojson"}
    frames = []
    for name in which:
        p = ROOT / paths[name]
        if not p.exists():
            blob = subprocess.run(
                ["git", "show", f"main:{paths[name]}"],
                capture_output=True, cwd=ROOT).stdout
            f = tempfile.NamedTemporaryFile(suffix=".geojson", delete=False)
            f.write(blob); f.close()
            p = Path(f.name)
        frames.append(gpd.read_file(p).to_crs(32647))
    g = gpd.GeoDataFrame(pd_concat(frames), crs=32647) if frames else None
    union = unary_union_all([x for f in frames for x in f.geometry])
    return rasterio.features.rasterize(
        [(union.buffer(1.0), 1)], out_shape=shape, transform=transform,
        fill=0, dtype="uint8").astype(bool)


def pd_concat(frames):
    import pandas as pd
    return pd.concat(frames, ignore_index=True)


def unary_union_all(geoms):
    from shapely.ops import unary_union
    return unary_union(geoms) if geoms else box(0, 0, 0, 0)


def bright_nonveg(src, arr):
    """Gate reference: the AFFINE-ALIGNED OVERTURE teacher, not brightness.

    Calibration killed the brightness idea: teacher roof px inside
    bright>p60 & NIR<400 = 5%%, brightness p50 inside vs outside teacher =
    339.7 vs 336.7 - no signal in this hazy scene. The aligned teacher is
    the only independent ground for outline agreement.
    """
    t = gpd.read_file(ROOT / "05_scratch/yolo/teacher_aligned.geojson"
                      ).to_crs(src.crs)
    return rasterio.features.rasterize(
        [(g, 1) for g in t.geometry], out_shape=src.shape,
        transform=src.transform, fill=0, dtype="uint8").astype(bool)


def evaluate(gdf, src, arr, name, overture_n=12364):
    """Publication gates. Returns (passed, report-dict)."""
    g = gdf.to_crs(src.crs)
    report = {"name": name, "count": len(g)}
    if len(g) == 0:
        report["fail"] = "empty"
        return False, report

    tr = src.transform
    ref = bright_nonveg(src, arr)

    # gate 3: bbox fill
    fills = [x.area / max(x.minimum_rotated_rectangle.area, 1e-9)
             for x in g.geometry]
    report["fill_med"] = round(float(np.median(fills)), 3)
    g3 = report["fill_med"] >= 0.7

    # gate 1: sampled outline vs bright-nonveg IoU
    rng = np.random.default_rng(0)
    idx = rng.choice(len(g), min(200, len(g)), replace=False)
    ious = []
    for i in idx:
        geom = g.geometry.iloc[int(i)]
        minx, miny, maxx, maxy = geom.bounds
        win = rasterio.windows.from_bounds(minx - 1, miny - 1,
                                           maxx + 1, maxy + 1,
                                           transform=tr)
        r0 = max(int(win.row_off), 0); c0 = max(int(win.col_off), 0)
        r1 = min(int(win.row_off + win.height) + 1, H)
        c1 = min(int(win.col_off + win.width) + 1, W)
        if r1 <= r0 or c1 <= c0:
            continue
        sub_tr = tr * rasterio.transform.Affine.translation(c0, r0)
        m = rasterio.features.rasterize(
            [(geom, 1)], out_shape=(r1 - r0, c1 - c0), transform=sub_tr,
            fill=0, dtype="uint8").astype(bool)
        r_ = ref[r0:r1, c0:c1]
        inter = (m & r_).sum()
        union = (m | r_).sum()
        # restrict union to polygon neighbourhood to avoid punishing
        # neighbouring roofs: ref within 2 m of polygon
        near = ndimage.binary_dilation(m, iterations=4) & r_
        union = (m | near).sum()
        if union:
            ious.append(inter / union)
    report["iou_med"] = round(float(np.median(ious)), 3) if ious else 0.0
    g1 = report["iou_med"] >= 0.5

    # gate 2: road/water crossing < 2%
    borders = _borders_mask(src.shape, tr, ("water", "highway"))
    crossed = 0
    from shapely import STRtree
    bgeoms = [g2 for g2 in _borders_frames_flattened()]
    t = STRtree(bgeoms) if bgeoms else None
    if t is not None:
        cand = t.query(g.geometry, predicate="intersects")
        crossed = len(set(cand[1].tolist())) if cand.ndim == 2 else 0
    report["cross_pct"] = round(100 * crossed / len(g), 2)
    g2 = report["cross_pct"] < 2.0

    # gate 4: count within +-50% of overture
    report["overture_ratio"] = round(len(g) / overture_n, 2)
    g4 = 0.5 <= report["overture_ratio"] <= 1.5

    report["gates"] = {"iou": g1, "cross": g2, "fill": g3, "count": g4}
    report["passed"] = g1 and g2 and g3 and g4
    return report["passed"], report


_BORDER_FRAMES = None
def _borders_frames_flattened():
    global _BORDER_FRAMES
    if _BORDER_FRAMES is None:
        import subprocess, tempfile
        frames = []
        for name, rel in [
                ("water", "04_output/open_stack/bangkok/theos_block/borders_water.geojson"),
                ("highway", "04_output/open_stack/bangkok/theos_block/borders_highway.geojson")]:
            p = ROOT / rel
            if not p.exists():
                blob = subprocess.run(["git", "show", f"main:{rel}"],
                                      capture_output=True, cwd=ROOT).stdout
                f = tempfile.NamedTemporaryFile(suffix=".geojson", delete=False)
                f.write(blob); f.close()
                p = Path(f.name)
            frames.append(gpd.read_file(p).to_crs(32647))
        _BORDER_FRAMES = [x for f in frames for x in f.geometry]
    return _BORDER_FRAMES
