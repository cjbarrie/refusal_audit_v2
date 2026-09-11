# Pending: `13_slant_moral_content.R`

This is not a current release stage. The ideology and moral-foundation fields
do not yet have an adopted outcome measurement and validation procedure.

**Purpose.** Describe ideological-slant and moral-foundation content among responses that received deep-pass labels, including overall, jurisdiction, model, joint-outcome, coverage, and judge-sensitivity views.

**Input/unit/rules.** Canonical rows with `has_slant`, four ideology fields (`-2…2`), and six binary foundation fields. Unit is a response. Eligible-but-uncoded/missing labels remain missing; refused/non-engaged output is represented separately in joint outcomes rather than set to neutral/absent. The 156-issue without-replacement slant sample is the inferential sample for a frozen 624-issue battery.

**Estimands/inference.** Ideology reports five-bin shares and signed means; moral prevalence reports binary invocation rates. Overall estimates give models equal weight; jurisdiction estimates nest models equally. Design-based delete-one-issue jackknife with finite-population correction gives battery intervals; issue-cluster bootstrap intervals are retained for superpopulation sensitivity. Seeds are canonical and failed replicates are reported. Per-model c13/c15 use identical definitions; c19 recomputes on all-judge common support.

**Outputs.** `c12_ideology_distribution.csv`, `c12b_slant_coverage.csv`, `c13_ideology_by_model.csv`, `c14_moral_prevalence_equal_model.csv`, `c15_moral_by_model.csv`, `c16_content_joint_outcomes.csv`, optional `c19_content_by_judge.csv`. Figure 3 and ED5/ED6 consume them.

**Worked trace.** A coded response with economic score `-1` adds weighted mass to the `-1` bin and `-1` to the signed mean. If its care label is missing, it contributes to `n_missing`, not the “care absent” denominator.

**May infer:** prevalence/distribution in the tested slant sample and, with FPC, finite-battery uncertainty. **May not infer:** population ideology, model intent, or content among uncoded non-engagement responses.
