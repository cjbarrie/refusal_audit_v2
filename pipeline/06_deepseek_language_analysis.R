#!/usr/bin/env Rscript
# =============================================================================
# Script 06: DeepSeek Language Analysis (Chinese vs English)
# =============================================================================
# Investigates why DeepSeek refuses MORE in Chinese (29.5%) than English (24.2%)
# Creates tables 35-38 and figure 19

library(tidyverse)
library(scales)

# Set working directory
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)

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
# Table 37: Ideology by language (engaged only)
# =============================================================================

cat("\nGenerating Table 37: Ideology by Language (Engaged Only)...\n")

t37 <- deepseek %>%
  filter(engaged) %>%
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
# Figure 19: DeepSeek Refusal Rates (Chinese vs English)
# =============================================================================

cat("\nGenerating Figure 19: DeepSeek Language Patterns...\n")

# Prepare data for visualization
viz_data <- deepseek %>%
  filter(response_language %in% c("en", "zh")) %>%
  mutate(language_label = ifelse(response_language == "en", "English", "Chinese")) %>%
  group_by(language_label, category, dataset_type_f) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  )

fig19 <- ggplot(viz_data, aes(x = category, y = refusal_rate, fill = language_label)) +
  geom_col(position = "dodge", width = 0.7) +
  geom_text(aes(label = percent(refusal_rate, accuracy = 1)),
            position = position_dodge(width = 0.7),
            vjust = -0.3, size = 2.5) +
  facet_wrap(~dataset_type_f, ncol = 1) +
  scale_fill_manual(values = c("English" = "#377EB8", "Chinese" = "#E41A1C")) +
  scale_y_continuous(labels = percent, limits = c(0, 1.05)) +
  labs(
    title = "DeepSeek Refusal Rates: Chinese vs English",
    subtitle = "Higher refusal rates in Chinese suggest more extensive post-training",
    x = "Category",
    y = "Refusal Rate",
    fill = "Language"
  ) +
  theme_bw() +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1, size = 9),
    legend.position = "top",
    panel.grid.minor = element_blank(),
    plot.title = element_text(face = "bold", size = 14)
  )

ggsave("pipeline/figures/fig19_deepseek_language_patterns.pdf", fig19, width = 12, height = 6)
cat("Saved: pipeline/figures/fig19_deepseek_language_patterns.pdf\n")

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
