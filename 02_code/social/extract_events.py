"""slum_pulse step 7 — Thai NLP event extraction + gazetteer geolocation.

Open-source only: pythainlp tokenization (word-cut so keyword hits respect word
boundaries where possible), exact gazetteer variant matching, lexicon
classification from event_lexicon.yaml.

Inputs : news_articles.jsonl, telegram_messages.jsonl, pantip_threads.jsonl
Output : 01_data/02_raw_imports/social/events.parquet

Tier logic per document:
  T1 slum_name variant matched AND that slum's khwaeng/district also in text  (conf 0.9)
  T2 slum_name variant matched alone (ambiguous name -> conf 0.5 else 0.7)
  T3 no slum name, but khwaeng name matched                                  (conf 0.4, cmt_id empty)
  T4 only landmark matched                                                   (conf 0.3)

Run:  python extract_events.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import pandas as pd
import yaml
from pythainlp.tokenize import word_tokenize

from pathlib import Path

from social_common import GAZETTEER_DIR, SOCIAL_RAW, ensure_dirs, read_jsonl

LEXICON_PATH = Path(__file__).resolve().parent / "event_lexicon.yaml"


def classify(text: str, lex: dict) -> tuple[str | None, list[str]]:
    matched = []
    for cat, kws in lex["categories"].items():
        if any(kw in text for kw in kws):
            matched.append(cat)
    if not matched:
        return None, []
    for cat in lex["priority"]:
        if cat in matched:
            return cat, matched
    return matched[0], matched


def main() -> int:
    ensure_dirs()
    lex = yaml.safe_load(open(LEXICON_PATH, encoding="utf-8"))

    gz = pd.read_csv(GAZETTEER_DIR / "slum_gazetteer.csv", dtype=str)
    # variant -> {kind, ambiguous, cmt_ids, sname, dname}
    vmap: dict[str, dict] = {}
    for v in gz.itertuples():
        e = vmap.setdefault(v.variant, {"kind": v.kind, "ambiguous": v.ambiguous == "True",
                                        "cmt_ids": set(), "sname": set(), "dname": set()})
        if v.cmt_id and v.cmt_id != "nan":
            e["cmt_ids"].add(v.cmt_id)
        e["sname"].add(v.sname)
        e["dname"].add(v.dname)
    print(f"gazetteer variants: {len(vmap)}")

    docs: list[dict] = []
    for fname, src in (("news_articles.jsonl", "news"),
                       ("telegram_messages.jsonl", "telegram"),
                       ("pantip_threads.jsonl", "pantip")):
        rows = read_jsonl(SOCIAL_RAW / fname)
        for r in rows:
            text = " ".join(x for x in (r.get("title"), r.get("snippet"), r.get("text")) if x)
            if len(text.strip()) < 10:
                continue
            docs.append({
                "doc_id": r.get("item_id") or r.get("topic_id") or r.get("msg_ref") or str(len(docs)),
                "source": src,
                "publisher": r.get("publisher") or r.get("channel") or src,
                "url": r.get("url"),
                "pubdate": r.get("pubdate") or r.get("ts"),
                "title": r.get("title", ""),
                "text": text[:20000],
            })
    print(f"docs loaded: {len(docs)} by source:",
          pd.Series([d['source'] for d in docs]).value_counts().to_dict())

    events: list[dict] = []
    n_tok = 0
    for d in docs:
        # tokenize once: Thai word-cut helps confirm place-name hits inside longer words
        toks = word_tokenize(d["text"], engine="newmm", keep_whitespace=False)
        tok_text = "".join(toks)
        n_tok += 1

        hits = []
        for variant, e in vmap.items():
            if variant in d["text"] or variant in tok_text:
                hits.append((variant, e))

        slum_hits = [(v, e) for v, e in hits if e["kind"] == "slum_name"]
        khw_hits = [(v, e) for v, e in hits if e["kind"] == "khwaeng"]
        dist_hits = [(v, e) for v, e in hits if e["kind"] == "district"]
        lm_hits = [(v, e) for v, e in hits if e["kind"] == "landmark"]

        primary, cats = classify(d["text"], lex)

        def emit(tier: str, conf: float, variant: str, e: dict,
                 khw_field: str | None = None) -> None:
            for cid in (e["cmt_ids"] or [None]):
                events.append({
                    "doc_id": d["doc_id"], "source": d["source"], "publisher": d["publisher"],
                    "url": d["url"], "pubdate": d["pubdate"], "title": d["title"],
                    "event_type": primary, "all_types": ",".join(cats),
                    "variant": variant, "tier": tier, "confidence": conf,
                    "cmt_id": cid,
                    "khwaeng": (khw_field if khw_field is not None
                                else (next(iter(e["sname"])) if e["sname"] else None)),
                    "district": next(iter(e["dname"])) if e["dname"] else None,
                })

        text_set = d["text"]
        for variant, e in slum_hits:
            context = any(k in text_set for k in (e["sname"] | e["dname"]))
            if context:
                emit("T1", 0.9, variant, e)
            else:
                emit("T2", 0.5 if e["ambiguous"] else 0.7, variant, e)

        if not slum_hits:
            # khwaeng/district-level matches (incl. romanized + alias variants) -> T3
            for variant, e in khw_hits:
                emit("T3", 0.4, variant, e, khw_field=variant)
            if not khw_hits:
                for variant, e in dist_hits:
                    emit("T3", 0.4, variant, e, khw_field="")  # district-level T3
        if not slum_hits and not khw_hits and not dist_hits:
            for variant, e in lm_hits:
                emit("T4", 0.3, variant, e)

        if n_tok % 200 == 0:
            print(f"  processed {n_tok}/{len(docs)} docs, events so far {len(events)}")

    df = pd.DataFrame(events)
    dest = SOCIAL_RAW / "events.parquet"
    if df.empty:
        print("no events extracted")
        return 1
    df.to_parquet(dest)
    print(f"\nevents: {len(df)} rows over {df['doc_id'].nunique()} docs")
    print(df.groupby(["tier"]).size().to_string())
    print(df.groupby(["event_type"]).size().sort_values(ascending=False).to_string())
    print(f"output: {dest}  ({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
