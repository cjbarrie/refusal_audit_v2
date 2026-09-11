# =============================================================================
# Script 21: Supporting estimates  (ESTIMATION ONLY -- no plotting)
# =============================================================================
# Input : pipeline/data_clean.RData
# Output: pipeline/estimates/*.csv
#
# Quantities for Main Figures 2 and 3. As in script 20, nothing here draws.
#
# CLUSTERING. Regular and boundary prompts are PAIRED WITHIN ISSUE by design
# (reg1/reg2 and bndA/bndB all derive from one issue), and every model answers
# the same battery. Independent-binomial intervals on a regular-vs-boundary
# difference would therefore be wrong twice over: they ignore the pairing and
# they ignore that the same issue recurs across models. Every tier contrast here
# comes from a mixed model with an issue random intercept, on the probability
# scale.

suppressPackageStartupMessages({
  library(tidyverse); library(lme4); library(MASS)
})
select <- dplyr::select

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")
load("pipeline/data_clean.RData")
EST <- "pipeline/estimates"; dir.create(EST, showWarnings = FALSE, recursive = TRUE)
set.seed(20260803)

cat(strrep("=", 78), "\nSUPPORTING ESTIMATES\n", strrep("=", 78), "\n", sep = "")

d <- data_clean %>%
  filter(!is.na(jurisdiction_f), prompt_language == "en") %>%
  mutate(juris  = factor(as.character(jurisdiction_f), levels = JURIS_LEVELS),
         tier   = factor(dataset_type, levels = c("base", "boundary"),
                         labels = c("regular", "boundary")),
         domain = factor(prompt_category),
         y      = as.numeric(refused))

# Probability-scale contrast of `tier` from a fitted model, by g-computation
# with a parametric bootstrap over the fixed effects.
tier_contrast <- function(m, dd, B = 1500) {
  Xb <- model.matrix(terms(m), transform(dd, tier = factor("boundary",
                                                           levels = levels(dd$tier))))
  Xr <- model.matrix(terms(m), transform(dd, tier = factor("regular",
                                                           levels = levels(dd$tier))))
  re <- ranef(m)$issue_id[as.character(dd$issue_id), 1]
  b  <- fixef(m); V <- as.matrix(vcov(m))
  dr <- MASS::mvrnorm(B, b, V)
  f  <- function(bb) {
    pb <- plogis(as.vector(Xb %*% bb) + re); pr <- plogis(as.vector(Xr %*% bb) + re)
    c(regular = mean(pr), boundary = mean(pb), shift = mean(pb - pr))
  }
  est <- f(b); bs <- t(apply(dr, 1, f))
  tibble(regular = est["regular"], boundary = est["boundary"], shift = est["shift"],
         conf_low = quantile(bs[, "shift"], .025),
         conf_high = quantile(bs[, "shift"], .975))
}

# -----------------------------------------------------------------------------
# A. Model x prompt tier
# -----------------------------------------------------------------------------
# One model per subject model: refused ~ tier + (1|issue_id). Region and domain
# are constant within issue and absorbed by the random intercept, so the tier
# contrast is a WITHIN-ISSUE paired comparison.
cat("\nA. model x tier (per-model mixed models, issue random intercept)\n")
mod_tier <- map_dfr(levels(droplevels(factor(d$model))), function(mm) {
  dd <- d %>% filter(model == mm) %>% mutate(tier = droplevels(tier))
  base_row <- tibble(model = mm, juris = as.character(dd$juris[1]),
                     n = nrow(dd), events = sum(dd$y),
                     n_issues = n_distinct(dd$issue_id))
  if (sum(dd$y) == 0)
    return(bind_cols(base_row, tibble(regular = 0, boundary = 0, shift = 0,
                                      conf_low = NA_real_, conf_high = NA_real_,
                                      estimable = FALSE,
                                      note = "0 observed refusals; contrast not estimable")))
  m <- tryCatch(glmer(y ~ tier + (1|issue_id), dd, binomial,
                      control = glmerControl(optimizer = "bobyqa",
                                             optCtrl = list(maxfun = 2e5))),
                error = function(e) NULL)
  if (is.null(m))
    return(bind_cols(base_row, tibble(regular = mean(dd$y[dd$tier == "regular"]),
                                      boundary = mean(dd$y[dd$tier == "boundary"]),
                                      shift = NA_real_, conf_low = NA_real_,
                                      conf_high = NA_real_, estimable = FALSE,
                                      note = "mixed model did not converge")))
  bind_cols(base_row, tier_contrast(m, dd)) %>% mutate(estimable = TRUE, note = "")
}) %>%
  mutate(spec = "refused ~ tier + (1|issue_id), per model",
         sample = "English, all regions", scale = "probability",
         contrast = "P(refuse|boundary) - P(refuse|regular), within issue")
write_csv(mod_tier, file.path(EST, "e11_model_tier.csv"))
print(as.data.frame(mod_tier %>% select(model, juris, regular, boundary, shift,
                                        conf_low, conf_high, estimable)),
      digits = 3, row.names = FALSE)

