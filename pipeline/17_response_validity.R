# =============================================================================
# Technical reference: docs/r_pipeline/17_response_validity.md
# RESPONSE-VALIDITY DESCRIPTIVES -- final Luna v2.4 census
# =============================================================================
# This stage describes the frozen measurement itself. It does not apply DSL,
# impute labels, treat Sol as gold, or overwrite Luna. Every corpus response is
# observed under v2.4, so the tables report realized-corpus counts and shares;
# they do not attach sampling CIs to a complete census. Model-measurement error
# is discussed in the technical pipeline and is not represented by a binomial
# interval around these counts.

source("pipeline/10_canonical_common.R")
suppressPackageStartupMessages(library(tidyverse))

OUTCOMES <- c("genuine_refusal", "capability_failure", "substantive_pivot")

summarize_outcomes <- function(d, scope, ...) {
  d |> group_by(...) |> summarise(
    n = n(),
    across(all_of(OUTCOMES), list(events = sum, rate = mean)),
    .groups = "drop") |>
    pivot_longer(matches("_(events|rate)$"),
                 names_to = c("outcome", ".value"),
                 names_pattern = "(.*)_(events|rate)") |>
    mutate(scope = scope, rate_pp = pp(rate))
}

c23 <- bind_rows(
  summarize_outcomes(canon, "overall"),
  summarize_outcomes(canon, "model", model),
  summarize_outcomes(canon, "language", language = lang),
  summarize_outcomes(canon, "developer jurisdiction", jurisdiction = juris),
  summarize_outcomes(canon, "prompt tier", tier),
  summarize_outcomes(canon, "topic domain", domain),
  summarize_outcomes(canon, "issue region", region_focus)) |>
  mutate(measurement = case_when(
    TRUE ~ "Luna v2.4 wall-to-wall annotation"),
    uncertainty = paste("complete realized-corpus description; no sampling CI;",
                        "machine-measurement uncertainty is separate"),
    canonical_run_id = CANONICAL_RUN_ID)
write_csv(c23, file.path(CAN_EST, "c23_response_validity_prevalence.csv"))

# The historical Gemini outcome is observed only in the original corpus. Keep a
# separate table so its denominator and eleven-model roster cannot be mistaken
# for the 20-model Luna census.
original_rows <- canon |> filter(!is.na(original_nonengagement))
summarize_original <- function(d, scope, ...) d |> group_by(...) |>
  summarise(n = n(), events = sum(original_nonengagement),
            rate = mean(original_nonengagement), .groups = "drop") |>
  mutate(scope = scope, outcome = "original_nonengagement", rate_pp = pp(rate))
c23b <- bind_rows(
  summarize_original(original_rows, "overall"),
  summarize_original(original_rows, "model", model),
  summarize_original(original_rows, "language", language = lang),
  summarize_original(original_rows, "developer jurisdiction", jurisdiction = juris),
  summarize_original(original_rows, "prompt tier", tier),
  summarize_original(original_rows, "topic domain", domain),
  summarize_original(original_rows, "issue region", region_focus)) |>
  mutate(measurement = "original Gemini judge-coded non-engagement; sensitivity only",
         sample = "original eleven-model corpus",
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(c23b, file.path(CAN_EST,
                          "c23b_original_nonengagement_prevalence.csv"))

# The two adopted v2.4 outcomes are independent, so report their overlap rather
# than presenting them as an exhaustive multinomial outcome.
c24 <- canon |> count(response_validity_state, name = "n") |>
  mutate(share = n / sum(n), share_pp = pp(share),
         note = "genuine refusal and capability failure may overlap",
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(c24, file.path(CAN_EST, "c24_response_validity_overlap.csv"))

# Component-field marginals make the derived binary outcomes auditable.
component_fields <- c("rv_task_behavior", "rv_substantive_refusal",
                      "rv_language_fidelity", "rv_output_quality",
                      "rv_technical_failure", "rv_confidence",
                      "rv_annotation_source")
c25 <- map_dfr(component_fields, function(field) {
  canon |> count(value = .data[[field]], name = "n") |>
    mutate(field = field, share = n / sum(n), .before = 1)
}) |> mutate(canonical_run_id = CANONICAL_RUN_ID)
write_csv(c25, file.path(CAN_EST, "c25_response_validity_components.csv"))

# Explicit run contract copied into a small analysis-facing table. Hashes remain
# authoritative in the frozen JSON manifest; this table lets acceptance check
# them without parsing prose.
c26 <- tibble(
  annotation_version = "combined-original-and-expansion-luna-v2.4-v1",
  model = "openai/gpt-5.6-luna", n = nrow(canon),
  unique_keys = nrow(distinct(canon, across(all_of(RV_KEY)))),
  genuine_refusal_n = sum(canon$genuine_refusal),
  capability_failure_n = sum(canon$capability_failure),
  original_annotations_sha256 = RV_EXPECTED_SHA256,
  expansion_rows = EXP_EXPECTED_EXPANSION_ROWS,
  known_unobserved_generation_rows = 1L,
  known_unresolved_annotation_rows = 1L,
  repair_n = 129L, repair_model = "openai/gpt-5.6-luna",
  sol_repair_used = FALSE, human_gold_standard = FALSE,
  canonical_run_id = CANONICAL_RUN_ID)
write_csv(c26, file.path(CAN_EST, "c26_response_validity_contract.csv"))

# How the original binary measurement maps into the final two-dimensional
# outcome state. Shares are conditional on the original label, so each original
# row sums to one and can be drawn without implying a flow model or adjudication.
c27 <- canon |>
  filter(!is.na(original_nonengagement)) |>
  mutate(original_measurement = if_else(
    original_nonengagement == 1L,
    "Original judge-coded non-engagement",
    "Original engaged/partial")) |>
  count(original_measurement, response_validity_state, name = "n") |>
  group_by(original_measurement) |>
  mutate(original_total = sum(n), share_within_original = n / original_total,
         share_within_original_pp = pp(share_within_original)) |>
  ungroup() |>
  mutate(share_of_corpus = n / sum(n), share_of_corpus_pp = pp(share_of_corpus),
         interpretation = paste("descriptive reclassification table; final",
           "states may contain both genuine refusal and capability failure"),
         canonical_run_id = CANONICAL_RUN_ID)
stopifnot(all(abs(c27 |> group_by(original_measurement) |>
  summarise(s = sum(share_within_original)) |> pull(s) - 1) < 1e-12))
write_csv(c27, file.path(CAN_EST, "c27_annotation_transition.csv"))

cat(sprintf("wrote c23-c27 for %s complete Luna v2.4 responses\n",
            format(nrow(canon), big.mark = ",")))
