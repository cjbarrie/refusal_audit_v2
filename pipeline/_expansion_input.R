# =============================================================================
# Technical reference: docs/r_pipeline/_expansion_input.md
# EXPANSION INPUT CONTRACT -- validate and append completed expansion models
# =============================================================================
# This helper makes no provider call. It reads the hash-bound declarative roster
# in config/analysis_roster_v1.json, verifies every Luna v2.4 batch, derives the
# two adopted outcomes from stored component fields, and appends the admitted
# expansion responses. Sol audit labels are deliberately not read here: they
# belong to the separate measurement-validation stage and never overwrite the
# complete Luna census.

suppressPackageStartupMessages({
  library(dplyr)
  library(arrow)
  library(jsonlite)
  library(digest)
  library(tibble)
})
# Base R cannot represent embedded NUL bytes found in a few provider-returned
# text fields. This affects text conversion only; the immutable source Parquet
# and its hash are verified before reading, and no outcome/key field is altered.
options(arrow.skip_nul = TRUE)

EXP_KEY <- c("prompt_id", "prompt_language", "model")
EXP_ROSTER_PATH <- "config/analysis_roster_v1.json"
if (!file.exists(EXP_ROSTER_PATH)) stop("missing analysis roster", call. = FALSE)
EXP_ROSTER <- jsonlite::read_json(EXP_ROSTER_PATH, simplifyVector = FALSE)
EXP_EXPECTED_N <- as.integer(EXP_ROSTER$expected$response_rows)
EXP_EXPECTED_MODELS <- as.integer(EXP_ROSTER$expected$models)
EXP_EXPECTED_REFUSALS <- as.integer(EXP_ROSTER$expected$genuine_refusals)
EXP_EXPECTED_CAPABILITY_FAILURES <- as.integer(EXP_ROSTER$expected$capability_failures)
EXP_EXPECTED_EXPANSION_ROWS <- as.integer(EXP_ROSTER$expected$expansion_rows)
EXPANSION_JURISDICTION <- unlist(EXP_ROSTER$models, use.names = TRUE)
exp_nullable_chr <- function(x) if (is.null(x)) NA_character_ else as.character(x)
EXPANSION_BATCHES <- purrr::map_dfr(EXP_ROSTER$batches, function(x) tibble(
  format = x$format, path = x$path, n_requested = as.integer(x$n_requested),
  n_complete = as.integer(x$n_complete),
  payload_sha256 = exp_nullable_chr(x$payload_sha256),
  assembled_sha256 = exp_nullable_chr(x$assembled_sha256),
  final_manifest_sha256 = exp_nullable_chr(x$final_manifest_sha256),
  expansion_wave = x$wave))

EXPANSION_GENERATION_ROOTS <- c(
  "annotations/model_expansion_v3/full_run_v1",
  "annotations/model_expansion_v3/hunyuan_all_languages_v3_1",
  "annotations/model_expansion_v4/full_generation_v1/sarvam-105b",
  "annotations/model_expansion_v4/full_generation_v1/bielik-11b-v3.0",
  "annotations/model_expansion_v4/local_gguf_full_hpc_v1"
)

exp_sha256 <- function(path) digest::digest(path, algo = "sha256", file = TRUE)
exp_stop <- function(...) stop("[expansion input contract] ", ..., call. = FALSE)

