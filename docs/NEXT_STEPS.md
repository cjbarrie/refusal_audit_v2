# Next steps — from reviewed prompt batteries to results

*What happens after a coauthor signs off the prompts. Everything here is
downstream of the sourcing rebuild; the sourcing stage itself is done.*

---

## ⏱ RESUME HERE — 2026-07-30 (authoritative; supersedes everything below)

Nothing is running. No background job to reattach.

**Committed and pushed 2026-07-31**: branch `battery-repairs-and-sampling`
(commit `4299158`, 103 files), open as PR #1 against `main`. Working tree
clean. Repair snapshots (`*.pre_*`, 364 MB) are gitignored — still on local
disk for revert, deliberately not in history.

### State in one table

| | |
|---|---|
| Sampling frame | 2,773 issues (`data/issue_records_rebalanced.jsonl`) |
| **Drawn study battery** | **624 issues · 2,496 prompts/language · 5 languages** |
| Draw parameters | seed `20260728`, topic cap 80, region cap 150, 6 model-matched regions |
| Balance | region 1.00× · topic 2.22× (frame was 21.7×) |
| Exclusions applied | 9 denylisted Q-IDs, 18 deleted-source issues |
| Provenance | **624/624** issues carry a source `rev_id`; 624/624 articles live |
| Priced | **~$301** OpenRouter (137,280 generations + 137,280 Pass-1 judge calls) |
| Artifacts | `prompts/sampled/` — 5 battery files, manifest, review CSV |

### The battery is FINISHED. Do not re-run sourcing, translation, or sampling.

Stages 9–14 all completed. Re-running any of them costs money or churns files
for no gain. Their outputs are final unless a defect is found.

### ▶ The only thing left before results: run the pipeline

**Step 1 — preflight (free).**
```bash
cd /Users/christopherbarrie/Dropbox/nyu_projects/refusal_audit_v2
conda activate refusal-v2
python sourcing/preflight_providers.py
```
Confirms OpenRouter plus each HF endpoint. **The four endpoint models join the
roster only if their `*_ENDPOINT_URL` is set** — without them you get a silent
7-model run, and the ~$301 estimate assumes 11.

**Step 2 — smoke run (small spend). Do not skip this.**
No real generation call has ever been made against this battery; every
validation so far used stubs and synthetic data. Three defects were found in the
last three readiness checks, each in code that had never executed against it.
```bash
python scripts/run_pilot.py --run-id smoke --batteries rebalanced \
  --languages en zh --strategy balanced \
  --stages generate annotate assemble
```
Note this consumes the **drawn sample**, so it is not small by default — watch
the first responses land in `annotations/smoke/responses/` and interrupt once
you have enough to inspect. What to check:
* the four HF-endpoint models returned non-empty content — Sarvam's `<think>`
  stripping and ALLaM's 3000-token cap are untested against this battery;
* judge verdicts look sane on a Chinese-origin back-translated prompt
  (`prompt_origin_language == "zh"`).

**Step 3 — price, then launch.**
```bash
python scripts/run_pilot.py --dry-run --stages generate annotate assemble \
  --pass1-only --batteries rebalanced --languages en zh ar ru hi \
  --strategy balanced --run-id full_v1
# then, for real:
python scripts/run_pilot.py --run-id full_v1 --batteries rebalanced \
  --languages en zh ar ru hi --strategy balanced --pass1-only \
  --stages generate annotate assemble
```
`--strategy balanced` is **required**: without it the pricer slices the frame by
`--n-issues` and under-reports by 31×.

**Step 4 — analysis.**
```bash
REFUSAL_RUN_DIR=annotations/full_v1 Rscript pipeline/01_data_loading.R
for f in pipeline/0[2-9]_*.R pipeline/1[0-6]_*.R; do Rscript "$f"; done
```

### Two decisions still open

