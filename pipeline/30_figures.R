# =============================================================================
# Script 30: Figures  (PLOTTING ONLY -- reads saved estimates, never re-fits)
# =============================================================================
# Input : pipeline/estimates/*.csv   (written by 20_ and 21_)
# Output: pipeline/figures/*.png     PNG ONLY, 600 dpi, two-column width
#
# THREE main figures, one message each:
#   FIG1  distinctive home-region sensitivity is overwhelmingly a China result
#   FIG2  prompt framing moves refusal in opposite directions
#   FIG3  models differ in the reason they state for refusing
#
# No one-column variants, no _2col duplicates: one canonical file per figure,
# rendered directly at final size. The locator map and the China-language panel
# are STANDALONE only -- they were removed from FIG1, which was carrying five
# competing panels.
#
# ENCODING (see _theme.R; enforced by audit_figures.R)
#   jurisdiction -> colour            tier     -> circle / triangle
#   estimand     -> filled / hollow   reason   -> own 4-hue palette
#   uncertainty  -> thin interval in a lighter tint of its mark
# Estimand deliberately does NOT use triangles: triangle already means boundary.

suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork); library(sf)
})
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")

EST <- "pipeline/estimates"; FIGS <- "pipeline/figures"
rd <- function(f) read_csv(file.path(EST, f), show_col_types = FALSE)
cat(strrep("=", 78), "\nFIGURES\n", strrep("=", 78), "\n", sep = "")

# Substantive order: strongest result first, structural zero last.
JORDER <- c("CN", "MENA", "India", "US", "EU")
yj <- function(x) factor(x, levels = rev(JORDER))

# Shared geometry. One scale for everything so panels sit together.
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


# Tier legend that actually renders. SHAPE_TIER uses fillable glyphs (21/24), and
# `fill` is mapped to jurisdiction with guide = "none", so without an override
# the legend keys draw unfilled and invisible -- which is why the words "regular"
# and "boundary" appeared with no symbol beside them.
tier_guide <- function(fill = INK_SOFT)
  guides(shape = guide_legend(
    override.aes = list(fill = fill, colour = "white", size = PT_SM + 0.4,
                        stroke = 0.4), order = 1))

# Header for the right-hand signed-shift column, so the numbers are identified.
shift_header <- function(x, y, label = "shift (pp)")
  annotate("text", x = x, y = y, label = label, hjust = 1, size = TXT - 0.45,
           colour = INK_FAINT)

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
# Locator strip -- palette key for FIG1, and standalone as P1
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

make_locator <- function(labels = FALSE) {
  g <- ggplot() +
    geom_sf(data = filter(world, is.na(reg)), fill = MAP_LAND, colour = "white",
            linewidth = 0.05) +
    geom_sf(data = filter(world, !is.na(reg)), aes(fill = reg), colour = "white",
            linewidth = 0.05) +
    scale_fill_manual(values = PAL_REGION, guide = "none") +
    # Tight crop: drop the southern ocean and the empty Pacific so the strip is
    # mostly land. Antarctica and the far south carry no coloured region.
    coord_sf(xlim = c(-1.30e7, 1.45e7), ylim = c(-1.0e6, 6.3e6), expand = FALSE) +
    theme_void() +
    theme(plot.margin = margin(0, 2, 0, 2),
          plot.background = element_rect(fill = "white", colour = NA))
  if (labels) {
    lab <- tribble(~reg, ~lon, ~lat,
                   "US", -100, 41, "Europe", 14, 57, "Arab", 22, 26,
                   "India", 94, 9, "China", 104, 40) %>%
      st_as_sf(coords = c("lon", "lat"), crs = 4326) %>% st_transform("+proj=robin")
    lab <- bind_cols(st_drop_geometry(lab), as_tibble(st_coordinates(lab)))
    g <- g + geom_text(data = lab, aes(X, Y, label = reg, colour = reg),
                       size = 2.1, family = FONT_SANS, fontface = "bold") +
      scale_colour_manual(guide = "none",
                          values = c(China = "white", Arab = "white",
                                     India = unname(PAL_REGION[["India"]]),
                                     US = INK, Europe = INK))
  }
  g
}
# In FIG1 the map is a key beside labelled statistical panels, so it carries no
# labels of its own; standalone it does.
p_locator_strip <- make_locator(labels = TRUE)
p_locator       <- make_locator(labels = TRUE)

