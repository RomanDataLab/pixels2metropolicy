# Pixels2MetroPolicy — Project Graph

## Overview

GeoHackathon 2026 entry ("Pixel2Policy TH") mapping Thailand's informal settlements. It produces interactive Leaflet maps comparing officially registered low-income communities (NHA, 1,588 points; BMA, 626 slum polygons) against Thai comprehensive-plan land-use zones (ผังเมืองรวม), plus supporting pages: roof segmentation results (SAM and U-Net generations over a THEOS-2 satellite scene), a social-signal "slum pulse" pipeline (news, complaints, Telegram, Pantip geolocated to slum polygons), a policy review, and a proposal. Audience: hackathon judges and policy researchers.

## Architecture

Two halves with no runtime coupling:

1. **Static site** (repo root): self-contained HTML pages using Leaflet 1.9.4 from unpkg CDN. `index.html` loads vector layers from `data/*.js` script tags (NGIS admin/environment layers, NHA communities, roofs); `slum.html` embeds its NHA + plan-zone GeoJSON inline as JS constants (hence 1.2 MB). All pages share a `#site-header` nav linking the seven public pages.
2. **Python pipelines** (`02_code/`): batch scripts that read raw data (`01_data/`, `05_scratch/`) and write app assets (`data/`, `theos_block/`, `04_output/`). Two pipelines: geo (roof extraction from a THEOS-2 scene) and social (event geolocation from public web sources).

```
GISTDA THEOS-2 (89 GB share)      Overture buildings        public web (RSS/Traffy/Pantip/t.me)
        |                                |                          |
 05_scratch/theos/*.tif        theos_block/overture_*.geojson   02_code/social/fetch_*.py
        |                                |                          |
 02_code/geo/gen1_samgeo_roofs.py   gen3_fix.py (Kabsch teacher     extract_events.py (gazetteer + lexicon)
        |                           alignment + U-Net retrain)           |
 04_output/... -> theos_block/gen{1,2}_roofs.geojson          social_patterns.py
        |                                |                          |
        +------- data/*.js + inline GeoJSON in HTML ------- 04_output/social_patterns/
                                     |
                          Static site (root *.html) -> Vercel
```

## Tech stack

No dependency manifest exists in the repo (no `requirements.txt`, `pyproject.toml`, `package.json`). Versions below are "not pinned"; libraries are documented only in runbooks.

| Layer | Technology | Version |
|---|---|---|
| Frontend | Plain HTML/CSS/JS + Leaflet (unpkg CDN) | Leaflet 1.9.4 (from `<script src>` in `index.html`, `slum.html`) |
| Frontend extras | TikTok / YouTube-nocookie embed iframes | not pinned |
| Backend language | Python (3.10+ per `05_scratch/share/open_stack_pipeline/SHARE_README.md`) | not pinned |
| Geo / raster | geopandas, rasterio, shapely, scipy, numpy, pandas, pyarrow, scikit-learn, overturemaps | not pinned |
| Segmentation | samgeo (MobileSAM vit_t), PyTorch, segmentation_models_pytorch (U-Net) | not pinned |
| Social ingest | feedparser, trafilatura, beautifulsoup4, requests, pythainlp, rapidfuzz, pyyaml, telethon | not pinned |
| Model artifact | `05_models/gen2b_unet.pt` (PyTorch state dict) | — |
| Deploy | Vercel static hosting (`vercel.json`) | — |

Install commands: `02_code/social/README_social_pipeline.md` (pip line) and `05_scratch/share/open_stack_pipeline/SHARE_README.md` (open-stack pipeline).

## Sources & data

External inputs (paths/URLs as found in code):

- **THEOS-2 scenes** — GISTDA read-only Google Drive share, 89 GB, EPSG:32647; workpieces used: `05_scratch/theos/theos_block.tif`, `05_scratch/theos/urban_20241012_2.tif` (from `02_code/geo/gen1_samgeo_roofs.py`, `gen3_fix.py`).
- **Overture building footprints** — `theos_block/overture_buildings.geojson` (12.5k buildings clipped; used as gen2 training teacher in `gen3_fix.py`).
- **NHA low-income communities** — gdcatalog dataset 23_01, 1,588 points; embedded inline as `const NHA` in `slum.html`; also `data/nha_communities.js` for `index.html`.
- **DPT comprehensive-plan zones** — `data/plan_zones.geojson`, `data/plan_boundary.geojson`; inline copy in `slum.html`.
- **NGIS/DOPA vector layers** — `data/districts.js`, `provinces.js`, `tambons.js`, `rivers.js`, `irrigation.js`, `highways.js`, `parks.js`, `wildlife.js` (loaded by `index.html`).
- **BMA community boundaries** — `01_data/02_external_vector/bkk_community_boundaries/bkk_community_boundary_slum.shp` (626 slum polygons, key `CMT_ID`) and root zip `bkk_community_boundaries_shapefile (1).zip` (from `02_code/social/build_gazetteer.py`).
- **OpenStreetMap Overpass** — `05_scratch/overpass/rail_*.json`, `water_*.json` (Bangkok bbox 100.30–100.95, 13.40–13.95).
- **Traffy Fondue** — `https://publicapi.traffy.in.th/share/search` public API, Bangkok bbox (100.32, 13.45, 100.95, 13.95) (`fetch_traffy.py`).
- **News RSS** — feeds listed in `01_data/00_source_inventory/social_signal_sources.csv` (registry CSV) + Google News RSS queries from the generated `gnews_queries.csv`.
- **Pantip** — public search page `https://pantip.com/search?q=` parsed via `__NEXT_DATA__` payload (`fetch_pantip.py`).
- **Telegram** — public channel previews `t.me/s/` (`fetch_social.py`); groups via Telethon MTProto with credentials from `G:\My Drive\J_Projects_Archive\config\config_telegram.json` (`fetch_telethon.py`; no env vars used).
- **Live map services** — `index.html` references GISTDA/LDD live tile services (per README).
- No API keys stored in repo; Traffy traffy360, ScrapeCreators (FB/TikTok) and BMA CKAN (Thai-IP-blocked) are deferred phases (`README_social_pipeline.md`).

