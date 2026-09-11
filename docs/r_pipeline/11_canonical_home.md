# `11_canonical_home.R`

## Scientific question and sample

This script asks whether models respond differently to issues from their
developer jurisdiction's home region. The primary sample is English responses
on home or away issues. General issues appear in descriptive rates but are
excluded from every home-minus-away contrast.

## Outcomes

- `genuine_refusal`: primary Luna v2.4 outcome;
- `capability_failure`: separate diagnostic outcome;
- `original_nonengagement`: original Gemini code 4--5, observed only for the
  original 11-model panel and refitted there as a measurement sensitivity.

The outcomes are never substituted for one another. A response can be both a
genuine refusal and a capability failure.

## Estimands

`c02` reports raw rates and an unadjusted equal-model home-minus-away
difference. The headline `c04` quantity for jurisdiction `j` and outcome `Y` is

`sum_i w_i [m_j(1,X_i)-m_j(0,X_i)]`,

where `m_j` is the fitted binomial-logit mean and `X` contains subject model,
prompt tier, topic domain and sourcing route. `w` is the nested target from
stage 10. The headline table estimates the two current outcomes. The original
measure is written separately in `c07`, because it necessarily changes both the
outcome and the model roster.

This is covariate-standardized predictive association. Home status is not
randomized and issue region is related to issue substance, so the result is not
a causal effect of being a home topic.

## Support and inference

The full-target result may extrapolate into model × domain × route × tier cells
observed in only one arm. `c06` lists those cells; `c06b` reports how much
nested target weight survives a common-support restriction. `c07` separately
changes response weighting, support, or outcome measurement so unlike
sensitivities are not presented as one estimand.

The primary genuine-refusal rows use `CANON_B_HEAD` issue-cluster bootstrap
draws (default 2,000). Other outcomes and exploratory rows use `CANON_B_SENS`
(default 500). Planned failures are counted and never resampled away.

For every estimable `c04` row, the script stores the standardized predicted
risk with all target rows set to home, the corresponding risk with all rows set
to away, and their difference. Bootstrap intervals apply to the difference;
the two levels are descriptive model-based predictions and show whether the
same percentage-point contrast occurs at a low or high baseline.

## Outputs

- `c02_home_descriptive_english.csv`;
- `c03_home_descriptive_all_languages_supplement.csv`;
- `c04_home_standardized.csv`;
- `c05_home_by_model.csv`;
- `c06_home_overlap.csv` and `c06b_common_support_diagnostics.csv`;
- `c07_home_sensitivities.csv`.

Main Figure 1 reads the `c02`, `c04`, and `c05` genuine-refusal rows. ED1--ED2
read the stored standardized home and away risks, and ED7--ED8 show explicitly labelled
model-specific estimates. Original non-engagement remains a table-only
sensitivity.

## Worked example

For a US-model response to a US issue, observed `home=1`. The fitted model
predicts that row twice, once after setting home to one and once to zero while
holding its tier/domain/route/model fixed. The weighted difference contributes
to the US standardized estimate. It is a counterfactual prediction from the
model, not a matched observation of the same issue as both home and away.
