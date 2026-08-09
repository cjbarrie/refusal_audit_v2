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
              script reads; 10-14 estimate, 20-21 plot, 30 accepts, 40 describes.
              One driver: make_release.R
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
                        always runs, 100% coverage) -> Pass 2 ideology
                        (skipped if engagement >= 4) -> Pass 3 moral
                        foundations (same skip rule). Passes 2/3 are OFF by
                        default (`--all-passes` opts in) and support
                        ISSUE-level subsampling via `--pass23-subsample FRAC`
                        / `--pass23-seed`; the draw is frozen in
                        `<run_dir>/pass23_subsample.json` and REUSED across
                        languages and resumes, so every language annotates the
                        same issues. See docs/SLANT_SUBSAMPLE.md.
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

**Estimation and plotting are separate, and must stay separate.** `11_`–`14_`
fit models and write tidy tables to `pipeline/estimates/canonical/`;
`20_figures_main.R` and `21_figures_extended.R` read those tables and draw,
fitting nothing — and may not write a canonical table either, or the table
exists only when the artwork is rebuilt.

**The canonical layer is what the paper reports.** Read
`docs/CANONICAL_ANALYSES.md` before touching any of it — it is the spec, not a
summary. The earlier v1 and v2 estimand layers are **superseded and archived**
under `pipeline/archive/`; `pipeline/archive/README.md` maps every archived file
to its replacement and lists what was deliberately not carried forward. Don't
run archived scripts to produce new results — they overwrite the historical
`e`-series CSVs in place.

The numbering encodes the manuscript structure:

| range | role | scripts |
|---|---|---|
| `01`–`02` | **inputs** | `01_data_loading.R` (builds `data_clean.RData`), `02_judge_reliability.R` (panel reliability `e23`–`e28`, feeds `c17`) |
| `10`–`14` | **estimation** | `10_canonical_common.R` (sample, nested weights, multiplicity-preserving bootstrap, shared `gcomp`), `11_canonical_home.R` → `c02`–`c07`, `12_canonical_language_framing.R` → `c08`–`c11`, `13_canonical_content.R` → `c12`–`c16`, `14_canonical_judge_uncertainty.R` → `c17`–`c17d` |
| `20`–`21` | **figures** | `20_figures_main.R` → `Fig1`–`Fig3` (manuscript), `21_figures_extended.R` → `ED1`–`ED5` (Extended Data) |
| `30` | **tests** | `30_acceptance.R` → `c01b`, non-zero exit on failure |
| `40` | **appendix descriptives** | `40_appendix_descriptives.R` → `a01`–`a04` |

**One driver**: `CANONICAL_RUN_ID=<id> Rscript pipeline/make_release.R`. It runs
inputs → reliability → estimation → appendix → figures → manifest → acceptance →
figure audit, builds into an immutable `pipeline/releases/<id>/`, and promotes to
the live directories only if every check passes. `run_all.R` and
`run_canonical.R` were removed: `run_all.R` called itself the analysis driver
while excluding every canonical script, and its `--figures` mode selected a
stage that no longer existed, so it ran nothing and exited 0.

Four rules the canonical layer depends on, all checked mechanically:
* the **issue-cluster bootstrap must label each draw** (`bootstrap_issue_instance`),
  so a resample that draws one issue twice keeps the copies distinct;
* the **canonical outcome is one named judge**, with the rest of the panel
  reported as an instrument-sensitivity *envelope* (`c17b`) that is never pooled
  with a bootstrap interval and never called a confidence interval — and, since
  the judges label the same responses, the judge-minus-canonical difference
  (`c17d`) is bootstrapped **paired**, inside each replicate, never by
  differencing two marginal intervals;
* **`gcomp()` lives in `10_canonical_common.R`** and is shared by `11` and `14`,
  so a judge-sensitivity result can never be a specification difference;
