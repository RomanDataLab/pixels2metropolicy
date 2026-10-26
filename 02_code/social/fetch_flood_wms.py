"""social-economic sensing step — flood-frequency sampling from GISTDA Vallaris WMS.

Samples each community at 5 points (centroid + 4 offsets) using the z14 tile
grid (256px tiles cached); pixel alpha = flood-frequency intensity (0-255).
Same WMS layer/key as the main map tab ("Repeated flood areas").

Output: 04_output/social_patterns/bangkok/flood_scores.csv (cmt_id, flood_frac, mean_alpha)

Run:  python fetch_flood_wms.py
"""
from __future__ import annotations

import io
import math
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from PIL import Image

from social_common import GAZETTEER_DIR, SOCIAL_OUT, ensure_dirs

KEY = "eEpbI0F7pN5cL1EPQoZcdUfKPJVyhQWjfsssUJjk8TelSFYYDU1gDUV30SLY6MPT"
BASE = "https://api-gateway.gistda.or.th/api/2.0/resources/maps/flood-freq/wms"
LAYER = "6799ab8c6f832362f99030e6"
Z = 14
CACHE = Path(__file__).resolve().parents[2] / "05_scratch" / "social" / "wms_tiles"
UA = {"User-Agent": "Mozilla/5.0 Pixels2MetroPolicy-research"}


def tile_of(lon: float, lat: float):
    n = 2 ** Z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return int(x), int(y)


def tile_bbox(tx: int, ty: int):
    n = 2 ** Z
    lon0, lon1 = tx / n * 360 - 180, (tx + 1) / n * 360 - 180
    lat1 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
    lat0 = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty + 1) / n))))
    return lon0, lat0, lon1, lat1


def get_tile(tx: int, ty: int, cache: dict) -> Image.Image | None:
    if (tx, ty) in cache:
        return cache[(tx, ty)]
    f = CACHE / f"{Z}_{tx}_{ty}.png"
    if f.exists():
        im = Image.open(f).convert("RGBA")
    else:
        bb = tile_bbox(tx, ty)
        r = requests.get(BASE, params={
            "service": "WMS", "version": "1.1.1", "request": "GetMap",
            "layers": LAYER, "styles": "", "format": "image/png",
            "transparent": "true", "width": "256", "height": "256",
            "srs": "EPSG:4326", "bbox": ",".join(map(str, bb)), "api_key": KEY,
        }, headers=UA, timeout=40)
        if r.status_code != 200 or "image" not in r.headers.get("content-type", ""):
            cache[(tx, ty)] = None
            return None
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_bytes(r.content)
        im = Image.open(io.BytesIO(r.content)).convert("RGBA")
        time.sleep(0.1)
    cache[(tx, ty)] = im
    return im


def alpha_at(im: Image.Image, lon: float, lat: float) -> int:
    bb = im.getbbox()
    lon0, lat0, lon1, lat1 = tile_bbox(*im.tile_xy)  # set by caller
    px = int((lon - lon0) / (lon1 - lon0) * im.width)
    py = int((lat1 - lat) / (lat1 - lat0) * im.height)
    px = min(im.width - 1, max(0, px))
    py = min(im.height - 1, max(0, py))
    return im.getpixel((px, py))[3]


def main() -> int:
    ensure_dirs()
    import geopandas as gpd
    poly = gpd.read_parquet(GAZETTEER_DIR / "slum_polygons.parquet")
    rows = []
    cache: dict = {}
    cache_im: dict = {}
    for c in poly.itertuples():
        pt = c.geometry.representative_point()
        lon, lat = float(pt.x), float(pt.y)
        pts = [(lon, lat), (lon + 0.0015, lat), (lon - 0.0015, lat),
               (lon, lat + 0.0015), (lon, lat - 0.0015)]
        hits, alphas = 0, []
        for plo, pla in pts:
            t = tile_of(plo, pla)
            im = cache_im.get(t)
            if im is None:
                base_im = get_tile(*t, cache=cache)
                if base_im is None:
                    continue
                base_im.tile_xy = t
                cache_im[t] = base_im
                im = base_im
            a = alpha_at(im, plo, pla)
            if a > 20:
                hits += 1
                alphas.append(a)
        rows.append({"cmt_id": str(c.CMT_ID),
                     "flood_frac": round(hits / len(pts), 2),
                     "flood_alpha": int(sum(alphas) / len(alphas)) if alphas else 0})
    df = pd.DataFrame(rows)
    df.to_csv(SOCIAL_OUT / "flood_scores.csv", index=False, encoding="utf-8-sig")
    print(f"communities sampled: {len(df)}; flooded(>0): {(df.flood_frac>0).sum()}")
    print(df.sort_values(["flood_frac", "flood_alpha"], ascending=False).head(8).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
