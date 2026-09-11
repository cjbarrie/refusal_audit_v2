# Fresh external response-validity audit: aggregate design recommendation

Status date: 2026-08-27.

Status: **paired model run complete; human verification pending**. The frozen
draw contains 1,197 responses after three overlaps between its two sampling
components. All 2,394 Luna and Sol judgments completed for $5.50 under the $16
ceiling. These machine labels are not human ground truth and do not yet certify
Luna externally.

## 1. Scientific purpose

The existing 700 human-reviewed responses helped develop the codebook or the
annotation procedure. They support internal diagnosis but cannot provide a
fresh test of GPT-5.6 Luna. The external audit therefore samples only from the
136,486 current-corpus responses outside those 700.

The audit has two separate jobs:

1. test whether Luna v2.3 identifies genuine refusal accurately on new cases;
2. test capability-failure measurement without allowing those more common
   cases to crowd genuine refusals out of the validation sample.

GPT-5.6 Sol will label the same cases independently. Sol is a strong second
annotator, not ground truth. Human judgments remain the reference.

## 2. Phase-one probability design

Each candidate plan is the union of two independent samples.

### Component A: model-by-language coverage

Draw the same fixed number of responses without replacement from each of the
55 model-by-language cells. The recommended plan draws ten per cell, producing
550 selections before overlap with Component B. This prevents good aggregate
accuracy from concealing an untested model-language cell.

### Component B: response-risk coverage

Independently sample without replacement from the seven frozen routing strata
already described in the technical pipeline. For the recommended plan:

| Routing stratum | Eligible external rows | Component-B draw |
|---|---:|---:|
| Wrong-language signal | 5,000 | 100 |
| Technical signal | 7,942 | 100 |
| Pivot signal | 9,026 | 50 |
| Genuine-refusal signal | 3,464 | 200 |
| Incoherent signal | 9,071 | 100 |
| Prior model-disagreement signal | 5,568 | 70 |
| General remainder | 96,415 | 30 |
| **Total** | **136,486** | **650** |

For response `i`, let `p_cell_i = 10/N_cell(i)` and
`p_risk_i = n_h/N_h`. Because the two components are drawn independently, the
probability that the response enters their union is

```text
pi_i = 1 - (1 - p_cell_i)(1 - p_risk_i).
```

The two components contain 1,200 selections before deduplication. Their
expected union contains 1,197.38 unique responses. The realized sample size
will differ slightly according to component overlap; every selected row will
retain its exact `pi_i`.

## 3. How candidate sizes were compared

The randomized 400-case enrichment wave was used only to calibrate expected
class yield within the frozen routing strata. None of those 400 responses is
eligible for the external audit.

For an outcome with `y_h` events among `n_h` calibration cases in stratum `h`,
the planning simulation used

```text
p_h ~ Beta(0.5 + y_h, 0.5 + n_h - y_h)
Y_h,new ~ Binomial(expected selected in h, p_h).
```

Ten thousand simulations were run with seed 20260827. These are planning
ranges, not confidence intervals for a completed audit.

| Plan | Expected unique cases | Guaranteed cell draw | Expected genuine refusals (90% range) | Expected capability failures (90% range) |
|---|---:|---:|---:|---:|
| Approximately 800 | 798.86 | 6 | 107.14 (84-130) | 281.66 (259-305) |
| Approximately 1,000 | 1,003.18 | 8 | 130.62 (103-157) | 349.12 (322-377) |
| **Approximately 1,200** | **1,197.38** | **10** | **146.40 (116-177)** | **414.81 (384-447)** |
| Approximately 1,500 | 1,505.88 | 12 | 188.88 (150-227) | 530.82 (492-572) |

The 1,200 plan is recommended because it supplies ten guaranteed selections in
every model-language cell while retaining substantial refusal support. The 800
plan would probably contain enough refusals overall, but six guaranteed cases
per cell is too thin for a deliberately multilingual external audit. Moving
from 1,200 to 1,500 adds appreciable provider and human work without changing
that basic conclusion.

## 4. Machine annotation and human verification

