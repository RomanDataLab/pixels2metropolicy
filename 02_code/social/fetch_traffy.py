"""slum_pulse step 2 — Traffy Fondue public share API ingestion (no token).

Public endpoint returns a rolling sample of shared reports (~100 of ~550 total,
spanning several years). Full traffy360 dataset needs an api-key (deferred phase).

Output: 01_data/02_raw_imports/social/traffy_reports.jsonl

Run:  python fetch_traffy.py
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone

from social_common import SOCIAL_RAW, ensure_dirs, polite_get, write_jsonl

API = "https://publicapi.traffy.in.th/share/search"
# generous Bangkok bbox (lon_min, lat_min, lon_max, lat_max)
BKK_BBOX = (100.32, 13.45, 100.95, 13.95)
KHW_ZHWA = re.compile(r"Khwaeng ([^,]+), Khet ([^,]+)")


def main() -> int:
    ensure_dirs()
    r = polite_get(API, params={"limit": 100}, timeout=90, retries=3)
    if r.status_code not in (200, 201):
        print(f"traffy: HTTP {r.status_code}, aborting")
        return 1
    data = r.json()
    results = data.get("results", [])
    print(f"traffy: {len(results)} reports of total={data.get('total')} (public window)")

    rows, dropped = [], {"no_coord": 0, "outside_bkk": 0}
    for rep in results:
        coord = rep.get("coord")
        if not coord or len(coord) != 2 or coord[0] is None or coord[1] is None:
            dropped["no_coord"] += 1
            continue
        lon, lat = float(coord[0]), float(coord[1])
        if not (BKK_BBOX[0] <= lon <= BKK_BBOX[2] and BKK_BBOX[1] <= lat <= BKK_BBOX[3]):
            dropped["outside_bkk"] += 1
            continue
        m = KHW_ZHWA.search(rep.get("address", "") or "")
        tags = [t.lstrip("#").strip() for t in rep.get("hashtag", []) if t]
        rows.append({
            "source": "traffy_public",
            "ts": rep.get("timestamp"),
            "lon": lon, "lat": lat,
            "khwaeng_en": m.group(1).strip() if m else None,
            "khet_en": m.group(2).strip() if m else None,
            "complaint_types": tags,
            "text": (rep.get("description") or "").strip(),
            # photo URLs dropped at ingestion (PDPA: UGC faces)
        })

    n = write_jsonl(SOCIAL_RAW / "traffy_reports.jsonl", rows)
    if rows:
        ts = sorted(x["ts"] for x in rows if x.get("ts"))
        print(f"kept {n} Bangkok reports; dropped {dropped}")
        print(f"date span in public window: {ts[0]} .. {ts[-1]}")
        types: dict[str, int] = {}
        for row in rows:
            for t in row["complaint_types"]:
                types[t] = types.get(t, 0) + 1
        top = sorted(types.items(), key=lambda kv: -kv[1])[:12]
        print("top complaint types:", ", ".join(f"{k}={v}" for k, v in top))
    print(f"output: {SOCIAL_RAW / 'traffy_reports.jsonl'}  ({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
