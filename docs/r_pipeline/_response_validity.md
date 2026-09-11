# `_response_validity.R`

## Scientific purpose

This is the only live R interface to the final Luna v2.4 measurement. It does
not annotate, model or correct outcomes. It verifies the frozen Parquet file
and attaches its fields to the response-level analysis frame by exact key.
Keeping this operation in one helper prevents different estimators from reading
different drafts of the annotation table or reimplementing the outcome rules.

## Exact input and integrity contract

Default input:
`annotations/response_validity_v2_4/wall_to_wall_luna_v1/final_annotations.parquet`.
The required SHA-256 is
`ce1b6c07de09e96912b034195c2c5ab6f2ef7762fbb103143e02913f1383cf75`.
The table must contain 137,186 rows and unique
`(prompt_id, prompt_language, model)` keys. It must contain exactly 3,591
`pred_genuine_refusal` and 43,317 `pred_capability_failure` positives. Missing
columns, unknown codebook values, duplicate keys or a hash mismatch stop the
pipeline.

Some stored response strings contain an embedded NUL byte. Parquet preserves
that byte, but R character vectors cannot safely slice it during a join. The
loader therefore enables Arrow's `arrow.skip_nul` option only while reading the
file and then restores the caller's previous setting. This strips the invalid
byte from the in-memory diagnostic text only; it does not alter the source
file, its verified hash, any response key or any structured annotation field.

The path and expected hash can be overridden through `RESPONSE_VALIDITY_PATH`
and `RESPONSE_VALIDITY_SHA256`. This supports a future versioned measurement,
but makes an accidental file substitution impossible.

## Variables added

The seven component judgments are added with an `rv_` prefix. The two frozen
derived outcomes become integer indicators named `genuine_refusal` and
`capability_failure`. R does not reconstruct them from component fields.
`substantive_pivot` is a descriptive indicator for
`rv_task_behavior == "coherent_pivot"`. `original_nonengagement` reproduces
`engagement_code >= 4` solely for labelled measurement sensitivity.

`response_validity_state` is a four-level descriptive cross-classification:
refusal and capability failure, refusal only, capability failure only, or
neither. Refusal and capability failure are not mutually exclusive.

## Worked example

Suppose one response key has `pred_genuine_refusal = TRUE`,
`pred_capability_failure = TRUE`, and `task_behavior = coherent_pivot`. The
joined row receives `genuine_refusal = 1`, `capability_failure = 1`,
`substantive_pivot = 1`, and state `refusal and capability failure`. The R layer
does not force that case into only one category and does not recode it as
engagement.

## What this permits

The helper establishes exact measurement provenance and complete keyed
coverage. It does not establish human gold-standard accuracy and supplies no
sampling uncertainty. Those limits belong to the measurement study, not the
join.
