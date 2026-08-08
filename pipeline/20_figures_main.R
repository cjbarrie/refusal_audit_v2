# =============================================================================
# MAIN FIGURES -- Fig 1, Fig 2, Fig 3
# =============================================================================
# Three figures, one estimand family each. They READ the canonical tables and
# fit nothing, which is what lets audit_figures.R check every plotted value
# against its source row.
#
#   Fig 1  home jurisdiction: observed rates, the unadjusted difference, and the
#          covariate-standardized contrast, ROW-ALIGNED by jurisdiction.
#   Fig 2  presentation: language effects (pooled and across models) and prompt
#          framing.
#   Fig 3  content of engaged responses: the full five-bin ideology
#          distribution, foundation prevalence, and agreement.
#
# NO TITLES, NO SUBTITLES, NO PROSE INSIDE A PANEL. Panel letters, axes, ticks,
# category names, facet headings and direct numeric labels only. Everything a
# reader needs beyond that is in docs/CANONICAL_FIGURE_LEGENDS.md.
#
# Two encodings are constant across the whole set and carry no legend:
#   * an INTERVAL is thin, dark and centred on its estimate; a paired CONNECTOR
#     is thicker, much paler, and runs only between two paired endpoints;
#   * a STRUCTURAL ZERO -- no refusals at all, so no contrast exists -- is a
#     hollow square and the words "not estimable", never a point at zero.

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
JORD <- c("CN", "MENA", "India", "US", "EU")
TXT  <- pt_to_mm(PT_MIN)
LWC  <- 0.5      # interval
LWD  <- 1.3      # dumbbell connector: thicker AND paler, so the two never blur

cat(strrep("=", 78), "\nMAIN FIGURES\n", strrep("=", 78), "\n", sep = "")

# =============================================================================
# FIGURE 1 -- home-jurisdiction asymmetry
# =============================================================================
# ROW-ALIGNED: every jurisdiction occupies the same horizontal band in all three
# panels, so the reader can follow one region from the observed rates through
# the unadjusted gap to the standardized contrast without re-finding its label.
#
# The alignment is GRAPHICAL ONLY. Panels a and b are descriptive and
# RESPONSE-weighted; panel c is model-based and NESTED-weighted. They are three
# different quantities, kept apart by three things a reader can see: separate
# panel letters, different axis titles, and hollow (descriptive) versus filled
# (standardized) markers.
#
# The locator map that used to be panel a is gone. It carried no estimate and
# took roughly a third of the figure; its region coding is a data-coding fact,
# documented in the legend and the technical reference, not a result.
cat("Fig 1 ...\n")
c02 <- rd("c02_home_descriptive_english.csv")
c04 <- rd("c04_home_standardized.csv")

jf <- function(x) factor(x, levels = rev(JORD))

# --- a: observed rates, BOTH endpoints labelled -------------------------------
# Labelling only the home endpoint made the absolute refusal rate the salient
# number in a panel whose subject is the gap between two rates.
obs <- c02 %>%
  filter(grouping == "jurisdiction", quantity == "observed_rate",
         weighting == "response", home_status %in% c("home", "away")) %>%
  transmute(jurisdiction, j = jf(jurisdiction), home_status,
            rate = rate_strict * 100, refusals_strict)
seg <- obs %>% select(jurisdiction, j, home_status, rate) %>%
  pivot_wider(names_from = home_status, values_from = rate)
# EU recorded zero refusals in BOTH arms: the two endpoints coincide at zero and
# there is no gap to draw. Panel c calls that not estimable; panel a must not
# quietly show it as a measured rate of zero.
zero_arm <- obs %>% group_by(jurisdiction, j) %>%
  summarise(z = sum(refusals_strict) == 0, .groups = "drop") %>% filter(z)
seg_d <- seg %>% anti_join(zero_arm, by = "jurisdiction")
obs_d <- obs %>% anti_join(zero_arm, by = "jurisdiction")

