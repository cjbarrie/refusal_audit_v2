# =============================================================================
# Script 15: PNAS per-finding figures
# =============================================================================
# One standalone horizontal dotplot per finding in pnas_paper.tex, title-free
# (the LaTeX \caption carries the description). Replaces the old four-panel
# composite fig_pnas_main.pdf.
#
# Outputs (pipeline/plots/):
#   fig_pnas_1_tasktype.pdf       F1  task-type refusal, Regular vs Boundary
#   fig_pnas_2_deepseek_pilot.pdf F2  DeepSeek pilot EN vs ZH, 5 audit models
#   fig_pnas_3_study_a.pdf        F3  Study A jurisdiction x language, 2 strata
#   fig_pnas_4_entity_swap.pdf    F4  Study B-refined DeepSeek entity swap
#   fig_pnas_5_native_mt.pdf      F5  Study B-orig refusal by prompt variant
#   fig_pnas_6_stance.pdf         F6  engaged-only CCP state-alignment, 12 models
#
# Run AFTER archive/pipeline_study_ab/10_study_a_panel.R, archive/pipeline_study_ab/13_deepseek_dotplots.R,
# 14_deepseek_brief_figures.R and archive/pipeline_study_ab/16_engaged_state_alignment.R, whose output
# CSVs this script reads. F1 is computed here from data_clean.RData.
# =============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(scales)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes
load("pipeline/data_clean.RData")

dir.create("pipeline/plots",  showWarnings = FALSE, recursive = TRUE)
dir.create("pipeline/tables", showWarnings = FALSE, recursive = TRUE)

# --- shared style ------------------------------------------------------------
deepseek_color <- "#c0392b"
other_color    <- "#7f8c8d"
en_shape <- 21
zh_shape <- 24

lang_shape <- scale_shape_manual(values = c(English = en_shape,
                                            Chinese = zh_shape), name = NULL)
lang_fill  <- scale_fill_manual(values = c(English = "white",
                                           Chinese = deepseek_color), name = NULL)
pct_x <- scale_x_continuous(labels = percent_format(accuracy = 1),
                            limits = c(0, NA),
                            expand = expansion(mult = c(0, 0.06)))
pnas_theme <- theme_nature() +
  theme(panel.grid.major.y = element_blank(),
        legend.position = "top")

# =============================================================================
# F1 - Task-type refusal, Regular vs Boundary (computed from data_clean)
# =============================================================================
# v2 topic-domain taxonomy (replaces the legacy task-type scheme). Ordered by
# descending overall refusal so the figure reads top-down.
cat_levels <- c("territorial_sovereignty", "security_conflict",
                "governance_democracy", "civil_rights_liberties",
                "social_moral", "economic_policy", "religion_state",
                "environment_energy", "migration_nationalism")
cat_pretty <- c(territorial_sovereignty = "Territorial sovereignty",
                security_conflict       = "Security / conflict",
                governance_democracy    = "Governance / democracy",
                civil_rights_liberties  = "Civil rights / liberties",
                social_moral            = "Social / moral",
                economic_policy         = "Economic policy",
                religion_state          = "Religion / state",
                environment_energy      = "Environment / energy",
                migration_nationalism   = "Migration / nationalism")

f1_dat <- data_clean %>%
  group_by(prompt_category, dataset_type_f) %>%
  summarise(refusal_rate = mean(refused), n = n(), .groups = "drop") %>%
  mutate(
    # Sovereignty/security are the politically constrained domains in v2,
    # analogous to the legacy "instrumental" highlight.
    instrumental = as.character(prompt_category) %in%
      c("territorial_sovereignty", "security_conflict"),
    cat_label = factor(cat_pretty[as.character(prompt_category)],
                       levels = rev(unname(cat_pretty[cat_levels])))
  )
write_csv(f1_dat, "pipeline/tables/45_pnas_tasktype.csv")

p1 <- ggplot(f1_dat, aes(x = refusal_rate, y = cat_label, colour = instrumental)) +
  geom_segment(aes(x = 0, xend = refusal_rate, yend = cat_label),
               linewidth = 0.5, alpha = 0.5) +
  geom_point(size = 3.2) +
  facet_wrap(~ dataset_type_f, ncol = 1) +
  scale_colour_manual(values = c(`FALSE` = other_color, `TRUE` = deepseek_color),
                      guide = "none") +
  pct_x +
  labs(x = "Refusal rate", y = NULL) +
  pnas_theme +
  theme(strip.text = element_text(face = "bold", hjust = 0))
save_fig(p1, "pipeline/plots/fig_pnas_1_tasktype.png", width = 6.50, height = 5.00)

