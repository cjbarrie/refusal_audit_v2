# =============================================================================
# v2 FIGURES -- PLOTTING ONLY, reads the v2 estimate tables, fits nothing
# =============================================================================
# Output: pipeline/figures/FIGA_*, FIGB_*, FIGC_* (PNG, 600 dpi, two-column)
#
# These sit ALONGSIDE the existing FIG1-FIG5 rather than replacing them: the
# canonical set has not been decided, and the older figures remain reproducible
# from the older tables. Nothing here overwrites an existing figure.
#
# One figure per estimand family, named for the family so a reader cannot
# confuse them:
#   FIGA  descriptive home results        (e32)   -- counts and rates, no model
#   FIGB  standardized home contrasts     (e33-e35) -- covariate-standardized
#   FIGC  prompt-fixed language effects   (e36-e37) -- paired within block
#
# LANGUAGE DISCIPLINE. No axis title, legend or annotation in this file may
# describe a Family B quantity as causal, a difference-in-differences, or a
# within-issue effect. audit_figures.R greps this source and fails the build if
# any of those appear unnegated. That is why the FIGB axis reads
# "covariate-standardized" and not "within-issue premium".

suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork)
})
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")

EST <- "pipeline/estimates"; FIGS <- "pipeline/figures"
rd <- function(f) read_csv(file.path(EST, f), show_col_types = FALSE)
has <- function(f) file.exists(file.path(EST, f))
cat(strrep("=", 78), "\nv2 FIGURES (alongside FIG1-5)\n", strrep("=", 78), "\n", sep = "")

if (!has("e32_home_descriptive.csv")) {
  cat("SKIP: v2 estimates absent. Run pipeline/41_v2_home_descriptive.R first.\n")
  quit(save = "no", status = 0)
}

JORDER <- c("CN", "MENA", "India", "US", "EU")
yj <- function(x) factor(x, levels = rev(JORDER))
PT <- 2.5; PT_SM <- 1.85; LW <- 0.9; LW_CI <- 0.55; TXT <- 2.2

theme_v2 <- function(grid = "x") theme_nature(grid = grid) +
  theme(plot.margin = margin(4, 7, 3, 4),
        axis.title.x = element_text(size = rel(0.92), margin = margin(t = 3)),
        axis.text.y  = element_text(colour = INK),
        plot.tag = element_text(family = FONT_SANS, face = "bold", size = 8.5,
                                colour = INK),
        plot.tag.position = c(0, 1))

# Position of an issue relative to the model's own jurisdiction. THREE positions,
# because `general` is not a kind of `away` -- it has no home jurisdiction at all.
POS_LAB <- c(home = "home region", away = "away region", general = "General (no region)")
SHAPE_POS <- c("home region" = 21, "away region" = 1, "General (no region)" = 22)

# =============================================================================
# FIGA -- descriptive
# =============================================================================
cat("FIGA descriptive\n")
e32 <- rd("e32_home_descriptive.csv")

cells <- e32 %>%
  filter(stratum == "overall", quantity == "cell_rate", !is.na(home_status)) %>%
  mutate(position = factor(unname(POS_LAB[home_status]), levels = unname(POS_LAB)),
         j = yj(jurisdiction))

pA1 <- ggplot(cells, aes(x = rate_strict, y = j)) +
  geom_line(aes(group = j), colour = RULE, linewidth = LW) +
  geom_point(aes(shape = position, fill = jurisdiction, colour = jurisdiction),
             size = PT_SM + 0.3, stroke = 0.6) +
  geom_text(data = cells %>% filter(home_status == "home"),
            aes(label = sprintf("%.1f", 100 * rate_strict), colour = jurisdiction),
            hjust = -0.45, size = TXT - 0.35, show.legend = FALSE) +
  scale_shape_manual(values = SHAPE_POS, name = NULL) +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  guides(shape = guide_legend(nrow = 1,
           override.aes = list(fill = INK_SOFT, colour = INK_SOFT, size = PT_SM + 0.4))) +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(0, 0.30), breaks = seq(0, 0.30, 0.10),
                     expand = c(0, 0)) +
  labs(x = "Observed refusal rate (%), all languages", y = NULL) +
  theme_v2() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.width = unit(8, "pt"), legend.key.height = unit(6, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0))

diffs <- e32 %>%
  filter(stratum == "overall", quantity == "home_minus_away") %>%
  mutate(j = yj(jurisdiction),
         wlab = factor(ifelse(weighting == "response", "response-weighted",
                              "equal-model"), levels = c("response-weighted", "equal-model")))
zero_rows <- diffs %>% filter(!estimable | is.na(estimate_pp)) %>% distinct(jurisdiction, j)
# EU has zero refusals anywhere, so its difference is an observed 0 with no
# sampling variation -- drawn as a hollow square with the reason, never as an
# estimate with an interval.
eu_like <- diffs %>% filter(estimable, conf_low_pp == 0, conf_high_pp == 0) %>%
  distinct(jurisdiction, j)

