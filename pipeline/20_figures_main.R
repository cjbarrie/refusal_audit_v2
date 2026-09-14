# =============================================================================
# Technical reference: docs/r_pipeline/20_figures_main.md
# MAIN FIGURES -- genuine refusal only
# =============================================================================
# Figure 1 places the English genuine-refusal semantic map beside the matching
# English home-topic contrasts for each developer jurisdiction. One fixed UMAP
# geometry is reused throughout. A coloured sector denotes each model that
# refused; this preserves multi-model combinations without inventing dozens of
# categorical combination colours.
#
# Figure 2 links delivered-language semantic maps to paired language contrasts.
# Capability failure is absent from both main figures and appears separately in
# Extended Data. This script fits no model, interval, embedding, or UMAP.

source("pipeline/_theme.R")
suppressPackageStartupMessages({library(tidyverse); library(patchwork)})

CAN_EST <- Sys.getenv("CANON_EST_DIR", "pipeline/estimates/canonical")
CAN_FIG <- Sys.getenv("CANON_FIG_DIR", "pipeline/figures/main")
CAN_LAYOUT <- Sys.getenv("CANON_LAYOUT_DIR", CAN_EST)
dir.create(CAN_FIG, showWarnings = FALSE, recursive = TRUE)
dir.create(CAN_LAYOUT, showWarnings = FALSE, recursive = TRUE)
rd <- function(f) {
  p <- file.path(CAN_EST, f)
  if (!file.exists(p)) stop("missing canonical table: ", f)
  read_csv(p, show_col_types = FALSE)
}
theme_set(theme_nature(base_size = PT_BODY))
figs <- list()
save_main <- function(plot, name, height) {
  save_fig(plot, file.path(CAN_FIG, paste0(name, ".png")),
           width = W2, height = height)
  figs[[name]] <<- plot
}

JURIS_LABEL <- c(CN = "China", Russia = "Russia", MENA = "MENA", India = "India",
                 US = "United States", EU = "Europe")
LANG_LABEL <- c(en = "English", zh = "Chinese", ar = "Arabic",
                ru = "Russian", hi = "Hindi")
HOME_X_LIMITS <- c(-15, 25)

# Shared data contracts ------------------------------------------------------
c02 <- rd("c02_home_descriptive_english.csv")
c04 <- rd("c04_home_standardized.csv")
c05 <- rd("c05_home_by_model.csv")
c08 <- rd("c08_language_paired.csv")
c09 <- rd("c09_language_by_model.csv")
c22 <- rd("c22_prompt_umap_coordinates.csv")
c22p <- rd("c22_prompt_outcome_propensities.csv")
c22m <- rd("c22_prompt_outcomes_by_model.csv")

stopifnot(nrow(c22) == 2496L, !anyDuplicated(c22$prompt_id),
          setequal(unique(c22m$model), ORDER_MODEL),
          all(c22m$genuine_refusal %in% 0:1))
c22m <- c22m |> mutate(jurisdiction = unname(MODEL_JURIS[model]))
stopifnot(!anyNA(c22m$jurisdiction))

# Convert the uncommon multi-model refusals into equal-angle sectors. Radius
# is expressed in UMAP coordinates and therefore fixed across every map.
make_wedges <- function(events, radius = .090, vertices = 14L) {
  if (!nrow(events)) return(tibble())
  events |>
    arrange(jurisdiction, prompt_id, factor(model, levels = ORDER_MODEL)) |>
    group_by(jurisdiction, prompt_id) |>
    mutate(n_refusers = n(), sector = row_number()) |>
    ungroup() |>
    filter(n_refusers > 1L) |>
    pmap_dfr(function(jurisdiction, prompt_id, model, genuine_refusal,
                      umap_x, umap_y, n_refusers, sector, ...) {
      a0 <- pi / 2 + 2 * pi * (sector - 1) / n_refusers
      a1 <- pi / 2 + 2 * pi * sector / n_refusers
      theta <- seq(a0, a1, length.out = vertices + 1L)
      tibble(
        jurisdiction = jurisdiction, prompt_id = prompt_id, model = model,
        glyph_group = paste(prompt_id, model, sep = "__"),
        vertex = seq_len(length(theta) + 2L),
        x = c(umap_x, umap_x + radius * cos(theta), umap_x),
        y = c(umap_y, umap_y + radius * sin(theta), umap_y))
    })
}

events <- c22m |>
  select(prompt_id, model, genuine_refusal, jurisdiction) |>
  filter(genuine_refusal == 1L) |>
  left_join(c22 |> select(prompt_id, umap_x, umap_y), by = "prompt_id") |>
  group_by(jurisdiction, prompt_id) |>
  mutate(n_refusers = n()) |>
  ungroup()
single_events <- events |> filter(n_refusers == 1L)
multi_polygons <- make_wedges(events |> select(-n_refusers))

