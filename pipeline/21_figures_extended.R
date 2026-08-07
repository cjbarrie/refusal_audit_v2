# =============================================================================
# EXTENDED DATA FIGURES -- ED1 .. ED4
# =============================================================================
#   ED1  judge sensitivity: every judge on ONE common-support sample
#   ED2  grouped sensitivity panels for the home contrast
#   ED3  refusal-text projection (diagnostic only)
#   ED4  language: weighting comparison and per-model intervals
#
# Like the main figures, these read tables and fit nothing.

source("pipeline/_theme.R")
suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork)
})

CAN_EST <- Sys.getenv("CANON_EST_DIR", "pipeline/estimates/canonical")
ED_FIG  <- Sys.getenv("CANON_APPFIG_DIR", "pipeline/figures/extended")
dir.create(ED_FIG, showWarnings = FALSE, recursive = TRUE)
rd <- function(f) { p <- file.path(CAN_EST, f)
  if (file.exists(p)) read_csv(p, show_col_types = FALSE) else NULL }
rdp <- function(f) { p <- file.path("pipeline/estimates", f)
  if (file.exists(p)) read_csv(p, show_col_types = FALSE) else NULL }

theme_set(theme_nature(base_size = PT_BODY))
tagt <- theme(plot.tag = element_text(family = FONT_SANS, face = "bold",
                                      size = PT_TAG, colour = INK),
              plot.tag.position = c(0, 1),
              plot.title = element_text(colour = INK, face = "bold",
                                        size = PT_TITLE, hjust = 0,
                                        margin = margin(b = 2, l = 14)),
              plot.subtitle = element_text(colour = INK_SOFT, size = PT_BODY,
                                           hjust = 0, margin = margin(b = 4, l = 14)))
JORD <- c("CN", "MENA", "India", "US", "EU")
TXT <- pt_to_mm(PT_MIN); LWC <- 0.45
ENVL <- "OBSERVED JUDGE SENSITIVITY ENVELOPE"

cat(strrep("=", 78), "\nEXTENDED DATA FIGURES\n", strrep("=", 78), "\n", sep = "")

# =============================================================================
# ED1 -- judge sensitivity on common support
# =============================================================================
c17b <- rd("c17b_judge_envelope.csv"); c17c <- rd("c17c_judge_support.csv")
if (!is.null(c17b) && nrow(c17b) && "estimable" %in% names(c17b)) {
  cat("ED1 judge sensitivity\n")
  d <- c17b %>% filter(estimable, judge_model != ENVL) %>%
    mutate(canonical = grepl("gemini", judge_model, fixed = TRUE),
           judge = str_remove(judge_model, "^[a-z]+/"),
           j = factor(jurisdiction, levels = JORD))
  env <- c17b %>% filter(estimable, judge_model == ENVL) %>%
    mutate(j = factor(jurisdiction, levels = JORD))
  jord <- d %>% distinct(judge, canonical) %>% arrange(desc(canonical), judge)
  d <- d %>% mutate(judge = factor(judge, levels = rev(jord$judge)))

  ed1 <- ggplot(d, aes(x = estimate_pp, y = judge)) +
    geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
    geom_rect(data = env, inherit.aes = FALSE,
              aes(xmin = conf_low_pp, xmax = conf_high_pp, ymin = -Inf, ymax = Inf),
              fill = INK_FAINT, alpha = 0.15) +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp,
                       colour = jurisdiction), linewidth = LWC) +
    geom_point(aes(fill = jurisdiction, shape = canonical), size = 1.5,
               colour = "white", stroke = 0.35) +
    scale_shape_manual(values = c(`TRUE` = 21, `FALSE` = 22), guide = "none") +
    scale_colour_manual(values = PAL_JURIS, guide = "none") +
    scale_fill_manual(values = PAL_JURIS, guide = "none") +
    facet_wrap(~ j, ncol = 2, scales = "free_x") +
    labs(x = "Home - away difference (pp)", y = NULL,
         title = "Standardized contrast under each judge",
         subtitle = paste("ALL judges recomputed on ONE common-support sample.",
                          "Shaded band = observed judge envelope, NOT a confidence interval.",
                          "Circle = canonical judge.")) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(size = PT_MIN),
          strip.text = element_text(size = PT_BODY)) + tagt
  save_fig(ed1, file.path(ED_FIG, "ED1_judge_sensitivity.png"),
           width = W2, height = 3.4)
}

