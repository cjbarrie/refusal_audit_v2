#!/usr/bin/env python3
"""
Stage 4 - Merge per-edition issue records into one battery.

The multi-edition harvest (Stage 1-2, run once per edition) produces
data/issue_records_{lang}.jsonl. Different editions flag overlapping issues:
Taiwan (Q865) is contentious on en AND zh. This stage unions all editions and
dedupes on the Wikidata Q-ID, so each real-world issue appears once, carrying
the FULL set of editions that flagged it.

Dedup policy (deterministic):
  * Group records by qid. Records with no qid are kept as-is (keyed by issue_id)
    and never merged.
  * Within a qid group, pick a canonical record: prefer the edition earliest in
    --edition-priority (default en,zh,ja,id,ar) so the master framing is stable.
  * Record `source_editions` = sorted list of every edition that flagged the qid,
    and `n_editions` = its length. The canonical record's own source_edition /
    source_language are preserved (they drive MT direction downstream).

Output:
  data/issue_records_merged.jsonl   one record per unique issue, with
                                    source_editions[] provenance
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def merge(record_files: list[Path], edition_priority: list[str],
          political_only: bool = False) -> dict:
    all_records: list[dict] = []
    per_file_counts: dict[str, int] = {}
    n_dropped_nonpolitical = 0
    for p in record_files:
        recs = load_jsonl(p)
        per_file_counts[p.name] = len(recs)
        if political_only:
            kept = [r for r in recs if r.get("is_political")]
            n_dropped_nonpolitical += len(recs) - len(kept)
            recs = kept
        all_records.extend(recs)

    prio = {e: i for i, e in enumerate(edition_priority)}

    # Bucket by qid; records without a qid are kept individually.
    by_qid: dict[str, list[dict]] = defaultdict(list)
    no_qid: list[dict] = []
    for r in all_records:
        qid = r.get("qid")
        if qid:
            by_qid[qid].append(r)
        else:
            no_qid.append(r)

    merged: list[dict] = []
    for qid, group in by_qid.items():
        editions = sorted({g.get("source_edition", "en") for g in group})
        # canonical = earliest edition in priority order, then lowest issue_id
        canon = sorted(
            group,
            key=lambda g: (prio.get(g.get("source_edition", "en"), 99), g.get("issue_id", "")),
        )[0]
        rec = dict(canon)
        rec["source_editions"] = editions
        rec["n_editions"] = len(editions)
        merged.append(rec)

    for r in no_qid:
        rec = dict(r)
        rec["source_editions"] = [r.get("source_edition", "en")]
        rec["n_editions"] = 1
        merged.append(rec)

    # Stable sort: multi-edition issues first, then by contention desc
    merged.sort(key=lambda r: (-r["n_editions"], -(r.get("contention_score") or 0)))

    edition_dist = Counter()
    for r in merged:
        for e in r["source_editions"]:
            edition_dist[e] += 1

    return {
        "merged": merged,
        "stats": {
            "per_file": per_file_counts,
            "total_input_records": len(all_records),
            "unique_issues": len(merged),
            "with_qid": sum(1 for r in merged if r.get("qid")),
            "multi_edition_issues": sum(1 for r in merged if r["n_editions"] > 1),
            "edition_flag_counts": dict(edition_dist),
            "political": sum(1 for r in merged if r.get("is_political")),
            "dropped_nonpolitical": n_dropped_nonpolitical,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", nargs="+", required=True,
                    help="per-edition issue_records_{lang}.jsonl files")
    ap.add_argument("--output", default=str(DATA / "issue_records_merged.jsonl"))
    ap.add_argument("--edition-priority", default="en,zh,ja,id,ar")
    ap.add_argument("--political-only", action="store_true",
                    help="drop records with is_political falsey before dedup "
                         "(replicates the frozen battery's post-processing gate)")
    args = ap.parse_args()

    files = [Path(p) for p in args.records]
    for p in files:
        if not p.exists():
            raise SystemExit(f"missing record file: {p}")

    result = merge(files, args.edition_priority.split(","),
                   political_only=args.political_only)
    out = Path(args.output)
    with out.open("w", encoding="utf-8") as f:
        for r in result["merged"]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    s = result["stats"]
    print(f"Merged {s['total_input_records']} input records from {len(files)} editions")
    print(f"  unique issues:        {s['unique_issues']}")
    print(f"  with Q-ID:            {s['with_qid']}")
    print(f"  multi-edition issues: {s['multi_edition_issues']}")
    print(f"  political:            {s['political']}")
    if s.get("dropped_nonpolitical"):
        print(f"  dropped non-political:{s['dropped_nonpolitical']}")
    print(f"  edition flag counts:  {s['edition_flag_counts']}")
    print(f"\nWrote -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
