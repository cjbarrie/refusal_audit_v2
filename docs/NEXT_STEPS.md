# Next steps — from reviewed prompt batteries to results

*What happens after a coauthor signs off the prompts. Everything here is
downstream of the sourcing rebuild; the sourcing stage itself is done.*

## Where we are — two frozen candidate batteries

The sourcing rebuild produced **two disjoint batteries** (English-sourced, then
translated into all five study languages) that share the identical enrich →
format → translate → review schema:

| battery | seed | issues | prompts (per lang) | languages | review sheet | figure |
|---|---|---:|---:|---|---|---|
| **Perennial** | `List of controversial issues` | 387 | 1,548 | en, zh, ja, id, ar (+ru pending) | `prompts/full_review_sheet.csv` + `canonical_review_all_languages.csv` | `docs/fig_full_battery.png` |
| **Temporal** | protection log, last 90 days | 799 | 3,199 | en, zh, ja, id, ar (+ru pending) | `prompts/temporal_review_en.csv` + `canonical_review_temporal_all_languages.csv` | `docs/fig_temporal_battery_en.png` |

**Six supported languages** (`SUPPORTED_LANGUAGES = [en, zh, ja, id, ar, ru]`).
Five are translated and frozen; **Russian (`ru`) is wired but not yet
generated** — run `python sourcing/05_translate_review.py --languages ru` on
both batteries (needs `OPENROUTER_API_KEY`) to produce `full_prompts_ru.json` /
`temporal_prompts_ru.json` and merge the `text_ru` column into the canonical
review CSVs (merge is incremental — existing languages are not re-translated).

Per-language prompt files: `full_prompts_{en,zh,ja,id,ar}.json` (+`_ru` pending)
and `temporal_prompts_{en,zh,ja,id,ar}.json` (+`_ru` pending). Translations produced by
`sourcing/05_translate_review.py` (sonnet-5); `text` is the translation,
`text_en_source` keeps the English original.

They are **fully disjoint on Wikidata Q-ID** (zero overlap): perennial surfaces
long-contested topics (civil-rights-led mix), temporal surfaces what is being
fought over *right now* (security_conflict dominates ~50%, region skews to live
conflict zones — Arab, India). The temporal route is **English-only at the
sourcing stage** — the protection-log seed does not transfer to other editions
(see `TEMPORAL_SOURCING.md`). Its prompts are, however, **translated into all
five study languages** (en/zh/ja/id/ar) for annotation, exactly as the
perennial battery is — so both arms are symmetric at delivery.

**Decision 0 — SETTLED: run the two batteries as separate arms.**
"Perennial vs. contemporary" is a design factor, not a pooled variable. Each
battery is reviewed, translated, generated, and judged as its own experiment,
and every record carries a `battery` field (`perennial` / `temporal`) so the two
never blur through a downstream join. (The alternatives considered and rejected:
*pooling* — the temporal set's ~50% security_conflict skew would distort pooled
domain means; *size-matching* — discards most of the temporal harvest. Separate
arms keeps both at full scale and makes the contemporary-vs-perennial contrast a
clean analysis axis.)

Provenance is already stamped on both frozen batteries:

| field location | perennial value | temporal value |
|---|---|---|
| top-level `battery` + per-prompt `battery` in the `.json` | `perennial` | `temporal` |
| `battery` column in the review `.csv` | `perennial` | `temporal` |
| `battery` on every `issue_records_*.jsonl` record | `perennial` | `temporal` |

The rest of this document is written to run **either** arm — the steps are
identical; only the input file names change. Run them independently (or in
parallel); the `battery` field keeps the outputs separable at analysis time.

The pipeline from here is the **unchanged legacy downstream**: translate →
generate → judge → analyze. The only new work is (a) wiring the reviewed battery
into it, (b) refreshing the model panel, and (c) three small edits to the R entry
script so it accepts the new `topic_domain` field and any new models. No new
methodology is required to get first results — the matched-pair and topic-domain
gains ride through the existing machinery.

