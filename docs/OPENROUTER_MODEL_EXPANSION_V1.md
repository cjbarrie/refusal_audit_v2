# OpenRouter-first model expansion v1

Status: **completed expansion provenance**. This document begins with the
eight-model pilot and then records the accepted seven-model v3 expansion,
including Hunyuan's all-language revision and all three Luna v2.4 annotation
batches. The resulting seven models are part of the 18-model `canon_024`
working release. The failed Mistral Small and Apertus routes remain historical
comparators and are not analysis rows. Prices and catalog metadata were checked
against OpenRouter's public model catalog on 2 September 2026. The pilot roster
is `config/model_rosters/openrouter_expansion_v1.json`; the production rosters
are the versioned `openrouter_expansion_v3*` files in the same directory.

## What this adds

The roster adds eight relatively affordable subject models while preserving
the existing panel unchanged. These models are opt-in: an ordinary
`generate_responses.py` command still uses `config.TEST_MODELS` and cannot pick
up any of these candidates by accident.

| Developer jurisdiction | Display name | Exact OpenRouter ID | Input / output per million tokens |
|---|---|---|---:|
| China | GLM 4.7 Flash | `z-ai/glm-4.7-flash` | $0.06 / $0.40 |
| China | Kimi K2.5 | `moonshotai/kimi-k2.5` | $0.45 / $2.25 |
| China | Hunyuan A13B Instruct | `tencent/hunyuan-a13b-instruct` | $0.14 / $0.57 |
| United States | Gemini 2.5 Flash-Lite | `google/gemini-2.5-flash-lite` | $0.10 / $0.40 |
| United States | Llama 4 Scout | `meta-llama/llama-4-scout` | $0.10 / $0.30 |
| United States | Nova Lite 1.0 | `amazon/nova-lite-v1` | $0.06 / $0.24 |
| Europe | Mistral Small 3.2 24B | `mistralai/mistral-small-3.2-24b-instruct` | $0.075 / $0.20 |
| Europe | Ministral 3 14B | `mistralai/ministral-14b-2512` | $0.20 / $0.20 |

“Jurisdiction” refers to the model developer, matching the study's existing
coding. It does not claim that an OpenRouter inference endpoint is physically
located in that jurisdiction.

The selection is deliberately not a frontier-model leaderboard. The purpose is
to increase the number and variety of developers observed in each jurisdiction
at a manageable price while retaining models capable of answering the short
multilingual political prompts.

## Fixed generation settings

Every model is configured for temperature 1.0 and at most 5,000 completion
tokens, matching the current subject-generation default. Provider fallbacks are
disabled and every model is pinned to one named OpenRouter endpoint. GLM, Kimi,
Hunyuan and Gemini advertise a reasoning
control, so their request body explicitly sets reasoning off and excludes it
from the response. The remaining models do not advertise that parameter and do
not receive it.

The response JSONL records the exact roster version and SHA-256, requested
model and routing controls, developer jurisdiction, returned model/provider,
token counts, and provider-reported cost. Hidden reasoning is never stored for
an expansion run.

The selected endpoint tags are DeepInfra BF16 for GLM, DeepInfra FP4 for Kimi,
SiliconFlow FP8 for Hunyuan, Google AI Studio for Gemini, DeepInfra FP8 for
Llama Scout and Mistral Small, Amazon Bedrock for Nova Lite, and Mistral's ZDR
route for Ministral. These were available and healthy in the public endpoint
catalog on 2 September 2026. The present roster remains blocked until a frozen
pilot payload and separate cost authorization exist.

## Prompt frame

The analysis battery is not `prompts/rebalanced_prompts_en.json`; that file is
the 11,089-row source bank. The frozen study draw is the five files:

```text
prompts/sampled/rebalanced_prompts_{en,zh,ar,ru,hi}_sample.json
```

Each contains the same 2,496 prompt IDs. A complete model therefore produces
12,480 responses: 2,496 prompts in each of five languages. The sample manifest
at `prompts/sampled/rebalanced_sample_manifest.json` records the draw, paths and
counts; the expansion roster separately freezes the SHA-256 of every language
file. The generator verifies the path, count and hash before reading a key or
making a provider call.

## Local validation and costs

These commands are local and free:

```bash
PY=python3.9
$PY scripts/model_roster.py config/model_rosters/openrouter_expansion_v1.json

$PY scripts/generate_responses.py \
  --roster config/model_rosters/openrouter_expansion_v1.json \
  --prompts prompts/sampled/rebalanced_prompts_en_sample.json \
  --output /tmp/openrouter-expansion-dry-run.jsonl \
  --dry-run
```

The planning scenario is 100 input and 1,500 output tokens per response. For
12,480 responses per model, the generation estimates are:

| Model | Estimated generation cost |
|---|---:|
| GLM 4.7 Flash | $7.56 |
| Kimi K2.5 | $42.68 |
| Hunyuan A13B | $10.85 |
| Gemini 2.5 Flash-Lite | $7.61 |
| Llama 4 Scout | $5.74 |
| Nova Lite | $4.57 |
| Mistral Small 3.2 | $3.84 |
| Ministral 14B | $3.99 |
| **Eight-model generation total** | **$86.84** |

This is an expected-cost calculation, not authorization and not a hard ceiling.
At current Luna v2.4 prices, annotating the additional 99,840 responses is
roughly another $93.76 under the previous run's conservative per-response token
assumption. Generation plus annotation is therefore about $180.60 before a
pilot, audit sample and contingency. Actual cost will depend mainly on response
length, especially for Kimi.

## Required next gate

Do not switch `provider_calls_authorized` in the roster itself. The multilingual
pilot below has now been frozen with exact prompt hashes, provider routes and a
cost ceiling. Its next gate is a separate explicit user authorization bound to
the exact payload SHA-256 and ceiling.

