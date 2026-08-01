# =============================================================================
# Shared publication theme + validated palettes
# =============================================================================
# Sourced by every plotting script. Before this existed, the 46 figures split
# between theme_bw() and theme_minimal() with ad-hoc hex codes assigned per
# script, so the same model could carry a different colour in two figures of the
# same paper. One theme, one palette, defined once.
#
# Design follows Tufte's data-ink principle: every mark that is not data is a
# candidate for deletion. Concretely -- no panel background, no panel border, no
# vertical gridlines, no legend box, no facet-strip box, ticks only where they
# disambiguate. What survives is the data and the minimum scaffolding needed to
# read it.
#
# Colours are NOT chosen by eye. The categorical palette was selected by search
# over a documented 8-hue set and validated for colour-vision deficiency with
# the all-pairs check (scatter/small-multiple safe, which matters because most
# figures here facet by language):
#
#   #2a78d6 blue · #1baf7a aqua · #eda100 yellow · #4a3aa7 violet · #e34948 red
#   worst all-pairs normal-vision dE 16.3 (>=15 floor)  PASS
#   worst all-pairs CVD dE 6.9 deutan / 9.6 tritan      floor band
#   contrast vs surface <3:1 for aqua and yellow        relief required
#
# Two consequences are load-bearing and must not be undone:
#   * The CVD figure sits in the 6-8 floor band, which is legal ONLY alongside a
#     secondary encoding. Every categorical figure here also separates series by
#     facet or position, which satisfies that -- do not produce a chart where
#     colour is the sole distinction between series.
#   * Aqua and yellow fall below 3:1 against the page, so any figure relying on
#     them for a thin mark needs a direct label or an accompanying table.
#
# Model colour follows JURISDICTION, not the model. Eleven models exceed any
# validated categorical palette (8 hues is the documented ceiling, and a 9th is
# never a generated hue), and jurisdiction is the analytic variable anyway --
# the paper asks whether US/CN/EU/MENA/India models behave differently. Models
# are separated within a jurisdiction by facet or position, which doubles as the
# secondary encoding the CVD band requires.

suppressPackageStartupMessages(library(ggplot2))

# --- ink -------------------------------------------------------------------
INK_PRIMARY   <- "#0b0b0b"
INK_SECONDARY <- "#52514e"
INK_MUTED     <- "#8a8985"
RULE          <- "#d8d7d2"   # gridlines / axis rules: present but recessive

# --- categorical: jurisdiction (validated all-pairs, light surface) --------
PAL_JURISDICTION <- c(
  "US"    = "#2a78d6",
  "CN"    = "#1baf7a",
  "EU"    = "#eda100",
  "MENA"  = "#4a3aa7",
  "India" = "#e34948"
)

# Languages reuse the same validated five in fixed order. Colour follows the
# entity, so a figure that drops a language must not repaint the survivors.
PAL_LANGUAGE <- c(
  "English" = "#2a78d6", "Chinese" = "#1baf7a", "Arabic" = "#eda100",
  "Russian" = "#4a3aa7", "Hindi"   = "#e34948"
)
PAL_LANGUAGE_CODE <- setNames(unname(PAL_LANGUAGE), c("en", "zh", "ar", "ru", "hi"))

# --- categorical: prompt tier (regular vs boundary) ------------------------
# Two levels only, and the contrast is "baseline vs the probe" -- so the
# baseline recedes to muted ink and only the boundary tier takes a hue. The
# lightness gap (L* 57 vs 43) carries the distinction independently of hue,
# which is what keeps it readable under deutan/protan.
PAL_TIER <- c("Regular Prompts" = INK_MUTED, "Boundary Prompts" = "#c0392b")

# --- sequential: engagement 1-5 is ORDERED, so one hue, light -> dark ------
# Not a categorical palette: 1 (full engagement) .. 5 (hard refusal) is a scale,
# and giving it five unrelated hues would encode order as identity.
PAL_ENGAGEMENT <- c(
  "Full engagement"        = "#cfe0f5",
  "Engagement with caveats"= "#9dc0e8",
  "Partial engagement"     = "#6b9fda",
  "Soft refusal"           = "#3d7fc9",
  "Hard refusal"           = "#1c5da8"
)

# --- diverging: stance / ideology, two poles + NEUTRAL GREY midpoint -------
# A hue at the midpoint would imply the middle is a category; it is the absence
# of lean, so it is grey.
PAL_DIVERGING <- c("#c0392b", "#e08b7f", "#cfcec9", "#7fa8dd", "#2a78d6")

