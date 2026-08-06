# =============================================================================
# CANONICAL FIGURES -- FIG1 / FIG2 / FIG3   (600 dpi PNG, two-column, white bg)
# =============================================================================
# One figure per estimand family, in the order the paper argues them:
#   FIG1  home-jurisdiction asymmetry   (Part 1: c02, c04)
#   FIG2  language and framing          (Part 2: c08, c09, c10, c11)
#   FIG3  content of engaged responses  (Part 3: c12, c14)
#
# These read the canonical CSVs only -- they never recompute an estimate. If a
# number appears in a figure it is traceable to a c-table row, which is what
# makes the acceptance test in 56 able to check figure/table agreement.
#
# Every figure states its estimand in the caption, because the three families
# answer different questions and are NOT interchangeable.

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

cat(strrep("=", 78), "\nCANONICAL FIGURES\n", strrep("=", 78), "\n", sep = "")

JORD <- c("CN", "MENA", "India", "US", "EU")          # pinned everywhere

# Panel tags sit at the plot's left edge; titles are therefore aligned to the
# PANEL rather than the plot, so the tag has the far-left corner to itself and
# does not overprint the title.
tagt <- theme(plot.tag = element_text(family = FONT_SANS, face = "bold",
                                      size = 8.5, colour = INK),
              plot.tag.position = c(0, 1),
              plot.title.position = "panel")

# Captions are laid out as a single text grob, so they must be pre-wrapped or
# they run off the page.
cap <- function(...) str_wrap(paste0(...), width = 150)

# =============================================================================
# FIG1 -- home-jurisdiction asymmetry
# =============================================================================
cat("FIG1 ...\n")

# --- panel A: locator map (issue regions, MENA labelled as such) -------------
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

# --- panel B: DESCRIPTIVE observed rates, home vs away ------------------------
c02 <- rd("c02_home_descriptive_english.csv")
obs <- c02 %>%
  filter(grouping == "jurisdiction", quantity == "observed_rate",
         weighting == "response", home_status %in% c("home", "away")) %>%
  transmute(j = factor(jurisdiction, levels = rev(JORD)),
            home_status, rate = rate_strict * 100)
seg <- obs %>% select(j, home_status, rate) %>%
  pivot_wider(names_from = home_status, values_from = rate)

p1b <- ggplot(obs, aes(x = rate, y = j)) +
  geom_segment(data = seg, aes(x = away, xend = home, y = j, yend = j),
               inherit.aes = FALSE, colour = INK_FAINT, linewidth = 0.5) +
  geom_point(aes(fill = home_status), shape = 21, size = 2.1,
             colour = "white", stroke = 0.4) +
  scale_fill_manual(values = c(away = INK_FAINT, home = ACCENT),
                    breaks = c("away", "home"),
                    labels = c("away issues", "home issues"), name = NULL) +
  scale_y_discrete(limits = rev(JORD)) +
  labs(x = "Refusal rate (%), English", y = NULL,
       title = "Descriptive: observed rates") +
  theme_nature(grid = "x") + theme(legend.position = "top") + tagt

# --- panel C: STANDARDIZED contrast ------------------------------------------
c04 <- rd("c04_home_standardized.csv") %>% filter(weighting == "nested")
est <- c04 %>% filter(estimable) %>%
  transmute(j = factor(jurisdiction, levels = rev(JORD)),
            estimate_pp, conf_low_pp, conf_high_pp)
noest <- c04 %>% filter(!estimable) %>%
  transmute(j = factor(jurisdiction, levels = rev(JORD)),
            lab = "no refusals in either arm\n(contrast not estimable)")

p1c <- ggplot(est, aes(x = estimate_pp, y = j)) +
  geom_vline(xintercept = 0, colour = INK_FAINT, linewidth = 0.3) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                 colour = INK, linewidth = 0.45) +
  geom_point(shape = 21, size = 2.1, fill = ACCENT, colour = "white",
             stroke = 0.4) +
  { if (nrow(noest))
      geom_text(data = noest, aes(x = 0, y = j, label = lab), inherit.aes = FALSE,
                hjust = -0.05, size = 1.8, lineheight = 0.95,
                family = FONT_SANS, colour = INK_FAINT) } +
  scale_y_discrete(limits = rev(JORD)) +
  labs(x = "Home − away refusal difference (pp)", y = NULL,
       title = "Standardized: composition held fixed") +
  theme_nature(grid = "x") + tagt

