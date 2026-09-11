# Repository and workflow map

Status: 11 September 2026. Paths are relative to the repository root. This map
describes the retained evidence and the supported live path; it does not turn
completed development experiments into production stages.

## Workflow at a glance

```text
Wikipedia/Wikidata
  -> sourcing records (`data/`)
  -> reviewed multilingual prompt batteries (`prompts/`)
  -> subject-model responses (`annotations/full_v1/` + `annotations/model_expansion_v3/` + `annotations/model_expansion_v4/`)
  -> original Gemini annotations (`annotations/full_v1/ann/` + assembled JSONL)
  -> human/codebook development + model evaluations (`annotations/response_validity_*`)
  -> frozen Luna v2.4 labels (137,186 original + 112,015 expansion rows)
  -> provisional R estimands/releases (`pipeline/`)
  -> local read-only refusal explorer (`interactive/`)
```

The ordered cross-directory contract is `config/REPLICATION_STAGES.csv` and
the practical entry point is `docs/REPLICATION_GUIDE.md`. Directory-level
registries enumerate every live script; archived and pending code is excluded
from the default execution surface.

The three-part key from generation onward is
`(prompt_id, prompt_language, model)`. `issue_id` is the resampling and
substantive clustering unit in the R pipeline; `prompt_id` identifies one of
2,496 prompt meanings.

## 1. Prompt sourcing and construction

`sourcing/run_pipeline.py` is the safe driver for the perennial Wikipedia
route. With no `--enrich` flag it only calls public Wikipedia/Wikidata APIs.
`--enrich` opts into paid LLM enrichment and prompt phrasing. The stages are:

| Stage | Implementation | Main retained outputs | State |
|---|---|---|---|
| Harvest perennial issues | `sourcing/01_harvest_controversial.py` | `data/candidate_issues*.json` | completed provenance; free rerun is possible but the live API can change |
| Enrich issues | `sourcing/02_enrich_issues.py` | `data/issue_records*.jsonl` | completed; paid/non-deterministic if rerun |
| Format prompts | `sourcing/03_format_prompts.py` | `prompts/*prompts_en.json`, review CSVs | completed; boundary templates deterministic, regular phrasing model-generated |
| Merge editions | `sourcing/04_merge_editions.py` | intermediate merged records incorporated into `data/issue_records_rebalanced.jsonl` | completed/local; mutable intermediate not retained |
| Translate/review | `sourcing/05_translate_review.py` | multilingual prompt JSON and canonical review CSV | completed; paid if rerun |
| Temporal protection-log route | `sourcing/06_harvest_temporal.py`, `07_enrich_temporal.py` | temporal candidates/records/prompts | completed provenance |
| Current-events supplement | `sourcing/08_harvest_current_events.py` | current-event candidate records | completed provenance |

The correction scripts that produced pre-fix snapshots now live under
`archive/2026-09-01_pre_rationalization/sourcing/`. Their outputs and pre-fix
copies were preserved in the same dated archive rather than discarded.

The frozen production battery is the `rebalanced_*` family in `prompts/` and
the copy under `annotations/full_v1/prompts_meta/`. English, Chinese, Arabic,
Russian and Hindi are in the analysis corpus. Japanese and Indonesian prompt
files remain as sourcing provenance but were not included in `full_v1`.

## 2. Subject-model response corpus

`scripts/generate_responses.py` is the response generator; `scripts/config.py`
holds the roster and provider routing. `scripts/run_pilot.py` is the retained
run-level assembler/orchestrator. Production output is append-only JSONL under
`annotations/full_v1/responses/`.

The original panel contains 11 display-model keys:

- US: `gpt-5.1`, `claude-opus-4.5`, `gpt-4o`, `grok-4.3`;
- China: `deepseek-chat-v3.1`, `qwen3-max`;
- EU: `mistral-large-2512`;
- MENA: `allam-7b`, `falcon3-10b`, `jais-8b`;
- India: `sarvam-30b`.

The first seven used OpenRouter. The MENA and India models used dedicated
OpenAI-compatible inference endpoints selected by environment variables.
Endpoint URLs and keys are deliberately absent from documentation and Git.
Generation used temperature 1.0 and a 5,000-token default completion ceiling;
`allam-7b` used 3,000 and `sarvam-30b` 8,000. Reasoning traces were retained as
provenance where supplied but were stripped from the answer passed to judges.

The v3 expansion adds seven display-model keys, all evaluated with the same
five languages, canonical prompt text, temperature 1.0 and 5,000-token ceiling:

- China: `glm-4.7-flash`, `hunyuan-a13b`, `kimi-k2.5`;
- Europe: `ministral-14b`;
- United States: `gemini-2.5-flash-lite`, `llama-4-scout`, `nova-lite`.

Their OpenRouter response records are under
`annotations/model_expansion_v3/full_run_v1/`; Hunyuan's all-language run is
under `annotations/model_expansion_v3/hunyuan_all_languages_v3_1/`. Routes were
pinned and fallbacks disabled. One Gemini Hindi request returned no usable
answer after two attempts, leaving 87,359 generated expansion responses.

Assembly follows the last-valid-record rule: a later error cannot erase an
earlier successful record with the same key. One Kimi Chinese response then
exhausted three schema-valid Luna annotation attempts. The analysis corpus
therefore contains 224,544 unique keys: 137,186 original and 87,358 expansion.
The v4 interim expansion adds Sarvam-105B (India) and Bielik 11B v3.0
(Europe). Sarvam returned 12,478 response-bearing records; Bielik returned
12,184, of which five exhausted Luna schema validation. Their immutable
generation and annotation artifacts are under
`annotations/model_expansion_v4/full_generation_v1/`. T-pro-it-2.0 is still
running and is not part of this analysis frame.

