# =============================================================================
# Script 11: Publication figures
# =============================================================================
# Requires: pipeline/data_clean.RData from 01_data_loading.R
# Writes:   pipeline/figures/*.png  (600 dpi, PNG only -- see _theme.R)
#
# Each figure is built around ONE analytical message, stated in its title.
# Design rules live in pipeline/_theme.R; this file should contain no colours,
# no font names and no ggsave() calls.
#
# COVERAGE. The run is still generating. English is complete for all 11 models;
# the seven OpenRouter models are complete for en/zh/ar and ~98% for ru; the
# MENA/India endpoint models have essentially no non-English data yet. Figures
# therefore declare their subset explicitly rather than pooling over cells that
# do not exist -- an unbalanced pool would read as a language effect when it is
# really a missingness pattern.

suppressPackageStartupMessages({
  library(tidyverse)
  library(scales)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")
load("pipeline/data_clean.RData")

FIGS <- "pipeline/figures"

cat(strrep("=", 78), "\nPUBLICATION FIGURES\n", strrep("=", 78), "\n", sep = "")

# Models complete outside English (the seven OpenRouter models).
OR7 <- c("gpt-5.1", "claude-opus-4.5", "gpt-4o", "grok-4.3",
         "deepseek-chat-v3.1", "qwen3-max", "mistral-large-2512")

# Rate + Wilson interval for an arbitrary grouping.
rate_by <- function(d, ...) {
  d %>% group_by(...) %>%
    summarise(n = n(), k = sum(refused), .groups = "drop") %>%
    mutate(rate = k / n) %>%
    bind_cols(wilson_ci(.$k, .$n))
}

# =============================================================================
# Figure 1. Refusal by model: regular vs boundary prompts (English)
# -----------------------------------------------------------------------------
# MESSAGE: models differ by more than an order of magnitude, and the boundary
# framing does NOT uniformly raise refusal -- for most models it lowers it.
# That heterogeneity of DIRECTION is the finding, so the encoding is a dumbbell:
# the segment is the within-model change, and its orientation is readable
# without consulting either endpoint's value.
# =============================================================================
cat("\nFigure 1: refusal by model, regular vs boundary\n")

f1 <- data_clean %>%
  filter(prompt_language == "en") %>%
  rate_by(model, dataset_type_f) %>%
  select(model, dataset_type_f, rate) %>%
  pivot_wider(names_from = dataset_type_f, values_from = rate) %>%
  rename(regular = `Regular Prompts`, boundary = `Boundary Prompts`) %>%
  mutate(model = fct_reorder(model, regular))

p1 <- ggplot(f1, aes(y = model)) +
  geom_segment(aes(x = regular, xend = boundary, yend = model),
               colour = RULE, linewidth = 0.9, lineend = "round") +
  geom_point(aes(x = regular),  colour = INK_FAINT, size = 1.9) +
  geom_point(aes(x = boundary), colour = ACCENT,    size = 1.9) +
  scale_x_rate(limit = 0.185, breaks = seq(0, 0.18, 0.06)) +
  scale_y_discrete(expand = expansion(add = c(0.7, 0.7))) +
  labs(
    title = "Refusal spans 0-17% across models, and boundary framing does not reliably raise it",
    # The key is carried by the subtitle sentence rather than by a legend or by
    # floating labels. Two endpoints 0.8 pp apart cannot both be labelled in the
    # panel without collision, and a colour legend would restate what the
    # sentence already has to say.
    subtitle = key_sentence(
      "Refusal rate on English prompts. Segment shows the within-model shift from",
      c(regular = INK_FAINT, boundary = ACCENT), "framing."),
    x = "Refusal rate", y = NULL
  ) +
  theme_nature(grid = "x", mono_y = TRUE, md_subtitle = TRUE)

save_fig(p1, file.path(FIGS, "fig1_refusal_by_model.png"),
         width = W2, height = h_rows(nlevels(f1$model)))

# =============================================================================
# Figure 2. DeepSeek by language
# -----------------------------------------------------------------------------
# MESSAGE: DeepSeek refuses ~3x more in Chinese than in English. This is the
# study's headline, so it gets the accent and a single uncluttered panel.
# Uncertainty is a Wilson interval; at n=2496 per cell the intervals are narrow,
# which is itself informative and worth showing rather than asserting.
# =============================================================================
cat("\nFigure 2: DeepSeek refusal by language\n")

f2 <- data_clean %>%
  filter(model == "deepseek-chat-v3.1", !is.na(language_f)) %>%
  rate_by(language_f) %>%
  filter(n >= 500) %>%                       # drop the barely-started Hindi cell
  mutate(language_f = fct_reorder(language_f, rate),
         mark = language_f == "Chinese")

p2 <- ggplot(f2, aes(x = rate, y = language_f)) +
  geom_errorbar(aes(xmin = lo, xmax = hi, colour = mark),
                orientation = "y", width = 0, linewidth = 0.45) +
  geom_point(aes(colour = mark), size = 2.2) +
  geom_text(aes(label = percent(rate, accuracy = 0.1), colour = mark),
            hjust = -0.65, size = 2.3, family = FONT_SANS) +
  scale_colour_manual(values = c(`TRUE` = ACCENT, `FALSE` = INK_FAINT)) +
  scale_x_rate(limit = 0.20, breaks = seq(0, 0.20, 0.05)) +
  labs(
    title = "DeepSeek refuses three times as often in Chinese as in English",
    subtitle = "Refusal rate by prompt language, DeepSeek V3.1. Bars are 95% Wilson intervals.",
    x = "Refusal rate", y = NULL
  ) +
  theme_nature(grid = "x")

save_fig(p2, file.path(FIGS, "fig2_deepseek_language.png"),
         width = W15, height = h_rows(nrow(f2), per = 0.21, chrome = 0.95))

# =============================================================================
# Figure 3. Is the language gap general?  Small multiples over models
# -----------------------------------------------------------------------------
# MESSAGE: no -- it is DeepSeek-specific. Small multiples on a COMMON x scale so
# panels are comparable; panels ordered by the size of the within-model language
# spread puts the finding in the reader's first fixation. DeepSeek is accented
# and every other model is ink, so the exception is visible without a legend and
# without reading seven panel titles.
# =============================================================================
cat("\nFigure 3: language effect by model (complete cells only)\n")

f3 <- data_clean %>%
  filter(model %in% OR7, prompt_language %in% c("en", "zh", "ar", "ru")) %>%
  rate_by(model, language_f) %>%
  group_by(model) %>% mutate(spread = max(rate) - min(rate)) %>% ungroup() %>%
  mutate(model = fct_reorder(model, spread, .desc = TRUE),
         mark  = model == "deepseek-chat-v3.1")

p3 <- ggplot(f3, aes(x = rate, y = fct_rev(language_f))) +
  geom_errorbar(aes(xmin = lo, xmax = hi, colour = mark),
                orientation = "y", width = 0, linewidth = 0.4) +
  geom_point(aes(colour = mark), size = 1.5) +
  facet_wrap(~ model, nrow = 2) +
  scale_colour_manual(values = c(`TRUE` = ACCENT, `FALSE` = INK)) +
  scale_x_rate(limit = 0.19, breaks = seq(0, 0.15, 0.05)) +
  labs(
    title = "The Chinese-language gap is specific to DeepSeek, not a general property of multilingual models",
    subtitle = "Refusal rate by prompt language within model, panels ordered by within-model spread. 95% Wilson intervals.",
    x = "Refusal rate", y = NULL
  ) +
  theme_nature(grid = "x") +
  theme(strip.text = element_text(family = FONT_MONO, face = "plain",
                                  colour = INK, size = rel(0.95), hjust = 0))

save_fig(p3, file.path(FIGS, "fig3_language_gap_by_model.png"),
         width = W2, height = 3.2)

# =============================================================================
# Figure 4. Refusal by topic domain
# -----------------------------------------------------------------------------
# MESSAGE: refusal concentrates in a few domains. Categories ordered by rate,
# not alphabetically. Regular and boundary are separate panels rather than
# separate colours, because the comparison is within-domain across tiers and
# small multiples make that a horizontal saccade.
# =============================================================================
cat("\nFigure 4: refusal by topic domain\n")

f4 <- data_clean %>%
  filter(prompt_language == "en") %>%
  rate_by(prompt_category, dataset_type_f) %>%
  mutate(domain = pretty_domain(prompt_category))

ord <- f4 %>% filter(dataset_type_f == "Regular Prompts") %>%
  arrange(rate) %>% pull(domain)
f4$domain <- factor(f4$domain, levels = ord)

p4 <- ggplot(f4, aes(x = rate, y = domain)) +
  geom_errorbar(aes(xmin = lo, xmax = hi), orientation = "y", width = 0,
                colour = INK_FAINT, linewidth = 0.4) +
  geom_point(colour = INK, size = 1.7) +
  facet_wrap(~ dataset_type_f) +
  scale_x_rate(limit = 0.13, breaks = seq(0, 0.12, 0.04)) +
  labs(
    title = "Refusal concentrates in security, governance and territorial topics",
    subtitle = "Refusal rate by topic domain, English prompts, all 11 models pooled. 95% Wilson intervals.",
    x = "Refusal rate", y = NULL
  ) +
  theme_nature(grid = "x")

save_fig(p4, file.path(FIGS, "fig4_refusal_by_domain.png"),
         width = W2, height = h_rows(9, per = 0.17, chrome = 1.15))

# =============================================================================
# Figure 5. What models say when they refuse
# -----------------------------------------------------------------------------
# MESSAGE: the REASON given for refusal differs by model, not just the rate.
# Composition, so a stacked bar is the honest encoding; the sequential ramp
# orders justification categories by lightness so the figure survives grayscale.
# Models with too few refusals to estimate a composition are dropped rather than
# shown as noisy 100% bars.
# =============================================================================
cat("\nFigure 5: refusal justifications by model\n")

# The judge emits seven codes (A-G). Seven steps of one hue are NOT visually
# separable in a stacked bar -- adjacent shades merge and the reader is forced
# into a legend lookup for every segment. Collapse to the four groups the
# substantive claim actually distinguishes: refusing because taking a position
# is improper (neutrality), because the content is dangerous (harm), because the
# question is hard or outside competence (epistemic), or without a stated reason.
JUST4 <- c(A = "Neutrality", C = "Harm avoidance",
           B = "Epistemic",  D = "Epistemic",
           E = "Epistemic",  F = "Unstated or other", G = "Unstated or other")
LEV4  <- c("Neutrality", "Harm avoidance", "Epistemic", "Unstated or other")

f5 <- data_clean %>%
  filter(prompt_language == "en", refused, !is.na(refusal_justification)) %>%
  mutate(just = factor(unname(JUST4[refusal_justification]), levels = LEV4)) %>%
  filter(!is.na(just)) %>%
  count(model, just, .drop = FALSE) %>%
  group_by(model) %>% mutate(total = sum(n), p = n / total) %>% ungroup() %>%
  filter(total >= 30)

if (nrow(f5) > 0) {
  # Order models by the neutrality share: that is the axis of the claim, so it
  # puts the gradient the figure is about along the vertical.
  ord5 <- f5 %>% filter(just == "Neutrality") %>% arrange(p) %>% pull(model)
  f5 <- f5 %>% mutate(model = factor(model, levels = ord5))

  # Four steps with a wide lightness range so the bars separate in grayscale.
  pal4 <- c("Neutrality" = "#22456F", "Harm avoidance" = "#6E8CAE",
            "Epistemic" = "#AFC1D4", "Unstated or other" = "#E4E8ED")

  p5 <- ggplot(f5, aes(x = p, y = model, fill = just)) +
    geom_col(width = 0.66) +
    scale_fill_manual(values = pal4, breaks = LEV4) +
    scale_x_continuous(labels = label_percent(accuracy = 1),
                       breaks = seq(0, 1, 0.25),
                       expand = expansion(mult = c(0, 0.005))) +
    guides(fill = guide_legend(nrow = 1)) +
    labs(
      title = "Models differ in the reason they give for refusing, not only in how often",
      subtitle = "Composition of refusal justifications, English prompts. Models with fewer than 30 refusals omitted.",
      x = "Share of refusals", y = NULL
    ) +
    theme_nature(grid = "none", mono_y = TRUE) +
    theme(legend.position = "top", legend.justification = "left",
          legend.key.height = unit(5, "pt"), legend.key.width = unit(9, "pt"),
          legend.spacing.x = unit(2, "pt"))

  save_fig(p5, file.path(FIGS, "fig5_refusal_justifications.png"),
           width = W2,
           height = h_rows(nlevels(droplevels(f5$model)), per = 0.21, chrome = 1.15))
} else {
  cat("  SKIP figure 5: no model has >=30 justified refusals yet\n")
}

# =============================================================================
# Figure 6. Model x language, complete cells only
# -----------------------------------------------------------------------------
# MESSAGE: a compact overview of where refusal lives in the design. A heatmap is
# the right encoding for a full crossing, but ONLY over cells that exist --
# incomplete cells are left blank rather than shaded, which would render "not
# generated yet" as "no refusals".
# =============================================================================
cat("\nFigure 6: model x language matrix\n")

f6 <- data_clean %>%
  rate_by(model, language_f) %>%
  filter(n >= 1000) %>%
  mutate(model = fct_reorder(model, rate, .fun = max))

p6 <- ggplot(f6, aes(x = language_f, y = model, fill = rate)) +
  geom_tile(colour = "white", linewidth = 0.9) +
  geom_text(aes(label = percent(rate, accuracy = 0.1),
                colour = rate > 0.09), size = 2.1, family = FONT_SANS) +
  scale_fill_gradientn(colours = SEQ_5, labels = label_percent(accuracy = 1),
                       name = NULL) +
  scale_colour_manual(values = c(`TRUE` = "white", `FALSE` = INK), guide = "none") +
  scale_x_discrete(position = "top", expand = c(0, 0)) +
  scale_y_discrete(expand = c(0, 0)) +
  labs(
    title = "Where refusal lives: model by prompt language",
    subtitle = "Refusal rate. Cells with fewer than 1,000 responses are omitted as still generating.",
    x = NULL, y = NULL
  ) +
  theme_nature(grid = "none", mono_y = TRUE) +
  theme(axis.line.x = element_blank(),
        axis.ticks.x = element_blank(), axis.ticks.y = element_blank(),
        legend.position = "right",
        legend.key.width = unit(6, "pt"), legend.key.height = unit(22, "pt"))

save_fig(p6, file.path(FIGS, "fig6_model_language_matrix.png"),
         width = W15,
         height = h_rows(nlevels(droplevels(f6$model)), per = 0.20, chrome = 1.2))

cat("\n", strrep("=", 78), "\nFIGURES COMPLETE\n", strrep("=", 78), "\n", sep = "")
