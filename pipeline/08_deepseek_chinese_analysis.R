#!/usr/bin/env Rscript
# =============================================================================
# Script 08: DeepSeek Chinese Refusal Deep-Dive
# =============================================================================
# Formal statistical tests for DeepSeek's higher refusal rates in Chinese
# Creates tables 41-42 and figures 22-23

library(tidyverse)
library(lme4)
library(scales)

# Set working directory
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes

# Load clean data
load("pipeline/data_clean.RData")

cat(rep("=", 80), "\n", sep = "")
cat("DEEPSEEK CHINESE REFUSAL DEEP-DIVE\n")
cat(rep("=", 80), "\n", sep = "")

# =============================================================================
# 1. Chi-Square Tests: Refusal by Language for Each Model
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("CHI-SQUARE / FISHER'S EXACT TESTS: REFUSAL × LANGUAGE BY MODEL\n")
cat(rep("-", 80), "\n", sep = "")

# Filter to English and Chinese only
data_en_zh <- data_clean %>%
  filter(prompt_language %in% c("en", "zh"))

models <- unique(data_en_zh$model)

chi_sq_results <- map_dfr(models, function(m) {
  model_data <- data_en_zh %>% filter(model == m)

  # Create 2x2 table: refused (yes/no) × language (en/zh)
  tbl <- table(model_data$refused, model_data$prompt_language)

  # Skip models with no variation in refusal (e.g., Grok with 0% refusal)
  if (nrow(tbl) < 2 || ncol(tbl) < 2) {
    return(tibble(
      model = m,
      test_type = "Skipped (no variation)",
      statistic = NA_real_,
      p_value = NA_real_,
      odds_ratio = NA_real_,
      ci_lower = NA_real_,
      ci_upper = NA_real_,
      min_expected_count = NA_real_,
      en_refusal_rate = mean(model_data$refused[model_data$prompt_language == "en"]),
      zh_refusal_rate = mean(model_data$refused[model_data$prompt_language == "zh"]),
      en_n = sum(model_data$prompt_language == "en"),
      zh_n = sum(model_data$prompt_language == "zh")
    ))
  }

  # Check if any cell < 5 for Fisher's exact test
  min_expected <- min(chisq.test(tbl)$expected)
  use_fisher <- min_expected < 5

  if (use_fisher) {
    test <- fisher.test(tbl)
    tibble(
      model = m,
      test_type = "Fisher's exact",
      statistic = NA_real_,
      p_value = test$p.value,
      odds_ratio = test$estimate,
      ci_lower = test$conf.int[1],
      ci_upper = test$conf.int[2],
      min_expected_count = min_expected,
      en_refusal_rate = mean(model_data$refused[model_data$prompt_language == "en"]),
      zh_refusal_rate = mean(model_data$refused[model_data$prompt_language == "zh"]),
      en_n = sum(model_data$prompt_language == "en"),
      zh_n = sum(model_data$prompt_language == "zh")
    )
  } else {
    test <- chisq.test(tbl)
    # Also compute OR from the table
    fisher_for_or <- fisher.test(tbl)
    tibble(
      model = m,
      test_type = "Chi-square",
      statistic = test$statistic,
      p_value = test$p.value,
      odds_ratio = fisher_for_or$estimate,
      ci_lower = fisher_for_or$conf.int[1],
      ci_upper = fisher_for_or$conf.int[2],
      min_expected_count = min_expected,
      en_refusal_rate = mean(model_data$refused[model_data$prompt_language == "en"]),
      zh_refusal_rate = mean(model_data$refused[model_data$prompt_language == "zh"]),
      en_n = sum(model_data$prompt_language == "en"),
      zh_n = sum(model_data$prompt_language == "zh")
    )
  }
})

cat("\nChi-square / Fisher's test results:\n")
print(chi_sq_results)

write_csv(chi_sq_results, "pipeline/tables/41_deepseek_chi_square_tests.csv")
cat("Saved: pipeline/tables/41_deepseek_chi_square_tests.csv\n")

# =============================================================================
# 2. Logistic Regression: DeepSeek Refusal ~ Language * Category
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("LOGISTIC REGRESSION: DEEPSEEK REFUSAL ~ LANGUAGE * CATEGORY\n")
cat(rep("-", 80), "\n", sep = "")

deepseek_en_zh <- data_en_zh %>%
  filter(model == "deepseek-chat-v3.1") %>%
  mutate(
    lang_zh = as.numeric(prompt_language == "zh"),
    refused_num = as.numeric(refused),
    category_f = factor(prompt_category)
  )

