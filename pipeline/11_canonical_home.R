# =============================================================================
# Technical reference: docs/r_pipeline/11_canonical_home.md
# HOME-REGION ANALYSIS -- final Luna v2.4 outcomes
# =============================================================================
# Primary estimand: within each developer jurisdiction, the weighted mean of
# m(1,X)-m(0,X), where m is a jurisdiction-specific logistic regression and
# weights give equal total weight to models, issues within models, and prompts
# within model-issue cells. This is predictive standardization, not causality.
#
# Outcomes: genuine_refusal (primary) and capability_failure (separate
# diagnostic). Original non-engagement is retained only in c07 on the eleven
# models for which the original Gemini label exists.
# Sample: English responses on home/away issues; General is never coded away.
# Inference: fixed-count issue-cluster percentile bootstrap; failures retained.
# Outputs: c02-c07 CSV files and run-scoped c18 bootstrap diagnostics.
# External effects: local reads and CSV writes only; no provider call.

source("pipeline/10_canonical_common.R")
suppressPackageStartupMessages(library(tidyverse))

B_PRIMARY <- as.integer(Sys.getenv("CANON_B_HEAD", "2000"))
B_SENS <- as.integer(Sys.getenv("CANON_B_SENS", "500"))
OUTCOMES <- c("genuine_refusal", "capability_failure")
OUTCOME_ROLE <- c(genuine_refusal = "primary",
                  capability_failure = "diagnostic")
SUPPORT_COLS <- c("model", "domain", "route_f", "tier")
ENG <- CANON_ENGLISH
ENG_HA <- ENG |> filter(home_status %in% c("home", "away"))

cat(strrep("=", 78), "\nHOME-REGION ANALYSIS: LUNA v2.4\n",
    strrep("=", 78), "\n", sep = "")

weighted_arm_difference <- function(d, outcome, wfun = w_equal_model) {
  issue_col <- if ("bootstrap_issue_instance" %in% names(d))
    "bootstrap_issue_instance" else "issue_id"
  h <- d[d$home_status == "home", , drop = FALSE]
  a <- d[d$home_status == "away", , drop = FALSE]
  if (!nrow(h) || !nrow(a)) return(NA_real_)
  sum(wfun(h, issue_col = issue_col) * h[[outcome]]) -
    sum(wfun(a, issue_col = issue_col) * a[[outcome]])
}

descriptive_difference <- function(d, outcome, label, B = B_SENS) {
  bt <- boot_canon(d, function(x) weighted_arm_difference(x, outcome),
                   B = B, label = label)
  record_diag(bt$diag)
  tibble(estimate = bt$estimate, conf_low = bt$conf_low,
         conf_high = bt$conf_high, estimate_pp = pp(bt$estimate),
         conf_low_pp = pp(bt$conf_low), conf_high_pp = pp(bt$conf_high),
         interval_reliable = bt$interval_reliable,
         replicate_failure_rate = bt$failure_rate)
}

