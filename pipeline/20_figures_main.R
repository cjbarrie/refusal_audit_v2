# =============================================================================
# CANONICAL FIGURES -- FIG1 / FIG2 / FIG3   (600 dpi PNG, two-column, white bg)
# =============================================================================
# The three main-manuscript figures, one per estimand family:
#   FIG1  home-jurisdiction asymmetry + what refusals look like  (c04, c17b, u01)
#   FIG2  language and framing                                   (c08-c11)
#   FIG3  content of engaged responses                           (c12, c14)
#
# These read the canonical CSVs only -- they never recompute an estimate, which
# is what lets the acceptance tests check figure/table agreement mechanically.
#
# FIG1 carries the STANDARDIZED contrast only. The descriptive rates are still
# estimated and reported (c02) and are plotted in the appendix; putting both in
# the main figure invited the reading that they are two estimates of one
# parameter, when they are two different estimands.

source("pipeline/_theme.R")
suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork); library(sf)
})

CAN_EST <- "pipeline/estimates/canonical"
# patchwork's plot_annotation(theme=) check rejects ggplot2 4.0 theme objects
# (it warns and drops them), so caption styling is set on the default theme
# instead -- patchwork picks that up for the assembled annotation.
theme_set(theme_nature() +
  theme(plot.caption = element_text(family = FONT_SANS, size = 5.6,
                                    colour = INK_FAINT, hjust = 0,
                                    lineheight = 1.15)))

CAN_FIG <- "pipeline/figures/canonical"
dir.create(CAN_FIG, showWarnings = FALSE, recursive = TRUE)
rd <- function(f) read_csv(file.path(CAN_EST, f), show_col_types = FALSE)
rdp <- function(f) { p <- file.path("pipeline/estimates", f)
  if (file.exists(p)) read_csv(p, show_col_types = FALSE) else NULL }

cat(strrep("=", 78), "\nCANONICAL FIGURES\n", strrep("=", 78), "\n", sep = "")

JORD <- c("CN", "MENA", "India", "US", "EU")          # pinned everywhere
# Marks carried over from the v1 figure system so the canonical figures read as
# the same family: filled point, hairline interval, one colour per jurisdiction.
PT <- 2.5; PT_SM <- 1.85; LW <- 0.9; LW_CI <- 0.55; TXT <- 2.2

tagt <- theme(plot.tag = element_text(family = FONT_SANS, face = "bold",
                                      size = 8.5, colour = INK),
              plot.tag.position = c(0, 1),
              plot.title.position = "panel")
cap <- function(...) str_wrap(paste0(...), width = 150)

# =============================================================================
# FIG1 -- home-jurisdiction asymmetry, and what the refusals look like
# =============================================================================
cat("FIG1 ...\n")

# --- panel a: locator map (issue regions, MENA labelled as such) -------------
ARAB <- c("DZA","BHR","COM","DJI","EGY","IRQ","JOR","KWT","LBN","LBY","MRT",
          "MAR","OMN","PSE","QAT","SAU","SOM","SDN","SYR","TUN","ARE","YEM")
world <- rnaturalearth::ne_countries(scale = "small", returnclass = "sf") %>%
  mutate(reg = case_when(
    iso_a3 == "CHN" ~ "China", iso_a3 == "IND" ~ "India", iso_a3 == "USA" ~ "US",
    iso_a3 %in% ARAB ~ "Arab",
    continent == "Europe" & iso_a3 != "RUS" ~ "Europe", TRUE ~ NA_character_)) %>%
  st_transform("+proj=robin")
lab <- tribble(~reg, ~disp, ~lon, ~lat,
               "US", "US", -100, 41, "Europe", "Europe", 14, 57,
               "Arab", "MENA", 22, 26,
               "India", "India", 94, 9, "China", "China", 104, 40) %>%
  st_as_sf(coords = c("lon", "lat"), crs = 4326) %>% st_transform("+proj=robin")
lab <- bind_cols(st_drop_geometry(lab), as_tibble(st_coordinates(lab)))