## File map

| Path | Purpose |
|---|---|
| `index.html` | Main NGIS layers map: Leaflet, loads all `data/*.js` layers, layer legend UI, GISTDA/LDD live services |
| `slum.html` | Slum map: inline `const NHA` (1,588 communities) + inline plan zones, modeled population panel, street-level video player (TikTok/YouTube embeds, `SLUM_VIDEO_ORDER`) |
| `social.html` | Social pulse map (3.9 MB self-contained; copy of pipeline output `make_intensity_map.py` style choropleth) |
| `slum_policies.html` | Policy review page: global slum-policy case cards, images from `img/slum_policies/`, refs up to 86 |
| `proposal.html` | "Stale data to policy kits" proposal page |
| `datamatch.html` | THEOS-2 scenes vs BMA land-use plan data-match map |
| `gen1_samgeo.html` | Map viewer for gen1 SAM roof polygons (`theos_block/gen1_roofs.geojson`) |
| `gen2_unet.html` | Map viewer for gen2 U-Net roof polygons + probability raster |
| `geohackathon_information.html` | Hackathon information page (75 KB) |
| `data/` (11 files) | App vector assets as JS/GeoJSON: admin boundaries, environment layers, `nha_communities.js`, `roofs.js`, `plan_zones.geojson` |
| `img/slum_policies/` (~80 jpg) | Country case thumbnails/full images for the policy review |
| `theos_block/` | Geo app assets: `gen1_roofs.geojson`, `gen2_roofs.geojson`, `gen2_prob.tif`, `overture_buildings.geojson`, `slum_blocks.geojson`, `theos_block.png` |
| `02_code/geo/gen1_samgeo_roofs.py` | Gen 1: SAM (MobileSAM) roof segmentation, 1024-px chips / 128 overlap, size filter 4–5000 m²; `--test` flag |
| `02_code/geo/gen3_fix.py` | Fix pass: Kabsch/RANSAC similarity alignment of Overture teacher vs SAM centroids, U-Net retrain (256-px chips, 15 epochs), Douglas-Peucker rectilinear regularization (`regularize`) |
| `02_code/geo/finalize_gen1.py` | Regularize dense gen1 roofs and republish to `theos_block/gen1_roofs.geojson` |
| `02_code/social/build_gazetteer.py` | Step 1: slum gazetteer (3.7k name variants), cleaned polygons parquet, Google News query list |
| `02_code/social/fetch_traffy.py` | Step 2: Traffy Fondue public share API, pin-level complaints JSONL |
| `02_code/social/fetch_official.py` | Step 4: gdcatalog/COJ/BMA-CKAN official statistics to normalized parquet; writes `NEED_THAI_IP.txt` marker on geo-block |
| `02_code/social/fetch_news_rss.py` | Step 4a: RSS ingestion, 92-day window, `--window-days`, `--max-gnews` flags |
| `02_code/social/fetch_articles.py` | Step 4b: gazetteer pre-filter, robots.txt check, trafilatura full text; `--max` flag |
| `02_code/social/fetch_pantip.py` | Step 5: Pantip search titles; `--n-slums`, `--n-khwaeng` flags |
| `02_code/social/fetch_social.py` | Step 6a: t.me/s channel previews; `--pages` flag |
| `02_code/social/fetch_telethon.py` | Step 6b: Telethon group ingestion; `--window-days`, `--join` flags |
| `02_code/social/extract_events.py` | Step 7: pythainlp tokenization + gazetteer matching + `event_lexicon.yaml` classification, tiers T1–T4 |
| `02_code/social/social_patterns.py` | Step 8: per-slum aggregation (key `CMT_ID`), weekly timeseries, match-quality report |
| `02_code/social/make_intensity_map.py` | Step 8b: community choropleth HTML + per-community counts CSV |
| `02_code/social/social_common.py` | Shared path constants, polite HTTP session (`UA`), JSONL helpers |
| `02_code/social/event_lexicon.yaml` | Thai event-type keyword lexicon |
| `02_code/social/README_social_pipeline.md` | Full social-pipeline runbook: run order, outputs, tiers, gates, known limits |
| `02_code/app/social.html` | Near-duplicate of root `social.html` (3,962,927 vs 3,962,735 bytes) |
| `02_code/app/data/data/` (9 files) | Older partial copy of root `data/` (no `nha_communities.js`, `roofs.js`, plan GeoJSON) |
| `02_code/scripts/` | Empty (only `desktop.ini`) |
| `01_data/` | Raw/derived data (gitignored): source inventory CSV, THEOS-2 crops, external vector, raw social imports, gazetteer, derived raster |
| `04_output/` | Pipeline outputs (gitignored): `open_stack/bangkok/`, `social_patterns/bangkok/`, `test_seg/` (SAM experiment PNGs/NPYs) |
| `05_models/gen2b_unet.pt` | Trained gen2 U-Net weights |
| `05_scratch/theos/` | THEOS-2 workpiece rasters |
| `05_scratch/social/` | Social pipeline aux: `add_social_tab.py`, `translate_fill.py`, translate cache, khet GeoJSON, HTML cache |
| `05_scratch/deploy_site/` | Manual staging copy of the deployed site (HTML + `data/` + `theos_block/` + `02_code/`) |
| `05_scratch/share/open_stack_pipeline/` | Standalone share copy of the earlier open-stack settlement pipeline (6 geo scripts + runbook + `data_manifest.csv` provenance) |
| `05_scratch/overpass/`, `05_scratch/s2_prob/` | Overpass extracts; Sentinel-2 probability raster |
| `october_pres/` | `P2MP_GeoHackathon2026_Kla.pptx` + PDF export (presentation deck) |
| `00_admin/`, `03_proposal_idea/` | Effectively empty in the working tree (only `desktop.ini`) |

