#!/usr/bin/env python3
"""
Stage 11 — re-translate the rows whose translations are known to be unreliable.

This is a thin, deliberate wrapper around Stage 5. Stage 5 owns forward
translation and the side-by-side review sheet, and nothing about that changes
here; what this script adds is the *position in the sequence*. The repair runs

    09  collision-free ids
    10  back-translate natively-sourced prompts
    11  re-translate affected rows        <- this script
    12  verify canonical boundary templates

and a step numbered 05 sitting between 10 and 12 reads like a mistake every time
someone opens the directory. It is not a mistake — Stage 5 genuinely has to run
after Stage 10, because Stage 10 rewrites the English text that Stage 5
translates *from* — but that is worth encoding in the filename rather than
leaving in a runbook.

Which rows get re-translated
---------------------------
The worklist is written by Stage 10 and is the union of three groups, all of
which are wrong for different reasons:

  * rows whose English changed  - Stage 10 back-translated them, so every
                                  other language must be re-derived from the
                                  corrected English pivot.
  * collision-suspect rows      - their old prompt id was ambiguous, so Stage
                                  5's id->translation map collapsed several
                                  rows onto one translation. Their English was
                                  always fine; only the translations are bad.
  * blank translations          - whatever the cause.

Rows already served by their own native original (a prompt authored wholly in
the target language) are excluded — there is nothing to translate.

Everything outside the worklist keeps the translation already on disk: Stage 5
merges in `--redo-ids` mode rather than rewriting the file. That is what keeps
this a ~290-call repair instead of a ~1,775-call re-translation of the frame.

Needs OPENROUTER_API_KEY. Stage 5's own guards still apply — it will refuse to
run if the English master still holds non-English prompts (i.e. Stage 10 has not
run) or if any prompt id is duplicated (i.e. Stage 9 has not run).

Usage:
    python 11_retranslate_affected.py --dry-run
    python 11_retranslate_affected.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"
PROMPTS = REPO / "prompts"

STAGE5 = HERE / "05_translate_review.py"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default=str(PROMPTS / "rebalanced_prompts_en.json"))
    ap.add_argument("--redo-ids", default=str(DATA / "backtranslate_redo_ids.json"),
                    help="worklist written by 10_backtranslate_native.py")
    ap.add_argument("--languages", nargs="+", default=["zh", "ar", "ru", "hi"])
    ap.add_argument("--model", default="anthropic/claude-sonnet-5")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--review-out", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="report the worklist and the command, run nothing")
    args = ap.parse_args()

    redo = Path(args.redo_ids)
    if not redo.exists():
        sys.exit(
            f"ABORT — worklist not found: {redo}\n"
            f"        It is written by 10_backtranslate_native.py. Run Stage 10 first;\n"
            f"        without it there is no record of which rows need re-translating."
        )

    payload = json.loads(redo.read_text(encoding="utf-8"))
    ids = payload.get("ids", {})
    total = sum(len(v) for k, v in ids.items() if k in args.languages)
    print(f"worklist: {redo.name}")
    print(f"  reason: {payload.get('reason', '(unrecorded)')}")
    for lang in args.languages:
        print(f"  {lang}: {len(ids.get(lang, []))} prompts")
    calls = -(-total // args.batch_size)
    print(f"  total {total} translation units -> ~{calls} batched calls "
          f"@{args.batch_size}/call")

    cmd = [sys.executable, str(STAGE5),
           "--prompts", args.prompts,
           "--languages", *args.languages,
           "--model", args.model,
           "--workers", str(args.workers),
           "--batch-size", str(args.batch_size),
           "--redo-ids", str(redo)]
    if args.review_out:
        cmd += ["--review-out", args.review_out]

    print()
    print("+ " + " ".join(cmd))
    if args.dry_run:
        print("\n--dry-run: nothing run.")
        return 0

    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