# =============================================================================
# theme_refusal() -- the publication theme
# =============================================================================
theme_refusal <- function(base_size = 10, base_family = "", grid = "y") {
  th <- theme_minimal(base_size = base_size, base_family = base_family) +
    theme(
      # Panel: no background, no border. The page is the background.
      panel.background  = element_blank(),
      panel.border      = element_blank(),
      plot.background   = element_blank(),

      # Gridlines: one direction only, and recessive. A grid perpendicular to
      # the value axis helps read magnitude; the other direction is decoration.
      panel.grid.major  = element_line(colour = RULE, linewidth = 0.25),
      panel.grid.minor  = element_blank(),

      # Axes: a thin rule on the categorical axis only; ticks short and muted.
      axis.line.x       = element_line(colour = RULE, linewidth = 0.3),
      axis.line.y       = element_blank(),
      axis.ticks        = element_line(colour = RULE, linewidth = 0.25),
      axis.ticks.length = unit(2, "pt"),
      axis.text         = element_text(colour = INK_SECONDARY, size = rel(0.9)),
      axis.title        = element_text(colour = INK_SECONDARY, size = rel(0.95)),

      # Legend: no box, no key background, sat at the top where it reads as a
      # caption rather than a panel competing with the data.
      legend.background = element_blank(),
      legend.key        = element_blank(),
      legend.position   = "top",
      legend.justification = "left",
      legend.title      = element_text(colour = INK_SECONDARY, size = rel(0.9)),
      legend.text       = element_text(colour = INK_SECONDARY, size = rel(0.9)),
      legend.margin     = margin(b = 2),

      # Facet strips: text, not boxes. Left-aligned so the eye tracks one edge.
      strip.background  = element_blank(),
      strip.text        = element_text(colour = INK_PRIMARY, face = "bold",
                                       size = rel(0.9), hjust = 0,
                                       margin = margin(b = 3)),

      # Titles: left-aligned, minimal weight contrast.
      plot.title        = element_text(colour = INK_PRIMARY, face = "bold",
                                       size = rel(1.15), hjust = 0,
                                       margin = margin(b = 3)),
      plot.subtitle     = element_text(colour = INK_SECONDARY, size = rel(0.95),
                                       hjust = 0, margin = margin(b = 8)),
      plot.caption      = element_text(colour = INK_MUTED, size = rel(0.8),
                                       hjust = 0, margin = margin(t = 8)),
      plot.title.position    = "plot",
      plot.caption.position  = "plot",
      plot.margin       = margin(6, 10, 6, 6)
    )
  # Value-axis grid only, per `grid`.
  if (identical(grid, "y")) {
    th <- th + theme(panel.grid.major.x = element_blank())
  } else if (identical(grid, "x")) {
    th <- th + theme(panel.grid.major.y = element_blank(),
                     axis.line.x = element_blank(),
                     axis.line.y = element_line(colour = RULE, linewidth = 0.3))
  } else if (identical(grid, "none")) {
    th <- th + theme(panel.grid.major = element_blank())
  }
  th
}

# Make it the default for any plot drawn after sourcing this file, so a script
# that forgets to add theme_refusal() still gets it.
theme_set(theme_refusal())

# --- scale helpers ---------------------------------------------------------
scale_fill_jurisdiction <- function(...)
  scale_fill_manual(values = PAL_JURISDICTION, na.value = INK_MUTED, ...)
scale_colour_jurisdiction <- function(...)
  scale_colour_manual(values = PAL_JURISDICTION, na.value = INK_MUTED, ...)
scale_color_jurisdiction <- scale_colour_jurisdiction

scale_fill_language <- function(...)
  scale_fill_manual(values = PAL_LANGUAGE, na.value = INK_MUTED, ...)
scale_colour_language <- function(...)
  scale_colour_manual(values = PAL_LANGUAGE, na.value = INK_MUTED, ...)
scale_color_language <- scale_colour_language

scale_fill_engagement <- function(...)
  scale_fill_manual(values = PAL_ENGAGEMENT, na.value = INK_MUTED, ...)

scale_fill_tier <- function(...)
  scale_fill_manual(values = PAL_TIER, na.value = INK_MUTED, ...)
scale_colour_tier <- function(...)
  scale_colour_manual(values = PAL_TIER, na.value = INK_MUTED, ...)
scale_color_tier <- scale_colour_tier

# Diverging scales take a midpoint of 0 by default (no lean).
scale_fill_stance <- function(midpoint = 0, ...)
  scale_fill_gradient2(low = PAL_DIVERGING[1], mid = PAL_DIVERGING[3],
                       high = PAL_DIVERGING[5], midpoint = midpoint, ...)
scale_colour_stance <- function(midpoint = 0, ...)
  scale_colour_gradient2(low = PAL_DIVERGING[1], mid = PAL_DIVERGING[3],
                         high = PAL_DIVERGING[5], midpoint = midpoint, ...)

# Single-series default: one colour, no legend needed (the title names it).
SERIES_ONE <- "#2a78d6"

# ggsave defaults for the paper: vector for print, no device-specific raster.
save_fig <- function(plot, file, width = 6.5, height = 4.0, ...) {
  ggsave(file, plot, width = width, height = height, units = "in",
         device = grDevices::cairo_pdf, ...)
}
