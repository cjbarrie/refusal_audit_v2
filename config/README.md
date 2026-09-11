# Configuration

This directory contains frozen machine-readable contracts, not a menu of
simultaneously active analyses.

- `replication_contract.json` is the current promoted/candidate release and
  input-hash contract.
- `REPLICATION_STAGES.csv` is the single ordered map from sourcing through
  release and interactive output. More detailed registries live beside the
  relevant code in `sourcing/`, `scripts/`, `hpc/`, `pipeline/` and
  `interactive/`.

- `response_validity_decomposed_v2_4.json` is the adopted response-validity
  schema. Earlier v2/v2.2/v2.3 files and bake-off/refinement specifications are
  retained because they document how v2.4 was developed; they are not current
  production alternatives.
- `response_translation_prompt_v1.txt` is the literal-translation prompt used
  in human-review preparation.
- `response_validity_migration.csv` is the hash-addressed provenance inventory
  for response-validity implementation files.
- `model_rosters/` contains versioned pilot and production rosters. The final
  analysed expansion is the v3/v3.1 family documented in
  `docs/OPENROUTER_MODEL_EXPANSION_V1.md`.
- `model_rosters/fanar_experiments_v1.json` keeps the completed native Fanar
  service and the proposed local QCRI checkpoint distinct while fixing their
  shared matched-prompt comparison.

Changing a frozen file requires a new version, corresponding tests and an
updated authorization record before any paid run.
