# =============================================================================
# MAIN FIGURES -- Fig 1, Fig 2, Fig 3
# =============================================================================
#   Fig 1  home jurisdiction: unadjusted and standardized differences, one forest
#   Fig 2  language: pooled, jurisdiction and model contrasts (framing is ED10)
#   Fig 3  content of engaged responses: ideology, foundations, agreement
#
# These READ the canonical tables and fit nothing, which is what lets
# audit_figures.R check every plotted value against its source row. They write
# no canonical table either: a table produced only by a plotting script exists
# only when the artwork is rebuilt.
#
# NO TITLES, SUBTITLES OR CAPTIONS INSIDE A PANEL. Panel letters (multi-panel
# figures only), axis labels, tick labels, category names, concise facet
# headings, compact legends and direct numeric labels. Everything else is in
# docs/CANONICAL_FIGURE_LEGENDS.md.
#
# ORDERINGS COME FROM pipeline/_orders.R and are never re-derived from the data.
#
# THREE ENCODINGS ARE CONSTANT ACROSS THE WHOLE SET and carry no legend:
#   * an INTERVAL is thin, dark and centred on its estimate; a paired CONNECTOR
#     is thicker, much paler, and runs only between two paired endpoints;
#   * a STRUCTURAL ZERO -- no refusals at all, so the contrast does not exist --
#     is a hollow square with the words "not estimable", never a point at zero;
#   * colour never carries two meanings in one figure.

source("pipeline/_theme.R")
suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork)
})

CAN_EST <- Sys.getenv("CANON_EST_DIR", "pipeline/estimates/canonical")
CAN_FIG <- Sys.getenv("CANON_FIG_DIR", "pipeline/figures/main")
dir.create(CAN_FIG, showWarnings = FALSE, recursive = TRUE)
rd <- function(f) { p <- file.path(CAN_EST, f)
  if (file.exists(p)) read_csv(p, show_col_types = FALSE) else
    stop("missing canonical table: ", f) }

PROMOTED_FIG <- "pipeline/figures/main"

# A PREVIEW RENDER MUST NOT TOUCH THE PROMOTED TREE. The layout artefact goes to
# CAN_EST, which defaults to the promoted estimates directory -- so rendering a
# draft to a scratch CANON_FIG_DIR without also redirecting CANON_EST_DIR used to
# overwrite a promoted file. Figures somewhere else plus estimates in the
# promoted tree means this is a preview, and the write is skipped.
save_layout <- function(obj, fname) {
  same <- function(a, b) identical(normalizePath(a, mustWork = FALSE),
                                   normalizePath(b, mustWork = FALSE))
  if (same(CAN_EST, "pipeline/estimates/canonical") &&
      !same(CAN_FIG, PROMOTED_FIG)) {
    cat("  preview render: layout artefact NOT written to the promoted tree\n")
  } else saveRDS(obj, file.path(CAN_EST, fname))
}
theme_set(theme_nature(base_size = PT_BODY))
TXT <- pt_to_mm(PT_MIN)
LWC <- 0.5

cat(strrep("=", 78), "\nMAIN FIGURES\n", strrep("=", 78), "\n", sep = "")

# =============================================================================
# FIGURE 1 -- home jurisdiction: hierarchical forest, two aligned columns
# =============================================================================
# TWO COLUMNS, ONE ROW SPINE. The unadjusted difference and the standardized
# contrast share a hierarchical y axis -- jurisdiction aggregate, then the models
# inside it -- and ONE x scale, so a mark at the same horizontal position means
# the same number in either column.
#
# THE TWO COLUMNS ARE DIFFERENT ESTIMANDS, not two goes at one number. Both are
# equal-model weighted so the only thing that differs between them is the
# adjustment; the standardized column remains a covariate-standardized
# predictive contrast, not a causal effect.
#
# WHY THE MODEL ROWS CARRY NO INTERVALS. The panel's job is to show whether a
# jurisdiction result is consistent across the models inside it, and that is a
# question about the SPREAD of the model points. Drawn with intervals, four
# overlapping pale bars in the US block obscure the spread and compete with the
# aggregate; drawn as points, the spread reads instantly. The model intervals
# are in c02 and c05, and they are exploratory in any case -- not
# multiplicity-adjusted -- so giving them interval-level prominence here would
# overstate them.
#
# COLOUR MEANS JURISDICTION AND NOTHING ELSE. The aggregate takes the full
# jurisdiction colour, the models the same hue at reduced opacity. Rank within a
# group is never encoded.
cat("Fig 1 ...\n")
c02 <- rd("c02_home_descriptive_english.csv")
c04 <- rd("c04_home_standardized.csv")
c05 <- rd("c05_home_by_model.csv")

