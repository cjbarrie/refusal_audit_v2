# =============================================================================
# Script 11: Visualizations
# =============================================================================
# Create publication-quality visualizations for key findings
# All figures: dot plots with 95% CIs, PDF output, theme_refusal(), no gridlines

library(tidyverse)
library(ggplot2)
library(scales)

# Set working directory
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes

# Load clean data
load("pipeline/data_clean.RData")

cat(rep("=", 80), "\n", sep = "")
cat("CREATING VISUALIZATIONS\n")
cat(rep("=", 80), "\n", sep = "")

# Ensure output directory exists
dir.create("pipeline/plots", showWarnings = FALSE, recursive = TRUE)

# =============================================================================
# Figure 1: Overall Engagement by Model
# =============================================================================

cat("\nCreating Figure 1: Refusal by Model and Dataset Type...\n")

model_refusal <- data_clean %>%
  group_by(model_f, dataset_type_f) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  tidyr::complete(model_f, dataset_type_f, fill = list(n = 0, refusal_rate = NA_real_)) %>%
  mutate(
    refusal_label = dplyr::case_when(
      n == 0 ~ "NA",
      TRUE ~ sprintf("%.1f%%", refusal_rate * 100)
    ),
    refusal_x = ifelse(n == 0, 0, refusal_rate)
  )

p1 <- ggplot(model_refusal, aes(y = reorder(model_f, refusal_x), color = dataset_type_f)) +
  geom_point(aes(x = refusal_rate),
             data = dplyr::filter(model_refusal, n > 0),
             size = 3) +
  geom_point(aes(x = 0),
             data = dplyr::filter(model_refusal, n == 0),
             shape = 1, size = 3, stroke = 1, show.legend = FALSE) +
  geom_text(aes(x = refusal_x, label = refusal_label),
            hjust = -0.4, size = 2.8, show.legend = FALSE) +
  scale_x_continuous(labels = percent_format(),
                     limits = c(0, 0.6),
                     expand = expansion(mult = c(0, 0.1))) +
  scale_color_manual(values = c("Regular Prompts" = "gray60", "Boundary Prompts" = "#E41A1C")) +
  facet_wrap(~dataset_type_f, ncol = 1) +
  labs(
    title = "Refusal of Political Prompts by Model: Regular vs Boundary",
    subtitle = sprintf("N = %d responses across 5 languages", nrow(data_clean)),
    x = "Refusal Rate",
    y = NULL,
    color = "Prompt Type"
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 10),
    axis.text.y = element_text(size = 9),
    legend.position = "top"
  )

ggsave("pipeline/plots/fig1_engagement_by_model.pdf", p1, width = 8, height = 6)
ggsave("pipeline/plots/fig1_engagement_by_model.png", p1, width = 8, height = 6, dpi = 300)
cat("Saved: pipeline/plots/fig1_engagement_by_model.pdf + .png\n")

# =============================================================================
# Figure 2: DeepSeek's Chinese Language Effect
# =============================================================================

cat("\nCreating Figure 2: DeepSeek Language Refusal by Dataset Type...\n")

deepseek_language <- data_clean %>%
  filter(model == "deepseek-chat-v3.1") %>%
  group_by(language_f, dataset_type_f) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  tidyr::complete(language_f, dataset_type_f, fill = list(n = 0, refusal_rate = NA_real_)) %>%
  mutate(
    refusal_label = dplyr::case_when(
      n == 0 ~ "NA",
      TRUE ~ sprintf("%.1f%%", refusal_rate * 100)
    ),
    refusal_x = ifelse(n == 0, 0, refusal_rate),
    highlight = ifelse(language_f %in% c("English", "Chinese"), "yes", "no")
  )

