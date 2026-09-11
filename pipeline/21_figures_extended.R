# =============================================================================
# Technical reference: docs/r_pipeline/21_figures_extended.md
# EXTENDED DATA -- rates, levels, measurement, heterogeneity and robustness
# =============================================================================
# Genuine refusal and capability failure remain separate. This script filters
# and reshapes accepted tables but fits no model, interval, embedding or UMAP.
# Every model-specific estimate is attached to an explicit model label.

source("pipeline/_theme.R")
suppressPackageStartupMessages({library(tidyverse); library(patchwork)})

CAN_EST <- Sys.getenv("CANON_EST_DIR", "pipeline/estimates/canonical")
ED_FIG <- Sys.getenv("CANON_APPFIG_DIR", "pipeline/figures/extended")
CAN_LAYOUT <- Sys.getenv("CANON_LAYOUT_DIR", CAN_EST)
dir.create(ED_FIG, showWarnings = FALSE, recursive = TRUE)
dir.create(CAN_LAYOUT, showWarnings = FALSE, recursive = TRUE)
rd <- function(f) {
  p <- file.path(CAN_EST, f)
  if (file.exists(p)) read_csv(p, show_col_types = FALSE) else NULL
}
theme_set(theme_nature(base_size = PT_BODY))
figs <- list()
save_ed <- function(plot, name, height = H_WIDE) {
  save_fig(plot, file.path(ED_FIG, paste0(name, ".png")),
           width = W2, height = height)
  figs[[name]] <<- plot
}
LANG_LABEL <- c(en = "English", zh = "Chinese", ar = "Arabic",
                ru = "Russian", hi = "Hindi")

# ED1-ED2: standardized absolute home and away risks --------------------------
c04 <- rd("c04_home_standardized.csv")
level_dumbbell <- function(outcome, colour) {
  d <- c04 |> filter(.data$outcome == .env$outcome, weighting == "nested",
                     support == "full target", estimable) |>
    mutate(jurisdiction = factor(jurisdiction, levels = rev(ORDER_JURIS)))
  ggplot(d, aes(y = jurisdiction)) +
    geom_segment(aes(x = standardized_away_risk, xend = standardized_home_risk,
                     yend = jurisdiction), colour = INK_FAINT, linewidth = .65) +
    geom_point(aes(x = standardized_away_risk, colour = "Away", shape = "Away"),
               size = 2, fill = "white", stroke = .5) +
    geom_point(aes(x = standardized_home_risk, colour = "Home", shape = "Home"),
               size = 2) +
    scale_colour_manual(values = c(Away = INK_SOFT, Home = colour), name = NULL) +
    scale_shape_manual(values = c(Away = 21, Home = 16), name = NULL) +
    scale_x_continuous(labels = scales::label_percent(accuracy = 1),
                       limits = c(0, NA), expand = expansion(mult = c(.02, .10))) +
    labs(x = "Standardized predicted risk", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(colour = INK, size = PT_BODY),
          legend.position = "top", legend.justification = "left") +
    tag_only() + theme(plot.tag = element_blank())
}
if (!is.null(c04)) {
  save_ed(level_dumbbell("genuine_refusal", ACCENT),
          "ED1_home_absolute_risks_genuine_refusal", H_SHORT)
  save_ed(level_dumbbell("capability_failure", ACCENT_2),
          "ED2_home_absolute_risks_capability_failure", H_SHORT)
}

