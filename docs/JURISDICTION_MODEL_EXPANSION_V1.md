# Jurisdiction model expansion: access-smoke protocol

This document records the first screening step for three candidate developers:
T-Tech in Russia, Ola Krutrim in India, and SpeakLeash/ACK Cyfronet in Poland.
It is an operational check, not an analysis and not a basis for estimating
refusal rates.

## Why these three

Each candidate adds a developer that is not already represented in the subject
model panel. The comparison is based on the developer's jurisdiction, not the
location of the inference provider or the languages mentioned in a model card.

The pinned models and routes are:

| Candidate | Route | Exact model value | Credential |
|---|---|---|---|
| T-pro-it-2.0 | Hugging Face proxy pinned to Featherless AI | `t-tech/T-pro-it-2.0:featherless-ai` | `HF_TOKEN` |
| Bielik 11B v3.0 | Hugging Face proxy pinned to PublicAI | `speakleash/Bielik-11B-v3.0-Instruct:publicai` | `HF_TOKEN` |
| Krutrim-2 | Krutrim native OpenAI-compatible API | copied from the model card into `KRUTRIM_MODEL_ID` | `KRUTRIM_API_KEY` |

The Hugging Face provider mappings were checked on 7 September 2026. T-pro was
live on Featherless AI; Bielik v3 was live on PublicAI. The providers are pinned
in the model string, so Hugging Face cannot silently substitute another route.

## Phase 1: Hugging Face routes

The script `scripts/jurisdiction_expansion_smoke.py` selects one prompt meaning
deterministically from the already-frozen 40-meaning expansion pilot. It then
loads that same meaning from each of the five canonical prompt files: English,
Chinese, Arabic, Russian, and Hindi. This gives five requests per model and ten
requests in total.

The provider receives the original canonical user message with no added system
message. Generation uses the study-wide settings of temperature 1.0 and a
5,000-token maximum. T-pro additionally receives
`chat_template_kwargs={"enable_thinking": false}` because it is a hybrid
reasoning model. There are no provider fallbacks and no retries in this access
smoke.

The public prices checked during preparation were:

- T-pro through Featherless: $0.408 per million input tokens and $1.972 per
  million output tokens.
- Bielik through PublicAI: $0.40 per million input tokens and $0.40 per million
  output tokens.

At 500 output tokens per response the ten requests are expected to cost about
half a cent. Reserving the full 5,000-token maximum for every response costs
about six cents. The guarded hard ceiling is therefore $0.10.

The script writes only to
`annotations/model_expansion_v4/jurisdiction_smoke_v1/hf_phase/`. It records the
frozen requests, their hash, authorization, append-only provider responses,
usage, latency, HTTP status, errors, and the final response-file hash.

### Initial transport failure

The authorized ten-request attempt on 7 September returned HTTP 403 for every
request. Both downstream providers reported Cloudflare error 1010, meaning the
HTTP client signature was denied before model inference. A free Featherless
model-metadata request reproduced the diagnosis: Python's default `urllib`
signature returned 403, while the same request with a Hugging Face client user
agent returned 200. No response text was generated, so these records say
nothing about either model's behavior or language coverage.

The repair changes only the HTTP `User-Agent`; the frozen prompts, provider
pins, model IDs and generation settings remain byte-for-byte unchanged. The
first failures remain in the append-only response ledger as attempt 1. A second
attempt cannot run until separately authorized with the same payload hash and
an additional $0.10 ceiling.

The repair was authorized and completed on 7 September. All ten corrected
requests returned HTTP 200 with non-empty text. The append-only response ledger
has SHA-256
`a218b08fe6e1020515a82d293e39c66c16eefbe880ceaa5e80f03cbd192a9879`.
No `<think>` markup appeared in any response.

Observed usage and cost, calculated from provider-reported token counts and the
frozen public rates, were:

| Model | Successful responses | Input tokens | Output tokens | Calculated cost |
|---|---:|---:|---:|---:|
| T-pro-it-2.0 | 5/5 | 371 | 10,052 | $0.019974 |
| Bielik 11B v3.0 | 5/5 | 504 | 4,156 | $0.001864 |

This establishes route viability, not model-language viability. The single
meaning exposed warning signs that must be measured in the larger pilot:

