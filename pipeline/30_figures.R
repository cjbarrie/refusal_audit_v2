# =============================================================================
# Script 30: Figures  (PLOTTING ONLY -- reads saved estimates, never re-fits)
# =============================================================================
# Input : pipeline/estimates/*.csv   (written by 20_, 21_, 22_, 23_)
# Output: pipeline/figures/*.png     PNG ONLY, 600 dpi, two-column, white bg
#
# FOUR main figures, one message each, emphasis following strength of evidence:
#   FIG1  distinctive home-region sensitivity is overwhelmingly a China result
#   FIG2  boundary framing moves refusal in opposite directions
#   FIG3  neutrality dominates stated rationales; Jais is harm-dominant
#   FIG4  engaged answers are ideologically neutral; moral content is ordered
#
# FIG4 is deliberately the quietest of the four: it rests on a 25% issue
# subsample, is conditional on engagement, and is the most measurement-sensitive.
# It gets no emphasised lead mark.
#
# One canonical file per figure, rendered directly at final size. No _1col, no
# _2col, no resized derivatives. The locator map opens FIG1 as a slim strip: it
# carries no statistical evidence, so it is kept deliberately short and visually
# subordinate to the three panels that do, rather than the tall block that was
# previously delaying the main result. It is also available standalone as P1.
#
# ENCODING (see _theme.R; enforced by audit_figures.R)
#   jurisdiction -> colour            tier     -> circle / triangle
#   estimand     -> filled / hollow   reason   -> own 5-hue palette
#   language     -> circle/hollow/diamond, ONLY where tier is not encoded
#   uncertainty  -> thin interval in a lighter tint of its mark

suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork); library(sf)
})
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")

EST <- "pipeline/estimates"; FIGS <- "pipeline/figures"
rd <- function(f) read_csv(file.path(EST, f), show_col_types = FALSE)
has <- function(f) file.exists(file.path(EST, f))
cat(strrep("=", 78), "\nFIGURES\n", strrep("=", 78), "\n", sep = "")

JORDER <- c("CN", "MENA", "India", "US", "EU")
yj <- function(x) factor(x, levels = rev(JORDER))

PT <- 2.5; PT_SM <- 1.85; LW <- 0.9; LW_CI <- 0.55; TXT <- 2.2
lighten <- function(hex, f = 0.55)
  grDevices::rgb(t(255 - (255 - grDevices::col2rgb(hex)) * (1 - f)), maxColorValue = 255)

theme_fig <- function(grid = "x") theme_nature(grid = grid) +
  theme(plot.margin = margin(4, 7, 3, 4),
        axis.title.x = element_text(size = rel(0.95), margin = margin(t = 3)),
        axis.text.y  = element_text(colour = INK, size = rel(1.0)),
        plot.tag = element_text(family = FONT_SANS, face = "bold", size = 8.5,
                                colour = INK),
        plot.tag.position = c(0, 1))

tier_guide <- function(fill = INK_SOFT)
  guides(shape = guide_legend(
    override.aes = list(fill = fill, colour = "white", size = PT_SM + 0.4,
                        stroke = 0.4), order = 1))

pretty_dom <- function(x) {
  x <- gsub("_", " ", x)
  x <- sub("^civil rights liberties$", "Civil rights and liberties", x)
  x <- sub("^governance democracy$",   "Governance and democracy", x)
  x <- sub("^religion state$",         "Religion and state", x)
  x <- sub("^social moral$",           "Social and moral issues", x)
  x <- sub("^migration nationalism$",  "Migration and nationalism", x)
  x <- sub("^environment energy$",     "Environment and energy", x)
  x <- sub("^security conflict$",      "Security and conflict", x)
  x <- sub("^economic policy$",        "Economic policy", x)
  x <- sub("^territorial sovereignty$","Territorial sovereignty", x)
  x
}

# =============================================================================
# Locator -- FIG1 panel A (slim strip) and standalone P1
# =============================================================================
cat("locator\n")
ARAB <- c("DZA","BHR","COM","DJI","EGY","IRQ","JOR","KWT","LBN","LBY","MRT",
          "MAR","OMN","PSE","QAT","SAU","SOM","SDN","SYR","TUN","ARE","YEM")
world <- rnaturalearth::ne_countries(scale = "small", returnclass = "sf") %>%
  mutate(reg = case_when(
    iso_a3 == "CHN" ~ "China", iso_a3 == "IND" ~ "India", iso_a3 == "USA" ~ "US",
    iso_a3 %in% ARAB ~ "Arab",
    continent == "Europe" & iso_a3 != "RUS" ~ "Europe", TRUE ~ NA_character_)) %>%
  st_transform("+proj=robin")

# `reg` keys the palette (region levels), `disp` is what is drawn: the Arab
# issue-region is labelled MENA on the map so it reads against the MENA
# jurisdiction column in panel C.
lab <- tribble(~reg, ~disp, ~lon, ~lat,
               "US", "US", -100, 41, "Europe", "Europe", 14, 57,
               "Arab", "MENA", 22, 26,
               "India", "India", 94, 9, "China", "China", 104, 40) %>%
  st_as_sf(coords = c("lon", "lat"), crs = 4326) %>% st_transform("+proj=robin")
lab <- bind_cols(st_drop_geometry(lab), as_tibble(st_coordinates(lab)))

make_locator <- function(ylim = c(-1.0e6, 6.3e6)) ggplot() +
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
  coord_sf(xlim = c(-1.30e7, 1.45e7), ylim = ylim, expand = FALSE) +
  theme_void() +
  theme(plot.margin = margin(0, 2, 0, 2),
        plot.background = element_rect(fill = "white", colour = NA),
        plot.tag = element_text(family = FONT_SANS, face = "bold", size = 8.5,
                                colour = INK),
        plot.tag.position = c(0, 1))

# The strip in FIG1 is cropped to the latitude band that actually contains the
# five regions, so the panel is mostly evidence-bearing land rather than ocean.
# Top of the band must clear the "Europe" label, which sits at 57N; cropping
# to 6.0e6 sheared it off.
p_locator_strip <- make_locator(ylim = c(-0.4e6, 6.75e6))
p_locator       <- make_locator()

