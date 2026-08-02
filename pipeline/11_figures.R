# =============================================================================
# Script 11: The figure system
# =============================================================================
# Requires: pipeline/data_clean.RData (01_data_loading.R)
# Writes:   pipeline/figures/*.png (600 dpi) + *.pdf (vector)
#
# NO TITLES, SUBTITLES OR PROSE INSIDE ANY PANEL. Every figure carries only what
# is needed to read the values: axes, tick labels, direct series labels, panel
# letters, reference lines. Explanation lives in docs/FIGURE_CAPTIONS.md.
#
# Design rules (fonts, colour, geometry, export) are in pipeline/_theme.R. This
# file contains no hex codes, no font names and no ggsave() calls.
#
# ANALYTICAL SPINE
#   F1  domain-adjusted home-region effect, by jurisdiction   <- primary result
#   F2  the raw jurisdiction x issue-region matrix behind F1
#   F3  whether that effect depends on prompt language        <- mechanism
#   F4  between-model heterogeneity and the tier shift        <- scope
#   F5  stated reason for refusal                             <- character
#   F6  topic-domain gradient                                 <- where it lives
#   FC  combined A/B/C: result, raw pattern, mechanism

suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")
load("pipeline/data_clean.RData")

FIGS <- "pipeline/figures"
set.seed(20260802)

cat(strrep("=", 78), "\nFIGURE SYSTEM\n", strrep("=", 78), "\n", sep = "")

# -----------------------------------------------------------------------------
# Shared preparation
# -----------------------------------------------------------------------------
# `home` is defined only off "General", which is a placeless stratum: an issue
# with no regional focus has no home jurisdiction, so including it would silently
# score every model as "away" on a sixth of the sample.
d <- data_clean %>%
  filter(!is.na(jurisdiction_f), !is.na(region_focus)) %>%
  mutate(
    juris  = factor(as.character(jurisdiction_f), levels = JURIS_LEVELS),
    region = factor(region_focus, levels = REGION_LEVELS),
    home   = as.character(region_focus) == HOME_REGION[as.character(jurisdiction_f)]
  )
d_en <- d %>% filter(prompt_language == "en")

rate_ci <- function(df, ...) {
  df %>% group_by(...) %>%
    summarise(n = n(), k = sum(refused), .groups = "drop") %>%
    mutate(rate = k / n) %>% bind_cols(wilson_ci(.$k, .$n))
}

# =============================================================================
# F1. Domain-adjusted home-region effect
# -----------------------------------------------------------------------------
# ESTIMAND: the average marginal effect of an issue being in the model's home
# region on P(refuse), holding topic domain fixed.
#
# The adjustment is not optional. Issue region and topic domain are strongly
# confounded by construction of the world, not of the battery: 45% of China
# issues are territorial-sovereignty and 45% of Arab issues are
# security-conflict, both high-refusal domains. An unadjusted home-vs-away
# contrast therefore mixes "this model is sensitive about its own region" with
# "this model is sensitive about sovereignty". g-computation over the observed
# domain distribution separates them.
#
# UNCERTAINTY: nonparametric bootstrap resampling ISSUES, not responses. The
# eleven models all answer the same issues, so responses are clustered within
# issue; a response-level interval would be far too narrow.
# =============================================================================
cat("\nF1  domain-adjusted home-region effect\n")

ame_home <- function(df, B = 400) {
  # Degenerate case: a model that never refuses (Mistral) carries no contrast to
  # estimate. Report the point estimate as zero and the interval as undefined
  # rather than letting glm return a separated fit with meaningless SEs.
  if (length(unique(df$refused)) < 2)
    return(tibble(ame = 0, lo = NA_real_, hi = NA_real_, degenerate = TRUE))

  g_comp <- function(dat) {
    fit <- suppressWarnings(
      glm(refused ~ home + prompt_category, data = dat, family = binomial))
    p1 <- predict(fit, transform(dat, home = TRUE),  type = "response")
    p0 <- predict(fit, transform(dat, home = FALSE), type = "response")
    mean(p1 - p0)
  }
  est <- g_comp(df)
  issues <- unique(df$issue_id)
  boots <- replicate(B, {
    take <- sample(issues, length(issues), replace = TRUE)
    bd <- df[unlist(lapply(take, function(i) which(df$issue_id == i))), ]
    tryCatch(g_comp(bd), error = function(e) NA_real_)
  })
  tibble(ame = est,
         lo = unname(quantile(boots, 0.025, na.rm = TRUE)),
         hi = unname(quantile(boots, 0.975, na.rm = TRUE)),
         degenerate = FALSE)
}

