"""Upload landing videos to Cloudflare R2 bucket 'pixels2metro'.

Reads credentials from G:/My Drive/J_Projects_Archive/config/config_cloudfare_r2_storage.json.
Deduplicated upload list: p2m-* clips shared by both landings go once under p2p/.
UIP originals (bigger quality) are uploaded for direct webpage playback.
"""
import json
import pathlib
import sys
import time

import boto3
from botocore.config import Config

ROOT = pathlib.Path(__file__).resolve().parent
CFG = json.loads(
    (pathlib.Path("G:/My Drive/J_Projects_Archive/config/config_cloudfare_r2_storage.json"))
    .read_text(encoding="utf-8")
)

BUCKET = "pixels2metro"
ENDPOINT = "https://b78144ec9c59df732db4a8a5c39ef8c4.r2.cloudflarestorage.com"

UIP = ROOT / "Urban_Intelligence_Platform_landing" / "web" / "media"
P2P = ROOT / "Pixels_to_Metro_Policy_landing" / "web" / "media"

UPLOADS = [
    # (local path, object key)
    (UIP / "assess.mp4", "uip/assess.mp4"),
    (UIP / "clip-fire.mp4", "uip/clip-fire.mp4"),
    (UIP / "clip-flood.mp4", "uip/clip-flood.mp4"),
    (UIP / "clip-street.mp4", "uip/clip-street.mp4"),
    (UIP / "design.mp4", "uip/design.mp4"),
    (UIP / "program.mp4", "uip/program.mp4"),
    (UIP / "priority.mp4", "uip/priority.mp4"),
    (UIP / "seg.mp4", "uip/seg.mp4"),
    (UIP / "walkthrough.mp4", "uip/walkthrough.mp4"),
    (UIP / "originals" / "participate.mp4", "uip/participate.mp4"),
    (UIP / "originals" / "toolkits.mp4", "uip/toolkits.mp4"),
    (P2P / "p2m-fire-makkasan.mp4", "p2p/p2m-fire-makkasan.mp4"),
    (P2P / "p2m-fire-makkasan.webm", "p2p/p2m-fire-makkasan.webm"),
    (P2P / "p2m-flood-lat-krabang.mp4", "p2p/p2m-flood-lat-krabang.mp4"),
    (P2P / "p2m-flood-lat-krabang.webm", "p2p/p2m-flood-lat-krabang.webm"),
]


def main() -> int:
    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=CFG["access_key_id_s3"],
        aws_secret_access_key=CFG["secret_access_key_s3"],
        region_name="auto",
        config=Config(max_pool_connections=4, retries={"max_attempts": 3}),
    )
    failed = []
    for path, key in UPLOADS:
        if not path.is_file():
            print(f"MISSING {path}", flush=True)
            failed.append(key)
            continue
        mb = path.stat().st_size / 1e6
        t0 = time.time()
        try:
            s3.upload_file(
                str(path),
                BUCKET,
                key,
                ExtraArgs={"ContentType": "video/mp4" if key.endswith(".mp4") else "video/webm"},
            )
            print(f"OK {key} {mb:.1f}MB in {time.time() - t0:.0f}s", flush=True)
        except Exception as exc:  # noqa: BLE001 - report and continue with rest
            print(f"FAIL {key}: {exc}", flush=True)
            failed.append(key)
    print("DONE failed=" + (",".join(failed) if failed else "none"), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