standardized_row <- function(d, outcome, jurisdiction, weighting = "nested",
                             support = "full target", B = B_PRIMARY, label) {
  wfun <- switch(weighting, nested = w_nested, response = w_response,
                 stop("unknown weighting: ", weighting))
  why <- estimable_chk(d, outcome)
  base <- tibble(
    jurisdiction = jurisdiction, outcome = outcome,
    outcome_role = unname(OUTCOME_ROLE[outcome]), weighting = weighting,
    support = support, n = nrow(d), n_issues = n_distinct(d$issue_id),
    n_models = n_distinct(d$model),
    events_home = sum(d[[outcome]][d$home == 1]),
    events_away = sum(d[[outcome]][d$home == 0]))
  if (nzchar(why)) return(base |> mutate(
    standardized_home_risk = NA_real_, standardized_away_risk = NA_real_,
    standardized_home_risk_pp = NA_real_, standardized_away_risk_pp = NA_real_,
    estimate = NA_real_, conf_low = NA_real_, conf_high = NA_real_,
    estimate_pp = NA_real_, conf_low_pp = NA_real_, conf_high_pp = NA_real_,
    estimable = FALSE, interval_reliable = FALSE,
    replicate_failure_rate = NA_real_, glm_warnings = "", note = why))

  probe <- fit_logit(build_f(d, outcome), d)
  diag <- sep_diagnose(probe$fit, wfun(d))
  if (diag$blocking) return(base |> mutate(
    standardized_home_risk = NA_real_, standardized_away_risk = NA_real_,
    standardized_home_risk_pp = NA_real_, standardized_away_risk_pp = NA_real_,
    estimate = NA_real_, conf_low = NA_real_, conf_high = NA_real_,
    estimate_pp = NA_real_, conf_low_pp = NA_real_, conf_high_pp = NA_real_,
    estimable = FALSE, interval_reliable = FALSE,
    replicate_failure_rate = NA_real_,
    glm_warnings = paste(unique(probe$warnings), collapse = " | "),
    note = paste("undefined fit:", diag$why)))

  bt <- boot_canon(d, function(x) gcomp(x, wfun, outcome), B = B,
                   label = label)
  record_diag(bt$diag)
  lv <- gcomp(d, wfun, outcome, return_levels = TRUE)
  base |> mutate(
    standardized_home_risk = unname(lv["home_risk"]),
    standardized_away_risk = unname(lv["away_risk"]),
    standardized_home_risk_pp = pp(standardized_home_risk),
    standardized_away_risk_pp = pp(standardized_away_risk),
    estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high,
    estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
    conf_high_pp = pp(bt$conf_high), estimable = is.finite(bt$estimate),
    interval_reliable = bt$interval_reliable,
    replicate_failure_rate = bt$failure_rate,
    glm_warnings = paste(unique(probe$warnings), collapse = " | "),
    note = if (bt$interval_reliable) "" else
      sprintf("interval unreliable: %.1f%% failed planned draws",
              100 * bt$failure_rate))
}

# A. Raw rates and unadjusted differences --------------------------------------
c02_cells <- ENG |> group_by(jurisdiction = as.character(juris), home_status) |>
  summarise(n = n(), n_issues = n_distinct(issue_id),
            across(all_of(OUTCOMES), list(events = sum, rate = mean)),
            .groups = "drop") |>
  pivot_longer(matches("_(events|rate)$"),
               names_to = c("outcome", ".value"),
               names_pattern = "(.*)_(events|rate)") |>
  mutate(quantity = "observed rate", estimate = rate,
         estimate_pp = pp(rate), weighting = "response")

c02_diff <- map_dfr(JURIS_C, function(j) {
  d <- ENG_HA |> filter(juris == j)
  map_dfr(OUTCOMES, function(y) {
    descriptive_difference(d, y, sprintf("c02|%s|%s", j, y),
                           if (y == "genuine_refusal") B_PRIMARY else B_SENS) |>
      mutate(jurisdiction = j, outcome = y, quantity = "home minus away",
             n = nrow(d), n_issues = n_distinct(d$issue_id),
             weighting = "equal model")
  })
})
c02 <- bind_rows(c02_cells, c02_diff) |> mutate(
  outcome_role = unname(OUTCOME_ROLE[outcome]), sample = "English",
  estimand = if_else(quantity == "observed rate", "raw response-cell rate",
                     "unadjusted equal-model home-minus-away difference"),
  general_handling = "general is separate and never away",
  causal_interpretation = "none", canonical_run_id = CANONICAL_RUN_ID)
write_csv(c02, file.path(CAN_EST, "c02_home_descriptive_english.csv"))

