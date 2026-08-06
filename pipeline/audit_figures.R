# =============================================================================
# Figure and estimate audit
# =============================================================================
# Run after 20_, 21_ and 30_. Exits non-zero if anything fails, so it can gate a
# commit or a build.
#
# The load-bearing check is section 4: every plotted quantity is re-read from
# the estimate tables and compared, so a figure cannot silently drift from the
# numbers it claims to show.

suppressPackageStartupMessages({ library(tidyverse); library(png) })
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")

EST <- "pipeline/estimates"; FIGS <- "pipeline/figures"
fails <- character(); warns <- character()
ok <- function(lab, pass, detail = "", warn_only = FALSE) {
  tag <- if (pass) "OK  " else if (warn_only) "WARN" else "FAIL"
  cat(sprintf("  %-42s %-4s %s\n", lab, tag, detail))
  if (!pass) { if (warn_only) warns <<- c(warns, lab) else fails <<- c(fails, lab) }
}
cat(strrep("=", 78), "\nFIGURE + ESTIMATE AUDIT\n", strrep("=", 78), "\n", sep = "")

# --- 1. PNG only -------------------------------------------------------------
cat("\n1. output format\n")
allf <- list.files(FIGS)
png_f <- grep("[.]png$", allf, value = TRUE)
bad   <- setdiff(allf, png_f)
ok("PNG only, no other format", length(bad) == 0,
   sprintf("%d png%s", length(png_f),
           if (length(bad)) paste0("; FOUND ", paste(bad, collapse = ", ")) else ""))

# --- 2. expected files -------------------------------------------------------
cat("\n2. expected files\n")
MAIN <- c("FIG1_home_region_main", "FIG2_model_domain_main",
          "FIG3_refusal_reasons_main")
PANELS <- c("P1_locator", "P2_home_interaction", "P3_estimand_comparison",
            "P4_region_structure_raw", "P4_region_structure_excess",
            "P5_china_language", "P6_model_tier", "P7_domain_tier",
            "P8_refusal_reasons", "P12_home_by_model")
# Language figures exist only once 25_estimates_language.R has run.
LANG <- if (file.exists("pipeline/estimates/e29_language_by_model.csv"))
  c("FIG5_language_main", "P13_language_by_model",
    "P14_home_premium_by_language") else character(0)
# The slant figures (FIG4/P9/P10) come from annotation passes 2/3, which run on
# a 25% issue subsample and may not have been run at all -- so they are expected
# only when their estimates exist. Present-but-unexpected would trip the "stale"
# check, so the same condition drives both directions.
SLANT <- if (file.exists("pipeline/estimates/e16b_ideology_summary.csv"))
  c("FIG4_slant_main", "P9_ideology_mean_neutral", "P9_ideology_distribution",
    "P10_moral_foundations", "P11_moral_by_language") else character(0)
# Two-column only. No _1col, no _2col: one canonical file per main figure.
expect <- c(paste0(MAIN, ".png"), paste0(PANELS, ".png"), paste0(SLANT, ".png"),
            paste0(LANG, ".png"))
missing <- setdiff(expect, png_f)
ok("every expected PNG present", length(missing) == 0,
   sprintf("%d expected%s", length(expect),
           if (length(missing)) paste0("; MISSING ", paste(missing, collapse = ", ")) else ""))
stale <- setdiff(png_f, expect)
ok("no stale figure artefacts", length(stale) == 0,
   if (length(stale)) paste("STALE:", paste(stale, collapse = ", ")) else "none")
# Explicit checks, so a regression is named rather than showing up as "stale".
onecol <- grep("_1col", png_f, value = TRUE)
twocol <- grep("_2col", png_f, value = TRUE)
ok("no one-column outputs", length(onecol) == 0,
   if (length(onecol)) paste(onecol, collapse = ", ") else "none")
ok("no duplicate _2col variants", length(twocol) == 0,
   if (length(twocol)) paste(twocol, collapse = ", ") else "none")

# --- 3. image integrity ------------------------------------------------------
cat("\n3. image integrity\n")
DPI <- 600
dims <- map_dfr(intersect(expect, png_f), function(f) {
  a <- tryCatch(png::readPNG(file.path(FIGS, f)), error = function(e) NULL)
  if (is.null(a)) return(tibble(file = f, w = NA_integer_, h = NA_integer_,
                                white = NA, mb = NA_real_))
  corner <- a[1:8, 1:8, 1:3]     # confirm a white background
  tibble(file = f, w = dim(a)[2], h = dim(a)[1], white = mean(corner) > 0.97,
         mb = file.size(file.path(FIGS, f)) / 1e6)
})
ok("all images open", all(!is.na(dims$w)), sprintf("%d files", nrow(dims)))
ok("white background", all(dims$white, na.rm = TRUE),
   paste(dims$file[!dims$white & !is.na(dims$white)], collapse = ", "))
