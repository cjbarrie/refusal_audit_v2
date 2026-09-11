# `40_appendix_descriptives.R`

This script produces descriptive appendix tables from the current Luna v2.4
frame. It does not run independent-sample hypothesis tests.

- `a01_outcome_rates_by_model_language.csv` reports genuine refusal and
  capability failure for each observed 20-model/language cell. These are raw
  rates, not language effects.
- `a02_task_behavior_composition.csv` reports the full v2.4 task-behavior
  distribution within each cell.
- `a03_refusal_type_composition.csv` reports explicit versus implicit refusal
  among rows already classified as genuine refusal. It is not an old Gemini
  justification taxonomy.
- `a04_deepseek_paired_outcomes.csv` applies the prompt-paired Chinese-minus-
  English construction to DeepSeek for genuine refusal and capability failure.

The a04 interval resamples issues and preserves the within-prompt pair. It uses
`CANON_B_SENS` planned draws (default 500), so the value recorded by the release
manifest is the value actually used. The
other tables are realized-corpus descriptions. Missing component values remain
missing and no capability failure is recoded as refusal or engagement.

If the same model has Arabic rate 5% and English rate 3% in a01, the two-point
gap cannot be called a language effect because prompt composition is not held
fixed there. The corresponding c08/a04 paired construction is the appropriate
contrast.
