# Pixels to Metro Policy · Landing page

Scroll-driven opening page for the Pixels to Metro Policy website: a population-bar
globe that descends to Asia, Thailand's provinces and Bangkok's 50 districts, then an
interactive bird's-eye evidence scene, data analytics, policy, pipeline, methodology
and a "next page" link into the platform.

Matches the walkthrough video v8.

## What is in this package

| Folder / file | Use |
|---|---|
| `web/` | **Ready to integrate.** `index.html` + `css/` + `js/` (incl. `js/vendor/` d3, topojson) + `fonts/` + `img/` + `media/`. No CDN, no external requests. |
| `standalone/index.html` | The same page as one self-contained file (fonts, scripts, images and clips inlined, ~9.8 MB). |
| `src/`, `data/`, `build.py` | Source, if you need to change something and rebuild. |
| `THIRD_PARTY_LICENSES/` | Licences for d3, topojson-client (ISC) and the IBM Plex / Archivo fonts (SIL OFL). |

Everything shown on the page is bundled: data layers, map images, segmentation images, the two footage clips
(MP4 + WebM) and their posters, fonts and JavaScript libraries.

## Rebuild

```bash
python3 build.py --platform-url /platform        # where "Platform →" and the final button link to
```
Writes `dist/web/` and `dist/standalone/`. Only the Python standard library is needed.

## Integrating into the main website

1. Copy `web/css`, `web/js`, `web/fonts`, `web/img` and `web/media` into the site's static folder (keep them together;
   `css/fonts.css` loads fonts from `../fonts/`).
2. Copy the `<body>` content of `web/index.html` into the home page template and keep the script order at the bottom:
   ```html
   <script src="js/p2m-data.js"></script>
   <script src="js/vendor/d3.min.js"></script>
   <script src="js/vendor/topojson-client.min.js"></script>
   <script src="js/p2m-voyage.js"></script>
   <script src="js/p2m-scene.js"></script>
   ```
3. Add `css/fonts.css` and `css/p2m-landing.css` to `<head>`.
4. If assets live elsewhere, adjust paths: image paths are inside `js/p2m-data.js`, clip paths in `index.html` (`media/`).

Notes for the integrator:
- **Global CSS**: the stylesheet styles `body`, `h1–h3`, `p`, `a` and class names such as `.wrap`, `.panel`, `.card`, `.btn`.
  If the main site has its own globals, load the page on its own route or prefix the selectors.
- **Fixed header**: the page has its own top bar (`header.top`); remove it if the site already has one.
- **Scroll journey**: two scroll containers share one map stage: `#voyage` (orbit to the audit, 1275vh) and `#voyage2`
  (THEOS-2, validation, SEA risk, 300vh) with the analytics section between them. Keep both, in this order.
- Works on desktop and phone widths; respects `prefers-reduced-motion`.

## Footage section

Two short muted loops (20 s each) sit below the Bangkok scene, cut from news reports the
project team downloaded: flood in Romklao–Lat Krabang (Ch7HD News, from 0:41) and the
Makkasan community fire, Ratchathewi (Nation Online, from 0:33). Files are in `src/media/`
as MP4 (H.264) and WebM (VP9) with JPEG posters. `dist/web` serves them from `media/`;
`dist/standalone` and `dist/artifact` inline them. Each card links to the full report with
sound on YouTube. Rights remain with the broadcasters and photographers; check reuse terms
before publishing the site publicly.

## Folder structure

```
build.py                    Builds dist/web and dist/standalone
src/
  index.template.html       Page markup (__P2MP__ = platform URL placeholder)
  p2m-landing.css           All styles
  p2m-voyage.js             Scroll voyage: globe, Thailand, Bangkok layers, HUD
  p2m-scene.js              Bird's-eye scene (hover/click/zoom) + analytics charts
data/
  popbars.json              Globe bars: [lon, lat, population, slum % of urban pop]
  landdots.json             Globe land dots
  w110.json                 World countries (Natural Earth 110m, TopoJSON)
  sea10.json                SE Asia country outlines (Natural Earth 10m)
  bkk.json                  Bangkok: provinces, 50 districts, 1,993 BMA community
                            polygons (626 congested), 177 Baan Mankong points,
                            candidate markers, fire/flood points, district stats,
                            model heat layer + roof segmentation image (base64)
tools/
  data_prep/                Scripts used to create data/ (reference, see below)
```