## Frozen pilot v1

The first pilot contains 40 prompt
meanings, all five languages and all eight models: **1,600 requests**. Each
prompt comes from a different issue. This is an enriched diagnostic sample,
not a probability sample and not a basis for estimating prevalence.

Within regular and boundary-testing prompts separately, it selects five cases
from each of four groups defined using final Luna v2.4 outcomes in the existing
panel:

1. high prior genuine-refusal propensity;
2. moderate prior genuine-refusal propensity;
3. zero prior genuine refusals;
4. a deterministic diverse reference group.

The selection algorithm then favors underrepresented regions, topic domains and
harvest routes. The resulting 40 cases cover all six regions, all nine domains
and all three routes. This gives the pilot hard, ordinary and varied prompts
without pretending that its refusal rate represents the full corpus.

Local artifacts are under
`annotations/model_expansion_v1/openrouter_pilot_v1/` and are gitignored because
they contain full prompt text. Their tracked construction code is
`src/refusal_audit/model_expansion/openrouter_pilot.py`.

```text
Requests:                 1,600
Payload SHA-256:          9e5b2ef03ded2a5c55352fd8f8e6f7a459a4dd917a45567395c4fbfd9e1b3835
Estimated input tokens:   83,496
Planning cost:            $1.3804
One-attempt reservation:  $4.5724
Suggested hard ceiling:   $6.00
Concurrency:              16 workers by default; maximum 32
Retries:                  at most two attempts per request
```

The runner is append-only and resumable. Before dispatching a request it
reserves that request's maximum possible cost against the ceiling. It stores
the visible response, model/provider identity, token accounting and cost, but
never hidden reasoning. Authorization must match the exact payload SHA-256 and
$6.00 ceiling.

The local preparation commands are:

```bash
$PY scripts/openrouter_expansion.py prepare-pilot
$PY scripts/openrouter_expansion.py estimate-pilot-cost
```

### Completed generation

The user authorized the exact payload and $6.00 ceiling on 2 September 2026.
Generation completed the same day:

```text
Intended keys:             1,600
Completed keys:            1,600
Incomplete keys:           0
Provider attempts:         1,613
Temporary 429 attempts:    13
Recovered on retry:        13
Actual provider cost:      $0.92431526
Authorized ceiling:        $6.00
Attempts SHA-256:          dfd500790fb1d4d9f20cf680bb6c28afbf183571fb23ffb80a6a02387298e763
Results SHA-256:           628082dea70a1714214f22347d8452e8adbd2b4587b2587b4874c5a60352d2ae
```

Every requested provider matched the provider returned by OpenRouter. Each
model contributed exactly 200 responses. No response was empty, no hidden
reasoning field was returned, and no inline `<think>` block remained. Eleven
temporary rate limits came from Mistral Small on DeepInfra and two from GLM on
DeepInfra; all recovered within the authorized two-attempt limit.

The generation pilot also did what it was intended to do: it exposed at least
one obvious capability failure before annotation. An Arabic Mistral Small
response hit the 5,000-token ceiling and expanded to 154,097 characters through
large whitespace runs and mixed-language degeneration. This is not silently
called a refusal. The v2.4 annotation stage must classify refusal and capability
failure separately across all 1,600 responses.

## Frozen Luna v2.4 annotation payload

All 1,600 pilot responses will be measured with the adopted Luna v2.4
annotation procedure. This is the same codebook, system prompt and strict JSON
schema used for the completed wall-to-wall corpus. The annotation request shows
Luna the target language, English reference prompt, target-language prompt and
original response. It does not use an English response translation. It also
does not reveal which subject model produced the response, its provider, the
pilot band, prior labels, or the reason the prompt entered the enriched pilot.

The response index that restores those fields is stored separately from the
provider payload. This permits model- and language-specific pilot summaries
after annotation without giving the judge information that might influence its
decision. The index contains exactly 200 responses per subject model and 320
per language.

```text
Requests:                    1,600
Luna model:                  openai/gpt-5.6-luna
Pinned provider:             OpenAI through OpenRouter
Input mode:                  source response only; no response translation
Temperature:                 0
Maximum output:              500 tokens
Reasoning:                   disabled and excluded
Provider fallbacks:          disabled
Maximum attempts:            3 per response
Estimated input tokens:      4,119,237
Planning output tokens:      320,000
Planning cost:               $1.2078474
One-attempt reserved cost:   $1.7838474
Suggested hard ceiling:      $2.50
Payload SHA-256:             917b7ecac55ebeec807c812a5254a0d30ae4910373f9ab8977ce073fec027e8c
Adopted prompt SHA-256:       d8b64963f77bd796f8bfc7d778ca2437c6fb5c572c9af0f7398955adaf3eb8af
Adopted schema SHA-256:       51ff1ebb6cf77fa05202b7391f0d0e2ba01e0c39caeafc2a10feaeea747d9c16
```

Preparation and costing are local and make no provider call:

```bash
$PY scripts/openrouter_expansion.py prepare-annotations
$PY scripts/openrouter_expansion.py estimate-annotation-cost
```

The user authorized this exact payload and ceiling on 2 September 2026. The
append-only runner used 16 concurrent workers and required 1,604 total attempts:
1,600 schema-valid completions and four invalid first or second responses that
were retried. No case remained incomplete.

```text
Completed annotations:       1,600 / 1,600
Schema success:              100%
Provider attempts:           1,604
Invalid attempts retried:    4
Actual provider cost:        $0.72121651
Authorized ceiling:          $2.50
Attempts SHA-256:            f1893f70b17e28d39443fd6b1c6bce0e8501c15f5b54163ffdf9045f258e5578
Results SHA-256:             da3e2d6c8ec54456425ea070c613bb9c3d2bd4b57795dabf460bc5e347e643f9
```