p1a <- ggplot() +
  geom_sf(data = filter(world, is.na(reg)), fill = MAP_LAND, colour = "white",
          linewidth = 0.05) +
  geom_sf(data = filter(world, !is.na(reg)), aes(fill = reg), colour = "white",
          linewidth = 0.05) +
  geom_text(data = lab, aes(X, Y, label = disp, colour = reg), size = 2.1,
            family = FONT_SANS, fontface = "bold") +
  scale_fill_manual(values = PAL_REGION, guide = "none") +
  scale_colour_manual(guide = "none",
                      values = c(China = "white", Arab = "white",
                                 India = unname(PAL_REGION[["India"]]),
                                 US = INK, Europe = INK)) +
  coord_sf(xlim = c(-1.30e7, 1.45e7), ylim = c(-0.4e6, 6.75e6), expand = FALSE) +
  theme_void() +
  theme(plot.margin = margin(0, 2, 0, 2),
        plot.background = element_rect(fill = "white", colour = NA)) + tagt

# --- panel b: the standardized contrast, one colour per jurisdiction ---------
c04 <- rd("c04_home_standardized.csv") %>% filter(weighting == "nested")
# The judge envelope, when 54 has produced it: drawn as a lighter outer rule
# BEHIND the bootstrap interval. It is not a confidence interval -- see the
# caption and docs/CANONICAL_ANALYSES.md 5b.
c17b <- if (file.exists(file.path(CAN_EST, "c17b_judge_envelope.csv")))
  rd("c17b_judge_envelope.csv") %>%
    filter(judge_model == "ENVELOPE (union across judges)", estimable) else NULL

est <- c04 %>% filter(estimable) %>%
  transmute(jurisdiction, j = factor(jurisdiction, levels = rev(JORD)),
            estimate_pp, conf_low_pp, conf_high_pp,
            lab = sprintf("%+.1f", estimate_pp))
envd <- if (is.null(c17b)) NULL else
  c17b %>% transmute(jurisdiction, j = factor(jurisdiction, levels = rev(JORD)),
                     lo = conf_low_pp, hi = conf_high_pp) %>%
    semi_join(est, by = "jurisdiction")
noest <- c04 %>% filter(!estimable) %>%
  transmute(j = factor(jurisdiction, levels = rev(JORD)),
            lab = "0 refusals in both arms; not estimable")

