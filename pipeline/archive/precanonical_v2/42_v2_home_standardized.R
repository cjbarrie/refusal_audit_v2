# =============================================================================
# v2 FAMILY B -- STANDARDIZED home-region contrasts
#   -> e33_home_standardized_equal_weight.csv
#   -> e34_home_standardized_response_weight.csv
#   -> e35_home_standardized_sensitivities.csv
#   (bootstrap diagnostics append to e39)
# =============================================================================
# WHAT THIS IS, AND WHAT IT IS NOT
# -----------------------------------------------------------------------------
# This is a COVARIATE-STANDARDIZED CONTRAST in the probability of refusal between
# home-region and away-region issues, computed separately within each
# jurisdiction and standardized to a stated target population.
#
# It is NOT causal. It is NOT a difference-in-differences. It is NOT a
# within-issue effect. `home` is a fixed property of an issue's region; nothing
# randomises it, and no comparison here holds an issue fixed while varying home.
# Every row of every output carries that statement, and
# 46_v2_acceptance_tests.R fails the build if the words "causal", "DiD" or
# "within-issue" ever attach to a Family B quantity.
#
# SPECIFICATION
#     refused ~ home + tier + domain + route + model        (per jurisdiction)
#
# No region fixed effects: within a jurisdiction, region DETERMINES home, so a
# region term would be collinear with the contrast of interest and the model
# would not be identified.
#
# LANGUAGE. The specification carries no language term, so pooling five languages
# into one fit would be misspecified -- language effects in this study are large
# (up to +62 pp) and would load onto the other terms. The primary fit is
# therefore ENGLISH ONLY, and language enters as a sensitivity that repeats the
# whole procedure within each language. This is a stated modelling choice, not a
# derivation.
#
# SAMPLE. home vs away only. General issues have no home jurisdiction and are
# excluded from Family B entirely; they are reported descriptively in e32.
#
# STANDARDIZATION TARGETS
#   primary     equal weight per tested MODEL and ISSUE  (e33)
#   sensitivity empirical response weighting             (e34)
#
# UNCERTAINTY. Issue-cluster bootstrap with the COMPLETE MODEL REFIT and the
# standardization recomputed inside every replicate; >= 2,000 successful
# replicates; percentile intervals. Fixed-coefficient simulation is not used as
# the primary interval method anywhere in this family.

source("pipeline/archive/precanonical_v2/40_v2_common.R")
cat(strrep("=", 78), "\nFAMILY B: STANDARDIZED HOME CONTRASTS\n", strrep("=", 78), "\n", sep = "")

B_PRIMARY <- 2000L
B_SENS    <- 500L
# V2_ONLY=primary re-runs just the primary contrasts. Used to regenerate their
# bootstrap DIAGNOSTICS without repeating the (much longer) sensitivity suite.
# The seed is fixed, so the estimates it rewrites are identical to the originals.
V2_ONLY <- Sys.getenv("V2_ONLY", "")

NOT_CAUSAL <- paste(
  "covariate-standardized contrast in refusal probability;",
  "NOT causal, NOT a difference-in-differences, NOT a within-issue effect;",
  "home is a fixed property of the issue region and is not randomised")

# --- sample -------------------------------------------------------------------
bsample <- function(d, language = "en") {
  d %>% filter(home_status %in% c("home", "away"),
               if (is.null(language)) TRUE else as.character(lang) == language) %>%
    droplevels()
}

# Drop terms with no variation in the subsample rather than letting glm return a
# rank-deficient fit with silent NA coefficients (single-model jurisdictions have
# no `model` term; some strata have one route or one tier).
build_formula <- function(d, outcome = "refused_strict") {
  rhs <- "home"
  for (v in c("tier", "domain", "route_f2", "model_f2"))
    if (nlevels(droplevels(factor(d[[v]]))) > 1) rhs <- c(rhs, v)
  as.formula(paste(outcome, "~", paste(rhs, collapse = " + ")))
}