The four invalid attempts were internal consistency failures caught by the
codebook validator—for example, reporting a refusal evidence span alongside a
non-refusal, or calling an incoherent response a refusal. Retrying yielded a
valid record in every case. The result file preserves the raw provider output,
usage and provider-reported cost for each accepted annotation.

### What the enriched pilot found

Luna classified 142 responses as genuine refusals and 279 as capability
failures; 15 met both definitions. These are deliberately separate outcomes.
A coherent refusal can also be in the wrong language or otherwise technically
damaged, so the categories are allowed to overlap.

The unweighted pilot rates were 8.9% genuine refusal and 17.4% capability
failure. They are **not prevalence estimates**. The 40 prompts were enriched
using existing refusal patterns and coverage criteria, rather than sampled
with known equal probabilities from the full prompt battery. Consequently,
these rates cannot be used as estimates for the complete corpus or as direct
jurisdiction comparisons.

The principal diagnostic is capability rather than an overall ranking. Mistral
Small produced capability failures on 71.0% of its 200 pilot responses, while
the other seven models ranged from 6.5% to 17.5%. Luna initially put the Hindi
failure rate at 47.5%. The independent Hindi audit below showed that this was
mostly a Luna language-classification error and must not be used as the Hindi
viability estimate. The previously observed 154,097-character Arabic Mistral
output was correctly classified as a capability failure rather than silently
treated as a refusal. Together, these results support language-specific gates
before a full generation run rather than accepting or rejecting each model as
an indivisible five-language package.

The reproducible local assembly command is:

```bash
$PY scripts/openrouter_expansion.py summarize-annotations
```

It creates an assembled label table and summaries by model, language, and
model-language cell. It makes no provider call and states explicitly that the
enriched pilot is descriptive only.

## Independent Hindi language and capability audit

### Why the audit used all 320 Hindi responses

Luna labelled 124 of the 320 Hindi responses as wrong-language and 152 as
capability failures. Checking only those positive cases would reveal false
positives but could not detect cases Luna had incorrectly cleared. The audit
therefore included every Hindi pilot response: all 152 Luna-flagged cases and
all 168 Luna-negative controls. Each of the eight model–Hindi cells contributed
the same 40 prompts. The selection did not depend on Sol or on the subject
model's identity.

Sol received the exact v2.4 system prompt, strict JSON schema, target-language
prompt, English reference prompt and original response used for the Luna
annotations. It did not receive Luna's labels, the subject-model identity, the
pilot band or any other selection metadata. No English response translation
was used. This is an independent same-codebook machine audit, not human ground
truth and not a probability sample from the full prompt battery.

```text
Requests:                    320
Rows per model–Hindi cell:   40
Sol model:                   openai/gpt-5.6-sol
Pinned provider:             OpenAI through OpenRouter
Temperature:                 0
Maximum output:              500 tokens
Reasoning:                   disabled and excluded
Provider fallbacks:          disabled
Maximum attempts:            3
Estimated input tokens:      836,793
Planning cost:               $2.313586
Authorized ceiling:          $4.50
Payload SHA-256:             c1756951d141fc175a703952b74ca60e5cb801e34863e03794ad89f8c00f052c
```

The user authorized the exact payload on 2 September 2026. Sixteen concurrent
workers completed all 320 requests on their first attempt. Every response
passed the strict schema and internal consistency checks.

```text
Completed annotations:       320 / 320
Provider attempts:           320
Invalid or failed attempts:  0
Actual provider cost:        $1.458978
Attempts SHA-256:            4b4cc9590e2805f78fee7ad8fa09e625ddf7190718c826016cad3d4bc38a3b28
Results SHA-256:             dd05143bbe006c26e53b58200e00f3cb0f2330bd19d497afaeea176c643bf8d3
```

### What the audit found

Sol called one response wrong-language, compared with Luna's 124. Exact
language-fidelity agreement was 56.3%. Sol called 46 responses capability
failures, compared with Luna's 152; binary capability agreement was 66.3% and
Cohen's kappa was 0.30. Of the 152 Luna capability positives, Sol retained 45
and overturned 107. Sol added one failure among Luna's 168 negatives.

This difference is not caused by a faulty join. There were 112 responses that
Luna called wrong-language and Sol called target-language. In every non-Mistral
cell, the median share of alphabetic characters in Devanagari among these
overturned cases ranged from 88.7% to 100%; the cell-specific minima ranged
from 66.3% to 98.5%. The responses Luna rejected were therefore visibly Hindi
in script. The deterministic script check is supporting evidence rather than a
semantic language label, but it establishes that Luna's Hindi decisions were
systematically unreliable.

The viability rule was fixed before examining Sol's labels:

- **approve:** at least 90% target-language and at most 10% capability failure;
- **conditional larger pilot:** at least 80% target-language and at most 20%
  capability failure;
- **reject Hindi:** below either conditional threshold.

These are operational gates applied to the 40-response enriched pilot cells.
They are not estimates of full-corpus failure prevalence. Genuine refusal does
not count against viability because refusal is the outcome being measured.

| Subject model | Sol target-language | Sol capability failure | Decision |
|---|---:|---:|---|
| Gemini 2.5 Flash Lite | 40/40 | 0/40 | approve |
| GLM 4.7 Flash | 39/40 | 2/40 | approve |
| Hunyuan A13B | 40/40 | 1/40 | approve |
| Kimi K2.5 | 40/40 | 2/40 | approve |
| Llama 4 Scout | 40/40 | 0/40 | approve |
| Ministral 14B | 39/40 | 0/40 | approve |
| Mistral Small 3.2 | 15/40 | 39/40 | reject Hindi |
| Nova Lite | 40/40 | 2/40 | approve |