- T-pro's English response was coherent and its Chinese and Hindi responses
  were predominantly in the requested script. Its Russian response was clearly
  degraded, mixing Cyrillic, Latin, Han, Hebrew, Korean and Arabic characters;
  its Arabic response incorrectly described the clean prompt as unclear.
- Bielik's English, Arabic and Russian responses were predominantly or entirely
  in the requested script. Its Chinese response mixed substantial Latin and
  Cyrillic material, and its Hindi response mixed Devanagari with substantial
  Latin and Cyrillic text.

These observations come from one prompt and cannot support acceptance or
rejection. They justify advancing both working routes to the established
40-meaning by five-language pilot, where capability failure is measured by
model-language cell.

## Phase 2: Krutrim

Krutrim documents an OpenAI-compatible endpoint at
`https://cloud.olakrutrim.com/v1/chat/completions` and lists Krutrim-2 at ₹6.60
per million input tokens and ₹6.60 per million output tokens. Its public
documentation does not expose the exact API model value; it instructs users to
copy that value from the model card's Starter Code tab. The Krutrim phase must
therefore remain blocked until both of these are stored in `.env`:

```text
KRUTRIM_API_KEY=...
KRUTRIM_MODEL_ID=...
```

Once configured, the Krutrim request bytes and cost ceiling will be frozen and
authorized separately. This prevents a guessed model identifier from entering
the scientific record.

On 7 September, account creation was found to require an Indian telephone
number. Krutrim was therefore deferred as an access failure. No Krutrim API
request was prepared or sent, and the model must not be described as having
failed the behavioral screen.

### Sarvam-105B alternative

The user configured `SARVAM_API_KEY` after Krutrim was deferred. The current
Indian candidate is therefore Sarvam AI's native `sarvam-105b` model at
`POST https://api.sarvam.ai/v1/chat/completions`. This is the flagship chat
model; the separate `sarvam-105b-conversations` variant is intended for
real-time and voice-agent dialogue. Sarvam-105B does not add a new Indian
developer, but it replaces the deprecated Sarvam generation with a current,
supported model and route.

The access smoke uses the same one matched meaning and five languages as the
T-pro/Bielik route screen. It sets temperature to 1.0 and
`reasoning_effort=null`. Its 4,096-token maximum is an explicit provider cap:
Sarvam documents 4,096 as the Starter-plan limit, below the project's usual
5,000-token request ceiling. The public price checked on 7 September was
₹29.28 per million input tokens and ₹73.20 per million output tokens.

The resulting five-request payload is frozen at SHA-256
`37853da4ce4b5a42ae2663f36a35bf2d489f63f4e73f321ba2304e7f80b869a2`.
The planning calculation assumes 500 output tokens per response and estimates
₹0.192633. If every request consumes the full 4,096-token allowance, the
one-attempt reserve is ₹1.508769. The guarded hard ceiling is ₹2.00.

The user authorized this payload on 7 September and the smoke completed 5/5
without an API error. The response ledger has SHA-256
`c71f3ba1a76f119d921ee587e207b7e65ad9ef71fd1eab8fe73915d19c342144`.
The provider reported 270 input tokens and 3,913 output tokens, implying a
charge of approximately ₹0.294337 at the documented rates. English, Chinese,
Arabic and Hindi yielded substantive responses in the requested language. The
Russian request yielded a substantive English response, so Russian language
fidelity must be tested directly in a larger pilot rather than assumed from
route success.

## Phase 3: T-pro and Bielik 40-meaning pilot

The two working Hugging Face routes advance to the exact 40 prompt meanings
used in expansion pilot v1. Each meaning is crossed with English, Chinese,
Arabic, Russian and Hindi for each model, giving 400 requests. This selection
is enriched for diagnostic variety and is not a probability sample for
estimating refusal prevalence.

`scripts/jurisdiction_expansion_pilot.py` freezes the request matrix, verifies
the prompt and selection hashes, calculates the maximum possible token charge,
and requires a separate hash- and ceiling-bound authorization. It preserves
the canonical temperature of 1.0 and 5,000-token maximum, disables T-pro's
thinking mode, pins the two provider routes, disables fallbacks, and permits
one attempt per request. Execution is resumable and uses no more than eight
concurrent requests.

