# Preliminary human-weighted v2.2 estimates

**Status (2026-08-26): complete local diagnostic; not a canonical paper
release. No provider call was made.**

## What this calculation does

This is the first population calculation using the revised refusal structure.
It uses only the original 300-case probability sample to estimate quantities
for the frozen 137,186-response corpus. The 400 deliberately enriched cases do
not receive population weight.

The human outcome comes from
`annotations/response_validity_human_v2/decomposed_review_v2_2/harmonized_evaluation_gold_v2_2.parquet`.
Within the probability sample, 45 rows have direct v2.2 review and 255 have a
non-ambiguous v2.1 class that determines genuine refusal and capability
failure. There are no unresolved rows.

For a linear estimand written as `theta = sum_i a_i Y_i`, the direct
Horvitz--Thompson estimate is:

```text
theta_hat = sum_{i in the 300-case sample} a_i Y_i / pi_i
```

Here `pi_i` is the exact probability that response `i` entered the union of the
global, model-by-language and priority components of the human draw. Variance
uses the exact pairwise inclusion probabilities of that union design. The
response coefficients `a_i` are built by `build_estimand_coefficients()` in
`src/refusal_audit/response_validity/estimand_precision.py`.

The implementation is
`src/refusal_audit/response_validity/stage18_preliminary.py`, called by:

```bash
python scripts/response_validity.py run-preliminary-stage18
```

## Main diagnostic results

| Quantity | Estimate | Human-design 95% interval | Human events |
|---|---:|---:|---:|
| Genuine-refusal prevalence | 1.83% | 0.77% to 2.90% | 13 |
| Capability-failure prevalence | 20.34% | 17.15% to 23.54% | 71 |

The genuine-refusal result meets the provisional two-percentage-point
half-width target. Capability failure is clearly common, but its direct
interval is wider than that target.

The paired target-language-minus-English genuine-refusal estimates are small:
Arabic -0.76 percentage points, Hindi +0.35, Russian -1.52 and Chinese -0.06.
Every interval includes zero and has a half-width between 3.2 and 4.4 points.
None meets the declared three-point precision target; Arabic and Russian also
have fewer than five human refusal events in their contributing rows.

Capability-failure language differences are much larger in this small sample:
Arabic +20.85 points, Hindi +33.42, Russian +24.85 and Chinese +11.50. Their
intervals remain wide, and each contrast has only one capability event in its
English/negative arm. They should not yet be treated as settled effects.

## What this says about the home finding

The current probability sample cannot support the standardized home analysis.
Only two relevant genuine-refusal events enter any standardized-home
coefficient, both in the US contrast. CN, EU, India and MENA have zero relevant
events. The resulting zero estimates are zero-event failures, not evidence of
an exact zero effect. The provisional US estimate is +29.6 percentage points
with an interval from -23.3 to +82.6 points, which is far too imprecise to
interpret.

The existing 680-selection home design therefore remains a useful workload
benchmark. It must be recalculated after the final subject-model roster is
frozen and before any response IDs are drawn. This diagnostic does not
authorize that draw.

## Outputs

All files are under
`annotations/response_validity_human_v2/stage18_preliminary_v2_2/`:

| File | Contents |
|---|---|
| `direct_estimates.csv` | Every audited family, cell and outcome |
| `main_estimands.csv` | Prevalence, paired-language and standardized-home rows |
| `home_support.csv` | Home estimates, event counts, precision gates and recommendation |
| `manifest.json` | Input and implementation hashes, output hashes and assumptions |

These intervals include human-sampling uncertainty conditional on the frozen
response corpus. They do not yet include whole-issue sampling uncertainty,
student-fitting uncertainty or uncertainty from a future expanded model roster.
