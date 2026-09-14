# Technical pipeline: from Wikipedia pages to analysis releases

Status: 14 September 2026.

This is the master account of the work that produced the current data. It is
written in execution order. The shorter `REPLICATION_GUIDE.md` tells a reader
how to verify or rebuild the current analysis; this document explains how the
underlying prompt, response and annotation records came into being.

Three labels are used throughout:

- **production**: contributes to a retained data product or analysis release;
- **amendment**: corrects a specific earlier defect and preserves the record it
  replaced; and
- **workbench**: a pilot, route test or unfinished model expansion that does not
  enter the current analysis.

Script numbers are local to their component. The global order is the numbered
sequence below and in `config/REPLICATION_STAGES.csv`. Component registries give
every live entry point a stable identifier:

- `sourcing/SOURCING_REGISTRY.csv` for prompt construction;
- `scripts/SCRIPT_REGISTRY.csv` for generation and annotation;
- `hpc/HPC_REGISTRY.csv` for Torch jobs;
- `pipeline/PIPELINE_REGISTRY.csv` for R analysis; and
- `interactive/INTERACTIVE_REGISTRY.csv` for the explorers.

Historical releases and provider ledgers are immutable. A repair creates a new
artifact; it never edits a provider response or an earlier annotation in place.

## 00. Environments, credentials and the execution boundary

Python dependencies are pinned in `requirements-lock.txt`; R dependencies are
in `renv.lock`; browser dependencies are in
`interactive/web/package-lock.json`. The supported setup and verification
commands are in `REPLICATION_GUIDE.md`.

Credentials live in the ignored root `.env`. Code names environment variables
but never stores their values in documentation, manifests or browser assets.
The existence of a credential is not permission to use it. Any paid stage
requires a frozen request inventory, its SHA-256, a provider or request ceiling,
an explicit authorization record and an explicit run flag.

**Output.** A local environment that passes `scripts/replication_check.py`.

## 01. Harvest the perennial Wikipedia seed

`sourcing/01_harvest_controversial.py` reads `sourcing/editions.yaml`. For each
edition it calls `https://<edition>.wikipedia.org/w/api.php`. English and
Indonesian start from named controversial-issue list pages. Chinese, Japanese,
Arabic and Russian use the edition-specific category names frozen in the YAML.
The harvester resolves titles and redirects, requests Wikidata Q-IDs, and
deduplicates within an edition.

The configured English source is
`Wikipedia:List of controversial issues`. Examples of native-edition sources
are `Category:南海争议` on Chinese Wikipedia and
`Категория:Спорные территории в Европе` on Russian Wikipedia. The complete
list—not an English translation of it—is in `sourcing/editions.yaml`.

**Input.** `sourcing/editions.yaml` and the live MediaWiki APIs.

**Output.** `data/candidate_issues_<language>.json`.

**Reproduction limit.** A present-day API call may see renamed categories,
redirects or revised pages. The retained candidate and issue-record files are
the historical evidence used downstream.

## 02. Add two time-sensitive seed routes

The perennial list is useful but slow-moving. Two additional routes supplied
contemporary and topically broader cases.

1. `sourcing/06_harvest_temporal.py` queries the MediaWiki protection log with
   `action=query`, `list=logevents`, `letype=protect`, article namespace and a
   fixed look-back window. It retains political contentious-topic signals and
   records the protection reason, number of protections and latest event.
2. `sourcing/08_harvest_current_events.py` reads English Wikipedia current-event
   portal pages, resolves their article links, and fetches article protection
   plus talk-page size as a cheap contention screen.

`sourcing/07_enrich_temporal.py` is the matching batch enricher for both routes.
It fetches extracts and revision identifiers in batches before classification.
This replaced an early attempt to call the general enricher once per article,
which overwhelmed the MediaWiki API with HTTP 429 responses.

**Inputs.** MediaWiki protection-log, page, revision and current-events records.

**Outputs.** `data/candidate_issues_temporal_en.json`,
`data/candidate_issues_temporal_180d_en.json`,
`data/candidate_issues_current_events_en.json` and their corresponding
`issue_records_*.jsonl` files.

The exact queries, windows and frozen counts are in `TEMPORAL_SOURCING.md` and
`REPRODUCIBILITY.md`.

## 03. Enrich candidate issues

`sourcing/02_enrich_issues.py` fetches the article lead, page protection, page
size, talk-page size and revision ID. It then uses a structured LLM call to
extract a neutral summary, two opposing positions, geographic focus, topic
domain and a political-content flag. It also calculates a contention score
from page protection and talk-page size.

