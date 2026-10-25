"""Pipeline v5.

Changes vs v4:
  - slum roof area threshold raised: area < 80 m2 (was 60); >150 m2 still never
  - small building = area < 80 m2; per-building small_den = small buildings
    within 30 m per ha (disc 0.2827 ha)
  - blob stat small_den_ha = ALL small buildings (red or pink) with centroid in
    blob, per ha; acceptance: >=10 red bldg AND (near_share >= 0.5 OR
    small_den_ha >= 40)
  - blob rings smoothed: Douglas-Peucker then 2x Chaikin corner cutting
    (rounded angles)

Reads v3 roof files (WGS84, descriptors) — no network. Pure stdlib.
Outputs: slum_roofs_red_v5.geojson, slum_roofs_pink_v5.geojson,
         slum_congestion_blobs_v5.geojson
"""
import json
import math
import os
from collections import defaultdict, deque

BASE = os.path.dirname(os.path.abspath(__file__))
QDIR = os.path.join(BASE, "qgis_project")

SITES = ["bkk_slum_1", "bkk_slum_3", "bkk_slum_5", "bkk_slum_6", "bkk_slum_7",
         "bkk_slum_8", "bkk_slum_9", "bkk_slum_10", "bkk_slum_11", "bkk_slum_12",
         "bkk_slum_13", "bkk_slum_41", "patt_slum_1", "slum_2"]

AREA_MAX = 80.0     # small building / slum-roof size cap
NEVER = 150.0       # never slum above this
NB_MIN = 10
DISC_HA = math.pi * 30.0 * 30.0 / 10000.0  # 30 m disc area in ha


def is_slum(p):
    a = p.get("area_m2") or 0
    nb = p.get("nb_20") or 0
    rect = p.get("rect")
    elong = p.get("elong")
    if a >= AREA_MAX or a > NEVER or nb < NB_MIN:
        return False
    return (rect is not None and rect < 0.6) or (elong is not None and elong > 0.7)


def ring_coords(geom):
    if geom["type"] == "Polygon":
        for r in geom["coordinates"]:
            yield r
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            for r in poly:
                yield r


def ring_points_flat(geom):
    pts = []
    for r in ring_coords(geom):
        pts.extend(r)
    return pts


def centroid(geom):
    pts = ring_points_flat(geom)
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def dilate(mark, r, bbox):
    out = set()
    rr = r * r
    for (i, j) in mark:
        for di in range(-r, r + 1):
            rem = rr - di * di
            if rem < 0:
                continue
            djmax = int(math.sqrt(rem))
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


def chaikin(ring, iterations=2):
    """Corner-cutting smoothing on a closed ring (first == last point)."""
    closed = ring[:-1] if ring[0] == ring[-1] else ring[:]
    for _ in range(iterations):
        n = len(closed)
        if n < 3:
            break
        out = []
        for i in range(n):
            a = closed[i]
            b = closed[(i + 1) % n]
            out.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            out.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        closed = out
    closed.append(closed[0])
    return closed