Mistral Small remains excluded. The other seven model–Hindi cells pass the
predeclared gate and may proceed if those models enter the full expansion.
Their other language cells require their own cell-level decisions; this Hindi
audit does not approve each model as a five-language package.

The guarded implementation is
`src/refusal_audit/model_expansion/hindi_cell_audit.py`, exposed through
`scripts/archive/model_expansion_pilot/hindi_expansion_audit.py`. The wrapper is
preserved as reference code, not maintained as a current command.

The paired labels, disagreements, script diagnostics, Wilson intervals and
cell decisions are stored under
`annotations/model_expansion_v1/openrouter_pilot_v1/hindi_sol_v2_4_cell_audit_v1/`.

## All-cell registry and Hunyuan follow-up

The next decision pass applies the same viability thresholds to each of the 40
completed model–language pilot cells. It does not promote a model simply because
one of its language cells succeeds. Three sources enter the registry:

1. the completed Luna pilot labels for all 40 cells;
2. the complete Sol Hindi audit above, which replaces Luna for the seven
   retained Hindi cells; and
3. the protected 1,173-response same-codebook comparison, where Luna recovered
   376 of Sol's 384 capability failures (recall .979). This external comparison
   supports using Luna to clear cells whose pilot rates are far inside the
   operational boundary, but it does not rescue a borderline cell.

Mistral Small's five cells are marked `removed_model` following the explicit
model removal and the 71% overall pilot failure rate. Twenty-six non-Hindi cells
for the remaining models pass the gate with clear Luna margins, and seven Hindi
cells pass under Sol. Two cells remain unresolved:

| Cell | Luna target-language | Luna capability failures | Provisional status |
|---|---:|---:|---|
| Hunyuan A13B–English | 37/40 | 8/40 | pending Sol |
| Hunyuan A13B–Russian | 38/40 | 6/40 | pending Sol |

Both are outside the 10% capability-failure approval threshold but within the
20% conditional band. The follow-up therefore included all 40 responses from
each cell. It does not select only Luna-positive rows: the 66 Luna-negative
responses remain controls capable of revealing false negatives.

```text
Requests:                    80
Cells:                       Hunyuan A13B–English and Hunyuan A13B–Russian
Rows per cell:               40
Sol model:                   openai/gpt-5.6-sol
Pinned provider:             OpenAI through OpenRouter
Input mode:                  source response only; no translation
Temperature:                 0
Maximum output:              500 tokens
Reasoning and fallbacks:     disabled
Estimated input tokens:      181,373
Planning cost:               $0.522746
One-attempt reserved cost:   $0.762746
Suggested hard ceiling:      $1.00
Payload SHA-256:             ff956d75fb3f2d4880665ce420058000c250636c00f19d95a300681cdd66fec6
```

The provisional registry is
`annotations/model_expansion_v1/openrouter_pilot_v1/cell_viability_v1/provisional_cell_registry.csv`.
Its implementation and guarded audit runner are
`src/refusal_audit/model_expansion/cell_viability_registry.py` and
`scripts/archive/model_expansion_pilot/expansion_cell_registry.py`.

### Hunyuan audit result and final registry

The user authorized the exact 80-request payload on 2 September 2026. All 80
requests completed on the first attempt, passed the strict schema checks and
cost $0.2814009. No provider fallback or reasoning output was used.

```text
Completed annotations:       80 / 80
Provider attempts:           80
Invalid or failed attempts:  0
Actual provider cost:        $0.2814009
Authorized ceiling:          $1.00
Attempts SHA-256:            daa4184c5996499405511f861d6e19ec2df2199d02c265805d6501b3d3eb9cbb
Results SHA-256:             7f25d89a727879e92bf6ef9cfe72046e870c4573ceaab928f2a8ad4ee7b9fd40
```

Neither cell crossed the approval threshold. Hunyuan English contained 36/40
target-language responses and 6/40 capability failures. Hunyuan Russian
contained 40/40 target-language responses and 5/40 capability failures. Their
failure rates of 15.0% and 12.5% remain within the prespecified conditional
band but exceed the 10% approval ceiling. Wilson 95% intervals for the failure
rates are 7.1–29.1% and 5.5–26.1%, respectively.

The final registry therefore contains:

- 33 approved cells;
- two conditional cells: Hunyuan English and Hunyuan Russian; and
- five removed cells belonging to Mistral Small.

The primary expansion excludes the two conditional cells. They can be added in
a separately labelled sensitivity expansion or reconsidered after a larger
pilot, but they are not silently promoted by relaxing the gate. The final
registry is
`annotations/model_expansion_v1/openrouter_pilot_v1/cell_viability_v1/final_cell_registry.csv`.

### Cost of the approved-cell expansion

The 33 approved cells contain 2,496 prompts each, giving 82,368 prospective
responses. Two estimates are retained because they answer different planning
questions:

- Under the roster assumption of 100 input and 1,500 output tokens per
  response, generation costs $78.67.
- Extrapolating the observed provider charges within the matching 40-response
  pilot cells gives $52.28 for generation and $37.43 for Luna annotation, or
  $89.71 combined.

The first figure holds token use fixed at the planning assumption. The second
preserves model- and language-specific pilot usage but extrapolates from an
enriched prompt set. Neither is a spending authorization. At the configured
5,000-token response limits, the maximum single-attempt generation reservation
would be $259.15; the runnable payload therefore needs staged execution and a
fresh ceiling based on its exact frozen requests.

Adding the two conditional Hunyuan cells would contribute another 4,992
responses. Their planning generation cost is $4.34; the pilot-extrapolated
generation-plus-annotation cost is $4.52. This small incremental cost does not
alter their scientific status.

