# =============================================================================
# v2 analysis layer -- SHARED FOUNDATION  (sourced by 41-46; not run alone)
# =============================================================================
# Builds the analysis sample, the exclusion ledger, the outcome definitions, the
# weighting schemes and the issue-cluster bootstrap used by every v2 estimand.
#
# SCOPE RULES FOR THIS LAYER
#   * Reads only. Nothing here writes to prompts/, responses/ or annotations/.
#   * Writes ONLY new e32-e40 files. Existing e01/e29/e30/e31 are never touched.
#   * Calls no API and no model endpoint.
#
# -----------------------------------------------------------------------------
# THREE ESTIMAND FAMILIES, KEPT SEPARATE ON PURPOSE
# -----------------------------------------------------------------------------
#   A (41_)  DESCRIPTIVE home results        -- counts and rates, no model
#   B (42_)  STANDARDIZED home contrasts     -- covariate-standardized, NOT causal
#   C (43_)  PROMPT-FIXED language effects   -- paired within model x prompt
#
# Family B is a *covariate-standardized contrast*. It is NOT a causal effect, NOT
# a difference-in-differences and NOT a within-issue effect: `home` is a fixed
# property of the issue's region, so nothing about this design randomises it and
# no issue-level comparison identifies it. The labels in the output tables say so
# explicitly, and 46_v2_acceptance_tests.R fails the build if any v2 output
# describes them otherwise.

suppressPackageStartupMessages({
  library(tidyverse); library(digest)
})
select <- dplyr::select
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())

EST     <- "pipeline/estimates"
RUN_DIR <- Sys.getenv("REFUSAL_RUN_DIR", "annotations/full_v1")
V2_SEED <- 20260806L
dir.create(EST, showWarnings = FALSE, recursive = TRUE)

# -----------------------------------------------------------------------------
# Exclusion ledger -- recorded, never silently dropped
# -----------------------------------------------------------------------------
# Established by reconciling responses -> annotations -> assembled surfaces
# (see 45_v2_reconciliation.R, which recomputes these from the artifacts).
# The two most recent generation failures are named explicitly as required.
V2_EXCLUSIONS <- tribble(
  ~prompt_id,                              ~prompt_language, ~model,        ~reason,                           ~detail,
  "issue_Q10932254__bndA",                 "hi", "allam-7b",    "generation_failed_latest",
    "2026-08-04T22:11:36Z HTTP 400: prompt exceeded the served context window",
  "issue_christina_bobb_Q122179069__reg2", "hi", "falcon3-10b", "generation_failed_latest",
    "2026-08-04T14:25:10Z empty response content (model returned no text)",
  "issue_Q30895__reg2",                    "hi", "jais-8b",     "response_never_annotated",
    "generation succeeded; no clean Pass-1 verdict exists for this key",
  "issue_Q16000984__reg2",                 "en", "gpt-4o",      "annotation_superseded_by_error",
    "a clean verdict was followed by a later error row for the same key; assemble is last-wins, so the row is absent from the assembled surfaces"
)
# 92 (prompt_id, language, model) keys were attempted but never produced a
# successful response at all. They are enumerated in e40 rather than listed here.

# -----------------------------------------------------------------------------
# Analysis sample
# -----------------------------------------------------------------------------
load("pipeline/data_clean.RData")

HOME_REGION_V2 <- c(US = "US", CN = "China", EU = "Europe",
                    MENA = "Arab", India = "India")
LANGS_V2 <- c("en", "zh", "ar", "ru", "hi")

v2 <- data_clean %>%
  filter(!is.na(jurisdiction_f), !is.na(engagement_code),
         prompt_language %in% LANGS_V2) %>%
  mutate(
    juris  = factor(as.character(jurisdiction_f),
                    levels = c("CN", "MENA", "India", "US", "EU")),
    lang   = factor(prompt_language, levels = LANGS_V2),
    tier   = factor(dataset_type, levels = c("base", "boundary"),
                    labels = c("regular", "boundary")),
    domain = factor(prompt_category),
    route_f2 = factor(route),
    model_f2 = factor(model),
    # THREE region positions, deliberately not two. General has no home
    # jurisdiction, so folding it into "away" would score every model as away on
    # a sixth of the battery and contaminate the reference category.
    home_status = case_when(
      region_focus == "General"                                            ~ "general",
      as.character(region_focus) == HOME_REGION_V2[as.character(juris)]     ~ "home",
      TRUE                                                                 ~ "away"),
    home = as.integer(home_status == "home"),
    # ---- OUTCOME DEFINITIONS (never silently relabel code 3) --------------
    refused_strict = as.integer(engagement_code >= 4),   # PRIMARY
    refused_any    = as.integer(engagement_code >= 3),   # sensitivity
    outcome3 = factor(case_when(engagement_code <= 2 ~ "engaged",
                                engagement_code == 3 ~ "partial",
                                TRUE                 ~ "refusal"),
                      levels = c("engaged", "partial", "refusal")),
    engagement_ordinal = as.integer(engagement_code),
    block_id = paste(model, prompt_id, sep = "||"))

