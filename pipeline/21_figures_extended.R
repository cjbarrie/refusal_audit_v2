# =============================================================================
# EXTENDED DATA FIGURES -- ED1 .. ED9
# =============================================================================
#   ED1  judge-instrument sensitivity      (c17d)
#   ED2  focused estimator/support/outcome (c04, c07)
#   ED3  issue-subsample stability         (c21)
#   ED4  model x language heterogeneity    (c09)
#   ED5  ideological slant by model        (c13)
#   ED6  moral foundations by model        (c14, c15)
#   ED7  measurement reliability           (e23, e24, e25)
#   ED8  prompt-semantic UMAP              (c22)
#   ED9  prompt-semantic UMAP by model     (c22)  -- optional
#   ED10 prompt framing, boundary - regular (c10, c11)
#
# Read tables, fit nothing, write no canonical table. No titles, subtitles or
# captions inside a panel. Orderings come from pipeline/_orders.R.

source("pipeline/_theme.R")
suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork)
})

CAN_EST <- Sys.getenv("CANON_EST_DIR", "pipeline/estimates/canonical")
ED_FIG  <- Sys.getenv("CANON_APPFIG_DIR", "pipeline/figures/extended")
dir.create(ED_FIG, showWarnings = FALSE, recursive = TRUE)
rd <- function(f) { p <- file.path(CAN_EST, f)
  if (file.exists(p)) suppressMessages(read_csv(p, show_col_types = FALSE)) else NULL }

theme_set(theme_nature(base_size = PT_BODY))
TXT <- pt_to_mm(PT_MIN); LWC <- 0.45
short_judge <- function(x) str_remove(x, "^[a-z]+/")
figs <- list()

cat(strrep("=", 78), "\nEXTENDED DATA FIGURES\n", strrep("=", 78), "\n", sep = "")

# =============================================================================
# ED1 -- judge sensitivity, one compact forest
# =============================================================================
# The quantity is the PAIRED difference from the canonical judge (c17d), formed
# inside each bootstrap replicate on one shared issue draw. Zero already means
# "agrees with the canonical judge", so no separate reference line is drawn --
# a dashed canonical rule on top of a zero rule was two marks for one fact.
#
# ONE COMMON X-AXIS across jurisdictions. The 2x2 grid of free scales it
# replaces made a -0.7 pp difference in US look the same size as a -5.2 pp
# difference in CN.
c17d <- rd("c17d_judge_paired_differences.csv")
if (!is.null(c17d) && "estimable" %in% names(c17d)) {
  cat("ED1 judge sensitivity\n")
  d <- c17d %>% filter(estimable, !is_canonical_judge) %>%
    mutate(judge = short_judge(judge_model),
           j = factor(jurisdiction, levels = ORDER_JURIS)) %>%
    arrange(j, judge)
  ne <- c17d %>% filter(!estimable) %>% distinct(jurisdiction) %>% pull()
  # Interleave a heading row per jurisdiction, so the grouping lives in the
  # y-axis labels rather than in a facet strip with its own scale.
  lay <- d %>% distinct(j) %>% mutate(lab = as.character(j), head = TRUE, k = 0L) %>%
    bind_rows(d %>% group_by(j) %>% mutate(k = row_number()) %>% ungroup() %>%
                transmute(j, lab = paste0("   ", judge), head = FALSE, k)) %>%
    arrange(j, k) %>% mutate(y = -row_number())
  dd <- d %>% arrange(j, judge) %>%
    mutate(y = lay$y[match(paste0("   ", judge, "|", j), paste0(lay$lab, "|", lay$j))])

  ed1 <- ggplot(dd, aes(x = estimate_pp, y = y)) +
    geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.4) +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), colour = INK,
                   linewidth = LWC) +
    geom_point(size = 1.7, shape = 21, fill = INK, colour = "white", stroke = 0.3) +
    geom_text(aes(x = Inf, label = sprintf("%+.2f [%+.2f, %+.2f]",
                                           estimate_pp, conf_low_pp, conf_high_pp)),
              hjust = 1.02, size = TXT, colour = INK_SOFT) +
    scale_y_continuous(breaks = lay$y, labels = lay$lab,
                       limits = range(lay$y) + c(-0.8, 0.8)) +
    scale_x_continuous(expand = expansion(mult = c(0.04, 0.42))) +
    labs(x = "Alternative judge minus canonical judge (pp)", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(size = PT_MIN, hjust = 0, colour = INK_SOFT),
          axis.ticks.y = element_blank()) +
    tag_only() + theme(plot.tag = element_blank())
  save_fig(ed1, file.path(ED_FIG, "ED1_judge_sensitivity.png"),
           width = W2, height = H_SHORT)
  figs$ED1_judge_sensitivity <- ed1
  if (length(ne)) cat("  not estimable, omitted:", paste(ne, collapse = ", "), "\n")
}

