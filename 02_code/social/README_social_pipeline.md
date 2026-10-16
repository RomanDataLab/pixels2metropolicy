# slum_pulse — social-signal pipeline runbook (Bangkok)

Evaluates economic + social behavior in Bangkok slums from news, official
complaints/statistics, and public social media, geolocated to the 626 official
BMA slum polygons (join key `CMT_ID`). Method plan:
`03_proposal_idea/slum_pulse_plan.md`.

## Environment

```bash
pip install feedparser trafilatura beautifulsoup4 pythainlp rapidfuzz \
            pyyaml pandas geopandas pyarrow requests
```

No API keys in this phase. ScrapeCreators (FB/TikTok) and Traffy traffy360
api-key are deliberately deferred. All ingests: public pages only, robots.txt
respected on article fetches, 1 req/s politeness, PII (usernames, photo URLs)
stripped at write time (PDPA posture).

## Run order

```bash
cd 02_code/social

# 0. sources are data: registry CSV (edit, no code)
#    01_data/00_source_inventory/social_signal_sources.csv

# 1. gazetteer (name variants from BMA polygons) — gate: printed 30-variant check
python build_gazetteer.py

# 2. Traffy Fondue public share API (pin-level, no token)
python fetch_traffy.py

# 3. official statistics (gdcatalog CSVs; COJ needs relaxed TLS; BMA CKAN geo-blocked
#    -> writes official/bma_ckan/NEED_THAI_IP.txt for UTT)
python fetch_official.py

# 4. news: RSS + 158 Google News queries (~5 min), then article texts
python fetch_news_rss.py
python fetch_articles.py --max 625

# 5. Pantip public search (top-20 slums + top-30 khwaeng)
python fetch_pantip.py

# 6. Telegram public channel previews (channels = registry rows category=telegram)
python fetch_social.py --pages 3

# 7. Thai NLP extraction: gazetteer tiers + event_lexicon.yaml categories
python extract_events.py

# 8. per-slum aggregation + covariates + reports
python social_patterns.py
```

## Outputs

| File | Producer | Content |
|---|---|---|
| `01_data/03_derived_vector/gazetteer/slum_gazetteer.csv` | 1 | 3.7k name variants, kinds slum_name/khwaeng/district/landmark, ambiguity flags |
| `01_data/03_derived_vector/gazetteer/slum_polygons.parquet` | 1 | 626 cleaned polygons, WGS84, POP_TOTAL |
| `01_data/03_derived_vector/gazetteer/gnews_queries.csv` | 1 | 118 khwaeng + 40 slum queries |
| `01_data/02_raw_imports/social/traffy_reports.jsonl` | 2 | pin-level complaints, Bangkok bbox |
| `01_data/02_raw_imports/social/official/*` | 3 | gdcatalog raw CSVs + official_stats.parquet |
| `01_data/02_raw_imports/social/news_items.jsonl` | 4a | 869 unique items, 92-day window |
| `01_data/02_raw_imports/social/news_articles.jsonl` | 4b | candidates w/ gazetteer hits; 620 snippet-only + full texts where robots-allowed |
| `01_data/02_raw_imports/social/pantip_threads.jsonl` | 5 | thread titles by slum/khwaeng query |
| `01_data/02_raw_imports/social/telegram_messages.jsonl` | 6 | public channel messages |
| `01_data/02_raw_imports/social/events.parquet` | 7 | tiered events (T1–T4) + event types |
| `04_output/social_patterns/bangkok/slum_social_profile.csv/.geojson` | 8 | per-slum indicators, `ev_*_per1k`, traffy counts |
| `04_output/social_patterns/bangkok/event_timeseries_weekly.csv` | 8 | weekly city-wide counts by type |
| `04_output/social_patterns/bangkok/match_quality_report.md` | 8 | tier distribution + 20-match skim sample |

## Match tiers

| Tier | Rule | Confidence |
|---|---|---|
| T1 | slum name + its khwaeng/district both in text | 0.9 |
| T2 | slum name alone (ambiguous name: 0.5) | 0.7 |
| T3 | khwaeng only — distributed across slums by population share | 0.4 |
| T4 | landmark (canal/road/temple…) only | 0.3 |

## Known limits (2026-10-06 run)

- Google News article links are JS redirects (`batchexecute`), not HTTP
  redirects: gnews items stay **snippet-only**; titles carry the location
  signal. Direct-feed items (Thairath/Sanook/Prachatai) get full text.
- Traffy public endpoint returns a rolling sample (~100 shared reports,
  2022–2026), not the full complaint history. Full `traffy360` needs api-key
  (deferred phase).
- BMA CKAN (`data.bangkok.go.th`) resets connections from non-Thai IPs —
  marker file written for UTT; risk-area registry join pending that fetch.
- COJ XLSX download fails TLS even relaxed — dataset metadata reachable,
  resource download to retry.
- Bangkok Post (TollBit), Matichon RSS (500), Daily News RSS (410),
  Khao Sod (bot wall) — compensated via Google News queries.
- Headlines rarely name slums directly: T3 (khwaeng) dominates; slum-level
  pin-point signal comes mostly from Traffy coordinates.

## Gates

1. Gazetteer 30-variant manual check — done at build (clean).
2. T1/T2 precision >= 0.6 on the 20-match skim sample in
   `match_quality_report.md` — pending human review.
3. Lexicon per-category precision — review category counts in report.
4. Traffy pin-in-polygon rate sanity — printed by step 8.

## Deferred (next phase)

- ScrapeCreators wrapper (FB/TikTok/IG) — key exists, wrapper not written.
- Traffy traffy360 api-key ingestion (Google Form registration).
- BMA CKAN risk-area registry + metro police station stats (need Thai IP / UTT).
- gnews `batchexecute` URL decoding for full article texts.
- TSDI district deprivation index + NSO SES ground-truth merge.