`sourcing/07_enrich_temporal.py` produces the same analytical fields for the
temporal routes while retaining their route-specific evidence. Provider calls
at this stage were part of construction, not the later refusal annotation.

**Inputs.** `data/candidate_issues*.json` plus MediaWiki page records.

**Outputs.** edition- and route-specific `data/issue_records*.jsonl` files.

Every retained record is intended to carry its source edition, source title,
URL, Wikidata Q-ID when one exists, snapshot date, sourcing route and revision
provenance. Section 06 explains the amendment applied when this contract was
found not to hold for every temporal record.

## 04. Merge issue records and construct prompts

`sourcing/04_merge_editions.py` merges edition-specific records on Wikidata
Q-ID when available and retains the provenance of each contributing edition.
`sourcing/03_format_prompts.py` converts one issue into four prompt meanings:

- two regular political questions generated from the neutral issue record; and
- a symmetric boundary pair asking the model to defend each opposing position.

Boundary prompts use `sourcing/boundary_templates.json`; they are not free-form
LLM rewrites. The regular questions and the boundary pair travel together under
one `issue_id`.

**Input.** Enriched issue records.

**Outputs.** `prompts/full_prompts_en.json`,
`prompts/temporal_prompts_en.json` and, after the rebalance,
`prompts/rebalanced_prompts_en.json`.

## 05. Rebalance the issue frame

The first combined frame was dominated by Arab-region security/conflict issues.
The rebalance added Chinese dispute categories, an English current-events route
and a wider protection-log window. `sourcing/run_rebalance.sh` records the
historical assembly order; `REBALANCE.md` gives the cell counts and commands.

The final draw is implemented by `scripts/sample_prompts.py`. It samples whole
issues, not individual prompts, so the four prompt meanings for an issue and
the matched boundary pair cannot be split. With seed `20260728`, the ethical
Q-ID denylist active, six eligible regions, equal region quotas and a topic cap
of 80, the draw retained 624 issues and 2,496 prompt meanings. Each region
contributes 104 issues. Topic counts range from 35 to 80. Max-flow establishes
the feasible equal region quota; iterative proportional fitting spreads each
region's quota across the topics it actually contains; seeded sampling then
chooses the issues in each cell.

**Inputs.** `data/issue_records_rebalanced.jsonl`, the ethical denylist and seed
`20260728`.

**Outputs.** `prompts/sampled/rebalanced_sample_manifest.json` and the English
sample battery. The manifest records the realized region-by-topic allocation.

## 06. Apply and record prompt-battery amendments

Quality checks found four defects after the first rebalanced battery was built.
These were repaired in sequence. The one-off implementations are retained under
`archive/2026-09-01_pre_rationalization/sourcing/`; they are not live commands.

| Amendment | Defect | Retained implementation | Result |
|---|---|---|---|
| 06A | slug-based `issue_id` values collided | `09_migrate_issue_ids.py` | collision-free issue and prompt keys; affected IDs recorded in `data/idfix_redo_ids.json` |
| 06B | 1,214 native-source prompts in the English master were not English | `10_backtranslate_native.py` | English pivot text restored; origin language retained in metadata |
| 06C | translations derived from affected English rows were now stale | `11_retranslate_affected.py` | only the union of affected multilingual rows was translated again |
| 06D | boundary wording had drifted across batteries | `12_normalize_boundary_templates.py` | canonical templates reapplied and checked |
| 06E | temporal/current-event revision IDs were missing | `13_recover_qids.py`, `14_recover_provenance.py` | historical-as-of revision lookup attempted and recovered IDs explicitly marked |

The required order was 06A, 06B, 06C, then 06D: translation worklists depended
on collision-free keys, and the translated batteries had to be regenerated
from the corrected English pivot before their templates could be checked.
Pre-repair snapshots and provider ledgers were retained. Nothing downstream is
silently rewritten by running a current replication target.

`sourcing/run_corrections.sh` is now a non-executing historical signpost. Its
old recipe depended on archived scripts and must not be mistaken for a supported
paid command.

## 07. Translate, review and freeze the five-language battery

`sourcing/05_translate_review.py` translates the corrected English prompt text
and writes side-by-side review files. Japanese and Indonesian batteries were
built historically but were dropped from the study sample because their issue
and home-model strata were too thin. The frozen study languages are English,
Chinese, Arabic, Russian and Hindi.

