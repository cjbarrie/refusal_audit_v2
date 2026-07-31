#!/usr/bin/env bash
# =============================================================================
# run_rebalance.sh — one-command rebalance of the refusal-audit prompt battery.
#
# Chains the three new sourcing routes + assembly + full-frame translation into
# a single reproducible run. See docs/REBALANCE.md for the design rationale.
#
#   Route A  zh China dispute-categories   (perennial pipeline: 01 -> 02)
#   Route B  en current-events topical      (08 -> 07 --route current-events)
#   Route C  CT-window widened to 180 days  (06 --days 180 -> 07)
#   Assembly merge --political-only -> format (English) -> translate (6 langs)
#
# SPEND: enrichment (02, 07), formatting (03), and translation (05) call the
# OpenRouter API and cost money. Harvest steps (01, 06, 08) are read-only
# Wikipedia and free. Order-of-magnitude cost is in docs/REBALANCE.md §6.
#
# SAFETY: all rebalance outputs are written to DISTINCT paths (suffixed
# _rebalanced / _180d / current_events). The frozen batteries
# (issue_records_full.jsonl, candidate_issues_temporal_en.json,
# full_prompts_*.json, temporal_prompts_*.json) are NEVER overwritten.
#
# Usage:
#   export OPENROUTER_API_KEY=sk-or-...
#   ./run_rebalance.sh                 # full run
#   ./run_rebalance.sh --dry-run       # print every command, run nothing
#   ./run_rebalance.sh --skip-harvest  # reuse existing candidate_* files
#   ./run_rebalance.sh --skip-enrich   # reuse existing issue_records_* (no re-spend)
#   CE_DAYS=60 CT_DAYS=180 WORKERS=8 ./run_rebalance.sh   # tune knobs
#
# RESUME AFTER A CRASH: enrichment writes its output file atomically (only on
# full success), so a completed route's issue_records_*.jsonl is safe to reuse.
# To pick up after a mid-run failure without re-spending on finished routes:
#   ./run_rebalance.sh --skip-harvest --skip-enrich
# =============================================================================
set -euo pipefail

# --- knobs (override via env) ------------------------------------------------
WORKERS="${WORKERS:-8}"
CE_DAYS="${CE_DAYS:-45}"           # current-events portal window
CE_MIN_CONTENTION="${CE_MIN_CONTENTION:-0.45}"
CT_DAYS="${CT_DAYS:-180}"          # widened protection-log window
MODEL="${MODEL:-anthropic/claude-sonnet-5}"
LANGS="${LANGS:-zh ar ru hi}"

DRY_RUN=0
SKIP_HARVEST=0
SKIP_ENRICH=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --skip-harvest) SKIP_HARVEST=1 ;;
    --skip-enrich) SKIP_ENRICH=1 ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# --- paths (repo-relative; script lives in sourcing/) ------------------------
cd "$(dirname "$0")"                # -> sourcing/
DATA=../data
PROMPTS=../prompts
mkdir -p "$DATA" "$PROMPTS"

# rebalance-specific output files (frozen inputs untouched)
ZH_CAND="$DATA/candidate_issues_zh.json"
ZH_REC="$DATA/issue_records_zh.jsonl"
CE_CAND="$DATA/candidate_issues_current_events_en.json"
CE_REC="$DATA/issue_records_current_events_en.jsonl"
CT_CAND="$DATA/candidate_issues_temporal_180d_en.json"
CT_REC="$DATA/issue_records_temporal_180d_en.jsonl"
PERENNIAL_REC="$DATA/issue_records_full.jsonl"      # FROZEN perennial pool (read-only input)
MERGED="$DATA/issue_records_rebalanced.jsonl"
EN_BATTERY="$PROMPTS/rebalanced_prompts_en.json"
EN_REVIEW="$PROMPTS/rebalanced_review_en.csv"

# --- helpers -----------------------------------------------------------------
PY="${PYTHON:-python}"
run() {   # echo + (unless dry-run) execute
  echo "+ $*"
  if [[ "$DRY_RUN" -eq 0 ]]; then "$@"; fi
}
banner() { echo; echo "===== $* ====="; }

