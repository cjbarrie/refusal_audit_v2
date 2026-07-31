#!/usr/bin/env bash
# =============================================================================
# run_corrections.sh — one-command repair of the rebalanced prompt battery.
#
# QC of the completed rebalance (docs/REBALANCE.md §8-§11) found three defects.
# This chains their fixes in the ONE order that is correct, because each stage
# consumes what the previous one produced:
#
#   Stage 9   collision-free issue/prompt ids            FREE   idempotent
#   Stage 10  back-translate natively-sourced prompts    SPEND  ~49 calls
#   Stage 11  re-translate only the affected rows        SPEND  ~242 calls
#   Stage 12  verify canonical boundary templates        FREE   expect 0 changes
#
# WHY THIS ORDER
#   9 before 10  - 10 keys its worklist on prompt id; while ids collide, 404
#                  Chinese issues share one id and the map collapses them.
#   10 before 11 - 11 wraps Stage 5, which translates FROM English; until 10
#                  rewrites them, 1,214 rows in the English master are Chinese.
#                  Running it first would render every other language from
#                  Chinese instead of from the shared English pivot — the exact
#                  defect being fixed, at full cost. (Stage 5 now refuses this
#                  rather than trust the runbook; --allow-non-english overrides.)
#   10 writes 11's worklist - only 10 knows which rows changed. It unions those
#                  with Stage 9's collision-suspect ids and any blank
#                  translations.
#   12 last      - Stage 5 re-applies canonical templates as it writes, so this
#                  is a CHECK, not a fix. A non-zero count here means the
#                  guard failed and should be investigated.
#
# SPEND: stages 10 and 11 call OpenRouter. Stages 9 and 12 are pure local file
# rewrites and cost nothing.
#
# SAFETY: every stage writes a one-time backup beside each file it touches
# (.pre_idfix, .pre_backtranslate, .pre_template_fix), so any stage can be
# reverted by restoring those.
#
# Usage:
#   export OPENROUTER_API_KEY=sk-or-...
#   ./run_corrections.sh --dry-run     # print every command + scope, spend nothing
#   ./run_corrections.sh               # full repair
#   ./run_corrections.sh --skip-ids    # ids already migrated (stage 9 is a no-op anyway)
#   ./run_corrections.sh --skip-backtranslate   # stage 10 already run
#   ./run_corrections.sh --check       # report state only, change nothing
#
# RESUME AFTER A CRASH: stages 9 and 12 are idempotent, and 10 skips rows that
# already carry prompt_origin_language, so re-running is safe. Stage 5 with
# --redo-ids merges into the existing batteries rather than rewriting them, so a
# partial translation run can simply be repeated.
# =============================================================================
set -euo pipefail

# --- knobs (override via env) ------------------------------------------------
WORKERS="${WORKERS:-8}"
MODEL="${MODEL:-anthropic/claude-sonnet-5}"
LANGS="${LANGS:-zh ar ru hi}"

DRY_RUN=0
SKIP_IDS=0
SKIP_BT=0
CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --skip-ids) SKIP_IDS=1 ;;
    --skip-backtranslate) SKIP_BT=1 ;;
    --check) CHECK_ONLY=1; DRY_RUN=1 ;;
    -h|--help) sed -n '2,48p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

cd "$(dirname "$0")"                # -> sourcing/
DATA=../data
PROMPTS=../prompts

EN_BATTERY="$PROMPTS/rebalanced_prompts_en.json"
MERGED="$DATA/issue_records_rebalanced.jsonl"
IDFIX_REDO="$DATA/idfix_redo_ids.json"
BT_REDO="$DATA/backtranslate_redo_ids.json"

PY="${PYTHON:-python}"
run() { echo "+ $*"; if [[ "$DRY_RUN" -eq 0 ]]; then "$@"; fi; }
banner() { echo; echo "===== $* ====="; }

# --- preflight ---------------------------------------------------------------
for f in "$EN_BATTERY" "$MERGED"; do
  [[ -f "$f" ]] || { echo "ERROR: missing input: $f" >&2; exit 1; }