# =============================================================================
# ED2 -- grouped sensitivity panels
# =============================================================================
c07 <- rd("c07_home_sensitivities.csv"); c04 <- rd("c04_home_standardized.csv")
if (!is.null(c07)) {
  cat("ED2 sensitivity panels\n")
  # Grouped by WHAT IS BEING VARIED, not strung on one curve. A specification
  # curve implies every row is an alternative way of estimating one quantity;
  # these are not that. Two rows in particular are different in kind:
  #   hierarchical_marginal is a DIFFERENT ESTIMAND (it integrates over the
  #     issue random effect instead of standardizing over the observed issues),
  #     so it is drawn in its own panel;
  #   min_response_chars conditions on a POST-OUTCOME property of the response,
  #     so it is a data-quality diagnostic, not a robustness check of the design.
  GRP <- tribble(
    ~sensitivity,            ~panel,
    "leave_one_model_out",   "Model composition",
    "prompt_type",           "Prompt tier",
    "language",              "Language",
    "outcome_code3",         "Outcome definition",
    "overlap_restricted",    "Support restriction",
    "min_response_chars",    "Data quality (post-outcome)",
    "hierarchical_marginal", "DIFFERENT ESTIMAND: hierarchical marginal")
  PORD <- unique(GRP$panel)
  sc <- c07 %>% filter(estimable) %>% left_join(GRP, by = "sensitivity") %>%
    filter(!is.na(panel)) %>%
    mutate(panel = factor(panel, levels = PORD),
           j = factor(jurisdiction, levels = JORD),
           row = paste0(level, "  [", jurisdiction, "]"))
  prim <- c04 %>% filter(weighting == "nested", support == "full target",
                         estimator == "maximum likelihood", estimable) %>%
    transmute(j = factor(jurisdiction, levels = JORD), estimate_pp)

  ed2 <- ggplot(sc, aes(x = estimate_pp, y = fct_rev(fct_inorder(row)),
                        colour = j)) +
    geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), linewidth = 0.35) +
    geom_point(aes(fill = j), shape = 21, size = 1.2, colour = "white", stroke = 0.25) +
    scale_colour_manual(values = PAL_JURIS, name = NULL) +
    scale_fill_manual(values = PAL_JURIS, guide = "none") +
    facet_wrap(~ panel, scales = "free", ncol = 2) +
    labs(x = "Home - away difference (pp)", y = NULL,
         title = "Sensitivity of the standardized contrast, grouped by what varies",
         subtitle = "dashed vertical rule in each panel is the primary estimate for that jurisdiction") +
    geom_vline(data = prim, aes(xintercept = estimate_pp, colour = j),
               linewidth = 0.3, linetype = "22", show.legend = FALSE) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(size = PT_MIN),
          strip.text = element_text(size = PT_MIN),
          legend.position = "top", legend.text = element_text(size = PT_MIN),
          legend.key.size = unit(6, "pt")) + tagt
  save_fig(ed2, file.path(ED_FIG, "ED2_sensitivity_panels.png"),
           width = W2, height = 7.0)
}

# =============================================================================
# ED3 -- refusal-text projection (DIAGNOSTIC ONLY)
# =============================================================================
u1 <- rdp("u01_refusal_umap.csv"); u2 <- rdp("u02_refusal_umap_all_languages.csv")
u3 <- rdp("u03_refusal_umap_lexical.csv")
if (!is.null(u1)) {
  cat("ED3 refusal-text projection\n")
  # Axes stripped: a UMAP layout has no units and only local distances are
  # faithful. The .x/.y sub-elements must be blanked individually because
  # theme_nature sets them explicitly.
  no_axes <- theme(
    axis.text.x = element_blank(), axis.text.y = element_blank(),
    axis.title.x = element_blank(), axis.title.y = element_blank(),
    axis.ticks.x = element_blank(), axis.ticks.y = element_blank(),
    axis.line.x = element_blank(), axis.line.y = element_blank(),
    panel.border = element_rect(fill = NA, colour = RULE, linewidth = 0.25),
    legend.position = "top", legend.text = element_text(size = PT_MIN),
    legend.key.size = unit(6, "pt"), legend.margin = margin(0, 0, 0, 0))
  trim <- function(d) {
    qx <- quantile(d$umap_x, c(0.015, 0.985)); qy <- quantile(d$umap_y, c(0.015, 0.985))
    d[d$umap_x >= qx[1] & d$umap_x <= qx[2] & d$umap_y >= qy[1] & d$umap_y <= qy[2], ]
  }
  mk <- function(d, aesx, ttl, sub) {
    ggplot(trim(d), aesx) +
      geom_point(size = 0.35, alpha = 0.65, stroke = 0) +
      coord_equal(clip = "on") + labs(title = ttl, subtitle = sub) +
      theme_nature(base_size = PT_BODY, grid = "none") + no_axes + tagt
  }
  pa <- mk(u1 %>% mutate(reason = factor(reason_group, levels = names(PAL_REASON))) %>%
             arrange(reason),
           aes(umap_x, umap_y, colour = reason),
           "English refusals, semantic space",
           sprintf("purity %.2f vs %.2f at random (embedding space)",
                   u1$purity_group_observed[1], u1$purity_group_baseline[1])) +
    scale_colour_manual(values = PAL_REASON, name = NULL, drop = FALSE) +
    guides(colour = guide_legend(override.aes = list(size = 1.4, alpha = 1), nrow = 2))
  LN <- c(en = "English", zh = "Chinese", ar = "Arabic", ru = "Russian", hi = "Hindi")
  pb <- if (is.null(u2)) NULL else
    mk(u2 %>% mutate(l = factor(unname(LN[prompt_language]), levels = names(PAL_LANGUAGE))) %>%
         arrange(l), aes(umap_x, umap_y, colour = l),
       "All five languages", "language dominates") +
    scale_colour_manual(values = PAL_LANGUAGE, name = NULL, drop = FALSE) +
    guides(colour = guide_legend(override.aes = list(size = 1.4, alpha = 1), nrow = 2))
  pc <- if (is.null(u3)) NULL else
    mk(u3 %>% mutate(reason = factor(reason_group, levels = names(PAL_REASON))) %>%
         arrange(reason), aes(umap_x, umap_y, colour = reason),
       "English, lexical representation",
       sprintf("purity %.2f vs %.2f at random", u3$purity_group_observed[1],
               u3$purity_group_baseline[1])) +
    scale_colour_manual(values = PAL_REASON, name = NULL, drop = FALSE) +
    guides(colour = guide_legend(override.aes = list(size = 1.4, alpha = 1), nrow = 2))

  # Two rows. In one row, coord_equal gives each panel a different width
  # depending on its data aspect, and the middle panel's subtitle ran underneath
  # the next panel's tag.
  bot <- Filter(Negate(is.null), list(pb, pc))
  ed3 <- if (!length(bot)) pa else pa / wrap_plots(bot, nrow = 1) +
    plot_layout(heights = c(1, 1))
  ed3 <- ed3 + plot_annotation(tag_levels = "a")
  save_fig(ed3, file.path(ED_FIG, "ED3_refusal_text_projection.png"),
           width = W2, height = 5.2)
}

