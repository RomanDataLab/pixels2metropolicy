#!/usr/bin/env python3
"""Prepare compact data files for the Urban Intelligence Platform landing.

Reads repo-wide source layers and writes trimmed JSON into web/data/.
Run from anywhere: paths resolve relative to the repo layout below.
"""
import json, math, os, re, pathlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
QGIS = os.path.join(REPO, "labeling", "qgis_project")
DEPLOY = os.path.join(REPO, "05_scratch", "deploy_site", "data")
OUT = os.path.join(HERE, "web", "data")

os.makedirs(OUT, exist_ok=True)


def r5(x):
    return round(x, 5)


def round_geom(g, nd=5):
    if isinstance(g, dict):
        if g.get("coordinates") is None:
            return None
        g = g["coordinates"]
    if g is None or len(g) == 0:
        return None
    if isinstance(g[0], (int, float)):
        return [r5(g[0]), r5(g[1])]
    return [round_geom(x, nd) for x in g]


def write(name, obj):
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print(name, os.path.getsize(p) // 1024, "KB")


def centroid(g):
    """Rough centroid: average of flattened coords."""
    pts = []

    def flat(x):
        if isinstance(x[0], (int, float)):
            pts.append(x)
        else:
            for i in x:
                flat(i)

    flat(g["coordinates"] if "coordinates" in g else g)
    n = len(pts)
    return [r5(sum(p[0] for p in pts) / n), r5(sum(p[1] for p in pts) / n)]


def bbox(g):
    xs, ys = [], []

    def flat(x):
        if isinstance(x[0], (int, float)):
            xs.append(x[0]); ys.append(x[1])
        else:
            for i in x:
                flat(i)

    flat(g["coordinates"] if "coordinates" in g else g)
    return [min(xs), min(ys), max(xs), max(ys)]


# ---------------------------------------------------------------- khet
khet = json.load(open(os.path.join(QGIS, "bkk_khet_wgs84.geojson"), encoding="utf-8"))
feats = []
for ft in khet["features"]:
    g = round_geom(ft["geometry"])
    if g is None:
        continue
    # normalize to MultiPolygon coordinates ([polygon][ring][pt])
    if ft["geometry"]["type"] == "Polygon":
        g = [g]
    feats.append({
        "n": ft["properties"].get("shapeName", ""),
        "g": g,
    })
write("uip-khet.json", {"type": "fc", "features": feats})

# ---------------------------------------------------------------- zones (regular properties)
z = json.load(open(os.path.join(DEPLOY, "plan_zones.geojson"), encoding="utf-8"))
feats = []
for ft in z["features"]:
    p = ft["properties"]
    g = round_geom(ft["geometry"])
    if g is None:
        continue
    feats.append({
        "u": p.get("use", ""), "c": p.get("cat_en", ""), "z": p.get("zone", ""),
        "g": g,
    })
write("uip-zones.json", {"type": "fc", "features": feats})

# ---------------------------------------------------------------- roofs: pick 3 cluster sites
roofs = json.load(open(os.path.join(QGIS, "slum_roofs_red_v8.geojson"), encoding="utf-8"))
# bucket features by 0.02-degree cell, keep the 3 densest cells
cells = {}
for ft in roofs["features"]:
    c = centroid(ft["geometry"])
    key = (round(c[0] / .02), round(c[1] / .02))
    cells.setdefault(key, []).append((c, ft))
top = sorted(cells.items(), key=lambda kv: -len(kv[1]))[:3]
SITE_NAMES = ["SITE A", "SITE B", "SITE C"]
sites = []
for (key, items), name in zip(top, SITE_NAMES):
    cx = sum(i[0][0] for i in items) / len(items)
    cy = sum(i[0][1] for i in items) / len(items)
    fs = []
    for c, ft in items:
        p = ft["properties"]
        g = round_geom(ft["geometry"])
        if g is None:
            continue
        fs.append({
            "a": p.get("area_m2"),
            "n": p.get("nb_20"),
            "d": p.get("nn_m"),
            "cf": p.get("confidence"),
            "g": g,
        })
    sites.append({"name": name, "c": [r5(cx), r5(cy)], "n": len(fs), "features": fs})
    print("site", name, len(fs), "buildings")
write("uip-roofs.json", {"type": "sites", "sites": sites})

# ---------------------------------------------------------------- hulls (highlighted blobs)
hulls = {"type": "fc", "features": []}
for fn, meth in (("blobcompare_A_hulls.geojson", "hull"), ("blobcompare_B_raster10.geojson", "raster10"), ("blobcompare_C_fill5.geojson", "fill5")):
    d = json.load(open(os.path.join(QGIS, fn), encoding="utf-8"))
    for ft in d["features"]:
        p = ft["properties"]
        g = round_geom(ft["geometry"])
        if g is None:
            continue
        hulls["features"].append({
            "m": meth,
            "b": p.get("buildings"), "dha": p.get("density_ha"), "oc": p.get("orient_conc"),
            "scv": p.get("size_cv"), "cm": p.get("canal_med_m"), "cs": p.get("canal_150m_share"),
            "ok": p.get("accepted"),
            "g": g,
        })
write("uip-hulls.json", hulls)

# ---------------------------------------------------------------- social: community polygons + category counts
soc_html = pathlib.Path(os.path.join(REPO, "social.html")).read_text(encoding="utf-8", errors="replace")
i = soc_html.find('"type": "FeatureCollection"')
j = soc_html.find('"type": "FeatureCollection"')
start = soc_html.rfind('{', 0, j) if j >= 0 else -1
# more robust: locate the KH-like assignment or first FeatureCollection literal
m = re.search(r'=\s*(\{"type":\s*"FeatureCollection".*?\}\s*)\s*[;<]', soc_html, re.S)
if not m:
    # try decode-brace scan from first {
    s = start if start >= 0 else soc_html.find('{"type": "FeatureCollection"')
    depth = 0; end = None
    for k in range(s, len(soc_html)):
        ch = soc_html[k]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = k + 1; break
    fc = json.loads(soc_html[s:end])
else:
    fc = json.loads(m.group(1))
feats = []
for ft in fc["features"]:
    p = ft["properties"]
    c = p.get("counts", {}) or {}
    feats.append({
        "nm": p.get("sname", ""), "dn": p.get("dname", ""), "pop": p.get("pop"),
        "tot": p.get("total", 0), "nd": p.get("n_docs", 0),
        "nd_": c.get("natural_disaster", 0), "td_": c.get("technical_disaster", 0),
        "ti": c.get("traffic_incident", 0), "cr": c.get("crime", 0),
        "sr": c.get("street_retail_popup", 0), "bh": c.get("begging_homeless", 0),
        "c": centroid(ft["geometry"]),
        "bb": bbox(ft["geometry"]),
    })
print("social communities:", len(feats))
write("uip-social.json", {"type": "pts", "features": feats})

# ---------------------------------------------------------------- nha communities
njs = pathlib.Path(os.path.join(DEPLOY, "nha_communities.js")).read_text(encoding="utf-8", errors="replace")
i = njs.find(".nha_communities=")
s = njs.index("{", i)
depth = 0
end = s
for k in range(s, len(njs)):
    ch = njs[k]
    if ch == '{':
        depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0:
            end = k
            break
nha = json.loads(njs[s:end + 1])
feats = []
for ft in nha["features"]:
    p = ft["properties"]
    g = ft["geometry"]
    c = g["coordinates"] if g["type"] == "Point" else centroid(g)
    feats.append({
        "nm": p.get("NAME_EN") or "", "th": p.get("COMM_NAME") or "",
        "hh": p.get("EST_HH"), "pop": p.get("EST_POP"),
        "yr": p.get("SHAPE_YEAR"),
        "c": [r5(c[0]), r5(c[1])],
    })
print("nha communities:", len(feats))
write("uip-nha.json", {"type": "pts", "features": feats})

print("done")