# Some English prompt-model outcomes are absent because generation or annotation
# failed. They must not silently become non-refusals; incomplete prompt cells
# receive the explicit hollow marker below.
coverage <- crossing(prompt_id = c22$prompt_id, model = ORDER_MODEL) |>
  mutate(jurisdiction = unname(MODEL_JURIS[model])) |>
  left_join(c22m |> select(prompt_id, model, genuine_refusal),
            by = c("prompt_id", "model")) |>
  group_by(jurisdiction, prompt_id) |>
  summarise(n_expected = n(), n_observed = sum(!is.na(genuine_refusal)),
            any_refusal = any(genuine_refusal == 1L, na.rm = TRUE),
            .groups = "drop")

x_lim <- range(c22$umap_x) + c(-.12, .12)
y_lim <- range(c22$umap_y) + c(-.12, .12)

semantic_map <- function(j) {
  mods <- ORDER_MODEL[unname(MODEL_JURIS[ORDER_MODEL]) == j]
  pal <- PAL_MODEL_BLOCK[[j]]
  bg <- c22 |> mutate(legend_group = "No genuine refusal")
  single <- single_events |> filter(jurisdiction == j) |>
    mutate(legend_group = model)
  poly <- multi_polygons |> filter(jurisdiction == j)
  incomplete <- coverage |> filter(jurisdiction == j, n_observed < n_expected,
                                    !any_refusal) |>
    left_join(c22 |> select(prompt_id, umap_x, umap_y), by = "prompt_id")
  legend_values <- c("No genuine refusal" = "#BFC3C5", pal)
  legend_breaks <- c("No genuine refusal", mods)

  ggplot() +
    geom_point(data = bg, aes(umap_x, umap_y, colour = legend_group),
               alpha = .34, size = .25) +
    geom_point(data = single, aes(umap_x, umap_y, colour = legend_group),
               alpha = .94, size = .82) +
    geom_polygon(data = poly, aes(x, y, group = glyph_group, fill = model),
                 colour = "white", linewidth = .045, alpha = .96) +
    geom_point(data = incomplete, aes(umap_x, umap_y), shape = 21,
               fill = "white", colour = INK_FAINT, stroke = .30, size = .72) +
    scale_colour_manual(values = legend_values, breaks = legend_breaks,
                        labels = legend_breaks, drop = FALSE, name = NULL) +
    scale_fill_manual(values = pal, guide = "none") +
    guides(colour = guide_legend(
      ncol = 1, byrow = TRUE,
      override.aes = list(alpha = 1, size = 1.15))) +
    coord_equal(xlim = x_lim, ylim = y_lim, expand = FALSE, clip = "off") +
    labs(x = NULL, y = NULL,
         tag = sprintf("%s · %d model%s", JURIS_LABEL[[j]], length(mods),
                       ifelse(length(mods) == 1L, "", "s"))) +
    theme_nature(base_size = PT_BODY, grid = "none") +
    theme(axis.text = element_blank(), axis.ticks = element_blank(),
          axis.ticks.x = element_blank(), axis.ticks.y = element_blank(),
          axis.line = element_blank(), axis.line.x = element_blank(),
          axis.line.y = element_blank(), legend.position = "right",
          legend.justification = "center", legend.text = element_text(size = PT_MIN),
          legend.spacing.x = unit(1, "pt"), legend.spacing.y = unit(0, "pt"),
          legend.key.height = unit(5.2, "pt"), legend.key.width = unit(5.2, "pt"),
          legend.box.margin = margin(0, 0, 0, 3),
          plot.tag = element_text(face = "bold", size = PT_TITLE, hjust = 0),
          plot.tag.position = c(0, 1), plot.margin = margin(8, 3, 1, 1),
          plot.title = element_blank(), plot.subtitle = element_blank(),
          plot.caption = element_blank())
}

