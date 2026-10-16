"""slum_pulse step 3a — news ingestion via RSS.

Sources:
  - newspaper RSS feeds from 01_data/00_source_inventory/social_signal_sources.csv (status=live)
  - Google News RSS queries from 01_data/03_derived_vector/gazetteer/gnews_queries.csv
    (every khwaeng + top-40 slums by population)

Output: 01_data/02_raw_imports/social/news_items.jsonl
Items outside the rolling 92-day window are dropped. Dedupe on title+publisher.

Run:  python fetch_news_rss.py [--window-days 92] [--max-gnews 200]
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html import unescape

import feedparser

from social_common import REPO, SOCIAL_RAW, ensure_dirs, polite_get, url_hash, write_jsonl

REGISTRY = REPO / "01_data" / "00_source_inventory" / "social_signal_sources.csv"
GNEWS_QUERIES = REPO / "01_data" / "03_derived_vector" / "gazetteer" / "gnews_queries.csv"
GNEWS_TMPL = "https://news.google.com/rss/search?q={q}&hl=th&gl=TH&ceid=TH:th"
TAG_RE = re.compile(r"<[^>]+>")


def clean(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub(" ", html or ""))).strip()


def entry_date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = getattr(entry, key, None)
        if st:
            return datetime(*st[:6], tzinfo=timezone.utc)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-days", type=int, default=92)
    ap.add_argument("--max-gnews", type=int, default=200)
    args = ap.parse_args()
    ensure_dirs()

    import pandas as pd
    reg = pd.read_csv(REGISTRY)
    feeds = reg[(reg["category"] == "newspaper_rss") & (reg["status"] == "live")]
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.window_days)

    items: list[dict] = []

    def add(entry, feed_label: str, publisher: str | None, query: str | None) -> None:
        title = clean(getattr(entry, "title", ""))
        if not title:
            return
        dt = entry_date(entry)
        if dt is None or dt < cutoff:
            return
        link = getattr(entry, "link", "")
        snippet = clean(getattr(entry, "summary", ""))[:600]
        items.append({
            "item_id": url_hash((publisher or feed_label) + title),
            "feed": feed_label,
            "query": query,
            "publisher": publisher or feed_label,
            "url": link,
            "title": title,
            "snippet": snippet,
            "pubdate": dt.isoformat(timespec="seconds"),
        })

    print("== direct newspaper feeds ==")
    for row in feeds.itertuples():
        parsed = feedparser.parse(row.url)
        n0 = len(items)
        for e in parsed.entries:
            add(e, row.source_id, None, None)
        print(f"  {row.source_id}: {len(parsed.entries)} entries, {len(items)-n0} in window")

    print("== google news queries ==")
    qdf = pd.read_csv(GNEWS_QUERIES).head(args.max_gnews)
    n_queries_live = 0
    for q in qdf.itertuples():
        url = GNEWS_TMPL.format(q=quote_query(q.query))
        r = polite_get(url, delay=0.0, timeout=45)
        parsed = feedparser.parse(r.content)
        n0 = len(items)
        for e in parsed.entries:
            # gnews titles look like "Headline - Publisher"
            pub = e.title.rsplit(" - ", 1)[-1].strip() if " - " in e.title else None
            add(e, "gnews", pub, q.query)
        n_queries_live += 1
        if n_queries_live % 25 == 0:
            print(f"  {n_queries_live}/{len(qdf)} queries, items so far {len(items)}")
        time.sleep(1.0)

    dedup = {it["item_id"]: it for it in items}
    rows = sorted(dedup.values(), key=lambda x: x["pubdate"], reverse=True)
    n = write_jsonl(SOCIAL_RAW / "news_items.jsonl", rows)
    print(f"\nkept {n} unique items "
          f"(from {len(items)} raw, {len(items)-n} dupes) in {args.window_days}-day window")
    pubs: dict[str, int] = {}
    for it in rows:
        pubs[it["publisher"]] = pubs.get(it["publisher"], 0) + 1
    print("top publishers:", sorted(pubs.items(), key=lambda kv: -kv[1])[:10])
    print(f"output: {SOCIAL_RAW / 'news_items.jsonl'}")
    return 0


def quote_query(q: str) -> str:
    import urllib.parse
    return urllib.parse.quote(q)


if __name__ == "__main__":
    sys.exit(main())
