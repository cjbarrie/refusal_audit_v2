# Pending analyses

Nothing in this directory is run by `pipeline/make_release.R`, sourced by a live
analysis script, or accepted as a current paper result. These files are retained
for inspection because they encode work that may become useful after an outcome
measure and estimand are agreed.

The main reasons for deferral are:

- `02_original_judge_reliability.R` and
  `14_original_judge_uncertainty.R` evaluate the original Gemini engagement
  instrument and its panel judges. They do not evaluate Luna v2.4, for which no
  comparable multi-judge wall-to-wall panel exists.
- `13_slant_moral_content.R` analyzes ideology and moral-foundation fields from
  the original 25% issue subsample. We have not adopted those fields as current
  outcome measures. Their reliability and conditioning rules therefore require
  a separate measurement decision before use.
- `15_mixed_outcome_subsample_stability.R`,
  `20_mixed_pre_v24_figures_main.R`, and
  `21_mixed_pre_v24_figures_extended.R` mix supported refusal analyses with the
  deferred content/judge analyses. They are preserved as pre-v2.4 design
  provenance, not as runnable release stages.
- `40_original_label_appendix.R` describes original engagement categories and
  refusal-justification codes. The live appendix now uses the v2.4 fields.

Before promoting any file here, specify the target construct, validate its
measurement, rewrite it to use the current keyed outcome contract, add a
companion technical document and tests, and register it as active in
`pipeline/PIPELINE_REGISTRY.csv`.
