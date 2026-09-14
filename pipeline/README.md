# R analysis pipeline

The active R files in this directory define the current candidate analysis built
from 299,080 Luna v2.4 response annotations across 24 models. The code treats genuine refusal and
capability failure as separate, potentially overlapping outcomes. It does not
silently treat the original Gemini non-engagement label as a refusal label.

The promoted baseline remains `canon_024`. It inherits the verified 18-model
estimates from `canon_021` and contains the accepted two-main-figure redesign.
`canon_029` is the earlier non-promoted candidate adding Sarvam-105B and Bielik
11B v3.0. Accepted non-promoted `canon_031` adds the completed Torch runs for
Krutrim 2, GigaChat3, EuroLLM 22B and Salamandra 7B. T-pro remains unfinished.
Because the accepted states were built from dirty
trees, a new clean-tree archival release will be required after the expansion
and estimands are frozen.
Test the live code against its matching candidate, then build new work without
promotion:

```bash
make r-candidate-test CANDIDATE_RELEASE=canon_031
CANONICAL_RUN_ID=<new-id> Rscript pipeline/make_release.R --no-promote
```

## Stages

| Stage | Role | Principal outputs |
|---|---|---|
| `01` | Assemble the original panel and six registry-defined expansion sources. | release-scoped `data_clean.RData` and `00_*` summaries |
| `10` | Define the shared analysis frame and statistical helpers. | In-memory objects; bootstrap diagnostics written by callers |
| `11` | Home-region descriptives and standardized associations. | `c02`–`c07` |
| `12` | Paired language and framing contrasts. | `c08`–`c11` |
| `15` | Issue-subsample stability. | `c21` |
| `16` | Fixed prompt UMAP, prompt concentration and cross-model recurrence. | `c22`, `c22b`–`c22d` |
| `17` | v2.4 measurement descriptives and contract. | `c23`–`c27` |
| `18` | Verify and publish the probability-weighted Torch Luna–Sol audit. | `c28`–`c30` |
| `40` | Appendix descriptives for current outcomes. | `a01`–`a04` |
| `20`–`21` | Draw two genuine-refusal main figures and the separate descriptive, capability-failure and heterogeneity appendix from saved estimates. | Fig1–Fig2 and ED1–ED14 |
| `30` + audit | Reject releases that violate the analytical or graphics contract. | `c01b`, non-zero exit on failure |

The exact executable inventory is `PIPELINE_REGISTRY.csv`. The release driver
stops if a root-level R file is not registered or a registered active script or
technical reference is missing.

## File-numbering convention

Numbered files are executable stages, ordered by role rather than by an
expectation that every integer is used: `01` assembles data; `10` supplies the
shared estimator layer; `11`--`17` estimate or describe results; `20`--`21`
render figures; `30` gates releases; and `40` writes appendix descriptives.
Leading-underscore files are sourced helpers. `make_release.R`,
`audit_figures.R`, and `tests_synthetic.R` are named entry points or checks, not
pipeline stages, so they deliberately have no numeric prefix. Gaps are reserved
and do not imply missing files.

## Outcomes

- Primary: Luna v2.4 `genuine_refusal`.
- Separate diagnostic outcome: Luna v2.4 `capability_failure`.
- Measurement sensitivity only: original Gemini `engagement_code >= 4`, named
  `original_nonengagement` in active code.

The helper `_response_validity.R` verifies the original-panel Parquet file.
`_expansion_input.R` reads the machine-readable roster and verifies six
expansion annotation sources, their manifests, indexes, keys, counts, and
hashes. Together the helpers enforce 299,080 observed response keys, 7,175
genuine refusals and 74,598 capability failures.

## Pending analyses

Files under `pending/` are outside the live pipeline. This includes slant,
ideology and moral-foundation analyses because no final adopted outcome
measurement currently supports them, as well as pre-v2.4 mixed figure and
reliability scripts. Nothing in `make_release.R` sources this directory.

## Output and graphics rules

- A release builds in `releases/<run-id>/`; accepted historical releases are
  never edited in place.
- Main and Extended Data figures are PNG only, 600 dpi, with no embedded title,
  subtitle or caption.
- Plotting scripts read estimate tables and do not fit statistical models.
- Promotion occurs only after acceptance and figure-audit checks pass and the
  release conditions are satisfied.

For formulas, units, weights and interpretation, read
`../docs/CANONICAL_ANALYSES.md`. For the manual per-script guide, read
`../docs/R_PIPELINE_WALKTHROUGH.md` and the linked files under
`../docs/r_pipeline/`.
