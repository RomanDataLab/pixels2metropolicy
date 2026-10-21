QGIS LABELING - chip at your point 13.928059, 100.602973
=========================================================

OPEN (drag into QGIS, or Layer > Add Layer):
  1. chip_1019_4568.png   (raster; pgw+prj georeference it in UTM47N)
  2. roofs.geojson         (NEW edit layer: one polygon per ROOF)
  3. slum_region.geojson   (NEW edit layer: ONE polygon around the whole
                            informal area - this replaces BMA as region truth)

DRAW
  - Layer > toggle editing; Add Polygon Feature
  - Snapping: magnet icon ON, snap to vertex/segment of same layer
  - roofs: click roof corners, right-click to close; every roof, any material;
    shared walls -> boundary at divider; visible extent only under trees;
    skip cars/containers/ground
  - slum_region: one closed polygon hugging the informal fabric

SAVE
  - Layer > Save Layer Edits (or toggle editing off -> save)
  - deliver back: roofs.geojson + slum_region.geojson from this folder

Target = 512x512 px chip = 256x256 m. 30-50 such chips total; this is #1.
