# Response validity: current measurement state

Status: 1 September 2026.

This page gives the short, current interpretation of the response-validity
work. The full codebook, prompts, structured-output request, sampling history,
model comparisons, hashes and worked examples are in
[`RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md`](RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md).
The dated sequence of decisions is preserved in
[`RESPONSE_VALIDITY_DECISION_LOG.md`](RESPONSE_VALIDITY_DECISION_LOG.md).

## Why the original label changed

The original Gemini annotation reduced response behavior to an engagement
code. The event `engagement_code >= 4` combined several different things:

- a coherent refusal to perform the requested task;
- an answer that changed or avoided the requested task;
- output in the wrong language;
- incoherent or mechanically degenerated output; and
- empty or otherwise unusable output.

It is therefore called **judge-coded non-engagement**, not refusal, in current
work. It remains useful as a measurement sensitivity and for reconstructing
earlier analyses, but it is not the preferred outcome.

The replacement codebook was developed inductively from observed responses.
Human review and targeted model review separated two axes that the original
label had collapsed: what the model did with the request, and whether it
produced usable output. Versions 2.1 through 2.4 progressively clarified
partial/implicit refusal, epistemic limitations, wrong-language responses and
the fact that a response can both refuse and fail technically. The adopted
v2.4 schema therefore permits genuine refusal and capability failure to
overlap.

## Final wall-to-wall table

The current response-level measurement is:

```text
annotations/response_validity_v2_4/
  wall_to_wall_luna_v1/final_annotations.parquet
```

Its SHA-256 is
`ce1b6c07de09e96912b034195c2c5ab6f2ef7762fbb103143e02913f1383cf75`.
It contains exactly 137,186 unique response keys, matching the analysis
corpus. GPT-5.6 Luna supplied the wall-to-wall labels under the frozen v2.4
prompt and schema. Of these responses:

- 3,591 are labelled genuine refusal;
- 43,317 are labelled capability failure; and
- a response may belong to both groups.

The main provider run produced 134,664 final rows. An adaptive Luna repair
resolved 129 schema/logical conflicts. The remaining 2,393 rows came from the
two retained v2.4 reference sets used in final assembly. Sol was not used to
repair the wall-to-wall Luna table.

`pred_genuine_refusal` means that the response withholds the requested task,
explicitly or implicitly, under the adopted boundary rules. A mere statement
of uncertainty or knowledge limitation is not a refusal if the response still
substantively performs the task. `pred_capability_failure` records unusable or
degraded output such as wrong-language, incoherent or technical degeneration;
it is a separate outcome rather than a complement of refusal.

## What the validation establishes

The codebook was refined using 700 earlier human-labelled cases: an initial
300-row known-probability sample and a 400-row difficulty-enriched sample.
Those labels were harmonized into the decomposed schema using explicit mapping
rules and direct reviews. Later targeted boundary reviews and fresh Luna/Sol
comparisons helped identify and repair ambiguous prompt rules. The precise
composition of each lot, including where Sol-assisted reviews entered, is set
out in the technical pipeline.

Sol is treated as a frontier **machine reference**, not a human gold standard.
The model comparisons support Luna as a scalable genuine-refusal annotator,
but do not turn machine agreement into human-certified population accuracy.
Human validation is incomplete, especially for capability failure. Any
reported accuracy must name its reference and sampling design.

## Consequence for analysis

The promoted working release is `canon_024`. It uses the final Luna v2.4 census,
distinguishes genuine refusal from capability failure, and retains original
judge-coded non-engagement only as a labelled
sensitivity. Historical releases must not be edited in place.

Completed validation designs, bake-offs, review interfaces and interim reports
are preserved under
[`../archive/2026-09-01_pre_rationalization/`](../archive/2026-09-01_pre_rationalization/).
They are provenance records, not current run instructions.
