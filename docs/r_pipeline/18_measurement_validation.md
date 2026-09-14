# `18_measurement_validation.R`

## Purpose

This stage keeps the primary analysis and its measurement check separate. The substantive analysis uses the complete Luna v2.4 census for all 49,879 successful Torch responses. This script verifies and republishes the independent Sol v2.4 audit of 1,335 sampled responses. It never replaces a Luna label with a Sol label.

## Inputs and provenance

The source directory is declared in `config/analysis_roster_v1.json`: `annotations/model_expansion_v4/local_gguf_full_hpc_sol_v2_4_audit_v1/`. The audit contains every Luna-coded genuine refusal (381), every Luna case whose refusal status was unassessable (271), a probability sample of assessable capability failures (298), and a probability sample of apparently clean responses (385). Frozen inclusion probabilities supply the inverse-probability design weights.

Before reading estimates, the script checks the final schema gate, sample and target-population counts, and SHA-256 hashes of the final Sol results and both design tables. Sol is a frontier-model reference rather than independent human ground truth.

## Outputs

- `c28_torch_validation_design.csv`: sample composition, target population, models, cost, and final hash.
- `c29_torch_design_weighted_agreement.csv`: design-weighted agreement and kappa for each codebook field.
- `c30_torch_design_based_outcomes.csv`: Luna and Sol prevalence estimates, standard errors, confidence intervals, and differences by model and language.

These tables support measurement-sensitivity reporting. They are not inputs to the home, language, framing, or semantic-atlas estimators.

## Interpretation

For genuine refusal, design-weighted Luna–Sol agreement is 99.87%; Sol sensitivity is 98.78%, specificity 99.88%, precision 84.25%, and F1 0.909 when Sol is treated as the reference. The weighted estimated prevalence is 0.764% under Luna and 0.651% under Sol. Capability-failure and wrong-language classifications agree less closely and should remain diagnostics rather than be folded into refusal.