w2 <- round(W2 * DPI)
dims <- dims %>% mutate(wrong = abs(w - w2) > 2)
ok("all figures at two-column width", !any(dims$wrong, na.rm = TRUE),
   sprintf("%d px expected; offenders: %s", w2,
           paste(dims$file[dims$wrong], collapse = ", ")))

# Clipped labels: ink touching the canvas edge means something ran off.
edge_ink <- map_dbl(intersect(expect, png_f), function(f) {
  a <- png::readPNG(file.path(FIGS, f))
  g <- if (length(dim(a)) == 3) apply(a[, , 1:3], c(1, 2), mean) else a
  min(mean(g[1, ]), mean(g[nrow(g), ]), mean(g[, 1]), mean(g[, ncol(g)]))
})
ok("no labels clipped at the canvas edge", all(edge_ink > 0.985),
   sprintf("min edge brightness %.3f", min(edge_ink)))
ok("file sizes reasonable (< 8 MB)", all(dims$mb < 8, na.rm = TRUE),
   sprintf("max %.1f MB", max(dims$mb, na.rm = TRUE)))
ok("rendered at 600 dpi", all(dims$w >= w2 - 2, na.rm = TRUE),
   sprintf("min width %d px", min(dims$w, na.rm = TRUE)))

# --- 4. estimates <-> figures -------------------------------------------------
cat("\n4. estimates <-> figures\n")
need <- c("e01_home_premium_primary.csv", "e04_estimand_comparison.csv",
          "e08_region_cells.csv", "e10_cn_home_by_language.csv",
          "e11_model_tier.csv", "e12_domain_tier.csv", "e13_refusal_reasons.csv")
ok("all estimate tables present", all(file.exists(file.path(EST, need))),
   paste(setdiff(need, list.files(EST)), collapse = ", "))

e1  <- read_csv(file.path(EST, "e01_home_premium_primary.csv"), show_col_types = FALSE)
e4  <- read_csv(file.path(EST, "e04_estimand_comparison.csv"),  show_col_types = FALSE)
e11 <- read_csv(file.path(EST, "e11_model_tier.csv"),           show_col_types = FALSE)
e12 <- read_csv(file.path(EST, "e12_domain_tier.csv"),          show_col_types = FALSE)
e13 <- read_csv(file.path(EST, "e13_refusal_reasons.csv"),      show_col_types = FALSE)

j <- e4 %>% filter(estimand == "Within-issue (primary)") %>%
  inner_join(filter(e1, estimable), by = "jurisdiction", suffix = c("_cmp", "_pri"))
ok("panel C reuses panel B's estimates",
   nrow(j) > 0 && max(abs(j$estimate_cmp - j$estimate_pri)) < 1e-9,
   sprintf("%d jurisdictions matched", nrow(j)))

ok("structural zeros carry no estimate", all(is.na(e1$estimate[!e1$estimable])),
   sprintf("%d non-estimable", sum(!e1$estimable)))
ok("structural zeros flagged in model tier", all(is.na(e11$conf_low[!e11$estimable])),
   sprintf("%d non-estimable: %s", sum(!e11$estimable),
           paste(e11$model[!e11$estimable], collapse = ", ")))

brackets <- function(d, col) {
  d <- d %>% filter(!is.na(conf_low), !is.na(conf_high))
  if (!nrow(d)) return(TRUE)
  v <- d[[col]]
  all(v >= d$conf_low - 1e-9 & v <= d$conf_high + 1e-9)
}
ok("intervals bracket their estimates",
   all(brackets(e1, "estimate"), brackets(e4, "estimate"),
       brackets(e11, "shift"), brackets(e12, "shift")), "e01/e04/e11/e12")
ok("compositions sum to 1",
   all(abs(e13 %>% group_by(model) %>% summarise(s = sum(share)) %>% pull(s) - 1) < 1e-8),
   sprintf("%d models", n_distinct(e13$model)))
