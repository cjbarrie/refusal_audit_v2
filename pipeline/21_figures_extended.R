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
CANONICAL_RUN_ID <- Sys.getenv("CANONICAL_RUN_ID", "unset")
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
ENVL <- "OBSERVED JUDGE POINT ENVELOPE"

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

  # The shaded band this replaces was the UNION OF PER-JUDGE BOOTSTRAP
  # INTERVALS drawn behind the intervals themselves, which reads as a confidence
  # region for judge uncertainty. It is not one. What is drawn now: each judge's
  # own sampling interval, plus a thin bracket spanning the RANGE OF JUDGE POINT
  # ESTIMATES -- the instrument-variation quantity, which contains no sampling
  # uncertainty at all.
  brk <- env %>% transmute(j, lo = point_envelope_low_pp, hi = point_envelope_high_pp) %>%
    filter(is.finite(lo), is.finite(hi))
  ytop <- length(unique(d$judge)) + 0.45
  brk <- brk %>% mutate(y = ytop, ylo = ytop - 0.12, yhi = ytop + 0.12,
                        ytxt = ytop + 0.30, mid = (lo + hi) / 2,
                        lab = "range of judge point estimates")
  ed1 <- ggplot(d, aes(x = estimate_pp, y = judge)) +
    geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp,
                       colour = jurisdiction), linewidth = LWC) +
    geom_point(aes(fill = jurisdiction, shape = canonical), size = 1.5,
               colour = "white", stroke = 0.35) +
    # bracket: horizontal span with short end ticks, above the judge rows
    geom_segment(data = brk, aes(x = lo, xend = hi, y = y, yend = y),
                 inherit.aes = FALSE, colour = INK, linewidth = 0.35) +
    geom_segment(data = brk, aes(x = lo, xend = lo, y = ylo, yend = yhi),
                 inherit.aes = FALSE, colour = INK, linewidth = 0.35) +
    geom_segment(data = brk, aes(x = hi, xend = hi, y = ylo, yend = yhi),
                 inherit.aes = FALSE, colour = INK, linewidth = 0.35) +
    geom_text(data = brk, aes(x = mid, y = ytxt, label = lab),
              inherit.aes = FALSE, size = TXT, colour = INK_SOFT) +
    scale_shape_manual(values = c(`TRUE` = 21, `FALSE` = 22), guide = "none") +
    scale_colour_manual(values = PAL_JURIS, guide = "none") +
    scale_fill_manual(values = PAL_JURIS, guide = "none") +
    scale_y_discrete(limits = levels(d$judge),
                     expand = expansion(add = c(0.6, 1.1))) +
    facet_wrap(~ j, ncol = 2, scales = "free_x") +
    labs(x = "Home - away difference (pp)", y = NULL,
         title = "Standardized contrast under each judge",
         subtitle = paste("all judges recomputed on ONE common-support sample;",
                          "coloured bars are each judge's sampling interval;",
                          "circle = canonical judge")) +
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
  # SPLIT BY KIND. Inferential sensitivities -- alternative but comparable ways
  # of estimating the same target -- go in the forest. Post-outcome diagnostics
  # (response-length filters condition on a property of the response, i.e. after
  # the outcome) are a different kind of claim and are labelled as such. The
  # hierarchical marginal estimate is a DIFFERENT ESTIMAND with no comparable
  # interval, so it is removed from the forest entirely and written to a small
  # separately labelled table instead of being read as a competing point.
  GRP <- tribble(
    ~sensitivity,            ~panel,                        ~kind,
    "leave_one_model_out",   "Model composition",           "inferential",
    "prompt_type",           "Prompt tier",                 "inferential",
    "language",              "Language",                    "inferential",
    "outcome_code3",         "Outcome definition",          "inferential",
    "functional_form",       "Functional form",             "inferential",
    "overlap_restricted",    "Support restriction",         "inferential",
    "min_response_chars",    "Response-length filter",      "post-outcome diagnostic")
  PORD <- unique(GRP$panel)
  sc <- c07 %>% filter(estimable) %>% left_join(GRP, by = "sensitivity") %>%
    filter(!is.na(panel)) %>%
    mutate(panel = factor(panel, levels = PORD),
           j = factor(jurisdiction, levels = JORD),
           row = paste0(level, "  [", jurisdiction, "]"))
  prim <- c04 %>% filter(weighting == "nested", support == "full target",
                         estimator == "maximum likelihood", estimable) %>%
    transmute(jurisdiction, estimate_pp) %>%
    inner_join(sc %>% distinct(panel, jurisdiction), by = "jurisdiction") %>%
    mutate(j = factor(jurisdiction, levels = JORD))

  # The hierarchical rows leave the figure and become a table.
  hier <- c07 %>% filter(sensitivity == "hierarchical_marginal")
  if (nrow(hier))
    write_csv(hier %>% mutate(
        note = paste("DIFFERENT ESTIMAND: integrates over the issue random",
                     "effect instead of standardizing over the observed issue",
                     "set. Not comparable to the forest above and deliberately",
                     "not plotted beside it.")),
      file.path(CAN_EST, "c07b_hierarchical_marginal.csv"))

  mk_forest <- function(dd, ttl, sub) {
    pr <- prim %>% semi_join(dd %>% distinct(panel), by = "panel")
    # Row ordering computed here, not inside aes(): fct_inorder() inside an
    # aesthetic makes the plot depend on evaluation order at build time.
    dd <- dd %>% mutate(row_f = fct_rev(fct_inorder(row)))
    ggplot(dd, aes(x = estimate_pp, y = row_f, colour = j)) +
      geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
      geom_vline(data = pr, aes(xintercept = estimate_pp, colour = j),
                 linewidth = 0.3, linetype = "22", show.legend = FALSE) +
      geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), linewidth = 0.35) +
      geom_point(aes(fill = j), shape = 21, size = 1.2, colour = "white", stroke = 0.25) +
      scale_colour_manual(values = PAL_JURIS, name = NULL) +
      scale_fill_manual(values = PAL_JURIS, guide = "none") +
      facet_wrap(~ panel, scales = "free", ncol = 2) +
      labs(x = "Home - away difference (pp)", y = NULL, title = ttl, subtitle = sub) +
      theme_nature(base_size = PT_BODY, grid = "x") +
      theme(axis.text.y = element_text(size = PT_MIN),
            strip.text = element_text(size = PT_MIN),
            legend.position = "top", legend.text = element_text(size = PT_MIN),
            legend.key.size = unit(6, "pt")) + tagt
  }
  inf_d <- sc %>% filter(kind == "inferential") %>% mutate(panel = droplevels(panel))
  dia_d <- sc %>% filter(kind != "inferential") %>% mutate(panel = droplevels(panel))
  ed2 <- mk_forest(inf_d, "Inferential sensitivities",
                   "alternative but comparable estimators of the same target; dashed rule = primary estimate") /
    mk_forest(dia_d, "Post-outcome data-quality diagnostics",
              "these condition on a property of the response, i.e. AFTER the outcome; not design robustness") +
    plot_layout(heights = c(2.6, 1)) + plot_annotation(tag_levels = "a")
  save_fig(ed2, file.path(ED_FIG, "ED2_sensitivity_panels.png"),
           width = W2, height = 8.2)
}

