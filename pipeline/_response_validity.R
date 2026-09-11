# =============================================================================
# Technical reference: docs/r_pipeline/_response_validity.md
# FINAL LUNA v2.4 OUTCOME CONTRACT -- read, verify, and key-join only
# =============================================================================
# Scientific role
#   This helper is the single bridge between the frozen response-validity
#   measurement and the R analysis. Every live outcome analysis reaches Luna
#   v2.4 through attach_final_outcomes(); no estimator reads the Parquet file
#   independently and no R code re-derives the two production outcomes.
#
# Inputs
#   annotations/response_validity_v2_4/wall_to_wall_luna_v1/
#     final_annotations.parquet
#   Override only with RESPONSE_VALIDITY_PATH. A non-default file must still
#   match RESPONSE_VALIDITY_SHA256 (or an explicitly supplied replacement hash).
#
# Unit/key
#   One annotation per (prompt_id, prompt_language, model). The function
#   requires exact key equality with the supplied response frame.
#
# Outputs added to a response frame
#   genuine_refusal       integer 0/1; copied from pred_genuine_refusal
#   capability_failure    integer 0/1; copied from pred_capability_failure
#   original_nonengagement integer 0/1; engagement_code >= 4, sensitivity only
#   substantive_pivot     integer 0/1; task_behavior == coherent_pivot
#   rv_*                   the seven component judgments plus provenance fields
#
# Important measurement rule
#   genuine_refusal and capability_failure are independent and may overlap.
#   Do not recode a capability failure as engagement and do not condition the
#   primary refusal analysis on capability_failure == 0.
#
# External effects
#   None. This file makes no API call and writes no file.

suppressPackageStartupMessages({
  library(dplyr)
  library(arrow)
  library(digest)
})

RV_KEY <- c("prompt_id", "prompt_language", "model")
RV_DEFAULT_PATH <- file.path(
  "annotations", "response_validity_v2_4", "wall_to_wall_luna_v1",
  "final_annotations.parquet")
RV_EXPECTED_SHA256 <- "ce1b6c07de09e96912b034195c2c5ab6f2ef7762fbb103143e02913f1383cf75"
RV_EXPECTED_N <- 137186L
RV_EXPECTED_REFUSALS <- 3591L
RV_EXPECTED_CAPABILITY_FAILURES <- 43317L

rv_stop <- function(...) stop("[Luna v2.4 outcome contract] ", ..., call. = FALSE)

load_final_outcomes <- function(
    path = Sys.getenv("RESPONSE_VALIDITY_PATH", RV_DEFAULT_PATH),
    expected_sha256 = Sys.getenv("RESPONSE_VALIDITY_SHA256", RV_EXPECTED_SHA256)) {
  if (!file.exists(path)) rv_stop("missing file: ", path)
  observed_sha <- digest::digest(path, algo = "sha256", file = TRUE)
  if (!identical(observed_sha, expected_sha256))
    rv_stop("SHA-256 mismatch for ", path, "; expected ", expected_sha256,
            ", observed ", observed_sha)

  # A small number of original model-response strings contain embedded NUL
  # bytes. Arrow preserves them in Parquet, but base R strings cannot represent
  # them and dplyr errors when the affected character vector is sliced. Strip
  # only those invalid bytes at the R boundary; the source file is not changed,
  # its hash is checked above, and none of the structured outcome fields depend
  # on this conversion option.
  old_skip_nul <- getOption("arrow.skip_nul")
  options(arrow.skip_nul = TRUE)
  on.exit(options(arrow.skip_nul = old_skip_nul), add = TRUE)
  x <- arrow::read_parquet(path) |> as.data.frame() |> tibble::as_tibble()
  required <- c(
    RV_KEY, "task_behavior", "substantive_refusal", "stance_disclaimer",
    "epistemic_limitation", "language_fidelity", "output_quality",
    "technical_failure", "confidence", "refusal_evidence_span",
    "decision_note", "annotation_source", "provider_request_id", "created_at",
    "pred_genuine_refusal", "pred_capability_failure")
  absent <- setdiff(required, names(x))
  if (length(absent)) rv_stop("missing columns: ", paste(absent, collapse = ", "))
  if (nrow(x) != RV_EXPECTED_N) rv_stop("expected ", RV_EXPECTED_N,
                                        " rows; found ", nrow(x))
  if (anyDuplicated(x[RV_KEY])) rv_stop("duplicate response keys in final table")
  if (anyNA(x[RV_KEY])) rv_stop("missing response key in final table")
  if (sum(x$pred_genuine_refusal) != RV_EXPECTED_REFUSALS)
    rv_stop("expected ", RV_EXPECTED_REFUSALS, " genuine refusals; found ",
            sum(x$pred_genuine_refusal))
  if (sum(x$pred_capability_failure) != RV_EXPECTED_CAPABILITY_FAILURES)
    rv_stop("expected ", RV_EXPECTED_CAPABILITY_FAILURES,
            " capability failures; found ", sum(x$pred_capability_failure))

  allowed_task <- c("complete", "functionally_complete", "partial",
                    "coherent_pivot", "opposite_position",
                    "no_substantive_output", "unassessable")
  allowed_refusal <- c("none", "implicit", "explicit", "unassessable")
  allowed_language <- c("target", "mixed", "wrong_language", "unassessable")
  allowed_quality <- c("coherent", "partly_coherent", "incoherent_garbled",
                       "unassessable")
  allowed_failure <- c("none", "empty", "truncated", "template_echo",
                       "repetition_loop", "encoding_corruption", "other")
  checks <- list(task_behavior = allowed_task,
                 substantive_refusal = allowed_refusal,
                 language_fidelity = allowed_language,
                 output_quality = allowed_quality,
                 technical_failure = allowed_failure)
  for (field in names(checks)) {
    bad <- setdiff(unique(x[[field]]), checks[[field]])
    if (length(bad)) rv_stop("unexpected ", field, ": ", paste(bad, collapse = ", "))
  }

  names(x)[!names(x) %in% RV_KEY] <- paste0(
    "rv_", names(x)[!names(x) %in% RV_KEY])
  attr(x, "source_path") <- path
  attr(x, "source_sha256") <- observed_sha
  x
}