p2 <- ggplot(deepseek_language,
             aes(y = reorder(language_f, refusal_x),
                 color = highlight)) +
  geom_point(aes(x = refusal_rate),
             data = dplyr::filter(deepseek_language, n > 0),
             size = 3) +
  geom_point(aes(x = 0),
             data = dplyr::filter(deepseek_language, n == 0),
             shape = 1, size = 3, stroke = 1, show.legend = FALSE) +
  geom_text(aes(x = refusal_x, label = refusal_label),
            hjust = -0.4, size = 2.8, color = "black", show.legend = FALSE) +
  scale_x_continuous(labels = percent_format(),
                     limits = c(0, 1),
                     expand = expansion(mult = c(0, 0.05))) +
  scale_color_manual(values = c("yes" = "#E41A1C", "no" = "#999999")) +
  facet_wrap(~dataset_type_f, ncol = 1) +
  labs(
    title = "DeepSeek Refusal Rates by Language: Regular vs Boundary",
    subtitle = "Chinese vs. English comparison highlighted",
    x = "Refusal Rate",
    y = NULL
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    legend.position = "none",
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 10),
    axis.text.y = element_text(size = 9)
  )

ggsave("pipeline/plots/fig2_deepseek_language_effect.pdf", p2, width = 8, height = 6)
ggsave("pipeline/plots/fig2_deepseek_language_effect.png", p2, width = 8, height = 6, dpi = 300)
cat("Saved: pipeline/plots/fig2_deepseek_language_effect.pdf + .png\n")

# =============================================================================
# Figure 3: Model × Language Engagement (Faceted by Model)
# =============================================================================

cat("\nCreating Figure 3: Model × Language × Dataset Type Refusal...\n")

model_language_data <- data_clean %>%
  group_by(model_f, language_f, dataset_type_f) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  tidyr::complete(model_f, language_f, dataset_type_f, fill = list(n = 0, refusal_rate = NA_real_)) %>%
  mutate(
    refusal_label = dplyr::case_when(
      n == 0 ~ "NA",
      TRUE ~ sprintf("%.0f%%", refusal_rate * 100)
    ),
    refusal_x = ifelse(n == 0, 0, refusal_rate)
  )

p3 <- ggplot(model_language_data, aes(y = language_f, color = dataset_type_f)) +
  geom_point(aes(x = refusal_rate),
             data = dplyr::filter(model_language_data, n > 0),
             size = 2.5) +
  geom_point(aes(x = 0),
             data = dplyr::filter(model_language_data, n == 0),
             shape = 1, size = 2.5, stroke = 1, show.legend = FALSE) +
  geom_text(aes(x = refusal_x, label = refusal_label),
            hjust = -0.3, size = 2.3, show.legend = FALSE) +
  facet_grid(dataset_type_f ~ model_f) +
  scale_x_continuous(labels = percent_format(), limits = c(0, 1)) +
  scale_color_manual(values = c("Regular Prompts" = "gray60", "Boundary Prompts" = "#E41A1C")) +
  labs(
    title = "Refusal Rates by Model, Language, and Prompt Type",
    subtitle = "Faceted by dataset type (rows) and model (columns)",
    x = "Refusal Rate",
    y = NULL,
    color = "Prompt Type"
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 8),
    axis.text.y = element_text(size = 8),
    strip.background = element_rect(fill = "gray95"),
    strip.text = element_text(face = "bold", size = 9),
    legend.position = "top"
  )

ggsave("pipeline/plots/fig3_engagement_by_language.pdf", p3, width = 9, height = 5)
ggsave("pipeline/plots/fig3_engagement_by_language.png", p3, width = 9, height = 5, dpi = 300)
cat("Saved: pipeline/plots/fig3_engagement_by_language.pdf + .png\n")

# =============================================================================
# Figure 3b: Refusal by Language (Model = columns, Dataset Type = rows), free x
# =============================================================================

cat("\nCreating Figure 3b: Refusal by Language faceted by Model × Dataset Type...\n")

model_language_bars <- model_language_data %>%
  filter(n > 0)

