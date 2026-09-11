# Stage A disagreement adjudication results

## Status and provenance

The coder completed all 18 Stage A disagreement tasks on 2026-08-21. The live
append-only log contains exactly one submitted record for every frozen packet
row, all from coder `Chris`, all tied to packet SHA-256
`7d483a8a8695eecc99beea09e8e8e96482affb0397390b251001860e69f75fa9`.
The completed log was frozen as `stage-a-human-adjudication-freeze-v1.0` with
canonical adjudicated-label SHA-256
`377d26e63b959dd366bd52bfeca983bbb5c50f4ff066b2a2f8b498e7374ec53f`.
No provider call was made and no original human label was overwritten.

The Streamlit interface hid the original label, note, source model, Luna
predictions, and disagreement count during submission. This was nevertheless
**not an independent blinded adjudication**: the 18 rows were selected because
Luna disagreed, and the coder had previously seen a casebook containing the
model predictions and preliminary assistant assessments. These results are
measurement-development evidence and cannot be used as an unbiased held-out
performance estimate.

## Label changes

Six of 18 primary classes changed:

| Original class | Adjudicated class | N |
|---|---|---:|
| Ambiguous | Incoherent/garbled | 2 |
| Genuine refusal | Coherent answer | 2 |
| Coherent pivot | Coherent answer | 1 |
| Incoherent/garbled | Coherent answer | 1 |

The other 12 labels were retained. In particular, one previously flagged
coherent-answer/garbling case remained a coherent answer, and one
disclaimer-plus-answer case remained a coherent pivot. The adjudication is the
coder's decision, not the assistant's preliminary triage.

Across the resulting 84-row audit/development set, the primary-class counts are:

| Class | N |
|---|---:|
| Coherent answer | 55 |
| Incoherent/garbled | 17 |
| Wrong language | 5 |
| Genuine refusal | 3 |
| Coherent pivot | 2 |
| Technical degeneration | 2 |
| Ambiguous | 0 |

Only primary class was replaced. All language-fidelity values remain from the
separate complete-language-review v3 because the simplified adjudication form
did not independently remeasure that dimension.

## Configuration rescore

| Configuration | Accuracy, original → adjudicated | Macro F1, original → adjudicated | Refusal P/R/F1, adjudicated | Pivot F1, adjudicated | Capability-failure F1, adjudicated |
|---|---:|---:|---:|---:|---:|
| Zero-shot joint | .857 → .917 | .630 → **.825** | 1.00/1.00/1.00 | **.667** | .939 |
| 7-shot joint | .857 → .881 | .644 → .759 | 1.00/1.00/1.00 | .333 | .894 |
| 14-shot joint | .869 → .893 | .630 → .725 | .75/1.00/.857 | 0 | .958 |
| 14-shot decomposed | .845 → .905 | .581 → .728 | .75/1.00/.857 | 0 | .939 |
| 22-shot error-targeted | .881 → **.929** | .684 → .794 | .75/1.00/.857 | 0 | **.958** |

Macro F1 is computed over classes having a gold-positive or predicted-positive
case. Because adjudication removed both ambiguous cases, the adjudicated macro
averages six observed classes rather than the original seven; the before/after
macro change is therefore not a strictly fixed-support comparison.

Zero-shot and 7-shot now classify all three adjudicated genuine refusals with
no false positives. The 22-shot prompt has the best overall accuracy and ties
for best capability-failure F1, while zero-shot has the best observed-class
macro F1 and pivot F1. The decomposed and both larger joint prompts identify
none of the two remaining pivots.

## Interpretation and decision

No single prompt dominates all relevant outcomes. More importantly, only three
genuine refusals and two pivots remain, so perfect refusal performance and
configuration rankings are highly unstable. The error-selected and
prior-exposed adjudication also mechanically tends to resolve some apparent
errors in Luna's favor.

Therefore:

1. Do not select a final surrogate from this rescore.
2. Use these cases to clarify the codebook and construct compact, verified
   examples, but label them as development examples only.
3. Freeze a new rare-class-enriched evaluation set before reviewing any of its
   responses or model predictions.
4. Annotate that set without showing the coder earlier labels, configuration
   outputs, assistant recommendations, or selection strata.
5. Compare the compact zero-/7-shot approach with the error-targeted approach
   on that untouched set. Refusal, pivot, and capability-failure performance
   remain separate selection criteria.

Machine-readable artifacts are under
`annotations/response_validity_human_v2/stage_a_adjudication_v1/freeze_v1/`.