# EQUAL-MODEL descriptive weighting, chosen deliberately: the standardized
# contrast standardizes to a target in which every model carries equal weight,
# so the descriptive column must weight models the same way. It is also what
# makes the hierarchy honest -- the aggregate is exactly the mean of the model
# points shown beneath it.
u_agg <- c02 %>% filter(grouping == "jurisdiction", quantity == "home_minus_away",
                        weighting == "equal_model") %>%
  transmute(jurisdiction, key = "AGG", est = estimate_pp,
            lo = conf_low_pp, hi = conf_high_pp, estimable)
u_mod <- c02 %>% filter(grouping == "model", quantity == "home_minus_away") %>%
  transmute(jurisdiction, key = stratum_value, est = estimate_pp,
            lo = conf_low_pp, hi = conf_high_pp, estimable)
s_agg <- c04 %>% filter(weighting == "nested", estimator == "maximum likelihood",
                        support == "full target") %>%
  transmute(jurisdiction, key = "AGG", est = estimate_pp,
            lo = conf_low_pp, hi = conf_high_pp, estimable)
s_mod <- c05 %>% filter(model != "EQUAL-MODEL AVERAGE") %>%
  transmute(jurisdiction, key = model, est = estimate_pp,
            lo = conf_low_pp, hi = conf_high_pp, estimable)

# STRUCTURAL ZEROS ARE NOT ESTIMATES. EU recorded no refusals in either arm, so
# the standardized contrast is undefined and the descriptive difference is an
# arithmetic 0 - 0 rather than a measured null. c02 reports it as estimable with
# a value of 0; that is true of the arithmetic and false of the quantity, so the
# jurisdiction is marked not estimable in BOTH columns here.
zero_arm <- c02 %>%
  filter(grouping == "jurisdiction", quantity == "observed_rate",
         weighting == "response", home_status %in% c("home", "away")) %>%
  group_by(jurisdiction) %>%
  summarise(structural = sum(refusals_strict) == 0, .groups = "drop") %>%
  filter(structural) %>% pull(jurisdiction)
blank_zero <- function(d) d %>%
  mutate(estimable = estimable & !(jurisdiction %in% zero_arm))
u_agg <- blank_zero(u_agg); u_mod <- blank_zero(u_mod)
s_agg <- blank_zero(s_agg); s_mod <- blank_zero(s_mod)

# A jurisdiction with ONE model has an aggregate that is arithmetically that
# model's estimate, in both columns. Two marks for one number is not a
# hierarchy, so those arms get a single row.
n_models <- s_mod %>% count(jurisdiction)
single <- n_models$jurisdiction[n_models$n == 1]

spine <- map_dfr(ORDER_JURIS, function(j) {
  ms <- intersect(ORDER_MODEL, s_mod$key[s_mod$jurisdiction == j])
  rows <- tibble(jurisdiction = j, key = "AGG", lab = j, is_agg = TRUE)
  if (!(j %in% single) && length(ms))
    rows <- bind_rows(rows, tibble(jurisdiction = j, key = ms,
                                   lab = paste0("   ", ms), is_agg = FALSE))
  rows
}) %>%
  # Whitespace, not rules or shading, separates the groups.
  mutate(gap = cumsum(is_agg & row_number() > 1), y = -(row_number() + 0.6 * gap))

# One shared x range across both columns.
XL <- bind_rows(u_agg, u_mod, s_agg, s_mod) %>% filter(estimable)
XLIM <- c(min(XL$lo, min(XL$est), na.rm = TRUE) - 1.0,
          max(XL$hi, max(XL$est), na.rm = TRUE) + 3.5)

