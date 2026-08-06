# =============================================================================
# Script 25: Prompt-language effects  (ESTIMATION ONLY -- no plotting)
# =============================================================================
# Input : pipeline/data_clean.RData
# Output: pipeline/estimates/e29..e31*.csv
#
# -----------------------------------------------------------------------------
# WHY THIS EXISTS
# -----------------------------------------------------------------------------
# Language was previously estimated for the two CHINESE models only (e09/e10,
# panel P5), because the DeepSeek Chinese-vs-English gap was the finding that
# prompted the analysis. That left most of the language variation unexamined,
# and the unexamined part is large:
#
#   allam-7b     refuses 68.8% in Russian against 17.1% in English
#   falcon3-10b  refuses 30.3% in Arabic  against  6.2% in English
#   sarvam-30b   refuses  0.8% in Hindi   against  6.1% in English (reversed)
#
# So the language effect is estimated here for EVERY model and EVERY language,
# and reported whether or not it is null -- a null for one model is evidence,
# not a reason to omit the row.
#
# -----------------------------------------------------------------------------
# THREE DISTINCT ESTIMANDS -- do not conflate them
# -----------------------------------------------------------------------------
#  e29  LANGUAGE effect, per model: does this model refuse more when prompted in
#       language L than in English? Contrast is within model, across languages,
#       holding the ISSUE fixed (the same issue is asked in all five languages).
#
#  e30  HOME-LANGUAGE effect: the same contrast restricted to the language of
#       the model's own jurisdiction (CN->zh, MENA->ar, India->hi). US and EU
#       models have English AS their home language, so no contrast exists for
#       them -- reported as such rather than silently dropped.
#
#  e31  HOME-REGION premium BY language, for every jurisdiction. This is the
#       generalisation of e10, which did it for CN only. It asks whether the
#       home premium itself moves with prompt language.
#
#       IMPORTANT: e31 is fitted PER JURISDICTION, so it is a WITHIN-JURISDICTION
#       home contrast -- the same estimand family as e03/e10, NOT the primary
#       cross-jurisdiction difference-in-differences of e01. Within one
#       jurisdiction, `home` is a property of the issue's region and is therefore
#       constant within issue, so it is identified from BETWEEN-issue variation
#       and the issue random intercept shrinks it. It must never be reported as
#       though it were the primary estimand.
#
# -----------------------------------------------------------------------------
# SPECIFICATION
# -----------------------------------------------------------------------------
# Prompts are translations of the SAME issue, so the issue is the natural
# blocking factor and every contrast is within-issue:
#
#     refused ~ language + tier + (1 | issue_id)        per model      (e29)
#     refused ~ home * language + tier + (1 | issue_id) per jurisdiction (e31)
#
# Probability-scale g-computation over the observed sample at the fitted issue
# effects (sample-conditional, exactly as in 20_), with a parametric bootstrap
# over the fixed-effect covariance.
#
# STRUCTURAL ZEROS AND MISSING CELLS ARE DIFFERENT THINGS and are kept apart:
#   * mistral-large-2512 records 0 refusals in ALL five languages -> not
#     estimable, carried as a flagged row, never plotted as zero.
#   * allam-7b / falcon3-10b / jais-8b have NO Hindi responses yet -> the cell is
#     absent, not zero. Marked `not_generated` so a figure can leave it blank
#     rather than draw a false zero.

suppressPackageStartupMessages({
  library(tidyverse); library(lme4); library(MASS)
})
select <- dplyr::select
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")
load("pipeline/data_clean.RData")
EST <- "pipeline/estimates"; dir.create(EST, showWarnings = FALSE, recursive = TRUE)
set.seed(20260803)
B_BOOT <- 1000

cat(strrep("=", 78), "\nPROMPT-LANGUAGE EFFECTS\n", strrep("=", 78), "\n", sep = "")

LANGS <- c("en", "zh", "ar", "ru", "hi")
LANG_LABEL <- c(en = "English", zh = "Chinese", ar = "Arabic",
                ru = "Russian", hi = "Hindi")
# The language of each jurisdiction's own linguistic sphere. US and EU models are
# English-native, so "home language" is English and the contrast is undefined.
HOME_LANG <- c(CN = "zh", MENA = "ar", India = "hi", US = "en", EU = "en")

d <- data_clean %>%
  filter(!is.na(jurisdiction_f), prompt_language %in% LANGS) %>%
  mutate(juris = factor(as.character(jurisdiction_f), levels = JURIS_LEVELS),
         lang  = factor(prompt_language, levels = LANGS),
         tier  = factor(dataset_type, levels = c("base", "boundary")),
         y     = as.numeric(refused))

