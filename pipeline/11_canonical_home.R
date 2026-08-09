# =============================================================================
# CANONICAL PART 1 -- geographic alignment and refusal
#   c02 home descriptive (English)      c05 home by model
#   c03 all-language supplement         c06 overlap tables
#   c04 home standardized               c07 sensitivities
# =============================================================================
# ESTIMAND NAME, used verbatim in every output and figure:
#     "covariate-standardized home-region refusal contrast"
#
# It is NOT causal, NOT a difference-in-differences, and NOT a within-issue
# effect. Adjustment controls MEASURED composition (prompt tier, topic domain,
# harvest route, subject model). It cannot remove unmeasured differences between
# home and away issues -- and there certainly are some: an issue's region is
# correlated with what the issue is about, how contested it is, and how much
# training data exists on it. A standardized contrast answers "among issues
# alike on the measured covariates, how much higher is refusal on home issues",
# and nothing stronger.

source("pipeline/10_canonical_common.R")
# build_f / estimable_chk / gcomp now live in 10_canonical_common.R:
# 14_canonical_judge_uncertainty.R refits the SAME specification under each
# judge, and a second copy here would let the two drift apart silently.
suppressPackageStartupMessages({ library(lme4); library(statmod) })
cat(strrep("=", 78), "\nCANONICAL PART 1: HOME REGION\n", strrep("=", 78), "\n", sep = "")

B_HEAD <- as.integer(Sys.getenv("CANON_B_HEAD", "2000"))
B_FIRTH <- as.integer(Sys.getenv("CANON_B_FIRTH", "200"))
B_SENS <- as.integer(Sys.getenv("CANON_B_SENS", "500"))

NOT_CAUSAL <- paste(
  "covariate-standardized home-region refusal contrast;",
  "NOT causal, NOT a difference-in-differences, NOT a within-issue effect;",
  "adjustment controls measured composition only and cannot remove unmeasured",
  "differences between home and away issues")

# The SAME English sample underlies the descriptive and the adjusted results.
ENG      <- CANON_ENGLISH
ENG_HA   <- ENG %>% filter(home_status %in% c("home", "away"))

# =============================================================================
# A. DESCRIPTIVE  (c02, c03)
# =============================================================================
cat("\nA. descriptive (English)\n")

cells_by <- function(d, group_label, ...) {
  d %>% group_by(..., home_status) %>%
    summarise(n = n(), refusals_strict = sum(refused_strict),
              refusals_any = sum(refused_any),
              rate_strict = mean(refused_strict), rate_any = mean(refused_any),
              n_issues = n_distinct(issue_id), .groups = "drop") %>%
    mutate(grouping = group_label)
}

# home - away difference; weighted mean over the resample, multiplicity-safe
diff_stat <- function(d, wfun = w_equal_model, outcome = "refused_strict") {
  ic <- if ("bootstrap_issue_instance" %in% names(d)) "bootstrap_issue_instance" else "issue_id"
  h <- d[d$home_status == "home", , drop = FALSE]
  a <- d[d$home_status == "away", , drop = FALSE]
  if (!nrow(h) || !nrow(a)) return(NA_real_)
  sum(wfun(h, issue_col = ic) * h[[outcome]]) -
    sum(wfun(a, issue_col = ic) * a[[outcome]])
}

diff_row <- function(d, key, wname, B, tag) {
  wfun <- switch(wname, response = w_response, equal_model = w_equal_model,
                 nested = w_nested)
  n_h <- sum(d$home_status == "home"); n_a <- sum(d$home_status == "away")
  if (!n_h || !n_a)
    return(tibble(!!!key, weighting = wname, estimate = NA_real_,
                  conf_low = NA_real_, conf_high = NA_real_,
                  estimate_pp = NA_real_, conf_low_pp = NA_real_,
                  conf_high_pp = NA_real_, n = nrow(d), n_home = n_h, n_away = n_a,
                  estimable = FALSE,
                  note = if (!n_h) "no home rows" else "no away rows"))
  bt <- boot_canon(d, function(x) diff_stat(x, wfun), B = B, label = tag)
  record_diag(bt$diag)
  tibble(!!!key, weighting = wname, estimate = bt$estimate,
         conf_low = bt$conf_low, conf_high = bt$conf_high,
         estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
         conf_high_pp = pp(bt$conf_high), n = nrow(d), n_home = n_h, n_away = n_a,
         estimable = TRUE, note = "")
}

