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
#   * Writes only the release estimate directory and pipeline/figures/{main,extended}/.
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

# Output locations are overridable so a release can be BUILT in isolation and
# promoted only after every check passes. Without this a failed build leaves a
# half-written canonical directory that looks current.
CAN_EST  <- Sys.getenv("CANON_EST_DIR", "pipeline/estimates/canonical")
CAN_FIG  <- Sys.getenv("CANON_FIG_DIR", "pipeline/figures/main")
CAN_APP_FIG <- Sys.getenv("CANON_APPFIG_DIR", "pipeline/figures/extended")
# Seed comes from the environment so the value the manifest records is the value
# the run actually used. Hard-coding it here while make_release.R recorded
# Sys.getenv("CAN_SEED") meant the two could disagree without anything failing.
CAN_SEED <- as.integer(Sys.getenv("CAN_SEED", "20260807"))
RUN_DIR  <- Sys.getenv("REFUSAL_RUN_DIR", "annotations/full_v1")
dir.create(CAN_EST, showWarnings = FALSE, recursive = TRUE)
dir.create(CAN_FIG, showWarnings = FALSE, recursive = TRUE)
dir.create(CAN_APP_FIG, showWarnings = FALSE, recursive = TRUE)

# Unique per invocation, so diagnostics are run-scoped and can never accumulate
# duplicates the way the shared e39 did (412 rows for 332 distinct labels).
CANONICAL_RUN_ID <- Sys.getenv("CANONICAL_RUN_ID",
  paste0("canon_", format(Sys.time(), "%Y%m%dT%H%M%S")))

# -----------------------------------------------------------------------------
# Sample
# -----------------------------------------------------------------------------
load("pipeline/data_clean.RData")

# ONE declaration of every canonical ordering, shared with the figure layer
# (`_theme.R` sources the same file). These three names are aliases kept so the
# existing call sites in 11-14 keep working. Before this, the estimation layer
# and the figure layer each declared their own copy; they agreed by luck.
source("pipeline/_orders.R")
HOME_REGION_C <- HOME_REGION_OF   # alias -> _orders.R
LANGS_C       <- ORDER_LANG       # alias -> _orders.R
JURIS_C       <- ORDER_JURIS      # alias -> _orders.R

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
                       label = NA_character_, max_fail_rate = 0.02) {
  # FIXED NUMBER OF DRAWS. An earlier version kept resampling until it had B
  # SUCCESSES, which silently conditions the interval on the replicates where
  # the estimator happened to be defined -- exactly the replicates where a
  # jurisdiction is not separated, i.e. the ones with more events. That biases
  # the interval inward. Now B draws are taken, failures are counted and
  # reported, and an interval built on too many failures is marked unreliable
  # rather than quietly returned.
  issues <- unique(d$issue_id)
  idx <- split(seq_len(nrow(d)), d$issue_id)
  d0 <- d; d0$bootstrap_issue_instance <- as.character(d0$issue_id)
  point <- tryCatch(stat(d0), error = function(e) NA_real_)

  set.seed(seed)
  vals <- rep(NA_real_, B)
  for (b in seq_len(B)) {
    drawn <- sample(issues, length(issues), replace = TRUE)
    rows <- unlist(idx[drawn], use.names = FALSE)
    # One instance label per DRAW, repeated across that draw's rows, so a
    # replicate that draws an issue twice keeps the copies distinct.
    inst <- rep(paste0(drawn, "#", seq_along(drawn)), times = lengths(idx[drawn]))
    dd <- d[rows, , drop = FALSE]
    dd$bootstrap_issue_instance <- inst
    v <- tryCatch(stat(dd), error = function(e) NA_real_)
    vals[b] <- if (is.null(v) || length(v) != 1L || !is.finite(v)) NA_real_ else v
  }
  nfail <- sum(is.na(vals)); ok <- vals[!is.na(vals)]
  frate <- nfail / B
  unreliable <- frate > max_fail_rate
  list(estimate = point,
       conf_low  = if (length(ok) > 1) unname(quantile(ok, .025)) else NA_real_,
       conf_high = if (length(ok) > 1) unname(quantile(ok, .975)) else NA_real_,
       replicates = ok,
       failure_rate = frate,
       interval_reliable = !unreliable,
       diag = tibble(canonical_run_id = CANONICAL_RUN_ID, label = label,
                     bootstrap_unit = "issue_id",
                     multiplicity_preserved = TRUE,
                     copy_id_column = "bootstrap_issue_instance",
                     seed = seed, replicates_requested = B,
                     replicates_drawn = B,
                     replicates_successful = length(ok),
                     replicates_failed = nfail,
                     failure_rate = frate,
                     failed_draws_replaced = FALSE,
                     interval_reliable = !unreliable,
                     interval_method = "percentile",
                     n_rows = nrow(d), n_issues = length(issues)))
}

