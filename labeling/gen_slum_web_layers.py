"""Build WGS84 web layers for slum.html from *_crit.geojson (EPSG:32647).

Outputs (labeling/qgis_project/):
  slum_roofs_red.geojson   - buildings with slum==1
  slum_roofs_pink.geojson  - buildings with slum==0
  slum_congestion_blobs_wgs84.geojson - convex hulls of congested slum clusters
                                        (slum==1 and nb_20>=8, clustered at 60 m, min 5 buildings)

Pure stdlib: UTM 47N (EPSG:32647) -> WGS84 inverse projection implemented inline.
"""
import json
import math
import os
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
QDIR = os.path.join(BASE, "qgis_project")

SITES = ["bkk_slum_1", "bkk_slum_3", "bkk_slum_5", "bkk_slum_6", "bkk_slum_7",
         "bkk_slum_8", "bkk_slum_9", "bkk_slum_10", "bkk_slum_11", "bkk_slum_12",
         "bkk_slum_13", "bkk_slum_41", "patt_slum_1", "slum_2"]

# WGS84 / UTM constants
A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)
EP2 = E2 / (1 - E2)
K0 = 0.9996
LON0 = math.radians(99.0)  # zone 47N central meridian
E4 = E2 * E2
E6 = E4 * E2


def utm47n_to_wgs84(easting, northing):
    x = easting - 500000.0
    y = northing
    M = y / K0
    mu = M / (A * (1 - E2 / 4 - 3 * E4 / 64 - 5 * E6 / 256))
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    j1 = 3 * e1 / 2 - 27 * e1 ** 3 / 32
    j2 = 21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32
    j3 = 151 * e1 ** 3 / 96
    j4 = 1097 * e1 ** 4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)
    sin_fp2 = math.sin(fp) ** 2
    C1 = EP2 * math.cos(fp) ** 2
    T1 = math.tan(fp) ** 2
    N1 = A / math.sqrt(1 - E2 * sin_fp2)
    R1 = A * (1 - E2) / (1 - E2 * sin_fp2) ** 1.5
    D = x / (N1 * K0)
    lat = fp - (N1 * math.tan(fp) / R1) * (
        D ** 2 / 2
        - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * EP2) * D ** 4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * EP2 - 3 * C1 ** 2) * D ** 6 / 720)
    lon = LON0 + (
        D
        - (1 + 2 * T1 + C1) * D ** 3 / 6
        + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * EP2 + 24 * T1 ** 2) * D ** 5 / 120) / math.cos(fp)
    return math.degrees(lon), math.degrees(lat)


def transform_coords(c):
    if isinstance(c[0], (int, float)):
        lon, lat = utm47n_to_wgs84(c[0], c[1])
        return [round(lon, 7), round(lat, 7)]
    return [transform_coords(x) for x in c]


def ring_points(geom):
    """First-ring vertex list of a Polygon/MultiPolygon geometry (UTM coords)."""
    pts = []
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        for ring in poly:
            pts.extend(ring)
    return pts


def convex_hull(points):
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def cluster_blobs(centroids, eps=60.0, min_size=5):
    """Grid-based BFS clustering of (x, y, idx); returns lists of idx."""
    cell = eps
    grid = defaultdict(list)
    for cx, cy, idx in centroids:
        grid[(int(cx // cell), int(cy // cell))].append(idx)
    pos = {idx: (cx, cy) for cx, cy, idx in centroids}
    seen = set()
    clusters = []
    for cx, cy, idx in centroids:
        if idx in seen:
            continue
        stack = [idx]
        seen.add(idx)
        comp = []
        gx, gy = int(cx // cell), int(cy // cell)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            px, py = pos[cur]
            cgx, cgy = int(px // cell), int(py // cell)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for other in grid.get((cgx + dx, cgy + dy), ()):
                        if other in seen:
                            continue
                        ox, oy = pos[other]
                        if (ox - px) ** 2 + (oy - py) ** 2 <= eps * eps:
                            seen.add(other)
                            stack.append(other)
        if len(comp) >= min_size:
            clusters.append([pos[i] for i in comp])
    return clusters


def main():
    red_feats, pink_feats, blob_feats = [], [], []
    fid = 0
    for site in SITES:
        path = os.path.join(QDIR, site + "_crit.geojson")
        gj = json.load(open(path, encoding="utf-8"))
        dense_pts = []
        n_red = n_pink = 0
        for feat in gj["features"]:
            p = feat["properties"]
            geom = {"type": feat["geometry"]["type"],
                    "coordinates": transform_coords(feat["geometry"]["coordinates"])}
            out_props = {"site": site, "det_id": p.get("det_id"),
                         "confidence": p.get("confidence"), "area_m2": p.get("area_m2"),
                         "nb_20": p.get("nb_20"), "rules_hit": p.get("rules_hit"),
                         "slum": p.get("slum")}
            out = {"type": "Feature", "id": fid,
                   "properties": out_props, "geometry": geom}
            fid += 1
            if p.get("slum") == 1:
                red_feats.append(out)
                n_red += 1
            else:
                pink_feats.append(out)
                n_pink += 1
            if p.get("slum") == 1 and (p.get("nb_20") or 0) >= 8:
                pts = ring_points(feat["geometry"])
                cx = sum(pt[0] for pt in pts) / len(pts)
                cy = sum(pt[1] for pt in pts) / len(pts)
                dense_pts.append((cx, cy, fid - 1))
        clusters = cluster_blobs(dense_pts)
        for cl in clusters:
            hull = convex_hull(cl)
            ring = [utm47n_to_wgs84(x, y) for x, y in hull]
            if len(ring) < 3:
                continue
            ring = [[round(lon, 7), round(lat, 7)] for lon, lat in ring]
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            blob_feats.append({"type": "Feature",
                               "properties": {"site": site, "buildings": len(cl)},
                               "geometry": {"type": "Polygon", "coordinates": [ring]}})
        print(f"{site:15s} red={n_red:6d} pink={n_pink:5d} blobs={len(clusters)}")

    def write(name, feats):
        out = {"type": "FeatureCollection",
               "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
               "features": feats}
        path = os.path.join(QDIR, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, separators=(",", ":"))
        print(f"wrote {name}: {len(feats)} features, {os.path.getsize(path) / 1e6:.1f} MB")

    write("slum_roofs_red.geojson", red_feats)
    write("slum_roofs_pink.geojson", pink_feats)
    write("slum_congestion_blobs_wgs84.geojson", blob_feats)

    # sanity: print centroid of first red feature (expect ~100.5-101.1E, 13.2-14.1N)
    if red_feats:
        c = red_feats[0]["geometry"]["coordinates"][0][0][0]
        print("sanity first red vertex lon/lat:", c)


if __name__ == "__main__":
    main()
