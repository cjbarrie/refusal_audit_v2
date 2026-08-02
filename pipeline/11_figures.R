# =============================================================================
# Script 11: The figure system
# =============================================================================
# Requires: pipeline/data_clean.RData (01_data_loading.R)
# Writes:   pipeline/figures/*.png (600 dpi) + *.pdf (vector)
#
# NO TITLES, SUBTITLES OR PROSE INSIDE ANY PANEL. Panel letters and short direct
# labels only. Explanation lives in docs/FIGURE_CAPTIONS.md.
#
# STRUCTURE
#   FIG1  hero collage : locator map (key) + home-region effect + region matrix
#                        + CN language decomposition
#   FIG2  supporting   : model heterogeneity + domain gradient + refusal reasons
#   P0..P6             : standalone versions of each panel
#
# The locator map is a KEY, not evidence. It introduces the jurisdiction palette
# in the same visual field as the main estimate, so every colour downstream is
# already learned. It carries no quantities and is visually subordinate.

suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork); library(sf)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")
load("pipeline/data_clean.RData")

FIGS <- "pipeline/figures"
set.seed(20260802)
cat(strrep("=", 78), "\nFIGURE SYSTEM\n", strrep("=", 78), "\n", sep = "")

# -----------------------------------------------------------------------------
# Data preparation
# -----------------------------------------------------------------------------
# `home` is defined only off "General": an issue with no regional focus has no
# home jurisdiction, so including it would score every model "away" on a sixth
# of the sample.
d <- data_clean %>%
  filter(!is.na(jurisdiction_f), !is.na(region_focus)) %>%
  mutate(juris  = factor(as.character(jurisdiction_f), levels = JURIS_LEVELS),
         region = factor(region_focus, levels = REGION_LEVELS),
         home   = as.character(region_focus) == HOME_REGION[as.character(jurisdiction_f)])
d_en <- d %>% filter(prompt_language == "en")

rate_ci <- function(df, ...) {
  df %>% group_by(...) %>%
    summarise(n = n(), k = sum(refused), .groups = "drop") %>%
    mutate(rate = k / n) %>% bind_cols(wilson_ci(.$k, .$n))
}

# =============================================================================
# PANEL A -- locator map (the palette key)
# =============================================================================
# A real but heavily simplified world map, Robinson projection, Antarctica
# dropped. Only the five jurisdiction regions are coloured; the rest of the world
# is a near-white ground so the key reads as five marks rather than as a map of
# everything. Region names are set directly on their landmass, so the panel needs
# no legend and no axis.
cat("\nA  locator map\n")

ARAB <- c("DZA","BHR","COM","DJI","EGY","IRQ","JOR","KWT","LBN","LBY","MRT",
          "MAR","OMN","PSE","QAT","SAU","SOM","SDN","SYR","TUN","ARE","YEM")

world <- rnaturalearth::ne_countries(scale = "small", returnclass = "sf") %>%
  mutate(reg = case_when(
    iso_a3 == "CHN"                         ~ "China",
    iso_a3 == "IND"                         ~ "India",
    iso_a3 == "USA"                         ~ "US",
    iso_a3 %in% ARAB                        ~ "Arab",
    continent == "Europe" & iso_a3 != "RUS" ~ "Europe",
    TRUE                                    ~ NA_character_)) %>%
  st_transform("+proj=robin")

# Label anchors placed by hand in lon/lat: automatic centroids put the Arab label
# in the Mediterranean and the Europe label in the Atlantic.
lab_pts <- tribble(
  ~reg,      ~lon, ~lat,
  "US",      -100,   41,
  "Europe",    14,   56,
  "Arab",      22,   26,
  "India",     94,    9,
  "China",    104,   40
) %>% st_as_sf(coords = c("lon", "lat"), crs = 4326) %>% st_transform("+proj=robin")
lab_xy <- bind_cols(st_drop_geometry(lab_pts), as_tibble(st_coordinates(lab_pts)))

