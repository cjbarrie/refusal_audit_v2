# =============================================================================
# Technical reference: docs/r_pipeline/_expansion_input.md
# EXPANSION INPUT CONTRACT -- validate and append completed expansion models
# =============================================================================
# This helper makes no provider call. It verifies the five frozen Luna v2.4
# annotation batches against their manifests and result hashes, derives the two
# adopted outcomes from the stored component fields, and supplies response rows
# for nine expansion models. Generation failures and annotations that exhaust
# their schema attempts remain absent; none is imputed. The combined observed
# analysis population is therefore 249,201.

suppressPackageStartupMessages({
  library(dplyr)
  library(arrow)
  library(jsonlite)
  library(digest)
  library(tibble)
})

EXP_KEY <- c("prompt_id", "prompt_language", "model")
EXP_EXPECTED_N <- 249201L
EXP_EXPECTED_MODELS <- 20L
EXP_EXPECTED_REFUSALS <- 6794L
EXP_EXPECTED_CAPABILITY_FAILURES <- 60968L
EXP_EXPECTED_EXPANSION_ROWS <- 112015L

EXPANSION_JURISDICTION <- c(
  "ministral-14b" = "EU",
  "nova-lite" = "US",
  "llama-4-scout" = "US",
  "hunyuan-a13b" = "CN",
  "glm-4.7-flash" = "CN",
  "gemini-2.5-flash-lite" = "US",
  "kimi-k2.5" = "CN",
  "sarvam-105b" = "India",
  "bielik-11b-v3.0" = "EU"
)

EXPANSION_BATCHES <- tribble(
  ~path, ~n_requested, ~n_complete, ~payload_sha256, ~expansion_wave,
  "annotations/model_expansion_v3/luna_v2_4_completed_batch1", 37440L, 37440L,
  "9dc329e7a84c1848e1f10803d8adfba5d17be052af16f2882a778b2860b6daed", "expansion_v3",
  "annotations/model_expansion_v3/luna_v2_4_completed_batch2", 37439L, 37439L,
  "2a794718d80b41055cd5e151163ce221c8ddc79e2c657e5425fa3c8e954bbef0", "expansion_v3",
  "annotations/model_expansion_v3/luna_v2_4_kimi_batch3", 12480L, 12479L,
  "113e2a2d269e91814434ec25a2ee7765d8460f319ea81ac96751ee20ce55dfe9", "expansion_v3",
  "annotations/model_expansion_v4/full_generation_v1/sarvam-105b/luna_v2_4_annotations_v1", 12478L, 12478L,
  "dec6a32dbcf50b755e73fe7d96943ddc3193289441d7ee293b01cf8e838a23e4", "expansion_v4",
  "annotations/model_expansion_v4/full_generation_v1/bielik-11b-v3.0/luna_v2_4_annotations_v1", 12184L, 12179L,
  "2221c6fa24d35896282173441d54ed57934dc91e6c9e441dd64b2c129dac78b7", "expansion_v4"
)

EXPANSION_GENERATION_ROOTS <- c(
  "annotations/model_expansion_v3/full_run_v1",
  "annotations/model_expansion_v3/hunyuan_all_languages_v3_1",
  "annotations/model_expansion_v4/full_generation_v1/sarvam-105b",
  "annotations/model_expansion_v4/full_generation_v1/bielik-11b-v3.0"
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

load_expansion_outcomes <- function() {
  batches <- lapply(seq_len(nrow(EXPANSION_BATCHES)), function(i) {
    z <- EXPANSION_BATCHES[i, ]
    read_expansion_batch(z$path, z$n_requested, z$n_complete, z$payload_sha256,
                         z$expansion_wave)
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
    exp_stop("final 20-model frame failed its count/key/outcome contract")
  }
  combined
}
