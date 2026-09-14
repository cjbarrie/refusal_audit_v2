# `17_response_validity.R`

This stage summarizes the final Luna v2.4 measurement already attached to
`canon`. It does not run DSL, predict missing labels, call Sol, adjudicate, or
change any response-level classification.

`c23_response_validity_prevalence.csv` gives counts and realized-corpus shares
overall and by model, language, developer jurisdiction, prompt tier, topic
domain and issue region. It includes genuine refusal, capability failure and
substantive pivot, with the measurement source identified on every row.

`c23b_original_nonengagement_prevalence.csv` reports the original Gemini
measure only for the original 137,186 rows. It is separate because expansion
models were never assigned that measure.

`c24_response_validity_overlap.csv` cross-tabulates the two adopted v2.4
outcomes. They are independent dimensions, so the overlap is retained rather
than forced into an exclusive primary class. `c25` reports marginals for task
behavior, substantive refusal, language fidelity, output quality, technical
failure, confidence and annotation source. `c26` records the exact response
count, outcome counts, final hash, 129-case Luna repair and the fact that no Sol
repair or human gold standard was used.

`c27_annotation_transition.csv` is likewise restricted to the original panel
and crosses the original binary engagement measure
with four mutually exclusive final states: neither outcome, capability failure
only, genuine refusal only, and both. It reports counts, shares within each
original label, and shares of the full corpus. This is an instrument-transition
description, not an estimate of either annotator's accuracy.

The current-outcome tables describe the 299,080 observed responses; the
original-measure tables describe the explicitly named original subset. The
script does not add binomial sampling intervals. Uncertainty in Luna's
measurement accuracy is a different problem and is documented in
`RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md`; a CI around a census share would not
represent it.

For example, a response labelled both refusal and wrong-language failure enters
both binary counts and the overlap state. It is not assigned to whichever label
happens to be checked first.
