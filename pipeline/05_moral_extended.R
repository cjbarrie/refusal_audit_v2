# =============================================================================
# Script 05: Extended Moral Foundations Analysis
# =============================================================================
# Analyzes moral foundations by language × category and co-occurrence patterns
# Requires: data_clean.RData from 01_data_loading.R

library(tidyverse)

# Set working directory
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)

cat(rep("=", 80), "\n", sep = "")
cat("EXTENDED MORAL FOUNDATIONS ANALYSIS\n")
cat(rep("=", 80), "\n", sep = "")

# Load data
load("pipeline/data_clean.RData")

# Filter to engaged responses with complete moral foundation data
data_moral <- data_clean %>%
  filter(
    engaged,
    !is.na(care_harm),
    !is.na(fairness_cheating),
    !is.na(loyalty_betrayal),
    !is.na(authority_subversion),
    !is.na(sanctity_degradation),
    !is.na(liberty_oppression)
  )

cat(sprintf("\nEngaged responses with complete moral data: %d\n", nrow(data_moral)))

# =============================================================================
# ANALYSIS 1: Moral Foundations by Language × Category
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 1: MORAL FOUNDATIONS BY LANGUAGE × CATEGORY\n")
cat(rep("=", 80), "\n", sep = "")

# Reshape to long format
moral_long <- data_moral %>%
  select(prompt_id, model_f, language_f, prompt_category, dataset_type_f,
         care_harm, fairness_cheating, loyalty_betrayal,
         authority_subversion, sanctity_degradation, liberty_oppression) %>%
  pivot_longer(
    cols = c(care_harm, fairness_cheating, loyalty_betrayal,
             authority_subversion, sanctity_degradation, liberty_oppression),
    names_to = "foundation",
    values_to = "present"
  ) %>%
  mutate(
    foundation_f = factor(
      foundation,
      levels = c("care_harm", "fairness_cheating", "loyalty_betrayal",
                 "authority_subversion", "sanctity_degradation", "liberty_oppression"),
      labels = c("Care/Harm", "Fairness/Cheating", "Loyalty/Betrayal",
                 "Authority/Subversion", "Sanctity/Degradation", "Liberty/Oppression")
    ),
    present_numeric = as.numeric(present)
  )