p3b <- ggplot(model_language_bars, aes(x = language_f, y = refusal_rate)) +
  geom_col(fill = "gray70") +
  geom_text(aes(label = sprintf("%.0f%%", refusal_rate * 100)),
            vjust = -0.3, size = 2.5) +
  facet_grid(dataset_type_f ~ model_f, scales = "free_x", space = "free_x") +
  scale_y_continuous(labels = percent_format(), limits = c(0, 1)) +
  labs(
    title = "Refusal Rates by Language",
    subtitle = "Faceted by model (columns) and prompt type (rows); x-axis free per facet",
    x = "Language",
    y = "Refusal Rate"
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 8, angle = 45, hjust = 1),
    axis.text.y = element_text(size = 8),
    strip.background = element_rect(fill = "gray95"),
    strip.text = element_text(face = "bold", size = 9)
  )

ggsave("pipeline/plots/fig3b_refusal_by_language_facets.pdf", p3b, width = 10, height = 8)
ggsave("pipeline/plots/fig3b_refusal_by_language_facets.png", p3b, width = 10, height = 8, dpi = 300)
cat("Saved: pipeline/plots/fig3b_refusal_by_language_facets.pdf + .png\n")

# =============================================================================
# Figure 3c/3d: Refusal by Language × Category (Model = columns; Category = rows)
# =============================================================================

cat("\nCreating Figure 3c/3d: Refusal by Language × Category, split by dataset type...\n")

language_category_base <- data_clean %>%
  filter(dataset_type_f == "Regular Prompts") %>%
  group_by(model_f, prompt_category, language_f) %>%
  summarise(n = n(), refusal_rate = mean(refused), .groups = "drop") %>%
  tidyr::complete(model_f, prompt_category, language_f, fill = list(n = 0, refusal_rate = NA_real_)) %>%
  mutate(
    refusal_label = dplyr::case_when(
      n == 0 ~ "NA",
      TRUE ~ sprintf("%.0f%%", refusal_rate * 100)
    ),
    refusal_x = ifelse(n == 0, 0, refusal_rate)
  )

language_category_boundary <- data_clean %>%
  filter(dataset_type_f == "Boundary Prompts") %>%
  group_by(model_f, prompt_category, language_f) %>%
  summarise(n = n(), refusal_rate = mean(refused), .groups = "drop") %>%
  tidyr::complete(model_f, prompt_category, language_f, fill = list(n = 0, refusal_rate = NA_real_)) %>%
  mutate(
    refusal_label = dplyr::case_when(
      n == 0 ~ "NA",
      TRUE ~ sprintf("%.0f%%", refusal_rate * 100)
    ),
    refusal_x = ifelse(n == 0, 0, refusal_rate)
  )

p3c <- ggplot(language_category_base, aes(x = refusal_rate, y = language_f)) +
  geom_point(data = dplyr::filter(language_category_base, n > 0), size = 2.5, color = "gray20") +
  geom_point(data = dplyr::filter(language_category_base, n == 0),
             aes(x = 0), shape = 1, size = 2.5, stroke = 1, color = "gray20") +
  geom_text(aes(x = refusal_x, label = refusal_label),
            hjust = -0.3, size = 2.5, color = "black") +
  facet_grid(model_f ~ prompt_category, scales = "free_x") +
  scale_x_continuous(labels = percent_format(), expand = expansion(mult = c(0, 0.1))) +
  labs(
    title = "Refusal Rates by Language (Regular Prompts)",
    subtitle = "Faceted by model (columns) and category (rows); x-axis free per facet",
    x = "Refusal Rate",
    y = NULL
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 8),
    axis.text.y = element_text(size = 8),
    strip.background = element_rect(fill = "gray95"),
    strip.text = element_text(face = "bold", size = 9)
  )

p3d <- ggplot(language_category_boundary, aes(x = refusal_rate, y = language_f)) +
  geom_point(data = dplyr::filter(language_category_boundary, n > 0), size = 2.5, color = "#E41A1C") +
  geom_point(data = dplyr::filter(language_category_boundary, n == 0),
             aes(x = 0), shape = 1, size = 2.5, stroke = 1, color = "#E41A1C") +
  geom_text(aes(x = refusal_x, label = refusal_label),
            hjust = -0.3, size = 2.5, color = "black") +
  facet_grid(model_f ~ prompt_category, scales = "free_x") +
  scale_x_continuous(labels = percent_format(), expand = expansion(mult = c(0, 0.1))) +
  labs(
    title = "Refusal Rates by Language (Boundary Prompts)",
    subtitle = "Faceted by model (columns) and category (rows); x-axis free per facet",
    x = "Refusal Rate",
    y = NULL
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 8),
    axis.text.y = element_text(size = 8),
    strip.background = element_rect(fill = "gray95"),
    strip.text = element_text(face = "bold", size = 9)
  )