home_forest <- function(j, show_key = FALSE, show_x_title = TRUE) {
  mods <- ORDER_MODEL[unname(MODEL_JURIS[ORDER_MODEL]) == j]
  pal <- PAL_MODEL_BLOCK[[j]]
  rows <- c("All models", mods)
  ypos <- setNames(rev(seq_along(rows)), rows)

  # The prompt frame has no Russia-focused issue stratum. GigaChat's refusal
  # map is fully observed, but a Russia home-minus-away contrast is undefined;
  # use the same cross mark used for other non-estimable coefficients rather
  # than explanatory prose inside the artwork.
  if (is.na(HOME_REGION_OF[[j]])) {
    absent <- tibble(label = rows, y = unname(ypos[rows]))
    return(ggplot(absent, aes(x = 0, y = y)) +
      geom_vline(xintercept = 0, colour = INK_FAINT, linewidth = .34) +
      geom_point(shape = 4, colour = INK_FAINT, size = 1.45, stroke = .55) +
      scale_x_continuous(limits = HOME_X_LIMITS, breaks = c(-10, 0, 10, 20),
                         expand = expansion(mult = c(0, .01))) +
      scale_y_continuous(breaks = unname(ypos), labels = names(ypos),
                         limits = c(.55, max(ypos) + .5), expand = c(0, 0)) +
      labs(x = if (show_x_title) "Home − away difference (percentage points)" else NULL,
           y = NULL) +
      theme_nature(base_size = PT_BODY, grid = "none") +
      theme(axis.text.y = element_text(colour = INK, size = PT_MIN),
            axis.title.x = element_text(size = PT_MIN),
            plot.margin = margin(8, 4, 2, 2)) + tag_only() +
      theme(plot.tag = element_blank()))
  }

  raw <- c02 |>
    filter(outcome == "genuine_refusal", quantity == "home minus away",
           jurisdiction == j) |>
    mutate(y = unname(ypos[["All models"]]) + .13,
           series = "Descriptive difference")
  adjusted <- c04 |>
    filter(outcome == "genuine_refusal", weighting == "nested",
           support == "full target", jurisdiction == j) |>
    mutate(y = unname(ypos[["All models"]]) - .13,
           series = "Standardized contrast")
  model_rows <- c05 |>
    filter(outcome == "genuine_refusal", jurisdiction == j) |>
    mutate(y = unname(ypos[model]))

  p <- ggplot() +
    geom_vline(xintercept = 0, colour = INK_FAINT, linewidth = .34) +
    geom_vline(xintercept = c(-10, 10, 20), colour = RULE, linewidth = .18) +
    geom_errorbar(data = raw,
                  aes(xmin = conf_low_pp, xmax = conf_high_pp, y = y),
                  orientation = "y", width = 0, colour = INK_FAINT,
                  linewidth = .42) +
    geom_point(data = raw, aes(estimate_pp, y, shape = series),
               colour = INK_FAINT, fill = "white", size = 1.6, stroke = .5) +
    geom_errorbar(data = filter(adjusted, interval_reliable),
                  aes(xmin = conf_low_pp, xmax = conf_high_pp, y = y),
                  orientation = "y", width = 0, colour = ACCENT,
                  linewidth = .62) +
    geom_point(data = adjusted, aes(estimate_pp, y, shape = series),
               colour = ACCENT,
               fill = if (isTRUE(adjusted$interval_reliable[[1]])) ACCENT else "white",
               size = 1.9, stroke = .58) +
    geom_errorbar(data = filter(model_rows, estimable, interval_reliable),
                  aes(xmin = conf_low_pp, xmax = conf_high_pp, y = y,
                      colour = model), orientation = "y", width = 0,
                  linewidth = .43) +
    geom_point(data = filter(model_rows, estimable),
               aes(estimate_pp, y, colour = model), size = 1.45) +
    geom_point(data = filter(model_rows, !estimable), aes(x = 0, y = y),
               shape = 4, colour = INK_FAINT, size = 1.45, stroke = .55) +
    scale_colour_manual(values = pal, guide = "none") +
    scale_shape_manual(values = c("Descriptive difference" = 21,
                                  "Standardized contrast" = 23),
                       breaks = c("Descriptive difference",
                                  "Standardized contrast"), name = NULL) +
    scale_x_continuous(limits = HOME_X_LIMITS,
                       breaks = c(-10, 0, 10, 20),
                       expand = expansion(mult = c(0, .01))) +
    scale_y_continuous(breaks = unname(ypos), labels = names(ypos),
                       limits = c(.55, max(ypos) + .5), expand = c(0, 0)) +
    labs(x = if (show_x_title) "Home − away difference (percentage points)" else NULL,
         y = NULL) +
    theme_nature(base_size = PT_BODY, grid = "none") +
    theme(axis.text.y = element_text(colour = INK, size = PT_MIN),
          axis.title.x = element_text(size = PT_MIN),
          legend.position = if (show_key) "top" else "none",
          legend.justification = "left", legend.text = element_text(size = PT_MIN),
          plot.margin = margin(8, 4, 2, 2)) +
    tag_only() + theme(plot.tag = element_blank())
  if (show_key) {
    p <- p + guides(shape = guide_legend(
      nrow = 1, override.aes = list(
        colour = c(INK_FAINT, ACCENT), fill = c("white", ACCENT), size = 1.5)))
  }
  p
}

jurisdiction_block <- function(j, show_key = FALSE, show_x_title = TRUE) {
  (semantic_map(j) | home_forest(j, show_key, show_x_title)) +
    plot_layout(widths = c(.52, .48))
}

