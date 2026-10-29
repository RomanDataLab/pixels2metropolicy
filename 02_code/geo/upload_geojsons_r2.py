"""Upload every repo geojson to Cloudflare R2 bucket 'pixels2metro' under geojson/.

Covers geojsons that were removed from GitHub (size / hygiene) — pages fetch
them from the public R2 base https://pub-7a6f5c500e1448d5b50de5ded48d85da.r2.dev.

Skips objects already present with the same size (safe to re-run).
Run:  py 02_code/geo/upload_geojsons_r2.py
"""
import json
import pathlib
import sys
import time

import boto3
from botocore.config import Config

REPO = pathlib.Path(__file__).resolve().parents[2]
CFG = json.loads(
    (pathlib.Path("G:/My Drive/J_Projects_Archive/config/config_cloudfare_r2_storage.json"))
    .read_text(encoding="utf-8")
)

BUCKET = "pixels2metro"
PREFIX = "geojson/"
PUB = "https://pub-7a6f5c500e1448d5b50de5ded48d85da.r2.dev"
EXCLUDE_DIRS = {".git", "01_data", "05_scratch", "05_models", "04_output", "node_modules", ".zcode"}


def main() -> int:
    s3 = boto3.client(
        "s3",
        aws_access_key_id=CFG["access_key_id_s3"],
        aws_secret_access_key=CFG["secret_access_key_s3"],
        endpoint_url="https://b78144ec9c59df732db4a8a5c39ef8c4.r2.cloudflarestorage.com",
        config=Config(retries={"max_attempts": 5}),
    )

    have = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            have[obj["Key"]] = obj["Size"]

    files = sorted(
        p for p in REPO.rglob("*.geojson")
        if not any(part in EXCLUDE_DIRS for part in p.relative_to(REPO).parts)
    )
    print(f"{len(files)} geojsons on disk, {len(have)} already in R2")

    done = failed = skipped = 0
    for p in files:
        key = PREFIX + p.relative_to(REPO).as_posix()
        size = p.stat().st_size
        if have.get(key) == size:
            skipped += 1
            continue
        t0 = time.time()
        try:
            s3.upload_file(str(p), BUCKET, key)
            done += 1
            print(f"ok  {key}  {size / 1e6:.1f} MB  {time.time() - t0:.0f}s")
        except Exception as e:
            failed += 1
            print(f"FAIL {key}: {e}", file=sys.stderr)
    print(f"uploaded {done}, skipped {skipped}, failed {failed}")
    print(f"public base: {PUB}/{PREFIX}<repo-relative-path>")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