Manual review checked the final prompt battery and the symmetry of adjacent
boundary pairs. The five retained files each contain the same 2,496 prompt IDs
in the same order:

| Language | Frozen file | SHA-256 |
|---|---|---|
| English | `prompts/sampled/rebalanced_prompts_en_sample.json` | `14d2d4a6d95423cfe1f8d41499087da5160052130cb0f208addb52664cc1fba2` |
| Chinese | `prompts/sampled/rebalanced_prompts_zh_sample.json` | `0582a9b5457ec2df43c6bfb2e8bad4307fd13e3b6b8652509a873b20c62b722f` |
| Arabic | `prompts/sampled/rebalanced_prompts_ar_sample.json` | `816401bafc50e5d3fd6686a36f2c2934bc919a614fe0eea3bbfb6d2187a84381` |
| Russian | `prompts/sampled/rebalanced_prompts_ru_sample.json` | `3487e9aba0b39e101b7209235a05f390905617bd0dcbb62dec26ebf583d1d994` |
| Hindi | `prompts/sampled/rebalanced_prompts_hi_sample.json` | `b1300f6303ac08f8fd2197ba7d660b7abcfe66c1a57b92ee45a20c3c1c2fb014` |

The human-facing review file is
`prompts/sampled/rebalanced_prompts_sample_review.csv`.

## 08. Generate the original model panel

`scripts/generate_responses.py` sends the same frozen prompt text to each
subject model without a system message. The request temperature is 1.0 and the
default maximum completion is 5,000 tokens. Model-specific exceptions are
declared in `scripts/config.py`: ALLaM used 3,000 because its endpoint context
was 4,096, while the historical Sarvam 30B endpoint used 8,000 to accommodate
its reasoning wrapper. Returned reasoning fields were kept outside the response
given to the annotation judge.

The original roster joined OpenRouter models to four dedicated Hugging Face
Inference Endpoints. `scripts/config.py` records exact model IDs, developer
jurisdictions, endpoint environment-variable names and per-model token limits.
The response key is `(prompt_id, prompt_language, model)`. Ledgers are append
only; resumption selects the last valid record for a key and retries only a key
without a valid response.

The eleven original subject models were:

| Developer jurisdiction | Subject models |
|---|---|
| China | DeepSeek Chat v3.1; Qwen3 Max |
| MENA | ALLaM 7B; Falcon3 10B; Jais 8B |
| India | Sarvam 30B |
| United States | Claude Opus 4.5; GPT-5.1; GPT-4o; Grok 4.3 |
| Europe | Mistral Large 2512 |

The exact provider-facing identifiers, rather than these display names, remain
authoritative in `scripts/config.py` and the frozen run configuration.

**Input.** Five frozen prompt files and the frozen original model roster.

**Output.** `annotations/full_v1/`, containing 137,186 usable responses. There
were 94 unavailable model-language-prompt cells; they are missing, not imputed.

`scripts/run_pilot.py` was the historical orchestration and assembly program.
`annotations/full_v1/pilot_config.json` records that run.

## 09. Run the original Gemini annotation

`scripts/annotation_pipeline.py` used `google/gemini-2.5-flash-lite` at
temperature 0. Its first pass assigned engagement codes 1–5 and, for codes
3–5, one refusal justification. Later passes produced slant and moral-foundation
fields. The exact original prompt is `PASS_1_TEMPLATE`; the stored output is in
`annotations/full_v1/`.

The paper originally treated codes 4–5 as refusal. Review showed that code 4
also contained substantive pivots, wrong-language output, incoherence and
mechanical failures. The original label is therefore retained only as
**Gemini judge-coded non-engagement**. Slant and moral-foundation analyses are
under `pipeline/pending/` because no adopted high-quality outcome replaces the
original passes.

## 10. Develop the response-validity codebook

The final codebook was developed inductively. A researcher read actual model
responses, grouped recurring forms of non-answering, and revised definitions
when one mutually exclusive label could not describe overlapping behavior.
The development material comprised 700 unique responses:

- the first 300 combined a simple random draw, a model-by-language stratified
  draw and prespecified priority groups; and
- the next 400 excluded those rows and oversampled deterministic signals for
  wrong language, technical failure, pivot, refusal, incoherence, prior model
  disagreement and a general control remainder.

The retained inclusion probability for the first wave was the union of its
three component probabilities,

```text
pi_i = 1 - (1 - p_global,i)
           (1 - p_model-language,i)
           (1 - p_priority,i).
```

