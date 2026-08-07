# =============================================================================
# MAIN FIGURES -- Fig 1, Fig 2, Fig 3
# =============================================================================
# Three figures, one estimand family each. They READ the canonical tables and
# fit nothing, which is what lets audit_figures.R check every plotted value
# against its source row.
#
#   Fig 1  home-jurisdiction ONLY: design, unadjusted rates, standardized
#          contrasts (full-target and common-support).
#   Fig 2  language and framing: the predeclared primary weighting only.
#   Fig 3  content of engaged responses: five ideology bins, foundations.
#
# Judge sensitivity and the refusal-text projection are Extended Data. They were
# in Fig 1 and did not belong: a main figure should carry one result family.
#
# Text is 5-7 pt at final size, panel labels 8 pt bold, widths 89 or 183 mm.
# Long explanatory captions live in docs/CANONICAL_FIGURE_LEGENDS.md, not inside
# the artwork.

source("pipeline/_theme.R")
suppressPackageStartupMessages({
  library(tidyverse); library(scales); library(patchwork); library(sf)
})

CAN_EST <- Sys.getenv("CANON_EST_DIR", "pipeline/estimates/canonical")
CAN_FIG <- Sys.getenv("CANON_FIG_DIR", "pipeline/figures/main")
dir.create(CAN_FIG, showWarnings = FALSE, recursive = TRUE)
rd <- function(f) { p <- file.path(CAN_EST, f)
  if (file.exists(p)) read_csv(p, show_col_types = FALSE) else
    stop("missing canonical table: ", f) }

theme_set(theme_nature(base_size = PT_BODY))
tagt <- theme(plot.tag = element_text(family = FONT_SANS, face = "bold",
                                      size = PT_TAG, colour = INK),
              plot.tag.position = c(0, 1),
              plot.title = element_text(colour = INK, face = "bold",
                                        size = PT_TITLE, hjust = 0,
                                        margin = margin(b = 2, l = 14)),
              plot.subtitle = element_text(colour = INK_SOFT, size = PT_BODY,
                                           hjust = 0, margin = margin(b = 4, l = 14)))
JORD <- c("CN", "MENA", "India", "US", "EU")
TXT <- pt_to_mm(PT_MIN)          # in-panel numeric labels, exactly at the floor
LWC <- 0.5

cat(strrep("=", 78), "\nMAIN FIGURES\n", strrep("=", 78), "\n", sep = "")

# =============================================================================
# FIGURE 1 -- home-jurisdiction asymmetry
# =============================================================================
cat("Fig 1 ...\n")
c02 <- rd("c02_home_descriptive_english.csv")
c04 <- rd("c04_home_standardized.csv")

# --- a: design schematic ------------------------------------------------------
# Deliberately compact. The map orients the reader; it carries no estimate, so
# it must not take more area than the quantitative panels.
ARAB <- c("DZA","BHR","COM","DJI","EGY","IRQ","JOR","KWT","LBN","LBY","MRT",
          "MAR","OMN","PSE","QAT","SAU","SOM","SDN","SYR","TUN","ARE","YEM")
world <- rnaturalearth::ne_countries(scale = "small", returnclass = "sf") %>%
  mutate(reg = case_when(
    iso_a3 == "CHN" ~ "China", iso_a3 == "IND" ~ "India", iso_a3 == "USA" ~ "US",
    iso_a3 %in% ARAB ~ "Arab",
    continent == "Europe" & iso_a3 != "RUS" ~ "Europe", TRUE ~ NA_character_)) %>%
  st_transform("+proj=robin")
lab <- tribble(~reg, ~disp, ~lon, ~lat,
               "US", "US", -100, 41, "Europe", "EU", 14, 57, "Arab", "MENA", 22, 26,
               "India", "India", 94, 9, "China", "CN", 104, 40) %>%
  st_as_sf(coords = c("lon", "lat"), crs = 4326) %>% st_transform("+proj=robin")