# ED3-ED4: paired English and target-language levels by model -----------------
c09 <- rd("c09_language_by_model.csv")
language_dumbbell <- function(outcome, colour) {
  d <- c09 |> filter(.data$outcome == .env$outcome) |>
    mutate(model = factor(model, levels = rev(ORDER_MODEL)),
           language = factor(unname(LANG_LABEL[language]),
                             levels = unname(LANG_LABEL[ORDER_LANG[-1]])))
  ggplot(d, aes(y = model)) +
    geom_segment(aes(x = mean_english, xend = mean_target, yend = model),
                 colour = INK_FAINT, linewidth = .5) +
    geom_point(aes(x = mean_english, colour = "English", shape = "English"),
               size = 1.5, fill = "white", stroke = .4) +
    geom_point(aes(x = mean_target, colour = "Target language",
                   shape = "Target language"), size = 1.5) +
    scale_colour_manual(values = c(English = INK_SOFT,
                                   `Target language` = colour), name = NULL) +
    scale_shape_manual(values = c(English = 21, `Target language` = 16),
                       name = NULL) +
    facet_wrap(~ language, nrow = 1) +
    scale_x_continuous(labels = scales::label_percent(accuracy = 1),
                       limits = c(0, NA), expand = expansion(mult = c(.02, .08))) +
    labs(x = "Paired-block outcome rate", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(colour = INK, size = PT_MIN),
          strip.text = element_text(size = PT_BODY),
          legend.position = "top", legend.justification = "left") +
    tag_only() + theme(plot.tag = element_blank())
}
if (!is.null(c09)) {
  save_ed(language_dumbbell("genuine_refusal", ACCENT),
          "ED3_language_absolute_rates_genuine_refusal", H_WIDE)
  save_ed(language_dumbbell("capability_failure", ACCENT_2),
          "ED4_language_absolute_rates_capability_failure", H_WIDE)
}

# ED5: compact measurement comparison, moved out of the main figures ----------
c24 <- rd("c24_response_validity_overlap.csv")
c27 <- rd("c27_annotation_transition.csv")
STATE_ORDER <- c("neither", "capability failure only", "genuine refusal only",
                 "refusal and capability failure")
STATE_LABEL <- c("neither" = "Neither",
  "capability failure only" = "Capability failure only",
  "genuine refusal only" = "Genuine refusal only",
  "refusal and capability failure" = "Both")
STATE_COLOUR <- c("neither" = "#B9B9BB", "capability failure only" = ACCENT_2,
  "genuine refusal only" = ACCENT,
  "refusal and capability failure" = "#6F4C78")
if (!is.null(c24) && !is.null(c27)) {
  overall <- c24 |>
    mutate(state = factor(response_validity_state, levels = rev(STATE_ORDER),
                          labels = unname(STATE_LABEL[rev(STATE_ORDER)])))
  p_overall <- ggplot(overall, aes(x = share, y = state,
                                   colour = response_validity_state)) +
    geom_segment(aes(x = 0, xend = share, yend = state), linewidth = .55) +
    geom_point(size = 2) +
    scale_colour_manual(values = STATE_COLOUR, guide = "none") +
    scale_x_continuous(labels = scales::label_percent(accuracy = 1),
                       limits = c(0, .70), expand = expansion(mult = c(0, .02))) +
    labs(x = "Share of all responses", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(colour = INK, size = PT_BODY)) +
    tag_only() + theme(plot.tag = element_blank())

  conditional <- c27 |>
    mutate(state = factor(response_validity_state, levels = rev(STATE_ORDER),
                          labels = unname(STATE_LABEL[rev(STATE_ORDER)])),
           original_measurement = factor(original_measurement,
             levels = c("Original engaged/partial",
                        "Original judge-coded non-engagement")))
  p_conditional <- ggplot(conditional,
      aes(x = share_within_original, y = state,
          colour = response_validity_state)) +
    geom_segment(aes(x = 0, xend = share_within_original, yend = state),
                 linewidth = .5) +
    geom_point(size = 1.9) +
    facet_wrap(~ original_measurement, nrow = 1) +
    scale_colour_manual(values = STATE_COLOUR, guide = "none") +
    scale_x_continuous(labels = scales::label_percent(accuracy = 1),
                       limits = c(0, 1), expand = expansion(mult = c(0, .02))) +
    labs(x = "Share within original label", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_blank(), strip.text = element_text(size = PT_MIN)) +
    tag_only() + theme(plot.tag = element_blank())
  save_ed(p_overall | p_conditional, "ED5_measurement_reclassification", H_WIDE)
}