fig1 <- (p1a / (p1b | p1c)) +
  plot_layout(heights = c(0.62, 1)) +
  plot_annotation(
    tag_levels = "a",
    caption = cap(
      "a, Issue regions. b, Observed English refusal rates on home- versus ",
      "away-region issues (no adjustment). c, Covariate-standardized home−away ",
      "contrast (prompt tier, topic domain, seed route; equal weight per model, ",
      "then per issue, then per prompt), issue-cluster bootstrap. b and c are ",
      "different estimands: neither is a causal effect."))
save_fig(fig1, file.path(CAN_FIG, "FIG1_canonical_home.png"), width = W2, height = 5.0)

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
  geom_vline(xintercept = 0, colour = INK_FAINT, linewidth = 0.3) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                 position = position_dodge(width = 0.55),
                 colour = INK, linewidth = 0.4) +
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
  geom_vline(xintercept = 0, colour = INK_FAINT, linewidth = 0.3) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                 position = position_dodge(width = 0.6), linewidth = 0.35) +
  geom_point(position = position_dodge(width = 0.6), size = 1.2) +
  scale_colour_manual(values = c(Chinese = ACCENT, Arabic = "#2A5183",
                                 Hindi = "#7F929F", Russian = "#C08B3E"),
                      name = NULL, drop = FALSE) +
  scale_y_discrete(limits = mord) +
  labs(x = "Paired difference vs. English (pp)", y = NULL,
       title = "By model") +
  theme_nature(grid = "x") +
  theme(legend.position = "top", axis.text.y = element_text(size = 5.4)) + tagt

# c: framing, boundary minus regular.
fr_all <- c10 %>% filter(scope == "overall") %>%
  transmute(g = "All models (pooled)", estimate_pp, conf_low_pp, conf_high_pp)
fr_m <- c11 %>% filter(grouping == "model") %>%
  transmute(g = group, estimate_pp, conf_low_pp, conf_high_pp)
fr <- bind_rows(fr_m, fr_all)
# Model rows keep FIG2b's ordering so the two panels read as one roster; the
# pooled row is pinned last regardless.
ford <- c(intersect(mord, fr$g), setdiff(fr$g, c(mord, "All models (pooled)")),
          "All models (pooled)")

p2c <- ggplot(fr, aes(x = estimate_pp, y = g)) +
  geom_vline(xintercept = 0, colour = INK_FAINT, linewidth = 0.3) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                 colour = INK, linewidth = 0.35) +
  geom_point(aes(fill = g == "All models (pooled)"), shape = 21, size = 1.6,
             colour = "white", stroke = 0.3) +
  scale_fill_manual(values = c(`TRUE` = ACCENT, `FALSE` = INK), guide = "none") +
  scale_y_discrete(limits = rev(ford)) +
  labs(x = "Boundary − regular (pp)", y = NULL,
       title = "Prompt framing, within issue×model") +
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
      "annotation drift."))
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
                 colour = INK, linewidth = 0.4) +
  geom_point(aes(fill = flag), shape = 21, size = 2.1, colour = INK,
             stroke = 0.4) +
  scale_fill_manual(values = c(`acceptable agreement` = ACCENT,
                               `weak judge agreement` = "white"), name = NULL) +
  scale_y_discrete(limits = ford3) +
  labs(x = "Prevalence among engaged responses (%)", y = NULL,
       title = "Moral foundations invoked") +
  theme_nature(grid = "x") + theme(legend.position = "top") + tagt

fig3 <- (p3a | p3b) +
  plot_annotation(
    tag_levels = "a",
    caption = cap(
      "Both panels are CONDITIONAL ON ENGAGEMENT: the judge skips these passes ",
      "for refusals, so the denominators are engaged responses and the panels ",
      "say nothing about what refused prompts would have contained. Equal weight ",
      "per model; issue-cluster bootstrap intervals. a, Ideology reliability is ",
      "weak (panel α ≈ 0.41 economic to 0.14 populism) and should not ",
      "carry substantive weight. b, Foundations are separate non-exclusive ",
      "indicators, not a composition; hollow points mark foundations whose ",
      "positive specific agreement across judges is low."))
save_fig(fig3, file.path(CAN_FIG, "FIG3_canonical_content.png"),
         width = W2, height = 3.4)

cat("\nwrote:\n"); print(list.files(CAN_FIG))
cat("\n", strrep("=", 78), "\nCANONICAL FIGURES DONE\n", strrep("=", 78), "\n", sep = "")