f1 <- d_en %>% filter(region != "General") %>%
  group_by(juris) %>% group_modify(~ ame_home(.x)) %>% ungroup() %>%
  mutate(juris = fct_reorder(juris, ame))

p_f1 <- ggplot(f1, aes(x = ame, y = juris, colour = juris)) +
  geom_vline(xintercept = 0, colour = INK_SOFT, linewidth = 0.3) +
  geom_errorbar(aes(xmin = lo, xmax = hi), orientation = "y",
                width = 0, linewidth = 0.5, na.rm = TRUE) +
  geom_point(size = 2.4) +
  # Mistral never refuses, so its contrast is identically zero with no interval.
  # Marking it is the honest alternative to a bare point that reads as a precise
  # null.
  geom_text(data = ~ filter(.x, degenerate), aes(label = "no refusals"),
            hjust = -0.35, size = 2.1, family = FONT_SANS, colour = INK_FAINT) +
  scale_colour_juris() +
  scale_x_continuous(labels = label_percent(accuracy = 1),
                     breaks = seq(-0.05, 0.20, 0.05),
                     expand = expansion(mult = c(0.05, 0.12))) +
  labs(x = "Home-region effect on refusal (percentage points)", y = NULL) +
  theme_nature(grid = "x")

save_fig(p_f1, file.path(FIGS, "F1_home_region_effect.png"),
         width = W1, height = 1.75)

# =============================================================================
# F2. The raw matrix behind F1
# -----------------------------------------------------------------------------
# Small multiples over jurisdiction, common x scale, regions in a fixed order so
# the reader compares the SAME six positions in every panel. The home cell is
# drawn in the jurisdiction colour and every other cell in ink, so the diagonal
# is visible without a legend.
#
# NOT A MAP. `region_focus` is six coarse strata, one of which -- "General",
# 17% of the sample -- has no location at all, and "Arab" is non-contiguous. A
# choropleth would have to drop or misplace a sixth of the data, and area
# shading reads less accurately than position on a common scale. Region enters
# through ordering and the marked diagonal instead.
# =============================================================================
cat("F2  jurisdiction x issue-region matrix\n")

f2 <- rate_ci(d_en, juris, region) %>%
  mutate(home = as.character(region) == HOME_REGION[as.character(juris)])

# The home cell is marked by SIZE as well as colour. US, India and EU sit low on
# the effect ordering and are therefore deliberately close to ink in PAL_JURIS --
# which means hue alone cannot carry the diagonal in their panels, and would also
# vanish in grayscale. Size is the redundant channel that survives both.
p_f2 <- ggplot(f2, aes(x = rate, y = fct_rev(region))) +
  geom_errorbar(aes(xmin = lo, xmax = hi, colour = ifelse(home, as.character(juris), NA)),
                orientation = "y", width = 0, linewidth = 0.4, na.rm = TRUE) +
  geom_point(aes(colour = ifelse(home, as.character(juris), NA),
                 size = home)) +
  scale_size_manual(values = c(`FALSE` = 1.15, `TRUE` = 2.2), guide = "none") +
  facet_wrap(~ juris, nrow = 1) +
  scale_colour_juris() +
  scale_x_continuous(labels = label_percent(accuracy = 1),
                     breaks = seq(0, 0.25, 0.1),
                     expand = expansion(mult = c(0.04, 0.10))) +
  labs(x = "Refusal rate", y = NULL) +
  theme_nature(grid = "x") +
  theme(strip.text = element_text(family = FONT_MONO, face = "plain",
                                  colour = INK, size = rel(0.95), hjust = 0))

save_fig(p_f2, file.path(FIGS, "F2_jurisdiction_region_matrix.png"),
         width = W2, height = 2.05)

# =============================================================================
# F3. Does the home-region effect depend on prompt language?
# -----------------------------------------------------------------------------
# The two CN models are the only ones with both a large home effect and complete
# Chinese coverage, so they are the case where the two channels can be separated.
# Four cells per model: {home, away} x {English, Chinese}. Showing the cells
# rather than an interaction coefficient lets the reader see that the home gap is
# PARALLEL across languages -- the two effects add, they do not multiply.
# =============================================================================
cat("F3  home effect by prompt language, CN models\n")