# =============================================================================
# F2 - DeepSeek pilot EN vs ZH, five audit models (36_pilot_deepseek_fig1.csv)
# =============================================================================
f2_dat <- read_csv("pipeline/tables/36_pilot_deepseek_fig1.csv",
                   show_col_types = FALSE) %>%
  mutate(
    model_label = factor(model_label,
                         levels = rev(c("DeepSeek V3.1", "Qwen3-Max", "Grok 4.3",
                                        "GPT-5.1", "Claude Opus 4.5", "GPT-4o",
                                        "Mistral Large 2512"))),
    language = factor(language, levels = c("English", "Chinese"))
  )
f2_segs <- f2_dat %>%
  select(model_label, language, refusal_rate) %>%
  pivot_wider(names_from = language, values_from = refusal_rate)

p2 <- ggplot(f2_dat, aes(x = refusal_rate, y = model_label,
                         shape = language, fill = language,
                         colour = model_label == "DeepSeek V3.1")) +
  geom_segment(data = f2_segs,
               aes(x = English, xend = Chinese,
                   y = model_label, yend = model_label,
                   colour = model_label == "DeepSeek V3.1"),
               inherit.aes = FALSE, linewidth = 0.6, alpha = 0.55) +
  geom_point(size = 3.5, stroke = 0.7) +
  scale_colour_manual(values = c(`TRUE` = deepseek_color, `FALSE` = other_color),
                      guide = "none") +
  lang_shape + lang_fill + pct_x +
  labs(x = "Refusal rate", y = NULL) +
  pnas_theme
save_fig(p2, "pipeline/plots/fig_pnas_2_deepseek_pilot.png", width = 6.50, height = 3.20)

# =============================================================================
# F3 - Study A jurisdiction x language, two content strata
#      (28_study_a_stratified_marginal.csv)
# =============================================================================
if (file.exists("pipeline/tables/28_study_a_stratified_marginal.csv")) {
f3_dat <- read_csv("pipeline/tables/28_study_a_stratified_marginal.csv",
                   show_col_types = FALSE) %>%
  mutate(
    jurisdiction = factor(jurisdiction, levels = c("eu", "us", "china"),
                          labels = c("EU", "U.S.", "China")),
    language = factor(language, levels = c("en", "zh", "ar"),
                      labels = c("English", "Chinese", "Arabic")),
    stratum = factor(stratum,
                     levels = c("cn_sensitive", "western_sensitive"),
                     labels = c("China-sensitive prompts",
                                "Western-sensitive prompts"))
  )

p3 <- ggplot(f3_dat, aes(x = predicted_refused, y = jurisdiction,
                         colour = language)) +
  geom_pointrange(aes(xmin = conf.low, xmax = conf.high),
                  position = position_dodge(width = 0.6),
                  size = 0.45, linewidth = 0.5, fatten = 3.2) +
  facet_wrap(~ stratum, ncol = 1) +
  scale_colour_manual(values = c(English = "#2c3e50",
                                 Chinese = deepseek_color,
                                 Arabic  = "#2980b9"), name = NULL) +
  scale_x_continuous(labels = percent_format(accuracy = 1), limits = c(0, NA)) +
  labs(x = "Model-estimated refusal probability (95% CI)", y = NULL) +
  pnas_theme +
  theme(strip.text = element_text(face = "bold", hjust = 0))
save_fig(p3, "pipeline/plots/fig_pnas_3_study_a.png", width = 6.50, height = 4.00)
} else cat("F3 skipped: Study A table not present in this run.\n")

# =============================================================================
# F4 - Study B-refined: DeepSeek entity swap (34_deepseek_brief_fig3.csv)
# =============================================================================
if (file.exists("pipeline/tables/34_deepseek_brief_fig3.csv")) {
f4_src <- read_csv("pipeline/tables/34_deepseek_brief_fig3.csv",
                   show_col_types = FALSE)
zh_order4 <- f4_src %>%
  filter(language == "Chinese") %>%
  arrange(desc(refusal_rate)) %>%
  pull(entity_label)
f4_dat <- f4_src %>%
  mutate(entity_label = factor(entity_label, levels = rev(zh_order4)),
         language = factor(language, levels = c("English", "Chinese")))
f4_segs <- f4_dat %>%
  select(entity_label, language, refusal_rate) %>%
  pivot_wider(names_from = language, values_from = refusal_rate)

p4 <- ggplot(f4_dat, aes(x = refusal_rate, y = entity_label,
                         shape = language, fill = language)) +
  geom_segment(data = f4_segs,
               aes(x = English, xend = Chinese,
                   y = entity_label, yend = entity_label),
               inherit.aes = FALSE, colour = deepseek_color,
               linewidth = 0.6, alpha = 0.6) +
  geom_point(size = 4, stroke = 0.7, colour = deepseek_color) +
  lang_shape + lang_fill + pct_x +
  labs(x = "Refusal rate", y = NULL) +
  pnas_theme
save_fig(p4, "pipeline/plots/fig_pnas_4_entity_swap.png", width = 6.50, height = 3.60)
} else cat("F4 skipped: Study B-refined table not present in this run.\n")