cat(sprintf("sample: %d responses, %d models, %d languages, %d issues\n\n",
            nrow(d), n_distinct(d$model), n_distinct(d$lang), n_distinct(d$issue_id)))

fit_lang <- function(f, dd) {
  for (opt in c("bobyqa", "Nelder_Mead")) {
    m <- tryCatch(glmer(f, dd, binomial,
                        control = glmerControl(optimizer = opt,
                                               optCtrl = list(maxfun = 2e5))),
                  error = function(e) NULL)
    if (!is.null(m)) return(m)
  }
  tryCatch(glmer(f, dd, binomial, nAGQ = 0,
                 control = glmerControl(optimizer = "bobyqa",
                                        optCtrl = list(maxfun = 2e5))),
           error = function(e) NULL)
}

# -----------------------------------------------------------------------------
# e29  Language effect per model
# -----------------------------------------------------------------------------
cat("e29 per-model language effects\n")
e29 <- map_dfr(sort(unique(d$model)), function(mm) {
  dd <- d %>% filter(model == mm) %>% mutate(lang = droplevels(lang))
  jur <- as.character(dd$juris[1])
  present <- levels(dd$lang)
  absent <- setdiff(LANGS, present)
  base_rows <- tibble(model = mm, jurisdiction = jur,
                      language = LANGS,
                      n = map_int(LANGS, ~ sum(dd$lang == .x)),
                      events = map_int(LANGS, ~ sum(dd$y[dd$lang == .x])),
                      raw_rate = map_dbl(LANGS, ~ {
                        s <- dd$lang == .x
                        if (!any(s)) NA_real_ else mean(dd$y[s]) }),
                      not_generated = LANGS %in% absent)

  if (sum(dd$y) == 0)
    return(base_rows %>% mutate(estimate = NA_real_, conf_low = NA_real_,
                                conf_high = NA_real_, estimable = FALSE,
                                note = "0 observed refusals in any language; not estimable"))
  if (nlevels(dd$lang) < 2)
    return(base_rows %>% mutate(estimate = NA_real_, conf_low = NA_real_,
                                conf_high = NA_real_, estimable = FALSE,
                                note = "only one language present"))

  dd <- dd[order(as.character(dd$issue_id), as.character(dd$lang)), ]
  rhs <- if (nlevels(droplevels(dd$tier)) > 1) "lang + tier" else "lang"
  m <- fit_lang(as.formula(paste("y ~", rhs, "+ (1|issue_id)")), dd)
  if (is.null(m))
    return(base_rows %>% mutate(estimate = NA_real_, conf_low = NA_real_,
                                conf_high = NA_real_, estimable = FALSE,
                                note = "model did not converge"))

  re <- ranef(m)$issue_id[as.character(dd$issue_id), 1]
  b <- fixef(m); V <- as.matrix(vcov(m))
  dr <- MASS::mvrnorm(B_BOOT, b, V)
  # Contrast: each language vs ENGLISH, with the issue held fixed. Both
  # counterfactuals are evaluated on the SAME rows, so the comparison is not
  # confounded by which issues happen to appear in which language file.
  X <- lapply(present, function(lv)
    model.matrix(terms(m), transform(dd, lang = factor(lv, levels = present))))
  names(X) <- present
  contrast_vs_en <- function(bb) {
    p <- vapply(present, function(lv) mean(plogis(as.vector(X[[lv]] %*% bb) + re)),
                numeric(1))
    p - p[["en"]]
  }
  est <- contrast_vs_en(b); bs <- t(apply(dr, 1, contrast_vs_en))
  res <- tibble(language = present, estimate = est,
                conf_low = apply(bs, 2, quantile, .025),
                conf_high = apply(bs, 2, quantile, .975))
  base_rows %>% left_join(res, by = "language") %>%
    mutate(estimable = !not_generated & language != "en", note = "")
}) %>%
  mutate(language_label = unname(LANG_LABEL[language]),
         spec = "refused ~ language + tier + (1|issue_id), per model",
         scale = "probability", contrast = "P(refuse|language) - P(refuse|English)",
         estimand_type = "sample-conditional",
         uncertainty = "parametric bootstrap over fixed effects; BLUPs held fixed")