# =============================================================================
# FIG1 A -- primary within-issue home premium  (the dominant panel)
# =============================================================================
cat("A  home premium\n")
e1 <- rd("e01_home_premium_primary.csv") %>% mutate(j = yj(jurisdiction))
a_ok <- filter(e1, estimable); a_no <- filter(e1, !estimable)
# CN carries the result, so it is drawn slightly heavier. Everything else is
# quieter -- emphasis by weight, not by a second colour scheme.
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
  # Structural zero: a short dash and plain words, never a point at zero.
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
  labs(x = "Home premium (percentage points)", y = NULL) +
  theme_fig() +
  theme(axis.text.y = element_text(colour = INK, size = rel(1.05)))

# =============================================================================
# FIG1 B -- primary vs descriptive estimand, one row per jurisdiction
# =============================================================================
cat("B  estimand comparison\n")
e4 <- rd("e04_estimand_comparison.csv")
wide <- e4 %>%
  select(jurisdiction, estimand, estimate) %>%
  pivot_wider(names_from = estimand, values_from = estimate) %>%
  rename(primary = `Within-issue (primary)`,
         descriptive = `Within-jurisdiction (descriptive)`) %>%
  left_join(e4 %>% filter(estimand == "Within-issue (primary)") %>%
              select(jurisdiction, conf_low, conf_high), by = "jurisdiction") %>%
  mutate(j = yj(jurisdiction), gap = abs(primary - descriptive))

p_cmp <- ggplot(wide, aes(y = j)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.45) +
  geom_segment(aes(x = descriptive, xend = primary, yend = j), colour = RULE,
               linewidth = LW, lineend = "round") +
  # Interval on the PRIMARY estimate only: showing both would congest the row
  # and the descriptive contrast is not the inferential target.
  geom_errorbar(aes(xmin = conf_low, xmax = conf_high, colour = jurisdiction),
                orientation = "y", width = 0, linewidth = LW_CI) +
  geom_point(aes(x = descriptive, colour = jurisdiction), shape = 1,
             size = PT_SM, stroke = 0.8) +
  geom_point(aes(x = primary, fill = jurisdiction), shape = 21, size = PT,
             colour = "white", stroke = 0.5) +
  # Label only where the two estimands materially disagree.
  # Right-aligned in a reserved gutter, so a label can never overprint its own
  # interval the way it did when anchored to the larger of the two estimates.
  geom_text(data = filter(wide, gap > 0.02),
            aes(x = 0.262, label = sprintf("%+.1f to %+.1f",
                                           100 * descriptive, 100 * primary)),
            hjust = 1, size = TXT - 0.4, colour = INK_SOFT) +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(-0.045, 0.265), breaks = seq(0, 0.20, 0.10),
                     expand = c(0, 0)) +
  labs(x = "Home effect (pp): descriptive ○ → primary ●", y = NULL) +
  theme_fig()

# =============================================================================
# FIG1 C -- raw jurisdiction x issue-region refusal rates
# =============================================================================
# Sequential scale, and the printed number is the SAME quantity the fill encodes.
# The previous version put raw rates over a residual colour scale, which cannot
# be decoded from the graphic. The residual matrix survives as P4.
cat("C  raw rate matrix\n")
e8 <- rd("e08_region_cells.csv") %>%
  mutate(juris = factor(juris, levels = JORDER),
         region = factor(region, levels = REGION_LEVELS))
p_rates <- ggplot(e8, aes(x = juris, y = fct_rev(region))) +
  geom_tile(aes(fill = rate), colour = "white", linewidth = 1.2) +
  # Home cells get a small jurisdiction dot, not a heavy box: an outline on
  # every home cell implies all five are exceptional, which is the opposite of
  # the finding.
  geom_tile(data = filter(e8, home), fill = NA, colour = INK_FAINT,
            linewidth = 0.45) +
  # One thin outline, on the single cell the figure is about.
  geom_tile(data = filter(e8, juris == "CN", region == "China"),
            fill = NA, colour = PAL_JURIS[["CN"]], linewidth = 0.75) +
  geom_text(aes(label = sprintf("%.1f", 100 * rate), colour = rate > 0.085),
            size = 2.2) +
  scale_fill_gradientn(colours = c("#FAFBFB", "#C9D3DA", "#7F929F", "#3E5568"),
                       limits = c(0, 0.20), oob = scales::squish,
                       labels = label_percent(accuracy = 1, suffix = ""),
                       name = NULL) +
  scale_colour_manual(values = c(PAL_JURIS, `TRUE` = "white", `FALSE` = INK),
                      guide = "none") +
  scale_x_discrete(position = "top", expand = c(0, 0)) +
  scale_y_discrete(expand = c(0, 0)) +
  labs(x = NULL, y = NULL) +
  theme_nature(grid = "none") +
  theme(plot.margin = margin(4, 7, 3, 4),
        axis.line.x = element_blank(), axis.ticks = element_blank(),
        axis.text.x.top = element_text(colour = INK, size = rel(1.0),
                                       margin = margin(b = 2)),
        axis.text.y = element_text(colour = INK, size = rel(1.0)),
        legend.position = "right", legend.key.width = unit(5, "pt"),
        legend.key.height = unit(20, "pt"),
        legend.text = element_text(size = rel(0.8)),
        plot.tag = element_text(family = FONT_SANS, face = "bold", size = 8.5,
                                colour = INK),
        plot.tag.position = c(0, 1))

