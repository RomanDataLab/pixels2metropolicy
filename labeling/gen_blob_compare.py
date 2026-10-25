"""Blob-method comparison for bkk_slum_3 (pure stdlib).

Outputs to labeling/qgis_project/:
  bkk_slum_3_roofs_enriched.geojson   - roofs + new descriptors (orientation
                                        concentration, size CV, canal distance)
  blobcompare_A_hulls.geojson         - convex hulls, clusters eps 30 m, min 15
  blobcompare_B_raster10.geojson      - raster closing 10 m from centroids
  blobcompare_C_fill5.geojson         - raster closing 5 m from filled polygons
All WGS84. Blob acceptance: >=10 buildings AND >=80 buildings/ha (loose cut).
"""
import json
import math
import os
from collections import defaultdict, deque

BASE = os.path.dirname(os.path.abspath(__file__))
QDIR = os.path.join(BASE, "qgis_project")
SITE = "bkk_slum_3"

A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)
EP2 = E2 / (1 - E2)
K0 = 0.9996
LON0 = math.radians(99.0)


def utm_to_wgs84(e, n):
    x = e - 500000.0
    M = n / K0
    mu = M / (A * (1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    fp = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) \
        + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu) \
        + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu)
    s = math.sin(fp) ** 2
    C1 = EP2 * math.cos(fp) ** 2
    T1 = math.tan(fp) ** 2
    N1 = A / math.sqrt(1 - E2 * s)
    R1 = A * (1 - E2) / (1 - E2 * s) ** 1.5
    D = x / (N1 * K0)
    lat = fp - (N1 * math.tan(fp) / R1) * (
        D ** 2 / 2
        - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * EP2) * D ** 4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * EP2 - 3 * C1 ** 2) * D ** 6 / 720)
    lon = LON0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6
                  + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * EP2 + 24 * T1 ** 2) * D ** 5 / 120) / math.cos(fp)
    return math.degrees(lon), math.degrees(lat)


def ring_points(geom):
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


def douglas_peucker(pts, tol):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i0, i1 = stack.pop()
        if i1 <= i0 + 1:
            continue
        ax, ay = pts[i0]
        bx, by = pts[i1]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy) or 1e-12
        best, bi = -1.0, -1
        for i in range(i0 + 1, i1):
            px, py = pts[i]
            d = abs((px - ax) * dy - (py - ay) * dx) / norm
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True
            stack.append((i0, bi))
            stack.append((bi, i1))
    return [p for p, k in zip(pts, keep) if k]


# ---------- load site ----------
site = json.load(open(os.path.join(QDIR, SITE + "_crit.geojson"), encoding="utf-8"))
feats = site["features"]

# per-building arrays in UTM meters
cent, area, orient = [], [], []
polys_utm = []
for f in feats:
    g = f["geometry"]
    pts = ring_points(g)
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    cent.append((cx, cy))
    area.append(f["properties"]["area_m2"] or 0.0)
    polys_utm.append(g)
    # PCA angle on vertices
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    sxx = syy = sxy = 0.0
    for p in pts:
        sxx += (p[0] - mx) ** 2
        syy += (p[1] - my) ** 2
        sxy += (p[0] - mx) * (p[1] - my)
    theta = 0.5 * math.atan2(2 * sxy, sxx - syy)
    orient.append(theta)

N = len(feats)

