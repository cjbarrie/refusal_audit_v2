# =============================================================================
# Script 09: PNAS-grade stats augmentation for the DeepSeek finding
# =============================================================================
# Recomputes the headline DeepSeek Chinese-vs-English chi-squared tests with
# bootstrap 95% odds-ratio CIs, Cramer's V effect sizes, and Benjamini-Hochberg-
# corrected p-values across the per-model and per-category test families.
#
# Does NOT modify 08_deepseek_chinese_analysis.R or the tables it produces.
# Emits new tables 43/44 that the PNAS paper pulls from directly.
# =============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(boot)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
load("pipeline/data_clean.RData")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
cramers_v <- function(tbl) {
  chisq <- suppressWarnings(chisq.test(tbl)$statistic)
  n     <- sum(tbl)
  k     <- min(nrow(tbl), ncol(tbl))
  as.numeric(sqrt(chisq / (n * (k - 1))))
}

bootstrap_or_ci <- function(data, R = 1000, seed = 42) {
  # 2x2 OR with Haldane-Anscombe correction for zero cells.
  or_stat <- function(df, idx) {
    s <- df[idx, ]
    a <- sum(s$lang_zh == 1 & s$refused == 1) + 0.5
    b <- sum(s$lang_zh == 1 & s$refused == 0) + 0.5
    c <- sum(s$lang_zh == 0 & s$refused == 1) + 0.5
    d <- sum(s$lang_zh == 0 & s$refused == 0) + 0.5
    (a / b) / (c / d)
  }
  set.seed(seed)
  bs <- boot::boot(data, statistic = or_stat, R = R)
  ci <- tryCatch(
    boot::boot.ci(bs, type = "perc")$percent[4:5],
    error = function(e) c(NA_real_, NA_real_)
  )
  tibble(or = bs$t0, or_lo = ci[1], or_hi = ci[2])
}

# -----------------------------------------------------------------------------
# Per-model Chinese-vs-English tests (BH-corrected across 5 models)
# -----------------------------------------------------------------------------
per_model <- data_clean %>%
  filter(prompt_language %in% c("en", "zh"),
         controversy_tier == "regular") %>%
  mutate(lang_zh = as.integer(prompt_language == "zh"),
         refused = as.integer(refused))

results_per_model <- per_model %>%
  group_split(model) %>%
  map_dfr(function(dat) {
    model_name <- dat$model[1]
    tbl <- table(dat$lang_zh, dat$refused)
    if (!all(dim(tbl) == c(2, 2)) || min(rowSums(tbl)) == 0) {
      return(tibble(
        model = model_name, test = "skipped (no variation)",
        chi_sq = NA, df = NA, p_value = NA, cramers_v = NA,
        or = NA, or_lo = NA, or_hi = NA,
        n_en = sum(dat$lang_zh == 0), n_zh = sum(dat$lang_zh == 1)
      ))
    }
    ct <- suppressWarnings(chisq.test(tbl))
    bs <- bootstrap_or_ci(dat, R = 1000)
    tibble(
      model = model_name,
      test  = "chi-squared",
      chi_sq = as.numeric(ct$statistic),
      df     = as.numeric(ct$parameter),
      p_value = ct$p.value,
      cramers_v = cramers_v(tbl),
      or = bs$or, or_lo = bs$or_lo, or_hi = bs$or_hi,
      n_en = sum(dat$lang_zh == 0), n_zh = sum(dat$lang_zh == 1)
    )
  })

# BH correction across 5 model-level tests.
results_per_model <- results_per_model %>%
  mutate(p_adj_bh = p.adjust(p_value, method = "BH"))

cat("\n=== Per-model Chinese vs English refusal: bootstrap OR + BH-adjusted p ===\n")
print(results_per_model, n = Inf)

dir.create("pipeline/tables", showWarnings = FALSE, recursive = TRUE)
write_csv(results_per_model, "pipeline/tables/43_per_model_lang_tests_pnas.csv")

# -----------------------------------------------------------------------------
# DeepSeek per-category tests (regular prompts only, BH-corrected across categories)
# -----------------------------------------------------------------------------
ds_regular <- data_clean %>%
  filter(model == "deepseek-chat-v3.1",
         prompt_language %in% c("en", "zh"),
         controversy_tier == "regular") %>%
  mutate(lang_zh = as.integer(prompt_language == "zh"),
         refused = as.integer(refused))

results_per_cat <- ds_regular %>%
  group_split(prompt_category) %>%
  map_dfr(function(dat) {
    cat_name <- dat$prompt_category[1]
    tbl <- table(dat$lang_zh, dat$refused)
    if (!all(dim(tbl) == c(2, 2)) || min(rowSums(tbl)) == 0) {
      return(tibble(
        prompt_category = cat_name,
        test = "skipped (no variation)",
        p_value = NA, cramers_v = NA,
        or = NA, or_lo = NA, or_hi = NA,
        n = nrow(dat)
      ))
    }
    # Use Fisher's exact when expected cells < 5; reflects the existing pipeline.
    min_expected <- suppressWarnings(min(chisq.test(tbl)$expected))
    if (min_expected < 5) {
      ft <- fisher.test(tbl)
      p_val <- ft$p.value
      cv    <- cramers_v(tbl)
    } else {
      ct <- suppressWarnings(chisq.test(tbl))
      p_val <- ct$p.value
      cv    <- cramers_v(tbl)
    }
    bs <- bootstrap_or_ci(dat, R = 1000)
    tibble(
      prompt_category = cat_name,
      test  = ifelse(min_expected < 5, "Fisher exact", "chi-squared"),
      p_value = p_val,
      cramers_v = cv,
      or = bs$or, or_lo = bs$or_lo, or_hi = bs$or_hi,
      n = nrow(dat)
    )
  })

results_per_cat <- results_per_cat %>%
  mutate(p_adj_bh = p.adjust(p_value, method = "BH")) %>%
  arrange(desc(or))

cat("\n=== DeepSeek per-category regular-prompt language tests (BH-adjusted) ===\n")
print(results_per_cat, n = Inf)

write_csv(results_per_cat, "pipeline/tables/44_deepseek_per_category_pnas.csv")

cat("\nWrote: tables/43_per_model_lang_tests_pnas.csv, tables/44_deepseek_per_category_pnas.csv\n")
