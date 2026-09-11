# Refusal audit v2

This repository studies when language models refuse political prompts, fail to
answer them coherently, or behave differently across issue regions and prompt
languages. The prompt battery is anchored in Wikipedia issue records rather
than drafted from scratch by a model.

## Current state and replication contract

- The promoted baseline contains **224,544** unique
  `(prompt_id, prompt_language, model)` keys from 18 models, five prompt
  languages, 624 issues and 2,496 English prompt meanings. It joins the
  137,186-response original panel to 87,358 completed expansion annotations.
- The original production annotation used Gemini 2.5 Flash-Lite. Its codes
  4–5 are retained as **judge-coded non-engagement**, not treated as validated
  refusal.
- The completed production measurement is Luna v2.4 at
  `annotations/response_validity_v2_4/wall_to_wall_luna_v1/final_annotations.parquet`.
  It contains one label per original-panel response, including 3,591 derived
  genuine refusals and 43,317 derived capability failures. Its SHA-256 is
  `ce1b6c07de09e96912b034195c2c5ab6f2ef7762fbb103143e02913f1383cf75`.
- Three frozen v3 expansion batches apply the unchanged Luna v2.4 codebook to the
  seven added models. The combined frame contains 6,127 genuine refusals and
  52,563 capability failures. One empty Gemini generation and one exhausted
  Kimi annotation remain missing; neither is imputed.
- The promoted working release is **`canon_024`**. It inherits the hash-verified
  18-model estimates from `canon_021` and makes the accepted compact two-figure
  genuine-refusal redesign canonical. It passes 29/29 analysis checks and
  16/16 figure checks. The manifest records that it was built from a dirty
  working tree under explicit approval; a clean-tree rebuild remains required
  before the final archival paper release.
- The live R source has advanced to an unpromoted **20-model candidate**. Its
  checked build, `canon_029`, contains 249,201 observed responses after adding
  Sarvam-105B and Bielik 11B v3.0. It passed the current gates but was also
  built from a dirty tree and does not silently replace `canon_024`.
- T-pro-it-2.0, the four NYU Torch local models and the local Fanar experiment
  remain operational workbench runs. None enters either release above.
- Sol was used as a frontier machine reference in validation work. It is not a
  human gold standard, and no selective Sol production cascade has been run.

No currently supported paid production stage runs by default. The guarded v2.4
provider commands require a frozen payload, an exact recorded authorization
and an explicit paid-run flag. Historical sourcing and generation programs are
preserved implementations, not blanket authorization to call providers.

## Repository structure

| Path | Purpose |
|---|---|
| `sourcing/` | Wikipedia harvest, enrichment, prompt construction and translation code |
| `data/` | retained sourcing inputs, intermediate records and the fixed English embedding cache |
| `prompts/` | frozen multilingual prompt batteries and review/provenance files |
| `scripts/` | numbered registry of response generation, measurement and guarded operational CLIs |
| `src/refusal_audit/` | response-validity design, validation and v2.4 implementation modules |
| `annotations/` | raw responses, original annotations, human reviews, validation runs and final v2.4 labels |
| `pipeline/` | current R estimators, PNG figures, immutable releases and acceptance gates |
| `interactive/` | read-only Streamlit verifier and standalone 3-D/2-D Refusal Observatory |
| `docs/` | current technical documentation, registries and decision records; indexed by `docs/README.md` |
| `archive/` | dated or stage-specific historical material; never part of the live execution path |
| `writeup/` | current technical write-up source/PDF and archived prior versions |

The detailed directory and data-flow map is
[`docs/REPOSITORY_MAP.md`](docs/REPOSITORY_MAP.md). The exhaustive file-level
inventory is [`docs/ARTIFACT_REGISTRY.csv`](docs/ARTIFACT_REGISTRY.csv).
The live Python command inventory is
[`scripts/SCRIPT_REGISTRY.csv`](scripts/SCRIPT_REGISTRY.csv).
Start a replication with
[`docs/REPLICATION_GUIDE.md`](docs/REPLICATION_GUIDE.md); use
[`docs/REPLICATION_STATUS.md`](docs/REPLICATION_STATUS.md) to distinguish
promoted results from work in progress.

