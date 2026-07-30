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
theme_custom <- theme_refusal() +
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
  scale_fill_manual(values = c("Regular Prompts" = "gray60",
                                "Boundary Prompts" = "#E41A1C")) +
  labs(
    title = "Refusal Rates: Regular vs Boundary Prompts",
    x = NULL,
    y = "Refusal Rate",
    fill = "Prompt Type"
  ) +
  theme_custom +
  theme(legend.position = "top")

ggsave("pipeline/plots/fig12_base_vs_boundary.pdf", fig12, width = 10, height = 6)
ggsave("pipeline/plots/fig12_base_vs_boundary.png", fig12, width = 10, height = 6, dpi = 300)
cat("Saved: pipeline/plots/fig12_base_vs_boundary.pdf + .png\n")

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

ggsave("pipeline/plots/fig13_ideology_shifts.pdf", fig13, width = 12, height = 7)
ggsave("pipeline/plots/fig13_ideology_shifts.png", fig13, width = 12, height = 7, dpi = 300)
cat("Saved: pipeline/plots/fig13_ideology_shifts.pdf + .png\n")

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

ggsave("pipeline/plots/fig14_moral_heatmap.pdf", fig14, width = 12, height = 10)
ggsave("pipeline/plots/fig14_moral_heatmap.png", fig14, width = 12, height = 10, dpi = 300)
cat("Saved: pipeline/plots/fig14_moral_heatmap.pdf + .png\n")

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("EXTENDED VISUALIZATION CREATION COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
cat("\nCreated 3 additional figures (fig12-fig14)\n")
cat("Total figures: 14 (11 from 11_visualizations.R + 3 extended)\n\n")
