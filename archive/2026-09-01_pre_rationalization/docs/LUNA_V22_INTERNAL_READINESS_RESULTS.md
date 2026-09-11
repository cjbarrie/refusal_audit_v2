# GPT-5.6 Luna exact-v2.2 readiness results

Status date: 2026-08-27. The frozen run is complete and failed its schema-
success gate. These results do not approve Luna for population annotation.

## Run integrity and cost

The authorized run sent the frozen 1,400-request payload with SHA-256
`a2edee4fb92ae9e515e18bb781312c8e855596d6130c79d8628b9116cda259cb`
to OpenRouter `openai/gpt-5.6-luna`, pinned to the OpenAI provider. Fallbacks
and reasoning output were disabled. The cumulative cost was $1.17194434 under
the $2.00 ceiling.

Of 1,400 requests, 1,292 produced locally valid v2.2 records and 108 exhausted
all four attempts. Each input mode completed 646 of 700 cases, or 92.29%. The
predeclared requirement was 99.5%, so neither mode passed.

## Why 108 requests failed

The failures were not primarily malformed JSON. They arose because Luna often
returned a non-`none` technical-failure subtype while calling the response
`incoherent_garbled` or `partly_coherent`. The frozen local validator permits a
technical subtype only when `output_quality = technical_degeneration`.

Across 590 rejected attempts:

- 579 supplied a technical subtype with another output-quality value;
- 8 called the output technical degeneration without a failure subtype;
- 3 also violated the rule that an incoherent or technically degenerated output
  cannot establish a substantive refusal.

All 108 incomplete requests exhausted the four-attempt maximum. The missing
cases are outcome-dependent: in each 700-case arm, 51 of the 54 incomplete
responses are human-labelled capability failures. Consequently, capability
metrics calculated on the 646 completed cases are biased and cannot be treated
as all-700 performance.

The runner preserved the cost, response IDs and validation errors for every
attempt, but the v1 error record did not preserve the rejected structured
content itself. That is a confirmed provenance defect to repair before another
run. Future runners must store the raw structured response even when local
logical validation rejects it.

## Completed-subset diagnostic

These figures are diagnostic only because completion is selective.

| Input | Refusal precision | Refusal recall | Refusal F1 | Capability F1 |
|---|---:|---:|---:|---:|
| Source response only | .939 | .979 | .958 | .836 |
| Source response + translation | .938 | .957 | .947 | .856 |

All 47 human genuine refusals happened to have valid outputs in both modes.
The source-only mode found 46 and produced three false positives. The
translation-assisted mode found 45 and produced three false positives.

This is encouraging evidence that the final v2.2 refusal definition repaired
the earlier recall problem. It is not a pass: schema success failed, the
capability subset is selective, and the 700 cases remain an internal
development corpus.

## Decision after the failed v2.2 run

Do not loosen the gate or silently recode the 108 failures. Before any rerun:

1. revise the structured schema so the technical-failure/output-quality
   relationship is machine-enforced rather than left to prose;
2. decide whether `technical_failure` should truly be exclusive to full
   technical degeneration, or whether partly coherent truncation is a valid
   overlapping state;
3. preserve every raw provider response before logical validation;
4. freeze and hash a corrected v2.2.1 payload; and
5. run a small local/provider smoke test before repeating the evaluation.

These requirements were subsequently implemented in the separately versioned
v2.3 repair below. Its new payload received its own cost estimate and explicit
authorization; the earlier $2.00 authorization was not reused.

### Completed repair test

The correction is now versioned as v2.3 rather than overwriting v2.2. It makes
semantic output quality and technical failure independent while leaving the
genuine-refusal definition unchanged. The frozen repair packet contains all 69
unique responses involved in the 108 v2.2 failures, under both source-only and
source-plus-translation input: 138 requests. This is an instrument-repair test,
not a fresh accuracy sample.

The provider-payload SHA-256 is
`9334a354f1c4b454c89b12a504c61af4d2408f3f35c511de2ee53d16dca03693`.
The authorized run completed all 138 requests with 100% schema success for
$0.0611691 under the $0.50 ceiling. The v2.3 runner stored the raw structured
content and its hash before applying local logical validation. Results SHA-256:
`b6e62f3f03fa76638f13076845cd8413f3828646c72b89823cdef3996bbe2f63`.

All 69 repair responses are human non-refusals. Luna produced no refusal false
positive in either input mode. Sixty-six are human capability failures; Luna
identified all 66 in each mode and additionally called the other three
capability failures, giving capability precision .957, recall 1.000 and F1
.978 within this deliberately failure-heavy repair set.

For an internal patched diagnostic, the 108 v2.3 predictions were used only
where the original v2.2 run lacked a valid prediction. The other 1,292 records
remain the immutable v2.2 outputs. This yields 700 predictions per mode but is
not presented as one uniform v2.3 run.

| Patched mode | Refusal precision | Refusal recall | Refusal F1 | Capability F1 |
|---|---:|---:|---:|---:|
| Source response only | .939 | .979 | .958 | .861 |
| Source plus translation | .938 | .957 | .947 | .878 |

Both modes pass the internal gates. The predeclared ordering selects source
response only because it has the higher refusal F1. On 30 predictions available
under both versions, the v2.2 and v2.3 headline outcomes agree exactly. This is
strong internal readiness evidence, not external certification.

## Reproducible artifacts

Outputs are under
`annotations/response_validity_human_v2/luna_exact_v2_2_internal_test_v1/` and
`annotations/response_validity_human_v2/luna_v2_3_repair_test_v1/`.
The immutable completed-result SHA-256 is
`60311e49018d255b3830716a6327c34a01c702c6bdf33d9b8b246d95b326a9d2`.
The original v2.2 `score_summary.json` continues to record
`failed_schema_coverage`. The repair directory's `score_summary.json` records
the patched candidate and exact v2.2/v2.3 provenance without rewriting either
source run.