# ---------- neighborhoods at 30 m (grid hash) ----------
CELL = 30.0
grid = defaultdict(list)
for i, (cx, cy) in enumerate(cent):
    grid[(int(cx // CELL), int(cy // CELL))].append(i)

nb30 = [[] for _ in range(N)]
for i, (cx, cy) in enumerate(cent):
    gx, gy = int(cx // CELL), int(cy // CELL)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for j in grid.get((gx + dx, gy + dy), ()):
                if j == i:
                    continue
                if (cent[j][0] - cx) ** 2 + (cent[j][1] - cy) ** 2 <= 900.0:
                    nb30[i].append(j)

orient_conc = [0.0] * N
size_cv = [0.0] * N
for i in range(N):
    grp = nb30[i] + [i]
    if len(grp) < 2:
        continue
    cs = sum(math.cos(2 * orient[j]) for j in grp)
    sn = sum(math.sin(2 * orient[j]) for j in grp)
    orient_conc[i] = math.hypot(cs, sn) / len(grp)
    a = [area[j] for j in grp]
    m = sum(a) / len(a)
    size_cv[i] = (math.sqrt(sum((x - m) ** 2 for x in a) / len(a)) / m) if m > 0 else 0.0

# ---------- canals ----------
canals_wgs = json.load(open(os.path.join(QDIR, "osm_canals_" + SITE + ".geojson"), encoding="utf-8"))
segs = []
for cw in canals_wgs["features"]:
    coords = cw["geometry"]["coordinates"]
    # transform lon/lat back to UTM approx: invert via Newton on lat/lon is heavy;
    # instead re-derive from original crit bbox? Use coarse approach: convert canal
    # vertices to UTM by solving with secant iteration around site center scale.
    # Simpler: build local equirectangular projection centered on site mean.
    pass
# local equirectangular projection around site centroid (good to ~1 m over 2 km)
lat0 = sum(utm_to_wgs84(c[0], c[1])[1] for c in cent[:50]) / 50
lon0 = sum(utm_to_wgs84(c[0], c[1])[0] for c in cent[:50]) / 50
M_PER_DEG_LAT = 111132.0
M_PER_DEG_LON = 111320.0 * math.cos(math.radians(lat0))


def ll_to_local(lon, lat):
    return ((lon - lon0) * M_PER_DEG_LON, (lat - lat0) * M_PER_DEG_LAT)


canal_lines = []
for cw in canals_wgs["features"]:
    pts = [ll_to_local(p[0], p[1]) for p in cw["geometry"]["coordinates"]]
    canal_lines.append(pts)

cent_local = []
for cx, cy in cent:
    lon, lat = utm_to_wgs84(cx, cy)
    cent_local.append(ll_to_local(lon, lat))


def canal_dist_m(px, py):
    best = 1e12
    for pts in canal_lines:
        for k in range(len(pts) - 1):
            ax, ay = pts[k]
            bx, by = pts[k + 1]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            if L2 == 0:
                t = 0.0
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
            ex = ax + t * dx - px
            ey = ay + t * dy - py
            d2 = ex * ex + ey * ey
            if d2 < best:
                best = d2
    return math.sqrt(best)


canal_d = [canal_dist_m(c[0], c[1]) for c in cent_local]
print("canal dist: min %.0f m, median %.0f m" % (min(canal_d), sorted(canal_d)[N // 2]))

# ---------- enriched roofs output ----------
def transform_coords(c):
    if isinstance(c[0], (int, float)):
        lon, lat = utm_to_wgs84(c[0], c[1])
        return [round(lon, 7), round(lat, 7)]
    return [transform_coords(x) for x in c]


enriched = {"type": "FeatureCollection",
            "features": []}
for i, f in enumerate(feats):
    p = dict(f["properties"])
    p["orient_conc"] = round(orient_conc[i], 3)
    p["size_cv"] = round(size_cv[i], 3)
    p["canal_m"] = round(canal_d[i], 1)
    enriched["features"].append({
        "type": "Feature",
        "properties": p,
        "geometry": {"type": f["geometry"]["type"],
                     "coordinates": transform_coords(f["geometry"]["coordinates"])}})
with open(os.path.join(QDIR, SITE + "_roofs_enriched.geojson"), "w") as fh:
    json.dump(enriched, fh, separators=(",", ":"))
print("enriched roofs written:", N)

# ---------- dense input set ----------
dense = [i for i in range(N) if feats[i]["properties"]["slum"] == 1
         and (feats[i]["properties"]["nb_20"] or 0) >= 8]
print("dense input buildings:", len(dense))


def blob_stats(idxs, poly_wgs_area_ha):
    n = len(idxs)
    oc = sum(orient_conc[i] for i in idxs) / n
    cv = sum(size_cv[i] for i in idxs) / n
    cd = sorted(canal_d[i] for i in idxs)[n // 2]
    near = sum(1 for i in idxs if canal_d[i] <= 150) / n
    return {"buildings": n, "density_ha": round(n / poly_wgs_area_ha, 1),
            "orient_conc": round(oc, 2), "size_cv": round(cv, 2),
            "canal_med_m": round(cd, 0), "canal_150m_share": round(near, 2)}


def dens_ha_ring_area(rings_ll, n_cells=None, cell_m=None):
    # shoelace on local meters
    def area_loc(ring):
        s = 0.0
        for k in range(len(ring) - 1):
            x1, y1 = ll_to_local(*ring[k])
            x2, y2 = ll_to_local(*ring[k + 1])
            s += x1 * y2 - x2 * y1
        return abs(s) / 2
    a = area_loc(rings_ll[0])
    for r in rings_ll[1:]:
        a -= area_loc(r)
    return a / 10000.0


def make_feature(rings_ll, idxs, method):
    ha = dens_ha_ring_area(rings_ll)
    st = blob_stats(idxs, ha)
    st["method"] = method
    ok = st["buildings"] >= 10 and st["density_ha"] >= 80
    st["accepted"] = ok
    return {"type": "Feature", "properties": st,
            "geometry": {"type": "Polygon", "coordinates": rings_ll}}, ok


def to_ll_ring(ring_m):
    return [[round(v, 7) for v in utm_to_wgs84(x, y)] for x, y in ring_m]


# ---------- method A: convex hulls, eps 30 m, min 15 ----------
def cluster(points, eps, min_size):
    cell = eps
    g = defaultdict(list)
    for k, (x, y) in enumerate(points):
        g[(int(x // cell), int(y // cell))].append(k)
    pos = points
    seen = set()
    comps = []
    for k in range(len(points)):
        if k in seen:
            continue
        stack = [k]
        seen.add(k)
        comp = []
        while stack:
            cur = stack.pop()
            comp.append(cur)
            px, py = pos[cur]
            cgx, cgy = int(px // cell), int(py // cell)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for o in g.get((cgx + dx, cgy + dy), ()):
                        if o in seen:
                            continue
                        if (pos[o][0] - px) ** 2 + (pos[o][1] - py) ** 2 <= eps * eps:
                            seen.add(o)
                            stack.append(o)
        if len(comp) >= min_size:
            comps.append(comp)
    return comps


featsA = []
pts_dense = [cent[i] for i in dense]
for comp in cluster(pts_dense, 30.0, 15):
    idxs = [dense[k] for k in comp]
    hull = convex_hull([pts_dense[k] for k in comp])
    if len(hull) < 3:
        continue
    ring = to_ll_ring(hull + [hull[0]])
    feat, ok = make_feature([ring], idxs, "A_hull")
    feat["properties"]["accepted"] = True  # show all, accepted flag in props
    featsA.append(feat)
json.dump({"type": "FeatureCollection", "features": featsA},
          open(os.path.join(QDIR, "blobcompare_A_hulls.geojson"), "w"), separators=(",", ":"))
print("A hulls:", len(featsA), "accepted:", sum(1 for f in featsA if f["properties"]["accepted"]))


# ---------- raster closing machinery ----------
def dilate(mark, r, bbox):
    out = set()
    rr = r * r
    for (i, j) in mark:
        x0, y0 = i, j
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if di * di + dj * dj <= rr:
                    key = (x0 + di, y0 + dj)
                    if key not in out:
                        if bbox[0] <= key[0] < bbox[1] and bbox[2] <= key[1] < bbox[3]:
                            out.add(key)
    return out


def erode(mark, r, bbox):
    # keep cells whose full disc radius r (in cells) is marked
    # complement dilate, then invert
    comp = set()
    for i in range(bbox[0], bbox[1]):
        for j in range(bbox[2], bbox[3]):
            if (i, j) not in mark:
                comp.add((i, j))
    dil = dilate(comp, r, bbox)
    return {c for c in mark if c not in dil}


def trace_components(mark):
    # 8-conn components
    seen = set()
    comps = []
    for c in mark:
        if c in seen:
            continue
        q = deque([c])
        seen.add(c)
        comp = []
        while q:
            cur = q.popleft()
            comp.append(cur)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    n = (cur[0] + di, cur[1] + dj)
                    if n in mark and n not in seen:
                        seen.add(n)
                        q.append(n)
        comps.append(comp)
    return comps


def trace_rings(comp, cell, ox, oy):
    """boundary edges between marked cells and empty neighbors, stitched to rings"""
    cs = set(comp)
    edges = []
    for (i, j) in comp:
        x0 = ox + i * cell
        y0 = oy + j * cell
        x1, y1 = x0 + cell, y0 + cell
        if (i, j - 1) not in cs:
            edges.append(((x0, y0), (x1, y0)))
        if (i + 1, j) not in cs:
            edges.append(((x1, y0), (x1, y1)))
        if (i, j + 1) not in cs:
            edges.append(((x1, y1), (x0, y1)))
        if (i - 1, j) not in cs:
            edges.append(((x0, y1), (x0, y0)))
    nxt = {}
    for a, b in edges:
        nxt.setdefault(a, []).append(b)
    rings = []
    while nxt:
        start = next(iter(nxt))
        ring = [start]
        cur = start
        prev_dir = None
        while True:
            outs = nxt.get(cur)
            if not outs:
                break
            # prefer continuing straight or turning right for consistent loops
            if len(outs) == 1:
                nb = outs[0]
            else:
                nb = outs[0]
            outs.remove(nb)
            if not outs:
                del nxt[cur]
            cur = nb
            if cur == start:
                break
            ring.append(cur)
        if len(ring) >= 4:
            rings.append(ring)
    return rings


def rings_to_polygon(rings_m, cell):
    ll_rings = []
    for r in rings_m:
        rr = douglas_peucker(r, 2.0)
        if len(rr) < 4:
            continue
        ll = to_ll_ring(rr)
        ll_rings.append(ll)
    if not ll_rings:
        return None
    # orientation fix: outer CCW, holes CW (shoelace in local meters)
    def area2(ring):
        s = 0.0
        for k in range(len(ring) - 1):
            x1, y1 = ll_to_local(*ring[k])
            x2, y2 = ll_to_local(*ring[k + 1])
            s += x1 * y2 - x2 * y1
        return s / 2
    outers = [r for r in ll_rings if area2(r) > 0]
    holes = [r for r in ll_rings if area2(r) <= 0]
    if not outers:
        ll_rings[0].reverse()
        outers = [ll_rings[0]]
        holes = ll_rings[1:]
    return [outers[0]] + holes


def raster_closing(input_cells, bbox, cell, dil_r, ero_r):
    m1 = dilate(input_cells, dil_r, bbox)
    m2 = erode(m1, ero_r, bbox)
    return m2


def cells_for_centroids(cell):
    cells = set()
    origin = None
    xs = [cent[i][0] for i in dense]
    ys = [cent[i][1] for i in dense]
    ox = math.floor(min(xs) / cell) * cell
    oy = math.floor(min(ys) / cell) * cell
    for i in dense:
        ci = int((cent[i][0] - ox) // cell)
        cj = int((cent[i][1] - oy) // cell)
        cells.add((ci, cj))
    xs_ = [ox + (c[0]) * cell for c in cells] + [ox]
    return cells, (min(c[0] for c in cells) - 5, max(c[0] for c in cells) + 6,
                   min(c[1] for c in cells) - 5, max(c[1] for c in cells) + 6), ox, oy


def cells_for_polygons(cell):
    # scanline fill: mark cells whose center is inside any dense building polygon
    xs = [cent[i][0] for i in dense]
    ys = [cent[i][1] for i in dense]
    ox = math.floor(min(xs) / cell) * cell - 10 * cell
    oy = math.floor(min(ys) / cell) * cell - 10 * cell
    nx = int((max(xs) - ox) / cell) + 21
    ny = int((max(ys) - oy) / cell) + 21
    marks = set()
    poly_list = []
    for i in dense:
        g = polys_utm[i]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        poly_list.extend(polys)
    for pi, poly in enumerate(poly_list):
        ext = poly[0]
        for r in range(len(ext) - 1):
            pass
    # point-in-polygon per cell center is too slow; use scanline per polygon row bands
    for poly in poly_list:
        ext = poly[0]
        ys_ = [p[1] for p in ext]
        r0 = max(0, int((min(ys_) - oy) / cell))
        r1 = min(ny - 1, int((max(ys_) - oy) / cell))
        for rj in range(r0, r1 + 1):
            yline = oy + (rj + 0.5) * cell
            xs_int = []
            for k in range(len(ext) - 1):
                x1, y1 = ext[k]
                x2, y2 = ext[k + 1]
                if (y1 <= yline < y2) or (y2 <= yline < y1):
                    t = (yline - y1) / (y2 - y1)
                    xs_int.append(x1 + t * (x2 - x1))
            xs_int.sort()
            for k in range(0, len(xs_int) - 1, 2):
                c0 = int((xs_int[k] - ox) / cell)
                c1 = int((xs_int[k + 1] - ox) / cell)
                for ci in range(max(0, c0), min(nx - 1, c1) + 1):
                    marks.add((ci, rj))
    return marks, (-5, nx + 5, -5, ny + 5), ox, oy


def build_raster_blobs(marks, bbox, ox, oy, cell, method):
    closed = raster_closing(marks, bbox, cell, dil_r=max(1, round(15 / cell)), ero_r=max(1, round(12 / cell)))
    comps = trace_components(closed)
    feats_out = []
    cell_ha = (cell * cell) / 10000.0
    # centroid cell lookup for building counts
    for comp in comps:
        cset = set(comp)
        idxs = []
        for i in dense:
            ci = int((cent[i][0] - ox) // cell)
            cj = int((cent[i][1] - oy) // cell)
            if (ci, cj) in cset:
                idxs.append(i)
        if not idxs:
            continue
        rings_m = trace_rings(comp, cell, ox, oy)
        poly = rings_to_polygon(rings_m, cell)
        if not poly:
            continue
        n = len(idxs)
        ha = n_cells_area = len(cset) * cell_ha
        st = blob_stats(idxs, ha)
        st["method"] = method
        st["accepted"] = st["buildings"] >= 10 and st["density_ha"] >= 80
        feats_out.append({"type": "Feature", "properties": st,
                          "geometry": {"type": "Polygon", "coordinates": poly}})
    return feats_out


# B: 10 m grid from centroids
cellsB, bboxB, oxB, oyB = cells_for_centroids(10.0)
featsB = build_raster_blobs(cellsB, bboxB, oxB, oyB, 10.0, "B_raster10")
json.dump({"type": "FeatureCollection", "features": featsB},
          open(os.path.join(QDIR, "blobcompare_B_raster10.geojson"), "w"), separators=(",", ":"))
print("B raster10:", len(featsB), "accepted:", sum(1 for f in featsB if f["properties"]["accepted"]))

# C: 5 m grid from filled polygons
cellsC, bboxC, oxC, oyC = cells_for_polygons(5.0)
featsC = build_raster_blobs(cellsC, bboxC, oxC, oyC, 5.0, "C_fill5")
json.dump({"type": "FeatureCollection", "features": featsC},
          open(os.path.join(QDIR, "blobcompare_C_fill5.geojson"), "w"), separators=(",", ":"))
print("C fill5:", len(featsC), "accepted:", sum(1 for f in featsC if f["properties"]["accepted"]))
print("DONE")