cat("FIG1 assembling\n")
fig1 <- (p_locator_strip + labs(tag = "A")) /
        ((p_home + labs(tag = "B")) | (p_cmp + labs(tag = "C"))) /
        (p_rates + labs(tag = "D")) +
  plot_layout(heights = c(0.95, 0.88, 1.02))
save_fig(fig1, file.path(FIGS, "FIG1_home_region_main.png"), width = W2, height = 5.7)

# =============================================================================
# FIG2 A -- model x prompt tier, integrated
# =============================================================================
cat("D  model tier\n")
e11 <- rd("e11_model_tier.csv")
# Order by signed shift: largest increase at top, most negative at the bottom,
# structural zero below that. The claim is about heterogeneous direction, so the
# ordering must be the signed change and nothing else.
ord11 <- c(e11 %>% filter(estimable) %>% arrange(shift) %>% pull(model),
           e11 %>% filter(!estimable) %>% pull(model))
e11 <- e11 %>% mutate(model = factor(model, levels = ord11))
ok11 <- filter(e11, estimable); no11 <- filter(e11, !estimable)
long11 <- ok11 %>% select(model, juris, regular, boundary) %>%
  pivot_longer(c(regular, boundary), names_to = "tier", values_to = "rate") %>%
  mutate(tier = factor(tier, levels = c("regular", "boundary")))
XMAX11 <- 0.205

p_modtier <- ggplot(e11, aes(y = model)) +
  geom_segment(data = ok11, aes(x = regular, xend = boundary, yend = model,
                                colour = juris), linewidth = LW, lineend = "round") +
  geom_point(data = long11, aes(x = rate, shape = tier, fill = juris),
             size = PT_SM, colour = "white", stroke = 0.4) +
  geom_point(data = no11, aes(x = 0), shape = 22, size = PT_SM - 0.2,
             colour = INK_FAINT, fill = "white", stroke = 0.4) +
  # Signed shift as a right-aligned label rather than a duplicate panel.
  geom_text(data = ok11, aes(x = XMAX11, label = sprintf("%+.1f", 100 * shift),
                             colour = juris),
            hjust = 1, size = TXT - 0.3) +
  geom_text(data = no11, aes(x = XMAX11, label = "n/e"), hjust = 1,
            size = TXT - 0.4, colour = INK_FAINT) +
  # A key for the structural zero, so the hollow square is identified rather
  # than left as an unexplained mark.
  geom_point(data = tibble(x = 0.163, y = nrow(e11) + 0.85), aes(x = x, y = y),
             inherit.aes = FALSE, shape = 22, size = PT_SM - 0.2,
             colour = INK_FAINT, fill = "white", stroke = 0.4) +
  annotate("text", x = 0.169, y = nrow(e11) + 0.85, label = "not estimable",
           hjust = 0, size = TXT - 0.45, colour = INK_FAINT) +
  shift_header(XMAX11, nrow(e11) + 0.85) +
  scale_shape_manual(values = SHAPE_TIER, name = NULL) +
  tier_guide() +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(-0.004, XMAX11), breaks = seq(0, 0.15, 0.05),
                     expand = c(0, 0)) +
  scale_y_discrete(expand = expansion(add = c(0.6, 1.5))) +
  labs(x = "Refusal rate (%)", y = NULL) +
  theme_fig() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0))

# =============================================================================
# FIG2 B -- topic domain x prompt tier
# =============================================================================
cat("E  domain tier\n")
e12 <- rd("e12_domain_tier.csv") %>%
  mutate(domain = pretty_dom(domain), domain = fct_reorder(domain, shift))