# =============================================================================
# FIG1 A -- primary within-issue home premium
# =============================================================================
cat("FIG1 A  home premium\n")
e1 <- rd("e01_home_premium_primary.csv") %>% mutate(j = yj(jurisdiction))
a_ok <- filter(e1, estimable); a_no <- filter(e1, !estimable)
# CN carries the result and is drawn slightly heavier. India is NOT promoted: it
# is a single-model jurisdiction that reverses sign between estimands, and the
# caption says so -- the graphic must not do the arguing.
a_ok <- a_ok %>% mutate(lead = jurisdiction == "CN",
                        sz = ifelse(lead, PT + 0.7, PT),
                        lwd = ifelse(lead, LW + 0.35, LW))

p_home <- ggplot(a_ok, aes(y = j)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  geom_errorbar(aes(xmin = conf_low, xmax = conf_high,
                    colour = jurisdiction, linewidth = I(lwd)),
                orientation = "y", width = 0) +
  geom_point(aes(x = estimate, fill = jurisdiction, size = I(sz)),
             shape = 21, colour = "white", stroke = 0.5) +
  geom_text(aes(x = conf_high, label = sprintf("%+.1f", 100 * estimate),
                colour = jurisdiction, fontface = I(ifelse(lead, "bold", "plain"))),
            hjust = -0.32, size = TXT) +
  geom_point(data = a_no, aes(x = 0), shape = 22, size = PT_SM,
             colour = INK_FAINT, fill = "white", stroke = 0.45) +
  geom_text(data = a_no, aes(x = 0, label = "0 observed refusals; not estimable"),
            hjust = -0.10, size = TXT - 0.35, colour = INK_FAINT) +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(-0.032, 0.265), breaks = seq(0, 0.20, 0.05),
                     expand = c(0, 0)) +
  scale_y_discrete(drop = FALSE, expand = expansion(add = c(0.6, 0.6))) +
  labs(x = "Within-issue home premium (pp)", y = NULL) +
  theme_fig() +
  theme(axis.text.y = element_text(colour = INK, size = rel(1.05)))

# =============================================================================
# FIG1 B -- primary vs descriptive estimand (paired dumbbell)
# =============================================================================
# The point is NOT two estimates of one parameter. It is that the inferential
# conclusion depends on which comparison identifies the effect. Labels sit ON the
# connector, not in a detached right-hand gutter.
cat("FIG1 B  estimand comparison\n")
e4 <- rd("e04_estimand_comparison.csv")
wide <- e4 %>% select(jurisdiction, estimand, estimate) %>%
  pivot_wider(names_from = estimand, values_from = estimate) %>%
  rename(primary = `Within-issue (primary)`,
         descriptive = `Within-jurisdiction (descriptive)`) %>%
  left_join(e4 %>% filter(estimand == "Within-issue (primary)") %>%
              select(jurisdiction, conf_low, conf_high), by = "jurisdiction") %>%
  mutate(j = yj(jurisdiction), gap = abs(primary - descriptive),
         mid = (primary + descriptive) / 2)
# EU appears as a row here too, so the reader sees all five jurisdictions and the
# reason one of them has no estimate -- rather than silently dropping it.
cmp_zero <- e1 %>% filter(!estimable) %>% transmute(jurisdiction, j = yj(jurisdiction))

p_cmp <- ggplot(wide, aes(y = j)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  # Stop the segment SHORT of the primary estimate. Drawn all the way to it, the
  # filled point sits exactly on top of the arrowhead and hides it -- so the axis
  # title promised an arrow that was not visible anywhere in the panel.
  geom_segment(aes(x = descriptive,
                   xend = primary - sign(primary - descriptive) * 0.0085,
                   yend = j, colour = jurisdiction),
               linewidth = LW, lineend = "butt", alpha = 0.65,
               arrow = arrow(length = unit(3.4, "pt"), type = "closed")) +
  geom_errorbar(aes(xmin = conf_low, xmax = conf_high, colour = jurisdiction),
                orientation = "y", width = 0, linewidth = LW_CI) +
  geom_point(aes(x = descriptive, colour = jurisdiction), shape = 1,
             size = PT_SM, stroke = 0.8) +
  geom_point(aes(x = primary, fill = jurisdiction), shape = 21, size = PT,
             colour = "white", stroke = 0.5) +
  # Transition label directly above its own connector.
  # The label must read in the SAME left-to-right order as the points it sits
  # above. Printing "descriptive first" unconditionally put the numbers the wrong
  # way round whenever the primary estimate is to the LEFT of the descriptive one
  # (MENA +2.9 -> +0.2, US +1.7 -> -0.7), which is most of the panel.
  geom_text(data = filter(wide, gap > 0.012) %>%
              mutate(lab = ifelse(primary < descriptive,
                                  sprintf("● %+.1f    ○ %+.1f",
                                          100 * primary, 100 * descriptive),
                                  sprintf("○ %+.1f    ● %+.1f",
                                          100 * descriptive, 100 * primary))),
            aes(x = mid, label = lab, colour = jurisdiction),
            vjust = -1.35, size = TXT - 0.45) +
  geom_point(data = cmp_zero, aes(x = 0), shape = 22, size = PT_SM,
             colour = INK_FAINT, fill = "white", stroke = 0.45) +
  geom_text(data = cmp_zero, aes(x = 0, label = "0 refusals; not estimable"),
            hjust = -0.10, size = TXT - 0.45, colour = INK_FAINT) +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(-0.055, 0.245), breaks = seq(0, 0.20, 0.10),
                     expand = c(0, 0)) +
  scale_y_discrete(drop = FALSE, expand = expansion(add = c(0.6, 0.95))) +
  labs(x = "Home effect (pp):  ○ descriptive,  ● primary (arrow points to primary)",
       y = NULL) +
  theme_fig()

# =============================================================================
# FIG1 C -- raw jurisdiction x issue-region refusal rates
# =============================================================================
# Printed value == the quantity the fill encodes, on ONE sequential scale.
# Home cells carry a small corner dot, not a heavy box: outlining all five would
# imply the whole diagonal is exceptional, which is the opposite of the finding.
cat("FIG1 C  raw rate matrix\n")
e8 <- rd("e08_region_cells.csv") %>%
  mutate(juris = factor(juris, levels = JORDER),
         region = factor(region, levels = REGION_LEVELS),
         structural_zero = !estimable)
# EU never refuses. Showing five ordinary "0.0" cells invites reading them as
# five small estimates, so the column is rendered as structurally empty instead.
e8_fill <- e8 %>% mutate(fill_rate = ifelse(structural_zero, NA_real_, rate))
corner <- e8 %>% filter(home, !structural_zero)