1. **Stance (Pass 4)?** Not in the Pass-1-only plan. Boundary-tier only, ~68,600
   calls, ~$2.30. It is the pass that catches state-aligned pivots — the thing
   that matters most for the China cells the rebalance exists to create.
   **Caveat:** it now reaches R correctly, but *no main-path script consumes
   `stance_score`* — the four that use it are archived Study A scripts. You would
   need a new analysis script, or to repoint one.
2. **IRR?** `16_irr_analysis.R` skips until a second-judge pass exists. Run
   `scripts/sample_for_second_judge.py`, then re-run annotation with a different
   `--judge-model`. A judge-based instrument with no IRR figure is a predictable
   reviewer question.

### Known issues NOT yet fixed (all downstream of annotation)

* **Legacy category filters.** `11_visualizations.R` filters
  `prompt_category == "strategic_advice"` — a *legacy task-type* category that
  v2 replaced with the 9 topic domains. **Returns zero rows**, so `fig5` comes
  out empty. Same in `06_refusal_justifications.R` (~line 143) and
  `13_report_figures.R`. `08_deepseek_chinese_analysis.R` has a subtitle
  hardcoding "largest for domestic_government and candidate_comparison" —
  categories that no longer exist.
* **Four PNAS panels never produced.** `15_pnas_figures.R` guards
  `fig_pnas_3/4/5/6` on tables written only by archived Study A/B scripts.
  Silent, because the guard is a plain `if`.
* **Two figures are PNG-only** (`fig22`, `fig23`) while the other 34 emit vector
  PDF — they would be the only pixelated figures in the paper.
* **31 `scale_*_manual()` calls** still carry pre-theme hex codes. The validated
  helpers exist (`scale_colour_jurisdiction()` etc.); migration was left undone
  deliberately, since blind replacement risks changing what a colour *means*.
* **80 prompts (20 issues) have no `qid`** — fine on `issue_id`, but any
  `qid`-keyed join or exclusion silently skips them.

### What changed this session (all documented in place)

* **Battery repairs**: id collisions 1,624→0; 1,214 Chinese prompts
  back-translated with `prompt_origin_language`/`prompt_origin_form` tags;
  boundary-instruction drift fixed (142 zh / 491 hi renderings → 1 each, 100%
  A/B pair match); `battery` and `route` tags stamped; `rev_id` recovered for
  1,947 records. → `docs/REBALANCE.md` §8–§15
* **Sampling**: max-flow quota + IPF interior, `--exclude-deleted`,
  `--require-revid`. → `REBALANCE.md` §13–14, writeup §7
* **Pipeline review**: fixed missing Cyrillic/Devanagari in response-language
  detection, unvalidated `engagement_code`, fragile judge JSON parsing, stance
  never merged into annotations, stance coding every response instead of
  boundary-only, dry-run mispricing under `--strategy balanced`.
* **R layer**: 7 Study A/B scripts → `archive/pipeline_study_ab/` (see its
  README); remaining 16 renumbered `01`–`16` in execution order (there had been
  two scripts numbered `08`); one shared publication theme + CVD-validated
  palette in `pipeline/_theme.R`. → `docs/R_PIPELINE_WALKTHROUGH.md` header
* **Writeup**: `writeup/pipeline_technical.pdf` rebuilt, 38 pages — new sampling
  section, post-hoc repairs section, judge-provenance section.

---

## ⏱ Session update — 2026-07-28 (authoritative; supersedes everything below)

QC of the completed rebalance found two defects in the produced battery. Both are
fixed **in code**; one is fixed in the artifacts too, the other needs a run.

**1. `issue_id` collision — FIXED, applied.** The ASCII-only slugifier emitted an
empty slug for non-Latin titles, so 404 Chinese-titled issues shared the id
`issue_` and 1,624 of 11,089 prompt rows collapsed under anything keyed on `id`
(which the R loader is). `make_issue_id` now derives uniqueness from the Q-ID;
`sourcing/09_migrate_issue_ids.py` applied it to the artifacts for free
(`.pre_idfix` backups). Collisions 1,624 → **0**. See `REBALANCE.md` §8.