## Build & deploy

**Run locally (site):** open any root `*.html` directly in a browser, or serve the repo root statically (e.g. `python -m http.server`). Pages depend only on the unpkg CDN and local `data/`, `img/`, `theos_block/` assets.

**Run pipelines:** see `02_code/social/README_social_pipeline.md` (numbered run order, `cd 02_code/social && python <script>`) and `05_scratch/share/open_stack_pipeline/SHARE_README.md` for the open-stack variant. Install deps via the pip lines in those runbooks; `fetch_telethon.py` additionally needs the Telegram API config at `G:\My Drive\J_Projects_Archive\config\config_telegram.json`.

**Deploy:** Vercel static hosting, configured by `vercel.json` (repo root):

- `cleanUrls: true`
- `Cache-Control: public, max-age=604800, immutable` for `/data/:file`
- permanent redirect `/app/:path*` to `/:path*`

Repo: `git@github.com:RomanDataLab/pixels2metropolicy.git` (remote `origin`, branch `main-sync`, main branch `main`). `.gitignore` excludes `01_data/`, `04_output/`, `05_models/`, `05_scratch/`, `theos_block/`, and binary formats (`*.pdf`, `*.pptx`, `*.parquet`, ...). No CI workflow found (no `.github/` in tree).

## Verification notes

- **No dependency manifest.** Stack claims come from import statements and runbook pip lines only; nothing is pinned.
- **Referenced files missing.** `02_code/social/README_social_pipeline.md` cites `03_proposal_idea/slum_pulse_plan.md` and the share README cites `03_proposal_idea/open_stack_methodology.md`, but `03_proposal_idea/` in the working tree contains only `desktop.ini`. Same for `05_scratch/share/open_stack_pipeline/01_data/` and `03_proposal_idea/` listed in its README — not verified present.
- **README vs redirect.** Root `README.md` describes `/app/` as the full hackathon app URL, but `vercel.json` permanently redirects `/app/:path*` to `/:path*`; the app now lives at the root and the README text is stale on that point.
- **Duplicates.** `02_code/app/social.html` ≈ root `social.html` (188-byte delta); `02_code/app/data/data/` is a partial older copy of root `data/`; `05_scratch/deploy_site/` duplicates the whole site (its README is byte-identical to root README). Unclear which copy is canonical.
- **Empty dirs.** `02_code/scripts/` and `00_admin/` contain no code.
- **Deploy target unconfirmed.** Vercel config exists and a GitHub remote exists, but no `.vercel/` or CI file confirms the project is linked/deployed from this working copy.
- `theos_block/` is gitignored yet also referenced as published app assets by `finalize_gen1.py`/`gen3_fix.py`; the deployed site needs those files copied in (the `05_scratch/deploy_site/` staging copy contains them).
