# =============================================================================
# Script 30: Figures  (PLOTTING ONLY -- reads saved estimates, never re-fits)
# =============================================================================
# Input : pipeline/estimates/*.csv   (written by 20_ and 21_)
# Output: pipeline/figures/*.png     PNG ONLY, 600 dpi
#
# Every plotted number comes from a saved estimate table. There are no model
# fits and no hard-coded values here, so a figure cannot silently diverge from
# the estimates. audit_figures.R re-reads both and fails if they disagree.
#
# No titles, subtitles or interpretive prose inside any panel. Panel letters and
# short direct labels only; everything else is in docs/FIGURE_CAPTIONS.md.

suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork); library(sf)
})
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")

EST <- "pipeline/estimates"; FIGS <- "pipeline/figures"
rd <- function(f) read_csv(file.path(EST, f), show_col_types = FALSE)
cat(strrep("=", 78), "\nFIGURES\n", strrep("=", 78), "\n", sep = "")

# Deterministic ordering everywhere.
JORDER <- c("CN", "MENA", "India", "US", "EU")
ord_j  <- function(x) factor(x, levels = rev(JORDER))

# Shared geometry so panels align.
PT <- 2.6; PT_SM <- 1.7; LW <- 0.85; TXT <- 2.15
theme_panel <- function(...) theme_nature(grid = "x", ...) +
  theme(plot.margin = margin(4, 6, 3, 4),
        axis.title.x = element_text(size = rel(0.95), margin = margin(t = 3)))

# =============================================================================
# P1 -- locator strip (compact key, <= 15% of FIG1)
# =============================================================================
cat("P1 locator\n")
ARAB <- c("DZA","BHR","COM","DJI","EGY","IRQ","JOR","KWT","LBN","LBY","MRT",
          "MAR","OMN","PSE","QAT","SAU","SOM","SDN","SYR","TUN","ARE","YEM")
world <- rnaturalearth::ne_countries(scale = "small", returnclass = "sf") %>%
  mutate(reg = case_when(
    iso_a3 == "CHN" ~ "China", iso_a3 == "IND" ~ "India", iso_a3 == "USA" ~ "US",
    iso_a3 %in% ARAB ~ "Arab",
    continent == "Europe" & iso_a3 != "RUS" ~ "Europe", TRUE ~ NA_character_)) %>%
  st_transform("+proj=robin")

# No in-map labels: the adjacent statistical panels carry the same colours and
# the caption states the operationalisation. This keeps the key subordinate.
p_locator <- ggplot() +
  geom_sf(data = filter(world, is.na(reg)), fill = MAP_LAND, colour = "white",
          linewidth = 0.06) +
  geom_sf(data = filter(world, !is.na(reg)), aes(fill = reg), colour = "white",
          linewidth = 0.06) +
  scale_fill_manual(values = PAL_REGION, guide = "none") +
  coord_sf(xlim = c(-1.34e7, 1.6e7), ylim = c(-3.6e6, 8.4e6), expand = FALSE) +
  theme_void() + theme(plot.margin = margin(1, 2, 1, 2),
                       plot.background = element_rect(fill = "white", colour = NA))

# =============================================================================
# P2 -- primary within-issue home premium  (HERO)
# =============================================================================
cat("P2 home premium (primary)\n")
e1 <- rd("e01_home_premium_primary.csv")
# Order: estimates descending, then any non-estimable case LAST. Mixing a
# structural zero into a magnitude ordering would imply it has a magnitude.
ordB <- c(e1 %>% filter(estimable) %>% arrange(estimate) %>% pull(jurisdiction),
          e1 %>% filter(!estimable) %>% pull(jurisdiction))
e1 <- e1 %>% mutate(jurisdiction = factor(jurisdiction, levels = ordB))
est <- filter(e1, estimable); nest <- filter(e1, !estimable)

