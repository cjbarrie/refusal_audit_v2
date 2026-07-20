# =============================================================================
# Script 03: Ideology and Moral Foundations Analysis
# =============================================================================
# Analyze ideological positioning and moral foundations in engaged responses
# Focus on cross-model and cross-language patterns

library(tidyverse)
library(lme4)
library(ggeffects)

# Set working directory
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)

# Load clean data
load("pipeline/data_clean.RData")

cat(rep("=", 80), "\n", sep = "")
cat("IDEOLOGY AND MORAL FOUNDATIONS ANALYSIS\n")
cat(rep("=", 80), "\n", sep = "")

# =============================================================================
# Filter to Engaged Responses Only
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("FILTERING TO ENGAGED RESPONSES\n")
cat(rep("-", 80), "\n", sep = "")

# Filter to engaged responses (codes 1-3)
engaged_data <- data_clean %>% filter(engaged)

cat(sprintf("Total engaged responses: %d (%.1f%% of dataset)\n",
            nrow(engaged_data),
            nrow(engaged_data) / nrow(data_clean) * 100))

# Check for NA ideology scores
ideology_complete <- engaged_data %>%
  filter(!is.na(economic_left_right),
         !is.na(social_left_right),
         !is.na(authoritarian_libertarian),
         !is.na(populist_elitist))

cat(sprintf("Responses with complete ideology scores: %d (%.1f%%)\n",
            nrow(ideology_complete),
            nrow(ideology_complete) / nrow(engaged_data) * 100))

# =============================================================================
# ANALYSIS 1: Ideological Positioning by Model
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 1: IDEOLOGICAL POSITIONING BY MODEL\n")
cat(rep("=", 80), "\n", sep = "")

# Reshape ideology data to long format
ideology_long <- ideology_complete %>%
  select(model_f, language_f, prompt_id, prompt_category,
         economic_left_right, social_left_right,
         authoritarian_libertarian, populist_elitist) %>%
  pivot_longer(
    cols = c(economic_left_right, social_left_right,
             authoritarian_libertarian, populist_elitist),
    names_to = "dimension",
    values_to = "score"
  ) %>%
  mutate(
    dimension_f = factor(
      dimension,
      levels = c("economic_left_right", "social_left_right",
                 "authoritarian_libertarian", "populist_elitist"),
      labels = c("Economic L-R", "Social L-R",
                 "Libertarian-Authoritarian", "Elitist-Populist")
    )
  )

cat(sprintf("\nIdeology long format: %d rows\n", nrow(ideology_long)))

# Summary by model
ideology_by_model <- ideology_long %>%
  group_by(model_f, dimension_f) %>%
  summarise(
    n = n(),
    mean = mean(score, na.rm = TRUE),
    sd = sd(score, na.rm = TRUE),
    se = sd / sqrt(n),
    .groups = "drop"
  )

cat("\nMean ideology scores by model and dimension:\n")
print(ideology_by_model)

# Save summary
write_csv(ideology_by_model, "pipeline/tables/11_ideology_by_model.csv")

# =============================================================================
# ANALYSIS 2: Ideological Positioning by Model × Language
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 2: IDEOLOGICAL POSITIONING BY MODEL × LANGUAGE\n")
cat(rep("=", 80), "\n", sep = "")

# Summary by model and language
ideology_by_model_lang <- ideology_long %>%
  group_by(model_f, language_f, dimension_f) %>%
  summarise(
    n = n(),
    mean = mean(score, na.rm = TRUE),
    sd = sd(score, na.rm = TRUE),
    se = sd / sqrt(n),
    .groups = "drop"
  )

cat("\nMean ideology scores by model, language, and dimension:\n")
print(ideology_by_model_lang %>% head(20))

# Save summary
write_csv(ideology_by_model_lang, "pipeline/tables/12_ideology_by_model_language.csv")

# =============================================================================
# Statistical Model: Ideology ~ Model × Language × Dimension
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("STATISTICAL MODEL: IDEOLOGY ~ MODEL × LANGUAGE × DIMENSION\n")
cat(rep("-", 80), "\n", sep = "")

# Fit linear model with three-way interaction
model_ideology <- lm(score ~ model_f * language_f * dimension_f, data = ideology_long)

cat("\nModel summary:\n")
print(summary(model_ideology))

# Get predicted values using ggeffects
cat("\nGenerating predicted ideology scores...\n")
ideology_predictions <- ggpredict(model_ideology,
                                   terms = c("model_f", "dimension_f", "language_f"))

cat("\nPredicted ideology scores:\n")
print(ideology_predictions)

# Convert to data frame for saving
ideology_predictions_df <- as.data.frame(ideology_predictions)
write_csv(ideology_predictions_df, "pipeline/tables/13_ideology_predictions.csv")

# =============================================================================
# ANALYSIS 3: Moral Foundations by Model
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 3: MORAL FOUNDATIONS BY MODEL\n")
cat(rep("=", 80), "\n", sep = "")

# Check for NA moral foundation scores
moral_complete <- engaged_data %>%
  filter(!is.na(care_harm),
         !is.na(fairness_cheating),
         !is.na(loyalty_betrayal),
         !is.na(authority_subversion),
         !is.na(sanctity_degradation),
         !is.na(liberty_oppression))