# Figure 1: six equal-height jurisdiction rows. A two-column prototype was
# rejected at print size: fixed-aspect maps left large vertical voids and the
# local model keys truncated. Full-width rows retain the map--estimate pairing,
# give every semantic map the same physical dimensions, and keep all 20 model
# names legible. Only the final row repeats the common x-axis title.
fig1_blocks <- map2(
  ORDER_JURIS,
  seq_along(ORDER_JURIS),
  ~ jurisdiction_block(.x, show_key = .y == 1L,
                        show_x_title = .y == length(ORDER_JURIS)))
fig1 <- wrap_plots(fig1_blocks, ncol = 1, heights = rep(1, length(fig1_blocks)))
save_main(fig1, "Fig1_jurisdiction_refusal_atlas_home", H_PAGE)

# Figure 2: semantic pattern and paired language contrasts -------------------
language_points <- c22p |>
  filter(outcome == "genuine_refusal", language %in% ORDER_LANG) |>
  left_join(c22 |> select(prompt_id, umap_x, umap_y), by = "prompt_id") |>
  mutate(language_label = factor(unname(LANG_LABEL[language]),
                                 levels = unname(LANG_LABEL[ORDER_LANG])))
stopifnot(nrow(language_points) == nrow(c22) * length(ORDER_LANG))

p_language_maps <- ggplot(language_points, aes(umap_x, umap_y)) +
  geom_point(colour = "#B8B8BA", alpha = .23, size = .16) +
  geom_point(data = filter(language_points, propensity > 0),
             aes(size = propensity), colour = ACCENT, alpha = .78) +
  facet_wrap(~ language_label, nrow = 1) +
  scale_size_area(max_size = 1.5, limits = c(0, 1),
                  breaks = c(.05, .10, .20),
                  labels = scales::label_percent(accuracy = 1),
                  name = "Genuine-refusal propensity") +
  coord_equal(xlim = x_lim, ylim = y_lim, expand = FALSE) +
  labs(x = NULL, y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "none") +
  theme(axis.text = element_blank(), axis.ticks = element_blank(),
        axis.line = element_blank(), strip.text = element_text(size = PT_MIN),
        legend.position = "top", legend.justification = "left",
        legend.text = element_text(size = PT_MIN),
        legend.title = element_text(size = PT_MIN)) +
  tag_only() + theme(plot.tag = element_blank())

agg_language <- c08 |>
  filter(outcome == "genuine_refusal", weighting == "equal_model") |>
  mutate(language_label = factor(unname(LANG_LABEL[language]),
                                 levels = rev(ORDER_LANG_CONTRAST)))
p_agg_language <- ggplot(agg_language, aes(estimate_pp, language_label)) +
  geom_vline(xintercept = 0, colour = INK_FAINT, linewidth = .34) +
  geom_errorbar(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                orientation = "y", width = 0, colour = ACCENT, linewidth = .62) +
  geom_point(shape = 23, fill = ACCENT, colour = ACCENT, size = 1.9) +
  scale_x_continuous(breaks = c(-1, -.5, 0, .5)) +
  labs(x = "Target language − English (percentage points)", y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.text.y = element_text(colour = INK, size = PT_BODY)) +
  tag_only() + theme(plot.tag = element_blank())

model_language <- c09 |>
  filter(outcome == "genuine_refusal") |>
  mutate(model = factor(model, levels = rev(ORDER_MODEL)),
         language_label = factor(unname(LANG_LABEL[language]),
                                 levels = ORDER_LANG_CONTRAST),
         excludes_zero = conf_low_pp > 0 | conf_high_pp < 0)
lim_lang <- max(abs(model_language$estimate_pp), na.rm = TRUE)
p_model_language <- ggplot(model_language,
    aes(language_label, model, fill = estimate_pp)) +
  geom_tile(colour = "white", linewidth = .2) +
  geom_point(data = filter(model_language, excludes_zero), shape = 16,
             colour = INK, size = .42) +
  scale_fill_gradient2(low = "#2C5F7C", mid = "#F2F2F0", high = "#8C363C",
                       midpoint = 0, limits = c(-lim_lang, lim_lang),
                       name = "Difference (pp)") +
  labs(x = NULL, y = NULL) +
  theme_nature(base_size = PT_BODY, grid = "none") +
  theme(axis.text.x = element_text(colour = INK, size = PT_MIN),
        axis.text.y = element_text(colour = INK, size = PT_MIN),
        legend.position = "top", legend.justification = "left",
        legend.text = element_text(size = PT_MIN),
        legend.title = element_text(size = PT_MIN), axis.line = element_blank(),
        axis.ticks = element_blank()) +
  tag_only() + theme(plot.tag = element_blank())

fig2 <- p_language_maps / (p_agg_language | p_model_language) +
  plot_layout(heights = c(.92, 1.08), widths = c(.42, .58))
save_main(fig2, "Fig2_language_refusal_atlas_contrasts", H_STD)

saveRDS(figs, file.path(CAN_LAYOUT, "c20_figure_layout_main.rds"))
