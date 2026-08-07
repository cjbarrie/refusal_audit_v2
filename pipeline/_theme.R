# =============================================================================
# Design system for publication figures
# =============================================================================
# Sourced by every plotting script. One theme, one palette, one export path.
#
# TARGET: a leading general-science journal. Concretely that means figures are
# designed at final printed size (Nature single column 89 mm, double 183 mm),
# not designed large and shrunk -- shrinking is what produces the 5 pt axis text
# and colliding labels that make a figure look amateur on the page.
#
# PRINCIPLES APPLIED (Tufte, data-ink)
#   * No panel background, no border, no vertical grid, no tick marks on the
#     categorical axis. The page is the background.
#   * Colour is not decoration. Default is ink; ACCENT is spent on the ONE
#     series or estimate the figure exists to show. A figure with every category
#     in its own hue has used colour to avoid deciding what it is about.
#   * Direct labels over legends. A legend is a lookup table the reader must
#     hold in memory; a label at the end of the series is not.
#   * Redundant encoding is removed: if facets already name the groups, colour
#     must not name them again.
#
# TYPOGRAPHY
#   ONE sans family throughout, including model names. Monospaced model labels
#   were tried and dropped: at 7 pt Courier is wide and pale next to the sans
#   axis text, so the labels read as a different kind of object from the rest of
#   the figure. FONT_MONO is retained only for any future code listing.
#
# EXPORT -- PNG ONLY. THIS IS A PROJECT RULE, NOT A DEFAULT.
#   Every figure is written as a 600 dpi PNG and NOTHING ELSE. No PDF, no SVG,
#   no EPS. Do not add a vector branch to save_fig(), do not call ggsave()
#   directly, and do not add a `device =` argument anywhere in pipeline/.
#   Rationale: multi-format export repeatedly drifted out of sync here (formats
#   rendered with different fonts and different metrics, and stale files from a
#   previous design lingered in the directory). One writer, one format, one
#   source of truth. pipeline/audit_figures.R FAILS if any non-PNG appears in
#   pipeline/figures/.
#   Rendering is via ragg, which has better hinting and more accurate text
#   metrics than grDevices.

suppressPackageStartupMessages({
  library(ggplot2)
  library(grid)
})

# --- fonts -----------------------------------------------------------------
# Resolve once, with fallbacks, so the file is portable off this machine.
.pick_font <- function(candidates, fallback) {
  if (!requireNamespace("systemfonts", quietly = TRUE)) return(fallback)
  fams <- unique(systemfonts::system_fonts()$family)
  hit <- candidates[candidates %in% fams]
  if (length(hit)) hit[1] else fallback
}
# Helvetica and Courier are kept (rather than Helvetica Neue / Menlo) so the
# design does not depend on macOS-only faces and renders identically on another
# machine. Output is PNG only, so there is no second device to keep in sync.
FONT_SANS <- .pick_font(c("Helvetica", "Arial"), "sans")
FONT_MONO <- "Courier"

# --- ink and rules ---------------------------------------------------------
INK        <- "#111111"   # primary text, data marks
INK_SOFT   <- "#59595B"   # axis text, secondary labels
INK_FAINT  <- "#9B9B9E"   # de-emphasised series, annotation
RULE       <- "#DEDEDE"   # gridlines, axis rules
PANEL_FILL <- "#F4F4F2"   # only for shaded reference bands

# --- accent ----------------------------------------------------------------
# ONE accent. Deep red reads as the marked case in print, holds up in grayscale
# (L* 39 against INK_FAINT L* 64 -- a 25-point lightness gap survives a
# black-and-white photocopy), and is distinguishable under deuteranopia and
# protanopia because the contrast carried is lightness, not hue.
ACCENT      <- "#A11226"
ACCENT_SOFT <- "#D98C99"
# Second accent only where two marked series are genuinely required.
ACCENT_2    <- "#1B4F8A"

# --- semantic colour: jurisdiction and region ------------------------------
# ONE identity-based mapping. A model inherits its developer jurisdiction's
# colour, and an issue inherits its region's colour -- so the locator map, the
# home-region estimates, the region matrix and the model plots all speak the
# same language, and the map can act as the palette key.
#
# Identity-based, NOT effect-based: if an estimate moves, the colours stay put.
# An earlier version keyed lightness to effect size, which would have silently
# recoloured the whole system the first time a number changed.
#
# Constructed in LCH at controlled lightness (L* 35/47/58/68/81/92), not picked
# by eye. Minimum pairwise L* gap is 10 under normal vision and 6-7 under
# simulated protan/deutan vision, so the ordering survives grayscale and CVD.
# Colour is nevertheless a SECONDARY encoding throughout -- position and direct
# labels carry the information.
PAL_JURIS <- c(
  "CN"    = "#8C363C",   # deep muted red      L* 35
  "India" = "#4F748F",   # slate blue          L* 47
  "MENA"  = "#B88047",   # burnt ochre         L* 58
  "US"    = "#96A8B6",   # cool grey-blue      L* 68
  "EU"    = "#C0CBD3"    # light cool slate    L* 81
)
# Issue regions carry the colour of the jurisdiction whose home they are;
# "General" has no jurisdiction and is a neutral near-white.
PAL_REGION <- c(
  "China"   = "#8C363C", "India" = "#4F748F", "Arab" = "#B88047",
  "US"      = "#96A8B6", "Europe" = "#C0CBD3", "General" = "#E5E9EC"
)

