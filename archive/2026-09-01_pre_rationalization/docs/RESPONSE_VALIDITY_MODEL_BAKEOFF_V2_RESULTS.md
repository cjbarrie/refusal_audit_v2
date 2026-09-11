# Response-validity student-model bake-off v2: results

Status: completed 31 August 2026. No alternative passed every frozen gate;
GPT-5.6 Luna remains the response-validity student.

## Run identity

The user authorized the 9,576-request maximum payload with SHA-256
`4bc54f501f5f8f4867a81ca1ccb4e3058800a0a6ff9e0e8a44b89af966ac7dd1`
under a cumulative $80.50 ceiling. Fallbacks were disabled and no request had
more than two unchanged attempts. The runner sent 50 common preflight cases to
each route, then sent the remaining 1,147 cases only to routes with at least 49
valid preflight records.

The run produced 4,734 valid final records and cost **$23.66423**. Results
SHA-256 is
`c86188161189b3fbb9a894dbc343df6b8b45fe927716cf0e544070727bddc419`;
the append-only attempts ledger SHA-256 is
`49bac4dbecd74e879b55ce46d09306655ac0d84376e366e07ea26d1adf6fb39b`.
Raw provider content and hashes were stored before local validation.

## Engineering gates

| Candidate | Valid preflight | Continued | Full valid coverage | Provider cost | Interpretation |
|---|---:|---|---:|---:|---|
| Gemini 3.5 Flash-Lite | 0/50 | No | — | $0.000 | Pinned endpoint rejected all requests because reasoning had become mandatory |
| Claude Haiku 4.5 | 50/50 | Yes | 1,146/1,197 (95.74%) | $5.412 | Failed full coverage after upstream 125-request/minute rate limits exhausted both attempts for 51 cases |
| Kimi K3 | 50/50 | Yes | 1,196/1,197 (99.92%) | $12.419 | Passed coverage |
| Qwen3.8 2.4T-A95B | 0/50 | No | — | $0.000 | Pinned endpoint rejected all requests because reasoning had become mandatory |
| GLM-5.3 | 45/50 | No | — | $0.154 | Failed the 49/50 gate under upstream rate limiting |
| DeepSeek V4 Pro 0813 | 50/50 | Yes | 1,196/1,197 (99.92%) | $4.984 | Passed coverage |
| MiniMax M3 | 50/50 | Yes | 1,196/1,197 (99.92%) | $0.634 | Passed coverage |
| Qwen3.8 27B | 48/50 | No | — | $0.062 | Four invalid records across two cases violated the codebook's coherence/refusal consistency rule |

The Gemini, large-Qwen and GLM results are route/configuration reliability
findings, not evidence that the underlying models have poor substantive
classification accuracy. Haiku's complete cases are retained as a diagnostic,
but its missingness disqualifies it from promotion.

## Refusal agreement with Sol v2.4

The 24 cases used to refine v2.4 are excluded. Metrics use the remaining 1,173
model-selection cases, minus one missing case for each fully covered candidate
and 51 missing cases for Haiku. Sol is a machine reference, not human gold.

| Candidate | Compared rows | Predicted refusals | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| **Luna baseline** | 1,173 | 112 | **.938** | .929 | **.933** |
| Haiku 4.5, diagnostic | 1,122 | 142 | .697 | .908 | .789 |
| Kimi K3 | 1,172 | 154 | .714 | **.973** | .824 |
| DeepSeek V4 Pro | 1,172 | 160 | .681 | .965 | .799 |
| MiniMax M3 | 1,172 | 142 | .704 | .885 | .784 |

Kimi and DeepSeek recover nearly every Sol-positive refusal but overclassify
many Sol-negative responses. Kimi has 44 false positives and three false
negatives; DeepSeek has 51 false positives and four false negatives. MiniMax
reduces recall without solving the precision problem. The alternatives appear
to apply a broader meaning of refusal than the v2.4 functional boundary,
despite receiving the identical prompt and schema.

The paired issue-cluster bootstrap confirms that this is not a trivial sample
fluctuation. Relative to Luna, refusal-F1 differences and 95% intervals are:

| Candidate | F1 difference from Luna | 95% issue-cluster interval |
|---|---:|---:|
| Kimi K3 | -.109 | [-.164, -.056] |
| DeepSeek V4 Pro | -.135 | [-.195, -.077] |
| MiniMax M3 | -.149 | [-.207, -.092] |

Every lower bound is well below the frozen non-inferiority margin of -.02.
None passes the required precision .90, recall .90, F1 .92 and paired
non-inferiority gates.

## Language pattern

Kimi's refusal recall ranges from .941 in Russian to 1.000 in English and
Hindi, but precision is only .630 in Hindi, .667 in Chinese and .676 in
English. DeepSeek has the same high-recall/low-precision pattern, with Chinese
precision .564. MiniMax is weakest in Chinese, where recall is .783 and F1
.655. These results rule out an aggregate score concealing a clearly superior
multilingual student.

## Capability-failure diagnostic

Kimi performs strongly on capability failure against Sol: precision .912,
recall .969 and F1 .939, exceeding Luna's F1 .887 on the same broad outcome.
DeepSeek reaches F1 .888 and MiniMax .787. This does not promote Kimi as the
refusal annotator because capability failure is secondary and its human
validation is weaker, but it identifies a potentially useful specialized role
for Kimi in later measurement work.

## Decision

Retain GPT-5.6 Luna as the scalable v2.4 refusal student. Do not tune a new
threshold or rewrite the prompt using these 1,173 cases and then report the
same cases as held-out evidence. The next scientifically clean step remains a
fresh, blinded probability-sample human audit of frozen Luna v2.4. Kimi's
high-recall errors may be inspected only as diagnosis or used to design a
future experiment with a new evaluation sample.

Reproducible outputs are under
`annotations/response_validity_human_v2/external_audit_v1/model_bakeoff_v2/`.
The guarded implementation is
`src/refusal_audit/response_validity/model_bakeoff_v2.py`.