# ED6: annotation component marginals -----------------------------------------
c25 <- rd("c25_response_validity_components.csv")
if (!is.null(c25)) {
  FIELD_LABEL <- c(rv_substantive_refusal = "Substantive refusal",
    rv_output_quality = "Output quality", rv_language_fidelity = "Language fidelity",
    rv_technical_failure = "Technical failure", rv_task_behavior = "Task behaviour")
  d <- c25 |> filter(field %in% names(FIELD_LABEL)) |>
    mutate(field_label = factor(unname(FIELD_LABEL[field]),
                                levels = unname(FIELD_LABEL)),
           value_label = pretty_domain(value))
  p <- ggplot(d, aes(x = share, y = reorder(value_label, share))) +
    geom_segment(aes(x = 0, xend = share, yend = reorder(value_label, share)),
                 colour = RULE, linewidth = .35) +
    geom_point(colour = INK_SOFT, size = 1.6) +
    facet_grid(rows = vars(field_label), scales = "free_y", space = "free_y",
               switch = "y") +
    scale_x_continuous(labels = scales::label_percent(accuracy = 1),
                       limits = c(0, 1), expand = expansion(mult = c(0, .02))) +
    labs(x = "Share of responses", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(strip.placement = "outside",
          strip.text.y.left = element_text(angle = 0, hjust = 1, size = PT_MIN),
          axis.text.y = element_text(colour = INK, size = PT_MIN)) +
    tag_only() + theme(plot.tag = element_blank())
  save_ed(p, "ED6_annotation_component_profile", H_TALL)
}

# ED7-ED8: every model-specific contrast is explicitly labelled ---------------
c05 <- rd("c05_home_by_model.csv")
c11 <- rd("c11_framing_by_model.csv")
model_forest <- function(d, colour, xlab, facet = NULL) {
  p <- ggplot(d, aes(x = estimate_pp, y = model)) +
    geom_vline(xintercept = 0, colour = INK_FAINT, linewidth = .3) +
    geom_errorbar(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                  orientation = "y", width = 0, colour = colour, linewidth = .42) +
    geom_point(colour = colour, size = 1.3) +
    labs(x = xlab, y = NULL) + theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(colour = INK, size = PT_MIN),
          strip.text = element_text(size = PT_MIN)) +
    tag_only() + theme(plot.tag = element_blank())
  if (!is.null(facet)) p <- p + facet_wrap(vars(.data[[facet]]), nrow = 1)
  p
}
heterogeneity_figure <- function(outcome, colour) {
  hm <- c05 |> filter(.data$outcome == .env$outcome, estimable) |>
    mutate(model = factor(model, levels = rev(ORDER_MODEL)))
  fm <- c11 |> filter(.data$outcome == .env$outcome) |>
    mutate(model = factor(model, levels = rev(ORDER_MODEL)))
  lm <- c09 |> filter(.data$outcome == .env$outcome) |>
    mutate(model = factor(model, levels = rev(ORDER_MODEL)),
           language_label = factor(unname(LANG_LABEL[language]),
             levels = unname(LANG_LABEL[ORDER_LANG[-1]])))
  p_home <- model_forest(hm, colour, "Standardized home minus away (pp)")
  p_frame <- model_forest(fm, colour, "Boundary minus regular (pp)")
  p_lang <- model_forest(lm, colour, "Target language minus English (pp)",
                         "language_label")
  (p_home | p_frame) / p_lang + plot_layout(heights = c(.92, 1.08))
}
if (!is.null(c05) && !is.null(c09) && !is.null(c11)) {
  save_ed(heterogeneity_figure("genuine_refusal", ACCENT),
          "ED7_model_specific_contrasts_genuine_refusal", H_TALL)
  save_ed(heterogeneity_figure("capability_failure", ACCENT_2),
          "ED8_model_specific_contrasts_capability_failure", H_TALL)
}

# ED9-ED10: descriptive content fingerprints ---------------------------------
c23 <- rd("c23_response_validity_prevalence.csv")
content_fingerprint <- function(outcome, colour) {
  d <- c23 |> filter(.data$outcome == .env$outcome,
                     scope %in% c("topic domain", "issue region")) |>
    mutate(group = if_else(scope == "topic domain", pretty_domain(domain),
                           region_label(region_focus)),
           scope_label = factor(scope, levels = c("topic domain", "issue region"),
                                labels = c("Topic domain", "Issue region")))
  ggplot(d, aes(x = rate, y = reorder(group, rate))) +
    geom_segment(aes(x = 0, xend = rate, yend = reorder(group, rate)),
                 colour = RULE, linewidth = .35) +
    geom_point(colour = colour, size = 1.7) +
    facet_wrap(~ scope_label, scales = "free_y", nrow = 1) +
    scale_x_continuous(labels = scales::label_percent(accuracy = .1),
                       limits = c(0, NA), expand = expansion(mult = c(0, .08))) +
    labs(x = "Realized response rate", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(colour = INK, size = PT_MIN)) +
    tag_only() + theme(plot.tag = element_blank())
}
if (!is.null(c23)) {
  save_ed(content_fingerprint("genuine_refusal", ACCENT),
          "ED9_content_fingerprint_genuine_refusal", H_STD)
  save_ed(content_fingerprint("capability_failure", ACCENT_2),
          "ED10_content_fingerprint_capability_failure", H_STD)
}

