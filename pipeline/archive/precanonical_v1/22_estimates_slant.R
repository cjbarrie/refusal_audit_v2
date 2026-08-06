# =============================================================================
# Script 22: Slant estimates -- ideology and moral foundations
# =============================================================================
# Input : pipeline/data_clean.RData
# Output: pipeline/estimates/e15..e18*.csv
#
# ESTIMATION ONLY. 30_figures.R reads these tables and draws; it never re-fits.
#
# -----------------------------------------------------------------------------
# SAMPLE: the 25% slant subsample
# -----------------------------------------------------------------------------
# Annotation passes 2 (ideology) and 3 (moral foundations) were run on a 25%
# subsample of ISSUES, not of responses -- see docs/SLANT_SUBSAMPLE.md. Sampling
# whole issues keeps every model x language x tier cell balanced and preserves
# issue-level clustering; sampling responses would have broken both.
#
# Every quantity here is therefore restricted to `slant_eligible & has_slant`.
# Refusal quantities elsewhere in the pipeline use the FULL sample and are
# unaffected: Pass 1 ran on everything.
#
# The codes are also CONDITIONAL ON ENGAGEMENT. Passes 2/3 are skipped for
# refusals by design (a refusal has no position to score), so these describe how
# models lean WHEN THEY ANSWER, not how often they answer.
#
# -----------------------------------------------------------------------------
# UNCERTAINTY
# -----------------------------------------------------------------------------
# Issue-cluster bootstrap throughout: responses are clustered within issue (all
# models answer the same battery), so a naive SE would be far too small. 800
# resamples of issues, percentile intervals.
#
# -----------------------------------------------------------------------------
# LANGUAGE RESTRICTION -- why the primary tables are English-only
# -----------------------------------------------------------------------------
# The subject-model roster is NOT constant across prompt languages: 11 models
# answer in English, Chinese and Arabic, but only 9 in Russian and 7 in Hindi.
# Pooling all five would confound a jurisdiction's measured slant with which of
# its models happen to answer in which language -- a composition artefact, not a
# finding. So the primary tables (e15-e18) are ENGLISH-ONLY, matching the rest of
# the pipeline, and the language comparison (e20) is restricted to the three
# complete-roster languages where the 11 models are held fixed.

suppressPackageStartupMessages({ library(tidyverse) })
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")
load("pipeline/data_clean.RData")
EST <- "pipeline/estimates"; dir.create(EST, showWarnings = FALSE, recursive = TRUE)
set.seed(20260803)
B <- 800

cat(strrep("=", 78), "\nSLANT ESTIMATES\n", strrep("=", 78), "\n", sep = "")

IDEO <- c(economic_left_right       = "Economic",
          social_left_right         = "Social",
          authoritarian_libertarian = "Authority",
          populist_elitist          = "Populism")
MFT  <- c(care_harm            = "Care / harm",
          fairness_cheating    = "Fairness / cheating",
          liberty_oppression   = "Liberty / oppression",
          authority_subversion = "Authority / subversion",
          loyalty_betrayal     = "Loyalty / betrayal",
          sanctity_degradation = "Sanctity / degradation")

LANG_COMPLETE <- c("en", "zh", "ar")   # all 11 models answer in these

d_all <- data_clean %>%
  filter(slant_eligible, has_slant, !is.na(jurisdiction_f)) %>%
  mutate(juris = factor(as.character(jurisdiction_f), levels = JURIS_LEVELS))
d <- d_all %>% filter(prompt_language == "en")

if (nrow(d) == 0) {
  cat("SKIP: no rows carry slant codes yet (passes 2/3 not run or not assembled).\n")
  quit(save = "no", status = 0)
}

cat(sprintf("Primary sample (English): %d responses, %d issues, %d models\n",
            nrow(d), n_distinct(d$issue_id), n_distinct(d$model)))
cat(sprintf("All languages available    : %d responses across %d languages\n",
            nrow(d_all), n_distinct(d_all$prompt_language)))
cat(sprintf("Engaged-only by construction: %.1f%% of rows have engagement_code <= 3\n\n",
            100 * mean(d$engaged)))