# Each endpoint's label goes on the OUTER side of the pair. Fixing "away left,
# home right" put both US labels on top of each other, because US is the one
# jurisdiction that refuses LESS at home than away -- which is exactly the case
# the panel needs to show clearly.
lab_a <- obs_d %>% left_join(seg_d %>% select(jurisdiction, away, home),
                             by = "jurisdiction") %>%
  mutate(outer = ifelse((home_status == "home") == (home >= away), 1L, -1L),
         hj = ifelse(outer > 0, -0.45, 1.45))
# Name the two marks once, on the top row only. A legend for two shapes is a
# lookup table the reader has to carry down the panel.
key_a <- lab_a %>% filter(jurisdiction == JORD[1]) %>%
  mutate(k = ifelse(home_status == "home", "home", "away"))

p1a <- ggplot(obs_d, aes(x = rate, y = j)) +
  geom_segment(data = seg_d, aes(x = away, xend = home, y = j, yend = j,
                                 colour = jurisdiction),
               inherit.aes = FALSE, linewidth = LWD, alpha = 0.30) +
  geom_point(data = filter(obs_d, home_status == "away"),
             aes(colour = jurisdiction), shape = 1, size = 1.5, stroke = 0.6) +
  geom_point(data = filter(obs_d, home_status == "home"),
             aes(fill = jurisdiction), shape = 21, size = 2, colour = "white",
             stroke = 0.4) +
  geom_text(data = lab_a, aes(label = sprintf("%.1f", rate), hjust = hj,
                              colour = jurisdiction), size = TXT) +
  geom_text(data = key_a, aes(label = k), vjust = -1.5, size = TXT,
            colour = INK_SOFT) +
  { if (nrow(zero_arm))
      geom_point(data = zero_arm, aes(x = 0, y = j), inherit.aes = FALSE,
                 shape = SHAPE_NOT_ESTIMABLE, size = 1.6, colour = INK_FAINT,
                 stroke = 0.4) } +
  { if (nrow(zero_arm))
      geom_text(data = zero_arm, aes(x = 0, y = j), inherit.aes = FALSE,
                label = "no refusals", hjust = -0.30, size = TXT,
                colour = INK_FAINT) } +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_y_discrete(limits = rev(JORD)) +
  scale_x_continuous(expand = expansion(mult = c(0.14, 0.18))) +
  labs(x = "Refusal rate (%)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") + tag_only()

# --- b: the UNADJUSTED difference, with the interval c02 already carries ------
# This row existed in c02 with a 95% issue-cluster bootstrap interval and was
# never plotted. Hollow marker: descriptive, and not to be confused with c.
und <- c02 %>%
  filter(grouping == "jurisdiction", quantity == "home_minus_away",
         weighting == "response") %>%
  transmute(jurisdiction, j = jf(jurisdiction),
            estimate_pp, conf_low_pp, conf_high_pp) %>%
  anti_join(zero_arm, by = "jurisdiction")