The frozen pilot has SHA-256
`7e3b4c4d84a7fb84185551eb1d1128343d6acc7f0e0bb138ed53508dd01a487f`.
The fixed planning calculation uses 1,500 output tokens per response and gives
an expected provider charge of $0.725313: $0.598525 for T-pro and $0.126789 for
Bielik. The one-attempt maximum, if all 400 responses consume the complete
5,000-token allowance, is $2.385713. The guarded hard ceiling is $3.00.

The user authorized the payload on 7 September. The first pass produced 197
responses and 203 transient provider errors. Bielik returned all 40 English,
Chinese, Arabic and Russian responses and 37/40 Hindi responses; its three
Hindi losses were HTTP 504 gateway timeouts. T-pro returned no responses:
Featherless reported 190 HTTP 429 per-user concurrency-limit errors and ten
HTTP 503 temporary-capacity errors. These are route failures, not model
outcomes, and must not enter refusal or capability-failure denominators. The
complete first-pass ledger has SHA-256
`6fc8efa71e59b77597636477b4625da09ed6c3cf31b00360dffb58c5a8944539`.

`scripts/jurisdiction_expansion_pilot_repair.py` freezes only those 203
transient failures. It reuses the original messages, model identifiers,
temperature, token ceiling, provider pins and fallback restrictions, allows
one additional attempt, and runs sequentially to respect Featherless's
five-request/ten-unit concurrency constraint. Its payload SHA-256 is
`3dc83b0a8bb8bebab1850066a50878e1faa16496145d7a4bc797290424eefcc4`.
The planning cost is $0.600472, the full-token reserve is $1.985072 and the
guarded ceiling is $2.25. The user authorized the repair on 7 September. It
recovered all three Bielik responses and 191/200 T-pro responses. Nine T-pro
records remain unresolved: seven HTTP 503 temporary-capacity errors and two
HTTP 200 responses with empty message content. The repair ledger has SHA-256
`9b701900158667b86d395afc8c99f9f6341e346d027a788653b2d1f0bd147f21`;
the combined latest-record ledger has SHA-256
`c3af3379f7450bac6bb87b6ebcbb4b11043edb8eaf57c16f71a37ad964adeea2`
and contains 391 usable responses. Reported token usage implies approximately
$0.633154 for successful repair responses. The nine unresolved records remain
explicit missing/technical outcomes and were not silently retried again.

## Phase 4: Sarvam-105B 40-meaning pilot

`scripts/sarvam_105b_pilot.py` applies the same 40 meanings and five languages
to the native Sarvam route, giving 200 requests. It keeps temperature 1.0,
disables reasoning, uses the provider-specific 4,096-token ceiling, permits
one attempt, and allows at most five concurrent requests. The payload is
frozen at SHA-256
`23b6f81c2d5cc31255fcc7e588c2b0727b58a2cdefd75d04d569849239eabcef`.
At the prices checked on 7 September, the 1,500-output-token planning estimate
is ₹22.456940 and the full-token reserve is ₹60.462380. The guarded ceiling
is ₹65.00.

The user authorized this payload on 7 September. All 200 requests succeeded;
the response ledger has SHA-256
`bb43c877a12702f4792f6f0540c517158a1b1de62641d5aeab8fc3b8df2b4eb1`.
The provider reported 12,271 input tokens and 170,139 output tokens, implying a
charge of approximately ₹12.813470. A deterministic Unicode-script screen
found the expected script dominant in 40/40 English, 39/40 Chinese, 40/40
Arabic, 37/40 Russian and 40/40 Hindi responses. This is only a diagnostic:
the unchanged v2.4 annotation and targeted language-fidelity audit must decide
whether the four flagged responses are wrong-language or contain legitimate
mixed-script material.

## Phase 5: uniform Luna v2.4 pilot annotation

`scripts/jurisdiction_pilot_annotation.py` assembles the latest successful,
non-empty response for each pilot key. This gives 591 annotation records: 191
T-pro, 200 Bielik and 200 Sarvam. The nine unresolved T-pro generation
outcomes remain explicit technical outcomes in the generation denominator and
are not converted into text annotations.

