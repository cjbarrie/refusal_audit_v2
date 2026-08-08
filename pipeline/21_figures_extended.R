# =============================================================================
# EXTENDED DATA FIGURES -- ED1 .. ED5
# =============================================================================
#   ED1  judge sensitivity: PAIRED difference from the canonical judge
#   ED2  inferential robustness of the home contrast, BY JURISDICTION
#   ED3  post-outcome data-quality diagnostics (response-length filters)
#   ED4  language heterogeneity: the model x language matrix and its intervals
#   ED5  measurement reliability: construct x metric
#
# Like the main figures, these read tables and fit nothing. No titles, no
# subtitles, no prose inside a panel -- see docs/CANONICAL_FIGURE_LEGENDS.md.

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

theme_set(theme_nature(base_size = PT_BODY))
JORD <- c("CN", "MENA", "India", "US", "EU")
TXT <- pt_to_mm(PT_MIN); LWC <- 0.45
short_judge <- function(x) str_remove(x, "^[a-z]+/")

cat(strrep("=", 78), "\nEXTENDED DATA FIGURES\n", strrep("=", 78), "\n", sep = "")
figs <- list()

# =============================================================================
# ED1 -- judge sensitivity as a PAIRED difference from the canonical judge
# =============================================================================
# The question is "how far does the estimate move when the judge changes", so
# the figure plots that quantity directly: c17d, the paired difference
# theta_j - theta_canonical, formed INSIDE each bootstrap replicate on one
# shared issue draw.
#
# What this replaces: four absolute estimates per jurisdiction, which asked the
# reader to difference overlapping intervals by eye. Differencing them on the
# page would also be wrong -- the judges label the SAME responses, so their
# estimates are strongly dependent and a marginal-interval subtraction is far
# too wide. The absolute estimates remain tabulated in c17b.
#
# The "range of judge point estimates" bracket is gone. With every judge's
# deviation drawn, it restated the spread of the points beneath it.
#
# Zero = this judge reproduces the canonical judge. The canonical judge is a
# REFERENCE INSTRUMENT, not ground truth.
c17d <- rd("c17d_judge_paired_differences.csv")
if (!is.null(c17d) && nrow(c17d) && "estimable" %in% names(c17d)) {
  cat("ED1 judge sensitivity (paired)\n")
  d <- c17d %>% filter(estimable, !is_canonical_judge) %>%
    mutate(judge = short_judge(judge_model),
           j = factor(jurisdiction, levels = JORD))
  ne <- c17d %>% filter(!estimable) %>% distinct(jurisdiction) %>%
    mutate(j = factor(jurisdiction, levels = JORD))
  jl <- sort(unique(d$judge))
  d <- d %>% mutate(judge_f = factor(judge, levels = rev(jl)))

  # Greys, not jurisdiction colour: these rows are instruments, and the
  # jurisdiction is already named by the facet.
  ed1 <- ggplot(d, aes(x = estimate_pp, y = judge_f)) +
    # Zero is the canonical reference, so it is the strongest rule here.
    geom_vline(xintercept = 0, colour = ACCENT, linewidth = 0.35) +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), colour = INK,
                   linewidth = LWC) +
    geom_point(shape = 21, size = 1.6, fill = INK_SOFT, colour = "white",
               stroke = 0.3) +
    geom_text(aes(x = conf_high_pp, label = fmt_pp(estimate_pp)),
              hjust = -0.28, size = TXT, colour = INK_SOFT) +
    facet_wrap(~ j, ncol = 2, scales = "free_x") +
    scale_x_continuous(expand = expansion(mult = c(0.10, 0.26))) +
    labs(x = "Difference from the canonical judge (pp)", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(size = PT_MIN),
          strip.text = element_text(size = PT_BODY)) + tag_only()
  if (nrow(ne))
    cat(sprintf("  not estimable, omitted: %s\n",
                paste(ne$jurisdiction, collapse = ", ")))
  save_fig(ed1, file.path(ED_FIG, "ED1_judge_sensitivity.png"),
           width = W2, height = H_WIDE)
  figs$ED1_judge_sensitivity <- ed1
}

