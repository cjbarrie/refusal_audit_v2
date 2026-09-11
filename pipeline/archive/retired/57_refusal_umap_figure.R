# =============================================================================
# REFUSAL-TEXT SPACE -- UMAP projection of every refusal   -> P15
# =============================================================================
# Reads the coordinates written by scripts/refusal_umap.py and draws them. No
# projection is computed here: fitting in the figure script is what the rest of
# this pipeline is built to avoid.
#
# WHAT THE FIGURE IS ARGUING. The judge assigns each refusal one of seven
# justification codes, collapsed to five groups. Those codes have the weakest
# inter-judge agreement of any construct in the study. This asks whether the
# taxonomy corresponds to anything in the text: if refusals given for different
# stated reasons occupy the same region, the codes are not recovering a
# distinction the text supports.
#
# The neighbourhood-purity number in the caption is what keeps this from being
# read by eye alone -- a scatter can always be described as "clustered".

source("pipeline/_theme.R")
suppressPackageStartupMessages({ library(tidyverse); library(patchwork) })

EST <- "pipeline/estimates"
U1 <- file.path(EST, "u01_refusal_umap.csv")
U2 <- file.path(EST, "u02_refusal_umap_all_languages.csv")
if (!file.exists(U1)) {
  cat("SKIP: run scripts/refusal_umap.py first.\n"); quit(status = 0)
}

theme_set(theme_nature() +
  theme(plot.caption = element_text(family = FONT_SANS, size = 5.6,
                                    colour = INK_FAINT, hjust = 0,
                                    lineheight = 1.15)))
tagt <- theme(plot.tag = element_text(family = FONT_SANS, face = "bold",
                                      size = 8.5, colour = INK),
              plot.tag.position = c(0, 1),
              # Anchor the title to the PLOT, not the panel: coord_equal centres
              # a square panel inside the available width, so a panel-anchored
              # title drifts towards the middle and collides with the next
              # panel's tag.
              plot.title.position = "plot",
              # These panels have no y-axis, so the panel starts at the plot's
              # left edge and plot.title.position = "panel" buys no offset --
              # the tag letter lands on top of the title. Indenting the title
              # element itself is what actually moves it.
              plot.title = element_text(colour = INK, face = "bold",
                                        size = rel(1.25), hjust = 0,
                                        margin = margin(b = 1.5, l = 16)),
              plot.margin = margin(5, 8, 4, 4))

`%||%` <- function(a, b) if (is.null(a)) b else a
u1 <- read_csv(U1, show_col_types = FALSE)
u2 <- if (file.exists(U2)) read_csv(U2, show_col_types = FALSE) else NULL

# Factor order is PAL_REASON's, so colour assignment needs no literals here and
# the legend reads in the same order as every other reason figure in the repo.
LEV5 <- names(PAL_REASON)
u1 <- u1 %>% mutate(reason = factor(reason_group, levels = LEV5))

# A projection has no meaningful axes: the units are arbitrary and the distances
# are only locally faithful. Drawing a numbered axis would invite exactly the
# over-reading the caption warns against, so both axes are stripped.
#
# The .x/.y sub-elements must be blanked INDIVIDUALLY. theme_nature() sets them
# explicitly, so a parent `axis.title = element_blank()` never reaches them and
# the titles render anyway.
no_axes <- theme(
  axis.text.x = element_blank(), axis.text.y = element_blank(),
  axis.title.x = element_blank(), axis.title.y = element_blank(),
  axis.ticks.x = element_blank(), axis.ticks.y = element_blank(),
  axis.line.x = element_blank(), axis.line.y = element_blank(),
  panel.grid.major.x = element_blank(), panel.grid.major.y = element_blank(),
  panel.grid.minor = element_blank(),
  panel.border = element_rect(fill = NA, colour = INK_FAINT, linewidth = 0.25))

# A handful of points sit far outside the main body and would otherwise squeeze
# the whole projection into a corner. The panel is limited to a robust range and
# the number of points falling outside it is reported in the caption -- trimming
# silently would misrepresent how many refusals are being shown.
# The window is forced SQUARE around the data centre. coord_equal is mandatory
# here -- an unequal aspect ratio silently rescales one axis and makes distances
# in the projection mean different things in x and y -- but a non-square window
# under coord_equal letterboxes the panel and pushes the cloud into a corner.
rng <- function(d, pad = 0.06) {
  qx <- quantile(d$umap_x, c(0.02, 0.98)); qy <- quantile(d$umap_y, c(0.02, 0.98))
  side <- max(diff(qx), diff(qy)) * (1 + 2 * pad)
  cx <- mean(qx); cy <- mean(qy)
  list(x = c(cx - side / 2, cx + side / 2),
       y = c(cy - side / 2, cy + side / 2))
}
n_outside <- function(d, r) sum(d$umap_x < r$x[1] | d$umap_x > r$x[2] |
                                 d$umap_y < r$y[1] | d$umap_y > r$y[2])