# EQUAL PANEL WIDTHS, so 1 pp is the same physical distance in both columns.
# The row labels sit in the left panel's y-axis strip and consume width the
# right panel would otherwise give to data. The right panel therefore carries
# the SAME labels drawn in no colour: the strip is measured and reserved
# identically, nothing is drawn, and the two panel regions come out the same
# width. Setting widths = c(1, 1) alone would not do it.
mk_col <- function(dat, xlab, show_y) {
  d   <- spine %>% left_join(dat, by = c("jurisdiction", "key"))
  agg <- d %>% filter(is_agg, estimable %in% TRUE)
  mod <- d %>% filter(!is_agg, estimable %in% TRUE)
  ne  <- d %>% filter(is_agg, !(estimable %in% TRUE))
  ggplot() +
    geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
    geom_point(data = mod, aes(x = est, y = y, colour = jurisdiction),
               size = 1.4, alpha = 0.5, shape = 16) +
    geom_linerange(data = agg, aes(y = y, xmin = lo, xmax = hi,
                                   colour = jurisdiction), linewidth = 0.85) +
    geom_point(data = agg, aes(x = est, y = y, fill = jurisdiction),
               shape = 23, size = 2.5, colour = "white", stroke = 0.4) +
    geom_text(data = agg, aes(x = hi, y = y, label = fmt_pp(est),
                              colour = jurisdiction),
              hjust = -0.30, size = TXT, fontface = "bold") +
    { if (nrow(ne))
        geom_point(data = ne, aes(x = 0, y = y), shape = SHAPE_NOT_ESTIMABLE,
                   size = 1.7, colour = INK_FAINT, stroke = 0.4) } +
    { if (nrow(ne))
        geom_text(data = ne, aes(x = 0, y = y), label = NOT_ESTIMABLE_TEXT,
                  hjust = -0.14, size = TXT, colour = INK_FAINT) } +
    scale_colour_manual(values = PAL_JURIS, guide = "none") +
    scale_fill_manual(values = PAL_JURIS, guide = "none") +
    scale_y_continuous(breaks = spine$y, labels = spine$lab,
                       limits = range(spine$y) + c(-0.9, 0.9)) +
    scale_x_continuous(limits = XLIM, expand = expansion(mult = c(0.01, 0.01))) +
    labs(x = xlab, y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.ticks.y = element_blank(),
          # Jurisdiction rows are ink and bold; model rows are indented, softer
          # and lighter, so the hierarchy reads without boxes or shading. The
          # per-tick vectors are the standard idiom for this and ggplot2 warns
          # that it is not formally supported; the warning is muted at the call
          # site rather than the styling being dropped.
          axis.text.y = element_text(
            hjust = 0, size = PT_MIN,
            colour = if (show_y) ifelse(spine$is_agg, INK, INK_SOFT) else NA,
            face = ifelse(spine$is_agg, "bold", "plain"))) +
    tag_only() + theme(plot.tag = element_blank())
}
quiet_vec_text <- function(expr) withCallingHandlers(expr, warning = function(w) {
  if (grepl("Vectorized input to `element_text", conditionMessage(w)))
    invokeRestart("muffleWarning") })

p1 <- quiet_vec_text(
  (mk_col(bind_rows(u_agg, u_mod), "Unadjusted home - away (pp)", TRUE) |
   mk_col(bind_rows(s_agg, s_mod), "Standardized home - away (pp)", FALSE)) +
    plot_layout(widths = c(1, 1)))
save_fig(p1, file.path(CAN_FIG, "Fig1_home_jurisdiction.png"),
         width = W2, height = H_WIDE)

# =============================================================================
# FIGURE 2 -- language: pooled, jurisdiction and model, on one shared scale
# =============================================================================
# FRAMING IS NOT IN THIS FIGURE. It is a different exposure answered by a
# different block, and pairing it with language forced both into a half-height
# panel. It is now ED10, at full size, with nothing removed from the analysis.
#
# THREE NESTED LEVELS, ALL CANONICAL. The overall pooled contrast (c08 primary,
# equal_model), the five jurisdiction contrasts and the eleven model contrasts
# (both c09). The jurisdiction rows are NOT an aesthetic addition: c09 applies
# the SAME estimator as c08's primary -- wmean_blocks(., "equal_model") over the
# paired blocks -- restricted to one jurisdiction's models, with its own paired
# bootstrap. The nesting is exact and is checked in audit_figures.R: each
# jurisdiction equals the equal-model mean of its models, and the overall equals
# the equal-model mean of all eleven, to 1e-8.
#
# COLOUR MEANS JURISDICTION. The pooled row is ink, not a hue, because "all
# models" is not a jurisdiction.
#
# ONE SHARED LINEAR SCALE, NOT FOUR FREE ONES. Cross-language magnitude is part
# of the result: Hindi is not Chinese with a different axis. The cost is real --
# five of the 44 model cells run past +15 pp and compress the rest -- and two
# alternatives were tested and rejected. Clipping the axis pushed the MENA
# aggregate for Hindi (+35 pp) off the panel, and a canonical aggregate must not
# be an arrowhead. A second magnified band read well but doubled the figure to a
# full page to re-draw the same spine, and the cell-level detail it showed is
# already ED4. What the shared scale still delivers is the finding: the pooled
# effects are small and the MENA spread around them is enormous.
cat("Fig 2 ...\n")
c08 <- rd("c08_language_paired.csv"); c09 <- rd("c09_language_by_model.csv")

