# Stage B cross-model surrogate bake-off

Status: **authorized, completed, and scored on 2026-08-23**. All 504 unique
requests completed for **$7.02100588**, below the $8.00 cumulative ceiling.

## Purpose

Stage B tests whether Stage A behavior was specific to GPT-5.6 Luna. It reuses
the same 84 prompt-grouped evaluation responses and the exact Stage A
zero-shot, 7-shot, and 22-shot prompts. It adds Gemini 3.5 Flash-Lite and Claude
Haiku 4.5. This remains a development comparison; it cannot select the final
population surrogate and cannot create consensus truth.

## Frozen payload

- Evaluation rows: 84.
- Configurations: `zero_shot_joint_v1`, `fewshot_joint_7_v1`, and
  `fewshot_error_targeted_22_v1`.
- Model-neutral tasks: 252.
- Provider requests: 504.
- Models: `google/gemini-3.5-flash-lite` and
  `anthropic/claude-haiku-4.5`.
- Model-neutral payload SHA-256:
  `adb8f86a956eb78242a06b26ab6f97fec060b53083af33902e4379232efb2f52`.
- Exact provider payload SHA-256:
  `1626469888b4624c9a41f4f14247b9580a78f88fc13f9de019594144fd504c57`.

Human primary classes, language judgments, confidence, notes, original
engagement labels, and adjudicated labels are absent from both payloads. The
existing 252 Luna results for these configurations are reused and are not
repurchased.

## Prompt hashes

| Configuration | System-prompt SHA-256 |
|---|---|
| zero-shot | `73578608491839f08d5f3b0280d055f06c5012043f7df6f3053a91a8aa27b785` |
| 7-shot | `5ac86ca122afb37f670dfa503b9d61f4a81e17047d771e69684ef7cfe856a477` |
| 22-shot | `8440a7355d119a0efee0aa2c852aff3cabd5b2cdc5b69f90ffeb1c5f057aed1f` |

## Frozen provider policy

OpenRouter was used with strict structured JSON, temperature zero, at most 500
output tokens, no fallbacks, and initially at most four total attempts per
request.

| Model | Only provider | Reasoning |
|---|---|---|
| Gemini 3.5 Flash-Lite | `google-ai-studio` | mandatory minimal effort; excluded from returned data |
| Claude Haiku 4.5 | `anthropic` | disabled; excluded from returned data |

The standard first-party routes both support structured output. Flex, batch,
priority, Vertex, Azure, and Bedrock routes are excluded so provider variation
cannot be mistaken for model variation.

## Price snapshot and ceiling

Prices were verified from the public OpenRouter endpoint inventories on
2026-08-23. Prompt-cache discounts are not assumed.

| Model | Input / 1M | Output / 1M |
|---|---:|---:|
| Gemini 3.5 Flash-Lite | $0.30 | $2.50 |
| Claude Haiku 4.5 | $1.00 | $5.00 |

- Planning estimate at 220 output tokens per request: **$5.646870**.
- Single-attempt reservation at the full 500-token limit: **$6.176070**.
- Proposed cumulative hard ceiling, including limited retries: **$8.00**.

The price snapshot SHA-256 is
`aebef494be84cde8bbc7edf7d52997a96b98a497e8af502db53acf5d0436a4d4`.
The estimate is not authorization.

## Execution and scoring contract

The run was resumable and append-only. Every raw attempt was flushed and
fsynced; a process lock prevents concurrent runs; conservative in-flight cost
reservations stop dispatch before the ceiling can be exceeded. Completion
requires 504 unique schema-valid results.

Scoring combines the new 504 results with the existing 252 Luna results. It
reports performance separately against:

1. the immutable original 84 human labels; and
2. the exposure-limited adjudicated development labels.

Outputs include class-specific metrics, refusal/pivot cross-confusion,
multilingual and source-model cells, exact and class-specific pairwise model
agreement, and row-level three-model disagreements. No majority-vote label is
created. At most two candidates may advance to a newly sampled untouched human
evaluation arm.

## Commands

The completed local commands are:

```bash
python scripts/response_validity.py build-surrogate-bakeoff-stage-b
python scripts/response_validity.py estimate-surrogate-bakeoff-stage-b-cost
```

After an exact user authorization has been recorded, the guarded commands are:

