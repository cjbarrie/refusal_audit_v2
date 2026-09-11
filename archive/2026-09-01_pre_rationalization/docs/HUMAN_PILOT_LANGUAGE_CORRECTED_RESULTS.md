# Preliminary human response-validity pilot results

> **Status: provisional.** These estimates use one coder's 300 unique judgments. The 36 blinded repeats remain locked and were not read or analyzed. This is not yet a human gold standard, an accepted canonical analysis, or a substitute for the planned human-referenced DSL stage.

## Frozen inputs and estimator

The immutable base freeze contains 300 submitted judgments under codebook `response-validity-human-v2.1`. Its canonical base-label hash is `5abfe83881152bb3d1c7c3c38c461e1a978d9eb81ce4c7c32a5597536a21b163`. The audit targets the frozen 137,186-response population and uses the exact first- and pairwise inclusion probabilities implied by the union of the global, model × language, and priority-stratified SRSWOR components.

The primary column is the Horvitz–Thompson (HT) domain mean with an exact union-design variance estimator and a normal 95% interval. The Hájek ratio estimate is retained as a calibrated sensitivity. Intervals do not yet incorporate repeat-coding reliability or model-training uncertainty.

## Headline prevalence

| Human outcome | HT estimate [95% CI] | Hájek sensitivity | Sample events |
|---|---:|---:|---:|
| Genuine Refusal | 2.1% [0.9%, 3.2%] | 2.1% | 14 |
| Capability Failure | 19.4% [16.2%, 22.6%] | 19.4% | 67 |
| Coherent Pivot | 1.0% [0.0%, 2.0%] | 1.0% | 7 |
| Coherent Noncompliance | 3.1% [1.6%, 4.6%] | 3.1% | 21 |
| Coherent Answer | 76.6% [72.1%, 81.1%] | 76.6% | 208 |
| Ambiguous | 1.0% [0.1%, 1.9%] | 1.0% | 4 |

## What the original judge-coded non-engagement label captured

The original outcome is called **judge-coded non-engagement**, not refusal. Among the population domain carrying that original code:

| Human outcome within original non-engagement | HT estimate [95% CI] | Hájek sensitivity | Sample events / rows |
|---|---:|---:|---:|
| Genuine Refusal | 18.7% [5.6%, 31.8%] | 20.6% | 7 / 34 |
| Capability Failure | 50.6% [32.8%, 68.5%] | 55.9% | 19 / 34 |
| Coherent Pivot | 2.7% [0.0%, 7.9%] | 2.9% | 1 / 34 |
| Coherent Answer | 10.7% [0.5%, 20.9%] | 11.8% | 4 / 34 |
| Ambiguous | 8.0% [0.0%, 16.8%] | 8.8% | 3 / 34 |
| Not genuine refusal (measurement false positive) | 81.3% [68.2%, 94.4%] | 79.4% | 27 / 34 |

Among original engaged controls, the estimated genuine-refusal rate is 0.5% [0.2%, 0.9%] and the capability-failure rate is 16.5% [13.1%, 20.0%]. Thus the original instrument has both a severe construct-validity problem among its positives and a smaller but nonzero missed-refusal problem.

## Language diagnostics

| Language | Genuine refusal HT [95% CI] | Capability failure HT [95% CI] | Human rows |
|---|---:|---:|---:|
| en | 3.3% [0.0%, 7.0%] | 2.2% [0.0%, 6.6%] | 48 |
| zh | 2.2% [0.0%, 4.6%] | 13.7% [5.9%, 21.6%] | 48 |
| ar | 1.5% [0.0%, 3.8%] | 21.9% [12.0%, 31.9%] | 64 |
| ru | 0.7% [0.0%, 1.7%] | 23.3% [14.1%, 32.4%] | 65 |
| hi | 2.6% [0.0%, 5.7%] | 35.7% [25.6%, 45.8%] | 75 |

These are marginal design-weighted diagnostics, not prompt-paired language effects. Hindi's large capability-failure estimate is the clearest provisional measurement warning; formal language contrasts must use the planned prompt-paired human-reference DSL estimator.

## Home-topic diagnostic

| Home status | Genuine refusal HT [95% CI] | Capability failure HT [95% CI] | Human rows |
|---|---:|---:|---:|
| Home | 1.8% [0.0%, 4.5%] | 11.5% [2.2%, 20.7%] | 45 |
| Away | 2.4% [0.8%, 4.0%] | 20.2% [15.5%, 24.8%] | 207 |
| General | 0.8% [0.0%, 2.0%] | 24.1% [11.7%, 36.5%] | 48 |

These are unstandardized domain descriptions. They do **not** estimate the canonical home-minus-away contrast and cannot resolve the home finding with only 45 sampled home rows and two observed home refusals. The eventual analysis must apply a human-referenced cross-fitted DSL outcome inside the declared nested standardization used for the home estimand.

## System comparison boundary

Only 39 of the 300 human rows overlap exact GPT-5.6 Sol reference judgments. Those confusion counts are reported as unweighted overlap descriptions only. Wall-to-wall Sol-derived prediction comparisons are surrogate diagnostics, not independent frontier-model judgments and not human truth.

Overall accuracy is misleading for rare refusal: a system can appear accurate by predicting almost every response as non-refusal. Precision, recall, refusal–pivot confusion, capability-failure performance, calibration, and model/language heterogeneity must govern the surrogate bake-off.

## Surrogate readiness gate

The frozen bake-off readiness gate is **FAIL**. It requires at least four high-confidence exemplar candidates and ten independent held-out judgments per primary class; a row cannot serve both roles.

| Primary class | Total human rows | High confidence | Languages represented | Required additional rows |
|---|---:|---:|---:|---:|
| Ambiguous | 4 | 4 | 2 | 10 |
| Coherent Answer | 208 | 207 | 5 | 0 |
| Coherent Pivot | 7 | 7 | 4 | 7 |
| Genuine Refusal | 14 | 12 | 5 | 0 |
| Incoherent Garbled | 48 | 34 | 5 | 0 |
| Technical Degeneration | 4 | 4 | 2 | 10 |
| Wrong Language | 15 | 15 | 3 | 0 |

The pilot contains 15 coder-confirmed wrong-language cases. The classes still below the frozen readiness requirements are: ambiguous, coherent pivot, technical degeneration. `exemplar_candidates.csv` is therefore a deterministic candidate inventory only—not a frozen few-shot prompt, training set, or test set. No model bake-off or population annotation should begin until a label-blind enrichment sample repairs these deficits and the development/evaluation split is frozen by `prompt_id`.

## Files and reproducibility

- Immutable base: `annotations/response_validity_human_v2/base_freeze_v2_language_corrected/`.
- Preliminary estimates: `annotations/response_validity_human_v2/preliminary_audit_v2_language_corrected/`.
- `measurement_error_by_cell.csv` reports provisional original-label error composition by language, model, jurisdiction, and response-length band; zero-sample domains are explicit rather than imputed.
- Deterministically selected disagreement rows remain local in `deterministic_disagreement_examples.csv`; they were selected by category and source hash, not rhetorical convenience.
- `exemplar_candidates.csv` and `surrogate_readiness.json` enforce the pre-bake-off gate and must not be treated as an authorized model payload.
- Reproduce locally with `python scripts/response_validity.py apply-human-language-review`.
- No network or paid model call is made by either command.

## Decision gate

Use these results to design the exemplar bank, surrogate bake-off, and final human-reference precision simulation. Do not promote them to the paper's main results until repeat reliability is available and the final human-reference DSL stage passes its predeclared acceptance gates.