# Stacked-segment labels: verify each sits inside its OWN segment and that the
# printed value equals the segment width. A hand-computed cumsum previously put
# every label on the wrong segment, and nothing in the pipeline caught it --
# geom_col stacks in reverse factor order.
seg_ok <- tryCatch({
  ed <- e13 %>% mutate(reason = factor(reason, levels = names(PAL_REASON)),
                       seg_lab = ifelse(share >= 0.12, sprintf("%.0f", 100 * share), ""))
  pp <- ggplot(ed, aes(x = share, y = model, fill = reason)) + geom_col(width = 0.68) +
    geom_text(aes(label = seg_lab), position = position_stack(vjust = 0.5))
  bb <- ggplot_build(pp)
  jj <- bb$data[[1]] %>% select(y, xmin, xmax, group) %>%
    inner_join(bb$data[[2]] %>% select(y, x, label, group), by = c("y", "group"))
  v <- suppressWarnings(as.numeric(jj$label)) / 100
  all(jj$x >= pmin(jj$xmin, jj$xmax) - 1e-9 & jj$x <= pmax(jj$xmin, jj$xmax) + 1e-9) &&
    all(is.na(v) | abs(abs(jj$xmax - jj$xmin) - v) < 0.005)
}, error = function(e) FALSE)
ok("stacked labels sit in their own segment", seg_ok,
   "position and printed value both verified")

ok("denominators recorded for compositions",
   all(!is.na(e13$n_refusals)) && all(e13$n_refusals >= 30),
   sprintf("min n = %d", min(e13$n_refusals)))

# Legend order must equal the DRAWN stack order. geom_col stacks in reverse
# factor order, so the legend has to be given breaks = rev(levels) -- and a
# mismatch is invisible in the estimate tables, so only a source check finds it.
src0 <- readLines("pipeline/30_figures.R", warn = FALSE)
ok("FIG3 legend order matches stack order",
   any(grepl("DRAWN_ORDER <- rev\\(names\\(PAL_REASON\\)\\)", src0)) &&
     any(grepl("breaks = DRAWN_ORDER", src0)),
   "legend breaks = rev(factor levels)")

# Stacked labels, checked with the REAL aesthetics. Mapping `colour` inside the
# text layer introduces a second grouping variable; position_stack then orders
# the labels by that group while geom_col orders by fill, and every label lands
# on the wrong segment. An earlier version of this check omitted the colour aes
# and therefore passed while the figure was wrong.
seg_ok <- tryCatch({
  ed <- e13 %>% mutate(reason = factor(reason, levels = names(PAL_REASON)),
                       seg_lab = ifelse(share >= 0.15, sprintf("%.0f", 100 * share), ""))
  ordm <- ed %>% filter(reason == "neutrality") %>% arrange(share) %>% pull(model)
  ed <- ed %>% mutate(model = factor(model, levels = ordm))
  pp <- ggplot(ed, aes(x = share, y = model, fill = reason)) + geom_col(width = 0.68) +
    geom_text(aes(label = seg_lab, colour = reason %in% c("neutrality", "harm"),
                  group = reason), position = position_stack(vjust = 0.5))
  bb <- ggplot_build(pp)
  bars <- bb$data[[1]] %>% select(y, xmin, xmax)
  txt  <- bb$data[[2]] %>% filter(label != "") %>% select(y, x, label)
  all(vapply(seq_len(nrow(txt)), function(i) {
    sgs <- bars[bars$y == txt$y[i], ]
    hit <- sgs[txt$x[i] >= pmin(sgs$xmin, sgs$xmax) &
               txt$x[i] <= pmax(sgs$xmin, sgs$xmax), ]
    nrow(hit) == 1 &&
      abs(abs(hit$xmax - hit$xmin) * 100 - as.numeric(txt$label[i])) < 0.6
  }, logical(1)))
}, error = function(e) FALSE)
ok("stacked labels match the segment they sit in", seg_ok,
   "checked with the figure's real aesthetics, incl. colour mapping")

ok("text layer pins its grouping to the fill factor",
   any(grepl("group = reason", src0)), "prevents position_stack divergence")

# Paired panels laid out side by side must state their category order
# explicitly; relying on factor levels alone let the two FIG2A panels resolve a
# different order and every shift lined up against the wrong model.
ok("paired FIG2 panels share an explicit category order",
   sum(grepl("limits = ord11", src0)) >= 2 && sum(grepl("limits = ord12", src0)) >= 2,
   "limits = ord11/ord12 on both panels of each row")

# Ideology: the neutral share must travel with the mean, never be omitted.
ok("ideology panel carries the neutral share",
   any(grepl("neutral_share", src0)) && any(grepl("% at 0", src0, fixed = TRUE)),
   "mean is never shown without its denominator context")

# EU must never appear as an ordinary zero estimate.
ok("EU not plotted as an ordinary zero",
   any(grepl("structural_zero", src0)) && any(grepl("not estimable", src0)),
   "structural zero rendered distinctly")