# g-computation on the probability scale
gcomp <- function(d, wfun, outcome = "refused_strict") {
  f <- build_formula(d, outcome)
  fit <- suppressWarnings(glm(f, data = d, family = binomial))
  if (!fit$converged) return(NA_real_)
  p1 <- predict(fit, newdata = transform(d, home = 1L), type = "response")
  p0 <- predict(fit, newdata = transform(d, home = 0L), type = "response")
  sum(wfun(d) * (p1 - p0))
}

# Separation / estimability guard. EU is preserved as DESCRIPTIVELY OBSERVED but
# statistically nonestimable: Mistral records zero refusals, so no finite
# contrast exists and one must not be manufactured.
estimable <- function(d) {
  if (!nrow(d)) return(list(ok = FALSE, why = "no rows"))
  if (sum(d$refused_strict) == 0)
    return(list(ok = FALSE, why = "0 observed refusals (complete separation)"))
  if (length(unique(d$home)) < 2)
    return(list(ok = FALSE, why = "home does not vary"))
  ev_home <- sum(d$refused_strict[d$home == 1])
  ev_away <- sum(d$refused_strict[d$home == 0])
  if (ev_home == 0 || ev_away == 0)
    return(list(ok = FALSE, why = sprintf("separation: %d home / %d away events",
                                          ev_home, ev_away)))
  list(ok = TRUE, why = "")
}

run_contrast <- function(d, wname, label, B) {
  wfun <- switch(wname, equal_model_issue = w_equal_model_issue,
                 response = w_response, equal_model = w_equal_model)
  es <- estimable(d)
  base <- tibble(
    n = nrow(d), n_issues = n_distinct(d$issue_id), n_models = n_distinct(d$model),
    events_total = sum(d$refused_strict),
    events_home = sum(d$refused_strict[d$home == 1]),
    events_away = sum(d$refused_strict[d$home == 0]),
    weighting = wname, estimable = es$ok, note = es$why)
  if (!es$ok)
    return(bind_cols(base, tibble(estimate = NA_real_, conf_low = NA_real_,
                                  conf_high = NA_real_, estimate_pp = NA_real_,
                                  conf_low_pp = NA_real_, conf_high_pp = NA_real_)))
  bt <- boot_issue(d, function(x) gcomp(x, wfun), B = B, seed = V2_SEED, label = label)
  append_boot_diag(bt$diag)
  bind_cols(base, tibble(estimate = bt$estimate, conf_low = bt$conf_low,
                         conf_high = bt$conf_high, estimate_pp = pp(bt$estimate),
                         conf_low_pp = pp(bt$conf_low), conf_high_pp = pp(bt$conf_high)))
}

JURIS <- c("CN", "MENA", "India", "US", "EU")

# --- e33 / e34 primary + response-weighted -----------------------------------
cat("\nprimary contrasts (English; B =", B_PRIMARY, "; refit inside every replicate)\n")
primary <- map_dfr(JURIS, function(j) {
  d <- bsample(v2 %>% filter(juris == j))
  map_dfr(c("equal_model_issue", "response"), function(w) {
    cat(sprintf("  %-6s %-18s n=%d\n", j, w, nrow(d)))
    run_contrast(d, w, sprintf("B|primary|%s|%s", j, w), B_PRIMARY) %>%
      mutate(jurisdiction = j, language = "en", spec = "refused ~ home + tier + domain + route + model")
  })
}) %>% mutate(estimand_family = "B_standardized",
              estimand_label = "covariate-standardized home-minus-away refusal contrast",
              target_population = ifelse(weighting == "equal_model_issue",
                "equal weight per tested model and issue (PRIMARY)",
                "empirical response composition (SENSITIVITY)"),
              causal_interpretation = NOT_CAUSAL,
              outcome = "refused_strict (engagement_code >= 4)",
              uncertainty = "issue-cluster bootstrap, model refit per replicate, percentile")

