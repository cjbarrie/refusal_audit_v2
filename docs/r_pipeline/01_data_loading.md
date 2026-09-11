# `01_data_loading.R`

## Role in the pipeline

This script creates the response-level analysis frame. It combines the original
Gemini records with prompt metadata, attaches the original-panel Luna v2.4
table, validates five expansion Luna batches, and appends nine additional
models. It estimates nothing.

## Inputs and keys

`REFUSAL_RUN_DIR` defaults to `annotations/full_v1`. The script reads
`annotations_all.jsonl`, each available
`annotations_<language>_boundary.jsonl`, the five
`prompts_meta/test_prompts_<language>.json` files, and
`pass23_subsample.json`. The last file is retained only to support analyses now
under `pipeline/pending/`. `_expansion_input.R` additionally reads each
expansion batch's manifest, run summary, response index and annotation results.

The response key is `(prompt_id, prompt_language, model)`. Error records,
missing models, blank language codes and Gemini engagement codes outside 1--5
are excluded. Boundary prompts accidentally appearing in the base file are
removed using prompt metadata. A response without matching prompt metadata is
excluded before the final key check.

Both the annotation and frozen prompt battery carry topic category and prompt
tier. After the join, the script requires exact equality between the two
sources. This prevents inclusion being decided by one tier field while a later
model adjusts for a contradictory field.

The original Luna table is joined through `_response_validity.R`: 137,186 keys
must match exactly. `_expansion_input.R` then adds 112,015 observed keys. The
combined frame must contain 249,201 unique keys and 20 models. Missing
generations and the six exhausted annotations (one Kimi, five Bielik) are not
imputed.

## Derived fields

Model jurisdiction, delivered-language factors, prompt tier, sourcing route,
prompt origin and home-region inputs are deterministic mappings. The script
retains `engaged`, `refused` and `engagement_category` only for reconstruction
of pending pre-v2.4 work. Live analyses instead use `genuine_refusal`,
`capability_failure`, `substantive_pivot` and
`original_nonengagement` attached by the outcome helper.

## Outputs

- `CANON_DATA_PATH` (release default: `<release>/estimates/data_clean.RData`),
  containing the object `data_clean`;
- `CANON_SUMMARY_DIR/00_model_summary.csv`;
- `CANON_SUMMARY_DIR/00_language_summary.csv`;
- `CANON_SUMMARY_DIR/00_category_summary.csv`.

The summaries report v2.4 refusal, capability-failure and original
non-engagement counts/rates. They are diagnostics, not effects.

## Worked example

An Arabic response with key `(p, ar, m)` is first matched to Arabic prompt
metadata. For an original model, the key must exist once in the original v2.4
Parquet file. For an expansion model, it must exist once in a frozen response
index and once in its matching annotation-results file. If Luna marked both
outcome flags, the saved row has `genuine_refusal=1` and
`capability_failure=1`; neither overwrites the other.

No API is called. The script supports sample reconstruction only and licenses
no causal or population inference.