p_rates <- ggplot(e8_fill, aes(x = juris, y = fct_rev(region))) +
  geom_tile(aes(fill = fill_rate), colour = "white", linewidth = 1.2) +
  geom_tile(data = filter(e8, juris == "CN", region == "China"),
            fill = NA, colour = PAL_JURIS[["CN"]], linewidth = 0.8) +
  # Home marker: a small dot in the jurisdiction's own colour, top-left of cell.
  # White halo under a coloured dot: a bare coloured dot vanished against the
  # dark China x CN cell, which is the one cell the marker most needs to survive.
  # Two plain layers on the existing colour scale -- no second fill scale needed.
  geom_point(data = corner, position = position_nudge(x = -0.385, y = 0.335),
             size = 1.9, colour = "white", show.legend = FALSE) +
  geom_point(data = corner, aes(colour = as.character(juris)),
             position = position_nudge(x = -0.385, y = 0.335),
             size = 1.15, show.legend = FALSE) +
  geom_text(data = filter(e8, !structural_zero),
            aes(label = sprintf("%.1f", 100 * rate), colour = rate > 0.085),
            size = 2.2) +
  geom_text(data = filter(e8, structural_zero),
            aes(label = "0"), colour = INK_FAINT, size = 2.2, fontface = "italic") +
  scale_fill_gradientn(colours = SEQ_MATRIX, limits = c(0, 0.20),
                       oob = scales::squish, na.value = CELL_EMPTY,
                       labels = label_percent(accuracy = 1, suffix = ""),
                       name = NULL) +
  scale_colour_manual(values = c(PAL_JURIS, `TRUE` = "white", `FALSE` = INK),
                      guide = "none") +
  scale_x_discrete(position = "top", expand = c(0, 0)) +
  # "Arab" is the stored region level; every figure displays it as MENA so the
  # row reads against the MENA jurisdiction column it is the home region of.
  scale_y_discrete(expand = c(0, 0), labels = region_label) +
  labs(x = NULL, y = NULL,
       caption = "● home region   │   EU: 0 refusals observed in 2,496 responses (structural zero)") +
  theme_nature(grid = "none") +
  theme(plot.margin = margin(4, 7, 3, 4),
        axis.line.x = element_blank(), axis.ticks = element_blank(),
        axis.text.x.top = element_text(colour = INK, size = rel(1.0),
                                       margin = margin(b = 2)),
        axis.text.y = element_text(colour = INK, size = rel(1.0)),
        plot.caption = element_text(hjust = 0, size = rel(0.78), colour = INK_FAINT,
                                    margin = margin(t = 3)),
        legend.position = "right", legend.key.width = unit(5, "pt"),
        legend.key.height = unit(20, "pt"),
        legend.text = element_text(size = rel(0.8)),
        plot.tag = element_text(family = FONT_SANS, face = "bold", size = 8.5,
                                colour = INK),
        plot.tag.position = c(0, 1))

# Compact variant of the same matrix for the half-width slot in FIG1: the
# colourbar and the caption are dropped (every value is printed, so the bar is
# redundant at this size) and the type is a shade smaller. Same data, same
# scale, same encoding -- only the furniture changes. P4_region_structure_raw
# keeps the full-width version with its legend.
p_rates_c <- p_rates +
  labs(caption = NULL) +
  guides(fill = "none") +
  theme(axis.text.x.top = element_text(size = rel(0.92)),
        axis.text.y = element_text(size = rel(0.92)),
        plot.margin = margin(4, 4, 3, 2))

cat("FIG1 assembling\n")
# Two rows: the locator key, then the estimand comparison beside the raw matrix.
# The primary home-premium interval plot is no longer a FIG1 panel -- panel B
# already shows the primary estimate WITH its interval, so a separate panel of
# the same numbers was redundant. It remains standalone as P2.
fig1 <- (p_locator_strip + labs(tag = "A")) /
        ((p_cmp + labs(tag = "B")) | (p_rates_c + labs(tag = "C"))) +
  plot_layout(heights = c(0.58, 1.30))
save_fig(fig1, file.path(FIGS, "FIG1_home_region_main.png"), width = W2, height = 4.05)

# =============================================================================
# FIG2 -- prompt framing: levels AND the shift, with its interval
# =============================================================================
# The previous version printed the signed shift as bare text with no interval,
# so grok-4.3 (+0.5 [-0.3, 1.6]) and qwen3-max (+0.4 [-1.0, 2.0]) -- both null --
# were drawn exactly like sarvam-30b (+6.8 [2.4, 11.3]). The shift IS the
# estimand, so it now gets its own panel with a zero line. The dumbbell is kept
# alongside because absolute level is substantive (allam-7b refuses at ~15%
# under either framing).
cat("FIG2 A  model tier\n")
e11 <- rd("e11_model_tier.csv")
# Signed shift, largest increase at TOP. A discrete y-axis draws level 1 at the
# bottom, so the estimable models are sorted ascending and the structural zero is
# placed first -- which puts it last visually.
ord11 <- c(e11 %>% filter(!estimable) %>% pull(model),
           e11 %>% filter(estimable) %>% arrange(shift) %>% pull(model))
e11 <- e11 %>% mutate(model = factor(model, levels = ord11))
ok11 <- filter(e11, estimable); no11 <- filter(e11, !estimable)
long11 <- ok11 %>% select(model, juris, regular, boundary) %>%
  pivot_longer(c(regular, boundary), names_to = "tier", values_to = "rate") %>%
  mutate(tier = factor(tier, levels = c("regular", "boundary")))

p_modtier <- ggplot(e11, aes(y = model)) +
  geom_segment(data = ok11, aes(x = regular, xend = boundary, yend = model,
                                colour = juris), linewidth = LW, lineend = "round") +
  geom_point(data = long11, aes(x = rate, shape = tier, fill = juris),
             size = PT_SM, colour = "white", stroke = 0.4) +
  geom_point(data = no11, aes(x = 0), shape = 22, size = PT_SM - 0.2,
             colour = INK_FAINT, fill = "white", stroke = 0.4) +
  geom_text(data = no11, aes(x = 0.012, label = "not estimable"), hjust = 0,
            size = TXT - 0.45, colour = INK_FAINT) +
  scale_shape_manual(values = SHAPE_TIER, name = NULL) +
  tier_guide() +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(-0.004, 0.175), breaks = seq(0, 0.15, 0.05),
                     expand = c(0, 0)) +
  scale_y_discrete(limits = ord11, drop = FALSE,
                   expand = expansion(add = c(0.6, 0.7))) +
  labs(x = "Refusal rate (%)", y = NULL) +
  theme_fig() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0))

