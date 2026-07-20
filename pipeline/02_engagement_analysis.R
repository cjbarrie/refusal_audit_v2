# =============================================================================
# Script 02: Engagement Analysis
# =============================================================================
# Analyze engagement patterns across models and languages
# Focus on DeepSeek's Chinese language effect

library(tidyverse)
library(lme4)
library(ggeffects)

# Set working directory
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)

# Load clean data
load("pipeline/data_clean.RData")

cat(rep("=", 80), "\n", sep = "")
cat("ENGAGEMENT ANALYSIS\n")
cat(rep("=", 80), "\n", sep = "")

# =============================================================================
# Model × Language Engagement Patterns
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("MODEL × LANGUAGE ENGAGEMENT PATTERNS\n")
cat(rep("-", 80), "\n", sep = "")

# Summary by model and language
model_language_summary <- data_clean %>%
  group_by(model_f, language_f) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  arrange(model_f, desc(engagement_rate))

print(model_language_summary)

# Save summary
write_csv(model_language_summary, "pipeline/tables/01_model_language_engagement.csv")

# =============================================================================
# FINDING 1: DeepSeek's Chinese Language Effect
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("FINDING 1: DEEPSEEK'S CHINESE LANGUAGE EFFECT\n")
cat(rep("=", 80), "\n", sep = "")

# Filter DeepSeek data
deepseek_data <- data_clean %>%
  filter(model == "deepseek-chat-v3.1")

# Engagement by language
deepseek_by_lang <- deepseek_data %>%
  group_by(language_f) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  arrange(desc(engagement_rate))

cat("\nDeepSeek engagement by language:\n")
print(deepseek_by_lang)

# Calculate English vs Chinese gap
deepseek_en_zh <- deepseek_by_lang %>%
  filter(language_f %in% c("English", "Chinese"))

if (nrow(deepseek_en_zh) == 2) {
  en_rate <- deepseek_en_zh$engagement_rate[deepseek_en_zh$language_f == "English"]
  zh_rate <- deepseek_en_zh$engagement_rate[deepseek_en_zh$language_f == "Chinese"]
  gap <- en_rate - zh_rate

  cat(sprintf("\n*** KEY FINDING ***\n"))
  cat(sprintf("DeepSeek engages %.1f%% in English vs %.1f%% in Chinese\n",
              en_rate * 100, zh_rate * 100))
  cat(sprintf("Gap: %.1f percentage points HIGHER engagement in English\n", gap * 100))
  cat(sprintf("This is opposite of what you'd expect from a Chinese model!\n"))
}

# Save DeepSeek language summary
write_csv(deepseek_by_lang, "pipeline/tables/02_deepseek_language.csv")

# =============================================================================
# Statistical Model: Language × Model Interaction
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("STATISTICAL MODEL: LANGUAGE × MODEL INTERACTION\n")
cat(rep("-", 80), "\n", sep = "")

# Fit logistic regression with interaction
# Convert engaged to numeric (0/1) for glm
# Use factor versions of predictors for ggeffects compatibility
data_clean$engaged_numeric <- as.numeric(data_clean$engaged)

model_interaction <- glm(
  engaged_numeric ~ language_f * model_f,
  data = data_clean,
  family = binomial(link = "logit")
)

cat("\nModel summary:\n")
print(summary(model_interaction))

# Get predicted probabilities using ggeffects
cat("\nGenerating predicted engagement rates...\n")
predictions <- ggpredict(model_interaction, terms = c("language_f", "model_f"))

cat("\nPredicted engagement rates by language and model:\n")
print(predictions)

# Convert to data frame for saving
predictions_df <- as.data.frame(predictions)
write_csv(predictions_df, "pipeline/tables/03_predicted_engagement.csv")

# =============================================================================
# Category-Specific Refusal Rates
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("CATEGORY-SPECIFIC REFUSAL RATES\n")
cat(rep("-", 80), "\n", sep = "")

