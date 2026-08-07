# =============================================================================
# CANONICAL LAYER -- shared foundation   (sourced by 51-56; not run alone)
# =============================================================================
# This is the paper's analysis layer. docs/CANONICAL_ANALYSES.md is its
# specification; docs/ESTIMANDS.md is a historical catalogue of what came before
# and is NOT the paper spec.
#
# SCOPE RULES
#   * Reads only. Never writes to prompts/, responses/, annotations/ or
#     data_clean.RData.
#   * Writes only pipeline/estimates/canonical/ and pipeline/figures/canonical/.
#   * Calls no API, endpoint, generation, translation or annotation service.
#
# -----------------------------------------------------------------------------
# THE BOOTSTRAP MULTIPLICITY REPAIR  (the reason the old intervals were retired)
# -----------------------------------------------------------------------------
# A cluster bootstrap draws issues with replacement, so an issue can be drawn
# k > 1 times. The previous implementation pasted the drawn rows together and
# then built weights keyed on `issue_id`. Because all k copies carried the SAME
# issue_id, the weighting collapsed them back into one issue -- the resample
# looked like it contained fewer, larger issues than it did, and an issue drawn
# three times contributed the same total weight as one drawn once.
#
# The repair: every drawn copy gets a distinct `bootstrap_issue_instance`, and
# every weight downstream keys on that, never on `issue_id`. An issue drawn k
# times then contributes exactly k times the weight, which is what a cluster
# bootstrap means. 30_acceptance.R proves this with a synthetic case.
#
# NO INTERVAL FROM THE PRE-CANONICAL LAYER IS REUSED. Everything is recomputed.

suppressPackageStartupMessages({
  library(tidyverse); library(digest)
})
select <- dplyr::select
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())

CAN_EST  <- "pipeline/estimates/canonical"
CAN_FIG  <- "pipeline/figures/canonical"
CAN_SEED <- 20260807L
RUN_DIR  <- Sys.getenv("REFUSAL_RUN_DIR", "annotations/full_v1")
dir.create(CAN_EST, showWarnings = FALSE, recursive = TRUE)
dir.create(CAN_FIG, showWarnings = FALSE, recursive = TRUE)

# Unique per invocation, so diagnostics are run-scoped and can never accumulate
# duplicates the way the shared e39 did (412 rows for 332 distinct labels).
CANONICAL_RUN_ID <- Sys.getenv("CANONICAL_RUN_ID",
  paste0("canon_", format(Sys.time(), "%Y%m%dT%H%M%S")))

# -----------------------------------------------------------------------------
# Sample
# -----------------------------------------------------------------------------
load("pipeline/data_clean.RData")

HOME_REGION_C <- c(US = "US", CN = "China", EU = "Europe",
                   MENA = "Arab", India = "India")
LANGS_C  <- c("en", "zh", "ar", "ru", "hi")
JURIS_C  <- c("CN", "MENA", "India", "US", "EU")

canon <- data_clean %>%
  filter(!is.na(jurisdiction_f), !is.na(engagement_code),
         prompt_language %in% LANGS_C) %>%
  mutate(
    juris   = factor(as.character(jurisdiction_f), levels = JURIS_C),
    lang    = factor(prompt_language, levels = LANGS_C),
    tier    = factor(dataset_type, levels = c("base", "boundary"),
                     labels = c("regular", "boundary")),
    domain  = factor(prompt_category),
    route_f = factor(route),
    model_f = factor(model),
    # THREE positions. `general` has no home jurisdiction and is never `away`.
    home_status = case_when(
      region_focus == "General" ~ "general",
      as.character(region_focus) == HOME_REGION_C[as.character(juris)] ~ "home",
      TRUE ~ "away"),
    home = as.integer(home_status == "home"),
    # Outcomes. Code 3 is preserved as a standalone category and is never
    # silently folded into either side.
    refused_strict = as.integer(engagement_code >= 4),
    refused_any    = as.integer(engagement_code >= 3),
    outcome3 = factor(case_when(engagement_code <= 2 ~ "engaged",
                                engagement_code == 3 ~ "partial",
                                TRUE ~ "refusal"),
                      levels = c("engaged", "partial", "refusal")),
    engagement_ordinal = as.integer(engagement_code),
    block_id = paste(model, prompt_id, sep = "||"))

# --- hard assertions on the authoritative sample ------------------------------
stopifnot(nrow(canon) == 137186L)
stopifnot(nrow(count(canon, model, prompt_id, prompt_language) %>% filter(n > 1)) == 0L)
stopifnot(n_distinct(canon$issue_id) == 624L,
          n_distinct(canon$model) == 11L,
          n_distinct(canon$lang) == 5L,
          nlevels(canon$tier) == 2L)