# Calculate activation rates by language × category
moral_lang_cat <- moral_long %>%
  group_by(language_f, prompt_category, foundation_f) %>%
  summarise(
    n = n(),
    activation_rate = mean(present_numeric, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  arrange(foundation_f, language_f, prompt_category)

cat("\nMoral foundation activation by language and category (first 30 rows):\n")
print(head(moral_lang_cat, 30))

write_csv(moral_lang_cat, "pipeline/tables/29_moral_by_language_category.csv")
cat("\nSaved: pipeline/tables/29_moral_by_language_category.csv\n")

# Calculate by model × language × category
moral_model_lang_cat <- moral_long %>%
  group_by(model_f, language_f, prompt_category, foundation_f) %>%
  summarise(
    n = n(),
    activation_rate = mean(present_numeric, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  arrange(model_f, foundation_f, language_f, prompt_category)

cat("\nMoral foundation activation by model, language, and category (first 30 rows):\n")
print(head(moral_model_lang_cat, 30))

write_csv(moral_model_lang_cat, "pipeline/tables/30_moral_model_lang_cat.csv")
cat("\nSaved: pipeline/tables/30_moral_model_lang_cat.csv\n")

# =============================================================================
# ANALYSIS 2: Foundation Co-occurrence Patterns
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 2: FOUNDATION CO-OCCURRENCE PATTERNS\n")
cat(rep("=", 80), "\n", sep = "")

# Create co-occurrence matrix
foundations <- c("care_harm", "fairness_cheating", "loyalty_betrayal",
                 "authority_subversion", "sanctity_degradation", "liberty_oppression")

# Calculate pairwise co-occurrence
co_occurrence <- expand.grid(
  foundation1 = foundations,
  foundation2 = foundations,
  stringsAsFactors = FALSE
) %>%
  filter(foundation1 < foundation2) %>%  # Only upper triangle
  rowwise() %>%
  mutate(
    both_present = sum(data_moral[[foundation1]] == 1 & data_moral[[foundation2]] == 1),
    either_present = sum(data_moral[[foundation1]] == 1 | data_moral[[foundation2]] == 1),
    co_occurrence_rate = both_present / nrow(data_moral),
    conditional_prob = both_present / sum(data_moral[[foundation1]] == 1)
  ) %>%
  ungroup() %>%
  arrange(desc(co_occurrence_rate))

cat("\nFoundation co-occurrence (sorted by rate):\n")
print(co_occurrence)

write_csv(co_occurrence, "pipeline/tables/31_foundation_cooccurrence.csv")
cat("\nSaved: pipeline/tables/31_foundation_cooccurrence.csv\n")

# Calculate by model (using a different approach to avoid nested data issues)
co_occurrence_by_model <- data.frame()

for (mod in unique(data_moral$model_f)) {
  model_data <- data_moral %>% filter(model_f == mod)

  for (i in 1:(length(foundations)-1)) {
    for (j in (i+1):length(foundations)) {
      f1 <- foundations[i]
      f2 <- foundations[j]

      both_present <- sum(model_data[[f1]] == 1 & model_data[[f2]] == 1)
      either_present <- sum(model_data[[f1]] == 1 | model_data[[f2]] == 1)

      co_occurrence_by_model <- bind_rows(
        co_occurrence_by_model,
        data.frame(
          model = as.character(mod),
          foundation1 = f1,
          foundation2 = f2,
          both_present = both_present,
          either_present = either_present,
          n_responses = nrow(model_data),
          co_occurrence_rate = both_present / nrow(model_data)
        )
      )
    }
  }
}

co_occurrence_by_model <- co_occurrence_by_model %>%
  arrange(model, desc(co_occurrence_rate))

cat("\nFoundation co-occurrence by model (first 20 rows):\n")
print(head(co_occurrence_by_model, 20))

write_csv(co_occurrence_by_model, "pipeline/tables/32_cooccurrence_by_model.csv")
cat("\nSaved: pipeline/tables/32_cooccurrence_by_model.csv\n")

# =============================================================================
# ANALYSIS 3: Foundation Combinations (Total Count)
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 3: FOUNDATION COMBINATION PATTERNS\n")
cat(rep("=", 80), "\n", sep = "")

# Calculate total number of foundations invoked per response
data_moral <- data_moral %>%
  mutate(
    total_foundations = care_harm + fairness_cheating + loyalty_betrayal +
                       authority_subversion + sanctity_degradation + liberty_oppression
  )

# Distribution of total foundations
foundation_count_dist <- data_moral %>%
  group_by(model_f, total_foundations) %>%
  summarise(
    n = n(),
    .groups = "drop"
  ) %>%
  group_by(model_f) %>%
  mutate(
    total = sum(n),
    pct = n / total
  ) %>%
  arrange(model_f, total_foundations)

cat("\nDistribution of total foundations invoked:\n")
print(foundation_count_dist)

write_csv(foundation_count_dist, "pipeline/tables/33_foundation_count_distribution.csv")
cat("\nSaved: pipeline/tables/33_foundation_count_distribution.csv\n")

# Mean foundations by category
foundation_count_category <- data_moral %>%
  group_by(prompt_category, model_f) %>%
  summarise(
    n = n(),
    mean_foundations = mean(total_foundations, na.rm = TRUE),
    sd_foundations = sd(total_foundations, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  arrange(desc(mean_foundations))

cat("\nMean foundations by category and model:\n")
print(foundation_count_category)

write_csv(foundation_count_category, "pipeline/tables/34_mean_foundations_by_category.csv")
cat("\nSaved: pipeline/tables/34_mean_foundations_by_category.csv\n")

# =============================================================================
# Summary Statistics
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("SUMMARY STATISTICS\n")
cat(rep("=", 80), "\n", sep = "")

# Key statistics
summary_stats <- list(
  total_responses = nrow(data_moral),
  mean_foundations = mean(data_moral$total_foundations, na.rm = TRUE),
  most_common_pair = co_occurrence$foundation1[1],
  most_common_pair2 = co_occurrence$foundation2[1],
  highest_cooccurrence = co_occurrence$co_occurrence_rate[1],
  mean_cooccurrence = mean(co_occurrence$co_occurrence_rate)
)

cat("\nKey Statistics:\n")
cat(sprintf("  Total responses: %d\n", summary_stats$total_responses))
cat(sprintf("  Mean foundations per response: %.2f\n", summary_stats$mean_foundations))
cat(sprintf("  Most common pair: %s + %s (%.1f%%)\n",
            summary_stats$most_common_pair,
            summary_stats$most_common_pair2,
            summary_stats$highest_cooccurrence * 100))
cat(sprintf("  Mean co-occurrence rate: %.2f%%\n",
            summary_stats$mean_cooccurrence * 100))

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("EXTENDED MORAL FOUNDATIONS ANALYSIS COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
cat("\nNext: Run 12_visualizations_extended.R\n\n")
