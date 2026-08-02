# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

An audit of LLM political-refusal behavior. The novelty of v2 vs. the legacy
repo (`../refusal_audit`, reference-only, never modified) is the **sourcing
stage**: instead of drafting controversial questions with GPT-4o (circular —
using an LLM to define what's controversial, then testing LLMs on it), this
version seeds prompts from **Wikipedia's human-curated controversy lists**
(the "perennial" route) and the **MediaWiki protection log** (the "temporal"
route, what's being fought over *right now*). Everything downstream of
sourcing — response generation, LLM-as-judge annotation, R analysis — is
carried over from the legacy repo largely unchanged so results stay
comparable. `MANIFEST.md` records exactly what was copied, rewritten, or
deliberately left behind, and is the first place to check before assuming a
file's provenance.

Read `docs/PIPELINE.md` (sourcing design + rationale) and `docs/NEXT_STEPS.md`
(current state + what's next, session-log style with a dated authoritative
block at the top) before making non-trivial changes — they carry context that
isn't derivable from the code alone.

## Environment

```bash
conda activate refusal-v2      # py3.13; matplotlib/pandas/numpy/openai/pyyaml
```

No `requirements.txt`/`environment.yml`/`pyproject.toml` exists — dependencies
are whatever's in the `refusal-v2` conda env (see comment above). No test
suite and no lint config exist in this repo; don't invent CI-style commands
that aren't backed by actual tooling here.

Secrets live in `.env` at repo root (git-ignored) and are loaded by
`scripts/env_utils.py::load_env_from_file()` — never read from the shell
directly and never written to disk by any pipeline stage. Keys: `OPENROUTER_API_KEY`
(subject models + judge, via OpenRouter), `HF_TOKEN` + per-model
`ALLAM_ENDPOINT_URL` / `FALCON3_ENDPOINT_URL` / `JAIS_ENDPOINT_URL` /
`SARVAM_ENDPOINT_URL` (dedicated HF Inference Endpoints for the MENA + India
arm — a model joins the roster only when its URL var is set; without it, the
run silently drops to the smaller OpenRouter-only roster, no error).

**`PYTHONSAFEPATH=1` is set in this environment**, so a script's own directory
is not auto-added to `sys.path`. Every entry script (`generate_responses.py`,
`annotation_pipeline.py`, `run_pilot.py`, sourcing stage scripts) bootstraps
its own dir onto `sys.path` near the top for sibling imports (`config`,
`env_utils`) — preserve that when adding new entry scripts.

Nothing in this repo should spend money without the user driving it — script
runs that call `OPENROUTER_API_KEY` or an HF endpoint are real spend. Use
`--dry-run` where a script supports it (`run_pilot.py`) and confirm before
launching a real generation/annotation run.

## Pipeline architecture (three stages, in order)

```
sourcing/   Wikipedia/protection-log seed -> enrich -> format -> merge -> translate
              (Stages 1-5, + 1b/2b for the temporal route)  -> prompts/*.json
scripts/    sample -> generate subject-model responses -> LLM-as-judge annotate
              -> assemble into the R-contract file layout   -> annotations/<run_id>/
pipeline/   R analysis: 01_data_loading.R builds the clean table every other
              script reads; 02-16_*.R are individual analyses/figures/tables
```

### 1. Sourcing (`sourcing/`) — two disjoint seed routes, one shared spine

Both routes feed the *same* enrich → format → translate stages and produce
issue records with an identical fixed schema (`neutral_summary`,
`positions {A,B}`, `key_entities`, `region`, `topic_domain`, `contention_score`,
`provenance`). They are **fully disjoint on Wikidata Q-ID**.

- **Perennial route** (main): `01_harvest_controversial.py` → `02_enrich_issues.py`
  → `03_format_prompts.py` → `04_merge_editions.py`. Driven end-to-end by
  `sourcing/run_pipeline.py` (harvest+merge are free; enrich/format need
  `OPENROUTER_API_KEY`, opt-in via `--enrich`). Per-edition config
  (API host, list page, sections, dispute categories) lives in
  `sourcing/editions.yaml`.
- **Temporal route** (English-seed only — the protection-log convention
  doesn't transfer to other Wikipedia editions): `06_harvest_temporal.py`
  (protection log, CT-coded areas) → `07_enrich_temporal.py` (batched,
  throttle-safe — Stage 2's per-article re-fetch 429-storms at ~1,000-article
  scale) → same `03_format_prompts.py`.
- **Translation** (`05_translate_review.py`, sonnet-5 via OpenRouter —
  *not* the legacy `translate_prompts.py`/GoogleTranslator, which is
  superseded/reference-only): translates either battery's English master into
  the other study languages, keeping `text_en_source` as a one-to-one lock and
  deriving the output prefix from the input stem so the two batteries never
  collide. Produces the canonical side-by-side review CSVs.
- **`positions{A,B}` is the load-bearing field** — the opposing-stance pair the
  boundary-tier design rests on; it's what always gets flagged `needs_review: true`.
- `topic_domain` is a **fixed nine-domain vocabulary** describing what an issue
  is *about* (not what task the model is asked to perform) — see `docs/PIPELINE.md`
  §3 for the full list. It replaces the legacy 8 task-type categories.
  `contention_score` (protection level + talk-page size) is carried as a
  covariate, never used to filter.
- Every prompt/record/review-row carries a `battery` field (`perennial` /
  `temporal`) — the two arms are run, translated, generated, and judged
  **separately** (settled decision, not pooled/size-matched) and this field is
  what keeps them separable through every downstream join.

### 2. Generation + annotation (`scripts/`)

```
sample_prompts.py       issue-level stratified subsample (stratified by
                        topic_domain, seeded, keeps matched boundary pairs
                        intact so A/B sides never split across the sample)
        v
generate_responses.py   queries the subject-model roster at temp=1.0
                        (deliberate — the subject condition, not a bug);
                        dispatches per-model by provider (OpenRouter vs.
                        per-model HF Inference Endpoint); carries full
                        provenance into every response record; skips
                        already-completed (prompt_id, language, model)
                        tuples, so it's safe to stop/restart or add models
                        incrementally
        v
annotation_pipeline.py  4-pass LLM-as-judge at temp=0 (judge model
                        google/gemini-2.5-flash-lite for passes 1-3):
                        Pass 1 engagement/refusal (1-5 + justification A-G,
                        always runs) -> Pass 2 ideology (skipped if
                        engagement >= 4) -> Pass 3 moral foundations (same
                        skip rule)
stance_coding.py        Pass 4: stance (-2..+2) on engaged boundary
                        responses only, judge model openai/gpt-oss-120b —
                        catches state-aligned pivots Pass 1 scores as
                        "engaged"
        v
run_pilot.py assemble   routes output into the R-contract file layout +
                        prompts_meta/ (writes `category` <- topic_domain
                        identity map so the R loader needs no schema change)
```

`run_pilot.py` orchestrates all of the above (`--stages sample generate
annotate assemble stance`, default "all"), keyed off one run directory
`annotations/<run_id>/`. `--dry-run` prints the exact call budget (read from
frozen battery files, not estimated) without spending anything. Sampling is
reproducible: `(battery, seed)` fully determines the issue set, recorded in
`prompts/sampled/<battery>_sample_manifest.json`.

The subject-model roster and supported languages are centralized in
`scripts/config.py` (`TEST_MODELS`, `ENDPOINT_MODELS`, `SUPPORTED_LANGUAGES`)
— this is the single place to add/remove a model or language; don't hardcode
either elsewhere. `ENDPOINT_MODELS` entries are appended to `TEST_MODELS` at
*import time* only if their endpoint-URL env var is set, so config.py must
load `.env` before that loop runs (see the comment in the file) — if you
change env-loading order, verify the endpoint roster still appears.

Output surfaces per run dir: `responses/<battery>_<lang>.jsonl`,
`ann/<battery>_<lang>.jsonl`, `annotations_all.jsonl` (regular tier,
`dataset_type="base"`), `annotations_<lang>_boundary.jsonl` (boundary tier),
`prompts_meta/test_prompts_<lang>.json` (R-shape metadata).

### 3. R analysis (`pipeline/`)

`01_data_loading.R` is the foundation — it reads `annotations/annotations_all.jsonl`,
derives `engaged`/`refused` (`engagement_code <= 3` / `>= 4`), the 5-point
`engagement_category`, and factor columns with fixed level orders (so
model/language always plot in the same order), and writes `data_clean.RData`,
which every one of `02..16_*.R` reads. It has been **patched for v2**
(`setwd()` → `here::here()`, run-dir input via `REFUSAL_RUN_DIR` env var
(default `annotations/pilot_v1`), 7-model factor levels, a join-collision fix
for `controversy_tier` — see `docs/ANNOTATION_RUNBOOK.md` for exact detail).
Scripts `02–16` have since had the same `here::here()` fix applied (verified:
0 of 23 carry the legacy hardcoded path). The Study A/B scripts
(`10`,`11`,`12`,`13`,`14`,`16`) additionally guard their inputs and
`quit(status=0)` with a SKIP message when those inputs are absent, so a
main-path run passes over them cleanly rather than erroring.

Run with: `REFUSAL_RUN_DIR=annotations/<run_id> Rscript pipeline/01_data_loading.R`,
then the numbered scripts in order (most read `data_clean.RData`, write to
`pipeline/figures/` and `pipeline/tables/`). `docs/R_PIPELINE_WALKTHROUGH.md` maps
what each of the 23 scripts does and which are core vs. optional/consolidatable
(several — `06`/`07`/`07b`/`06b` — investigate the same DeepSeek finding at
different rigor levels).

The **annotation contract** (`docs/ANNOTATION_CONTRACT.md`) is the interface
between Python annotation output and this R stage — if you touch the judge's
output schema, check that contract for what fields/joins R depends on.

## Working across the stack

- Prompt files (`prompts/{full,temporal}_prompts_<lang>.json`) are **frozen
  batteries** once reviewed (`needs_review: false`, a `frozen_at` stamp). Don't
  regenerate or hand-edit them; if a battery needs to change, that's a sourcing
  pipeline change (edit upstream, re-run, re-freeze), not a JSON patch.
  `data/` holds the intermediate sourcing artifacts (candidate lists, issue
  records) that feed those frozen files.
- Two seed-route battery families exist per the current session state:
  perennial + temporal, and (per `docs/REBALANCE.md`,
  `sourcing/run_rebalance.sh`) a rebalanced frame correcting region/topic skew.
  `docs/NEXT_STEPS.md`'s dated top block is authoritative over the rest of
  that document when they conflict — check the date against what you're
  about to do.
- Adding a subject model or language touches, in order: `scripts/config.py`
  → `sourcing/05_translate_review.py` (if a new language needs translation)
  → `pipeline/01_data_loading.R` factor levels — check `docs/ANNOTATION_RUNBOOK.md`
  for the exact list of R-side edits a roster change requires.
- `archive/` holds superseded pilot/probe artifacts (old annotations, sampled
  prompts) kept for reference — don't treat it as live pipeline input.