cat(sprintf("\nDeepSeek EN+ZH observations: %d\n", nrow(deepseek_en_zh)))

# Mixed-effects logistic regression with prompt_id random intercept
cat("\nFitting mixed-effects model: refused ~ lang_zh * category_f + (1|prompt_id)\n")
# The prompt_id random intercept is near-degenerate here: each prompt_id has at
# most two observations (EN and ZH), and within several topic domains DeepSeek
# refuses almost never, so the interaction cells approach separation. lme4 then
# fails in PIRLS with "Downdated VtV is not positive definite" -- an
# UNRECOVERABLE error, not a warning, which took the whole script down and every
# table and figure after it. Fall back to a fixed-effects logit with
# cluster-free SEs and say so, rather than losing the rest of the analysis.
model_mixed <- tryCatch(
  glmer(
    refused_num ~ lang_zh * category_f + (1 | prompt_id),
    data = deepseek_en_zh,
    family = binomial(link = "logit"),
    control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 100000))
  ),
  error = function(e) {
    cat(sprintf("\n  NOTE: mixed model did not converge (%s).\n",
                sub("\n.*", "", conditionMessage(e))))
    cat("  Falling back to fixed-effects logit without the prompt random intercept.\n")
    cat("  Standard errors below do NOT account for the EN/ZH pairing, so they\n")
    cat("  are anti-conservative; treat the ORs as descriptive.\n")
    NULL
  }
)

if (is.null(model_mixed)) {
  model_mixed <- glm(refused_num ~ lang_zh * category_f,
                     data = deepseek_en_zh, family = binomial(link = "logit"))
  mixed_converged <- FALSE
} else {
  mixed_converged <- TRUE
}

cat("\nModel summary:\n")
print(summary(model_mixed))

# Extract odds ratios with 95% CIs
cat("\n\nOdds ratios (exponentiated coefficients):\n")
coef_table <- as.data.frame(summary(model_mixed)$coefficients)
coef_table$OR <- exp(coef_table$Estimate)
coef_table$OR_lower <- exp(coef_table$Estimate - 1.96 * coef_table$`Std. Error`)
coef_table$OR_upper <- exp(coef_table$Estimate + 1.96 * coef_table$`Std. Error`)
coef_table$term <- rownames(coef_table)

print(coef_table[, c("term", "OR", "OR_lower", "OR_upper", "Pr(>|z|)")])

# =============================================================================
# 3. Category-Specific Odds Ratios for Language Effect
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("CATEGORY-SPECIFIC ODDS RATIOS FOR CHINESE vs ENGLISH\n")
cat(rep("-", 80), "\n", sep = "")

categories <- unique(deepseek_en_zh$prompt_category)

category_ors <- map_dfr(categories, function(cat_name) {
  cat_data <- deepseek_en_zh %>% filter(prompt_category == cat_name)

  # Check if there's enough variation
  if (length(unique(cat_data$refused_num)) < 2 ||
      length(unique(cat_data$lang_zh)) < 2) {
    return(tibble(
      category = cat_name,
      or_estimate = NA_real_,
      or_lower = NA_real_,
      or_upper = NA_real_,
      p_value = NA_real_,
      en_refusal = mean(cat_data$refused_num[cat_data$lang_zh == 0]),
      zh_refusal = mean(cat_data$refused_num[cat_data$lang_zh == 1]),
      n = nrow(cat_data),
      note = "Insufficient variation"
    ))
  }

  # Simple logistic regression per category
  cat_model <- tryCatch(
    glm(refused_num ~ lang_zh, data = cat_data, family = binomial),
    error = function(e) NULL
  )

  if (is.null(cat_model)) {
    return(tibble(
      category = cat_name,
      or_estimate = NA_real_,
      or_lower = NA_real_,
      or_upper = NA_real_,
      p_value = NA_real_,
      en_refusal = mean(cat_data$refused_num[cat_data$lang_zh == 0]),
      zh_refusal = mean(cat_data$refused_num[cat_data$lang_zh == 1]),
      n = nrow(cat_data),
      note = "Model failed"
    ))
  }

  coefs <- summary(cat_model)$coefficients
  lang_row <- coefs["lang_zh", ]
  ci <- confint.default(cat_model)["lang_zh", ]

  tibble(
    category = cat_name,
    or_estimate = exp(lang_row["Estimate"]),
    or_lower = exp(ci[1]),
    or_upper = exp(ci[2]),
    p_value = lang_row["Pr(>|z|)"],
    en_refusal = mean(cat_data$refused_num[cat_data$lang_zh == 0]),
    zh_refusal = mean(cat_data$refused_num[cat_data$lang_zh == 1]),
    n = nrow(cat_data),
    note = ""
  )
})

