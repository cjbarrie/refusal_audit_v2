# =============================================================================
# EXPANDED V3 18-MODEL FIGURES -- PNG ONLY
# =============================================================================
# Plotting only. No estimate or UMAP is fitted here. Figures contain no title,
# subtitle, caption, or prose annotation. Genuine refusal and capability failure
# are never combined in one mark or rate.

source("pipeline/_theme.R")
suppressPackageStartupMessages({library(tidyverse); library(patchwork)})
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())

EST <- "pipeline/expanded/estimates_v3"
FIG <- "pipeline/figures/expanded_v3"
dir.create(FIG, recursive = TRUE, showWarnings = FALSE)
rd <- function(x) read_csv(file.path(EST, x), show_col_types = FALSE)
MODEL_ORDER_EXP <- c(
  "deepseek-chat-v3.1", "glm-4.7-flash", "hunyuan-a13b", "kimi-k2.5", "qwen3-max",
  "allam-7b", "falcon3-10b", "jais-8b", "sarvam-30b",
  "claude-opus-4.5", "gemini-2.5-flash-lite", "gpt-4o", "gpt-5.1",
  "grok-4.3", "llama-4-scout", "nova-lite",
  "ministral-14b", "mistral-large-2512")
NEW_MODELS <- c("glm-4.7-flash", "hunyuan-a13b", "kimi-k2.5", "gemini-2.5-flash-lite",
                "llama-4-scout", "nova-lite", "ministral-14b")
LANG_LABEL_EXP <- c(en = "English", zh = "Chinese", ar = "Arabic",
                    ru = "Russian", hi = "Hindi")
theme_set(theme_nature(base_size = PT_BODY))

# 1. Realized model-language rate atlases ------------------------------------
rates <- rd("e01_model_language_rates.csv")
rate_plot <- function(outcome, colour, file) {
  d <- rates |>
    transmute(model = factor(model, levels = rev(MODEL_ORDER_EXP)),
              language = factor(LANG_LABEL_EXP[prompt_language],
                                levels = unname(LANG_LABEL_EXP[ORDER_LANG])),
              rate = .data[[paste0(outcome, "_rate")]])
  p <- ggplot(d, aes(rate, model)) +
    geom_segment(aes(x = 0, xend = rate, yend = model),
                 colour = RULE, linewidth = .32) +
    geom_point(colour = colour, size = 1.55) +
    facet_wrap(~ language, nrow = 1) +
    scale_x_continuous(labels = scales::label_percent(accuracy = 1),
                       limits = c(0, NA), expand = expansion(mult = c(0, .06))) +
    labs(x = "Realized response rate", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(colour = INK, size = PT_MIN),
          strip.text = element_text(size = PT_BODY)) + tag_only()
  save_fig(p, file.path(FIG, file), width = W2, height = H_TALL)
}
rate_plot("genuine_refusal", ACCENT,
          "E1_model_language_genuine_refusal.png")
rate_plot("capability_failure", ACCENT_2,
          "E2_model_language_capability_failure.png")

# 2. Core aggregate estimands: one common percentage-point scale -------------
home <- rd("e03_home_by_jurisdiction.csv") |>
  filter(estimable) |>
  transmute(outcome, family = "Home region", item = jurisdiction,
            estimate_pp, conf_low_pp, conf_high_pp)
language <- rd("e05_language_paired.csv") |>
  transmute(outcome, family = "Delivered language",
            item = LANG_LABEL_EXP[language], estimate_pp, conf_low_pp, conf_high_pp)
framing <- rd("e07_framing_paired.csv") |>
  transmute(outcome, family = "Prompt framing", item = "Boundary minus regular",
            estimate_pp, conf_low_pp, conf_high_pp)
order <- c("CN", "MENA", "India", "US", "EU", "Chinese", "Arabic",
           "Russian", "Hindi", "Boundary minus regular")
core <- bind_rows(home, language, framing) |>
  mutate(outcome_label = factor(outcome,
    levels = c("genuine_refusal", "capability_failure"),
    labels = c("Genuine refusal", "Capability failure")),
    family = factor(family, levels = c("Home region", "Delivered language",
                                       "Prompt framing")),
    item = factor(item, levels = rev(order)))
