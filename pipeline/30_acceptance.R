# =============================================================================
# Technical reference: docs/r_pipeline/30_acceptance.md
# RELEASE ACCEPTANCE -- final Luna v2.4 analysis contract
# =============================================================================
# Read-only gate over already-produced tables and PNGs. It never estimates,
# renders, annotates or calls a provider. Every check is written to c01b before
# a non-zero exit. Historical pre-v2.4 releases such as `canon_012` are expected
# to fail this contract and are never altered to make them pass.

source("pipeline/10_canonical_common.R")
suppressPackageStartupMessages(library(tidyverse))

READONLY <- identical(Sys.getenv("CANON_ACCEPT_READONLY", "0"), "1")
results <- list()
chk <- function(id, description, pass, detail = "") {
  pass <- isTRUE(pass)
  results[[length(results) + 1L]] <<- tibble(
    check_id = id, description = description,
    status = if (pass) "PASS" else "FAIL", detail = as.character(detail),
    canonical_run_id = CANONICAL_RUN_ID)
  cat(sprintf("[%s] %s: %s%s\n", id, if (pass) "PASS" else "FAIL",
              description, if (nzchar(detail)) paste0(" -- ", detail) else ""))
  invisible(pass)
}
rd <- function(file) {
  p <- file.path(CAN_EST, file)
  if (!file.exists(p)) return(NULL)
  read_csv(p, show_col_types = FALSE)
}

# A. Measurement and sample ----------------------------------------------------
chk("A1", "analysis has 249,201 unique response keys across 20 models",
    nrow(canon) == EXP_EXPECTED_N && n_distinct(canon$model) == EXP_EXPECTED_MODELS &&
      !anyDuplicated(canon[RV_KEY]))
chk("A2", "final v2.4 hash is the frozen accepted hash",
    identical(digest::digest(Sys.getenv("RESPONSE_VALIDITY_PATH", RV_DEFAULT_PATH),
                             "sha256", file = TRUE), RV_EXPECTED_SHA256))
chk("A3", "combined genuine-refusal count is 6,794",
    sum(canon$genuine_refusal) == EXP_EXPECTED_REFUSALS)
chk("A4", "combined capability-failure count is 60,968",
    sum(canon$capability_failure) == EXP_EXPECTED_CAPABILITY_FAILURES)
original_rows <- canon |> filter(!is.na(original_nonengagement))
chk("A5", "original-label sensitivity is confined to and exact for 137,186 rows",
    nrow(original_rows) == 137186L &&
      all(original_rows$original_nonengagement ==
            as.integer(original_rows$engagement_code >= 4)))
chk("A6", "refusal and capability failure are allowed to overlap",
    sum(canon$genuine_refusal & canon$capability_failure) >= 0L,
    paste("overlap n =", sum(canon$genuine_refusal & canon$capability_failure)))

# B. Required tables -----------------------------------------------------------
required <- c(
  "c02_home_descriptive_english.csv",
  "c03_home_descriptive_all_languages_supplement.csv",
  "c04_home_standardized.csv", "c05_home_by_model.csv",
  "c06_home_overlap.csv", "c06b_common_support_diagnostics.csv",
  "c07_home_sensitivities.csv", "c08_language_paired.csv",
  "c08b_weighting_comparison.csv",
  "c08c_original_nonengagement_sensitivity.csv",
  "c09_language_by_model.csv",
  "c10_framing_paired.csv", "c10b_framing_incomplete_blocks.csv",
  "c10c_original_nonengagement_sensitivity.csv",
  "c11_framing_by_model.csv", "c21_subsample_summary.csv",
  "c21_subsample_draws.csv.gz",
  "c22_prompt_umap_coordinates.csv",
  "c22_prompt_outcome_propensities.csv",
  "c22_prompt_outcomes_by_model.csv",
  "c22b_prompt_concentration.csv",
  "c22c_prompt_cross_model_counts.csv",
  "c22d_prompt_cross_model_distribution.csv",
  "c23_response_validity_prevalence.csv",
  "c24_response_validity_overlap.csv",
  "c25_response_validity_components.csv",
  "c26_response_validity_contract.csv",
  "c27_annotation_transition.csv",
  "c23b_original_nonengagement_prevalence.csv")