JURIS_LEVELS  <- c("CN", "MENA", "India", "US", "EU")
REGION_LEVELS <- c("China", "Arab", "India", "US", "Europe", "General")

# DISPLAY labels for issue regions. The stored level is "Arab" (the 22 Arab
# League states, as harvested), but every figure shows "MENA" so the issue
# region reads against the MENA jurisdiction it is the home region of. Keeping
# the data value and the display label separate avoids a rename that would touch
# HOME_REGION, PAL_REGION and every stored estimate table.
REGION_DISPLAY <- c("China" = "China", "Arab" = "MENA", "India" = "India",
                    "US" = "US", "Europe" = "Europe", "General" = "General")
region_label <- function(x) unname(REGION_DISPLAY[as.character(x)])
HOME_REGION   <- c(US = "US", CN = "China", EU = "Europe",
                   MENA = "Arab", India = "India")

scale_colour_juris <- function(...)
  scale_colour_manual(values = PAL_JURIS, na.value = INK_FAINT, ...)
scale_color_juris <- scale_colour_juris
scale_fill_juris <- function(...)
  scale_fill_manual(values = PAL_JURIS, na.value = INK_FAINT, ...)

# --- ENCODING RULES (enforced by audit_figures.R) --------------------------
# A visual variable must never carry two meanings. Jurisdiction colour is
# reserved for jurisdiction / home-region / the locator map. Everything else
# gets its own channel:
#
#   language        -> shape + linetype (NOT the China red)
#   prompt tier     -> shape: circle = regular, triangle = boundary
#   refusal reason  -> its own qualitative palette, below
#   increase/decr.  -> sign and direction, never a second colour scheme
#   not estimable   -> hollow square, and the words "not estimable"
#
# Refusal reasons are response types, not model origins, so they must not borrow
# jurisdiction hues. Four qualitative colours, lightness-separated for grayscale.
# Refusal reasons are NOMINAL categories, so they get four distinct hues, not
# four shades of one. Built in LCH at controlled lightness (L* 38/52/64/76;
# min pairwise gap 12 normal, 8 protan) and verified disjoint from PAL_JURIS,
# because a reason must never be mistaken for a model origin.
# FIVE categories, not four. The judge's code G ("other") is 15.7% of English
# refusals and its free text shows it is heterogeneous -- degenerate output,
# explicit task refusals, and epistemic statements all land there. Folding it
# into F ("no reason given") produced a single "unstated" bar that meant two
# incompatible things and silently absorbed a measurement failure mode. The two
# are now separate and G is named honestly.
#
# Order here is the FACTOR order (neutrality first). geom_col stacks in reverse
# factor order, so on the drawn bar this reads right-to-left: neutrality sits at
# the right edge. The legend must be given breaks = rev(levels) to match the
# drawn order -- audit_figures.R checks that they agree.
PAL_REASON <- c(
  "neutrality"  = "#325D83",  # slate blue   L* 38  -- the modal reason
  "harm"        = "#AD6C48",  # muted rust   L* 52
  "epistemic"   = "#A994B4",  # muted violet L* 64
  "other"       = "#B0B6BA",  # mid grey     L* 73  -- judge code G
  "none given"  = "#DDE1E4"   # pale grey    L* 89  -- judge code F
)

SHAPE_TIER <- c("regular" = 21, "boundary" = 24)   # circle / triangle, fillable
SHAPE_ESTIMAND <- c(primary = 21, descriptive = 1)  # filled vs hollow
# Prompt language. Circle filled/hollow for the en-vs-zh pair, plus a diamond
# for Arabic in the three-language roster comparison. Triangle (24) stays
# reserved for the boundary tier and square for "not estimable", so these never
# collide with the tier or estimand encodings -- audit_figures.R enforces it.
SHAPE_LANG <- c("en" = 21, "zh" = 1, "ar" = 23)
LTY_LANG   <- c("en" = "solid", "zh" = "22")

# Sequential ramp for ordered quantities (engagement 1-5, rates in a heatmap).
# Single hue, light -> dark: order is encoded by lightness, so it survives
# grayscale and CVD without any hue discrimination at all.
SEQ_5 <- c("#E8EDF3", "#C2D0E0", "#8FA8C6", "#5A7CA5", "#2A5183")

