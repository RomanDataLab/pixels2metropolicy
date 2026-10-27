// Find a unique, relevant Wikimedia Commons image for each participation-technique card.
// Uses the parallel-search skill script (Commons allowlist), dedupes across cards and
// against the existing class images listed in web/img/part/SOURCES.md.
// Output: web/img/part/cards/map.json  [{ idx, cls, title, file, page }]
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SEARCH = "C:\\Users\\Real\\.zcode\\skills\\parallel-search\\scripts\\parallel_search.mjs";
const OUT_DIR = join(ROOT, "web", "img", "part", "cards");
const OUT = join(OUT_DIR, "map.json");

const CARDS = [
  { cls: 1, title: "Showcase social programming", q: ["community festival informal settlement", "social program event slum stage"] },
  { cls: 1, title: "Mandated consultation, in practice", q: ["public meeting audience hall", "town hall meeting audience"] },
  { cls: 2, title: "Design contests per settlement", q: ["architecture competition exhibition models", "design exhibition boards"] },
  { cls: 2, title: "Residents vote on proposals", q: ["community vote hands raised", "assembly voting show of hands"] },
  { cls: 2, title: "Infrastructure design workshops", q: ["community design workshop table", "participatory design workshop"] },
  { cls: 2, title: "Household compensation negotiation", q: ["contract signing negotiation table", "signing documents meeting"] },
  { cls: 2, title: "Statutory public hearings", q: ["public hearing meeting room", "public comment meeting"] },
  { cls: 2, title: "Works notice + layout vote", q: ["construction site notice board", "building site sign"] },
  { cls: 2, title: "Vendor committee consultation", q: ["street vendors meeting market", "market vendors committee"] },
  { cls: 3, title: "Resident-run house enumerations", q: ["slum enumeration survey", "household survey clipboard"] },
  { cls: 3, title: "City-wide community surveys", q: ["community survey interview", "census enumerator interview"] },
  { cls: 3, title: "Consortium plan co-writing", q: ["planning workshop documents group", "collaborative planning meeting notes"] },
  { cls: 3, title: "Women's issue campaigns", q: ["women community meeting sanitation", "women campaign water"] },
  { cls: 3, title: "Resident mapping of evacuation routes", q: ["community mapping workshop", "participatory mapping gis"] },
  { cls: 3, title: "Digital complaints with write-back", q: ["smartphone reporting city app", "mobile phone complaint city"] },
  { cls: 3, title: "District youth councils", q: ["youth council meeting", "young people forum debate"] },
  { cls: 4, title: "Participatory budgeting of project shares", q: ["participatory budgeting voting", "orcamento participativo reuniao"] },
  { cls: 4, title: "Committees co-decide works sequence", q: ["community committee meeting project", "committee construction meeting"] },
  { cls: 4, title: "Youth co-design of public space", q: ["youth design workshop city", "children urban design model"] },
  { cls: 4, title: "Associations as service providers", q: ["community association office", "ngo field workers"] },
  { cls: 4, title: "Participatory local planning rounds", q: ["participatory planning map table", "planning charrette workshop"] },
  { cls: 4, title: "Pracha-rath partnership", q: ["Thailand community volunteers", "volunteer village Thailand"] },
  { cls: 4, title: "Khlong Toei community interlocutors", q: ["Khlong Toei", "Khlong Toei community Bangkok"] },
  { cls: 4, title: "Vendor co-management of market days", q: ["Bangkok fresh market vendors", "market stall holders management"] },
  { cls: 4, title: "Co-decided relocation package", q: ["new housing keys handover", "resettlement housing project"] },
  { cls: 4, title: "Co-decided retrofit package", q: ["housing renovation volunteers", "home repair community help"] },
  { cls: 5, title: "Collective tenure + direct subsidy", q: ["land title deed handover", "land certificate ceremony"] },
  { cls: 5, title: "Community savings groups", q: ["microfinance savings group meeting", "savings group counting money"] },
  { cls: 5, title: "Collective land negotiation", q: ["land negotiation meeting", "handshake agreement meeting"] },
  { cls: 5, title: "Board seats for the poor", q: ["board meeting representatives", "council chamber meeting"] },
  { cls: 5, title: "Federation co-production", q: ["slum dweller federation meeting", "urban poor network assembly"] },
  { cls: 5, title: "Anti-eviction organizing", q: ["anti eviction protest", "housing protest march"] },
  { cls: 5, title: "Cooperative-managed common use", q: ["cooperative members workshop", "community kitchen cooking together"] },
  { cls: 6, title: "Protest as the de facto channel", q: ["slum protest demonstration", "squatter resistance eviction"] },
  { cls: 6, title: "Gang mediation", q: ["street mediation talk", "conflict resolution conversation street"] },
];

function fileTitles(md) {
  const out = [];
  const re = /commons\.wikimedia\.org\/wiki\/((?:File%3A|File:)([^\s)#?]+))/g;
  let m;
  while ((m = re.exec(md)) !== null) {
    let name = decodeURIComponent(m[2]).replace(/_/g, " ").trim();
    if (!out.includes(name)) out.push(name);
  }
  return out;
}

const used = new Set();
// never reuse the six class images
const sources = readFileSync(join(ROOT, "web", "img", "part", "SOURCES.md"), "utf8");
for (const m of sources.matchAll(/File:([^\|]+)\|/g)) used.add(m[1].trim());
for (const m of sources.matchAll(/File:(.+?) \|/g)) used.add(m[1].trim());

if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });
const map = [];
for (let i = 0; i < CARDS.length; i++) {
  const c = CARDS[i];
  const objective = `Find a Wikimedia Commons photograph depicting the participation technique "${c.title}" (participation class ${c.cls}) for a card background`;
  let md = "";
  try {
    md = execFileSync("node", [SEARCH, objective, ...c.q, "--mode", "fast", "--max-results", "8", "--include", "commons.wikimedia.org"], { encoding: "utf8", timeout: 60000 });
  } catch (e) {
    console.log(`${i + 1}/${CARDS.length} SEARCH FAIL ${c.title}: ${String(e).slice(0, 120)}`);
  }
  const titles = fileTitles(md);
  let pick = null;
  for (const t of titles) {
    if (/\.(jpg|jpeg|png)$/i.test(t) && !used.has(t)) { pick = t; break; }
  }
  if (pick) {
    used.add(pick);
    map.push({ idx: i + 1, cls: c.cls, title: c.title, file: pick, page: "https://commons.wikimedia.org/wiki/File:" + encodeURIComponent(pick.replace(/ /g, "_")) });
    console.log(`${i + 1}/${CARDS.length} OK  ${c.title} -> ${pick}`);
  } else {
    map.push({ idx: i + 1, cls: c.cls, title: c.title, file: null, page: null });
    console.log(`${i + 1}/${CARDS.length} MISS ${c.title} (candidates: ${titles.slice(0, 3).join(" ; ")})`);
  }
  writeFileSync(OUT, JSON.stringify(map, null, 1));
}
const missing = map.filter(m => !m.file).length;
console.log(`done: ${map.length - missing} found, ${missing} missing -> ${OUT}`);
