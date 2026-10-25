"""Pipeline v6 — group-based slum identification.

Unit = slum GROUP (blob), not the individual building vote.

1. small building: area < 80 m2. Per-building small_den = small bldg within 30 m / ha.
2. markers: buildings with small_den >= 35 (dense-small context, any site, ribbon-friendly).
3. 10 m grid: mark cells containing a marker; morphological closing dilate 5 / erode 4
   (25 m / 20 m) bridges gaps up to ~50 m — connecting ribbons between blobs get absorbed.
4. group accepted: >= 10 markers inside AND (>=50% markers within 150 m of
   canal/road/rail/industrial OR mean small_den >= 40/ha).
5. RED = ALL buildings (any size) with centroid inside an accepted group.
   Pink = everything else.
6. Blob rings: Douglas-Peucker 4 m + 3x Chaikin — smooth rounded, no saw.

Reads v3 files (descriptors incl corridor distances). No network. Pure stdlib.
Outputs: slum_roofs_red_v6.geojson, slum_roofs_pink_v6.geojson,
         slum_congestion_blobs_v6.geojson
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

SMALL_MAX = 80.0
MARK_DEN = 35.0
DISC_HA = math.pi * 900.0 / 10000.0


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


def chaikin(ring, iterations=3):
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
    red_v3 = json.load(open(os.path.join(QDIR, "slum_roofs_red_v3.geojson")))
    pink_v3 = json.load(open(os.path.join(QDIR, "slum_roofs_pink_v3.geojson")))
    by_site = defaultdict(list)
    for f in red_v3["features"] + pink_v3["features"]:
        by_site[f["properties"]["site"]].append(f)

    out_red, out_pink, blobs = [], [], []
    for site in SITES:
        feats = by_site.get(site, [])
        N = len(feats)

        lat0 = sum(centroid(f["geometry"])[1] for f in feats[:50]) / min(50, N)
        lon0 = sum(centroid(f["geometry"])[0] for f in feats[:50]) / min(50, N)
        mlon = 111320.0 * math.cos(math.radians(lat0))
        mlat = 111132.0

        def to_local(lon, lat):
            return ((lon - lon0) * mlon, (lat - lat0) * mlat)

        cents_ll = [centroid(f["geometry"]) for f in feats]
        cents_loc = [to_local(*c) for c in cents_ll]
        is_small = [(f["properties"].get("area_m2") or 0) < SMALL_MAX for f in feats]

        CELL = 30.0
        grid = defaultdict(list)
        for i, (x, y) in enumerate(cents_loc):
            grid[(int(x // CELL), int(y // CELL))].append(i)
        small_den = [0.0] * N
        for i, (cx, cy) in enumerate(cents_loc):
            gx, gy = int(cx // CELL), int(cy // CELL)
            cnt = 0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in grid.get((gx + dx, gy + dy), ()):
                        if j != i and is_small[j] and \
                           (cents_loc[j][0] - cx) ** 2 + (cents_loc[j][1] - cy) ** 2 <= 900.0:
                            cnt += 1
            small_den[i] = cnt / DISC_HA

        markers = [i for i in range(N) if is_small[i] and small_den[i] >= MARK_DEN]

        # 10 m grid closing
        cell = 10.0
        xs = [cents_loc[i][0] for i in markers] if markers else [0]
        ys = [cents_loc[i][1] for i in markers] if markers else [0]
        ox = math.floor(min(xs) / cell) * cell - 20 * cell
        oy = math.floor(min(ys) / cell) * cell - 20 * cell
        nx = int((max(xs) - ox) / cell) + 41
        ny = int((max(ys) - oy) / cell) + 41
        bboxc = (-5, nx + 5, -5, ny + 5)
        marks = {(int((cents_loc[i][0] - ox) // cell), int((cents_loc[i][1] - oy) // cell))
                 for i in markers}
        closed = erode(dilate(marks, 5, bboxc), 4, bboxc) if marks else set()

        def cell_of(i):
            return (int((cents_loc[i][0] - ox) // cell), int((cents_loc[i][1] - oy) // cell))

        n_red = n_blob = n_acc = 0
        red_ids = set()
        for comp in trace_components(closed):
            cset = set(comp)
            inside = [i for i in range(N) if cell_of(i) in cset]
            mk_in = [i for i in inside if i in set(markers)]
            if len(mk_in) < 10:
                continue
            mean_den = sum(small_den[i] for i in mk_in) / len(mk_in)

            def share(key):
                return sum(1 for i in mk_in if (feats[i]["properties"].get(key) or 1e9) <= 150) / len(mk_in)
            near = sum(1 for i in mk_in
                       if min(feats[i]["properties"].get("canal_m") or 1e9,
                              feats[i]["properties"].get("road_m") or 1e9,
                              feats[i]["properties"].get("rail_m") or 1e9,
                              feats[i]["properties"].get("indu_m") or 1e9) <= 150) / len(mk_in)
            accepted = len(mk_in) >= 10 and (near >= 0.5 or mean_den >= 40)
            if not accepted:
                continue

            rings_m = trace_rings(comp, cell, ox, oy)
            ll_rings = []
            for r in rings_m:
                rr = douglas_peucker(r, 4.0)
                if len(rr) < 4:
                    continue
                sm = chaikin(rr, 3)
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

            small_in = sum(1 for i in inside if is_small[i])
            ha = len(cset) * cell * cell / 10000.0
            blobs.append({"type": "Feature", "properties": {
                "site": site, "buildings": len(inside), "small_buildings": small_in,
                "small_den_ha": round(small_in / ha, 1) if ha > 0 else 0,
                "near_share": round(near, 2), "canal_share": round(share("canal_m"), 2),
                "road_share": round(share("road_m"), 2), "rail_share": round(share("rail_m"), 2),
                "indu_share": round(share("indu_m"), 2), "accepted": True},
                "geometry": {"type": "Polygon", "coordinates": [outer] + holes}})
            n_blob += 1
            n_acc += 1
            red_ids.update(inside)

        for i, f in enumerate(feats):
            p = f["properties"]
            p["small_den"] = round(small_den[i], 1)
            if i in red_ids:
                p["slum_group"] = 1
                out_red.append(f)
                n_red += 1
            else:
                p["slum_group"] = 0
                out_pink.append(f)
        print(f"{site:15s} bldg={N:6d} markers={len(markers):5d} groups={n_blob} red={n_red:6d}")

    def write(name, collection):
        path = os.path.join(QDIR, name)
        json.dump({"type": "FeatureCollection", "features": collection},
                  open(path, "w"), separators=(",", ":"))
        print(f"wrote {name}: {len(collection)} feats, {os.path.getsize(path)/1e6:.1f} MB")

    write("slum_roofs_red_v6.geojson", out_red)
    write("slum_roofs_pink_v6.geojson", out_pink)
    write("slum_congestion_blobs_v6.geojson", blobs)


if __name__ == "__main__":
    main()