write_csv(primary %>% filter(weighting == "equal_model_issue"),
          file.path(EST, "e33_home_standardized_equal_weight.csv"))
write_csv(primary %>% filter(weighting == "response"),
          file.path(EST, "e34_home_standardized_response_weight.csv"))
cat("\nPRIMARY (equal model x issue):\n")
print(as.data.frame(primary %>% filter(weighting == "equal_model_issue") %>%
        select(jurisdiction, n, events_home, events_away, estimate_pp,
               conf_low_pp, conf_high_pp, estimable)), digits = 3, row.names = FALSE)

if (identical(V2_ONLY, "primary")) {
  cat("\nV2_ONLY=primary -- sensitivities skipped; e35 left as-is\n")
  quit(save = "no", status = 0)
}

# --- e35 sensitivities --------------------------------------------------------
cat("\nsensitivities (B =", B_SENS, ")\n")
sens <- list()

# (1) per model
cat("  per-model\n")
sens$per_model <- map_dfr(JURIS, function(j) {
  dj <- bsample(v2 %>% filter(juris == j))
  map_dfr(sort(unique(as.character(dj$model))), function(mm) {
    d <- dj %>% filter(model == mm) %>% droplevels()
    run_contrast(d, "equal_model_issue", sprintf("B|per_model|%s|%s", j, mm), B_SENS) %>%
      mutate(jurisdiction = j, sensitivity = "per_model", level = mm)
  })
})

# (2) leave-one-model-out (multi-model jurisdictions only)
cat("  leave-one-model-out\n")
sens$lomo <- map_dfr(JURIS, function(j) {
  dj <- bsample(v2 %>% filter(juris == j))
  ms <- sort(unique(as.character(dj$model)))
  if (length(ms) < 2) return(NULL)
  map_dfr(ms, function(mm) {
    d <- dj %>% filter(model != mm) %>% droplevels()
    run_contrast(d, "equal_model_issue", sprintf("B|lomo|%s|drop_%s", j, mm), B_SENS) %>%
      mutate(jurisdiction = j, sensitivity = "leave_one_model_out", level = paste0("drop_", mm))
  })
})

# (3) prompt type
cat("  prompt type\n")
sens$tier <- map_dfr(JURIS, function(j) {
  dj <- bsample(v2 %>% filter(juris == j))
  map_dfr(levels(droplevels(dj$tier)), function(tt) {
    d <- dj %>% filter(tier == tt) %>% droplevels()
    run_contrast(d, "equal_model_issue", sprintf("B|tier|%s|%s", j, tt), B_SENS) %>%
      mutate(jurisdiction = j, sensitivity = "prompt_type", level = tt)
  })
})

# (4) language -- the whole procedure repeated within each language
cat("  language\n")
sens$language <- map_dfr(JURIS, function(j) {
  map_dfr(LANGS_V2, function(lg) {
    d <- bsample(v2 %>% filter(juris == j), language = lg)
    run_contrast(d, "equal_model_issue", sprintf("B|language|%s|%s", j, lg), B_SENS) %>%
      mutate(jurisdiction = j, sensitivity = "language", level = lg)
  })
})

# (5) response length -- drop very short responses, which are the ones most
#     likely to be truncation or degenerate output rather than a considered answer
cat("  response length\n")
lens <- read_csv("pipeline/response_lengths.csv", show_col_types = FALSE)
v2len <- v2 %>% left_join(lens, by = c("prompt_id", "prompt_language", "model"))
sens$length <- map_dfr(JURIS, function(j) {
  map_dfr(c(20, 50, 100), function(thr) {
    d <- bsample(v2len %>% filter(juris == j, !is.na(response_chars),
                                  response_chars >= thr))
    run_contrast(d, "equal_model_issue", sprintf("B|len%d|%s", thr, j), B_SENS) %>%
      mutate(jurisdiction = j, sensitivity = "min_response_chars", level = as.character(thr))
  })
})