The 400-case wave was development enrichment, not a prevalence sample. Literal
English translations helped the reviewer understand content, but language
fidelity was decided from the source response. Translation never replaced it.

The instrument then changed as follows:

| Version | Why it changed | Main change |
|---|---|---|
| Gemini original | engagement code pooled several mechanisms | retained as historical non-engagement only |
| human v2.1 | recurring response forms were identified manually | seven mutually exclusive validity classes |
| decomposed v2.2 | a response could be wrong-language and still refuse | task behavior, refusal, language, quality and failure became separate fields |
| decomposed v2.3 | 108/1,400 Luna records violated the first schema’s logic | semantic output quality was separated from mechanical failure and invalid combinations were enforced in validation |
| decomposed v2.4 | human review exposed disagreement about limitation-plus-substitute answers | withholding was defined as refusal even when a response also supplies background or a safer substitute; schema fields did not change |

The exact definitions and decisions are in
`RESPONSE_VALIDITY_CODEBOOK_RATIONALE.md`; the chronological experiment record
is `RESPONSE_VALIDITY_DECISION_LOG.md`. The complete current prompt, JSON schema,
request code and human-sample construction are in
`RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md`.

## 11. Select and validate the scalable annotation model

All candidate annotators received the same source-language prompt and model
response, the same v2.4 system prompt and the same structured-output schema.
They were blind to the subject model, prior labels and sampling reason.

Luna was chosen as the scalable annotator after staged prompt tests and a
same-codebook model bake-off. Sol served as a frontier machine reference, not a
human gold standard. On 1,173 protected v2.4 cases, Luna and Sol agreed on
98.72% of refusal decisions; treating Sol as the reference gave Luna refusal
precision .938, recall .929 and F1 .933. Alternative API models did not meet the
predeclared refusal non-inferiority rule. A later fresh probability sample kept
model selection separate from accuracy estimation. Human validation remains
limited; claims must say “Luna-coded” or “Sol-referenced” where relevant.

**Implementation.** `scripts/response_validity.py` exposes the guarded commands;
the implementations are versioned under `src/refusal_audit/response_validity/`.

## 12. Annotate the original panel with Luna v2.4

Two earlier sets contained 2,393 byte-identical Luna v2.4 labels. They were
reused by exact response key. The remaining 134,793 responses were frozen into
a compact request index and annotated wall to wall through OpenRouter’s pinned
OpenAI route with `openai/gpt-5.6-luna`, temperature 0, 500 output tokens,
reasoning excluded, provider fallbacks disabled and at most three recorded
attempts.

The first run returned 134,664 valid annotations. The 129 exhausted rows all
contained a specific contradiction between garbled output and an asserted
refusal. The versioned repair in
`src/refusal_audit/response_validity/wall_to_wall_repair_v24.py` kept the same
codebook and fields but added the validator error to a fresh repair request.
All 129 resolved on the first repair attempt. The repair is an amendment to
stage 12, not a new outcome definition.

**Final output.** `annotations/response_validity_v2_4/wall_to_wall_luna_v1/final_annotations.parquet`
contains exactly 137,186 unique response keys. SHA-256:
`ce1b6c07de09e96912b034195c2c5ab6f2ef7762fbb103143e02913f1383cf75`.
It contains 3,591 derived genuine refusals and 43,317 capability failures.

## 13. Expand the model panel through hosted APIs

Hosted expansion followed an admission sequence: small route smoke, matched
40-meaning pilot, Luna v2.4 annotation, targeted Sol audit, then a frozen full
run only for viable routes. The full generation prompt text and settings stayed
the same across subject models.

Connection modes were:

| Mode | How it was called | Examples | Operational record |
|---|---|---|---|
| OpenRouter | OpenAI-compatible chat completions; provider pinned; fallback disabled | Ministral 14B, Nova Lite, Llama 4 Scout, Hunyuan A13B, GLM 4.7 Flash, Gemini 2.5 Flash-Lite, Kimi K2.5 | `OPENROUTER_MODEL_EXPANSION_V1.md` |
| native API | provider-specific HTTP client and credential | Sarvam-105B; Fanar experiments | `JURISDICTION_MODEL_EXPANSION_V1.md`, `FANAR_EXPERIMENTS_V1.md` |
| Hugging Face router | model plus provider pin; fallback disabled | Bielik 11B v3.0; T-pro-it-2.0 | `JURISDICTION_MODEL_EXPANSION_V1.md` |
| dedicated HF endpoint | private OpenAI-compatible endpoint URL | original ALLaM, Falcon, Jais and Sarvam 30B | `scripts/config.py` and archived endpoint notes |