# =============================================================================
# ED2 -- FOCUSED estimator / support / outcome sensitivity
# =============================================================================
# The sprawling multiverse forest is retired as a figure. It put rows that
# change the ESTIMATOR next to rows that change the TARGET POPULATION and rows
# that change the OUTCOME DEFINITION, and called them all robustness.
#
# Four points per jurisdiction, and only four:
#   * primary  -- maximum likelihood, full target
#   * Firth    -- different ESTIMATOR, same target
#   * common support -- different TARGET POPULATION
#   * refused_any    -- different OUTCOME DEFINITION
# Shape marks what changed. The full grid -- language, tier, leave-one-model-out,
# functional form, response length, hierarchical -- is the c07c table.
#
# Overlapping intervals here are NOT a test of equality between specifications.
c04 <- rd("c04_home_standardized.csv"); c07 <- rd("c07_home_sensitivities.csv")
if (!is.null(c04)) {
  cat("ED2 focused sensitivity\n")
  SPEC <- c("Primary (ML, full target)", "Firth (estimator)",
            "Common support (target)", "refused_any (outcome)")
  s1 <- c04 %>% filter(weighting == "nested", estimator == "maximum likelihood",
                       support == "full target") %>%
    transmute(jurisdiction, estimate_pp, conf_low_pp, conf_high_pp, estimable,
              spec = SPEC[1])
  s2 <- c04 %>% filter(weighting == "nested", estimator == "Firth penalized logit",
                       support == "full target") %>%
    transmute(jurisdiction, estimate_pp, conf_low_pp, conf_high_pp, estimable,
              spec = SPEC[2])
  s3 <- c04 %>% filter(weighting == "nested", estimator == "maximum likelihood",
                       support == "common support") %>%
    transmute(jurisdiction, estimate_pp, conf_low_pp, conf_high_pp, estimable,
              spec = SPEC[3])
  s4 <- if (is.null(c07)) NULL else c07 %>% filter(sensitivity == "outcome_code3") %>%
    transmute(jurisdiction, estimate_pp, conf_low_pp, conf_high_pp, estimable,
              spec = SPEC[4])
  sd2 <- bind_rows(s1, s2, s3, s4) %>%
    mutate(j = factor(jurisdiction, levels = ORDER_JURIS),
           s = factor(spec, levels = SPEC))
  drawable <- sd2 %>% filter(estimable, is.finite(estimate_pp), is.finite(conf_low_pp))
  ne2 <- sd2 %>% filter(!(estimable & is.finite(estimate_pp))) %>%
    distinct(jurisdiction) %>%
    filter(!jurisdiction %in% drawable$jurisdiction)
  off <- setNames(seq(0.30, -0.30, length.out = length(SPEC)), SPEC)
  drawable <- drawable %>% mutate(y = as.numeric(factor(j, levels = rev(ORDER_JURIS))) +
                                    off[as.character(s)])

  ed2 <- ggplot(drawable, aes(x = estimate_pp, y = y)) +
    geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp, colour = s),
                   linewidth = LWC) +
    geom_point(aes(shape = s, fill = s, colour = s), size = 1.9, stroke = 0.5) +
    { if (nrow(ne2))
        geom_text(data = ne2 %>% mutate(y = as.numeric(factor(jurisdiction,
                                        levels = rev(ORDER_JURIS)))),
                  aes(x = 0, y = y), inherit.aes = FALSE,
                  label = NOT_ESTIMABLE_TEXT, hjust = -0.12, size = TXT,
                  colour = INK_FAINT) } +
    scale_shape_manual(values = c(23, 21, 22, 24), breaks = SPEC, name = NULL) +
    scale_fill_manual(values = c(INK, "white", INK_SOFT, "white"),
                      breaks = SPEC, name = NULL) +
    scale_colour_manual(values = c(INK, INK, INK_SOFT, INK_SOFT),
                        breaks = SPEC, name = NULL) +
    scale_y_continuous(breaks = seq_along(ORDER_JURIS), labels = rev(ORDER_JURIS),
                       limits = c(0.4, length(ORDER_JURIS) + 0.6)) +
    scale_x_continuous(expand = expansion(mult = c(0.06, 0.10))) +
    labs(x = "Home - away difference (pp)", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(colour = INK, size = PT_BODY),
          axis.ticks.y = element_blank(),
          legend.position = "top", legend.text = element_text(size = PT_MIN),
          legend.key.size = unit(7, "pt")) +
    tag_only() + theme(plot.tag = element_blank())
  save_fig(ed2, file.path(ED_FIG, "ED2_focused_sensitivity.png"),
           width = W2, height = H_SHORT)
  figs$ED2_focused_sensitivity <- ed2
}

