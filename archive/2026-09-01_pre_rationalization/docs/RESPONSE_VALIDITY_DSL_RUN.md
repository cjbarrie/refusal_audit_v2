# GPT-5.6 Sol reference run and DSL assembly record

## Status and scope

This document is the immutable technical record for the completed
`response-validity-dsl-v1.0` reference run. It records the machine-reference
measurement and wall-to-wall design-based supervised-learning (DSL) assembly.
It does **not** claim that GPT-5.6 Sol is human ground truth, and it does not by
itself establish any home-topic or language effect.

The fixed population contains 137,186 canonical
`(prompt_id, prompt_language, model)` responses. The reference design contains
all 11,475 original `engagement_code >= 4` rows plus a 2,500-row stratified
SRSWOR sample of code-1/2/3 controls. The design was frozen before the full Sol
run. Exact design details and the estimator are in
[`RESPONSE_VALIDITY_DSL.md`](RESPONSE_VALIDITY_DSL.md).

## Authorization, pricing, and routing

- User authorization recorded: 2026-08-19 09:54:54 UTC.
- Authorized maximum provider cost: $95.00.
- Pilot-calibrated expected cost: $75.088780625.
- Calculated 20% contingency recommendation: $91.
- Actual incremental provider-reported cost: **$75.264048625**.
- Model ID: `openai/gpt-5.6-sol`.
- Provider restriction: `only = ["openai"]`, `allow_fallbacks = false`.
- Reasoning: disabled; observed reasoning tokens: zero.
- Verified promotional prices: $2.50/M ordinary input, $0.25/M cache read,
  $3.125/M cache write, and $15/M output.
- The ceiling guard reserved undiscounted prices for every in-flight batch, so
  a mid-run promotional price change could not silently exceed authorization.

The paid calls ran from 2026-08-19 09:55:24.913291 UTC through
2026-08-19 10:47:07.739233 UTC. Exactly 1,172 byte-identical v1.1 pilot labels
were reused at zero incremental cost; 12,803 new calls were made.

## Prompt, blinding, and codebook

Sol received only:

1. the target language;
2. the English reference prompt;
3. the target-language prompt; and
4. the model response.

It did not receive the original engagement code, original justification,
subject-model identity, developer jurisdiction, audit stratum, or prior judge
labels. The v1.1 prompt SHA-256 is
`647d678823f3676fd867655a96bcabcdf392195e3202b31966e5a3dcff594969` and the
schema SHA-256 is
`a76301ba0013027941c5c6368022bd7fb59c738643f581165fac7759a493e3c2`.

The reference outcome `clean_genuine_refusal` requires coherent or partly
coherent communicated noncompliance, target or mixed language, and no technical
failure. Capability failure and coherent pivot remain separate outcomes.
Original code 4/5 is retained as `judge-coded non-engagement` and is never
overwritten.

## Execution accounting

The append-only raw file contains 14,018 records:

- 13,975 unique successful reference IDs;
- 43 recorded failed attempts over 27 unique IDs;
- zero unresolved IDs after resumable cleanup;
- 16 successful records with a documented deterministic consistency repair.

All 43 failed attempts arose from the same post-schema logical conflict: Sol
marked output incoherent or unassessable while also marking an explicit or
implicit communicated refusal. Repeated calls left 16 persistent cases. The
original v1.1 codebook explicitly says unintelligible failure is not refusal.
For those 16 cases only, the runner changed the signal to `none` when coherence
was `incoherent`, or to `unassessable` when coherence was `unassessable`, and
cleared the evidence span. It then reran the complete validator. The untouched
model JSON, validation error, and named repair rule are stored in
`validation_repair`. No other inconsistency is repaired.

New paid calls used 20,697,314 prompt tokens and 827,221 completion tokens,
including 18,134,075 cache-write tokens and 98,377 cache-read tokens. Provider
responses reported only `openai/gpt-5.6-sol`.

## Design and artifact hashes

| Artifact | SHA-256 |
|---|---|
| Population key frame | `2b1f4be22ef82ccbe071dfba766422518107230fcd2e1ccf7602b84f56a538bb` |
| Reference keys | `985fd82ea0bda389130b933d5c9969fcff5fcfb56f86755826f4c019b54e87a4` |
| Allocation CSV | `a4e612038cda46814b14912b0ef0c396c433471a3ea03916ee1b9c516e3d8cf6` |
| `reference_universe.parquet` | `097021d0c415daf262a430c2e2bccf05868c56c455205b959047632e6c57fa19` |
| `sol_reference_labels.jsonl` | `82ef781a69d514af3f23f74d0e2553325fc45c7b8414a298dde3a00b759cb778` |
| `assembled_reference_labels.parquet` | `3629963e2d30316b46f7a43e9cda76f820444e69c3470b9adb82974141f2c06e` |
| `dsl_pseudo_outcomes.parquet` | `5a3665187eaf13013e5b4de40fd70e67ef50b2206efd637a9c0756482ea5e1ef` |
| `dsl_crossfit_diagnostics.csv` | `d32ce298ea10e01d0a0b539bc826a950d590c14746879e8ef2c9caa2089ac020` |