lab <- bind_cols(st_drop_geometry(lab), as_tibble(st_coordinates(lab)))

p1a <- ggplot() +
  geom_sf(data = filter(world, is.na(reg)), fill = MAP_LAND, colour = "white",
          linewidth = 0.04) +
  geom_sf(data = filter(world, !is.na(reg)), aes(fill = reg), colour = "white",
          linewidth = 0.04) +
  geom_text(data = lab, aes(X, Y, label = disp, colour = reg),
            size = pt_to_mm(PT_MIN), family = FONT_SANS, fontface = "bold") +
  scale_fill_manual(values = PAL_REGION, guide = "none") +
  scale_colour_manual(guide = "none",
                      values = c(China = "white", Arab = "white",
                                 India = unname(PAL_REGION[["India"]]),
                                 US = INK, Europe = INK)) +
  coord_sf(xlim = c(-1.30e7, 1.45e7), ylim = c(-0.4e6, 6.75e6), expand = FALSE) +
  labs(title = "Issue regions") +
  theme_void(base_size = PT_BODY) +
  theme(plot.margin = margin(1, 2, 1, 2),
        plot.background = element_rect(fill = "white", colour = NA)) + tagt

# --- b: UNADJUSTED rates ------------------------------------------------------
obs <- c02 %>%
  filter(grouping == "jurisdiction", quantity == "observed_rate",
         weighting == "response", home_status %in% c("home", "away")) %>%
  transmute(jurisdiction, j = factor(jurisdiction, levels = rev(JORD)),
            home_status, rate = rate_strict * 100)
seg <- obs %>% select(jurisdiction, j, home_status, rate) %>%
  pivot_wider(names_from = home_status, values_from = rate)

p1b <- ggplot(obs, aes(x = rate, y = j)) +
  geom_segment(data = seg, aes(x = away, xend = home, y = j, yend = j,
                               colour = jurisdiction),
               inherit.aes = FALSE, linewidth = 0.8, alpha = 0.5) +
  geom_point(data = filter(obs, home_status == "away"),
             aes(colour = jurisdiction), shape = 1, size = 1.5, stroke = 0.6) +
  geom_point(data = filter(obs, home_status == "home"),
             aes(fill = jurisdiction), shape = 21, size = 2, colour = "white",
             stroke = 0.4) +
  geom_text(data = seg, aes(x = pmax(home, away), y = j,
                            label = sprintf("%.1f", home), colour = jurisdiction),
            inherit.aes = FALSE, hjust = -0.35, size = TXT) +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_y_discrete(limits = rev(JORD)) +
  scale_x_continuous(expand = expansion(mult = c(0.04, 0.16))) +
  labs(x = "Refusal rate (%)", y = NULL, title = "Unadjusted rates",
       subtitle = "hollow = away issues, filled = home issues") +
  theme_nature(base_size = PT_BODY, grid = "x") + tagt

# --- c: standardized, both estimands -----------------------------------------
std <- c04 %>%
  filter(weighting == "nested", estimator == "maximum likelihood") %>%
  mutate(j = factor(jurisdiction, levels = rev(JORD)),
         sup = factor(support, levels = c("full target", "common support")))
est <- std %>% filter(estimable)
noest <- std %>% filter(!estimable) %>% distinct(jurisdiction, j)

