# =============================================================================
# Script 20: Home-region estimates  (ESTIMATION ONLY -- no plotting)
# =============================================================================
# Input : pipeline/data_clean.RData
# Output: pipeline/estimates/*.csv   (tidy, one row per plotted quantity)
#
# Every figure quantity in Main Figure 1 is computed here and written to a tidy
# table. 30_figures.R reads those tables and draws; it never re-estimates.
#
# -----------------------------------------------------------------------------
# IDENTIFICATION -- why the model is specified the way it is
# -----------------------------------------------------------------------------
# The substantive question is DISTINCTIVE home-region sensitivity:
#
#   On the same issues, are models from the home jurisdiction more likely to
#   refuse than models from other jurisdictions?
#
# That is a within-issue, between-jurisdiction contrast. It is the discriminating
# formulation because it does not count a generally sensitive issue as evidence
# of home sensitivity merely because everyone refuses it more.
#
# Key structural fact, verified in this script and asserted by the design:
#
#     region_focus is CONSTANT within issue_id      (an issue has one region)
#     topic_domain is CONSTANT within issue_id      (an issue has one domain)
#     home         VARIES   within issue_id         (across jurisdictions)
#     tier         VARIES   within issue_id         (reg1/reg2 vs bndA/bndB)
#
# Consequently a `juris * region` fixed-effects parameterisation WITH an issue
# random intercept is not estimable: the region main effects are collinear with
# the random intercept and lme4 fails with "Downdated VtV is not positive
# definite". The identified and transparent equivalent is
#
#     refused ~ home * juris + tier + (1 | issue_id)
#
# CONTRAST ALGEBRA. With home in {0,1} and juris a factor (reference = CN),
#   logit P(refuse) = b0 + b_home*home + b_j + b_hj*(home x juris_j)
#                        + b_tier*tier + u_issue
# The home coefficient for jurisdiction j on the log-odds scale is
#   CN : b_home
#   j  : b_home + b_hj
# Because u_issue holds the issue fixed, and region/domain are properties of the
# issue, this contrast compares jurisdiction j against the other jurisdictions
# ANSWERING THE SAME ISSUES. It is therefore the interaction (difference-in-
# differences) quantity, not a within-jurisdiction home-vs-away difference.
#
# The issue random intercept absorbs region, topic domain, and any unmeasured
# issue-level characteristic. That is a stronger control than adjusting for
# topic domain alone. A `+ domain` variant is fitted as a sensitivity check.
#
# EU is EXCLUDED, not estimated: Mistral produces 0 refusals in all five region
# cells. This is complete separation, not sparsity, and any coefficient it
# received would be imposed by shared structure. It is reported as a structural
# zero in a dedicated column of the estimate table.
#
# UNCERTAINTY -- and what the interval is conditional on. Probability-scale
# contrasts by g-computation over the observed sample. Predictions ADD THE
# FITTED RANDOM EFFECTS (the issue BLUPs), so the estimand is
#
#     SAMPLE-CONDITIONAL: the contrast averaged over the observed issues, at
#     their estimated issue effects.
#
# It is NOT the "typical issue" (u = 0) quantity and NOT marginal over a
# hypothetical population of issues. Do not mix those readings.
#
# The interval draws B times from MVN(fixef, vcov) with the BLUPs HELD FIXED, so
# it propagates FIXED-EFFECT UNCERTAINTY ONLY. That is coherent with a
# sample-conditional estimand -- the issue effects are being treated as known
# features of the realised sample, not as draws to be re-simulated. A full
# bootstrap over theta would widen the interval but would also change the
# estimand to a population-marginal one, which is not what is reported. Every
# estimate table carries this in an `uncertainty` column.
#
# Responses are clustered within issue; that clustering is handled by the model,
# not by treating rows as independent.

suppressPackageStartupMessages({
  library(tidyverse); library(lme4); library(MASS)
})
select <- dplyr::select

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")
load("pipeline/data_clean.RData")
EST <- "pipeline/estimates"; dir.create(EST, showWarnings = FALSE, recursive = TRUE)
set.seed(20260803)
B_BOOT <- 2000

cat(strrep("=", 78), "\nHOME-REGION ESTIMATES\n", strrep("=", 78), "\n", sep = "")