p1b <- ggplot(und, aes(x = estimate_pp, y = j, colour = jurisdiction)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), linewidth = LWC) +
  geom_point(shape = SHAPE_ESTIMAND[["descriptive"]], size = 1.7, stroke = 0.7) +
  geom_text(aes(x = conf_high_pp, label = fmt_pp(estimate_pp)),
            hjust = -0.30, size = TXT) +
  { if (nrow(zero_arm))
      geom_text(data = zero_arm, aes(x = 0, y = j), inherit.aes = FALSE,
                label = NOT_ESTIMABLE_TEXT, hjust = -0.10, size = TXT,
                colour = INK_FAINT) } +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_y_discrete(limits = rev(JORD), labels = NULL) +
  scale_x_continuous(expand = expansion(mult = c(0.10, 0.24))) +
  labs(x = "Unadjusted difference (pp)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.ticks.y = element_blank()) + tag_only()

# --- c: the standardized contrast, FULL TARGET only ---------------------------
# The full-target estimate is the headline and gets the most width. Common
# support is NOT a robustness check of it -- it is a different target
# population, and the restriction costs 59% of CN's nested target weight. That
# comparison, with retained weight annotated, is Extended Data.
std <- c04 %>%
  filter(weighting == "nested", estimator == "maximum likelihood",
         support == "full target") %>%
  mutate(j = jf(jurisdiction))
est   <- std %>% filter(estimable)
noest <- std %>% filter(!estimable) %>% distinct(jurisdiction, j)

p1c <- ggplot(est, aes(x = estimate_pp, y = j, colour = jurisdiction)) +
  geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), linewidth = LWC) +
  geom_point(aes(fill = jurisdiction), shape = SHAPE_ESTIMAND[["primary"]],
             size = 2.3, colour = "white", stroke = 0.4) +
  geom_text(aes(x = conf_high_pp, label = fmt_pp(estimate_pp)),
            hjust = -0.25, size = TXT) +
  { if (nrow(noest))
      geom_point(data = noest, aes(x = 0, y = j), inherit.aes = FALSE,
                 shape = SHAPE_NOT_ESTIMABLE, size = 1.6, colour = INK_FAINT,
                 stroke = 0.4) } +
  { if (nrow(noest))
      geom_text(data = noest, aes(x = 0, y = j), inherit.aes = FALSE,
                label = NOT_ESTIMABLE_TEXT, hjust = -0.18, size = TXT,
                colour = INK_FAINT) } +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_y_discrete(limits = rev(JORD), labels = NULL) +
  scale_x_continuous(expand = expansion(mult = c(0.06, 0.16))) +
  labs(x = "Standardized difference (pp)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.ticks.y = element_blank()) + tag_only()

# Width is allocated to inferential importance: the standardized contrast is the
# headline and takes the most.
fig1 <- (p1a | p1b | p1c) +
  plot_layout(widths = c(1.00, 0.85, 1.35)) +
  plot_annotation(tag_levels = "a")
save_fig(fig1, file.path(CAN_FIG, "Fig1_home_jurisdiction.png"),
         width = W2, height = H_WIDE)

# =============================================================================
# FIGURE 2 -- language and prompt framing
# =============================================================================
cat("Fig 2 ...\n")
c08 <- rd("c08_language_paired.csv"); c09 <- rd("c09_language_by_model.csv")
c10 <- rd("c10_framing_paired.csv"); c11 <- rd("c11_framing_by_model_domain.csv")

PRIMARY_W <- "equal_model"   # predeclared; c08$primary_weighting asserts it
# Ordered by pooled magnitude. This is a property of the estimates, so it is
# derived from the table rather than typed in.
prim <- c08 %>% filter(sensitivity == "primary", weighting == PRIMARY_W) %>%
  transmute(language_label, estimate_pp, conf_low_pp, conf_high_pp) %>%
  arrange(estimate_pp)
LORD <- prim$language_label
prim <- prim %>% mutate(l = factor(language_label, levels = LORD))

# --- a: the pooled paired contrast, on an axis suited to its range ------------
p2a <- ggplot(prim, aes(x = estimate_pp, y = l)) +
  geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), colour = INK,
                 linewidth = LWC) +
  geom_point(size = 2.0, shape = 21, fill = ACCENT, colour = "white",
             stroke = 0.35) +
  geom_text(aes(x = conf_high_pp, label = fmt_pp(estimate_pp)), hjust = -0.3,
            size = TXT) +
  scale_y_discrete(limits = LORD) +
  scale_x_continuous(expand = expansion(mult = c(0.10, 0.26))) +
  labs(x = "Pooled difference vs. English (pp)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") + tag_only()

# --- b: the SAME estimand across models, on one shared axis -------------------
# The pooled effects span 1.3-8.5 pp; the per-model effects span -6 to +61. The
# heterogeneity is an order of magnitude larger than the aggregate, which is the
# substantive result, so it gets its own panel and the most area.
#
# ONE SHARED X-AXIS across all four languages. Hindi genuinely disperses more
# than Chinese; normalising each language separately would delete exactly that.
# No log scale: the quantity is a signed percentage-point difference.
bym <- c09 %>% filter(grouping == "model") %>%
  transmute(model = group, jurisdiction,
            language_label, estimate_pp,
            l = factor(language_label, levels = LORD))
# mistral-large-2512 returned zero refusals in EVERY language, so its four zeros
# are not estimates of a null effect -- the paired difference is undefined on a
# constant outcome. Same hollow-square encoding as EU in Fig 1.
const_models <- bym %>% group_by(model) %>%
  summarise(z = all(estimate_pp == 0), .groups = "drop") %>% filter(z) %>%
  pull(model)