# drop = FALSE below is load-bearing. This panel plots only the estimable models,
# but it is laid out beside a panel that lists ALL of them; without keeping the
# unused level the two panels have different row counts and every shift lines up
# against the wrong model (Mistral's empty row absorbed Sarvam's estimate).
p_modshift <- ggplot(ok11, aes(y = model)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  geom_errorbar(aes(xmin = conf_low, xmax = conf_high, colour = juris),
                orientation = "y", width = 0, linewidth = LW_CI) +
  geom_point(aes(x = shift, fill = juris), shape = 21, size = PT_SM + 0.15,
             colour = "white", stroke = 0.4) +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(-0.075, 0.13), breaks = seq(-0.05, 0.10, 0.05),
                     expand = c(0, 0)) +
  scale_y_discrete(limits = ord11, drop = FALSE,
                   expand = expansion(add = c(0.6, 0.7))) +
  labs(x = "Boundary − regular (pp)", y = NULL) +
  theme_fig() +
  theme(axis.text.y = element_blank(), plot.margin = margin(4, 7, 3, 1))

cat("FIG2 B  domain tier\n")
e12 <- rd("e12_domain_tier.csv") %>%
  mutate(domain = pretty_dom(domain), domain = fct_reorder(domain, shift))
ord12 <- levels(e12$domain)
long12 <- e12 %>% select(domain, regular, boundary) %>%
  pivot_longer(c(regular, boundary), names_to = "tier", values_to = "rate") %>%
  mutate(tier = factor(tier, levels = c("regular", "boundary")))

p_domtier <- ggplot(e12, aes(y = domain)) +
  geom_segment(aes(x = regular, xend = boundary, yend = domain),
               colour = lighten(INK_SOFT, 0.55), linewidth = LW, lineend = "round") +
  geom_point(data = long12, aes(x = rate, shape = tier), size = PT_SM,
             fill = INK_SOFT, colour = "white", stroke = 0.4) +
  scale_shape_manual(values = SHAPE_TIER, name = NULL) +
  tier_guide() +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(0, 0.135), breaks = seq(0, 0.12, 0.04),
                     expand = c(0, 0)) +
  scale_y_discrete(limits = ord12, drop = FALSE,
                   expand = expansion(add = c(0.6, 0.7))) +
  labs(x = "Refusal rate (%)", y = NULL) +
  theme_fig() +
  theme(legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0))

p_domshift <- ggplot(e12, aes(y = domain)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  geom_errorbar(aes(xmin = conf_low, xmax = conf_high), orientation = "y",
                width = 0, linewidth = LW_CI, colour = INK_SOFT) +
  geom_point(aes(x = shift), shape = 21, size = PT_SM + 0.15,
             fill = INK_SOFT, colour = "white", stroke = 0.4) +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(-0.09, 0.105), breaks = seq(-0.05, 0.05, 0.05),
                     expand = c(0, 0)) +
  scale_y_discrete(limits = ord12, drop = FALSE,
                   expand = expansion(add = c(0.6, 0.7))) +
  labs(x = "Boundary − regular (pp)", y = NULL) +
  theme_fig() +
  theme(axis.text.y = element_blank(), plot.margin = margin(4, 7, 3, 1))

cat("FIG2 assembling\n")
# guides = "collect" is not cosmetic here: a top legend on the left panel only
# makes its panel body shorter than the right one, so the rows stop corresponding.
fig2 <- ((p_modtier + labs(tag = "A")) | p_modshift) /
        ((p_domtier + labs(tag = "B")) | p_domshift) +
  plot_layout(widths = c(1, 0.62), heights = c(1.12, 1), guides = "collect") +
  # `& theme(...)` does not dispatch under ggplot2 4.0 (S7 generic); the
  # collected guide is positioned through plot_annotation instead.
  plot_annotation(theme = theme(legend.position = "top",
                                legend.justification = "left",
                                legend.margin = margin(0, 0, 2, 0)))
save_fig(fig2, file.path(FIGS, "FIG2_model_domain_main.png"), width = W2, height = 5.05)

# =============================================================================
# FIG3 -- refusal-reason composition
# =============================================================================
# FIVE categories. "other" (judge code G) is 15.7% of refusals and is NOT the
# same thing as "none given": its free text mixes degenerate output, explicit
# task refusals and epistemic statements. Keeping them apart is the honest
# reading and stops a measurement failure mode hiding inside a grey bar.
#
# Legend order is set to the DRAWN order. geom_col stacks in reverse factor
# order, so with levels (neutrality ... none given) the bar reads left-to-right
# as none given -> other -> epistemic -> harm -> neutrality, putting the modal
# reason at the right edge. audit_figures.R checks the two orders agree.
cat("FIG3  refusal reasons\n")
e13 <- rd("e13_refusal_reasons.csv") %>%
  mutate(reason = factor(reason, levels = names(PAL_REASON)))
ord13 <- e13 %>% filter(reason == "neutrality") %>% arrange(share) %>% pull(model)
den <- e13 %>% distinct(model, juris, n_refusals) %>%
  mutate(lab = sprintf("%s  ·  n=%d", model, n_refusals))
lab_map <- setNames(den$lab, den$model)
e13 <- e13 %>% mutate(model = factor(lab_map[model], levels = lab_map[ord13]))
den  <- den  %>% mutate(model = factor(lab, levels = lab_map[ord13]))
# One labelling rule: percentages only, at >= 15%, no category names in bars.
e13 <- e13 %>% mutate(seg_lab = ifelse(share >= 0.15, sprintf("%.0f", 100 * share), ""))
DRAWN_ORDER <- rev(names(PAL_REASON))