p1b <- ggplot(est, aes(y = j)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  { if (!is.null(envd))
      geom_linerange(data = envd, aes(y = j, xmin = lo, xmax = hi),
                     inherit.aes = FALSE, colour = INK_FAINT,
                     linewidth = 1.6, alpha = 0.40) } +
  # The bar from zero is the estimate; the hairline through it is the interval.
  geom_segment(aes(x = 0, xend = estimate_pp, yend = j, colour = jurisdiction),
               linewidth = LW, lineend = "butt", alpha = 0.55) +
  geom_errorbar(aes(xmin = conf_low_pp, xmax = conf_high_pp,
                    colour = jurisdiction),
                orientation = "y", width = 0, linewidth = LW_CI) +
  geom_point(aes(x = estimate_pp, fill = jurisdiction), shape = 21, size = PT,
             colour = "white", stroke = 0.5) +
  geom_text(aes(x = estimate_pp, label = lab, colour = jurisdiction),
            vjust = -1.30, size = TXT) +
  # EU is carried as a flagged row, never as an ordinary zero.
  geom_point(data = noest, aes(x = 0, y = j), inherit.aes = FALSE, shape = 22,
             size = PT_SM, colour = INK_FAINT, fill = "white", stroke = 0.45) +
  geom_text(data = noest, aes(x = 0, y = j, label = lab), inherit.aes = FALSE,
            hjust = -0.08, size = TXT, colour = INK_FAINT) +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_y_discrete(limits = rev(JORD)) +
  scale_x_continuous(expand = expansion(mult = c(0.10, 0.16))) +
  labs(x = "Home − away refusal difference (pp)", y = NULL,
       title = "Standardized contrast") +
  theme_nature(grid = "x") + tagt

# --- panel c: refusal text in semantic space, by stated reason ---------------
u1 <- rdp("u01_refusal_umap.csv")
p1c <- if (is.null(u1)) NULL else {
  u1 <- u1 %>% mutate(reason = factor(reason_group, levels = names(PAL_REASON)))
  # A projection has no units and only local distances are faithful, so the axes
  # are stripped. The .x/.y sub-elements must be blanked INDIVIDUALLY --
  # theme_nature() sets them explicitly, so blanking the parent does nothing.
  # A few points sit far from the mass and would otherwise shrink everything
  # else to a smudge. They are DROPPED, not clipped, so the panel autoscales to
  # what is actually drawn; the count is reported in the caption rather than
  # trimmed silently. coord_equal is kept: an unequal aspect would make the same
  # distance mean different things along x and y.
  qx <- quantile(u1$umap_x, c(0.015, 0.985)); qy <- quantile(u1$umap_y, c(0.015, 0.985))
  keep <- u1$umap_x >= qx[1] & u1$umap_x <= qx[2] &
          u1$umap_y >= qy[1] & u1$umap_y <= qy[2]
  N_DROP <<- sum(!keep)
  ggplot(u1[keep, ] %>% arrange(reason), aes(umap_x, umap_y, colour = reason)) +
    geom_point(size = 0.5, alpha = 0.72, stroke = 0) +
    scale_colour_manual(values = PAL_REASON, name = NULL, drop = FALSE) +
    guides(colour = guide_legend(override.aes = list(size = 1.9, alpha = 1),
                                 nrow = 2)) +
    coord_equal(clip = "on") +
    labs(x = NULL, y = NULL, title = "Refusal text, semantic space") +
    theme_nature(grid = "none") +
    theme(axis.text.x = element_blank(), axis.text.y = element_blank(),
          axis.ticks.x = element_blank(), axis.ticks.y = element_blank(),
          axis.line.x = element_blank(), axis.line.y = element_blank(),
          panel.border = element_rect(fill = NA, colour = RULE, linewidth = 0.3),
          # No y-axis here, so the panel starts at the plot's left edge and the
          # tag letter would print on top of the title. Indent the title itself.
          plot.title = element_text(colour = INK, face = "bold",
                                    size = rel(1.25), hjust = 0,
                                    margin = margin(b = 1.5, l = 16)),
          legend.position = "top") + tagt
}

if (!exists("N_DROP")) N_DROP <- 0L
pur <- if (is.null(u1)) "" else sprintf(
  " Among each refusal's 15 nearest neighbours, %.0f%% share its stated reason, against %.0f%% expected at random; %d of %d points lie outside the plotted range and are not drawn.",
  100 * u1$purity_group_observed[1], 100 * u1$purity_group_baseline[1],
  N_DROP, nrow(u1))

fig1 <- (p1a / (p1b | p1c)) +
  plot_layout(heights = c(0.58, 1)) +
  plot_annotation(
    tag_levels = "a",
    caption = cap(
      "a, Issue regions. b, Covariate-standardized home−away refusal contrast ",
      "(prompt tier, topic domain and seed route held fixed; equal weight per ",
      "model, then per issue, then per prompt). The coloured hairline is the ",
      "95% issue-cluster bootstrap under the canonical judge; the grey rule ",
      "behind it is the union of that interval refit under all four judges -- a ",
      "sensitivity envelope covering instrument choice, and NOT a confidence ",
      "interval. Home is a fixed property of an issue's region, so this is not ",
      "a causal effect. c, Every English refusal embedded in semantic space ",
      "(local sentence-transformer, then UMAP), coloured by the reason the ",
      "judge assigned; axes are unlabelled because the layout has no units and ",
      "only local distances are faithful.", pur))
save_fig(fig1, file.path(CAN_FIG, "FIG1_canonical_home.png"), width = W2, height = 5.4)

# =============================================================================
# FIG2 -- language and framing
# =============================================================================
cat("FIG2 ...\n")
c08 <- rd("c08_language_paired.csv"); c09 <- rd("c09_language_by_model.csv")
c10 <- rd("c10_framing_paired.csv");  c11 <- rd("c11_framing_by_model_domain.csv")

LORD <- c("Chinese", "Arabic", "Hindi", "Russian")

# a: paired language effect, all languages, all three weightings.
prim <- c08 %>% filter(sensitivity == "primary") %>%
  transmute(l = factor(language_label, levels = rev(LORD)),
            weighting = factor(weighting,
              levels = c("pooled", "equal_model", "equal_model_issue")),
            estimate_pp, conf_low_pp, conf_high_pp)

p2a <- ggplot(prim, aes(x = estimate_pp, y = l, shape = weighting)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                 position = position_dodge(width = 0.55),
                 colour = INK, linewidth = LW_CI) +
  geom_point(position = position_dodge(width = 0.55), size = 1.9,
             fill = ACCENT, colour = "white", stroke = 0.35) +
  scale_shape_manual(values = c(pooled = 21, equal_model = 22,
                                equal_model_issue = 24), name = NULL,
                     labels = c("pooled", "equal per model",
                                "equal per model×issue")) +
  scale_y_discrete(limits = rev(LORD)) +
  labs(x = "Paired difference vs. English (pp)", y = NULL,
       title = "Language, all four tested") +
  theme_nature(grid = "x") + theme(legend.position = "top") + tagt

# b: by model x language -- where the pooled null hides opposing model effects.
bym <- c09 %>% filter(grouping == "model") %>%
  mutate(language_label = factor(language_label, levels = LORD))
mord <- bym %>% filter(language_label == "Chinese") %>% arrange(estimate_pp) %>%
  pull(group)
mord <- c(mord, setdiff(unique(bym$group), mord))
bym <- bym %>% mutate(m = factor(group, levels = mord))

p2b <- ggplot(bym, aes(x = estimate_pp, y = m, colour = language_label)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                 position = position_dodge(width = 0.6), linewidth = 0.35) +
  geom_point(position = position_dodge(width = 0.6), size = 1.2) +
  # Shared palette, so a language means the same colour in the main figure and
  # in the appendix. It is lightness-ordered; see PAL_LANGUAGE in _theme.R.
  scale_colour_language(name = NULL, drop = FALSE) +
  scale_y_discrete(limits = mord) +
  labs(x = "Paired difference vs. English (pp)", y = NULL,
       title = "By model, ordered by the Chinese effect") +
  theme_nature(grid = "x") +
  theme(legend.position = "top", axis.text.y = element_text(size = 5.4)) + tagt

# c: framing, boundary minus regular. Ordered by its OWN estimate -- carrying
# panel b's ordering across made these rows look arbitrary, because nothing in
# this panel explains why the models would be in that sequence.
fr_all <- c10 %>% filter(scope == "overall") %>%
  transmute(g = "All models (pooled)", estimate_pp, conf_low_pp, conf_high_pp)
fr_m <- c11 %>% filter(grouping == "model") %>%
  transmute(g = group, estimate_pp, conf_low_pp, conf_high_pp) %>%
  arrange(estimate_pp)
fr <- bind_rows(fr_m, fr_all)
ford <- c(fr_m$g, "All models (pooled)")

p2c <- ggplot(fr, aes(x = estimate_pp, y = g)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                 colour = INK, linewidth = 0.35) +
  geom_point(aes(fill = g == "All models (pooled)"), shape = 21, size = 1.6,
             colour = "white", stroke = 0.3) +
  scale_fill_manual(values = c(`TRUE` = ACCENT, `FALSE` = INK), guide = "none") +
  scale_y_discrete(limits = rev(ford)) +
  labs(x = "Boundary − regular (pp)", y = NULL,
       title = "Prompt framing, ordered by effect") +
  theme_nature(grid = "x") +
  theme(axis.text.y = element_text(size = 5.4)) + tagt

fig2 <- (p2a | p2b) / p2c +
  plot_layout(heights = c(1, 1.15)) +
  plot_annotation(
    tag_levels = "a",
    caption = cap(
      "Paired within-block differences; blocks are model×prompt (a, b) and ",
      "issue×model×language (c), so prompt content is held fixed by ",
      "construction. Intervals are issue-cluster bootstrap percentiles. a ",
      "isolates the tested translation, not the causal effect of user language: ",
      "it assumes translation equivalence and no language-specific provider or ",
      "annotation drift. In c the pooled row is pinned last; every other row is ",
      "ordered by its own estimate."))
save_fig(fig2, file.path(CAN_FIG, "FIG2_canonical_language_framing.png"),
         width = W2, height = 5.6)

# =============================================================================
# FIG3 -- content of engaged responses
# =============================================================================
cat("FIG3 ...\n")
c12 <- rd("c12_ideology_distribution.csv"); c14 <- rd("c14_moral_prevalence_equal_model.csv")

# a: ideology -- the full distribution is the primary estimand, so plot shares.
DORD <- c("Economic", "Social", "Authority", "Populism")
ideo <- c12 %>% filter(quantity %in% c("share_negative", "share_neutral",
                                       "share_positive")) %>%
  mutate(d = factor(dimension, levels = rev(DORD)),
         direction = factor(recode(quantity,
                                   share_negative = "left / liberal pole",
                                   share_neutral  = "neutral (0)",
                                   share_positive = "right / conservative pole"),
                            levels = c("left / liberal pole", "neutral (0)",
                                       "right / conservative pole")),
         share = estimate * 100)

# reverse = TRUE so the segments run left pole -> neutral -> right pole across
# the bar; position_stack's default order would put the conservative pole at the
# left-hand end, which reads as the opposite of what it is.
p3a <- ggplot(ideo, aes(x = share, y = d, fill = direction, group = direction)) +
  geom_col(width = 0.62, colour = "white", linewidth = 0.25,
           position = position_stack(reverse = TRUE)) +
  scale_fill_manual(values = c("left / liberal pole" = PAL_DIVERGE[[1]],
                               "neutral (0)" = "#E6E8EA",
                               "right / conservative pole" = PAL_DIVERGE[[5]]),
                    name = NULL) +
  scale_y_discrete(limits = rev(DORD)) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.02))) +
  labs(x = "Share of engaged responses (%)", y = NULL,
       title = "Ideological placement") +
  theme_nature(grid = "x") +
  theme(legend.position = "top") + tagt