long12 <- e12 %>% select(domain, regular, boundary) %>%
  pivot_longer(c(regular, boundary), names_to = "tier", values_to = "rate") %>%
  mutate(tier = factor(tier, levels = c("regular", "boundary")))
XMAX12 <- 0.155
p_domtier <- ggplot(e12, aes(y = domain)) +
  geom_segment(aes(x = regular, xend = boundary, yend = domain),
               colour = lighten(INK_SOFT, 0.55), linewidth = LW, lineend = "round") +
  geom_point(data = long12, aes(x = rate, shape = tier), size = PT_SM,
             fill = INK_SOFT, colour = "white", stroke = 0.4) +
  geom_text(aes(x = XMAX12, label = sprintf("%+.1f", 100 * shift)), hjust = 1,
            size = TXT - 0.3, colour = INK_SOFT) +
  shift_header(XMAX12, nlevels(e12$domain) + 0.85) +
  scale_shape_manual(values = SHAPE_TIER, name = NULL) +
  tier_guide() +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(0, XMAX12), breaks = seq(0, 0.12, 0.04),
                     expand = c(0, 0)) +
  scale_y_discrete(expand = expansion(add = c(0.6, 1.5))) +
  labs(x = "Refusal rate (%)", y = NULL) +
  theme_fig() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0))

cat("FIG2 assembling\n")
fig2 <- (p_modtier + labs(tag = "A")) | (p_domtier + labs(tag = "B"))
fig2 <- fig2 + plot_layout(widths = c(1, 1.02))
save_fig(fig2, file.path(FIGS, "FIG2_model_domain_main.png"), width = W2, height = 2.85)

# =============================================================================
# FIG3 -- refusal-reason composition
# =============================================================================
cat("F  refusal reasons\n")
e13 <- rd("e13_refusal_reasons.csv") %>%
  mutate(reason = factor(reason, levels = names(PAL_REASON)))
# Neutrality-dominant at the top, harm-dominant (Jais) at the bottom.
ord13 <- e13 %>% filter(reason == "neutrality") %>% arrange(share) %>% pull(model)
den <- e13 %>% distinct(model, juris, n_refusals) %>%
  mutate(lab = sprintf("%s  ·  n=%d", model, n_refusals))
lab_map <- setNames(den$lab, den$model)
e13 <- e13 %>% mutate(model = factor(lab_map[model], levels = lab_map[ord13]))
den  <- den  %>% mutate(model = factor(lab, levels = lab_map[ord13]))

# Segment labels are placed by position_stack(), NOT by a hand-computed cumsum.
# geom_col stacks in reverse factor order, so a manual cumsum put every label on
# the wrong segment. Small shares get an empty label rather than being filtered
# out, so the text layer stacks identically to the bar layer.
e13 <- e13 %>% mutate(seg_lab = ifelse(share >= 0.12, sprintf("%.0f", 100 * share), ""))

p_reasons <- ggplot(e13, aes(x = share, y = model, fill = reason)) +
  geom_col(width = 0.68) +
  geom_text(aes(label = seg_lab, colour = reason %in% c("neutrality", "harm")),
            position = position_stack(vjust = 0.5),
            size = TXT - 0.45, show.legend = FALSE) +
  geom_point(data = den, mapping = aes(x = -0.028, y = model, colour = juris),
             inherit.aes = FALSE, size = 1.15) +
  scale_fill_manual(values = PAL_REASON, name = NULL) +
  scale_colour_manual(values = c(PAL_JURIS, `TRUE` = "white", `FALSE` = INK),
                      guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(-0.045, 1.005), breaks = c(0, 0.5, 1),
                     expand = c(0, 0)) +
  labs(x = "Share of that model's refusals (%)", y = NULL) +
  theme_nature(grid = "none") +
  theme(plot.margin = margin(4, 8, 3, 4),
        legend.position = "top", legend.justification = "left",
        legend.key.height = unit(7, "pt"), legend.key.width = unit(11, "pt"),
        legend.text = element_text(size = rel(0.9)),
        legend.margin = margin(0, 0, 2, 0),
        axis.text.y = element_text(colour = INK, size = rel(1.0)))
save_fig(p_reasons, file.path(FIGS, "FIG3_refusal_reasons_main.png"),
         width = W2, height = 2.7)

# =============================================================================
# Standalone panels (not part of the main sequence)
# =============================================================================
cat("standalone panels\n")

# P1 locator is built above (it is now part of FIG1 as well).