lv_all <- c08 %>% filter(sensitivity == "primary", weighting == "equal_model") %>%
  transmute(language, key = "ALL", jurisdiction = NA_character_,
            est = estimate_pp, lo = conf_low_pp, hi = conf_high_pp, lvl = "all")
lv_jur <- c09 %>% filter(grouping == "jurisdiction") %>%
  transmute(language, key = group, jurisdiction = group, est = estimate_pp,
            lo = conf_low_pp, hi = conf_high_pp, lvl = "juris")
lv_mod <- c09 %>% filter(grouping == "model") %>%
  transmute(language, key = group, jurisdiction, est = estimate_pp,
            lo = conf_low_pp, hi = conf_high_pp, lvl = "model")
lv <- bind_rows(lv_all, lv_jur, lv_mod)

# A one-model jurisdiction has an aggregate equal to its model, so it gets one
# row -- the same rule as Fig 1.
lv_single <- lv_mod %>% distinct(jurisdiction, key) %>% count(jurisdiction) %>%
  filter(n == 1) %>% pull(jurisdiction)
lspine <- bind_rows(
  tibble(jurisdiction = NA_character_, key = "ALL", lab = "All models", lvl = "all"),
  map_dfr(ORDER_JURIS, function(j) {
    ms <- intersect(ORDER_MODEL, lv_mod$key[lv_mod$jurisdiction == j])
    r <- tibble(jurisdiction = j, key = j, lab = j, lvl = "juris")
    if (!(j %in% lv_single) && length(ms))
      r <- bind_rows(r, tibble(jurisdiction = j, key = ms,
                               lab = paste0("   ", ms), lvl = "model"))
    r
  })) %>%
  # Whitespace, not rules or shading, separates the groups.
  mutate(gap = cumsum(lvl != "model" & row_number() > 1),
         y = -(row_number() + 0.7 * gap))

LANG_XLIM <- c(-9, 72)

lang_panel <- function(L) {
  d <- lspine %>% left_join(filter(lv, language == L),
                            by = c("jurisdiction", "key", "lvl"))
  A <- filter(d, lvl == "all"); J <- filter(d, lvl == "juris")
  M <- filter(d, lvl == "model")
  span <- diff(LANG_XLIM)
  # A label goes left of its interval when the interval runs near the panel
  # edge, so no direct label is ever clipped.
  place <- function(x) x %>% mutate(
    lx = if_else(hi > LANG_XLIM[2] - 0.22 * span, lo, hi),
    hj = if_else(hi > LANG_XLIM[2] - 0.22 * span, 1.22, -0.28))
  # Only genuinely extreme model cells are labelled; labelling all 11 per panel
  # would bury the aggregate the panel exists to show.
  EXT <- place(filter(M, abs(est) >= 15))
  ggplot() +
    geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
    geom_linerange(data = M, aes(y = y, xmin = lo, xmax = hi,
                                 colour = jurisdiction),
                   linewidth = 0.3, alpha = 0.5) +
    geom_point(data = M, aes(x = est, y = y, colour = jurisdiction),
               size = 0.95, alpha = 0.62, shape = 16) +
    geom_linerange(data = J, aes(y = y, xmin = lo, xmax = hi,
                                 colour = jurisdiction), linewidth = 0.62) +
    geom_point(data = J, aes(x = est, y = y, fill = jurisdiction),
               shape = 23, size = 1.8, colour = "white", stroke = 0.3) +
    geom_linerange(data = A, aes(y = y, xmin = lo, xmax = hi), colour = INK,
                   linewidth = 0.8) +
    geom_point(data = A, aes(x = est, y = y), shape = 23, size = 2.5,
               fill = INK, colour = "white", stroke = 0.35) +
    geom_text(data = place(A), aes(x = lx, y = y, label = fmt_pp(est), hjust = hj),
              size = TXT, fontface = "bold", colour = INK) +
    { if (nrow(EXT))
        geom_text(data = EXT, aes(x = lx, y = y, label = fmt_pp0(est),
                                  colour = jurisdiction, hjust = hj), size = TXT) } +
    scale_colour_manual(values = PAL_JURIS, guide = "none", na.value = INK) +
    scale_fill_manual(values = PAL_JURIS, guide = "none", na.value = INK) +
    scale_y_continuous(breaks = lspine$y, labels = lspine$lab,
                       limits = range(lspine$y) + c(-0.9, 0.9)) +
    scale_x_continuous(limits = LANG_XLIM,
                       expand = expansion(mult = c(0.02, 0.02))) +
    labs(x = NULL, y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "x") +
    theme(axis.ticks.y = element_blank(), axis.text.y = element_blank())
}