The manifest is
`annotations/response_validity_dsl_v1/reference_manifest.json`. The raw JSONL
is the provider-level audit trail; the Parquet files are reproducible assembled
artifacts. Secrets and reasoning traces are absent.

## Reference-label composition

Among the 11,475 original code-4/5 census rows:

| Sol outcome | Count | Rate |
|---|---:|---:|
| Clean genuine refusal | 2,441 | 21.2723% |
| Capability failure | 6,835 | 59.5643% |
| Coherent pivot | 460 | 4.0087% |

Among the 2,500 sampled controls, the unweighted counts are 115 clean genuine
refusals, 149 capability failures, and 20 coherent pivots. Those raw control
proportions are not population estimates because sampling probabilities vary.
The Hájek control estimates are 1.0573%, 13.2351%, and 0.8879%, respectively.

Across the full 137,186-response population:

| Outcome | Reference HT | Prediction only | Rectified DSL |
|---|---:|---:|---:|
| Clean genuine refusal | 2.7482% | 2.7035% | 2.7754% |
| Capability failure | 17.1103% | 17.5978% | 17.3484% |
| Coherent pivot | 1.1489% | 1.2936% | 1.2188% |

The prediction-only column is potentially biased and is retained only as a
diagnostic. The reference HT and rectified DSL columns use known reference
inclusion probabilities. These are descriptive population prevalences, not
home or language effects.

## DSL construction and diagnostics

The DSL assembly uses five issue-level folds and ten fixed repeated partitions.
For each outcome it writes the cross-fitted prediction, between-repeat
prediction SD, inverse-probability residual correction, and rectified
pseudo-outcome for every population response, plus each of the ten
repeat-specific rectified pseudo-outcomes. Pseudo-outcomes are deliberately not
clipped to `[0,1]`. The downstream file contains only canonical keys and these
analysis columns; prompt/response text remains in the separately hashed feature
frame and is not duplicated into the estimator artifact.

The diagnostic file has 150 rows: three outcomes × ten repeats × five folds.

| Outcome | Mean weighted Brier | Brier range | Mean weighted log loss | Log-loss range |
|---|---:|---:|---:|---:|
| Clean genuine refusal | 0.013151 | 0.007770–0.020300 | 0.052308 | 0.027899–0.098900 |
| Capability failure | 0.042018 | 0.023235–0.073563 | 0.153382 | 0.084907–0.377125 |
| Coherent pivot | 0.012635 | 0.004573–0.023984 | 0.080161 | 0.023317–0.186790 |

The completed wall-to-wall output contains 137,186 unique canonical keys and
the three rectified outcomes. The reference-label file contains 13,975 unique
keys. Eighteen repository Python tests passed after the run and assembly.

## Inferential boundary and next integration

These results target the frozen Sol measurement construct. Human review is
still required to quantify residual Sol error. Repeated Sol calls establish
consistency, not truth.

Canonical integration must retain four distinct quantities wherever feasible:

1. original judge-coded non-engagement;
2. reference-only HT/Hájek estimate;
3. prediction-only diagnostic; and
4. rectified DSL estimate.

Home analyses remain descriptive or standardized associations unless their
identification assumptions support stronger language. Prompt-paired language
contrasts retain the strongest design-based causal interpretation available,
subject to translation equivalence, no interference, and a stable response
generation regime. Content analyses remain conditional on the original content
annotation sample unless recovered responses are separately annotated.

### Post-run variance audit

The integration review found 207 noncensus control strata with a single sampled
row. This did not invalidate v1.0 HT/DSL points, but it prevented empirical
within-stratum SRSWOR variance estimation. A label-blind SRS augmentation was
authorized and completed as v1.1 and is documented in
[`RESPONSE_VALIDITY_DSL_AUGMENTATION.md`](RESPONSE_VALIDITY_DSL_AUGMENTATION.md).
The final design has no noncensus singleton stratum. Production integration must
use v1.1 inclusion probabilities and retain v1.0 as a version sensitivity.

## v1.1 completed-design addendum

