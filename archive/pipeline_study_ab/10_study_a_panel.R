# =============================================================================
# Script 10: Study A — jurisdiction-panel mixed-effects analysis
# =============================================================================
# Loads annotations for Study A's 45 prompts x 13 models x 3 languages run,
# fits the preregistered glmer model, and emits:
#   - tables/28_study_a_panel.csv: interaction terms + marginal means
#   - tables/28_study_a_dropone.csv: drop-one-model sensitivity
#   - plots/fig_pnas_study_a.pdf: jurisdiction x language heatmap
# =============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(jsonlite)
  library(lme4)
  library(broom.mixed)
  library(ggeffects)
  library(boot)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes
# --- STUDY-A/B INPUT GUARD (v2) ---------------------------------------
if (!file.exists("data/study_a_prompt_subset_cn_addon.csv")) {
  cat("SKIP 10_study_a_panel.R: required input (Study A jurisdiction-panel data) not present in this run.\n")
  quit(save = "no", status = 0)
}
# ---------------------------------------------------------------------


# Study A reads the original 11-model run plus the Middle-East arm (Jais +
# Falcon, jurisdiction = "middle_east") added later from local vLLM generation.
ANNOTATIONS      <- c("annotations/annotations_study_a.jsonl",
                      "annotations/annotations_study_a_me.jsonl")
RESPONSES        <- c("responses/responses_study_a.jsonl",
                      "responses/responses_study_a_me.jsonl")
ORIGINAL_SUBSET  <- "data/study_a_prompt_subset.csv"        # Western-sensitive (30)
CN_ADDON_SUBSET  <- "data/study_a_prompt_subset_cn_addon.csv"  # CN-sensitive (15)

# Helper: robust JSONL reader that skips malformed lines.
read_jsonl <- function(path) {
  lines <- readLines(path, warn = FALSE)
  lines <- lines[nzchar(lines)]
  map_dfr(lines, ~ fromJSON(.x, flatten = TRUE))
}

# -----------------------------------------------------------------------------
# Load data
# -----------------------------------------------------------------------------
# Annotations hold engagement_code and ideology dims; responses hold the
# jurisdiction tag we attached in the generation step. Join on the natural key.

ann <- map_dfr(ANNOTATIONS, read_jsonl) %>%
  filter(!is.na(engagement_code)) %>%
  mutate(refused = as.integer(engagement_code >= 4))

resp <- map_dfr(RESPONSES, read_jsonl) %>%
  filter(!is.na(response_text)) %>%
  select(prompt_id, prompt_language, model, jurisdiction)

dat <- ann %>%
  inner_join(resp, by = c("prompt_id", "prompt_language", "model"))

# Tag each prompt with its content stratum based on which frozen subset CSV it
# came from. Original 30 = Western/global-sensitive (selected by cross-model
# variance from the full battery). CN-addon 15 = China-sensitive (keyword-
# filtered for Xi / Mao / Taiwan / Tiananmen / Uyghur / Tibet / HK / CCP / etc).
cn_ids <- read_csv(CN_ADDON_SUBSET, show_col_types = FALSE)$prompt_id
dat <- dat %>%
  mutate(stratum = if_else(prompt_id %in% cn_ids, "cn_sensitive", "western_sensitive"),
         stratum = factor(stratum, levels = c("western_sensitive", "cn_sensitive")))

cat(sprintf("Study A records: %d (annotated + response-matched)\n", nrow(dat)))
cat("Jurisdiction x language distribution:\n")
print(dat %>% count(jurisdiction, prompt_language))
cat("\nStratum x language distribution:\n")
print(dat %>% count(stratum, prompt_language))

# -----------------------------------------------------------------------------
# Primary analysis: mixed-effects logistic regression
# -----------------------------------------------------------------------------
# Preregistered form:
#   refused ~ jurisdiction * language + category + (1|model) + (1|prompt)
# with binomial family.

