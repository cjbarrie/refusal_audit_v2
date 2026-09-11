# Scalable annotation bake-off: internal-validation results

Status date: 2026-08-25. The authorized run and frozen scoring are complete.
No candidate passed every promotion gate, so no model/prompt/input combination
is approved for population annotation.

## Run identity and cost

The run used the exact 8,400-request payload with SHA-256
`bcc6725be78d86e0c74a8516ca5cd218ef53ef27c611843a6948bbc95c4ded83`.
All 8,400 request IDs have one valid final result; results SHA-256 is
`585bd509e8b09ed7b6c148f7324f064123e924c1759cbf0d296eaa59c4c2691e`.
Observed provider cost was **$12.54203861**, below the authorized $31 ceiling.
Luna's 4,200 valid results cost $2.96793041 and Gemini's cost $9.52248070.
Paid invalid-output retries cost $0.05162750.

There are 18,368 append-only attempt records:

- 8,400 valid completions;
- 9,906 zero-cost authentication failures caused by a stale shell key
  shadowing the current repository `.env`;
- 58 initially rejected Luna outputs caused by an overly restrictive local
  cross-field validator;
- one Luna probability-sum violation; and
- three Gemini malformed-JSON escapes.

The credential defect was repaired by loading the repository `.env` only at
the paid CLI boundary, matching the project's existing secret-loading contract.
The validator defect was repaired because semantic behavior and capability are
separate dimensions: a coherent answer in the wrong language can have
`semantic_behavior=answer` and `primary_class=wrong_language`. Neither repair
changed a message, model, input mode, fold, example, schema, provider route, or
payload hash. Failed records and their costs remain in `attempts.jsonl`.
The top-level manifest initially retained its pre-run `network_call_made=false`
flag; final reconciliation now derives that field from the attempt ledger and
sets it to `true`. The reconciliation made no provider request and reproduced
the same results hash, coverage and cost.

## Frozen promotion result

Promotion required schema success at least .995, refusal precision at least
.75, refusal recall at least .80, and capability-failure F1 at least .80. Every
candidate achieved schema success 1.00 after retry. **Every candidate failed
the refusal-recall gate.** Gemini zero-shot also failed capability F1. The
scorer therefore returned `no_candidate_passed`; thresholds were not relaxed.

Production-eligible hard-label results are:

| Model | Prompt | Input | Refusal precision | Refusal recall | Capability F1 | Registered score | Decision |
|---|---|---|---:|---:|---:|---:|---|
| Luna | zero-shot | original | .807 | .730 | .906 | .0513 | fail recall |
| Luna | zero-shot | original + translation | .887 | .746 | .904 | .0532 | fail recall |
| Gemini | 15-shot | original + translation | .882 | .714 | .919 | .0597 | fail recall |
| Luna | 15-shot | original | .917 | .698 | .897 | .0629 | fail recall |
| Luna | 15-shot | original + translation | .955 | .667 | .910 | .0661 | fail recall |
| Gemini | 15-shot | original | .852 | .730 | .901 | .0680 | fail recall |
| Gemini | zero-shot | original + translation | .839 | .746 | .647 | .0949 | fail recall and capability F1 |
| Gemini | zero-shot | original | .833 | .714 | .672 | .0968 | fail recall and capability F1 |

The registered score is lower-is-better and combines design-weighted Brier
scores on the probability 300 with class-balanced Brier scores on all 700. The
lowest score belongs to Luna zero-shot original-only, but it cannot be selected
because its refusal recall is .730.

## What translation and examples did

For Luna zero-shot, adding translation improved refusal precision from .807 to
.887 and recall from .730 to .746. It also improved refusal probability Brier
scores, but worsened the probability-sample capability Brier enough that the
registered composite score rose slightly. This is evidence that translation is
useful for refusal discrimination, not evidence that translation alone is
sufficient.

Translation-only capability F1 fell to .781 for Luna zero-shot, .834 for Luna
15-shot, .571 for Gemini zero-shot, and .818 for Gemini 15-shot. This confirms
the predeclared warning: translation can hide wrong-language and source-text
failures and cannot replace the original response.

The 15-example prompts generally increased refusal precision but reduced
refusal recall. The current examples make the classifier more conservative;
they do not solve the missed-refusal boundary.

## Error profile

Luna zero-shot plus translation is the best hard-label refusal candidate:
47/63 human refusals detected, six false positives, and 16 false negatives.
Among the missed refusals:

- 11 were human-coded implicit noncompliance and five explicit;
- 14 were predicted as coherent answers, one as a pivot, and one as wrong
  language;
- five of the 11 Russian refusals were missed, compared with two of nine Arabic,
  four of 19 English, two of 12 Hindi, and three of 12 Chinese refusals; and
- most missed cases received very low refusal probability, so ordinary
  threshold adjustment cannot recover them without additional false positives.

A same-700, explicitly post-hoc threshold diagnostic found that Luna zero-shot
could barely cross the two refusal gates at threshold .08 without translation
(precision .761, recall .810) or .05 with translation (precision .750, recall
.810). No other candidate had such a threshold. These values cannot promote a
candidate because the thresholds were chosen on the same 700 labels. They
justify a separately frozen, fold-nested threshold study; they do not repair the
failed experiment.

## Scientific decision

Do not run any candidate over the full population. Retain Luna zero-shot in
both original-only and original-plus-translation forms as development
candidates. The next local iteration should use the completed out-of-fold
errors to build fold-specific implicit/partial-refusal examples from training
issues only, then estimate a threshold using training folds and apply it once
to the held-out fold. This tests the two plausible improvements without letting
an evaluation issue supply its own example or threshold.

If that nested refinement still fails .80 recall and .75 precision, compare one
stronger but still scalable model against the same folds rather than adding
more general human annotation. Regardless of model, the next roster expansion's
probability sample remains the external audit. Human-reference DSL remains the
final protection for paper estimates and continues to use the original 300 as
the current-population residual-correction sample.

## Reproducible outputs

All files are under
`annotations/response_validity_human_v2/scalable_annotation_bakeoff_v1/`:

- `attempts.jsonl`, `results.jsonl`, and `run_summary.json` record execution;
- `metrics.csv` and `metrics_by_language.csv` contain frozen hard-label and
  probability scores;
- `candidate_selection.csv` applies the registered gates and score;
- `refusal_error_profile.csv` aggregates refusal misses without exposing full
  response text;
- `posthoc_threshold_diagnostics.csv` is clearly marked non-promotional; and
- `score_summary.json` records `no_candidate_passed` and hashes every scoring
  artifact.
