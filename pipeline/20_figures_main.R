# =============================================================================
# MAIN FIGURES -- Fig 1, Fig 2, Fig 3
# =============================================================================
#   Fig 1  home jurisdiction: unadjusted and standardized differences, one forest
#   Fig 2  presentation: pooled language contrasts, and framing
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
# FIGURE 2 -- language and framing
# =============================================================================
cat("Fig 2 ...\n")
c08 <- rd("c08_language_paired.csv")
c10 <- rd("c10_framing_paired.csv"); c11 <- rd("c11_framing_by_model_domain.csv")

# --- a: pooled paired language contrasts --------------------------------------
# The model x language matrix is ED4. Showing the per-model spread here as well
# put the same 44 numbers in the main figure and in Extended Data, which is one
# display too many for a quantity whose aggregate is the paper's claim.
prim <- c08 %>% filter(sensitivity == "primary", weighting == "equal_model") %>%
  transmute(language_label, estimate_pp, conf_low_pp, conf_high_pp) %>%
  mutate(l = factor(language_label, levels = rev(ORDER_LANG_CONTRAST)))

p2a <- ggplot(prim, aes(x = estimate_pp, y = l)) +
  geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), colour = INK,
                 linewidth = LWC) +
  geom_point(size = 2.1, shape = 21, fill = INK, colour = "white", stroke = 0.35) +
  geom_text(aes(x = conf_high_pp, label = fmt_pp(estimate_pp)), hjust = -0.32,
            size = TXT, colour = INK_SOFT) +
  scale_y_discrete(limits = rev(ORDER_LANG_CONTRAST)) +
  scale_x_continuous(expand = expansion(mult = c(0.10, 0.26))) +
  labs(x = "Paired difference vs. English (pp)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.text.y = element_text(colour = INK)) + tag_only()

# --- b: framing, pooled primary + per-model heterogeneity ---------------------
fr_all <- c10 %>% filter(scope == "overall") %>%
  transmute(g = "All models", estimate_pp, conf_low_pp, conf_high_pp)
fr_m <- c11 %>% filter(grouping == "model") %>%
  transmute(g = group, estimate_pp, conf_low_pp, conf_high_pp)
# A model with an exactly zero point AND a zero-width interval never refused in
# either arm: structural, not a precisely estimated null.
fr_z <- fr_m %>% filter(estimate_pp == 0, conf_low_pp == 0, conf_high_pp == 0)
fr_m <- fr_m %>% anti_join(fr_z, by = "g")
# FIXED model order from _orders.R, not the observed effects.
mord <- intersect(ORDER_MODEL, c(fr_m$g, fr_z$g))
ford <- c("All models", mord)
ypos <- tibble(g = ford, y = seq_along(ford))
fr <- bind_rows(fr_all, fr_m) %>% left_join(ypos, by = "g") %>%
  mutate(pooled = g == "All models")
fr_z <- fr_z %>% left_join(ypos, by = "g")

p2b <- ggplot(fr, aes(x = estimate_pp, y = y)) +
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
  scale_colour_manual(values = c(`TRUE` = INK, `FALSE` = INK_SOFT), guide = "none") +
  scale_fill_manual(values = c(`TRUE` = INK, `FALSE` = INK_SOFT), guide = "none") +
  scale_size_manual(values = c(`TRUE` = 2.4, `FALSE` = 1.4), guide = "none") +
  scale_shape_manual(values = c(`TRUE` = 23, `FALSE` = 21), guide = "none") +
  scale_linewidth_manual(values = c(`TRUE` = LWC, `FALSE` = 0.35), guide = "none") +
  scale_y_reverse(breaks = ypos$y, labels = ypos$g,
                  expand = expansion(add = c(0.7, 0.7))) +
  scale_x_continuous(expand = expansion(mult = c(0.05, 0.05))) +
  labs(x = "Boundary - regular (pp)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.text.y = element_text(size = PT_MIN),
        axis.ticks.y = element_blank()) + tag_only()

fig2 <- (p2a / p2b) + plot_layout(heights = c(0.55, 1.45)) +
  plot_annotation(tag_levels = "a")
save_fig(fig2, file.path(CAN_FIG, "Fig2_language_framing.png"),
         width = W2, height = H_WIDE)

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
            Fig2_language_framing = fig2,
            Fig3_content = fig3),
            "c20_figure_layout_main.rds")

cat("\nwrote:\n"); print(list.files(CAN_FIG))
cat("\n", strrep("=", 78), "\nMAIN FIGURES DONE\n", strrep("=", 78), "\n", sep = "")
