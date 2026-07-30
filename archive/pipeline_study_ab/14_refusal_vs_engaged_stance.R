# =============================================================================
# Script 14: "Refusal vs.\ engaged stance" — the core-argument figure
# =============================================================================
# Two-panel horizontal dotplot showing both dimensions of the editorial
# argument simultaneously:
#   Panel A: refusal rate per (model x language) on CN-sensitive prompts.
#   Panel B: engaged-only mean state-alignment per (model x language) on the
#            9 unambiguous-direction CN-sensitive prompts.
#
# All 11 Study A models, grouped by developer jurisdiction (US / China / EU).
# DeepSeek V3.1 highlighted. EN <-> ZH connector segments per model.
#
# Outputs:
#   plots/fig_refusal_vs_engaged_stance.pdf
#   tables/35_refusal_vs_engaged_stance.csv
# =============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(jsonlite)
  library(yaml)
  library(scales)
  library(patchwork)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes
# --- STUDY-A/B INPUT GUARD (v2) ---------------------------------------
if (!file.exists("annotations/annotations_study_a.jsonl")) {
  cat("SKIP 14_refusal_vs_engaged_stance.R: required input (Study A annotations) not present in this run.\n")
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

# -----------------------------------------------------------------------------
# Inputs: Study A annotations + Pass-4 stance + narrative map
# -----------------------------------------------------------------------------
ann <- read_jsonl("annotations/annotations_study_a.jsonl") %>%
  filter(!is.na(engagement_code)) %>%
  select(prompt_id, prompt_language, model, engagement_code)

resp <- read_jsonl("responses/responses_study_a.jsonl") %>%
  filter(!is.na(response_text)) %>%
  select(prompt_id, prompt_language, model, jurisdiction) %>%
  distinct()

stance <- read_jsonl("annotations/stance_study_a_cn.jsonl") %>%
  filter(!is.na(stance_score)) %>%
  select(prompt_id, prompt_language, model, stance_score)

cn_ids <- read_csv("data/study_a_prompt_subset_cn_addon.csv",
                    show_col_types = FALSE)$prompt_id

narr_yaml <- yaml::read_yaml("data/prompt_narrative_map.yaml")$prompts
narr_df <- tibble(
  prompt_id = names(narr_yaml),
  ccp_dir   = map_dbl(narr_yaml,
                      ~ ifelse(is.null(.x$ccp_aligned_stance),
                                NA_real_, .x$ccp_aligned_stance))
)

# -----------------------------------------------------------------------------
# Refusal rate on the 15-prompt CN-sensitive stratum, EN + ZH only.
# -----------------------------------------------------------------------------
refusal <- ann %>%
  filter(prompt_id %in% cn_ids,
         prompt_language %in% c("en", "zh")) %>%
  inner_join(resp, by = c("prompt_id", "prompt_language", "model")) %>%
  group_by(model, jurisdiction, prompt_language) %>%
  summarise(refusal_rate = mean(engagement_code >= 4),
            n = n(), .groups = "drop")

# -----------------------------------------------------------------------------
# Engaged-only mean state-alignment on the 9 unambiguous CN-sensitive prompts.
# State-alignment = stance * sign(ccp_aligned_stance).
# Engaged = engagement_code < 4.
# -----------------------------------------------------------------------------
engaged_stance <- stance %>%
  inner_join(narr_df, by = "prompt_id") %>%
  inner_join(ann,    by = c("prompt_id", "prompt_language", "model")) %>%
  inner_join(resp,   by = c("prompt_id", "prompt_language", "model")) %>%
  filter(!is.na(ccp_dir),
         prompt_language %in% c("en", "zh"),
         engagement_code < 4) %>%
  mutate(state_aligned = stance_score * sign(ccp_dir)) %>%
  group_by(model, jurisdiction, prompt_language) %>%
  summarise(mean_engaged_alignment = mean(state_aligned),
            n_engaged = n(), .groups = "drop")

# -----------------------------------------------------------------------------
# Combine and order. DeepSeek-first ordering within China; jurisdiction order
# US -> China -> EU.
# -----------------------------------------------------------------------------
model_label_lookup <- c(
  "gpt-5.1"            = "GPT-5.1",
  "claude-opus-4.5"    = "Claude Opus 4.5",
  "gpt-4o"             = "GPT-4o",
  "gemini-2.5-pro"     = "Gemini 2.5 Pro",
  "llama-4-maverick"   = "Llama 4 Maverick",
  "deepseek-chat-v3.1" = "DeepSeek V3.1",
  "qwen3-235b"         = "Qwen3-235B",
  "glm-4.6"            = "GLM-4.6",
  "kimi-k2"            = "Kimi K2",
  "mistral-large"      = "Mistral Large",
  "mixtral-8x22b"      = "Mixtral 8\u00d722B"
)

# Y-axis order: US (5) -> China (4, DeepSeek first) -> EU (2). Reversed so
# top of plot = US first.
y_order <- rev(c(
  "GPT-5.1", "Claude Opus 4.5", "GPT-4o", "Gemini 2.5 Pro", "Llama 4 Maverick",
  "DeepSeek V3.1", "Qwen3-235B", "GLM-4.6", "Kimi K2",
  "Mistral Large", "Mixtral 8\u00d722B"
))

prep_panel <- function(df, value_col) {
  df %>%
    mutate(
      model_label = model_label_lookup[model],
      model_label = factor(model_label, levels = y_order),
      jurisdiction = factor(jurisdiction, levels = c("us", "china", "eu", "middle_east"),
                            labels = c("U.S.", "China", "EU", "Middle East")),
      language = factor(prompt_language, levels = c("en", "zh"),
                        labels = c("English", "Chinese")),
      is_deepseek = model == "deepseek-chat-v3.1"
    )
}

panel_a_dat <- prep_panel(refusal,          "refusal_rate")
panel_b_dat <- prep_panel(engaged_stance,   "mean_engaged_alignment")

# Connector segments (EN -> ZH per model).
panel_a_seg <- panel_a_dat %>%
  select(model_label, is_deepseek, language, refusal_rate) %>%
  pivot_wider(names_from = language, values_from = refusal_rate)

panel_b_seg <- panel_b_dat %>%
  select(model_label, is_deepseek, language, mean_engaged_alignment) %>%
  pivot_wider(names_from = language, values_from = mean_engaged_alignment)

# -----------------------------------------------------------------------------
# Combined long table for record (writes to CSV).
# -----------------------------------------------------------------------------
combined <- refusal %>%
  rename(refused_n = n) %>%
  full_join(engaged_stance,
            by = c("model", "jurisdiction", "prompt_language")) %>%
  arrange(jurisdiction, model, prompt_language)

write_csv(combined, "pipeline/tables/35_refusal_vs_engaged_stance.csv")

# -----------------------------------------------------------------------------
# Plot
# -----------------------------------------------------------------------------
deepseek_color <- "#c0392b"
other_color    <- "#7f8c8d"

panel_theme <- theme_refusal(base_size = 10) +
  theme(panel.grid.major.y = element_blank(),
        panel.grid.minor   = element_blank(),
        axis.title.y       = element_blank(),
        plot.subtitle      = element_text(size = 9, face = "italic",
                                            margin = margin(b = 4)),
        legend.position    = "top",
        legend.box.spacing = unit(0, "pt"),
        legend.margin      = margin(t = 0, b = 0))

# Panel A: refusal rate
p_a <- ggplot(panel_a_dat,
              aes(x = refusal_rate, y = model_label,
                  shape = language, fill = language,
                  colour = is_deepseek)) +
  geom_segment(data = panel_a_seg,
               aes(x = English, xend = Chinese,
                   y = model_label, yend = model_label,
                   colour = is_deepseek),
               inherit.aes = FALSE,
               linewidth = 0.5, alpha = 0.55) +
  geom_point(size = 3, stroke = 0.6) +
  scale_colour_manual(values = c(`TRUE` = deepseek_color,
                                  `FALSE` = other_color),
                      guide = "none") +
  scale_shape_manual(values = c(English = 21, Chinese = 24), name = NULL) +
  scale_fill_manual(values  = c(English = "white", Chinese = deepseek_color),
                    name = NULL) +
  scale_x_continuous(labels = percent_format(accuracy = 1),
                     limits = c(0, NA),
                     expand = expansion(mult = c(0, 0.06))) +
  labs(
    title    = "(A) How often does each model refuse?",
    subtitle = "Refusal rate on the 15-prompt China-sensitive stratum, by language.",
    x = "Refusal rate"
  ) +
  panel_theme

# Panel B: engaged-only state-alignment
p_b <- ggplot(panel_b_dat,
              aes(x = mean_engaged_alignment, y = model_label,
                  shape = language, fill = language,
                  colour = is_deepseek)) +
  geom_vline(xintercept = 0, colour = "grey60", linewidth = 0.4) +
  geom_segment(data = panel_b_seg,
               aes(x = English, xend = Chinese,
                   y = model_label, yend = model_label,
                   colour = is_deepseek),
               inherit.aes = FALSE,
               linewidth = 0.5, alpha = 0.55) +
  geom_point(size = 3, stroke = 0.6) +
  scale_colour_manual(values = c(`TRUE` = deepseek_color,
                                  `FALSE` = other_color),
                      guide = "none") +
  scale_shape_manual(values = c(English = 21, Chinese = 24), name = NULL) +
  scale_fill_manual(values  = c(English = "white", Chinese = deepseek_color),
                    name = NULL) +
  scale_x_continuous(limits = c(-2, 2),
                     breaks = c(-2, -1, 0, 1, 2),
                     labels = c("\u22122\nanti-CCP", "\u22121", "0",
                                  "+1", "+2\npro-CCP")) +
  labs(
    title    = "(B) When the model does engage, where does it land?",
    subtitle = "Mean state-alignment of non-refused responses (9 unambiguous-direction prompts).",
    x = NULL
  ) +
  panel_theme +
  theme(axis.text.y = element_blank())   # share Panel A's labels

# Combine: stack vertically with shared y-axis. Use 2-column layout so the
# panels sit side by side (the y-labels appear once on the left).
fig <- p_a + p_b + plot_layout(ncol = 2, guides = "collect") &
  theme(legend.position = "top")

ggsave("pipeline/plots/fig_refusal_vs_engaged_stance.pdf", fig,
       width = 11, height = 5.5)

cat("Wrote: plots/fig_refusal_vs_engaged_stance.pdf\n")
cat("Wrote: tables/35_refusal_vs_engaged_stance.csv\n")
print(combined, n = Inf)