```
 {full,temporal}_review ──►  STEP 0  freeze reviewed battery
   .csv  (signed off)          │
                                  ▼
                          STEP 1  translate  (05_translate_review.py, sonnet-5)  [DONE]
                                  │   en → zh, ja, id, ar  (text_en_source lock)
                                  ▼
                          STEP 2  refresh model panel  (config.py, 7-model panel)  [DONE]
                                  │
                                  ▼
                          STEP 3  sample + generate  (sample_prompts.py, run_pilot.py, generate_responses.py)
                                  │   prompt × language × model  → annotations/<run>/responses/*.jsonl
                                  ▼
                          STEP 4  judge / annotate  (annotation_pipeline.py + stance_coding.py)
                                  │   3 passes + stance  → annotations/<run>/*.jsonl
                                  ▼
                          STEP 5  patch R entry script  (01_data_loading.R)  [DONE]
                                  │   setwd → here::here; run-dir inputs; model levels; join-collision fix
                                  ▼
                          STEP 6  run analysis  (pipeline/02..16_*.R)  → plots/ tables/
                                  ▼
                          STEP 7  new analyses the rebuild enables
                                  (directional asymmetry; refusal-vs-contention)
```

---

## Decisions to lock at the review gate

These should be settled *during* review, because they change what gets
translated and generated (and therefore the cost):

| # | Decision | Recommended default |
|---|---|---|
| 0 | **Battery relationship** — separate arms / pool / size-match | **SETTLED: separate arms** (see above). `battery` field carries the arm label through every stage |
| A | **Final scale** — perennial: keep all 387 issues (1,548 prompts) or prune; temporal: keep all 799 (3,199) or sample | Prune during review to issues whose positions are clean and whose regional/domain spread you want; ~150–250 issues per battery keeps generation cost sane while preserving coverage. For temporal, sampling also lets you tame the security_conflict skew |
| B | **Languages** — which of en/zh/ja/id/ar/ru to run | **Five DONE, Russian wired + pending.** Both batteries exist in en + zh/ja/id/ar translations (`sourcing/05_translate_review.py`, sonnet-5). `ru` is the 6th supported language (`config.SUPPORTED_LANGUAGES`) and the translator/merge are wired for it; running `--languages ru` (needs `OPENROUTER_API_KEY`) produces `{full,temporal}_prompts_ru.json` + merges `text_ru`. The temporal *seed* is English-only, but delivery is symmetric with perennial |
| C | **Cross-lingual method** — translate-through vs Wikidata-native entity rendering | Translate-through for both batteries (preserves the one-to-one language lock); reserve Wikidata-native for a dedicated entity-swap arm |
| D | **Model panel** — which subject models, which jurisdictions | See Step 2 |

---

## Step 0 — Freeze the reviewed battery

**Goal:** turn the signed-off review sheet back into a frozen prompt file with a
version stamp, so every downstream artifact traces to an immutable input.

- Apply the reviewer's edits (position wording, drops) from the review sheet
  (`full_review_sheet.csv` for perennial, `temporal_review_en.csv` for temporal)
  back onto the corresponding prompts file (`full_prompts_en.json` /
  `temporal_prompts_en.json`).
- Set `needs_review: false` and stamp a `frozen_at` date + a battery version
  (e.g. `v2.0-frozen-perennial`, `v2.0-frozen-temporal`).
- Keep the provenance fields (`issue_id`, `qid`, `contention_score`,
  `position_side`, `topic_domain`, and — temporal only — `ct_area`,
  `last_protection`) — the analysis will group on them.

**Output:** the frozen English masters — `prompts/full_prompts_en.json`
(perennial) and `prompts/temporal_prompts_en.json` (temporal), each with
`needs_review: false` and a `frozen_at` / battery-version stamp.
The `battery` field (`perennial` / `temporal`) is already stamped on every
prompt, review row, and issue record — carry it through the freeze so the two
arms stay separable downstream.

---

## Step 1 — Translate — **DONE** (`sourcing/05_translate_review.py`)

**Goal:** produce the four non-English batteries from the frozen English master,
preserving the one-to-one `text_en_source` lock that makes *language* the clean
experimental knob.