ggsave("pipeline/plots/fig3c_refusal_by_language_category_regular.pdf", p3c, width = 14, height = 10)
ggsave("pipeline/plots/fig3c_refusal_by_language_category_regular.png", p3c, width = 14, height = 10, dpi = 300)
cat("Saved: pipeline/plots/fig3c_refusal_by_language_category_regular.pdf + .png\n")

ggsave("pipeline/plots/fig3d_refusal_by_language_category_boundary.pdf", p3d, width = 14, height = 10)
ggsave("pipeline/plots/fig3d_refusal_by_language_category_boundary.png", p3d, width = 14, height = 10, dpi = 300)
cat("Saved: pipeline/plots/fig3d_refusal_by_language_category_boundary.pdf + .png\n")

# =============================================================================
# Figure 4: Refusal by Category
# =============================================================================

cat("\nCreating Figure 4: Refusal by Category...\n")

category_data <- data_clean %>%
  group_by(prompt_category, controversy_tier) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  mutate(
    highlight = ifelse(prompt_category == "strategic_advice", "yes", "no")
  )

p4 <- ggplot(category_data, aes(x = refusal_rate,
                                 y = reorder(prompt_category, refusal_rate),
                                 color = highlight)) +
  geom_point(size = 3) +
  geom_text(aes(label = sprintf("%.1f%%", refusal_rate * 100)),
            hjust = -0.5, size = 3.5, color = "black") +
  facet_wrap(~ controversy_tier, ncol = 1) +
  scale_x_continuous(
    labels = percent_format(),
    limits = c(
      min(0, min(category_data$refusal_rate, na.rm = TRUE)),
      max(category_data$refusal_rate, na.rm = TRUE) * 1.1
    ),
    expand = c(0, 0)
  ) +
  scale_color_manual(values = c("yes" = "#E41A1C", "no" = "#999999")) +
  labs(
    title = "Refusal Rates by Prompt Category",
    subtitle = "Strategic advice has dramatically higher refusal rate (faceted by controversy tier)",
    x = "Refusal Rate",
    y = NULL
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    legend.position = "none",
    plot.title = element_text(face = "bold", size = 14),
    axis.text = element_text(size = 10)
  )

ggsave("pipeline/plots/fig4_category_refusal.pdf", p4, width = 10, height = 6)
ggsave("pipeline/plots/fig4_category_refusal.png", p4, width = 10, height = 6, dpi = 300)
cat("Saved: pipeline/plots/fig4_category_refusal.pdf + .png\n")

# =============================================================================
# Figure 5: Strategic Advice by Model
# =============================================================================

cat("\nCreating Figure 5: Strategic Advice by Model...\n")

strategic_data <- data_clean %>%
  filter(prompt_category == "strategic_advice") %>%
  group_by(model_f) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  )

overall_refusal <- mean(data_clean$refused)

p5 <- ggplot(strategic_data, aes(x = refusal_rate,
                                  y = reorder(model_f, refusal_rate))) +
  geom_vline(xintercept = overall_refusal, linetype = "dashed",
             color = "red", linewidth = 0.8) +
  geom_point(size = 3) +
  geom_text(aes(label = sprintf("%.1f%%", refusal_rate * 100)),
            hjust = -0.4, size = 3.5) +
  annotate("text", x = overall_refusal + 0.02, y = 3.5,
           label = sprintf("Overall avg refusal: %.1f%%", overall_refusal * 100),
           color = "red", size = 3.5, hjust = 0) +
  scale_x_continuous(labels = percent_format(),
                     limits = c(0, max(strategic_data$refusal_rate, overall_refusal) * 1.1),
                     expand = c(0, 0)) +
  labs(
    title = "Refusal of Strategic Advice Prompts",
    subtitle = "Dashed line shows overall refusal rate",
    x = "Refusal Rate",
    y = NULL
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 11)
  )

