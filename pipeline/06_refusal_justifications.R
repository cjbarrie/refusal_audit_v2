# =============================================================================
# Script 06: Refusal Justifications Analysis
# =============================================================================
# Analyze refusal justifications across models and languages

library(tidyverse)

# Set working directory
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)

# Load clean data
load("pipeline/data_clean.RData")

cat(rep("=", 80), "\n", sep = "")
cat("REFUSAL JUSTIFICATIONS ANALYSIS\n")
cat(rep("=", 80), "\n", sep = "")

# =============================================================================
# Filter to Refusals Only
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("FILTERING TO REFUSALS\n")
cat(rep("-", 80), "\n", sep = "")

# Filter to refusals (engagement_code >= 4)
refusals <- data_clean %>%
  filter(refused) %>%
  mutate(
    refusal_justification_f = factor(
      refusal_justification,
      levels = c("A", "B", "C", "D", "E", "F", "G"),
      labels = c("Neutrality/Balance", "Complexity/Uncertainty",
                 "Harm Avoidance", "Expertise Limitation",
                 "User Autonomy", "No Justification", "Other")
    )
  )

cat(sprintf("Total refusals: %d (%.1f%% of dataset)\n",
            nrow(refusals),
            nrow(refusals) / nrow(data_clean) * 100))

# Check for NA justifications
refusals_with_justification <- refusals %>%
  filter(!is.na(refusal_justification_f))

cat(sprintf("Refusals with coded justifications: %d (%.1f%%)\n",
            nrow(refusals_with_justification),
            nrow(refusals_with_justification) / nrow(refusals) * 100))

# =============================================================================
# ANALYSIS 1: Refusal Justifications by Model
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 1: REFUSAL JUSTIFICATIONS BY MODEL\n")
cat(rep("=", 80), "\n", sep = "")

# Justification distribution by model
justifications_by_model <- refusals_with_justification %>%
  group_by(model_f, refusal_justification_f) %>%
  summarise(n = n(), .groups = "drop") %>%
  group_by(model_f) %>%
  mutate(
    total = sum(n),
    prop = n / total
  ) %>%
  ungroup()

cat("\nRefusal justifications by model:\n")
print(justifications_by_model)

# Save summary
write_csv(justifications_by_model, "pipeline/tables/19_refusal_justifications_by_model.csv")

# Overall justification distribution
justifications_overall <- refusals_with_justification %>%
  group_by(refusal_justification_f) %>%
  summarise(n = n()) %>%
  mutate(prop = n / sum(n)) %>%
  arrange(desc(n))

cat("\nOverall refusal justifications:\n")
print(justifications_overall)

# =============================================================================
# ANALYSIS 2: Refusal Justifications by Model × Language
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 2: REFUSAL JUSTIFICATIONS BY MODEL × LANGUAGE\n")
cat(rep("=", 80), "\n", sep = "")

# Justification distribution by model and language
justifications_by_model_lang <- refusals_with_justification %>%
  group_by(model_f, language_f, refusal_justification_f) %>%
  summarise(n = n(), .groups = "drop") %>%
  group_by(model_f, language_f) %>%
  mutate(
    total = sum(n),
    prop = n / total
  ) %>%
  ungroup()

cat("\nRefusal justifications by model and language:\n")
print(justifications_by_model_lang %>% head(30))

# Save summary
write_csv(justifications_by_model_lang, "pipeline/tables/20_refusal_justifications_by_model_language.csv")

# =============================================================================
# ANALYSIS 3: Most Common Justifications by Model
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 3: MOST COMMON JUSTIFICATIONS BY MODEL\n")
cat(rep("=", 80), "\n", sep = "")

# Find most common justification for each model
most_common_by_model <- justifications_by_model %>%
  group_by(model_f) %>%
  slice_max(prop, n = 1) %>%
  ungroup()

cat("\nMost common justification by model:\n")
print(most_common_by_model)

