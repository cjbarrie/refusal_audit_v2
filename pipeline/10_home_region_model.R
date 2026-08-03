# =============================================================================
# Script 10: Home-region effect -- mixed-model specification
# =============================================================================
# Requires: pipeline/data_clean.RData (01_data_loading.R)
# Writes:   pipeline/tables/45_home_region_mixed.csv
#           pipeline/tables/46_home_region_contrasts.csv
#
# WHY THIS EXISTS ALONGSIDE FIG1B
# The headline home-region estimate reported in the figures (11_figures.R) is a
# g-computation average marginal effect with an issue-clustered bootstrap. It is
# on the PROBABILITY scale, makes no distributional assumption about the issue
# effect, and is robust to the fact that one jurisdiction (EU / Mistral) never
# refuses at all.
#
# This script fits the corresponding MIXED MODEL: the same contrast on the
# log-odds scale, with issue-level clustering handled parametrically by a random
# intercept rather than by resampling. The two are complementary -- agreement
# between them is evidence the result is not an artefact of either approach.
#
# GROUPING FACTOR IS issue_id.
# An earlier specification used (1 | prompt_id) and was not identifiable: each
# prompt_id carried only 2 observations (one prompt in two languages, one
# model), and lme4 returned a random-intercept SD of 13.8 on the logit scale
# with a degenerate Hessian -- a variance component pinned at the boundary, not
# an estimate. issue_id gives ~44 observations per group in the English sample
# across the eleven models, which is well identified (SD ~0.98, clean
# convergence). It is also the correct clustering level: prompts drawn from the
# same Wikipedia issue share content, so the issue is what repeats.

suppressPackageStartupMessages({
  library(tidyverse); library(lme4)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")
load("pipeline/data_clean.RData")
dir.create("pipeline/tables", showWarnings = FALSE, recursive = TRUE)

cat(strrep("=", 78), "\nHOME-REGION MIXED MODEL\n", strrep("=", 78), "\n", sep = "")

d <- data_clean %>%
  filter(!is.na(jurisdiction_f), !is.na(region_focus),
         prompt_language == "en", region_focus != "General") %>%
  mutate(juris       = factor(as.character(jurisdiction_f), levels = JURIS_LEVELS),
         home        = as.character(region_focus) == HOME_REGION[as.character(jurisdiction_f)],
         refused_num = as.numeric(refused),
         category_f  = factor(prompt_category))

cat(sprintf("n = %d | issues = %d | obs per issue = %.1f | refusals = %d\n\n",
            nrow(d), n_distinct(d$issue_id),
            nrow(d) / n_distinct(d$issue_id), sum(d$refused_num)))

# EU never refuses, so its home contrast is not estimable from the data: any
# finite coefficient it receives is imposed by the shared category structure
# rather than identified. Fit WITHOUT it and report EU separately, so the model
# is not quietly carrying a coefficient the data cannot support.
eu_refusals <- sum(d$refused_num[d$juris == "EU"])
if (eu_refusals == 0) {
  cat("EU (Mistral) has 0 refusals in this sample: excluded from the model and\n")
  cat("reported as a structural zero rather than an estimate.\n\n")
  d_fit <- d %>% filter(juris != "EU") %>% mutate(juris = droplevels(juris))
} else {
  d_fit <- d
}

fit <- tryCatch(
  glmer(refused_num ~ home * juris + category_f + (1 | issue_id),
        data = d_fit, family = binomial(link = "logit"),
        control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 1e5))),
  error = function(e) { cat("MIXED MODEL FAILED:", conditionMessage(e), "\n"); NULL })

if (is.null(fit)) {
  cat("SKIP: no mixed-model output written.\n")
} else {
  msgs <- fit@optinfo$conv$lme4$messages
  cat(sprintf("issue-level SD = %.3f | convergence warnings: %s\n\n",
              sqrt(unlist(VarCorr(fit))),
              if (is.null(msgs)) "none" else paste(msgs, collapse = "; ")))

  co <- as.data.frame(summary(fit)$coefficients) %>%
    rownames_to_column("term") %>%
    filter(grepl("home", term)) %>%
    transmute(term,
              log_odds = Estimate, se = `Std. Error`,
              z = `z value`, p = `Pr(>|z|)`,
              or = exp(Estimate),
              or_lo = exp(Estimate - 1.96 * `Std. Error`),
              or_hi = exp(Estimate + 1.96 * `Std. Error`))
  print(co, digits = 3, row.names = FALSE)
  write_csv(co, "pipeline/tables/45_home_region_mixed.csv")

  # Per-jurisdiction home contrast on the log-odds scale: the reference level's
  # main effect plus its own interaction. Reported as an odds ratio, which is
  # what the model estimates -- the probability-scale version is FIG1B.
  ref <- levels(d_fit$juris)[1]
  b <- fixef(fit); V <- as.matrix(vcov(fit))
  rows <- lapply(levels(d_fit$juris), function(j) {
    nm <- if (j == ref) "homeTRUE" else c("homeTRUE", paste0("homeTRUE:juris", j))
    nm <- nm[nm %in% names(b)]
    L <- setNames(rep(0, length(b)), names(b)); L[nm] <- 1
    est <- sum(L * b); se <- sqrt(drop(t(L) %*% V %*% L))
    tibble(jurisdiction = j, log_odds = est, se = se, or = exp(est),
           or_lo = exp(est - 1.96 * se), or_hi = exp(est + 1.96 * se))
  })
  contr <- bind_rows(rows)
  if (eu_refusals == 0)
    contr <- bind_rows(contr, tibble(jurisdiction = "EU", log_odds = NA_real_,
                                     se = NA_real_, or = NA_real_,
                                     or_lo = NA_real_, or_hi = NA_real_))
  cat("\nHome-region contrast by jurisdiction (odds ratio, issue-clustered):\n")
  print(as.data.frame(contr), digits = 3, row.names = FALSE)
  write_csv(contr, "pipeline/tables/46_home_region_contrasts.csv")
  cat("\nSaved: tables/45_home_region_mixed.csv, tables/46_home_region_contrasts.csv\n")
}

cat("\n", strrep("=", 78), "\nDONE\n", strrep("=", 78), "\n", sep = "")
