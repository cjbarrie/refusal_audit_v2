# =============================================================================
# PENDING -- pre-v2.4 mixed figure set; see pipeline/pending/README.md
# Historical technical reference: docs/r_pipeline/pending/20_mixed_pre_v24_figures_main.md
# MAIN FIGURES -- Fig 1, Fig 2, Fig 3
# =============================================================================
#   Fig 1  standardized home association under three outcome definitions
#   Fig 2  paired language contrasts: genuine refusal vs capability failure
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
# FIGURE 1 -- standardized home association, three measurement outcomes
# =============================================================================
# One forest plot replaces the old two-column original-label comparison. The
# three marks show how the same standardized home-minus-away association changes
# when non-engagement is decomposed into genuine refusal and capability failure.
# Intervals are the predeclared max-t family bands across five jurisdictions.
cat("Fig 1 ...\n")
c25 <- rd("c25_home_response_validity_sensitivity.csv")
h1 <- c25 %>%
  filter((estimator == "dsl" & outcome %in% c("genuine_refusal", "capability_failure")) |
           (estimator == "original" & outcome == "original_nonengagement")) %>%
  mutate(jurisdiction = factor(jurisdiction, levels = rev(ORDER_JURIS)),
         measure = recode(outcome,
           original_nonengagement = "Judge-coded non-engagement",
           genuine_refusal = "Genuine refusal",
           capability_failure = "Capability failure"),
         measure = factor(measure, levels = c("Judge-coded non-engagement",
                                              "Genuine refusal",
                                              "Capability failure")))
stopifnot(nrow(h1) == 15L, !anyDuplicated(h1[c("jurisdiction", "measure")]))
# A few capability-failure bands are extremely wide because the reference
# sample contains little information for those jurisdiction-specific moments.
# Preserve one common linear scale but cap display-only whiskers, marking every
# off-scale endpoint with an outward arrow. Exact bounds remain in c25 and the
# external legend; estimates and inferential decisions are never clipped.
HOME_X <- c(-15, 25)
h1 <- h1 %>% mutate(
  low_offscale = simultaneous_low_pp < HOME_X[1],
  high_offscale = simultaneous_high_pp > HOME_X[2],
  display_low = pmax(simultaneous_low_pp, HOME_X[1]),
  display_high = pmin(simultaneous_high_pp, HOME_X[2]),
  low_arrow_x = HOME_X[1], high_arrow_x = HOME_X[2])
pd1 <- position_dodge(width = 0.56)
p1 <- ggplot(h1, aes(x = estimate_pp, y = jurisdiction,
                     colour = measure, shape = measure)) +
  geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.35) +
  geom_errorbar(aes(xmin = display_low, xmax = display_high),
                width = 0, linewidth = 0.62, position = pd1) +
  geom_text(data = h1 %>% filter(low_offscale), aes(x = low_arrow_x, label = "←"),
            position = pd1, size = pt_to_mm(PT_BODY), fontface = "bold",
            show.legend = FALSE) +
  geom_text(data = h1 %>% filter(high_offscale), aes(x = high_arrow_x, label = "→"),
            position = pd1, size = pt_to_mm(PT_BODY), fontface = "bold",
            show.legend = FALSE) +
  geom_point(size = 2.45, stroke = 0.45, position = pd1) +
  scale_colour_manual(values = c("Judge-coded non-engagement" = INK_SOFT,
    "Genuine refusal" = ACCENT, "Capability failure" = ACCENT_2)) +
  scale_shape_manual(values = c("Judge-coded non-engagement" = 15,
    "Genuine refusal" = 16, "Capability failure" = 17)) +
  labs(x = "Standardized home minus away difference (percentage points)",
       y = NULL, colour = NULL, shape = NULL) +
  scale_x_continuous(limits = HOME_X, breaks = c(-10, 0, 10, 20),
                     expand = expansion(mult = c(0.015, 0.015))) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.ticks.y = element_blank(), legend.position = "top",
        legend.justification = "left", legend.text = element_text(size = PT_MIN),
        legend.key.width = unit(8, "pt"), legend.key.height = unit(5, "pt"),
        legend.spacing.x = unit(3, "pt"), legend.margin = margin(0, 0, 2, 0)) +
  guides(colour = guide_legend(nrow = 1, byrow = TRUE),
         shape = guide_legend(nrow = 1, byrow = TRUE))
save_fig(p1, file.path(CAN_FIG, "Fig1_home_jurisdiction.png"),
         width = W2, height = H_WIDE)

# =============================================================================
# FIGURE 2 -- language: genuine refusal vs capability failure
# =============================================================================
# The original c08/c09 outcome combined coherent noncompliance with garbled,
# wrong-language and technically degenerated output. This replacement shows the
# two mechanisms separately on one shared percentage-point scale. Every mark is
# a two-phase, validation-weighted target-language-minus-English estimate on the
# fixed prompt/model roster from c24. The original outcome remains an explicitly
# labelled Extended Data sensitivity.
cat("Fig 2 ...\n")
c24 <- rd("c24_language_response_validity.csv")
stopifnot(!is.null(c24))
lv <- c24 %>%
  filter(estimator == "dsl",
         outcome %in% c("genuine_refusal", "capability_failure")) %>%
  mutate(language = factor(language, levels = rev(ORDER_LANG_CONTRAST_CODE),
                           labels = rev(unname(LANG_LABEL[ORDER_LANG_CONTRAST_CODE]))),
         outcome = recode(outcome,
           genuine_refusal = "Genuine refusal",
           capability_failure = "Capability failure"),
         outcome = factor(outcome, levels = c("Genuine refusal",
                                              "Capability failure")))
stopifnot(nrow(lv) == 8L, !anyDuplicated(lv[c("language", "outcome")]))
pd <- position_dodge(width = 0.48)
fig2 <- ggplot(lv, aes(x = estimate_pp, y = language, colour = outcome,
                       shape = outcome)) +
  geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.35) +
  geom_errorbar(aes(xmin = simultaneous_low_pp, xmax = simultaneous_high_pp),
                width = 0, linewidth = 0.65, position = pd) +
  geom_point(size = 2.5, stroke = 0.45, position = pd) +
  scale_colour_manual(values = c("Genuine refusal" = ACCENT,
                                 "Capability failure" = ACCENT_2)) +
  scale_shape_manual(values = c("Genuine refusal" = 16,
                                "Capability failure" = 17)) +
  labs(x = "Difference from English (percentage points)", y = NULL,
       colour = NULL, shape = NULL) +
  guides(colour = guide_legend(nrow = 1, byrow = TRUE,
                               override.aes = list(linewidth = 1)),
         shape = guide_legend(nrow = 1, byrow = TRUE)) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.ticks.y = element_blank(), legend.position = "top",
        legend.justification = "left", legend.text = element_text(size = PT_MIN),
        legend.key.width = unit(8, "pt"), legend.key.height = unit(5, "pt"),
        legend.spacing.x = unit(3, "pt"), legend.margin = margin(0, 0, 2, 0))
save_fig(fig2, file.path(CAN_FIG, "Fig2_language.png"), width = W2, height = H_WIDE)

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
