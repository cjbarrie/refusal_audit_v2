# Targeted human augmentation for the home-refusal estimand

**Status (2026-08-25): planning complete; no response IDs have been drawn, no
additional annotation is authorized, and no provider call was made. The former
123-case classifier reserve has been retired for the separate all-700 internal
bake-off; that decision does not authorize using those cases as an ordinary
probability sample for the home estimand.**

**Roster timing gate.** The 680-selection design targets the current frozen
11-model, 137,186-response population. If the planned model expansion belongs
in the same paper, do not draw these rows yet. Complete and freeze the enlarged
response population, reconstruct its standardized-home coefficients, and rerun
the planning design once. The current allocation remains a workload benchmark;
it is not automatically valid for an enlarged equal-model target.

**v2.2 update (2026-08-26).** The completed direct human-weighted diagnostic
finds only two genuine-refusal events contributing to any standardized-home
coefficient, both in the US contrast. CN, EU, India and MENA have no relevant
events in the original probability sample. This strengthens the conclusion
that the existing sample cannot identify the home contrast. The 680-selection
allocation below remains a workload benchmark, not a draw-ready design; rerun
it after the final model roster is frozen using the revised v2.2 outcome and
student probabilities.

## Recommendation

Freeze an initial targeted sample of **680 English home/away selections**. Match
the selected keys against already completed human reviews before creating the
queue, so 680 is an upper bound on genuinely new annotation tasks. Stop after
that wave if the predeclared precision gate passes. If it fails, activate a
predeclared augmentation of at most 570 further selections, for a maximum of
**1,250 targeted selections in total**.

This is not another general enrichment wave. It is designed only for the five
jurisdiction-specific standardized genuine-refusal home-minus-away estimates.

## Why 680 rather than 300 or 400

The original 300 contain only 39 English home/away responses and three genuine
refusals relevant to the home analysis. They contribute no human refusal event
to the CN, EU or India standardized contrasts, one to MENA and two to the US.

An equal allocation of 300--600 cases across the ten jurisdiction × arm cells
is inefficient because the standardized estimator gives different responses
different leverage. In a conservative simulation, even 600 equally allocated
responses left several home contrasts wider than the five-percentage-point
planning target. The accepted planner therefore allocates within frozen
leverage-by-risk strata using anticipated Neyman allocation.

Two outcome calibrations bracket the workload:

- **Initial scenario:** human event probability is `0.75 × frozen Sol refusal
  probability`. This requires 680 selections.
- **Conservative reserve scenario:** human event probability is `0.50 × frozen
  Sol probability + 0.005`, clipped to one. This allows refusals missed by the
  machine predictor and requires at most 1,250 selections.

These are workload assumptions, not substantive models and not paper results.
The first wave is stopped or augmented using actual human residuals, not by
assuming either calibration is true.

## Initial allocation

| Jurisdiction | Initial selections | Anticipated half-width | Anticipated genuine refusals: home / away |
|---|---:|---:|---:|
| CN | 190 | 2.72 pp | 29.0 / 5.1 |
| EU | 120 | 0.56 pp under the initial calibration | near zero / near zero |
| India | 80 | 4.98 pp | 5.8 / 9.9 |
| MENA | 170 | 1.70 pp | 8.3 / 5.1 |
| US | 120 | 3.28 pp | 5.3 / 5.5 |
| **Total** | **680** |  |  |

The conservative maximum is CN 330, EU 120, India 160, MENA 420 and US 220,
totalling 1,250. The second wave adds only the difference between the initial
and conservative stratum allocations.

## EU is a zero-event verification problem

The frozen predictor assigns essentially zero refusal probability throughout
both EU arms, and the original outcome also had a structural zero. Requiring
five EU refusals would force an enormous sample in search of events that may not
exist. EU therefore receives a simple random sample without replacement of 60
home and 60 away responses.

If both arms produce zero genuine refusals, the one-sided rule-of-three bound is
`3/60 = 5%` per arm (the exact bound should be reported in the analysis). EU is
then reported as a zero-event result with a one-sided bound, not as a
zero-variance point estimate. If an event appears, EU switches to the ordinary
event-support and estimand-precision gate.

## Sampling mechanics

1. Restrict the frame to English responses with `home_status` equal to `home`
   or `away`.
2. Reconstruct the exact Stage-17 standardized-home response coefficient
   `a_i` for every row.
3. Within each non-EU jurisdiction × arm, rank rows by
   `|a_i| × sqrt(p_i(1-p_i))`, where `p_i` is the frozen Sol probability.
4. Split each arm into five fixed rank bands, resolving ties with the frozen
   response key.
5. Allocate at least two selections to every band and distribute the remaining
   workload by the anticipated reduction in design variance. Draw by SRSWOR
   inside each band using a frozen seed.
6. Draw EU by SRSWOR separately within its two arms.
7. Do not reveal human outcomes, original judge labels or model identity in the
   review interface. Because every new response is English, no translation run
   is needed.
8. Match drawn keys to completed human reviews only after the draw. Reusing an
   already collected label is allowed because the new selection did not use its
   outcome. Record every reuse. The retired reserve's labels may be reused only
   when a response is independently selected by this new probability design;
   they do not acquire an inclusion probability merely because they entered
   the internal bake-off.

The primary home estimator should treat the original human-labelled rows as
known and estimate the remaining finite-population residual total with the new
conditional probability sample. The implementation must derive the conditional
first- and pairwise-inclusion probabilities; it must not concatenate sampling
weights from the old and new designs.

## Predeclared first-wave gate

After all initial selections have a valid human label, compute only the
following adequacy outputs before deciding whether to activate the reserve:

- For CN, India, MENA and US: at least five genuine refusals in both the home
  and away arms.
- For every jurisdiction: human-sampling 95% half-width no greater than five
  percentage points for the exact standardized-home estimator.
- No missing keys, duplicate responses, invalid labels or failed variance
  replicates.
- Report effective sample size and the largest normalized residual-correction
  contribution; no single response may silently dominate a result.
- For EU with zero events: the predeclared one-sided upper bound must be no
  greater than five percent in both arms.

If every gate passes, stop. If any non-EU jurisdiction fails, activate only its
predeclared stratum increments, subject to the overall 1,250-selection cap.
Failure at the cap is reported as insufficient support; it is not repaired by
changing the estimand or sampling rule after seeing the results.

## Human-review burden

At 30 seconds per new response, 680 tasks require about 5.7 hours; at 45 seconds,
about 8.5 hours. Reused existing labels reduce this. The maximum 1,250-task
design would require approximately 10.4--15.6 total hours before reuse. A small
blinded repeat subset may be added for reliability, but repeat work does not
count toward the estimand-support totals.

## Reproducibility

```bash
python scripts/response_validity.py plan-home-human-augmentation
```

The command writes only aggregate planning artifacts under
`annotations/response_validity_human_v2/home_augmentation_planning_v1/`:

- `scenario_summary.csv`;
- `stratum_allocations.csv`;
- `workload_totals.csv`;
- `planning_manifest.json`.

It deliberately emits no response ID or annotation packet. A separate command,
design review and explicit user approval are required before drawing the 680
initial selections.
