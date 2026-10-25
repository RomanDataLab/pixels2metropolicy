"""Full pipeline v2: all 14 sites, blob method C (raster closing 5 m, filled).

Stages:
  1. Fetch OSM canals per site bbox (Overpass, cached to labeling/qgis_project/canals/<site>.geojson)
  2. Per-building descriptors: existing crit fields + orientation concentration (30 m),
     size CV (30 m), canal distance
  3. Blobs: raster closing on 5 m grid from filled dense-building polygons;
     dilate 15 m, erode 12 m (3 cells at 5 m); accepted = >=10 buildings AND >=80 bldg/ha
  4. Outputs (WGS84):
     slum_roofs_red_v2.geojson    - slum==1 roofs with all descriptors
     slum_roofs_pink_v2.geojson   - slum==0 roofs with all descriptors
     slum_congestion_blobs_v2.geojson - method C blobs, accepted flag + stats

Pure stdlib.
"""
import json
import math
import os
import time
import urllib.parse
import urllib.request
from collections import defaultdict, deque

BASE = os.path.dirname(os.path.abspath(__file__))
QDIR = os.path.join(BASE, "qgis_project")
CDIR = os.path.join(QDIR, "canals")
os.makedirs(CDIR, exist_ok=True)

SITES = ["bkk_slum_1", "bkk_slum_3", "bkk_slum_5", "bkk_slum_6", "bkk_slum_7",
         "bkk_slum_8", "bkk_slum_9", "bkk_slum_10", "bkk_slum_11", "bkk_slum_12",
         "bkk_slum_13", "bkk_slum_41", "patt_slum_1", "slum_2"]

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


def transform_coords(c):
    if isinstance(c[0], (int, float)):
        lon, lat = utm_to_wgs84(c[0], c[1])
        return [round(lon, 7), round(lat, 7)]
    return [transform_coords(x) for x in c]


def ring_points(geom):
    pts = []
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        for ring in poly:
            pts.extend(ring)
    return pts


def bbox_wgs(feats, pad=400):
    xs, ys = [], []
    for f in feats:
        for p in ring_points(f["geometry"]):
            xs.append(p[0])
            ys.append(p[1])
    sw = utm_to_wgs84(min(xs) - pad, min(ys) - pad)
    ne = utm_to_wgs84(max(xs) + pad, max(ys) + pad)
    return sw[1], sw[0], ne[1], ne[0]  # S, W, N, E


def fetch_canals(site, bbox):
    path = os.path.join(CDIR, site + ".geojson")
    if os.path.exists(path) and os.path.getsize(path) > 100:
        return json.load(open(path))
    S, W, N, E = bbox
    q = f'[out:json][timeout:60];(way["waterway"~"^(canal|river|stream|drain)"]({S},{W},{N},{E}););out geom;'
    url = "https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(q)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "slum-blob-v2/1.0"})
            data = json.load(urllib.request.urlopen(req, timeout=90))
            break
        except Exception as ex:
            print("  overpass retry", attempt + 1, str(ex)[:60])
            time.sleep(5 * (attempt + 1))
    else:
        json.dump({"type": "FeatureCollection", "features": []}, open(path, "w"))
        return {"type": "FeatureCollection", "features": []}
    feats = []
    for el in data.get("elements", []):
        if el.get("type") != "way" or "geometry" not in el:
            continue
        feats.append({"type": "Feature",
                      "properties": {"waterway": el.get("tags", {}).get("waterway"),
                                     "name": el.get("tags", {}).get("name")},
                      "geometry": {"type": "LineString",
                                   "coordinates": [[p["lon"], p["lat"]] for p in el["geometry"]]}})
    json.dump({"type": "FeatureCollection", "features": feats}, open(path, "w"))
    return {"type": "FeatureCollection", "features": feats}


def local_frame(cent):
    lat0 = sum(utm_to_wgs84(c[0], c[1])[1] for c in cent[:50]) / 50
    lon0 = sum(utm_to_wgs84(c[0], c[1])[0] for c in cent[:50]) / 50
    mlat = 111132.0
    mlon = 111320.0 * math.cos(math.radians(lat0))
    return lon0, lat0, mlon, mlat


def ll_to_local(lon, lat, fr):
    return ((lon - fr[0]) * fr[2], (lat - fr[1]) * fr[3])