The seven completed v3 OpenRouter models and the completed Sarvam and Bielik
runs use the unchanged Luna v2.4 annotation. Their batch paths, request counts
and payload hashes are declared in `config/analysis_roster_v1.json` and verified
by `pipeline/_expansion_input.R` before any row is joined.

The thirteen accepted additions are listed below. This is the roster admitted
to `canon_031`, not a list of every model ever piloted.

| Route | Accepted additions |
|---|---|
| OpenRouter | Ministral 14B; Nova Lite; Llama 4 Scout; Hunyuan A13B; GLM 4.7 Flash; Gemini 2.5 Flash-Lite; Kimi K2.5 |
| Native Sarvam API | Sarvam-105B |
| Hugging Face router | Bielik 11B v3.0 |
| NYU Torch, local GGUF | Krutrim 2; GigaChat3 10B A1.8B; EuroLLM 22B; Salamandra 7B |

T-pro is not in the analysis. Its provider returned many HTTP-200 bodies that
contained a valid completion followed by an error object or a truncated JSON
wrapper. `scripts/tpro_full_recovery.py` losslessly recovers only intact text
already present in those saved bodies and freezes unresolved keys separately.
`scripts/tpro_full_retry_probe.py` tests whether a new attempt is worthwhile.
This amendment never invents or edits response text and cannot silently admit
T-pro into an analysis release.

Fanar experiments remain workbench evidence because provider filtering and
checkpoint differences prevent a clean full-corpus comparison.

## 14. Generate locally runnable models and move them to Torch

Local admission pilots used Q8 GGUF checkpoints through llama.cpp. GigaChat
required a versioned raw-completion template repair; the original failed output
was retained. Krutrim 2, GigaChat3, EuroLLM 22B and Salamandra 7B passed the
mechanical pilot gate and were moved to NYU Torch for the full corpus.

The Torch sequence is explicit:

1. `hpc/prepare_local_gguf_full.py` freezes 40 model-language array tasks and
   audits their task map.
2. `hpc/slurm/00_bootstrap.sbatch` creates the scratch environment and pulls the
   pinned llama.cpp Apptainer image.
3. `hpc/slurm/01_download_models.sbatch` downloads four revision- and
   SHA-pinned GGUF files.
4. `hpc/slurm/02_benchmark.sbatch` runs 100 responses per model; only the
   separately invoked `hpc/audit_benchmark.py` evaluates the mechanical gate.
5. `hpc/slurm/03_generate_full.sbatch` runs the 40 full model-language shards.
6. `hpc/prepare_local_gguf_full.py audit` assembles and hashes the terminal
   records.

The engine was llama.cpp server in Apptainer, with four parallel slots, an
8,192-token context per slot, temperature 1.0, 5,000 maximum output tokens,
repeat penalty 1.0 and at most two attempts. The completed run contains 49,920
terminal records: 49,879 non-empty responses, 28 empty responses and 13 runtime
or transport failures. Empty/error records are retained as delivery outcomes
but are not assigned a semantic refusal label.

**Operational record.** `HPC_LOCAL_GGUF_FULL_V1.md`,
`config/model_rosters/local_gguf_hpc_v1.json` and
`annotations/model_expansion_v4/local_gguf_full_hpc_v1/`.

## 15. Annotate and audit the Torch panel

Luna v2.4 annotated all 49,879 non-empty Torch responses. Twelve exhausted
schemas were repaired with the same fields and definitions. The assembled Luna
census contains 381 genuine refusals and 13,630 capability failures; SHA-256:
`f6f1c3afe59bc48db191cd3d423d491a63ab5eda82d0c10aee813992931f587d`.

Because local models presented a clear distribution shift, a separate Sol
audit used all 381 Luna refusal positives, all 271 refusal-unassessable rows,
a probability sample of 298 assessable capability failures and a probability
sample of 385 apparently clean controls. Frozen inclusion probabilities recover
the 49,879-response population. `pipeline/18_measurement_validation.R` verifies
the audit hashes and publishes design-weighted agreement; it does not replace
individual Luna labels with Sol labels.

## 16. Assemble the analysis frame