# (6) HIERARCHICAL sensitivity, with MARGINAL (population-level) predictions
cat("  hierarchical (marginal predictions; BLUPs NOT held fixed)\n")
suppressPackageStartupMessages(library(lme4))
marginal_gcomp <- function(d, wfun, S = 400) {
  f <- as.formula(paste(deparse(build_formula(d)), "+ (1|issue_id) + (1|prompt_id)"))
  m <- tryCatch(glmer(f, data = d, family = binomial,
                      control = glmerControl(optimizer = "bobyqa",
                                             optCtrl = list(maxfun = 2e5))),
                error = function(e) NULL)
  if (is.null(m)) return(list(est = NA_real_, note = "did not converge", sing = NA))
  sds <- as.data.frame(VarCorr(m))$sdcor
  b <- fixef(m)
  X1 <- model.matrix(terms(m), transform(d, home = 1L))
  X0 <- model.matrix(terms(m), transform(d, home = 0L))
  # Marginalise over the RANDOM-EFFECT DISTRIBUTION rather than plugging in the
  # fitted BLUPs. Holding BLUPs fixed while toggling `home` would answer a
  # different question -- the contrast for these particular issues at their
  # estimated effects -- and would understate the variance being integrated over.
  set.seed(V2_SEED)
  u <- rowSums(matrix(rnorm(S * length(sds)), nrow = S) *
                 matrix(sds, nrow = S, ncol = length(sds), byrow = TRUE))
  e1 <- as.vector(X1 %*% b); e0 <- as.vector(X0 %*% b)
  p1 <- rowMeans(vapply(u, function(uu) plogis(e1 + uu), numeric(length(e1))))
  p0 <- rowMeans(vapply(u, function(uu) plogis(e0 + uu), numeric(length(e0))))
  list(est = sum(wfun(d) * (p1 - p0)), note = "", sing = isSingular(m))
}
sens$hierarchical <- map_dfr(JURIS, function(j) {
  d <- bsample(v2 %>% filter(juris == j))
  es <- estimable(d)
  if (!es$ok) return(tibble(jurisdiction = j, sensitivity = "hierarchical_marginal",
                            level = "(1|issue_id)+(1|prompt_id)", estimable = FALSE,
                            note = es$why, n = nrow(d), weighting = "equal_model_issue"))
  r <- marginal_gcomp(d, w_equal_model_issue)
  tibble(jurisdiction = j, sensitivity = "hierarchical_marginal",
         level = "(1|issue_id)+(1|prompt_id)", estimable = !is.na(r$est),
         estimate = r$est, estimate_pp = pp(r$est), n = nrow(d),
         n_issues = n_distinct(d$issue_id), weighting = "equal_model_issue",
         note = paste0(r$note, if (isTRUE(r$sing)) " singular fit" else ""),
         singular = r$sing)
})

e35 <- bind_rows(sens) %>%
  mutate(estimand_family = "B_standardized",
         estimand_label = "covariate-standardized home-minus-away refusal contrast (sensitivity)",
         causal_interpretation = NOT_CAUSAL,
         outcome = "refused_strict (engagement_code >= 4)",
         language = ifelse(sensitivity == "language", level, "en")) %>%
  select(estimand_family, sensitivity, jurisdiction, level, weighting, language,
         n, n_issues, n_models, events_home, events_away,
         estimate, conf_low, conf_high, estimate_pp, conf_low_pp, conf_high_pp,
         estimable, note, everything())
write_csv(e35, file.path(EST, "e35_home_standardized_sensitivities.csv"))
cat(sprintf("\nwrote e33/e34/e35 (%d sensitivity rows)\n", nrow(e35)))
cat("\nhierarchical (marginal) vs primary, pp:\n")
print(as.data.frame(
  e35 %>% filter(sensitivity == "hierarchical_marginal") %>%
    select(jurisdiction, estimate_pp, estimable, note)), digits = 3, row.names = FALSE)
