# =============================================================================
# Script 12: Extended Visualizations
# =============================================================================
# Creates additional figures for boundary prompts and extended analyses
# Requires: data_clean.RData, tables from extended analysis scripts

library(tidyverse)
library(scales)

# Set working directory
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes

cat(rep("=", 80), "\n", sep = "")
cat("CREATING EXTENDED VISUALIZATIONS\n")
cat(rep("=", 80), "\n", sep = "")

# Load data
load("pipeline/data_clean.RData")

# Base theme
theme_custom <- theme_nature() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.title = element_text(size = 12),
    axis.text = element_text(size = 10)
  )

# ============================================================================
# Figure 12: Base vs Boundary Refusal Rates
# =============================================================================

cat("\nCreating Figure 12: Base vs Boundary Refusal Rates...\n")

refusal_by_dataset <- data_clean %>%
  group_by(model_f, dataset_type_f) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  )

fig12 <- ggplot(refusal_by_dataset, aes(x = model_f, y = refusal_rate,
                                         fill = dataset_type_f)) +
  geom_col(position = "dodge", width = 0.7) +
  geom_text(aes(label = percent(refusal_rate, accuracy = 0.1)),
            position = position_dodge(width = 0.7),
            vjust = -0.5, size = 3) +
  scale_y_continuous(labels = percent, limits = c(0, 0.6)) +
  scale_fill_tier() +
  labs(
    title = "Refusal Rates: Regular vs Boundary Prompts",
    x = NULL,
    y = "Refusal Rate",
    fill = "Prompt Type"
  ) +
  theme_custom +
  theme(legend.position = "top")

save_fig(fig12, "pipeline/plots/fig12_base_vs_boundary.png", width = 7.20, height = 4.32)
cat("Saved: pipeline/plots/fig12_base_vs_boundary.pdf + .png\n")

# Figure 13 (ideology shifts) depends on annotation Pass 2 (ideology/moral foundations), which the
# canonical Pass-1-only run does not produce (docs/ANNOTATION_TRIM_FULL_RUN.md).
# The table below is written by a script now in archive/pipeline_slant/, so an
# unguarded read_csv() aborted this script and every figure after it. Runs
# normally against a run annotated with --all-passes.
if (file.exists("pipeline/tables/27_ideology_shifts.csv")) {
# =============================================================================
# Figure 13: Ideology Shifts (Base → Boundary)
# =============================================================================

cat("\nCreating Figure 13: Ideology Shifts...\n")

ideology_shifts <- read_csv("pipeline/tables/27_ideology_shifts.csv",
                            show_col_types = FALSE)

fig13 <- ggplot(ideology_shifts,
                aes(x = dimension_f, y = shift, fill = model_f)) +
  geom_col(position = "dodge") +
  geom_hline(yintercept = 0, linetype = "dashed", color = "gray30") +
  scale_fill_brewer(palette = "Set2") +
  labs(
    title = "Ideology Shifts on Boundary Prompts (vs Regular Prompts)",
    subtitle = "Negative = Left/Libertarian shift, Positive = Right/Authoritarian shift",
    x = "Ideology Dimension",
    y = "Shift (Boundary - Regular)",
    fill = "Model"
  ) +
  theme_custom +
  theme(axis.text.x = element_text(angle = 45, hjust = 1),
        legend.position = "top")

save_fig(fig13, "pipeline/plots/fig13_ideology_shifts.png", width = 7.20, height = 4.20)
cat("Saved: pipeline/plots/fig13_ideology_shifts.pdf + .png\n")

} else {
  cat("\nSKIP Figure 13 (ideology shifts): pipeline/tables/27_ideology_shifts.csv absent (Pass-1-only run).\n")
}
# Figure 14 (moral foundations heatmap) depends on annotation Pass 2 (ideology/moral foundations), which the
# canonical Pass-1-only run does not produce (docs/ANNOTATION_TRIM_FULL_RUN.md).
# The table below is written by a script now in archive/pipeline_slant/, so an
# unguarded read_csv() aborted this script and every figure after it. Runs
# normally against a run annotated with --all-passes.
if (file.exists("pipeline/tables/29_moral_by_language_category.csv")) {
# =============================================================================
# Figure 14: Moral Foundations Heatmap (Language × Category)
# =============================================================================

cat("\nCreating Figure 14: Moral Foundations Heatmap...\n")

moral_lang_cat <- read_csv("pipeline/tables/29_moral_by_language_category.csv",
                           show_col_types = FALSE)

# Focus on top foundations
top_foundations <- c("Care/Harm", "Fairness/Cheating", "Liberty/Oppression")

moral_heatmap_data <- moral_lang_cat %>%
  filter(foundation_f %in% top_foundations)

fig14 <- ggplot(moral_heatmap_data,
                aes(x = prompt_category, y = language_f, fill = activation_rate)) +
  geom_tile(color = "white") +
  geom_text(aes(label = percent(activation_rate, accuracy = 1)),
            color = "black", size = 2.5) +
  scale_fill_gradient2(low = "#2166AC", mid = "white", high = "#B2182B",
                       midpoint = 0.5, labels = percent) +
  facet_wrap(~ foundation_f, ncol = 1) +
  labs(
    title = "Moral Foundation Activation by Language and Category",
    x = "Prompt Category",
    y = "Language",
    fill = "Activation\nRate"
  ) +
  theme_custom +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))

save_fig(fig14, "pipeline/plots/fig14_moral_heatmap.png", width = 7.20, height = 6.00)
cat("Saved: pipeline/plots/fig14_moral_heatmap.pdf + .png\n")

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("EXTENDED VISUALIZATION CREATION COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
cat("\nCreated 3 additional figures (fig12-fig14)\n")
cat("Total figures: 14 (11 from 11_visualizations.R + 3 extended)\n\n")

} else {
  cat("\nSKIP Figure 14 (moral foundations heatmap): pipeline/tables/29_moral_by_language_category.csv absent (Pass-1-only run).\n")
}