# -----------------------------------------------------------------------------
# Sample construction (stated explicitly; every restriction is recorded)
# -----------------------------------------------------------------------------
base <- data_clean %>%
  filter(!is.na(jurisdiction_f), !is.na(region_focus), prompt_language == "en") %>%
  mutate(juris  = factor(as.character(jurisdiction_f), levels = JURIS_LEVELS),
         region = factor(region_focus, levels = REGION_LEVELS),
         home   = as.integer(as.character(region_focus) ==
                               HOME_REGION[as.character(jurisdiction_f)]),
         domain = factor(prompt_category),
         tier   = factor(dataset_type, levels = c("base", "boundary")),
         y      = as.numeric(refused))

# Structural zeros, identified from the data rather than hard-coded.
zero_juris <- base %>% group_by(juris) %>% summarise(k = sum(y), .groups = "drop") %>%
  filter(k == 0) %>% pull(juris) %>% as.character()
cat("Structural zeros (0 refusals anywhere, excluded from models):",
    if (length(zero_juris)) paste(zero_juris, collapse = ", ") else "none", "\n")

dat <- base %>% filter(region != "General", !juris %in% zero_juris) %>%
  mutate(juris = droplevels(juris), region = droplevels(region))

cat(sprintf("Primary sample: n=%d  issues=%d  events=%d (%.2f%%)  juris=%s\n\n",
            nrow(dat), n_distinct(dat$issue_id), sum(dat$y), 100*mean(dat$y),
            paste(levels(dat$juris), collapse = "/")))

# Assert the identification facts rather than trusting the prose above.
varies <- function(v, g) any(tapply(as.character(v), g, function(x) length(unique(x)) > 1))
stopifnot(!varies(dat$region, dat$issue_id), !varies(dat$domain, dat$issue_id),
          varies(dat$home, dat$issue_id),    varies(dat$tier, dat$issue_id))
cat("Identification check passed: region/domain constant within issue; home/tier vary.\n\n")

# -----------------------------------------------------------------------------
# Fitting + probability-scale contrasts
# -----------------------------------------------------------------------------
fit_model <- function(d, add_domain = FALSE, extra = NULL) {
  # Drop any term with no variation in this subsample. The tier-restricted
  # sensitivity fits hold tier constant, which makes "+ tier" rank-deficient and
  # was being reported as a convergence failure when it is really a
  # specification error.
  rhs <- c("home * juris")
  if (nlevels(droplevels(d$tier)) > 1) rhs <- c(rhs, "tier")
  if (add_domain && nlevels(droplevels(d$domain)) > 1) rhs <- c(rhs, "domain")
  rhs <- c(rhs, extra)
  f <- as.formula(paste("y ~", paste(rhs, collapse = " + "), "+ (1|issue_id)"))

  # Deterministic row order. PIRLS starting values depend on the order rows
  # arrive in, and data_clean is rebuilt by concatenating annotation files whose
  # order changes as generation proceeds -- so the identical model on the
  # identical sample could fit one day and fail with "Downdated VtV is not
  # positive definite" the next. Sorting makes the fit reproducible.
  d <- d[order(as.character(d$issue_id), as.character(d$model)), ]

  # Optimiser ladder. bobyqa is the default; if PIRLS fails, fall back rather
  # than reporting a specification as inestimable when it is merely a bad start.
  for (opt in c("bobyqa", "Nelder_Mead")) {
    m <- tryCatch(glmer(f, data = d, family = binomial,
                        control = glmerControl(optimizer = opt,
                                               optCtrl = list(maxfun = 2e5))),
                  error = function(e) NULL)
    if (!is.null(m)) { attr(m, "optimizer") <- opt; return(m) }
  }
  # Last resort: nAGQ = 0 uses a faster, less accurate PIRLS step that is much
  # more robust to poor starts. Flagged so it is visible in the diagnostics.
  m <- glmer(f, data = d, family = binomial, nAGQ = 0,
             control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5)))
  attr(m, "optimizer") <- "bobyqa/nAGQ=0"
  m
}

diagnose <- function(m, label) {
  msg <- m@optinfo$conv$lme4$messages
  tibble(spec = label,
         issue_sd  = sqrt(unlist(VarCorr(m))),
         singular  = isSingular(m),
         max_se    = max(sqrt(diag(as.matrix(vcov(m))))),
         max_abs_b = max(abs(fixef(m))),
         optimizer = if (is.null(attr(m, "optimizer"))) "bobyqa" else attr(m, "optimizer"),
         warnings  = if (is.null(msg)) "none" else paste(msg, collapse = "; "))
}

