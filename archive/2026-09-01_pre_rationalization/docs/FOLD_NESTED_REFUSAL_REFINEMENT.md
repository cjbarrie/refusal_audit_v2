# Fold-nested implicit-refusal refinement v2

Status: frozen locally on 2026-08-26; unpaid and unauthorized.

This experiment is the narrow follow-up to the completed 700-label scalable
bake-off. It tests whether error-targeted examples can recover implicit and
partial refusals without sacrificing precision or capability-failure accuracy.
It is internal validation, not an external certification exercise.

## Why this experiment exists

No candidate in the first all-700 bake-off reached the frozen 0.80
genuine-refusal recall gate. The strongest hard-label candidate, GPT-5.6 Luna
zero-shot with original text plus English translation, reached precision 0.887
and recall 0.746. Eleven of its sixteen missed refusals were implicit. Fifteen
generic balanced examples tended to raise precision while lowering recall.

The new design therefore changes one thing at a time:

- retain GPT-5.6 Luna through the pinned OpenAI provider route;
- retain only source-containing input modes;
- replace generic examples with error-targeted boundary examples; and
- freeze fold-specific probability thresholds before the new provider run.

The previous zero-shot results remain the baseline and are not redundantly
queried again.

## Frozen design

The experiment uses the same 700 human labels and five whole-`issue_id` folds
as the first bake-off. For each held-out fold, the example bank is selected
only from the other four folds. Each bank contains fifteen responses:

- one hard human refusal in each of five languages;
- one high-scoring coherent non-refusal in each language; and
- one low-scoring human capability failure in each language.

Implicit refusals are selected before explicit refusals, then the lowest prior
refusal probability identifies the hardest available case. Twenty-three of the
twenty-five fold-specific refusal placements are implicit refusals. The other
two use the hardest available explicit refusal because that language's sole
implicit case lies in the held-out fold. The boundary non-refusal and
capability-failure examples are selected from prior out-of-fold errors. No
example shares an issue with its evaluation fold.

Each of the 700 responses is queried under two conditions:

1. original response only;
2. original response plus literal English translation.

This yields 1,400 provider requests. Translation-only input is excluded because
it cannot assess source-language fidelity and performed poorly as a capability
measure. Provider fallbacks are disabled and reasoning output is excluded.

## Threshold nesting

Threshold selection is also isolated from the held-out fold. For evaluation
fold `f` and input mode `m`:

1. read only the completed v1 Luna zero-shot probabilities and human labels
   from the other four folds;
2. evaluate every unique training probability, plus zero and one;
3. among thresholds reaching precision 0.75 and recall 0.80, maximize F1, then
   precision, then choose the higher threshold;
4. if none reaches both gates, preserve recall of at least 0.80 and maximize
   precision, then F1, then choose the higher threshold; and
5. freeze that threshold before any v2 output exists and apply it unchanged to
   the v2 probabilities in fold `f`.

This transfers a threshold from the previous zero-shot prompt to the refined
prompt. That may be conservative if the new prompt changes calibration, but it
does not reuse the held-out outcome. Tuning a threshold from new predictions on
the other folds would require an additional inner cross-fitting layer because
those prompts could otherwise contain examples from the eventual held-out
fold. The present transfer avoids that leakage and avoids 5,600 additional
provider calls.

Three of the ten training-fold threshold cells cannot meet both historical
precision and recall gates. Their frozen fallbacks meet the recall target and
record the precision shortfall. Final promotion still depends only on the
concatenated untouched v2 predictions.

## Promotion rule

For each input mode, the scorer concatenates the five held-out predictions and
applies the pre-run fold-specific thresholds. Promotion requires all of:

- schema success at least 0.995;
- genuine-refusal recall at least 0.80;
- genuine-refusal precision at least 0.75; and
- capability-failure F1 at least 0.80.

The model's own hard primary class is reported as a diagnostic but does not
replace the frozen threshold rule. If both input modes pass, the winner is the
one with the lower predeclared combination of design-weighted and
class-balanced Brier scores. Any winner is an **internal candidate** and still
requires external probability-sample validation on newly added subject models.

## Exact freeze and cost

| Item | Frozen value |
|---|---|
| Configuration | `fold_nested_error_targeted_15_v2` |
| Model | `openai/gpt-5.6-luna` |
| Provider | OpenAI through OpenRouter |
| Requests | 1,400 |
| Provider payload SHA-256 | `654f90724c940b8f325dd5e4c122bd1bf9e9af70eb4a3bcfc27c5b619e3a7e87` |
| Estimated input tokens | 20,730,978 |
| Planning output tokens | 266,000 |
| Planning cost | $4.9516954 |
| Single-attempt reserved cost | $4.8517956 |
| Suggested hard ceiling | $7.50 |
| Paid authorization | No |
| Network call made | No |

The cost uses the 2026-08-25 frozen OpenRouter price snapshot: $0.20 per million
input tokens and $1.20 per million output tokens for the pinned OpenAI route.
No prompt-cache discount is assumed. Pricing must be rechecked before an
authorization is recorded if the provider listing has changed.

## Inputs and outputs

Authoritative directory:

`annotations/response_validity_human_v2/fold_nested_refusal_refinement_v2/`

| File | Contents |
|---|---|
| `refinement_manifest.json` | Design, input hashes, gates, payload hashes, and authorization state |
| `evaluation_gold.parquet` | The frozen 700 human rows and inherited fold assignments |
| `fold_exemplars.csv` | Fold-specific example identities and prior error scores |
| `transferred_thresholds.csv` | Ten pre-run fold-by-input thresholds and training diagnostics |
| `model_neutral_requests.jsonl` | Exact model-neutral messages and schemas |
| `provider_requests.jsonl` | Exact pinned OpenRouter payload |
| `token_volume.csv` | Per-request input and output token reservations |
| `cost_estimate.csv` | Cost components by input mode |
| `cost_estimate_summary.json` | Frozen aggregate cost and ceiling |

The builder and cost estimator are network-free:

```bash
python scripts/response_validity.py build-fold-nested-refusal-refinement
python scripts/response_validity.py estimate-fold-nested-refusal-refinement-cost
```

Authorization, execution, and scoring are separate fail-closed commands. They
must not be invoked as evidence of permission. A paid run requires a new user
authorization naming the exact payload hash, 1,400 requests, model and provider
route, fallback and reasoning settings, and a hard cost ceiling of $7.50.