# =============================================================================
# The refusal-text projection is RETIRED (was ED3)
# =============================================================================
# It is not rebuilt here and no longer ships. Three reasons, none of them
# cosmetic:
#   * it was visually uninformative -- a diffuse cloud with heavy overlap;
#   * LEXICAL purity (0.58) was at least as high as SEMANTIC purity (0.57),
#     so the projection did not show that the judge's reason codes track
#     meaning, which was the only question it was built to answer;
#   * it was never rebuilt by make_release.R, so what shipped could silently
#     date from a different run than every other figure.
# scripts/refusal_umap.py and the u01-u03 outputs move to
# pipeline/archive/exploratory_umap/ for provenance. Nothing in the canonical
# layer reads them.

# =============================================================================
# ED3 -- language: per-model intervals (weighting comparison is a table)
# =============================================================================
c08 <- rd("c08_language_paired.csv"); c09 <- rd("c09_language_by_model.csv")
if (!is.null(c08)) {
  cat("ED3 language detail\n")
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
    bym <- bym %>% mutate(group_f = factor(group, levels = mo))
    ggplot(bym, aes(x = estimate_pp, y = group_f)) +
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
  # The three weightings agree to within a fraction of a point, so the
  # comparison is a TABLE (c08 already holds every row) and the figure space
  # goes to the per-model intervals, which carry information the heatmap in the
  # main figure cannot.
  write_csv(w %>% transmute(language = language_label, weighting,
                            estimate_pp, conf_low_pp, conf_high_pp,
                            note = "weighting comparison; the three agree closely, so this is tabulated rather than plotted",
                            canonical_run_id = CANONICAL_RUN_ID),
            file.path(CAN_EST, "c08b_weighting_comparison.csv"))
  ed4 <- if (is.null(pb)) pa else pb
  ed4 <- ed4 + plot_annotation(tag_levels = "a")
  save_fig(ed4, file.path(ED_FIG, "ED3_language_detail.png"), width = W2, height = 4.2)
}

saveRDS(Filter(Negate(is.null),
               list(ED1_judge_sensitivity = if (exists("ed1")) ed1 else NULL,
                    ED2_sensitivity_panels = if (exists("ed2")) ed2 else NULL,
                    ED3_language_detail = if (exists("ed4")) ed4 else NULL)),
        file.path(CAN_EST, "c20_figure_layout_extended.rds"))

cat("\nwrote:\n"); print(list.files(ED_FIG))
cat("\n", strrep("=", 78), "\nEXTENDED DATA DONE\n", strrep("=", 78), "\n", sep = "")