# g-computation of the home premium on the probability scale, per jurisdiction.
# Predictions use the FITTED random effects, so this is a sample-average
# contrast rather than a "typical issue" (u = 0) one.
home_premium <- function(m, d, B = B_BOOT) {
  d <- d[order(as.character(d$issue_id), as.character(d$model)), ]   # match fit_model
  X1 <- model.matrix(terms(m), transform(d, home = 1L))
  X0 <- model.matrix(terms(m), transform(d, home = 0L))
  re <- ranef(m)$issue_id[as.character(d$issue_id), 1]
  b  <- fixef(m); V <- as.matrix(vcov(m))
  draws <- MASS::mvrnorm(B, b, V)

  point <- function(bb) {
    p1 <- plogis(as.vector(X1 %*% bb) + re)
    p0 <- plogis(as.vector(X0 %*% bb) + re)
    vapply(levels(d$juris), function(j) mean(p1[d$juris == j] - p0[d$juris == j]), numeric(1))
  }
  est <- point(b)
  bs  <- t(apply(draws, 1, point))
  tibble(jurisdiction = levels(d$juris),
         estimate = est,
         conf_low  = apply(bs, 2, quantile, 0.025),
         conf_high = apply(bs, 2, quantile, 0.975),
         n = as.integer(table(d$juris)[levels(d$juris)]),
         events = as.integer(tapply(d$y, d$juris, sum)[levels(d$juris)]),
         n_issues = as.integer(tapply(d$issue_id, d$juris,
                                      function(x) n_distinct(x))[levels(d$juris)]))
}

# -----------------------------------------------------------------------------
# A. PRIMARY specification
# -----------------------------------------------------------------------------
cat("A. primary: y ~ home*juris + tier + (1|issue_id)\n")
m_pri <- fit_model(dat)
diag_tbl <- diagnose(m_pri, "primary")
print(diag_tbl, width = 200)

prim <- home_premium(m_pri, dat) %>%
  mutate(spec = "primary", scale = "probability",
         contrast = "within-issue home premium (DiD): P(refuse|home) - P(refuse|away), issue held fixed",
         sample = "English, non-General, EU excluded", estimable = TRUE,
         estimand_type = "sample-conditional (averaged over observed issues at fitted BLUPs)",
         uncertainty = "parametric bootstrap over fixed-effect covariance; BLUPs held fixed",
         weighting = "response-weighted within jurisdiction")

# EU appended as a structural zero, never as an estimate.
if (length(zero_juris)) {
  eu <- base %>% filter(juris %in% zero_juris, region != "General")
  prim <- bind_rows(prim, tibble(
    jurisdiction = zero_juris, estimate = NA_real_,
    conf_low = NA_real_, conf_high = NA_real_,
    n = nrow(eu), events = 0L, n_issues = n_distinct(eu$issue_id),
    spec = "primary", scale = "probability",
    contrast = "0 observed refusals; contrast not estimable",
    sample = "English, non-General", estimable = FALSE))
}
write_csv(prim, file.path(EST, "e01_home_premium_primary.csv"))
print(as.data.frame(prim %>% select(jurisdiction, estimate, conf_low, conf_high,
                                    n, events, estimable)), digits = 3, row.names = FALSE)

# Odds-ratio companion (supplementary).
or_tab <- as.data.frame(summary(m_pri)$coefficients) %>%
  rownames_to_column("term") %>%
  transmute(term, log_odds = Estimate, se = `Std. Error`, z = `z value`,
            p = `Pr(>|z|)`, or = exp(Estimate),
            or_low = exp(Estimate - 1.96*`Std. Error`),
            or_high = exp(Estimate + 1.96*`Std. Error`)) %>%
  mutate(spec = "primary")
write_csv(or_tab, file.path(EST, "e02_home_primary_oddsratios.csv"))

