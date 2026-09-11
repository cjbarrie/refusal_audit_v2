# Repository instructions

Read `README.md`, `docs/REPOSITORY_MAP.md` and
`docs/PIPELINE_ENTRYPOINTS.md` before changing this project. The file-level
authority is `docs/ARTIFACT_REGISTRY.csv`; moved paths are resolved through
`docs/ARCHIVE_MANIFEST.csv`.

## Scientific state that must not be silently changed

- Corpus key: `(prompt_id, prompt_language, model)`; 224,544 unique analysed
  responses across 18 models. The original panel contributes 137,186 rows and
  the completed expansion contributes 87,358.
- Final response-validity table:
  `annotations/response_validity_v2_4/wall_to_wall_luna_v1/final_annotations.parquet`.
- Expected table SHA-256:
  `ce1b6c07de09e96912b034195c2c5ab6f2ef7762fbb103143e02913f1383cf75`.
- Final derived counts: 3,591 genuine refusals; 43,317 capability failures.
- All 129 initial Luna logical conflicts were repaired by Luna under the frozen
  adaptive protocol. Sol was not the repair mechanism.
- Promoted working analysis release: `canon_024`. It inherits hash-verified
  estimates from `canon_021`, passes 29/29 analytical and 16/16 figure checks,
  and records its explicitly allowed dirty tree. `canon_013` is incomplete and
  noncanonical. A new clean-tree release is still required for the final
  archival paper freeze.
- Human validation is incomplete. Sol is a machine reference, not human gold.
  A selective Sol production cascade is a possible future stage, not completed.

Do not mutate prompts, raw responses, annotation ledgers, human-review logs,
accepted releases or historical manifests. Do not describe original Gemini
codes 4–5 as validated refusal; call them judge-coded non-engagement.

## Execution and safety

- Run commands from the repository root.
- Python tests use `/Users/christopherbarrie/.pyenv/shims/python3.9` and
  `requirements.txt`.
- `pipeline/make_release.R` is the only R release driver. Use a fresh ID and
  `--no-promote` until a candidate has been inspected.
- No external or paid call is authorized by a task that merely asks for code,
  documentation, a payload, a cost estimate or a local test. Provider runs need
  an exact frozen payload, matching authorization record, cost ceiling and
  explicit paid-run flag.
- `.env` is ignored and local. Never print or copy its values. Endpoint URLs,
  account identifiers and model reasoning traces must not enter docs or app
  assets.
- Preserve append-only and last-valid-record semantics: a later error never
  erases an earlier valid response or annotation.

## Code boundaries

- `sourcing/`: Wikipedia/Wikidata prompt construction.
- `scripts/generate_responses.py`, `annotation_pipeline.py`, `run_pilot.py`:
  historical production generation/original annotation implementation.
- `scripts/response_validity.py`: guarded response-validity command surface.
- `src/refusal_audit/response_validity/`: versioned design/run modules.
- `pipeline/`: current and provisional R analysis; every root R file must be in
  `pipeline/PIPELINE_REGISTRY.csv` and have a companion reference.
- `interactive/`: one read-only v2.4 refusal explorer. Completed review pages
  are archived and must not be restored to the live navigation.

When code behavior changes, add or update a test and repair every live path
reference. Historical manifests retain their original paths; document mappings
instead of rewriting them.