def canal_distances(cent, canal_feats, fr):
    lines = []
    for cf in canal_feats["features"]:
        lines.append([ll_to_local(p[0], p[1], fr) for p in cf["geometry"]["coordinates"]])
    cent_local = [ll_to_local(*utm_to_wgs84(c[0], c[1]), fr) for c in cent]
    out = []
    for px, py in cent_local:
        best = 1e12
        for pts in lines:
            for k in range(len(pts) - 1):
                ax, ay = pts[k]
                bx, by = pts[k + 1]
                dx, dy = bx - ax, by - ay
                L2 = dx * dx + dy * dy
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
                ex = ax + t * dx - px
                ey = ay + t * dy - py
                d2 = ex * ex + ey * ey
                if d2 < best:
                    best = d2
        out.append(math.sqrt(best))
    return out


def neighborhood_stats(cent, area, orient):
    N = len(cent)
    CELL = 30.0
    grid = defaultdict(list)
    for i, (cx, cy) in enumerate(cent):
        grid[(int(cx // CELL), int(cy // CELL))].append(i)
    orient_conc = [0.0] * N
    size_cv = [0.0] * N
    for i, (cx, cy) in enumerate(cent):
        gx, gy = int(cx // CELL), int(cy // CELL)
        grp = [i]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    if j != i and (cent[j][0] - cx) ** 2 + (cent[j][1] - cy) ** 2 <= 900.0:
                        grp.append(j)
        cs = sum(math.cos(2 * orient[j]) for j in grp)
        sn = sum(math.sin(2 * orient[j]) for j in grp)
        orient_conc[i] = math.hypot(cs, sn) / len(grp)
        a = [area[j] for j in grp]
        m = sum(a) / len(a)
        size_cv[i] = (math.sqrt(sum((x - m) ** 2 for x in a) / len(a)) / m) if m > 0 else 0.0
    return orient_conc, size_cv


# ---- raster closing (method C) ----
def dilate(mark, r, bbox):
    out = set()
    rr = r * r
    for (i, j) in mark:
        for di in range(-r, r + 1):
            djmax = int(math.sqrt(rr - di * di)) if rr - di * di >= 0 else -1
            for dj in range(-djmax, djmax + 1):
                key = (i + di, j + dj)
                if bbox[0] <= key[0] < bbox[1] and bbox[2] <= key[1] < bbox[3]:
                    out.add(key)
    return out


def erode(mark, r, bbox):
    comp = set()
    for i in range(bbox[0], bbox[1]):
        for j in range(bbox[2], bbox[3]):
            if (i, j) not in mark:
                comp.add((i, j))
    dil = dilate(comp, r, bbox)
    return {c for c in mark if c not in dil}


def trace_components(mark):
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
    nxt = defaultdict(list)
    for a, b in edges:
        nxt[a].append(b)
    rings = []
    while nxt:
        start = next(iter(nxt))
        ring = [start]
        cur = start
        while True:
            outs = nxt.get(cur)
            if not outs:
                del nxt[cur]
                break
            nb = outs.pop(0)
            if not outs:
                del nxt[cur]
            cur = nb
            if cur == start:
                break
            ring.append(cur)
        if len(ring) >= 4:
            rings.append(ring)
    return rings


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
            d = abs((pts[i][0] - ax) * dy - (pts[i][1] - ay) * dx) / norm
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True
            stack.append((i0, bi))
            stack.append((bi, i1))
    return [p for p, k in zip(pts, keep) if k]


def fill_polygons_to_cells(poly_utm_list, dense_polys, cell):
    xs = [p[0] for g in dense_polys for p in ring_points(g)]
    ys = [p[1] for g in dense_polys for p in ring_points(g)]
    ox = math.floor(min(xs) / cell) * cell - 15 * cell
    oy = math.floor(min(ys) / cell) * cell - 15 * cell
    nx = int((max(xs) - ox) / cell) + 31
    ny = int((max(ys) - oy) / cell) + 31
    marks = set()
    for g in dense_polys:
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            ext = poly[0]
            r0 = max(0, int((min(p[1] for p in ext) - oy) / cell))
            r1 = min(ny - 1, int((max(p[1] for p in ext) - oy) / cell))
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


def main():
    red, pink, blobs = [], [], []
    fid = 0
    for site in SITES:
        t0 = time.time()
        gj = json.load(open(os.path.join(QDIR, site + "_crit.geojson"), encoding="utf-8"))
        feats = gj["features"]
        N = len(feats)
        cent, area, orient, polys_utm = [], [], [], []
        for f in feats:
            g = f["geometry"]
            pts = ring_points(g)
            cent.append((sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)))
            area.append(f["properties"]["area_m2"] or 0.0)
            polys_utm.append(g)
            mx = sum(p[0] for p in pts) / len(pts)
            my = sum(p[1] for p in pts) / len(pts)
            sxx = syy = sxy = 0.0
            for p in pts:
                sxx += (p[0] - mx) ** 2
                syy += (p[1] - my) ** 2
                sxy += (p[0] - mx) * (p[1] - my)
            orient.append(0.5 * math.atan2(2 * sxy, sxx - syy))

        bbox = bbox_wgs(feats)
        canals = fetch_canals(site, bbox)
        fr = local_frame(cent)
        canal_d = canal_distances(cent, canals, fr)
        orient_conc, size_cv = neighborhood_stats(cent, area, orient)

        dense = [i for i in range(N) if feats[i]["properties"].get("slum") == 1
                 and (feats[i]["properties"].get("nb_20") or 0) >= 8]

        for i, f in enumerate(feats):
            p = dict(f["properties"])
            p.update({"site": site, "orient_conc": round(orient_conc[i], 3),
                      "size_cv": round(size_cv[i], 3), "canal_m": round(canal_d[i], 1)})
            out = {"type": "Feature", "id": fid, "properties": p,
                   "geometry": {"type": f["geometry"]["type"],
                                "coordinates": transform_coords(f["geometry"]["coordinates"])}}
            fid += 1
            (red if p.get("slum") == 1 else pink).append(out)

        # method C blobs
        dense_polys = [polys_utm[i] for i in dense]
        cell = 5.0
        marks, bboxc, ox, oy = fill_polygons_to_cells(polys_utm, dense_polys, cell)
        dil_r = max(1, round(15 / cell))
        ero_r = max(1, round(12 / cell))
        closed = erode(dilate(marks, dil_r, bboxc), ero_r, bboxc)
        n_blob = 0
        n_acc = 0
        for comp in trace_components(closed):
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
            ll_rings = []
            for r in rings_m:
                rr = douglas_peucker(r, 2.0)
                if len(rr) < 4:
                    continue
                ll_rings.append([[round(v, 7) for v in utm_to_wgs84(x, y)] for x, y in rr])
            if not ll_rings:
                continue

            def area_loc(ring):
                s = 0.0
                for k in range(len(ring) - 1):
                    x1, y1 = ll_to_local(ring[k][0], ring[k][1], fr)
                    x2, y2 = ll_to_local(ring[k + 1][0], ring[k + 1][1], fr)
                    s += x1 * y2 - x2 * y1
                return s / 2
            outers = [r for r in ll_rings if area_loc(r) > 0]
            holes = [r for r in ll_rings if area_loc(r) <= 0]
            if not outers:
                continue
            for r in outers + holes:
                if r[0] != r[-1]:
                    r.append(r[0])
            poly = [outers[0]] + holes
            n = len(idxs)
            ha = len(cset) * cell * cell / 10000.0
            dens = n / ha if ha > 0 else 0
            oc = sum(orient_conc[i] for i in idxs) / n
            cv = sum(size_cv[i] for i in idxs) / n
            cmed = sorted(canal_d[i] for i in idxs)[n // 2]
            nshare = sum(1 for i in idxs if canal_d[i] <= 150) / n
            accepted = n >= 10 and dens >= 80
            blobs.append({"type": "Feature", "properties": {
                "site": site, "buildings": n, "density_ha": round(dens, 1),
                "orient_conc": round(oc, 2), "size_cv": round(cv, 2),
                "canal_med_m": round(cmed, 0), "canal_150m_share": round(nshare, 2),
                "accepted": accepted},
                "geometry": {"type": "Polygon", "coordinates": poly}})
            n_blob += 1
            n_acc += accepted
        print(f"{site:15s} bldg={N:6d} dense={len(dense):5d} canals={len(canals['features']):3d} "
              f"blobs={n_blob} accepted={n_acc} ({time.time()-t0:.0f}s)")

    def write(name, collection):
        path = os.path.join(QDIR, name)
        json.dump({"type": "FeatureCollection", "features": collection},
                  open(path, "w"), separators=(",", ":"))
        print(f"wrote {name}: {len(collection)} feats, {os.path.getsize(path)/1e6:.1f} MB")

    write("slum_roofs_red_v2.geojson", red)
    write("slum_roofs_pink_v2.geojson", pink)
    write("slum_congestion_blobs_v2.geojson", blobs)


if __name__ == "__main__":
    main()
