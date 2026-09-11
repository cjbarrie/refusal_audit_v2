# `10_canonical_common.R`

## Role in the pipeline

Every estimator sources this file. It verifies and constructs `canon`, defines
weights and resampling, implements the home standardization model, and records
bootstrap diagnostics. It does not write a headline estimate itself.

## Analysis frame

The script loads the release-scoped `CANON_DATA_PATH`, then validates both the
original outcome contract and the expansion contract. `make_release.R` always
rebuilds this file for a full release; its retired `--skip-data` option is
rejected because a mutable saved frame could predate the current roster.
`canon` contains 249,201 unique response
keys, 624 issues, 20 models and five delivered languages. Its primary binary
outcome is `genuine_refusal`; the diagnostic outcome is `capability_failure`;
`original_nonengagement` is observed only for the 137,186 original-panel rows
and is sensitivity only.

Home status is constructed by comparing an issue's region with the fixed home
region of the subject model's developer jurisdiction. `General` is a third
status and never becomes away. `block_id` is `(model,prompt_id)`.

## Weights

The primary nested weights assign equal total mass to each model, equal mass to
each issue within model, and equal mass to prompts within model-issue. Response
weights and equal-model-only weights are named alternatives. All weights sum to
one over the frame passed by the caller.

## Bootstrap

`boot_canon()` samples `issue_id` clusters with replacement exactly `B` times.
If issue A is drawn three times, its copies receive distinct
`bootstrap_issue_instance` identifiers. A statistic that uses nested weights
therefore counts three sampled issue instances rather than collapsing them back
to A. Failed draws remain failed, contribute to the reported failure rate and
are never replaced. Intervals are percentile intervals over successful planned
draws and are marked unreliable above the declared failure threshold.

## Home model and standardization

`build_f()` constructs
`OUTCOME ~ home * model + tier + domain + route` when more than one model is
present, and uses `OUTCOME ~ home + tier + domain + route` for a single-model
fit. Any nuisance covariate with no variation in the supplied subset is omitted
rather than passed as a one-level factor. `fit_logit()` fits a
binomial GLM while preserving warnings. `gcomp()` predicts each target row with
`home=1` and again with `home=0`, then averages the prediction difference using
the requested weights. With `return_levels = TRUE`, it also returns the two
weighted standardized risks. Their stored identity is checked explicitly:
`home_risk - away_risk = contrast`. Separation, non-finite predictions and
support are reported rather than silently repaired.

## Outputs and limits

`flush_diag()` writes or updates `c18_bootstrap_diagnostics.csv` using unique
run/label keys. Original multi-judge helper functions remain in this file only
so pending historical scripts can be inspected; the active release never calls
them. Predictive standardization controls measured composition but does not
identify a causal home effect.
