"""slum_pulse step 6b — Telethon ingestion for Telegram GROUPS (no public preview).

Groups (chat communities) have no t.me/s web preview; only channels do. This
script reads them via the official MTProto API using a real account
("lovedesignbuild"): official API usage, read-only, flood-wait aware, PII
stripped at write time (usernames/ids/photos never stored).

Prerequisite (one-time):
  1. my.telegram.org (account phone) -> API development tools -> api_id + api_hash
  2. Save as G:\\My Drive\\J_Projects_Archive\\config\\config_telegram.json:
       {"telegram_api_id": 12345, "telegram_api_hash": "..."}
  3. First run asks for the login code sent to the phone, then caches
     05_scratch/social/telethon.session (never re-login).

Targets: registry rows category=telegram_group.
Output: merges into 01_data/02_raw_imports/social/telegram_messages.jsonl.

Run:  python fetch_telethon.py [--window-days 92] [--join]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from social_common import REPO, SOCIAL_RAW, ensure_dirs, read_jsonl, write_jsonl

CONFIG = Path(r"G:\My Drive\J_Projects_Archive\config\config_telegram.json")
SESSION = REPO / "05_scratch" / "social" / "telethon.session"
REGISTRY = REPO / "01_data" / "00_source_inventory" / "social_signal_sources.csv"


async def run(window_days: int, do_join: bool) -> int:
    try:
        from telethon import TelegramClient
    except ImportError:
        print("telethon not installed: pip install telethon")
        return 1
    if not CONFIG.exists():
        print(f"missing {CONFIG} — create it with telegram_api_id / telegram_api_hash")
        return 1
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

    import pandas as pd
    reg = pd.read_csv(REGISTRY)
    targets = reg[reg["category"] == "telegram_group"]["url"].tolist()
    print(f"targets: {targets}")

    ensure_dirs()
    client = TelegramClient(str(SESSION), cfg["telegram_api_id"], cfg["telegram_api_hash"])
    await client.start()  # asks for phone/code once, then uses the session file

    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows: list[dict] = []
    for url in targets:
        username = url.rstrip("/").split("/")[-1]
        try:
            entity = await client.get_entity(username)
            if do_join:
                from telethon.tl.functions.channels import JoinChannelRequest
                try:
                    await client(JoinChannelRequest(entity))
                except Exception as exc:  # noqa: BLE001
                    print(f"  {username}: join failed/already member ({type(exc).__name__})")
            n = 0
            async for msg in client.iter_messages(entity, offset_date=datetime.now(timezone.utc),
                                                  reverse=False):
                if msg.date < cutoff:
                    break
                text = (msg.message or "").strip()
                if len(text) < 10:
                    continue
                rows.append({
                    "source": "telegram",
                    "channel": f"tg_group:{username}",
                    "msg_ref": f"{username}/{msg.id}",
                    "ts": msg.date.isoformat(),
                    "text": text[:2000],   # PII: no usernames/ids/photos stored
                })
                n += 1
            print(f"  {username}: {n} messages")
            await asyncio.sleep(5)  # politeness between groups
        except Exception as exc:  # noqa: BLE001
            print(f"  {username}: {type(exc).__name__} {str(exc)[:70]}")

    await client.disconnect()

    # merge with preview-channel messages (dedupe by msg_ref)
    existing = read_jsonl(SOCIAL_RAW / "telegram_messages.jsonl")
    seen = {r.get("msg_ref") for r in existing}
    merged = existing + [r for r in rows if r["msg_ref"] not in seen]
    n = write_jsonl(SOCIAL_RAW / "telegram_messages.jsonl", merged)
    print(f"\ntelegram_messages.jsonl now {n} rows ({len(rows)} new from groups)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-days", type=int, default=92)
    ap.add_argument("--join", action="store_true",
                    help="also send join requests for the target groups")
    args = ap.parse_args()
    return asyncio.run(run(args.window_days, args.join))


if __name__ == "__main__":
    sys.exit(main())