The annotation messages contain only the English reference prompt, the
source-language prompt, the source-language response and the requested
language. Subject-model identity, provider, pilot band and selection metadata
remain outside the messages. The stage reconstructs and verifies the adopted
v2.4 system prompt and structured-output schema byte-for-byte, then pins Luna
to the OpenAI provider with temperature 0, a 500-token maximum, reasoning
disabled, fallbacks disabled and at most three schema attempts.

The frozen 591-request provider payload has SHA-256
`c5a96ac2df4994ec1be856577d33748b6e33c937b72f90d1ef094daa59a86186`.
At the existing Luna prices, the planning estimate is $0.444473, the
single-attempt full-output reserve is $0.657233 and the empirically calibrated
hard ceiling is $0.75. The user authorized the run on 7 September. Luna
returned 591/591 schema-valid annotations at a provider-reported cost of
$0.265026. The attempts and result ledgers have SHA-256
`798c522c06c8cda7a8d3f84f75e86e9857f1b60f32444b433387f74fb9b4fff1`
and `409b5de6f619fd4439f15665410b015673e38796db53dc49a1d5e9938c21f76b`,
respectively.

The Luna screen suggests sharply concentrated capability problems: 59.0% of
Bielik responses and 58.1% of T-pro responses were classified as capability
failures, compared with 9.5% for Sarvam. The worst cells were Bielik Hindi
(40/40), Bielik Chinese (37/40), T-pro Hindi (37/39) and T-pro Russian (39/39).
These are enriched-pilot proportions, not population estimates. They are also
single-judge results: the prespecified Sol audit must verify refusal,
wrong-language and capability classifications before any cell decision.

## Phase 6: targeted Sol v2.4 audit

`scripts/jurisdiction_pilot_sol_audit.py` freezes a frontier-model audit using
messages and schema identical to Luna's. The design includes all 279 responses
that Luna classified as a genuine refusal, capability failure or wrong-language
response. It then selects up to ten apparently clean controls independently in
each subject-model by language cell. Within each cell, clean records are ranked
by SHA-256 of a frozen seed and response ID, giving 113 additional records and
392 requests in total. The file retains each record's inclusion probability
and inverse-probability weight so aggregate Luna–Sol agreement can be estimated
for all 591 responses rather than only for the enriched audit sample.

The frozen Sol payload has SHA-256
`01511aa67eb049f1514dfb70f0329f75e36ecf65c547cd638b7a1b7de98eb9bf`.
It pins `openai/gpt-5.6-sol` to the OpenAI provider, uses the unchanged v2.4
source-response-only messages and structured schema, temperature 0, a
500-token maximum, reasoning disabled, fallbacks disabled and at most three
schema attempts. The planning estimate is $2.804070, the single-attempt reserve
is $3.980070 and the hard ceiling is $5.00. The user authorized the run on 7
September. Sol returned
392/392 schema-valid annotations at a provider-reported cost of $1.736498. The
attempts and result ledgers have SHA-256
`edce545a272126cc971afb74920f2eb1a616481b1739f777609dff75010a7918`
and `d410173e96bb3490c18f08354b27ff61922413d0eb135ce9e57ba57be6d1aca8`,
respectively.

Using the stored inverse-probability weights to reconstruct the 591-response
pilot, Luna agreed with Sol on genuine refusal in 98.1% of cases (weighted
κ=0.856; sensitivity 81.5%, specificity 99.5%) and on capability failure in
93.3% (κ=0.861; sensitivity 94.2%, specificity 92.7%). Wrong-language
classification was less reliable: agreement was 89.5%, but Luna's precision
against Sol was only 24.1% because Luna classified 13.4% as wrong-language and
Sol classified 3.6%. Cell-level decisions should therefore use Sol's language
assessment and treat Luna's wrong-language field as a high-recall screen.

Sol confirms the broad capability pattern. Its design-weighted capability
rates are 100% for Bielik Hindi, 97.5% for Bielik Chinese, 100% for T-pro
Russian and 79.5% for T-pro Hindi. Sarvam is much cleaner: zero estimated
capability failures in English, Arabic and Hindi, 5% in Chinese and 15% in
Russian. These remain enriched-pilot diagnostics rather than prevalence
estimates from the full prompt population.

## Phase 7: frozen full-corpus generation contracts

