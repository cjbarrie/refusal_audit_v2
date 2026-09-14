# Current documentation

Only current, reader-facing documents live directly in `docs/`. Historical
plans and superseded specifications are in `docs/archive/` or a dated root
archive. Frozen manifests may retain their original paths; those records are
not rewritten after a move.

## Start here

- `TECHNICAL_PIPELINE.md`: the complete numbered account from Wikipedia
  harvesting through prompt corrections, provider connections, annotation,
  analysis and release;
- `REPLICATION_GUIDE.md`: the ordered, safe replication route;
- `REPLICATION_STATUS.md`: promoted, unpromoted, in-progress and deferred work;
- `PRIVATE_REPOSITORY_HANDOFF.md`: pre-commit size, credential and data-boundary checks;
- `REPOSITORY_MAP.md`: directories, data flow and retention rules;
- `PIPELINE_ENTRYPOINTS.md`: supported commands and paid-call boundaries;
- `CANONICAL_ANALYSES.md`: current estimands and inferential limits;
- `R_PIPELINE_WALKTHROUGH.md`: numbered R stages and per-script references;
- `CANONICAL_FIGURE_LEGENDS.md`: external legends for the current PNGs.

## Measurement

- `RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md`: complete adopted workflow;
- `RESPONSE_VALIDITY_CODEBOOK_RATIONALE.md`: v2.1--v2.4 codebook decisions;
- `RESPONSE_VALIDITY_DECISION_LOG.md`: dated decision and execution record;
- `RESPONSE_VALIDITY.md`: concise current measurement status.

## Prompt and model provenance

- `PIPELINE.md`, `NATIVE_SOURCING.md`, `TEMPORAL_SOURCING.md`, `REBALANCE.md`,
  `REPRODUCIBILITY.md`, and `repro_check.md`: Wikipedia sourcing and frozen
  prompt construction;
- `OPENROUTER_MODEL_EXPANSION_V1.md`: completed seven-model expansion,
  generation settings, route pins, counts and annotation batches.
- `JURISDICTION_MODEL_EXPANSION_V1.md`: guarded access-smoke protocol for the
  next Russian, Indian and European developer candidates.
- `LOCAL_GGUF_MODEL_EXPANSION_V1.md`: local Krutrim, EuroLLM, Salamandra and
  GigaChat admission pilots and their Luna/Sol cell audit.
- `HPC_LOCAL_GGUF_FULL_V1.md`: pinned NYU Torch implementation for the
  four-model, five-language, 49,920-response full-corpus run.
- `HPC_LOCAL_MODEL_CANDIDATE_SWEEP.md`: source-backed shortlist and admission
  protocol for the next jurisdiction-balanced local-model expansion.
- `FANAR_EXPERIMENTS_V1.md`: native-provider filtering, conservative refusal
  bounds, the frozen 29-case filter retest and the matched local QCRI pilot.

The operational histories above support the numbered master pipeline. They are
not additional steps in the default paper replication. Use
`TECHNICAL_PIPELINE.md` to understand what happened, `REPLICATION_GUIDE.md` for
the short verification route, and an operational document only when
reproducing that specific expansion.

## Audits and deferred work

- `CODE_ANALYSIS_AUDIT.md`: current forensic R/code audit;
- `REPOSITORY_AUDIT_2026-09-14.md`: current sequential-pipeline findings and
  resolutions; the 11 September audit remains a dated earlier state;
- `DEFERRED_SLANT_MORAL_VALIDITY.md`: why content outcomes remain pending;
- `ARTIFACT_REGISTRY.csv`: regenerated file-level inventory;
- `ARCHIVE_MANIFEST.csv`: hash-preserving record of the 1 September cleanup.

`r_pipeline/` contains one technical reference per live R file and a parallel
`pending/` section for analyses that are deliberately outside the release.
