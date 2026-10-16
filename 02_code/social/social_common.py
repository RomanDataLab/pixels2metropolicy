"""Shared helpers for the slum_pulse social-signal pipeline."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[2]
SOCIAL_RAW = REPO / "01_data" / "02_raw_imports" / "social"
SOCIAL_OUT = REPO / "04_output" / "social_patterns" / "bangkok"
GAZETTEER_DIR = REPO / "01_data" / "03_derived_vector" / "gazetteer"
SCRATCH_HTML = REPO / "05_scratch" / "social" / "html"

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "Pixels2MetroPolicy-research/0.1 (GeoHackathon2026; polite; contact via repo)"
    )
}


def ensure_dirs() -> None:
    for p in (SOCIAL_RAW, SOCIAL_OUT, GAZETTEER_DIR, SCRATCH_HTML):
        p.mkdir(parents=True, exist_ok=True)


def url_hash(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def polite_get(url: str, *, delay: float = 1.0, retries: int = 2, timeout: int = 40,
               session: requests.Session | None = None, **kw) -> requests.Response:
    """GET with retries and a per-process politeness delay. Raises on final failure."""
    getter = (session or requests).get
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = getter(url, headers=UA, timeout=timeout, **kw)
            if r.status_code in (429, 502, 503) and attempt < retries:
                last = RuntimeError(f"HTTP {r.status_code}")
                time.sleep((attempt + 1) * 5)
                continue
            return r
        except Exception as exc:  # noqa: BLE001 - network errors vary
            last = exc
            if attempt < retries:
                time.sleep((attempt + 1) * 5)
    raise last  # type: ignore[misc]


def write_jsonl(path: Path, rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
