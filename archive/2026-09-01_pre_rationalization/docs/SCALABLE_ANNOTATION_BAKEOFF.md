# Scalable human-referenced annotation bake-off

Status date: 2026-08-25. The authorized run is complete: all 8,400 requests
produced valid results for $12.54203861. No candidate passed the frozen
refusal-recall gate, so no population annotation is approved. Results are in
[`SCALABLE_ANNOTATION_BAKEOFF_RESULTS.md`](SCALABLE_ANNOTATION_BAKEOFF_RESULTS.md).

## Purpose

The immediate problem is to obtain accurate, inexpensive response-validity
annotations each time the project adds subject models. Design-based supervised
learning (DSL) remains the method for correcting final paper estimates, but it
is downstream: it should not prevent the project from first selecting a useful
annotation instrument.

This bake-off uses all 700 completed human reviews for **internal validation**.
The old 123-case reserve failed its predeclared refusal-support threshold and
has been explicitly retired for this purpose. It is no longer described as a
pristine test set. A probability sample from responses produced by the next
model expansion will be the first genuinely external validation of the selected
instrument.

## Human inputs

| Input | Rows | Role |
|---|---:|---|
| Complete-language base freeze | 300 | Probability sample of the current 137,186-response population |
| Completed enrichment freeze | 400 | Difficult and uncommon cases selected for instrument development |
| Literal English translations | 700 | Optional comprehension aid and translation ablation |
| Human codebook v2.1 | 1 version | Frozen outcome definitions and component-first boundary rules |

The 700 human classes are: 379 coherent answers, 63 genuine refusals, 12
coherent pivots, 162 incoherent/garbled responses, 61 wrong-language responses,
18 technical degenerations, and five ambiguous responses. The main evaluation
outcomes are genuine refusal and the union of the three capability-failure
classes. Pivot remains diagnostic because 12 cases cannot support precise model
selection.

## Cross-validation design

Whole `issue_id` groups, not individual responses, are assigned to five fixed
folds using seed `20260825`. No issue contributes both an evaluation case and a
few-shot example in the same fold. The fold sizes are 153, 150, 125, 137 and
135 responses. They contain respectively 13, 12, 9, 13 and 16 refusals and 53,
53, 43, 48 and 44 capability failures.

Each response is evaluated under:

- two models: OpenAI GPT-5.6 Luna and Google Gemini 3.5 Flash-Lite;
- two prompts: component-first zero-shot and component-first 15-shot;
- three input modes: original response only; original plus literal English
  translation; and translation only.

The 15-shot bank is rebuilt separately for each fold from other issues. It
contains one human-verified coherent answer, genuine refusal, and capability
failure in each of Arabic, English, Hindi, Russian and Chinese. The evaluation
label never appears in its query or examples.

Translation-only is a diagnostic, not a production candidate. It withholds the
source response and forces language fidelity to `unassessable`, because an
English rendering cannot establish whether the model answered in the requested
language. The other translation conditions include translator-reported source
language and uncertain spans. The original response remains mandatory for any
production annotation that measures wrong-language output, script mixture,
repetition, encoding damage, or garbling.

This crossing produces 4,200 model-neutral requests and 8,400 provider
requests. The exact provider payload SHA-256 is
`bcc6725be78d86e0c74a8516ca5cd218ef53ef27c611843a6948bbc95c4ded83`.

## Output schema and scoring

The model returns component-level fields for semantic behavior, language
fidelity, coherence and technical failure, followed by a seven-class hard
label, calibrated probabilities for genuine refusal and capability failure,
confidence, and a short evidence span. The two outcome probabilities must lie
in `[0,1]` and sum to no more than one. Schema parsing fails closed.

The predeclared production gates are:

- at least 99.5% schema-valid completion;
- genuine-refusal recall at least 0.80;
- genuine-refusal precision at least 0.75; and
- capability-failure F1 at least 0.80.

Among original-containing candidates that pass every gate, selection minimizes:

```text
0.40 × design-weighted refusal Brier score on the probability 300
+ 0.25 × design-weighted capability Brier score on the probability 300
+ 0.25 × class-balanced refusal Brier score on all 700
+ 0.10 × class-balanced capability Brier score on all 700
```

Hard-label metrics and Brier/log-loss are also reported separately by language.
The selected result is an internally validated candidate, not external
certification and not a population prevalence estimate.

## Frozen pricing and authorization boundary

Pricing was checked on 2026-08-25 against the exact non-batch chat routes:

| Model and pinned provider | Input / 1M | Output / 1M |
|---|---:|---:|
| `openai/gpt-5.6-luna` through `openai` | $0.20 | $1.20 |
| `google/gemini-3.5-flash-lite` through `google-ai-studio` | $0.30 | $2.50 |

Fallbacks and reasoning output are disabled. No cache discount is assumed. The
token freeze contains 61,921,990 estimated input tokens, 1,596,000 planning
output tokens, and 3,528,000 maximum output tokens. Cost protection reserves
10% plus 256 input tokens per request, producing 70,264,594 reserved input
tokens. The planning estimate is **$20.5187485**, the maximum single-attempt
reservation is **$22.0072975**, and the suggested hard ceiling is **$31.00**.

The runner is resumable and append-only. It pins providers, disables fallbacks,
checks the authorized payload hash and ceiling, counts prior paid attempts, and
reserves every in-flight request before dispatch. A build, cost estimate, score,
or canonical release cannot authorize or call a provider.

## Exact files

The implementation is `src/refusal_audit/response_validity/scalable_bakeoff.py`.
Its guarded commands are exposed through `scripts/response_validity.py`. Frozen
artifacts are under
`annotations/response_validity_human_v2/scalable_annotation_bakeoff_v1/`:

| File | Contents |
|---|---|
| `evaluation_gold.parquet` | 700 human rows, translations, sample source and fold |
| `fold_assignments.parquet` | Response keys, issue, sample source and fold |
| `fold_diagnostics.csv` | Fold sizes, issues, refusal and capability counts |
| `fold_exemplars.csv` | The 15 training examples used for each fold |
| `model_neutral_requests.jsonl` | 4,200 evaluation messages before model crossing |
| `provider_requests.jsonl` | Exact 8,400-request provider payload |
| `token_volume.csv` | Per-request token counts and output reservations |
| `response_schema.json` | Strict structured-output schema |
| `bakeoff_manifest.json` | Input and artifact hashes; unpaid authorization state |
| `cost_estimate.csv` | Cost by model, prompt and input mode |
| `cost_estimate_summary.json` | Aggregate tokens, price hash and $31 ceiling |

Completed scoring adds `metrics.csv`, `metrics_by_language.csv`,
`candidate_selection.csv`, `refusal_error_profile.csv`,
`posthoc_threshold_diagnostics.csv`, and `score_summary.json`.
The manifest hashes the actual data, translation, codebook and pricing inputs.
It deliberately does not hash this document or the chronological decision log:
those narrative records must be updated after a freeze, so treating them as
scientific inputs would make an otherwise unchanged payload invalidate itself.

## Reproduction

Local, unpaid commands:

```bash
python scripts/response_validity.py build-scalable-annotation-bakeoff
python scripts/response_validity.py estimate-scalable-annotation-bakeoff-cost
```

The completed authorization named the provider payload hash, 8,400 calls, both
pinned routes, and the exact $31.00 ceiling. The final manifest and run summary
record complete coverage and actual provider cost. A later refinement or
population-wide annotation is a new payload and requires new authorization.
