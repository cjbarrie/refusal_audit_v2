# =============================================================================
# Technical reference: docs/r_pipeline/18_measurement_validation.md
# TORCH MEASUREMENT VALIDATION -- frozen probability audit against Sol v2.4
# =============================================================================
# This stage imports, verifies, and republishes the design-weighted validation
# results for the four Torch-generated models. Luna remains the complete-census
# outcome used by every substantive estimator. Sol is a frontier-model reference
# observed on a probability sample; it is not substituted into response rows and
# is not described as human ground truth.

suppressPackageStartupMessages({
  library(readr); library(dplyr); library(jsonlite); library(digest)
})

CAN_EST <- Sys.getenv("CANON_EST_DIR", "pipeline/estimates/canonical")
dir.create(CAN_EST, showWarnings = FALSE, recursive = TRUE)
source("pipeline/_expansion_input.R")

audit <- EXP_ROSTER$sol_audits[[1]]
root <- audit$path
summary_path <- file.path(root, "summary.json")
manifest_path <- file.path(root, "final_annotations_manifest.json")
agreement_path <- file.path(root, "design_weighted_agreement.csv")
estimates_path <- file.path(root, "design_based_model_language_estimates.csv")
results_path <- file.path(root, "final_results.jsonl")
required <- c(summary_path, manifest_path, agreement_path, estimates_path, results_path)
if (!all(file.exists(required))) stop("measurement-validation artifacts are incomplete")

summary <- read_json(summary_path, simplifyVector = TRUE)
manifest <- read_json(manifest_path, simplifyVector = TRUE)
sha <- function(x) digest(x, algo = "sha256", file = TRUE)
if (!isTRUE(manifest$schema_gate_pass) || manifest$n_incomplete != 0L ||
    manifest$n_completed != audit$n || summary$audit_n != audit$n ||
    summary$weighted_population_n != audit$population_n ||
    sha(results_path) != audit$final_results_sha256 ||
    sha(results_path) != manifest$final_results_sha256 ||
    sha(agreement_path) != summary$artifact_sha256[["design_weighted_agreement.csv"]] ||
    sha(estimates_path) != summary$artifact_sha256[["design_based_model_language_estimates.csv"]]) {
  stop("measurement-validation hash/count/schema contract failed")
}

c28 <- tibble(
  audit_version = summary$version,
  audit_n = summary$audit_n,
  target_population_n = summary$weighted_population_n,
  selection_luna_refusal_census = summary$selection_counts$luna_genuine_refusal_census,
  selection_luna_unassessable_census = summary$selection_counts$luna_refusal_unassessable_census,
  selection_capability_probability_sample = summary$selection_counts$luna_capability_failure_probability_sample,
  selection_clean_probability_sample = summary$selection_counts$luna_apparently_clean_probability_sample,
  reference_model = "openai/gpt-5.6-sol",
  primary_census_model = "openai/gpt-5.6-luna",
  provider_cost_usd = summary$provider_cost_usd,
  inference = paste("Design weights recover the 49,879-response Torch population;",
                    "Sol is a frontier-model reference, not human ground truth."),
  final_results_sha256 = audit$final_results_sha256)
write_csv(c28, file.path(CAN_EST, "c28_torch_validation_design.csv"))

c29 <- read_csv(agreement_path, show_col_types = FALSE) |>
  mutate(reference_model = "openai/gpt-5.6-sol",
         weighting = "inverse frozen inclusion probability",
         interpretation = "measurement agreement; not a substantive estimand")
write_csv(c29, file.path(CAN_EST, "c29_torch_design_weighted_agreement.csv"))

c30 <- read_csv(estimates_path, show_col_types = FALSE) |>
  mutate(reference_model = "openai/gpt-5.6-sol",
         weighting = "inverse frozen inclusion probability",
         interpretation = "Luna-versus-Sol measurement sensitivity")
write_csv(c30, file.path(CAN_EST, "c30_torch_design_based_outcomes.csv"))

cat(sprintf("wrote c28-c30; verified %s over %s weighted responses\n",
            format(summary$audit_n, big.mark = ","),
            format(summary$weighted_population_n, big.mark = ",")))