f3 <- d %>%
  filter(juris == "CN", region != "General",
         prompt_language %in% c("en", "zh")) %>%
  rate_ci(model, language_f, home) %>%
  mutate(side = factor(ifelse(home, "home", "away"), levels = c("away", "home")))

lab3 <- f3 %>% filter(model == first(model), language_f == "Chinese")

p_f3 <- ggplot(f3, aes(x = rate, y = fct_rev(language_f))) +
  geom_line(aes(group = language_f), colour = RULE, linewidth = 0.8,
            lineend = "round") +
  geom_errorbar(aes(xmin = lo, xmax = hi, colour = side), orientation = "y",
                width = 0, linewidth = 0.4) +
  geom_point(aes(colour = side), size = 1.8) +
  geom_text(data = lab3, aes(label = as.character(side), colour = side),
            vjust = -1.3, size = 2.1, family = FONT_SANS) +
  facet_wrap(~ model, nrow = 1) +
  scale_colour_manual(values = c(away = INK_FAINT, home = PAL_JURIS[["CN"]])) +
  scale_x_continuous(labels = label_percent(accuracy = 1),
                     limits = c(0, 0.40), breaks = seq(0, 0.40, 0.10),
                     expand = expansion(mult = c(0.02, 0.05))) +
  scale_y_discrete(expand = expansion(add = c(0.5, 0.9))) +
  labs(x = "Refusal rate", y = NULL) +
  theme_nature(grid = "x") +
  theme(strip.text = element_text(family = FONT_MONO, face = "plain",
                                  colour = INK, size = rel(0.95), hjust = 0))

save_fig(p_f3, file.path(FIGS, "F3_home_effect_by_language.png"),
         width = W15, height = 1.75)

# =============================================================================
# F4. Between-model heterogeneity and the tier shift
# -----------------------------------------------------------------------------
# A dumbbell: the segment IS the estimand (the within-model change from regular
# to boundary framing), and its direction is readable without consulting either
# endpoint. Models ordered by regular-tier rate; jurisdiction carried by colour
# so this figure and F1/F2 share one encoding.
# =============================================================================
cat("F4  refusal by model and tier\n")

f4 <- d_en %>%
  rate_ci(model, juris, dataset_type_f) %>%
  select(model, juris, dataset_type_f, rate) %>%
  pivot_wider(names_from = dataset_type_f, values_from = rate) %>%
  rename(regular = `Regular Prompts`, boundary = `Boundary Prompts`) %>%
  mutate(model = fct_reorder(model, regular))

p_f4 <- ggplot(f4, aes(y = model)) +
  geom_segment(aes(x = regular, xend = boundary, yend = model),
               colour = RULE, linewidth = 0.9, lineend = "round") +
  geom_point(aes(x = regular), colour = INK_FAINT, size = 1.7) +
  geom_point(aes(x = boundary, colour = juris), size = 1.7) +
  scale_colour_juris() +
  scale_x_continuous(labels = label_percent(accuracy = 1),
                     limits = c(0, 0.185), breaks = seq(0, 0.18, 0.06),
                     expand = expansion(mult = c(0.02, 0.06))) +
  labs(x = "Refusal rate", y = NULL) +
  theme_nature(grid = "x", mono_y = TRUE)

save_fig(p_f4, file.path(FIGS, "F4_model_tier.png"),
         width = W15, height = h_rows(nlevels(f4$model), per = 0.15, chrome = 0.75))

# =============================================================================
# F5. Stated reason for refusal
# -----------------------------------------------------------------------------
# Composition, so stacked. Seven judge codes collapse to four groups: seven
# steps of one hue are not separable in a stacked bar. Models ordered by the
# neutrality share, which is the axis of the claim.
# =============================================================================
cat("F5  refusal justification composition\n")

JUST4 <- c(A = "neutrality", C = "harm", B = "epistemic", D = "epistemic",
           E = "epistemic", F = "unstated", G = "unstated")
LEV4  <- c("neutrality", "harm", "epistemic", "unstated")

f5 <- d_en %>%
  filter(refused, !is.na(refusal_justification)) %>%
  mutate(just = factor(unname(JUST4[refusal_justification]), levels = LEV4)) %>%
  filter(!is.na(just)) %>%
  count(model, just, .drop = FALSE) %>%
  group_by(model) %>% mutate(total = sum(n), p = n / total) %>% ungroup() %>%
  filter(total >= 30)