# -----------------------------------------------------------------------------
# B. Topic domain x prompt tier
# -----------------------------------------------------------------------------
# Pooled across models with BOTH an issue and a model random intercept. Pooling
# without a model term would let a few high-refusal models drive apparent domain
# differences; the previous version treated all responses as independent.
cat("\nB. domain x tier (pooled, issue + model random intercepts)\n")
m_dom <- tryCatch(
  glmer(y ~ tier * domain + (1|issue_id) + (1|model), d, binomial,
        control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))),
  error = function(e) { cat("  FAILED:", sub("\n.*", "", conditionMessage(e)), "\n"); NULL })

if (!is.null(m_dom)) {
  msg <- m_dom@optinfo$conv$lme4$messages
  cat(sprintf("  issue SD=%.3f  model SD=%.3f  warnings: %s\n",
              sqrt(VarCorr(m_dom)$issue_id[1]), sqrt(VarCorr(m_dom)$model[1]),
              if (is.null(msg)) "none" else paste(msg, collapse = "; ")))
  Xb <- model.matrix(terms(m_dom), transform(d, tier = factor("boundary", levels = levels(d$tier))))
  Xr <- model.matrix(terms(m_dom), transform(d, tier = factor("regular", levels = levels(d$tier))))
  re <- ranef(m_dom)$issue_id[as.character(d$issue_id), 1] +
        ranef(m_dom)$model[as.character(d$model), 1]
  b <- fixef(m_dom); V <- as.matrix(vcov(m_dom))
  dr <- MASS::mvrnorm(1500, b, V)
  f <- function(bb) {
    pb <- plogis(as.vector(Xb %*% bb) + re); pr <- plogis(as.vector(Xr %*% bb) + re)
    c(vapply(levels(d$domain), function(g) mean(pr[d$domain == g]), numeric(1)),
      vapply(levels(d$domain), function(g) mean(pb[d$domain == g]), numeric(1)),
      vapply(levels(d$domain), function(g) mean(pb[d$domain == g] - pr[d$domain == g]), numeric(1)))
  }
  nd <- nlevels(d$domain); est <- f(b); bs <- t(apply(dr, 1, f))
  dom_tier <- tibble(
    domain   = levels(d$domain),
    regular  = est[1:nd], boundary = est[(nd+1):(2*nd)], shift = est[(2*nd+1):(3*nd)],
    conf_low  = apply(bs[, (2*nd+1):(3*nd)], 2, quantile, .025),
    conf_high = apply(bs[, (2*nd+1):(3*nd)], 2, quantile, .975),
    n      = as.integer(table(d$domain)),
    events = as.integer(tapply(d$y, d$domain, sum))) %>%
    mutate(estimable = TRUE,
           spec = "refused ~ tier*domain + (1|issue_id) + (1|model)",
           sample = "English, all models, all regions", scale = "probability",
           contrast = "P(refuse|boundary) - P(refuse|regular), within issue")
  write_csv(dom_tier, file.path(EST, "e12_domain_tier.csv"))
  print(as.data.frame(dom_tier %>% select(domain, regular, boundary, shift,
                                          conf_low, conf_high)),
        digits = 3, row.names = FALSE)
}

# Sensitivity: model as a FIXED effect. The 11 subject models are purposively
# chosen, not a random sample from a population of models, so a random intercept
# is a shrinkage convenience rather than a sampling claim. The domain x tier
# contrast is the estimand and `model` is a nuisance control, so what matters is
# whether the choice moves the domain shifts. Both are exported; the random-
# intercept version stays primary because it converged cleanly and the fixed
# version is a strictly larger parameterisation of the same nuisance.
cat("\n   sensitivity: model as fixed effect\n")
m_dom_fx <- tryCatch(
  glmer(y ~ tier * domain + model + (1|issue_id), d, binomial,
        control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))),
  error = function(e) { cat("   FAILED:", sub("\n.*", "", conditionMessage(e)), "\n"); NULL })
if (!is.null(m_dom_fx) && exists("dom_tier")) {
  Xb2 <- model.matrix(terms(m_dom_fx), transform(d, tier = factor("boundary", levels = levels(d$tier))))
  Xr2 <- model.matrix(terms(m_dom_fx), transform(d, tier = factor("regular",  levels = levels(d$tier))))
  re2 <- ranef(m_dom_fx)$issue_id[as.character(d$issue_id), 1]
  b2  <- fixef(m_dom_fx)
  pb2 <- plogis(as.vector(Xb2 %*% b2) + re2); pr2 <- plogis(as.vector(Xr2 %*% b2) + re2)
  fx <- tibble(domain = levels(d$domain),
               shift_fixed_model = vapply(levels(d$domain),
                 function(g) mean(pb2[d$domain == g] - pr2[d$domain == g]), numeric(1)))
  sens_dom <- dom_tier %>% select(domain, shift_random_model = shift) %>%
    left_join(fx, by = "domain") %>%
    mutate(abs_diff_pp = 100 * abs(shift_random_model - shift_fixed_model))
  write_csv(sens_dom, file.path(EST, "e12b_domain_tier_model_fixed.csv"))
  cat(sprintf("   max |random - fixed| across domains: %.2f pp\n",
              max(sens_dom$abs_diff_pp)))
}