bym_e <- bym %>% filter(!model %in% const_models)
bym_z <- bym %>% filter(model %in% const_models)
# Label only the handful of models that carry the panel's message. An earlier
# threshold of 10 pp produced overlapping labels in the crowded Chinese row.
lab_m <- bym_e %>% filter(abs(estimate_pp) >= 20)

# The pooled estimate is NOT repeated here. It is panel a, on the same four
# rows, so the reader reads across the row: aggregate on the left, the spread it
# summarises on the right. Drawing it in both panels made the same number look
# like two findings, and forced a +1.3 pp estimate onto an axis that has to
# reach +61.
# A small DETERMINISTIC vertical offset, not random jitter: most models sit
# within a few pp of zero and overprint on an axis that has to reach +61, so
# without it the reader cannot see that the near-zero cluster is nine models
# rather than three. The offset is a function of the model's rank within its
# row, so it is stable across rebuilds and carries no meaning of its own.
spread <- function(x) {
  r <- rank(x, ties.method = "first")
  0.30 * (r - (length(r) + 1) / 2) / max(1, (length(r) - 1) / 2)
}
bym_e <- bym_e %>% group_by(l) %>% mutate(dy = spread(estimate_pp)) %>% ungroup()
bym_z <- bym_z %>% mutate(dy = 0)

p2b <- ggplot(bym_e, aes(x = estimate_pp, y = as.numeric(l) + dy)) +
  geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
  geom_point(aes(colour = jurisdiction), size = 1.3, alpha = 0.9) +
  { if (nrow(bym_z))
      geom_point(data = bym_z, aes(x = estimate_pp, y = as.numeric(l) + dy),
                 shape = SHAPE_NOT_ESTIMABLE, size = 1.4, colour = INK_FAINT,
                 stroke = 0.4) } +
  geom_text(data = lab_m %>% left_join(bym_e %>% select(model, l, dy),
                                       by = c("model", "l")),
            aes(x = estimate_pp, y = as.numeric(l) + dy, label = model),
            size = TXT, colour = INK_SOFT, vjust = -1.3) +
  scale_colour_manual(values = PAL_JURIS, name = NULL) +
  scale_y_continuous(breaks = seq_along(LORD), labels = NULL,
                     limits = c(0.4, length(LORD) + 0.6)) +
  scale_x_continuous(expand = expansion(mult = c(0.04, 0.06))) +
  labs(x = "Per-model paired difference vs. English (pp)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.ticks.y = element_blank(),
        legend.position = "top", legend.text = element_text(size = PT_MIN),
        legend.key.size = unit(6, "pt"),
        legend.margin = margin(0, 0, 0, 0)) + tag_only()

# --- c: framing, complete 2+2 blocks only -------------------------------------
fr_m <- c11 %>% filter(grouping == "model") %>%
  transmute(g = group, estimate_pp, conf_low_pp, conf_high_pp) %>%
  arrange(estimate_pp)
fr_all <- c10 %>% filter(scope == "overall") %>%
  transmute(g = "All models", estimate_pp, conf_low_pp, conf_high_pp)
# A model with a zero-width interval at exactly zero never refused in either
# arm: structural, not a precisely estimated null.
fr_z <- fr_m %>% filter(estimate_pp == 0, conf_low_pp == 0, conf_high_pp == 0)
fr_m <- fr_m %>% anti_join(fr_z, by = "g")
# Explicit numeric row positions with scale_y_reverse. Row order matters here --
# the pooled estimate on top, then the exploratory rows by effect, then the
# structural zero last -- and a reversed discrete factor is one negation away
# from silently inverting the whole panel.
ford <- c("All models", fr_m$g, fr_z$g)
ypos <- tibble(g = ford, y = seq_along(ford))
fr <- bind_rows(fr_all, fr_m) %>% left_join(ypos, by = "g") %>%
  mutate(pooled = g == "All models")
fr_z <- fr_z %>% left_join(ypos, by = "g")