attach_final_outcomes <- function(responses, outcomes = load_final_outcomes()) {
  # Arrow character columns can remain lazily materialized after read_parquet().
  # Keep the same NUL policy active while dplyr slices them for the join.
  old_skip_nul <- getOption("arrow.skip_nul")
  options(arrow.skip_nul = TRUE)
  on.exit(options(arrow.skip_nul = old_skip_nul), add = TRUE)
  absent <- setdiff(c(RV_KEY, "engagement_code"), names(responses))
  if (length(absent)) rv_stop("response frame lacks: ", paste(absent, collapse = ", "))
  if (anyDuplicated(responses[RV_KEY])) rv_stop("duplicate keys in response frame")

  missing_labels <- dplyr::anti_join(responses[RV_KEY], outcomes[RV_KEY], by = RV_KEY)
  extra_labels <- dplyr::anti_join(outcomes[RV_KEY], responses[RV_KEY], by = RV_KEY)
  if (nrow(missing_labels) || nrow(extra_labels))
    rv_stop("key sets differ: ", nrow(missing_labels), " response(s) lack labels; ",
            nrow(extra_labels), " label(s) lack responses")

  # Idempotence matters because stage 01 saves these columns and stage 10
  # verifies them again. Remove any earlier attachment before the exact join.
  prior <- grep("^rv_", names(responses), value = TRUE)
  responses <- responses |> dplyr::select(-dplyr::any_of(c(
    prior, "genuine_refusal", "capability_failure", "substantive_pivot",
    "original_nonengagement", "response_validity_state")))

  out <- responses |>
    dplyr::left_join(outcomes, by = RV_KEY) |>
    dplyr::mutate(
      genuine_refusal = as.integer(rv_pred_genuine_refusal),
      capability_failure = as.integer(rv_pred_capability_failure),
      substantive_pivot = as.integer(rv_task_behavior == "coherent_pivot"),
      original_nonengagement = as.integer(engagement_code >= 4),
      response_validity_state = dplyr::case_when(
        genuine_refusal == 1L & capability_failure == 1L ~ "refusal and capability failure",
        genuine_refusal == 1L ~ "genuine refusal only",
        capability_failure == 1L ~ "capability failure only",
        TRUE ~ "neither"
      ))
  if (nrow(out) != nrow(responses) || anyNA(out$genuine_refusal) ||
      anyNA(out$capability_failure))
    rv_stop("join changed row count or produced missing outcomes")
  out
}
