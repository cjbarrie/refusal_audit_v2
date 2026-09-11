# Current artifact manifest

This is a human-readable index, not a substitute for the row-level hashes in
`docs/ARTIFACT_REGISTRY.csv` or the immutable release manifests.

## Scientific inputs and evidence

- Frozen prompt batteries: `prompts/`
- Prompt-sourcing records and embedding cache: `data/`
- Canonical response and original Gemini annotation run: `annotations/full_v1/`
- Human reviews and model-validation runs: `annotations/response_validity_*/`
- Final Luna v2.4 table:
  `annotations/response_validity_v2_4/wall_to_wall_luna_v1/final_annotations.parquet`
- Final Luna v2.4 manifest:
  `annotations/response_validity_v2_4/wall_to_wall_luna_v1/final_annotations_manifest.json`

The original-panel v2.4 table is expected to contain 137,186 unique
`(prompt_id, prompt_language, model)` keys and to hash to
`ce1b6c07de09e96912b034195c2c5ab6f2ef7762fbb103143e02913f1383cf75`.

Accepted v3 expansion response and Luna v2.4 inputs are under
`annotations/model_expansion_v3/`. The three accepted annotation batches are
`luna_v2_4_completed_batch1`, `luna_v2_4_completed_batch2` and
`luna_v2_4_kimi_batch3`. Their manifests and hashes are enforced by
`pipeline/_expansion_input.R`. Together with the original panel they produce
224,544 observed response keys across 18 models, with 6,127 genuine refusals
and 52,563 capability failures.

Two completed v4 batches add Sarvam-105B and Bielik 11B v3.0. The live R code
verifies these batches and produces a 249,201-response, 20-model candidate with
6,794 genuine refusals and 60,968 capability failures. `canon_029` is the latest
checked candidate, but it is not the promoted pointer. T-pro-it-2.0, the four
NYU Torch local-model full runs and the local Fanar experiment remain excluded.

## Code and configuration

- Sourcing: `sourcing/`
- Generation and original annotation: `scripts/generate_responses.py`,
  `scripts/annotation_pipeline.py`, `scripts/run_pilot.py`
- Response-validity orchestration: `scripts/response_validity.py`
- Response-validity implementation: `src/refusal_audit/response_validity/`
- Frozen codebooks and experiment specifications: `config/`
- Analysis and release machinery: `pipeline/`
- Active R script registry: `pipeline/PIPELINE_REGISTRY.csv`
- Active Python command registry: `scripts/SCRIPT_REGISTRY.csv`
- Ordered replication contract: `config/replication_contract.json` and
  `config/REPLICATION_STAGES.csv`
- Reproducible environments: `requirements-lock.txt`, `renv.lock` and
  `interactive/web/package-lock.json`
- Large binary Git policy: `.gitattributes` (Git LFS)
- Sourcing/HPC/interactive registries: `sourcing/SOURCING_REGISTRY.csv`,
  `hpc/HPC_REGISTRY.csv`, `interactive/INTERACTIVE_REGISTRY.csv`
- Per-script R technical references: `docs/r_pipeline/`
- Unsupported slant/moral and pre-v2.4 analyses: `pipeline/pending/`
- Interactive explorer: `interactive/`

## Analysis outputs

- Promoted release pointer: `pipeline/estimates/canonical/c00_manifest.csv`
- Promoted estimates: `pipeline/estimates/canonical/`
- Promoted figures: `pipeline/figures/`
- Immutable builds: `pipeline/releases/`

The promoted working release is `canon_024`. It inherits the complete,
hash-verified 18-model estimates from `canon_021`, contains the accepted two
main figures and 14 Extended Data figures, and passes 29/29 analysis and 16/16
figure gates. Its manifest records the explicitly allowed dirty tree. A new
clean-tree release is still required for the final archival paper freeze.
The present R source targets the unpromoted 20-model candidate, so a bare
`Rscript pipeline/tests_synthetic.R` against the promoted 18-model data is an
invalid cross-profile test. Use `make r-candidate-test` instead.

## Forensic records

- Complete registry: `docs/ARTIFACT_REGISTRY.csv`
- Cleanup manifest: `docs/ARCHIVE_MANIFEST.csv`
- Repository map: `docs/REPOSITORY_MAP.md`
- Supported commands: `docs/PIPELINE_ENTRYPOINTS.md`
- Repository replication audit: `docs/REPOSITORY_AUDIT_2026-09-11.md`
- Current R analysis audit: `docs/CODE_ANALYSIS_AUDIT.md`
- Private commit boundary: `docs/PRIVATE_REPOSITORY_HANDOFF.md`
- Dated pre-cleanup archive: `archive/2026-09-01_pre_rationalization/`
- Post-v2.4 cleanup archive: `archive/2026-09-04_post_v24_rationalization/`

Frozen historical manifests keep their original paths and hashes. The cleanup
manifest records any corresponding archived location.
