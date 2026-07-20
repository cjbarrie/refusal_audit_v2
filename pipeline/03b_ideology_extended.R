# =============================================================================
# Script 03b: Extended Ideology Analysis
# =============================================================================
# Analyzes ideology consistency across categories and base vs boundary prompts
# Requires: data_clean.RData from 01_data_loading.R

library(tidyverse)
library(lme4)

# Set working directory
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)

cat(rep("=", 80), "\n", sep = "")
cat("EXTENDED IDEOLOGY ANALYSIS\n")
cat(rep("=", 80), "\n", sep = "")

# Load data
load("pipeline/data_clean.RData")

# Filter to engaged responses only
data_engaged <- data_clean %>%
  filter(engaged)

cat(sprintf("\nEngaged responses: %d\n", nrow(data_engaged)))

# =============================================================================
# ANALYSIS 1: Category-level ideology consistency
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 1: IDEOLOGY CONSISTENCY ACROSS CATEGORIES\n")
cat(rep("=", 80), "\n", sep = "")

# Reshape to long format for ideology dimensions
ideology_long <- data_engaged %>%
  select(prompt_id, model_f, language_f, prompt_category, dataset_type_f,
         economic_left_right, social_left_right,
         authoritarian_libertarian, populist_elitist) %>%
  pivot_longer(
    cols = c(economic_left_right, social_left_right,
             authoritarian_libertarian, populist_elitist),
    names_to = "dimension",
    values_to = "score"
  ) %>%
  filter(!is.na(score)) %>%
  mutate(
    dimension_f = factor(
      dimension,
      levels = c("economic_left_right", "social_left_right",
                 "authoritarian_libertarian", "populist_elitist"),
      labels = c("Economic L-R", "Social L-R",
                 "Authoritarian-Libertarian", "Populist-Elitist")
    )
  )

# Calculate ideology by model × category
ideology_by_category <- ideology_long %>%
  group_by(model_f, prompt_category, dimension_f) %>%
  summarise(
    n = n(),
    mean_score = mean(score, na.rm = TRUE),
    sd_score = sd(score, na.rm = TRUE),
    se_score = sd_score / sqrt(n),
    .groups = "drop"
  ) %>%
  arrange(model_f, dimension_f, prompt_category)

cat("\nIdeology by model and category (first 20 rows):\n")
print(head(ideology_by_category, 20))

write_csv(ideology_by_category, "pipeline/tables/24_ideology_by_model_category.csv")
cat("\nSaved: pipeline/tables/24_ideology_by_model_category.csv\n")

# Calculate consistency metrics (within-model variance across categories)
ideology_consistency <- ideology_long %>%
  group_by(model_f, dimension_f) %>%
  summarise(
    # Calculate SD of category means
    n_categories = n_distinct(prompt_category),
    category_mean_sd = sd(tapply(score, prompt_category, mean, na.rm = TRUE)),
    overall_mean = mean(score, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  arrange(dimension_f, category_mean_sd)

cat("\nIdeology consistency (lower SD = more consistent):\n")
print(ideology_consistency)

write_csv(ideology_consistency, "pipeline/tables/25_ideology_consistency.csv")
cat("\nSaved: pipeline/tables/25_ideology_consistency.csv\n")

# =============================================================================
# ANALYSIS 2: Base vs Boundary Ideology Comparison
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 2: IDEOLOGY SHIFTS (BASE vs BOUNDARY)\n")
cat(rep("=", 80), "\n", sep = "")

# Compare ideology by dataset type
ideology_by_dataset <- ideology_long %>%
  group_by(model_f, dataset_type_f, dimension_f) %>%
  summarise(
    n = n(),
    mean_score = mean(score, na.rm = TRUE),
    sd_score = sd(score, na.rm = TRUE),
    se_score = sd_score / sqrt(n),
    .groups = "drop"
  ) %>%
  arrange(model_f, dimension_f, dataset_type_f)

cat("\nIdeology by model and dataset type:\n")
print(ideology_by_dataset)

write_csv(ideology_by_dataset, "pipeline/tables/26_ideology_by_dataset_type.csv")
cat("\nSaved: pipeline/tables/26_ideology_by_dataset_type.csv\n")

# Calculate shifts (boundary - base)
ideology_shifts <- ideology_by_dataset %>%
  select(model_f, dimension_f, dataset_type_f, mean_score) %>%
  pivot_wider(names_from = dataset_type_f, values_from = mean_score) %>%
  mutate(
    shift = `Boundary Prompts` - `Regular Prompts`,
    shift_direction = case_when(
      shift > 0.1 ~ "Right/Authoritarian/Elitist",
      shift < -0.1 ~ "Left/Libertarian/Populist",
      TRUE ~ "No shift"
    )
  ) %>%
  arrange(desc(abs(shift)))

cat("\nIdeology shifts (Boundary - Base):\n")
print(ideology_shifts)

write_csv(ideology_shifts, "pipeline/tables/27_ideology_shifts.csv")
cat("\nSaved: pipeline/tables/27_ideology_shifts.csv\n")

# =============================================================================
# ANALYSIS 3: Detailed category × dataset type breakdown
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 3: CATEGORY × DATASET TYPE BREAKDOWN\n")
cat(rep("=", 80), "\n", sep = "")

ideology_category_dataset <- ideology_long %>%
  group_by(model_f, prompt_category, dataset_type_f, dimension_f) %>%
  summarise(
    n = n(),
    mean_score = mean(score, na.rm = TRUE),
    sd_score = sd(score, na.rm = TRUE),
    .groups = "drop"
  ) %>%
  arrange(model_f, dimension_f, prompt_category, dataset_type_f)

cat("\nIdeology by model, category, and dataset type (first 30 rows):\n")
print(head(ideology_category_dataset, 30))

write_csv(ideology_category_dataset, "pipeline/tables/28_ideology_category_dataset.csv")
cat("\nSaved: pipeline/tables/28_ideology_category_dataset.csv\n")

# =============================================================================
# Summary Statistics
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("SUMMARY STATISTICS\n")
cat(rep("=", 80), "\n", sep = "")

# Key statistics
summary_stats <- list(
  total_engaged = nrow(data_engaged),
  ideology_complete = sum(!is.na(data_engaged$economic_left_right)),
  mean_consistency_sd = mean(ideology_consistency$category_mean_sd),
  max_shift = max(abs(ideology_shifts$shift)),
  n_large_shifts = sum(abs(ideology_shifts$shift) > 0.2)
)

cat("\nKey Statistics:\n")
for (name in names(summary_stats)) {
  cat(sprintf("  %s: %.3f\n", name, summary_stats[[name]]))
}

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("EXTENDED IDEOLOGY ANALYSIS COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
cat("\nNext: Run 03c_moral_extended.R\n\n")
