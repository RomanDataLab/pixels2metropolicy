"""social-economic sensing of slums — rankings-only map.

Standalone dark-basemap page showing ONLY the five→four ranking layers as
rank-graded GPS pins (no event choropleth, no other toggles). Same data as
the Rankings panel of category_intensity_map.html (slum_rankings.csv,
code_risk.csv for the breached-norm details).

Output : 04_output/social_patterns/bangkok/rankings_map.html
Run    :  python make_rankings_map.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

from social_common import GAZETTEER_DIR, REPO, SOCIAL_OUT, ensure_dirs

RK_DEFS = [("rank", "score", "Alkire-Foster composite"),
           ("rank_danger", "danger_rate", "most-dangerous events (severity-weighted/1k)"),
           ("rank_flood", "flood_score", "flooded blocks (GISTDA flood-frequency)"),
           ("rank_code", "code_risk", "broken build-code proximity (setback proxy)")]
DESCS = {
    "rank": "Multidimensional deprivation score (Alkire-Foster method, as used by the "
            "WFP Multidimensional Deprivation Index): each of the 10 event domains counts "
            "as deprived when its rate per 1,000 residents exceeds the citywide P75 "
            "cutoff; the score is the mean of the 10 domain scores. Higher = more domains "
            "affected, more intensely. Communities with pop&lt;100 are unranked.",
    "rank_danger": "Events per 1,000 residents weighted by domain severity: fire 1.0, "
                   "flooding/crime 0.9, accidents 0.8, contamination/tenure 0.6, "
                   "services 0.5, destitution 0.4, informal economy 0.2, support 0.1.",
    "rank_flood": "Share of sampled community points that fall inside GISTDA "
                  "repeated-flood areas, multiplied by mean flood intensity "
                  "(flood_score from the Vallaris flood-frequency layer).",
    "rank_code": "Weighted count of legal setback bands the community touches: "
                 "water 6 m, railway 30 m, road 6 m, industrial 100 m. "
                 "Click a pin for the exact norms breached.",
}
NORMS = [("water", "public waterway", 6.0,
          "Ministerial Regulation No. 55 (B.E. 2543) ข้อ 40: 3-6 m bank setback"),
         ("rail", "railway", 30.0,
          "Rail Transport Act practice: 30 m from track centreline"),
         ("highway", "public road", 6.0,
          "Ministerial Regulation No. 55 (B.E. 2543) ข้อ 41: 2-6 m setback by road width"),
         ("industrial", "industrial zone", 100.0,
          "comprehensive-plan nuisance buffer (policy proxy, not law)")]


def main() -> int:
    ensure_dirs()
    rk = pd.read_csv(SOCIAL_OUT / "slum_rankings.csv", dtype={"cmt_id": str}).fillna("")
    cr = pd.read_csv(SOCIAL_OUT / "code_risk.csv", dtype={"cmt_id": str})
    cr = cr[~cr["cmt_id"].duplicated()].set_index("cmt_id")

    poly = gpd.read_parquet(GAZETTEER_DIR / "slum_polygons.parquet")
    poly["cmt_id"] = poly["CMT_ID"].astype(str)
    poly = poly.to_crs(32647)
    ctr = poly.geometry.representative_point().to_crs(4326)
    xy = {c: (p.y, p.x) for c, p in zip(poly["cmt_id"], ctr)}

    def code_vlist(cid: str) -> list[str]:
        if cid not in cr.index:
            return []
        row = cr.loc[cid]
        return [f"{name}: boundary {float(row[f'dist_{src}']):.0f} m away vs "
                f"{thr:.0f} m allowed — {law}"
                for src, name, thr, law in NORMS if int(row[f"viol_{src}"]) == 1]

    rank_sets = {}
    for rk_col, v_col, label in RK_DEFS:
        rows = rk[rk[rk_col] > 0].sort_values(rk_col).head(30)
        items = []
        for _, r in rows.iterrows():
            cid = str(r["cmt_id"])
            if cid not in xy:
                continue
            it = {"rank": int(r[rk_col]), "id": cid,
                  "th": str(r["CMT_NAME"])[:34], "en": str(r.get("name_en", ""))[:44],
                  "sname": str(r["SNAME"]), "dname": str(r["DNAME"]),
                  "lat": xy[cid][0], "lon": xy[cid][1],
                  "v": round(float(r[v_col]), 2)}
            if rk_col == "rank_code":
                it["vlist"] = code_vlist(cid)
            items.append(it)
        rank_sets[rk_col] = {"label": label, "desc": DESCS[rk_col], "items": items}
    print("ranking sizes:", {k: len(v["items"]) for k, v in rank_sets.items()})

    html = (HTML
            .replace("__RANKSETS__", json.dumps(rank_sets, ensure_ascii=False))
            .replace("__TITLE__", "social-economic sensing of irregular neighborhoods — rankings"))
    (SOCIAL_OUT / "rankings_map.html").write_text(html, encoding="utf-8")
    print(f"output: {SOCIAL_OUT}\\rankings_map.html")
    return 0


HTML = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  body{margin:0;font-family:sans-serif;background:#0d1216}
  #map{position:absolute;top:0;bottom:0;right:0;left:0}
  .panel{position:absolute;top:10px;right:10px;z-index:1000;background:rgba(13,18,22,0.88);
         color:#cfd8dd;padding:10px 14px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.5);
         max-width:320px;max-height:92vh;overflow-y:auto}
  h1{font-size:15px;margin:0 0 8px;color:#fff}
  .panel label{display:block;font-size:13px;margin-top:3px;cursor:pointer}
  .note{font-size:11px;color:#8a979e;margin-top:6px}
  #rankdesc{display:none;margin-top:6px;border-top:1px solid #33424a;padding-top:5px;
            color:#b9c6cc;line-height:1.4;font-size:12px}
  .scale{margin-top:8px;border-top:1px solid #33424a;padding-top:6px;font-size:12px}
</style>
</head>
<body>
<div id="map"></div>
<div class="panel">
  <h1>rankings — top 30 irregular neighborhoods (ชุมชนแออัด)</h1>
  <div id="rankopts"></div>
  <div id="rankdesc"></div>
  <div class="scale" id="scale"></div>
  <div class="note">Pin color = rank: #1 darkest red &rarr; #30 lightest.
  Click a pin for name and value. 92-day sensing window.</div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const RANKSETS = __RANKSETS__;
const BKK = L.latLngBounds([13.47, 100.28], [14.02, 100.98]);
const map = L.map('map', {zoomControl: true}).fitBounds(BKK, {animate: false});
(function refit(){
  if (map.getZoom() >= 9) return;
  map.invalidateSize(); map.fitBounds(BKK, {animate: false});
  setTimeout(refit, 400);
})();
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
  {maxZoom: 19, maxNativeZoom: 16, attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ'}).addTo(map);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
  {maxZoom: 19, maxNativeZoom: 16, opacity: 0.8, attribution: ''}).addTo(map);

let pinLayer = null;
function pinColor(rank){
  const t = Math.min(1, (rank - 1) / 29);
  return `hsl(8,78%,${Math.round(22 + 40 * t)}%)`;   // rank 1 dark red -> rank 30 light
}
function showRank(key){
  if (pinLayer) { map.removeLayer(pinLayer); pinLayer = null; }
  const set = RANKSETS[key];
  pinLayer = L.layerGroup(set.items.map(it => {
    const col = pinColor(it.rank);
    const icon = L.divIcon({className: '', iconSize: [30, 43], iconAnchor: [15, 43], popupAnchor: [0, -40],
      html: `<svg width="30" height="43" viewBox="0 0 30 43">` +
            `<path d="M15 42 C 10 33 4 22 4 13 a11 11 0 1 1 22 0 C 26 22 20 33 15 42 Z"` +
            ` fill="${col}" stroke="#fff" stroke-width="1.5"/>` +
            `<circle cx="15" cy="13" r="6.5" fill="#fff"/>` +
            `<text x="15" y="16.8" text-anchor="middle" font-family="sans-serif"` +
            ` font-weight="700" font-size="10" fill="${col}">${it.rank}</text></svg>`});
    return L.marker([it.lat, it.lon], {icon}).bindPopup(
      `<b>#${it.rank} · ${it.en}</b>` +
      `<div style="color:#0a5f73;font-size:11px">${it.th}</div>` +
      `${it.sname} · ${it.dname}<br>` +
      `${set.label}: <b>${it.v}</b>` +
      (it.vlist && it.vlist.length
        ? `<div style="margin-top:4px;text-align:left"><b>norms breached:</b>` +
          it.vlist.map(v => `<div style="margin-top:2px">&bull; ${v}</div>`).join('') +
          `<div style="margin-top:3px;color:#666">community-level proxy — not per-building compliance</div></div>`
        : ''));
  })).addTo(map);
  map.fitBounds(L.latLngBounds(set.items.map(it => [it.lat, it.lon])).pad(0.15));
}
const box = document.getElementById('rankopts');
Object.entries(RANKSETS).forEach(([key, set], i) => {
  const l = document.createElement('label');
  const r = document.createElement('input'); r.type = 'radio'; r.name = 'rankset'; r.value = key;
  if (i === 0) r.checked = true;
  const t = document.createElement('span'); t.textContent = ' ' + set.label;
  l.append(r, t); box.appendChild(l);
  r.onchange = () => {
    showRank(key);
    const d = document.getElementById('rankdesc');
    d.innerHTML = `<b>${set.label}</b> — ${set.desc}`;
    d.style.display = 'block';
  };
});
(function boot(){                      // default selection on load
  const first = document.querySelector('input[name=rankset]');
  if (!first) return;
  first.dispatchEvent(new Event('change'));
  if (pinLayer) return;
  setTimeout(boot, 300);
})();
document.getElementById('scale').innerHTML =
  '<b>color scale</b><br>' +
  Array.from({length: 30}, (_, i) =>
    `<i style="display:inline-block;width:8px;height:10px;margin-right:1px;background:${pinColor(i + 1)}"></i>`).join('') +
  '<br>#1 &mdash; #30';
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