stopifnot(!any(canon$home_status == "away" & canon$region_focus == "General"))

CANON_ENGLISH <- canon %>% filter(lang == "en")

# Response lengths (read-only derivation, cached by the v2 layer).
CANON_LEN <- if (file.exists("pipeline/response_lengths.csv"))
  suppressMessages(read_csv("pipeline/response_lengths.csv", show_col_types = FALSE)) else NULL

# -----------------------------------------------------------------------------
# Weights
# -----------------------------------------------------------------------------
# PRIMARY TARGET, nested exactly as specified:
#   equal total weight per tested MODEL
#     -> within model, equal total weight per ISSUE
#        -> within model x issue, equal weight per PROMPT
#
# `issue_col` is a parameter so the bootstrap can pass
# `bootstrap_issue_instance`. Passing `issue_id` inside a resample would silently
# merge repeated draws of the same issue -- the bug this layer exists to fix.
w_nested <- function(d, issue_col = "issue_id") {
  m  <- as.character(d$model)
  iss <- as.character(d[[issue_col]])
  mi <- paste(m, iss, sep = "\r")
  n_models     <- length(unique(m))
  issues_per_m <- tapply(iss, m, function(x) length(unique(x)))
  rows_per_mi  <- table(mi)
  (1 / n_models) *
    (1 / as.numeric(issues_per_m[m])) *
    (1 / as.numeric(rows_per_mi[mi]))
}

w_response    <- function(d, ...) rep(1 / nrow(d), nrow(d))

w_equal_model <- function(d, ...) {
  n_m <- table(as.character(d$model))
  (1 / length(n_m)) / as.numeric(n_m[as.character(d$model)])
}

# -----------------------------------------------------------------------------
# Issue-cluster bootstrap WITH multiplicity preserved
# -----------------------------------------------------------------------------
# `stat(dd)` receives a data frame carrying `bootstrap_issue_instance`. Any
# weighting or refitting it performs must use that column for the issue level.
boot_canon <- function(d, stat, B = 2000L, seed = CAN_SEED,
                       label = NA_character_, max_attempts = NULL) {
  if (is.null(max_attempts)) max_attempts <- ceiling(B * 1.5) + 50L
  issues <- unique(d$issue_id)
  idx <- split(seq_len(nrow(d)), d$issue_id)
  d0 <- d; d0$bootstrap_issue_instance <- as.character(d0$issue_id)
  point <- tryCatch(stat(d0), error = function(e) NA_real_)

  set.seed(seed)
  vals <- numeric(0); att <- 0L; fail <- 0L
  while (length(vals) < B && att < max_attempts) {
    att <- att + 1L
    drawn <- sample(issues, length(issues), replace = TRUE)
    rows <- unlist(idx[drawn], use.names = FALSE)
    # One instance label per DRAW, repeated across that draw's rows.
    inst <- rep(paste0(drawn, "#", seq_along(drawn)),
                times = lengths(idx[drawn]))
    dd <- d[rows, , drop = FALSE]
    dd$bootstrap_issue_instance <- inst
    v <- tryCatch(stat(dd), error = function(e) NA_real_)
    if (is.null(v) || length(v) != 1L || !is.finite(v)) { fail <- fail + 1L; next }
    vals <- c(vals, v)
  }
  list(estimate = point,
       conf_low  = if (length(vals) > 1) unname(quantile(vals, .025)) else NA_real_,
       conf_high = if (length(vals) > 1) unname(quantile(vals, .975)) else NA_real_,
       diag = tibble(canonical_run_id = CANONICAL_RUN_ID, label = label,
                     bootstrap_unit = "issue_id",
                     multiplicity_preserved = TRUE,
                     copy_id_column = "bootstrap_issue_instance",
                     seed = seed, replicates_requested = B,
                     replicates_attempted = att,
                     replicates_successful = length(vals),
                     replicates_failed = fail,
                     failure_rate = fail / max(att, 1),
                     interval_method = "percentile",
                     n_rows = nrow(d), n_issues = length(issues)))
}