The model-level cost table and input hashes are stored in
`annotations/model_expansion_v1/openrouter_pilot_v1/cell_viability_v1/approved_expansion_cost_by_model.csv`
and `approved_expansion_cost_estimate.json`. The archived wrapper records how
they were produced; the files are frozen provenance rather than live planning
outputs.

## Frozen approved-cell full run (v3)

The planning matrix above was converted into a runnable—but still
unauthorized—payload on 2 September 2026. The v3 roster does not treat a model
as an all-language package. It includes the 33 cells marked `approved` in the
final registry: all five languages for Gemini, GLM, Kimi, Llama, Ministral and
Nova, and Arabic, Hindi and Chinese only for Hunyuan. Hunyuan English and
Russian remain conditional; all Mistral Small cells and the failed Apertus
route are absent.

### Comparability contract

Every request uses the same canonical prompt text that was used for the
original model panel and the expansion pilot. For a given prompt ID and
language, the text is byte-identical across subject models. Each request has
exactly one `user` message and no system message. Temperature remains 1.0,
the maximum output is 5,000 tokens, the provider is singly pinned, fallbacks
are disabled, and reasoning is disabled where the route supports that switch.
The only intended request-level differences are the model/route and the
approved presence or absence of a model–language cell.

The five prompt files remain hash-locked:

| Language | SHA-256 |
|---|---|
| English | `14d2d4a6d95423cfe1f8d41499087da5160052130cb0f208addb52664cc1fba2` |
| Chinese | `0582a9b5457ec2df43c6bfb2e8bad4307fd13e3b6b8652509a873b20c62b722f` |
| Arabic | `816401bafc50e5d3fd6686a36f2c2934bc919a614fe0eea3bbfb6d2187a84381` |
| Russian | `3487e9aba0b39e101b7209235a05f390905617bd0dcbb62dec26ebf583d1d994` |
| Hindi | `b1300f6303ac08f8fd2197ba7d660b7abcfe66c1a57b92ee45a20c3c1c2fb014` |

### Stages, payload hashes and stop-loss ceilings

The 82,368 requests are split by model. This lets each route be authorized,
run and checked independently; a failure in one model cannot consume the
budget reserved for another. The cost estimate uses the fixed `o200k_base`
tokenizer for prompt planning, plus 1,500 output tokens per response. This is a
consistent cross-model planning count; provider billing remains final because
routes may tokenize differently. The hard ceiling is a
stop-loss set 50% above that planning estimate and rounded upward to the next
50 cents. It is not a prediction that every response will use 1,500 tokens.
The separate 5,000-token column shows the much more conservative cost if every
request reached its configured maximum.

| Stage | Model | Cells | Requests | Planning cost | 5,000-token reservation | Suggested ceiling | Payload SHA-256 |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | Ministral 14B | 5 | 12,480 | $3.87 | $12.61 | $6.00 | `2040c57d5d05917fb4751ab6aea9eb98802ae490dea4d54a0fbcf354be329cca` |
| 2 | Nova Lite | 5 | 12,480 | $4.53 | $15.02 | $7.00 | `fc738c3dfb3fd06f1b2083d45f57fe1b996caad69fe7d83ebbe10f44cdd3d77e` |
| 3 | Llama 4 Scout | 5 | 12,480 | $5.68 | $18.79 | $9.00 | `f89fdfb66c1fcfa670871f88473daff756b6c8274d968a0c277e8d6925515dca` |
| 4 | Hunyuan A13B | 3 | 7,488 | $6.46 | $21.40 | $10.00 | `f2ea2f7c7db2f2db6cb174c7711f17943730ddc7e0cd30a9cfbe3c7b54740341` |
| 5 | GLM 4.7 Flash | 5 | 12,480 | $7.53 | $25.00 | $11.50 | `de9b2fb6ae67979af38d7428cdd22c303d213838a20af12987dcc176400e0d7f` |
| 6 | Gemini 2.5 Flash Lite | 5 | 12,480 | $7.55 | $25.03 | $11.50 | `b3c52f1d302aee6d6093e64fc0eaa6aea2b3225c534e1797c109af89ef8433cb` |
| 7 | Kimi K2.5 | 5 | 12,480 | $42.41 | $140.69 | $64.00 | `b6eafbeb05583604c2c2cfbc712cd8a728416a9adebcd0e4e1ea357f3f7924a9` |
| **Total** |  | **33** | **82,368** | **$78.04** | **$258.53** | **$119.00** |  |

No request was sent during freezing. The payloads are local, derived artifacts
under `annotations/model_expansion_v3/full_run_v1/` and are excluded from Git
because they contain complete prompt text. Their construction code, roster,
hashes and tests are tracked in:

- `config/model_rosters/openrouter_expansion_v3_cell_approved.json`;
- `src/refusal_audit/model_expansion/full_run_v3.py`;
- `scripts/openrouter_expansion_v3.py`; and
- `tests/test_openrouter_expansion_v3.py`.

The local reconstruction and cost check are:

```bash
PYTHONPATH=src python scripts/openrouter_expansion_v3.py prepare
PYTHONPATH=src python scripts/openrouter_expansion_v3.py cost
```

Neither command can call a provider. A paid runner and authorization record
must be added only after the user authorizes an exact stage hash and ceiling.

### Stage 1 completion: Ministral 14B

The user authorized Stage 1 on 2 September 2026, binding authorization to the
12,480-request payload hash and a $6.00 ceiling. The run completed the same day.
All 12,480 expected responses are present under unique request IDs, with 2,496
responses in each of English, Chinese, Arabic, Russian and Hindi. There are no
empty responses and no recorded request errors. Every provider result reports
the requested `mistralai/ministral-14b-2512` model and Mistral as the serving
provider; no reasoning output was returned.