stopifnot(all(v2$home_status %in% c("home", "away", "general")))

# -----------------------------------------------------------------------------
# Weighting
# -----------------------------------------------------------------------------
# response weighting  : every response counts once (empirical composition)
# equal-model         : every MODEL contributes equally within the summary group
# equal model x issue : every (model, issue) cell contributes equally -- the
#                       primary standardization target for family B, so that a
#                       jurisdiction's contrast is not driven by whichever models
#                       or issues happen to supply more rows.
w_response <- function(d) rep(1 / nrow(d), nrow(d))

w_equal_model <- function(d) {
  n_m <- table(droplevels(factor(d$model)))
  (1 / length(n_m)) / as.numeric(n_m[as.character(d$model)])
}

w_equal_model_issue <- function(d) {
  cell <- paste(d$model, d$issue_id, sep = "||")
  n_c <- table(cell)
  (1 / length(n_c)) / as.numeric(n_c[cell])
}

# -----------------------------------------------------------------------------
# Issue-cluster bootstrap
# -----------------------------------------------------------------------------
# The outer resampling unit is ALWAYS issue_id: an issue supplies four prompts to
# every model in every language, so responses are clustered within issue and
# resampling rows would understate the spread by a wide margin.
#
# `stat` is re-executed on each resampled data frame, so any model it fits is
# REFIT and any standardization it performs is RE-STANDARDIZED inside the
# replicate. Replicates that fail (separation, non-convergence) are counted, not
# silently dropped, and drawing continues until `B` successes or `max_attempts`.
boot_issue <- function(d, stat, B = 2000, seed = V2_SEED, max_attempts = NULL,
                       label = NA_character_) {
  if (is.null(max_attempts)) max_attempts <- ceiling(B * 1.5) + 50
  set.seed(seed)
  issues <- unique(d$issue_id)
  idx <- split(seq_len(nrow(d)), d$issue_id)
  point <- tryCatch(stat(d), error = function(e) NA_real_)
  vals <- numeric(0); attempts <- 0L; fails <- 0L
  while (length(vals) < B && attempts < max_attempts) {
    attempts <- attempts + 1L
    tk <- sample(issues, length(issues), replace = TRUE)
    dd <- d[unlist(idx[tk], use.names = FALSE), , drop = FALSE]
    v <- tryCatch(stat(dd), error = function(e) NA_real_,
                  warning = function(w) suppressWarnings(stat(dd)))
    if (is.null(v) || !is.finite(v)) { fails <- fails + 1L; next }
    vals <- c(vals, v)
  }
  list(estimate = point,
       conf_low  = if (length(vals) > 1) unname(quantile(vals, .025)) else NA_real_,
       conf_high = if (length(vals) > 1) unname(quantile(vals, .975)) else NA_real_,
       diag = tibble(label = label, bootstrap_unit = "issue_id", seed = seed,
                     replicates_requested = B, replicates_attempted = attempts,
                     replicates_successful = length(vals),
                     replicates_failed = fails,
                     failure_rate = fails / max(attempts, 1),
                     interval_method = "percentile",
                     n_rows = nrow(d), n_issues = length(issues)))
}