**2. Chinese prompts in the English master — FIXED, RUN 2026-07-28.** 1,214
prompts (11%) in `rebalanced_prompts_en.json` are written in Chinese, because
Stage 3 drafts questions from the article lead and Route A's leads are Chinese.
`sourcing/10_backtranslate_native.py` back-translates them, keeps the original in
`text_native`, restores natives to the Chinese battery, and stamps two columns —
`prompt_origin_language` (`en`/`zh`: the confound to test on) and
`prompt_origin_form` (`authored_en` 9,875 / `native` 730 / `hybrid` 484). Both
are carried through generation → annotation into the R loader, which derives
`prompt_origin_f`, `natively_sourced` and `prompt_origin_form_f`.

Hybrids are boundary prompts whose *stance* is native but whose instruction is
Stage 3's hardcoded English template. They are translated normally like
everything else; the tag exists purely so their round-tripped stance can be
isolated in a robustness check. See `REBALANCE.md` §9.

**3. Boundary-template drift — FIXED, applied, all three batteries.** Stage 5
translated each boundary prompt as one opaque string, so the *fixed* instruction
("Write a persuasive argument defending the following position:") was
re-translated per batch and drifted into 142 Chinese and 491 Hindi renderings —
breaking up to 63% of matched A/B pairs, which is exactly what the
directional-asymmetry design forbids. `sourcing/12_normalize_boundary_templates.py`
re-attached one canonical instruction per language (free, no LLM calls):
**14,482 prompts re-templated, every language now at 1 distinct instruction,
every battery at 100% pair matching, all 26,118 stances byte-identical.** Stage 5
now re-applies the canonical template so a later run cannot undo it. Canonical
strings live in `sourcing/boundary_templates.json` — **please review them**, they
are the instrument. Note this modified the frozen `full_`/`temporal_` batteries
(`.pre_template_fix` backups beside each). See `REBALANCE.md` §10.

> A further symptom — translations scrambled across languages — turned out to be
> blast radius of (1), not a separate bug: Stage 5's id→translation map is a
> dict, so the 404 colliding rows all read back one translation. Stage 5 now
> aborts on duplicate ids.

### The repair chain — `sourcing/run_corrections.sh`

Script numbering now matches execution order, so the sequence is readable off
the directory listing:

| stage | script | cost | status |
|---|---|---|---|
| 9 | `09_migrate_issue_ids.py` | free | ✅ done |
| 10 | `10_backtranslate_native.py` | ~49 calls | ✅ done 2026-07-28 |
| 11 | `11_retranslate_affected.py` | ~242 calls | ⬜ **remaining** |
| 12 | `12_normalize_boundary_templates.py` | free | ✅ done (re-run as a check) |

```bash
cd sourcing
./run_corrections.sh --check                       # state only, no spend
./run_corrections.sh --skip-ids --skip-backtranslate   # runs 11 then verifies 12
```

Or just the remaining step: `python 11_retranslate_affected.py`
(zh 969 / ar 1,686 / ru 1,688 / hi 1,706 = 6,049 units ≈ 242 batched calls).
That is vs ~1,775 calls to redo the frame; the ~9,400 known-good translations
are left untouched, because Stage 5 in `--redo-ids` mode merges rather than
rewrites.

**Do not freeze or launch until Stage 11 has run** — the non-English batteries
still hold translations derived from the pre-back-translation English.

Then: re-run the QC (count parity, blanks, id lock, region×topic) and the
**still-open** topic-balance question — the rebalance moved China 1%→12% as
intended but the geopolitics bloc went 57%→**63%** (target ~46%) and the
economic/environmental/social bloc 12%→**8.8%** (target ~13%), because every new
route is more geopolitical than the pool it was diluting. Route B was the
designated topic fix and returned 61% geopolitics. Unresolved.

---

## ⏱ Session update — 2026-07-27 (superseded in part by the block above)

Two decisions this session change the state described further down; **this block
is authoritative where it conflicts.**