```text
Expected responses:          12,480
Completed responses:         12,480
Incomplete responses:        0
Recorded errors:             0
Locally attributed cost:     $5.1360152
Authorized ceiling:          $6.00
Payload SHA-256:             2040c57d5d05917fb4751ab6aea9eb98802ae490dea4d54a0fbcf354be329cca
Attempts SHA-256:            5c0e42e5cb8b1226bf9c67e393210b658dc7f48b74753250af71d764b97804cf
Results SHA-256:             189439845b6169b8e758d464889e1cace39270c50ccc601e77673ad22a1211c4
```

The first process was interrupted after 104 durable completions to increase
concurrency from 32 to 64 workers. Those 104 records were preserved and the run
resumed from them. At most 32 calls were in flight at interruption; any that
finished remotely after the local process stopped would be included in the
OpenRouter account bill but not in the locally attributed `$5.1360152`. The
maximum configured cost of those calls was about $0.032, which remained inside
the unused ceiling margin. The final response file itself has exact coverage
and no duplicate request IDs.

### Stage 2 completion: Nova Lite

The user authorized the exact 12,480-request Nova Lite payload under a $7.00
ceiling on 2 September 2026. All requests completed through the pinned Amazon
Bedrock route. The final file has 2,496 unique responses in each language, no
empty responses, no errors and no unexpected reasoning output. Every result
reports `amazon/nova-lite-v1` and Amazon Bedrock.

```text
Expected responses:          12,480
Completed responses:         12,480
Incomplete responses:        0
Recorded errors:             0
Provider cost:               $2.63699148
Authorized ceiling:          $7.00
Payload SHA-256:             fc738c3dfb3fd06f1b2083d45f57fe1b996caad69fe7d83ebbe10f44cdd3d77e
Attempts SHA-256:            f6cdfb7b6b9c6a193511602e4bfa10ff02d7b1caa752f6c257a1af06d9aaa818
Results SHA-256:             e188a1eb116f5e914c7e38ae18d6c9b110d7bc1c7e5f7720f52ff5635cf48541
```

### Stage 3 completion: Llama 4 Scout

The user authorized the exact 12,480-request Llama 4 Scout payload under a
$9.00 ceiling. DeepInfra returned 230 transient upstream rate-limit errors.
Concurrency was reduced from 64 to 16 before any request exhausted its second
attempt; all 230 affected requests then completed successfully. The final file
has 2,496 unique responses in each language, no empty responses and no
incomplete requests. Every result reports `meta-llama/llama-4-scout` and
DeepInfra, with no unexpected reasoning output.

```text
Expected responses:          12,480
Completed responses:         12,480
Incomplete responses:        0
Transient error records:     230
Requests recovered:          230
Requests exhausted:          0
Provider cost:               $2.2253998
Authorized ceiling:          $9.00
Payload SHA-256:             f89fdfb66c1fcfa670871f88473daff756b6c8274d968a0c277e8d6925515dca
Attempts SHA-256:            37d99a256e5761cd2e2e8c0053a339471589ef4e750c5c55ccc40f53aa3b15f7
Results SHA-256:             fe3d23032c89df1185a867e65e21ce9ebb4280a4a2e9d3adc9844c739a23a8c6
```

## V3.1 decision: retain every language for Hunyuan

On 3 September 2026, before any Hunyuan full-run request was sent, the user
revised the cell policy. English and Russian are retained even though their
enriched pilots crossed the provisional capability-failure gate. Capability
failure is an outcome to measure and report separately from genuine refusal;
using pilot outcomes to remove cells would also make the model panels differ
across languages and prevent Hunyuan's paired English-language contrasts.

The earlier three-language Stage 4 payload remains frozen for provenance but
is superseded and must not be run. The replacement contains all 2,496 prompts
in each of English, Chinese, Arabic, Russian and Hindi. English and Russian
carry `conditional_retained` flags so their pilot history remains visible in
analysis and sensitivity checks. Prompts, generation parameters and the pinned
SiliconFlow FP8 route are unchanged.

```text
Revised expansion models:    7
Revised expansion cells:     35
Revised expansion requests:  87,360
Hunyuan Stage 4 requests:    12,480
Planning cost:               $10.76143486
5,000-token reservation:     $35.65903486
Suggested hard ceiling:      $16.50
Payload SHA-256:             1fbcd681385d89cdb4e9b64cb82f2c069ba73443cb656f91d25acab39aaa6659
```

The immutable decision specification is
`config/model_rosters/openrouter_expansion_v3_1_all_languages.json`. The local
freeze and cost commands are:

```bash
PYTHONPATH=src python scripts/openrouter_expansion_v3.py prepare-hunyuan-revision
PYTHONPATH=src python scripts/openrouter_expansion_v3.py cost-hunyuan-revision
```

Neither command calls a provider. The replacement Hunyuan stage requires a
new hash- and ceiling-bound authorization.

## Luna v2.4 annotation of completed expansion models

The completed Ministral 14B, Nova Lite and Llama 4 Scout stages were frozen as
the first production annotation batch while Hunyuan generation continued. The
batch contains all 37,440 completed responses—12,480 per subject model and
2,496 per model–language cell. It does not select responses using their text or
any predicted outcome.

Luna receives the unchanged v2.4 system prompt, the canonical target-language
prompt, the English reference prompt and the source response. The input mode is
`source_response_only`: no machine translation is supplied. Subject-model
identity, provider route and selection metadata remain in the local join index
but are absent from Luna's messages. The structured-output schema, temperature
0, 500-token maximum, pinned OpenAI provider, disabled reasoning and disabled
fallbacks are identical to the adopted wall-to-wall annotation stage.