* `flush_diag()` replaces only the **(run, label)** pairs it recomputed — dropping
  the whole run made each part wipe the previous part's diagnostics.

`01_data_loading.R` is the foundation — it reads `annotations/annotations_all.jsonl`,
derives `engaged`/`refused` (`engagement_code <= 3` / `>= 4`), the 5-point
`engagement_category`, and factor columns with fixed level orders (so
model/language always plot in the same order), and writes `data_clean.RData`,
which the estimation layer and `40_appendix_descriptives.R` read. It has been **patched for v2**
(`setwd()` → `here::here()`, run-dir input via `REFUSAL_RUN_DIR` env var
(default `annotations/pilot_v1`), 7-model factor levels, a join-collision fix
for `controversy_tier` — see `docs/ANNOTATION_RUNBOOK.md` for exact detail).
The appendix scripts have since had the same `here::here()` fix applied, and
they guard their inputs and `quit(status=0)` with a SKIP message when those
inputs are absent, so a run passes over them cleanly rather than erroring.
(A note that used to sit here referred to "Study A/B scripts `10`–`16`". Those
scripts are not in this repo, and `10`–`14` now mean the canonical estimation
layer — do not read the old numbering into the new one.)

Run with:

```bash
CANONICAL_RUN_ID=<id> Rscript pipeline/make_release.R   # the whole thing
CANONICAL_RUN_ID=<id> Rscript pipeline/make_release.R --no-promote   # build + check only
Rscript pipeline/audit_figures.R                        # the figure gate on its own
```

`docs/R_PIPELINE_WALKTHROUGH.md` maps what each script does; its dated top block
is authoritative over the rest of that file.

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
  `archive/pipeline_slant/` is the *pre-trim* slant analysis; the live slant
  path is `pipeline/13_canonical_content.R` + FIG3, so don't reintroduce the
  archived scripts alongside it.
- **The canonical estimand layer** (`docs/CANONICAL_ANALYSES.md`) reports three
  separated families and is what the paper quotes: **Part 1 home** (descriptive
  `c02` *and* standardized `c04`, never collapsed into one number) · **Part 2
  language + framing** (paired within `model × prompt_id` and
  `issue × model × language`) · **Part 3 content** (conditional on engagement).
  * **The standardized contrast must never be described as causal, a
    difference-in-differences, or a within-issue effect.** `home` is a fixed
    property of an issue's region; nothing randomises it. Those strings are
    banned — `30_acceptance.R` (test E1) fails the build on an
    unnegated use anywhere in the canonical tables.
  * `General` is a THIRD region position, never folded into `away`.
  * Every bootstrap resamples **whole issues**, labels each draw, and refits
    inside the replicate.
  * Ideology and moral-foundation tables are **conditional on engagement** and
    must say so; ideology additionally carries a weak-reliability warning.
  * ~2 h runtime; built by `pipeline/make_release.R`, which is the only driver.
- **Multi-judge reliability panel** (`docs/MULTI_JUDGE_PLAN.md`). Every
  annotation record carries `judge_model` / `judge_prompt_version` /
  `annotation_run_id`. `run_pilot.py --judge-panel [MODEL ...]` annotates the
  same responses with additional judges into `<run_dir>/panel/<judge>/`, and
  assemble emits the long-format `annotations_panel.jsonl`.
  **`annotations_all.jsonl` keeps its exact contract**, so the panel is purely
  additive and `01_data_loading.R` never changes. Reliability lives in
  `02_judge_reliability.R`; the per-judge estimate envelope lives in
  `14_canonical_judge_uncertainty.R` (`c17b`).
  Two hard-won operational rules:
  * **Judge suitability cannot be read off a model card.** Two candidates passed
    every specification check (structured outputs, reasoning disabled, decent
    quality index) and still failed to measure the construct — one flagged
    refusal at 1.76% against the anchor's 6.5%. Bake off candidates on a pilot
    slice and select on measured recall/α, never on specs.
  * **Never use a judge whose reasoning is `mandatory: true`** (e.g.
    `openai/gpt-oss-*`): reasoning tokens bill as output and cannot be turned
    off. The judge client sets `reasoning: {enabled: false}`, a 90s timeout and
    its own retry/backoff — a run once hung 2h19m with no timeout when a
    provider started returning null payloads.
