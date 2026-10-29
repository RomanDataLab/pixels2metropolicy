"""social-economic sensing of slums — combined priorities map.

Standalone dark-basemap page combining the FOUR rankings of
rankings_map.html (Alkire-Foster deprivation, dangerous events, flood,
build-code) into one priority score = mean of the four rank positions
(a community unranked on a layer counts as one past that layer's last
rank). Top 30 combined get rank-graded pins with a 3-ring pulse on
hover; a click opens the full neighborhood profile (component
standings, main dangerous events, breached norms).

Output : 04_output/social_patterns/bangkok/prioritiesmap.html
Run    :  python make_priorities_map.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

from social_common import GAZETTEER_DIR, REPO, SOCIAL_OUT, ensure_dirs

RK_DEFS = [("rank", "score", "deprivation (Alkire-Foster)"),
           ("rank_danger", "danger_rate", "dangerous events"),
           ("rank_flood", "flood_score", "flood exposure"),
           ("rank_code", "code_risk", "build-code risk")]
DESC = ("Combined priority = mean position across the four rankings below. "
        "A community unranked on a layer (pop&lt;100 or no data) counts as one "
        "past that layer's last rank, so gaps push it down. Lower mean = "
        "higher priority. Click a pin for the full profile.")
# popup "main problems": domains ordered by the severity weights of
# rank_danger (fire 1.0, flooding/crime 0.9, accidents 0.8, contamination/
# tenure 0.6, services 0.5, destitution 0.4, informal economy 0.2, support
# 0.1); env_hazard sits with the 0.8 band (industrial/pollution hazard).
EV_ORDER = [("fire", "Fire"),
            ("flooding", "Flooding"),
            ("crime_security", "Crime & security"),
            ("env_hazard", "Environmental hazard"),
            ("contamination", "Contamination"),
            ("housing_tenure_risk", "Housing / tenure risk"),
            ("basic_services", "Basic services"),
            ("destitution", "Destitution"),
            ("informal_economy", "Informal economy"),
            ("social_support", "Social support")]
NORMS = [("water", "public waterway", 6.0,
          "Ministerial Regulation No. 55 (B.E. 2543) ข้อ 40: 3-6 m bank setback"),
         ("rail", "railway", 30.0,
          "Rail Transport Act practice: 30 m from track centreline"),
         ("highway", "public road", 6.0,
          "Ministerial Regulation No. 55 (B.E. 2543) ข้อ 41: 2-6 m setback by road width"),
         ("industrial", "industrial zone", 100.0,
          "comprehensive-plan nuisance buffer (policy proxy, not law)")]


def _num(x, nd: int = 2) -> float:
    """csv cell to float; '' or NaN to 0."""
    v = pd.to_numeric(x, errors="coerce")
    return round(float(v), nd) if pd.notna(v) else 0.0


def main() -> int:
    ensure_dirs()
    rk = pd.read_csv(SOCIAL_OUT / "slum_rankings.csv", dtype={"cmt_id": str}).fillna("")
    cr = pd.read_csv(SOCIAL_OUT / "code_risk.csv", dtype={"cmt_id": str})
    cr = cr[~cr["cmt_id"].duplicated()].set_index("cmt_id")
    cc = pd.read_csv(SOCIAL_OUT / "neighborhood_category_counts.csv",
                     dtype={"cmt_id": str}).set_index("cmt_id")

    def main_events(cid: str) -> list[dict]:
        """Non-zero event domains, most dangerous first (severity order)."""
        if cid not in cc.index:
            return []
        row = cc.loc[cid]
        return [{"d": label, "n": int(row[col])}
                for col, label in EV_ORDER if int(row[col]) > 0]

    poly = gpd.read_parquet(GAZETTEER_DIR / "slum_polygons.parquet")
    poly["cmt_id"] = poly["CMT_ID"].astype(str)
    ctr = poly.to_crs(32647).geometry.representative_point().to_crs(4326)
    xy = {c: (p.y, p.x) for c, p in zip(poly["cmt_id"], ctr)}

    def _round5(c):
        if isinstance(c[0], (int, float)):
            return [round(c[0], 5), round(c[1], 5)]
        return [_round5(x) for x in c]

    feats = []
    for cid, geom in zip(poly["cmt_id"], poly.geometry.to_crs(4326)):
        if geom is None or geom.is_empty:
            continue
        gj = json.loads(json.dumps(geom.__geo_interface__))
        if gj.get("coordinates"):
            gj["coordinates"] = _round5(gj["coordinates"])
        feats.append({"type": "Feature", "id": cid, "geometry": gj})
    polys_geojson = {"type": "FeatureCollection", "features": feats}
    print("community outlines:", len(feats))

    def code_vlist(cid: str) -> list[str]:
        if cid not in cr.index:
            return []
        row = cr.loc[cid]
        return [f"{name}: boundary {float(row[f'dist_{src}']):.0f} m away vs "
                f"{thr:.0f} m allowed — {law}"
                for src, name, thr, law in NORMS if int(row[f"viol_{src}"]) == 1]

    # ---- combined ranking: mean of the four rank positions ---------------
    rk = rk.set_index("cmt_id")
    n_ranked = {c: int(pd.to_numeric(rk[c], errors="coerce").fillna(0).max()) for c, _, _ in RK_DEFS}
    eff = pd.DataFrame({c: pd.to_numeric(rk[c], errors="coerce").fillna(0) for c, _, _ in RK_DEFS})
    eff = eff.where(eff > 0, pd.Series({c: n_ranked[c] + 1 for c in eff.columns}), axis=1)
    avg = eff.mean(axis=1)
    any_ranked = pd.concat([pd.to_numeric(rk[c], errors="coerce").fillna(0) for c, _, _ in RK_DEFS], axis=1).max(axis=1) > 0
    items = []
    for crank, (cid, cavg) in enumerate(avg[any_ranked].sort_values().head(30).items(), 1):
        r = rk.loc[cid]
        comps = [{"l": label, "r": int(_num(r[rkc], 0)),
                  "v": _num(r[vc])}
                 for rkc, vc, label in RK_DEFS]
        evs = main_events(cid)
        items.append({"rank": crank, "id": cid,
                      "th": str(r["CMT_NAME"])[:34], "en": str(r.get("name_en", ""))[:44],
                      "sname": str(r["SNAME"]), "dname": str(r["DNAME"]),
                      "pop": int(_num(r["pop"], 0)),
                      "lat": xy[cid][0], "lon": xy[cid][1],
                      "avg": round(float(cavg), 1),
                      "comps": comps, "ev": evs, "ev_more": 0,
                      "total": int(cc.loc[cid, "total"]) if cid in cc.index else 0,
                      "vlist": code_vlist(cid)})
    print("combined top-30:", len(items), "| layers ranked:", n_ranked)

    html = (HTML
            .replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
            .replace("__POLYS__", json.dumps(polys_geojson, ensure_ascii=False, separators=(",", ":")))
            .replace("__DESC__", DESC)
            .replace("__TITLE__", "combined priorities — top 30 irregular neighborhoods"))
    (SOCIAL_OUT / "prioritiesmap.html").write_text(html, encoding="utf-8")
    print(f"output: {SOCIAL_OUT}\\prioritiesmap.html")
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
  .panel{position:absolute;top:10px;right:10px;z-index:1000;background:rgba(13,18,22,0.9);
         color:#cfd8dd;padding:10px 14px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.5);
         max-width:330px;max-height:92vh;overflow-y:auto}
  h1{font-size:15px;margin:0 0 8px;color:#fff}
  .phead{display:flex;align-items:flex-start;gap:8px}
  .phead h1{flex:1;margin:0}
  #rollbtn{flex:none;background:none;border:1px solid #33424a;color:#cfd8dd;border-radius:4px;
           width:22px;height:22px;line-height:1;font-size:15px;cursor:pointer;padding:0}
  #rollbtn:hover{background:#1d262c;color:#fff}
  .note{font-size:11px;color:#8a979e;margin-top:6px}
  .scale{margin-top:8px;border-top:1px solid #33424a;padding-top:6px;font-size:12px}
  /* 5 pulsating rings, spreading out on pin hover: center ring thinnest,
     each outer ring +30% border width (x1.3) and +20% more transparent */
  .pulse-wrap{position:relative}
  .pulse{position:absolute;left:50%;top:50%;width:65px;height:65px;margin:-32.5px 0 0 -32.5px;
         border-radius:50%;border:2.25px solid #ff5a4e;opacity:0;pointer-events:none;
         animation:ripple 1.8s cubic-bezier(.2,.55,.45,1) infinite}
  @keyframes ripple{0%{transform:scale(.06);opacity:var(--omax,1)}
                    70%{opacity:calc(var(--omax,1)*.4)}
                    100%{transform:scale(1);opacity:0}}
  /* click profile */
  #info{display:none;margin-top:8px;border-top:1px solid #33424a;padding-top:6px;font-size:12px;line-height:1.45}
  #info .nm{font-size:14px;font-weight:700;color:#fff}
  #info .th{color:#7fb7c4;font-size:11.5px;margin-bottom:2px}
  #info .loc{color:#8a979e;font-size:11px;margin-bottom:6px}
  #info .close{float:right;cursor:pointer;color:#8a979e;font-weight:700;padding:0 2px}
  #info .close:hover{color:#fff}
  .chips{display:flex;flex-wrap:wrap;gap:4px;margin:5px 0}
  .chip{border:1px solid #33424a;border-radius:4px;padding:2px 5px;font-size:11px;color:#cfd8dd;
        background:rgba(255,255,255,.03)}
  .chip b{color:#fff}
  .chip.hot{border-color:#a33;background:rgba(170,50,50,.18)}
  #info h4{margin:8px 0 3px;font-size:11px;color:#93a3ad;text-transform:uppercase;letter-spacing:.06em}
  #info ul{margin:2px 0;padding-left:16px}
  #info li{margin:1px 0}
  .muted{color:#666}
</style>
</head>
<body>
<div id="map"></div>
<div class="panel">
  <div class="phead">
    <h1>combined priorities — top 30 irregular neighborhoods (ชุมชนแออัด)</h1>
    <button id="rollbtn" title="roll up">&minus;</button>
  </div>
  <div id="pbody">
  <div id="rankdesc">__DESC__</div>
  <div class="scale" id="scale"></div>
  <div class="note">Pin color = combined rank: #1 darkest red &rarr; #30 lightest.
  Hover a pin: pulse rings. Click a pin: full neighborhood profile &mdash; main problems included.
  92-day sensing window.<br>
  Outlines = irregular neighborhoods: colored = combined top 30, white = rest (50% transparent).</div>
  <div id="info"></div>
  </div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const ITEMS = __ITEMS__;
const POLYS = __POLYS__;
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

function pinColor(rank){
  const t = Math.min(1, (rank - 1) / 29);
  return `hsl(8,78%,${Math.round(22 + 40 * t)}%)`;   // rank 1 dark red -> rank 30 light
}
const byId = Object.fromEntries(ITEMS.map(it => [it.id, it]));
const polyLayer = L.geoJSON(POLYS, {
  style: f => byId[f.id] !== undefined
    ? {color: pinColor(byId[f.id].rank), weight: 1.5, opacity: 0.5, fill: false}
    : {color: '#fff', weight: 1.5, opacity: 0.5, fill: false},
  interactive: false
}).addTo(map);

/* ---- pins: hover = 3 pulsating rings, click = full profile ---------- */
let pulseMk = null, selId = null;
function pulseOn(it, col){
  pulseOff();
  let html = '<div class="pulse-wrap">';
  for (let i = 0; i < 5; i++) {           // ring 0 = innermost: thinnest, most opaque
    html += `<div class="pulse" style="border-color:${col};` +
            `border-width:${(2.25 * Math.pow(1.3, i)).toFixed(2)}px;` +
            `--omax:${Math.max(0, 1 - 0.2 * i).toFixed(2)};` +
            `animation-delay:${(i * 0.36).toFixed(2)}s"></div>`;
  }
  html += '</div>';
  pulseMk = L.marker([it.lat, it.lon], {interactive: false, zIndexOffset: -500,
    icon: L.divIcon({className: '', iconSize: [0, 0], html})}).addTo(map);
}
function pulseOff(){ if (pulseMk) { map.removeLayer(pulseMk); pulseMk = null; } }

const info = document.getElementById('info');
function showInfo(it){
  selId = it.id;
  const comps = it.comps.map(c =>
    `<span class="chip${c.r > 0 && c.r <= 10 ? ' hot' : ''}" title="rank on this layer">` +
    `${c.l}: <b>${c.r > 0 ? '#' + c.r : 'unranked'}</b> · ${c.v}</span>`).join('');
  const evs = it.ev.length
    ? `<h4>main dangerous events (severity order)</h4><ul>` +
      it.ev.map(e => `<li>${e.d}: <b>${e.n}</b></li>`).join('') + `</ul>` +
      `<div class="muted">total events (92 days): ${it.total}</div>`
    : `<h4>main dangerous events</h4><div class="muted">no events in the 92-day window</div>`;
  const norms = it.vlist && it.vlist.length
    ? `<h4>build-code norms breached</h4><ul>` +
      it.vlist.map(v => `<li>${v}</li>`).join('') + `</ul>` +
      `<div class="muted">community-level proxy — not per-building compliance</div>`
    : `<h4>build-code norms breached</h4><div class="muted">none detected</div>`;
  info.innerHTML =
    `<span class="close" title="close">&times;</span>` +
    `<div class="nm">#${it.rank} · ${it.en}</div>` +
    `<div class="th">${it.th}</div>` +
    `<div class="loc">${it.sname} · ${it.dname} · pop ${it.pop.toLocaleString()}</div>` +
    `<div>combined priority <b>#${it.rank}</b> — mean rank <b>${it.avg}</b> across the 4 rankings</div>` +
    `<div class="chips">${comps}</div>` +
    evs + norms;
  info.style.display = 'block';
  info.querySelector('.close').onclick = clearSel;
  // highlight the community outline while selected
  polyLayer.setStyle(f => {
    if (f.id === selId) return {color: pinColor(it.rank), weight: 3, opacity: 1,
                                fill: true, fillColor: pinColor(it.rank), fillOpacity: 0.18};
    return byId[f.id] !== undefined
      ? {color: pinColor(byId[f.id].rank), weight: 1.5, opacity: 0.5, fill: false}
      : {color: '#fff', weight: 1.5, opacity: 0.5, fill: false};
  });
}
function clearSel(){
  selId = null;
  info.style.display = 'none';
  polyLayer.setStyle(f => byId[f.id] !== undefined
    ? {color: pinColor(byId[f.id].rank), weight: 1.5, opacity: 0.5, fill: false}
    : {color: '#fff', weight: 1.5, opacity: 0.5, fill: false});
}
map.on('click', clearSel);

ITEMS.forEach(it => {
  const col = pinColor(it.rank);
  const icon = L.divIcon({className: '', iconSize: [30, 43], iconAnchor: [15, 43], popupAnchor: [0, -40],
    html: `<svg width="30" height="43" viewBox="0 0 30 43">` +
          `<path d="M15 42 C 10 33 4 22 4 13 a11 11 0 1 1 22 0 C 26 22 20 33 15 42 Z"` +
          ` fill="${col}" stroke="#fff" stroke-width="1.5"/>` +
          `<circle cx="15" cy="13" r="6.5" fill="#fff"/>` +
          `<text x="15" y="16.8" text-anchor="middle" font-family="sans-serif"` +
          ` font-weight="700" font-size="10" fill="${col}">${it.rank}</text></svg>`});
  const mk = L.marker([it.lat, it.lon], {icon}).addTo(map);
  mk.on('mouseover', () => pulseOn(it, col));
  mk.on('mouseout', pulseOff);
  mk.on('click', e => { L.DomEvent.stopPropagation(e); pulseOff(); showInfo(it); });
});

document.getElementById('scale').innerHTML =
  '<b>color scale</b><br>' +
  Array.from({length: 30}, (_, i) =>
    `<i style="display:inline-block;width:8px;height:10px;margin-right:1px;background:${pinColor(i + 1)}"></i>`).join('') +
  '<br>#1 &mdash; #30';
map.fitBounds(L.latLngBounds(ITEMS.map(it => [it.lat, it.lon])).pad(0.15));

/* legend roll up / down */
const pbody = document.getElementById('pbody');
const roll = document.getElementById('rollbtn');
let panelOpen = true;
roll.onclick = () => {
  panelOpen = !panelOpen;
  pbody.style.display = panelOpen ? '' : 'none';
  roll.textContent = panelOpen ? '\\u2212' : '+';
  roll.title = panelOpen ? 'roll up' : 'roll down';
};
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
