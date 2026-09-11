# Pending: `14_original_judge_uncertainty.R`

This is not a current release stage. It perturbs the original Gemini instrument
and cannot quantify uncertainty in the final single-model Luna v2.4 census.

**Purpose.** Re-estimate headline measurements under each judge on explicit common support, separating instrument variability from sampling variability.

**Input/unit/rules.** Shared panel loader from stage 02 plus canonical English keys and home covariates. Unit is response × judge; comparisons use pairwise or all-judge intersections. Different codebook versions are not silently pooled. Missing judge ratings restrict support and are documented in `c17c`.

**Estimands/models.** `c17` gives headline quantities by instrument; `c17b` refits the exact stage-11 binomial-logit g-computation under each judge; its observed judge-point envelope is not a confidence interval. `c17d` bootstraps the paired judge-minus-canonical estimate on the same responses/issues, retaining induced dependence. Issue-cluster resampling uses `B_JUDGE`, fixed seeds, and explicit failures.

**Outputs.** `c17_measurement_sensitivity.csv`, `c17b_judge_envelope.csv`, `c17c_judge_support.csv`, `c17d_judge_paired_differences.csv`; Figures ED1/ED7 and acceptance consume them. If panel coverage is absent, explicit empty tables are written rather than stale global files reused.

**Worked trace.** On one common-support response, judge J's binary label minus the canonical label is retained as a paired contribution; resampling its issue moves both labels together. Subtracting two independent interval endpoints would be incorrect.

**May infer:** sensitivity to available machine instruments. **May not infer:** which judge is true or human validity.