p_core <- ggplot(core, aes(estimate_pp, item, colour = outcome_label)) +
  geom_vline(xintercept = 0, colour = INK_FAINT, linewidth = .3) +
  geom_errorbar(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                orientation = "y", width = 0, linewidth = .58) +
  geom_point(size = 1.9) +
  facet_grid(rows = vars(family), cols = vars(outcome_label),
             scales = "free", space = "free_y") +
  scale_colour_manual(values = c("Genuine refusal" = ACCENT,
                                 "Capability failure" = ACCENT_2), guide = "none") +
  labs(x = "Difference (percentage points)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.text.y = element_text(colour = INK, size = PT_BODY),
        strip.text = element_text(size = PT_BODY),
        panel.spacing.y = unit(5, "pt")) + tag_only()
save_fig(p_core, file.path(FIG, "E3_core_estimands.png"),
         width = W2, height = H_STD)

# 3. Model-specific home contrasts, with labels on every estimate ------------
home_model <- rd("e04_home_by_model.csv") |>
  filter(estimable) |>
  mutate(model = factor(model, levels = rev(MODEL_ORDER_EXP)),
         outcome_label = factor(outcome,
           levels = c("genuine_refusal", "capability_failure"),
           labels = c("Genuine refusal", "Capability failure")))
p_home_model <- ggplot(home_model,
    aes(estimate_pp, model, colour = outcome_label)) +
  geom_vline(xintercept = 0, colour = INK_FAINT, linewidth = .3) +
  geom_errorbar(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                orientation = "y", width = 0, linewidth = .48) +
  geom_point(size = 1.5) +
  facet_wrap(~ outcome_label, nrow = 1) +
  scale_colour_manual(values = c("Genuine refusal" = ACCENT,
                                 "Capability failure" = ACCENT_2), guide = "none") +
  labs(x = "Standardized home minus away difference (percentage points)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.text.y = element_text(colour = INK, size = PT_MIN),
        strip.text = element_text(size = PT_BODY)) + tag_only()
save_fig(p_home_model, file.path(FIG, "E4_home_contrasts_by_model.png"),
         width = W2, height = H_TALL)

# 4. Fixed semantic geometry for every new model x language cell -------------
coords <- read_csv("pipeline/estimates/canonical/c22_prompt_umap_coordinates.csv",
                   show_col_types = FALSE) |> select(prompt_id, umap_x, umap_y)
events <- readRDS("pipeline/expanded/derived/expanded_panel_v3.rds") |>
  filter(model %in% NEW_MODELS) |>
  select(prompt_id, prompt_language, model, genuine_refusal, capability_failure) |>
  left_join(coords, by = "prompt_id") |>
  mutate(model = factor(model, levels = NEW_MODELS),
         language = factor(LANG_LABEL_EXP[prompt_language],
                           levels = unname(LANG_LABEL_EXP[ORDER_LANG])))
stopifnot(!anyNA(events$umap_x), nrow(events) == 87358L)
background <- crossing(model = factor(NEW_MODELS, levels = NEW_MODELS),
                       language = factor(unname(LANG_LABEL_EXP[ORDER_LANG]),
                                         levels = unname(LANG_LABEL_EXP[ORDER_LANG])),
                       coords)

umap_outcome <- function(outcome, label, colour, file) {
  marked <- events |> filter(.data[[outcome]] == 1L)
  p <- ggplot() +
    geom_point(data = background,
      aes(umap_x, umap_y, colour = "All prompts"), alpha = .24, size = .11) +
    geom_point(data = marked,
      aes(umap_x, umap_y, colour = label), alpha = .82, size = .42) +
    facet_grid(model ~ language) + coord_equal() +
    scale_colour_manual(values = c("All prompts" = INK_FAINT,
                                   setNames(colour, label)), name = NULL,
      breaks = c("All prompts", label),
      guide = guide_legend(override.aes = list(alpha = 1, size = c(.8, 1.2)))) +
    labs(x = NULL, y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "none") +
    theme(axis.text = element_blank(), axis.ticks = element_blank(),
          axis.line = element_blank(), strip.text = element_text(size = PT_MIN),
          panel.spacing = unit(2.5, "pt"), legend.position = "top",
          legend.justification = "left") + tag_only()
  save_fig(p, file.path(FIG, file), width = W2, height = H_PAGE)
}
umap_outcome("genuine_refusal", "Genuine refusal", ACCENT,
             "E5_new_models_umap_genuine_refusal.png")
umap_outcome("capability_failure", "Capability failure", ACCENT_2,
             "E6_new_models_umap_capability_failure.png")

cat("Wrote six expanded-v3 PNG figures\n")