# =============================================================================
# ED3 -- issue-subsample stability
# =============================================================================
# THE BANDS ARE NOT CONFIDENCE INTERVALS. They are across-subsample ranges: the
# spread of the estimate when the issue battery is smaller. The question the
# panel answers is how much of the full-sample conclusion is already recovered
# as issues are added.
c21 <- rd("c21_subsample_summary.csv")
if (!is.null(c21) && nrow(c21)) {
  cat("ED3 subsample stability\n")
  keep_fam <- c("home", "language", "framing")
  st <- c21 %>% filter(family %in% keep_fam) %>%
    mutate(panel = case_when(
      grepl("standardized", estimand) ~ paste0("Standardized home  ", level),
      grepl("descriptive", estimand)  ~ paste0("Unadjusted home  ", level),
      family == "language"            ~ paste0("Language  ", level),
      TRUE                            ~ "Framing  all models")) %>%
    filter(!is.na(full_value)) %>%
    # A structural zero has no stability to display: EU recorded no refusals at
    # any fraction, so its panel would be a flat line at zero with no band and
    # would read as a precisely recovered estimate.
    group_by(panel) %>% filter(!all(p10 == 0 & p90 == 0)) %>% ungroup()
  pord <- c(paste0("Standardized home  ", ORDER_JURIS),
            paste0("Unadjusted home  ", ORDER_JURIS),
            paste0("Language  ", ORDER_LANG_CONTRAST), "Framing  all models")
  st <- st %>% mutate(p = factor(panel, levels = intersect(pord, unique(panel))))

  band <- ggplot(st, aes(x = 100 * fraction)) +
    geom_ribbon(aes(ymin = p025, ymax = p975), fill = RULE, alpha = 0.55) +
    geom_ribbon(aes(ymin = p10, ymax = p90), fill = INK_FAINT, alpha = 0.55) +
    geom_hline(aes(yintercept = full_value), colour = ACCENT, linewidth = 0.3) +
    geom_line(aes(y = median_estimate), colour = INK, linewidth = 0.4) +
    facet_wrap(~ p, ncol = 5, scales = "free_y") +
    scale_x_continuous(breaks = c(10, 50, 100)) +
    labs(x = NULL, y = "Estimate (pp)") +
    theme_nature(base_size = PT_BODY, grid = "y") +
    theme(strip.text = element_text(size = PT_MIN),
          axis.text = element_text(size = PT_MIN)) + tag_only()

  # Sign agreement in a narrow ALIGNED strip, not on a second y-axis.
  strip <- ggplot(st, aes(x = 100 * fraction, y = sign_agreement)) +
    geom_hline(yintercept = 1, colour = RULE, linewidth = 0.3) +
    geom_line(colour = INK_SOFT, linewidth = 0.4) +
    facet_wrap(~ p, ncol = 5) +
    scale_x_continuous(breaks = c(10, 50, 100)) +
    scale_y_continuous(limits = c(0, 1), breaks = c(0, 1)) +
    labs(x = "Issue battery sampled (%)", y = "Sign agreement") +
    theme_nature(base_size = PT_BODY, grid = "y") +
    theme(strip.text = element_blank(), axis.text = element_text(size = PT_MIN)) +
    tag_only()

  ed3 <- (band / strip) + plot_layout(heights = c(2.5, 1)) +
    plot_annotation(tag_levels = "a")
  save_fig(ed3, file.path(ED_FIG, "ED3_sample_size_stability.png"),
           width = W2, height = H_TALL)
  figs$ED3_sample_size_stability <- ed3
}

