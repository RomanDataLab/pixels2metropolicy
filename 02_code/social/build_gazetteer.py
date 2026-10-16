"""slum_pulse step 1 — build the Thai slum gazetteer (name-matching dictionary).

Sources:
  - BMA slum community polygons (626, CMT_TYPE = ชุมชนแออัด)
  - NHA low-income community points (cross-check only)
  - khwaeng/district names from the BMA layer itself

Outputs (01_data/03_derived_vector/gazetteer/):
  - slum_gazetteer.csv     one row per name variant (slum_name / landmark / khwaeng / district)
  - slum_polygons.parquet  cleaned polygons for spatial joins downstream
  - gnews_queries.csv      Google News RSS queries (all khwaeng + top-40 slums by population)

Run:  python build_gazetteer.py
"""
from __future__ import annotations

import re
import sys

import geopandas as gpd
import pandas as pd

from social_common import GAZETTEER_DIR, REPO, ensure_dirs

SLUM_SHP = REPO / "01_data" / "02_external_vector" / "bkk_community_boundaries" / "bkk_community_boundary_slum.shp"

# landmark prefixes worth indexing from ADDRESS / N-S-E-W boundary text
LANDMARK_PREFIX = re.compile(
    r"(?:คลอง|ถนน|ซอย|แม่น้ำ|ทางรถไฟ|สถานี|ตลาด|วัด|โรงเรียน|สะพาน|ท่าเรือ|แยก|มหาวิทยาลัย|โรงพยาบาล)"
    r"[\u0e00-\u0e7fa-zA-Z0-9\.]*"
)
MIN_NAME_LEN = 4          # Thai chars: keep names long enough to be unambiguous
PREFIXES_TO_STRIP = ("ชุมชน",)


def normalize_name(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip())


def core_name(name: str) -> str:
    n = normalize_name(name)
    for p in PREFIXES_TO_STRIP:
        if n.startswith(p) and len(n) > len(p) + MIN_NAME_LEN:
            n = n[len(p):]
    return n.strip()