ggsave("pipeline/plots/fig5_strategic_advice_by_model.pdf", p5, width = 8, height = 6)
ggsave("pipeline/plots/fig5_strategic_advice_by_model.png", p5, width = 8, height = 6, dpi = 300)
cat("Saved: pipeline/plots/fig5_strategic_advice_by_model.pdf + .png\n")

# =============================================================================
# Figure 6: Refusal by Model, Faceted by Category
# =============================================================================

cat("\nCreating Figure 6: Refusal by Model, Faceted by Category...\n")

refusal_model_category <- data_clean %>%
  group_by(model_f, prompt_category) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  )

p6 <- ggplot(refusal_model_category, aes(x = refusal_rate, y = model_f)) +
  geom_point(size = 2.5) +
  geom_text(aes(label = sprintf("%.1f%%", refusal_rate * 100)),
            hjust = -0.4, size = 3) +
  facet_wrap(~ prompt_category, ncol = 2, scales = "free_y") +
  scale_x_continuous(labels = percent_format()) +
  labs(
    title = "Refusal Rates by Model and Category",
    subtitle = "Dot plots with 95% CIs, faceted by prompt category",
    x = "Refusal Rate",
    y = NULL
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 9),
    strip.background = element_rect(fill = "white"),
    strip.text = element_text(face = "bold", size = 10)
  )

ggsave("pipeline/plots/fig6_refusal_by_model_category.pdf", p6, width = 12, height = 10)
ggsave("pipeline/plots/fig6_refusal_by_model_category.png", p6, width = 12, height = 10, dpi = 300)
cat("Saved: pipeline/plots/fig6_refusal_by_model_category.pdf + .png\n")

# =============================================================================
# Figure 7: Controversial Category by Model × Language
# =============================================================================

cat("\nCreating Figure 7: Controversial by Model × Language...\n")

controversial_data <- data_clean %>%
  filter(controversy_tier == "boundary_testing") %>%
  group_by(model_f, language_f) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  tidyr::complete(model_f, language_f, fill = list(n = 0, refusal_rate = NA_real_)) %>%
  mutate(
    refusal_label = dplyr::case_when(
      n == 0 ~ "NA",
      TRUE ~ sprintf("%.1f%%", refusal_rate * 100)
    ),
    refusal_x = ifelse(n == 0, 0, refusal_rate)
  )

p7 <- ggplot(controversial_data, aes(y = language_f)) +
  geom_point(aes(x = refusal_rate),
             data = dplyr::filter(controversial_data, n > 0),
             size = 2.5) +
  geom_point(aes(x = 0),
             data = dplyr::filter(controversial_data, n == 0),
             shape = 1, size = 2.5, stroke = 1, show.legend = FALSE) +
  geom_text(aes(x = refusal_x, label = refusal_label),
            hjust = -0.4, size = 3) +
  facet_wrap(~ model_f, ncol = 1) +
  scale_x_continuous(labels = percent_format()) +
  labs(
    title = "Refusal Rates for Controversial Prompts by Model and Language",
    subtitle = "Boundary testing prompts only, faceted by model",
    x = "Refusal Rate",
    y = NULL
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 9),
    strip.background = element_rect(fill = "white"),
    strip.text = element_text(face = "bold", size = 11)
  )

ggsave("pipeline/plots/fig7_controversial_by_model_language.pdf", p7, width = 7, height = 5)
ggsave("pipeline/plots/fig7_controversial_by_model_language.png", p7, width = 7, height = 5, dpi = 300)
cat("Saved: pipeline/plots/fig7_controversial_by_model_language.pdf + .png\n")

# =============================================================================
# Figure 8: Domestic Government by Model × Language
# =============================================================================

cat("\nCreating Figure 8: Domestic Government by Model × Language...\n")