# =============================================================================
# ED4 -- model x language heterogeneity
# =============================================================================
# ONE display, not two. The heatmap-plus-forest pair showed the same 44 numbers
# twice; the exact values live in c09, so the figure spends its space on the
# thing the table cannot show, which is the uncertainty.
#
# COMMON X-AXIS across the four language facets, so the ten-fold difference in
# dispersion between Hindi and Chinese is visible rather than normalised away.
c09 <- rd("c09_language_by_model.csv")
if (!is.null(c09)) {
  cat("ED4 language heterogeneity\n")
  bym <- c09 %>% filter(grouping == "model") %>%
    transmute(model = group, jurisdiction,
              language = factor(language_label, levels = ORDER_LANG_CONTRAST),
              estimate_pp, conf_low_pp, conf_high_pp) %>%
    mutate(m = factor(model, levels = rev(ORDER_MODEL)))
  lab4 <- bym %>% filter(abs(estimate_pp) >= 15)
  ed4 <- ggplot(bym, aes(x = estimate_pp, y = m)) +
    geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp,
                       colour = jurisdiction), linewidth = 0.4) +
    geom_point(aes(colour = jurisdiction), size = 1.1) +
    geom_text(data = lab4, aes(label = sprintf("%+.0f", estimate_pp)),
              hjust = -0.35, size = TXT, colour = INK_SOFT) +
    facet_wrap(~ language, nrow = 1) +
    scale_colour_manual(values = PAL_JURIS, breaks = ORDER_JURIS, name = NULL) +
    scale_y_discrete(limits = rev(ORDER_MODEL)) +
    scale_x_continuous(expand = expansion(mult = c(0.04, 0.12))) +
    labs(x = "Paired difference vs. English (pp)", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(size = PT_MIN, colour = INK),
          strip.text = element_text(size = PT_BODY),
          legend.position = "top", legend.text = element_text(size = PT_MIN),
          legend.key.size = unit(6, "pt")) +
    tag_only() + theme(plot.tag = element_blank())
  save_fig(ed4, file.path(ED_FIG, "ED4_language_heterogeneity.png"),
           width = W2, height = H_WIDE)
  figs$ED4_language_heterogeneity <- ed4
}

# =============================================================================
# ED5 -- ideological slant by model
# =============================================================================
# The five-bin composition is the PRIMARY estimand and is what is drawn: a
# signed mean alone would collapse a distribution that is 80-92% neutral into
# one number and invite over-reading of a tiny directional tail.
c13 <- rd("c13_ideology_by_model.csv")
if (!is.null(c13) && "quantity" %in% names(c13)) {
  cat("ED5 slant by model\n")
  BINL <- c(share_neg2 = "-2", share_neg1 = "-1", share_zero = "0",
            share_pos1 = "+1", share_pos2 = "+2")
  i5 <- c13 %>% filter(role == "PRIMARY") %>%
    mutate(bin = factor(unname(BINL[quantity]), levels = ORDER_IDEO_BIN),
           d = factor(dimension, levels = ORDER_IDEO_DIM),
           m = factor(model, levels = rev(ORDER_MODEL)),
           share = estimate * 100)
  stk <- position_stack(reverse = TRUE)
  ed5 <- ggplot(i5, aes(x = share, y = m, fill = bin)) +
    geom_col(width = 0.72, colour = "white", linewidth = 0.18, position = stk) +
    facet_wrap(~ d, nrow = 1) +
    scale_fill_manual(values = PAL_IDEO, name = NULL, breaks = ORDER_IDEO_BIN) +
    scale_y_discrete(limits = rev(ORDER_MODEL)) +
    scale_x_continuous(labels = label_percent(scale = 1, accuracy = 1),
                       breaks = c(0, 50), expand = expansion(mult = c(0, 0.02))) +
    labs(x = "Share of that model's engaged responses", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "none") +
    theme(axis.text.y = element_text(size = PT_MIN, colour = INK),
          strip.text = element_text(size = PT_BODY),
          legend.position = "top", legend.text = element_text(size = PT_MIN),
          legend.key.size = unit(5, "pt"),
          panel.spacing.x = unit(11, "pt")) +
    tag_only() + theme(plot.tag = element_blank())
  save_fig(ed5, file.path(ED_FIG, "ED5_slant_by_model.png"),
           width = W2, height = H_WIDE)
  figs$ED5_slant_by_model <- ed5
}

