# Archived R analyses

Nothing under this directory is sourced by `pipeline/make_release.R`, accepted
as a current result, or shown in the canonical figures. The live executable map
is `pipeline/PIPELINE_REGISTRY.csv`; the manual guide is
`docs/R_PIPELINE_WALKTHROUGH.md`.

## Contents

- `pre_v24_luna/`: the immediately preceding home, language, UMAP,
  response-validity, acceptance and test code. These scripts used original or
  intermediate outcome definitions and were replaced by the v2.4 stages.
- `precanonical_v1/`: the first estimand surface (`e`/`d` tables and early
  figures), including unpaired language comparisons and odds-ratio home models.
- `precanonical_v2/`: the later probability-scale estimands whose issue
  bootstrap did not preserve repeated cluster draws correctly.
- `precanonical_appendix/`: original-Gemini descriptive appendix programs.
- `exploratory_umap/`: exploratory projection code superseded by the one fixed
  geometry produced by active stage 16.
- `retired/` and other dated subdirectories: discontinued utilities retained
  only to trace earlier outputs.

Archived scripts may contain old relative paths and output names. They are
reference code, not maintained commands, and must never be run against live
canonical directories. Historical results that matter are preserved in their
release or dated root archive. Slant and moral-foundation code that may be
revisited is in `pipeline/pending/`, where its unresolved measurement status is
explicit.

| Role | Current file |
|---|---|
| Data assembly | `pipeline/01_data_loading.R` |
| Shared estimators and bootstrap | `pipeline/10_canonical_common.R` |
| Home-region associations | `pipeline/11_canonical_home.R` |
| Paired language and framing contrasts | `pipeline/12_canonical_language_framing.R` |
| Stability diagnostics | `pipeline/15_subsample_stability.R` |
| Fixed semantic geometry | `pipeline/16_prompt_umap.R` |
| v2.4 measurement summaries | `pipeline/17_response_validity.R` |
| Main and Extended Data figures | `pipeline/20_figures_main.R`, `pipeline/21_figures_extended.R` |
| Release gates | `pipeline/30_acceptance.R`, `pipeline/audit_figures.R` |
| Appendix descriptives | `pipeline/40_appendix_descriptives.R` |