cat(sprintf("Responses with complete moral foundation scores: %d (%.1f%%)\n",
            nrow(moral_complete),
            nrow(moral_complete) / nrow(engaged_data) * 100))

# Reshape moral foundation data to long format
moral_long <- moral_complete %>%
  select(model_f, language_f, prompt_id, prompt_category,
         care_harm, fairness_cheating, loyalty_betrayal,
         authority_subversion, sanctity_degradation, liberty_oppression,
         dominant_foundation) %>%
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

cat(sprintf("\nMoral foundations long format: %d rows\n", nrow(moral_long)))

# Summary by model
moral_by_model <- moral_long %>%
  group_by(model_f, foundation_f) %>%
  summarise(
    n = n(),
    activation_rate = mean(present_numeric, na.rm = TRUE),
    se = sqrt(activation_rate * (1 - activation_rate) / n),
    .groups = "drop"
  )

cat("\nMoral foundation activation rates by model:\n")
print(moral_by_model)

# Save summary
write_csv(moral_by_model, "pipeline/tables/14_moral_by_model.csv")

# =============================================================================
# ANALYSIS 4: Moral Foundations by Model × Language
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("ANALYSIS 4: MORAL FOUNDATIONS BY MODEL × LANGUAGE\n")
cat(rep("=", 80), "\n", sep = "")

# Summary by model and language
moral_by_model_lang <- moral_long %>%
  group_by(model_f, language_f, foundation_f) %>%
  summarise(
    n = n(),
    activation_rate = mean(present_numeric, na.rm = TRUE),
    se = sqrt(activation_rate * (1 - activation_rate) / n),
    .groups = "drop"
  )

cat("\nMoral foundation activation rates by model and language:\n")
print(moral_by_model_lang %>% head(20))

# Save summary
write_csv(moral_by_model_lang, "pipeline/tables/15_moral_by_model_language.csv")

# =============================================================================
# Statistical Model: Moral ~ Model × Language × Foundation
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("STATISTICAL MODEL: MORAL ~ MODEL × LANGUAGE × FOUNDATION\n")
cat(rep("-", 80), "\n", sep = "")

# Fit logistic regression with three-way interaction
model_moral <- glm(present_numeric ~ model_f * language_f * foundation_f,
                   data = moral_long,
                   family = binomial(link = "logit"))

cat("\nModel summary:\n")
print(summary(model_moral))

# Get predicted probabilities using ggeffects
cat("\nGenerating predicted moral foundation activation rates...\n")
moral_predictions <- ggpredict(model_moral,
                               terms = c("model_f", "foundation_f", "language_f"))

cat("\nPredicted moral foundation activation rates:\n")
print(moral_predictions)

# Convert to data frame for saving
moral_predictions_df <- as.data.frame(moral_predictions)
write_csv(moral_predictions_df, "pipeline/tables/16_moral_predictions.csv")

# =============================================================================
# Dominant Foundation Distribution
# =============================================================================

cat("\n")
cat(rep("-", 80), "\n", sep = "")
cat("DOMINANT FOUNDATION DISTRIBUTION\n")
cat(rep("-", 80), "\n", sep = "")

# Dominant foundation by model
dominant_by_model <- moral_complete %>%
  filter(!is.na(dominant_foundation)) %>%
  group_by(model_f, dominant_foundation) %>%
  summarise(n = n(), .groups = "drop") %>%
  group_by(model_f) %>%
  mutate(prop = n / sum(n)) %>%
  ungroup()

cat("\nDominant foundation distribution by model:\n")
print(dominant_by_model)

# Dominant foundation by model and language
dominant_by_model_lang <- moral_complete %>%
  filter(!is.na(dominant_foundation)) %>%
  group_by(model_f, language_f, dominant_foundation) %>%
  summarise(n = n(), .groups = "drop") %>%
  group_by(model_f, language_f) %>%
  mutate(prop = n / sum(n)) %>%
  ungroup()

cat("\nDominant foundation distribution by model and language:\n")
print(dominant_by_model_lang %>% head(20))

# Save summaries
write_csv(dominant_by_model, "pipeline/tables/17_dominant_foundation_by_model.csv")
write_csv(dominant_by_model_lang, "pipeline/tables/18_dominant_foundation_by_model_language.csv")

# =============================================================================
# Summary Statistics
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("SUMMARY STATISTICS\n")
cat(rep("=", 80), "\n", sep = "")

summary_stats <- list(
  engaged_responses = nrow(engaged_data),
  ideology_complete = nrow(ideology_complete),
  moral_complete = nrow(moral_complete),
  ideology_pct = nrow(ideology_complete) / nrow(engaged_data),
  moral_pct = nrow(moral_complete) / nrow(engaged_data)
)

cat("\nKey Statistics:\n")
for (name in names(summary_stats)) {
  cat(sprintf("  %s: %.3f\n", name, summary_stats[[name]]))
}

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("IDEOLOGY AND MORAL FOUNDATIONS ANALYSIS COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
cat("\nNext: Run 04_visualizations.R\n\n")