# -----------------------------------------------------------------------------
# B. DESCRIPTIVE within-jurisdiction contrast (relabelled, NOT primary)
# -----------------------------------------------------------------------------
# Separate logistic fit per jurisdiction, adjusting for topic domain, then
# g-computation. This is the "adjusted within-jurisdiction home-versus-away
# difference": it asks whether a jurisdiction refuses more on its own region
# than on other regions, WITHOUT reference to how other jurisdictions treat the
# same issues. It is descriptive and is retained only to show why the two
# estimands diverge.
cat("\nB. descriptive within-jurisdiction g-computation (per-jurisdiction fits)\n")
gcomp_one <- function(d, B = 500) {
  if (length(unique(d$y)) < 2) return(tibble(estimate = 0, conf_low = NA, conf_high = NA))
  g <- function(dd) {
    f <- suppressWarnings(glm(y ~ home + domain, dd, family = binomial))
    mean(predict(f, transform(dd, home = 1L), type = "response") -
         predict(f, transform(dd, home = 0L), type = "response"))
  }
  est <- g(d); iss <- unique(d$issue_id)
  bs <- replicate(B, {
    tk <- sample(iss, length(iss), TRUE)
    tryCatch(g(d[unlist(lapply(tk, function(i) which(d$issue_id == i))), ]),
             error = function(e) NA_real_)
  })
  tibble(estimate = est, conf_low = quantile(bs, .025, na.rm = TRUE),
         conf_high = quantile(bs, .975, na.rm = TRUE))
}
desc <- dat %>% group_by(jurisdiction = juris) %>% group_modify(~ gcomp_one(.x)) %>%
  ungroup() %>%
  left_join(prim %>% select(jurisdiction, n, events, n_issues), by = "jurisdiction") %>%
  mutate(spec = "descriptive_within_jurisdiction", scale = "probability",
         contrast = "adjusted within-jurisdiction home-vs-away difference (issue NOT held fixed)",
         sample = "English, non-General, EU excluded", estimable = TRUE,
         jurisdiction = as.character(jurisdiction))
write_csv(desc, file.path(EST, "e03_home_within_jurisdiction.csv"))
print(as.data.frame(desc %>% select(jurisdiction, estimate, conf_low, conf_high)),
      digits = 3, row.names = FALSE)

# Side-by-side, for the estimand-comparison panel.
cmp <- bind_rows(
  prim %>% filter(estimable) %>%
    transmute(jurisdiction, estimand = "Within-issue (primary)", estimate, conf_low, conf_high),
  desc %>% transmute(jurisdiction, estimand = "Within-jurisdiction (descriptive)",
                     estimate, conf_low, conf_high))
write_csv(cmp, file.path(EST, "e04_estimand_comparison.csv"))

# -----------------------------------------------------------------------------
# C. SENSITIVITY
# -----------------------------------------------------------------------------
cat("\nC. sensitivity specifications\n")
sens <- list(); diags <- list(diag_tbl); failed <- list()

add_sens <- function(label, d, add_domain = FALSE, extra = NULL, note = "") {
  err <- NULL
  m <- tryCatch(fit_model(d, add_domain, extra),
                error = function(e) { err <<- sub("\n.*", "", conditionMessage(e)); NULL })
  if (is.null(m)) {
    cat(sprintf("  %-28s NOT ESTIMABLE: %s\n", label, substr(err, 1, 60)))
    failed[[label]] <<- tibble(spec = label, reason = err, n = nrow(d), events = sum(d$y))
    return(NULL)
  }
  diags[[length(diags) + 1]] <<- diagnose(m, label)
  out <- home_premium(m, d, B = 800) %>%
    mutate(spec = label, note = note, scale = "probability")
  cat(sprintf("  %-28s ok (n=%d, events=%d)\n", label, nrow(d), sum(d$y)))
  out
}

sens$domain      <- add_sens("plus_topic_domain", dat, add_domain = TRUE,
                             note = "issue RE already absorbs domain; included as a check")
sens$regular     <- add_sens("regular_prompts_only", filter(dat, tier == "base"))
sens$boundary    <- add_sens("boundary_prompts_only", filter(dat, tier == "boundary"))
sens$authored_en <- add_sens("exclude_backtranslated",
                             filter(dat, prompt_origin_language == "en"),
                             note = "drops the 300 back-translated prompts")
# contention_score and route are ISSUE-level attributes and therefore constant
# within issue_id, exactly like region and domain. The issue random intercept
# already absorbs them; adding them as fixed effects is not identified. Record
# that as a structural fact rather than attempting a fit that cannot converge.
for (v in c("contention_score", "route")) {
  if (!v %in% names(dat)) next
  if (!varies(dat[[v]], dat$issue_id))
    failed[[paste0("plus_", v)]] <- tibble(
      spec = paste0("plus_", v), n = nrow(dat), events = sum(dat$y),
      reason = paste0(v, " is constant within issue_id and absorbed by the issue ",
                      "random intercept; not separately identified"))
  else sens[[v]] <- add_sens(paste0("plus_", v), dat, extra = v)
}

