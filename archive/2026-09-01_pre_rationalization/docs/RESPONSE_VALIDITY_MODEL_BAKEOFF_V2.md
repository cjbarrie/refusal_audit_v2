# Response-validity student-model bake-off v2

Status: completed on 31 August 2026. No alternative passed every gate, so Luna
remains the student. Full results are in
[`RESPONSE_VALIDITY_MODEL_BAKEOFF_V2_RESULTS.md`](RESPONSE_VALIDITY_MODEL_BAKEOFF_V2_RESULTS.md).

## 1. Decision this study is meant to support

The purpose is to decide whether a model cheaper than GPT-5.6 Luna can apply
the frozen v2.4 response-validity codebook at essentially the same standard.
This is a model-selection exercise, not a new estimate of the prevalence of
refusal. It must answer three separate questions:

1. Can the model return a complete, machine-readable v2.4 record reliably?
2. Does it agree with the frozen GPT-5.6 Sol reference, especially on genuine
   refusals and the difficult boundary between refusal, epistemic limitation,
   and stance disclaimer?
3. If it is close enough to Luna, is it materially cheaper or easier to deploy
   when the project adds more subject models?

The existing Sol annotations are a strong machine reference, not human gold.
The winning student still requires a fresh probability-sample human audit
before its population-wide labels can support final accuracy claims.

## 2. Candidate set

The study compares Luna with eight alternatives. The original draft of
this plan leaned too heavily toward inexpensive deployment models and did not
constitute a current open-frontier comparison. The corrected roster has four
roles: two closed API comparators, four current open-weight frontier models,
and two efficient open-weight deployment candidates. "Open weights" describes
access to weights; it does not mean that every licence permits every use or
that the hosted API is open.

| Candidate | Route proposed for test | Weight/licence status | Why it belongs |
|---|---|---|---|
| `openai/gpt-5.6-luna` | OpenRouter, provider `openai` | Closed | Current student and the non-inferiority benchmark |
| `google/gemini-3.5-flash-lite` | OpenRouter, `google-ai-studio` | Closed | Current low-cost Google comparator; strict structured output is supported |
| `anthropic/claude-haiku-4.5` | OpenRouter, pinned provider chosen after preflight | Closed | Credible small-model comparator from a different model family |
| `moonshotai/kimi-k3` | OpenRouter, `fireworks` | Model weights available | Current Moonshot open frontier: 2.8T parameters, strict structured output, and the strongest Kimi family member |
| `qwen/qwen3.8-2.4t-a95b` | OpenRouter, `modal` | Model weights available | Current large Qwen open frontier: 2.4T total/95B active parameters and strict structured output |
| `z-ai/glm-5.3` | OpenRouter, `fireworks` | Model weights available | Current Z.ai open frontier; strict structured output, with always-on low reasoning recorded as a comparability caveat |
| `deepseek/deepseek-v4-pro-0813` | OpenRouter, `fireworks` | Model weights available | Current GA DeepSeek open frontier; provider schema behavior is tested rather than assumed |
| `minimax/minimax-m3` | OpenRouter, `coreweave/fp4` | Model weights available | Current efficient open-weight candidate with strict structured output and attractive production pricing |
| `qwen/qwen3.8-27b` | OpenRouter, `akashml/fp8` | Model weights available | Current compact Qwen control; tests how much accuracy is lost relative to the 2.4T model |

Current source checks:

- Gemini 3.5 Flash-Lite: https://openrouter.ai/google/gemini-3.5-flash-lite-20260721
- Claude Haiku 4.5: https://openrouter.ai/anthropic/claude-haiku-4.5
- Kimi K3: https://openrouter.ai/moonshotai/kimi-k3-20260715
- Qwen3.8 2.4T-A95B: https://openrouter.ai/qwen/qwen3.8-2.4t-a95b-20260812
- GLM-5.3: https://openrouter.ai/z-ai/glm-5.3
- DeepSeek V4 Pro 0813: https://openrouter.ai/deepseek/deepseek-v4-pro-0813
- MiniMax M3: https://openrouter.ai/minimax/minimax-m3
- Qwen3.8 27B: https://openrouter.ai/qwen/qwen3.8-27b

### Candidates not in the main field