# Delete-one-issue jackknife WITH a finite-population correction, for quantities
# estimated on the slant subsample. The subsample is 156 issues drawn without
# replacement from the frozen 624-issue battery, so a bootstrap percentile
# interval targets a superpopulation and is too wide for inference to the
# battery itself. Shrinking a percentile interval by sqrt(1-f) after the fact --
# which is what this replaces -- is not a design-based correction: it rescales
# an interval whose shape came from a with-replacement resampling model that
# does not match the sampling design at all.
#
# The jackknife variance of a smooth function of issue-level contributions is
#     v = (n-1)/n * sum_i (theta_(-i) - theta_bar)^2
# and the FPC multiplies that variance by (1 - f). Returns a normal-approximation
# interval, which is appropriate for a mean-like statistic over 156 clusters.
jack_fpc <- function(d, stat, n_total, issue_col = "issue_id",
                     label = NA_character_, conf = 0.95) {
  iss <- unique(d[[issue_col]])
  n <- length(iss)
  theta <- stat(d)
  th <- vapply(iss, function(i) {
    v <- tryCatch(stat(d[d[[issue_col]] != i, , drop = FALSE]),
                  error = function(e) NA_real_)
    if (is.null(v) || length(v) != 1L) NA_real_ else v
  }, numeric(1))
  okj <- is.finite(th)
  f <- n / n_total
  v <- ((n - 1) / n) * sum((th[okj] - mean(th[okj]))^2) * (1 - f)
  z <- stats::qnorm(1 - (1 - conf) / 2)
  list(estimate = theta, se = sqrt(v),
       conf_low = theta - z * sqrt(v), conf_high = theta + z * sqrt(v),
       diag = tibble(canonical_run_id = CANONICAL_RUN_ID, label = label,
                     bootstrap_unit = issue_col,
                     method = "delete-one-issue jackknife with FPC",
                     n_issues_sampled = n, n_issues_frame = n_total,
                     sampling_fraction = f, fpc = 1 - f,
                     leave_one_out_failed = sum(!okj),
                     interval_method = "normal approximation",
                     n_rows = nrow(d)))
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

estimable_chk <- function(d, outcome = "refused_strict") {
  # The outcome is a PARAMETER. Hard-coding refused_strict here meant the
  # codes-3-5 sensitivity was tested for separation on the wrong variable, so a
  # specification could be declared estimable on one outcome and then fit on
  # another.
  if (!nrow(d)) return("no rows")
  if (!outcome %in% names(d)) return(paste("outcome", outcome, "absent"))
  y <- d[[outcome]]
  if (sum(y) == 0) return(paste0("0 observed events on ", outcome,
                                 " (complete separation)"))
  if (length(unique(d$home)) < 2) return("home does not vary")
  eh <- sum(y[d$home == 1]); ea <- sum(y[d$home == 0])
  if (eh == 0 || ea == 0)
    return(sprintf("separation on %s: %d home / %d away events", outcome, eh, ea))
  ""
}

# Explicit separation diagnosis for a FITTED model. Complete or quasi-complete
# separation does not always produce an error -- glm returns huge coefficients
# with huge standard errors and a fitted probability of essentially 0 or 1, and
# the g-computation contrast then looks like a normal number. These are the
# symptoms worth naming rather than a single pass/fail.
# Explicit separation diagnosis for a FITTED model, reported as SYMPTOMS rather
# than a single verdict. Complete or quasi-complete separation does not always
# raise a warning: glm returns huge coefficients with huge standard errors and
# fitted probabilities at 0 or 1, and the g-computation contrast then looks like
# an ordinary number.
#
# `blocking` is deliberately narrower than `separated`. Quasi-separation inside a
# NUISANCE cell -- a (model x domain) combination with no events -- makes that
# cell's prediction degenerate without making the standardized contrast
# undefined, and it is the reason the full-target estimand extrapolates. That is
# reported as a number (degenerate_weight) and handled by the common-support
# estimand, not by discarding the estimate. Only a genuinely undefined fit
# blocks: non-finite parameters, non-finite predictions, or non-convergence.
sep_diagnose <- function(fit, w = NULL) {
  if (is.null(fit)) return(list(separated = TRUE, blocking = TRUE, why = "no fit",
                                degenerate_weight = NA_real_))
  co <- stats::coef(fit)
  se <- tryCatch(summary(fit)$coefficients[, 2], error = function(e) rep(NA_real_, length(co)))
  fv <- tryCatch(stats::fitted(fit), error = function(e) NA_real_)
  big_beta <- any(is.finite(co) & abs(co) > 15)
  big_se   <- any(is.finite(se) & se > 25)
  deg      <- is.finite(fv) & (fv < 1e-6 | fv > 1 - 1e-6)
  extreme  <- any(deg)
  nonfin   <- any(!is.finite(co)) || any(!is.finite(fv))
  noconv   <- !isTRUE(fit$converged) && !inherits(fit, "logistf")
  why <- c(if (nonfin) "non-finite coefficient or prediction",
           if (noconv) "did not converge",
           if (big_beta) "|coef| > 15",
           if (big_se) "SE > 25",
           if (extreme) sprintf("%d fitted probabilities at 0 or 1", sum(deg)))
  list(separated = length(why) > 0,
       blocking = nonfin || noconv,
       why = paste(why, collapse = "; "),
       # NAMED FOR WHAT IT MEASURES. This is the share of weight whose OBSERVED
       # fit is extreme; it is not the g-computation diagnostic, because
       # g-computation evaluates both counterfactuals. cf_extreme_weight()
       # below is the quantity that actually bears on the contrast.
       observed_fit_extreme_weight =
         if (is.null(w) || !any(is.finite(fv))) NA_real_ else sum(w[deg]))
}

# Counterfactual extremeness: the share of target weight for which EITHER
# counterfactual prediction -- p(home = 1) or p(home = 0) -- is numerically 0 or
# 1. This is the diagnostic that matches the estimand, because the standardized
# contrast is built from both prediction vectors. A unit whose observed fit is
# comfortable can still have a degenerate counterfactual, and that is precisely
# the extrapolation the common-support estimand exists to avoid.
#
# The transparent headline measure of unsupported target remains
# 1 - target_weight_retained from restrict_support(); this adds the
# model-based view of the same problem.
cf_extreme_weight <- function(fit, d, w, outcome = "refused_strict") {
  if (is.null(fit)) return(NA_real_)
  p1 <- tryCatch(stats::predict(fit, newdata = transform(d, home = 1L),
                                type = "response"), error = function(e) NULL)
  p0 <- tryCatch(stats::predict(fit, newdata = transform(d, home = 0L),
                                type = "response"), error = function(e) NULL)
  if (is.null(p1) || is.null(p0)) return(NA_real_)
  ext <- (p1 < 1e-6 | p1 > 1 - 1e-6) | (p0 < 1e-6 | p0 > 1 - 1e-6)
  sum(w[ext])
}

# Fit with warnings captured rather than swallowed. suppressWarnings() around a
# glm hides "fitted probabilities numerically 0 or 1", which is the single most
# useful signal that a jurisdiction is separated.
fit_logit <- function(f, data, firth = FALSE) {
  warns <- character(0)
  fit <- withCallingHandlers(
    tryCatch({
      if (firth) logistf::logistf(f, data = data, control = logistf::logistf.control(maxit = 200))
      else stats::glm(f, data = data, family = binomial)
    }, error = function(e) { warns <<- c(warns, paste("error:", conditionMessage(e))); NULL }),
    warning = function(w) { warns <<- c(warns, conditionMessage(w)); invokeRestart("muffleWarning") })
  list(fit = fit, warnings = warns)
}

gcomp <- function(d, wfun = w_nested, outcome = "refused_strict",
                  per_model = FALSE, firth = FALSE, strict = TRUE) {
  ic <- if ("bootstrap_issue_instance" %in% names(d)) "bootstrap_issue_instance" else "issue_id"
  f  <- build_f(d, outcome)
  r  <- fit_logit(f, d, firth = firth)
  fit <- r$fit
  if (is.null(fit)) return(if (per_model) NULL else NA_real_)

  if (firth) {
    # logistf carries no predict() for new data, so build the linear predictor
    # from the model matrix directly under each counterfactual.
    mm1 <- stats::model.matrix(f, transform(d, home = 1L))
    mm0 <- stats::model.matrix(f, transform(d, home = 0L))
    b <- stats::coef(fit)
    b <- b[colnames(mm1)]
    p1 <- stats::plogis(as.vector(mm1 %*% b))
    p0 <- stats::plogis(as.vector(mm0 %*% b))
  } else {
    # A separated fit returns finite-looking numbers with meaningless standard
    # errors. Under strict = TRUE the replicate is FAILED rather than counted,
    # and boot_canon reports the failure instead of resampling past it.
    # Only an UNDEFINED fit is rejected; degenerate nuisance cells are reported
    # by the caller instead, because rejecting them would discard the very
    # estimate whose extrapolation the diagnostics are there to quantify.
    if (strict && sep_diagnose(fit)$blocking) return(if (per_model) NULL else NA_real_)
    p1 <- stats::predict(fit, newdata = transform(d, home = 1L), type = "response")
    p0 <- stats::predict(fit, newdata = transform(d, home = 0L), type = "response")
  }
  if (any(!is.finite(p1)) || any(!is.finite(p0)))
    return(if (per_model) NULL else NA_real_)

  w <- wfun(d, issue_col = ic)
  if (!per_model) return(sum(w * (p1 - p0)))
  ms <- sort(unique(as.character(d$model)))
  vapply(ms, function(m) {
    sel <- as.character(d$model) == m
    sum(w[sel] * (p1[sel] - p0[sel])) / sum(w[sel])
  }, numeric(1))
}

# =============================================================================
# Common support
# =============================================================================
# Positivity for this design is a JOINT condition. Restricting on one covariate
# at a time can leave cells that exist in only one arm, and the standardized
# contrast then extrapolates the outcome model into regions with no data. The
# stratum is defined over every covariate the outcome model conditions on.
support_cells <- function(d, cols = c("model", "domain", "route_f")) {
  cols <- intersect(cols, names(d))
  key <- .cell_key(d, cols)
  tibble(cell = key, home = d$home) %>%
    group_by(cell) %>%
    summarise(n_home = sum(home == 1), n_away = sum(home == 0),
              n = n(), .groups = "drop") %>%
    mutate(both_arms = n_home > 0 & n_away > 0)
}

# Built with base indexing rather than .data[[ ]] inside mutate: the tidy-eval
# form silently failed to find the loop variable and took the whole thing down.
.cell_key <- function(d, cols)
  do.call(paste, c(lapply(cols, function(k) as.character(d[[k]])), list(sep = " | ")))

# Restrict to jointly supported cells and report exactly what that cost, in the
# units a reader needs: rows, issues, cells, and the share of the nested target
# weight retained. A support restriction that silently drops 40% of the target
# weight is a different estimand, not a robustness check.
restrict_support <- function(d, cols = c("model", "domain", "route_f")) {
  cols <- intersect(cols, names(d))
  cells <- support_cells(d, cols)
  keep <- cells$cell[cells$both_arms]
  key <- .cell_key(d, cols)
  inside <- key %in% keep
  w_all <- w_nested(d)
  list(data = d[inside, , drop = FALSE],
       diag = tibble(cells_total = nrow(cells), cells_both_arms = sum(cells$both_arms),
                     rows_total = nrow(d), rows_retained = sum(inside),
                     issues_total = n_distinct(d$issue_id),
                     issues_retained = n_distinct(d$issue_id[inside]),
                     target_weight_retained = sum(w_all[inside]),
                     support_definition = paste(cols, collapse = " x ")))
}

# =============================================================================
# The judge panel: ONE loader, one resume-key rule
# =============================================================================
# There used to be two: 02_judge_reliability.R read annotations_panel.jsonl and
# 14 read <run_dir>/panel/<judge>/*.jsonl, with different de-duplication. Two
# loaders means the reliability number and the judge re-estimate could be
# computed on different rows without anything failing.
#
# RESUME KEY. The annotator's own resume predicate is
# (prompt_id, prompt_language, model) within a judge, and it appends on resume,
# so a repeated key means the response was re-judged. LAST WINS, matching the
# annotator. Uniqueness is asserted after collapsing rather than papered over
# with values_fn = first, which would hide a genuinely inconsistent record.
PANEL_KEY <- c("prompt_id", "prompt_language", "model", "judge_model")

# ANCHOR_JUDGE's labels are not in the panel: they ARE the analysis sample,
# produced in the main annotation pass. A loader that returns only the panel
# directories therefore returns three judges, and any reliability computed from
# it silently excludes the judge the paper actually reports.
ANCHOR_JUDGE <- "google/gemini-2.5-flash-lite"

load_judge_panel <- function(run_dir = RUN_DIR, language = "en",
                             fields = c("engagement_code"),
                             include_anchor = TRUE,
                             anchor_name = ANCHOR_JUDGE) {
  root <- file.path(run_dir, "panel")
  long <- file.path(run_dir, "annotations_panel.jsonl")
  out <- NULL

  if (dir.exists(root)) {
    dirs <- list.dirs(root, recursive = FALSE)
    out <- map_dfr(dirs, function(dd) {
      fs <- list.files(dd, pattern = "\\.jsonl$", full.names = TRUE)
      map_dfr(fs, function(f) {
        ls <- readLines(f, warn = FALSE); ls <- ls[nzchar(ls)]
        map_dfr(ls, function(l) {
          r <- tryCatch(jsonlite::fromJSON(l), error = function(e) NULL)
          if (is.null(r) || is.null(r$engagement_code) || !is.null(r$error)) return(NULL)
          if (!is.null(language) && !identical(r$prompt_language, language)) return(NULL)
          base <- tibble(prompt_id = r$prompt_id, prompt_language = r$prompt_language,
                         model = r$model)
          for (fl in fields)
            base[[fl]] <- if (is.null(r[[fl]])) NA else
              if (is.numeric(r[[fl]])) as.numeric(r[[fl]]) else as.character(r[[fl]])
          base
        })
      }) %>% mutate(judge_model = gsub("__", "/", basename(dd)))
    })
  } else if (file.exists(long)) {
    out <- jsonlite::stream_in(file(long), verbose = FALSE) %>% as_tibble()
    if (!is.null(language)) out <- out %>% filter(prompt_language == language)
  }
  if (is.null(out) || !nrow(out)) return(NULL)

  # Append the anchor from the analysis sample when it is not already present,
  # so both callers see the same judge set.
  if (include_anchor && !anchor_name %in% out$judge_model && exists("canon")) {
    keep <- intersect(c(fields, "issue_id"), names(canon))
    anc <- canon %>%
      { if (is.null(language)) . else filter(., prompt_language == language) } %>%
      select(prompt_id, prompt_language, model, all_of(keep)) %>%
      mutate(judge_model = anchor_name)
    out <- bind_rows(out, anc)
  }
  # Carry issue_id so downstream clustering does not need a second join.
  if (!"issue_id" %in% names(out) && exists("canon"))
    out <- out %>% left_join(canon %>% distinct(prompt_id, issue_id), by = "prompt_id")

  n_before <- nrow(out)
  out <- out %>% group_by(across(all_of(PANEL_KEY))) %>%
    slice_tail(n = 1) %>% ungroup()
  attr(out, "duplicates_collapsed") <- n_before - nrow(out)
  # Assert, do not assume.
  stopifnot(!anyDuplicated(out[PANEL_KEY]))
  out
}

# Backwards-compatible name; both call sites now share one implementation.
judge_labels <- function(run_dir = RUN_DIR, language = "en")
  load_judge_panel(run_dir, language, fields = "engagement_code")

# =============================================================================
# Agreement statistics
# =============================================================================
# TRUE positive specific agreement, for a PAIR of raters:
#     PSA = 2a / (2a + b + c)
# where a = both positive, b and c = the two disagreement cells. This is the
# standard definition (Cicchetti & Feinstein). It is a pairwise quantity; with
# k > 2 raters the defensible summary is the mean over pairs, with the range.
#
# What this replaces was NOT positive specific agreement: it computed, among
# units any rater called positive, the share where ALL raters agreed positive.
# That statistic falls mechanically as raters are added and has no standard
# interpretation. It is still available as all_rater_positive_unanimity(),
# under a name that says what it is.
psa_pair <- function(x, y) {
  keep <- !is.na(x) & !is.na(y)
  x <- x[keep]; y <- y[keep]
  a <- sum(x == 1 & y == 1); b <- sum(x == 1 & y == 0); cc <- sum(x == 0 & y == 1)
  if (2 * a + b + cc == 0) return(NA_real_)
  2 * a / (2 * a + b + cc)
}

psa_matrix <- function(m) {
  if (is.null(m) || ncol(m) < 2) return(NULL)
  js <- colnames(m); out <- list()
  for (i in seq_len(ncol(m) - 1)) for (j in (i + 1):ncol(m))
    out[[length(out) + 1]] <- tibble(judge_a = js[i], judge_b = js[j],
                                     n_pair = sum(!is.na(m[, i]) & !is.na(m[, j])),
                                     psa = psa_pair(m[, i], m[, j]))
  bind_rows(out)
}

psa_summary <- function(m) {
  pw <- psa_matrix(m)
  if (is.null(pw) || !nrow(pw)) return(tibble(psa_mean = NA_real_, psa_min = NA_real_,
                                              psa_max = NA_real_, n_pairs = 0L))
  tibble(psa_mean = mean(pw$psa, na.rm = TRUE),
         psa_min = min(pw$psa, na.rm = TRUE), psa_max = max(pw$psa, na.rm = TRUE),
         n_pairs = sum(!is.na(pw$psa)))
}

all_rater_positive_unanimity <- function(m) {
  if (is.null(m) || !nrow(m)) return(NA_real_)
  flagged <- apply(m, 1, function(r) any(r == 1, na.rm = TRUE))
  if (!any(flagged)) return(NA_real_)
  mean(apply(m[flagged, , drop = FALSE], 1,
             function(r) { r <- r[!is.na(r)]; all(r == 1) }))
}