## Supported entry points

Run commands from the repository root. The authoritative command guide is
[`docs/PIPELINE_ENTRYPOINTS.md`](docs/PIPELINE_ENTRYPOINTS.md).

```bash
# Verify the frozen prompts, outcome table and promoted canon_024 release
make baseline-check PYTHON=.venv/bin/python

# Check prospective private-Git files without printing any matched value
make private-repo-preflight PYTHON=.venv/bin/python

# Run Python tests and test the current R code against its matching candidate
make python-tests PYTHON=.venv/bin/python
make r-candidate-test CANDIDATE_RELEASE=canon_029

# Rebuild explorer assets from the promoted release and start the web version
make interactive-data PYTHON=.venv/bin/python
make interactive-web

# Build, but do not promote, a newly named candidate analysis release
make candidate-release RUN_ID=canon_030
```

Prompt sourcing, model generation, translation and annotation can make
external or paid calls. The guarded v2.4 commands, inputs and authorization rules
are listed in the entry-point guide; do not infer permission from the presence
of a local `.env` file.

## Technical references

- Ordered replication procedure:
  [`docs/REPLICATION_GUIDE.md`](docs/REPLICATION_GUIDE.md)
- Current inclusion status:
  [`docs/REPLICATION_STATUS.md`](docs/REPLICATION_STATUS.md)
- Private Git handoff and disclosure boundary:
  [`docs/PRIVATE_REPOSITORY_HANDOFF.md`](docs/PRIVATE_REPOSITORY_HANDOFF.md)
- Adopted response-validity procedure:
  [`docs/RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md`](docs/RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md)
- Final codebook and decision history:
  [`docs/RESPONSE_VALIDITY_CODEBOOK_RATIONALE.md`](docs/RESPONSE_VALIDITY_CODEBOOK_RATIONALE.md) and
  [`docs/RESPONSE_VALIDITY_DECISION_LOG.md`](docs/RESPONSE_VALIDITY_DECISION_LOG.md)
- Current estimands:
  [`docs/CANONICAL_ANALYSES.md`](docs/CANONICAL_ANALYSES.md)
- R script index: [`docs/R_PIPELINE_WALKTHROUGH.md`](docs/R_PIPELINE_WALKTHROUGH.md)
- Completed model-expansion provenance:
  [`docs/OPENROUTER_MODEL_EXPANSION_V1.md`](docs/OPENROUTER_MODEL_EXPANSION_V1.md)
- New-developer route screening:
  [`docs/JURISDICTION_MODEL_EXPANSION_V1.md`](docs/JURISDICTION_MODEL_EXPANSION_V1.md)
- Local-model runtime and admission pilots:
  [`docs/LOCAL_GGUF_MODEL_EXPANSION_V1.md`](docs/LOCAL_GGUF_MODEL_EXPANSION_V1.md)
  records the local admission pilots; the reproducible NYU Torch full-corpus
  implementation is documented in
  [`docs/HPC_LOCAL_GGUF_FULL_V1.md`](docs/HPC_LOCAL_GGUF_FULL_V1.md).
- Current R/code audit:
  [`docs/CODE_ANALYSIS_AUDIT.md`](docs/CODE_ANALYSIS_AUDIT.md)
- The hash-preserving 1 September cleanup manifest:
  [`docs/ARCHIVE_MANIFEST.csv`](docs/ARCHIVE_MANIFEST.csv); later cleanup
  inventory: [`archive/2026-09-04_post_v24_rationalization/README.md`](archive/2026-09-04_post_v24_rationalization/README.md)

Historical paths in frozen manifests are not rewritten. Use the archive
manifest to resolve paths moved during the 1 September 2026 rationalization.