# Sequential ramp for the raw jurisdiction x region rate matrix. Lives here, not
# in the figure script, so figures stay free of literal colour values.
SEQ_MATRIX <- c("#FAFBFB", "#C9D3DA", "#7F929F", "#3E5568")

# Regular vs boundary: the baseline recedes, the probe is marked.
PAL_TIER <- c("Regular Prompts" = INK_FAINT, "Boundary Prompts" = ACCENT)

# Diverging, centred at zero: for the excess-refusal (interaction residual)
# matrix, where the sign is the whole point. Neutral grey at the midpoint so
# "no excess" reads as absence rather than as a category.
PAL_DIVERGE <- c("#2C5F7C", "#8FAFC2", "#EFEFEF", "#D69B7A", "#8C363C")

# Neutral land on the locator map, and the fill for a cell whose value is not
# estimable. Defined here so no colour literal appears in a figure script.
MAP_LAND   <- "#F4F5F6"
CELL_EMPTY <- "#FBFBFC"

# Languages: ink by default; scripts that must distinguish all five use this
# ordered ramp, which is again lightness-ordered rather than hue-coded.
# Ordered by LIGHTNESS, not hue: with all five languages in one panel, English
# and Chinese previously sat at the same L* (34) and were indistinguishable in
# grayscale or for a colour-vision-deficient reader. Chinese keeps the accent
# hue but is darkened; Russian is lightened. audit_figures.R enforces a minimum
# L* gap of 5 across this palette.
PAL_LANGUAGE <- c("Chinese" = "#6E0C18", "English" = "#2A5183",
                  "Arabic"  = "#5A7CA5", "Hindi"   = "#9B9B9E",
                  "Russian" = "#C6D3E0")

# --- figure geometry -------------------------------------------------------
# Journal column widths in inches. Design to these; never scale afterwards.
W1 <- 89  / 25.4   # single column, 3.50 in
W15 <- 120 / 25.4  # 1.5 column,   4.72 in
W2 <- 183 / 25.4   # double column, 7.20 in

# =============================================================================
# theme_nature()
# =============================================================================
# grid: "x" puts the grid perpendicular to a horizontal value axis (dot plots
# with categories on y), "y" for vertical value axes, "none" when the figure is
# directly labelled and the grid would be pure ink.
# mono_y / mono_x: set the categorical axis in monospace, for model identifiers.
theme_nature <- function(base_size = 7, grid = "x",
                         mono_y = FALSE, mono_x = FALSE,
                         md_subtitle = FALSE) {
  th <- theme_minimal(base_size = base_size, base_family = FONT_SANS) +
    theme(
      panel.background = element_blank(),
      panel.border     = element_blank(),
      plot.background  = element_rect(fill = "white", colour = NA),

      panel.grid.major = element_line(colour = RULE, linewidth = 0.2),
      panel.grid.minor = element_blank(),

      axis.line.x  = element_line(colour = INK_SOFT, linewidth = 0.3),
      axis.line.y  = element_blank(),
      axis.ticks.x = element_line(colour = INK_SOFT, linewidth = 0.3),
      axis.ticks.y = element_blank(),
      axis.ticks.length = unit(1.6, "pt"),

      axis.text  = element_text(colour = INK_SOFT, size = rel(1.0)),
      axis.title = element_text(colour = INK_SOFT, size = rel(1.0)),
      axis.title.x = element_text(margin = margin(t = 4)),
      axis.title.y = element_text(margin = margin(r = 4)),

      legend.position   = "none",          # direct labels are the default
      legend.background = element_blank(),
      legend.key        = element_blank(),
      legend.title      = element_blank(),
      legend.text       = element_text(colour = INK_SOFT, size = rel(0.95)),
      legend.margin     = margin(0, 0, 0, 0),
      legend.box.spacing = unit(3, "pt"),

      strip.background = element_blank(),
      strip.text = element_text(colour = INK, face = "bold", size = rel(1.0),
                                hjust = 0, margin = margin(b = 2.5, t = 1)),

      plot.title = element_text(colour = INK, face = "bold", size = rel(1.25),
                                hjust = 0, margin = margin(b = 1.5)),
      plot.subtitle = element_text(colour = INK_SOFT, size = rel(1.05),
                                   hjust = 0, margin = margin(b = 6)),
      plot.caption = element_text(colour = INK_FAINT, size = rel(0.9), hjust = 0),
      plot.title.position   = "plot",
      plot.caption.position = "plot",
      plot.margin = margin(5, 8, 4, 4),
      panel.spacing = unit(7, "pt")
    )

  if (identical(grid, "x")) th <- th + theme(panel.grid.major.y = element_blank())
  if (identical(grid, "y")) th <- th + theme(panel.grid.major.x = element_blank(),
                                             axis.line.x = element_blank(),
                                             axis.ticks.x = element_blank())
  if (identical(grid, "none")) th <- th + theme(panel.grid.major = element_blank())

  if (mono_y) th <- th + theme(axis.text.y = element_text(family = FONT_MONO,
                                                          colour = INK,
                                                          size = rel(0.95)))
  if (mono_x) th <- th + theme(axis.text.x = element_text(family = FONT_MONO,
                                                          colour = INK,
                                                          size = rel(0.95)))
  # Render the subtitle as markdown so a key can be carried inside the sentence
  # (see key_sentence). Needs ggtext; degrades to a plain subtitle without it.
  if (md_subtitle && requireNamespace("ggtext", quietly = TRUE)) {
    th <- th + theme(plot.subtitle = ggtext::element_markdown(
      colour = INK_SOFT, size = rel(1.05), hjust = 0,
      margin = margin(b = 6), lineheight = 1.25))
  }
  th
}