# Run-scoped diagnostics. Appends within a run, but a (run_id, label) pair can
# never duplicate -- 56_ asserts it.
.CANON_DIAG <- new.env(parent = emptyenv())
.CANON_DIAG$rows <- list()
record_diag <- function(df) {
  key <- paste(df$canonical_run_id, df$label)
  if (key %in% names(.CANON_DIAG$rows))
    stop("duplicate diagnostic label within run: ", key)
  .CANON_DIAG$rows[[key]] <- df
  invisible(NULL)
}
flush_diag <- function(file = "c18_bootstrap_diagnostics.csv") {
  if (!length(.CANON_DIAG$rows)) return(invisible(NULL))
  out <- bind_rows(.CANON_DIAG$rows)
  p <- file.path(CAN_EST, file)
  if (file.exists(p)) {
    old <- suppressMessages(read_csv(p, show_col_types = FALSE))
    # Replace only the (run, label) pairs this session actually recomputed.
    # Dropping every row of the run instead would mean that re-running ONE part
    # under an existing run id silently deleted the other parts' diagnostics --
    # and a partial re-run is the normal way to iterate on one part.
    key_new <- paste(out$canonical_run_id, out$label)
    old <- old %>% filter(!paste(canonical_run_id, label) %in% key_new)
    out <- bind_rows(old, out)
  }
  write_csv(out, p)
  invisible(out)
}

pp <- function(x) 100 * x

# -----------------------------------------------------------------------------
# MULTI-JUDGE INTEGRATION
# -----------------------------------------------------------------------------
# Principle: the canonical outcome is the Gemini label. Additional judges are a
# SENSITIVITY DIMENSION, not a correction and not a consensus. Majority vote is
# never computed as ground truth -- with no human calibration there is no basis
# for saying the majority is right, and a consensus label would conceal exactly
# the disagreement the panel exists to expose.
#
# Three things every headline quantity can therefore report:
#   1. the canonical estimate (Gemini);
#   2. the same estimate recomputed under each judge's labels, where coverage
#      permits (currently English only);
#   3. the SPREAD across judges, reported as a range, not an interval -- it is
#      not sampling uncertainty and must not be pooled with the bootstrap.
judge_labels <- function(run_dir = RUN_DIR, language = "en") {
  root <- file.path(run_dir, "panel")
  if (!dir.exists(root)) return(NULL)
  dirs <- list.dirs(root, recursive = FALSE)
  out <- map_dfr(dirs, function(dd) {
    fs <- list.files(dd, pattern = "\\.jsonl$", full.names = TRUE)
    map_dfr(fs, function(f) {
      ls <- readLines(f, warn = FALSE); ls <- ls[nzchar(ls)]
      map_dfr(ls, function(l) {
        r <- tryCatch(jsonlite::fromJSON(l), error = function(e) NULL)
        if (is.null(r) || is.null(r$engagement_code) || !is.null(r$error)) return(NULL)
        if (!is.null(language) && !identical(r$prompt_language, language)) return(NULL)
        tibble(prompt_id = r$prompt_id, prompt_language = r$prompt_language,
               model = r$model, engagement_code = as.integer(r$engagement_code))
      })
    }) %>% mutate(judge_model = gsub("__", "/", basename(dd)))
  })
  if (!nrow(out)) return(NULL)
  # last-wins on the resume key, matching the annotator's own predicate
  out %>% group_by(prompt_id, prompt_language, model, judge_model) %>%
    slice_tail(n = 1) %>% ungroup()
}

# Recompute any statistic under each judge's labels and return the spread.
judge_sensitivity <- function(d, stat_fun, judges = NULL, language = "en") {
  if (is.null(judges)) judges <- judge_labels(language = language)
  canon_row <- tibble(judge_model = "google/gemini-2.5-flash-lite (canonical)",
                      estimate = stat_fun(d), n = nrow(d))
  if (is.null(judges) || !nrow(judges)) return(canon_row)
  alt <- map_dfr(sort(unique(judges$judge_model)), function(j) {
    lab <- judges %>% filter(judge_model == j) %>%
      select(prompt_id, prompt_language, model, jc = engagement_code)
    dd <- d %>% inner_join(lab, by = c("prompt_id", "prompt_language", "model")) %>%
      mutate(refused_strict = as.integer(jc >= 4),
             refused_any = as.integer(jc >= 3))
    if (!nrow(dd)) return(NULL)
    tibble(judge_model = j, estimate = stat_fun(dd), n = nrow(dd))
  })
  bind_rows(canon_row, alt)
}

