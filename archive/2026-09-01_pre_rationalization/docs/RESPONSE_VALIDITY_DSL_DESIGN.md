# DSL reference-sample precision planning

This is a **cost-free design calculation, not a scientific result**. It uses the
probability-weighted 1,306-row GPT-5.6 Sol pilot to approximate the conditional
variance of clean-refusal residuals. It compares phase-two reference-label
sampling error while holding the 624-issue response corpus fixed. It does not
include issue-sampling uncertainty, cross-fit variation, or residual Sol error.

## Candidate designs

Every design labels all 11,475 original code-4/5 responses and draws controls by
stratified SRS without replacement from the code-1/2/3 population. Strata are
`model × prompt language × home status × original engagement code`. Every
populated stratum receives at least one control, after which bounded Neyman
allocation uses the pilot risk with a variance floor.

|   control_budget | family    |   median |   p90 |   maximum |
|-----------------:|:----------|---------:|------:|----------:|
|             1250 | cell_rate |    1.381 | 2.617 |     3.264 |
|             1250 | home      |    1.005 | 1.303 |     1.421 |
|             1250 | language  |    0.647 | 0.697 |     0.718 |
|             1250 | overall   |    0.226 | 0.226 |     0.226 |
|             2500 | cell_rate |    0.948 | 1.691 |     2.204 |
|             2500 | home      |    0.646 | 0.825 |     0.909 |
|             2500 | language  |    0.431 | 0.464 |     0.478 |
|             2500 | overall   |    0.151 | 0.151 |     0.151 |
|             5000 | cell_rate |    0.629 | 1.157 |     1.488 |
|             5000 | home      |    0.400 | 0.520 |     0.589 |
|             5000 | language  |    0.294 | 0.316 |     0.324 |
|             5000 | overall   |    0.103 | 0.103 |     0.103 |
|            10000 | cell_rate |    0.440 | 0.773 |     0.976 |
|            10000 | home      |    0.208 | 0.311 |     0.348 |
|            10000 | language  |    0.197 | 0.211 |     0.217 |
|            10000 | overall   |    0.070 | 0.070 |     0.070 |
|            20000 | cell_rate |    0.282 | 0.494 |     0.597 |
|            20000 | home      |    0.123 | 0.151 |     0.163 |
|            20000 | language  |    0.125 | 0.133 |     0.137 |
|            20000 | overall   |    0.045 | 0.045 |     0.045 |

The current planning recommendation is **2,500 controls**, subject to
the predeclared rule that the maximum expected phase-two SE for each headline
home/language family should be below 1 percentage point and the 90th percentile
of model × language cell-rate SEs below 2 percentage points. If this gate fails
in the table above, use 5,000 rather than selectively altering strata.

## Allocation-model diagnostics

- Apparent probability-weighted pilot Brier score:
  0.0472.
- Apparent probability-weighted pilot log loss:
  0.1660.
- These are deliberately labelled apparent and never support an accuracy claim.

Exact per-estimand calculations are in
`annotations/response_validity_dsl_v1/design_precision_by_estimand.csv`; every
candidate stratum allocation is in `candidate_allocations.csv`.
