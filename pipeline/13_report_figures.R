# =============================================================================
# Script 13: Report Figures
# =============================================================================
# Creates 5 purpose-built figures for KEY_FINDINGS.md
# All figures: faceted dot plots with Wilson 95% CI error bars
# Style: geom_point + geom_errorbar(orientation="y"), theme_bw, no gridlines
#
# Figures:
#   R1: Doing vs Discussing (refusal by category, faceted by prompt type)
#   R2: DeepSeek Language-Specific Compliance (EN vs ZH by category)
#   R3: Safety Thresholds by Model (refusal by model, faceted by prompt type)
#   R4: Ideology Shifts on Auth-Lib dimension (boundary - regular, by model)
#   R5: Justification Patterns (Harm Avoidance vs Neutrality vs Other, by model)
#
# Requires: data_clean.RData from 01_data_loading.R

library(tidyverse)
library(scales)

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes
load("pipeline/data_clean.RData")
dir.create("pipeline/plots", showWarnings = FALSE, recursive = TRUE)

cat(rep("=", 80), "\n", sep = "")
cat("CREATING REPORT FIGURES (04c)\n")
cat(rep("=", 80), "\n", sep = "")

# =============================================================================
# Helper: Wilson score confidence interval
# =============================================================================

wilson_ci <- function(k, n, z = 1.96) {
  p <- k / n
  denom <- 1 + z^2 / n
  center <- (p + z^2 / (2 * n)) / denom
  half <- z * sqrt((p * (1 - p) + z^2 / (4 * n)) / n) / denom
  data.frame(lower = pmax(0, center - half), upper = pmin(1, center + half))
}

# Shared theme
theme_report <- theme_refusal() +
  theme(
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 13),
    plot.subtitle = element_text(size = 10, color = "gray30"),
    axis.title = element_text(size = 11),
    axis.text = element_text(size = 10),
    strip.background = element_rect(fill = "gray95"),
    strip.text = element_text(face = "bold", size = 11)
  )

# =============================================================================
# Figure R1: Doing vs. Discussing Politics
# Refusal rate by category, faceted by prompt type
# =============================================================================

cat("\nCreating Figure R1: Doing vs. Discussing Politics...\n")

r1_data <- data_clean %>%
  group_by(prompt_category, dataset_type_f) %>%
  summarise(
    n = n(),
    k = sum(refused),
    rate = k / n,
    .groups = "drop"
  ) %>%
  bind_cols(wilson_ci(.$k, .$n)) %>%
  mutate(
    highlight = ifelse(prompt_category %in% c("strategic_advice", "image_generation"),
                       "Instrumental", "Analytical"),
    cat_label = str_replace_all(prompt_category, "_", " ") %>% str_to_title()
  )

fig_r1 <- ggplot(r1_data, aes(x = rate, y = reorder(cat_label, rate), color = highlight)) +
  geom_errorbar(orientation = "y",aes(xmin = lower, xmax = upper), width = 0.25, linewidth = 0.5) +
  geom_point(size = 2.5) +
  facet_wrap(~dataset_type_f, ncol = 1, scales = "free_x") +
  scale_x_continuous(labels = percent_format(accuracy = 1),
                     expand = expansion(mult = c(0, 0.05))) +
  scale_color_manual(values = c("Instrumental" = "#E41A1C", "Analytical" = "gray50"),
                     name = NULL) +
  labs(
    title = "Refusal Rates by Prompt Category",
    subtitle = "Strategic advice and image generation (red) involve producing political content,\nnot analyzing it. Wilson 95% CI.",
    x = "Refusal Rate",
    y = NULL
  ) +
  theme_report +
  theme(legend.position = "top")

ggsave("pipeline/plots/fig_r1_doing_vs_discussing.pdf", fig_r1, width = 8, height = 7)
ggsave("pipeline/plots/fig_r1_doing_vs_discussing.png", fig_r1, width = 8, height = 7, dpi = 300)
cat("Saved: fig_r1_doing_vs_discussing.pdf + .png\n")

# =============================================================================
# Figure R2: DeepSeek Language-Specific Compliance
# DeepSeek refusal rates, EN vs ZH, by category, faceted by prompt type
# =============================================================================

cat("\nCreating Figure R2: DeepSeek Language-Specific Compliance...\n")