missing <- required[!file.exists(file.path(CAN_EST, required))]
chk("B1", "all required v2.4 estimate tables exist", !length(missing),
    paste(missing, collapse = ", "))

# C. Home contract -------------------------------------------------------------
c04 <- rd("c04_home_standardized.csv")
chk("C1", "home table has 5 jurisdictions x 2 distinct current outcomes",
    !is.null(c04) && nrow(c04) == 10L &&
      setequal(c04$outcome, c("genuine_refusal", "capability_failure")) &&
      !anyDuplicated(c04[c("jurisdiction", "outcome")]))
chk("C2", "home primary rows are nested full-target predictive contrasts",
    !is.null(c04) && all(c04$weighting == "nested") &&
      all(c04$support == "full target") &&
      all(grepl("predictive standardization", c04$causal_interpretation)))
chk("C3", "finite home estimates are probability differences",
    !is.null(c04) && all(abs(c04$estimate[is.finite(c04$estimate)]) <= 1))
chk("C3b", "standardized home and away risks reproduce the contrast",
    !is.null(c04) && all(c04$standardized_home_risk >= 0 &
      c04$standardized_home_risk <= 1, na.rm = TRUE) &&
      all(c04$standardized_away_risk >= 0 & c04$standardized_away_risk <= 1,
          na.rm = TRUE) &&
      all(abs((c04$standardized_home_risk - c04$standardized_away_risk) -
                c04$estimate) < 1e-10, na.rm = TRUE))
c06b <- rd("c06b_common_support_diagnostics.csv")
chk("C4", "common-support diagnostics report retained target weight",
    !is.null(c06b) && nrow(c06b) == 5L &&
      all(c06b$target_weight_retained >= 0 & c06b$target_weight_retained <= 1))

# D. Language and framing contracts -------------------------------------------
c08 <- rd("c08_language_paired.csv")
chk("D1", "language table has 4 contrasts x 2 current outcomes",
    !is.null(c08) && nrow(c08) == 8L &&
      !anyDuplicated(c08[c("language", "outcome")]))
chk("D2", "language blocks are complete prompt/model pairs",
    !is.null(c08) && all(c08$n_complete_blocks > 0) &&
      all(c08$block == "model x prompt_id"))
chk("D3", "language estimates are bounded differences",
    !is.null(c08) && all(abs(c08$estimate) <= 1, na.rm = TRUE))
chk("D3b", "paired language arm levels reproduce each contrast",
    !is.null(c08) && all(abs((c08$mean_target - c08$mean_english) -
                               c08$estimate) < 1e-10, na.rm = TRUE))
c10 <- rd("c10_framing_paired.csv")
chk("D4", "framing table has the same two current outcomes",
    !is.null(c10) && nrow(c10) == 2L &&
      setequal(c10$outcome, c("genuine_refusal", "capability_failure")))
chk("D5", "framing primary requires complete 2+2 English blocks",
    !is.null(c10) && all(c10$sample == "English complete 2+2 blocks"))
chk("D6", "equal-model framing arm levels reproduce each contrast",
    !is.null(c10) && all(abs((c10$mean_boundary - c10$mean_regular) -
                               c10$estimate) < 1e-10, na.rm = TRUE))

# E. Stability and exploratory geometry ---------------------------------------
c21 <- rd("c21_subsample_summary.csv")
chk("E1", "stability uses only current v2.4 outcomes",
    !is.null(c21) && setequal(unique(c21$outcome),
                             c("genuine_refusal", "capability_failure")))
chk("E2", "stability ranges are explicitly not confidence intervals",
    !is.null(c21) && all(grepl("NOT a confidence interval", c21$interval_type)))