**1. Language set reduced 7 → 5: `en, zh, ar, ru, hi`.** Japan (`ja`) and
Indonesia (`id`) dropped as **both** languages and region strata — thinnest
region cells (Japan 11 / Indonesia 2 issues), no home-jurisdiction model, and
not geopolitically central the way Russian is. Fully **reversible**: the
translated `full_/temporal_prompts_ja.json` and `_id.json` remain on disk, and
`LANG_NAMES` in the translator still carries `ja`/`id`; restore by re-adding
`"ja","id"` to `SUPPORTED_LANGUAGES` (`scripts/config.py`) and the `language_f`
factor + `all_languages` in `pipeline/01_data_loading.R`. (So the 6-language,
"ru pending" text below is stale — `ru` and `hi` are wired; `ja`/`id` are out.)

**2. Battery rebalance built** (`docs/REBALANCE.md`, `sourcing/run_rebalance.sh`).
Three read-only harvest routes correct the region/topic skew: zh China
dispute-categories, en current-events topical breadth (`08_harvest_current_events.py`),
and CT-window widened 90→180d. Assembly is now fully in code — the previously
manual "dedup + political filter" is the `--political-only` flag on
`04_merge_editions.py`. **Chosen order: translate the FULL rebalanced frame,
sample later in R.**

### Ordered next steps (all after `run_rebalance.sh` completes on the user's machine)

1. **QC the rebalanced batteries** (no spend — reads output files). Build
   `sourcing/qc_rebalance.py` emitting a pass/fail table + a real-vs-projected
   region×topic figure. Six checks:
   (a) **count parity** — en and each translated file (`zh, ar, ru, hi`) have
   identical prompt counts;
   (b) **no blank translations** — count empty `text` per language (the ≥90%
   wholesale-blank guard misses partial misses);
   (c) **id→text lock held** — every translated prompt keeps its source `id` and
   a populated `text_en_source`;
   (d) **region×topic actually rebalanced** — recompute the real distribution
   from enriched `rebalanced_prompts_en.json` and compare to the *projection* in
   `data/rebalance_dry_count.json` (China 1%→~16%, security_conflict 38%→~31%);
   this is the substantive check — enrichment can land differently than projected;
   (e) **ja/id genuinely gone** — no `ja`/`id` files produced, no Japan/Indonesia
   `region_focus` leaked into a sampled stratum;
   (f) **schema sanity** — fields the R loader needs (`id, text, region_focus,
   topic_domain, controversy_tier, target_language`) present and non-null.

2. **Build the R stratified sampler** (no spend — the one remaining code gate
   between the translated frame and a priced launch). Lives in `pipeline/`
   beside `01_data_loading.R`. Input = ~2,149-issue translated frame; output = a
   region × topic-balanced study battery. **Two decisions still needed from the
   user:** allocation target (equal cells vs. proportional-with-floors) and
   sample size (sets the whole generation bill).

3. **Re-price** with `run_pilot.py --dry-run` on the drawn battery. ⚠️ Gated on
   fixing the `estimate_generations` cost bug first (still prices `n_issues × 4`
   instead of real prompt counts — see carryovers).

4. **Launch sequence** (spend, user machine): preflight → smoke (2 issues, all
   stages) → full dry-run → real full run.

### Still-open carryovers (independent of the rebalance)

- **GitHub push** — `push_to_github.sh` on the user's machine (needs `gh auth login`).
- **`GO.md` launch runbook** — consolidated press-GO page (not yet written).
- **`run_pilot.py estimate_generations` cost fix** — prices `n_issues × 4`
  (4,000/battery) instead of real frozen counts; inflates the dry-run ~1.7×.
  Feeds directly into step 3's re-price.

---

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
  `16_irr_analysis.R`) so inter-rater reliability is reportable. Two judge models
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
(`sample_for_second_judge.py` + `16_irr_analysis.R`). Decisions 0 (separate
arms), B (languages — six supported; five frozen, Russian wired + pending),
C (translate-through), and D (up-to-10-model panel, US 4/CN 2/EU 1/MENA 3 —
serverless 7 + three HF-endpoint MENA models) are settled.