The authorized 207-row label-blind augmentation completed on 2026-08-19. All
207 calls succeeded. Incremental cost was **$1.303606875** and cumulative v1.0
plus v1.1 cost was **$76.567655500**, below the cumulative $95 hard ceiling.
Reasoning tokens and validation repairs were both zero. The final reference
design has 14,182 unique keys, including 2,707 controls, and no noncensus
stratum with fewer than two observations. Exact selection logic, payload,
hashes, and provider accounting are in
[`RESPONSE_VALIDITY_DSL_AUGMENTATION.md`](RESPONSE_VALIDITY_DSL_AUGMENTATION.md).

Refitting five issue-level folds over ten fixed repeated partitions produced
137,186 population rows, 30 repeat-specific pseudo-outcome columns, and 150
cross-fit diagnostics. The completed v1.1 population points are:

| Outcome | Reference HT | Prediction only | Rectified DSL |
|---|---:|---:|---:|
| Clean genuine refusal | 2.7817% | 2.7171% | **2.7963%** |
| Capability failure | 17.5236% | 18.2076% | **18.0112%** |
| Coherent pivot | 1.2761% | 1.3802% | **1.3748%** |

These point estimates are invariant to the number of downstream bootstrap
replicates. Their production intervals are generated by
`pipeline/17_response_validity.R` using 500 whole-issue plus Rao–Wu phase-two
replicates and ten-split variance; smoke-run intervals must never be reported.

## Production canonical-integration run

The 500-replicate integration completed on 2026-08-19 with four deterministic
forked workers. A three-replicate serial-versus-parallel equivalence test first
produced identical data frames for all eight output tables (8/8). Every DSL and
original family then completed 500/500 replicates: maximum failure rate 0,
zero non-finite point estimates, zero non-finite inferential standard errors,
and zero non-finite simultaneous bands. Local synthetic tests passed 43/43;
Python assembly/provenance tests passed 17/17. A combined candidate run passed
113/113 analytical acceptance checks and the complete figure audit. It has not
been promoted as `canon_014` because the working tree is not yet a stable commit.

### Standardized home association

Values are percentage-point home-minus-away associations. Brackets are 95%
max-|t| simultaneous bands across the five jurisdictions separately within each
outcome family.

| Jurisdiction | Original judge-coded non-engagement | DSL genuine refusal | DSL capability failure |
|---|---:|---:|---:|
| CN | 16.03 [9.93, 22.13] | 4.59 [−1.12, 10.31] | 13.84 [−10.24, 37.93] |
| MENA | 4.03 [0.69, 7.38] | 1.76 [−2.24, 5.75] | −11.00 [−49.93, 27.93] |
| India | −3.55 [−8.31, 1.20] | −2.40 [−8.60, 3.79] | 0.38 [−3.12, 3.89] |
| US | 1.33 [−1.15, 3.82] | 2.70 [−4.31, 9.72] | −0.04 [−0.16, 0.08] |
| EU | 0.00 [0.00, 0.00] | 2.53 [−9.69, 14.75] | 0.13 [−0.99, 1.24] |

The historical positive CN and MENA home findings do **not** remain resolved as
genuine-refusal associations under corrected measurement: all five genuine-
refusal simultaneous bands include zero. Capability-failure bands also include
zero and are especially imprecise in CN and MENA. This does not prove absence;
it shows that the original home result cannot be presented as a robust genuine-
refusal finding under the current reference design. Home is not randomized, so
all three columns remain standardized associations rather than causal effects.

### Prompt-paired language contrast

Values are target-language minus English percentage points, paired within
model × prompt and then averaged equally across models. Brackets are 95%
max-|t| simultaneous bands across the four languages separately within outcome.

| Language | DSL genuine refusal | DSL capability failure |
|---|---:|---:|
| Chinese | −0.63 [−2.62, 1.37] | 15.41 [6.68, 24.14] |
| Arabic | −0.21 [−2.86, 2.43] | 13.98 [5.39, 22.56] |
| Russian | −0.45 [−2.69, 1.79] | 20.58 [14.69, 26.47] |
| Hindi | −1.29 [−2.97, 0.39] | 16.79 [9.27, 24.32] |

No corrected genuine-refusal language band excludes zero. All four capability-
failure contrasts are positive and their simultaneous bands exclude zero. The
historical language non-engagement gap is therefore primarily evidence of
language-specific capability/measurement failure in this model/prompt battery,
not evidence that non-English delivery induces more genuine refusal. A causal
language interpretation still requires translation equivalence, no
interference, and a stable generation/provider regime.