read_expansion_batch <- function(path, n_requested, n_complete, payload_sha256,
                                 expansion_wave) {
  files <- file.path(path, c("manifest.json", "run_summary.json",
                            "response_index.parquet", "results.jsonl"))
  if (!all(file.exists(files))) exp_stop("missing batch artifact under ", path)
  manifest <- jsonlite::read_json(files[1], simplifyVector = TRUE)
  summary <- jsonlite::read_json(files[2], simplifyVector = TRUE)
  if (!identical(as.integer(manifest$n_requests), as.integer(n_requested)) ||
      !identical(as.character(manifest$provider_payload_sha256), payload_sha256) ||
      !identical(as.character(summary$provider_payload_sha256), payload_sha256) ||
      !identical(as.integer(summary$n_expected), as.integer(n_requested)) ||
      !identical(as.integer(summary$n_completed), as.integer(n_complete)) ||
      !identical(as.integer(summary$n_incomplete), as.integer(n_requested - n_complete)) ||
      !identical(as.character(summary$results_sha256), exp_sha256(files[4])) ||
      !isTRUE(summary$schema_gate_pass)) {
    exp_stop("manifest/run-summary contract failed for ", path)
  }
  art <- manifest$artifact_sha256
  if (!identical(as.character(art[["response_index.parquet"]]), exp_sha256(files[3])) ||
      !identical(as.character(art[["provider_requests.jsonl"]]), payload_sha256)) {
    exp_stop("artifact hash contract failed for ", path)
  }

  index <- arrow::read_parquet(files[3]) |> as.data.frame() |> as_tibble()
  con <- file(files[4], open = "r", encoding = "UTF-8")
  on.exit(close(con), add = TRUE)
  labels <- jsonlite::stream_in(con, verbose = FALSE) |> as_tibble()
  if (nrow(index) != n_requested || nrow(labels) != n_complete ||
      anyDuplicated(index$audit_response_id) || anyDuplicated(labels$audit_response_id) ||
      !all(labels$status == "complete")) {
    exp_stop("row/key/status contract failed for ", path)
  }

  rows <- index |>
    inner_join(labels |> select(
      audit_response_id, task_behavior, substantive_refusal,
      stance_disclaimer, epistemic_limitation, language_fidelity,
      output_quality, technical_failure, confidence,
      refusal_evidence_span, decision_note,
      annotation_provider_request_id = provider_request_id,
      annotation_created_at = created_at),
      by = "audit_response_id", relationship = "one-to-one") |>
    transmute(
      prompt_id, prompt_language, model = subject_model,
      rv_task_behavior = task_behavior,
      rv_substantive_refusal = substantive_refusal,
      rv_stance_disclaimer = stance_disclaimer,
      rv_epistemic_limitation = epistemic_limitation,
      rv_language_fidelity = language_fidelity,
      rv_output_quality = output_quality,
      rv_technical_failure = technical_failure,
      rv_confidence = confidence,
      rv_refusal_evidence_span = refusal_evidence_span,
      rv_decision_note = decision_note,
      rv_annotation_source = paste("Luna v2.4", expansion_wave, "census"),
      rv_provider_request_id = annotation_provider_request_id,
      rv_created_at = annotation_created_at,
      rv_pred_genuine_refusal = substantive_refusal %in% c("explicit", "implicit") &
        output_quality %in% c("coherent", "partly_coherent"),
      rv_pred_capability_failure = language_fidelity == "wrong_language" |
        output_quality == "incoherent_garbled" | technical_failure != "none",
      generation_provider_request_id,
      generation_response_sha256,
      corpus = expansion_wave)

  missing <- index |>
    anti_join(labels |> distinct(audit_response_id), by = "audit_response_id") |>
    transmute(prompt_id, prompt_language, model = subject_model,
              audit_response_id, provider_request_id)
  if (nrow(rows) != n_complete || nrow(missing) != n_requested - n_complete)
    exp_stop("completed/missing partition failed for ", path)
  list(rows = rows, missing = missing)
}

read_assembled_batch <- function(path, n_requested, n_complete,
                                 assembled_sha256, final_manifest_sha256,
                                 expansion_wave) {
  files <- file.path(path, c("assembled_labels.parquet",
                            "final_annotations_manifest.json"))
  if (!all(file.exists(files))) exp_stop("missing assembled batch artifact under ", path)
  if (!identical(exp_sha256(files[1]), assembled_sha256) ||
      !identical(exp_sha256(files[2]), final_manifest_sha256))
    exp_stop("assembled batch hash contract failed for ", path)
  manifest <- jsonlite::read_json(files[2], simplifyVector = TRUE)
  if (!identical(as.integer(manifest$response_labels), as.integer(n_complete)) ||
      !identical(as.character(manifest$assembled_labels_sha256), assembled_sha256))
    exp_stop("assembled batch manifest contract failed for ", path)
  # A handful of provider-returned evidence strings contain embedded NUL bytes.
  # Arrow preserves those bytes in the immutable Parquet artifact but base R
  # strings cannot represent them. Strip only those NULs during conversion;
  # outcome fields, keys, and the verified source artifact remain unchanged.
  labels <- arrow::read_parquet(files[1]) |> as.data.frame() |> as_tibble()
  if (nrow(labels) != n_complete || anyDuplicated(labels[c(
      "prompt_id", "prompt_language", "subject_model")]))
    exp_stop("assembled batch row/key contract failed for ", path)
  rows <- labels |> transmute(
    prompt_id, prompt_language, model = subject_model,
    rv_task_behavior = task_behavior,
    rv_substantive_refusal = substantive_refusal,
    rv_stance_disclaimer = stance_disclaimer,
    rv_epistemic_limitation = epistemic_limitation,
    rv_language_fidelity = language_fidelity,
    rv_output_quality = output_quality,
    rv_technical_failure = technical_failure,
    rv_confidence = confidence,
    rv_refusal_evidence_span = refusal_evidence_span,
    rv_decision_note = decision_note,
    rv_annotation_source = paste("Luna v2.4", expansion_wave, "census"),
    rv_provider_request_id = provider_request_id,
    rv_created_at = created_at,
    rv_pred_genuine_refusal = as.logical(pred_genuine_refusal),
    rv_pred_capability_failure = as.logical(pred_capability_failure),
    generation_provider_request_id = generation_request_id,
    generation_response_sha256,
    corpus = expansion_wave)
  list(rows = rows, missing = tibble(
    prompt_id = character(), prompt_language = character(), model = character(),
    audit_response_id = character(), provider_request_id = character()))
}