# =============================================================================
# F5 - Study B-orig: refusal by prompt variant (34_deepseek_brief_fig4.csv)
# =============================================================================
if (file.exists("pipeline/tables/34_deepseek_brief_fig4.csv")) {
f5_dat <- read_csv("pipeline/tables/34_deepseek_brief_fig4.csv",
                   show_col_types = FALSE) %>%
  mutate(
    variant = factor(variant,
                     levels = rev(c("Native English", "MT English (from ZH)",
                                    "MT Chinese (from EN)", "Native Chinese"))),
    model_label = factor(model_label,
                         levels = c("DeepSeek V3.1", "Qwen3-235B",
                                    "Claude Opus 4.5", "GPT-5.1"))
  )

p5 <- ggplot(f5_dat, aes(x = refusal_rate, y = variant,
                         colour = model_label == "DeepSeek V3.1")) +
  geom_segment(aes(x = 0, xend = refusal_rate, yend = variant),
               linewidth = 0.5, alpha = 0.5) +
  geom_point(size = 3.5) +
  facet_wrap(~ model_label, ncol = 1, strip.position = "top") +
  scale_colour_manual(values = c(`TRUE` = deepseek_color, `FALSE` = other_color),
                      guide = "none") +
  pct_x +
  labs(x = "Refusal rate", y = NULL) +
  pnas_theme +
  theme(strip.text = element_text(face = "bold", hjust = 0))
save_fig(p5, "pipeline/plots/fig_pnas_5_native_mt.png", width = 6.00, height = 5.50)
} else cat("F5 skipped: native/MT table not present in this run.\n")

# =============================================================================
# F6 - Engaged-only CCP state-alignment, 12 models (37_engaged_state_alignment.csv)
# =============================================================================
if (file.exists("pipeline/tables/37_engaged_state_alignment.csv")) {
f6_dat <- read_csv("pipeline/tables/37_engaged_state_alignment.csv",
                   show_col_types = FALSE) %>%
  mutate(
    model_label = factor(model_label,
      levels = rev(c("GPT-5.1", "Claude Opus 4.5", "GPT-4o", "Gemini 2.5 Pro",
                     "Llama 4 Maverick", "Grok 4.1", "DeepSeek V3.1",
                     "Qwen3-235B", "GLM-4.6", "Kimi K2",
                     "Mistral Large", "Mixtral 8×22B"))),
    language = factor(language, levels = c("English", "Chinese"))
  )
f6_segs <- f6_dat %>%
  select(model_label, language, mean_state_aligned) %>%
  pivot_wider(names_from = language, values_from = mean_state_aligned)

p6 <- ggplot(f6_dat, aes(x = mean_state_aligned, y = model_label,
                         shape = language, fill = language,
                         colour = model_label == "DeepSeek V3.1")) +
  geom_vline(xintercept = 0, colour = "grey60", linewidth = 0.4) +
  geom_segment(data = f6_segs,
               aes(x = English, xend = Chinese,
                   y = model_label, yend = model_label,
                   colour = model_label == "DeepSeek V3.1"),
               inherit.aes = FALSE, linewidth = 0.5, alpha = 0.55) +
  geom_point(size = 3, stroke = 0.6) +
  scale_colour_manual(values = c(`TRUE` = deepseek_color, `FALSE` = other_color),
                      guide = "none") +
  lang_shape + lang_fill +
  scale_x_continuous(limits = c(-2, 2), breaks = -2:2,
                     labels = c("−2\nanti-CCP", "−1", "0",
                                "+1", "+2\npro-CCP")) +
  labs(x = NULL, y = NULL) +
  pnas_theme
save_fig(p6, "pipeline/plots/fig_pnas_6_stance.png", width = 6.50, height = 4.80)
} else cat("F6 skipped: engaged state-alignment table not present in this run.\n")

cat("Wrote PNAS figures to pipeline/plots/ (F1, F2 always; F3-F6 when Study A/B tables present):\n",
    " fig_pnas_1_tasktype.pdf\n fig_pnas_2_deepseek_pilot.pdf\n",
    "fig_pnas_3_study_a.pdf\n fig_pnas_4_entity_swap.pdf\n",
    "fig_pnas_5_native_mt.pdf\n fig_pnas_6_stance.pdf\n", sep = "")