# =============================================================================
# ED6 -- moral foundations by model
# =============================================================================
# Point AND interval for every model-foundation cell: a heatmap without
# uncertainty would rank eleven models on differences the design may not
# resolve. The aggregate is a thin reference rule, deliberately subordinate.
c15 <- rd("c15_moral_by_model.csv"); c14 <- rd("c14_moral_prevalence_equal_model.csv")
if (!is.null(c15) && "conf_low" %in% names(c15)) {
  cat("ED6 foundations by model\n")
  m6 <- c15 %>% mutate(f = factor(foundation, levels = ORDER_FOUNDATION),
                       m = factor(model, levels = rev(ORDER_MODEL)))
  ref <- if (is.null(c14)) NULL else c14 %>% filter(scope == "overall") %>%
    transmute(f = factor(foundation, levels = ORDER_FOUNDATION), agg = estimate)
  ed6 <- ggplot(m6, aes(x = estimate * 100, y = m)) +
    { if (!is.null(ref))
        geom_vline(data = ref, aes(xintercept = agg * 100), colour = INK_FAINT,
                   linewidth = 0.25, linetype = "22") } +
    geom_linerange(aes(xmin = conf_low * 100, xmax = conf_high * 100,
                       colour = jurisdiction), linewidth = 0.4) +
    geom_point(aes(colour = jurisdiction), size = 1.1) +
    facet_wrap(~ f, nrow = 1) +
    scale_colour_manual(values = PAL_JURIS, breaks = ORDER_JURIS, name = NULL) +
    scale_y_discrete(limits = rev(ORDER_MODEL)) +
    scale_x_continuous(labels = label_percent(scale = 1, accuracy = 1),
                       breaks = c(0, 30, 60),
                       expand = expansion(mult = c(0.05, 0.05))) +
    labs(x = "Prevalence among that model's engaged responses", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(size = PT_MIN, colour = INK),
          axis.text.x = element_text(size = PT_MIN),
          strip.text = element_text(size = PT_MIN),
          legend.position = "top", legend.text = element_text(size = PT_MIN),
          legend.key.size = unit(6, "pt")) +
    tag_only() + theme(plot.tag = element_blank())
  save_fig(ed6, file.path(ED_FIG, "ED6_foundations_by_model.png"),
           width = W2, height = H_WIDE)
  figs$ED6_foundations_by_model <- ed6
}

