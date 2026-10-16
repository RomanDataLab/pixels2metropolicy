"""slum_pulse step 5 — Pantip public search ingestion (titles, no login).

Queries: top-20 slums by population + top-30 khwaeng by slum population.
Parses the Next.js __NEXT_DATA__ payload of the public search page; strips the
{{em}} highlight markers. Public threads only; usernames never stored (PDPA).

Output: 01_data/02_raw_imports/social/pantip_threads.jsonl

Run:  python fetch_pantip.py [--n-slums 20] [--n-khwaeng 30]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone

from social_common import GAZETTEER_DIR, SOCIAL_RAW, ensure_dirs, polite_get, write_jsonl

SEARCH = "https://pantip.com/search?q="
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def search_pantip(query: str) -> list[dict]:
    r = polite_get(SEARCH + query, timeout=40)
    m = NEXT_DATA.search(r.text)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        entries = (data["props"]["initialProps"]["pageProps"]
                   .get("resultList", {}).get("data", []))
    except Exception:  # noqa: BLE001
        return []
    out = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        title = re.sub(r"\{\{/?e+e?m\}\}", "", e.get("title", "") or "").strip()
        tid = e.get("_id") or e.get("topic_id")
        if not title or not tid:
            continue
        ts = e.get("created_time") or e.get("disp_date") or e.get("date")
        out.append({
            "source": "pantip",
            "topic_id": str(tid),
            "url": f"https://pantip.com/topic/{tid}",
            "title": title,
            "ts": str(ts) if ts else None,
            "query": query,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-slums", type=int, default=20)
    ap.add_argument("--n-khwaeng", type=int, default=30)
    args = ap.parse_args()
    ensure_dirs()

    import pandas as pd
    poly = pd.read_parquet(GAZETTEER_DIR / "slum_polygons.parquet")
    gz = pd.read_csv(GAZETTEER_DIR / "slum_gazetteer.csv", dtype=str)

    queries: list[tuple[str, str]] = []
    top_slums = poly.sort_values("POP_TOTAL", ascending=False).head(args.n_slums)
    for s in top_slums.itertuples():
        name = s.CMT_NAME[3:] if s.CMT_NAME.startswith("ชุมชน") else s.CMT_NAME
        queries.append((name, "slum"))
    kpop = (poly.groupby("SNAME")["POP_TOTAL"].sum().sort_values(ascending=False))
    for k in kpop.head(args.n_khwaeng).index:
        queries.append((k, "khwaeng"))

    rows: dict[str, dict] = {}
    for q, kind in queries:
        try:
            hits = search_pantip(q)
        except Exception as exc:  # noqa: BLE001
            print(f"  query '{q}': {type(exc).__name__}")
            continue
        for h in hits:
            h["query_kind"] = kind
            rows.setdefault(h["topic_id"], h)
        print(f"  [{kind}] '{q}': {len(hits)} threads")
        time.sleep(1.5)

    out = sorted(rows.values(), key=lambda h: h.get("ts") or "", reverse=True)
    n = write_jsonl(SOCIAL_RAW / "pantip_threads.jsonl", out)
    print(f"\nthreads stored: {n} unique")
    print(f"output: {SOCIAL_RAW / 'pantip_threads.jsonl'}  "
          f"({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