# -----------------------------------------------------------------------------
# C. Refusal-justification composition
# -----------------------------------------------------------------------------
# Conditional on having refused, so the unit is the refusal EVENT and the
# denominator is that model's refusal count. The four groups are a collapse of
# the judge's seven codes. This is a composition constrained to sum to 1, and
# the measurement instrument is a single LLM judge with no reliability estimate
# -- both facts belong in the caption, and the denominators are carried here so
# the figure can show them.
cat("\nC. refusal-justification composition\n")
# FIVE groups, not four. Auditing the raw codes showed the old collapse was not
# defensible:
#   * G ("other") is 15.7% of English refusals -- almost as large as harm -- and
#     reading all 222 free-text entries shows it is heterogeneous: degenerate
#     output ("nonsensical and rambling"), explicit task refusals, and epistemic
#     statements ("lacks reliable information") all land in G. Folding it into F
#     ("no reason given") created a category meaning two incompatible things and
#     hid a measurement failure mode -- worst for allam-7b, where G is 31.7% of
#     426 refusals.
#   * B and E have TWO responses each in the whole English refusal set, so
#     "epistemic" is effectively D (expertise limitation) alone. Kept as one
#     group because the three are conceptually one family, but the caption must
#     say the category is thin.
# The raw 7-code table is exported alongside so the collapse is auditable.
J5 <- c(A = "neutrality", C = "harm", B = "epistemic", D = "epistemic",
        E = "epistemic", F = "none given", G = "other")
LEV5 <- names(PAL_REASON)   # neutrality, harm, epistemic, other, none given

raw_codes <- d %>%
  filter(refused, !is.na(refusal_justification)) %>%
  count(model, refusal_justification) %>%
  group_by(model) %>% mutate(n_refusals = sum(n), share = n / n_refusals) %>%
  ungroup() %>%
  mutate(group = unname(J5[refusal_justification]),
         code_label = c(A = "A neutrality", B = "B complexity", C = "C harm avoidance",
                        D = "D expertise limitation", E = "E user autonomy",
                        F = "F none given", G = "G other")[refusal_justification])
write_csv(raw_codes, file.path(EST, "e13b_refusal_codes_raw.csv"))
cat(sprintf("  raw codes: %d model x code rows; G share overall %.1f%%\n",
            nrow(raw_codes),
            100 * sum(raw_codes$n[raw_codes$refusal_justification == "G"]) /
              sum(raw_codes$n)))

reasons <- d %>%
  filter(refused, !is.na(refusal_justification)) %>%
  mutate(reason = factor(unname(J5[refusal_justification]), levels = LEV5)) %>%
  filter(!is.na(reason)) %>%
  # .drop = FALSE must span model x reason ONLY. Including juris in the count
  # expands every model against every jurisdiction level, producing phantom rows
  # (each model appearing under all five jurisdictions with n = 0). juris is a
  # property of the model, so it is joined back afterwards.
  count(model, reason, .drop = FALSE) %>%
  group_by(model) %>% mutate(n_refusals = sum(n), share = n / n_refusals) %>%
  ungroup() %>%
  left_join(distinct(d, model, juris), by = "model") %>%
  filter(n_refusals >= 30) %>%
  bind_cols(wilson_ci(.$n, .$n_refusals)) %>%
  rename(conf_low = lo, conf_high = hi) %>%
  mutate(juris = as.character(juris),
         spec = "descriptive composition, conditional on refusal",
         sample = "English, models with >= 30 refusals", scale = "share of refusals",
         contrast = "share of that model's refusals citing each reason group",
         estimable = TRUE)
write_csv(reasons, file.path(EST, "e13_refusal_reasons.csv"))
cat(sprintf("  %d models x %d reason groups; denominators %d-%d refusals\n",
            n_distinct(reasons$model), nlevels(reasons$reason),
            min(reasons$n_refusals), max(reasons$n_refusals)))

# Overall rate summary, used as an optional compact strip.
overall <- d %>% group_by(model, juris) %>%
  summarise(n = n(), events = sum(y), rate = mean(y), .groups = "drop") %>%
  bind_cols(wilson_ci(.$events, .$n)) %>% rename(conf_low = lo, conf_high = hi) %>%
  mutate(juris = as.character(juris), estimable = TRUE,
         spec = "descriptive rate", sample = "English, all regions",
         scale = "probability", contrast = "overall refusal rate")
write_csv(overall, file.path(EST, "e14_overall_rates.csv"))

cat("\n", strrep("=", 78), "\nDONE\n", strrep("=", 78), "\n", sep = "")