# =============================================================================
# ED2 -- inferential robustness, ORGANISED BY JURISDICTION
# =============================================================================
# Reorganised around the reader's question. "Is the CN conclusion robust?" used
# to require visiting six specification-family facets and picking the CN-red
# rows out of each; jurisdiction was the within-facet nuisance dimension. Now
# each jurisdiction is a facet and the sensitivity families are grouped rows
# inside it, so stability is visible without reading a number.
#
# Post-outcome diagnostics are NOT here -- they are ED3. A shared figure number
# is itself a claim of kinship, and a response-length filter conditions on a
# realized property of the outcome.
c07 <- rd("c07_home_sensitivities.csv"); c04 <- rd("c04_home_standardized.csv")
if (!is.null(c07)) {
  cat("ED2 inferential robustness\n")
  FAM <- tribble(
    ~sensitivity,            ~family,                 ~kind,
    "leave_one_model_out",   "Model composition",     "inferential",
    "prompt_type",           "Prompt tier",           "inferential",
    "language",              "Language",              "inferential",
    "outcome_code3",         "Outcome definition",    "inferential",
    "functional_form",       "Functional form",       "inferential",
    "overlap_restricted",    "Support restriction",   "inferential",
    "min_response_chars",    "Response-length filter", "post-outcome")
  FORD <- FAM$family[FAM$kind == "inferential"]

  # A row is PLOTTABLE only if it has a point AND an interval. `estimable` in
  # c07 records that a fit was attempted, not that an estimate exists: five
  # functional-form rows carry estimable = TRUE with estimate_pp = NA, and the
  # previous figure filtered on that flag and reserved a whole empty facet for
  # them. Unplottable rows are counted and named in a terse marker instead.
  sc <- c07 %>% left_join(FAM, by = "sensitivity") %>%
    filter(kind == "inferential")
  drawable <- sc %>% filter(estimable, is.finite(estimate_pp),
                            is.finite(conf_low_pp), is.finite(conf_high_pp))
  dropped <- sc %>% anti_join(drawable, by = c("sensitivity", "jurisdiction",
                                               "level"))

  prim <- c04 %>% filter(weighting == "nested", support == "full target",
                         estimator == "maximum likelihood", estimable) %>%
    transmute(jurisdiction, primary_pp = estimate_pp)

  # Rows are stacked family by family, in a fixed family order, with the row
  # order inside a family fixed by the table rather than by the estimates -- so
  # the layout never implies a finding.
  #
  # The family name is a HEADER ROW in the y axis, not a text grob floating in
  # the panel: drawn in the panel it printed on top of whichever data row
  # happened to sit at the same height. Data rows are indented under their
  # header. Every facet needs its own y positions, and different facets carry
  # different families, so the row set is built per jurisdiction and the panels
  # use free y.
  base <- drawable %>%
    mutate(family = factor(family, levels = FORD),
           j = factor(jurisdiction, levels = JORD),
           level_lab = paste0("   ", str_replace(level, "^drop_", "- ")))
  rows <- base %>% arrange(j, family, level_lab) %>%
    group_by(j, family) %>% mutate(k = row_number()) %>% ungroup()
  # Interleave one header per family with its data rows.
  # y runs NEGATIVE downward on a plain continuous scale. scale_y_reverse()
  # clipped the topmost break in every panel -- so each facet lost its first
  # family heading -- and the loss was invisible unless you counted the rows
  # against the table.
  lay <- rows %>% distinct(j, family) %>% arrange(j, family) %>%
    mutate(level_lab = as.character(family), header = TRUE, k = 0L) %>%
    bind_rows(rows %>% mutate(header = FALSE)) %>%
    arrange(j, family, k) %>%
    group_by(j) %>% mutate(y = -row_number()) %>% ungroup()
  rows <- lay %>% filter(!header)
  # Terse marker for what a family could not deliver, carried as one more row
  # label rather than a floating annotation, so the absence is visible and
  # cannot drift off the panel.
  miss <- dropped %>% group_by(jurisdiction, family) %>%
    summarise(k = n(), .groups = "drop") %>%
    mutate(j = factor(jurisdiction, levels = JORD),
           level_lab = sprintf("%s: %d not estimable", family, k)) %>%
    semi_join(rows, by = "j") %>%
    group_by(j) %>% mutate(y = min(lay$y[lay$j == first(j)]) - row_number()) %>%
    ungroup()
  lay <- bind_rows(lay, miss %>% mutate(header = FALSE))

  # One PLOT per jurisdiction, not one facet. Each carries a different set of
  # families and therefore a different row-label vector, and a facetted y scale
  # is shared across facets -- which is what forced the previous version to
  # draw row labels as in-panel text, where they printed over the data.
  #
  # An empty facet is canvas spent on nothing. EU has no estimable sensitivity
  # of any kind -- it produced zero refusals in both arms -- so it gets no
  # panel at all, and the legend says why.
  mk_panel <- function(jj, show_x) {
    rr <- rows %>% filter(j == jj); if (!nrow(rr)) return(NULL)
    ll <- lay %>% filter(j == jj)
    pr <- prim %>% filter(jurisdiction == jj)
    ggplot(rr, aes(x = estimate_pp, y = y)) +
      geom_vline(xintercept = 0, colour = RULE, linewidth = 0.3) +
      { if (nrow(pr))
          geom_vline(xintercept = pr$primary_pp[1], colour = ACCENT,
                     linewidth = 0.3, linetype = "22") } +
      geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), colour = INK,
                     linewidth = 0.3) +
      geom_point(size = 0.85, colour = INK) +
      facet_wrap(~ j) +
      # LIMITS FROM THE LABEL SET, not from the data. A scale takes its range
      # from the plotted points, and the family headings and the
      # "not estimable" markers are label-only rows with no point -- so every
      # panel silently dropped its first heading and all of its markers.
      scale_y_continuous(breaks = ll$y, labels = ll$level_lab,
                         limits = range(ll$y) + c(-0.9, 0.9),
                         expand = expansion(add = 0)) +
      scale_x_continuous(expand = expansion(mult = c(0.06, 0.06))) +
      # The axis title is identical in all four panels; printing it four times
      # is three redundant strings, so only the bottom row carries it.
      labs(x = if (show_x) "Home - away difference (pp)" else NULL, y = NULL) +
      theme_nature(base_size = PT_BODY, grid = "x") +
      theme(axis.text.y = element_text(size = PT_MIN, colour = INK_SOFT,
                                       hjust = 0),
            axis.ticks.y = element_blank(),
            axis.title.x = element_text(size = PT_MIN),
            strip.text = element_text(size = PT_BODY)) + tag_only()
  }
  have <- JORD[vapply(JORD, function(z) any(rows$j == z), logical(1))]
  panels <- Filter(Negate(is.null),
                   lapply(seq_along(have), function(i)
                     mk_panel(have[i], i > length(have) - 2)))
  ed2 <- patchwork::wrap_plots(panels, ncol = 2) +
    plot_annotation(tag_levels = "a")
  save_fig(ed2, file.path(ED_FIG, "ED2_inferential_robustness.png"),
           width = W2, height = H_TALL)
  figs$ED2_inferential_robustness <- ed2
  cat(sprintf("  %d rows drawn, %d not estimable and omitted\n",
              nrow(rows), nrow(dropped)))

  # ===========================================================================
  # ED3 -- post-outcome data-quality diagnostics, in their OWN figure
  # ===========================================================================
  # Response-length filters condition on a property of the response, i.e. after
  # the outcome. They are a data-quality check, not design robustness, and they
  # do not belong under the same figure number as the inferential forest.
  cat("ED3 post-outcome diagnostics\n")
  po <- c07 %>% left_join(FAM, by = "sensitivity") %>%
    filter(kind == "post-outcome", estimable, is.finite(estimate_pp),
           is.finite(conf_low_pp)) %>%
    mutate(j = factor(jurisdiction, levels = JORD),
           thresh = factor(level, levels = sort(unique(as.numeric(level)))))
  if (nrow(po)) {
    ed3 <- ggplot(po, aes(x = estimate_pp, y = fct_rev(thresh))) +
      geom_vline(xintercept = 0, colour = RULE, linewidth = 0.3) +
      geom_vline(data = prim %>%
                   mutate(j = factor(jurisdiction, levels = JORD)) %>%
                   semi_join(po, by = "j"),
                 aes(xintercept = primary_pp), colour = ACCENT,
                 linewidth = 0.3, linetype = "22") +
      geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), colour = INK,
                     linewidth = 0.35) +
      geom_point(size = 1.2, colour = INK) +
      facet_wrap(~ j, nrow = 1, scales = "free_x") +
      labs(x = "Home - away difference (pp)",
           y = "Minimum response length (characters)") +
      theme_nature(base_size = PT_BODY, grid = "x") +
      theme(strip.text = element_text(size = PT_BODY),
            axis.title.y = element_text(size = PT_MIN)) + tag_only()
    save_fig(ed3, file.path(ED_FIG, "ED3_postoutcome_diagnostics.png"),
             width = W2, height = H_SHORT)
    figs$ED3_postoutcome_diagnostics <- ed3
  }
}