# --- preflight ---------------------------------------------------------------
if [[ "$DRY_RUN" -eq 0 && -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "ERROR: OPENROUTER_API_KEY is not set. Enrichment/format/translate need it." >&2
  echo "       export OPENROUTER_API_KEY=sk-or-...   (or run with --dry-run)" >&2
  exit 1
fi
if [[ ! -f "$PERENNIAL_REC" ]]; then
  echo "ERROR: frozen perennial pool missing: $PERENNIAL_REC" >&2
  echo "       (expected the 516-record enriched perennial battery)" >&2
  exit 1
fi

# =============================================================================
banner "Route A — zh China dispute-categories (region fix)"
if [[ "$SKIP_HARVEST" -eq 0 || ! -f "$ZH_CAND" ]]; then
  run "$PY" 01_harvest_controversial.py --lang zh          # -> $ZH_CAND (free)
else
  echo "  (skip-harvest) reusing $ZH_CAND"
fi
if [[ "$SKIP_ENRICH" -eq 1 && -f "$ZH_REC" ]]; then
  echo "  (skip-enrich) reusing $ZH_REC"
else
run "$PY" 02_enrich_issues.py --lang zh --workers "$WORKERS" --model "$MODEL" \
    --candidates "$ZH_CAND" --output "$ZH_REC"
fi

banner "Route B — en current-events topical breadth (topic fix)"
if [[ "$SKIP_HARVEST" -eq 0 || ! -f "$CE_CAND" ]]; then
  # 08 batches all API calls (50 titles/request); it has no --workers knob.
  run "$PY" 08_harvest_current_events.py --days "$CE_DAYS" \
      --min-contention "$CE_MIN_CONTENTION" --out "$CE_CAND"  # free
else
  echo "  (skip-harvest) reusing $CE_CAND"
fi
if [[ "$SKIP_ENRICH" -eq 1 && -f "$CE_REC" ]]; then
  echo "  (skip-enrich) reusing $CE_REC"
else
  run "$PY" 07_enrich_temporal.py --workers "$WORKERS" --model "$MODEL" \
      --route current-events --candidates "$CE_CAND" --output "$CE_REC"
fi

banner "Route C — CT-window widened to ${CT_DAYS}d (volume: US/Europe/Russia)"
if [[ "$SKIP_HARVEST" -eq 0 || ! -f "$CT_CAND" ]]; then
  run "$PY" 06_harvest_temporal.py --days "$CT_DAYS" --lang en --output "$CT_CAND"  # free
else
  echo "  (skip-harvest) reusing $CT_CAND"
fi
if [[ "$SKIP_ENRICH" -eq 1 && -f "$CT_REC" ]]; then
  echo "  (skip-enrich) reusing $CT_REC"
else
  run "$PY" 07_enrich_temporal.py --workers "$WORKERS" --model "$MODEL" \
      --route temporal --candidates "$CT_CAND" --output "$CT_REC"
fi

banner "Assembly — merge (--political-only), dedup on QID"
run "$PY" 04_merge_editions.py --political-only \
    --records "$PERENNIAL_REC" "$ZH_REC" "$CE_REC" "$CT_REC" \
    --output "$MERGED"

banner "Format — English rebalanced battery"
run "$PY" 03_format_prompts.py --workers "$WORKERS" \
    --records "$MERGED" --out-prompts "$EN_BATTERY" --out-review "$EN_REVIEW"

banner "Translate — full frame into: $LANGS"
run "$PY" 05_translate_review.py --prompts "$EN_BATTERY" \
    --languages $LANGS --workers "$WORKERS" --model "$MODEL"

banner "DONE"
echo "English frame:   $EN_BATTERY"
echo "Translations:    $PROMPTS/rebalanced_prompts_{$(echo $LANGS | tr ' ' ',')}.json"
echo "Review sheet:    $PROMPTS/canonical_review_all_languages.csv"
echo "Next: stratified sample in R (pipeline/), then run_pilot.py --dry-run to re-price."