p_reasons <- ggplot(e13, aes(x = share, y = model, fill = reason)) +
  geom_col(width = 0.68) +
  # group = reason is LOAD-BEARING. Mapping `colour` here introduces a second
  # grouping variable, and position_stack then stacks the labels in that new
  # group order while geom_col stacks in fill order -- so every label lands on
  # the wrong segment. Pinning the group to the fill factor keeps the two layers
  # in lockstep. audit_figures.R re-checks this with the real aesthetics.
  geom_text(aes(label = seg_lab, colour = reason %in% c("neutrality", "harm"),
                group = reason),
            position = position_stack(vjust = 0.5),
            size = TXT - 0.45, show.legend = FALSE) +
  geom_point(data = den, mapping = aes(x = -0.028, y = model, colour = juris),
             inherit.aes = FALSE, size = 1.15) +
  scale_fill_manual(values = PAL_REASON, name = NULL, breaks = DRAWN_ORDER) +
  scale_colour_manual(values = c(PAL_JURIS, `TRUE` = "white", `FALSE` = INK),
                      guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(-0.045, 1.005), breaks = c(0, 0.5, 1),
                     expand = c(0, 0)) +
  guides(fill = guide_legend(nrow = 1)) +
  labs(x = "Share of that model's refusals (%)", y = NULL) +
  theme_nature(grid = "none") +
  theme(plot.margin = margin(4, 8, 3, 4),
        legend.position = "top", legend.justification = "left",
        legend.key.height = unit(7, "pt"), legend.key.width = unit(11, "pt"),
        legend.text = element_text(size = rel(0.88)),
        legend.margin = margin(0, 0, 2, 0),
        axis.text.y = element_text(colour = INK, size = rel(1.0)))
save_fig(p_reasons, file.path(FIGS, "FIG3_refusal_reasons_main.png"),
         width = W2, height = 2.75)

# =============================================================================
# FIG4 -- slant: ideology and moral foundations among ENGAGED responses
# =============================================================================
if (has("e16b_ideology_summary.csv")) {
  cat("FIG4  slant\n")
  e16b <- rd("e16b_ideology_summary.csv")
  e17  <- rd("e17_moral_prevalence.csv")

  # --- A: directional mean WITH the neutral share ------------------------
  # The previous diverging-bar form removed the neutral category from the bars
  # and printed it marginally, so bar length represented only the non-neutral
  # remainder on a +-13% axis -- which overstates ideological content to any
  # reader who does not parse the side column. The mean is the directional
  # estimand; it is plotted with its issue-clustered interval, and the neutral
  # share travels WITH it, adjacent to the denominator it qualifies.
  ORD_D <- c("Economic", "Social", "Authority", "Populism")
  e16b <- e16b %>% mutate(dimension = factor(dimension, levels = ORD_D),
                          j = yj(jurisdiction))
  LIMI <- 0.225
  # Annotations are anchored to REAL factor levels and nudged, never to numeric
  # y positions: a numeric y trained against a discrete scale errors in
  # ggplot2 4.0 (scales::train_continuous on a discrete range).
  TOPROW <- factor(JORDER[1], levels = rev(JORDER))            # CN, drawn top
  BOTROW <- factor(JORDER[length(JORDER)], levels = rev(JORDER))  # EU, drawn bottom
  poles <- tibble(
    dimension = factor(rep(ORD_D, each = 2), levels = ORD_D),
    label = c("left", "right", "progressive", "traditional",
              "authoritarian", "libertarian", "populist", "elitist"),
    x = rep(c(-LIMI, LIMI), 4) * 0.99, hj = rep(c(0, 1), 4),
    j = rep(BOTROW, 8))
  hdr <- tibble(dimension = factor(ORD_D, levels = ORD_D),
                j = rep(TOPROW, 4), lab = "% at 0")

  p_ideo <- ggplot(e16b, aes(y = j)) +
    geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
    geom_errorbar(aes(xmin = conf_low, xmax = conf_high, colour = jurisdiction),
                  orientation = "y", width = 0, linewidth = LW_CI) +
    geom_point(aes(x = mean, fill = jurisdiction), shape = 21, size = PT_SM + 0.15,
               colour = "white", stroke = 0.4) +
    geom_text(aes(x = LIMI * 1.10, label = sprintf("%.0f", 100 * neutral_share)),
              hjust = 0, size = 2.0, family = FONT_SANS, colour = INK_SOFT) +
    geom_text(data = hdr, inherit.aes = FALSE,
              aes(x = LIMI * 1.10, y = j, label = lab), vjust = -1.9,
              hjust = 0, size = 2.0, family = FONT_SANS, colour = INK_SOFT) +
    geom_text(data = poles, inherit.aes = FALSE,
              aes(x = x, y = j, label = label, hjust = hj), vjust = 2.6,
              size = 2.0, family = FONT_SANS, colour = INK_SOFT,
              fontface = "italic") +
    facet_wrap(~ dimension, nrow = 1) +
    scale_colour_manual(values = PAL_JURIS, guide = "none") +
    scale_fill_manual(values = PAL_JURIS, guide = "none") +
    scale_y_discrete(drop = FALSE, expand = expansion(add = c(1.35, 1.25))) +
    scale_x_continuous(breaks = c(-0.2, 0, 0.2), expand = c(0, 0)) +
    coord_cartesian(xlim = c(-LIMI, LIMI), clip = "off") +
    labs(x = "Mean ideology code (−2 to +2) among engaged responses", y = NULL) +
    theme_nature(grid = "none") +
    theme(plot.margin = margin(4, 26, 3, 4),
          panel.spacing.x = unit(26, "pt"),
          axis.text.y = element_text(colour = INK),
          axis.title.x = element_text(size = rel(0.85)),
          strip.text = element_text(colour = INK, face = "bold",
                                    size = rel(0.95), hjust = 0),
          plot.tag = element_text(family = FONT_SANS, face = "bold",
                                  size = 8.5, colour = INK),
          plot.tag.position = c(0, 1))

  # --- B: moral foundations, with a pooled reference ---------------------
  # The dominant pattern is BETWEEN foundations (fairness ~61% vs sanctity ~3%),
  # not between jurisdictions. A pooled grey estimate anchors that ranking so the
  # reader does not mistake the small jurisdiction spread for the main signal.
  ord_f <- e17 %>% group_by(foundation) %>% summarise(m = mean(estimate)) %>%
    arrange(m) %>% pull(foundation)
  e17 <- e17 %>% mutate(foundation = factor(foundation, levels = ord_f),
                        jurisdiction = factor(jurisdiction, levels = JORDER))
  pooled <- if (has("e17b_moral_pooled.csv"))
    rd("e17b_moral_pooled.csv") %>%
      mutate(foundation = factor(foundation, levels = ord_f)) else NULL

  p_mft <- ggplot(e17, aes(x = estimate, y = foundation))
  if (!is.null(pooled))
    p_mft <- p_mft +
      # Drawn as a zero-width errorbar on the DISCRETE y, not a geom_segment with
      # numeric y +- 0.42: numeric y against a discrete scale errors in
      # ggplot2 4.0. This gives the same vertical rule spanning the row.
      geom_errorbar(data = pooled, inherit.aes = FALSE,
                    aes(y = foundation, xmin = pooled, xmax = pooled),
                    orientation = "y", width = 0.78,
                    colour = INK_FAINT, linewidth = 0.7)
  p_mft <- p_mft +
    geom_errorbar(aes(xmin = conf_low, xmax = conf_high, colour = jurisdiction),
                  orientation = "y", width = 0, linewidth = 0.45,
                  position = position_dodge(width = 0.62)) +
    geom_point(aes(fill = jurisdiction), shape = 21, size = PT_SM + 0.2,
               colour = "white", stroke = 0.4,
               position = position_dodge(width = 0.62)) +
    scale_colour_manual(values = PAL_JURIS, guide = "none") +
    scale_fill_manual(values = PAL_JURIS, name = NULL) +
    guides(fill = guide_legend(nrow = 1, override.aes = list(size = PT_SM + 0.5))) +
    scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                       limits = c(0, 0.78), breaks = seq(0, 0.6, 0.2),
                       expand = c(0, 0)) +
    labs(x = "Share of engaged responses invoking the foundation (%)   │   grey rule = pooled",
         y = NULL) +
    theme_fig() +
    theme(legend.position = "top", legend.justification = "left",
          legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
          legend.text = element_text(size = rel(0.85)),
          axis.title.x = element_text(size = rel(0.85)),
          legend.margin = margin(0, 0, 1, 0))

  fig4 <- (p_ideo + labs(tag = "A")) / (p_mft + labs(tag = "B")) +
    plot_layout(heights = c(1, 1.12))
  save_fig(fig4, file.path(FIGS, "FIG4_slant_main.png"), width = W2, height = 4.3)

  # --- supplementary: the full five-category ideology distribution -------
  e15 <- rd("e15_ideology_distribution.csv") %>%
    mutate(dimension = factor(dimension, levels = ORD_D),
           juris = factor(juris, levels = JORDER),
           code_f = factor(code, levels = c(-2, -1, 0, 1, 2),
                           labels = c("−2", "−1", "0", "+1", "+2")))
  PAL_CODE <- setNames(PAL_DIVERGE, levels(e15$code_f))
  p_ideo_dist <- ggplot(e15, aes(x = share, y = fct_rev(juris), fill = code_f)) +
    geom_col(width = 0.68) +
    facet_wrap(~ dimension, nrow = 1) +
    scale_fill_manual(values = PAL_CODE, name = NULL) +
    guides(fill = guide_legend(nrow = 1, keywidth = unit(9, "pt"),
                               keyheight = unit(6, "pt"))) +
    scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                       breaks = c(0, 0.5, 1), expand = c(0, 0)) +
    labs(x = "Share of engaged responses (%), full distribution", y = NULL) +
    theme_nature(grid = "none") +
    theme(plot.margin = margin(4, 8, 3, 4),
          panel.spacing.x = unit(9, "pt"),
          legend.position = "top", legend.justification = "left",
          legend.text = element_text(size = rel(0.85)),
          legend.margin = margin(0, 0, 1, 0),
          axis.text.y = element_text(colour = INK),
          strip.text = element_text(colour = INK, face = "bold",
                                    size = rel(0.95), hjust = 0))

  # --- supplementary: moral foundations by prompt language ---------------
  p_mlang <- NULL
  if (has("e20_moral_by_language.csv")) {
    e20 <- rd("e20_moral_by_language.csv") %>%
      mutate(foundation = factor(foundation, levels = ord_f),
             lang = factor(prompt_language, levels = c("en", "zh", "ar"),
                           labels = c("English", "Chinese", "Arabic")))
    p_mlang <- ggplot(e20, aes(x = estimate, y = foundation, shape = lang)) +
      geom_errorbar(aes(xmin = conf_low, xmax = conf_high), orientation = "y",
                    width = 0, linewidth = 0.4, colour = INK_FAINT,
                    position = position_dodge(width = 0.6)) +
      # Shape 21 filled white is indistinguishable from hollow shape 1, so fill
      # must vary with shape or English and Chinese collapse to one glyph.
      geom_point(aes(fill = lang), size = PT_SM, colour = INK_SOFT, stroke = 0.5,
                 position = position_dodge(width = 0.6)) +
      scale_shape_manual(values = unname(SHAPE_LANG[c("en", "zh", "ar")]),
                         name = NULL) +
      scale_fill_manual(values = c(English = INK_SOFT, Chinese = "white",
                                   Arabic = INK_SOFT), name = NULL) +
      guides(shape = guide_legend(override.aes = list(size = PT_SM + 0.4))) +
      scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                         limits = c(0, 0.7), breaks = seq(0, 0.6, 0.2),
                         expand = c(0, 0)) +
      labs(x = "Share of engaged responses invoking the foundation (%)", y = NULL) +
      theme_fig() +
      theme(legend.position = "top", legend.justification = "left",
            legend.key.width = unit(8, "pt"),
            legend.text = element_text(size = rel(0.85)),
            legend.margin = margin(0, 0, 1, 0))
  }
} else {
  cat("SKIP FIG4: slant estimates absent\n")
  p_ideo <- p_mft <- p_ideo_dist <- p_mlang <- NULL
}

