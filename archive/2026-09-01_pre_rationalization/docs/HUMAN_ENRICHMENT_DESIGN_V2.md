# Human rare-class enrichment design simulation v2

> **Simulation record.** This document records the ex ante planning analysis.
> The recommended 400-row wave was subsequently approved and frozen on
> 2026-08-24; see the execution record below. No network or paid call has yet
> been made for that wave.

This replaces the superseded v1 simulation. It uses the complete-language v3 human freeze and the completed Stage B disagreement evidence. Stage B covers only 84 rows, so its predictions are not misrepresented as population labels: a classifier transfers only the label-blind pattern of cross-model disagreement to population features.

## Candidate routing pools

| Stratum | Candidate rows | Models | Languages | Issues |
|---|---:|---:|---:|---:|
| wrong language signal | 5,045 | 11 | 5 | 624 |
| technical signal | 8,007 | 10 | 5 | 624 |
| pivot signal | 9,091 | 11 | 5 | 604 |
| genuine refusal signal | 3,509 | 10 | 5 | 498 |
| incoherent signal | 9,116 | 9 | 5 | 624 |
| stage b disagreement signal | 5,623 | 11 | 5 | 608 |
| general remainder | 96,495 | 11 | 5 | 624 |

## Expected rare-class yield

Posterior-predictive ranges are planning quantities, not confidence intervals.

| Workload | Class | Expected | 90% range | P(meet target) |
|---:|---|---:|---:|---:|
| 150 | wrong language | 23.8 | 19-31 | 92.8% |
| 150 | technical degeneration | 8.0 | 2-16 | 18.6% |
| 150 | coherent pivot | 12.3 | 4-22 | 31.7% |
| 150 | genuine refusal | 26.1 | 15-37 | 84.2% |
| 150 | incoherent garbled | 44.7 | 35-55 | -- |
| 250 | wrong language | 36.5 | 29-47 | 99.9% |
| 250 | technical degeneration | 12.6 | 4-24 | 51.4% |
| 250 | coherent pivot | 19.1 | 7-33 | 69.2% |
| 250 | genuine refusal | 40.7 | 25-57 | 99.0% |
| 250 | incoherent garbled | 71.3 | 57-87 | -- |
| 400 | wrong language | 55.4 | 45-71 | 100.0% |
| 400 | technical degeneration | 20.0 | 7-37 | 82.4% |
| 400 | coherent pivot | 30.0 | 13-52 | 91.8% |
| 400 | genuine refusal | 63.4 | 40-88 | 100.0% |
| 400 | incoherent garbled | 112.0 | 90-135 | -- |
| 600 | wrong language | 80.2 | 65-101 | 100.0% |
| 600 | technical degeneration | 29.1 | 12-52 | 95.1% |
| 600 | coherent pivot | 43.8 | 19-74 | 98.3% |
| 600 | genuine refusal | 93.0 | 60-127 | 100.0% |
| 600 | incoherent garbled | 164.9 | 135-197 | -- |

## Worst-case phase-two precision proxies

These are conditional design-planning half-widths under stratified SRS and the conservative bound Var(Y-m) <= 0.25. They are not accepted confidence intervals and do not include first-wave, cross-fit, or issue-bootstrap uncertainty.

| Workload | Estimand family | Maximum 95% half-width |
|---:|---|---:|
| 150 | boundary minus regular proxy | 0.313 |
| 150 | home minus away proxy | 1.665 |
| 150 | language difference vs english | 0.516 |
| 150 | model language prevalence | 1.362 |
| 150 | model prevalence | 0.608 |
| 150 | overall prevalence | 0.156 |
| 150 | temporal minus perennial proxy | 0.347 |
| 250 | boundary minus regular proxy | 0.210 |
| 250 | home minus away proxy | 1.110 |
| 250 | language difference vs english | 0.345 |
| 250 | model language prevalence | 0.908 |
| 250 | model prevalence | 0.406 |
| 250 | overall prevalence | 0.105 |
| 250 | temporal minus perennial proxy | 0.232 |
| 400 | boundary minus regular proxy | 0.158 |
| 400 | home minus away proxy | 0.832 |
| 400 | language difference vs english | 0.259 |
| 400 | model language prevalence | 0.681 |
| 400 | model prevalence | 0.304 |
| 400 | overall prevalence | 0.079 |
| 400 | temporal minus perennial proxy | 0.175 |
| 600 | boundary minus regular proxy | 0.122 |
| 600 | home minus away proxy | 0.641 |
| 600 | language difference vs english | 0.200 |
| 600 | model language prevalence | 0.524 |
| 600 | model prevalence | 0.234 |
| 600 | overall prevalence | 0.061 |
| 600 | temporal minus perennial proxy | 0.135 |

