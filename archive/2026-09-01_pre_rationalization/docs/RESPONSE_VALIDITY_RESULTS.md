# Response-validity results: GPT-5.6 Sol DSL v1.1

Status: production 500-replicate integration complete; candidate acceptance
113/113 and figure audit passed; not yet promoted as `canon_014` because the Git
tree is not stable. The historical dual-judge report is preserved at
`docs/archive/RESPONSE_VALIDITY_RESULTS_DUAL_JUDGE.md`.

## Population measurement

The 14,182-row blinded probability sample comprises all 11,475 original
judge-coded non-engagement rows and 2,707 SRSWOR controls. Rectified DSL targets
the full 137,186-response population.

| Outcome | Reference HT | Prediction only | Rectified DSL |
|---|---:|---:|---:|
| Genuine refusal | 2.7817% | 2.7171% | **2.7963%** |
| Capability failure | 17.5236% | 18.2076% | **18.0112%** |
| Coherent pivot | 1.2761% | 1.3802% | **1.3748%** |

Prediction-only output is diagnostic, not inferential. Sol is a machine
reference, not human ground truth.

## Standardized home-minus-away association

Percentage points; 95% max-|t| simultaneous bands across jurisdictions within
each outcome. Specification: per-jurisdiction linear moment
`X'(Y-X beta)-1e-8 P beta=0`, `X = home*model + tier + domain + route`, followed
by equal-model → equal-issue → equal-prompt g-computation.

| Jurisdiction | Original non-engagement | Genuine refusal DSL | Capability failure DSL |
|---|---:|---:|---:|
| CN | 16.03 [9.93, 22.13] | 4.59 [−1.12, 10.31] | 13.84 [−10.24, 37.93] |
| MENA | 4.03 [0.69, 7.38] | 1.76 [−2.24, 5.75] | −11.00 [−49.93, 27.93] |
| India | −3.55 [−8.31, 1.20] | −2.40 [−8.60, 3.79] | 0.38 [−3.12, 3.89] |
| US | 1.33 [−1.15, 3.82] | 2.70 [−4.31, 9.72] | −0.04 [−0.16, 0.08] |
| EU | 0.00 [0.00, 0.00] | 2.53 [−9.69, 14.75] | 0.13 [−0.99, 1.24] |

The original CN and MENA home results are not statistically resolved as
genuine-refusal associations after corrected measurement. Every corrected
genuine-refusal and capability-failure simultaneous band includes zero. This is
an adjusted association, not a causal home effect.

## Prompt-paired language contrast

Target language minus English percentage points; paired within model × prompt,
models weighted equally; 95% max-|t| simultaneous bands across languages within
each outcome.

| Language | Genuine refusal DSL | Capability failure DSL |
|---|---:|---:|
| Chinese | −0.63 [−2.62, 1.37] | 15.41 [6.68, 24.14] |
| Arabic | −0.21 [−2.86, 2.43] | 13.98 [5.39, 22.56] |
| Russian | −0.45 [−2.69, 1.79] | 20.58 [14.69, 26.47] |
| Hindi | −1.29 [−2.97, 0.39] | 16.79 [9.27, 24.32] |

No genuine-refusal band excludes zero; every capability-failure band does. The
historical non-English non-engagement gap is therefore principally a capability
failure finding under this measurement design. A causal language reading still
requires translation equivalence, no interference, and stable generation and
provider conditions.

## Inference and reproducibility

DSL uncertainty combines a whole-issue bootstrap, Rao–Wu rescaled phase-two
SRSWOR replicates, and ten-partition cross-fit variance. Every reported family
completed 500/500 draws with zero failures and finite estimates, standard
errors, and simultaneous bands. Serial and four-worker test runs produced
identical tables. Exact prompts, authorization, provider accounting, hashes,
sampling repair, equations, and limitations are documented in:

- `docs/RESPONSE_VALIDITY_DSL_RUN.md`;
- `docs/RESPONSE_VALIDITY_DSL_AUGMENTATION.md`;
- `docs/r_pipeline/17_response_validity.md`.