# ED11-ED12: prompt concentration and cross-model recurrence -----------------
c22b <- rd("c22b_prompt_concentration.csv")
c22d <- rd("c22d_prompt_cross_model_distribution.csv")
prompt_distribution <- function(outcome, colour) {
  cc <- c22b |> filter(.data$outcome == .env$outcome)
  cm <- c22d |> filter(.data$outcome == .env$outcome)
  p1 <- ggplot(cc, aes(cumulative_prompt_share, cumulative_outcome_share)) +
    geom_abline(slope = 1, intercept = 0, colour = INK_FAINT,
                linewidth = .3, linetype = "22") +
    geom_line(colour = colour, linewidth = .65) +
    scale_x_continuous(labels = scales::label_percent(accuracy = 25), limits = c(0, 1)) +
    scale_y_continuous(labels = scales::label_percent(accuracy = 25), limits = c(0, 1)) +
    labs(x = "Prompts, ordered by propensity", y = "Cumulative outcome propensity") +
    theme_nature(base_size = PT_BODY, grid = "none") +
    tag_only() + theme(plot.tag = element_blank())
  p2 <- ggplot(cm, aes(n_models_event, share_prompts)) +
    geom_segment(aes(xend = n_models_event, y = 0, yend = share_prompts),
                 colour = RULE, linewidth = .38) +
    geom_point(colour = colour, size = 1.55) +
    scale_x_continuous(breaks = seq(0, length(ORDER_MODEL), by = 2),
                       limits = c(-.5, length(ORDER_MODEL) + .5)) +
    scale_y_continuous(labels = scales::label_percent(accuracy = 1),
                       limits = c(0, NA), expand = expansion(mult = c(0, .06))) +
    labs(x = "English-evaluated models with outcome", y = "Share of prompts") +
    theme_nature(base_size = PT_BODY, grid = "y") +
    tag_only() + theme(plot.tag = element_blank())
  p1 | p2
}
if (!is.null(c22b) && !is.null(c22d)) {
  save_ed(prompt_distribution("genuine_refusal", ACCENT),
          "ED11_prompt_distribution_genuine_refusal", H_WIDE)
  save_ed(prompt_distribution("capability_failure", ACCENT_2),
          "ED12_prompt_distribution_capability_failure", H_WIDE)
}

