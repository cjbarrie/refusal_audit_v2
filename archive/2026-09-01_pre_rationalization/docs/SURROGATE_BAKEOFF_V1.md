# Human-referenced surrogate bake-off v1

## Status

Stage A was authorized and completed on 2026-08-21. All 420 frozen requests
were successfully labeled by `openai/gpt-5.6-luna` through OpenRouter on the
first attempt, with no schema failures or retries. Actual provider cost was
$0.36666348 under the $2.00 hard ceiling. This remains a pilot configuration
comparison; it cannot select a final population surrogate until the systematic
disagreements are adjudicated and rare-class enrichment expands the evaluation
evidence. Full results are in
[`SURROGATE_BAKEOFF_STAGE_A_RESULTS.md`](SURROGATE_BAKEOFF_STAGE_A_RESULTS.md).

## Current human reference

All 300 original pilot responses have complete coder-confirmed language
fidelity:

- target: 283;
- mixed: 2;
- wrong language: 15.

The current row-level input is
`annotations/response_validity_human_v2/base_freeze_v3_complete_language_review/`.
Its canonical label SHA-256 is
`e674ca04e5623e23bb18ff60e3c761c8dabd6817724a3ca64fe4c05ad74019ff`.
The original submissions and the v1/v2 freezes remain unchanged.

## Frozen split

Split unit is `prompt_id`, preventing translations, languages, or model
responses belonging to the same prompt from crossing arms.

| Primary class | Development | Locked evaluation |
|---|---:|---:|
| Coherent answer | 157 | 51 |
| Genuine refusal | 9 | 5 |
| Coherent pivot | 4 | 3 |
| Incoherent/garbled | 32 | 16 |
| Wrong language | 10 | 5 |
| Technical degeneration | 2 | 2 |
| Ambiguous | 2 | 2 |
| **Total** | **216** | **84** |

The evaluation set contains all five languages and all eleven response models.
There are zero shared prompt IDs across arms. Evaluation labels cannot enter
prompts, exemplar selection, or configuration editing.

This test is adequate for early error discovery and prompt comparison but is
too sparse for final class-specific reliability claims. In particular, two
technical and two ambiguous evaluation cases cannot establish stable
precision/recall.

## Configurations

Five model-neutral configurations produce the same structured schema:

1. `zero_shot_joint_v1`: codebook only.
2. `fewshot_joint_7_v1`: one verified development example per class.
3. `fewshot_joint_14_v1`: two per class.
4. `fewshot_decomposed_14_v1`: the same 14 examples, but language validity,
   coherence, and technical status must be decided before semantic behavior and
   the primary class.
5. `fewshot_error_targeted_22_v1`: additional refusal, pivot, incoherence, and
   wrong-language boundaries, while retaining both available development cases
   for technical and ambiguous output.

Every configuration records system-prompt and exemplar-ID hashes. Full model
responses are included in the v1 examples so the first experiment directly
measures the reliability-versus-context-cost tradeoff. A later compact-example
configuration may be added as a new version; it must not mutate these prompts.

The model-neutral logical payload contains 420 requests—84 evaluation rows × 5
configurations—with SHA-256
`42eb65c4da98631a00f4479a5810ff8b4da044105845631679e021d9e03caafb`.

## Scoring

Configuration and model comparisons must report:

- primary-class macro F1;
- per-class precision, recall, and F1;
- genuine-refusal precision and recall;
- refusal–pivot confusion;
- language-fidelity accuracy and wrong-language recall;
- capability-failure performance;
- schema/parse success;
- results by prompt language and source model where support permits;
- observed tokens, provider cost, and latency.

Overall accuracy is never sufficient because coherent answers dominate the
sample. Evaluation rows remain unweighted for this prompt-development bake-off;
population inference continues to use the known-probability human reference and
DSL, not this deliberately class-aware holdout.

## Cost gate

Prices were checked on 2026-08-21 against the OpenRouter model pages. The
conservative estimates use listed prices and assume no prompt-cache discount:

| Model | Input / 1M | Output / 1M |
|---|---:|---:|
| `openai/gpt-5.6-luna` | $0.10 | $0.60 |
| `google/gemini-3.5-flash-lite` | $0.30 | $2.50 |
| `anthropic/claude-haiku-4.5` | $1.00 | $5.00 |

Recommended sequential experiment:

1. Run all five configurations on GPT-5.6 Luna: 420 calls, approximately
   7.60 million input tokens plus 92,400 planning output tokens across the
   configuration sweep, with a conservative listed-price estimate of **$0.82**.
   A **$2.00 hard ceiling** provides retry and token-estimation contingency.
2. Score the configuration sweep before spending on another model.
3. Run only the winning one or two configurations on Gemini Flash Lite and
   Claude Haiku. One configuration across both models ranges from approximately
   $0.29 for zero-shot to $3.91 for the 22-example prompt at listed prices.

Running all five configurations on all three models would cost approximately
$11.39 before contingency and is not recommended as the first experiment.
Prompt caching may reduce actual cost, but it is excluded from authorization
planning.

Price sources: [GPT-5.6 Luna](https://openrouter.ai/openai/gpt-5.6-luna-20260709),
[Gemini 3.5 Flash Lite](https://openrouter.ai/google/gemini-3.5-flash-lite-20260721),
and [Claude Haiku 4.5](https://openrouter.ai/anthropic/claude-haiku-4.5/pricing).

## Reproduction

```bash
python scripts/response_validity.py freeze-complete-language-review
python scripts/response_validity.py build-surrogate-bakeoff
python scripts/response_validity.py estimate-surrogate-bakeoff-cost
```

The exact authorization was recorded before execution. The completed paid run
and scoring interfaces are:

```bash
python scripts/response_validity.py authorize-surrogate-bakeoff \
  --payload-sha256 42eb65c4da98631a00f4479a5810ff8b4da044105845631679e021d9e03caafb \
  --model openai/gpt-5.6-luna --ceiling 2.00
python scripts/response_validity.py run-surrogate-bakeoff-stage-a \
  --authorized --ceiling 2.00
python scripts/response_validity.py score-surrogate-bakeoff \
  --results annotations/response_validity_human_v2/surrogate_bakeoff_v1/stage_a_luna_results.jsonl
```

The first three build/estimate commands and the scoring command are local. The
authorization command records an already granted authorization; it does not
make a network call. The run command makes paid calls and must never be rerun
for another payload, model, call count, or ceiling without a new explicit
authorization. It is resumable and returns immediately when all frozen request
IDs are already complete.