p_home <- ggplot(est, aes(y = jurisdiction)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.5) +
  geom_errorbar(aes(xmin = conf_low, xmax = conf_high, colour = as.character(jurisdiction)),
                orientation = "y", width = 0, linewidth = LW) +
  geom_point(aes(x = estimate, colour = as.character(jurisdiction)),
             size = PT + 0.9, shape = 21, fill = "white", stroke = 0) +
  geom_point(aes(x = estimate, fill = as.character(jurisdiction)),
             size = PT, shape = 21, colour = "white", stroke = 0.5) +
  geom_text(aes(x = conf_high, label = sprintf("%+.1f", 100 * estimate),
                colour = as.character(jurisdiction)),
            hjust = -0.3, size = TXT, fontface = "bold") +
  # Structural zero: hollow square + explicit words. Never a point at zero.
  geom_point(data = nest, aes(x = 0), shape = 22, size = PT, colour = INK_FAINT,
             fill = "white", stroke = 0.5) +
  geom_text(data = nest, aes(x = 0, label = "0 observed refusals; not estimable"),
            hjust = -0.09, size = TXT - 0.25, colour = INK_FAINT, fontface = "italic") +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(-0.035, 0.30), breaks = seq(0, 0.20, 0.05),
                     expand = c(0, 0)) +
  labs(x = "Home premium (percentage points)", y = NULL) +
  theme_panel() +
  theme(axis.text.y = element_text(face = "bold", colour = INK, size = rel(1.05)))

# =============================================================================
# P3 -- estimand comparison
# =============================================================================
cat("P3 estimand comparison\n")
e4 <- rd("e04_estimand_comparison.csv") %>%
  mutate(jurisdiction = ord_j(jurisdiction),
         estimand = factor(estimand, levels = c("Within-issue (primary)",
                                                "Within-jurisdiction (descriptive)")))
p_cmp <- ggplot(e4, aes(x = estimate, y = jurisdiction)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.5) +
  geom_line(aes(group = jurisdiction), colour = RULE, linewidth = LW,
            lineend = "round") +
  geom_errorbar(aes(xmin = conf_low, xmax = conf_high), orientation = "y",
                width = 0, linewidth = 0.45, colour = INK_SOFT) +
  geom_point(aes(shape = estimand, fill = as.character(jurisdiction)),
             size = PT_SM + 0.5, colour = "white", stroke = 0.4) +
  # Shape, not colour, separates the two estimands: colour already means
  # jurisdiction everywhere in this figure.
  scale_shape_manual(values = c("Within-issue (primary)" = 21,
                                "Within-jurisdiction (descriptive)" = 24)) +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     breaks = seq(0, 0.20, 0.10)) +
  labs(x = "Home effect (pp)", y = NULL) +
  theme_panel() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0),
        axis.text.y = element_text(colour = INK))

# =============================================================================
# P4 -- region structure as EXCESS over an additive baseline
# =============================================================================
cat("P4 region structure (excess)\n")
e8 <- rd("e08_region_cells.csv") %>%
  mutate(juris = factor(juris, levels = JORDER),
         region = factor(region, levels = REGION_LEVELS))
p_matrix <- ggplot(e8, aes(x = juris, y = fct_rev(region))) +
  geom_tile(aes(fill = excess), colour = "white", linewidth = 1.1) +
  # Home cells get a ring, not a different fill: fill is reserved for the
  # quantity. Previously the diagonal was coloured, which made home cells look
  # special before the reader could judge their magnitude.
  geom_tile(data = filter(e8, home), fill = NA, colour = INK, linewidth = 0.6) +
  geom_text(aes(label = sprintf("%.1f", 100 * rate),
                colour = abs(excess) > 0.045), size = 2.15) +
  scale_fill_gradientn(colours = PAL_DIVERGE, limits = c(-0.09, 0.09),
                       oob = scales::squish, na.value = CELL_EMPTY,
                       labels = label_percent(accuracy = 1, suffix = ""),
                       name = NULL) +
  scale_colour_manual(values = c(`TRUE` = "white", `FALSE` = INK), guide = "none") +
  scale_x_discrete(position = "top", expand = c(0, 0)) +
  scale_y_discrete(expand = c(0, 0)) +
  labs(x = NULL, y = NULL) +
  theme_nature(grid = "none") +
  theme(plot.margin = margin(4, 4, 3, 4),
        axis.line.x = element_blank(), axis.ticks.x = element_blank(),
        axis.ticks.y = element_blank(),
        axis.text.x.top = element_text(colour = INK, size = rel(1.0),
                                       margin = margin(b = 2)),
        axis.text.y = element_text(colour = INK, size = rel(1.0)),
        legend.position = "right", legend.key.width = unit(5, "pt"),
        legend.key.height = unit(16, "pt"),
        legend.text = element_text(size = rel(0.8)))