c03 <- canon |> group_by(jurisdiction = as.character(juris),
                          language = as.character(lang), home_status) |>
  summarise(n = n(), n_issues = n_distinct(issue_id),
            across(all_of(OUTCOMES), list(events = sum, rate = mean)),
            .groups = "drop") |>
  pivot_longer(matches("_(events|rate)$"),
               names_to = c("outcome", ".value"),
               names_pattern = "(.*)_(events|rate)") |>
  mutate(estimate = rate, estimate_pp = pp(rate),
         outcome_role = unname(OUTCOME_ROLE[outcome]),
         sample = "all delivered languages; descriptive only",
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(c03, file.path(CAN_EST,
                         "c03_home_descriptive_all_languages_supplement.csv"))

# B. Standardized jurisdiction and model contrasts ----------------------------
c04 <- map_dfr(JURIS_C, function(j) {
  d <- ENG_HA |> filter(juris == j) |> droplevels()
  map_dfr(OUTCOMES, function(y)
    standardized_row(d, y, j,
      B = if (y == "genuine_refusal") B_PRIMARY else B_SENS,
      label = sprintf("c04|%s|%s|nested", j, y)))
}) |> mutate(
  formula = paste("OUTCOME ~ home * model + tier + domain + route;",
                  "home + covariates for a single-model jurisdiction"),
  standardization_target = paste("English home/away rows; equal model;",
    "within model equal issue; within model-issue equal prompt"),
  uncertainty = "issue-cluster percentile bootstrap; fixed draws; failures retained",
  causal_interpretation = paste("predictive standardization only; adjustment",
    "does not remove unmeasured home/away issue differences"),
  canonical_run_id = CANONICAL_RUN_ID)
write_csv(c04, file.path(CAN_EST, "c04_home_standardized.csv"))

c05 <- map_dfr(sort(unique(as.character(ENG_HA$model))), function(m) {
  d <- ENG_HA |> filter(model == m) |> droplevels()
  j <- as.character(d$juris[1])
  map_dfr(c("genuine_refusal", "capability_failure"), function(y)
    standardized_row(d, y, j, B = B_SENS,
                     label = sprintf("c05|%s|%s", m, y)) |>
      mutate(model = m))
}) |> mutate(
  estimand = "model-specific standardized home-minus-away predictive contrast",
  multiplicity = "exploratory model heterogeneity; no multiplicity adjustment",
  canonical_run_id = CANONICAL_RUN_ID)
write_csv(c05, file.path(CAN_EST, "c05_home_by_model.csv"))

# C. Positivity and common support ---------------------------------------------
c06 <- map_dfr(JURIS_C, function(j) {
  d <- ENG_HA |> filter(juris == j) |> droplevels()
  support_cells(d, SUPPORT_COLS) |> mutate(jurisdiction = j, .before = 1)
}) |> mutate(support_definition = paste(SUPPORT_COLS, collapse = " x "),
             canonical_run_id = CANONICAL_RUN_ID)
write_csv(c06, file.path(CAN_EST, "c06_home_overlap.csv"))

c06b <- map_dfr(JURIS_C, function(j) {
  d <- ENG_HA |> filter(juris == j) |> droplevels()
  restrict_support(d, SUPPORT_COLS)$diag |> mutate(jurisdiction = j, .before = 1)
}) |> mutate(unsupported_target_weight = 1 - target_weight_retained,
             canonical_run_id = CANONICAL_RUN_ID)
write_csv(c06b, file.path(CAN_EST, "c06b_common_support_diagnostics.csv"))

# D. Sensitivities; `changed` prevents unlike targets being conflated ---------
c07 <- map_dfr(JURIS_C, function(j) {
  d <- ENG_HA |> filter(juris == j) |> droplevels()
  ds <- restrict_support(d, SUPPORT_COLS)$data |> droplevels()
  # The original Gemini measure was not collected for expansion models. Its
  # sensitivity target is therefore the original eleven-model panel, stated
  # explicitly rather than represented by zeros or silently dropped by glm().
  d_original <- d |> filter(!is.na(original_nonengagement)) |> droplevels()
  bind_rows(
    standardized_row(d, "genuine_refusal", j, weighting = "response",
                     B = B_SENS, label = sprintf("c07|%s|response", j)) |>
      mutate(sensitivity = "response weighting",
             changed = "standardization target weights"),
    standardized_row(ds, "genuine_refusal", j, support = "common support",
                     B = B_SENS, label = sprintf("c07|%s|support", j)) |>
      mutate(sensitivity = "common support",
             changed = "target population restricted to jointly observed cells"),
    standardized_row(d_original, "original_nonengagement", j, B = B_SENS,
                     label = sprintf("c07|%s|original", j)) |>
      mutate(sensitivity = "original Gemini outcome",
             changed = paste("outcome definition and roster; original eleven",
                             "models only because expansion has no Gemini labels")))
}) |> mutate(
  estimand = "standardized home-minus-away predictive contrast",
  causal_interpretation = "none", canonical_run_id = CANONICAL_RUN_ID)
write_csv(c07, file.path(CAN_EST, "c07_home_sensitivities.csv"))

flush_diag()
cat(sprintf("wrote c02-c07; %d standardized jurisdiction rows\n", nrow(c04)))