# =============================================================================
# FIG5 -- prompt-language effects  (all models, all languages)
# =============================================================================
# Previously the language analysis covered the two CHINESE models only, which
# left the largest effects in the study unreported: allam-7b refuses 53 pp more
# in Russian, and falcon3-10b 24 pp more in Arabic -- its own home language.
# Every model x language cell is shown here, null ones included, because a null
# for one model is evidence rather than a reason to omit a row.
p_langmodel <- p_langhome <- NULL
if (has("e29_language_by_model.csv")) {
  cat("FIG5  language effects\n")
  LANG_ORD <- c("Chinese", "Arabic", "Russian", "Hindi")
  e29 <- rd("e29_language_by_model.csv") %>%
    filter(language != "en") %>%
    mutate(language_label = factor(language_label, levels = LANG_ORD),
           jurisdiction = factor(jurisdiction, levels = JORDER))
  # Order models by jurisdiction, then by their largest absolute effect, so
  # related models sit together and the outliers are immediately visible.
  ord_m <- e29 %>% group_by(model, jurisdiction) %>%
    summarise(mx = max(abs(estimate), na.rm = TRUE), .groups = "drop") %>%
    mutate(mx = ifelse(is.finite(mx), mx, 0)) %>%
    arrange(desc(jurisdiction), mx) %>% pull(model)
  e29 <- e29 %>% mutate(model = factor(model, levels = ord_m))
  drawn <- e29 %>% filter(estimable, !is.na(estimate))
  # A model with zero refusals in every language still gets a row: omitting it
  # would silently drop a model from a figure whose whole point is to show every
  # model x language cell, null ones included.
  zero29 <- e29 %>% filter(!not_generated, !estimable, is.na(estimate)) %>%
    distinct(model, language_label)
  # Cells that were never generated are BLANK with an explicit tick, not zero:
  # four models have no Hindi responses at all, and a zero there would be a lie.
  gaps <- e29 %>% filter(not_generated)

  p_langmodel <- ggplot(drawn, aes(y = model)) +
    geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
    geom_errorbar(aes(xmin = conf_low, xmax = conf_high, colour = jurisdiction),
                  orientation = "y", width = 0, linewidth = LW_CI) +
    geom_point(aes(x = estimate, fill = jurisdiction), shape = 21,
               size = PT_SM + 0.15, colour = "white", stroke = 0.4) +
    geom_text(data = gaps, aes(x = 0, y = model), label = "not generated",
              hjust = 0.5, vjust = 0.35, size = TXT - 0.75, colour = INK_FAINT,
              fontface = "italic", inherit.aes = FALSE) +
    geom_text(data = zero29, aes(x = 0, y = model), label = "0 refusals",
              hjust = 0.5, vjust = 0.35, size = TXT - 0.75, colour = INK_FAINT,
              fontface = "italic", inherit.aes = FALSE) +
    facet_wrap(~ language_label, nrow = 1) +
    scale_y_discrete(limits = ord_m, drop = FALSE) +
    scale_colour_manual(values = PAL_JURIS, name = NULL) +
    scale_fill_manual(values = PAL_JURIS, guide = "none") +
    guides(colour = guide_legend(nrow = 1, override.aes = list(size = PT_SM + 0.5))) +
    scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                       breaks = seq(-0.2, 0.6, 0.2), expand = expansion(mult = 0.06)) +
    labs(x = "Refusal difference vs English prompts (pp), same issue", y = NULL) +
    theme_fig() +
    theme(legend.position = "top", legend.justification = "left",
          legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
          legend.text = element_text(size = rel(0.85)),
          legend.margin = margin(0, 0, 1, 0),
          panel.spacing.x = unit(10, "pt"),
          strip.text = element_text(colour = INK, face = "bold",
                                    size = rel(0.95), hjust = 0))

  if (has("e31_home_premium_by_language.csv")) {
    e31 <- rd("e31_home_premium_by_language.csv") %>%
      mutate(jurisdiction = factor(jurisdiction, levels = JORDER),
             language_label = factor(language_label,
                                     levels = c("English", LANG_ORD)))
    ok31 <- filter(e31, estimable, !is.na(estimate))
    no31 <- e31 %>% filter(!estimable) %>% distinct(jurisdiction)
    p_langhome <- ggplot(ok31, aes(y = fct_rev(jurisdiction))) +
      geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
      geom_errorbar(aes(xmin = conf_low, xmax = conf_high, colour = jurisdiction),
                    orientation = "y", width = 0, linewidth = LW_CI,
                    position = position_dodge(width = 0.68)) +
      geom_point(aes(x = estimate, fill = jurisdiction, shape = language_label),
                 size = PT_SM + 0.15, colour = "white", stroke = 0.4,
                 position = position_dodge(width = 0.68)) +
      geom_text(data = no31, aes(x = 0, y = fct_rev(jurisdiction)),
                label = "0 refusals; not estimable", hjust = -0.04,
                size = TXT - 0.55, colour = INK_FAINT, inherit.aes = FALSE) +
      # limits pinned: the estimable layer has no EU row, so without this the
      # not-estimable layer appended EU and it rendered at the TOP of the panel
      # instead of last.
      scale_y_discrete(limits = rev(JORDER), drop = FALSE) +
      scale_colour_manual(values = PAL_JURIS, guide = "none") +
      scale_fill_manual(values = PAL_JURIS, guide = "none") +
      scale_shape_manual(values = c(21, 22, 23, 24, 25), name = NULL) +
      guides(shape = guide_legend(nrow = 1,
               override.aes = list(fill = INK_SOFT, colour = "white",
                                   size = PT_SM + 0.4))) +
      scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                         breaks = seq(0, 0.25, 0.05),
                         expand = expansion(mult = 0.06)) +
      labs(x = "Within-jurisdiction home-region premium (pp), by prompt language",
           y = NULL) +
      theme_fig() +
      theme(legend.position = "top", legend.justification = "left",
            legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
            legend.text = element_text(size = rel(0.85)),
            legend.margin = margin(0, 0, 1, 0))
    fig5 <- (p_langmodel + labs(tag = "A")) / (p_langhome + labs(tag = "B")) +
      plot_layout(heights = c(1.35, 1))
    save_fig(fig5, file.path(FIGS, "FIG5_language_main.png"),
             width = W2, height = 5.1)
  }
}