```text
Subject models:              Ministral 14B, Nova Lite, Llama 4 Scout
Requests:                    37,440
Estimated input tokens:      100,782,256
Planning output tokens:      7,488,000
Planning cost:               $29.1420512
Empirical cost projection:   $17.5929142
Suggested hard ceiling:      $35.00
Payload SHA-256:             9dc329e7a84c1848e1f10803d8adfba5d17be052af16f2882a778b2860b6daed
V2.4 prompt SHA-256:         d8b64963f77bd796f8bfc7d778ca2437c6fb5c572c9af0f7398955adaf3eb8af
V2.4 schema SHA-256:         51ff1ebb6cf77fa05202b7391f0d0e2ba01e0c39caeafc2a10feaeea747d9c16
```

The empirical projection uses the more conservative realized per-response
cost from two completed v2.4 runs: `$63.27810359 / 134,664` for the original
wall-to-wall run and `$0.72121651 / 1,600` for the expansion pilot. The $35
stop-loss is the larger of 120% of the token-based planning cost and 150% of
the empirical projection, rounded upward to 50 cents. It is intentionally much
tighter than assuming that every structured label uses the full 500-token
maximum.

The guarded implementation is
`src/refusal_audit/model_expansion/full_run_annotation_v3.py`; artifacts are
under `annotations/model_expansion_v3/luna_v2_4_completed_batch1/`. Preparation
and costing make no provider calls:

```bash
PYTHONPATH=src python scripts/openrouter_expansion_v3.py prepare-completed-annotations
PYTHONPATH=src python scripts/openrouter_expansion_v3.py cost-completed-annotations
```

The user authorized this exact payload under a $35.00 ceiling on 3 September
2026. All 37,440 labels completed. Four schema-invalid first attempts were
retried successfully, leaving no incomplete annotations and a final schema
success rate of 100%.

```text
Expected annotations:        37,440
Completed annotations:       37,440
Incomplete annotations:      0
Invalid first attempts:      4
Recovered on retry:          4
Provider cost:               $17.74093538
Authorized ceiling:          $35.00
Payload SHA-256:             9dc329e7a84c1848e1f10803d8adfba5d17be052af16f2882a778b2860b6daed
Attempts SHA-256:            387c0f73b3c9e0c11288153ea78f580fad28db1ee82a67cd6dbdd3b703e34e69
Results SHA-256:             3f14019c3aa6b5ec0890a69b61591a113b6fef81f750c5a6cc55f5cc04cfb80b
```

## Native Fanar candidate pilot (7 September 2026)

Fanar-C-2-27B was tested as a possible additional MENA model through Fanar's
native API. This is a candidate-route audit, not part of `canon_024` and not a
population sample. The frozen payload crossed the same 40 deliberately varied
prompt meanings used for expansion diagnostics with all five canonical
languages, producing 200 requested responses. Prompts and generation settings
were unchanged across languages: one user message, temperature 1.0, at most
5,000 completion tokens, repetition penalty 1.0, and thinking disabled.

The user authorized payload SHA-256
`4a60a5511384a304558f17be45514a9c61f9178cb1a610f61bcedcc2f01e4bd9`
with an absolute ceiling of 240 provider calls. The guarded runner made 200
calls. It returned 171 responses and 29 deterministic HTTP 400 content-filter
responses; no transient failure occurred and no retry was used. Returned
responses consumed 11,139 prompt tokens and 67,698 completion tokens. Fanar
does not expose a monetary charge in the response schema, so cost is recorded
as unavailable rather than zero.

| Language | Requested | Returned | Provider-filtered | Obvious script mismatch among returns |
|---|---:|---:|---:|---:|
| English | 40 | 38 | 2 | 0 |
| Chinese | 40 | 30 | 10 | 5 |
| Arabic | 40 | 33 | 7 | 1 |
| Russian | 40 | 36 | 4 | 13 |
| Hindi | 40 | 34 | 6 | 7 |

“Obvious script mismatch” is a deterministic screen: fewer than 20% of the
response's Latin, Han, Arabic, Cyrillic or Devanagari letters were in the
script expected for the prompt language. It is not a language-model or human
annotation. The enriched pilot also cannot estimate population failure or
refusal prevalence. The result nevertheless identifies two issues that must
remain separate in any later analysis: native provider filtering and a
returned model response in the wrong language. Neither is automatically a
model refusal.

The next gate was Luna v2.4 annotation of the 171 returned responses with the
unchanged source-response-only codebook, followed by model-language cell
review. Its payload SHA-256 was
`47b3a4d47d158a55a8d856407db659adef3320c6ff1bcb8d4faace5d73e33650`.
It contains an estimated 349,947 input tokens; the planning cost is $0.1110,
the single-attempt 500-token reservation is $0.1726, and the proposed hard
ceiling is $0.25. Luna is pinned to OpenAI, fallbacks and reasoning are
disabled, temperature is zero, and the output limit is 500 tokens. The 29
provider-filtered requests remain explicit structural provider outcomes and
are not passed to the refusal annotator or silently recoded as model refusals.
A full 12,480-response Fanar run is not approved by this pilot.

The user authorized that exact payload and ceiling on 7 September 2026. All
171 records completed with valid final schemas, at a provider-reported cost of
$0.05445338. One initial output omitted the required refusal evidence span and
was recovered on retry. Luna classified 43 returned responses
as genuine refusals and 38 as capability failures; 18 met both definitions.
The overlap is retained because a coherent refusal can also be delivered in
the wrong language. These are enriched-pilot proportions among returned
responses, not estimates of full-corpus prevalence.

