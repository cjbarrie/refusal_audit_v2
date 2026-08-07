#!/usr/bin/env Rscript
# =============================================================================
# Script 07: DeepSeek Language Analysis (Chinese vs English)
# =============================================================================
# Investigates why DeepSeek refuses MORE in Chinese (29.5%) than English (24.2%)
# Creates tables 35-38 and figure 19

library(tidyverse)
library(scales)

# Set working directory
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes

cat(rep("=", 80), "\n", sep = "")
cat("DEEPSEEK LANGUAGE ANALYSIS\n")
cat(rep("=", 80), "\n", sep = "")

# Load data
load("pipeline/data_clean.RData")

# Filter to DeepSeek only
deepseek <- data_clean %>% filter(model == "deepseek-chat-v3.1")

cat("\nTotal DeepSeek responses:", nrow(deepseek), "\n")
cat("English responses:", sum(deepseek$response_language == "en"), "\n")
cat("Chinese responses:", sum(deepseek$response_language == "zh"), "\n")

# =============================================================================
# Table 35: Refusal by language × category × dataset_type
# =============================================================================

cat("\nGenerating Table 35: Refusal by Language × Category × Dataset Type...\n")

t35 <- deepseek %>%
  group_by(response_language, category, dataset_type) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  arrange(response_language, category, dataset_type)

write_csv(t35, "pipeline/tables/35_deepseek_refusal_by_language_category.csv")
cat("Saved: pipeline/tables/35_deepseek_refusal_by_language_category.csv\n")

# =============================================================================
# Table 36: Engagement distribution by language
# =============================================================================

cat("\nGenerating Table 36: Engagement Distribution by Language...\n")

t36 <- deepseek %>%
  group_by(response_language, engagement_code) %>%
  summarise(n = n(), .groups = "drop") %>%
  group_by(response_language) %>%
  mutate(pct = n / sum(n))

write_csv(t36, "pipeline/tables/36_deepseek_engagement_distribution.csv")
cat("Saved: pipeline/tables/36_deepseek_engagement_distribution.csv\n")

# =============================================================================
# Table 37: Ideology by language (engaged only)  -- PASS-2 ONLY
# =============================================================================
# Pass 2 covers a 25% ISSUE SUBSAMPLE, not the whole run
# (docs/SLANT_SUBSAMPLE.md), so the ideology columns are NA for most rows. The
# table is guarded on the columns carrying any data at all, so it also skips
# cleanly on a Pass-1-only run. Tables 35, 36, 38 and figure 19 are Pass 1 and
# always run.
#
# `filter(has_slant)` is load-bearing: without it `n = n()` would count every
# engaged response while the means were computed over the subsample alone via
# na.rm, reporting an `n` roughly four times the number of observations the
# estimates actually rest on.

if (all(is.na(deepseek$economic_left_right))) {
  cat("\nSKIP Table 37 (ideology): Pass 2 not present in this run.\n")
} else {
  cat("\nGenerating Table 37: Ideology by Language (engaged, slant subsample)...\n")

  t37 <- deepseek %>%
    filter(engaged, has_slant) %>%
    group_by(response_language) %>%
    summarise(
      n = n(),
      economic_mean = mean(economic_left_right, na.rm = TRUE),
      economic_sd = sd(economic_left_right, na.rm = TRUE),
      social_mean = mean(social_left_right, na.rm = TRUE),
      social_sd = sd(social_left_right, na.rm = TRUE),
      auth_lib_mean = mean(authoritarian_libertarian, na.rm = TRUE),
      auth_lib_sd = sd(authoritarian_libertarian, na.rm = TRUE),
      pop_elite_mean = mean(populist_elitist, na.rm = TRUE),
      pop_elite_sd = sd(populist_elitist, na.rm = TRUE)
    )

  write_csv(t37, "pipeline/tables/37_deepseek_ideology_by_language.csv")
  cat("Saved: pipeline/tables/37_deepseek_ideology_by_language.csv\n")
}

# =============================================================================
# Table 38: Justifications by language
# =============================================================================

cat("\nGenerating Table 38: Refusal Justifications by Language...\n")

t38 <- deepseek %>%
  filter(refused) %>%
  group_by(response_language, refusal_justification) %>%
  summarise(n = n(), .groups = "drop") %>%
  group_by(response_language) %>%
  mutate(pct = n / sum(n)) %>%
  arrange(response_language, desc(n))

write_csv(t38, "pipeline/tables/38_deepseek_justifications_by_language.csv")
cat("Saved: pipeline/tables/38_deepseek_justifications_by_language.csv\n")

# =============================================================================
# Figure 19 REMOVED 2026-08-02 -- superseded by figure 22
# =============================================================================
# It plotted exactly the data in fig22 (DeepSeek, topic domain, zh vs en, split
# by tier) but as bars on a 0-100% axis for a 43% maximum, categories in
# alphabetical rather than substantive order, a detached legend, and no
# uncertainty. fig22 in 43_appendix_deepseek_chinese.R shows the same comparison
# as estimates with Wilson intervals, ordered by the size of the gap.
# This script keeps tables 35, 36 and 38.

# =============================================================================
# Summary Statistics
# =============================================================================

cat("\n", rep("=", 80), "\n", sep = "")
cat("SUMMARY STATISTICS\n")
cat(rep("=", 80), "\n", sep = "")

# Overall refusal by language
overall_refusal <- deepseek %>%
  group_by(response_language) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused)
  )

cat("\nOverall Refusal Rates:\n")
print(overall_refusal)

# Language gap
eng_rate <- overall_refusal$refusal_rate[overall_refusal$response_language == "en"]
chi_rate <- overall_refusal$refusal_rate[overall_refusal$response_language == "zh"]
gap <- chi_rate - eng_rate

cat(sprintf("\nLanguage Gap: %.1f%% (Chinese) - %.1f%% (English) = %.1f percentage points\n",
            chi_rate * 100, eng_rate * 100, gap * 100))

cat("\n", rep("=", 80), "\n", sep = "")
cat("DEEPSEEK LANGUAGE ANALYSIS COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