# =============================================================================
# ANALYSIS 4: Refusal Justifications for Strategic Advice
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 4: REFUSAL JUSTIFICATIONS FOR STRATEGIC ADVICE\n")
cat(rep("=", 80), "\n", sep = "")

# Filter to strategic advice refusals
strategic_refusals <- refusals_with_justification %>%
  filter(prompt_category == "strategic_advice")

cat(sprintf("\nStrategic advice refusals: %d\n", nrow(strategic_refusals)))

if (nrow(strategic_refusals) > 0) {
  strategic_justifications <- strategic_refusals %>%
    group_by(model_f, refusal_justification_f) %>%
    summarise(n = n(), .groups = "drop") %>%
    group_by(model_f) %>%
    mutate(
      total = sum(n),
      prop = n / total
    ) %>%
    ungroup()

  cat("\nRefusal justifications for strategic advice by model:\n")
  print(strategic_justifications)

  # Save summary
  write_csv(strategic_justifications, "pipeline/tables/21_strategic_refusal_justifications.csv")
}

# =============================================================================
# ANALYSIS 5: Refusal Justifications for Controversial Prompts
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 5: REFUSAL JUSTIFICATIONS FOR CONTROVERSIAL PROMPTS\n")
cat(rep("=", 80), "\n", sep = "")

# Filter to controversial (boundary_testing) refusals
controversial_refusals <- refusals_with_justification %>%
  filter(controversy_tier == "boundary_testing")

cat(sprintf("\nControversial prompt refusals: %d\n", nrow(controversial_refusals)))

if (nrow(controversial_refusals) > 0) {
  controversial_justifications <- controversial_refusals %>%
    group_by(model_f, refusal_justification_f) %>%
    summarise(n = n(), .groups = "drop") %>%
    group_by(model_f) %>%
    mutate(
      total = sum(n),
      prop = n / total
    ) %>%
    ungroup()

  cat("\nRefusal justifications for controversial prompts by model:\n")
  print(controversial_justifications)

  # Save summary
  write_csv(controversial_justifications, "pipeline/tables/22_controversial_refusal_justifications.csv")
}

# =============================================================================
# ANALYSIS 6: Refusal Justifications for Domestic Government
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 6: REFUSAL JUSTIFICATIONS FOR DOMESTIC GOVERNMENT\n")
cat(rep("=", 80), "\n", sep = "")

# Filter to domestic_government refusals
domestic_refusals <- refusals_with_justification %>%
  filter(prompt_category == "domestic_government")

cat(sprintf("\nDomestic government refusals: %d\n", nrow(domestic_refusals)))

if (nrow(domestic_refusals) > 0) {
  domestic_justifications <- domestic_refusals %>%
    group_by(model_f, refusal_justification_f) %>%
    summarise(n = n(), .groups = "drop") %>%
    group_by(model_f) %>%
    mutate(
      total = sum(n),
      prop = n / total
    ) %>%
    ungroup()

  cat("\nRefusal justifications for domestic government prompts by model:\n")
  print(domestic_justifications)

  # Save summary
  write_csv(domestic_justifications, "pipeline/tables/23_domestic_refusal_justifications.csv")
}

# =============================================================================
# Summary Statistics
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("SUMMARY STATISTICS\n")
cat(rep("=", 80), "\n", sep = "")

summary_stats <- list(
  total_refusals = nrow(refusals),
  refusals_with_justification = nrow(refusals_with_justification),
  strategic_refusals = nrow(strategic_refusals),
  controversial_refusals = nrow(controversial_refusals),
  domestic_refusals = nrow(domestic_refusals),
  refusal_pct = nrow(refusals) / nrow(data_clean)
)

cat("\nKey Statistics:\n")
for (name in names(summary_stats)) {
  cat(sprintf("  %s: %.0f\n", name, summary_stats[[name]]))
}

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("REFUSAL JUSTIFICATIONS ANALYSIS COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
cat("\nNext: Run 11_visualizations.R\n\n")