p1c <- ggplot(est, aes(x = estimate_pp, y = j, colour = jurisdiction,
                       shape = sup, group = sup)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp),
                 position = position_dodge(width = 0.55), linewidth = LWC) +
  geom_point(aes(fill = jurisdiction), position = position_dodge(width = 0.55),
             size = 1.8, colour = "white", stroke = 0.35) +
  # The label sits to the RIGHT of its own interval, on its own dodged row.
  # Placing it above/below the marker collided with the other estimand's label
  # (vjust does not survive position_dodge), and placing it on the point hid the
  # marker.
  geom_text(aes(x = conf_high_pp, label = sprintf("%+.1f", estimate_pp)),
            position = position_dodge(width = 0.55), hjust = -0.25, size = TXT,
            show.legend = FALSE) +
  { if (nrow(noest))
      geom_text(data = noest, aes(x = 0, y = j),
                label = "no refusals in either arm; not estimable",
                inherit.aes = FALSE, hjust = -0.04, size = TXT, colour = INK_FAINT) } +
  scale_colour_manual(values = PAL_JURIS, guide = "none") +
  scale_fill_manual(values = PAL_JURIS, guide = "none") +
  scale_shape_manual(values = c(`full target` = 21, `common support` = 24),
                     name = NULL) +
  # Without override.aes the key glyphs inherit an unmapped colour/fill and the
  # legend renders as bare text with no markers.
  guides(shape = guide_legend(override.aes = list(fill = INK_SOFT,
                                                  colour = INK_SOFT, size = 1.6))) +
  scale_y_discrete(limits = rev(JORD)) +
  scale_x_continuous(expand = expansion(mult = c(0.10, 0.20))) +
  labs(x = "Home - away difference (percentage points)", y = NULL,
       title = "Standardized contrasts",
       subtitle = "composition held fixed; not a causal effect") +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(legend.position = "top", legend.justification = "left",
        legend.text = element_text(size = PT_MIN),
        legend.key.size = unit(7, "pt"),
        legend.margin = margin(0, 0, 0, 0)) + tagt

fig1 <- (p1a | p1b) / p1c +
  plot_layout(heights = c(0.9, 1.05), widths = c(1, 1)) +
  plot_annotation(tag_levels = "a")
save_fig(fig1, file.path(CAN_FIG, "Fig1_home_jurisdiction.png"),
         width = W2, height = 4.3)

# =============================================================================
# FIGURE 2 -- language and framing
# =============================================================================
cat("Fig 2 ...\n")
c08 <- rd("c08_language_paired.csv"); c09 <- rd("c09_language_by_model.csv")
c10 <- rd("c10_framing_paired.csv"); c11 <- rd("c11_framing_by_model_domain.csv")

# The PREDECLARED PRIMARY weighting is equal-per-model, matching the target
# population used everywhere else in the paper. The other two weightings are a
# robustness question, not a result, and are Extended Data.
PRIMARY_W <- "equal_model"
# Alphabetical: no ordering here should imply that one tested language is more
# fundamental than another. English is the paired reference by design, which is
# a stated property of the estimand, not a ranking of languages.
LORD <- c("Arabic", "Chinese", "Hindi", "Russian")

prim <- c08 %>% filter(sensitivity == "primary", weighting == PRIMARY_W) %>%
  transmute(l = factor(language_label, levels = rev(LORD)),
            estimate_pp, conf_low_pp, conf_high_pp)

p2a <- ggplot(prim, aes(x = estimate_pp, y = l)) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), colour = INK,
                 linewidth = LWC) +
  geom_point(size = 1.9, shape = 21, fill = ACCENT, colour = "white", stroke = 0.35) +
  geom_text(aes(label = sprintf("%+.1f", estimate_pp)), vjust = -1.2, size = TXT) +
  scale_y_discrete(limits = rev(LORD)) +
  scale_x_continuous(expand = expansion(mult = c(0.12, 0.12))) +
  labs(x = "Paired difference vs. English (pp)", y = NULL,
       title = "Language effect",
       subtitle = "equal weight per model; paired within model × prompt") +
  theme_nature(base_size = PT_BODY, grid = "x") + tagt

# --- b: model x language heatmap, values printed ------------------------------
# The four-colour forest this replaces was unreadable at 183 mm and encoded
# language in colour alone. A heatmap with the signed value printed in each cell
# carries the number redundantly, so it survives greyscale and colour-vision
# deficiency; the intervals live in the accompanying Extended Data table.
hm <- c09 %>% filter(grouping == "model") %>%
  transmute(model = group, language = factor(language_label, levels = LORD),
            estimate_pp, jurisdiction)