| Language | Returned | Target language | Genuine refusals | Capability failures |
|---|---:|---:|---:|---:|
| English | 38 | 38 (100.0%) | 13 (34.2%) | 0 (0.0%) |
| Chinese | 30 | 25 (83.3%) | 5 (16.7%) | 8 (26.7%) |
| Arabic | 33 | 32 (97.0%) | 7 (21.2%) | 1 (3.0%) |
| Russian | 36 | 23 (63.9%) | 11 (30.6%) | 13 (36.1%) |
| Hindi | 34 | 18 (52.9%) | 7 (20.6%) | 16 (47.1%) |

To protect the cell decision against judge-specific language errors, all 171
returned responses were frozen for a same-codebook Sol audit. The messages and
schema were byte-identical to Luna's; only the judge model and derived request
ID changed. Payload SHA-256
`3d247df5165f23c2b4d563157a1cadaeab1f2240921639a8f243d03116b216ba`
was authorized under a $2.00 ceiling. Sol returned 170 valid labels for
$0.52939110. One English response produced no usable provider content on all
three authorized attempts and remains explicitly incomplete.

Treating Sol as a frontier machine reference, Luna's genuine-refusal outcome
had 97.1% accuracy, 90.5% precision, 97.4% recall and Cohen's kappa 0.919 over
170 matched rows. Its capability-failure outcome had 91.8% accuracy, 71.1%
precision, 90.0% recall and kappa 0.744. Ten language-fidelity labels differed;
all ten were Hindi. Sol confirmed that Luna had substantially overcalled Hindi
wrong-language output, but Fanar's Hindi cell still failed the established
quality gate.

| Language | Sol rows | Target language | Genuine refusals | Capability failures | Output gate |
|---|---:|---:|---:|---:|---|
| English | 37 + 1 incomplete | 37 (100.0%) | 11 (29.7%) | 0 (0.0%) | approve |
| Chinese | 30 | 25 (83.3%) | 6 (20.0%) | 5 (16.7%) | conditional |
| Arabic | 33 | 32 (97.0%) | 6 (18.2%) | 1 (3.0%) | approve |
| Russian | 36 | 23 (63.9%) | 10 (27.8%) | 13 (36.1%) | fail |
| Hindi | 34 | 26 (76.5%) | 6 (17.6%) | 11 (32.4%) | fail |

These gates concern returned model output only. No Fanar cell is yet approved
at the route level: the native content filter suppressed 2/40 English, 10/40
Chinese, 7/40 Arabic, 4/40 Russian and 6/40 Hindi requests, and the pilot
deliberately overrepresents challenging prompts. A probability-sampled route
audit is needed to estimate this selective blocking, or the analysis must
prespecify provider blocking as a separate service-level access-denial outcome
and show a composite sensitivity alongside genuine model refusal.

The preparation, execution and audit code is in
`scripts/fanar_pilot.py`, with shared native-API helpers in
`scripts/fanar_diagnostic.py`. Resumable raw records, the authorization, run
summary, manifest and deterministic diagnostics are generated under
`annotations/model_expansion_v4/fanar_c2_27b_pilot_v1/` and are excluded from
Git because they contain prompt and response text.

### Frozen probability-sampled route audit

The follow-up route audit treats the 40 already-observed prompt IDs as a
certainty stratum and draws 200 prompt IDs by simple random sampling without
replacement from the remaining 2,456. The same selected IDs are paired across
English and Arabic, giving 400 new requests. For either language, each sampled
remaining-frame prompt has inclusion probability `200/2456` and design weight
`2456/200 = 12.28`. The finite-population filter-rate estimator is

```text
[known filter total among the 40 certainty prompts
 + (2456/200) * filter total in the 200-prompt random sample] / 2496.
```

The certainty stratum has no sampling variance. The remaining-stratum variance
uses the usual simple-random-sampling finite-population correction. Route
approval is prespecified separately by language: approve when the estimated
filter rate is at most 5% and its design-based 95% upper bound is at most 10%;
conditional when the estimate is at most 10% but misses the approval rule; and
fail when the estimate exceeds 10%. These are operational comparability gates,
not substantive definitions of refusal.

The random seed is `20260907`. The frozen 400-request payload SHA-256 is
`f5266ba74cf81e70309a27ab7f5ac551c92fcb780b38830fe31000fb0ec512ad`.
It uses the unchanged Fanar generation settings and allows one retry only for
rate-limit, server or transport errors. Content-filter responses are not
retried. Because Fanar publishes no price, authorization is bounded by an
absolute ceiling of 480 provider requests rather than a monetary ceiling. The
user authorized this exact payload on 7 September 2026. The run completed all
400 logical requests in 400 provider calls, with 356 returned responses and 44
deterministic HTTP 400 content-filter outcomes. No transient failure or retry
occurred. Returned responses used 22,326 prompt tokens and 167,232 completion
tokens; monetary cost remains unavailable rather than zero.

| Language | Known filters in certainty 40 | Filters in remaining sample 200 | Design-weighted rate | Design-based 95% interval | Route gate |
|---|---:|---:|---:|---:|---|
| English | 2 | 17 | 8.44% | 4.79–12.10% | conditional |
| Arabic | 7 | 27 | 13.56% | 9.09–18.04% | fail |

English misses approval because the point estimate exceeds 5% and the upper
bound exceeds 10%. Arabic fails because its estimated filter rate exceeds 10%.
The route therefore does not supply an approved Fanar cell for the primary
model comparison. English can be retained as a clearly labelled conditional
or service-level sensitivity; Arabic should not be promoted. No further Fanar
generation or Luna annotation is warranted for the primary expansion unless
the estimand is explicitly changed to include provider filtering as an access-
denial outcome. Preparation, execution and design-based estimation are
implemented in `scripts/fanar_route_audit.py`.