p_map <- ggplot() +
  geom_sf(data = filter(world, is.na(reg)), fill = "#F2F3F4",
          colour = "white", linewidth = 0.08) +
  geom_sf(data = filter(world, !is.na(reg)), aes(fill = reg),
          colour = "white", linewidth = 0.08) +
  geom_text(data = lab_xy, aes(X, Y, label = reg, colour = reg),
            size = 2.2, family = FONT_SANS, fontface = "bold") +
  scale_fill_manual(values = PAL_REGION, guide = "none") +
  # Labels sit on their own fill, so the two lightest regions take ink and the
  # three darkest take white; a single label colour would fail at one end.
  scale_colour_manual(guide = "none",
                      values = c(China = "white", Arab = "white",
                                 India = unname(PAL_REGION[["India"]]),
                                 US = INK, Europe = INK)) +
  coord_sf(xlim = c(-1.32e7, 1.58e7), ylim = c(-3.7e6, 8.6e6), expand = FALSE) +
  theme_void(base_family = FONT_SANS) +
  theme(plot.margin = margin(2, 2, 2, 2),
        plot.background = element_rect(fill = "white", colour = NA))

# =============================================================================
# PANEL B -- home-region effect (the hero)
# =============================================================================
# ESTIMAND: average marginal effect of an issue falling in the model's home
# region on P(refuse), holding topic domain fixed by g-computation over the
# observed domain distribution.
#
# Adjustment is load-bearing, not cosmetic. 45% of China issues are
# territorial-sovereignty and 45% of Arab issues are security-conflict, both
# high-refusal domains, so the raw contrast conflates "sensitive about its own
# region" with "sensitive about sovereignty". Adjustment halves MENA (5.8 -> 2.7)
# and flips the sign for the US (-0.9 -> +1.6).
#
# UNCERTAINTY: bootstrap resampling ISSUES, not responses. All models answer the
# same battery, so responses are clustered within issue.
cat("B  home-region effect\n")

ame_home <- function(df, B = 400) {
  if (length(unique(df$refused)) < 2)
    return(tibble(ame = 0, lo = NA_real_, hi = NA_real_,
                  n = nrow(df), degenerate = TRUE))
  g <- function(x) {
    f <- suppressWarnings(glm(refused ~ home + prompt_category, x, family = binomial))
    mean(predict(f, transform(x, home = TRUE),  type = "response") -
         predict(f, transform(x, home = FALSE), type = "response"))
  }
  est <- g(df); iss <- unique(df$issue_id)
  bs <- replicate(B, {
    tk <- sample(iss, length(iss), replace = TRUE)
    tryCatch(g(df[unlist(lapply(tk, function(i) which(df$issue_id == i))), ]),
             error = function(e) NA_real_)
  })
  tibble(ame = est, lo = quantile(bs, .025, na.rm = TRUE),
         hi = quantile(bs, .975, na.rm = TRUE), n = nrow(df), degenerate = FALSE)
}

f1 <- d_en %>% filter(region != "General") %>%
  group_by(juris) %>% group_modify(~ ame_home(.x)) %>% ungroup() %>%
  mutate(juris = fct_reorder(juris, ame))

XMAX <- 0.345
p_effect <- ggplot(f1, aes(x = ame, y = juris)) +
  # Zero is a reference, not data: a hairline drawn under everything.
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.5) +
  geom_errorbar(aes(xmin = lo, xmax = hi, colour = juris), orientation = "y",
                width = 0, linewidth = 1.0, na.rm = TRUE) +
  # A white halo lets the estimate sit cleanly on top of its own interval.
  geom_point(colour = "white", size = 4.6, na.rm = TRUE) +
  geom_point(aes(colour = juris), size = 3.3) +
  geom_text(data = ~ filter(.x, !degenerate),
            aes(x = hi, label = sprintf("%+.1f", 100 * ame), colour = juris),
            hjust = -0.32, size = 2.55, family = FONT_SANS, fontface = "bold") +
  geom_text(data = ~ filter(.x, degenerate), aes(x = 0, label = "never refuses"),
            hjust = -0.18, size = 2.1, family = FONT_SANS, colour = INK_FAINT,
            fontface = "italic") +
  # n as an unobtrusive right-hand column rather than a second axis.
  # n sits in a reserved gutter with its own hairline, so it can never collide
  # with the effect labels the way it did when both floated at the right edge.
  annotate("segment", x = 0.295, xend = 0.295, y = 0.4, yend = 5.55,
           colour = RULE, linewidth = 0.4) +
  geom_text(aes(x = XMAX, label = format(n, big.mark = ",")), hjust = 1,
            size = 2.0, family = FONT_SANS, colour = INK_FAINT) +
  annotate("text", x = XMAX, y = 5.62, label = "n", hjust = 1,
           size = 2.0, family = FONT_SANS, colour = INK_FAINT) +
  scale_colour_juris() +
  scale_x_continuous(labels = label_percent(accuracy = 1),
                     limits = c(-0.062, XMAX), breaks = seq(0, 0.20, 0.10),
                     expand = c(0, 0)) +
  scale_y_discrete(expand = expansion(add = c(0.55, 0.95))) +
  labs(x = "Home-region effect (pp, domain-adjusted)", y = NULL) +
  theme_nature(grid = "x") +
  theme(axis.text.y = element_text(face = "bold", colour = INK, size = rel(1.15)))

