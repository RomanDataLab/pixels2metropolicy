# Wire per-card participation images: SOURCES.md attribution + uip-data.js img fields + uip-main.js bg use.
import json
import re
import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
m = json.loads((root / "web/img/part/cards/map.json").read_text(encoding="utf-8"))

# 1) SOURCES.md attribution
lines = ["", "# per-card backgrounds (35 techniques, unique per card)",
         "# all from Wikimedia Commons; search provenance in web/img/part/cards/map.json"]
for e in m:
    lines.append('cards/p%02d.jpg | File:%s | class %d · "%s" | %s' % (e["idx"], e["file"], e["cls"], e["title"], e["page"]))
p = root / "web/img/part/SOURCES.md"
p.write_text(p.read_text(encoding="utf-8").rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
print("SOURCES.md updated,", len(m), "entries")

# 2) uip-data.js: inject img per card
dp = root / "web/js/uip-data.js"
ds = dp.read_text(encoding="utf-8")
i = ds.find("PART_CARDS")
j = ds.find("];", i)
seg = ds[i:j]
count = 0
for e in m:
    title = e["title"]
    if e["idx"] == 7:
        title = "Statutory public hearings (ประชาพิจารณ์)"  # data keeps the Thai parenthetical
    pat = re.compile(r'(\{ c: %d, t: "%s", d: "(?:[^"\\]|\\.)*", tags: \[[^\]]*\])(?!, img:)' % (e["cls"], re.escape(title)))
    seg, n = pat.subn(lambda mo, idx=e["idx"]: mo.group(1) + ', img: "img/part/cards/p%02d.jpg"' % idx, seg, count=1)
    count += n
ds = ds[:i] + seg + ds[j:]
dp.write_text(ds, encoding="utf-8")
print("uip-data.js: img added to", count, "cards")
assert count == len(m), "not all cards matched"

# 3) uip-main.js: use card image with class fallback + label
mp = root / "web/js/uip-main.js"
s = mp.read_text(encoding="utf-8")
old = "d.innerHTML = '<div class=\"bg\" style=\"background-image:url(' + cl.img + ')\"></div>' +"
new = "d.innerHTML = '<div class=\"bg\" style=\"background-image:url(' + (c.img || cl.img) + ')\"></div>' +"
assert old in s, "bg anchor"
s = s.replace(old, new)
old2 = '" techniques · background: class imagery</span></div>\' +'
new2 = '" techniques · background: per-technique imagery (Wikimedia Commons)</span></div>\' +'
assert old2 in s, "label anchor"
s = s.replace(old2, new2)
mp.write_text(s, encoding="utf-8")
print("uip-main.js patched")