c22 <- rd("c22_prompt_umap_coordinates.csv")
if (!is.null(c22)) {
  chk("E3", "UMAP has one coordinate per 2,496 prompts",
      nrow(c22) == 2496L && !anyDuplicated(c22$prompt_id))
  chk("E4", "UMAP carries v2.4 refusal and capability propensities",
      all(paste0("genuine_refusal_", ORDER_LANG) %in% names(c22)) &&
      all(paste0("capability_failure_", ORDER_LANG) %in% names(c22)))
  chk("E4b", "region atlas has six balanced 416-prompt strata",
      setequal(unique(c22$region_focus), ORDER_REGION) &&
        all(c22 |> count(region_focus) |> pull(n) == 416L))
}
c27 <- rd("c27_annotation_transition.csv")
chk("E5", "original-to-final transition rows sum to one within original label",
    !is.null(c27) && n_distinct(c27$original_measurement) == 2L &&
      all(abs(c27 |> group_by(original_measurement) |>
        summarise(s = sum(share_within_original)) |> pull(s) - 1) < 1e-10))

# F. Figures and pending separation -------------------------------------------
main_expected <- c("Fig1_jurisdiction_refusal_atlas_home.png",
                   "Fig2_language_refusal_atlas_contrasts.png")
main_found <- sort(list.files(CAN_FIG, pattern = "[.]png$"))
chk("F1", "main figure inventory is exactly two PNGs",
    identical(sort(main_expected), main_found), paste(main_found, collapse = ", "))
extended_expected <- c(
  "ED1_home_absolute_risks_genuine_refusal.png",
  "ED2_home_absolute_risks_capability_failure.png",
  "ED3_language_absolute_rates_genuine_refusal.png",
  "ED4_language_absolute_rates_capability_failure.png",
  "ED5_measurement_reclassification.png",
  "ED6_annotation_component_profile.png",
  "ED7_model_specific_contrasts_genuine_refusal.png",
  "ED8_model_specific_contrasts_capability_failure.png",
  "ED9_content_fingerprint_genuine_refusal.png",
  "ED10_content_fingerprint_capability_failure.png",
  "ED11_prompt_distribution_genuine_refusal.png",
  "ED12_prompt_distribution_capability_failure.png")
if (!is.null(c22)) extended_expected <- c(extended_expected,
  "ED13_capability_failure_semantic_atlas.png",
  "ED14_genuine_refusal_semantic_atlas_by_model.png")
extended_found <- sort(list.files(CAN_APP_FIG, pattern = "[.]png$"))
chk("F2", "extended figure inventory contains only supported analyses",
    identical(sort(extended_expected), extended_found),
    paste(extended_found, collapse = ", "))
active_code <- paste(vapply(list.files("pipeline", pattern = "[.]R$", full.names = TRUE),
                           function(p) paste(readLines(p, warn = FALSE), collapse = "\n"),
                           character(1)), collapse = "\n")
chk("F3", "live root scripts never source pipeline/pending",
    !grepl("source\\([\"']pipeline/pending", active_code))

# G. Documentation surface -----------------------------------------------------
active_scripts <- list.files("pipeline", pattern = "[.]R$", full.names = TRUE)
missing_header <- active_scripts[!vapply(active_scripts, function(p)
  any(grepl("Technical reference: docs/r_pipeline/", head(readLines(p, warn = FALSE), 20))),
  logical(1))]
chk("G1", "every active root R script links a technical reference",
    !length(missing_header), paste(missing_header, collapse = ", "))

out <- bind_rows(results)
if (!READONLY) write_csv(out, file.path(CAN_EST, "c01b_acceptance_tests.csv"))
cat(sprintf("\nAcceptance: %d/%d passed\n", sum(out$status == "PASS"), nrow(out)))
if (any(out$status == "FAIL")) quit(save = "no", status = 1)