# =============================================================================
# ED4 -- language heterogeneity: the matrix AND its intervals, as ONE pair
# =============================================================================
# The two panels are designed as a pair and must be readable against each other,
# so they share model order, language order and spelling exactly. Panel a is the
# cross-language overview; panel b is the within-language uncertainty companion.
#
# Panel b keeps free x-scales DELIBERATELY: its task is within-language model
# comparison and interval width, and the cross-language magnitude comparison is
# panel a's job. One panel is not asked to do both tasks poorly.
c08 <- rd("c08_language_paired.csv"); c09 <- rd("c09_language_by_model.csv")
if (!is.null(c09)) {
  cat("ED4 language heterogeneity\n")
  LORD <- c08 %>% filter(sensitivity == "primary", weighting == "equal_model") %>%
    arrange(estimate_pp) %>% pull(language_label)
  bym <- c09 %>% filter(grouping == "model") %>%
    transmute(model = group, jurisdiction,
              language = factor(language_label, levels = LORD),
              estimate_pp, conf_low_pp, conf_high_pp)
  # ONE model order for both panels, fixed by jurisdiction group and then name,
  # never by the effects being displayed.
  mord <- bym %>% distinct(model, jurisdiction) %>%
    mutate(j = factor(jurisdiction, levels = JORD)) %>%
    arrange(desc(j), desc(model)) %>% pull(model)
  bym <- bym %>% mutate(model_f = factor(model, levels = mord))

  # A model that never refused in any language has an undefined paired
  # difference, not a zero one. It is excluded from the colour scale and drawn
  # as the hollow square used everywhere else for a structural zero.
  const <- bym %>% group_by(model) %>%
    summarise(z = all(estimate_pp == 0), .groups = "drop") %>%
    filter(z) %>% pull(model)
  hm_e <- bym %>% filter(!model %in% const)
  hm_z <- bym %>% filter(model %in% const)
  # Colour scale is set by a robust quantile, not by the maximum. Scaling to
  # max|estimate| = 61 pp pushed the 30 cells below 6 pp into the middle 10% of
  # the ramp, where they were indistinguishable. Cells beyond the limit are
  # squished to the endpoint colour and still carry their printed value, so no
  # information is lost -- only saturation is.
  LIM <- max(6, as.numeric(quantile(abs(hm_e$estimate_pp), 0.85)))
  hm_e <- hm_e %>%
    mutate(cell = fmt_pp0(estimate_pp),
           dark = abs(estimate_pp) > 0.72 * LIM)

  p4a <- ggplot(hm_e, aes(x = language, y = model_f, fill = estimate_pp)) +
    geom_tile(colour = "white", linewidth = 0.4) +
    geom_text(aes(label = cell, colour = dark), size = TXT) +
    { if (nrow(hm_z))
        geom_tile(data = hm_z, aes(x = language, y = model_f),
                  inherit.aes = FALSE, fill = CELL_EMPTY, colour = "white",
                  linewidth = 0.4) } +
    { if (nrow(hm_z))
        geom_point(data = hm_z, aes(x = language, y = model_f),
                   inherit.aes = FALSE, shape = SHAPE_NOT_ESTIMABLE, size = 1.2,
                   colour = INK_FAINT, stroke = 0.35) } +
    scale_fill_gradient2(low = PAL_DIVERGE[[1]], mid = "#F4F4F2",
                         high = PAL_DIVERGE[[5]], midpoint = 0,
                         limits = c(-LIM, LIM), oob = scales::squish,
                         guide = "none") +
    scale_colour_manual(values = c(`TRUE` = "white", `FALSE` = INK),
                        guide = "none") +
    # limits = mord EXPLICITLY. A discrete scale drops unused levels, so with
    # the structural-zero model filtered out of the main layer its level was
    # dropped and then re-appended by the second layer -- putting one row at the
    # top of panel a and the bottom of panel b, in a pair whose whole purpose is
    # a shared ordering.
    scale_y_discrete(limits = mord) +
    labs(x = NULL, y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "none") +
    theme(axis.text = element_text(size = PT_MIN),
          axis.line = element_blank(), axis.ticks = element_blank()) +
    tag_only()

  p4b <- ggplot(bym, aes(x = estimate_pp, y = model_f)) +
    geom_vline(xintercept = 0, colour = RULE, linewidth = 0.3) +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), colour = INK,
                   linewidth = 0.3) +
    geom_point(size = 0.9, colour = INK) +
    facet_wrap(~ language, nrow = 1, scales = "free_x") +
    scale_y_discrete(limits = mord) +
    labs(x = "Paired difference vs. English (pp)", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.text.y = element_text(size = PT_MIN),
          strip.text = element_text(size = PT_MIN)) + tag_only()

  ed4 <- (p4a / p4b) + plot_layout(heights = c(1, 1)) +
    plot_annotation(tag_levels = "a")
  save_fig(ed4, file.path(ED_FIG, "ED4_language_heterogeneity.png"),
           width = W2, height = H_STD)
  figs$ED4_language_heterogeneity <- ed4
}