pA2 <- ggplot(diffs %>% filter(!jurisdiction %in% eu_like$jurisdiction),
              aes(y = j, colour = jurisdiction)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  geom_errorbar(aes(xmin = conf_low_pp, xmax = conf_high_pp, group = wlab),
                orientation = "y", width = 0, linewidth = LW_CI,
                position = position_dodge(width = 0.55)) +
  geom_point(aes(x = estimate_pp, shape = wlab, fill = jurisdiction),
             size = PT_SM + 0.1, colour = "white", stroke = 0.4,
             position = position_dodge(width = 0.55)) +
  geom_point(data = eu_like, aes(x = 0, y = j), shape = 22, size = PT_SM,
             colour = INK_FAINT, fill = "white", stroke = 0.45, inherit.aes = FALSE) +
  geom_text(data = eu_like, aes(x = 0, y = j), label = "0 refusals observed",
            hjust = -0.12, size = TXT - 0.45, colour = INK_FAINT, inherit.aes = FALSE) +
  scale_shape_manual(values = c("response-weighted" = 21, "equal-model" = 24), name = NULL) +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  guides(shape = guide_legend(nrow = 1,
           override.aes = list(fill = INK_SOFT, colour = "white", size = PT_SM + 0.4))) +
  # limits pinned: the estimable layer has no EU row, so without this the
  # zero-refusal layer appends EU and it renders at the TOP instead of last.
  scale_y_discrete(limits = rev(JORDER), drop = FALSE) +
  scale_x_continuous(limits = c(-4, 18), breaks = seq(0, 15, 5), expand = c(0, 0)) +
  labs(x = "Descriptive difference in observed rates, home − away (pp)", y = NULL) +
  theme_v2() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.width = unit(8, "pt"), legend.key.height = unit(6, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0))

figA <- (pA1 + labs(tag = "A")) / (pA2 + labs(tag = "B")) +
  plot_layout(heights = c(1, 1))
save_fig(figA, file.path(FIGS, "FIGA_home_descriptive.png"), width = W2, height = 3.9)

# =============================================================================
# FIGB -- standardized
# =============================================================================
cat("FIGB standardized\n")
e33 <- rd("e33_home_standardized_equal_weight.csv")
e34 <- rd("e34_home_standardized_response_weight.csv")
e35 <- rd("e35_home_standardized_sensitivities.csv")

prim <- bind_rows(e33 %>% mutate(target = "equal model × issue (primary)"),
                  e34 %>% mutate(target = "response-weighted")) %>%
  mutate(j = yj(jurisdiction),
         target = factor(target, levels = c("equal model × issue (primary)",
                                            "response-weighted")))
prim_ok <- prim %>% filter(estimable, !is.na(estimate_pp))
prim_no <- prim %>% filter(!estimable) %>% distinct(jurisdiction, j, note)

pB1 <- ggplot(prim_ok, aes(y = j, colour = jurisdiction)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  geom_errorbar(aes(xmin = conf_low_pp, xmax = conf_high_pp, group = target),
                orientation = "y", width = 0, linewidth = LW_CI,
                position = position_dodge(width = 0.5)) +
  geom_point(aes(x = estimate_pp, shape = target, fill = jurisdiction),
             size = PT_SM + 0.15, colour = "white", stroke = 0.4,
             position = position_dodge(width = 0.5)) +
  geom_point(data = prim_no, aes(x = 0, y = j), shape = 22, size = PT_SM,
             colour = INK_FAINT, fill = "white", stroke = 0.45, inherit.aes = FALSE) +
  geom_text(data = prim_no, aes(x = 0, y = j), label = "not estimable (0 refusals)",
            hjust = -0.08, size = TXT - 0.45, colour = INK_FAINT, inherit.aes = FALSE) +
  scale_shape_manual(values = c(21, 24), name = NULL) +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  guides(shape = guide_legend(nrow = 1,
           override.aes = list(fill = INK_SOFT, colour = "white", size = PT_SM + 0.4))) +
  scale_y_discrete(limits = rev(JORDER), drop = FALSE) +
  scale_x_continuous(limits = c(-9, 28), breaks = seq(-5, 25, 5), expand = c(0, 0)) +
  labs(x = "Covariate-standardized contrast, home − away (pp)", y = NULL) +
  theme_v2() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.width = unit(8, "pt"), legend.key.height = unit(6, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0))

SENS_LAB <- c(per_model = "per model", leave_one_model_out = "leave one model out",
              prompt_type = "prompt type", language = "language",
              min_response_chars = "min response length",
              hierarchical_marginal = "hierarchical (marginal)")
lad <- e35 %>%
  filter(!is.na(estimate_pp), jurisdiction %in% c("CN", "MENA", "India", "US")) %>%
  mutate(sens = factor(unname(SENS_LAB[sensitivity]), levels = unname(SENS_LAB)),
         jurisdiction = factor(jurisdiction, levels = JORDER),
         row = paste(sens, level, sep = ": "))
# The hierarchical row has no interval (fitted once, not bootstrapped) and is
# drawn hollow so it cannot be mistaken for an equally-supported estimate.
lad <- lad %>% mutate(has_ci = !is.na(conf_low_pp))