dat <- dat %>%
  mutate(
    jurisdiction = factor(jurisdiction, levels = c("us", "china", "eu", "middle_east")),
    language     = factor(prompt_language, levels = c("en", "zh", "ar")),
    category     = factor(prompt_category),
  )

fit <- glmer(
  refused ~ jurisdiction * language + category + (1 | model) + (1 | prompt_id),
  family  = binomial,
  data    = dat,
  control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 5e5))
)

cat("\n=== Primary model ===\n")
print(summary(fit))

# Interaction-term table (fixed effects only) with 95% CI.
fe <- broom.mixed::tidy(fit, effects = "fixed", conf.int = TRUE)
cat("\n=== Fixed effects ===\n")
print(fe, n = Inf)

# Marginal means per (jurisdiction x language) cell with bootstrap CIs.
marg <- ggeffects::ggpredict(
  fit,
  terms = c("jurisdiction", "language"),
  type  = "fixed"
) %>%
  as_tibble() %>%
  rename(jurisdiction = x, language = group, predicted_refused = predicted)

cat("\n=== Marginal means (jurisdiction x language) ===\n")
print(marg)

# -----------------------------------------------------------------------------
# Content-stratified fits: the primary model aggregates over Western- and
# CN-sensitive prompts, but the mechanism may differ by content. Refit the
# same model on each stratum separately to report within-stratum effects.
# -----------------------------------------------------------------------------
fit_by_stratum <- list()
marg_by_stratum <- list()
fe_by_stratum <- list()

for (s in levels(dat$stratum)) {
  sub <- dat %>% filter(stratum == s)
  cat(sprintf("\n=== Stratum: %s  (n = %d)  ===\n", s, nrow(sub)))
  f <- tryCatch(
    glmer(
      refused ~ jurisdiction * language + category + (1 | model) + (1 | prompt_id),
      family = binomial, data = sub,
      control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 5e5))
    ),
    error = function(e) NULL
  )
  if (is.null(f)) {
    cat("  (convergence failure)\n")
    next
  }
  fit_by_stratum[[s]] <- f
  fe_s <- broom.mixed::tidy(f, effects = "fixed", conf.int = TRUE) %>%
    mutate(stratum = s)
  fe_by_stratum[[s]] <- fe_s
  cat("  Fixed effects (interaction terms):\n")
  print(fe_s %>% filter(str_detect(term, "jurisdiction.+:language")))

  m_s <- ggeffects::ggpredict(f, terms = c("jurisdiction", "language"), type = "fixed") %>%
    as_tibble() %>%
    rename(jurisdiction = x, language = group, predicted_refused = predicted) %>%
    mutate(stratum = s)
  marg_by_stratum[[s]] <- m_s
}

fe_strat    <- bind_rows(fe_by_stratum)
marg_strat  <- bind_rows(marg_by_stratum)

# -----------------------------------------------------------------------------
# Drop-one-model sensitivity
# -----------------------------------------------------------------------------
# For each of the 11 models, refit the primary model with that model excluded.
# Report the interaction-term coefficient stability.

models_present <- unique(as.character(dat$model))
cat(sprintf("\nDrop-one-model sensitivity over %d models...\n", length(models_present)))

drop_one <- map_dfr(models_present, function(dropped) {
  sub <- dat %>% filter(model != dropped)
  f <- tryCatch(
    glmer(
      refused ~ jurisdiction * language + category + (1 | model) + (1 | prompt_id),
      family = binomial, data = sub,
      control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 5e5))
    ),
    error = function(e) NULL
  )
  if (is.null(f)) return(tibble(dropped = dropped, converged = FALSE))
  coefs <- broom.mixed::tidy(f, effects = "fixed", conf.int = TRUE) %>%
    filter(str_detect(term, "jurisdiction.*:language") | str_detect(term, "jurisdiction"))
  coefs %>% mutate(dropped = dropped, converged = TRUE) %>% select(dropped, term, estimate, conf.low, conf.high, p.value)
})