# THE ROW LABELS ARE THEIR OWN COLUMN. Reserving the label strip inside all four
# panels is the only way to force equal panel widths when one carries axis text,
# but with four panels that spends a quarter of the figure on three invisible
# strips. As a column the labels are drawn as data, so the jurisdiction/model
# hierarchy is mapped rather than styled per tick, and the four panels are
# identical in width by construction.
lang_labels <- function() {
  ggplot(lspine, aes(x = 0, y = y, label = lab)) +
    geom_text(aes(colour = lvl == "model",
                  fontface = if_else(lvl == "model", "plain", "bold")),
              hjust = 0, size = TXT, show.legend = FALSE) +
    scale_colour_manual(values = c(`TRUE` = INK_SOFT, `FALSE` = INK)) +
    scale_y_continuous(limits = range(lspine$y) + c(-0.9, 0.9)) +
    scale_x_continuous(limits = c(0, 1), expand = expansion(0)) +
    coord_cartesian(clip = "off") +
    labs(x = NULL, y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "none") +
    # The x axis is kept but invisible: its height is what holds these rows in
    # register with the four panels, which do carry one.
    theme(axis.text.y = element_blank(), axis.ticks = element_blank(),
          axis.ticks.x.bottom = element_blank(),
          axis.text.x = element_text(colour = NA),
          axis.line = element_blank(), axis.line.x.bottom = element_blank(),
          panel.grid = element_blank(), plot.margin = margin(1, 0, 1, 1))
}

lang_ps <- imap(LANG_LABEL[ORDER_LANG_CONTRAST_CODE], function(lab, L)
  lang_panel(L) + labs(tag = lab) +
    theme(plot.tag = element_text(size = PT_BODY, face = "bold", hjust = 0),
          plot.tag.position = c(0.02, 0.995)))

fig2 <- wrap_elements(
  wrap_plots(c(list(lang_labels()), lang_ps), nrow = 1,
             widths = c(0.40, 1, 1, 1, 1))) /
  grid::textGrob("Difference from English (percentage points)",
                 gp = grid::gpar(fontsize = PT_AXIS, col = INK)) +
  plot_layout(heights = c(1, 0.04))
fig2 <- quiet_vec_text(fig2)
save_fig(fig2, file.path(CAN_FIG, "Fig2_language.png"), width = W2, height = H_STD)

# =============================================================================
# FIGURE 3 -- content of engaged responses
# =============================================================================
cat("Fig 3 ...\n")
c12 <- rd("c12_ideology_distribution.csv")
c14 <- rd("c14_moral_prevalence_equal_model.csv")

# --- a: the FULL five-bin distribution ----------------------------------------
# The estimand is a distribution over five categories summing to one. Plotting
# only the four directional bins gave all the ink to between 8% and 20% of it.
# Neutral is drawn, and dominates the row exactly as it dominates the data.
BINL <- c(share_neg2 = "-2", share_neg1 = "-1", share_zero = "0",
          share_pos1 = "+1", share_pos2 = "+2")
ideo <- c12 %>% filter(role == "PRIMARY") %>%
  mutate(d = factor(dimension, levels = rev(ORDER_IDEO_DIM)),
         bin = factor(unname(BINL[quantity]), levels = ORDER_IDEO_BIN),
         share = estimate * 100,
         lab = ifelse(estimate * 100 >= 8, sprintf("%.0f", estimate * 100), ""))
ends <- tibble(dimension = names(IDEO_ENDPOINTS),
               endpoint_neg = vapply(IDEO_ENDPOINTS, `[`, character(1), 1),
               endpoint_pos = vapply(IDEO_ENDPOINTS, `[`, character(1), 2)) %>%
  mutate(d = factor(dimension, levels = rev(ORDER_IDEO_DIM)))