mord <- hm %>% group_by(model) %>% summarise(m = mean(estimate_pp), .groups = "drop") %>%
  arrange(m) %>% pull(model)
LIM <- max(abs(hm$estimate_pp), na.rm = TRUE)

p2b <- ggplot(hm, aes(x = language, y = factor(model, levels = mord),
                      fill = estimate_pp)) +
  geom_tile(colour = "white", linewidth = 0.4) +
  # "%+.0f" prints "-0" for anything in (-0.5, 0); round first so a value that
  # is effectively zero reads as zero.
  geom_text(aes(label = sprintf("%+.0f", round(estimate_pp) + 0),
                colour = abs(estimate_pp) > 0.55 * LIM), size = TXT) +
  scale_fill_gradient2(low = PAL_DIVERGE[[1]], mid = "#F2F2F2",
                       high = PAL_DIVERGE[[5]], midpoint = 0,
                       limits = c(-LIM, LIM), guide = "none") +
  scale_colour_manual(values = c(`TRUE` = "white", `FALSE` = INK), guide = "none") +
  labs(x = NULL, y = NULL, title = "By model",
       subtitle = "signed pp difference vs. English, printed in every cell; red = more refusal in that language, blue = less; intervals in Extended Data") +
  theme_nature(base_size = PT_BODY, grid = "none") +
  theme(axis.text.y = element_text(size = PT_MIN),
        axis.text.x = element_text(size = PT_MIN),
        legend.title = element_text(size = PT_MIN),
        legend.text = element_text(size = PT_MIN),
        panel.grid = element_blank(), axis.line = element_blank(),
        axis.ticks = element_blank()) + tagt

# --- c: framing, complete blocks only -----------------------------------------
fr_m <- c11 %>% filter(grouping == "model") %>%
  transmute(g = group, estimate_pp, conf_low_pp, conf_high_pp) %>% arrange(estimate_pp)
fr_all <- c10 %>% filter(scope == "overall") %>%
  transmute(g = "All models", estimate_pp, conf_low_pp, conf_high_pp)
fr <- bind_rows(fr_m, fr_all)
ford <- c(fr_m$g, "All models")

p2c <- ggplot(fr, aes(x = estimate_pp, y = factor(g, levels = rev(ford)))) +
  geom_vline(xintercept = 0, colour = RULE, linewidth = 0.4) +
  geom_linerange(aes(xmin = conf_low_pp, xmax = conf_high_pp), colour = INK,
                 linewidth = 0.4) +
  geom_point(aes(fill = g == "All models"), shape = 21, size = 1.5,
             colour = "white", stroke = 0.3) +
  scale_fill_manual(values = c(`TRUE` = ACCENT, `FALSE` = INK), guide = "none") +
  scale_x_continuous(expand = expansion(mult = c(0.05, 0.05))) +
  labs(x = "Boundary - regular (pp)", y = NULL, title = "Prompt framing",
       subtitle = "complete 2+2 blocks only; ordered by effect") +
  theme_nature(base_size = PT_BODY, grid = "x") +
  theme(axis.text.y = element_text(size = PT_MIN),
        plot.margin = margin(3, 4, 2, 2)) + tagt

fig2 <- (p2a | p2b) / p2c +
  plot_layout(heights = c(1, 0.95)) +
  plot_annotation(tag_levels = "a")
save_fig(fig2, file.path(CAN_FIG, "Fig2_language_framing.png"),
         width = W2, height = 4.6)

# =============================================================================
# FIGURE 3 -- content of engaged responses
# =============================================================================
cat("Fig 3 ...\n")
c12 <- rd("c12_ideology_distribution.csv"); c14 <- rd("c14_moral_prevalence_equal_model.csv")