pB2 <- ggplot(lad, aes(x = estimate_pp, y = fct_rev(row), colour = jurisdiction)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
  geom_errorbar(aes(xmin = conf_low_pp, xmax = conf_high_pp), orientation = "y",
                width = 0, linewidth = 0.4, na.rm = TRUE) +
  geom_point(aes(fill = jurisdiction, shape = has_ci), size = PT_SM - 0.15,
             colour = "white", stroke = 0.35) +
  facet_wrap(~ jurisdiction, nrow = 1, scales = "free_x") +
  scale_shape_manual(values = c(`TRUE` = 21, `FALSE` = 24), guide = "none") +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  labs(x = "Covariate-standardized contrast (pp) — sensitivity ladder; ▲ = no bootstrap interval",
       y = NULL) +
  theme_v2(grid = "x") +
  theme(axis.text.y = element_text(size = rel(0.72), colour = INK_SOFT),
        axis.title.x = element_text(size = rel(0.8)),
        # Wider gutter: with free x-scales the right-most tick of one facet and
        # the left-most of the next collided into an unreadable run of digits.
        panel.spacing.x = unit(16, "pt"),
        strip.text = element_text(colour = INK, face = "bold", size = rel(0.9), hjust = 0))

figB <- (pB1 + labs(tag = "A")) / (pB2 + labs(tag = "B")) +
  plot_layout(heights = c(0.62, 1.38))
save_fig(figB, file.path(FIGS, "FIGB_home_standardized.png"), width = W2, height = 5.6)

# =============================================================================
# FIGC -- prompt-fixed language
# =============================================================================
cat("FIGC language paired\n")
e36 <- rd("e36_language_paired_effects.csv")
e37 <- rd("e37_language_paired_by_model.csv")
LORD <- c("Chinese", "Arabic", "Russian", "Hindi")

pC1 <- e36 %>% mutate(l = factor(language_label, levels = rev(LORD))) %>%
  ggplot(aes(y = l)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  geom_errorbar(aes(xmin = conf_low_pp, xmax = conf_high_pp), orientation = "y",
                width = 0, linewidth = LW_CI, colour = INK_SOFT) +
  geom_point(aes(x = estimate_pp), shape = 21, size = PT_SM + 0.2,
             fill = INK_SOFT, colour = "white", stroke = 0.4) +
  geom_text(aes(x = conf_high_pp, label = sprintf("%+.1f", estimate_pp)),
            hjust = -0.35, size = TXT - 0.35, colour = INK_SOFT) +
  geom_text(aes(x = 10.6, label = sprintf("%s / %s", format(n_complete_blocks, big.mark = ","),
                                          n_missing_blocks)),
            hjust = 1, size = TXT - 0.55, colour = INK_FAINT) +
  annotate("text", x = 10.6, y = 4.62, label = "complete / missing blocks",
           hjust = 1, size = TXT - 0.6, colour = INK_FAINT) +
  scale_x_continuous(limits = c(-1, 11), breaks = seq(0, 10, 2), expand = c(0, 0)) +
  scale_y_discrete(expand = expansion(add = c(0.6, 1.05))) +
  labs(x = "Paired within-block difference, language − English (pp)", y = NULL) +
  theme_v2()

bym <- e37 %>% filter(grouping == "model") %>%
  mutate(l = factor(language_label, levels = LORD))
ordm <- bym %>% group_by(group) %>% summarise(m = max(abs(estimate_pp))) %>%
  arrange(m) %>% pull(group)
bym <- bym %>% mutate(group = factor(group, levels = ordm))

pC2 <- ggplot(bym, aes(x = estimate_pp, y = group)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
  geom_errorbar(aes(xmin = conf_low_pp, xmax = conf_high_pp, colour = jurisdiction),
                orientation = "y", width = 0, linewidth = 0.4) +
  geom_point(aes(fill = jurisdiction), shape = 21, size = PT_SM - 0.1,
             colour = "white", stroke = 0.35) +
  scale_colour_manual(values = PAL_JURIS, name = NULL) +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  guides(colour = guide_legend(nrow = 1, override.aes = list(linewidth = 1.4))) +
  facet_wrap(~ l, nrow = 1) +
  scale_x_continuous(breaks = seq(0, 60, 20), expand = expansion(mult = 0.08)) +
  labs(x = "Paired within-block difference, language − English (pp)", y = NULL) +
  theme_v2() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.width = unit(10, "pt"), legend.key.height = unit(5, "pt"),
        legend.text = element_text(size = rel(0.82)),
        legend.margin = margin(0, 0, 1, 0),
        axis.text.y = element_text(size = rel(0.8)),
        panel.spacing.x = unit(12, "pt"),
        strip.text = element_text(colour = INK, face = "bold", size = rel(0.92), hjust = 0))

figC <- (pC1 + labs(tag = "A")) / (pC2 + labs(tag = "B")) +
  plot_layout(heights = c(0.72, 1.28))
save_fig(figC, file.path(FIGS, "FIGC_language_paired.png"), width = W2, height = 4.6)

cat("\n", strrep("=", 78), "\nv2 FIGURES COMPLETE (alongside FIG1-5)\n",
    strrep("=", 78), "\n", sep = "")
