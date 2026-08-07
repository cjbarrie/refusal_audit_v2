# =============================================================================
# APPENDIX FIGURES -- S1 .. S4   (600 dpi PNG, two-column, white bg)
# =============================================================================
# The main figures (20_figures_main.R) carry one estimate per question. This
# script carries the material a referee will ask for and a reader does not need
# on first pass:
#
#   S1  the DESCRIPTIVE home/away rates, which the main figure no longer shows
#   S2  the standardized contrast refit under every judge (instrument sensitivity)
#   S3  the specification curve: every sensitivity family, one row each
#   S4  refusal-text projection supplement: all five languages, and the same
#       English refusals under a lexical rather than semantic representation
#
# Like the main figures, these READ tables and fit nothing.

source("pipeline/_theme.R")
suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork)
})

CAN_EST <- "pipeline/estimates/canonical"
APP_FIG <- "pipeline/figures/appendix"
dir.create(APP_FIG, showWarnings = FALSE, recursive = TRUE)

theme_set(theme_nature() +
  theme(plot.caption = element_text(family = FONT_SANS, size = 5.6,
                                    colour = INK_FAINT, hjust = 0,
                                    lineheight = 1.15)))
tagt <- theme(plot.tag = element_text(family = FONT_SANS, face = "bold",
                                      size = 8.5, colour = INK),
              plot.tag.position = c(0, 1),
              plot.title.position = "panel")
cap <- function(...) str_wrap(paste0(...), width = 150)
rd <- function(f) { p <- file.path(CAN_EST, f)
  if (file.exists(p)) read_csv(p, show_col_types = FALSE) else NULL }
rdp <- function(f) { p <- file.path("pipeline/estimates", f)
  if (file.exists(p)) read_csv(p, show_col_types = FALSE) else NULL }

JORD <- c("CN", "MENA", "India", "US", "EU")
PT <- 2.5; PT_SM <- 1.85; LW <- 0.9; LW_CI <- 0.55; TXT <- 2.2

cat(strrep("=", 78), "\nAPPENDIX FIGURES\n", strrep("=", 78), "\n", sep = "")

# =============================================================================
# S1 -- descriptive home vs away rates
# =============================================================================
# Dropped from the main figure because printing it beside the standardized
# contrast invited the reading that the two are competing estimates of one
# parameter. They are different estimands, and this one is the raw fact about
# the corpus, confounded with issue composition by construction.
c02 <- rd("c02_home_descriptive_english.csv")
if (!is.null(c02)) {
  cat("S1 descriptive rates\n")
  obs <- c02 %>%
    filter(grouping == "jurisdiction", quantity == "observed_rate",
           weighting == "response", home_status %in% c("home", "away")) %>%
    transmute(jurisdiction, j = factor(jurisdiction, levels = rev(JORD)),
              home_status, rate = rate_strict * 100)
  seg <- obs %>% select(jurisdiction, j, home_status, rate) %>%
    pivot_wider(names_from = home_status, values_from = rate)
  # The label sits above the MIDPOINT of its own barbell. Pinned at x = 0 it
  # floated in the left margin, far from the segment it describes.
  dif <- c02 %>% filter(grouping == "jurisdiction",
                        quantity == "home_minus_away",
                        weighting == "equal_model") %>%
    transmute(jurisdiction, j = factor(jurisdiction, levels = rev(JORD)),
              estimate_pp, lab = sprintf("%+.1f pp", estimate_pp)) %>%
    left_join(seg %>% transmute(jurisdiction, mid = (away + home) / 2),
              by = "jurisdiction")

  s1 <- ggplot(obs, aes(x = rate, y = j)) +
    geom_segment(data = seg, aes(x = away, xend = home, y = j, yend = j,
                                 colour = jurisdiction),
                 inherit.aes = FALSE, linewidth = LW, alpha = 0.55) +
    geom_point(data = filter(obs, home_status == "away"),
               aes(colour = jurisdiction), shape = 1, size = PT_SM, stroke = 0.8) +
    geom_point(data = filter(obs, home_status == "home"),
               aes(fill = jurisdiction), shape = 21, size = PT,
               colour = "white", stroke = 0.5) +
    geom_text(data = dif, aes(x = mid, y = j, label = lab, colour = jurisdiction),
              inherit.aes = FALSE, vjust = -1.3, size = TXT) +
    scale_colour_manual(values = PAL_JURIS, guide = "none") +
    scale_fill_manual(values = PAL_JURIS, guide = "none") +
    scale_y_discrete(limits = rev(JORD)) +
    labs(x = "Observed refusal rate (%), English", y = NULL,
         title = "Descriptive: hollow = away issues, filled = home issues") +
    theme_nature(grid = "x") + tagt

  s1 <- s1 + labs(caption = cap(
    "Observed English refusal rates, no adjustment: this is what the corpus ",
    "looks like, not an effect. Home and away issue sets differ in topic ",
    "domain, prompt tier and seed route, so the gap mixes model behaviour with ",
    "issue composition -- which is exactly what the standardized contrast in ",
    "the main figure holds fixed. Labels are the equal-per-model difference."))
  save_fig(s1, file.path(APP_FIG, "S1_home_descriptive.png"),
           width = W2, height = 2.9)
}

