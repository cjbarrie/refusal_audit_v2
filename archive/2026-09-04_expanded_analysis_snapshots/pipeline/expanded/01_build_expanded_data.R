# =============================================================================
# EXPANDED V3 PANEL -- assemble frozen Luna v2.4 outcomes
# =============================================================================
# Purpose
#   Build a read-only analysis frame containing the accepted 11-model corpus
#   plus all seven expansion models. Two response keys have no outcome label:
#   one Gemini generation returned empty content twice, and one Kimi Luna
#   annotation exhausted three schema-validation attempts. Neither is imputed.
#
# Inputs
#   pipeline/data_clean.RData
#   annotations/model_expansion_v3/luna_v2_4_completed_batch{1,2}/ and
#   annotations/model_expansion_v3/luna_v2_4_kimi_batch3/
#     response_index.parquet, results.jsonl, manifest.json, run_summary.json
#
# Output
#   pipeline/expanded/derived/expanded_panel_v3.rds
#   pipeline/expanded/derived/expanded_panel_v3_manifest.json
#
# The script never calls a provider and never changes a canonical release.

suppressPackageStartupMessages({
  library(tidyverse)
  library(arrow)
  library(jsonlite)
  library(digest)
})
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())

OUT_DIR <- "pipeline/expanded/derived"
dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)
KEY <- c("prompt_id", "prompt_language", "model")

sha <- function(path) digest::digest(path, algo = "sha256", file = TRUE)

read_batch <- function(path, expected_requests, expected_completed,
                       expected_payload_sha) {
  manifest_path <- file.path(path, "manifest.json")
  summary_path <- file.path(path, "run_summary.json")
  index_path <- file.path(path, "response_index.parquet")
  results_path <- file.path(path, "results.jsonl")
  manifest <- jsonlite::read_json(manifest_path, simplifyVector = TRUE)
  summary <- jsonlite::read_json(summary_path, simplifyVector = TRUE)
  stopifnot(
    identical(as.integer(manifest$n_requests), as.integer(expected_requests)),
    identical(as.character(manifest$provider_payload_sha256), expected_payload_sha),
    identical(as.character(summary$provider_payload_sha256), expected_payload_sha),
    identical(as.integer(summary$n_expected), as.integer(expected_requests)),
    identical(as.integer(summary$n_completed), as.integer(expected_completed)),
    identical(as.integer(summary$n_incomplete),
              as.integer(expected_requests - expected_completed)),
    identical(as.character(summary$results_sha256), sha(results_path)),
    isTRUE(summary$schema_gate_pass)
  )

  index <- arrow::read_parquet(index_path) |> as_tibble()
  con <- file(results_path, open = "r", encoding = "UTF-8")
  on.exit(close(con), add = TRUE)
  labels <- jsonlite::stream_in(con, verbose = FALSE) |> as_tibble()
  stopifnot(nrow(index) == expected_requests, nrow(labels) == expected_completed,
            !anyDuplicated(index$audit_response_id),
            !anyDuplicated(labels$audit_response_id),
            all(labels$status == "complete"))

  missing <- index |> anti_join(labels |> distinct(audit_response_id),
                                by = "audit_response_id") |>
    select(prompt_id, prompt_language, model = subject_model,
           audit_response_id, provider_request_id)
  stopifnot(nrow(missing) == expected_requests - expected_completed)

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
      rv_provider_request_id = annotation_provider_request_id,
      rv_created_at = annotation_created_at,
      generation_provider_request_id,
      generation_response_sha256,
      genuine_refusal = as.integer(
        substantive_refusal %in% c("explicit", "implicit") &
          output_quality %in% c("coherent", "partly_coherent")),
      capability_failure = as.integer(
        language_fidelity == "wrong_language" |
          output_quality == "incoherent_garbled" |
          technical_failure != "none"),
      substantive_pivot = as.integer(task_behavior == "coherent_pivot"),
      annotation_source = "Luna v2.4 expansion census")
  stopifnot(nrow(rows) == expected_completed)
  list(rows = rows, missing = missing)
}

batch1 <- read_batch(
  "annotations/model_expansion_v3/luna_v2_4_completed_batch1",
  37440L, 37440L,
  "9dc329e7a84c1848e1f10803d8adfba5d17be052af16f2882a778b2860b6daed")
batch2 <- read_batch(
  "annotations/model_expansion_v3/luna_v2_4_completed_batch2",
  37439L, 37439L,
  "2a794718d80b41055cd5e151163ce221c8ddc79e2c657e5425fa3c8e954bbef0")
batch3 <- read_batch(
  "annotations/model_expansion_v3/luna_v2_4_kimi_batch3",
  12480L, 12479L,
  "113e2a2d269e91814434ec25a2ee7765d8460f319ea81ac96751ee20ce55dfe9")
