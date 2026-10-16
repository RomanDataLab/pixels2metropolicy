"""slum_pulse step 4 — official statistics ingestion (gdcatalog + COJ + BMA CKAN attempt).

Downloads CSV/XLSX resources for crime/drug/corrections/court indicators and
normalizes the clean ones into a long parquet (source, indicator, period,
geo_level, geo_name, value). Province-level data cannot be pinned to slums —
used only as calibration covariates in social_patterns.py.

BMA CKAN is geo-blocked from non-Thai IPs: on failure a NEED_THAI_IP marker is
written for the Bangkok teammate (UTT) to fetch manually.

Run:  python fetch_official.py
"""
from __future__ import annotations

import io
import sys
import urllib3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from social_common import SOCIAL_RAW, ensure_dirs, polite_get

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OFFICIAL = SOCIAL_RAW / "official"
GDCATALOG = "https://gdcatalog.go.th"
COJ = "https://opendata.coj.go.th"
BMA = "https://data.bangkok.go.th"

GDCAT_DATASETS = [
    ("gdpublish-skt2567pl-53-16", "crime_cases"),
    ("gdpublish-dataset-30-225", "crime_arrests"),
    ("gdpublish-301-002", "drug_cases"),
    ("gdpublish-21_02", "corrections_drug"),
]
COJ_DATASETS = [("security-cases-2026", "court_security_cases")]

PROV_HINTS = ("จังหวัด", "พื้นที่", "เขต", "province", "รายการ", "ปี", "ไตรมาส", "เดือน")


def ckan_show(base: str, ds: str, verify: bool = True) -> dict | None:
    try:
        r = polite_get(f"{base}/api/3/action/package_show",
                       params={"id": ds}, timeout=60, verify=verify)
        if r.status_code == 200:
            return r.json()["result"]
        print(f"  {ds}: HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001
        print(f"  {ds}: {type(exc).__name__}: {str(exc)[:70]}")
    return None


def download_resources(pkg: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for res in pkg.get("resources", []):
        url = res.get("url")
        fmt = (res.get("format") or "").lower()
        if not url or fmt not in ("csv", "xlsx"):
            continue
        name = (res.get("name") or res.get("id", "res"))[:60].replace("/", "_")
        dest = out_dir / f"{name}.{fmt}"
        if dest.exists():
            saved.append(dest)
            continue
        try:
            r = polite_get(url, timeout=120)
            if r.status_code == 200 and len(r.content) > 50:
                dest.write_bytes(r.content)
                saved.append(dest)
        except Exception as exc:  # noqa: BLE001
            print(f"    dl fail {name}: {type(exc).__name__}")
    return saved


def read_any(path: Path) -> pd.DataFrame | None:
    for enc in ("utf-8", "tis-620", "cp874"):
        try:
            if path.suffix == ".csv":
                return pd.read_csv(path, encoding=enc)
            return pd.read_excel(path)
        except (UnicodeDecodeError, ValueError):
            continue
        except Exception:  # noqa: BLE001
            return None
    return None


def normalize(df: pd.DataFrame, source: str) -> pd.DataFrame | None:
    """Best-effort melt into long form; keeps province-ish row labels."""
    if df is None or df.empty:
        return None
    df = df.dropna(how="all").dropna(axis=1, how="all")
    label_col = next((c for c in df.columns
                      if any(h in str(c).lower() for h in map(str.lower, PROV_HINTS))), None)
    if label_col is None:
        return None
    out = []
    for col in df.columns:
        if col == label_col:
            continue
        series = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
        if series.notna().sum() < max(3, len(df) // 3):
            continue  # skip text columns
        part = pd.DataFrame({
            "source": source, "indicator": str(col),
            "geo_name": df[label_col].astype(str).str.strip(),
            "value": series,
        })
        out.append(part)
    if not out:
        return None
    long = pd.concat(out, ignore_index=True)
    long["period"] = None
    long["geo_level"] = "subnational"
    long["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return long


def main() -> int:
    ensure_dirs()
    parts, raw_files = [], []

    print("== gdcatalog ==")
    for ds, slug in GDCAT_DATASETS:
        pkg = ckan_show(GDCATALOG, ds)
        if not pkg:
            continue
        files = download_resources(pkg, OFFICIAL / "gdcatalog" / slug)
        raw_files += [str(f) for f in files]
        print(f"  {slug}: {len(files)} files")
        for f in files:
            df = read_any(f)
            if df is not None:
                norm = normalize(df, f"gdcatalog/{slug}")
                if norm is not None:
                    parts.append(norm)
                    print(f"    normalized {f.name}: {len(norm)} rows")

    print("== COJ (relaxed TLS) ==")
    for ds, slug in COJ_DATASETS:
        pkg = ckan_show(COJ, ds, verify=False)
        if not pkg:
            continue
        files = download_resources(pkg, OFFICIAL / "coj" / slug)
        raw_files += [str(f) for f in files]
        print(f"  {slug}: {len(files)} files")
        for f in files:
            df = read_any(f)
            if df is not None:
                norm = normalize(df, f"coj/{slug}")
                if norm is not None:
                    parts.append(norm)
                    print(f"    normalized {f.name}: {len(norm)} rows")

    print("== BMA CKAN (attempt; likely Thai-IP blocked) ==")
    marker = OFFICIAL / "bma_ckan" / "NEED_THAI_IP.txt"
    try:
        r = polite_get(f"{BMA}/api/3/action/package_search",
                       params={"q": "พื้นที่เสี่ยง", "rows": 1}, timeout=30)
        print(f"  reachable: HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            "data.bangkok.go.th connection reset from this IP (geo-block).\n"
            "UTT: please fetch 'บัญชีพื้นที่เสี่ยงและพื้นที่อันตราย กทม.' + district welfare datasets\n"
            "via CKAN API or browser, store under this folder.\n"
            f"probe failed: {type(exc).__name__}\n", encoding="utf-8")
        print(f"  geo-blocked ({type(exc).__name__}); marker written: {marker}")

    if parts:
        stats = pd.concat(parts, ignore_index=True)
        dest = OFFICIAL / "official_stats.parquet"
        stats.to_parquet(dest)
        print(f"\nofficial_stats.parquet: {len(stats)} rows, "
              f"{stats['source'].nunique()} sources, indicators: {stats['indicator'].nunique()}")
    else:
        print("\nno parseable tabular stats (raw files kept for manual review)")
    print(f"raw files under: {OFFICIAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