# =============================================================================
# S2 -- the standardized contrast under every judge
# =============================================================================
c17b <- rd("c17b_judge_envelope.csv")
if (!is.null(c17b) && nrow(c17b)) {
  cat("S2 judge multiverse\n")
  ENVL <- "ENVELOPE (union across judges)"
  d <- c17b %>% filter(estimable, judge_model != ENVL) %>%
    mutate(canonical = grepl("canonical", judge_model, fixed = TRUE),
           judge = str_replace(judge_model, " \\(canonical\\)", ""),
           judge = str_remove(judge, "^[a-z]+/"),
           j = factor(jurisdiction, levels = JORD))
  env <- c17b %>% filter(estimable, judge_model == ENVL) %>%
    mutate(j = factor(jurisdiction, levels = JORD))
  jord <- d %>% distinct(judge, canonical) %>% arrange(desc(canonical), judge)
  d <- d %>% mutate(judge = factor(judge, levels = rev(jord$judge)))

  s2 <- ggplot(d, aes(x = estimate_pp, y = judge)) +
    geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
    geom_rect(data = env, inherit.aes = FALSE,
              aes(xmin = conf_low_pp, xmax = conf_high_pp,
                  ymin = -Inf, ymax = Inf),
              fill = INK_FAINT, alpha = 0.16) +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp,
                       colour = jurisdiction), linewidth = LW_CI) +
    geom_point(aes(fill = jurisdiction, shape = canonical), size = PT_SM,
               colour = "white", stroke = 0.45) +
    scale_shape_manual(values = c(`TRUE` = 21, `FALSE` = 22), guide = "none") +
    scale_colour_manual(values = PAL_JURIS, guide = "none") +
    scale_fill_manual(values = PAL_JURIS, guide = "none") +
    facet_wrap(~ j, ncol = 2, scales = "free_x") +
    labs(x = "Home − away refusal difference (pp)", y = NULL) +
    theme_nature(grid = "x") +
    theme(axis.text.y = element_text(size = 5.4)) +
    labs(caption = cap(
      "The same covariate-standardized contrast, recomputed with each judge's ",
      "labels in turn (circle = canonical judge, squares = panel). Coloured ",
      "hairlines are 95% issue-cluster bootstrap intervals holding the ",
      "instrument fixed; the shaded band is their union, a sensitivity ",
      "envelope covering instrument choice. The band is NOT a confidence ",
      "interval and has no coverage guarantee: four judges chosen for cost and ",
      "speed are not a sample from a population of judges, and none is known ",
      "to be correct. Read it as a bound on how much the conclusion depends on ",
      "the measuring instrument."))
  save_fig(s2, file.path(APP_FIG, "S2_judge_multiverse.png"),
           width = W2, height = 4.2)
}

# =============================================================================
# S3 -- specification curve for the home contrast
# =============================================================================
c07 <- rd("c07_home_sensitivities.csv"); c04 <- rd("c04_home_standardized.csv")
if (!is.null(c07)) {
  cat("S3 specification curve\n")
  FAM <- c(leave_one_model_out = "drop one model",
           prompt_type = "prompt tier only",
           language = "one language only",
           outcome_code3 = "outcome: codes 3-5",
           min_response_chars = "minimum response length",
           overlap_restricted = "strata with both arms",
           hierarchical_marginal = "hierarchical, marginal")
  sc <- c07 %>% filter(estimable) %>%
    mutate(fam = recode(sensitivity, !!!FAM),
           j = factor(jurisdiction, levels = JORD),
           row = paste(fam, level, sep = ": "))
  prim <- c04 %>% filter(weighting == "nested", estimable) %>%
    transmute(j = factor(jurisdiction, levels = JORD), estimate_pp)

  s3 <- ggplot(sc, aes(x = estimate_pp, y = fct_rev(fct_inorder(row)))) +
    geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
    geom_vline(data = prim, aes(xintercept = estimate_pp, colour = j),
               linewidth = 0.4, linetype = "22") +
    geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp, colour = j),
                   linewidth = 0.35) +
    geom_point(aes(fill = j), shape = 21, size = 1.4, colour = "white",
               stroke = 0.3) +
    scale_colour_manual(values = PAL_JURIS, guide = "none") +
    scale_fill_manual(values = PAL_JURIS, guide = "none") +
    facet_wrap(~ j, ncol = 2, scales = "free") +
    labs(x = "Home − away refusal difference (pp)", y = NULL,
         caption = cap(
           "Every sensitivity in c07, one row per specification, with the ",
           "primary estimate as a dashed rule. The hierarchical row is a ",
           "different estimand rather than a check on the same one: it ",
           "integrates over the issue random effect instead of standardizing ",
           "over the observed issue set, so it is expected to differ.")) +
    theme_nature(grid = "x") +
    theme(axis.text.y = element_text(size = 4.6),
          strip.text = element_text(size = 6)) + tagt
  save_fig(s3, file.path(APP_FIG, "S3_specification_curve.png"),
           width = W2, height = 7.2)
}