new_labels <- bind_rows(batch1$rows, batch2$rows, batch3$rows)
annotation_missing <- bind_rows(batch1$missing, batch2$missing, batch3$missing)
stopifnot(nrow(new_labels) == 87358L, !anyDuplicated(new_labels[KEY]),
          nrow(annotation_missing) == 1L,
          identical(annotation_missing$model, "kimi-k2.5"))

load("pipeline/data_clean.RData")
prompt_meta_fields <- c(
  "prompt_id", "prompt_language", "prompt_category", "topic_domain",
  "battery", "controversy_tier", "qid", "issue_id", "region_focus",
  "contention_score", "prompt_origin_language", "prompt_origin_form",
  "route", "dataset_type", "position_side", "natively_sourced",
  "contemporary", "category", "meta_controversy_tier")
prompt_meta <- data_clean |>
  distinct(across(all_of(prompt_meta_fields)))
stopifnot(nrow(prompt_meta) == 12480L,
          !anyDuplicated(prompt_meta[c("prompt_id", "prompt_language")]))

NEW_JURIS <- c(
  "ministral-14b" = "EU", "nova-lite" = "US", "llama-4-scout" = "US",
  "hunyuan-a13b" = "CN", "glm-4.7-flash" = "CN",
  "gemini-2.5-flash-lite" = "US", "kimi-k2.5" = "CN")
new_rows <- new_labels |>
  left_join(prompt_meta, by = c("prompt_id", "prompt_language"),
            relationship = "many-to-one") |>
  mutate(jurisdiction = unname(NEW_JURIS[model]), corpus = "expansion_v3")
stopifnot(nrow(new_rows) == 87358L, !anyNA(new_rows$issue_id),
          !anyNA(new_rows$jurisdiction),
          sum(new_rows$genuine_refusal) >= 0,
          sum(new_rows$capability_failure) >= 0)

old_rows <- data_clean |>
  transmute(
    across(all_of(prompt_meta_fields)), model,
    jurisdiction = as.character(jurisdiction_f),
    across(starts_with("rv_")), genuine_refusal, capability_failure,
    substantive_pivot, annotation_source = "Luna v2.4 original census",
    generation_provider_request_id = NA_character_,
    generation_response_sha256 = NA_character_, corpus = "original_v1")

common <- intersect(names(old_rows), names(new_rows))
expanded <- bind_rows(old_rows |> select(all_of(common)),
                      new_rows |> select(all_of(common)))
stopifnot(nrow(expanded) == 224544L, !anyDuplicated(expanded[KEY]),
          n_distinct(expanded$model) == 18L,
          setequal(unique(new_rows$model), names(NEW_JURIS)))

out_path <- file.path(OUT_DIR, "expanded_panel_v3.rds")
saveRDS(expanded, out_path, compress = "xz")

manifest <- list(
  version = "expanded-panel-v3-with-kimi",
  created_at = format(Sys.time(), tz = "UTC", usetz = TRUE),
  scientific_status = paste(
    "complete seven-model expansion analysis; original canonical release unchanged;",
    "one Gemini provider response and one Kimi annotation are explicitly missing"),
  rows = nrow(expanded), models = n_distinct(expanded$model),
  original_rows = nrow(old_rows), expansion_rows = nrow(new_rows),
  model_counts = as.list(table(expanded$model)),
  excluded_missing_labels = annotation_missing,
  outcome_counts = list(
    genuine_refusal = sum(expanded$genuine_refusal),
    capability_failure = sum(expanded$capability_failure)),
  input_sha256 = list(
    batch1_index = sha("annotations/model_expansion_v3/luna_v2_4_completed_batch1/response_index.parquet"),
    batch1_results = sha("annotations/model_expansion_v3/luna_v2_4_completed_batch1/results.jsonl"),
    batch2_index = sha("annotations/model_expansion_v3/luna_v2_4_completed_batch2/response_index.parquet"),
    batch2_results = sha("annotations/model_expansion_v3/luna_v2_4_completed_batch2/results.jsonl"),
    batch3_index = sha("annotations/model_expansion_v3/luna_v2_4_kimi_batch3/response_index.parquet"),
    batch3_results = sha("annotations/model_expansion_v3/luna_v2_4_kimi_batch3/results.jsonl")),
  output_sha256 = sha(out_path))
jsonlite::write_json(manifest,
  file.path(OUT_DIR, "expanded_panel_v3_manifest.json"),
  pretty = TRUE, auto_unbox = TRUE)
cat(sprintf("Wrote %s rows across %s models to %s\n",
            format(nrow(expanded), big.mark = ","), n_distinct(expanded$model), out_path))
