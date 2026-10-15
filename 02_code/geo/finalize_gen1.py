# -*- coding: utf-8 -*-
"""Regularize the dense gen1 SAM roofs and publish to app assets."""
import numpy as np
import rasterio
import geopandas as gpd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from gen3_fix import regularize

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "04_output/open_stack/bangkok/theos_block/gen1_roofs.geojson"
APP = ROOT / "theos_block/gen1_roofs.geojson"

src = rasterio.open(ROOT / "05_scratch/theos/theos_block.tif")
g = gpd.read_file(SRC).to_crs(src.crs)
reg = [regularize(x) for x in g.geometry]
reg = [x for x in reg if x is not None and x.area >= 4.0]
out = gpd.GeoDataFrame({"area_m2": [x.area for x in reg]}, geometry=reg,
                       crs=src.crs).to_crs(4326)
out.to_file(APP, driver="GeoJSON")
fills = [x.area / max(x.minimum_rotated_rectangle.area, 1e-9)
         for x in out.to_crs(src.crs).geometry[:800]]
print("dense gen1 regularized:", len(out),
      "| bbox-fill median:", round(float(np.median(fills)), 3))