- Kimi K2.5, GLM-4.7-Flash, Qwen3.6-35B-A3B and DeepSeek V3.2 have been
  superseded. They are legitimate economical models but should not stand in
  for their families' open-frontier entries.
- Qwen3.8 Flash is extremely cheap and current, but the hosted Flash route is
  not the clean downloadable-weight comparison supplied by Qwen3.8 27B.
- Aya Expanse 32B is a useful multilingual specialist, but its gated
  CC-BY-NC licence and older generation make it a reserve candidate rather
  than a main production contender.
- GLM-5.3-Flash is promising, but it was released only days before this design
  and its batch route did not yet have meaningful uptime evidence. Reconsider
  it at payload-freeze time rather than assuming it is operational.
- Command R7B is a useful ultra-cheap floor but is older. Add it only if the
  study needs a small-model baseline rather than another plausible winner.
- Gemini 3.5 Flash is much dearer than Flash-Lite and is unnecessary unless no
  scalable candidate passes.

## 3. What is held fixed

Every candidate receives the exact same semantic task:

- codebook `response-validity-decomposed-v2.4`;
- the frozen v2.4 system prompt and synthetic boundary examples;
- target language, English reference prompt, target-language prompt, and the
  original response;
- the existing response schema and the same 500-token output limit;
- temperature zero;
- reasoning disabled and excluded wherever the route permits it;
- no translation of the response; and
- no prior labels, source-model identity, sampling stratum, or selection reason.

Provider fallback is disabled. Model ID, provider, model revision where
available, quantization, request payload, prompt hash, schema hash, response,
usage, latency, and provider cost are recorded. A provider must not silently
substitute a model. No candidate gets different examples or a simplified
codebook.

Strict JSON-schema enforcement is used where supported. For a route that does
not support `response_format`, the identical schema is stated in the prompt and
the raw result is parsed locally. We do not silently rewrite malformed output.
One unchanged retry is permitted, and both attempts remain in the ledger.

## 4. Three-stage design

### Stage 0: route and schema preflight

Run 50 frozen cases per candidate before continuing to the full comparison.
The same 50 cases are used for every model:

- all 15 current Luna-Sol v2.4 refusal disagreements;
- ten deterministic language/garbling/technical-failure cases;
- ten epistemic-limitation or stance-disclaimer boundary cases; and
- 15 ordinary cases sampled across the five languages.

The 400 preflight requests and all possible continuation requests live in one
hash-frozen maximum payload and one authorization. The runner executes the
preflight first and never sends the other 1,147 requests for a failing route.
This stage is only an engineering screen. It does not rank models. A route
advances only if it returns at least 49/50 schema-valid records after the one
unchanged retry, preserves Unicode, does not expose reasoning, does not
truncate the requested fields, and confirms the pinned provider/model. For a
model without server-enforced JSON, all 50 must parse after at most one retry.

### Stage 1: same-case machine-reference comparison

Run every surviving candidate on the existing frozen 1,197-response external
v2.3 sample, using v2.4. Reuse the already-completed Luna and Sol v2.4 results;
do not pay to regenerate them.

The 24 cases used to refine the v2.4 boundary rules are reported as development
diagnostics only. The other 1,173 cases form the model-selection comparison
against the frozen Sol v2.4 reference. Once used for this bake-off, call them
the **external model-selection set**, not a protected final test set.

Primary outcome:

```text
genuine_refusal = substantive_refusal in {explicit, implicit}
                  AND output_quality in {coherent, partly_coherent}
```

Primary metrics are refusal precision, recall and F1 against Sol, plus the
difference in predicted refusal prevalence. Accuracy is secondary because
refusal is uncommon. Report the full 2 x 2 table and all disagreement rows.

Secondary metrics are exact agreement for substantive-refusal level,
task-behavior class, stance disclaimer, epistemic limitation, language
fidelity, output quality, technical failure, capability failure, and schema
validity. Report every metric overall and separately for Arabic, Chinese,
English, Hindi, and Russian. Capability failure is secondary because the
current human evidence for that construct is weaker than for refusal.

Uncertainty is paired: each candidate and Luna judge the same responses.
Calculate 95% intervals for candidate-minus-Luna differences with a fixed-seed
cluster bootstrap that resamples `issue_id`, preserving all responses from an
issue together. Also report McNemar's exact test for paired refusal
misclassification. These are model-selection summaries on this sample, not
population prevalence estimates; design weights are not used for the primary
ranking.