domestic_data <- data_clean %>%
  filter(prompt_category == "domestic_government") %>%
  group_by(model_f, language_f) %>%
  summarise(
    n = n(),
    refusal_rate = mean(refused),
    .groups = "drop"
  ) %>%
  tidyr::complete(model_f, language_f, fill = list(n = 0, refusal_rate = NA_real_)) %>%
  mutate(
    refusal_label = dplyr::case_when(
      n == 0 ~ "NA",
      TRUE ~ sprintf("%.1f%%", refusal_rate * 100)
    ),
    refusal_x = ifelse(n == 0, 0, refusal_rate)
  )

p8 <- ggplot(domestic_data, aes(y = language_f)) +
  geom_point(aes(x = refusal_rate),
             data = dplyr::filter(domestic_data, n > 0),
             size = 2.5) +
  geom_text(aes(x = refusal_x, label = refusal_label),
            hjust = -0.4, size = 3) +
  facet_wrap(~ model_f, ncol = 2) +
  scale_x_continuous(
    labels = percent_format(),
    limits = c(0, max(domestic_data$refusal_x, na.rm = TRUE) * 1.1),
    expand = expansion(mult = c(0, 0.1))
  ) +
  labs(
    title = "Refusal Rates for Domestic Government Prompts by Model and Language",
    subtitle = "Faceted by model (only languages with data shown)",
    x = "Refusal Rate",
    y = NULL
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 9),
    strip.background = element_rect(fill = "white"),
    strip.text = element_text(face = "bold", size = 11)
  )

ggsave("pipeline/plots/fig8_domestic_government_by_model_language.pdf", p8, width = 12, height = 5)
ggsave("pipeline/plots/fig8_domestic_government_by_model_language.png", p8, width = 12, height = 5, dpi = 300)
cat("Saved: pipeline/plots/fig8_domestic_government_by_model_language.pdf + .png\n")

# =============================================================================
# Figure 9: Ideology by Model and Dimension Grid
# =============================================================================

# Figures 9 and 10 render Pass-2/Pass-3 (slant) predictions produced by the
# archived 03_ideology_analysis.R. The canonical run is Pass-1-only
# (docs/ANNOTATION_TRIM_FULL_RUN.md), so those tables do not exist and an
# unguarded read_csv() here aborted the whole script -- taking figures 11+
# with it. Guarded so a Pass-1 run skips these two and continues.
if (file.exists("pipeline/tables/13_ideology_predictions.csv")) {
cat("\nCreating Figure 9: Ideology by Model and Dimension Grid...\n")

# Load ideology predictions from 03_ideology_analysis.R
ideology_predictions <- read_csv("pipeline/tables/13_ideology_predictions.csv", show_col_types = FALSE)

# Rename columns to match ggpredict output structure
ideology_plot_data <- ideology_predictions %>%
  rename(
    model_f = x,
    dimension_f = group,
    language_f = facet,
    mean = predicted,
    ci_low = conf.low,
    ci_high = conf.high
  )

p9 <- ggplot(ideology_plot_data, aes(x = mean, y = language_f)) +
  geom_point(size = 2) +
  geom_text(aes(label = sprintf("%.2f", mean)),
            hjust = -0.4, size = 2.8) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
  facet_grid(model_f ~ dimension_f) +
  scale_x_continuous(expand = expansion(mult = c(0.05, 0.2))) +
  labs(
    title = "Ideological Positioning by Model and Language",
    subtitle = "Predicted ideology scores; languages on y-axis, faceted by model and dimension",
    x = "Ideology Score (-2 to +2)",
    y = NULL
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 8),
    strip.background = element_rect(fill = "white"),
    strip.text = element_text(face = "bold", size = 10),
    legend.position = "none"
  )

ggsave("pipeline/plots/fig9_ideology_by_model_language.pdf", p9, width = 16, height = 6)
ggsave("pipeline/plots/fig9_ideology_by_model_language.png", p9, width = 16, height = 6, dpi = 300)
cat("Saved: pipeline/plots/fig9_ideology_by_model_language.pdf + .png\n")
} else {
  cat("\nSKIP Figure 9: pipeline/tables/13_ideology_predictions.csv absent (Pass-1-only run).\n")
}

