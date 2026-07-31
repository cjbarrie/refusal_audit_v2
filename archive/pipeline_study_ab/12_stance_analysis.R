# =============================================================================
# Script 12: Stance + state-alignment analysis (Pass 4)
# =============================================================================
# Joins Pass 4 stance scores with Study A CN-sensitive responses, derives
# state-alignment using data/prompt_narrative_map.yaml, and reports:
#   * mean stance per (model x language) and per (jurisdiction x language)
#   * inter-judge kappa between primary (GPT-OSS 120B) and secondary (Command A)
#     on the IRR subset
#   * mixed-effects model: state_aligned_score ~ jurisdiction * language +
#       (1 | model) + (1 | prompt_id), restricted to prompts with non-null
#       ccp_aligned_stance
#
# Outputs:
#   tables/31_stance_by_cell.csv
#   tables/32_stance_irr.csv
#   tables/33_state_alignment_fit.csv
#   plots/fig_stance_heatmap.pdf
# =============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(jsonlite)
  library(yaml)
  library(lme4)
  library(lmerTest)        # provides p-values for lmer fixed effects
  library(broom.mixed)
  library(irr)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes
# --- STUDY-A/B INPUT GUARD (v2) ---------------------------------------
if (!file.exists("annotations/stance_study_a_cn.jsonl")) {
  cat("SKIP 12_stance_analysis.R: required input (Study A CN stance scores) not present in this run.\n")
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
# Load primary stance scores + narrative map + response metadata
# -----------------------------------------------------------------------------
stance <- read_jsonl("annotations/stance_study_a_cn.jsonl") %>%
  filter(!is.na(stance_score)) %>%
  rename(stance_primary = stance_score)

resp <- read_jsonl("responses/responses_study_a.jsonl") %>%
  filter(!is.na(response_text)) %>%
  select(prompt_id, prompt_language, model, jurisdiction)

narrative <- yaml::read_yaml("data/prompt_narrative_map.yaml")$prompts
narr_df <- tibble(
  prompt_id           = names(narrative),
  proposition         = map_chr(narrative, ~ .x$proposition %||% NA_character_),
  ccp_aligned_stance  = map_dbl(narrative, ~ ifelse(is.null(.x$ccp_aligned_stance), NA_real_, .x$ccp_aligned_stance))
)

cat(sprintf("Stance records: %d, narrative-mapped prompts: %d\n",
            nrow(stance), nrow(narr_df)))
cat(sprintf("Prompts with unambiguous CCP direction: %d\n",
            sum(!is.na(narr_df$ccp_aligned_stance))))

dat <- stance %>%
  inner_join(resp, by = c("prompt_id", "prompt_language", "model")) %>%
  inner_join(narr_df, by = "prompt_id") %>%
  mutate(jurisdiction = factor(jurisdiction, levels = c("us", "china", "eu", "middle_east")),
         language     = factor(prompt_language, levels = c("en", "zh")))

cat(sprintf("\nJoined dataset: %d records\n", nrow(dat)))

# -----------------------------------------------------------------------------
# Per-cell stance means
# -----------------------------------------------------------------------------
by_cell <- dat %>%
  group_by(model, jurisdiction, language) %>%
  summarise(
    n            = n(),
    mean_stance  = mean(stance_primary),
    .groups = "drop"
  )

cat("\n=== Mean stance by (model, language) ===\n")
print(by_cell %>% arrange(jurisdiction, model, language), n = Inf)

write_csv(by_cell, "pipeline/tables/31_stance_by_cell.csv")

# -----------------------------------------------------------------------------
# State-alignment score
# -----------------------------------------------------------------------------
# state_aligned = stance_primary * sign(ccp_aligned_stance)
# Mapped to: -2 (anti-CCP), -1 (weak anti), 0 (neutral/refusal), +1 (weak pro), +2 (strong pro)
dat_aligned <- dat %>%
  filter(!is.na(ccp_aligned_stance)) %>%
  mutate(state_aligned = stance_primary * sign(ccp_aligned_stance))

cat(sprintf("\nState-alignment subset: %d records (across %d prompts with unambiguous CCP direction)\n",
            nrow(dat_aligned), n_distinct(dat_aligned$prompt_id)))

cat("\n=== Mean state-alignment by (jurisdiction, language) ===\n")
sa_by_jur_lang <- dat_aligned %>%
  group_by(jurisdiction, language) %>%
  summarise(
    n              = n(),
    mean_aligned   = mean(state_aligned),
    se             = sd(state_aligned) / sqrt(n()),
    .groups = "drop"
  )
print(sa_by_jur_lang)
write_csv(sa_by_jur_lang, "pipeline/tables/31_state_alignment_by_jur_lang.csv")

# -----------------------------------------------------------------------------
# Mixed-effects regression on state-alignment (continuous outcome)
# -----------------------------------------------------------------------------
# Use lmer (linear mixed) since the -2..+2 outcome is approximately interval.
fit <- lmer(
  state_aligned ~ jurisdiction * language +
                  (1 | model) + (1 | prompt_id),
  data = dat_aligned
)

cat("\n=== state_aligned ~ jurisdiction * language ===\n")
fe <- broom.mixed::tidy(fit, effects = "fixed", conf.int = TRUE)
print(fe, n = Inf)
fe_out <- fe %>%
  mutate(p.value = if ("p.value" %in% names(.)) p.value else NA_real_) %>%
  select(any_of(c("term", "estimate", "std.error", "conf.low", "conf.high",
                   "statistic", "p.value")))
write_csv(fe_out, "pipeline/tables/33_state_alignment_fit.csv")

# -----------------------------------------------------------------------------
# Inter-judge agreement on the IRR sample
# -----------------------------------------------------------------------------
secondary <- read_jsonl("annotations/stance_study_a_cn_irr_command_a.jsonl") %>%
  filter(!is.na(stance_score)) %>%
  rename(stance_secondary = stance_score) %>%
  select(prompt_id, prompt_language, model, stance_secondary)

if (nrow(secondary) > 0) {
  paired <- inner_join(stance %>% select(prompt_id, prompt_language, model, stance_primary),
                        secondary,
                        by = c("prompt_id", "prompt_language", "model"))
  cat(sprintf("\nIRR paired records: %d\n", nrow(paired)))

  k_unweighted <- irr::kappa2(paired %>% select(stance_primary, stance_secondary), weight = "unweighted")
  k_linear     <- irr::kappa2(paired %>% select(stance_primary, stance_secondary), weight = "equal")
  k_squared    <- irr::kappa2(paired %>% select(stance_primary, stance_secondary), weight = "squared")
  exact        <- mean(paired$stance_primary == paired$stance_secondary)
  within1      <- mean(abs(paired$stance_primary - paired$stance_secondary) <= 1)

  irr_tbl <- tibble(
    statistic = c("Cohen's kappa (unweighted)",
                  "Cohen's kappa (linear-weighted)",
                  "Cohen's kappa (squared-weighted)",
                  "Exact agreement",
                  "Within-1 agreement"),
    value = c(k_unweighted$value, k_linear$value, k_squared$value, exact, within1),
    n     = c(k_unweighted$subjects, k_linear$subjects, k_squared$subjects, nrow(paired), nrow(paired))
  )
  cat("\n=== Inter-judge agreement (GPT-OSS 120B vs Command A) ===\n")
  print(irr_tbl)
  write_csv(irr_tbl, "pipeline/tables/32_stance_irr.csv")
} else {
  cat("\nNo secondary-judge data yet; skipping IRR.\n")
}

# -----------------------------------------------------------------------------
# Heatmap: state-alignment by (model, language)
# -----------------------------------------------------------------------------
plot_dat <- dat_aligned %>%
  group_by(model, jurisdiction, language) %>%
  summarise(mean_aligned = mean(state_aligned), n = n(), .groups = "drop") %>%
  mutate(model = fct_reorder(model, as.integer(jurisdiction) * 100 + match(model, sort(unique(model)))))

p <- ggplot(plot_dat, aes(x = language, y = model, fill = mean_aligned)) +
  geom_tile(color = "white", linewidth = 0.5) +
  geom_text(aes(label = sprintf("%+0.1f", mean_aligned)), size = 3) +
  scale_fill_gradient2(low = "#2c7fb8", mid = "#f7f7f7", high = "#c0392b",
                       midpoint = 0, limits = c(-2, 2),
                       name = "Mean state-alignment\n(-2 anti-CCP .. +2 pro-CCP)") +
  labs(
    title    = "State-alignment by model x language (Study A, CN-sensitive prompts)",
    subtitle = sprintf("%d responses on %d prompts with unambiguous CCP direction",
                       nrow(dat_aligned), n_distinct(dat_aligned$prompt_id)),
    x = "Prompt language", y = NULL
  ) +
  theme_refusal(base_size = 10) +
  theme(panel.grid = element_blank(),
        plot.subtitle = element_text(face = "italic"))

ggsave("pipeline/plots/fig_stance_heatmap.pdf", p, width = 7, height = 5)
cat("\nWrote: tables/31_*, tables/32_stance_irr.csv, tables/33_state_alignment_fit.csv\n")
cat("Wrote: plots/fig_stance_heatmap.pdf\n")
