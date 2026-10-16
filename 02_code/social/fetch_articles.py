"""slum_pulse step 3b — fetch full text of news items that mention gazetteer names.

Pipeline:
  1. pre-filter news_items.jsonl on title+snippet hitting any gazetteer variant
  2. resolve Google News redirect links to the publisher URL
  3. robots.txt check, polite fetch, trafilatura text extraction
  4. cache HTML under 05_scratch/social/html/, store extracted text

Output: 01_data/02_raw_imports/social/news_articles.jsonl

Run:  python fetch_articles.py [--max 400]
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.robotparser
from urllib.parse import urlparse

import pandas as pd
import trafilatura
from requests.sessions import Session

from social_common import GAZETTEER_DIR, SCRATCH_HTML, SOCIAL_RAW, UA, ensure_dirs, read_jsonl, url_hash, write_jsonl


def load_variants() -> dict[str, list[dict]]:
    gz = pd.read_csv(GAZETTEER_DIR / "slum_gazetteer.csv", dtype=str)
    by_variant: dict[str, list[dict]] = {}
    for v in gz.itertuples():
        by_variant.setdefault(v.variant, []).append(
            {"kind": v.kind, "cmt_id": v.cmt_id, "ambiguous": v.ambiguous == "True"})
    return by_variant


def find_matches(text: str, by_variant: dict[str, list[dict]]) -> list[dict]:
    hits = []
    for variant, refs in by_variant.items():
        if variant in text:
            hits.append({"variant": variant, "kind": refs[0]["kind"],
                         "ambiguous": refs[0]["ambiguous"]})
    return hits


class Robots:
    def __init__(self) -> None:
        self.cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def allowed(self, url: str, session: Session) -> bool:
        host = urlparse(url).netloc
        if host not in self.cache:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = session.get(f"https://{host}/robots.txt", headers=UA, timeout=15)
                if r.status_code == 200 and r.text.strip():
                    rp.parse(r.text.splitlines())
                    self.cache[host] = rp
                else:
                    self.cache[host] = None  # no robots -> allow
            except Exception:  # noqa: BLE001
                self.cache[host] = None
        rp = self.cache[host]
        return True if rp is None else rp.can_fetch(UA["User-Agent"], url)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=400)
    args = ap.parse_args()
    ensure_dirs()

    items = read_jsonl(SOCIAL_RAW / "news_items.jsonl")
    by_variant = load_variants()
    print(f"items: {len(items)}, gazetteer variants: {len(by_variant)}")

    candidates = []
    for it in items:
        hits = find_matches(it["title"] + " " + it["snippet"], by_variant)
        if hits:
            kinds = {h["kind"] for h in hits}
            if kinds & {"slum_name", "khwaeng", "district", "landmark"}:
                it["match_variants"] = hits
                candidates.append(it)
    print(f"candidates mentioning gazetteer terms: {len(candidates)}")

    session = Session()
    robots = Robots()
    out: list[dict] = []
    fetched, skipped = 0, 0
    t0 = time.time()
    for it in candidates[: args.max]:
        url = it["url"]
        # gnews article links are JS redirects (batchexecute) — not resolvable via plain
        # HTTP. Keep those items as snippet-only; extract_events works off title+snippet.
        if "news.google.com" in urlparse(url).netloc:
            out.append({
                "item_id": it["item_id"],
                "publisher": it["publisher"],
                "url": url,
                "pubdate": it["pubdate"],
                "title": it["title"],
                "text": "",
                "match_variants": it["match_variants"],
                "snippet_only": True,
            })
            fetched += 1
            continue
        final_url = url
        try:
            # resolve gnews redirect (fetches publisher page in one hop)
            r = session.get(url, headers=UA, timeout=30, allow_redirects=True)
            final_url = str(r.url)
            if r.status_code != 200 or "news.google.com" in final_url:
                skipped += 1
                continue
            if not robots.allowed(final_url, session):
                skipped += 1
                continue
            html = r.text
            if "news.google.com" in html[:2000].lower():
                skipped += 1
                continue
            cache = SCRATCH_HTML / f"{url_hash(final_url)}.html"
            cache.write_text(html, encoding="utf-8", errors="ignore")
            text = trafilatura.extract(html, include_comments=False) or ""
            out.append({
                "item_id": it["item_id"],
                "publisher": it["publisher"],
                "url": final_url,
                "pubdate": it["pubdate"],
                "title": it["title"],
                "text": text[:20000],
                "match_variants": it["match_variants"],
            })
            fetched += 1
            if fetched % 25 == 0:
                rate = fetched / max(1, time.time() - t0)
                print(f"  fetched {fetched} ({rate:.1f}/s), skipped {skipped}")
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            print(f"  fail {url[:60]}: {type(exc).__name__}")
        time.sleep(1.0)

    n = write_jsonl(SOCIAL_RAW / "news_articles.jsonl", out)
    print(f"\narticles stored: {n} (fetched {fetched}, skipped/failed {skipped})")
    print(f"output: {SOCIAL_RAW / 'news_articles.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