## How the data was prepared (tools/data_prep)

These scripts document how `data/` was produced. They contain absolute paths from the
original working environment; update the paths before re-running.

| Script | What it does | Inputs |
|---|---|---|
| `00_prepare_world_geometry.js` | Extracts SE Asia outlines from Natural Earth | `world-atlas@2.0.2`, `topojson-client@3.1.0` (npm) |
| `01_extract_bma_layers_from_pptx.py` | Reads the vector map on slide 3 of the GeoHackathon deck and georeferences BMA community polygons and Baan Mankong points using the 50 district shapes (error < 1 m) | `P2MP_GeoHackathon2026_Kla.pptx`, OpenGISData-Thailand `districts.geojson` |
| `02_extract_model_heat_and_candidates.py` | Turns the prob_informal map image into a transparent heat layer and digitises the 244 candidate markers (overlapping markers merge) | slide images from the deck |
| `03_extract_fire_flood_points.py` | Georeferences fire-risk and outside-flood-wall markers from slides 7–8 | the deck + districts |

Population bars: WebGL Globe population grid (SEDAC, year 2000) joined to the World Bank
indicator `EN.POP.SLUM.UR.ZS` (latest year per country). Needs `shapely`, `pycountry`.

## SEA and infrastructure layers (added)

| Layer | Source | How it was made |
|---|---|---|
| Flood impact 2569 / 2554 by district | BMA announcement of 29 Sept 2569, compiled by Rocket Media Lab | District lists transcribed (`bkk.flood69`, `bkk.flood54`) |
| Flood hazard (high / moderate / low) | Sawangnate, Chaisri & Kittipongvises (2022), *Water* 14(8):1268, CC BY | Figure georeferenced to the 50 district boundaries (chamfer fit), reclassified; shares 56/37/7% vs published 50/35/14% |
| Population density 2564 | Urban TH map of DOPA registered population | Georeferenced to province outlines (~400 m), legend colours read per pixel; per-district class is the median |
| Fire incidents 2568 by district | BMA Office of Disaster Prevention via Rocket Media Lab raw data | All 50 districts, 657 incidents (372 building fires) |
| Flood damage claims 2569 | Claim Bangkok registrations to 20 Oct 2569 (BMA briefing, Bangkok Biznews) | Top 5 districts + 2 districts still flooded on 21 Oct |
| Crime risk spots | BMA risk and danger spots 2564 via Rocket Media Lab | Only 17 of 50 districts have published counts |
| Canals and rivers | © OpenStreetMap contributors (ODbL) via ekkamon/waterway-bkk (MIT) | Canals > ~400 m kept, simplified |
| BTS, MRT, ARL, BRT | hspotlight/metro-fare station coordinates (MIT) | Stations joined in line order |
| Mainline rail | Natural Earth 10m | Coarse; on the Bangkok map expressways are not included (awaiting an OSM export) |
| Metro road links | Natural Earth 10m roads (public domain) | Expressways and highways clipped to the 7 provinces (`tools/data_prep/12`) |
| Registered residents 31 Dec 2564 | DOPA announcement (dopa.go.th news 9159) | 7 provinces: 11,596,278 |

Computed analytics (`bkk.an`): 45% of congested communities lie within 100 m of a canal or
river (other registered 24%, random 26%); 35% within 800 m of a rail-transit station (11% / 9%);
all 15 high-impact districts in 2569 are east of the Chao Phraya. Per-community values for the
hover card are in `bkk.ext` = [flood69 level, hazard class, metres to canal, metres to station].

## Data sources and limits

- BMA Community FeatureServer/14 (downloaded 16 Oct 2026), NHA, CODI Baan Mankong,
  fire-risk assessments 2568, flood-wall list Nov 2568, citywide screening and audit
  figures: Pixels to Metro Policy GeoHackathon 2026 deck.
- UN SDG Report 2023 and 2024 (Goal 11); CODI, Sept 2025; World Bank EN.POP.SLUM.UR.ZS.
- Province and district boundaries: OpenGISData-Thailand, CC BY 4.0 (keep attribution).
- World geometry: Natural Earth (public domain) via world-atlas.
- Candidate areas are unverified screening output; positions are digitised and
  approximate. Crime and social layers are shown as "not connected" because no
  spatial dataset was available. Only 6 of 11 outside-flood-wall communities have
  coordinates.