## Minimum expected coverage

| Workload | Family | Minimum expected new rows in any cell |
|---:|---|---:|
| 150 | jurisdiction home | 0.4 |
| 150 | language | 19.8 |
| 150 | model | 2.6 |
| 150 | model language | 0.5 |
| 150 | route | 25.9 |
| 150 | tier | 69.4 |
| 250 | jurisdiction home | 1.0 |
| 250 | language | 34.5 |
| 250 | model | 5.9 |
| 250 | model language | 1.2 |
| 250 | route | 43.1 |
| 250 | tier | 114.5 |
| 400 | jurisdiction home | 1.7 |
| 400 | language | 56.3 |
| 400 | model | 10.4 |
| 400 | model language | 2.1 |
| 400 | route | 68.8 |
| 400 | tier | 183.5 |
| 600 | jurisdiction home | 2.9 |
| 600 | language | 85.8 |
| 600 | model | 17.6 |
| 600 | model language | 3.5 |
| 600 | route | 103.4 |
| 600 | tier | 278.7 |

## Recommendation

Use **400 new human-coded responses as the initial wave**. The original planning
rule proposed stopping if frozen realized counts reached 20 genuine refusals,
15 pivots, 20 wrong-language outputs, and 12 technical degenerations, otherwise
using the predeclared stratum-specific increment to a cumulative **600**. This
was a rare-class surrogate-development rule, not a power requirement for a
principal estimand.

**Outcome-informed protocol history, 2026-08-24:** after the first 100
unique labels yielded one pivot overall and none among 20 reviewed
`pivot_signal` rows, the 15-pivot assumption was no longer credible enough to
justify 200 additional human judgments by itself. The initial amendment was to
complete 400 but not extend solely for a pivot deficit. After 200 contiguous
randomized review orders were completed, a second explicitly outcome-informed
amendment paused coding: orders 1--200 were frozen, orders 201--400 became an
unreviewed reserve, and the 116 protected rows became the one-shot evaluation
for the two advancing configurations. The original 300, rather than the
enriched checkpoint, supplies the planned DSL residual correction. Resuming a
next-100 block requires a new logged adequacy decision. The original workload
and increment remain preserved as design provenance. See
[`RESPONSE_VALIDITY_CODEBOOK_RATIONALE.md`](RESPONSE_VALIDITY_CODEBOOK_RATIONALE.md).

## Approved local execution

The user approved beginning the annotations on 2026-08-24. The repository then
froze the 400-row wave using independent SRSWOR within the seven routing strata.
All 300 prior human-coded response keys were excluded. The original pilot
probabilities were independently reconstructed and matched the frozen pilot;
the new design stores both the second-wave conditional probability and the
declared sequential inclusion probability.

The sample was assigned by `prompt_id`, before labels were observed, to 161
development rows and 239 untouched evaluation rows. No prompt crosses arms.
The exact translation payload SHA-256 is
`f91cf3d093a398df03561cb8906e1f45965da87fe76d804ffd2f679bf35d6785`;
the unchanged literal-translation prompt SHA-256 is
`427dcc37b06a03e5a4b01682ad1a090ba6436b8d56472c58627cf1b6d2deb9be`.
The local token estimate is 585,740 input and 538,325 planned output tokens.
At the 2026-08-24 OpenRouter list prices for `openai/gpt-5.6-luna`
($0.20/M input and $1.20/M output), the deliberately uncached planning estimate
is $0.763138. The proposed new-run ceiling is $3.00 because execution reserves
room for structured-output retries and unusually long translations; the prior
300-row translation cost $0.8759864 and is accounted for separately.
Translation remains a separate approval gate.

## Translation and review-packet execution

The user subsequently authorized the exact payload, Luna/OpenAI route, disabled
fallbacks and reasoning, and a $3.00 hard ceiling. Final reconstructed upstream
spend was **$2.9852299**. BYOK cost accounting uses
`cost_details.upstream_inference_cost`, because the OpenRouter platform-cost
field is zero for these calls.

The final packet covers all 400 rows: 289 translations are complete, 107 are
partial, and four are unassessable. Twelve extreme long outputs required special
handling. Eight were recombined from lossless translated chunks. Four remaining
rows were marked locally unassessable after the ceiling guard activated; all
four independently satisfied `diag_repetition_loop = TRUE` and repeated-trigram
ratio at least .90. No provider call or response-validity label was created by
that local step. The full original response remains visible in every case, and
all partial/untranslated spans are disclosed.

The blinded human packet SHA-256 is
`bc8dfe97139085fa28051433ebc03f047c812839fb05570362e1037c96d36402`.
It excludes model identity, routing stratum, split membership, predictions, and
prior labels. The new annotation log is separate and initially absent.
