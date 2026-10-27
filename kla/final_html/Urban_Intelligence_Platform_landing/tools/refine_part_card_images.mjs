// Refine weak card-image picks with direct Wikimedia Commons file-namespace search.
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const MAP = join(ROOT, "web", "img", "part", "cards", "map.json");

// idx -> better search terms (file namespace)
const REPLACE = {
  3: ["architectural models exhibition", "architecture student model exhibition"],
  11: ["door to door survey interview", "household interview survey"],
  14: ["community mapping workshop", "participatory mapping community"],
  17: ["participatory budgeting", "orcamento participativo"],
  21: ["urban planning workshop", "planning workshop city model"],
  27: ["land title ceremony", "certificate handover ceremony"],
  32: ["housing protest", "affordable housing demonstration"],
  35: ["mediation meeting community", "peace dialogue community"],
};

const map = JSON.parse(readFileSync(MAP, "utf8"));
const used = new Set(map.filter(m => m.file).map(m => m.file));
// also exclude class images
const src = readFileSync(join(ROOT, "web", "img", "part", "SOURCES.md"), "utf8");
for (const m of src.matchAll(/File:(.+?) \|/g)) used.add(m[1].trim());

async function commonsSearch(term) {
  const url = "https://commons.wikimedia.org/w/api.php?action=query&format=json&list=search&srnamespace=6&srlimit=12&srsearch=" + encodeURIComponent(term);
  const r = await fetch(url, { headers: { "User-Agent": "Pixels2MetroPolicy-card-images/1.0" } });
  const j = await r.json();
  return (j.query?.search || []).map(s => s.title.replace(/^File:/, ""));
}

for (const entry of map) {
  if (!REPLACE[entry.idx]) continue;
  let pick = null;
  for (const term of REPLACE[entry.idx]) {
    const titles = await commonsSearch(term);
    for (const t of titles) {
      if (!/\.(jpe?g|png)$/i.test(t)) continue;
      if (/(logo|icon|map of|diagram|chart|svg|blank|flag of)/i.test(t)) continue;
      if (!used.has(t)) { pick = { t, term }; break; }
    }
    if (pick) break;
  }
  if (pick) {
    used.delete(entry.file);
    used.add(pick.t);
    entry.file = pick.t;
    entry.page = "https://commons.wikimedia.org/wiki/File:" + encodeURIComponent(pick.t.replace(/ /g, "_"));
    console.log(`#${entry.idx} ${entry.title} -> ${pick.t}   [${pick.term}]`);
  } else {
    console.log(`#${entry.idx} ${entry.title} -> KEEP (no better hit)`);
  }
  writeFileSync(MAP, JSON.stringify(map, null, 1));
}
console.log("refine done");