# =============================================================================
# S4 -- refusal-text projection supplement
# =============================================================================
u2 <- rdp("u02_refusal_umap_all_languages.csv")
u3 <- rdp("u03_refusal_umap_lexical.csv")
if (!is.null(u2) || !is.null(u3)) {
  cat("S4 projection supplement\n")
  no_axes <- theme(
    axis.text.x = element_blank(), axis.text.y = element_blank(),
    axis.title.x = element_blank(), axis.title.y = element_blank(),
    axis.ticks.x = element_blank(), axis.ticks.y = element_blank(),
    axis.line.x = element_blank(), axis.line.y = element_blank(),
    panel.border = element_rect(fill = NA, colour = RULE, linewidth = 0.3),
    plot.title = element_text(colour = INK, face = "bold", size = rel(1.25),
                              hjust = 0, margin = margin(b = 1.5, l = 16)),
    legend.position = "top")
  trim <- function(d) {
    qx <- quantile(d$umap_x, c(0.015, 0.985)); qy <- quantile(d$umap_y, c(0.015, 0.985))
    d[d$umap_x >= qx[1] & d$umap_x <= qx[2] &
        d$umap_y >= qy[1] & d$umap_y <= qy[2], ]
  }
  LANG_NAME <- c(en = "English", zh = "Chinese", ar = "Arabic",
                 ru = "Russian", hi = "Hindi")

  pa <- if (is.null(u2)) NULL else {
    d <- trim(u2) %>% mutate(l = factor(unname(LANG_NAME[prompt_language]),
                                        levels = names(PAL_LANGUAGE)))
    ggplot(d %>% arrange(l), aes(umap_x, umap_y, colour = l)) +
      geom_point(size = 0.35, alpha = 0.6, stroke = 0) +
      scale_colour_manual(values = PAL_LANGUAGE, name = NULL, drop = FALSE) +
      guides(colour = guide_legend(override.aes = list(size = 1.9, alpha = 1),
                                   nrow = 1)) +
      coord_equal() + theme_nature(grid = "none") + no_axes + tagt +
      labs(title = "All languages, by language")
  }
  pb <- if (is.null(u3)) NULL else {
    d <- trim(u3) %>% mutate(reason = factor(reason_group,
                                             levels = names(PAL_REASON)))
    ggplot(d %>% arrange(reason), aes(umap_x, umap_y, colour = reason)) +
      geom_point(size = 0.5, alpha = 0.72, stroke = 0) +
      scale_colour_manual(values = PAL_REASON, name = NULL, drop = FALSE) +
      guides(colour = guide_legend(override.aes = list(size = 1.9, alpha = 1),
                                   nrow = 2)) +
      coord_equal() + theme_nature(grid = "none") + no_axes + tagt +
      labs(title = "English, lexical representation")
  }
  purl <- if (is.null(u3)) "" else sprintf(
    " Under the lexical representation the same codes reach %.0f%% neighbourhood purity against %.0f%% at random, ABOVE the semantic figure in the main text -- the codes track wording more closely than meaning.",
    100 * u3$purity_group_observed[1], 100 * u3$purity_group_baseline[1])

  s4 <- (if (is.null(pa)) pb else if (is.null(pb)) pa else (pa | pb)) +
    plot_annotation(tag_levels = "a", caption = cap(
      "Left: every refusal in all five languages, one shared projection. ",
      "Language dominates the layout, which is why the main-text panel is ",
      "English-only -- a multilingual space mostly separates writing systems. ",
      "Right: the same English refusals under TF-IDF rather than sentence ",
      "embeddings.", purl,
      " Points beyond the central 97% on either axis are not drawn."))
  save_fig(s4, file.path(APP_FIG, "S4_projection_supplement.png"),
           width = W2, height = 3.6)
}

cat("\nwrote:\n"); print(list.files(APP_FIG))
cat("\n", strrep("=", 78), "\nAPPENDIX FIGURES DONE\n", strrep("=", 78), "\n", sep = "")