The former root `responses` placeholder contained no data
and was removed; the scientifically material responses are all under
`annotations/`.

## 3. Original Gemini annotation

`scripts/annotation_pipeline.py` ran the original multi-pass judge. The frozen
`annotations/full_v1/pilot_config.json` records Gemini 2.5 Flash-Lite,
temperature 0, eight workers and a pass-1-only production assembly. Raw
per-language records are under `annotations/full_v1/ann/`; assembled R-contract
files are `annotations_all.jsonl` and `annotations_<language>_boundary.jsonl`.

The original `engagement_code >= 4` variable pooled refusals, pivots and some
failures. Current documents therefore call it *judge-coded non-engagement*.
It is retained for measurement comparison, not used as ground-truth refusal.

## 4. Response-validity measurement

The categories were developed inductively from observed responses. Human
review and targeted validation produced v2.1; overlapping phenomena prompted
the decomposed v2.2 codebook; schema collisions prompted v2.3; and review of
limitation/disclaimer boundaries produced v2.4. Exact definitions, prompts and
structured-output code are in
`docs/RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md` and `config/`.

`scripts/response_validity.py` is the guarded command surface. Implementation
modules are in `src/refusal_audit/response_validity/`. Completed development
samples, translations, reviewer ledgers, bake-offs and frontier comparisons
remain under `annotations/response_validity_*` because they explain how the
measure was chosen. They are not inputs to the final wall-to-wall merge unless
the final manifest names them.

For the original panel, the production sequence is:

1. Reuse 2,393 already valid v2.4 evaluation labels.
2. Run Luna v2.4 on 134,793 remaining keys: 134,664 validated; 129 exhausted
   the initial logical validator.
3. Rerun those 129 under the frozen adaptive repair protocol; all validated.
4. Assemble one immutable row per corpus key.

The original-panel result is
`annotations/response_validity_v2_4/wall_to_wall_luna_v1/final_annotations.parquet`:
137,186 unique rows, 3,591 derived genuine refusals and 43,317 capability
failures. The expected SHA-256 is recorded in the root README and final
manifest. Sol did not repair the 129 cases. A selective future Sol cascade is
not implemented or complete. Human validation remains incomplete, and Sol
labels are machine-reference labels rather than human truth.

The same v2.4 prompt and schema were applied to the expansion responses in
five frozen Luna batches. `pipeline/_expansion_input.R` validates their
manifests, payload and artifact hashes, keys and status counts before appending
them. The resulting interim 20-model frame contains 6,794 genuine refusals and
60,968 capability failures.

## 5. R analysis and releases

`pipeline/make_release.R` is the only release driver. Root-level R files and
their companion documents are enumerated in `pipeline/PIPELINE_REGISTRY.csv`
and `docs/R_PIPELINE_WALKTHROUGH.md`. A build writes to
`pipeline/releases/<run_id>/`; acceptance and figure audits must pass before
promotion to `pipeline/estimates/canonical/` and `pipeline/figures/`.

`canon_024` is the current promoted baseline. It inherits the verified
18-model estimates from `canon_021` and contains the accepted compact
main-figure redesign; it passes 29/29 analysis plus 16/16 figure gates.
`canon_013` remains incomplete and is never selected by numeric suffix.
`canon_024` records an explicitly approved dirty-tree promotion, so a new
clean-tree release is still required before the final archival paper freeze.
The live source now targets the 20-model candidate in `canon_029`; this is
accepted but unpromoted and must not be confused with the baseline.

## 6. Interactive explorer

`interactive/build_data.py` verifies the promoted UMAP and response-frame
manifest, checks all seven expansion response files against the hashes used for
annotation, then joins prompt text, response text and v2.4 fields into
ignored Parquet assets. It does not refit UMAP. `interactive/app.py` displays
all 2,496 fixed prompt points in gray and overlays prompts with v2.4 genuine
refusals in red. It is read-only and local; historical annotation forms were
archived.

`interactive/build_web_data.py` derives a second, fixed three-dimensional UMAP
from the same frozen 512-dimensional English-prompt embeddings. The fit uses
R `uwot`, cosine distance, 25 neighbours, minimum distance 0.15 and seed
20260809. It is an exploratory locator only: outcomes never enter the fit and
filters never move points. The standalone React/Three.js site under
`interactive/web/` offers both this 3-D constellation and the canonical `c22`
2-D coordinates. It exports prompt metadata and genuine-refusal response text
only; all browser assets are reproducible, hashed and gitignored.

## 7. Directory retention policy

- `annotations/`, `prompts/`, `data/`, `config/`, `pipeline/releases/` and
  historical run manifests are evidence. They are retained even when large or
  apparently duplicative.
- `pipeline/estimates/canonical/` and `pipeline/figures/` are promoted outputs.
- `archive/2026-09-01_pre_rationalization/` preserves paths moved out of the
  live interface. `docs/ARCHIVE_MANIFEST.csv` maps every original path and hash.
- Disposable previews, renderer fragments, bytecode and caches were moved to
  `/tmp/refusal_audit_v2_cleanup_2026-09-01`, not irreversibly erased.
- `.env` remains ignored and local. No secret value is copied into any registry
  or application asset.

## 8. Non-pipeline material

The unrelated `prompts/AI Workshop Invite List.csv` had no code or scientific
consumer and was removed from the live prompt tree during the 4 September
rationalization. It is preserved in the dated archive rather than deleted.