# geom_col reverses the fill factor when stacking, so both the bars and their
# labels take reverse = TRUE and the drawn order IS the scale order.
stk  <- position_stack(reverse = TRUE)
stkc <- position_stack(vjust = 0.5, reverse = TRUE)

p3a <- ggplot(ideo, aes(x = share, y = d, fill = bin)) +
  geom_col(width = 0.56, colour = "white", linewidth = 0.25, position = stk) +
  geom_text(aes(label = lab, colour = bin %in% c("-2", "+2")),
            position = stkc, size = TXT, show.legend = FALSE) +
  geom_text(data = ends, aes(x = -5, y = d, label = endpoint_neg),
            inherit.aes = FALSE, hjust = 1, size = TXT, colour = INK_SOFT) +
  geom_text(data = ends, aes(x = 105, y = d, label = endpoint_pos),
            inherit.aes = FALSE, hjust = 0, size = TXT, colour = INK_SOFT) +
  scale_fill_manual(values = PAL_IDEO, name = NULL, breaks = ORDER_IDEO_BIN) +
  scale_colour_manual(values = c(`TRUE` = "white", `FALSE` = INK), guide = "none") +
  scale_x_continuous(labels = label_percent(scale = 1, accuracy = 1),
                     breaks = c(0, 50, 100),
                     expand = expansion(mult = c(0.30, 0.24))) +
  coord_cartesian(clip = "off") +
  labs(x = "Share of engaged responses", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "none") +
  theme(legend.position = "top", legend.text = element_text(size = PT_MIN),
        legend.key.size = unit(5, "pt"), legend.margin = margin(0, 0, 0, 0),
        axis.text.y = element_text(colour = INK, face = "bold", size = PT_BODY)) +
  tag_only()

# --- b + c: prevalence and agreement, ONE aligned compound block --------------
# One row-label column, two value columns, one shared row order. The two columns
# keep separate axes and different geometries because they are DIFFERENT
# QUANTITIES: prevalence carries a 95% issue-cluster sampling interval; PSA
# carries a min-max across the six judge pairs, which has no coverage at all.
mf <- c14 %>% filter(scope == "overall") %>%
  mutate(f = factor(foundation, levels = rev(ORDER_FOUNDATION)))

p3b <- ggplot(mf, aes(x = estimate * 100, y = f)) +
  geom_linerange(aes(xmin = conf_low * 100, xmax = conf_high * 100),
                 colour = INK, linewidth = LWC) +
  geom_point(shape = 21, size = 2.0, fill = INK, colour = "white", stroke = 0.35) +
  scale_y_discrete(limits = rev(ORDER_FOUNDATION)) +
  scale_x_continuous(expand = expansion(mult = c(0.05, 0.08)),
                     labels = label_percent(scale = 1, accuracy = 1)) +
  labs(x = "Prevalence among engaged responses", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.text.y = element_text(colour = INK)) + tag_only()

p3c <- ggplot(mf, aes(x = psa_mean, y = f)) +
  geom_errorbar(aes(xmin = psa_min, xmax = psa_max), colour = INK_FAINT,
                linewidth = 0.35, width = 0.28, orientation = "y") +
  geom_point(shape = 21, size = 1.8, fill = INK_SOFT, colour = "white",
             stroke = 0.3) +
  scale_y_discrete(limits = rev(ORDER_FOUNDATION), labels = NULL) +
  scale_x_continuous(limits = c(0, 1), breaks = c(0, 0.5, 1),
                     expand = expansion(mult = c(0.06, 0.06))) +
  labs(x = "Positive specific agreement", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.ticks.y = element_blank()) + tag_only()

fig3 <- (p3a | p3b | p3c) + plot_layout(widths = c(1.30, 1.05, 0.50)) +
  plot_annotation(tag_levels = "a")
save_fig(fig3, file.path(CAN_FIG, "Fig3_content.png"),
         width = W2, height = H_WIDE)

# Assembled objects are saved so audit_figures.R can MEASURE the rendered layout
# rather than grep the source for font sizes. AUDIT ARTEFACTS, not artwork.
save_layout(list(Fig1_home_jurisdiction = p1,
            Fig2_language = fig2,
            Fig3_content = fig3),
            "c20_figure_layout_main.rds")

cat("\nwrote:\n"); print(list.files(CAN_FIG))
cat("\n", strrep("=", 78), "\nMAIN FIGURES DONE\n", strrep("=", 78), "\n", sep = "")