# =============================================================================
# ED7 -- measurement reliability
# =============================================================================
# A compact dot matrix with ONE shared row-label column and no stems. The
# statistics keep separate facets because they are not commensurable: engagement
# scores alpha 0.51 and Gwet AC1 0.97 on the same labels. A structurally
# undefined cell gets an em dash, once, not a repeated sentence.
e23 <- rd("e23_reliability_pass1.csv"); e24 <- rd("e24_reliability_justification.csv")
e25 <- rd("e25_reliability_slant.csv")
if (!is.null(e23) && !is.null(e25)) {
  cat("ED7 measurement reliability\n")
  grab <- function(x, grp) if (is.null(x)) NULL else tibble(
    construct = x$construct, group = grp,
    `Raw agreement` = x$raw_agreement,
    `Krippendorff alpha` = x$krippendorff_alpha,
    `Gwet AC1 / AC2` = x$gwet_ac1,
    `Positive specific agreement` = if ("psa_mean" %in% names(x)) x$psa_mean else NA_real_)
  rel <- bind_rows(
    grab(e23, "Engagement"), grab(e24, "Justification"),
    grab(e25 %>% filter(grepl("ordinal", scale)), "Ideology"),
    grab(e25 %>% filter(!grepl("ordinal", scale)), "Foundations")) %>%
    mutate(construct = str_replace_all(construct, "_", " "),
           row = paste0(group, "  ", construct)) %>%
    arrange(factor(group, levels = c("Engagement", "Justification", "Ideology",
                                     "Foundations")),
            desc(`Krippendorff alpha`)) %>%
    mutate(r = fct_rev(fct_inorder(row)))
  long <- rel %>%
    pivot_longer(c(`Raw agreement`, `Krippendorff alpha`, `Gwet AC1 / AC2`,
                   `Positive specific agreement`),
                 names_to = "metric", values_to = "value") %>%
    mutate(metric = factor(metric, levels = c("Raw agreement", "Krippendorff alpha",
                                              "Gwet AC1 / AC2",
                                              "Positive specific agreement")))
  ed7 <- ggplot(long %>% filter(!is.na(value)), aes(x = value, y = r)) +
    geom_vline(xintercept = c(0, 0.5, 1), colour = RULE, linewidth = 0.25) +
    geom_point(aes(colour = group), size = 1.5) +
    geom_text(aes(label = sprintf("%.2f", value)), hjust = -0.4, size = TXT,
              colour = INK_SOFT) +
    geom_text(data = long %>% filter(is.na(value)), aes(x = 0.5, y = r),
              inherit.aes = FALSE, label = "—", size = TXT, colour = INK_FAINT) +
    facet_wrap(~ metric, nrow = 1) +
    scale_colour_manual(values = c(Engagement = ACCENT, Justification = ACCENT_2,
                                   Ideology = INK_SOFT, Foundations = INK),
                        name = NULL) +
    scale_x_continuous(limits = c(0, 1.25), breaks = c(0, 0.5, 1),
                       expand = expansion(mult = c(0.02, 0))) +
    labs(x = NULL, y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "none") +
    theme(axis.text.y = element_text(size = PT_MIN, colour = INK),
          axis.text.x = element_text(size = PT_MIN),
          strip.text = element_text(size = PT_MIN),
          legend.position = "top", legend.text = element_text(size = PT_MIN),
          legend.key.size = unit(6, "pt"),
          panel.spacing.x = unit(3, "pt")) +
    tag_only() + theme(plot.tag = element_blank())
  save_fig(ed7, file.path(ED_FIG, "ED7_measurement_reliability.png"),
           width = W2, height = H_WIDE)
  figs$ED7_measurement_reliability <- ed7
}