load_expansion_outcomes <- function() {
  batches <- lapply(seq_len(nrow(EXPANSION_BATCHES)), function(i) {
    z <- EXPANSION_BATCHES[i, ]
    if (z$format == "standard_jsonl")
      read_expansion_batch(z$path, z$n_requested, z$n_complete,
                           z$payload_sha256, z$expansion_wave)
    else if (z$format == "assembled_parquet")
      read_assembled_batch(z$path, z$n_requested, z$n_complete,
                           z$assembled_sha256, z$final_manifest_sha256,
                           z$expansion_wave)
    else exp_stop("unknown batch format: ", z$format)
  })
  rows <- bind_rows(lapply(batches, `[[`, "rows"))
  missing <- bind_rows(lapply(batches, `[[`, "missing"))
  expected_missing <- c("bielik-11b-v3.0" = 5L, "kimi-k2.5" = 1L)
  observed_missing <- table(missing$model)
  if (nrow(rows) != EXP_EXPECTED_EXPANSION_ROWS || anyDuplicated(rows[EXP_KEY]) ||
      nrow(missing) != 6L ||
      !identical(as.integer(observed_missing[names(expected_missing)]),
                 as.integer(expected_missing))) {
    exp_stop("combined expansion outcome contract failed")
  }
  attr(rows, "missing_annotations") <- missing
  rows
}

append_expansion_rows <- function(original) {
  required_meta <- c(
    "prompt_id", "prompt_language", "prompt_category", "topic_domain",
    "battery", "controversy_tier", "qid", "issue_id", "region_focus",
    "contention_score", "prompt_origin_language", "prompt_origin_form",
    "route", "dataset_type", "position_side", "natively_sourced",
    "contemporary", "category", "meta_controversy_tier")
  absent <- setdiff(required_meta, names(original))
  if (length(absent)) exp_stop("original frame lacks metadata: ", paste(absent, collapse = ", "))
  prompt_meta <- original |> distinct(across(all_of(required_meta)))
  if (nrow(prompt_meta) != 12480L ||
      anyDuplicated(prompt_meta[c("prompt_id", "prompt_language")]))
    exp_stop("prompt metadata is not one row per 2,496 x 5 prompt-language key")

  labels <- load_expansion_outcomes()
  new <- labels |>
    left_join(prompt_meta, by = c("prompt_id", "prompt_language"),
              relationship = "many-to-one") |>
    mutate(
      jurisdiction = unname(EXPANSION_JURISDICTION[model]),
      response_language = NA_character_, engagement_code = NA_integer_,
      refusal_justification = NA_character_,
      refusal_justification_other = NA_character_,
      judge_model = "openai/gpt-5.6-luna",
      judge_prompt_version = "response-validity-v2.4",
      annotation_run_id = corpus,
      genuine_refusal = as.integer(rv_pred_genuine_refusal),
      capability_failure = as.integer(rv_pred_capability_failure),
      substantive_pivot = as.integer(rv_task_behavior == "coherent_pivot"),
      original_nonengagement = NA_integer_,
      response_validity_state = case_when(
        genuine_refusal == 1L & capability_failure == 1L ~ "refusal and capability failure",
        genuine_refusal == 1L ~ "genuine refusal only",
        capability_failure == 1L ~ "capability failure only",
        TRUE ~ "neither"),
      corpus = corpus)

  # The original Gemini and slant fields were never collected for expansion
  # models. `bind_rows()` represents them as missing; no zero/neutral label is
  # manufactured. Convert factors before binding, then reconstruct the factors
  # over the full roster below.
  original <- original |> mutate(across(where(is.factor), as.character),
                                  corpus = "original_v1")
  combined <- bind_rows(original, new) |>
    mutate(
      model_f = factor(model),
      jurisdiction_f = factor(if_else(corpus != "original_v1", jurisdiction,
                                      jurisdiction_f)),
      language_f = factor(prompt_language),
      dataset_type_f = factor(dataset_type),
      prompt_origin_f = factor(prompt_origin_language),
      prompt_origin_form_f = factor(prompt_origin_form),
      route_f = factor(route))
  if (nrow(combined) != EXP_EXPECTED_N || anyDuplicated(combined[EXP_KEY]) ||
      n_distinct(combined$model) != EXP_EXPECTED_MODELS ||
      sum(combined$genuine_refusal) != EXP_EXPECTED_REFUSALS ||
      sum(combined$capability_failure) != EXP_EXPECTED_CAPABILITY_FAILURES ||
      sum(is.na(combined$original_nonengagement)) != EXP_EXPECTED_EXPANSION_ROWS) {
    exp_stop("final registry-defined frame failed its count/key/outcome contract")
  }
  combined
}