# Leave-one-model-out within multi-model jurisdictions: is any jurisdiction's
# result driven by a single model?
multi <- dat %>% count(juris, model) %>% count(juris) %>% filter(n > 1) %>% pull(juris)
for (j in as.character(multi)) for (mm in unique(dat$model[dat$juris == j])) {
  lab <- paste0("drop_", mm)
  s <- add_sens(lab, filter(dat, model != mm), note = paste("leave-one-out within", j))
  if (!is.null(s)) sens[[lab]] <- s %>% filter(jurisdiction == j)
}

sens_tbl <- bind_rows(sens) %>%
  mutate(sample = "English, non-General, EU excluded", estimable = TRUE)
write_csv(sens_tbl, file.path(EST, "e05_home_sensitivity.csv"))
write_csv(bind_rows(diags), file.path(EST, "e06_model_diagnostics.csv"))
if (length(failed))
  write_csv(bind_rows(failed), file.path(EST, "e06b_not_estimable.csv"))

# China decomposition: DeepSeek and Qwen separately, rather than pooled only.
cat("\n  CN decomposition (per-model home premium)\n")
cn_dec <- map_dfr(c("deepseek-chat-v3.1", "qwen3-max"), function(mm) {
  d <- dat %>% filter(juris != "CN" | model == mm)
  m <- tryCatch(fit_model(d), error = function(e) { cat("    ", mm, "not estimable:",
                sub("\n.*", "", conditionMessage(e)), "\n"); NULL })
  if (is.null(m)) return(tibble(spec = paste0("CN_only_", mm), jurisdiction = "CN",
                                estimate = NA_real_, conf_low = NA_real_,
                                conf_high = NA_real_, estimable = FALSE))
  home_premium(m, d, B = 800) %>% filter(jurisdiction == "CN") %>%
    mutate(spec = paste0("CN_only_", mm), estimable = TRUE)
})
write_csv(cn_dec, file.path(EST, "e07_cn_model_decomposition.csv"))
print(as.data.frame(cn_dec %>% select(spec, estimate, conf_low, conf_high)),
      digits = 3, row.names = FALSE)

# -----------------------------------------------------------------------------
# D. Region structure: raw cell rates AND the interaction residual
# -----------------------------------------------------------------------------
# The raw matrix confounds "this jurisdiction refuses a lot" and "this region is
# sensitive" with the interaction of interest. The residual is the excess over
# an additive jurisdiction + region baseline, which is the quantity the primary
# model estimates.
cat("\nD. region structure (raw rates + additive-model residual)\n")
cells <- base %>% filter(region != "General") %>%
  group_by(juris, region) %>%
  summarise(n = n(), events = sum(y), rate = mean(y), .groups = "drop") %>%
  bind_cols(wilson_ci(.$events, .$n)) %>%
  rename(conf_low = lo, conf_high = hi)

cells_est <- filter(cells, !juris %in% zero_juris) %>% mutate(juris = droplevels(juris))
add_fit <- glm(cbind(events, n - events) ~ juris + region, data = cells_est,
               family = binomial)
# Predict only on rows the baseline was fitted on: a structural-zero jurisdiction
# is not a level of that model and must not be given a fitted value.
cells_est$expected <- predict(add_fit, newdata = cells_est, type = "response")
cells <- cells %>%
  left_join(cells_est %>% select(juris, region, expected), by = c("juris", "region")) %>%
  mutate(
    excess = rate - expected,
    home = as.character(region) == HOME_REGION[as.character(juris)],
    estimable = !(juris %in% zero_juris))
write_csv(cells, file.path(EST, "e08_region_cells.csv"))
cat(sprintf("  %d cells; excess = observed - additive(jurisdiction + region) prediction\n",
            nrow(cells)))

# -----------------------------------------------------------------------------
# E. China language decomposition, with a FORMAL interaction test
# -----------------------------------------------------------------------------
# The previous slopegraph implied additivity from visual parallelism. Additivity
# is a claim about an interaction and needs an estimate with an interval.
cat("\nE. CN language decomposition + home x language interaction\n")
cn <- data_clean %>%
  filter(jurisdiction_f == "CN", region_focus != "General",
         prompt_language %in% c("en", "zh")) %>%
  mutate(home = as.integer(region_focus == "China"),
         lang = factor(prompt_language, levels = c("en", "zh")),
         tier = factor(dataset_type), y = as.numeric(refused))