This is **already complete for both batteries**. Translation is done by
`sourcing/05_translate_review.py` using **sonnet-5** (via OpenRouter) — *not* the
legacy `translate_prompts.py` / GoogleTranslator, which is superseded. Each
translated prompt sets `text` to the translation and keeps `text_en_source` as
the English original, plus `qid`/`topic_domain`/`battery` provenance.

- Files: `prompts/full_prompts_{zh,ja,id,ar}.json` and
  `prompts/temporal_prompts_{zh,ja,id,ar}.json`.
- Side-by-side review CSVs: `prompts/canonical_review_all_languages.csv`
  (perennial) and `prompts/canonical_review_temporal_all_languages.csv`
  (temporal) — every cell non-empty, zero identical-to-English.
- The matched-pair boundary directives were translated as a unit and verified
  symmetric across A/B sides.

To re-run: `python sourcing/05_translate_review.py --prompts
../prompts/full_prompts_en.json` (output prefix derives from the input stem, so
the two batteries never collide).

---

## Step 2 — Refresh the model panel — **DONE** (`scripts/config.py`)

**Goal:** run current models (the second improvement from the original scope).

`config.py` `TEST_MODELS` is a **7-model serverless panel** plus three
**HF-endpoint MENA models** (`ENDPOINT_MODELS`) appended at import time when
their `*_ENDPOINT_URL` env var is set — up to a **10-model jurisdiction panel**
(4-tuples of `display_name, model_id, jurisdiction, provider`):

| model | model_id / hub repo | jurisdiction | provider |
|---|---|---|---|
| gpt-5.1 | `openai/gpt-5.1` | US | openrouter |
| claude-opus-4.5 | `anthropic/claude-opus-4.5` | US | openrouter |
| gpt-4o | `openai/gpt-4o` | US | openrouter |
| grok-4.3 | `x-ai/grok-4.3` | US | openrouter |
| deepseek-chat-v3.1 | `deepseek/deepseek-chat-v3.1` | CN | openrouter |
| qwen3-max | `qwen/qwen3-max` | CN | openrouter |
| mistral-large-2512 | `mistralai/mistral-large-2512` | EU | openrouter |
| allam-7b | `humain-ai/ALLaM-7B-Instruct-preview` | MENA | hf-endpoint |
| falcon3-10b | `tiiuae/Falcon3-10B-Instruct` | MENA | hf-endpoint |
| jais-8b | `inceptionai/Jais-2-8B-Chat` | MENA | hf-endpoint |

Jurisdiction counts with all endpoints deployed: **US 4, CN 2, EU 1, MENA 3**.
The tuple carries a fourth `provider` field so `generate_responses.py` dispatches
OpenRouter models to `https://openrouter.ai/api/v1` (`OPENROUTER_API_KEY`) and
each MENA model to its **dedicated HF Inference Endpoint** (per-model
`*_ENDPOINT_URL`, `HF_TOKEN`). It auto-detects the served `model_id` per endpoint
via `GET /v1/models` and logs it per response so a refusal is attributable to a
known backend.

Notes on the roster: the retired `grok-4.1-fast` was replaced with `grok-4.3`
(`grok-4.5` is region-locked for the current OpenRouter account); `qwen3-max`
(CN) and `mistral-large-2512` (EU) broadened the panel beyond the legacy
US-heavy five; **ALLaM (SDAIA/HUMAIN, Saudi), Falcon3 (TII, UAE) and Jais
(G42/Inception, UAE) form the MENA developer arm**, each self-hosted on a
dedicated HF Inference Endpoint.

- **MENA models have no serverless provider:** ALLaM, Falcon3, and Jais have no
  OpenRouter or HF-router serverless endpoint (verified), so they are served via
  dedicated HF Inference Endpoints (TGI). The former serverless MENA candidates
  Fanar (QCRI) and SILMA were **removed** — the MENA arm is now endpoint-only.
  Deploy recipe: `docs/MENA_HF_ENDPOINT_INTEGRATION.md`.
- **`HF_TOKEN` + the three `*_ENDPOINT_URL` vars are required** for the MENA arm.
  Without them, the 7 OpenRouter models still run and the endpoint models are
  simply not added to the roster (no per-row errors). Confirm all paths with
  `python sourcing/preflight_providers.py`.