# =============================================================================
# ED5 -- measurement reliability: construct x metric
# =============================================================================
# A single "agreement" axis would imply these statistics are interchangeable.
# They are not, and the run says so plainly: engagement has Krippendorff alpha
# 0.51 and Gwet AC1 0.97 on the same labels, because alpha's chance correction
# collapses when one category dominates. Rare constructs are exactly where the
# metrics diverge most, so the reliability figure shows them side by side rather
# than choosing one.
#
# PSA is defined only for binary constructs (it is agreement on POSITIVE labels),
# so its column is empty for the ordinal scales. That is a property of the
# statistic, marked with a dash rather than left blank.
e23 <- rd("e23_reliability_pass1.csv"); e24 <- rd("e24_reliability_justification.csv")
e25 <- rd("e25_reliability_slant.csv")
if (!is.null(e23) && !is.null(e25)) {
  cat("ED5 measurement reliability\n")
  grab <- function(x, grp) {
    if (is.null(x)) return(NULL)
    tibble(construct = x$construct, group = grp, scale = x$scale,
           raw = x$raw_agreement, alpha = x$krippendorff_alpha,
           ac = x$gwet_ac1,
           ac_stat = if ("gwet_statistic" %in% names(x)) x$gwet_statistic else NA_character_,
           psa = if ("psa_mean" %in% names(x)) x$psa_mean else NA_real_,
           prev = if ("prevalence" %in% names(x)) x$prevalence else NA_real_)
  }
  rel <- bind_rows(grab(e23, "Engagement"), grab(e24, "Justification"),
                   grab(e25 %>% filter(grepl("ordinal", scale)), "Ideology"),
                   grab(e25 %>% filter(!grepl("ordinal", scale)), "Moral foundations")) %>%
    mutate(construct = str_replace_all(construct, "_", " "),
           row = paste(group, construct, sep = "  |  "))
  # Ordered by group, then by alpha within group: the grouping is structural and
  # the ordering inside it is informative.
  rel <- rel %>% arrange(factor(group, levels = c("Engagement", "Justification",
                                                  "Ideology", "Moral foundations")),
                         desc(alpha)) %>%
    mutate(row_f = fct_rev(fct_inorder(row)))
  long <- rel %>%
    transmute(row_f, group,
              `Raw agreement` = raw, `Krippendorff alpha` = alpha,
              `Gwet AC1 / AC2` = ac, `Positive specific agreement` = psa) %>%
    pivot_longer(-c(row_f, group), names_to = "metric", values_to = "value") %>%
    mutate(metric = factor(metric, levels = c("Raw agreement",
                                              "Krippendorff alpha",
                                              "Gwet AC1 / AC2",
                                              "Positive specific agreement")))
  na_marks <- long %>% filter(is.na(value))

  ed5 <- ggplot(long %>% filter(!is.na(value)),
                aes(x = value, y = row_f)) +
    geom_vline(xintercept = c(0, 0.5, 1), colour = RULE, linewidth = 0.25) +
    geom_segment(aes(x = 0, xend = value, yend = row_f), colour = RULE,
                 linewidth = 0.5) +
    geom_point(aes(colour = group), size = 1.5) +
    geom_text(aes(label = sprintf("%.2f", value)), hjust = -0.35, size = TXT,
              colour = INK_SOFT) +
    { if (nrow(na_marks))
        geom_text(data = na_marks, aes(x = 0.02, y = row_f),
                  inherit.aes = FALSE, label = "-- not defined for this scale",
                  hjust = 0, size = TXT, colour = INK_FAINT) } +
    facet_wrap(~ metric, nrow = 1) +
    scale_colour_manual(values = c(Engagement = ACCENT,
                                   Justification = ACCENT_2,
                                   Ideology = INK_SOFT,
                                   `Moral foundations` = INK), guide = "none") +
    scale_x_continuous(limits = c(0, 1.18), breaks = c(0, 0.5, 1),
                       expand = expansion(mult = c(0.02, 0))) +
    labs(x = "Agreement statistic", y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "none") +
    theme(axis.text.y = element_text(size = PT_MIN),
          strip.text = element_text(size = PT_MIN),
          panel.spacing.x = unit(4, "pt")) + tag_only()
  save_fig(ed5, file.path(ED_FIG, "ED5_measurement_reliability.png"),
           width = W2, height = H_TALL)
  figs$ED5_measurement_reliability <- ed5
}

saveRDS(figs, file.path(CAN_EST, "c20_figure_layout_extended.rds"))

cat("\nwrote:\n"); print(list.files(ED_FIG))
cat("\n", strrep("=", 78), "\nEXTENDED DATA DONE\n", strrep("=", 78), "\n", sep = "")