r2_data <- data_clean %>%
  filter(model == "deepseek-chat-v3.1",
         prompt_language %in% c("en", "zh")) %>%
  group_by(prompt_category, dataset_type_f, language_f) %>%
  summarise(
    n = n(),
    k = sum(refused),
    rate = k / n,
    .groups = "drop"
  ) %>%
  bind_cols(wilson_ci(.$k, .$n)) %>%
  mutate(
    cat_label = str_replace_all(prompt_category, "_", " ") %>% str_to_title()
  )

fig_r2 <- ggplot(r2_data, aes(x = rate, y = reorder(cat_label, rate),
                                color = language_f)) +
  geom_errorbar(orientation = "y",aes(xmin = lower, xmax = upper),
                 width = 0.3, linewidth = 0.5,
                 position = position_dodge(width = 0.6)) +
  geom_point(size = 2.5, position = position_dodge(width = 0.6)) +
  facet_wrap(~dataset_type_f, ncol = 1, scales = "free_x") +
  scale_x_continuous(labels = percent_format(accuracy = 1),
                     expand = expansion(mult = c(0, 0.05))) +
  scale_color_manual(values = c("English" = "#4DAF4A", "Chinese" = "#E41A1C"),
                     name = "Response Language") +
  labs(
    title = "DeepSeek Refusal: English vs. Chinese",
    subtitle = "Chinese prompts refused at higher rates across categories.\nWilson 95% CI.",
    x = "Refusal Rate",
    y = NULL
  ) +
  theme_report +
  theme(legend.position = "top")

ggsave("pipeline/plots/fig_r2_deepseek_language.pdf", fig_r2, width = 8, height = 7)
ggsave("pipeline/plots/fig_r2_deepseek_language.png", fig_r2, width = 8, height = 7, dpi = 300)
cat("Saved: fig_r2_deepseek_language.pdf + .png\n")

# =============================================================================
# Figure R3: Safety Thresholds by Model
# Refusal rate by model, faceted by prompt type
# =============================================================================

cat("\nCreating Figure R3: Safety Thresholds by Model...\n")

r3_data <- data_clean %>%
  group_by(model_f, dataset_type_f) %>%
  summarise(
    n = n(),
    k = sum(refused),
    rate = k / n,
    .groups = "drop"
  ) %>%
  bind_cols(wilson_ci(.$k, .$n))

fig_r3 <- ggplot(r3_data, aes(x = rate, y = reorder(model_f, rate))) +
  geom_errorbar(orientation = "y",aes(xmin = lower, xmax = upper), width = 0.3, linewidth = 0.5,
                 color = "gray40") +
  geom_point(size = 3, color = "#377EB8") +
  geom_text(aes(label = sprintf("%.1f%%", rate * 100)),
            hjust = -0.4, size = 3.2, color = "gray20") +
  facet_wrap(~dataset_type_f, ncol = 1, scales = "free_x") +
  scale_x_continuous(labels = percent_format(accuracy = 1),
                     expand = expansion(mult = c(0, 0.12))) +
  labs(
    title = "Refusal Rates by Model",
    subtitle = "Models vary substantially in baseline refusal and boundary sensitivity.\nWilson 95% CI.",
    x = "Refusal Rate",
    y = NULL
  ) +
  theme_report

ggsave("pipeline/plots/fig_r3_safety_thresholds.pdf", fig_r3, width = 8, height = 6)
ggsave("pipeline/plots/fig_r3_safety_thresholds.png", fig_r3, width = 8, height = 6, dpi = 300)
cat("Saved: fig_r3_safety_thresholds.pdf + .png\n")

# =============================================================================
# Figure R4: Ideology Shifts on Authoritarian-Libertarian Dimension
# Shift (boundary mean - regular mean) by model, with pooled SE CI
# =============================================================================

cat("\nCreating Figure R4: Ideology Shifts (Auth-Lib)...\n")

# Load pre-computed ideology by dataset type (has n, mean, sd, se per model × dataset × dimension)
ideology_by_dt <- read_csv("pipeline/tables/26_ideology_by_dataset_type.csv",
                           show_col_types = FALSE)

