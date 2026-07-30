# =============================================================================
# Script 13: DeepSeek brief — four dotplots
# =============================================================================
# Standalone dotplot figures for `deepseek_brief.tex`. No CIs (point estimates
# only). Outcome on x-axis, model / categorical variable on y-axis. Reuses
# existing CSV / JSONL outputs from earlier scripts; no new annotation work.
#
# Outputs:
#   plots/deepseek_brief_fig1_refusal.pdf
#   plots/deepseek_brief_fig2_state_alignment.pdf
#   plots/deepseek_brief_fig3_entity_swap.pdf
#   plots/deepseek_brief_fig4_register.pdf
#
#   tables/34_deepseek_brief_fig{1..4}.csv
# =============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(jsonlite)
  library(yaml)
  library(scales)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes
# --- STUDY-A/B INPUT GUARD (v2) ---------------------------------------
if (!file.exists("annotations/annotations_study_a.jsonl")) {
  cat("SKIP 13_deepseek_dotplots.R: required input (Study A annotations) not present in this run.\n")
  quit(save = "no", status = 0)
}
# ---------------------------------------------------------------------


read_jsonl <- function(path) {
  if (!file.exists(path)) return(tibble())
  lines <- readLines(path, warn = FALSE)
  lines <- lines[nzchar(lines)]
  if (length(lines) == 0) return(tibble())
  map_dfr(lines, ~ fromJSON(.x, flatten = TRUE))
}

dir.create("pipeline/plots",  showWarnings = FALSE, recursive = TRUE)
dir.create("pipeline/tables", showWarnings = FALSE, recursive = TRUE)

CN_MODELS <- c("deepseek-chat-v3.1", "qwen3-235b", "glm-4.6", "kimi-k2")

# Pretty model labels with DeepSeek at top.
model_label_lookup <- c(
  "deepseek-chat-v3.1" = "DeepSeek V3.1",
  "qwen3-235b"         = "Qwen3-235B",
  "glm-4.6"            = "GLM-4.6",
  "kimi-k2"            = "Kimi K2",
  "claude-opus-4.5"    = "Claude Opus 4.5",
  "gpt-5.1"            = "GPT-5.1"
)

# DeepSeek-emphasis: bold deeper red dot/segment for DeepSeek; muted grey for the rest.
deepseek_color <- "#c0392b"
other_color    <- "#7f8c8d"
en_shape <- 21   # filled circle outline
zh_shape <- 24   # filled triangle

# -----------------------------------------------------------------------------
# Fig 1 — Study A CN-sensitive refusal rate, across China-origin models
# -----------------------------------------------------------------------------
ann_a <- read_jsonl("annotations/annotations_study_a.jsonl") %>%
  filter(!is.na(engagement_code))
cn_ids <- read_csv("data/study_a_prompt_subset_cn_addon.csv",
                    show_col_types = FALSE)$prompt_id

fig1_dat <- ann_a %>%
  filter(prompt_id %in% cn_ids,
         model %in% CN_MODELS,
         prompt_language %in% c("en", "zh")) %>%
  group_by(model, prompt_language) %>%
  summarise(
    refusal_rate = mean(engagement_code >= 4),
    n = n(),
    .groups = "drop"
  ) %>%
  mutate(
    model_label = model_label_lookup[model],
    model_label = factor(model_label,
                         levels = rev(c("DeepSeek V3.1", "Qwen3-235B",
                                         "GLM-4.6", "Kimi K2"))),
    language = factor(prompt_language, levels = c("en", "zh"),
                      labels = c("English", "Chinese"))
  )

write_csv(fig1_dat, "pipeline/tables/34_deepseek_brief_fig1.csv")

# Connector segments per model (EN -> ZH).
fig1_segs <- fig1_dat %>%
  select(model_label, language, refusal_rate) %>%
  pivot_wider(names_from = language, values_from = refusal_rate)

p1 <- ggplot(fig1_dat,
             aes(x = refusal_rate, y = model_label,
                 colour = model_label == "DeepSeek V3.1",
                 shape  = language, fill = language)) +
  geom_segment(data = fig1_segs,
               aes(x = English, xend = Chinese,
                   y = model_label, yend = model_label,
                   colour = model_label == "DeepSeek V3.1"),
               inherit.aes = FALSE,
               linewidth = 0.6, alpha = 0.6) +
  geom_point(size = 4, stroke = 0.7) +
  scale_colour_manual(values = c(`TRUE` = deepseek_color, `FALSE` = other_color),
                      guide = "none") +
  scale_shape_manual(values = c(English = en_shape, Chinese = zh_shape),
                     name = NULL) +
  scale_fill_manual(values = c(English = "white", Chinese = deepseek_color),
                    name = NULL) +
  scale_x_continuous(labels = percent_format(accuracy = 1),
                     limits = c(0, NA),
                     expand = expansion(mult = c(0, 0.08))) +
  labs(
    title    = "Study A: refusal rate on China-sensitive prompts",
    subtitle = "Four China-origin models. Each line connects English (circle) to Chinese (triangle).",
    x = "Refusal rate", y = NULL
  ) +
  theme_refusal(base_size = 11) +
  theme(panel.grid.major.y = element_blank(),
        legend.position = "top")