# =============================================================================
# ED8 -- prompt-semantic UMAP
# =============================================================================
# ONE fixed geometry, reused in every panel. Colour is a refusal PROPENSITY
# across models, on a shared perceptually-uniform scale -- never a binary "ever
# refused", which would make a prompt one model declined look identical to one
# that all eleven declined.
c22 <- rd("c22_prompt_umap_coordinates.csv")
if (!is.null(c22) && nrow(c22)) {
  cat("ED8 prompt-semantic UMAP\n")
  panels <- c(ALL = "All languages", en = "English", zh = "Chinese",
              ar = "Arabic", ru = "Russian", hi = "Hindi")
  long8 <- map_dfr(names(panels), function(k) {
    col <- if (k == "ALL") "refusal_propensity_all" else paste0("refusal_", k)
    if (!col %in% names(c22)) return(NULL)
    c22 %>% transmute(umap_x, umap_y, p = .data[[col]],
                      panel = factor(unname(panels[k]), levels = unname(panels)))
  })
  LIMP <- c(0, max(long8$p, na.rm = TRUE))
  ed8 <- ggplot(long8 %>% arrange(p), aes(umap_x, umap_y, colour = p)) +
    geom_point(size = 0.22, alpha = 0.85, shape = 16) +
    facet_wrap(~ panel, nrow = 2) +
    scale_colour_viridis_c(option = "magma", direction = -1, limits = LIMP,
                           breaks = c(0, 0.25, 0.50),
                           labels = label_percent(accuracy = 1), name = NULL,
                           guide = guide_colourbar(barwidth = unit(70, "pt"),
                                                   barheight = unit(4, "pt"),
                                                   ticks = FALSE)) +
    coord_fixed() +
    labs(x = NULL, y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "none") +
    theme(axis.text = element_blank(), axis.ticks = element_blank(),
          axis.ticks.length = unit(0, "pt"),
          axis.line = element_blank(), axis.line.x = element_blank(),
          strip.text = element_text(size = PT_BODY),
          legend.position = "top", legend.text = element_text(size = PT_MIN),
          panel.spacing = unit(3, "pt")) +
    tag_only() + theme(plot.tag = element_blank())
  save_fig(ed8, file.path(ED_FIG, "ED8_prompt_semantic_umap.png"),
           width = W2, height = H_STD)
  figs$ED8_prompt_semantic_umap <- ed8

  # ---- ED9: the same geometry, one panel per model -------------------------
  bym9 <- rd("c22_prompt_refusal_by_model.csv")
  if (!is.null(bym9) && nrow(bym9)) {
    cat("ED9 UMAP by model\n")
    # In a single language a single model either refused a prompt or did not, so
    # this quantity is BINARY by construction -- a continuous ramp would imply a
    # gradation that does not exist here. Two levels, one of them near-invisible,
    # so the eye reads the refusals as marks on a common ground rather than
    # hunting shades. The continuous propensity across models is ED8.
    d9 <- bym9 %>% inner_join(c22 %>% select(prompt_id, umap_x, umap_y),
                              by = "prompt_id") %>%
      mutate(m = factor(model, levels = ORDER_MODEL),
             r = factor(ifelse(refused > 0.5, "refused", "engaged"),
                        levels = c("engaged", "refused")))
    ed9 <- ggplot(d9 %>% arrange(r), aes(umap_x, umap_y, colour = r, size = r)) +
      geom_point(alpha = 0.9, shape = 16) +
      facet_wrap(~ m, nrow = 3) +
      scale_colour_manual(values = c(engaged = "#E4E6E4", refused = ACCENT),
                          name = NULL) +
      scale_size_manual(values = c(engaged = 0.14, refused = 0.34), guide = "none") +
      coord_fixed() + labs(x = NULL, y = NULL) +
      theme_nature(base_size = PT_BODY, grid = "none") +
      theme(axis.text = element_blank(), axis.ticks = element_blank(),
            axis.ticks.length = unit(0, "pt"),
            axis.line = element_blank(), axis.line.x = element_blank(),
            strip.text = element_text(size = PT_MIN),
            legend.position = "top", legend.text = element_text(size = PT_MIN),
            legend.key.size = unit(6, "pt"),
            panel.spacing = unit(2, "pt")) +
      tag_only() + theme(plot.tag = element_blank())
    save_fig(ed9, file.path(ED_FIG, "ED9_prompt_semantic_umap_by_model.png"),
             width = W2, height = H_STD)
    figs$ED9_prompt_semantic_umap_by_model <- ed9
  }
}