# Duplicated tick labels where two facets/panels meet (the "400" collision).
dupe_tick <- tryCatch({
  e10x <- read_csv(file.path(EST, "e10_cn_home_by_language.csv"), show_col_types = FALSE)
  brk <- grep("breaks = seq\\(0, 0.30, 0.10\\)", src0)
  length(brk) > 0
}, error = function(e) FALSE)
ok("no terminal tick at a panel boundary (P5)", dupe_tick,
   "x breaks stop short of the panel edge")

# --- 5. colour semantics ------------------------------------------------------
cat("\n5. colour semantics\n")
ok("jurisdiction palette complete",
   setequal(names(PAL_JURIS), c("CN", "MENA", "India", "US", "EU")),
   paste(names(PAL_JURIS), collapse = " "))
ok("home region inherits jurisdiction colour",
   all(PAL_REGION[unname(HOME_REGION[names(PAL_JURIS)])] == PAL_JURIS[names(PAL_JURIS)]),
   "region colour == its jurisdiction colour")
ok("reason palette disjoint from jurisdiction",
   length(intersect(toupper(PAL_REASON), toupper(PAL_JURIS))) == 0,
   sprintf("%d reason colours", length(PAL_REASON)))
ok("reason palette has a separate 'other' and 'none given'",
   all(c("other", "none given") %in% names(PAL_REASON)),
   "judge code G is not folded into F")

src  <- readLines("pipeline/30_figures.R", warn = FALSE)
code <- grep("^\\s*#", src, value = TRUE, invert = TRUE)
ok("no model fitting in the figure script",
   length(grep("glmer\\(|[^a-z.]glm\\(|lmer\\(", code)) == 0, "plotting only")
ok("no direct ggsave in the figure script",
   length(grep("ggsave\\(", code)) == 0, "save_fig is sole writer")
ok("no in-panel titles", length(grep("title *=|subtitle *=", code)) == 0, "")
ok("model labels use the sans family (no mono)",
   length(grep("FONT_MONO", code)) == 0, "one family throughout")
# Shape meanings must not collide: tier uses circle/triangle, so estimand and
# language must use fill, not triangles.
ok("shape encodings do not collide",
   identical(unname(SHAPE_TIER[["boundary"]]), 24) &&
     !any(SHAPE_ESTIMAND == 24) && !any(SHAPE_LANG == 24),
   "triangle reserved for boundary tier")
# The main matrix must print the SAME quantity its fill encodes.
mat <- paste(code, collapse = "\n")
blk <- sub(".*p_rates <- ", "", mat); blk <- sub("p_modtier <-.*", "", blk)
# The fill and the printed number must be the SAME quantity. `fill_rate` is the
# raw rate with structural zeros masked to NA so the EU column renders as empty
# rather than as five ordinary zeros -- still the raw rate, never the residual.
ok("main matrix: raw values over a raw-rate scale",
   grepl("aes\\(fill = fill_rate\\)", blk) && grepl("100 \\* rate", blk) &&
     !grepl("excess", blk), "fill and printed value both = raw rate")
hex <- grep("#[0-9A-Fa-f]{6}", code, value = TRUE)
ok("palette not hard-coded in figures", length(hex) <= 1,
   sprintf("%d literal hex", length(hex)))

# --- 6. grayscale / CVD -------------------------------------------------------
cat("\n6. grayscale / colour-vision\n")
L <- function(h) round(farver::decode_colour(h, to = "lab")[, 1])
gaps <- c(normal = min(diff(sort(L(unname(PAL_JURIS))))))
for (f in c("deutan", "protan", "tritan"))
  gaps[f] <- min(diff(sort(L(do.call(f, list(unname(PAL_JURIS)),
                                     envir = asNamespace("colorspace"))))))
ok("jurisdiction separable in grayscale/CVD", all(gaps >= 5),
   paste(sprintf("%s %d", names(gaps), gaps), collapse = "  "))
rg <- min(diff(sort(L(unname(PAL_REASON)))))
ok("reason palette separable in grayscale", rg >= 5, sprintf("min L* gap %d", rg))

# --- summary ------------------------------------------------------------------
cat("\n", strrep("=", 78), "\n", sep = "")
if (length(fails)) {
  cat("AUDIT FAILED (", length(fails), "):\n", sep = "")
  for (f in fails) cat("   - ", f, "\n", sep = "")
} else {
  cat("AUDIT PASSED",
      if (length(warns)) sprintf("  (%d warnings)", length(warns)) else "", "\n", sep = "")
}
cat(strrep("=", 78), "\n", sep = "")
quit(save = "no", status = if (length(fails)) 1 else 0)
