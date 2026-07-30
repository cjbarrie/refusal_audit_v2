# =============================================================================
# Script 11: Study B — language register (B-orig) and entity-swap (B-refined)
# =============================================================================
# B-orig analysis (Part 1): within-model paired-prompt mixed model contrasting
#   refusal probability across native_en / mt_en / native_zh / mt_zh variants.
# B-refined analysis (Part 2): within-prompt mixed model contrasting refusal
#   across entity variants holding template + language constant.
#
# Outputs:
#   tables/29_study_b_orig.csv
#   tables/30_study_b_refined.csv
#   plots/fig_pnas_study_b.pdf  (B-orig forest + B-refined heatmap)
# =============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(jsonlite)
  library(lme4)
  library(broom.mixed)
  library(ggeffects)
  library(patchwork)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
source("pipeline/_theme.R")  # shared publication theme + validated palettes

read_jsonl <- function(path) {
  if (!file.exists(path)) return(tibble())
  lines <- readLines(path, warn = FALSE); lines <- lines[nzchar(lines)]
  if (length(lines) == 0) return(tibble())
  map_dfr(lines, ~ fromJSON(.x, flatten = TRUE))
}

safe_ann <- function(df) {
  if (nrow(df) == 0 || !"engagement_code" %in% names(df)) return(tibble())
  df %>% filter(!is.na(engagement_code)) %>%
    mutate(refused = as.integer(engagement_code >= 4))
}
safe_resp <- function(df) {
  if (nrow(df) == 0 || !"response_text" %in% names(df)) return(tibble())
  df %>% filter(!is.na(response_text))
}

# -----------------------------------------------------------------------------
# Load + join annotations with response metadata (jurisdiction, variant, etc.)
# -----------------------------------------------------------------------------
ann_refined  <- safe_ann(read_jsonl("annotations/annotations_study_b_refined.jsonl"))
resp_refined <- safe_resp(read_jsonl("responses/responses_study_b_refined.jsonl"))
ann_orig     <- safe_ann(read_jsonl("annotations/annotations_study_b_orig.jsonl"))
resp_orig    <- safe_resp(read_jsonl("responses/responses_study_b_orig.jsonl"))

# -----------------------------------------------------------------------------
# PART 1: Study B-orig (native vs MT)
# -----------------------------------------------------------------------------
if (nrow(ann_orig) > 0 && nrow(resp_orig) > 0) {
  # Re-derive `variant` from the response metadata via prompt_id, which was
  # constructed as "{pair_id}_{variant}" in the runner.
  dat_orig <- ann_orig %>%
    inner_join(
      resp_orig %>%
        select(prompt_id, model, prompt_language, variant, pair_id,
               qn_type, entity_country, model_jurisdiction),
      by = c("prompt_id", "model", "prompt_language")
    ) %>%
    mutate(variant = factor(variant,
                             levels = c("native_en", "mt_en", "native_zh", "mt_zh")))

  cat(sprintf("Study B-orig: %d records across %d pairs x %d models\n",
              nrow(dat_orig),
              n_distinct(dat_orig$pair_id),
              n_distinct(dat_orig$model)))

  # Per-model model: refused ~ variant + (1|pair_id). Report the key
  # native_zh − mt_zh contrast across models.
  fit_per_model <- dat_orig %>%
    group_split(model) %>%
    map_dfr(function(d) {
      if (n_distinct(d$variant) < 4 || sum(d$refused) < 2 ||
          sum(!d$refused) < 2) {
        return(tibble(model = d$model[1], term = NA, estimate = NA,
                      conf.low = NA, conf.high = NA, p.value = NA,
                      note = "insufficient variation"))
      }
      f <- tryCatch(glmer(refused ~ variant + (1 | pair_id),
                           family = binomial, data = d,
                           control = glmerControl(optimizer = "bobyqa",
                                                   optCtrl = list(maxfun = 1e5))),
                     error = function(e) NULL)
      if (is.null(f)) {
        return(tibble(model = d$model[1], term = NA, estimate = NA,
                      conf.low = NA, conf.high = NA, p.value = NA,
                      note = "convergence failure"))
      }
      broom.mixed::tidy(f, effects = "fixed", conf.int = TRUE) %>%
        filter(grepl("^variant", term)) %>%
        mutate(model = d$model[1], note = "") %>%
        select(model, term, estimate, conf.low, conf.high, p.value, note)
    })

  write_csv(fit_per_model, "pipeline/tables/29_study_b_orig.csv")
  cat("Wrote: tables/29_study_b_orig.csv\n")
} else {
  cat("Skipping B-orig (no annotation data yet)\n")
  fit_per_model <- NULL
}