- **Slant (passes 2/3) covers a 25% issue subsample, not the whole run.** Any
  new slant quantity must filter on `slant_eligible & has_slant` and is
  **conditional on engagement** (passes 2/3 skip refusals by design). Its
  primary tables are **English-only** because `13_canonical_content.R` fixes
  `lang == "en"`. The roster argument that used to justify this is stale: in the
  completed run all 11 models answer in all five languages, and slant coverage is
  complete for English *and Hindi* (only Russian is genuinely short, at 68%).
  `c12b` marks Hindi eligible on a coverage-only rule that the estimator does not
  act on — see `docs/CANONICAL_ANALYSES.md` §9. Pooling languages would
  confound slant with roster composition. `docs/SLANT_SUBSAMPLE.md` is
  authoritative; `docs/ANNOTATION_TRIM_FULL_RUN.md` predates it and is
  superseded on anything touching passes 2/3.
- `run_pilot.py --stages assemble` writes its output surfaces in `"w"` mode, so
  it must be given the **right `--batteries`** (this run: `rebalanced`, not the
  `perennial temporal` default). A mismatch used to truncate a complete
  `annotations_all.jsonl` to zero rows; assemble now refuses to write an empty
  file and names the batteries it found instead.

## Figure output policy — PNG ONLY

Every figure in `pipeline/figures/` is a **600 dpi PNG and nothing else**. No
PDF, no SVG, no EPS. Enforced in three places, all of which must stay true:

1. `pipeline/_theme.R::save_fig()` is the only sanctioned writer and emits PNG
   only. Do not add a vector branch, a `device =` argument, or a second format.
2. No script in `pipeline/` may call `ggsave()` directly.
3. `pipeline/audit_figures.R` **fails** if any non-PNG file appears in
   `pipeline/figures/`.

Multi-format export was tried and removed twice: the formats drifted apart
(different fonts, different metrics) and stale files from superseded designs
accumulated in the directory. One writer, one format.

**The figures directory holds exactly what the manuscript ships**, in two
subdirectories: `figures/main/` (`Fig1`–`Fig3`, main text) and
`figures/extended/` (`ED1`–`ED5`, Extended Data). The obsolete `figures/canonical/`
and `figures/appendix/` trees must not exist at all. `audit_figures.R` fails on
anything else in there, in either direction — a missing expected figure *or* a
stale extra one. That check exists because 23 PNGs from superseded scripts sat
in the directory looking current for weeks.

Three further rules the audit enforces mechanically:

* **Every figure is two-column (183 mm) and one of three approved heights**
  (85 / 125 / 165 mm, `H_WIDE`/`H_STD`/`H_TALL` in `_theme.R`). No one-column
  variants, no `_1col`/`_2col` duplicates, and no script picks its own
  dimensions. The audit checks the pixel width *and* the `pHYs` resolution
  chunk — a large raster with no `pHYs` is placed at 72 dpi by a journal's
  layout software.
* **No titles, subtitles or captions inside a PNG.** Panel letters, axis
  labels, tick labels, category names, facet headings, compact legends and
  direct numeric labels only. Captions live in
  `docs/CANONICAL_FIGURE_LEGENDS.md`, the single authoritative caption
  document. `tag_only()` blanks the title slots and the audit fails on any
  `title=`/`subtitle=`/`caption=` in a figure script.
* **A figure script may not write a canonical table.** `20`/`21` read tables and
  fit nothing; if a plotting script is the sole producer of an output, the
  output exists only when the artwork is rebuilt.
