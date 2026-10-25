"""Per-building descriptors for slum sites — pure stdlib replacement of the
original QGIS compute step.

For each <site>.geojson (EPSG:32647) writes <site>_crit.geojson with
fid, det_id, class, confidence, area_m2, perimeter_m + nb_20, nn_m, rect, elong,
rules_hit, slum (legacy 2-of-4 vote, kept for backward compatibility).

Polygon-to-polygon distance approximated as min vertex-pair distance (exact for
these footprints at the 20 m / nearest-neighbour scale).
"""
import json
import math
import os
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
QDIR = os.path.join(BASE, "qgis_project")


def rings_of(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def main(sites):
    for site in sites:
        src = os.path.join(QDIR, site + ".geojson")
        dst = os.path.join(QDIR, site + "_crit.geojson")
        d = json.load(open(src, encoding="utf-8"))
        feats = d["features"]
        N = len(feats)

        cents = []
        bb = []
        area = []
        elong = []
        for f in feats:
            polys = rings_of(f["geometry"])
            pts = [p for poly in polys for ring in poly for p in ring]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cents.append((sum(xs) / len(xs), sum(ys) / len(ys)))
            bb.append((min(xs), min(ys), max(xs), max(ys)))
            a = f["properties"]["area_m2"] or 0.0
            area.append(a)
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            sxx = syy = sxy = 0.0
            for p in pts:
                sxx += (p[0] - mx) ** 2
                syy += (p[1] - my) ** 2
                sxy += (p[0] - mx) * (p[1] - my)
            tr = sxx + syy
            disc = max(0.0, tr * tr / 4 - (sxx * syy - sxy * sxy))
            l1 = math.sqrt(max(0.0, tr / 2 + math.sqrt(disc)))
            l2 = math.sqrt(max(0.0, tr / 2 - math.sqrt(disc)))
            elong.append(1.0 - math.sqrt(max(l2, 0.0) / l1) if l1 > 1e-9 else 0.0)

        rect = []
        for i in range(N):
            x0, y0, x1, y1 = bb[i]
            ba = (x1 - x0) * (y1 - y0)
            rect.append(area[i] / ba if ba > 0 else 1.0)

        # spatial grid on centroids, 25 m cells
        CELL = 25.0
        grid = defaultdict(list)
        for i, (cx, cy) in enumerate(cents):
            grid[(int(cx // CELL), int(cy // CELL))].append(i)

        nb20 = [0] * N
        nn = [-1.0] * N
        for i, (cx, cy) in enumerate(cents):
            gx, gy = int(cx // CELL), int(cy // CELL)
            cnt = 0
            best = -1.0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in grid.get((gx + dx, gy + dy), ()):
                        if j == i:
                            continue
                        # bbox reject first
                        bx0, by0, bx1, by1 = bb[j]
                        if bx0 - 20 > bb[i][2] + 20 or bx1 + 20 < bb[i][0] - 20:
                            continue
                        if by0 - 20 > bb[i][3] + 20 or by1 + 20 < bb[i][1] - 20:
                            continue
                        # min vertex-pair distance
                        dmin = 1e18
                        polys_i = rings_of(feats[i]["geometry"])
                        polys_j = rings_of(feats[j]["geometry"])
                        short_i = [(p[0], p[1]) for poly in polys_i for ring in poly for p in ring]
                        short_j = [(p[0], p[1]) for poly in polys_j for ring in poly for p in ring]
                        for pi in range(0, len(short_i), 2):
                            xi, yi = short_i[pi]
                            for pj in range(0, len(short_j), 2):
                                dxv = short_j[pj][0] - xi
                                dyv = short_j[pj][1] - yi
                                dv = dxv * dxv + dyv * dyv
                                if dv < dmin:
                                    dmin = dv
                        dmin = math.sqrt(dmin)
                        if dmin <= 20.0:
                            cnt += 1
                        if best < 0 or dmin < best:
                            best = dmin
            nb20[i] = cnt
            nn[i] = best

        out = {"type": "FeatureCollection",
               "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32647"}},
               "features": []}
        for i, f in enumerate(feats):
            p = f["properties"]
            a = area[i]
            c1 = nb20[i] >= 8
            c2 = nn[i] >= 0 and nn[i] < 4.0
            c3 = a < 70.0
            c4 = rect[i] < 0.55 or elong[i] > 0.75
            rules = int(c1) + int(c2) + int(c3) + int(c4)
            p = dict(p)
            p.update({"nb_20": nb20[i],
                      "nn_m": round(nn[i], 2) if nn[i] >= 0 else None,
                      "rect": round(rect[i], 3), "elong": round(elong[i], 3),
                      "rules_hit": rules, "slum": 1 if rules >= 2 else 0})
            out["features"].append({"type": "Feature", "properties": p,
                                    "geometry": f["geometry"]})
        json.dump(out, open(dst, "w", encoding="utf-8"), separators=(",", ":"))
        flagged = sum(1 for f in out["features"] if f["properties"]["slum"] == 1)
        print(f"{site:15s} n={N:6d} legacy_slum={flagged:5d} -> {os.path.basename(dst)}")


if __name__ == "__main__":
    default = ["bkk_slum_12", "bkk_slum_14", "bkk_slum_15", "bkk_slum_41",
               "chm_slum_1", "chm_slum_2", "chm_slum_3",
               "hat_slum_1", "hat_slum_2", "patt_slum_2", "phu_slum_1", "phu_slum_2"]
    main(sys.argv[1:] or default)