def main() -> None:
    ensure_dirs()
    gdf = gpd.read_file(SLUM_SHP)
    gdf.columns = [c.upper() if c != gdf.geometry.name else c for c in gdf.columns]
    gdf = gdf.set_geometry(gdf.geometry.name)
    gdf["geometry"] = gdf.geometry.buffer(0)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    for col in ("CMT_NAME", "DNAME", "SNAME", "ADDRESS", "N_BND", "S_BND", "E_BND", "W_BND"):
        gdf[col] = gdf[col].map(lambda v: normalize_name(v) if isinstance(v, str) else "")
    gdf["POP_TOTAL"] = pd.to_numeric(gdf["POP_TOTAL"], errors="coerce").fillna(0).astype(int)
    print(f"slum polygons loaded: {len(gdf)}, crs={gdf.crs.to_epsg()}")

    variants: list[dict] = []

    def add(variant: str, kind: str, row: pd.Series) -> None:
        variant = normalize_name(variant)
        if len(variant.replace(" ", "")) < MIN_NAME_LEN:
            return
        variants.append({
            "variant": variant, "kind": kind,
            "cmt_id": row["CMT_ID"], "cmt_name": row["CMT_NAME"],
            "dname": row["DNAME"], "sname": row["SNAME"],
        })

    for _, row in gdf.iterrows():
        # slum-name variants: full official name + core (prefix-stripped) name
        add(row["CMT_NAME"], "slum_name", row)
        core = core_name(row["CMT_NAME"])
        if core != normalize_name(row["CMT_NAME"]):
            add(core, "slum_name", row)
        # landmarks from ADDRESS and the four adjacency descriptions
        for src in (row["ADDRESS"], row["N_BND"], row["S_BND"], row["E_BND"], row["W_BND"]):
            for m in LANDMARK_PREFIX.findall(src or ""):
                add(m, "landmark", row)
        # admin context variants (T3 targets)
        add(row["SNAME"], "khwaeng", row)
        add(row["DNAME"], "district", row)

    df = pd.DataFrame(variants)
    dup = df.duplicated(subset=["variant", "kind", "cmt_id"], keep="first")
    df = df[~dup].reset_index(drop=True)

    # ambiguity: same variant+kind pointing at several slums
    amb = df.groupby(["variant", "kind"])["cmt_id"].nunique()
    df["ambiguous"] = df.set_index(["variant", "kind"]).index.map(amb) > 1

    # khwaeng/district variants are inherently multi-slum; not "ambiguous" in the bad sense
    df.loc[df["kind"].isin(["khwaeng", "district"]), "ambiguous"] = False

    # landmark == khwaeng/district name would double-fire; drop those landmark rows
    admin_names = set(df.loc[df["kind"].isin(["khwaeng", "district"]), "variant"])
    df = df[~(df["kind"].eq("landmark") & df["variant"].isin(admin_names))].reset_index(drop=True)

    # ---- romanized / Latin-script variants (2026-10-08) ----
    # district English names from geoBoundaries khet layer, matched by slum centroid
    khet_path = REPO / "05_scratch" / "social" / "bkk_khet.geojson"
    if khet_path.exists():
        khet = gpd.read_file(khet_path)[["shapeName", "geometry"]]
        pts = gdf.copy()
        pts["geometry"] = pts.to_crs(32647).geometry.centroid.to_crs(4326)
        sk = gpd.sjoin(pts[["DNAME", "geometry"]],
                       khet.rename(columns={"shapeName": "khet_en"}),
                       how="left", predicate="within")
        dname_to_en = (sk.dropna(subset=["khet_en"]).drop_duplicates("DNAME")
                       .set_index("DNAME")["khet_en"].to_dict())
        for thai, en in dname_to_en.items():
            for _, row in gdf[gdf["DNAME"] == thai].iterrows():
                variants.append({"variant": en, "kind": "district",
                                 "cmt_id": row["CMT_ID"], "cmt_name": row["CMT_NAME"],
                                 "dname": thai, "sname": row["SNAME"]})
        print(f"romanized district variants: {len(dname_to_en)} districts")
    else:
        print("no bkk_khet.geojson - district romanization skipped")

    # famous-area aliases (Latin) -> Thai khwaeng/district names
    ALIASES = {
        "Khaosan": ["พระนคร"], "Khao San": ["พระนคร"],
        "Yaowarat": ["สัมพันธวงศ์"], "Chinatown": ["สัมพันธวงศ์"],
        "Silom": ["บางรัก"], "Sathorn": ["สาทร"], "Sathon": ["สาทร"],
        "Siam": ["ปทุมวัน"], "Victory Monument": ["ราชเทวี"],
        "Sukhumvit": ["วัฒนา", "คลองเตย", "พระโขนง"],
        "Asok": ["วัฒนา"], "Asoke": ["วัฒนา"], "Nana": ["วัฒนา"],
        "Thonglor": ["วัฒนา"], "Thong Lo": ["วัฒนา"], "Ekkamai": ["วัฒนา"],
        "On Nut": ["พระโขนง"], "Onnut": ["พระโขนง"],
        "RCA": ["ห้วยขวาง"], "Ratchada": ["ห้วยขวาง", "ดินแดง"],
        "Chatuchak": ["จตุจักร"], "JJ Market": ["จตุจักร"], "Mo Chit": ["จตุจักร"],
        "Lat Phrao": ["ลาดพร้าว"], "Ladprao": ["ลาดพร้าว"],
        "Bang Na": ["บางนา"], "Bang Chak": ["พระโขนง"],
        "Phetchaburi": ["ราชเทวี"], "Ari": ["พญาไท"],
        "Klong Toey": ["คลองเตย"], "Khlong Toei": ["คลองเตย"],
        "Klong Toei": ["คลองเตย"], "Khlong Toey": ["คลองเตย"],
        "Thonburi": ["ธนบุรี"], "Thon Buri": ["ธนบุรี"],
        "Wongwian Yai": ["ธนบุรี"], "Pinklao": ["บางกอกน้อย"],
    }
    n_alias = 0
    for alias, targets in ALIASES.items():
        for target in targets:
            is_khw = (gdf["SNAME"] == target).any()
            for _, row in gdf[(gdf["SNAME"] == target) | (gdf["DNAME"] == target)].iterrows():
                variants.append({"variant": alias, "kind": "khwaeng" if is_khw else "district",
                                 "cmt_id": row["CMT_ID"], "cmt_name": row["CMT_NAME"],
                                 "dname": row["DNAME"], "sname": row["SNAME"]})
                n_alias += 1
    print(f"alias variant rows: {n_alias} ({len(ALIASES)} aliases)")

    # rebuild + re-dedupe with the new variants
    df = pd.DataFrame(variants)
    dup = df.duplicated(subset=["variant", "kind", "cmt_id"], keep="first")
    df = df[~dup].reset_index(drop=True)
    amb = df.groupby(["variant", "kind"])["cmt_id"].nunique()
    df["ambiguous"] = df.set_index(["variant", "kind"]).index.map(amb) > 1
    df.loc[df["kind"].isin(["khwaeng", "district"]), "ambiguous"] = False

    df = df.sort_values(["kind", "variant"]).reset_index(drop=True)
    df.to_csv(GAZETTEER_DIR / "slum_gazetteer.csv", index=False, encoding="utf-8-sig")

    poly = gdf[["CMT_ID", "CMT_NAME", "DNAME", "SNAME", "POP_TOTAL", "HOUSEHOLD", "AREA_SQM", "ESTABLISH", "geometry"]]
    poly.to_parquet(GAZETTEER_DIR / "slum_polygons.parquet")

    # Google News queries: every khwaeng + top-40 slums by population
    khwaeng = (gdf.groupby(["SNAME", "DNAME"])
               .agg(n_slums=("CMT_ID", "size"), pop=("POP_TOTAL", "sum"))
               .reset_index().sort_values("pop", ascending=False))
    queries: list[dict] = [
        {"query": f'"{k.SNAME}" กรุงเทพ', "kind": "khwaeng", "sname": k.SNAME, "dname": k.DNAME}
        for k in khwaeng.itertuples()
    ]
    top_slums = gdf.sort_values("POP_TOTAL", ascending=False).head(40)
    for k in top_slums.itertuples():
        queries.append({"query": f'"{core_name(k.CMT_NAME)}"', "kind": "slum",
                        "sname": k.SNAME, "dname": k.DNAME})
    pd.DataFrame(queries).to_csv(GAZETTEER_DIR / "gnews_queries.csv", index=False, encoding="utf-8-sig")

    # ---- gate report ----
    print(f"\ngazetteer rows: {len(df)} variants over {df['cmt_id'].nunique() or 'n/a'} slums")
    print(df.groupby("kind").agg(rows=("variant", "size"), unique=("variant", "nunique"),
                                 ambiguous=("ambiguous", "sum")).to_string())
    print(f"\nkhwaeng count: {len(khwaeng)} (queries: {len(queries)})")
    print("\n-- gate: 30 random slum_name variants --")
    sample = (df[df["kind"] == "slum_name"].sample(n=min(30, len(df)), random_state=7))
    for v in sample.itertuples():
        flag = "AMBIG" if v.ambiguous else "ok   "
        print(f"  [{flag}] {v.variant}  ({v.dname} / {v.sname})")
    amb_slum = df[df["kind"] == "slum_name"]["ambiguous"]
    print(f"\nambiguous slum-name rows: {amb_slum.sum()} / {len(amb_slum)}")
    print(f"outputs: {GAZETTEER_DIR}\\{{slum_gazetteer.csv, slum_polygons.parquet, gnews_queries.csv}}")


if __name__ == "__main__":
    sys.exit(main())