# =============================================================================
# P5 -- China language decomposition
# =============================================================================
cat("P5 China language\n")
e10 <- rd("e10_cn_home_by_language.csv")
e9  <- rd("e09_cn_language_cells.csv")
lang_lab <- c(en = "English", zh = "Chinese")
e10 <- e10 %>% mutate(lang_f = factor(lang_lab[lang], levels = c("English", "Chinese")))
base_rates <- e9 %>% filter(home == 0) %>%
  transmute(model, lang_f = factor(lang_lab[lang], levels = c("English", "Chinese")),
            away = rate)
e10 <- left_join(e10, base_rates, by = c("model", "lang_f"))

p_lang <- ggplot(e10, aes(x = estimate, y = fct_rev(lang_f))) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.5) +
  geom_errorbar(aes(xmin = conf_low, xmax = conf_high), orientation = "y",
                width = 0, linewidth = LW, colour = PAL_JURIS[["CN"]]) +
  # Language is shape + linetype, never the China red -- that colour means
  # jurisdiction. Both models are CN, so both take the CN colour.
  geom_point(aes(shape = lang_f), size = PT, fill = PAL_JURIS[["CN"]],
             colour = "white", stroke = 0.5) +
  geom_text(aes(x = conf_high, label = sprintf("away %.0f%%", 100 * away)),
            hjust = -0.18, size = TXT - 0.4, colour = INK_FAINT) +
  facet_wrap(~ model, nrow = 1) +
  scale_shape_manual(values = c(English = 21, Chinese = 24), name = NULL) +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(0, 0.42), breaks = seq(0, 0.30, 0.10),
                     expand = c(0, 0)) +
  scale_y_discrete(expand = expansion(add = c(0.75, 0.75))) +
  labs(x = "Home premium (pp)", y = NULL) +
  theme_panel() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0),
        strip.text = element_text(colour = INK, size = rel(0.95), hjust = 0),
        axis.text.y = element_text(colour = INK))

# =============================================================================
# FIG1
# =============================================================================
cat("FIG1 assembling\n")
tagit <- theme(plot.tag = element_text(family = FONT_SANS, face = "bold",
                                       size = 8.5, colour = INK),
               plot.tag.position = c(0, 1))
fig1 <- (p_locator + tagit) /
        ((p_home + tagit) + (p_cmp + tagit) + plot_layout(widths = c(1.25, 1))) /
        ((p_matrix + tagit) + (p_lang + tagit) + plot_layout(widths = c(1, 1.05))) +
  plot_layout(heights = c(0.42, 1.05, 1.15)) +
  plot_annotation(tag_levels = "A")
save_fig(fig1, file.path(FIGS, "FIG1_home_region_main.png"), width = W2, height = 5.6)

# =============================================================================
# P6 -- model x prompt tier
# =============================================================================
cat("P6 model x tier\n")
e11 <- rd("e11_model_tier.csv") %>%
  mutate(juris = factor(juris, levels = JORDER),
         model = fct_reorder(model, ifelse(is.na(shift), 0, shift)))
e11_ok <- filter(e11, estimable); e11_no <- filter(e11, !estimable)
long11 <- e11_ok %>%
  select(model, juris, regular, boundary) %>%
  pivot_longer(c(regular, boundary), names_to = "tier", values_to = "rate") %>%
  mutate(tier = factor(tier, levels = c("regular", "boundary")))