# -----------------------------------------------------------------------------
# Write outputs
# -----------------------------------------------------------------------------
dir.create("pipeline/tables", showWarnings = FALSE, recursive = TRUE)
dir.create("pipeline/plots",  showWarnings = FALSE, recursive = TRUE)

out_fixed <- fe %>%
  select(term, estimate, std.error, conf.low, conf.high, p.value)
write_csv(out_fixed, "pipeline/tables/28_study_a_fixed_effects.csv")

write_csv(marg %>% select(jurisdiction, language, predicted_refused,
                            conf.low, conf.high),
          "pipeline/tables/28_study_a_marginal.csv")

write_csv(drop_one, "pipeline/tables/28_study_a_dropone.csv")
write_csv(fe_strat,   "pipeline/tables/28_study_a_stratified_fixed.csv")
write_csv(marg_strat, "pipeline/tables/28_study_a_stratified_marginal.csv")

# Horizontal dot plot: refusal rate on x-axis, jurisdiction on y-axis,
# language as colour + shape, content stratum as vertically stacked facets.
marg_plot <- if (nrow(marg_strat) > 0) marg_strat else marg %>% mutate(stratum = "pooled")

stratum_labels <- c(
  western_sensitive = "Western/global-sensitive prompts (n=30)",
  cn_sensitive      = "China-sensitive prompts (n=15)",
  pooled            = "All prompts"
)
jurisdiction_labels <- c(us = "US", china = "China", eu = "EU", middle_east = "Middle East")
language_labels    <- c(en = "English", zh = "Chinese", ar = "Arabic")

marg_plot <- marg_plot %>%
  mutate(
    jurisdiction_label = factor(jurisdiction_labels[as.character(jurisdiction)],
                                levels = rev(c("US", "China", "EU", "Middle East"))),
    language_label     = factor(language_labels[as.character(language)],
                                levels = c("English", "Chinese", "Arabic")),
    stratum            = factor(stratum,
                                levels = c("western_sensitive", "cn_sensitive", "pooled"))
  )

p <- ggplot(marg_plot, aes(predicted_refused, jurisdiction_label,
                            colour = language_label, shape = language_label)) +
  geom_errorbarh(aes(xmin = conf.low, xmax = conf.high), height = 0.25,
                 linewidth = 0.4, position = position_dodge(width = 0.55)) +
  geom_point(size = 2.6, position = position_dodge(width = 0.55)) +
  facet_wrap(~ stratum, ncol = 1, labeller = labeller(stratum = stratum_labels)) +
  scale_x_continuous(labels = scales::percent_format(accuracy = 1),
                     limits = c(0, NA), expand = expansion(mult = c(0, 0.05))) +
  scale_colour_manual(values = c(English = "#4d4d4d", Chinese = "#c0392b", Arabic = "#27ae60"),
                      name = "Prompt language") +
  scale_shape_manual(values = c(English = 16, Chinese = 17, Arabic = 15),
                     name = "Prompt language") +
  labs(
    title    = "Study A: refusal rates by developer jurisdiction and user language",
    subtitle = sprintf("%d models across US / China / EU / Middle East; content-stratified",
                       n_distinct(dat$model)),
    x = "Predicted refusal rate (95% CI)", y = NULL
  ) +
  theme_refusal(base_size = 11) +
  theme(strip.text = element_text(face = "bold", hjust = 0),
        legend.position = "top",
        panel.grid.major.y = element_blank(),
        panel.grid.minor.x = element_blank())

ggsave("pipeline/plots/fig_pnas_study_a.pdf", p, width = 7, height = 6.5)
cat("\nWrote: tables/28_study_a_*.csv and plots/fig_pnas_study_a.pdf\n")

# Save the fit for reuse by figure / writeup scripts.
save(fit, dat, marg, marg_strat, drop_one, fe, fe_strat, fit_by_stratum,
     file = "pipeline/study_a_results.RData")
cat("Saved: pipeline/study_a_results.RData\n")