# =============================================================================
# PANEL C -- jurisdiction x issue-region matrix
# =============================================================================
# A table-graphic, replacing five faceted dot panels. Cells are shaded by rate
# and the value printed; the home cell is filled in the jurisdiction colour with
# reversed type. Three facts land in one fixation that the dot version buried:
# the coloured diagonal, the uniformly dark Arab ROW (Arab issues are broadly
# sensitive, including to models with no stake in them), and CN's China-specific
# spike rather than a general elevation.
cat("C  jurisdiction x region matrix\n")

ramp <- colorRampPalette(c("#F7F7F8", "#6E7276"))(101)
f2 <- rate_ci(d_en, juris, region) %>%
  mutate(home  = as.character(region) == HOME_REGION[as.character(juris)],
         shade = scales::rescale(pmin(rate, 0.14), from = c(0, 0.14)),
         fill  = ifelse(home, unname(PAL_JURIS[as.character(juris)]),
                        ramp[round(shade * 100) + 1]),
         ink   = ifelse(farver::decode_colour(fill, to = "lab")[, 1] < 62, "white", INK),
         lab   = sprintf("%.1f", 100 * rate))

p_matrix <- ggplot(f2, aes(x = juris, y = fct_rev(region))) +
  geom_tile(aes(fill = fill), colour = "white", linewidth = 1.2) +
  geom_text(aes(label = lab, colour = ink,
                fontface = ifelse(home, "bold", "plain")),
            size = 2.3, family = FONT_SANS) +
  scale_fill_identity() + scale_colour_identity() +
  scale_x_discrete(position = "top", expand = c(0, 0)) +
  scale_y_discrete(expand = c(0, 0)) +
  labs(x = NULL, y = NULL) +
  theme_nature(grid = "none") +
  theme(axis.line.x = element_blank(), axis.ticks = element_blank(),
        axis.text.x.top = element_text(face = "bold", colour = INK,
                                       size = rel(1.1), margin = margin(b = 3)),
        axis.text.y = element_text(colour = INK, size = rel(1.05)))

# =============================================================================
# PANEL D -- CN models: home x language slopegraph
# =============================================================================
# Two rows (away, home), one line per language. PARALLEL LINES ARE THE FINDING:
# the home gap is ~15-18 pp in every row, so the regional effect does not depend
# on language. What moves is the BASELINE -- DeepSeek's away rate jumps 2.6 ->
# 14.5 in Chinese while Qwen's barely moves. A paired-dot layout made the reader
# compute both facts; a slopegraph shows them.
cat("D  CN home x language\n")

f3 <- d %>%
  filter(juris == "CN", region != "General", prompt_language %in% c("en", "zh")) %>%
  rate_ci(model, language_f, home) %>%
  mutate(side = factor(ifelse(home, "home", "away"), levels = c("away", "home")))
# Label in the FIRST facet only. Qwen's English and Chinese lines nearly
# coincide, so labelling both panels overprinted "Chinese" on "English"; the
# colour semantic is shared across facets, so one direct label suffices.
lab3 <- f3 %>% filter(side == "home", model == "deepseek-chat-v3.1")

p_lang <- ggplot(f3, aes(x = rate, y = side, group = language_f)) +
  geom_line(aes(colour = language_f), linewidth = 1.0, lineend = "round") +
  geom_point(colour = "white", size = 3.4) +
  geom_point(aes(colour = language_f), size = 2.2) +
  geom_text(data = lab3, aes(label = as.character(language_f), colour = language_f),
            hjust = -0.28, size = 2.15, family = FONT_SANS, fontface = "bold") +
  facet_wrap(~ model, nrow = 1) +
  # Chinese takes the CN jurisdiction colour; English recedes to ink. Language is
  # a within-jurisdiction contrast here, so it borrows the same semantic.
  scale_colour_manual(values = c(English = INK_FAINT, Chinese = unname(PAL_JURIS[["CN"]]))) +
  scale_x_continuous(labels = label_percent(accuracy = 1),
                     limits = c(0, 0.47), breaks = seq(0, 0.40, 0.10),
                     expand = c(0, 0)) +
  scale_y_discrete(expand = expansion(add = c(0.6, 0.6))) +
  labs(x = "Refusal rate", y = NULL) +
  theme_nature(grid = "x") +
  theme(axis.text.y = element_text(colour = INK, size = rel(1.05)),
        strip.text = element_text(family = FONT_MONO, colour = INK,
                                  size = rel(1.0), hjust = 0))

