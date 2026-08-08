# MANIFEST — provenance of every file in refusal_audit_v2

Legacy repo referenced: `../refusal_audit` (reference-only, not modified).

## Downstream machinery (carried from legacy, adapted for v2)

These are the parts of the pipeline downstream of sourcing. The core judge
logic is carried over so audit results stay comparable across the two repos;
several scripts were adapted to the v2 prompt schema (`topic_domain`,
`battery`, provenance passthrough).

### `scripts/` (Python)
| file | role | status |
|---|---|---|
| `generate_responses.py` | query subject models (temp 1.0); reads v2 `topic_domain`, loops the up-to-10-model roster, **dispatches per-model by provider** (OpenRouter vs per-model HF Inference Endpoint), carries provenance | adapted for v2 |
| `annotation_pipeline.py` | 4-pass LLM-as-judge (engagement, ideology, moral; Pass 4 stance separate); provenance passthrough to output records | adapted for v2 |
| `stance_coding.py` | Pass 4 stance coding on engaged boundary responses | carried |
| `config.py` | up-to-10-model jurisdiction panel (US 4/CN 2/EU 1/MENA 3) — 7 serverless 4-tuples + 3 HF-endpoint MENA models (`ENDPOINT_MODELS`, joined when `*_ENDPOINT_URL` set); 6 languages (`en/zh/ja/id/ar/ru`); OpenRouter + HF-endpoint config | rewritten for v2 |
| `sample_prompts.py` | issue-level stratified subsampler (by `topic_domain`, seeded, keeps matched boundary pairs intact) | **new (v2)** |
| `run_pilot.py` | end-to-end pilot driver: sample → generate → annotate → assemble, run-dir keyed, `--dry-run` budget | **new (v2)** |
| `study_a_jurisdiction_panel.py` | 15-model jurisdiction panel runner (roster not yet refreshed) | carried |
| `study_b_runner.py` | entity-swap + native-vs-MT mechanism experiments | carried |
| `translate_prompts.py` | legacy Google-translate EN → zh/ja/id/ar — **superseded by `sourcing/05_translate_review.py`** (sonnet-5); kept for reference only | superseded |
| `sample_for_second_judge.py` | IRR: sample for a second judge model | carried |
| `validate_data.py` | data integrity checks | carried |
| `env_utils.py` | .env / API-key loader | carried |

> Note: this environment sets `PYTHONSAFEPATH=1`, so entry scripts
> (`generate_responses.py`, `annotation_pipeline.py`, `run_pilot.py`) bootstrap
> their own directory onto `sys.path` (two lines near the top) for sibling
> imports.

### `pipeline/` (R)
The R analysis layer. Since the canonical revision this is `01`, `02`, `10`–`14`, `20`–`21`, `30`, `40`, plus `_theme.R`, `make_release.R`, `audit_figures.R` and `tests_synthetic.R`; the superseded scripts named below live under `pipeline/archive/` with a README per group. See `docs/R_PIPELINE_WALKTHROUGH.md`.
`01_data_loading.R` has been **patched for v2 and validated** (portable
`here::here()`, run-dir env-var inputs, 7-model factor levels, provenance
join-collision fix — see `docs/ANNOTATION_RUNBOOK.md`). Scripts **02–16 still
carry the hardcoded `setwd("/Users/solomonmessing/...")`** and must be fixed the
same way before the full analysis runs (open task).

## Built fresh in this repo (the new sourcing stage)
| file | role | status |
|---|---|---|
| `sourcing/01_harvest_controversial.py` | Stage 1: harvest a Wikipedia edition (`--lang`) -> candidate issues | built |
| `sourcing/02_enrich_issues.py` | Stage 2: enrich each issue into a structured record (concurrent, per-edition, carries provenance) | built |
| `sourcing/03_format_prompts.py` | Stage 3: format issue records into matched regular + boundary prompts | built |
| `sourcing/04_merge_editions.py` | Stage 4: union per-edition records, dedupe on Wikidata Q-ID | built |
| `sourcing/05_translate_review.py` | Stage 5: LLM-translate either battery (perennial or temporal) into zh/ja/id/ar + canonical side-by-side review CSV; output prefix derived from input stem so batteries never collide (replaces legacy Google-Translate) | built |
| `sourcing/06_harvest_temporal.py` | Stage 1b (alt seed): harvest *contemporary* contested issues from the protection log (CT-coded areas), schema-compatible with Stage 1 | built |
| `sourcing/07_enrich_temporal.py` | Stage 2b (temporal enrich): batch-fetch lead extracts (20 titles/call) then concurrent LLM extraction — the throttle-safe enricher for the ~1,000-article temporal seed (Stage 2's inline per-article re-fetch 429-storms at that scale) | built + run |
| `sourcing/run_pipeline.py` | one-command driver: harvest→enrich→format→merge, logs to `run.log`; LLM stages opt-in via `--enrich` | built |
| `sourcing/editions.yaml` | per-edition config (API host, list page, sections, dispute categories) | built |
| `docs/PIPELINE.md` | full design document | built |
| `docs/TEMPORAL_SOURCING.md` | temporal (protection-log) route rationale, method, 90-day run | built |
| `docs/NATIVE_SOURCING.md` | multi-edition (native-language) sourcing rationale + probe | built |
| `docs/REPRODUCIBILITY.md` | operational runbook to reproduce the whole sourcing stage | built |
| `docs/repro_check.md` | verification: committed pipeline vs. frozen English battery | built |
| `docs/NEXT_STEPS.md` | downstream runbook (translate → generate → judge → R) | built |
| `docs/probe_findings.md` | 10-issue probe assessment | built |
| `docs/ANNOTATION_CONTRACT.md` | the R pipeline's input contract (fields, join keys, file layout) the annotation stage must satisfy | built |
| `docs/ANNOTATION_RUNBOOK.md` | how to run the annotation pipeline (sample → generate → annotate → assemble), roster, R-loader changes | built |
| `docs/R_PIPELINE_WALKTHROUGH.md` | walkthrough of the 23-script R analysis layer | built |

## Deliberately NOT copied from legacy
- **All prompt/response/annotation data** (`prompts/*.json`, `responses/*.jsonl`,
  `annotations/*.jsonl`) — this repo generates its own battery from scratch.
- **One-off / maintenance scripts** — the many `fix_*`, `merge_*`, `retry_*`,
  `retranslate_*`, `redesign_*`, `add_*`, `extract_*`, `clean_*`, `verify_*`,
  `download_me2.py`, `gen_me_arm.py` (+ SLURM) scripts. These patched the
  legacy battery's history and are not part of a clean build. Pull
  individually from `../refusal_audit/scripts/` only if a specific need arises.
- **`create_new_prompts.py`** — the legacy GPT-4o free-drafting sourcer. This
  is precisely the component the new sourcing pipeline replaces.
- **`papers/`, `plots/`, `tables/`** — regenerated downstream once the new
  battery is run.