p_modtier <- ggplot(e11, aes(y = model)) +
  geom_segment(data = e11_ok,
               aes(x = regular, xend = boundary, yend = model,
                   colour = as.character(juris)), linewidth = LW, lineend = "round") +
  geom_point(data = long11, aes(x = rate, shape = tier, fill = as.character(juris)),
             size = PT_SM + 0.4, colour = "white", stroke = 0.4) +
  # Structural zero drawn in BOTH halves so the row sets match exactly.
  geom_point(data = e11_no, mapping = aes(x = 0, y = model), inherit.aes = FALSE,
             shape = 22, size = PT_SM, colour = INK_FAINT, fill = "white",
             stroke = 0.4) +
  scale_shape_manual(values = SHAPE_TIER, name = NULL) +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(0, 0.175), breaks = seq(0, 0.15, 0.05),
                     expand = c(0, 0)) +
  labs(x = "Refusal rate (%)", y = NULL) +
  theme_panel() +
  theme(legend.position = "top", legend.justification = "left",
        legend.key.height = unit(6, "pt"), legend.key.width = unit(8, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0),
        axis.text.y = element_text(colour = INK, size = rel(0.95)))

# Companion: the signed shift with its interval, which the segment cannot show.
p_modshift <- ggplot(e11, aes(y = model)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.5) +
  geom_errorbar(data = e11_ok, aes(xmin = conf_low, xmax = conf_high,
                    colour = as.character(juris)), orientation = "y",
                width = 0, linewidth = 0.55) +
  geom_point(data = e11_ok, aes(x = shift, fill = as.character(juris)), shape = 21,
             size = PT_SM + 0.2, colour = "white", stroke = 0.4) +
  geom_point(data = e11_no, aes(x = 0), shape = 22, size = PT_SM, colour = INK_FAINT,
             fill = "white", stroke = 0.4) +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     breaks = seq(-0.04, 0.08, 0.04)) +
  labs(x = "Shift, boundary − regular (pp)", y = NULL) +
  theme_panel() +
  theme(axis.text.y = element_blank())

# =============================================================================
# P7 -- domain x prompt tier
# =============================================================================
cat("P7 domain x tier\n")
e12 <- rd("e12_domain_tier.csv") %>%
  mutate(domain = pretty_domain(domain), domain = fct_reorder(domain, regular))
long12 <- e12 %>% select(domain, regular, boundary) %>%
  pivot_longer(c(regular, boundary), names_to = "tier", values_to = "rate") %>%
  mutate(tier = factor(tier, levels = c("regular", "boundary")))
p_domtier <- ggplot(e12, aes(y = domain)) +
  geom_segment(aes(x = regular, xend = boundary, yend = domain),
               colour = RULE, linewidth = LW, lineend = "round") +
  geom_point(data = long12, aes(x = rate, shape = tier), size = PT_SM + 0.4,
             fill = INK_SOFT, colour = "white", stroke = 0.4) +
  scale_shape_manual(values = SHAPE_TIER, name = NULL) +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(0, 0.135), breaks = seq(0, 0.12, 0.04),
                     expand = c(0, 0)) +
  labs(x = "Refusal rate (%)", y = NULL) +
  theme_panel() +
  theme(legend.position = "none",   # the tier key is already given in panel A
        axis.text.y = element_text(colour = INK))
p_domshift <- ggplot(e12, aes(y = domain)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.5) +
  geom_errorbar(aes(xmin = conf_low, xmax = conf_high), orientation = "y",
                width = 0, linewidth = 0.55, colour = INK_SOFT) +
  geom_point(aes(x = shift), shape = 21, size = PT_SM + 0.2, fill = INK,
             colour = "white", stroke = 0.4) +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     breaks = seq(-0.04, 0.04, 0.04)) +
  labs(x = "Shift (pp)", y = NULL) +
  theme_panel() + theme(axis.text.y = element_blank())

cat("FIG2 assembling\n")
fig2 <- ((p_modtier + tagit) + (p_modshift + theme(plot.margin = margin(4,6,3,0))) +
           plot_layout(widths = c(1, 0.62))) /
        ((p_domtier + tagit) + (p_domshift + theme(plot.margin = margin(4,6,3,0))) +
           plot_layout(widths = c(1, 0.62))) +
  plot_layout(heights = c(1, 0.92)) +
  plot_annotation(tag_levels = list(c("A", "", "B", "")))
save_fig(fig2, file.path(FIGS, "FIG2_model_domain_main.png"), width = W2, height = 4.4)

# =============================================================================
# P8 / FIG3 -- refusal reasons
# =============================================================================
cat("P8 refusal reasons\n")
e13 <- rd("e13_refusal_reasons.csv") %>%
  mutate(reason = factor(reason, levels = names(PAL_REASON)))