`pipeline/01_data_loading.R` reads the original response/annotation products and
calls `pipeline/_expansion_input.R`. The latter accepts only batches declared in
`config/analysis_roster_v1.json`, verifies their hashes and expected counts,
normalizes keys, and rejects duplicates. Metadata are joined by stable prompt
and issue keys. Missing generation or annotation cells remain missing.

Current states must not be conflated:

| State | Rows | Models | Status |
|---|---:|---:|---|
| `canon_024` | 224,544 | 18 | promoted working baseline |
| `canon_031` | 299,080 | 24 | accepted but unpromoted current candidate |

The live R source targets the 24-model candidate. It includes 137,186 original
responses and 161,894 accepted expansion responses, with 7,175 Luna-coded
genuine refusals and 74,598 capability failures. T-pro and Fanar are excluded.
Both releases were built from dirty Git trees, so neither is the final archival
paper release.

## 17. Estimate the current outcomes

`pipeline/10_canonical_common.R` validates the analysis frame and defines the
shared weights, bootstrap units, support checks and g-computation helpers.
Active estimators then run in number order:

- `11_canonical_home.R`: descriptive English rates and standardized
  home-jurisdiction contrasts;
- `12_canonical_language_framing.R`: prompt-fixed language contrasts and matched
  boundary-framing contrasts;
- `15_subsample_stability.R`: issue-level subsample stability;
- `16_prompt_umap.R`: one fixed semantic geometry plus outcome concentration;
- `17_response_validity.R`: measurement prevalence, overlap and transition; and
- `18_measurement_validation.R`: the Torch Luna–Sol audit.

`40_appendix_descriptives.R` writes descriptive appendix tables. Slant, moral
foundations and original-label uncertainty remain in `pipeline/pending/` and
are not called by `pipeline/make_release.R`.

Exact formulas, target populations, bootstrap units and permitted
interpretations are in `CANONICAL_ANALYSES.md` and the per-script documents in
`docs/r_pipeline/`.

## 18. Render figures, audit and release

`pipeline/20_figures_main.R` and `21_figures_extended.R` render PNGs from
retained estimate tables and the fixed UMAP coordinates; they do not fit models.
`pipeline/30_acceptance.R` checks numerical contracts and
`pipeline/audit_figures.R` checks the raster inventory and table-to-figure
agreement. `pipeline/make_release.R` refuses to overwrite an existing release
ID. Promotion is separate from building a candidate.

The final archival paper release must be built from a clean Git tree with a new
release ID. Until that happens, `canon_024` remains promoted and `canon_031`
remains the accepted 24-model candidate.

## 19. Build the interactive explorers

`interactive/build_data.py` and `interactive/build_web_data.py` resolve the
promoted release pointer rather than selecting the largest numbered directory.
They reuse the one fixed UMAP coordinate pair for each of the 2,496 English
prompt embeddings. `interactive/app.py` provides local verification;
`interactive/web/` provides the standalone 2-D/3-D browser view. Generated
Parquet and browser JSON are derived, ignored artifacts.

## 20. Trace one record through the pipeline

For one selected issue, the provenance chain is:

1. a Wikipedia title and edition enter a `candidate_issues_*.json` record;
2. enrichment attaches Q-ID when available, source revision, neutral summary,
   opposing positions, region and topic in an `issue_records_*.jsonl` row;
3. prompt formatting produces two regular and two boundary prompt IDs under the
   same `issue_id`;
4. the issue-level balanced draw either keeps all four prompts or drops all four;
5. translation preserves the same prompt IDs in five aligned batteries;
6. generation adds model and language to form the unique response key;
7. Luna v2.4 adds separate task behavior, refusal, language fidelity, output
   quality and technical-failure fields to that key;
8. R joins issue and model jurisdiction metadata, derives `genuine_refusal` and
   `capability_failure`, and contributes the row to the declared estimand; and
9. figures read the saved estimate or prompt-outcome table rather than
   re-estimating from the plotted data.

If any key, count or hash fails at stages 12–18, the pipeline stops. It does not
drop the row and continue silently.

## 21. What remains outside the production spine

The following are deliberately excluded until a later, separately accepted
release:

- T-pro residual recovery and retry work;
- native and local Fanar experiments;
- prospective local-model candidate sweeps;
- unfinished provider routes or cells that failed an admission pilot;
- slant and moral-foundation analysis based only on the original Gemini passes;
- a selective Luna-to-Sol production cascade; and
- final independent human accuracy certification.

Their ledgers and decision records are preserved because they explain what was
tried. They are not additional steps a replicator must run.