# =============================================================================
# ED4 -- language: weighting comparison and per-model intervals
# =============================================================================
c08 <- rd("c08_language_paired.csv"); c09 <- rd("c09_language_by_model.csv")
if (!is.null(c08)) {
  cat("ED4 language weighting and per-model intervals\n")
  LORD <- c("Arabic", "Chinese", "Hindi", "Russian")
  w <- c08 %>% filter(sensitivity == "primary") %>%
    mutate(l = factor(language_label, levels = rev(LORD)),
           weighting = factor(weighting,
                              levels = c("pooled", "equal_model", "equal_model_issue")))
  pa <- ggplot(w, aes(x = estimate_pp, y = l, shape = weighting)) +
    geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                   position = position_dodge(width = 0.6), colour = INK,
                   linewidth = LWC) +
    geom_point(position = position_dodge(width = 0.6), size = 1.5, fill = ACCENT,
               colour = "white", stroke = 0.3) +
    scale_shape_manual(values = c(pooled = 21, equal_model = 22,
                                  equal_model_issue = 24), name = NULL,
                       labels = c("pooled", "equal per model (PRIMARY)",
                                  "equal per model x issue")) +
    scale_y_discrete(limits = rev(LORD)) +
    labs(x = "Paired difference vs. English (pp)", y = NULL,
         title = "Weighting comparison",
         subtitle = "the main figure reports the predeclared primary weighting only") +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(legend.position = "top", legend.text = element_text(size = PT_MIN),
          legend.key.size = unit(6, "pt")) + tagt

  pb <- if (is.null(c09)) NULL else {
    bym <- c09 %>% filter(grouping == "model") %>%
      mutate(language = factor(language_label, levels = LORD))
    mo <- bym %>% group_by(group) %>% summarise(m = mean(estimate_pp), .groups = "drop") %>%
      arrange(m) %>% pull(group)
    ggplot(bym, aes(x = estimate_pp, y = factor(group, levels = mo))) +
      geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
      geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), linewidth = 0.3,
                     colour = INK) +
      geom_point(size = 0.9, colour = INK) +
      facet_wrap(~ language, nrow = 1, scales = "free_x") +
      labs(x = "Paired difference vs. English (pp)", y = NULL,
           title = "Per-model intervals",
           subtitle = "the values behind the main-figure heatmap") +
      theme_nature(base_size = PT_BODY, grid = "x") +
      theme(axis.text.y = element_text(size = PT_MIN),
            strip.text = element_text(size = PT_MIN)) + tagt
  }
  ed4 <- if (is.null(pb)) pa else pa / pb + plot_layout(heights = c(1, 1.3))
  ed4 <- ed4 + plot_annotation(tag_levels = "a")
  save_fig(ed4, file.path(ED_FIG, "ED4_language_detail.png"), width = W2, height = 4.6)
}

cat("\nwrote:\n"); print(list.files(ED_FIG))
cat("\n", strrep("=", 78), "\nEXTENDED DATA DONE\n", strrep("=", 78), "\n", sep = "")