cn_cells <- cn %>% group_by(model, lang, home) %>%
  summarise(n = n(), events = sum(y), rate = mean(y), .groups = "drop") %>%
  bind_cols(wilson_ci(.$events, .$n)) %>% rename(conf_low = lo, conf_high = hi)
write_csv(cn_cells, file.path(EST, "e09_cn_language_cells.csv"))

cn_int <- map_dfr(unique(cn$model), function(mm) {
  d <- cn %>% filter(model == mm)
  m <- tryCatch(glmer(y ~ home * lang + tier + (1|issue_id), d, binomial,
                      control = glmerControl(optimizer = "bobyqa",
                                             optCtrl = list(maxfun = 2e5))),
                error = function(e) NULL)
  if (is.null(m)) return(tibble(model = mm, term = NA_character_))
  # Probability-scale home premium within each language, plus the interaction.
  # The model matrix is built on the FULL data and only then subset by language.
  # Filtering first drops the unused `lang` factor level, so model.matrix returns
  # fewer columns than there are coefficients and the multiply fails -- which is
  # what silently lost Qwen from this table on the first run.
  X1 <- model.matrix(terms(m), transform(d, home = 1L))
  X0 <- model.matrix(terms(m), transform(d, home = 0L))
  re <- ranef(m)$issue_id[as.character(d$issue_id), 1]
  b <- fixef(m); V <- as.matrix(vcov(m))
  dr <- MASS::mvrnorm(1500, b, V)
  gp <- function(lv) {
    idx <- which(d$lang == lv)
    f <- function(bb) mean(plogis(as.vector(X1[idx, ] %*% bb) + re[idx]) -
                           plogis(as.vector(X0[idx, ] %*% bb) + re[idx]))
    bs <- apply(dr, 1, f)
    tibble(model = mm, lang = lv, estimate = f(b),
           conf_low = quantile(bs, .025), conf_high = quantile(bs, .975),
           n = length(idx), events = sum(d$y[idx]))
  }
  res <- bind_rows(gp("en"), gp("zh"))
  co <- summary(m)$coefficients
  iterm <- grep("^home:lang", rownames(co), value = TRUE)
  res$interaction_log_odds <- co[iterm, "Estimate"]
  res$interaction_se       <- co[iterm, "Std. Error"]
  res$interaction_p        <- co[iterm, "Pr(>|z|)"]
  res
})
write_csv(cn_int, file.path(EST, "e10_cn_home_by_language.csv"))
print(as.data.frame(cn_int %>% select(model, lang, estimate, conf_low, conf_high,
                                      interaction_log_odds, interaction_p)),
      digits = 3, row.names = FALSE)

# -----------------------------------------------------------------------------
# F. PER-MODEL home premium, and the weighting question
# -----------------------------------------------------------------------------
# The primary specification interacts home with JURISDICTION, so every model in
# a jurisdiction receives the identical fitted contrast -- DeepSeek and Qwen both
# return exactly the pooled CN value. That means the usual reassurance
# "response-weighting and equal-model-weighting agree" is VACUOUS there: it is a
# property of the specification, not evidence about the data.
#
# Interacting home with MODEL makes the within-jurisdiction spread visible and
# lets the jurisdiction summary be recomputed under equal-model weighting. It
# answers three things the pooled model cannot:
#   * is China's result carried by both Chinese models, or only one?
#   * is any jurisdiction's null hiding offsetting model-level effects?
#   * do single-model jurisdictions (India, EU) deserve a different reading?
cat("\nF. per-model home premium: y ~ home*model + tier + (1|issue_id)\n")
dat_m <- dat %>% mutate(mdl = droplevels(factor(model)))
dat_m <- dat_m[order(as.character(dat_m$issue_id), as.character(dat_m$model)), ]