if (nrow(f5) > 0) {
  ord5 <- f5 %>% filter(just == "neutrality") %>% arrange(p) %>% pull(model)
  f5 <- f5 %>% mutate(model = factor(model, levels = ord5))
  pal4 <- c(neutrality = "#22456F", harm = "#6E8CAE",
            epistemic  = "#AFC1D4", unstated = "#E4E8ED")
  # Direct labels on the widest bar replace the legend.
  lab5 <- f5 %>% filter(model == ord5[length(ord5)]) %>%
    arrange(desc(just)) %>% mutate(xpos = cumsum(p) - p / 2) %>% filter(p > 0.06)

  p_f5 <- ggplot(f5, aes(x = p, y = model, fill = just)) +
    geom_col(width = 0.66) +
    geom_text(data = lab5, aes(x = xpos, y = model, label = as.character(just)),
              vjust = -1.4, size = 2.0, family = FONT_SANS, colour = INK_SOFT,
              inherit.aes = FALSE) +
    scale_fill_manual(values = pal4) +
    scale_x_continuous(labels = label_percent(accuracy = 1),
                       breaks = seq(0, 1, 0.25),
                       expand = expansion(mult = c(0, 0.005))) +
    scale_y_discrete(expand = expansion(add = c(0.6, 1.1))) +
    labs(x = "Share of refusals", y = NULL) +
    theme_nature(grid = "none", mono_y = TRUE)

  save_fig(p_f5, file.path(FIGS, "F5_justifications.png"),
           width = W15, height = h_rows(nlevels(droplevels(f5$model)),
                                        per = 0.17, chrome = 0.8))
}

# =============================================================================
# F6. Topic-domain gradient
# -----------------------------------------------------------------------------
# Domains ordered by regular-tier rate, the same order in both panels so the
# reader's eye tracks one vertical position across the tier comparison.
# =============================================================================
cat("F6  refusal by topic domain\n")

f6 <- rate_ci(d_en, prompt_category, dataset_type_f) %>%
  mutate(domain = pretty_domain(prompt_category))
ord6 <- f6 %>% filter(dataset_type_f == "Regular Prompts") %>%
  arrange(rate) %>% pull(domain)
f6$domain <- factor(f6$domain, levels = ord6)

p_f6 <- ggplot(f6, aes(x = rate, y = domain)) +
  geom_errorbar(aes(xmin = lo, xmax = hi), orientation = "y", width = 0,
                colour = INK_FAINT, linewidth = 0.4) +
  geom_point(colour = INK, size = 1.6) +
  facet_wrap(~ dataset_type_f) +
  scale_x_continuous(labels = label_percent(accuracy = 1),
                     limits = c(0, 0.13), breaks = seq(0, 0.12, 0.04),
                     expand = expansion(mult = c(0.03, 0.06))) +
  labs(x = "Refusal rate", y = NULL) +
  theme_nature(grid = "x")

save_fig(p_f6, file.path(FIGS, "F6_topic_domain.png"),
         width = W2, height = h_rows(9, per = 0.16, chrome = 0.75))

# =============================================================================
# FC. Combined figure: result, raw pattern, mechanism
# -----------------------------------------------------------------------------
# A gets the width and the top row because it is the result. B is the evidence
# behind A, C is its relation to language. F4-F6 are deliberately excluded:
# different estimands on different scales, and folding them in would make a
# collage rather than an argument.
# =============================================================================
cat("FC  combined figure\n")

# patchwork's `&` operator does not dispatch against ggplot2 4.0 themes, so the
# tag styling and margins are applied to each panel before assembly rather than
# broadcast afterwards.
tag_style <- theme(
  plot.tag = element_text(family = FONT_SANS, face = "bold", size = 8,
                          colour = INK, hjust = 0),
  plot.tag.position = c(0, 1),
  plot.margin = margin(6, 8, 4, 4)
)

fc <- (p_f1 + tag_style) / (p_f2 + tag_style) / (p_f3 + tag_style) +
  plot_layout(heights = c(1, 1.3, 1)) +
  plot_annotation(tag_levels = "A")

save_fig(fc, file.path(FIGS, "FC_combined.png"), width = W2, height = 6.0)

cat("\n", strrep("=", 78), "\nFIGURES COMPLETE\n", strrep("=", 78), "\n", sep = "")