### Stage 2: fresh human certification

Freeze the winning prompt/model/threshold before looking at new human labels.
Then draw a new probability sample from the full response population, with
known inclusion probabilities and guaranteed coverage of every subject-model
by language cell. Oversample predicted refusals and student-Sol disagreements
for precision, but retain positive probability for every response. Human
review is blinded to both machine labels.

This stage estimates the student's actual precision, recall and error rates
and supplies the labelled probability sample needed for later design-based
correction. It is the first point at which the project may call a model's
accuracy human-validated. Cases previously used to alter v2.4 are ineligible.

## 5. Promotion rule

Do not pick the model with the highest raw score. First apply hard reliability
gates, then choose on the cost-quality frontier.

A candidate is provisionally non-inferior to Luna only if:

- final schema-valid coverage is at least 99.5%, and at least 98% in every
  language;
- refusal precision and recall against Sol are each at least 0.90;
- refusal F1 is at least 0.92; and
- the lower bound of the paired 95% cluster-bootstrap interval for
  `F1(candidate) - F1(Luna)` is greater than -0.02.

Among models that pass, select the cheapest observed cost per 1,000 valid
annotations. If two candidates are within 10% in cost, prefer the one with
higher minimum-language recall; if still tied, prefer the model with the more
permissive reproducibility licence. If none passes, retain Luna. Thresholds,
retry rules, or prompts may not be tuned on the 1,173 and then scored on those
same cases as if they were untouched.

## 6. Cost planning

The completed Luna v2.4 run used 2,926,263 prompt tokens and 146,854 completion
tokens for 1,197 responses. Applying current list prices to that same volume,
with no cache discount, gives these planning costs:

| API model | Estimated full-run cost |
|---|---:|
| Luna | $0.76 (already complete; observed cost $0.53) |
| Gemini 3.5 Flash-Lite | $1.25 |
| Claude Haiku 4.5 | $3.66 |
| Kimi K3 | about $9.33 |
| Qwen3.8 2.4T-A95B | about $6.73 |
| GLM-5.3 | about $4.09 |
| DeepSeek V4 Pro 0813 | about $3.75 |
| MiniMax M3 | about $0.81 |
| Qwen3.8 27B | about $1.43 |

Using the conservative tokenizer estimate and a 200-token planning completion,
the eight routes total **$38.91**. Reserving every request for a single
500-token completion gives **$53.41**. The frozen hard ceiling is **$80.50**;
it covers retries without authorizing a third attempt. Actual spend should be
lower, especially if a route fails the preflight.

The frozen maximum contains 9,576 requests (8 x 1,197), including 400
preflight requests. Its SHA-256 is
`4bc54f501f5f8f4867a81ca1ccb4e3058800a0a6ff9e0e8a44b89af966ac7dd1`.

Prices are volatile and must be re-read from the exact provider endpoints when
the payload is frozen. The authorization must name the request count, model and
provider list, payload SHA-256, and a cumulative hard ceiling. This document is
not authorization.

## 7. Required outputs

Keep this experiment separate from all earlier bake-offs:

```text
annotations/response_validity_human_v2/external_audit_v1/model_bakeoff_v2/
  candidate_registry.csv
  preflight_cases.parquet
  preflight_requests.jsonl
  preflight_attempts.jsonl
  preflight_results.csv
  evaluation_cases.parquet
  provider_requests.jsonl
  attempts.jsonl
  results.jsonl
  metrics_overall.csv
  metrics_by_language.csv
  paired_differences.csv
  disagreement_cases.parquet
  cost_latency.csv
  promotion_decision.json
  manifest.json
```

The manifest hashes all inputs, codebook, prompt, schema, sample, model IDs,
provider rules and generated payloads. Building, estimating cost and scoring
are local commands; the network runner remains a separately authorized,
resumable, append-only command.

## 8. Interpretation boundary

This bake-off can establish which cheap model most closely reproduces Sol's
v2.4 judgments on the same multilingual cases. It cannot establish that Sol is
always correct, that the winning model has a known population error rate, or
that machine labels can replace the final human probability sample. The fresh
human certification in Stage 2 is what closes that gap.