# =============================================================================
# Standalone panels
# =============================================================================
cat("standalone panels\n")

# P4 excess -- the analytically sharper view of the same cells. The baseline is a
# FITTED additive-in-logit model on cell counts, not arithmetic margins, so the
# label says so.
p_excess <- ggplot(e8, aes(x = juris, y = fct_rev(region))) +
  geom_tile(aes(fill = excess), colour = "white", linewidth = 1.2) +
  geom_tile(data = filter(e8, home), fill = NA, colour = INK, linewidth = 0.5) +
  geom_text(aes(label = ifelse(is.na(excess), "–",
                               sprintf("%+.1f", 100 * excess)),
                colour = abs(excess) > 0.05), size = 2.2) +
  scale_fill_gradientn(colours = PAL_DIVERGE, limits = c(-0.09, 0.09),
                       oob = scales::squish, na.value = CELL_EMPTY,
                       labels = label_percent(accuracy = 1, suffix = ""),
                       name = NULL) +
  scale_colour_manual(values = c(`TRUE` = "white", `FALSE` = INK), guide = "none") +
  scale_x_discrete(position = "top", expand = c(0, 0)) +
  scale_y_discrete(expand = c(0, 0), labels = region_label) +
  labs(x = NULL,
       y = "Observed − fitted additive (jurisdiction + region) baseline (pp)") +
  theme_nature(grid = "none") +
  theme(axis.line.x = element_blank(), axis.ticks = element_blank(),
        axis.title.y = element_text(size = rel(0.85), colour = INK_SOFT),
        axis.text.x.top = element_text(colour = INK, margin = margin(b = 2)),
        axis.text.y = element_text(colour = INK),
        legend.position = "right", legend.key.width = unit(5, "pt"),
        legend.key.height = unit(20, "pt"))

