# Current R analysis pipeline

This is the index for the R code that produces the canonical working analyses.
Use this page to find the relevant stage, then use the linked page to check its
data, formula, weights, resampling and outputs line by line.

The current analysis code combines the 137,186-row original Luna v2.4 table
with 112,015 completed Luna v2.4 expansion annotations: 249,201 responses from
20 models.
`genuine_refusal` is the primary response-behaviour outcome;
`capability_failure` is analysed separately and may overlap it. The original
Gemini `engagement_code >= 4` measure appears only as an explicitly labelled
measurement sensitivity. `canon_024` is the promoted working release; it
inherits the verified 18-model estimates from `canon_021` and contains the
accepted two-main-figure redesign. The accepted, non-promoted `canon_029`
interim release adds Sarvam-105B and Bielik 11B v3.0 and passes 29/29 numerical
plus 17/17 figure checks; unfinished T-pro is excluded.

Paper-level specifications are in [CANONICAL_ANALYSES.md](CANONICAL_ANALYSES.md).
The exact outcome join is described in
[r_pipeline/_response_validity.md](r_pipeline/_response_validity.md). The
machine-readable inventory is
[pipeline/PIPELINE_REGISTRY.csv](../pipeline/PIPELINE_REGISTRY.csv).

## Run order

```text
full_v1 responses + prompt metadata + expansion label batches
                  |
                  v
01_data_loading.R + hash-verified Luna v2.4 outcomes
                  |
                  v
10_canonical_common.R (shared frame, weights and estimators)
                  |
       +----------+----------+-----------+-----------+
       v          v          v           v           v
      11         12         15          16          17/40
     home   language/frame  stability   UMAP     descriptions
       +----------+----------+-----------+-----------+
                  |
                  v
             20/21 figures
                  |
                  v
        30 acceptance + figure audit
```

`make_release.R` executes this order in an isolated release directory. It never
runs a script under `pipeline/pending/`.

The file names encode the same stage families shown above. Numbers are not
required to be consecutive: `01` is assembly; `10` is shared estimation code;
`11`--`17` are analytical stages; `20`--`21` are renderers; `30` is the release
gate; and `40` is the appendix. Files beginning with `_` are sourced helpers.
The release driver, figure audit and synthetic test runner are named tools, not
stages, and therefore are intentionally unnumbered.

## Active script index

| Script | What it does | Detailed reference |
|---|---|---|
| `01_data_loading.R` | Reconstructs the original panel, verifies its v2.4 labels, and appends the hash-checked expansion panel. | [01_data_loading.md](r_pipeline/01_data_loading.md) |
| `_expansion_input.R` | Verifies the five expansion annotation batches, derives the same two outcomes, and enforces combined counts and keys. | [_expansion_input.md](r_pipeline/_expansion_input.md) |
| `_response_validity.R` | Enforces the outcome file hash, schema, counts and exact key equality. | [_response_validity.md](r_pipeline/_response_validity.md) |
| `10_canonical_common.R` | Creates the analysis frame, weights, issue bootstrap, support checks, logistic models and standardization functions. | [10_canonical_common.md](r_pipeline/10_canonical_common.md) |
| `11_canonical_home.R` | Describes home/away rates and estimates standardized home-region associations. | [11_canonical_home.md](r_pipeline/11_canonical_home.md) |
| `12_canonical_language_framing.R` | Estimates prompt-paired language contrasts and boundary-minus-regular framing contrasts. | [12_canonical_language_framing.md](r_pipeline/12_canonical_language_framing.md) |
| `15_subsample_stability.R` | Measures how estimates deviate from the full result after sampling declared percentages of issues. | [15_subsample_stability.md](r_pipeline/15_subsample_stability.md) |
| `16_prompt_umap.R` | Reuses the fixed English-prompt geometry and describes outcome propensity, concentration and cross-model recurrence. | [16_prompt_umap.md](r_pipeline/16_prompt_umap.md) |
| `17_response_validity.R` | Describes v2.4 outcomes, components, overlap, original-to-final transition and provenance. | [17_response_validity.md](r_pipeline/17_response_validity.md) |
| `40_appendix_descriptives.R` | Produces current model/language and task-behaviour appendix tables. | [40_appendix_descriptives.md](r_pipeline/40_appendix_descriptives.md) |
| `20_figures_main.R` | Draws two genuine-refusal figures linking fixed semantic maps to home and language contrasts; it does not estimate. | [20_figures_main.md](r_pipeline/20_figures_main.md) |
| `21_figures_extended.R` | Draws 14 Extended Data PNGs, including all capability-failure artwork and detailed model-level atlases. | [21_figures_extended.md](r_pipeline/21_figures_extended.md) |
| `30_acceptance.R` | Checks sample, measurement, estimands, files and figure inventory. | [30_acceptance.md](r_pipeline/30_acceptance.md) |
| `audit_figures.R` | Checks PNG-only output, artwork structure and table-to-figure contracts. | [audit_figures.md](r_pipeline/audit_figures.md) |
| `make_release.R` | Builds an immutable candidate and promotes only after all gates pass. | [make_release.md](r_pipeline/make_release.md) |
| `tests_synthetic.R` | Runs fast outcome, weighting, g-computation and bootstrap tests. | [tests_synthetic.md](r_pipeline/tests_synthetic.md) |
| `_orders.R` | Freezes shared category orderings. | [_orders.md](r_pipeline/_orders.md) |
| `_theme.R` | Freezes the PNG export and visual style contract. | [_theme.md](r_pipeline/_theme.md) |

## Pending work

Slant, ideology, moral-foundation, original-judge reliability and other
pre-v2.4 mixed analyses are under `pipeline/pending/`. They are retained for
provenance, but they are not sourced by active scripts, run by the release
driver, or accepted as current paper analyses. See
[pipeline/pending/README.md](../pipeline/pending/README.md) for the exact reason
each file is waiting.

## Safe commands

Run fast checks:

```bash
Rscript pipeline/tests_synthetic.R
```

Build a new candidate without changing the promoted release:

```bash
CANONICAL_RUN_ID=<new-id> Rscript pipeline/make_release.R --no-promote
```

Do not use the largest numbered release directory as a proxy for acceptance.
The promoted pointer and release manifest are the authority. `canon_013` remains
an incomplete historical directory and is not canonical.
