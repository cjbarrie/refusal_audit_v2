# `_expansion_input.R`

**Purpose.** This is the read-only bridge between the 13 completed expansion
models and the R analysis. It reads `config/analysis_roster_v1.json`, validates
each frozen Luna v2.4 source, derives the adopted outcomes, joins the fixed
prompt metadata, and appends the resulting rows to the original panel.

**Inputs.** The six batch directories declared in the roster: Batch 1
(Ministral, Nova, Llama), Batch 2 (Hunyuan, GLM, Gemini), and Batch 3 (Kimi).
Two v4 directories contain the completed Sarvam-105B and Bielik 11B v3.0
annotations. The sixth contains the 49,879-row Torch Luna census for Krutrim 2,
GigaChat3, EuroLLM 22B and Salamandra 7B. Standard batches provide
`manifest.json`, `run_summary.json`,
`response_index.parquet`, and `results.jsonl`. Payload hashes, artifact hashes,
requested/completed counts, schema-gate status, unique audit IDs, and complete
statuses must agree before any row is returned. The Torch source instead
provides a hash-bound `assembled_labels.parquet` and final manifest.

**Unit and joins.** One row is keyed by `(prompt_id,prompt_language,model)`.
The response index joins the Luna result one-to-one on `audit_response_id`.
Prompt metadata joins many-to-one on `(prompt_id,prompt_language)`. The helper
then appends 161,894 expansion rows to the 137,186-row original frame.

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

**Output contract.** `append_expansion_rows(original)` returns 299,080 unique
keys across 24 models, with exactly 7,175 genuine refusals and 74,598 capability
failures. Any mismatch stops execution. The helper makes no network call and
writes no file itself.

Embedded NUL bytes in a few provider-returned free-text evidence fields are
stripped only when Arrow converts the verified Parquet artifact into R strings.
The source file, hash, keys and outcome fields are unchanged.

**Worked example.** A Batch 3 Kimi index row identifies the prompt, language,
model and generation-response hash. Its matching Luna result supplies the seven
component judgments. If Luna records an explicit refusal and coherent output,
the appended row receives `genuine_refusal=1`. Its prompt metadata comes from
the same fixed prompt-language record used by the original models.

**Interpretation.** The helper establishes data provenance and measurement
consistency. It does not estimate a rate, contrast, causal effect, or interval.