r4_data <- ideology_by_dt %>%
  filter(dimension_f == "Authoritarian-Libertarian") %>%
  select(model_f, dataset_type_f, n, mean_score, se_score) %>%
  pivot_wider(
    names_from = dataset_type_f,
    values_from = c(n, mean_score, se_score),
    names_sep = "_"
  ) %>%
  mutate(
    shift = `mean_score_Boundary Prompts` - `mean_score_Regular Prompts`,
    se_shift = sqrt(`se_score_Regular Prompts`^2 + `se_score_Boundary Prompts`^2),
    lower = shift - 1.96 * se_shift,
    upper = shift + 1.96 * se_shift,
    model_f = factor(model_f, levels = model_f[order(shift)])
  )

fig_r4 <- ggplot(r4_data, aes(x = shift, y = model_f)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "gray50") +
  geom_errorbar(orientation = "y",aes(xmin = lower, xmax = upper), width = 0.3, linewidth = 0.5,
                 color = "gray40") +
  geom_point(size = 3, color = "#984EA3") +
  geom_text(aes(label = sprintf("%.2f", shift)),
            hjust = -0.4, size = 3.2, color = "gray20") +
  scale_x_continuous(expand = expansion(mult = c(0.05, 0.15))) +
  labs(
    title = "Libertarian Shift on Boundary Prompts",
    subtitle = "Authoritarian-Libertarian dimension (negative = libertarian shift).\nDifference in means (boundary - regular) among engaged responses. 95% CI.",
    x = "Ideology Shift (Boundary - Regular)",
    y = NULL
  ) +
  theme_report

ggsave("pipeline/plots/fig_r4_ideology_shifts.pdf", fig_r4, width = 8, height = 5)
ggsave("pipeline/plots/fig_r4_ideology_shifts.png", fig_r4, width = 8, height = 5, dpi = 300)
cat("Saved: fig_r4_ideology_shifts.pdf + .png\n")

# =============================================================================
# Figure R5: Neutrality vs. Harm Avoidance Justification Patterns
# Proportion of refusals citing each justification group, by model
# =============================================================================

cat("\nCreating Figure R5: Justification Patterns...\n")

r5_data <- data_clean %>%
  filter(refused, !is.na(refusal_justification)) %>%
  mutate(
    justification_group = case_when(
      refusal_justification == "C" ~ "Harm Avoidance",
      refusal_justification == "A" ~ "Neutrality / Balance",
      TRUE ~ "Other"
    ),
    justification_group = factor(justification_group,
                                  levels = c("Harm Avoidance", "Neutrality / Balance", "Other"))
  ) %>%
  group_by(model_f, justification_group) %>%
  summarise(k = n(), .groups = "drop") %>%
  group_by(model_f) %>%
  mutate(n = sum(k), rate = k / n) %>%
  ungroup() %>%
  bind_cols(wilson_ci(.$k, .$n))

fig_r5 <- ggplot(r5_data, aes(x = rate, y = reorder(model_f, rate))) +
  geom_errorbar(orientation = "y",aes(xmin = lower, xmax = upper), width = 0.3, linewidth = 0.5,
                 color = "gray40") +
  geom_point(size = 2.5, color = "#FF7F00") +
  geom_text(aes(label = sprintf("%.0f%%", rate * 100)),
            hjust = -0.3, size = 3, color = "gray20") +
  facet_wrap(~justification_group, ncol = 1, scales = "free_x") +
  scale_x_continuous(labels = percent_format(accuracy = 1),
                     expand = expansion(mult = c(0, 0.12))) +
  labs(
    title = "Refusal Justification Patterns by Model",
    subtitle = "Models differ in whether they frame refusals as harm prevention or\nneutrality maintenance. Wilson 95% CI.",
    x = "Proportion of Refusals",
    y = NULL
  ) +
  theme_report

ggsave("pipeline/plots/fig_r5_justification_patterns.pdf", fig_r5, width = 8, height = 7)
ggsave("pipeline/plots/fig_r5_justification_patterns.png", fig_r5, width = 8, height = 7, dpi = 300)
cat("Saved: fig_r5_justification_patterns.pdf + .png\n")

# =============================================================================
# Done
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("REPORT FIGURES COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
cat("\n5 figures saved to pipeline/plots/ (PDF + PNG):\n")
cat("  fig_r1_doing_vs_discussing\n")
cat("  fig_r2_deepseek_language\n")
cat("  fig_r3_safety_thresholds\n")
cat("  fig_r4_ideology_shifts\n")
cat("  fig_r5_justification_patterns\n\n")