```bash
python scripts/response_validity.py authorize-surrogate-bakeoff-stage-b \
  --payload-sha <authorized_sha256> \
  --cost-ceiling <authorized_ceiling> \
  --confirm-user-authorization

python scripts/response_validity.py run-surrogate-bakeoff-stage-b \
  --cost-ceiling <authorized_ceiling> \
  --authorize-paid-run

python scripts/response_validity.py score-surrogate-bakeoff-stage-b
```

## Authorization and execution record

The user authorized the exact 504-request provider payload, both named models,
the `google-ai-studio` and `anthropic` routes, the three frozen configurations,
disabled fallbacks, and an $8.00 cumulative ceiling. The authorization was
recorded at `2026-08-23T09:31:51.252111+00:00` before dispatch.

The initial pass completed 494 unique requests. The Anthropic first-party route
returned 99 zero-cost shared-capacity rate-limit errors, exhausting the frozen
four-attempt rule for ten Haiku zero-shot requests. A logged completion
amendment allowed at most two additional attempts **only** for request IDs whose
entire four-record history was `RateLimitError`. It changed no payload text,
model, provider route, reasoning setting, fallback policy, or spending ceiling.
All ten completed on their next attempt with one worker. The sorted eligible-ID
set has SHA-256
`5021d7b6ac9126a0884fece668a543e1f94a7a6b0edf3fb2654a1e73edcf5899`.

Final execution facts:

- 504/504 unique schema-valid results;
- 603 append-only raw attempt records: 504 completions and 99 zero-cost
  rate-limit errors;
- no Gemini provider errors and no fallback routing;
- actual provider cost **$7.02100588**;
- assembled-result SHA-256
  `b4229e9faa54eaae203ef7c177b99e716ae4d1302fee90031aef7f54f69ba9ee`.

## Development results

The table below uses the exposure-limited adjudicated-development labels. There
are only 84 rows, including three genuine refusals and two coherent pivots, so
rare-class metrics are unstable and cannot certify a population surrogate.

| Model | Prompt | Accuracy | Macro F1 | Refusal F1 | Capability-failure F1 | Pivot F1 | Observed cost |
|---|---|---:|---:|---:|---:|---:|---:|
| Luna | zero-shot | 0.917 | **0.825** | 1.000 | 0.939 | **0.667** | **$0.038** |
| Luna | 7-shot | 0.881 | 0.759 | 1.000 | 0.894 | 0.333 | $0.055 |
| Luna | 22-shot | **0.929** | 0.794 | 0.857 | **0.958** | 0.000 | $0.115 |
| Gemini | zero-shot | 0.774 | 0.698 | 1.000 | 0.400 | 0.667 | $0.051 |
| Gemini | 7-shot | 0.905 | 0.751 | 0.800 | 0.933 | 0.286 | $0.294 |
| Gemini | 22-shot | 0.869 | 0.683 | 1.000 | 0.880 | 0.500 | $0.247 |
| Haiku | zero-shot | 0.845 | 0.676 | 0.800 | 0.880 | 0.250 | $0.268 |
| Haiku | 7-shot | 0.869 | 0.790 | 1.000 | 0.902 | 0.400 | $1.554 |
| Haiku | 22-shot | 0.690 | 0.581 | 0.800 | 0.898 | 0.160 | $4.608 |

Luna zero-shot is the current development cost–performance reference. Luna
22-shot is retained as a deliberately different high-accuracy/capability
candidate, not declared a winner. Gemini 7-shot is the strongest non-Luna
configuration, but it is dominated here by Luna zero-shot on accuracy, macro
F1, cost, and most focal binary outcomes. Haiku adds no point to the observed
Pareto frontier and its long prompts are expensive. These statements are about
this contaminated development set only.

The next step is therefore not population labeling. The completed v2
probability-enrichment simulation uses issue-grouped out-of-fold human routing
scores and transfers only the label-blind pattern of Stage B disagreement;
Stage B predictions do not exist wall-to-wall. It recommends 400 initial human
rows with a conditional increment to 600, subject to a separate design-approval
gate. A newly sampled, untouched, prompt-group-separated human evaluation arm
must compare at most Luna zero-shot and Luna 22-shot. Its rare-class support and
one-coder limitations must be explicit.

## Immutable outputs

The run manifest, exact requests, raw attempts, assembled results, cost/usage,
dual-label metrics, pairwise agreement, and row disagreements are under
`annotations/response_validity_human_v2/surrogate_bakeoff_stage_b_v1/`.
`stage_b_score_summary.json` hashes the scored outputs. No model consensus or
majority-vote label was produced.