# =============================================================================
# FIG 1 -- hero collage
# =============================================================================
# The map sits beside the hero estimate so the palette is learned exactly where
# it is first used. B gets the widest, tallest cell because it is the result; C
# and D are full-width bands beneath, reading as evidence then mechanism. Three
# cell geometries and three graphical forms: an argument with a shape, not a
# column of plots.
cat("FIG1  hero collage\n")

tag_style <- theme(
  plot.tag = element_text(family = FONT_SANS, face = "bold", size = 9, colour = INK),
  plot.tag.position = c(0, 1), plot.margin = margin(6, 8, 4, 6))

top  <- (p_map + tag_style) + (p_effect + tag_style) + plot_layout(widths = c(0.85, 1))
fig1 <- top / (p_matrix + tag_style) / (p_lang + tag_style) +
  plot_layout(heights = c(1.05, 1.20, 0.85)) +
  plot_annotation(tag_levels = "A")

save_fig(fig1, file.path(FIGS, "FIG1_hero.png"), width = W2, height = 6.5)

save_fig(p_map, file.path(FIGS, "P0_locator.png"), width = W15, height = 1.80)
save_fig(p_effect, file.path(FIGS, "P1_home_effect.png"), width = W15, height = 2.00)
save_fig(p_matrix, file.path(FIGS, "P2_region_matrix.png"), width = W15, height = 2.35)
save_fig(p_lang,   file.path(FIGS, "P3_home_by_language.png"), width = W15, height = 1.75)

# =============================================================================
# PANEL E -- between-model heterogeneity
# =============================================================================
# Arrows, not dumbbells: the finding is that boundary framing moves models in
# OPPOSITE directions, so direction must be encoded rather than inferred from
# which end is which. A right-hand strip carries the signed shift, so magnitude
# is readable without measuring the arrow.
cat("E  model heterogeneity\n")

f4 <- d_en %>% rate_ci(model, juris, dataset_type_f) %>%
  select(model, juris, dataset_type_f, rate) %>%
  pivot_wider(names_from = dataset_type_f, values_from = rate) %>%
  rename(regular = `Regular Prompts`, boundary = `Boundary Prompts`) %>%
  mutate(shift = boundary - regular, model = fct_reorder(model, regular))
NM <- nlevels(f4$model)

p_models <- ggplot(f4, aes(y = model)) +
  geom_segment(aes(x = regular, xend = boundary, yend = model, colour = juris),
               linewidth = 1.0, lineend = "butt",
               arrow = arrow(length = unit(3.4, "pt"), type = "closed")) +
  geom_point(aes(x = regular), colour = INK_FAINT, size = 1.5) +
  annotate("segment", x = 0.192, xend = 0.192, y = 0.4, yend = NM + 0.6,
           colour = RULE, linewidth = 0.4) +
  geom_text(aes(x = 0.212, label = sprintf("%+.1f", 100 * shift), colour = juris),
            hjust = 1, size = 2.2, family = FONT_SANS) +
  annotate("text", x = 0.212, y = NM + 0.8, label = "shift", hjust = 1,
           size = 2.0, family = FONT_SANS, colour = INK_FAINT) +
  scale_colour_juris() +
  scale_x_continuous(labels = label_percent(accuracy = 1),
                     limits = c(0, 0.214), breaks = seq(0, 0.15, 0.05),
                     expand = c(0, 0)) +
  scale_y_discrete(expand = expansion(add = c(0.55, 1.1))) +
  labs(x = "Refusal rate, regular to boundary", y = NULL) +
  theme_nature(grid = "x") +
  theme(axis.text.y = element_text(family = FONT_MONO, colour = INK, size = rel(0.95)))

# =============================================================================
# PANEL F -- stated reason for refusal
# =============================================================================
# Four small multiples on a COMMON x, one per reason -- not a stacked bar. A
# stack forces the reader to compare segment widths at different left offsets,
# the comparison the eye is worst at, and it hid the two most interesting facts
# (Jais 81% harm, Claude 18% epistemic). Faceting puts every model on the same
# baseline within each reason.
cat("F  refusal reasons\n")

