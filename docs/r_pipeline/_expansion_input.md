# `_expansion_input.R`

**Purpose.** This is the read-only bridge between the nine completed model-
expansion runs and the R analysis. It validates the frozen Luna v2.4 annotation
batches, derives the adopted outcomes from their stored component fields, joins
the fixed prompt metadata, and appends the resulting rows to the original panel.

**Inputs.** The five batch directories named in `EXPANSION_BATCHES`: Batch 1
(Ministral, Nova, Llama), Batch 2 (Hunyuan, GLM, Gemini), and Batch 3 (Kimi).
The two v4 directories contain the completed Sarvam-105B and Bielik 11B v3.0
full-corpus Luna annotations.
For each it reads `manifest.json`, `run_summary.json`,
`response_index.parquet`, and `results.jsonl`. Payload hashes, artifact hashes,
requested/completed counts, schema-gate status, unique audit IDs, and complete
statuses must agree before any row is returned.

**Unit and joins.** One row is keyed by `(prompt_id,prompt_language,model)`.
The response index joins the Luna result one-to-one on `audit_response_id`.
Prompt metadata joins many-to-one on `(prompt_id,prompt_language)`. The helper
then appends expansion rows to the 137,186-row original frame.

**Outcomes.** `genuine_refusal` is one when `substantive_refusal` is explicit or
implicit and `output_quality` is coherent or partly coherent.
`capability_failure` is one for wrong-language output, incoherent/garbled output,
or a non-`none` technical failure. These outcomes can overlap. Original Gemini
engagement and slant fields are missing for expansion rows; they are never set
to zero or neutral.

**Missingness.** One Gemini Hindi generation produced no response; one Kimi
Chinese response and five Bielik responses exhausted Luna schema attempts.
Sarvam returned 12,478 of 12,480 requested generations and Bielik returned
12,184; generation failures never enter an annotation index. These records are
not imputed or counted as model capability failures: the analysis population is
the set of responses that both exist and have a valid v2.4 annotation.

**Output contract.** `append_expansion_rows(original)` returns 249,201 unique
keys across 20 models, with exactly 6,794 genuine refusals and 60,968 capability
failures. Any mismatch stops execution. The helper makes no network call and
writes no file itself.

**Worked example.** A Batch 3 Kimi index row identifies the prompt, language,
model and generation-response hash. Its matching Luna result supplies the seven
component judgments. If Luna records an explicit refusal and coherent output,
the appended row receives `genuine_refusal=1`. Its prompt metadata comes from
the same fixed prompt-language record used by the original models.

**Interpretation.** The helper establishes data provenance and measurement
consistency. It does not estimate a rate, contrast, causal effect, or interval.