pt <- function(d, aes_extra, r) {
  ggplot(d, aes(umap_x, umap_y)) +
    geom_point(aes_extra, size = 0.5, alpha = 0.7, stroke = 0) +
    coord_equal(xlim = r$x, ylim = r$y, expand = FALSE, clip = "on") +
    no_axes + tagt
}

# --- a: English refusals, coloured by the judge's reason group ---------------
R1 <- rng(u1)
OUT1 <- n_outside(u1, R1)
pa <- pt(u1 %>% arrange(reason), aes(colour = reason), R1) +
  scale_colour_manual(values = PAL_REASON, name = NULL, drop = FALSE) +
  guides(colour = guide_legend(override.aes = list(size = 1.9, alpha = 1),
                               nrow = 2)) +
  labs(title = "By stated reason") +
  theme(legend.position = "top")

# --- b: same projection, coloured by jurisdiction ----------------------------
# Same points, same coordinates -- only the colouring changes, so the reader can
# see whether the structure that exists is about the reason or about who wrote
# the refusal.
pb <- pt(u1 %>% filter(!is.na(jurisdiction)) %>%
           mutate(j = factor(jurisdiction, levels = JURIS_LEVELS)),
         aes(colour = j), R1) +
  scale_colour_juris(name = NULL, drop = FALSE) +
  guides(colour = guide_legend(override.aes = list(size = 1.9, alpha = 1),
                               nrow = 1)) +
  labs(title = "By issue jurisdiction") +
  theme(legend.position = "top")

# --- c: all five languages ---------------------------------------------------
LANG_NAME <- c(en = "English", zh = "Chinese", ar = "Arabic",
               ru = "Russian", hi = "Hindi")
pc <- if (!is.null(u2)) {
  d2 <- u2 %>% mutate(l = factor(unname(LANG_NAME[prompt_language]),
                                 levels = names(PAL_LANGUAGE)))
  R2 <- rng(d2); OUT2 <- n_outside(d2, R2)
  pt(d2 %>% arrange(l), aes(colour = l), R2) +
    scale_colour_manual(values = PAL_LANGUAGE, name = NULL, drop = FALSE) +
    guides(colour = guide_legend(override.aes = list(size = 1.9, alpha = 1),
                                 nrow = 1)) +
    labs(title = "All languages") +
    theme(legend.position = "top")
} else NULL

pur <- sprintf("%.2f against %.2f expected at random",
               u1$purity_group_observed[1], u1$purity_group_baseline[1])
pur2 <- if (!is.null(u2))
  sprintf("%.2f against %.2f", u2$purity_group_observed[1],
          u2$purity_group_baseline[1]) else NA_character_

cap <- str_wrap(paste0(
  "UMAP of TF-IDF (word 1-2 grams in a, b; character 3-5 grams in c) reduced ",
  "to 100 dimensions by truncated SVD, cosine metric, seed ",
  u1$seed[1], ", n_neighbors ", u1$n_neighbors[1], ", min_dist ",
  u1$min_dist[1], ". The representation is LEXICAL, not semantic: it sees ",
  "shared wording, so boilerplate refusals collapse together whatever their ",
  "stated reason. Axes are unlabelled because a UMAP layout has no units and ",
  "only local distances are faithful -- cluster sizes and between-cluster gaps ",
  "carry no meaning. ", OUT1, " of ", nrow(u1), " points in a and b fall ",
  "outside the plotted range and are not drawn",
  if (!is.null(u2)) paste0(" (", OUT2, " of ", nrow(u2), " in c)") else "",
  ". Reason groups do occupy distinguishable regions but ",
  "overlap heavily: among each point's 15 nearest neighbours the share sharing ",
  "its reason group is ", pur, if (!is.na(pur2)) paste0(" (", pur2,
  " across all five languages)") else "", ". a, b share one projection and ",
  "differ only in colouring. c is a separate projection: with five scripts in ",
  "one space, language is the dominant axis of variation, which is why a and b ",
  "are English-only."), width = 150)

SUB <- paste0("English refusals (n = ", format(nrow(u1), big.mark = ","),
              ") in a and b; all ", format(nrow(u2 %||% u1), big.mark = ","),
              " refusals across five languages in c")
fig <- if (!is.null(pc)) {
  (pa | pb) / pc + plot_layout(heights = c(1, 1)) +
    plot_annotation(title = "Refusal-text space", subtitle = SUB,
                    tag_levels = "a", caption = cap)
} else {
  (pa | pb) + plot_annotation(title = "Refusal-text space", subtitle = SUB,
                              tag_levels = "a", caption = cap)
}

save_fig(fig, "pipeline/figures/P15_refusal_text_umap.png",
         width = W2, height = if (!is.null(pc)) 6.4 else 3.4)

cat(sprintf("\nEnglish refusals plotted: %s | all-language: %s\n",
            format(nrow(u1), big.mark = ","),
            if (is.null(u2)) "-" else format(nrow(u2), big.mark = ",")))
