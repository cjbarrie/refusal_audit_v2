#!/usr/bin/env python3
"""
Backfill record-level provenance onto already-built prompt files.

Some facts live on the issue record but are needed on the prompt, because only
the prompt travels downstream into generation, annotation and the R analysis.
`03_format_prompts.py` now stamps them at build time; this brings existing
batteries up to the same state without rebuilding them (which would cost LLM
calls and change the prompt text).

Currently stamped:

  route     which harvest route produced the issue — `perennial` (curated
            controversy list), `temporal` (protection log) or `current-events`
            (portal). The rebalanced frame merges all three, so this is what
            makes the perennial-vs-contested-right-now contrast runnable from a
            single arm. Without it that comparison cannot be run at all: the
            route exists only on the records, which the annotation output never
            sees.

Deliberately NOT stamped: `source_article_status`. Whether an article still
exists on Wikipedia changes over time, so a copy frozen into the prompt files
would go stale silently. `sample_prompts.py --exclude-deleted` reads it from the
records instead, which are refreshed by `sourcing/14_recover_provenance.py`.

Idempotent, free, no network.

Usage:
    python stamp_prompt_provenance.py --battery rebalanced --dry-run
    python stamp_prompt_provenance.py --battery rebalanced
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sample_prompts import BATTERY_STEM, LANGS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

RECORDS_FOR = {
    "rebalanced": "issue_records_rebalanced.jsonl",
    "perennial": "issue_records_full.jsonl",
    "temporal": "issue_records_temporal_en.jsonl",
}


def route_of(rec: dict) -> str:
    return ((rec.get("contention_signals") or {}).get("route")
            or (rec.get("provenance") or {}).get("route")
            or "perennial")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--battery", default="rebalanced", choices=list(BATTERY_STEM))
    ap.add_argument("--records", default=None)
    ap.add_argument("--prompts-dir", default=os.path.join(ROOT, "prompts"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    stem = BATTERY_STEM[args.battery]
    rec_path = args.records or os.path.join(
        ROOT, "data", RECORDS_FOR.get(args.battery, ""))
    if not os.path.exists(rec_path):
        sys.exit(f"records not found: {rec_path}")

    route_by_issue = {}
    with open(rec_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                route_by_issue[r["issue_id"]] = route_of(r)
    print(f"{len(route_by_issue)} issue records from {os.path.basename(rec_path)}")
    print("  routes:", dict(collections.Counter(route_by_issue.values())))

    total_missing = 0
    for lang in LANGS:
        path = os.path.join(args.prompts_dir, f"{stem}_{lang}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        n = unmatched = 0
        for p in doc["prompts"]:
            if p.get("route"):
                continue
            route = route_by_issue.get(p.get("issue_id"))
            if route is None:
                unmatched += 1
                continue
            p["route"] = route
            n += 1
        total_missing += unmatched
        note = f"  ({unmatched} prompts had no matching record)" if unmatched else ""
        print(f"  {os.path.basename(path)}: {n} stamped{note}")
        if n and not args.dry_run:
            if not args.no_backup:
                bak = path + ".pre_route_tag"
                if not os.path.exists(bak):
                    shutil.copy2(path, bak)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)

    if total_missing:
        print(f"\n! {total_missing} prompt(s) had no matching issue record — "
              f"they keep no route and will read as NA downstream.")
    if args.dry_run:
        print("\n--dry-run: nothing written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