cat("\nCategory-specific odds ratios (Chinese vs English refusal):\n")
print(category_ors %>% arrange(desc(or_estimate)))

write_csv(category_ors, "pipeline/tables/42_deepseek_odds_ratios.csv")
cat("Saved: pipeline/tables/42_deepseek_odds_ratios.csv\n")

# =============================================================================
# 4. Comparison: DeepSeek Chinese vs Other Models' Chinese
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("COMPARISON: DEEPSEEK vs OTHER MODELS IN CHINESE\n")
cat(rep("-", 80), "\n", sep = "")

chinese_data <- data_clean %>%
  filter(prompt_language == "zh") %>%
  mutate(is_deepseek = as.numeric(model == "deepseek-chat-v3.1"))

# Chi-square test: DeepSeek vs all others in Chinese
tbl_ds_vs_others <- table(chinese_data$refused, chinese_data$is_deepseek)
chi_test_ds <- chisq.test(tbl_ds_vs_others)

cat(sprintf("\nChi-square test (DeepSeek vs others in Chinese):\n"))
cat(sprintf("  Chi-sq = %.2f, df = %d, p = %.2e\n",
            chi_test_ds$statistic, chi_test_ds$parameter, chi_test_ds$p.value))

# Refusal rates by model in Chinese
chinese_by_model <- chinese_data %>%
  group_by(model) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  arrange(desc(refusal_rate))

cat("\nRefusal rates in Chinese by model:\n")
print(chinese_by_model)

# =============================================================================
# 5. Figure 22: Category × Language Breakdown for DeepSeek
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("GENERATING FIGURE 22: CATEGORY × LANGUAGE BREAKDOWN\n")
cat(rep("-", 80), "\n", sep = "")

deepseek_all_lang <- data_clean %>%
  filter(model == "deepseek-chat-v3.1",
         prompt_language %in% c("en", "zh"))

viz_data <- deepseek_all_lang %>%
  mutate(
    language_label = ifelse(prompt_language == "en", "English", "Chinese"),
    tier_label = ifelse(controversy_tier == "regular", "Regular", "Boundary")
  ) %>%
  group_by(prompt_category, language_label, tier_label) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    se = sqrt(refusal_rate * (1 - refusal_rate) / n),
    .groups = "drop"
  )

# =============================================================================
# Figures removed 2026-08-02 -- folded into the figure system
# =============================================================================
# fig22 (DeepSeek refusal by topic domain, zh vs en) and fig23 (zh-en gap by
# model) were built before 11_figures.R existed. Both carried in-panel titles
# and subtitles, which the figure system does not permit -- explanation belongs
# in docs/FIGURE_CAPTIONS.md -- and both are now covered by F3 (the home-region
# effect by prompt language) and F6 (the topic-domain gradient).
#
# This script keeps its statistical output: the chi-squared tests, the
# odds-ratio table, and the mixed / fixed-effects models.

# =============================================================================
# 7. Language × Category Interaction Test
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("INTERACTION TEST: LANGUAGE × CATEGORY WITHIN DEEPSEEK\n")
cat(rep("-", 80), "\n", sep = "")

# Compare model with and without interaction
model_main <- glm(refused_num ~ lang_zh + category_f,
                  data = deepseek_en_zh, family = binomial)
model_interact <- glm(refused_num ~ lang_zh * category_f,
                      data = deepseek_en_zh, family = binomial)

anova_result <- anova(model_main, model_interact, test = "Chisq")
cat("\nLikelihood ratio test for language × category interaction:\n")
print(anova_result)

cat(sprintf("\nInteraction model improvement: Deviance = %.2f, df = %d, p = %.4f\n",
            anova_result$Deviance[2], anova_result$Df[2], anova_result$`Pr(>Chi)`[2]))

# =============================================================================
# Summary
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("DEEPSEEK CHINESE DEEP-DIVE COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")

cat("\nKey findings:\n")
cat("  - Tables saved: 41_deepseek_chi_square_tests.csv, 42_deepseek_odds_ratios.csv\n")
cat("\nNext: Run scripts/analyze_deepseek_refusals.py for content analysis\n\n")