J4 <- c(A = "neutrality", C = "harm", B = "epistemic", D = "epistemic",
        E = "epistemic", F = "unstated", G = "unstated")
f5 <- d_en %>%
  filter(refused, !is.na(refusal_justification)) %>%
  mutate(j = factor(unname(J4[refusal_justification]),
                    levels = c("neutrality", "harm", "unstated", "epistemic"))) %>%
  filter(!is.na(j)) %>%
  count(model, j, .drop = FALSE) %>%
  group_by(model) %>% mutate(tot = sum(n), p = n / tot) %>% ungroup() %>%
  filter(tot >= 30) %>%
  left_join(distinct(d_en, model, juris), by = "model")
ord5 <- f5 %>% filter(j == "neutrality") %>% arrange(p) %>% pull(model)
f5 <- f5 %>% mutate(model = factor(model, levels = ord5))

p_reasons <- ggplot(f5, aes(x = p, y = model)) +
  geom_segment(aes(x = 0, xend = p, yend = model), colour = RULE, linewidth = 0.8) +
  geom_point(aes(colour = juris), size = 1.8) +
  facet_wrap(~ j, nrow = 1) +
  scale_colour_juris() +
  scale_x_continuous(labels = c("0", "50", "100"), limits = c(0, 1),
                     breaks = c(0, 0.5, 1),
                     expand = expansion(mult = c(0.04, 0.08))) +
  labs(x = "Share of that model's refusals (%)", y = NULL) +
  theme_nature(grid = "x") +
  theme(axis.text.y = element_text(family = FONT_MONO, colour = INK, size = rel(0.9)),
        strip.text = element_text(colour = INK, face = "bold", size = rel(1.0), hjust = 0))

# =============================================================================
# PANEL G -- topic-domain gradient
# =============================================================================
# Slope segments, regular -> boundary, ordered by regular rate. The tier ORDERING
# differs between tiers -- security and governance fall under boundary framing
# while religion, social-moral and civil-rights roughly double -- which a
# two-panel dot layout revealed only if the reader tracked nine rows twice.
cat("G  topic-domain gradient\n")

f6 <- rate_ci(d_en, prompt_category, dataset_type_f) %>%
  select(prompt_category, dataset_type_f, rate) %>%
  pivot_wider(names_from = dataset_type_f, values_from = rate) %>%
  rename(regular = `Regular Prompts`, boundary = `Boundary Prompts`) %>%
  mutate(domain = pretty_domain(prompt_category),
         domain = fct_reorder(domain, regular),
         up = boundary > regular)

p_domain <- ggplot(f6, aes(y = domain)) +
  geom_segment(aes(x = regular, xend = boundary, yend = domain, colour = up),
               linewidth = 1.0, lineend = "butt",
               arrow = arrow(length = unit(3.4, "pt"), type = "closed")) +
  geom_point(aes(x = regular), colour = INK_FAINT, size = 1.5) +
  scale_colour_manual(values = c(`TRUE` = INK, `FALSE` = INK_FAINT),
                      guide = "none") +
  scale_x_continuous(labels = label_percent(accuracy = 1),
                     limits = c(0, 0.128), breaks = seq(0, 0.12, 0.04),
                     expand = c(0, 0)) +
  labs(x = "Refusal rate, regular to boundary", y = NULL) +
  theme_nature(grid = "x") +
  theme(axis.text.y = element_text(colour = INK, size = rel(1.0)))

# =============================================================================
# FIG 2 -- supporting collage
# =============================================================================
cat("FIG2  supporting collage\n")

fig2 <- ((p_models + tag_style) + (p_domain + tag_style) +
           plot_layout(widths = c(1, 0.92))) /
  (p_reasons + tag_style) +
  plot_layout(heights = c(1, 0.9)) +
  plot_annotation(tag_levels = "A")

save_fig(fig2, file.path(FIGS, "FIG2_supporting.png"), width = W2, height = 4.6)

save_fig(p_models,  file.path(FIGS, "P4_model_tier.png"),      width = W15, height = 2.50)
save_fig(p_reasons, file.path(FIGS, "P5_refusal_reasons.png"), width = W2,  height = 2.30)
save_fig(p_domain,  file.path(FIGS, "P6_topic_domain.png"),    width = W15, height = 2.20)

cat("\n", strrep("=", 78), "\nFIGURES COMPLETE\n", strrep("=", 78), "\n", sep = "")
