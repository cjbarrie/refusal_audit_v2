#!/usr/bin/env python3
"""
One-off migration — rewrite issue_id / prompt id onto the collision-free scheme.

Why this exists
---------------
Both enrichers used to derive the issue id from an ASCII-only slug of the title:

    issue_id = "issue_" + re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:48]

For a title in a non-Latin script that pattern matches every character, so the
slug came out EMPTY and the record was given the id "issue_". In the rebalanced
frame that put 404 Chinese-titled issues on one id, and because
03_format_prompts.py derives prompt ids as f"{issue_id}__reg1", the ids
issue___reg1 / __reg2 / __bndA / __bndB each ended up carrying 404 rows.

02_enrich_issues.make_issue_id now derives uniqueness from the Wikidata Q-ID.
This script applies that scheme to artifacts that were ALREADY built, so they do
not have to be regenerated: prompt text is unaffected by the id change and has
already been paid for.

How prompts are matched to records
----------------------------------
The prompt files preserve record order, and every record emits its "__reg1"
prompt first, so splitting the prompt list at each "__reg1" yields blocks that
map 1:1 onto the records in order. The script verifies this (block count ==
record count, and every block's qid agrees with its record's) and aborts rather
than guess.

Positional alignment is used rather than a qid join because 45 of the colliding
records have no Q-ID at all — they cannot be keyed on qid, which is precisely
the case a join would silently get wrong.

The non-English batteries are matched to the English one by position too, after
asserting they carry the identical OLD id sequence.

Idempotent: re-running on already-migrated files is a no-op.

Usage:
    python 09_migrate_issue_ids.py --dry-run          # report, touch nothing
    python 09_migrate_issue_ids.py                    # migrate in place (+ .bak)
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"
PROMPTS = REPO / "prompts"

# 02's module name starts with a digit, so it cannot be imported normally.
_spec = importlib.util.spec_from_file_location("enrich02", HERE / "02_enrich_issues.py")
enrich02 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(enrich02)
make_issue_id = enrich02.make_issue_id


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def split_blocks(prompts: list[dict]) -> list[list[dict]]:
    """Group prompts into per-issue blocks, starting a block at each __reg1."""
    blocks: list[list[dict]] = []
    for p in prompts:
        if p["id"].endswith("__reg1") or not blocks:
            blocks.append([])
        blocks[-1].append(p)
    return blocks


def verify_alignment(blocks: list[list[dict]], recs: list[dict]) -> list[str]:
    """Return a list of problems; empty means the positional mapping is sound."""
    problems: list[str] = []
    if len(blocks) != len(recs):
        problems.append(f"block count {len(blocks)} != record count {len(recs)}")
        return problems
    for i, (b, r) in enumerate(zip(blocks, recs)):
        if b[0].get("qid") != r.get("qid"):
            problems.append(f"block {i}: qid {b[0].get('qid')} != record qid {r.get('qid')}")
        if not b[0]["id"].endswith("__reg1"):
            problems.append(f"block {i}: does not start at a __reg1 prompt ({b[0]['id']})")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", default=str(DATA / "issue_records_rebalanced.jsonl"))
    ap.add_argument("--prompts", default=str(PROMPTS / "rebalanced_prompts_en.json"),
                    help="the English master; sibling languages are derived from its stem")
    ap.add_argument("--languages", nargs="+", default=["zh", "ar", "ru", "hi"])
    ap.add_argument("--review", default=str(PROMPTS / "rebalanced_review_en.csv"))
    ap.add_argument("--redo-out", default=str(DATA / "idfix_redo_ids.json"),
                    help="where to record the NEW ids of prompts whose OLD id was "
                         "ambiguous; their existing translations are unreliable "
                         "(the id->translation map collapsed them) and must be redone")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    rec_path = Path(args.records)
    en_path = Path(args.prompts)
    recs = load_jsonl(rec_path)
    en_doc = json.loads(en_path.read_text(encoding="utf-8"))
    en_prompts = en_doc["prompts"]

    blocks = split_blocks(en_prompts)
    problems = verify_alignment(blocks, recs)
    if problems:
        print("ABORT — prompts do not align with records positionally:", file=sys.stderr)
        for p in problems[:10]:
            print(f"  {p}", file=sys.stderr)
        return 1
    print(f"alignment OK: {len(blocks)} prompt blocks <-> {len(recs)} records")

    # --- compute the new ids -------------------------------------------------
    old_ids = [p["id"] for p in en_prompts]
    new_ids: list[str] = []
    new_issue_ids: list[str] = []
    for rec, block in zip(recs, blocks):
        new_iid = make_issue_id(rec["title"], rec.get("qid"))
        for p in block:
            suffix = p["id"].rsplit("__", 1)[1]
            new_ids.append(f"{new_iid}__{suffix}")
            new_issue_ids.append(new_iid)

    collisions_before = len(old_ids) - len(set(old_ids))
    collisions_after = len(new_ids) - len(set(new_ids))
    changed = sum(1 for a, b in zip(old_ids, new_ids) if a != b)
    print(f"prompt ids: {changed}/{len(old_ids)} change; "
          f"rows lost to collision {collisions_before} -> {collisions_after}")
    if collisions_after:
        print("ABORT — the new scheme still collides; not writing.", file=sys.stderr)
        return 1
    if changed == 0:
        print("nothing to do (already migrated).")
        return 0

    # --- language batteries: verify then plan --------------------------------
    lang_docs: dict[str, dict] = {}
    for lang in args.languages:
        p = en_path.with_name(en_path.name.replace("_en.json", f"_{lang}.json"))
        if not p.exists():
            print(f"  [{lang}] {p.name} not found — skipping")
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        seq = [x["id"] for x in doc["prompts"]]
        if seq != old_ids:
            print(f"ABORT — {p.name} does not carry the same id sequence as the "
                  f"English master; refusing to migrate it positionally.", file=sys.stderr)
            return 1
        lang_docs[lang] = {"path": p, "doc": doc}
        print(f"  [{lang}] {p.name}: id sequence matches ({len(seq)} prompts)")

    if args.dry_run:
        print("\n--dry-run: no files written. Examples of the rewrite:")
        shown = 0
        for a, b in zip(old_ids, new_ids):
            if a != b and shown < 5:
                print(f"    {a}  ->  {b}")
                shown += 1
        return 0

    def backup(p: Path) -> None:
        if not args.no_backup:
            bak = p.with_suffix(p.suffix + ".pre_idfix")
            if not bak.exists():
                shutil.copy2(p, bak)

    # --- write records -------------------------------------------------------
    backup(rec_path)
    for rec, block in zip(recs, blocks):
        rec["issue_id"] = make_issue_id(rec["title"], rec.get("qid"))
    rec_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
    print(f"wrote {rec_path.name}")

    # --- write batteries -----------------------------------------------------
    for path, doc in [(en_path, en_doc)] + [(v["path"], v["doc"]) for v in lang_docs.values()]:
        backup(path)
        for p, nid, niid in zip(doc["prompts"], new_ids, new_issue_ids):
            p["id"] = nid
            p["issue_id"] = niid
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {path.name}")

    # --- write review sheet (one row per issue, same order) ------------------
    rev = Path(args.review)
    if rev.exists():
        rows = list(csv.DictReader(rev.open(encoding="utf-8")))
        if len(rows) == len(recs):
            backup(rev)
            for row, rec in zip(rows, recs):
                row["issue_id"] = rec["issue_id"]
            with rev.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
            print(f"wrote {rev.name}")
        else:
            print(f"  ! {rev.name}: {len(rows)} rows != {len(recs)} records — left untouched")

    # Rows whose OLD id was ambiguous received whichever translation the
    # id->text map happened to retain, so every translation of them is suspect
    # regardless of language. Record their NEW ids for targeted re-translation.
    dup_old = {i for i, c in Counter(old_ids).items() if c > 1}
    suspect = sorted(new for old, new in zip(old_ids, new_ids) if old in dup_old)
    Path(args.redo_out).write_text(
        json.dumps({"source": en_path.name,
                    "reason": "old prompt id was ambiguous; translation map collapsed it",
                    "ids": {lang: suspect for lang in args.languages}},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {Path(args.redo_out).name}: {len(suspect)} prompts with unreliable "
          f"translations (per language)")

    print("\nmigration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