Luna v2.3 and Sol will independently annotate every selected response. They
will see the source-language prompt,
the English reference prompt, the source response and intended language. They
must not see the source-model identity, prior labels, sampling reason or the
other annotator's result. With an expected 1,197.38 responses, this implies
2,394 provider annotations in the realized draw.
The exact number and cost cannot be frozen until the realized rows and payloads
exist.

Human verification is a second probability phase:

- probability 1.00 for any model-identified refusal, any Luna-Sol headline
  disagreement, any schema failure, or any low-confidence result;
- probability 0.50 for cases where both models agree on capability failure and
  neither identifies refusal; and
- probability 0.10 for ordinary high-confidence agreements, sampled within
  model-by-language cells.

If `q_i` is this second-phase probability, a human-reviewed response has
combined probability `pi_i q_i`. Weighted confusion-matrix totals use

```text
T_ab = sum_i I(i sampled and human reviewed)
             * I(human outcome=a, Luna outcome=b) / (pi_i q_i).
```

Precision, recall, specificity and related measures are calculated from these
weighted totals. Human verification probabilities must be retained exactly;
unreviewed agreements may not simply be treated as correct.

Using the current human labels as a workload proxy for the not-yet-observed Sol
decisions gives the following projections for the 1,200 plan:

| Verification scenario | Capability-positive agreement probability | Ordinary-agreement probability | Expected human reviews |
|---|---:|---:|---:|
| Lean | .35 | .08 | 434.87 |
| **Recommended** | **.50** | **.10** | **505.88** |
| Conservative | .75 | .20 | 660.61 |

The 506-review figure is a workload estimate, not a fixed quota. The actual
priority count is known only after Luna and Sol have run. The proxy does not
assume that Sol equals the human coder for accuracy; it uses that substitution
only to anticipate review volume.

## 5. Proposed external gates

These gates should be frozen before the sample is drawn:

- schema success at least .995;
- genuine-refusal precision and recall point estimates at least .90;
- design-based 95% lower bounds for refusal precision and recall at least .80;
- capability-failure F1 at least .85;
- refusal recall at least .70 in any language with at least five verified
  refusal events; and
- complete human review of all certainty-phase rows, with no silent parse or
  provenance failure.

Failing a gate triggers diagnosis or instrument revision. It does not permit
changing the threshold after seeing results.

## 6. Frozen draw and next authorization gate

The user approved the reproducible draw and local payload construction on
2026-08-27. That approval did not authorize an API call. The realized draw has
550 model-by-language component selections, 650 risk-component selections and
three overlaps, giving 1,197 unique responses.

Each model payload contains 1,197 requests and an estimated 2,664,980 input
tokens. At prices checked on 2026-08-27, the planned combined cost is $8.54 and
the combined single-attempt reservation is $12.57. The proposed hard ceiling is
$16. The exact payload hashes are recorded in
`external_audit_v1/manifest.json`; a paid run requires separate authorization
bound to both hashes, the OpenAI provider route, disabled fallbacks and the $16
ceiling. That authorization was subsequently given and the run completed with
2,394/2,394 valid final records. There was one schema-invalid Luna attempt; its
raw output and cost were retained before an unchanged retry succeeded. Actual
provider-reported cost was $5.50, with no unreconciled cost.

Luna identifies 115 genuine refusals and Sol 114; they disagree on nine refusal
decisions. Luna identifies 491 capability failures and Sol 383; they disagree
on 124 capability decisions. The phase-two partition contains 229 certainty
reviews, 374 capability-positive agreements eligible at probability .50, and
594 ordinary agreements eligible at probability .10. Expected human workload
is therefore 475.4 before the realized second-phase draw.

Implementation: `src/refusal_audit/response_validity/external_audit_design.py`.
CLI: `python scripts/response_validity.py plan-external-validity-audit`.
Frozen aggregate artifacts:
`annotations/response_validity_human_v2/external_audit_planning_v1/`.
Frozen realized artifacts:
`annotations/response_validity_human_v2/external_audit_v1/`.