# Issue-cluster bootstrap for a scalar statistic over a data frame.
boot_ci <- function(df, stat, B. = B) {
  iss <- unique(df$issue_id)
  idx <- split(seq_len(nrow(df)), df$issue_id)
  bs <- replicate(B., {
    tk <- sample(iss, length(iss), replace = TRUE)
    stat(df[unlist(idx[tk]), , drop = FALSE])
  })
  c(lo = unname(quantile(bs, .025, na.rm = TRUE)),
    hi = unname(quantile(bs, .975, na.rm = TRUE)))
}

# -----------------------------------------------------------------------------
# e15  Ideology: the DISTRIBUTION, not just the mean
# -----------------------------------------------------------------------------
# Reported as the share at each code because the mean alone is misleading here:
# the codes are overwhelmingly 0, so every mean sits near zero and a
# mean-with-interval plot would show five dots on the origin and imply the
# instrument had failed. The distribution shows what is actually true -- that the
# judge finds these responses ideologically neutral in the large majority of
# cases, with small and asymmetric tails.
cat("e15 ideology distribution\n")
e15 <- map_dfr(names(IDEO), function(f) {
  d %>% filter(!is.na(.data[[f]])) %>%
    count(juris, code = .data[[f]]) %>%
    group_by(juris) %>% mutate(share = n / sum(n), n_juris = sum(n)) %>%
    ungroup() %>% mutate(dimension = unname(IDEO[f]), field = f)
})
write_csv(e15, file.path(EST, "e15_ideology_distribution.csv"))
print(e15 %>% group_by(dimension) %>%
        summarise(`share at 0` = sprintf("%.1f%%", 100 * sum(n[code == 0]) / sum(n)),
                  .groups = "drop") %>% as.data.frame(), row.names = FALSE)

# -----------------------------------------------------------------------------
# e16  Ideology: mean position with issue-clustered intervals
# -----------------------------------------------------------------------------
cat("\ne16 ideology means\n")
e16 <- map_dfr(names(IDEO), function(f) {
  map_dfr(levels(d$juris), function(j) {
    dd <- d %>% filter(juris == j, !is.na(.data[[f]]))
    if (nrow(dd) < 30) return(NULL)
    st <- function(x) mean(x[[f]])
    ci <- boot_ci(dd, st)
    tibble(jurisdiction = j, dimension = unname(IDEO[f]), field = f,
           estimate = st(dd), conf_low = ci[["lo"]], conf_high = ci[["hi"]],
           n = nrow(dd), n_issues = n_distinct(dd$issue_id))
  })
}) %>% mutate(scale = "mean code on -2..+2",
              sample = "slant subsample, engaged, English",
              contrast = "mean ideological position", estimable = TRUE)
write_csv(e16, file.path(EST, "e16_ideology_means.csv"))
print(e16 %>% select(dimension, jurisdiction, estimate, conf_low, conf_high) %>%
        as.data.frame(), digits = 3, row.names = FALSE)

# -----------------------------------------------------------------------------
# e17  Moral foundations: prevalence by jurisdiction
# -----------------------------------------------------------------------------
cat("\ne17 moral-foundation prevalence\n")
e17 <- map_dfr(names(MFT), function(f) {
  map_dfr(levels(d$juris), function(j) {
    dd <- d %>% filter(juris == j, !is.na(.data[[f]]))
    if (nrow(dd) < 30) return(NULL)
    st <- function(x) mean(x[[f]])
    ci <- boot_ci(dd, st)
    tibble(jurisdiction = j, foundation = unname(MFT[f]), field = f,
           estimate = st(dd), conf_low = ci[["lo"]], conf_high = ci[["hi"]],
           n = nrow(dd), n_issues = n_distinct(dd$issue_id))
  })
}) %>% mutate(scale = "share invoking", sample = "slant subsample, engaged, English",
              contrast = "share of engaged responses invoking the foundation",
              estimable = TRUE)
write_csv(e17, file.path(EST, "e17_moral_prevalence.csv"))
print(e17 %>% select(foundation, jurisdiction, estimate, conf_low, conf_high) %>%
        as.data.frame(), digits = 3, row.names = FALSE)