`scripts/jurisdiction_expansion_full.py` creates an independent full-run
contract for each model. Every contract crosses all 2,496 canonical prompt
meanings with English, Chinese, Arabic, Russian and Hindi, giving 12,480
requests per model. Prompts, temperature and token ceilings are unchanged from
the pilots. Each route permits at most two attempts, and only HTTP 429/5xx or
transport failures may receive the second attempt. Empty HTTP-200 responses
remain technical outcomes rather than being silently treated as model text.
The executor appends every attempt, reconstructs the latest terminal state on
resume, and stops scheduling before the authorized cost ceiling.

The route-specific contracts are:

| Model | Payload SHA-256 | Safe workers | Pilot-mean cost | Runtime | Hard ceiling |
|---|---|---:|---:|---:|---:|
| T-pro-it-2.0 | `a515ff1968f21d13e2ad7b4422746487b9f4256aa42f41da01db82513cecda23` | 4 | $41.230930 | 27.4 h | $65.00 |
| Bielik 11B v3.0 | `e3b1174af4a318486251b97ff1ca49630c7b0d6091b2091956bbe6510acfd50d` | 8 | $4.751261 | 6.3 h | $8.00 |
| Sarvam-105B | `2abcde71bbf051a856d0a27b2e53df377bd4e00ce3bd21efc51e7efc4600b1ac` | 5 | ₹799.560508 | 4.3 h | ₹1,250.00 |

Costs and runtimes are projections from the completed 191-response T-pro and
200-response Bielik/Sarvam pilots, not provider guarantees. The ceilings add a
substantial margin over the pilot means but remain below the theoretical cost
if every response consumes its entire output allowance. This is deliberate:
the executor stops safely if empirical output length shifts enough to exhaust
a ceiling, at which point continuation requires a new recorded authorization.
The user authorized all three payloads on 7 September, and the three independent
resumable runs were started that day. Until completion, their manifests and
append-only attempt ledgers are the authoritative progress record; counts are
not copied into this narrative because they change while the jobs are live.

On 8 September, the T-pro executor was paused and its scheduler was improved
without changing the scientific or provider contract. The original executor
submitted requests in waves of four and waited for the slowest member of each
wave before scheduling more work. The revised executor holds one persistent
four-worker pool and replaces each completed request immediately. It still
permits no more than four T-pro requests in flight, reserves the maximum possible
charge for every in-flight request before submitting another, uses the same
two-attempt transient-failure rule, and resumes from the existing append-only
ledger. `tests/test_jurisdiction_expansion_full.py` verifies the concurrency
bound. Prompts, generation settings, payload hash and authorized ceiling are
unchanged.

A second, optional concurrency amendment was frozen later on 8 September after
the continuous four-worker runner showed additional provider headroom. Protocol
SHA-256 `94c79f63f67df42a13f3df576dab5bc5895d9c424445547f08d0e56200a2f426`
authorizes a 30-minute trial with at most eight requests in flight. The runner
stops scheduling automatically after 30 minutes and drains calls already in
flight. The trial is retained only if HTTP 503 errors remain at or below 10%,
all errors remain at or below 15%, and throughput improves by at least 40%
relative to four workers; otherwise it returns to four. The $65 ceiling and all
scientific and provider settings remain unchanged.

The user authorized the amendment, but the trial failed immediately for a
clear provider-side reason. Featherless returned HTTP 429 with the message that
the account permits 10 active units and each T-pro request consumes two units.
Eight concurrent requests therefore cannot run on this route. The stopped trial
logged 808 attempts: 14 succeeded and 794 were rejected with HTTP 429. Each
rejected key used only its first attempt, so no key exhausted the two-attempt
allowance and rejected calls incurred no recorded token charge. The executor
was returned to four workers; its first six affected retries all succeeded with
HTTP 200. The effective concurrency cap is again four. A future five-worker
test would require a new amendment rather than relying on the failed one.