# ED13: capability-failure semantic atlas matching Main Figure 1 --------------
c22 <- rd("c22_prompt_umap_coordinates.csv")
c22p <- rd("c22_prompt_outcome_propensities.csv")
c22m <- rd("c22_prompt_outcomes_by_model.csv")
if (!is.null(c22) && !is.null(c22p) && !is.null(c22m)) {
  umap_theme <- theme_nature(base_size = PT_BODY, grid = "none") +
    theme(axis.text = element_blank(), axis.ticks = element_blank(),
          axis.line = element_blank(), strip.text = element_text(size = PT_MIN),
          panel.spacing = unit(4.5, "pt"), legend.position = "top",
          legend.justification = "left",
          legend.title = element_text(colour = INK_SOFT, size = PT_MIN))
  propensity_scale <- scale_size_area(max_size = 1.65, limits = c(0, 1),
    breaks = c(.10, .25, .50), labels = scales::label_percent(accuracy = 1),
    name = "Capability-failure propensity")
  region_background <- tidyr::crossing(
    facet_region = factor(ORDER_REGION, levels = ORDER_REGION,
                          labels = region_label(ORDER_REGION)),
    c22 |> select(prompt_id, umap_x, umap_y))
  region_points <- c22 |> select(prompt_id, region_focus, umap_x, umap_y) |>
    left_join(c22p |> filter(language == "ALL", outcome == "capability_failure") |>
                select(prompt_id, propensity), by = "prompt_id") |>
    mutate(facet_region = factor(region_focus, levels = ORDER_REGION,
                                 labels = region_label(ORDER_REGION)))
  p_region <- ggplot() +
    geom_point(data = region_background,
               aes(umap_x, umap_y, colour = "Reference geometry"),
               alpha = .22, size = .12) +
    geom_point(data = region_points,
               aes(umap_x, umap_y, colour = "Prompt in facet"),
               alpha = .42, size = .20) +
    geom_point(data = filter(region_points, propensity > 0),
               aes(umap_x, umap_y, size = propensity,
                   colour = "Capability failure"), alpha = .76) +
    facet_wrap(~ facet_region, ncol = 3) + propensity_scale +
    scale_colour_manual(values = c("Reference geometry" = RULE,
      "Prompt in facet" = INK_FAINT, "Capability failure" = ACCENT_2),
      name = NULL) +
    guides(colour = guide_legend(order = 1, override.aes = list(
             alpha = 1, size = c(.7, .9, 1.2))),
           size = guide_legend(order = 2)) + coord_equal() +
    labs(x = NULL, y = NULL) + umap_theme
  language_points <- c22p |>
    filter(outcome == "capability_failure", language %in% ORDER_LANG) |>
    left_join(c22 |> select(prompt_id, umap_x, umap_y), by = "prompt_id") |>
    mutate(language = factor(language, levels = ORDER_LANG,
                             labels = unname(LANG_LABEL[ORDER_LANG])))
  p_language <- ggplot(language_points, aes(umap_x, umap_y)) +
    geom_point(colour = INK_FAINT, alpha = .25, size = .16) +
    geom_point(data = filter(language_points, propensity > 0), aes(size = propensity),
               colour = ACCENT_2, alpha = .74) +
    facet_wrap(~ language, nrow = 1) + propensity_scale + coord_equal() +
    labs(x = NULL, y = NULL) + umap_theme + theme(legend.position = "none")
  events <- c22m |> filter(capability_failure == 1) |>
    left_join(c22 |> select(prompt_id, umap_x, umap_y), by = "prompt_id") |>
    mutate(model = factor(model, levels = ORDER_MODEL))
  model_background <- tidyr::crossing(
    model = factor(ORDER_MODEL, levels = ORDER_MODEL),
    c22 |> select(prompt_id, umap_x, umap_y))
  p_model <- ggplot() +
    geom_point(data = model_background, aes(umap_x, umap_y), colour = INK_FAINT,
               alpha = .25, size = .16) +
    geom_point(data = events, aes(umap_x, umap_y), colour = ACCENT_2,
               alpha = .80, size = .52, shape = 17) +
    facet_wrap(~ model, ncol = 6) + coord_equal() + labs(x = NULL, y = NULL) +
    umap_theme + theme(legend.position = "none")
  atlas <- p_region / p_language / p_model +
    plot_layout(heights = c(1.40, .55, 1.28))
  save_ed(atlas, "ED13_capability_failure_semantic_atlas", H_PAGE)

  # ED14 preserves the exact model-level English atlas at readable appendix
  # size. It is deliberately separate from the combined jurisdiction maps in
  # Main Figure 1: red means the same binary outcome in every facet, whereas
  # the main figure spends colour on model identity and multi-model overlap.
  refusal_events <- c22m |> filter(genuine_refusal == 1) |>
    left_join(c22 |> select(prompt_id, umap_x, umap_y), by = "prompt_id") |>
    mutate(model = factor(model, levels = ORDER_MODEL))
  model_background <- tidyr::crossing(
    model = factor(ORDER_MODEL, levels = ORDER_MODEL),
    c22 |> select(prompt_id, umap_x, umap_y))
  model_atlas <- ggplot() +
    geom_point(data = model_background, aes(umap_x, umap_y),
               colour = INK_FAINT, alpha = .24, size = .16) +
    geom_point(data = refusal_events, aes(umap_x, umap_y),
               colour = ACCENT, alpha = .84, size = .56) +
    facet_wrap(~ model, ncol = 6) + coord_equal() +
    labs(x = NULL, y = NULL) + umap_theme + theme(legend.position = "none")
  save_ed(model_atlas, "ED14_genuine_refusal_semantic_atlas_by_model", H_TALL)
}

saveRDS(figs, file.path(CAN_LAYOUT, "c20_figure_layout_extended.rds"))