# =============================================================================
# Figure 10: Moral Foundations by Model and Foundation Grid
# =============================================================================

if (file.exists("pipeline/tables/16_moral_predictions.csv")) {
cat("\nCreating Figure 10: Moral Foundations by Model and Foundation Grid...\n")

# Load moral foundations predictions from 03_ideology_analysis.R
moral_predictions <- read_csv("pipeline/tables/16_moral_predictions.csv", show_col_types = FALSE)

# Rename columns
moral_plot_data <- moral_predictions %>%
  rename(
    model_f = x,
    foundation_f = group,
    language_f = facet,
    prop = predicted,
    ci_low = conf.low,
    ci_high = conf.high
  )

p10 <- ggplot(moral_plot_data, aes(x = prop, y = language_f)) +
  geom_point(size = 2) +
  geom_text(aes(label = sprintf("%.1f%%", prop * 100)),
            hjust = -0.4, size = 2.8) +
  facet_grid(model_f ~ foundation_f) +
  scale_x_continuous(labels = percent_format(),
                     expand = expansion(mult = c(0.05, 0.2))) +
  labs(
    title = "Moral Foundation Activation by Model and Language",
    subtitle = "Predicted activation rates; languages on y-axis, faceted by model and foundation",
    x = "Activation Rate",
    y = NULL
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(size = 7),
    strip.background = element_rect(fill = "white"),
    strip.text = element_text(face = "bold", size = 10),
    legend.position = "none"
  )

ggsave("pipeline/plots/fig10_moral_foundations_by_model_language.pdf", p10, width = 16, height = 6)
ggsave("pipeline/plots/fig10_moral_foundations_by_model_language.png", p10, width = 16, height = 6, dpi = 300)
cat("Saved: pipeline/plots/fig10_moral_foundations_by_model_language.pdf + .png\n")
} else {
  cat("\nSKIP Figure 10: pipeline/tables/16_moral_predictions.csv absent (Pass-1-only run).\n")
}

# =============================================================================
# Figure 11: Refusal Justifications by Model (Histogram)
# =============================================================================

cat("\nCreating Figure 11: Refusal Justifications by Model...\n")

# Load refusal justifications data
refusal_data <- data_clean %>%
  filter(refused) %>%
  mutate(
    refusal_justification_f = factor(
      refusal_justification,
      levels = c("A", "B", "C", "D", "E", "F", "G"),
      labels = c("Neutrality/Balance", "Complexity/Uncertainty",
                 "Harm Avoidance", "Expertise Limitation",
                 "User Autonomy", "No Justification", "Other")
    )
  ) %>%
  filter(!is.na(refusal_justification_f))

refusal_counts <- refusal_data %>%
  group_by(model_f, refusal_justification_f) %>%
  summarise(n = n(), .groups = "drop")

p11 <- ggplot(refusal_counts, aes(x = refusal_justification_f, y = n, fill = refusal_justification_f)) +
  geom_col() +
  facet_wrap(~ model_f, ncol = 1, scales = "free_y") +
  scale_fill_brewer(palette = "Set2") +
  labs(
    title = "Distribution of Refusal Justifications by Model",
    subtitle = "Count of refusals by justification type, faceted by model",
    x = NULL,
    y = "Count",
    fill = "Justification"
  ) +
  theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    axis.text.x = element_text(angle = 45, hjust = 1, size = 9),
    strip.background = element_rect(fill = "white"),
    strip.text = element_text(face = "bold", size = 11),
    legend.position = "right"
  )

ggsave("pipeline/plots/fig11_refusal_justifications_by_model.pdf", p11, width = 12, height = 10)
ggsave("pipeline/plots/fig11_refusal_justifications_by_model.png", p11, width = 12, height = 10, dpi = 300)
cat("Saved: pipeline/plots/fig11_refusal_justifications_by_model.pdf + .png\n")

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("VISUALIZATION CREATION COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
cat("\nAll 11 figures saved to pipeline/plots/ (PDF + PNG)\n\n")