# b: moral foundations -- non-exclusive binaries, hollow when agreement is weak.
mf <- c14 %>% filter(scope == "overall") %>%
  mutate(f = fct_reorder(foundation, estimate),
         flag = ifelse(low_agreement_flag, "weak judge agreement",
                       "acceptable agreement"))
ford3 <- levels(mf$f)

p3b <- ggplot(mf, aes(x = estimate * 100, y = f)) +
  geom_linerange(aes(xmin = conf_low * 100, xmax = conf_high * 100),
                 colour = INK, linewidth = LW_CI) +
  geom_point(aes(fill = flag), shape = 21, size = 2.1, colour = INK,
             stroke = 0.4) +
  scale_fill_manual(values = c(`acceptable agreement` = ACCENT,
                               `weak judge agreement` = "white"), name = NULL) +
  scale_y_discrete(limits = ford3) +
  labs(x = "Prevalence among engaged responses (%)", y = NULL,
       title = "Moral foundations invoked") +
  theme_nature(grid = "x") + theme(legend.position = "top") + tagt

# No in-figure caption here. The conditioning and reliability caveats are long,
# they are stated in full in docs/CANONICAL_ANALYSES.md 4, and setting them
# under two small panels crowded the figure. The panel titles carry what a
# reader needs to read the axes; the manuscript caption carries the rest.
fig3 <- (p3a | p3b) + plot_annotation(tag_levels = "a")
save_fig(fig3, file.path(CAN_FIG, "FIG3_canonical_content.png"),
         width = W2, height = 2.9)

cat("\nwrote:\n"); print(list.files(CAN_FIG))
cat("\n", strrep("=", 78), "\nCANONICAL FIGURES DONE\n", strrep("=", 78), "\n", sep = "")