c02_cells <- bind_rows(
  cells_by(ENG, "jurisdiction", jurisdiction = juris) %>%
    mutate(stratum_value = as.character(jurisdiction)),
  cells_by(ENG, "model", jurisdiction = juris, model) %>%
    mutate(stratum_value = model))

c02_diff <- bind_rows(
  map_dfr(JURIS_C, function(j) {
    d <- ENG_HA %>% filter(juris == j)
    map_dfr(c("response", "equal_model"), function(w)
      diff_row(d, list(grouping = "jurisdiction", jurisdiction = j,
                       stratum_value = j), w, B_HEAD,
               sprintf("c02|juris|%s|%s", j, w)))
  }),
  map_dfr(sort(unique(as.character(ENG_HA$model))), function(m) {
    d <- ENG_HA %>% filter(model == m)
    diff_row(d, list(grouping = "model",
                     jurisdiction = as.character(d$juris[1]), stratum_value = m),
             "response", B_SENS, sprintf("c02|model|%s", m))
  }))

c02 <- bind_rows(
  c02_cells %>% mutate(quantity = "observed_rate", weighting = "response",
                       estimate = rate_strict, estimate_pp = pp(rate_strict)),
  c02_diff %>% mutate(quantity = "home_minus_away")) %>%
  mutate(sample = "English only", outcome = "refused_strict (codes 4-5)",
         estimand = "descriptive difference in observed rates",
         causal_interpretation = "none: observed rates, unadjusted",
         general_handling = "General reported separately; never in the away category",
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(c02, file.path(CAN_EST, "c02_home_descriptive_english.csv"))
cat(sprintf("  c02: %d rows\n", nrow(c02)))

cat("A2. all-language supplement\n")
c03 <- bind_rows(
  cells_by(canon, "jurisdiction x language", jurisdiction = juris, language = lang) %>%
    mutate(quantity = "observed_rate", estimate = rate_strict,
           estimate_pp = pp(rate_strict)),
  map_dfr(JURIS_C, function(j) map_dfr(LANGS_C, function(lg) {
    d <- canon %>% filter(juris == j, lang == lg, home_status %in% c("home", "away"))
    diff_row(d, list(grouping = "jurisdiction x language", jurisdiction = j,
                     language = lg), "equal_model", B_SENS,
             sprintf("c03|%s|%s", j, lg)) %>% mutate(quantity = "home_minus_away")
  }))) %>%
  mutate(sample = "ALL languages (SUPPLEMENTARY; the primary sample is English)",
         outcome = "refused_strict (codes 4-5)",
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(c03, file.path(CAN_EST, "c03_home_descriptive_all_languages_supplement.csv"))
cat(sprintf("  c03: %d rows\n", nrow(c03)))

# =============================================================================
# B. STANDARDIZED  (c04, c05)
# =============================================================================
cat("\nB. standardized contrast\n")




std_row <- function(d, key, wname, B, tag, outcome = "refused_strict",
                    firth = FALSE) {
  wfun <- switch(wname, nested = w_nested, response = w_response,
                 equal_model = w_equal_model)
  # estimable_chk is asked about the OUTCOME actually being fitted.
  why <- estimable_chk(d, outcome)
  base <- tibble(!!!key, weighting = wname, outcome = outcome,
                 estimator = if (firth) "Firth penalized logit" else "maximum likelihood",
                 n = nrow(d), n_issues = n_distinct(d$issue_id),
                 n_models = n_distinct(d$model),
                 events_home = sum(d[[outcome]][d$home == 1]),
                 events_away = sum(d[[outcome]][d$home == 0]))
  # Fit once on the full data to record what the estimator actually did:
  # warnings, separation, and whether every parameter is finite.
  probe <- fit_logit(build_f(d, outcome), d, firth = firth)
  sep <- sep_diagnose(probe$fit, w = wfun(d))
  base <- bind_cols(base, tibble(
    glm_warnings = paste(unique(probe$warnings), collapse = " | "),
    separation_detected = sep$separated,
    separation_blocking = sep$blocking,
    separation_reason = sep$why,
    # Two different diagnostics, named for what each measures.
    observed_fit_extreme_weight = sep$observed_fit_extreme_weight,
    counterfactual_extreme_weight = cf_extreme_weight(probe$fit, d, wfun(d), outcome)))

  if (nzchar(why) || sep$blocking)
    return(bind_cols(base, tibble(
      estimate = NA_real_, conf_low = NA_real_, conf_high = NA_real_,
      estimate_pp = NA_real_, conf_low_pp = NA_real_, conf_high_pp = NA_real_,
      estimable = FALSE, interval_reliable = FALSE, replicate_failure_rate = NA_real_,
      note = if (nzchar(why)) why else paste("separation:", sep$why))))

  bt <- boot_canon(d, function(x) gcomp(x, wfun, outcome, firth = firth),
                   B = B, label = tag)
  record_diag(bt$diag)
  bind_cols(base, tibble(
    estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high,
    estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
    conf_high_pp = pp(bt$conf_high), estimable = TRUE,
    interval_reliable = bt$interval_reliable,
    replicate_failure_rate = bt$failure_rate,
    note = if (bt$interval_reliable) "" else
      sprintf("UNRELIABLE INTERVAL: %.1f%% of bootstrap draws had no defined estimate",
              100 * bt$failure_rate)))
}

cat("  primary (nested weights) + response-weighted sensitivity, B =", B_HEAD, "\n")

# Two standardized estimands, reported side by side, because they answer
# different questions:
#
#   FULL TARGET     -- standardize over every issue in the jurisdiction's arm.
#                      Where a covariate cell appears in only one arm, the
#                      outcome model EXTRAPOLATES into it. That is a modelling
#                      assumption, not data.
#   COMMON SUPPORT  -- restrict to cells present in BOTH arms first, then
#                      standardize. No extrapolation, but the target population
#                      is now those cells, and the retained target weight says
#                      how much of the original target that is.
SUPPORT_COLS <- c("model", "domain", "route_f", "tier")

sup_diag <- map_dfr(JURIS_C, function(j) {
  d <- ENG_HA %>% filter(juris == j) %>% droplevels()
  restrict_support(d, SUPPORT_COLS)$diag %>% mutate(jurisdiction = j, .before = 1)
}) %>% mutate(
  # The transparent measure of how much of the original target the
  # non-extrapolative estimand gives up.
  unsupported_target_weight = 1 - target_weight_retained,
  canonical_run_id = CANONICAL_RUN_ID)
write_csv(sup_diag, file.path(CAN_EST, "c06b_common_support_diagnostics.csv"))
cat("  common support (jurisdiction x model x domain x route x tier):\n")
print(as.data.frame(sup_diag %>% select(jurisdiction, cells_total, cells_both_arms,
                                        rows_retained, rows_total,
                                        target_weight_retained)),
      digits = 3, row.names = FALSE)

c04 <- map_dfr(JURIS_C, function(j) {
  d <- ENG_HA %>% filter(juris == j) %>% droplevels()
  sup <- restrict_support(d, SUPPORT_COLS)
  ds <- sup$data %>% droplevels()
  bind_rows(
    map_dfr(c("nested", "response"), function(w) {
      cat(sprintf("    %-6s %-9s full-target   n=%d\n", j, w, nrow(d)))
      std_row(d, list(jurisdiction = j, support = "full target"), w, B_HEAD,
              sprintf("c04|%s|%s|full", j, w))
    }),
    {
      cat(sprintf("    %-6s %-9s common-supp   n=%d\n", j, "nested", nrow(ds)))
      std_row(ds, list(jurisdiction = j, support = "common support"), "nested",
              B_HEAD, sprintf("c04|%s|nested|cs", j)) %>%
        mutate(target_weight_retained = sup$diag$target_weight_retained,
             unsupported_target_weight = 1 - sup$diag$target_weight_retained,
               cells_both_arms = sup$diag$cells_both_arms,
               cells_total = sup$diag$cells_total)
    },
    # Declared penalized-logit sensitivity: where ML is undefined (separation),
    # Firth still has a defined estimator in every replicate, so an interval
    # exists at all. Reported as a sensitivity, never as the primary.
    {
      cat(sprintf("    %-6s %-9s Firth         n=%d\n", j, "nested", nrow(d)))
      # Firth is ~37x slower per fit than ML, so the declared penalized-logit
      # sensitivity uses its own, smaller replicate count. Recorded in c18.
      std_row(d, list(jurisdiction = j, support = "full target"), "nested",
              B_FIRTH, sprintf("c04|%s|firth", j), firth = TRUE)
    })
}) %>%
  mutate(spec = "refused_strict ~ home * model + tier + domain + route (per jurisdiction; home + ... when single-model)",
         region_fixed_effects = "EXCLUDED: region determines home within jurisdiction",
         sample = "English, home vs away, General excluded",
         support_definition = paste(SUPPORT_COLS, collapse = " x "),
         target_population = ifelse(weighting == "nested",
           "equal weight per model; within model equal per issue; within model-issue equal per prompt (PRIMARY)",
           "empirical response composition (SENSITIVITY)"),
         estimand = ifelse(support == "common support",
           "covariate-standardized home contrast on cells present in BOTH arms",
           "covariate-standardized home contrast over the full jurisdiction arm"),
         extrapolation = ifelse(support == "common support",
           "none: restricted to jointly supported cells",
           "EXTRAPOLATES into covariate cells observed in only one arm; the outcome model supplies those predictions"),
         causal_interpretation = NOT_CAUSAL,
         uncertainty = "issue-cluster bootstrap; multiplicity preserved; fixed B draws; failures counted, never replaced; percentile",
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(c04, file.path(CAN_EST, "c04_home_standardized.csv"))
cat("\n  PRIMARY (nested, full target) and common support:\n")
print(as.data.frame(c04 %>% filter(weighting == "nested",
                                   estimator == "maximum likelihood") %>%
        select(jurisdiction, support, n, events_home, events_away, estimate_pp,
               conf_low_pp, conf_high_pp, estimable, interval_reliable)),
      digits = 3, row.names = FALSE)

cat("\n  model-specific standardized contrasts\n")
c05 <- map_dfr(JURIS_C, function(j) {
  d <- ENG_HA %>% filter(juris == j) %>% droplevels()
  why <- estimable_chk(d, "refused_strict")
  ms <- sort(unique(as.character(d$model)))
  if (nzchar(why))
    return(tibble(jurisdiction = j, model = ms, estimate = NA_real_,
                  conf_low = NA_real_, conf_high = NA_real_,
                  estimable = FALSE, note = why))
  per_model <- map_dfr(ms, function(m) {
    st <- function(x) {
      v <- gcomp(x, w_nested, per_model = TRUE)
      if (is.null(v) || !m %in% names(v)) return(NA_real_)
      unname(v[[m]])
    }
    bt <- boot_canon(d, st, B = B_SENS, label = sprintf("c05|%s|%s", j, m))
    record_diag(bt$diag)
    tibble(jurisdiction = j, model = m, estimate = bt$estimate,
           conf_low = bt$conf_low, conf_high = bt$conf_high, estimable = TRUE,
           interval_reliable = bt$interval_reliable, note = "")
  })
  # The equal-model average is bootstrapped JOINTLY, in the same replicates that
  # produced the model-specific numbers, so it carries an interval. Averaging
  # the point estimates afterwards produced a number with no uncertainty at all,
  # and averaging the per-model intervals would have been wrong anyway: the
  # model-specific contrasts within a jurisdiction are estimated on the SAME
  # issues and are strongly dependent.
  st_avg <- function(x) {
    v <- gcomp(x, w_nested, per_model = TRUE)
    if (is.null(v)) return(NA_real_)
    mean(v)
  }
  bavg <- boot_canon(d, st_avg, B = B_SENS, label = sprintf("c05|%s|EQUALMODEL", j))
  record_diag(bavg$diag)
  bind_rows(per_model,
            tibble(jurisdiction = j, model = "EQUAL-MODEL AVERAGE",
                   estimate = bavg$estimate, conf_low = bavg$conf_low,
                   conf_high = bavg$conf_high, estimable = TRUE,
                   interval_reliable = bavg$interval_reliable,
                   note = "jointly bootstrapped mean of this jurisdiction's model-specific contrasts"))
}) %>% mutate(estimate_pp = pp(estimate), conf_low_pp = pp(conf_low),
              conf_high_pp = pp(conf_high),
              estimand = "model-specific covariate-standardized home contrast",
              causal_interpretation = NOT_CAUSAL,
              canonical_run_id = CANONICAL_RUN_ID)
write_csv(c05, file.path(CAN_EST, "c05_home_by_model.csv"))
cat(sprintf("  c05: %d rows\n", nrow(c05)))

# =============================================================================
# C. OVERLAP (positivity)  c06
# =============================================================================
# A standardized contrast is only supported where BOTH arms are observed within
# a covariate stratum. Where a stratum carries only home or only away rows, the
# model is extrapolating rather than comparing.
cat("\nC. overlap tables\n")
ov <- function(d, name, ...) {
  d %>% group_by(jurisdiction = as.character(juris), ...) %>%
    summarise(n_home = sum(home_status == "home"),
              n_away = sum(home_status == "away"), .groups = "drop") %>%
    mutate(stratum = name, both_arms = n_home > 0 & n_away > 0,
           across(where(is.factor), as.character))
}
c06 <- bind_rows(
  ov(ENG_HA, "model", model) %>% rename(level = model),
  ov(ENG_HA, "domain", domain) %>% rename(level = domain),
  ov(ENG_HA, "route", route_f) %>% rename(level = route_f),
  ov(ENG_HA, "tier", tier) %>% rename(level = tier),
  ov(ENG_HA, "domain x route", domain, route_f) %>%
    mutate(level = paste(domain, route_f, sep = " | ")) %>% select(-domain, -route_f),
  ov(ENG_HA, "model x domain", model, domain) %>%
    mutate(level = paste(model, domain, sep = " | ")) %>% select(-model, -domain)) %>%
  mutate(canonical_run_id = CANONICAL_RUN_ID)
write_csv(c06, file.path(CAN_EST, "c06_home_overlap.csv"))
cat(sprintf("  c06: %d strata; %d lack an arm\n", nrow(c06), sum(!c06$both_arms)))

# =============================================================================
# D. SENSITIVITIES  c07
# =============================================================================
cat("\nD. sensitivities (B =", B_SENS, ")\n")
sens <- list()

# --- functional form ---------------------------------------------------------
# The primary specification enters topic domain and seed route ADDITIVELY, which
# assumes the home contrast does not vary across them. That is an assumption, not
# a finding, so it is tested directly: refit with home x domain and with
# home x route wherever the interaction is estimable, and standardize as before.
# Cells that cannot support an interaction are reported rather than dropped.
cat("  functional form: home x domain, home x route\n")
ff_row <- function(d, j, term, tag) {
  f_add <- build_f(d, "refused_strict")
  f_int <- stats::as.formula(paste(deparse(f_add, width.cutoff = 500),
                                   "+ home:", term))
  base <- tibble(sensitivity = "functional_form", jurisdiction = j,
                 level = paste0("home x ", term), weighting = "nested",
                 n = nrow(d), n_issues = n_distinct(d$issue_id),
                 n_models = n_distinct(d$model))
  # Estimable only if the interacting factor varies and every level has both arms.
  lv <- droplevels(factor(d[[term]]))
  tab <- table(lv, d$home)
  if (nlevels(lv) < 2 || any(tab == 0))
    return(bind_cols(base, tibble(estimate = NA_real_, conf_low = NA_real_,
                                  conf_high = NA_real_, estimable = FALSE,
                                  note = "interaction not estimable: a level lacks one arm")))
  st <- function(x) {
    r <- fit_logit(f_int, x)
    if (is.null(r$fit) || sep_diagnose(r$fit)$blocking) return(NA_real_)
    p1 <- stats::predict(r$fit, newdata = transform(x, home = 1L), type = "response")
    p0 <- stats::predict(r$fit, newdata = transform(x, home = 0L), type = "response")
    if (any(!is.finite(p1)) || any(!is.finite(p0))) return(NA_real_)
    ic <- if ("bootstrap_issue_instance" %in% names(x)) "bootstrap_issue_instance" else "issue_id"
    sum(w_nested(x, issue_col = ic) * (p1 - p0))
  }
  bt <- boot_canon(d, st, B = B_SENS, label = tag)
  record_diag(bt$diag)
  bind_cols(base, tibble(estimate = bt$estimate, conf_low = bt$conf_low,
                         conf_high = bt$conf_high, estimable = TRUE,
                         note = if (bt$interval_reliable) "" else
                           sprintf("UNRELIABLE: %.1f%% of draws undefined",
                                   100 * bt$failure_rate)))
}
sens$functional_form <- map_dfr(JURIS_C, function(j) {
  d <- ENG_HA %>% filter(juris == j) %>% droplevels()
  if (nzchar(estimable_chk(d, "refused_strict"))) return(NULL)
  bind_rows(ff_row(d, j, "domain", sprintf("c07|ff|dom|%s", j)),
            ff_row(d, j, "route_f", sprintf("c07|ff|route|%s", j)))
})

cat("  leave-one-model-out\n")
sens$lomo <- map_dfr(JURIS_C, function(j) {
  d <- ENG_HA %>% filter(juris == j)
  ms <- sort(unique(as.character(d$model)))
  if (length(ms) < 2) return(NULL)
  map_dfr(ms, function(m)
    std_row(d %>% filter(model != m) %>% droplevels(),
            list(jurisdiction = j, sensitivity = "leave_one_model_out",
                 level = paste0("drop_", m)), "nested", B_SENS,
            sprintf("c07|lomo|%s|%s", j, m)))
})

cat("  prompt type\n")
sens$tier <- map_dfr(JURIS_C, function(j) map_dfr(c("regular", "boundary"), function(t)
  std_row(ENG_HA %>% filter(juris == j, tier == t) %>% droplevels(),
          list(jurisdiction = j, sensitivity = "prompt_type", level = t),
          "nested", B_SENS, sprintf("c07|tier|%s|%s", j, t))))

cat("  language\n")
sens$lang <- map_dfr(JURIS_C, function(j) map_dfr(LANGS_C, function(lg)
  std_row(canon %>% filter(juris == j, lang == lg,
                           home_status %in% c("home", "away")) %>% droplevels(),
          list(jurisdiction = j, sensitivity = "language", level = lg),
          "nested", B_SENS, sprintf("c07|lang|%s|%s", j, lg))))

cat("  code-3 (any-refusal outcome)\n")
sens$code3 <- map_dfr(JURIS_C, function(j)
  std_row(ENG_HA %>% filter(juris == j) %>% droplevels(),
          list(jurisdiction = j, sensitivity = "outcome_code3",
               level = "refused_any (codes 3-5)"), "nested", B_SENS,
          sprintf("c07|code3|%s", j), outcome = "refused_any"))

cat("  response length\n")
if (!is.null(CANON_LEN)) {
  eng_len <- ENG_HA %>% left_join(CANON_LEN,
    by = c("prompt_id", "prompt_language", "model"))
  sens$len <- map_dfr(JURIS_C, function(j) map_dfr(c(20, 50, 100), function(thr)
    std_row(eng_len %>% filter(juris == j, !is.na(response_chars),
                               response_chars >= thr) %>% droplevels(),
            list(jurisdiction = j, sensitivity = "min_response_chars",
                 level = as.character(thr)), "nested", B_SENS,
            sprintf("c07|len%d|%s", thr, j))))
}

cat("  overlap-restricted\n")
# Restrict to model x domain strata where BOTH arms appear, so the contrast is
# supported by comparison rather than extrapolation.
ok_cells <- c06 %>% filter(stratum == "model x domain", both_arms) %>%
  transmute(jurisdiction, key = level)
sens$overlap <- map_dfr(JURIS_C, function(j) {
  keys <- ok_cells$key[ok_cells$jurisdiction == j]
  d <- ENG_HA %>% filter(juris == j) %>%
    mutate(key = paste(model, domain, sep = " | ")) %>%
    filter(key %in% keys) %>% droplevels()
  std_row(d, list(jurisdiction = j, sensitivity = "overlap_restricted",
                  level = "model x domain strata with both arms"),
          "nested", B_SENS, sprintf("c07|overlap|%s", j))
})

cat("  hierarchical (marginal predictions, deterministic quadrature)\n")
# Deterministic Gauss-Hermite over the SUM of the two independent random
# effects (u_issue + u_prompt ~ N(0, s1^2 + s2^2)), rather than a few hundred
# Monte Carlo draws. Kept SUPPLEMENTARY and reported only if the fit converges:
# an unconverged fit must not be given an interval or a point beside fully
# bootstrapped estimates.
marg_gcomp <- function(d, nq = 40L) {
  f <- as.formula(paste(deparse(build_f(d), width.cutoff = 500),
                        "+ (1|issue_id) + (1|prompt_id)"))
  m <- tryCatch(glmer(f, data = d, family = binomial,
                      control = glmerControl(optimizer = "bobyqa",
                                             optCtrl = list(maxfun = 2e5))),
                error = function(e) NULL, warning = function(w) NULL)
  if (is.null(m)) return(list(est = NA_real_, note = "did not converge"))
  msg <- m@optinfo$conv$lme4$messages
  if (!is.null(msg)) return(list(est = NA_real_,
                                 note = paste("not estimable:", paste(msg, collapse = "; "))))
  sig <- sqrt(sum(as.data.frame(VarCorr(m))$vcov))
  gq <- statmod::gauss.quad.prob(nq, dist = "normal", mu = 0, sigma = sig)
  b <- fixef(m)
  e1 <- as.vector(model.matrix(terms(m), transform(d, home = 1L)) %*% b)
  e0 <- as.vector(model.matrix(terms(m), transform(d, home = 0L)) %*% b)
  p1 <- rowSums(vapply(seq_len(nq), function(k) gq$weights[k] * plogis(e1 + gq$nodes[k]),
                       numeric(length(e1))))
  p0 <- rowSums(vapply(seq_len(nq), function(k) gq$weights[k] * plogis(e0 + gq$nodes[k]),
                       numeric(length(e0))))
  list(est = sum(w_nested(d) * (p1 - p0)), note = "")
}
sens$hier <- map_dfr(JURIS_C, function(j) {
  d <- ENG_HA %>% filter(juris == j) %>% droplevels()
  why <- estimable_chk(d)
  if (nzchar(why))
    return(tibble(jurisdiction = j, sensitivity = "hierarchical_marginal",
                  level = "(1|issue_id)+(1|prompt_id)", estimable = FALSE,
                  note = why, n = nrow(d), weighting = "nested"))
  r <- marg_gcomp(d)
  tibble(jurisdiction = j, sensitivity = "hierarchical_marginal",
         level = "(1|issue_id)+(1|prompt_id)",
         estimable = !is.na(r$est), estimate = r$est, estimate_pp = pp(r$est),
         n = nrow(d), weighting = "nested",
         note = paste0(r$note, if (is.na(r$est)) "" else
           " SUPPLEMENTARY: point only, no bootstrap; not plotted beside bootstrapped estimates"))
})

c07 <- bind_rows(sens) %>%
  mutate(estimand = "covariate-standardized home-region refusal contrast (sensitivity)",
         causal_interpretation = NOT_CAUSAL,
         sample = ifelse(sensitivity == "language", paste("language:", level), "English"),
         canonical_run_id = CANONICAL_RUN_ID) %>%
  select(canonical_run_id, sensitivity, jurisdiction, level, weighting, n,
         n_issues, n_models, events_home, events_away, estimate, conf_low,
         conf_high, estimate_pp, conf_low_pp, conf_high_pp, estimable, note,
         everything())
write_csv(c07, file.path(CAN_EST, "c07_home_sensitivities.csv"))
cat(sprintf("\n  c07: %d rows across %d sensitivity families\n",
            nrow(c07), n_distinct(c07$sensitivity)))

# --- c07c: the sensitivity CATALOGUE, classified by what each row changes -----
# The single word "robustness" was doing far too much work. These rows are not
# all alternative estimators of one estimand: some change the ESTIMATOR while
# holding the target fixed, some change the TARGET POPULATION, some change the
# OUTCOME DEFINITION, and one conditions on a property of the response that is
# only known AFTER the outcome. Putting them in one undifferentiated forest
# invited exactly the reading that overlapping intervals mean agreement about
# the same quantity.
#
# The classification is explicit here so the figure can plot only the
# same-target comparisons and the table can carry the rest.
SENS_CLASS <- tribble(
  ~sensitivity,            ~change_class,                ~target_changed, ~note,
  "leave_one_model_out",   "D. model roster",            TRUE,
    "drops a model, so the equal-model target is over a different roster",
  "prompt_type",           "B. target population",       TRUE,
    "restricts to one prompt tier",
  "language",              "B. target population",       TRUE,
    "restricts to one prompt language",
  "outcome_code3",         "C. outcome definition",      FALSE,
    "same target, different label threshold (codes 3-5 rather than 4-5)",
  "functional_form",       "A. estimator, same target",  FALSE,
    "alternative adjustment terms for the same standardized contrast",
  "overlap_restricted",    "B. target population",       TRUE,
    "common support: covariate cells present in both arms only",
  "min_response_chars",    "E. POST-OUTCOME diagnostic", TRUE,
    "conditions on a realized property of the response; NOT design robustness",
  "hierarchical_marginal", "F. different estimand",      TRUE,
    "integrates over the issue random effect instead of standardizing")

prim_pp <- c04 %>%
  filter(weighting == "nested", support == "full target",
         estimator == "maximum likelihood") %>%
  transmute(jurisdiction, primary_pp = estimate_pp,
            primary_estimable = estimable)

c07c <- c07 %>%
  left_join(SENS_CLASS, by = "sensitivity") %>%
  left_join(prim_pp, by = "jurisdiction") %>%
  mutate(
    difference_from_primary_pp = estimate_pp - primary_pp,
    plottable = estimable & is.finite(estimate_pp) & is.finite(conf_low_pp),
    # `estimable` records that a FIT WAS ATTEMPTED, not that an estimate exists.
    # Anything consuming this table must use `plottable`.
    estimable_flag_note = paste("`estimable` means a fit was attempted;",
                                "`plottable` means a point AND an interval",
                                "exist. Five functional-form rows are",
                                "estimable = TRUE with no estimate."),
    difference_note = paste("difference_from_primary_pp is a DIFFERENCE OF",
                            "POINT ESTIMATES. No interval is given for it:",
                            "subtracting marginal endpoints is not a paired",
                            "contrast, and the paired issue bootstrap that",
                            "would be required is not run for these rows."),
    canonical_run_id = CANONICAL_RUN_ID) %>%
  select(sensitivity, change_class, target_changed, jurisdiction, level,
         estimate_pp, conf_low_pp, conf_high_pp, primary_pp,
         difference_from_primary_pp, n, n_issues, n_models,
         events_home, events_away, estimable, plottable, interval_reliable,
         replicate_failure_rate, glm_warnings, separation_detected,
         everything())
write_csv(c07c, file.path(CAN_EST, "c07c_sensitivity_catalogue.csv"))
cat(sprintf("  c07c: %d rows; %d plottable; classes %s\n", nrow(c07c),
            sum(c07c$plottable),
            paste(sort(unique(c07c$change_class)), collapse = " / ")))

# --- c07b: the hierarchical marginal estimate, split out as a table -----------
# A DIFFERENT ESTIMAND, not a sensitivity of the standardized contrast: it
# integrates over the issue random effect instead of standardizing over the
# observed issue set, and it has no comparable interval. It is tabulated here so
# it can never be read as a competing point in a forest of estimates that do
# target the same quantity.
#
# This table used to be written by 21_figures_extended.R. A plotting script must
# not be the sole implementation of a canonical output: the table then exists
# only if the figure ran, and it changes whenever the artwork does.
hier <- c07 %>% filter(sensitivity == "hierarchical_marginal")
if (nrow(hier))
  write_csv(hier %>% mutate(
      note = paste("DIFFERENT ESTIMAND: integrates over the issue random",
                   "effect instead of standardizing over the observed issue",
                   "set. Not comparable to the sensitivity forest and",
                   "deliberately not plotted beside it."),
      canonical_run_id = CANONICAL_RUN_ID),
    file.path(CAN_EST, "c07b_hierarchical_marginal.csv"))
print(as.data.frame(c07 %>% filter(sensitivity == "hierarchical_marginal") %>%
        select(jurisdiction, estimable, estimate_pp, note)), digits = 3, row.names = FALSE)

flush_diag()
cat("\n", strrep("=", 78), "\nPART 1 DONE\n", strrep("=", 78), "\n", sep = "")