# P5 China x language. Rates, not just the premium: the claim is about two things
# at once -- similar gaps, different baselines.
e10 <- rd("e10_cn_home_by_language.csv")
e9  <- rd("e09_cn_language_cells.csv")
LL  <- c(en = "English", zh = "Chinese")
cells <- e9 %>%
  mutate(lang_f = factor(LL[lang], levels = c("English", "Chinese")),
         side   = factor(ifelse(home == 1, "home region", "elsewhere"),
                         levels = c("elsewhere", "home region")))
spans <- cells %>% select(model, lang_f, side, rate) %>%
  pivot_wider(names_from = side, values_from = rate) %>%
  rename(away = elsewhere, home = `home region`) %>%
  left_join(e10 %>% mutate(lang_f = factor(LL[lang], levels = c("English", "Chinese"))) %>%
              select(model, lang_f, premium = estimate), by = c("model", "lang_f"))

p_cnlang <- ggplot(cells, aes(y = fct_rev(lang_f))) +
  geom_segment(data = spans, aes(x = away, xend = home, yend = fct_rev(lang_f)),
               colour = lighten(PAL_JURIS[["CN"]], 0.72), linewidth = LW + 0.3,
               lineend = "round") +
  geom_errorbar(aes(xmin = conf_low, xmax = conf_high), orientation = "y",
                width = 0, linewidth = 0.4, colour = INK_FAINT) +
  geom_point(aes(x = rate, shape = side), size = PT, fill = PAL_JURIS[["CN"]],
             colour = PAL_JURIS[["CN"]], stroke = 0.7) +
  geom_text(data = spans, aes(x = (away + home) / 2, y = fct_rev(lang_f),
                              label = sprintf("+%.0f pp", 100 * premium)),
            inherit.aes = FALSE, vjust = -1.25, size = TXT - 0.4,
            colour = INK_SOFT) +
  facet_wrap(~ model, nrow = 1) +
  scale_shape_manual(values = c("elsewhere" = 1, "home region" = 21), name = NULL) +
  guides(shape = guide_legend(override.aes = list(size = PT, stroke = 0.7))) +
  # Terminal tick dropped: with two facets the right-hand 40 and the next
  # panel's 0 collided into "400" at the panel boundary.
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(0, 0.40), breaks = seq(0, 0.30, 0.10),
                     expand = c(0, 0)) +
  scale_y_discrete(expand = expansion(add = c(0.75, 1.05))) +
  labs(x = "Refusal rate (%)", y = NULL) +
  theme_fig() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0),
        panel.spacing.x = unit(14, "pt"),
        strip.text = element_text(colour = INK, size = rel(0.95), hjust = 0))

# P12 per-model home premium -- the panel that shows China's result is carried by
# BOTH Chinese models, and that the US null hides real heterogeneity.
p_bymodel <- NULL
if (has("e21_home_by_model.csv")) {
  e21 <- rd("e21_home_by_model.csv") %>%
    mutate(jurisdiction = factor(jurisdiction, levels = JORDER)) %>%
    arrange(jurisdiction, estimate) %>%
    mutate(model = factor(model, levels = model))
  p_bymodel <- ggplot(e21, aes(y = model)) +
    geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
    geom_errorbar(aes(xmin = conf_low, xmax = conf_high, colour = jurisdiction),
                  orientation = "y", width = 0, linewidth = LW_CI) +
    geom_point(aes(x = estimate, fill = jurisdiction), shape = 21, size = PT,
               colour = "white", stroke = 0.5) +
    # show.legend = FALSE: without it the text layer contributes an "a" glyph to
    # the colour key, which reads as a stray mark next to each jurisdiction.
    geom_text(aes(x = conf_high, label = sprintf("%+.1f", 100 * estimate),
                  colour = jurisdiction), hjust = -0.30, size = TXT - 0.3,
              show.legend = FALSE) +
    scale_colour_manual(values = PAL_JURIS, name = NULL) +
    scale_fill_manual(values = PAL_JURIS, name = NULL) +
    guides(colour = guide_legend(nrow = 1, override.aes = list(size = PT)),
           fill = "none") +
    scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                       limits = c(-0.06, 0.30), breaks = seq(0, 0.25, 0.05),
                       expand = c(0, 0)) +
    labs(x = "Within-issue home premium (pp), by subject model", y = NULL) +
    theme_fig() +
    theme(legend.position = "top", legend.justification = "left",
          legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
          legend.text = element_text(size = rel(0.85)),
          legend.margin = margin(0, 0, 1, 0))
}

panels <- list(
  P1_locator                = list(p_locator,   2.10),
  P2_home_interaction       = list(p_home,      1.90),
  P3_estimand_comparison    = list(p_cmp,       1.95),
  P4_region_structure_raw   = list(p_rates,     2.45),
  P4_region_structure_excess= list(p_excess,    2.35),
  P5_china_language         = list(p_cnlang,    1.95),
  P6_model_tier             = list(p_modtier,   2.55),
  P7_domain_tier            = list(p_domtier,   2.35),
  P8_refusal_reasons        = list(p_reasons,   2.75))
if (!is.null(p_bymodel))    panels$P12_home_by_model          <- list(p_bymodel,   2.55)
if (!is.null(p_langmodel))  panels$P13_language_by_model      <- list(p_langmodel, 3.00)
if (!is.null(p_langhome))   panels$P14_home_premium_by_language <- list(p_langhome, 2.20)
if (!is.null(p_ideo))       panels$P9_ideology_mean_neutral   <- list(p_ideo,      2.05)
if (!is.null(p_ideo_dist))  panels$P9_ideology_distribution   <- list(p_ideo_dist, 2.05)
if (!is.null(p_mft))        panels$P10_moral_foundations      <- list(p_mft,       2.35)
if (!is.null(p_mlang))      panels$P11_moral_by_language      <- list(p_mlang,     2.30)

for (nm in names(panels)) {
  s <- panels[[nm]]
  save_fig(s[[1]] + labs(tag = NULL), file.path(FIGS, paste0(nm, ".png")),
           width = W2, height = s[[2]])
}

cat("\n", strrep("=", 78), "\nFIGURES COMPLETE\n", strrep("=", 78), "\n", sep = "")