# =============================================================================
# ED10 -- prompt framing: boundary minus regular
# =============================================================================
# MOVED OUT OF FIGURE 2, NOT DROPPED. Framing is a different exposure answered
# by a different block from the language contrast, and pairing the two forced
# both into a half-height panel. Nothing about the estimand changed.
cat("ED10 framing\n")
c10 <- rd("c10_framing_paired.csv"); c11 <- rd("c11_framing_by_model_domain.csv")
if (!is.null(c10) && !is.null(c11)) {
  fr_all <- c10 %>% filter(scope == "overall") %>%
    transmute(g = "All models", estimate_pp, conf_low_pp, conf_high_pp)
  fr_m <- c11 %>% filter(grouping == "model") %>%
    transmute(g = group, estimate_pp, conf_low_pp, conf_high_pp)
  # A model with an exactly zero point AND a zero-width interval never refused
  # in either arm: structural, not a precisely estimated null.
  fr_z <- fr_m %>% filter(estimate_pp == 0, conf_low_pp == 0, conf_high_pp == 0)
  fr_m <- fr_m %>% anti_join(fr_z, by = "g")
  # FIXED model order from _orders.R, not the observed effects.
  mord <- intersect(ORDER_MODEL, c(fr_m$g, fr_z$g))
  ypos <- tibble(g = c("All models", mord), y = seq_len(length(mord) + 1))
  fr <- bind_rows(fr_all, fr_m) %>% left_join(ypos, by = "g") %>%
    mutate(pooled = g == "All models")
  fr_z <- fr_z %>% left_join(ypos, by = "g")

  ed10 <- ggplot(fr, aes(x = estimate_pp, y = y)) +
    geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
    # A rule under the pooled row: it is the estimate; the rows below it are
    # exploratory heterogeneity, not eleven separate findings.
    geom_hline(yintercept = 1.5, colour = RULE, linewidth = 0.4) +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp,
                       colour = pooled, linewidth = pooled)) +
    geom_point(aes(fill = pooled, size = pooled, shape = pooled),
               colour = "white", stroke = 0.3) +
    { if (nrow(fr_z))
        geom_point(data = fr_z, aes(x = 0, y = y), inherit.aes = FALSE,
                   shape = SHAPE_NOT_ESTIMABLE, size = 1.5, colour = INK_FAINT,
                   stroke = 0.4) } +
    { if (nrow(fr_z))
        geom_text(data = fr_z, aes(x = 0, y = y), inherit.aes = FALSE,
                  label = NOT_ESTIMABLE_TEXT, hjust = -0.16, size = TXT,
                  colour = INK_FAINT) } +
    geom_text(data = filter(fr, pooled),
              aes(x = conf_high_pp, label = fmt_pp(estimate_pp)), hjust = -0.32,
              size = TXT, fontface = "bold", colour = INK) +
    scale_colour_manual(values = c(`TRUE` = INK, `FALSE` = INK_SOFT), guide = "none") +
    scale_fill_manual(values = c(`TRUE` = INK, `FALSE` = INK_SOFT), guide = "none") +
    scale_size_manual(values = c(`TRUE` = 2.4, `FALSE` = 1.4), guide = "none") +
    scale_shape_manual(values = c(`TRUE` = 23, `FALSE` = 21), guide = "none") +
    scale_linewidth_manual(values = c(`TRUE` = 0.5, `FALSE` = 0.35), guide = "none") +
    scale_y_reverse(breaks = ypos$y, labels = ypos$g,
                    expand = expansion(add = c(0.7, 0.7))) +
    scale_x_continuous(expand = expansion(mult = c(0.05, 0.12))) +
    labs(x = "Boundary - regular (pp)", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(size = PT_MIN),
          axis.ticks.y = element_blank()) +
    tag_only() + theme(plot.tag = element_blank())
  save_fig(ed10, file.path(ED_FIG, "ED10_framing.png"), width = W2, height = H_SHORT)
  figs$ED10_framing <- ed10
}

# A PREVIEW RENDER MUST NOT TOUCH THE PROMOTED TREE -- see 20_figures_main.R for
# why. Figures somewhere else plus estimates in the promoted tree means preview.
{
  same <- function(a, b) identical(normalizePath(a, mustWork = FALSE),
                                   normalizePath(b, mustWork = FALSE))
  if (same(CAN_EST, "pipeline/estimates/canonical") &&
      !same(ED_FIG, "pipeline/figures/extended")) {
    cat("  preview render: layout artefact NOT written to the promoted tree\n")
  } else saveRDS(figs, file.path(CAN_EST, "c20_figure_layout_extended.rds"))
}
cat("\nwrote:\n"); print(list.files(ED_FIG))
cat("\n", strrep("=", 78), "\nEXTENDED DATA DONE\n", strrep("=", 78), "\n", sep = "")