# -----------------------------------------------------------------------------
# e18  Moral foundations by MODEL, for the model-level view
# -----------------------------------------------------------------------------
cat("\ne18 moral-foundation prevalence by model\n")
e18 <- map_dfr(names(MFT), function(f) {
  d %>% filter(!is.na(.data[[f]])) %>%
    group_by(model, juris) %>%
    summarise(estimate = mean(.data[[f]]), n = n(),
              n_issues = n_distinct(issue_id), .groups = "drop") %>%
    filter(n >= 30) %>%
    mutate(foundation = unname(MFT[f]), field = f)
}) %>% mutate(juris = as.character(juris), scale = "share invoking",
              sample = "slant subsample, engaged, English", estimable = TRUE)
write_csv(e18, file.path(EST, "e18_moral_by_model.csv"))
cat(sprintf("  %d models x %d foundations\n", n_distinct(e18$model), n_distinct(e18$foundation)))

# -----------------------------------------------------------------------------
# e16b  Ideology: the FULL summary a reader needs to judge the mean
# -----------------------------------------------------------------------------
# The mean alone is not interpretable when 74-93% of codes are exactly 0, and
# the neutral share alone hides direction. Both are exported together, with the
# pole shares, so no figure can show one without the other. The main panel plots
# `estimate` (the mean) and MUST also print `neutral_share`.
cat("\ne16b ideology full summary\n")
e16b <- map_dfr(names(IDEO), function(f) {
  map_dfr(levels(d$juris), function(j) {
    dd <- d %>% filter(juris == j, !is.na(.data[[f]]))
    if (nrow(dd) < 30) return(NULL)
    x <- dd[[f]]
    st <- function(z) mean(z[[f]])
    ci <- boot_ci(dd, st)
    tibble(jurisdiction = j, dimension = unname(IDEO[f]), field = f,
           n = nrow(dd), n_issues = n_distinct(dd$issue_id),
           n_models = n_distinct(dd$model),
           mean = mean(x), median = median(x),
           conf_low = ci[["lo"]], conf_high = ci[["hi"]],
           neutral_share = mean(x == 0), nonneutral_share = mean(x != 0),
           neg_share = mean(x < 0), pos_share = mean(x > 0))
  })
}) %>% mutate(scale = "mean code on -2..+2 (engaged responses)",
              sample = "slant subsample, engaged, English",
              uncertainty = "issue-clustered bootstrap, 800 resamples",
              weighting = "response-weighted", estimable = TRUE)
write_csv(e16b, file.path(EST, "e16b_ideology_summary.csv"))
print(as.data.frame(e16b %>% filter(dimension == "Populism") %>%
        select(jurisdiction, mean, conf_low, conf_high, neutral_share)),
      digits = 3, row.names = FALSE)

# -----------------------------------------------------------------------------
# e16c  Does jurisdiction aggregation hide model-level heterogeneity?
# -----------------------------------------------------------------------------
# Jurisdiction is DEFINED by model membership, so a jurisdiction mean is a
# composite of 1-4 model means. Reporting the decomposition is the only honest
# way to show whether a jurisdiction difference is a jurisdiction fact or one
# model. Also gives the equal-model-weighted alternative to the response-
# weighted mean actually plotted.
cat("\ne16c ideology decomposition (model within jurisdiction)\n")
e16c <- map_dfr(names(IDEO), function(f) {
  d %>% filter(!is.na(.data[[f]])) %>%
    group_by(juris, model) %>%
    summarise(model_mean = mean(.data[[f]]), n = n(), .groups = "drop") %>%
    group_by(juris) %>%
    mutate(juris_mean_equal_model = mean(model_mean),
           between_model_sd = ifelse(n() > 1, sd(model_mean), NA_real_),
           n_models = n()) %>%
    ungroup() %>% mutate(dimension = unname(IDEO[f]), field = f)
}) %>% mutate(juris = as.character(juris),
              sample = "slant subsample, engaged, English")
write_csv(e16c, file.path(EST, "e16c_ideology_by_model.csv"))
cat(sprintf("  max between-model SD within a jurisdiction: %.3f\n",
            max(e16c$between_model_sd, na.rm = TRUE)))