- The **Study A jurisdiction panel** (`study_a_jurisdiction_panel.py`) is a
  separate, larger roster and has **not** yet been refreshed — do that only if
  Study A is run.

---

## Step 3 — Sample + generate responses (`scripts/sample_prompts.py`, `run_pilot.py`, `generate_responses.py`)

**Goal:** collect one response per (prompt × language × model). Generation
temperature stays at **1.0** (deliberate — it is the subject condition, not a
bug to fix). The wiring is **built and validated end-to-end** (sample → generate
→ annotate → assemble → R load, tested against a synthetic run dir); launching
the real run is the remaining trigger, because it spends the OpenRouter key.

- **Subsample first** (for a pilot). `sample_prompts.py` draws an *issue-level*
  stratified subsample (whole issues, so matched boundary pairs stay intact),
  stratified by `topic_domain`, seeded (`--seed 20260712`) for reproducibility.
  The current pilot config is **20 issues per battery ≈ 160 prompts**. Non-en
  editions are filtered to the same issue set so all five languages stay aligned.
- **Drive with `run_pilot.py`.** Stages `sample,generate,annotate,assemble`
  (default "all"), keyed off a run dir `annotations/<run_id>/`. `--dry-run`
  prints the call budget. Example:
  `python run_pilot.py --run-id pilot_v1 --stages sample generate annotate assemble`.
- **`generate_responses.py`** reads the v2 prompt files (keyed on `topic_domain`,
  not the legacy `category`), loops the 7-model roster, and carries full
  provenance (`battery, controversy_tier, qid, issue_id, region_focus,
  position_side, contention_score, topic_domain`) into every response record.
  It skips already-completed `(prompt_id, language, model)` tuples — safe to
  stop/restart and add models incrementally.
- Cost scales as `prompts × languages × models`. Pilot budget (~5,600
  generations + ~14,900 judge calls on flash-lite + ~2,800 stance) prints from
  `--dry-run`.

**Output:** `annotations/<run_id>/responses/<battery>_<lang>.jsonl`.

---

## Step 4 — Judge / annotate (`scripts/annotation_pipeline.py` + `stance_coding.py`)

**Goal:** score every response for engagement/refusal, ideology, moral framing,
and (on engaged boundary responses) directional stance. Judge temperature = **0**.

- **Passes 1–3** (`annotation_pipeline.py`, judge `google/gemini-2.5-flash-lite`):
  Pass 1 engagement/refusal (1–5 + A–G justification, always runs); Pass 2
  ideology (4 dims, skipped when engagement ≥ 4); Pass 3 moral foundations (same
  skip rule).
- **Pass 4 stance** (`stance_coding.py`, judge `openai/gpt-oss-120b`): −2..+2
  stance toward the prompt's embedded claim, on engaged boundary responses. This
  is the pass that catches state-aligned pivots that Pass 1 scores as "engaged".
- **IRR:** run the second-judge sample (`sample_for_second_judge.py` +
  `08_irr_analysis.R`) so inter-rater reliability is reportable. Two judge models
  are in play (Gemini for 1–3, gpt-oss for stance) — document both.
- Merge to `annotations/annotations_all.jsonl`.

**Output:** `annotations/*.jsonl`, `annotations_all.jsonl`.

---

## Step 5 — Patch the R entry script (`pipeline/01_data_loading.R`)

**Goal:** make the R gatekeeper run on this machine and accept the rebuilt
battery. `01_data_loading.R` is **now patched and validated** (run against a
synthetic run dir in the exact pilot output layout). Four edits landed:

1. **Path — DONE.** Hardcoded
   `setwd("/Users/solomonmessing/workspace/aligned_to_whom/refusal_audit")`
   replaced with `setwd(here::here())` (adds a `library(here)` dependency).
2. **Run-dir inputs — DONE.** The loader reads from a run dir set by env var
   (`REFUSAL_RUN_DIR`, default `annotations/pilot_v1`) and reads prompt metadata
   from `<run_dir>/prompts_meta/test_prompts_<lang>.json`.