done
if [[ "$DRY_RUN" -eq 0 && -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "ERROR: OPENROUTER_API_KEY is not set. Stages 10 and 11 need it." >&2
  echo "       export OPENROUTER_API_KEY=sk-or-...   (or run with --dry-run)" >&2
  exit 1
fi

banner "State before"
"$PY" - <<'EOF'
import json, collections, pathlib
p = pathlib.Path("../prompts/rebalanced_prompts_en.json")
pr = json.loads(p.read_text(encoding="utf-8"))["prompts"]
ids = [x["id"] for x in pr]
def foreign(t):
    cut = t.find(": ")
    probe = t[cut+2:] if (cut > 0 and t[:cut].isascii()) else t
    lat = sum(1 for c in probe if c.isascii() and c.isalpha())
    for_ = sum(1 for c in probe if not c.isascii() and c.isalpha())
    return for_ / max(lat, 1) > 0.25
print(f"  prompts                : {len(pr)}")
print(f"  duplicate ids          : {len(ids)-len(set(ids))}   (stage 9 fixes)")
print(f"  non-English prompts    : {sum(1 for x in pr if foreign(x.get('text','')))}   (stage 10 fixes)")
print(f"  already tagged origin  : {sum(1 for x in pr if 'prompt_origin_language' in x)}")
EOF

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  banner "--check: reporting only, nothing run"
  exit 0
fi

# =============================================================================
banner "Stage 9 — collision-free ids (FREE, idempotent)"
if [[ "$SKIP_IDS" -eq 1 ]]; then
  echo "  (--skip-ids) skipping"
else
  run "$PY" 09_migrate_issue_ids.py \
      --records "$MERGED" --prompts "$EN_BATTERY" --languages $LANGS \
      --redo-out "$IDFIX_REDO"
fi

banner "Stage 10 — back-translate natively-sourced prompts (SPEND)"
if [[ "$SKIP_BT" -eq 1 ]]; then
  echo "  (--skip-backtranslate) skipping; reusing $BT_REDO"
  [[ -f "$BT_REDO" ]] || { echo "ERROR: $BT_REDO missing — stage 10 has not run" >&2; exit 1; }
else
  run "$PY" 10_backtranslate_native.py \
      --prompts "$EN_BATTERY" --languages $LANGS \
      --model "$MODEL" --workers "$WORKERS" \
      --redo-out "$BT_REDO" --merge-redo "$IDFIX_REDO"
fi

banner "Stage 11 — re-translate only the affected rows (SPEND)"
run "$PY" 11_retranslate_affected.py \
    --prompts "$EN_BATTERY" --languages $LANGS \
    --model "$MODEL" --workers "$WORKERS" \
    --redo-ids "$BT_REDO"

banner "Stage 12 — verify canonical boundary templates (FREE, expect 0 changes)"
run "$PY" 12_normalize_boundary_templates.py --batteries rebalanced_prompts \
    --languages $LANGS --dry-run

# =============================================================================
banner "State after"
if [[ "$DRY_RUN" -eq 0 ]]; then
"$PY" - <<'EOF'
import json, collections, pathlib
P = pathlib.Path("../prompts")
en = json.loads((P/"rebalanced_prompts_en.json").read_text(encoding="utf-8"))["prompts"]
ids = [x["id"] for x in en]
def foreign(t):
    cut = t.find(": ")
    probe = t[cut+2:] if (cut > 0 and t[:cut].isascii()) else t
    lat = sum(1 for c in probe if c.isascii() and c.isalpha())
    for_ = sum(1 for c in probe if not c.isascii() and c.isalpha())
    return for_ / max(lat, 1) > 0.25
print(f"  duplicate ids            : {len(ids)-len(set(ids))}          (want 0)")
print(f"  non-English in en master : {sum(1 for x in en if foreign(x.get('text','')))}          (want 0)")
form = collections.Counter(x.get("prompt_origin_form","-") for x in en)
print(f"  prompt_origin_form       : {dict(form)}")
for lang in ["zh","ar","ru","hi"]:
    f = P/f"rebalanced_prompts_{lang}.json"
    if not f.exists():
        continue
    pr = json.loads(f.read_text(encoding="utf-8"))["prompts"]
    blank = sum(1 for x in pr if not str(x.get("text","")).strip())
    same  = [x["id"] for x in pr]
    ok = "OK " if (len(pr) == len(en) and same == ids and blank == 0) else "!! "
    print(f"  {ok}[{lang}] n={len(pr)} idlock={same==ids} blanks={blank}")
EOF
else
  echo "  (dry-run) not evaluated"
fi

banner "Done"
cat <<'EOF'
Next:
  * re-run the region x topic QC on data/issue_records_rebalanced.jsonl
  * the topic-balance question is still OPEN (geopolitics 57% -> 63% against a
    ~46% target) — see docs/REBALANCE.md §3 and the NEXT_STEPS header block
  * do NOT freeze/launch until the QC above is clean
EOF