# Fast path for count-based statistics (Family A). The generic boot_issue()
# rebuilds a data frame per replicate, which is fine when the statistic refits a
# model (Family B) but ruinous when it is only a weighted mean: a single
# 20,000-row descriptive bootstrap took longer than the entire model-refitting
# family. This variant precomputes integer vectors once and resamples indices,
# giving identical numbers with no data-frame construction in the loop.
boot_issue_fast <- function(y, issue, group, wmode, B = 2000, seed = V2_SEED,
                            label = NA_character_) {
  # group: integer arm code, 1 = home, 0 = away. wmode: "response"|"equal_model"
  # model_idx supplied via attribute for equal-model weighting.
  midx <- attr(y, "model_idx")
  iss <- split(seq_along(y), issue)
  wmean <- function(ix, arm) {
    sel <- ix[group[ix] == arm]
    if (!length(sel)) return(NA_real_)
    if (wmode == "response") return(mean(y[sel]))
    m <- midx[sel]
    tot <- tabulate(m, nbins = max(midx))
    hit <- tabulate(m[y[sel] == 1L], nbins = max(midx))
    present <- tot > 0
    mean((hit[present]) / (tot[present]))     # each model weighted equally
  }
  stat_ix <- function(ix) wmean(ix, 1L) - wmean(ix, 0L)
  point <- stat_ix(seq_along(y))
  set.seed(seed)
  keys <- names(iss); vals <- numeric(0); att <- 0L; fail <- 0L
  maxatt <- ceiling(B * 1.5) + 50
  while (length(vals) < B && att < maxatt) {
    att <- att + 1L
    ix <- unlist(iss[sample(keys, length(keys), replace = TRUE)], use.names = FALSE)
    v <- stat_ix(ix)
    if (!is.finite(v)) { fail <- fail + 1L; next }
    vals <- c(vals, v)
  }
  list(estimate = point,
       conf_low  = if (length(vals) > 1) unname(quantile(vals, .025)) else NA_real_,
       conf_high = if (length(vals) > 1) unname(quantile(vals, .975)) else NA_real_,
       diag = tibble(label = label, bootstrap_unit = "issue_id", seed = seed,
                     replicates_requested = B, replicates_attempted = att,
                     replicates_successful = length(vals), replicates_failed = fail,
                     failure_rate = fail / max(att, 1), interval_method = "percentile",
                     n_rows = length(y), n_issues = length(iss)))
}

# e39 accumulates across scripts; each appends its own diagnostics.
append_boot_diag <- function(df) {
  f <- file.path(EST, "e39_bootstrap_diagnostics.csv")
  if (file.exists(f)) {
    old <- suppressMessages(read_csv(f, show_col_types = FALSE))
    df <- bind_rows(old, df)
  }
  write_csv(df, f)
}

# -----------------------------------------------------------------------------
# Percentage points
# -----------------------------------------------------------------------------
# Single conversion point, so "pp equals 100x the probability difference" is true
# by construction and testable (46_).
pp <- function(x) 100 * x

# -----------------------------------------------------------------------------
# OPTIONAL nested annotation-error layer -- ARCHITECTED, NOT ACTIVE
# -----------------------------------------------------------------------------
# Placeholder for a future measurement-error correction. When human-coded
# calibration exists, `sens`/`spec` per stratum can be supplied and this draws
# latent labels inside each bootstrap replicate, giving intervals that carry
# annotation error as well as sampling error.
#
# It is NOT called anywhere: there is currently no human calibration, and
# inventing sensitivity/specificity would manufacture precision the study has not
# earned. Until then every judge is reported SEPARATELY and a judge-sensitivity
# range is given; majority vote is never treated as ground truth.
draw_latent_labels <- function(y, strata = NULL, sens = NULL, spec = NULL,
                               rng = NULL) {
  if (is.null(sens) || is.null(spec))
    stop("draw_latent_labels() requires human-estimated sensitivity/specificity ",
         "per stratum. None exist yet -- see docs/MULTI_JUDGE_PLAN.md. This ",
         "layer is architected but deliberately inactive.")
  s <- if (is.null(strata)) rep(1L, length(y)) else as.integer(factor(strata))
  p_true <- ifelse(y == 1, sens[s] / (sens[s] + (1 - spec[s])),
                   (1 - sens[s]) / ((1 - sens[s]) + spec[s]))
  rbinom(length(y), 1, p_true)
}

V2_ANNOTATION_ERROR_LAYER <- list(
  status = "architected_inactive",
  requires = c("human-coded sensitivity per stratum", "human-coded specificity per stratum"),
  hook = "draw_latent_labels()",
  note = paste("No human calibration exists. Judges are reported separately and",
               "a judge-sensitivity range is given; majority vote is NOT treated",
               "as ground truth."))

cat(sprintf("[v2 common] analysis rows: %s | issues: %s | models: %s | languages: %s\n",
            format(nrow(v2), big.mark = ","), n_distinct(v2$issue_id),
            n_distinct(v2$model), n_distinct(v2$lang)))