ord13 <- e13 %>% filter(reason == "neutrality") %>% arrange(share) %>% pull(model)
e13 <- e13 %>% mutate(model = factor(model, levels = ord13))
lab13 <- e13 %>% group_by(model) %>% arrange(reason, .by_group = TRUE) %>%
  mutate(xpos = cumsum(share) - share / 2) %>% ungroup() %>%
  filter(share >= 0.18)
den <- e13 %>% distinct(model, juris, n_refusals)

p_reasons <- ggplot(e13, aes(x = share, y = model, fill = reason)) +
  geom_col(width = 0.66) +
  geom_text(data = lab13, aes(x = xpos, label = reason,
                              colour = reason %in% c("neutrality", "harm")),
            size = TXT - 0.45, show.legend = FALSE) +
  # Model origin appears only as a bullet beside the name, so jurisdiction
  # colour never doubles as a refusal-reason colour.
  geom_point(data = den, aes(x = -0.035, y = model, colour = NULL,
                             fill = NULL, shape = NULL),
             inherit.aes = FALSE, size = 1.6,
             colour = PAL_JURIS[den$juris]) +
  geom_text(data = den, aes(x = 1.02, y = model, label = n_refusals),
            inherit.aes = FALSE, hjust = 0, size = TXT - 0.35, colour = INK_FAINT) +
  annotate("text", x = 1.02, y = length(ord13) + 0.75, label = "n", hjust = 0,
           size = TXT - 0.35, colour = INK_FAINT) +
  scale_fill_manual(values = PAL_REASON, name = NULL) +
  scale_colour_manual(values = c(`TRUE` = "white", `FALSE` = INK), guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1, suffix = ""),
                     limits = c(-0.05, 1.10), breaks = c(0, 0.5, 1),
                     expand = c(0, 0)) +
  scale_y_discrete(expand = expansion(add = c(0.6, 1.0))) +
  labs(x = "Share of that model's refusals (%)", y = NULL) +
  theme_nature(grid = "none") +
  theme(plot.margin = margin(4, 6, 3, 4),
        legend.position = "top", legend.justification = "left",
        legend.key.height = unit(6, "pt"), legend.key.width = unit(9, "pt"),
        legend.text = element_text(size = rel(0.85)),
        legend.margin = margin(0, 0, 1, 0),
        axis.text.y = element_text(colour = INK, size = rel(0.95)))
save_fig(p_reasons, file.path(FIGS, "FIG3_refusal_reasons_main.png"),
         width = W15, height = 2.8)

# =============================================================================
# Standalone panels + journal-width previews
# =============================================================================
cat("standalone panels\n")
panels <- list(P1_locator = list(p_locator, W15, 1.35),
               P2_home_interaction = list(p_home, W15, 1.95),
               P3_estimand_comparison = list(p_cmp, W15, 2.05),
               P4_region_structure = list(p_matrix, W15, 2.30),
               P5_china_language = list(p_lang, W15, 1.85),
               P6_model_tier = list(p_modtier, W15, 2.50),
               P7_domain_tier = list(p_domtier, W15, 2.35),
               P8_refusal_reasons = list(p_reasons, W15, 2.80))
for (nm in names(panels)) {
  s <- panels[[nm]]
  save_fig(s[[1]], file.path(FIGS, paste0(nm, ".png")), width = s[[2]], height = s[[3]])
}

# Previews are RE-RENDERED at each width, never downscaled from a bigger raster.
cat("journal-width previews\n")
mains <- list(FIG1_home_region_main = list(fig1, 5.6),
              FIG2_model_domain_main = list(fig2, 4.4),
              FIG3_refusal_reasons_main = list(p_reasons, 2.8))
for (nm in names(mains)) {
  o <- mains[[nm]]
  save_fig(o[[1]], file.path(FIGS, paste0(nm, "_1col.png")),
           width = W1, height = o[[2]] * (W1 / W2) * 1.45)
  save_fig(o[[1]], file.path(FIGS, paste0(nm, "_2col.png")),
           width = W2, height = o[[2]])
}

cat("\n", strrep("=", 78), "\nFIGURES COMPLETE\n", strrep("=", 78), "\n", sep = "")