# -----------------------------------------------------------------------------
# ANNOTATION-ERROR HOOK -- DISABLED, and now correct when it is enabled
# -----------------------------------------------------------------------------
# The previous implementation computed
#     P(true=1 | obs=1) = sens / (sens + (1 - spec))
# which is Bayes' rule with the PRIOR SILENTLY SET TO 0.5. Refusal prevalence is
# ~5%, so that assumption would have been badly wrong in the direction that
# matters, inflating the implied number of true positives roughly twenty-fold.
#
# The corrected form requires a stratum-specific prevalence:
#     P(true=1 | obs=1) = sens*prev / (sens*prev + (1-spec)*(1-prev))
#     P(true=1 | obs=0) = (1-sens)*prev / ((1-sens)*prev + spec*(1-prev))
#
# It remains DISABLED: no human sensitivity/specificity estimates exist, and
# supplying guesses would manufacture precision the study has not earned. See
# docs/CANONICAL_ANALYSES.md for the planned design-based validation.
draw_latent_labels <- function(y, strata = NULL, sens = NULL, spec = NULL,
                               prevalence = NULL) {
  if (is.null(sens) || is.null(spec) || is.null(prevalence))
    stop("draw_latent_labels() requires human-estimated sensitivity, specificity ",
         "AND stratum-specific prevalence. None exist. This hook is deliberately ",
         "disabled -- see docs/CANONICAL_ANALYSES.md.")
  s <- if (is.null(strata)) rep(1L, length(y)) else as.integer(factor(strata))
  se <- sens[s]; sp <- spec[s]; pv <- prevalence[s]
  p1 <- se * pv / (se * pv + (1 - sp) * (1 - pv))
  p0 <- (1 - se) * pv / ((1 - se) * pv + sp * (1 - pv))
  rbinom(length(y), 1, ifelse(y == 1, p1, p0))
}

CANON_META <- list(
  canonical_run_id = CANONICAL_RUN_ID,
  seed = CAN_SEED,
  bootstrap_unit = "issue_id",
  bootstrap_copy_id = "bootstrap_issue_instance (multiplicity preserved)",
  primary_outcome = "refused_strict = engagement_code >= 4",
  sensitivity_outcome = "refused_any = engagement_code >= 3",
  code3 = "standalone partial/mixed category; never merged silently",
  general_handling = "reported separately; never in the away category",
  primary_language = "en",
  api_calls = 0L)

cat(sprintf("[canonical] run %s | rows %s | English %s | issues %d\n",
            CANONICAL_RUN_ID, format(nrow(canon), big.mark = ","),
            format(nrow(CANON_ENGLISH), big.mark = ","), n_distinct(canon$issue_id)))

# =============================================================================
# Standardized home contrast: specification, estimability, g-computation
# =============================================================================
# Shared by 51 (the canonical estimate) and 54 (the same estimate refit under
# each panel judge). One definition, so a judge-sensitivity result can never
# be a specification difference wearing a judge's name.

# home * model where a jurisdiction has >1 model, so model-specific contrasts
# come straight out of the fit. No region term: region DETERMINES home within a
# jurisdiction, so it is collinear with the contrast of interest.
build_f <- function(d, outcome = "refused_strict") {
  rhs <- if (nlevels(droplevels(factor(d$model))) > 1) "home * model_f" else "home"
  for (v in c("tier", "domain", "route_f"))
    if (nlevels(droplevels(factor(d[[v]]))) > 1) rhs <- c(rhs, v)
  as.formula(paste(outcome, "~", paste(rhs, collapse = " + ")))
}

estimable_chk <- function(d) {
  if (!nrow(d)) return("no rows")
  if (sum(d$refused_strict) == 0) return("0 observed refusals (complete separation)")
  if (length(unique(d$home)) < 2) return("home does not vary")
  eh <- sum(d$refused_strict[d$home == 1]); ea <- sum(d$refused_strict[d$home == 0])
  if (eh == 0 || ea == 0)
    return(sprintf("separation: %d home / %d away events", eh, ea))
  ""
}

# g-computation returning the overall standardized contrast AND the
# model-specific ones, all on the probability scale.
gcomp <- function(d, wfun = w_nested, outcome = "refused_strict", per_model = FALSE) {
  ic <- if ("bootstrap_issue_instance" %in% names(d)) "bootstrap_issue_instance" else "issue_id"
  fit <- suppressWarnings(glm(build_f(d, outcome), data = d, family = binomial))
  if (!fit$converged) return(if (per_model) NULL else NA_real_)
  p1 <- predict(fit, newdata = transform(d, home = 1L), type = "response")
  p0 <- predict(fit, newdata = transform(d, home = 0L), type = "response")
  w  <- wfun(d, issue_col = ic)
  if (!per_model) return(sum(w * (p1 - p0)))
  ms <- sort(unique(as.character(d$model)))
  vapply(ms, function(m) {
    s <- as.character(d$model) == m
    sum(w[s] * (p1[s] - p0[s])) / sum(w[s])   # renormalise within model
  }, numeric(1))
}