3. **`category` ← `topic_domain` — handled in the assemble stage, not R.** The
   assemble stage writes the `prompts_meta/` files with `category` already set
   from `topic_domain` (identity map of the nine domains), so R's existing
   `category`/`prompt_category` grouping works unchanged. No R-side merge repoint
   was needed.
4. **Model factor levels — DONE.** Updated to the 7-model roster from Step 2.
5. **Join-collision fix — DONE.** The v2 annotation records now carry
   `controversy_tier` via provenance, which also exists in the metadata; the
   metadata copy is imported as `meta_controversy_tier` to avoid a `.x/.y` join
   collision, and the drop-unmatched filter keys off `category`. Without this the
   final `filter()` errored with `object 'controversy_tier' not found`.

**Output:** `pipeline/data_clean.RData` (the object every 02–16 script reads).

> The other R scripts (02–16) still carry a hardcoded `setwd(...)` per the legacy
> repo. Only `01_data_loading.R` has been fixed. Fix 02–16 the same way (or add a
> small `pipeline/_setup.R` that all scripts source) before running the full
> analysis — mechanical, flagged in `MANIFEST.md`.

---

## Step 6 — Run the analysis (`pipeline/02..16_*.R`)

**Goal:** regenerate the engagement, ideology, refusal-justification, and
jurisdiction figures/tables on the new data.

- Run in order. Most scripts read `data_clean.RData` and write to `plots/` and
  `tables/`.
- Expect the topic-domain swap to change the category-facet plots (nine domains
  instead of eight task types) — check axis labels and any hardcoded category
  strings in the plotting scripts.

**Output:** `pipeline/plots/*.pdf`, `pipeline/tables/*.csv`.

---

## Step 7 — New analyses the rebuild unlocks

These are the payoff of the sourcing changes — worth building as new R scripts
rather than shoehorning into the legacy ones:

- **Directional refusal asymmetry (the headline new capability).** Every boundary
  issue now has a matched A/B pair from an identical template. For each
  (model × issue), compare refusal on side A vs side B. A model that argues one
  side but refuses the other reveals directional political behavior the legacy
  single-directive design could not see. Aggregate asymmetry by `topic_domain`
  and by `region`.
- **Refusal vs. contention.** `contention_score` is carried as a per-prompt
  covariate. Test whether refusal rises with how fought-over the underlying
  Wikipedia page is — a validation that the sourcing signal tracks real-world
  contention.
- **Refusal by topic domain × jurisdiction.** With domains as a clean substantive
  axis, ask whether (e.g.) China-developed models refuse `territorial_sovereignty`
  and `governance_democracy` disproportionately, versus US/EU models on
  `social_moral` or `civil_rights_liberties`.
- **Perennial vs. contemporary (temporal battery).** If both batteries run
  (Decision 0), test whether refusal behavior differs on issues contested *right
  now* versus *long-standing* controversies — holding topic domain and
  jurisdiction fixed. The temporal battery's recency (`last_protection` date) and
  CT-area (`ct_area`) are per-issue covariates for this. A model more cautious on
  live conflicts than on settled debates is a distinct, publishable finding the
  perennial-only design cannot surface.

**Output:** new `pipeline/17_asymmetry.R`, `18_contention.R`, `19_temporal.R`,
and their figures.

---

## Critical-path summary

Steps 1, 2, and 5 are **done** (translation, model panel, R loader). The
remaining minimum to get first numbers is **Step 3 (sample + generate)** and
**Step 4 (judge)** — both spend the OpenRouter key, and both are wired,
validated end-to-end, and waiting only on a launch trigger. Their cost is driven
by how much you prune/sample at the review gate. Step 7 is where the rebuild
earns its keep and should be scoped once first results confirm the battery
behaves.

**Open decisions before launch:** final scale / sample size (A — a 20-issue
pilot config exists), stance (Pass 4) scope (all five languages vs English-only;
keep `gpt-oss-120b` or switch), and inter-rater-reliability scope
(`sample_for_second_judge.py` + `08_irr_analysis.R`). Decisions 0 (separate
arms), B (languages — six supported; five frozen, Russian wired + pending),
C (translate-through), and D (up-to-10-model panel, US 4/CN 2/EU 1/MENA 3 —
serverless 7 + three HF-endpoint MENA models) are settled.
