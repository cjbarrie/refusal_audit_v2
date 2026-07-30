# =============================================================================
# Script 14: Pilot DeepSeek dotplots for the brief
# =============================================================================
# Two clean horizontal dotplots from the primary audit data, no CIs, no
# statistical test annotations. Designed for embedding in deepseek_brief.tex.
#
# Outputs:
#   plots/deepseek_brief_pilot_fig1_models_by_language.pdf
#       5 audit models x EN/ZH refusal on regular-tier prompts. Dot per
#       (model, language). DeepSeek highlighted.
#   plots/deepseek_brief_pilot_fig2_deepseek_by_category.pdf
#       DeepSeek's per-category refusal rate, EN vs ZH, regular tier.
#       Dot per (category, language). Connector segment shows the gap.
#
#   tables/36_pilot_deepseek_fig1.csv
#   tables/36_pilot_deepseek_fig2.csv
# =============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(scales)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes

# Cleaned pilot dataset assembled by 01_data_loading.R.
load("pipeline/data_clean.RData")

dir.create("pipeline/plots",  showWarnings = FALSE, recursive = TRUE)
dir.create("pipeline/tables", showWarnings = FALSE, recursive = TRUE)

deepseek_color <- "#c0392b"
other_color    <- "#7f8c8d"

model_label_lookup <- c(
  "deepseek-chat-v3.1"  = "DeepSeek V3.1",
  "gpt-5.1"             = "GPT-5.1",
  "claude-opus-4.5"     = "Claude Opus 4.5",
  "gpt-4o"              = "GPT-4o",
  "grok-4.3"            = "Grok 4.3",
  "qwen3-max"           = "Qwen3-Max",
  "mistral-large-2512"  = "Mistral Large 2512",
  "allam-7b"            = "ALLaM 7B",
  "jais-8b"             = "Jais 8B",
  "falcon3-10b"         = "Falcon3 10B"
)

# -----------------------------------------------------------------------------
# Pilot Fig 1: 5 audit models x EN/ZH refusal rate, regular tier
# -----------------------------------------------------------------------------
fig1_dat <- data_clean %>%
  filter(controversy_tier == "regular",
         prompt_language %in% c("en", "zh"),
         model %in% names(model_label_lookup)) %>%
  group_by(model, prompt_language) %>%
  summarise(refusal_rate = mean(refused), n = n(), .groups = "drop") %>%
  mutate(
    model_label = model_label_lookup[model],
    model_label = factor(model_label,
                         levels = rev(c("DeepSeek V3.1", "Qwen3-Max",
                                         "Grok 4.3", "GPT-5.1",
                                         "Claude Opus 4.5", "GPT-4o",
                                         "Mistral Large 2512"))),
    language = factor(prompt_language, levels = c("en", "zh"),
                      labels = c("English", "Chinese"))
  )

write_csv(fig1_dat, "pipeline/tables/36_pilot_deepseek_fig1.csv")

fig1_segs <- fig1_dat %>%
  select(model_label, language, refusal_rate) %>%
  pivot_wider(names_from = language, values_from = refusal_rate)

p_pilot_1 <- ggplot(fig1_dat,
                     aes(x = refusal_rate, y = model_label,
                         shape = language, fill = language,
                         colour = model_label == "DeepSeek V3.1")) +
  geom_segment(data = fig1_segs,
               aes(x = English, xend = Chinese,
                   y = model_label, yend = model_label,
                   colour = model_label == "DeepSeek V3.1"),
               inherit.aes = FALSE,
               linewidth = 0.6, alpha = 0.55) +
  geom_point(size = 3.5, stroke = 0.7) +
  scale_colour_manual(values = c(`TRUE` = deepseek_color,
                                  `FALSE` = other_color),
                      guide = "none") +
  scale_shape_manual(values = c(English = 21, Chinese = 24), name = NULL) +
  scale_fill_manual(values = c(English = "white", Chinese = deepseek_color),
                    name = NULL) +
  scale_x_continuous(labels = percent_format(accuracy = 1),
                     limits = c(0, NA),
                     expand = expansion(mult = c(0, 0.06))) +
  labs(
    title    = "Pilot audit: refusal rate on regular-tier political prompts",
    subtitle = "Five audit models, English (circle) vs Chinese (triangle).",
    x = "Refusal rate", y = NULL
  ) +
  theme_refusal(base_size = 11) +
  theme(panel.grid.major.y = element_blank(),
        legend.position    = "top")