# -----------------------------------------------------------------------------
# e17b  Moral foundations: pooled reference + equal-model weighting
# -----------------------------------------------------------------------------
# The dominant pattern is BETWEEN foundations, not between jurisdictions, so the
# figure carries a pooled estimate per foundation to anchor the ranking. The
# equal-model column tests whether a jurisdiction average is driven by its model
# count (US has 4 models, India and EU one each).
cat("\ne17b moral foundations: pooled + equal-model weighting\n")
e17b <- map_dfr(names(MFT), function(f) {
  dd <- d %>% filter(!is.na(.data[[f]]))
  st <- function(z) mean(z[[f]])
  ci <- boot_ci(dd, st)
  bym <- dd %>% group_by(model) %>% summarise(m = mean(.data[[f]]), .groups = "drop")
  tibble(foundation = unname(MFT[f]), field = f,
         pooled = st(dd), conf_low = ci[["lo"]], conf_high = ci[["hi"]],
         equal_model = mean(bym$m), n = nrow(dd),
         n_issues = n_distinct(dd$issue_id), n_models = nrow(bym))
}) %>% mutate(sample = "slant subsample, engaged, English",
              uncertainty = "issue-clustered bootstrap, 800 resamples",
              contrast = "pooled prevalence across all models", estimable = TRUE)
write_csv(e17b, file.path(EST, "e17b_moral_pooled.csv"))
print(as.data.frame(e17b %>% select(foundation, pooled, conf_low, conf_high,
                                    equal_model)), digits = 3, row.names = FALSE)

# Equal-model-weighted jurisdiction estimates, as a weighting sensitivity.
e17c <- map_dfr(names(MFT), function(f) {
  d %>% filter(!is.na(.data[[f]])) %>%
    group_by(juris, model) %>% summarise(m = mean(.data[[f]]), .groups = "drop") %>%
    group_by(juris) %>%
    summarise(equal_model = mean(m), n_models = n(), .groups = "drop") %>%
    mutate(foundation = unname(MFT[f]), field = f)
}) %>% mutate(juris = as.character(juris))
write_csv(e17c, file.path(EST, "e17c_moral_equal_model.csv"))

# -----------------------------------------------------------------------------
# e20  Does slant travel across prompt language?
# -----------------------------------------------------------------------------
# Restricted to en/zh/ar, where the roster is identical, so a language difference
# cannot be a composition effect. Reported for the moral foundations, which carry
# real variance; the ideology codes are too concentrated at 0 to support a
# language contrast at this sample size.
cat("\ne20 moral foundations by prompt language (complete-roster languages)\n")
dL <- d_all %>% filter(prompt_language %in% LANG_COMPLETE)
e20 <- map_dfr(names(MFT), function(f) {
  map_dfr(LANG_COMPLETE, function(lg) {
    dd <- dL %>% filter(prompt_language == lg, !is.na(.data[[f]]))
    if (nrow(dd) < 30) return(NULL)
    st <- function(x) mean(x[[f]])
    ci <- boot_ci(dd, st)
    tibble(prompt_language = lg, foundation = unname(MFT[f]), field = f,
           estimate = st(dd), conf_low = ci[["lo"]], conf_high = ci[["hi"]],
           n = nrow(dd), n_issues = n_distinct(dd$issue_id),
           n_models = n_distinct(dd$model))
  })
}) %>% mutate(scale = "share invoking",
              sample = "slant subsample, engaged, en/zh/ar (11-model roster)",
              contrast = "share invoking, by prompt language", estimable = TRUE)
write_csv(e20, file.path(EST, "e20_moral_by_language.csv"))
print(e20 %>% select(foundation, prompt_language, estimate, conf_low, conf_high) %>%
        as.data.frame(), digits = 3, row.names = FALSE)

# Coverage note carried alongside, so a figure can state the sample honestly.
cov <- tibble(
  n_rows = nrow(d), n_issues = n_distinct(d$issue_id),
  n_models = n_distinct(d$model), primary_language = "en",
  n_rows_all_lang = nrow(d_all),
  languages_available = paste(sort(unique(d_all$prompt_language)), collapse = "/"),
  languages_complete_roster = paste(LANG_COMPLETE, collapse = "/"),
  subsample_frac = 0.25, subsample_seed = 20260803, unit = "issue_id")
write_csv(cov, file.path(EST, "e19_slant_coverage.csv"))

cat("\n", strrep("=", 78), "\nDONE\n", strrep("=", 78), "\n", sep = "")