# Build a subtitle in which the series names ARE the key: each name is set in
# its own series colour and bolded, inline in the sentence. This removes the
# legend without spending panel space on floating labels, which collide whenever
# two series happen to sit close together.
key_sentence <- function(prefix, named_colours, suffix = "") {
  parts <- vapply(names(named_colours), function(nm)
    sprintf("<span style='color:%s'>**%s**</span>", named_colours[[nm]], nm),
    character(1))
  joined <- if (length(parts) > 1)
    paste(paste(head(parts, -1), collapse = ", "), "to", tail(parts, 1))
  else parts
  trimws(paste(prefix, joined, suffix))
}

theme_set(theme_nature())

# =============================================================================
# Export -- the single sanctioned writer
# =============================================================================
# PNG at 600 dpi through ragg. `height` is in inches; pick it from the number of
# rows so row spacing stays constant across figures rather than stretching.
save_fig <- function(plot, file, width = W2, height = 4.2, dpi = 600) {
  dir.create(dirname(file), showWarnings = FALSE, recursive = TRUE)
  stem <- sub("\\.[a-z]+$", "", file)
  # PNG ONLY -- see the export rule at the top of this file. Do not reinstate a
  # vector branch here.
  dev <- if (requireNamespace("ragg", quietly = TRUE)) ragg::agg_png else NULL
  if (is.null(dev)) {
    ggsave(paste0(stem, ".png"), plot, width = width, height = height,
           units = "in", dpi = dpi, bg = "white")
  } else {
    ggsave(paste0(stem, ".png"), plot, width = width, height = height,
           units = "in", dpi = dpi, device = dev, bg = "white")
  }
  cat(sprintf("  saved %-42s %.2f x %.2f in @ %d dpi\n",
              basename(stem), width, height, dpi))
  invisible(stem)
}

# Height that keeps row pitch constant in a dot plot: n rows at ~0.16 in each
# plus fixed chrome for title/axis.
h_rows <- function(n, per = 0.155, chrome = 1.05) chrome + per * n

# =============================================================================
# Small helpers
# =============================================================================
# Wilson score interval -- correct at the small cell counts and near-zero rates
# this study produces, where a Wald interval would run below 0.
wilson_ci <- function(k, n, z = 1.96) {
  p <- k / n
  d <- 1 + z^2 / n
  c0 <- (p + z^2 / (2 * n)) / d
  hw <- z * sqrt((p * (1 - p) + z^2 / (4 * n)) / n) / d
  data.frame(lo = pmax(0, c0 - hw), hi = pmin(1, c0 + hw))
}

# Topic domains are snake_case in the data; render as prose in figures.
pretty_domain <- function(x) {
  x <- gsub("_", " ", x)
  paste0(toupper(substring(x, 1, 1)), substring(x, 2))
}

scale_fill_tier   <- function(...) scale_fill_manual(values = PAL_TIER, ...)
scale_colour_tier <- function(...) scale_colour_manual(values = PAL_TIER, ...)
scale_color_tier  <- scale_colour_tier
scale_colour_language <- function(...) scale_colour_manual(values = PAL_LANGUAGE, ...)
scale_color_language  <- scale_colour_language
scale_fill_language   <- function(...) scale_fill_manual(values = PAL_LANGUAGE, ...)

# Percent axis that stops where the data stops. Truncating the top of a rate
# axis at 100% when nothing exceeds 25% wastes three-quarters of the panel and
# flattens every difference the figure exists to show.
scale_x_rate <- function(limit, breaks = waiver(), expand_mult = c(0.01, 0.10)) {
  scale_x_continuous(labels = scales::label_percent(accuracy = 1),
                     limits = c(0, limit), breaks = breaks,
                     expand = expansion(mult = expand_mult))
}