ggsave("pipeline/plots/deepseek_brief_fig1_refusal.pdf", p1,
       width = 7, height = 4)

# -----------------------------------------------------------------------------
# Fig 2 — Study A CN-sensitive state-alignment, across China-origin models
# -----------------------------------------------------------------------------
stance <- read_jsonl("annotations/stance_study_a_cn.jsonl") %>%
  filter(!is.na(stance_score))

narr_yaml <- yaml::read_yaml("data/prompt_narrative_map.yaml")$prompts
narr_df <- tibble(
  prompt_id = names(narr_yaml),
  ccp_dir   = map_dbl(narr_yaml,
                      ~ ifelse(is.null(.x$ccp_aligned_stance),
                                NA_real_, .x$ccp_aligned_stance))
)

fig2_dat <- stance %>%
  inner_join(narr_df, by = "prompt_id") %>%
  filter(!is.na(ccp_dir),
         model %in% CN_MODELS,
         prompt_language %in% c("en", "zh")) %>%
  mutate(state_aligned = stance_score * sign(ccp_dir)) %>%
  group_by(model, prompt_language) %>%
  summarise(
    mean_state_aligned = mean(state_aligned),
    n = n(),
    .groups = "drop"
  ) %>%
  mutate(
    model_label = model_label_lookup[model],
    model_label = factor(model_label,
                         levels = rev(c("DeepSeek V3.1", "Qwen3-235B",
                                         "GLM-4.6", "Kimi K2"))),
    language = factor(prompt_language, levels = c("en", "zh"),
                      labels = c("English", "Chinese"))
  )

write_csv(fig2_dat, "pipeline/tables/34_deepseek_brief_fig2.csv")

fig2_segs <- fig2_dat %>%
  select(model_label, language, mean_state_aligned) %>%
  pivot_wider(names_from = language, values_from = mean_state_aligned)

p2 <- ggplot(fig2_dat,
             aes(x = mean_state_aligned, y = model_label,
                 colour = model_label == "DeepSeek V3.1",
                 shape  = language, fill = language)) +
  geom_vline(xintercept = 0, colour = "grey60", linewidth = 0.4) +
  geom_segment(data = fig2_segs,
               aes(x = English, xend = Chinese,
                   y = model_label, yend = model_label,
                   colour = model_label == "DeepSeek V3.1"),
               inherit.aes = FALSE,
               linewidth = 0.6, alpha = 0.6) +
  geom_point(size = 4, stroke = 0.7) +
  scale_colour_manual(values = c(`TRUE` = deepseek_color, `FALSE` = other_color),
                      guide = "none") +
  scale_shape_manual(values = c(English = en_shape, Chinese = zh_shape),
                     name = NULL) +
  scale_fill_manual(values = c(English = "white", Chinese = deepseek_color),
                    name = NULL) +
  scale_x_continuous(limits = c(-2, 2),
                     breaks = c(-2, -1, 0, 1, 2),
                     labels = c("-2\nanti-CCP", "-1", "0", "+1", "+2\npro-CCP")) +
  labs(
    title    = "Study A: pro-CCP stance on China-sensitive prompts",
    subtitle = "Mean state-alignment (\u22122 anti-CCP \u2026 +2 pro-CCP), 9 unambiguous-direction prompts.",
    x = NULL, y = NULL
  ) +
  theme_refusal(base_size = 11) +
  theme(panel.grid.major.y = element_blank(),
        legend.position = "top")

ggsave("pipeline/plots/deepseek_brief_fig2_state_alignment.pdf", p2,
       width = 7, height = 4)

# -----------------------------------------------------------------------------
# Fig 3 — Study B-refined: DeepSeek refusal rate by entity country
# -----------------------------------------------------------------------------
entity_label_map <- c(
  CN = "Xi Jinping (CN)",
  RU = "Putin (RU)",
  NK = "Kim Jong Un (NK)",
  DE = "Merkel (DE)",
  UK = "Thatcher (UK)",
  US = "Washington (US)"
)

fig3_dat <- read_csv("pipeline/tables/30_study_b_refined.csv",
                      show_col_types = FALSE) %>%
  filter(model == "deepseek-chat-v3.1",
         entity_country %in% names(entity_label_map)) %>%
  mutate(
    entity_label = entity_label_map[entity_country],
    language     = factor(prompt_language, levels = c("en", "zh"),
                           labels = c("English", "Chinese"))
  )

# Order y by ZH refusal rate descending so the steepest entries sit on top.
zh_order <- fig3_dat %>%
  filter(language == "Chinese") %>%
  arrange(desc(refusal_rate)) %>%
  pull(entity_label)
fig3_dat <- fig3_dat %>%
  mutate(entity_label = factor(entity_label, levels = rev(zh_order)))

write_csv(fig3_dat, "pipeline/tables/34_deepseek_brief_fig3.csv")

fig3_segs <- fig3_dat %>%
  select(entity_label, language, refusal_rate) %>%
  pivot_wider(names_from = language, values_from = refusal_rate)

