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

theme_set(theme_nature(base_size = PT_BODY))
TXT <- pt_to_mm(PT_MIN)
LWC <- 0.5

cat(strrep("=", 78), "\nMAIN FIGURES\n", strrep("=", 78), "\n", sep = "")

# =============================================================================
# FIGURE 1 -- home jurisdiction: ONE forest, two estimands
# =============================================================================
# The three-panel version (rates | unadjusted difference | standardized
# difference) said the same thing three times. The rates are a different
# quantity from the differences and do not belong on a difference axis, so they
# are now a table (c02) and are not plotted at all; the two DIFFERENCES share
# one axis, which is what makes the comparison the figure exists for.
#
# COLOUR IS NOT USED HERE. Jurisdiction is on the y-axis with a direct label, so
# hue would be redundant; and the two accent hues available are close to the CN
# and India jurisdiction colours used elsewhere, which would make the same red
# mean "China" in one figure and "adjusted" in another. Ink, fill and shape
# separate the two series, which also survives greyscale and every form of
# colour-vision deficiency without a caveat.
#
# THE TWO POINTS ARE NOT TWO ESTIMATES OF ONE EFFECT. They differ in adjustment
# AND in weighting target, and the legend says so. Overlaying them shows how the
# descriptive gap moves once measured composition is held fixed; it does not
# make either a causal effect.
cat("Fig 1 ...\n")
c02 <- rd("c02_home_descriptive_english.csv")
c04 <- rd("c04_home_standardized.csv")

# EQUAL-MODEL descriptive weighting, chosen deliberately: the standardized
# contrast standardizes to a target in which every model carries equal weight,
# so the descriptive point it is compared against must weight models the same
# way. The response-weighted version is in c02 and differs by at most 0.001 pp
# here, but the two are conceptually different targets and the figure states
# which one it draws.
DESC_W <- "equal_model"

desc <- c02 %>%
  filter(grouping == "jurisdiction", quantity == "home_minus_away",
         weighting == DESC_W) %>%
  transmute(jurisdiction, estimate_pp, conf_low_pp, conf_high_pp,
            series = "Unadjusted difference")
# EU observed zero refusals in BOTH arms. 0 - 0 = 0 is arithmetically defined
# but it is a structural zero, not a measured null, and drawing it as a point at
# zero with a zero-width interval claims a precision the design cannot deliver.
zero_arm <- c02 %>%
  filter(grouping == "jurisdiction", quantity == "observed_rate",
         weighting == "response", home_status %in% c("home", "away")) %>%
  group_by(jurisdiction) %>%
  summarise(structural = sum(refusals_strict) == 0, .groups = "drop") %>%
  filter(structural)

std <- c04 %>%
  filter(weighting == "nested", estimator == "maximum likelihood",
         support == "full target") %>%
  transmute(jurisdiction, estimate_pp, conf_low_pp, conf_high_pp, estimable,
            series = "Standardized contrast")

SER <- c("Unadjusted difference", "Standardized contrast")
fig1_dat <- bind_rows(desc %>% mutate(estimable = TRUE), std) %>%
  filter(!jurisdiction %in% zero_arm$jurisdiction, estimable) %>%
  mutate(j = factor(jurisdiction, levels = rev(ORDER_JURIS)),
         s = factor(series, levels = SER),
         dodge = ifelse(series == SER[1], 0.19, -0.19))
ne1 <- bind_rows(
  std %>% filter(!estimable) %>% transmute(jurisdiction, why = "not estimable"),
  zero_arm %>% transmute(jurisdiction, why = "no refusals in either arm")) %>%
  distinct(jurisdiction, .keep_all = TRUE) %>%
  mutate(j = factor(jurisdiction, levels = rev(ORDER_JURIS)))

p1 <- ggplot(fig1_dat, aes(x = estimate_pp,
                           y = as.numeric(j) + dodge)) +
  geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp, colour = s),
                 linewidth = LWC) +
  geom_point(aes(shape = s, fill = s, colour = s), size = 2.2, stroke = 0.6) +
  geom_text(aes(x = conf_high_pp, label = fmt_pp(estimate_pp), colour = s),
            hjust = -0.3, size = TXT) +
  { if (nrow(ne1))
      geom_point(data = ne1, aes(x = 0, y = as.numeric(j)), inherit.aes = FALSE,
                 shape = SHAPE_NOT_ESTIMABLE, size = 1.7, colour = INK_FAINT,
                 stroke = 0.4) } +
  { if (nrow(ne1))
      geom_text(data = ne1, aes(x = 0, y = as.numeric(j), label = why),
                inherit.aes = FALSE, hjust = -0.13, size = TXT,
                colour = INK_FAINT) } +
  scale_shape_manual(values = c(21, 23), breaks = SER, name = NULL) +
  scale_fill_manual(values = c("white", INK), breaks = SER, name = NULL) +
  scale_colour_manual(values = c(INK_SOFT, INK), breaks = SER, name = NULL) +
  scale_y_continuous(breaks = seq_along(ORDER_JURIS),
                     labels = rev(ORDER_JURIS),
                     limits = c(0.4, length(ORDER_JURIS) + 0.6)) +
  scale_x_continuous(expand = expansion(mult = c(0.06, 0.20))) +
  labs(x = "Home - away difference (percentage points)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.ticks.y = element_blank(),
        axis.text.y = element_text(colour = INK, size = PT_BODY),
        legend.position = "top", legend.text = element_text(size = PT_MIN),
        legend.key.size = unit(7, "pt"), legend.margin = margin(0, 0, 0, 0)) +
  tag_only() + theme(plot.tag = element_blank())   # single panel: no letter
save_fig(p1, file.path(CAN_FIG, "Fig1_home_jurisdiction.png"),
         width = W2, height = H_SHORT)

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
saveRDS(list(Fig1_home_jurisdiction = p1,
             Fig2_language_framing = fig2,
             Fig3_content = fig3),
        file.path(CAN_EST, "c20_figure_layout_main.rds"))

cat("\nwrote:\n"); print(list.files(CAN_FIG))
cat("\n", strrep("=", 78), "\nMAIN FIGURES DONE\n", strrep("=", 78), "\n", sep = "")