ggsave("pipeline/plots/deepseek_brief_pilot_fig1_models_by_language.pdf",
       p_pilot_1, width = 7, height = 3.6)

# -----------------------------------------------------------------------------
# Pilot Fig 2: DeepSeek refusal by category, EN vs ZH, regular tier
# -----------------------------------------------------------------------------
# v2 topic-domain taxonomy (replaces the legacy task-type categories).
cat_pretty <- c(
  "territorial_sovereignty" = "Territorial sovereignty",
  "security_conflict"       = "Security / conflict",
  "governance_democracy"    = "Governance / democracy",
  "civil_rights_liberties"  = "Civil rights / liberties",
  "social_moral"            = "Social / moral",
  "economic_policy"         = "Economic policy",
  "religion_state"          = "Religion / state",
  "environment_energy"      = "Environment / energy",
  "migration_nationalism"   = "Migration / nationalism"
)

fig2_dat <- data_clean %>%
  filter(model == "deepseek-chat-v3.1",
         controversy_tier == "regular",
         prompt_language %in% c("en", "zh")) %>%
  group_by(prompt_category, prompt_language) %>%
  summarise(refusal_rate = mean(refused), n = n(), .groups = "drop") %>%
  mutate(
    cat_label = cat_pretty[prompt_category],
    language = factor(prompt_language, levels = c("en", "zh"),
                      labels = c("English", "Chinese"))
  )

# Order y by ZH refusal rate descending
zh_order <- fig2_dat %>%
  filter(language == "Chinese") %>%
  arrange(desc(refusal_rate)) %>%
  pull(cat_label)
fig2_dat <- fig2_dat %>%
  mutate(cat_label = factor(cat_label, levels = rev(zh_order)))

write_csv(fig2_dat, "pipeline/tables/36_pilot_deepseek_fig2.csv")

fig2_segs <- fig2_dat %>%
  select(cat_label, language, refusal_rate) %>%
  pivot_wider(names_from = language, values_from = refusal_rate)

p_pilot_2 <- ggplot(fig2_dat,
                     aes(x = refusal_rate, y = cat_label,
                         shape = language, fill = language)) +
  geom_segment(data = fig2_segs,
               aes(x = English, xend = Chinese,
                   y = cat_label, yend = cat_label),
               inherit.aes = FALSE,
               colour = deepseek_color, linewidth = 0.6, alpha = 0.55) +
  geom_point(size = 3.5, stroke = 0.7, colour = deepseek_color) +
  scale_shape_manual(values = c(English = 21, Chinese = 24), name = NULL) +
  scale_fill_manual(values  = c(English = "white", Chinese = deepseek_color),
                    name = NULL) +
  scale_x_continuous(labels = percent_format(accuracy = 1),
                     limits = c(0, NA),
                     expand = expansion(mult = c(0, 0.06))) +
  labs(
    title    = "Pilot audit: DeepSeek refusal rate by category, regular tier",
    subtitle = "English (circle) vs Chinese (triangle); categories ordered by Chinese rate.",
    x = "Refusal rate", y = NULL
  ) +
  theme_refusal(base_size = 11) +
  theme(panel.grid.major.y = element_blank(),
        legend.position    = "top")

ggsave("pipeline/plots/deepseek_brief_pilot_fig2_deepseek_by_category.pdf",
       p_pilot_2, width = 7, height = 4.2)

cat("Wrote 2 PDFs:\n")
cat("  plots/deepseek_brief_pilot_fig1_models_by_language.pdf\n")
cat("  plots/deepseek_brief_pilot_fig2_deepseek_by_category.pdf\n")

cat("\n=== Pilot fig 1 (5 models x EN/ZH on regular) ===\n")
print(fig1_dat %>% select(model, prompt_language, refusal_rate, n))

cat("\n=== Pilot fig 2 (DeepSeek by category) ===\n")
print(fig2_dat %>% select(prompt_category, prompt_language, refusal_rate, n))