p3 <- ggplot(fig3_dat,
             aes(x = refusal_rate, y = entity_label,
                 shape = language, fill = language)) +
  geom_segment(data = fig3_segs,
               aes(x = English, xend = Chinese,
                   y = entity_label, yend = entity_label),
               inherit.aes = FALSE,
               colour = deepseek_color, linewidth = 0.6, alpha = 0.6) +
  geom_point(size = 4, stroke = 0.7, colour = deepseek_color) +
  scale_shape_manual(values = c(English = en_shape, Chinese = zh_shape),
                     name = NULL) +
  scale_fill_manual(values = c(English = "white", Chinese = deepseek_color),
                    name = NULL) +
  scale_x_continuous(labels = percent_format(accuracy = 1),
                     limits = c(0, NA),
                     expand = expansion(mult = c(0, 0.08))) +
  labs(
    title    = "Study B-refined: DeepSeek refusal by entity (single-token swap)",
    subtitle = "Same template, single proper-noun swap. English (circle), Chinese (triangle).",
    x = "Refusal rate", y = NULL
  ) +
  theme_refusal(base_size = 11) +
  theme(panel.grid.major.y = element_blank(),
        legend.position = "top")

ggsave("pipeline/plots/deepseek_brief_fig3_entity_swap.pdf", p3,
       width = 7, height = 4.2)

# -----------------------------------------------------------------------------
# Fig 4 — Study B-orig: refusal rate by variant, DeepSeek + 3 controls
# -----------------------------------------------------------------------------
ann_b <- read_jsonl("annotations/annotations_study_b_orig.jsonl") %>%
  filter(!is.na(engagement_code))
resp_b <- read_jsonl("responses/responses_study_b_orig.jsonl") %>%
  select(prompt_id, prompt_language, model, variant)

fig4_dat <- ann_b %>%
  inner_join(resp_b, by = c("prompt_id", "prompt_language", "model")) %>%
  filter(model %in% c("deepseek-chat-v3.1", "qwen3-235b",
                       "claude-opus-4.5", "gpt-5.1")) %>%
  group_by(model, variant) %>%
  summarise(
    refusal_rate = mean(engagement_code >= 4),
    n = n(),
    .groups = "drop"
  ) %>%
  mutate(
    model_label = model_label_lookup[model],
    model_label = factor(model_label,
                         levels = c("DeepSeek V3.1", "Qwen3-235B",
                                     "Claude Opus 4.5", "GPT-5.1")),
    variant = factor(variant,
                     levels = rev(c("native_en", "mt_en", "mt_zh", "native_zh")),
                     labels = rev(c("Native English",
                                     "MT English (from ZH)",
                                     "MT Chinese (from EN)",
                                     "Native Chinese")))
  )

write_csv(fig4_dat, "pipeline/tables/34_deepseek_brief_fig4.csv")

p4 <- ggplot(fig4_dat,
             aes(x = refusal_rate, y = variant,
                 colour = model_label == "DeepSeek V3.1")) +
  geom_point(size = 3.5) +
  facet_wrap(~ model_label, ncol = 1, strip.position = "top") +
  scale_colour_manual(values = c(`TRUE` = deepseek_color, `FALSE` = other_color),
                      guide = "none") +
  scale_x_continuous(labels = percent_format(accuracy = 1),
                     limits = c(0, NA),
                     expand = expansion(mult = c(0, 0.08))) +
  labs(
    title    = "Study B-orig: refusal rate by prompt variant",
    subtitle = "Same semantic content (back-translation chrF \u2265 0.4); native vs.\ Google-translated registers.",
    x = "Refusal rate", y = NULL
  ) +
  theme_refusal(base_size = 11) +
  theme(panel.grid.major.y = element_blank(),
        strip.text = element_text(face = "bold", hjust = 0))

ggsave("pipeline/plots/deepseek_brief_fig4_register.pdf", p4,
       width = 7, height = 6)

cat("Wrote 4 PDFs:\n")
cat("  plots/deepseek_brief_fig1_refusal.pdf\n")
cat("  plots/deepseek_brief_fig2_state_alignment.pdf\n")
cat("  plots/deepseek_brief_fig3_entity_swap.pdf\n")
cat("  plots/deepseek_brief_fig4_register.pdf\n")
cat("Wrote 4 summary tables: tables/34_deepseek_brief_fig{1..4}.csv\n")

# Quick sanity check.
cat("\n=== Sanity check on fig1 (Study A CN-sensitive refusal) ===\n")
print(fig1_dat %>% select(model, prompt_language, refusal_rate, n))
cat("\n=== Sanity check on fig2 (Study A CN-sensitive state-alignment) ===\n")
print(fig2_dat %>% select(model, prompt_language, mean_state_aligned, n))
cat("\n=== Sanity check on fig3 (DeepSeek B-refined entity refusal) ===\n")
print(fig3_dat %>% select(entity_country, prompt_language, refusal_rate, n))
cat("\n=== Sanity check on fig4 (B-orig variant refusal) ===\n")
print(fig4_dat %>% select(model, variant, refusal_rate, n))