write_csv(e29, file.path(EST, "e29_language_by_model.csv"))
print(as.data.frame(e29 %>% filter(language != "en", !not_generated, estimable) %>%
        select(model, language, raw_rate, estimate, conf_low, conf_high) %>%
        arrange(desc(abs(estimate))) %>% head(12)), digits = 3, row.names = FALSE)

# -----------------------------------------------------------------------------
# e30  Home-language effect
# -----------------------------------------------------------------------------
cat("\ne30 home-language effect (own-sphere language vs English)\n")
e30 <- e29 %>%
  mutate(home_language = unname(HOME_LANG[jurisdiction])) %>%
  filter(language == home_language) %>%
  mutate(defined = home_language != "en",
         note = ifelse(!defined,
                       "English IS this jurisdiction's home language; no contrast exists",
                       note)) %>%
  select(model, jurisdiction, home_language, language_label, n, events, raw_rate,
         estimate, conf_low, conf_high, estimable, defined, not_generated, note)
write_csv(e30, file.path(EST, "e30_home_language.csv"))
print(as.data.frame(e30 %>% select(model, jurisdiction, home_language,
                                   raw_rate, estimate, conf_low, conf_high,
                                   defined, not_generated)),
      digits = 3, row.names = FALSE)

# -----------------------------------------------------------------------------
# e31  Home-REGION premium by language, all jurisdictions
# -----------------------------------------------------------------------------
# Generalises e10 (which covered CN only). Asks whether the within-issue home
# premium itself depends on the language the prompt is asked in.
cat("\ne31 home-region premium by language, per jurisdiction\n")
dr_all <- d %>%
  filter(!is.na(region_focus), region_focus != "General") %>%
  mutate(home = as.integer(as.character(region_focus) ==
                             HOME_REGION[as.character(juris)]))
e31 <- map_dfr(levels(droplevels(dr_all$juris)), function(jj) {
  dd <- dr_all %>% filter(juris == jj) %>% mutate(lang = droplevels(lang))
  if (sum(dd$y) == 0)
    return(tibble(jurisdiction = jj, language = levels(dd$lang),
                  estimate = NA_real_, conf_low = NA_real_, conf_high = NA_real_,
                  n = NA_integer_, events = 0L, estimable = FALSE,
                  note = "0 observed refusals; not estimable"))
  dd <- dd[order(as.character(dd$issue_id), as.character(dd$model)), ]
  m <- fit_lang(y ~ home * lang + tier + (1|issue_id), dd)
  if (is.null(m))
    return(tibble(jurisdiction = jj, language = levels(dd$lang),
                  estimate = NA_real_, conf_low = NA_real_, conf_high = NA_real_,
                  n = NA_integer_, events = NA_integer_, estimable = FALSE,
                  note = "did not converge"))
  X1 <- model.matrix(terms(m), transform(dd, home = 1L))
  X0 <- model.matrix(terms(m), transform(dd, home = 0L))
  re <- ranef(m)$issue_id[as.character(dd$issue_id), 1]
  b <- fixef(m); V <- as.matrix(vcov(m))
  dr2 <- MASS::mvrnorm(B_BOOT, b, V)
  pt <- function(bb) {
    p1 <- plogis(as.vector(X1 %*% bb) + re); p0 <- plogis(as.vector(X0 %*% bb) + re)
    vapply(levels(dd$lang), function(lv) mean(p1[dd$lang == lv] - p0[dd$lang == lv]),
           numeric(1))
  }
  est <- pt(b); bs <- t(apply(dr2, 1, pt))
  tibble(jurisdiction = jj, language = levels(dd$lang), estimate = est,
         conf_low = apply(bs, 2, quantile, .025),
         conf_high = apply(bs, 2, quantile, .975),
         n = as.integer(table(dd$lang)[levels(dd$lang)]),
         events = as.integer(tapply(dd$y, dd$lang, sum)[levels(dd$lang)]),
         estimable = TRUE, note = "")
}) %>%
  mutate(language_label = unname(LANG_LABEL[language]),
         spec = "refused ~ home*language + tier + (1|issue_id), per jurisdiction",
         scale = "probability",
         contrast = "WITHIN-JURISDICTION home premium by prompt language (not the primary DiD)",
         estimand_type = "sample-conditional")
write_csv(e31, file.path(EST, "e31_home_premium_by_language.csv"))
print(as.data.frame(e31 %>% filter(estimable) %>%
        select(jurisdiction, language, estimate, conf_low, conf_high)),
      digits = 3, row.names = FALSE)

cat("\n", strrep("=", 78), "\nDONE\n", strrep("=", 78), "\n", sep = "")