# P4 residual matrix -- the analytically sharper view, kept out of the main
# figure because raw rates read faster there.
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
  scale_y_discrete(expand = c(0, 0)) +
  labs(x = NULL, y = "Excess refusal (pp) over jurisdiction + region") +
  theme_nature(grid = "none") +
  theme(axis.line.x = element_blank(), axis.ticks = element_blank(),
        axis.title.y = element_text(size = rel(0.9), colour = INK_SOFT),
        axis.text.x.top = element_text(colour = INK, margin = margin(b = 2)),
        axis.text.y = element_text(colour = INK),
        legend.position = "right", legend.key.width = unit(5, "pt"),
        legend.key.height = unit(20, "pt"))

# P5 China language -- REDESIGNED.
# The previous version plotted only the home PREMIUM, with the away baseline
# relegated to an unexplained "away (%)" column and a legend that merely repeated
# the y-axis. The claim is about two things at once -- similar gaps, different
# baselines -- and neither was visible.
#
# Now it plots the underlying REFUSAL RATES: away and home as two points joined
# by a segment. The baseline is a position, the premium is the segment length
# (printed), and DeepSeek's Chinese baseline shift is the away point sliding
# right. Wilson intervals on each rate show precision. The legend distinguishes
# away from home, which the axis does not already say.
e10 <- rd("e10_cn_home_by_language.csv")
e9  <- rd("e09_cn_language_cells.csv")
LL  <- c(en = "English", zh = "Chinese")

cells <- e9 %>%
  mutate(lang_f = factor(LL[lang], levels = c("English", "Chinese")),
         side   = factor(ifelse(home == 1, "home region", "elsewhere"),
                         levels = c("elsewhere", "home region")))
spans <- cells %>%
  select(model, lang_f, side, rate) %>%
  pivot_wider(names_from = side, values_from = rate) %>%
  rename(away = elsewhere, home = `home region`) %>%
  left_join(e10 %>% mutate(lang_f = factor(LL[lang], levels = c("English", "Chinese"))) %>%
              select(model, lang_f, premium = estimate), by = c("model", "lang_f"))

p_lang <- ggplot(cells, aes(y = fct_rev(lang_f))) +
  geom_segment(data = spans, aes(x = away, xend = home, yend = fct_rev(lang_f)),
               colour = lighten(PAL_JURIS[["CN"]], 0.72), linewidth = LW + 0.3,
               lineend = "round") +
  geom_errorbar(aes(xmin = conf_low, xmax = conf_high), orientation = "y",
                width = 0, linewidth = 0.4, colour = INK_FAINT) +
  geom_point(aes(x = rate, shape = side), size = PT, fill = PAL_JURIS[["CN"]],
             colour = PAL_JURIS[["CN"]], stroke = 0.7) +
  # The premium is the segment length, so it is labelled on the segment.
  geom_text(data = spans, aes(x = (away + home) / 2, y = fct_rev(lang_f),
                              label = sprintf("+%.0f pp", 100 * premium)),
            inherit.aes = FALSE, vjust = -1.25, size = TXT - 0.4,
            colour = INK_SOFT) +
  facet_wrap(~ model, nrow = 1) +
  # Hollow = elsewhere, filled = home region. Language is the y-axis, so shape
  # is free to carry the contrast that actually needs a key.
  scale_shape_manual(values = c("elsewhere" = 1, "home region" = 21), name = NULL) +
  guides(shape = guide_legend(override.aes = list(size = PT, stroke = 0.7))) +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(0, 0.40), breaks = seq(0, 0.40, 0.10),
                     expand = c(0, 0)) +
  scale_y_discrete(expand = expansion(add = c(0.75, 1.05))) +
  labs(x = "Refusal rate (%)", y = NULL) +
  theme_fig() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0),
        strip.text = element_text(colour = INK, size = rel(0.95), hjust = 0))

panels <- list(P1_locator = list(p_locator, 2.10),
               P2_home_interaction = list(p_home, 1.90),
               P3_estimand_comparison = list(p_cmp, 1.90),
               P4_region_structure = list(p_excess, 2.35),
               P5_china_language = list(p_lang, 1.95),
               P6_model_tier = list(p_modtier, 2.55),
               P7_domain_tier = list(p_domtier, 2.35),
               P8_refusal_reasons = list(p_reasons, 2.70))
for (nm in names(panels)) {
  s <- panels[[nm]]
  save_fig(s[[1]] + labs(tag = NULL), file.path(FIGS, paste0(nm, ".png")),
           width = W2, height = s[[2]])
}

cat("\n", strrep("=", 78), "\nFIGURES COMPLETE\n", strrep("=", 78), "\n", sep = "")