DORD <- c("Economic", "Social", "Authority", "Populism")
BINL <- c(share_neg2 = "-2", share_neg1 = "-1", share_zero = "0",
          share_pos1 = "+1", share_pos2 = "+2")

ideo <- c12 %>% filter(role == "PRIMARY") %>%
  mutate(d = factor(dimension, levels = rev(DORD)),
         bin = factor(unname(BINL[quantity]), levels = unname(BINL)),
         share = estimate * 100)
# Dimension-specific endpoint text: "left/right" is meaningful for the economic
# scale and misleading for the other three.
ends <- c12 %>% distinct(dimension, endpoint_neg, endpoint_pos) %>%
  mutate(d = factor(dimension, levels = rev(DORD)))

p3a <- ggplot(ideo, aes(x = share, y = d, fill = bin, group = bin)) +
  geom_col(width = 0.6, colour = "white", linewidth = 0.2,
           position = position_stack(reverse = TRUE)) +
  geom_text(data = ends, aes(x = -1, y = d, label = endpoint_neg),
            inherit.aes = FALSE, hjust = 1, size = TXT, colour = INK_SOFT) +
  geom_text(data = ends, aes(x = 101, y = d, label = endpoint_pos),
            inherit.aes = FALSE, hjust = 0, size = TXT, colour = INK_SOFT) +
  scale_fill_manual(values = setNames(c(PAL_DIVERGE[[1]], PAL_DIVERGE[[2]],
                                        "#EDEDED", PAL_DIVERGE[[4]], PAL_DIVERGE[[5]]),
                                      unname(BINL)), name = NULL) +
  scale_y_discrete(limits = rev(DORD)) +
  scale_x_continuous(expand = expansion(mult = c(0.30, 0.30)),
                     breaks = c(0, 50, 100)) +
  labs(x = "Share of engaged responses (%)", y = NULL,
       title = "Ideological placement, all five categories",
       subtitle = "CONDITIONAL ON ENGAGEMENT · descriptive/exploratory: judge agreement is weak") +
  theme_nature(base_size = PT_BODY, grid = "none") +
  theme(legend.position = "top", legend.text = element_text(size = PT_MIN),
        legend.key.size = unit(6, "pt")) + tagt

mf <- c14 %>% filter(scope == "overall") %>%
  mutate(f = fct_reorder(foundation, estimate),
         psa_lab = ifelse(is.na(psa_mean), "agreement n/a",
                          sprintf("PSA %.2f", psa_mean)))

p3b <- ggplot(mf, aes(x = estimate * 100, y = f)) +
  geom_linerange(aes(xmin = conf_low * 100, xmax = conf_high * 100), colour = INK,
                 linewidth = LWC) +
  geom_point(shape = 21, size = 1.9, fill = ACCENT, colour = "white", stroke = 0.35) +
  # The agreement statistic is printed as a NUMBER. No "acceptable"/"weak"
  # verdict: the 0.35 threshold that produced one was invented, not preregistered.
  geom_text(aes(x = conf_high * 100, label = psa_lab), hjust = -0.15,
            size = TXT, colour = INK_SOFT) +
  scale_y_discrete(limits = levels(mf$f)) +
  scale_x_continuous(expand = expansion(mult = c(0.04, 0.34))) +
  labs(x = "Prevalence among engaged responses (%)", y = NULL,
       title = "Moral foundations invoked",
       subtitle = "NON-EXCLUSIVE indicators · PSA = pairwise positive specific agreement") +
  theme_nature(base_size = PT_BODY, grid = "x") + tagt

fig3 <- (p3a | p3b) + plot_annotation(tag_levels = "a")
save_fig(fig3, file.path(CAN_FIG, "Fig3_content.png"), width = W2, height = 2.6)

cat("\nwrote:\n"); print(list.files(CAN_FIG))
cat("\n", strrep("=", 78), "\nMAIN FIGURES DONE\n", strrep("=", 78), "\n", sep = "")
