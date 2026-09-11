# `15_subsample_stability.R`

This script asks how the supported v2.4 point estimates change when fewer
issues are retained. It samples `issue_id` without replacement at 25%, 50%,
75% and 100% by default. Every response, model, language and prompt belonging
to a sampled issue travels with it; individual responses are never sampled.

For each subset it recomputes standardized home, prompt-paired language and
issue/model-paired framing quantities for genuine refusal and capability
failure. Slant and moral-foundation quantities have been removed from the live
script and retained in `pipeline/pending/15_mixed_outcome_subsample_stability.R`.

Fractions below 100% use `CANON_STABILITY_REPS` repetitions (default 100) and
seed `CANON_STABILITY_SEED` (default 20260812). The output records every planned
draw, including non-estimable ones, and its exact seed. The deterministic seed
is `base_seed + round(1000*fraction) + replicate`; the metadata JSON records
that rule. Summary bands are the median and empirical
5th/95th percentiles across repeated subsets. They are explicitly **not
confidence intervals** and do not replace the issue bootstrap used by the main
estimators.

Each draw is joined to its estimate from the full 100% issue set. The draw
table therefore stores the signed and absolute deviation from that full-data
estimate, in percentage points. The summary stores the median and 5th--95th
percentiles of the signed deviation plus the median absolute deviation. These
tables are retained as diagnostics, but the current figure inventory does not
plot them: the empirical bands were difficult to interpret and are not
inferential intervals. They can answer a specific robustness question without
being presented as generic uncertainty figures.

Outputs are `c21_subsample_draws.csv.gz`, `c21_subsample_summary.csv`,
`c21_subsample_failures.csv` and `c21_subsample_metadata.json`.

A 50% draw first selects roughly 312 of 624 issues, reconstructs all response
rows for them, and refits/recomputes each statistic. Failure of one jurisdiction
fit is recorded for that planned draw; no replacement issue sample is drawn.