def main():
    red_all = json.load(open(os.path.join(QDIR, "slum_roofs_red_v3.geojson")))
    pink_all = json.load(open(os.path.join(QDIR, "slum_roofs_pink_v3.geojson")))
    by_site = defaultdict(list)
    for f in red_all["features"] + pink_all["features"]:
        by_site[f["properties"]["site"]].append(f)

    out_red, out_pink, blobs = [], [], []
    for site in SITES:
        feats = by_site.get(site, [])

        # per-building small-building density within 30 m (local meters via equirect)
        lat0 = sum(centroid(f["geometry"])[1] for f in feats[:50]) / min(50, len(feats))
        lon0 = sum(centroid(f["geometry"])[0] for f in feats[:50]) / min(50, len(feats))
        mlon = 111320.0 * math.cos(math.radians(lat0))
        mlat = 111132.0

        def to_local(lon, lat):
            return ((lon - lon0) * mlon, (lat - lat0) * mlat)

        cents_ll = [centroid(f["geometry"]) for f in feats]
        cents_loc = [to_local(*c) for c in cents_ll]
        is_small = [(f["properties"].get("area_m2") or 0) < AREA_MAX for f in feats]
        CELL = 30.0
        grid = defaultdict(list)
        for i, (x, y) in enumerate(cents_loc):
            grid[(int(x // CELL), int(y // CELL))].append(i)
        small_den = [0.0] * len(feats)
        for i, (cx, cy) in enumerate(cents_loc):
            gx, gy = int(cx // CELL), int(cy // CELL)
            cnt = 0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in grid.get((gx + dx, gy + dy), ()):
                        if j == i:
                            continue
                        if (cents_loc[j][0] - cx) ** 2 + (cents_loc[j][1] - cy) ** 2 <= 900.0 and is_small[j]:
                            cnt += 1
            small_den[i] = cnt / DISC_HA

        n_red = 0
        for i, f in enumerate(feats):
            p = f["properties"]
            p["small_den"] = round(small_den[i], 1)
            if is_slum(p):
                p["slum_strict"] = 1
                out_red.append(f)
                n_red += 1
            else:
                p["slum_strict"] = 0
                out_pink.append(f)

        # ---- blobs from strict-red footprints, method C + Chaikin smoothing ----
        red_idx = [i for i, f in enumerate(feats) if is_slum(f["properties"])]
        n_blob = n_acc = 0
        if red_idx:
            cell = 5.0
            loc_polys = []
            xs, ys = [], []
            for i in red_idx:
                rings = []
                for r in ring_coords(feats[i]["geometry"]):
                    lr = [to_local(p[0], p[1]) for p in r]
                    rings.append(lr)
                    xs.extend(p[0] for p in lr)
                    ys.extend(p[1] for p in lr)
                loc_polys.append(rings)
            ox = math.floor(min(xs) / cell) * cell - 15 * cell
            oy = math.floor(min(ys) / cell) * cell - 15 * cell
            nx = int((max(xs) - ox) / cell) + 31
            ny = int((max(ys) - oy) / cell) + 31
            marks = set()
            for rings in loc_polys:
                ext = rings[0]
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
            bboxc = (-5, nx + 5, -5, ny + 5)
            closed = erode(dilate(marks, 3, bboxc), 2, bboxc)

            def cell_of(i):
                return (int((cents_loc[i][0] - ox) // cell), int((cents_loc[i][1] - oy) // cell))

            for comp in trace_components(closed):
                cset = set(comp)
                idxs = [i for i in range(len(feats)) if cell_of(i) in cset]
                red_in = [i for i in idxs if is_slum(feats[i]["properties"])]
                if not red_in:
                    continue
                rings_m = trace_rings(comp, cell, ox, oy)
                ll_rings = []
                for r in rings_m:
                    rr = douglas_peucker(r, 2.0)
                    if len(rr) < 4:
                        continue
                    sm = chaikin(rr, 2)
                    ll_rings.append([[round(lon0 + x / mlon, 7), round(lat0 + y / mlat, 7)] for x, y in sm])
                if not ll_rings:
                    continue

                def area_loc(ring):
                    s = 0.0
                    for k in range(len(ring) - 1):
                        s += ring[k][0] * ring[k + 1][1] - ring[k + 1][0] * ring[k][1]
                    return abs(s) / 2 * mlon * mlat
                outer = max(ll_rings, key=area_loc)
                holes = [r for r in ll_rings if r is not outer]
                for r in [outer] + holes:
                    if r[0] != r[-1]:
                        r.append(r[0])
                n = len(red_in)
                ha = len(cset) * cell * cell / 10000.0
                dens = n / ha if ha > 0 else 0
                small_all = sum(1 for i in idxs if is_small[i])
                small_den_ha = small_all / ha if ha > 0 else 0

                def near_i(p):
                    return min(p.get("canal_m") or 1e9, p.get("road_m") or 1e9,
                               p.get("rail_m") or 1e9, p.get("indu_m") or 1e9) <= 150
                near = sum(1 for i in red_in if near_i(feats[i]["properties"])) / n

                def share(key):
                    return sum(1 for i in red_in if (feats[i]["properties"].get(key) or 1e9) <= 150) / n
                accepted = n >= 10 and (near >= 0.5 or small_den_ha >= 40)
                blobs.append({"type": "Feature", "properties": {
                    "site": site, "buildings": n, "density_ha": round(dens, 1),
                    "small_den_ha": round(small_den_ha, 1),
                    "near_share": round(near, 2), "canal_share": round(share("canal_m"), 2),
                    "road_share": round(share("road_m"), 2), "rail_share": round(share("rail_m"), 2),
                    "indu_share": round(share("indu_m"), 2), "accepted": accepted},
                    "geometry": {"type": "Polygon", "coordinates": [outer] + holes}})
                n_blob += 1
                n_acc += accepted
        print(f"{site:15s} bldg={len(feats):6d} strict_red={n_red:6d} blobs={n_blob} accepted={n_acc}")

    def write(name, collection):
        path = os.path.join(QDIR, name)
        json.dump({"type": "FeatureCollection", "features": collection},
                  open(path, "w"), separators=(",", ":"))
        print(f"wrote {name}: {len(collection)} feats, {os.path.getsize(path)/1e6:.1f} MB")

    write("slum_roofs_red_v5.geojson", out_red)
    write("slum_roofs_pink_v5.geojson", out_pink)
    write("slum_congestion_blobs_v5.geojson", blobs)


if __name__ == "__main__":
    main()