# Overall by category
category_refusal <- data_clean %>%
  group_by(prompt_category) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  arrange(refusal_rate)

cat("\nRefusal rates by category:\n")
print(category_refusal)

# Category by model
category_model <- data_clean %>%
  group_by(prompt_category, model_f) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  arrange(prompt_category, desc(engagement_rate))

cat("\nRefusal rates by category and model:\n")
print(category_model)

# Save summaries
write_csv(category_refusal, "pipeline/tables/04_category_refusal.csv")
write_csv(category_model, "pipeline/tables/05_category_model_refusal.csv")

# =============================================================================
# FINDING 2: Strategic Advice Has Highest Refusal Rate
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("FINDING 2: HIGHEST-REFUSAL TOPIC DOMAIN\n")
cat(rep("=", 80), "\n", sep = "")

# Topic-domain scheme (v2): report the domain with the lowest engagement /
# highest refusal that is actually present in this run, rather than the
# legacy hardcoded "strategic_advice" task-type category.
overall_rate <- mean(data_clean$engaged)
top_refusal_domain <- category_refusal %>% arrange(engagement_rate) %>% slice(1)
strategic_category <- top_refusal_domain$prompt_category
strategic_rate <- top_refusal_domain$engagement_rate

cat(sprintf("\nHighest-refusal domain: %s\n", strategic_category))
cat(sprintf("  engagement in that domain: %.1f%%\n", strategic_rate * 100))
cat(sprintf("Overall engagement: %.1f%%\n", overall_rate * 100))
cat(sprintf("Gap: %.1f percentage points LOWER than overall\n",
            (overall_rate - strategic_rate) * 100))

# That domain, broken out by model
strategic_by_model <- data_clean %>%
  filter(prompt_category == strategic_category) %>%
  group_by(model_f) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  arrange(desc(engagement_rate))

cat(sprintf("\n'%s' engagement by model:\n", strategic_category))
print(strategic_by_model)

# =============================================================================
# FINDING 3: Controversial (Boundary Testing) Prompts
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("FINDING 3: CONTROVERSIAL (BOUNDARY TESTING) PROMPTS\n")
cat(rep("=", 80), "\n", sep = "")

# Filter controversial prompts
controversial_data <- data_clean %>%
  filter(controversy_tier == "boundary_testing")

cat(sprintf("\nTotal controversial prompts: %d (%.1f%% of dataset)\n",
            nrow(controversial_data),
            nrow(controversial_data) / nrow(data_clean) * 100))

# Overall controversial engagement
controversial_overall <- controversial_data %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused)
  )

regular_overall <- data_clean %>%
  filter(controversy_tier == "regular") %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused)
  )

cat(sprintf("\nControversial prompts engagement: %.1f%%\n",
            controversial_overall$engagement_rate * 100))
cat(sprintf("Regular prompts engagement: %.1f%%\n",
            regular_overall$engagement_rate * 100))
cat(sprintf("Gap: %.1f percentage points LOWER for controversial\n",
            (regular_overall$engagement_rate - controversial_overall$engagement_rate) * 100))

# Controversial by model
controversial_by_model <- controversial_data %>%
  group_by(model_f) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  arrange(desc(engagement_rate))

cat("\nControversial prompts by model:\n")
print(controversial_by_model)

# Controversial by model and language
controversial_by_model_lang <- controversial_data %>%
  group_by(model_f, language_f) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  arrange(model_f, desc(engagement_rate))

cat("\nControversial prompts by model and language:\n")
print(controversial_by_model_lang)

# Save summaries
write_csv(controversial_by_model, "pipeline/tables/07_controversial_by_model.csv")
write_csv(controversial_by_model_lang, "pipeline/tables/08_controversial_by_model_language.csv")

# =============================================================================
# FINDING 4: Domestic Government Category
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("FINDING 4: DOMESTIC GOVERNMENT CATEGORY\n")
cat(rep("=", 80), "\n", sep = "")

