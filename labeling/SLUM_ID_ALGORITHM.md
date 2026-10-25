# Slum identification algorithm (v8, 2026-10-24)

Script: `gen_slum_web_layers_v8.py` (pure stdlib Python, no network after corridor cache).
Inputs: `qgis_project/<site>_crit.geojson` (UTM 47N) and `qgis_project/slum_roofs_{red,pink}_v3.geojson`
(WGS84, corridor descriptors from `gen_slum_web_layers_v3.py`).
Outputs (WGS84, served to `slum.html`): `slum_roofs_red_v8`, `slum_roofs_pink_v8`,
`slum_congestion_blobs_v8`.

## Unit = slum GROUP, not the individual building

1. **Small building**: footprint area < 100 m2 (`SMALL_MAX`).
2. **Per-building small density**: count of small buildings within 30 m, per hectare
   (disc 0.2827 ha). Reported on every roof as `small_den`.
3. **Spacing**: mean distance to the 5 nearest NON-TOUCHING (>0.5 m) neighbours within 30 m.
   Raw nearest-neighbour is ~0 for terraced rows (shared walls, merged polygons), so this
   measures block gaps / alley width. Reported as `spacing_m`.
4. **Markers**: buildings with small_den >= 35/ha (`MARK_DEN`).
5. **Raster closing**: 10 m grid, cells containing a marker; dilate 6 cells / erode 5 cells
   (60 m / 50 m) — bridges gaps up to ~100 m, absorbs connecting ribbons.
6. **Group acceptance**: >= 10 markers inside AND any of
   - >= 50% of markers within 150 m of canal / motorway-trunk-primary road / railway /
     industrial area (`near_share >= 0.5`), or
   - mean marker small_den >= 40/ha, or
   - mean marker spacing <= 16 m.
7. **Red = every building whose centroid is inside the accepted group polygon**
   (point-in-polygon on the final smoothed ring) AND area <= 150 m2 AND elongation <= 0.8
   (PCA thinness; excludes warehouses and long rows). Everything else pink.
8. **Blob geometry**: boundary trace, Douglas-Peucker 4 m, 3x Chaikin corner cutting —
   smooth rounded outlines.

## Tuning knobs (top of script)

`SMALL_MAX=100`, `MARK_DEN=35`, `MARK_SPACING=12` (info only), acceptance clause
`near>=0.5 / den>=40 / spacing<=16`, closing radii 6/5 cells, red filters
`area<=150`, `elong<=0.8`.

## Known context

- AI segmentations merge terraced rows into single polygons; spacing therefore measures
  gaps between built blocks (8-20 m inside slum sites).
- OSM corridor cache: `qgis_project/canals/<site>_{water,road,rail,indu}.geojson`.
  Delete a file to force refetch (bkk_slum_5 road fetch failed with 502s).
- Original 4-rule per-building vote (2-of-4) is obsolete — kept only as legacy
  `rules_hit`/`slum` fields in the `*_crit.geojson` files.