fit_by_model <- function(d) {
  f <- y ~ home * mdl + tier + (1 | issue_id)
  for (opt in c("bobyqa", "Nelder_Mead")) {
    m <- tryCatch(glmer(f, d, binomial,
                        control = glmerControl(optimizer = opt,
                                               optCtrl = list(maxfun = 2e5))),
                  error = function(e) NULL)
    if (!is.null(m)) return(m)
  }
  glmer(f, d, binomial, nAGQ = 0,
        control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5)))
}
m_mod <- fit_by_model(dat_m)
cat(sprintf("  singular=%s  issue SD=%.3f\n", isSingular(m_mod),
            sqrt(unlist(VarCorr(m_mod)))))

X1 <- model.matrix(terms(m_mod), transform(dat_m, home = 1L))
X0 <- model.matrix(terms(m_mod), transform(dat_m, home = 0L))
re <- ranef(m_mod)$issue_id[as.character(dat_m$issue_id), 1]
b  <- fixef(m_mod); V <- as.matrix(vcov(m_mod))
dr <- MASS::mvrnorm(B_BOOT, b, V)
pt <- function(bb) {
  p1 <- plogis(as.vector(X1 %*% bb) + re); p0 <- plogis(as.vector(X0 %*% bb) + re)
  vapply(levels(dat_m$mdl), function(k) mean(p1[dat_m$mdl == k] - p0[dat_m$mdl == k]),
         numeric(1))
}
est <- pt(b); bs <- t(apply(dr, 1, pt))
mj  <- dat_m %>% distinct(mdl, juris) %>% mutate(mdl = as.character(mdl))
per_model <- tibble(
  model = levels(dat_m$mdl), estimate = est,
  conf_low = apply(bs, 2, quantile, .025), conf_high = apply(bs, 2, quantile, .975),
  n = as.integer(table(dat_m$mdl)[levels(dat_m$mdl)]),
  events = as.integer(tapply(dat_m$y, dat_m$mdl, sum)[levels(dat_m$mdl)])) %>%
  left_join(mj, by = c("model" = "mdl")) %>%
  rename(jurisdiction = juris) %>%
  mutate(jurisdiction = as.character(jurisdiction), estimable = TRUE,
         spec = "y ~ home*model + tier + (1|issue_id)", scale = "probability",
         contrast = "within-issue home premium, per subject model",
         sample = "English, non-General, EU excluded",
         estimand_type = "sample-conditional",
         uncertainty = "parametric bootstrap over fixed-effect covariance; BLUPs held fixed") %>%
  arrange(match(jurisdiction, JURIS_LEVELS), desc(estimate))
write_csv(per_model, file.path(EST, "e21_home_by_model.csv"))
print(as.data.frame(per_model %>% select(jurisdiction, model, estimate,
                                         conf_low, conf_high, events)),
      digits = 3, row.names = FALSE)

# Three weightings of the same jurisdiction quantity, so the caption can state
# which one is plotted and show it does not drive the conclusion.
resp_wt <- prim %>% filter(estimable) %>%
  transmute(jurisdiction, weighting = "response-weighted (plotted)", estimate)
eqm_wt <- per_model %>% group_by(jurisdiction) %>%
  summarise(estimate = mean(estimate), n_models = n(), .groups = "drop") %>%
  mutate(weighting = "equal-model-weighted")
# Leave-one-model-out: the spread of jurisdiction means when each of its models
# is dropped in turn. Undefined for single-model jurisdictions, and said so.
loo <- per_model %>% group_by(jurisdiction) %>%
  summarise(loo_min = if (n() > 1) min(sapply(seq_len(n()), function(i) mean(estimate[-i]))) else NA_real_,
            loo_max = if (n() > 1) max(sapply(seq_len(n()), function(i) mean(estimate[-i]))) else NA_real_,
            n_models = n(), .groups = "drop")
wt <- bind_rows(resp_wt, eqm_wt %>% select(jurisdiction, weighting, estimate)) %>%
  left_join(loo, by = "jurisdiction") %>%
  mutate(single_model = n_models == 1,
         note = ifelse(n_models == 1,
                       "single-model jurisdiction; weighting and leave-one-out undefined", ""))
write_csv(wt, file.path(EST, "e22_weighting_sensitivity.csv"))
cat("\n  weighting sensitivity (pp)\n")
print(as.data.frame(wt %>% mutate(pp = 100 * estimate) %>%
                      select(jurisdiction, weighting, pp, n_models)),
      digits = 3, row.names = FALSE)

cat("\n", strrep("=", 78), "\nWROTE ", length(list.files(EST)), " estimate tables to ", EST, "\n",
    strrep("=", 78), "\n", sep = "")
