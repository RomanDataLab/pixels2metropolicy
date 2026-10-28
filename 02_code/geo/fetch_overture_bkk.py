# -*- coding: utf-8 -*-
"""Fetch Overture Maps buildings for the Bangkok AOI and store a parquet layer.

Output: 01_data/03_derived_vector/buildings/bangkok_buildings_overture.parquet
(WGS84, columns: id, geometry, height_m). Streaming batch write keeps memory
bounded for the ~3M-building AOI. No auth needed (Overture public reader).

Run:  py -3.13 02_code/geo/fetch_overture_bkk.py [--bbox lon_min lat_min lon_max lat_max]
"""
import argparse
import urllib.request
from pathlib import Path

# CloudFront in front of stac.overturemaps.org 403s the default python-urllib UA
_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", "Mozilla/5.0")]
urllib.request.install_opener(_opener)

import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from shapely import wkb

import overturemaps

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "01_data/03_derived_vector/buildings/bangkok_buildings_overture.parquet"

# default AOI mirrors fetch_building_footprints.py's Bangkok box
BKK_BBOX = (100.30, 13.40, 100.95, 13.95)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"))
    args = ap.parse_args()
    bbox = tuple(args.bbox) if args.bbox else BKK_BBOX

    try:
        reader = overturemaps.record_batch_reader("building", bbox=bbox)
    except TypeError:  # overturemaps 0.x kwarg names
        reader = overturemaps.record_batch_reader(theme="buildings", type="building", bbox=bbox)

    schema = pa.schema([
        ("id", pa.string()),
        ("height_m", pa.float64()),
        ("geometry", pa.binary()),
    ])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".parquet.tmp")
    writer = pq.ParquetWriter(tmp, schema, compression="zstd")
    total = 0
    try:
        while True:
            try:
                batch = reader.read_next_batch()
            except StopIteration:
                break
            if batch.num_rows == 0:
                continue
            cols = {c: batch.column(c).to_pylist() if c != "geometry" else None
                    for c in ("id",)}
            ids = batch.column("id").to_pylist() if "id" in batch.column_names else [None] * batch.num_rows
            hcol = "height" if "height" in batch.column_names else None
            heights = batch.column(hcol).to_pylist() if hcol else [None] * batch.num_rows
            geoms = batch.column("geometry").to_pylist()
            # keep raw WKB bytes; validate cheaply via shapely only for emptiness
            keep_ids, keep_h, keep_g = [], [], []
            for i, h, g in zip(ids, heights, geoms):
                if g is None:
                    continue
                keep_ids.append(str(i) if i is not None else None)
                keep_h.append(float(h) if h is not None else None)
                keep_g.append(bytes(g))
            if not keep_g:
                continue
            table = pa.table({"id": keep_ids, "height_m": keep_h, "geometry": keep_g}, schema=schema)
            writer.write_table(table)
            total += len(keep_g)
            print(f"  {total} buildings...", flush=True)
    finally:
        writer.close()
    tmp.replace(OUT)
    print(f"done: {total} buildings -> {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