p2c <- ggplot(fr, aes(x = estimate_pp, y = y)) +
  geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
  # A rule under the pooled row: it is the estimate, the rows below it are
  # exploratory heterogeneity, not eleven separate findings.
  geom_hline(yintercept = 1.5, colour = INK_SOFT, linewidth = 0.3) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp,
                     colour = pooled, linewidth = pooled)) +
  geom_point(aes(fill = pooled, size = pooled, shape = pooled),
             colour = "white", stroke = 0.3) +
  { if (nrow(fr_z))
      geom_point(data = fr_z, aes(x = 0, y = y), inherit.aes = FALSE,
                 shape = SHAPE_NOT_ESTIMABLE, size = 1.4, colour = INK_FAINT,
                 stroke = 0.4) } +
  { if (nrow(fr_z))
      geom_text(data = fr_z, aes(x = 0, y = y), inherit.aes = FALSE,
                label = NOT_ESTIMABLE_TEXT, hjust = -0.16, size = TXT,
                colour = INK_FAINT) } +
  scale_colour_manual(values = c(`TRUE` = ACCENT, `FALSE` = INK_SOFT),
                      guide = "none") +
  scale_fill_manual(values = c(`TRUE` = ACCENT, `FALSE` = INK_SOFT),
                    guide = "none") +
  scale_size_manual(values = c(`TRUE` = 2.2, `FALSE` = 1.3), guide = "none") +
  scale_shape_manual(values = c(`TRUE` = 23, `FALSE` = 21), guide = "none") +
  scale_linewidth_manual(values = c(`TRUE` = LWC, `FALSE` = 0.35),
                         guide = "none") +
  scale_y_reverse(breaks = ypos$y, labels = ypos$g,
                  expand = expansion(add = c(0.7, 0.7))) +
  scale_x_continuous(expand = expansion(mult = c(0.05, 0.05))) +
  labs(x = "Boundary - regular (pp)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.text.y = element_text(size = PT_MIN),
        axis.ticks.y = element_blank()) + tag_only()

fig2 <- (p2a | p2b) / p2c +
  plot_layout(heights = c(0.80, 1.20), widths = c(0.82, 1.18)) +
  plot_annotation(tag_levels = "a")
save_fig(fig2, file.path(CAN_FIG, "Fig2_language_framing.png"),
         width = W2, height = H_STD)

# =============================================================================
# FIGURE 3 -- content of engaged responses
# =============================================================================
cat("Fig 3 ...\n")
c12 <- rd("c12_ideology_distribution.csv")
c14 <- rd("c14_moral_prevalence_equal_model.csv")

DORD <- c("Economic", "Social", "Authority", "Populism")
BINL <- c(share_neg2 = "-2", share_neg1 = "-1", share_zero = "0",
          share_pos1 = "+1", share_pos2 = "+2")

# --- a: the FULL five-bin distribution ----------------------------------------
# The estimand is a distribution over five categories that sums to one. The
# previous panel plotted four of the five and printed the fifth as a grey note,
# so 100% of the ink described between 8% and 20% of the distribution and the
# reader inferred a far more polarised picture than the estimand states.
#
# The neutral segment now dominates the panel exactly as it dominates the data
# (79.5-92.4%). The cost, stated in the legend: a composition cannot carry a
# per-bin interval. Those intervals stay in c12, and this panel is descriptive
# and exploratory -- panel Krippendorff alpha is 0.02-0.39 by dimension.
ideo <- c12 %>% filter(role == "PRIMARY") %>%
  mutate(d = factor(dimension, levels = rev(DORD)),
         bin = factor(unname(BINL[quantity]), levels = names(PAL_IDEO)),
         share = estimate * 100)
# Endpoint names are dimension-specific: "left/right" is meaningful for the
# economic scale and misleading on the other three, so the codebook's own words
# go at the ends of each row.
ends <- c12 %>% distinct(dimension, endpoint_neg, endpoint_pos) %>%
  mutate(d = factor(dimension, levels = rev(DORD)))