# Filter domestic government prompts
domestic_data <- data_clean %>%
  filter(prompt_category == "domestic_government")

cat(sprintf("\nTotal domestic_government prompts: %d (%.1f%% of dataset)\n",
            nrow(domestic_data),
            nrow(domestic_data) / nrow(data_clean) * 100))

# Overall domestic engagement
domestic_overall <- domestic_data %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused)
  )

overall_rate <- mean(data_clean$engaged)

cat(sprintf("\nDomestic government engagement: %.1f%%\n",
            domestic_overall$engagement_rate * 100))
cat(sprintf("Overall engagement: %.1f%%\n", overall_rate * 100))
cat(sprintf("Gap: %.1f percentage points LOWER for domestic_government\n",
            (overall_rate - domestic_overall$engagement_rate) * 100))

# Domestic by model
domestic_by_model <- domestic_data %>%
  group_by(model_f) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  arrange(desc(engagement_rate))

cat("\nDomestic government by model:\n")
print(domestic_by_model)

# Domestic by model and language
domestic_by_model_lang <- domestic_data %>%
  group_by(model_f, language_f) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  arrange(model_f, desc(engagement_rate))

cat("\nDomestic government by model and language:\n")
print(domestic_by_model_lang)

# Save summaries
write_csv(domestic_by_model, "pipeline/tables/09_domestic_by_model.csv")
write_csv(domestic_by_model_lang, "pipeline/tables/10_domestic_by_model_language.csv")

# =============================================================================
# Cross-Language Consistency
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("CROSS-LANGUAGE CONSISTENCY\n")
cat(rep("-", 80), "\n", sep = "")

# For each prompt, check engagement across languages
prompt_consistency <- data_clean %>%
  group_by(prompt_id, model) %>%
  summarise(
    n_languages = n(),
    engagement_rate = mean(engaged),
    languages_engaged = sum(engaged),
    .groups = "drop"
  ) %>%
  mutate(
    consistency = case_when(
      languages_engaged == 0 ~ "Refused in all languages",
      languages_engaged == n_languages ~ "Engaged in all languages",
      TRUE ~ "Mixed engagement"
    )
  )

consistency_summary <- prompt_consistency %>%
  group_by(consistency) %>%
  summarise(
    n_prompts = n(),
    .groups = "drop"
  ) %>%
  mutate(pct = n_prompts / sum(n_prompts) * 100)

cat("\nPrompt consistency across languages:\n")
print(consistency_summary)

# Most inconsistent prompts
inconsistent_prompts <- prompt_consistency %>%
  filter(consistency == "Mixed engagement") %>%
  arrange(engagement_rate)

cat(sprintf("\nFound %d prompts with mixed engagement across languages\n",
            nrow(inconsistent_prompts)))

# =============================================================================
# Summary Statistics for Report
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("SUMMARY STATISTICS\n")
cat(rep("=", 80), "\n", sep = "")

summary_stats <- list(
  overall_engagement = mean(data_clean$engaged),
  overall_refusal = mean(data_clean$refused),
  deepseek_en_engagement = en_rate,
  deepseek_zh_engagement = zh_rate,
  deepseek_gap = gap,
  top_refusal_domain_engagement = strategic_rate,
  top_refusal_domain_gap = overall_rate - strategic_rate
)

cat("\nKey Statistics:\n")
for (name in names(summary_stats)) {
  cat(sprintf("  %s: %.3f\n", name, summary_stats[[name]]))
}

# Save summary stats
summary_df <- data.frame(
  statistic = names(summary_stats),
  value = unlist(summary_stats)
)
write_csv(summary_df, "pipeline/tables/06_summary_statistics.csv")

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ENGAGEMENT ANALYSIS COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
cat("\nNext: Run 03_ideology_analysis.R\n\n")