That narrower test was subsequently prepared as concurrency amendment v2,
SHA-256 `293a7e2c6f48ce23ca3e7d66250545502ef667d621203f4ed80cef799c05b69f`.
It permits a 30-minute trial at five workers, the maximum implied by the
provider's stated active-unit accounting. Unlike the first trial, the runner
halts new submissions immediately if it observes even one HTTP 429 and then
drains calls already in flight. Retention requires no 429s, no more than 15%
total errors and at least 15% higher throughput than the four-worker baseline.
The payload and $65 ceiling remain unchanged. This amendment is frozen but not
authorized, and preparing it made no provider call. The user subsequently
authorized the exact amendment. Featherless accepted five concurrent calls and
returned no HTTP 429s, but the first 10 completed attempts contained one success
and nine malformed HTTP-200 JSON envelopes. This 90% technical-error rate failed
the predeclared 15% ceiling, so the trial was stopped early and the effective
cap returned to four. The executor now preserves up to 100,000 characters of a
malformed HTTP-200 envelope in its internal attempt record so future failures
can be diagnosed without another request. This logging change does not alter
the payload or generation settings.

## Phase 8: full-corpus Luna annotation

Full-corpus responses are annotated model by model, and only after the relevant
generation ledger is complete. This avoids freezing a moving partial sample and
means each annotation payload can be tied to the hashes of the exact generation
manifest, request ledger, attempt ledger and successful-response ledger. The
script `scripts/jurisdiction_full_annotation.py` applies the unchanged Luna
v2.4 codebook. Luna sees the English reference prompt, the prompt in its tested
language and the response, but receives no repository field identifying the
subject model or provider. No translation is used. Successful non-empty model
responses are annotation inputs; generation failures remain separate technical
outcomes in the 12,480-record model denominator.

Sarvam-105B completed first. Its generation ledger contains 12,478 successful
responses and two terminal technical failures. The frozen annotation payload
therefore contains 12,478 requests and has SHA-256
`dec6a32dbcf50b755e73fe7d96943ddc3193289441d7ee293b01cf8e838a23e4`.
At the pinned Luna prices of $0.20 per million input tokens and $1.20 per million
output tokens, the planning estimate is $9.454249. The conservative hard ceiling
is $14.25. Freezing and costing this payload made no provider call. The user
authorized that exact hash and ceiling on 8 September 2026, after which the
resumable annotation runner was started with 32 concurrent workers. It
completed all 12,478 response labels with 100% schema success for $5.649245.
The assembled label table has SHA-256
`0fd2f2502de6e50a6d4b88b0bf2a6a39eaeb7a6509331ed4375cd9a2ada54a84`;
it contains 603 Luna-coded genuine refusals and 1,276 Luna-coded capability
failures. These are unadjusted counts, not yet the paper's estimands.

Bielik completed with 12,184 successful responses and 296 technical generation
failures, at an actual generation cost of $4.772896. Its Luna payload contains
those 12,184 response-bearing records and has SHA-256
`2221c6fa24d35896282173441d54ed57934dc91e6c9e441dd64b2c129dac78b7`.
The planning estimate was $7.983942 and the authorized hard ceiling is $12.00.
The user authorized that exact contract on 8 September and the annotation run
was started with 32 workers. Before any provider request, the existing JSONL
reader exposed a Unicode handling defect: `str.splitlines()` treated an embedded
U+2028 paragraph separator in a valid response as a new record. The reader now
iterates over physical LF-delimited records, a regression test covers U+2028 and
U+2029, and the unchanged authorized payload then began successfully.

The run subsequently completed with 12,179 schema-valid labels and five
schema-exhausted responses (99.959% success), at $3.903067. The immutable
`results.jsonl` has SHA-256
`15f422eba00dec43b3bcad7c854b5af35b5e7cf3b33ac5ea3f501aef83772ac3`.
Among the valid labels, Luna identified 64 genuine refusals and 7,129
capability failures. The five missing annotations and 296 generation failures
remain missing; neither group is imputed as engagement, refusal, or behavioral
capability failure.

T-pro should be frozen for annotation when its longer generation run completes.
This sequencing changes only when annotation begins, not the codebook, prompt,
schema or downstream outcome definitions, so results remain comparable across
subject models.

## Decision after the smoke test

A successful route is not enough for inclusion. Any candidate that returns all
five records proceeds to the existing 40-meaning by five-language pilot. That
pilot will be annotated using the unchanged Luna v2.4 codebook, with targeted
Sol review of language or capability disagreements. Model-language cells will
be approved individually; this smoke test will never be used to estimate an
outcome prevalence.
