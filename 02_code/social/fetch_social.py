"""slum_pulse step 6a — Telegram public channel preview ingestion (t.me/s/, no login).

Channels come from the source registry (category=telegram). Only the public web
preview is read; ~20 most recent messages per channel, with ?before= pagination
when message ids are present. ScrapeCreators (FB/TikTok) is a deferred phase.

Output: 01_data/02_raw_imports/social/telegram_messages.jsonl

Run:  python fetch_social.py [--pages 3]
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timezone

from social_common import REPO, SOCIAL_RAW, ensure_dirs, polite_get, write_jsonl

REGISTRY = REPO / "01_data" / "00_source_inventory" / "social_signal_sources.csv"
MSG_RE = re.compile(
    r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
TIME_RE = re.compile(r'<time[^>]*datetime="([^"]+)"')
ID_RE = re.compile(r'data-post="([^"]+)"')
TAG_RE = re.compile(r"<[^>]+>")


def parse_channel(html: str, channel: str) -> list[dict]:
    # messages and their ids appear in document order; pair them by position
    blocks = re.split(r'class="tgme_widget_message_wrap', html)
    msgs = []
    for block in blocks[1:]:
        tm = MSG_RE.search(block)
        dt = TIME_RE.search(block)
        pid = ID_RE.search(block)
        if not tm:
            continue
        text = TAG_RE.sub(" ", tm.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        if not text or text.startswith("Channel "):
            continue
        msgs.append({
            "source": "telegram",
            "channel": channel,
            "msg_ref": pid.group(1) if pid else None,
            "ts": dt.group(1) if dt else None,
            "text": text[:2000],
        })
    return msgs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=3)
    args = ap.parse_args()
    ensure_dirs()

    import pandas as pd
    reg = pd.read_csv(REGISTRY)
    channels = reg[(reg["category"] == "telegram") & (reg["status"] == "live")]
    print(f"live telegram channels: {list(channels['source_id'])}")

    rows: dict[tuple, dict] = {}
    for ch in channels.itertuples():
        base = ch.url.rstrip("/")          # https://t.me/s/<channel>
        got = 0
        before = None
        for page in range(args.pages):
            url = base + (f"?before={before}" if before else "")
            try:
                r = polite_get(url, timeout=30)
            except Exception as exc:  # noqa: BLE001
                print(f"  {ch.source_id} page {page}: {type(exc).__name__}")
                break
            msgs = parse_channel(r.text, ch.source_id)
            if not msgs:
                break
            for m in msgs:
                key = (m["channel"], m["msg_ref"] or m["text"][:80])
                rows.setdefault(key, m)
            got += len(msgs)
            last_ref = msgs[-1]["msg_ref"]
            if not last_ref:
                break
            before = int(last_ref.split("/")[-1])
            time.sleep(1.0)
        print(f"  {ch.source_id}: {got} messages")

    out = sorted(rows.values(), key=lambda m: m.get("ts") or "")
    n = write_jsonl(SOCIAL_RAW / "telegram_messages.jsonl", out)
    print(f"\nmessages stored: {n}")
    print(f"output: {SOCIAL_RAW / 'telegram_messages.jsonl'}  "
          f"({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
