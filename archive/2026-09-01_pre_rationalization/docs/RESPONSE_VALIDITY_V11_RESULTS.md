# GPT-5.6 Sol response-validity v1.1 pilot results

Status: completed 2026-08-13. This is a blinded frontier-machine-judge pilot,
not human validation and not a population-prevalence sample. Protocol and exact
prompt: [`RESPONSE_VALIDITY_V11_PILOT.md`](RESPONSE_VALIDITY_V11_PILOT.md).

## Execution integrity

- Frozen rows completed: 1,306/1,306.
- API/parse/schema/logical-consistency failures: 0.
- Provider-reported cost: $12.45, below the authorized $15 ceiling.
- Provider usage: 1,627,476 prompt tokens,
  92,942 completion tokens, and
  0 reasoning tokens.
- Communicated-refusal evidence spans matching the response after Unicode and
  whitespace normalization: 718/726
  (98.9%).
- Eight evidence deviations are retained for review; inspection shows formatting
  removal, punctuation normalization, or ellipsis/paraphrase rather than missing
  categorical fields. They are included in the blinded disagreement packet.

## Pilot outcomes

| pilot stratum                     |   n | refusal communicated   | clean genuine refusal   | capability failure   | coherent pivot   |
|:----------------------------------|----:|:-----------------------|:------------------------|:---------------------|:-----------------|
| All v1.0 conflicts                | 979 | 65.2%                  | 63.7%                   | 2.7%                 | 19.9%            |
| Balanced non-conflict comparators | 327 | 26.9%                  | 22.9%                   | 32.4%                | 4.6%             |

These percentages describe the deliberately enriched pilot strata only. All
979 conflicts are a census of the v1.0 contradiction set. The 327 comparator
rows are one-per-cell diagnostics and have no population weights.

Exact comparator confusion matrix (rows are v1.0; columns are Sol v1.1):

|       |   false |   true |
|:------|--------:|-------:|
| false |     246 |     32 |
| true  |       6 |     43 |

## Judge-output diagnostics

| confidence   |    n |
|:-------------|-----:|
| high         | 1288 |
| medium       |   18 |

| noncompliance signal   |   n |
|:-----------------------|----:|
| explicit               | 613 |
| none                   | 578 |
| implicit               | 113 |
| unassessable           |   2 |

The absence of low-confidence outputs does not establish correctness; it is a
model self-report. No row used hidden reasoning, and reasoning-token usage was
zero.

## What the original contradiction meant

Among the 979 conflicts, v1.0 had marked a refusal component while its nominal
class was almost always `coherent pivot`. Sol v1.1 divides them rather than
forcing one post-hoc precedence:

- Explicit v1.0 refusal-component cases: 359; Sol clean genuine
  refusal 97.8%, coherent pivot
  0.0%.
- Implicit v1.0 refusal-component cases: 620; Sol clean genuine
  refusal 44.0%, coherent pivot
  31.5%.

The explicit component was highly reproducible; the implicit component was not.
This is evidence that v1.0's implicit-refusal Boolean was too permissive and
often captured pivots or nonresponse.

## Conflict-set diagnostics by language

| language   |   n | clean genuine refusal   | capability failure   | coherent pivot   |
|:-----------|----:|:------------------------|:---------------------|:-----------------|
| ar         | 211 | 130 (61.6%)             | 4 (1.9%)             | 45 (21.3%)       |
| en         | 351 | 267 (76.1%)             | 4 (1.1%)             | 42 (12.0%)       |
| hi         | 104 | 50 (48.1%)              | 1 (1.0%)             | 32 (30.8%)       |
| ru         | 110 | 74 (67.3%)              | 4 (3.6%)             | 17 (15.5%)       |
| zh         | 203 | 103 (50.7%)             | 13 (6.4%)            | 59 (29.1%)       |

## Conflict-set diagnostics by subject model

| model              |   n | clean genuine refusal   | capability failure   | coherent pivot   |
|:-------------------|----:|:------------------------|:---------------------|:-----------------|
| allam-7b           | 152 | 73 (48.0%)              | 2 (1.3%)             | 41 (27.0%)       |
| claude-opus-4.5    |  51 | 46 (90.2%)              | 0 (0.0%)             | 1 (2.0%)         |
| deepseek-chat-v3.1 | 312 | 121 (38.8%)             | 4 (1.3%)             | 127 (40.7%)      |
| falcon3-10b        |  60 | 48 (80.0%)              | 2 (3.3%)             | 1 (1.7%)         |
| gpt-4o             |  46 | 42 (91.3%)              | 0 (0.0%)             | 0 (0.0%)         |
| gpt-5.1            | 115 | 114 (99.1%)             | 0 (0.0%)             | 0 (0.0%)         |
| grok-4.3           |  14 | 8 (57.1%)               | 4 (28.6%)            | 3 (21.4%)        |
| jais-8b            |  27 | 18 (66.7%)              | 1 (3.7%)             | 4 (14.8%)        |
| qwen3-max          | 103 | 69 (67.0%)              | 4 (3.9%)             | 16 (15.5%)       |
| sarvam-30b         |  99 | 85 (85.9%)              | 9 (9.1%)             | 2 (2.0%)         |

These language/model percentages are conditional on inclusion in the v1.0
contradiction census. They must not be interpreted as model or language refusal
rates in the full response population.

## Non-conflict diagnostic agreement

On the 327 balanced non-conflict comparators, v1.0 genuine refusal versus Sol
clean genuine refusal has raw agreement 88.4% and Cohen's kappa
0.626. This is useful prompt diagnostics but not an accuracy estimate:
neither machine label is human ground truth, and the comparator sample is
cell-balanced rather than population-representative.

## Decision

The codebook passes the mechanical pilot gates: complete structured coverage,
zero logical contradictions, and clean separation of communicated refusal from
language/technical failure. It does not yet pass the human-validity gate. A
deterministic 120-row blinded packet was generated at
`annotations/response_validity_v11_pilot/blinded_disagreement_review.parquet`,
with labels held separately in the local key. Complete that review before
treating v1.1 as the final measurement rule or purchasing the full 12,725-row
Sol run.

At the observed pilot rate and full frozen-row token volumes, the revised v1.1
full audit is expected to cost approximately $131; a prudent hard ceiling would
be $150. That run would estimate the percentage of all 11,475 original
non-engagement cases that are clean genuine refusals and apply the existing
design weights to the 1,250 controls. It is not authorized by the $15 pilot
approval.
