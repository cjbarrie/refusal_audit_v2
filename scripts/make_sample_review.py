#!/usr/bin/env python3
"""
Emit a side-by-side review sheet for a drawn sample.

One row per prompt, one column per language, plus the design fields the draw was
stratified on (region, topic) and the provenance a reviewer needs to judge a row
(issue title, Q-ID, tier, which side of the matched pair, and whether the prompt
was authored in English or back-translated).

This is the human gate before generation spends money: the sample is what the
models will actually be asked, so it should be readable in a spreadsheet rather
than only as JSON.

Usage:
    python make_sample_review.py --battery rebalanced
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sample_prompts import BATTERY_STEM, LANGS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--battery", default="rebalanced", choices=list(BATTERY_STEM))
    ap.add_argument("--sample-dir", default=os.path.join(ROOT, "prompts", "sampled"))
    ap.add_argument("--records", default=os.path.join(
        ROOT, "data", "issue_records_rebalanced.jsonl"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    stem = BATTERY_STEM[args.battery]
    out = args.out or os.path.join(args.sample_dir, f"{stem}_sample_review.csv")

    # issue_id -> title, for a reviewer to recognise what the prompt is about
    titles = {}
    if os.path.exists(args.records):
        with open(args.records, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    titles[r["issue_id"]] = r.get("title", "")

    per_lang = {}
    for lang in LANGS:
        p = os.path.join(args.sample_dir, f"{stem}_{lang}_sample.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                per_lang[lang] = {x["id"]: x for x in json.load(f)["prompts"]}
    if "en" not in per_lang:
        sys.exit(f"no English sample found in {args.sample_dir}")
    langs = [l for l in LANGS if l in per_lang]

    en = per_lang["en"]
    # Group so a matched A/B pair sits on adjacent rows, and an issue's prompts
    # stay together — the reviewer is judging symmetry, which is unreadable if
    # the two sides are hundreds of rows apart.
    order = sorted(en.values(), key=lambda p: (
        p.get("region_focus") or "", p.get("topic_domain") or "",
        p.get("issue_id") or "", p.get("controversy_tier") or "",
        p.get("position_side") or ""))

    cols = ["issue_id", "title", "qid", "region_focus", "topic_domain",
            "controversy_tier", "position_side", "prompt_origin_language",
            "prompt_origin_form", "id"] + [f"text_{l}" for l in langs]

    os.makedirs(args.sample_dir, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for p in order:
            row = {
                "issue_id": p.get("issue_id"),
                "title": titles.get(p.get("issue_id"), ""),
                "qid": p.get("qid"),
                "region_focus": p.get("region_focus"),
                "topic_domain": p.get("topic_domain"),
                "controversy_tier": p.get("controversy_tier"),
                "position_side": p.get("position_side") or "",
                "prompt_origin_language": p.get("prompt_origin_language", "en"),
                "prompt_origin_form": p.get("prompt_origin_form", "authored_en"),
                "id": p["id"],
            }
            for l in langs:
                row[f"text_{l}"] = (per_lang[l].get(p["id"]) or {}).get("text", "")
            w.writerow(row)

    print(f"wrote {out}")
    print(f"  {len(order)} prompts x {len(langs)} languages ({', '.join(langs)})")
    n_iss = len({p.get('issue_id') for p in order})
    print(f"  {n_iss} issues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
