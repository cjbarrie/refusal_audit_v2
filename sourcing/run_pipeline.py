#!/usr/bin/env python3
"""
Sourcing pipeline driver.

Runs the whole sourcing stage for one or more Wikipedia editions and merges the
result into a single battery. Every knob is read from sourcing/editions.yaml or
passed on the command line, so a run is fully specified by config + command.

Stages, per edition:
  1. harvest   (01_harvest_controversial.py)  -- FREE, Wikipedia API only
  2. enrich    (02_enrich_issues.py)          -- LLM spend; OPT-IN via --enrich
  3. format    (03_format_prompts.py)         -- LLM spend; runs only if enriched
Then once:
  4. merge     (04_merge_editions.py)          -- FREE, dedupe on Q-ID

Default (no --enrich) does ONLY the free candidate harvest across the requested
editions and stops before spending the OpenRouter key. This is the safe default
for validation runs.

The LLM stages need OPENROUTER_API_KEY in the environment (never written to disk
by this pipeline). See docs/REPRODUCIBILITY.md.

Examples:
  # free five-edition candidate harvest (no LLM):
  python run_pipeline.py --editions en zh ar ja id

  # full English battery (harvest + enrich + format), then merge:
  python run_pipeline.py --editions en --enrich --model anthropic/claude-sonnet-5
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"
PROMPTS = REPO / "prompts"
LOG = HERE / "run.log"

PY = sys.executable


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list[str], stage: str, lang: str) -> float:
    """Run a subprocess, timing it, tee-ing a one-line summary to run.log."""
    t0 = time.time()
    log(f"START {stage} [{lang}] :: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(HERE), capture_output=True, text=True)
    dt = time.time() - t0
    tail = proc.stdout.strip().splitlines()[-3:] if proc.stdout.strip() else []
    for t in tail:
        log(f"    {stage} [{lang}] | {t}")
    if proc.returncode != 0:
        log(f"FAIL  {stage} [{lang}] rc={proc.returncode} ({dt:.0f}s)")
        log(f"    stderr: {proc.stderr.strip()[-800:]}")
        raise SystemExit(f"{stage} failed for {lang}")
    log(f"OK    {stage} [{lang}] ({dt:.0f}s)")
    return dt


def cand_path(lang: str) -> Path:
    return DATA / ("candidate_issues.json" if lang == "en" else f"candidate_issues_{lang}.json")


def records_path(lang: str) -> Path:
    return DATA / ("issue_records_full.jsonl" if lang == "en" else f"issue_records_{lang}.jsonl")


def prompts_path(lang: str) -> Path:
    return PROMPTS / ("full_prompts_en.json" if lang == "en" else f"full_prompts_{lang}.json")


def review_path(lang: str) -> Path:
    return PROMPTS / ("full_review_sheet.csv" if lang == "en" else f"full_review_sheet_{lang}.csv")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--editions", nargs="+", default=["en"],
                    help="edition keys from editions.yaml (en/zh/ar/ja/id)")
    ap.add_argument("--enrich", action="store_true",
                    help="ALSO run LLM enrichment + prompt formatting (spends OpenRouter key). "
                         "Without this flag the driver does only the free candidate harvest.")
    ap.add_argument("--model", default="anthropic/claude-sonnet-5")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="cap issues per edition (probes)")
    ap.add_argument("--merge", action="store_true", default=True,
                    help="merge per-edition records on Q-ID (default on)")
    ap.add_argument("--no-merge", dest="merge", action="store_false")
    ap.add_argument("--edition-priority", default="en,zh,ja,id,ar")
    args = ap.parse_args()

    log("=" * 72)
    log(f"RUN editions={args.editions} enrich={args.enrich} model={args.model if args.enrich else '(none)'}")

    record_files: list[Path] = []
    for lang in args.editions:
        # Stage 1 — harvest (free)
        run([PY, "01_harvest_controversial.py", "--lang", lang], "harvest", lang)

        if not args.enrich:
            continue

        # Stage 2 — enrich (LLM)
        cmd = [PY, "02_enrich_issues.py", "--lang", lang,
               "--candidates", str(cand_path(lang)),
               "--output", str(records_path(lang)),
               "--model", args.model, "--workers", str(args.workers)]
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        run(cmd, "enrich", lang)
        record_files.append(records_path(lang))

        # Stage 3 — format (LLM)
        run([PY, "03_format_prompts.py",
             "--records", str(records_path(lang)),
             "--out-prompts", str(prompts_path(lang)),
             "--out-review", str(review_path(lang)),
             "--model", args.model], "format", lang)

    # Stage 4 — merge (free), only when we produced >1 edition's records
    if args.enrich and args.merge and len(record_files) >= 1:
        run([PY, "04_merge_editions.py", "--records", *[str(p) for p in record_files],
             "--edition-priority", args.edition_priority], "merge", "all")

    log("DONE")
    if not args.enrich:
        log("NOTE: candidate harvest only (free). Re-run with --enrich to build prompts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
