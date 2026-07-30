# =============================================================================
# Script 16: Engaged-only state-alignment, pooled across all stance data
# =============================================================================
# Pools stance scores from three sources:
#   - CN-addon (15 prompts x 11 Study A models x 2 langs)
#   - Study A originals CN-only (4 prompts x 11 models x 2 langs)
#   - Primary audit CN-sensitive (29 prompts x 5 audit models x 2 langs)
#
# Filters out engagement_code >= 4 (refused) records BEFORE computing state-
# alignment, because the stance rubric codes refusals as 0 stance regardless
# of underlying editorial position. Including refusals depresses the Chinese
# average toward 0 even when the underlying alignment matches the English
# response, producing a misleading EN > ZH gap. Engaged-only removes that
# artifact: it answers "when the model speaks, where does it land?"
#
# Outputs:
#   plots/fig_engaged_state_alignment.pdf
#   tables/37_engaged_state_alignment.csv
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
if (!file.exists("annotations/stance_study_a_cn.jsonl")) {
  cat("SKIP 16_engaged_state_alignment.R: required input (Study A CN stance scores) not present in this run.\n")
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
# Pool stance from three sources
# -----------------------------------------------------------------------------
stance_addon  <- read_jsonl("annotations/stance_study_a_cn.jsonl")
stance_orig   <- read_jsonl("annotations/stance_study_a_originals_cn.jsonl")
stance_pilot  <- read_jsonl("annotations/stance_pilot_cn.jsonl")

stance <- bind_rows(
  stance_addon  %>% mutate(source = "study_a_cn_addon"),
  stance_orig   %>% mutate(source = "study_a_originals"),
  stance_pilot  %>% mutate(source = "pilot")
) %>%
  filter(!is.na(stance_score))

cat(sprintf("Stance records: %d (addon=%d, originals=%d, pilot=%d)\n",
            nrow(stance), nrow(stance_addon), nrow(stance_orig), nrow(stance_pilot)))

# -----------------------------------------------------------------------------
# Pool engagement codes from corresponding response sources
# -----------------------------------------------------------------------------
ann_a <- read_jsonl("annotations/annotations_study_a.jsonl") %>%
  filter(!is.na(engagement_code)) %>%
  select(prompt_id, prompt_language, model, engagement_code)

# Pilot annotations live in annotations_all + annotations_{lang}_boundary
ann_pilot <- bind_rows(
  read_jsonl("annotations/annotations_all.jsonl"),
  map_dfr(c("en","zh"),
          ~ read_jsonl(sprintf("annotations/annotations_%s_boundary.jsonl", .x)))
) %>%
  filter(!is.na(engagement_code)) %>%
  select(prompt_id, prompt_language, model, engagement_code)

eng <- bind_rows(ann_a, ann_pilot) %>% distinct()

# -----------------------------------------------------------------------------
# Narrative map -> CCP-aligned direction per prompt
# -----------------------------------------------------------------------------
narr_yaml <- yaml::read_yaml("data/prompt_narrative_map.yaml")$prompts
narr_df <- tibble(
  prompt_id = names(narr_yaml),
  ccp_dir   = map_dbl(narr_yaml,
                      ~ ifelse(is.null(.x$ccp_aligned_stance),
                                NA_real_, .x$ccp_aligned_stance))
)

# -----------------------------------------------------------------------------
# Build engaged-only state-alignment dataset
# -----------------------------------------------------------------------------
dat <- stance %>%
  inner_join(narr_df, by = "prompt_id") %>%
  inner_join(eng,     by = c("prompt_id", "prompt_language", "model")) %>%
  filter(!is.na(ccp_dir),
         prompt_language %in% c("en", "zh"),
         engagement_code < 4) %>%        # ENGAGED ONLY -- refusals dropped
  mutate(state_aligned = stance_score * sign(ccp_dir))

cat(sprintf("\nEngaged + unambiguous-direction records: %d\n", nrow(dat)))
cat("Records by source:\n")
print(dat %>% count(source))

# -----------------------------------------------------------------------------
# Per-(model, language) mean state-alignment (engaged-only)
# -----------------------------------------------------------------------------
by_cell <- dat %>%
  group_by(model, prompt_language) %>%
  summarise(
    n_engaged          = n(),
    mean_state_aligned = mean(state_aligned),
    .groups = "drop"
  ) %>%
  mutate(
    language = factor(prompt_language, levels = c("en", "zh"),
                      labels = c("English", "Chinese"))
  )

# -----------------------------------------------------------------------------
# Jurisdiction lookup (from any prior response file)
# -----------------------------------------------------------------------------
jur_lookup <- c(
  "gpt-5.1"            = "us",
  "claude-opus-4.5"    = "us",
  "gpt-4o"             = "us",
  "gemini-2.5-pro"     = "us",
  "llama-4-maverick"   = "us",
  "grok-4.3"      = "us",
  "deepseek-chat-v3.1" = "china",
  "qwen3-235b"         = "china",
  "glm-4.6"            = "china",
  "kimi-k2"            = "china",
  "mistral-large"      = "eu",
  "mixtral-8x22b"      = "eu"
)
model_label_lookup <- c(
  "gpt-5.1"            = "GPT-5.1",
  "claude-opus-4.5"    = "Claude Opus 4.5",
  "gpt-4o"             = "GPT-4o",
  "gemini-2.5-pro"     = "Gemini 2.5 Pro",
  "llama-4-maverick"   = "Llama 4 Maverick",
  "grok-4.3"      = "Grok 4.3",
  "deepseek-chat-v3.1" = "DeepSeek V3.1",
  "qwen3-235b"         = "Qwen3-235B",
  "glm-4.6"            = "GLM-4.6",
  "kimi-k2"            = "Kimi K2",
  "mistral-large"      = "Mistral Large",
  "mixtral-8x22b"      = "Mixtral 8\u00d722B"
)

by_cell <- by_cell %>%
  mutate(
    jurisdiction = factor(jur_lookup[model],
                           levels = c("us", "china", "eu", "middle_east"),
                           labels = c("U.S.", "China", "EU", "Middle East")),
    model_label  = factor(model_label_lookup[model],
                           levels = rev(c(
                             "GPT-5.1", "Claude Opus 4.5", "GPT-4o",
                             "Gemini 2.5 Pro", "Llama 4 Maverick", "Grok 4.3",
                             "DeepSeek V3.1", "Qwen3-235B", "GLM-4.6", "Kimi K2",
                             "Mistral Large", "Mixtral 8\u00d722B"
                           )))
  )

write_csv(by_cell, "pipeline/tables/37_engaged_state_alignment.csv")

# -----------------------------------------------------------------------------
# Plot
# -----------------------------------------------------------------------------
deepseek_color <- "#c0392b"
other_color    <- "#7f8c8d"

segs <- by_cell %>%
  select(model_label, language, mean_state_aligned) %>%
  pivot_wider(names_from = language, values_from = mean_state_aligned)

p <- ggplot(by_cell,
            aes(x = mean_state_aligned, y = model_label,
                shape  = language, fill = language,
                colour = model_label == "DeepSeek V3.1")) +
  geom_vline(xintercept = 0, colour = "grey60", linewidth = 0.4) +
  geom_segment(data = segs,
               aes(x = English, xend = Chinese,
                   y = model_label, yend = model_label,
                   colour = model_label == "DeepSeek V3.1"),
               inherit.aes = FALSE,
               linewidth = 0.5, alpha = 0.55) +
  geom_point(size = 3, stroke = 0.6) +
  scale_colour_manual(values = c(`TRUE` = deepseek_color,
                                  `FALSE` = other_color),
                      guide = "none") +
  scale_shape_manual(values = c(English = 21, Chinese = 24), name = NULL) +
  scale_fill_manual(values = c(English = "white", Chinese = deepseek_color),
                    name = NULL) +
  scale_x_continuous(limits = c(-2, 2),
                     breaks = c(-2, -1, 0, 1, 2),
                     labels = c("\u22122\nanti-CCP", "\u22121", "0",
                                  "+1", "+2\npro-CCP")) +
  labs(
    title    = "Engaged-only state-alignment: where does each model land when it speaks?",
    subtitle = "Pooled stance across pilot audit + Study A; refusals excluded.",
    x = NULL, y = NULL
  ) +
  theme_refusal(base_size = 11) +
  theme(panel.grid.major.y = element_blank(),
        legend.position    = "top")

ggsave("pipeline/plots/fig_engaged_state_alignment.pdf", p,
       width = 7.5, height = 5)

cat("\nWrote: plots/fig_engaged_state_alignment.pdf\n")
cat("Wrote: tables/37_engaged_state_alignment.csv\n\n")

cat("=== Per-cell engaged-only state-alignment ===\n")
print(by_cell %>% select(model_label, prompt_language, n_engaged, mean_state_aligned)
        %>% arrange(model_label, prompt_language), n = Inf)
