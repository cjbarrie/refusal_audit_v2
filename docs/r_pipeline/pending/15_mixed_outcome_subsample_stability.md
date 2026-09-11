# Pending `15_mixed_outcome_subsample_stability.R`

Status: retained pre-v2.4 analysis; not run by `make_release.R`.

This script sampled reduced sets of `issue_id` without replacement and carried
all responses for selected issues into each draw. It mixed home, language and
framing statistics with ideology, moral-foundation and original-judge
reliability statistics. Fractions below 100% were repeatedly sampled and
summarized by empirical percentiles; those ranges were design-stability ranges,
not confidence intervals.

It reads the pre-v2.4 `canon` frame plus slant-subsample and judge-panel fields
and historically wrote the `c21` draw, summary, failure and metadata files.
Because several constituent outcomes are not adopted and the old script mixes
constructs in one output family, it must not be used alongside the current c21.
The live replacement is `pipeline/15_subsample_stability.R`, which contains
only genuine refusal, capability failure and supported estimand families.

Before reconsideration, separate each measurement family, adopt and validate
the content outcomes, and rewrite the script against the current v2.4 keyed
contract. Its historical code comments contain the original sampling details.