# -----------------------------------------------------------------------------
# PART 2: Study B-refined (entity-swap)
# -----------------------------------------------------------------------------
if (nrow(ann_refined) > 0 && nrow(resp_refined) > 0) {
  dat_ref <- ann_refined %>%
    inner_join(
      resp_refined %>%
        select(prompt_id, model, prompt_language, pair_id, template_id,
               entity_type, entity_en, entity_country, model_jurisdiction),
      by = c("prompt_id", "model", "prompt_language")
    ) %>%
    mutate(
      model_jur = factor(model_jurisdiction, levels = c("us", "china", "eu")),
      entity_country = factor(entity_country,
                                levels = c("CN", "RU", "NK", "US", "UK", "DE")),
      template_id = factor(template_id)
    )

  cat(sprintf("\nStudy B-refined: %d records across %d entities x %d templates x %d models\n",
              nrow(dat_ref),
              n_distinct(dat_ref$entity_en),
              n_distinct(dat_ref$template_id),
              n_distinct(dat_ref$model)))

  # Heatmap summary: refusal rate by (model x entity_country) within each language.
  refined_summary <- dat_ref %>%
    group_by(model, model_jurisdiction, prompt_language, entity_country) %>%
    summarise(
      n = n(),
      refusal_rate = mean(refused),
      n_refused = sum(refused),
      .groups = "drop"
    )

  write_csv(refined_summary, "pipeline/tables/30_study_b_refined.csv")
  cat("Wrote: tables/30_study_b_refined.csv\n")

  # Per-model mixed-effects fit: refused ~ entity_country + template_id + (1|prompt_id)
  refined_model_fits <- dat_ref %>%
    group_split(model, prompt_language) %>%
    map_dfr(function(d) {
      if (n_distinct(d$entity_country) < 2 || sum(d$refused) < 3 ||
          sum(!d$refused) < 3) {
        return(tibble(model = d$model[1], language = d$prompt_language[1],
                      term = NA, estimate = NA, conf.low = NA, conf.high = NA,
                      p.value = NA, note = "insufficient variation"))
      }
      f <- tryCatch(glm(refused ~ entity_country + template_id,
                         family = binomial, data = d),
                     error = function(e) NULL)
      if (is.null(f)) {
        return(tibble(model = d$model[1], language = d$prompt_language[1],
                      term = NA, estimate = NA, conf.low = NA, conf.high = NA,
                      p.value = NA, note = "fit failed"))
      }
      # Use Wald CIs (confint.default); profile-based CIs fail under
      # complete separation which is common here (some model x entity cells
      # always refuse or never refuse).
      tidy_f <- broom::tidy(f)
      wald_ci <- suppressWarnings(confint.default(f))
      tidy_f$conf.low  <- wald_ci[match(tidy_f$term, rownames(wald_ci)), 1]
      tidy_f$conf.high <- wald_ci[match(tidy_f$term, rownames(wald_ci)), 2]
      tidy_f %>%
        filter(grepl("^entity_country", term)) %>%
        mutate(model = d$model[1], language = d$prompt_language[1], note = "") %>%
        select(model, language, term, estimate, conf.low, conf.high, p.value, note)
    })

  write_csv(refined_model_fits, "pipeline/tables/30b_study_b_refined_fits.csv")

  # Heatmap plot: refusal rate by (model x entity_country) faceted by language.
  p_heatmap <- ggplot(refined_summary,
                       aes(x = entity_country, y = model, fill = refusal_rate)) +
    geom_tile(color = "white") +
    geom_text(aes(label = sprintf("%.0f%%", refusal_rate * 100)), size = 3) +
    facet_wrap(~ prompt_language, ncol = 2,
               labeller = labeller(prompt_language = c(en = "English prompt",
                                                        zh = "Chinese prompt"))) +
    scale_fill_gradient(low = "#f0f0f0", high = "#c0392b",
                        labels = scales::percent_format(accuracy = 1),
                        name = "Refusal rate") +
    labs(
      title = "Study B-refined: entity-swap refusal rates",
      subtitle = "Same template, different entity, within-language.",
      x = "Entity country", y = "Model"
    ) +
    theme_refusal(base_size = 10) +
    theme(panel.grid = element_blank())
} else {
  p_heatmap <- NULL
  refined_summary <- NULL
  cat("\nSkipping B-refined (no annotation data yet)\n")
}

# -----------------------------------------------------------------------------
# Combined panel figure for the PNAS paper
# -----------------------------------------------------------------------------
if (!is.null(fit_per_model) && any(!is.na(fit_per_model$estimate)) &&
    !is.null(p_heatmap)) {
  # Forest plot for B-orig: native_zh − mt_zh contrast per model.
  forest_data <- fit_per_model %>%
    filter(term == "variantnative_zh") %>%
    mutate(model = fct_reorder(model, estimate))

  p_forest <- ggplot(forest_data,
                      aes(x = estimate, y = model,
                          xmin = conf.low, xmax = conf.high)) +
    geom_vline(xintercept = 0, color = "gray60", linetype = "dashed") +
    geom_pointrange(size = 0.5) +
    labs(
      title = "Study B-orig: native-Chinese vs MT-Chinese refusal contrast",
      subtitle = "Coefficient on variantnative_zh (reference = native_en)",
      x = "log-odds of refusal", y = NULL
    ) +
    theme_refusal(base_size = 10)

  combined <- p_forest / p_heatmap + plot_layout(heights = c(1, 1.4))
  ggsave("pipeline/plots/fig_pnas_study_b.pdf", combined,
         width = 8, height = 7)
  cat("\nWrote: plots/fig_pnas_study_b.pdf\n")
} else if (!is.null(p_heatmap)) {
  ggsave("pipeline/plots/fig_pnas_study_b.pdf", p_heatmap,
         width = 6.5, height = 4)
  cat("\nWrote: plots/fig_pnas_study_b.pdf (heatmap only; B-orig pending)\n")
}