# Label a segment only when it is wide enough to hold a legible number inside
# itself. The neutral bin always clears that bar (79.5-92.4%).
ideo <- ideo %>% mutate(lab = ifelse(share >= 8, sprintf("%.0f", share), ""))
# STACK ORDER IS EXPLICIT. geom_col()'s default reverses the fill factor, so a
# bar drawn -2..+2 left to right had the +1 segment where the -1 segment's
# label was computed. Both the bars and their labels take reverse = TRUE, so
# the drawn order is the scale order and the two cannot drift apart.
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
  scale_fill_manual(values = PAL_IDEO, name = NULL,
                    breaks = names(PAL_IDEO)) +
  scale_colour_manual(values = c(`TRUE` = "white", `FALSE` = INK),
                      guide = "none") +
  scale_x_continuous(labels = label_percent(scale = 1, accuracy = 1),
                     breaks = c(0, 50, 100),
                     expand = expansion(mult = c(0.30, 0.24))) +
  coord_cartesian(clip = "off") +
  labs(x = "Share of engaged responses", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "none") +
  theme(legend.position = "top", legend.text = element_text(size = PT_MIN),
        legend.key.size = unit(5, "pt"), legend.margin = margin(0, 0, 0, 0),
        axis.text.y = element_text(colour = INK, face = "bold",
                                   size = PT_BODY)) + tag_only()

# --- b + c: prevalence and agreement as ONE aligned compound panel ------------
# One row-label column, two value columns, one shared row order. The category
# names are written once. The two columns keep SEPARATE axes because they are
# different quantities, and different geometries so the difference survives
# without a legend:
#   prevalence -> point + 95% issue-cluster sampling interval;
#   PSA        -> point + min-max over the six judge pairs, which is instrument
#                 variation and has no coverage at all.
mf <- c14 %>% filter(scope == "overall") %>%
  mutate(f = fct_reorder(foundation, estimate))
ford3 <- levels(mf$f)

p3b <- ggplot(mf, aes(x = estimate * 100, y = f)) +
  geom_linerange(aes(xmin = conf_low * 100, xmax = conf_high * 100),
                 colour = INK, linewidth = LWC) +
  geom_point(shape = 21, size = 2.0, fill = ACCENT, colour = "white",
             stroke = 0.35) +
  scale_y_discrete(limits = ford3) +
  scale_x_continuous(expand = expansion(mult = c(0.05, 0.08))) +
  labs(x = "Prevalence among engaged responses (%)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") + tag_only()

p3c <- ggplot(mf, aes(x = psa_mean, y = f)) +
  # Range, not interval: light, with end ticks, so it cannot be mistaken for the
  # dark centred confidence interval in the column beside it.
  geom_errorbar(aes(xmin = psa_min, xmax = psa_max), colour = INK_FAINT,
                linewidth = 0.35, width = 0.28, orientation = "y") +
  geom_point(shape = 21, size = 1.7, fill = INK_SOFT, colour = "white",
             stroke = 0.3) +
  scale_y_discrete(limits = ford3, labels = NULL) +
  scale_x_continuous(limits = c(0, 1), breaks = c(0, 0.5, 1),
                     expand = expansion(mult = c(0.06, 0.06))) +
  labs(x = "Positive specific agreement", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.ticks.y = element_blank()) + tag_only()

# Prevalence gets more area than the agreement companion: it is the result, the
# agreement column is how far to trust it.
fig3 <- (p3a | p3b | p3c) +
  plot_layout(widths = c(1.30, 1.05, 0.50)) +
  plot_annotation(tag_levels = "a")
save_fig(fig3, file.path(CAN_FIG, "Fig3_content.png"),
         width = W2, height = H_WIDE)

# The assembled objects are saved so audit_figures.R can MEASURE the rendered
# layout (text overflow, panel sizes, tag/title collisions) instead of scanning
# source code for font sizes. They live in the estimates directory, not the
# figure tree, which holds PNGs and nothing else. They are AUDIT ARTEFACTS, not
# publication artwork.
saveRDS(list(Fig1_home_jurisdiction = fig1,
             Fig2_language_framing = fig2,
             Fig3_content = fig3),
        file.path(CAN_EST, "c20_figure_layout_main.rds"))

cat("\nwrote:\n"); print(list.files(CAN_FIG))
cat("\n", strrep("=", 78), "\nMAIN FIGURES DONE\n", strrep("=", 78), "\n", sep = "")
