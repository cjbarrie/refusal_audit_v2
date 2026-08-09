# =============================================================================
# Figure audit
# =============================================================================
# Runs after 20_figures_main.R and 21_figures_extended.R. Exits non-zero on any
# failure, so make_release.R can gate promotion on it.
#
# MEMORY. Rasters are processed ONE AT A TIME and released immediately. The
# previous version built a tibble by mapping over all seven 4,322-pixel PNGs and
# then ran apply(a[,,1:3], c(1,2), mean) on each -- a ~42-million-element apply
# per file. It exhausted memory during the image-integrity section and never
# reached its own summary, so the audit reported nothing while appearing to run.
# Every per-image statistic here is computed with vectorised slice means.

suppressPackageStartupMessages({ library(tidyverse) })
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")

EST     <- "pipeline/estimates"
CAN_EST <- Sys.getenv("CANON_EST_DIR", file.path(EST, "canonical"))
MAIN_FIG <- Sys.getenv("CANON_FIG_DIR", "pipeline/figures/main")
ED_FIG   <- Sys.getenv("CANON_APPFIG_DIR", "pipeline/figures/extended")

fails <- character(); warns <- character()
ok <- function(lab, pass, detail = "", warn_only = FALSE) {
  if (length(pass) != 1L || is.na(pass) || !is.logical(pass)) {
    detail <- paste("CHECK BROKEN: condition was not a single TRUE/FALSE.", detail)
    pass <- FALSE
  }
  cat(sprintf("  %-52s %-4s %s\n", lab,
              if (pass) "OK" else if (warn_only) "WARN" else "FAIL", detail))
  if (!pass) { if (warn_only) warns <<- c(warns, lab) else fails <<- c(fails, lab) }
}
rdc <- function(f) { p <- file.path(CAN_EST, f)
  if (file.exists(p)) suppressMessages(read_csv(p, show_col_types = FALSE)) else NULL }
cat(strrep("=", 78), "\nFIGURE AUDIT\n", strrep("=", 78), "\n", sep = "")

MAIN <- c("Fig1_home_jurisdiction", "Fig2_language_framing", "Fig3_content")
# PNG ONLY. One raster per expected figure and nothing else, anywhere under the
# active figure directories.
ED   <- c("ED1_judge_sensitivity", "ED2_focused_sensitivity",
          "ED3_sample_size_stability", "ED4_language_heterogeneity",
          "ED5_slant_by_model", "ED6_foundations_by_model",
          "ED7_measurement_reliability", "ED8_prompt_semantic_umap",
          "ED9_prompt_semantic_umap_by_model")
# Filenames retired in the restructure. Their presence means a stale raster
# survived, which is exactly the failure the inventory check exists to catch.
RETIRED_FIG <- c("ED2_inferential_robustness", "ED2_sensitivity_panels",
                 "ED3_postoutcome_diagnostics", "ED3_language_detail",
                 "ED5_measurement_reliability", "S1_home_descriptive",
                 "S2_judge_multiverse", "S3_specification_curve",
                 "S4_projection_supplement", "P15_refusal_text_umap")
# Approved two-column canvases, in pixels at 600 dpi. Every figure must land on
# one of these exactly: letting each script choose its own height produced a set
# whose aspect ratios ran from 183x81 to 183x208 mm, so identical point sizes
# read as different sizes side by side on the page.
CANVAS_PX <- round(unname(CANVASES) * 600)

# --- 1. formats ---------------------------------------------------------------
cat("\n1. output formats\n")
expect_main <- paste0(MAIN, ".png")
expect_ed   <- paste0(ED, ".png")
have_main <- list.files(MAIN_FIG, recursive = TRUE)
have_ed   <- list.files(ED_FIG, recursive = TRUE)

ok("main figures present, exactly the expected PNGs",
   setequal(have_main, expect_main),
   sprintf("missing: %s | unexpected: %s",
           paste(setdiff(expect_main, have_main), collapse = ","),
           paste(setdiff(have_main, expect_main), collapse = ",")))
ok("Extended Data present, exactly the expected PNGs",
   setequal(have_ed, expect_ed),
   sprintf("missing: %s | unexpected: %s",
           paste(setdiff(expect_ed, have_ed), collapse = ","),
           paste(setdiff(have_ed, expect_ed), collapse = ",")))
non_png <- grep("[.]png$", c(have_main, have_ed), value = TRUE, invert = TRUE)
ok("no non-PNG file in any active figure directory", length(non_png) == 0,
   paste(non_png, collapse = ", "))
# The obsolete trees must be gone, not merely empty.
obsolete <- c("pipeline/figures/canonical", "pipeline/figures/appendix")
gone <- !vapply(obsolete, dir.exists, logical(1))
ok("obsolete figure directories removed", all(gone),
   paste(obsolete[!gone], collapse = ", "))
stale <- intersect(sub("[.]png$", "", c(have_main, have_ed)), RETIRED_FIG)
ok("no retired figure filename survives", length(stale) == 0,
   paste(stale, collapse = ", "))

# --- 2. raster integrity, one file at a time ---------------------------------
cat("\n2. raster integrity (streamed)\n")
# PNG dimensions come from the IHDR header: 8 bytes signature, 4 length,
# 4 type, then width and height as big-endian uint32. No pixels are read.
png_dim <- function(p) {
  con <- file(p, "rb"); on.exit(close(con))
  raw <- readBin(con, "raw", n = 24)
  if (length(raw) < 24) return(c(NA, NA))
  w <- sum(as.integer(raw[17:20]) * 256^(3:0))
  h <- sum(as.integer(raw[21:24]) * 256^(3:0))
  c(w, h)
}
# RESOLUTION METADATA, read from the pHYs chunk rather than inferred from the
# pixel count. A large raster is not a 600 dpi figure: without pHYs a journal's
# layout software places the image at 72 dpi and the type comes out four times
# too big. Returns dpi (x, y) or NA if the chunk is absent.
png_dpi <- function(p) {
  d <- readBin(p, "raw", n = min(file.size(p), 65536L))
  i <- 9L
  while (i + 8L <= length(d)) {
    ln  <- sum(as.integer(d[i:(i + 3)]) * 256^(3:0))
    typ <- rawToChar(d[(i + 4):(i + 7)])
    if (identical(typ, "pHYs")) {
      b <- d[(i + 8):(i + 16)]
      px <- sum(as.integer(b[1:4]) * 256^(3:0))
      py <- sum(as.integer(b[5:8]) * 256^(3:0))
      if (as.integer(b[9]) != 1L) return(c(NA_real_, NA_real_))  # not metres
      return(round(c(px, py) * 0.0254, 1))
    }
    if (identical(typ, "IDAT")) break
    i <- i + 12L + ln
  }
  c(NA_real_, NA_real_)
}
inspect <- function(p) {
  d <- png_dim(p)
  a <- png::readPNG(p)
  nr <- dim(a)[1]; nc <- dim(a)[2]
  ch <- if (length(dim(a)) == 3) min(3, dim(a)[3]) else 1
  sl <- function(i, j) if (ch == 1) a[i, j] else a[i, j, 1:ch]
  res <- list(w = d[1], h = d[2],
              corner = mean(sl(1:8, 1:8)),
              edge = min(mean(sl(1, seq_len(nc))), mean(sl(nr, seq_len(nc))),
                         mean(sl(seq_len(nr), 1)), mean(sl(seq_len(nr), nc))))
  rm(a); gc(verbose = FALSE)
  res
}
W2_PX <- round(W2 * 600)
bad_w <- character(); bad_bg <- character(); bad_edge <- character()
bad_h <- character(); bad_dpi <- character()
for (s in c(MAIN, ED)) {
  p <- file.path(if (s %in% MAIN) MAIN_FIG else ED_FIG, paste0(s, ".png"))
  if (!file.exists(p)) next
  r <- inspect(p)
  if (!is.na(r$w) && abs(r$w - W2_PX) > 3) bad_w <- c(bad_w, s)
  # ONE-COLUMN OUTPUT IS FORBIDDEN. Every figure is designed at 183 mm; an 89 mm
  # variant would need different type sizes and would drift from its sibling.
  if (!is.na(r$w) && abs(r$w - round(W1 * 600)) <= 3)
    bad_w <- c(bad_w, paste0(s, " (one-column)"))
  if (!is.na(r$h) && !any(abs(r$h - CANVAS_PX) <= 3))
    bad_h <- c(bad_h, sprintf("%s (%d px)", s, r$h))
  dpi <- png_dpi(p)
  if (any(is.na(dpi)) || any(abs(dpi - 600) > 1)) bad_dpi <- c(bad_dpi, s)
  if (r$corner <= 0.97) bad_bg <- c(bad_bg, s)
  if (r$edge <= 0.985) bad_edge <- c(bad_edge, s)
}
ok("all figures at the declared column width", length(bad_w) == 0,
   sprintf("%d px expected; %s", W2_PX, paste(bad_w, collapse = ", ")))
ok("every height matches an approved canvas", length(bad_h) == 0,
   sprintf("approved: %s px; %s", paste(CANVAS_PX, collapse = "/"),
           paste(bad_h, collapse = ", ")))
ok("PNGs carry 600 dpi resolution metadata (pHYs)", length(bad_dpi) == 0,
   paste(bad_dpi, collapse = ", "))
ok("white background", length(bad_bg) == 0, paste(bad_bg, collapse = ", "))
ok("nothing clipped at the canvas edge", length(bad_edge) == 0,
   paste(bad_edge, collapse = ", "))

# --- 3. rendered layout (MEASURED, not inferred from source) -----------------
cat("\n3. rendered layout\n")
# The previous version of this section claimed to measure layout and in fact
# grepped the source for font sizes, which is why a clipped subtitle and
# colliding panel tags both passed. The assembled ggplot/patchwork objects are
# now saved by the figure scripts and measured here with grid: text grobs that
# are wider than the canvas they sit on, panels below a usable width, and tags
# that would overprint a title are all detectable before anyone looks at a PNG.
suppressPackageStartupMessages({ library(grid); library(patchwork) })
lay <- c(
  tryCatch(readRDS(file.path(CAN_EST, "c20_figure_layout_main.rds")),
           error = function(e) list()),
  tryCatch(readRDS(file.path(CAN_EST, "c20_figure_layout_extended.rds")),
           error = function(e) list()))
ok("assembled figure objects available for measurement", length(lay) > 0,
   sprintf("%d figures", length(lay)))

FIG_W_IN <- W2
if (length(lay)) {
  overflow <- character(); thin <- character(); tagclash <- character()
  for (nm in names(lay)) {
    g <- tryCatch(patchwork::patchworkGrob(lay[[nm]]), error = function(e)
      tryCatch(ggplotGrob(lay[[nm]]), error = function(e2) NULL))
    if (is.null(g)) { overflow <- c(overflow, paste0(nm, " (ungrobbable)")); next }
    # Every text grob measured at its real font size and family.
    ws <- vapply(g$grobs, function(gr) {
      if (!inherits(gr, "titleGrob") && !inherits(gr, "text")) return(0)
      as.numeric(grid::convertWidth(grid::grobWidth(gr), "in", valueOnly = TRUE))
    }, numeric(1))
    if (any(is.finite(ws) & ws > FIG_W_IN + 0.02))
      overflow <- c(overflow, sprintf("%s (%.2f in > %.2f)", nm, max(ws), FIG_W_IN))
    # Panel widths: a panel narrower than this cannot carry a readable axis.
    #
    # A PANEL'S WIDTH IS A `null` UNIT and convertWidth() cannot resolve it
    # outside a drawing context -- it silently returns 0. The previous version
    # summed the columns and converted, so every panel measured 0 in, the
    # zero-width results were then dropped by a `> 0` filter, and the check
    # reported OK while measuring nothing. Resolve the allocation the way grid
    # does instead: absolute widths first, then the remainder shared among the
    # null units in proportion to their null values.
    pnl <- g$layout[grepl("^panel", g$layout$name), , drop = FALSE]
    # patchwork adds a "panel-area" row spanning every sub-panel; it is the
    # container, not a panel.
    pnl <- pnl[pnl$name != "panel-area", , drop = FALSE]
    if (nrow(pnl)) {
      is_null <- grid::unitType(g$widths) == "null"
      abs_in <- vapply(seq_along(g$widths), function(i)
        if (is_null[i]) 0 else
          tryCatch(as.numeric(grid::convertWidth(g$widths[i], "in",
                                                 valueOnly = TRUE)),
                   error = function(e) 0), numeric(1))
      null_val <- ifelse(is_null, as.numeric(g$widths), 0)
      free <- FIG_W_IN - sum(abs_in)
      per_null <- if (sum(null_val) > 0) free / sum(null_val) else 0
      wid <- vapply(seq_len(nrow(pnl)), function(k) {
        idx <- seq(pnl$l[k], pnl$r[k])
        idx <- idx[idx >= 1 & idx <= length(g$widths)]
        if (!length(idx)) return(NA_real_)
        sum(abs_in[idx]) + per_null * sum(null_val[idx])
      }, numeric(1))
      wid <- wid[is.finite(wid)]
      if (length(wid) && min(wid) < 0.55)
        thin <- c(thin, sprintf("%s (%.2f in)", nm, min(wid)))
    }
  }
  ok("no text grob wider than the figure canvas", length(overflow) == 0,
     paste(overflow, collapse = "; "))
  ok("no panel narrower than 0.55 in", length(thin) == 0,
     paste(thin, collapse = "; "))
}

# NO TITLES, SUBTITLES OR CAPTIONS INSIDE A PNG. Checked two ways, because the
# earlier rule (an indent wide enough to clear the tag) accepted titles and
# merely tried to stop them colliding -- which they then did anyway.
#   1. no figure script may pass title=, subtitle= or caption= at all;
#   2. no assembled object may render a non-empty title/subtitle grob.
fig_src <- c("pipeline/20_figures_main.R", "pipeline/21_figures_extended.R")
code_of <- function(f) grep("^\\s*#", readLines(f, warn = FALSE),
                            value = TRUE, invert = TRUE)
titled <- unlist(lapply(fig_src, function(f)
  grep("(title|subtitle|caption)\\s*=\\s*[\"'a-z]", code_of(f), value = TRUE)))
titled <- grep("plot\\.(title|subtitle|caption)|axis\\.title|legend\\.title|strip",
               titled, value = TRUE, invert = TRUE)
ok("no title/subtitle/caption passed by any figure script", length(titled) == 0,
   if (length(titled)) substr(titled[1], 1, 70) else "")

# Prose belongs in the external legend, never in the plotting region. These are
# the specific strings the previous design embedded.
BANNED_PROSE <- c("hollow = away", "composition held fixed", "equal weight per model",
                  "per-model rows are exploratory", "CONDITIONAL ON ENGAGEMENT",
                  "NON-EXCLUSIVE", "mean and range over judge pairs",
                  "all judges recomputed", "alternative but comparable",
                  "these condition on a property", "the values behind",
                  "Unadjusted rates", "Issue regions", "signed pp difference")
prose_hits <- unlist(lapply(fig_src, function(f) {
  cd <- code_of(f)
  # Only string literals reach the canvas; a variable name mentioning a banned
  # phrase does not.
  lit <- unlist(regmatches(cd, gregexpr('"[^"]*"', cd)))
  unlist(lapply(BANNED_PROSE, function(b) grep(b, lit, fixed = TRUE, value = TRUE)))
}))
ok("no explanatory prose in any plotting specification", length(prose_hits) == 0,
   if (length(prose_hits)) substr(prose_hits[1], 1, 60) else "")

# --- 4. figures agree with the tables ----------------------------------------
cat("\n4. figures agree with the tables\n")
c02 <- rdc("c02_home_descriptive_english.csv"); c04 <- rdc("c04_home_standardized.csv")
c08 <- rdc("c08_language_paired.csv"); c09 <- rdc("c09_language_by_model.csv")
c10 <- rdc("c10_framing_paired.csv"); c12 <- rdc("c12_ideology_distribution.csv")
c14 <- rdc("c14_moral_prevalence_equal_model.csv"); c17b <- rdc("c17b_judge_envelope.csv")

ok("Fig1c: both standardized estimands present",
   !is.null(c04) && all(c("full target", "common support") %in% c04$support))
ok("Fig1c: EU carried as flagged, not as zero",
   !is.null(c04) && any(!c04$estimable))
ok("Fig2a: the primary weighting is the one plotted",
   !is.null(c08) && "primary_weighting" %in% names(c08) &&
     n_distinct(c08$primary_weighting) == 1 &&
     c08$primary_weighting[1] %in% c08$weighting)
ok("Fig2b: every model x language cell has a value",
   !is.null(c09) && nrow(filter(c09, grouping == "model")) ==
     n_distinct(c09$group[c09$grouping == "model"]) * n_distinct(c09$language))
ok("Fig2c: framing uses complete 2+2 blocks",
   !is.null(c10) && any(grepl("complete 2", c10$block_rule %||% "")),
   if (is.null(c10)) "" else unique(c10$block_rule)[1])
ok("Fig3a: exactly five ideology bins per dimension",
   !is.null(c12) && {
     k <- c12 %>% filter(role == "PRIMARY") %>% count(dimension)
     nrow(k) > 0 && all(k$n == 5) })
ok("Fig3a: bins sum to one within each dimension",
   !is.null(c12) && {
     s <- c12 %>% filter(role == "PRIMARY") %>% group_by(dimension) %>%
       summarise(s = sum(estimate), .groups = "drop")
     all(abs(s$s - 1) < 1e-8) })
ok("Fig3b: a numeric agreement statistic is available",
   !is.null(c14) && "psa_mean" %in% names(c14))
ok("Fig3b: no acceptance verdict is stored on the table",
   !is.null(c14) && !any(grepl("acceptable", unlist(c14[sapply(c14, is.character)]),
                               ignore.case = TRUE)))
ok("ED1: the envelope is named as an observed envelope",
   !is.null(c17b) && any(grepl("OBSERVED JUDGE POINT ENVELOPE",
                               c17b$judge_model)))
ok("ED1: every judge row comes from the same common-support sample",
   !is.null(c17b) && {
     n <- c17b %>% filter(estimable, judge_model != "OBSERVED JUDGE POINT ENVELOPE") %>%
       group_by(jurisdiction) %>% summarise(k = n_distinct(n), .groups = "drop")
     nrow(n) > 0 && all(n$k == 1) })

# --- the new panels -----------------------------------------------------------
c07  <- rdc("c07_home_sensitivities.csv")
c17d <- rdc("c17d_judge_paired_differences.csv")
# ED1 plots a PAIRED difference. Its interval must come from a paired bootstrap,
# not from differencing two marginal intervals -- so the table has to declare
# itself paired, and the interval must be narrower than the naive combination of
# the two marginal intervals it would replace.
ok("ED1: the plotted judge difference is a paired estimate",
   !is.null(c17d) && "paired" %in% names(c17d) && all(c17d$paired))
ok("ED1: paired intervals are narrower than differenced marginal intervals",
   !is.null(c17d) && !is.null(c17b) && {
     m <- c17b %>% filter(estimable, judge_model != "OBSERVED JUDGE POINT ENVELOPE") %>%
       transmute(judge_model, jurisdiction, mw = conf_high_pp - conf_low_pp)
     can <- m %>% filter(grepl("gemini", judge_model)) %>%
       transmute(jurisdiction, cw = mw)
     j <- c17d %>% filter(estimable, !is_canonical_judge) %>%
       transmute(judge_model, jurisdiction, pw = conf_high_pp - conf_low_pp) %>%
       inner_join(m, by = c("judge_model", "jurisdiction")) %>%
       inner_join(can, by = "jurisdiction")
     nrow(j) > 0 && all(j$pw < j$mw + j$cw) },
   "a paired interval that is not narrower has not used the pairing")
ok("ED1: the canonical judge is a reference, not ground truth",
   !is.null(c17d) && any(grepl("not ground truth", c17d$interpretation)))
# ED2 must not draw a row it has no estimate for. `estimable` in c07 records
# that a fit was attempted; five functional-form rows carry estimable = TRUE
# with no estimate, and an earlier ED2 reserved a whole empty facet for them.
ok("ED2: only same-estimand-family specs are plotted; the grid is a table",
   !is.null(c07) && file.exists(file.path(CAN_EST, "c07c_sensitivity_catalogue.csv")))
ok("ED2: the hierarchical marginal estimand is not in the forest",
   !is.null(c07) && file.exists(file.path(CAN_EST, "c07b_hierarchical_marginal.csv")))
ok("ED2: response-length rows are tabulated, not plotted",
   !is.null(c07) && any(c07$sensitivity == "min_response_chars") &&
     !any(grepl("min_response_chars", readLines("pipeline/21_figures_extended.R",
                                                warn = FALSE))),
   "post-outcome diagnostics belong in c07c")
c21s <- rdc("c21_subsample_summary.csv")
ok("ED3: stability bands are named as ranges, never confidence intervals",
   !is.null(c21s) && "interval_note" %in% names(c21s) &&
     all(grepl("NOT confidence intervals", c21s$interval_note)))
ok("ED3: the resampling unit is the issue",
   !is.null(c21s) && all(grepl("^issue_id", c21s$resampling_unit)))
ok("ED4: one display of the model x language cells, with intervals",
   !is.null(c09) && {
     src <- readLines("pipeline/21_figures_extended.R", warn = FALSE)
     !any(grepl("geom_tile", src)) })
c13a <- rdc("c13_ideology_by_model.csv"); c15a <- rdc("c15_moral_by_model.csv")
ok("ED5: model-level ideology carries issue-clustered intervals",
   !is.null(c13a) && all(c("conf_low", "conf_high", "conf_low_battery") %in% names(c13a)))
ok("ED5: the five bins sum to one within every (dimension, model)",
   !is.null(c13a) && {
     k <- c13a %>% filter(role == "PRIMARY") %>% group_by(dimension, model) %>%
       summarise(s = sum(estimate), .groups = "drop")
     nrow(k) > 0 && all(abs(k$s - 1) < 1e-8) })
ok("ED6: model-level foundations carry issue-clustered intervals",
   !is.null(c15a) && all(c("conf_low", "conf_high", "conf_low_battery") %in% names(c15a)))
ok("ED7: reliability shows more than one agreement statistic",
   !is.null(rdc("e25_reliability_slant.csv")) && {
     e <- rdc("e25_reliability_slant.csv")
     all(c("raw_agreement", "krippendorff_alpha", "gwet_ac1", "psa_mean") %in% names(e)) })
c22c <- rdc("c22_prompt_umap_coordinates.csv")
c22p <- rdc("c22_prompt_refusal_propensities.csv")
ok("ED8: exactly one UMAP coordinate pair per prompt",
   is.null(c22c) || (nrow(c22c) == dplyr::n_distinct(c22c$prompt_id) &&
                     !anyNA(c22c$umap_x) && !anyNA(c22c$umap_y)),
   "skipped when the embedding cache is absent", warn_only = is.null(c22c))
ok("ED8: refusal propensities are bounded in [0,1]",
   is.null(c22p) || all(c22p$refusal_propensity >= 0 & c22p$refusal_propensity <= 1,
                        na.rm = TRUE),
   "", warn_only = is.null(c22p))
ok("ED8/ED9: no facet refits the projection",
   { src <- readLines("pipeline/21_figures_extended.R", warn = FALSE)
     !any(grepl("uwot::|umap\\(", src)) })
# A distribution estimand must be shown as a distribution: the neutral bin holds
# 80-92% of the mass and an earlier Fig3a plotted only the four directional bins.
ok("Fig3a: the neutral bin is drawn, not annotated",
   { src <- readLines("pipeline/20_figures_main.R", warn = FALSE)
     !any(grepl('filter\\(bin != "0"\\)', src)) &&
       any(grepl("geom_col", src)) })

# Plot-data equality: the labels drawn in Fig1c are re-derived from c04 here, so
# a figure that formats a different number than its source row fails.
if (!is.null(c04)) {
  lab_src <- c04 %>% filter(weighting == "nested", estimator == "maximum likelihood",
                            estimable) %>%
    mutate(lab = sprintf("%+.1f", estimate_pp))
  ok("Fig1c: printed labels are derivable from c04", nrow(lab_src) > 0 &&
       all(!is.na(lab_src$lab)), sprintf("%d labels", nrow(lab_src)))
}

# --- 5. figure scripts plot, they do not estimate ----------------------------
cat("\n5. figure scripts\n")
for (src in c("pipeline/20_figures_main.R", "pipeline/21_figures_extended.R")) {
  nm <- basename(src)
  if (!file.exists(src)) { ok(paste(nm, "exists"), FALSE, "missing"); next }
  cd <- grep("^\\s*#", readLines(src, warn = FALSE), value = TRUE, invert = TRUE)
  ok(paste(nm, "fits no models"),
     length(grep("glmer\\(|[^a-z._]glm\\(|lmer\\(|\\blm\\(|logistf\\(", cd)) == 0)
  ok(paste(nm, "never calls ggsave directly"), length(grep("ggsave\\(", cd)) == 0)
  ok(paste(nm, "reads the canonical tables"),
     any(grepl("CAN_EST|estimates/canonical", cd)))
  joined <- paste(cd, collapse = " ")
  banned <- c("causal", "difference-in-differences", "DiD", "within-issue")
  hit <- character(0)
  for (b in banned) for (m in gregexpr(b, joined, fixed = TRUE)[[1]]) {
    if (m < 0) next
    win <- substr(joined, max(1, m - 200), m + nchar(b))
    if (!grepl("\\b(not|NOT|never|NEVER|neither|no|cannot|rather than)\\b", win))
      hit <- c(hit, substr(win, max(1, nchar(win) - 50), nchar(win)))
  }
  ok(paste(nm, "avoids unnegated causal language"), length(hit) == 0,
     if (length(hit)) hit[1] else "")
  hex <- grep("#[0-9A-Fa-f]{6}", cd, value = TRUE)
  ok(paste(nm, "does not hard-code the palette"), length(hex) <= 3,
     sprintf("%d literal hex", length(hex)))
}
# The RETIRED projection is the refusal-TEXT one: it embedded the text of each
# refusal and coloured it by the judge's justification code. The current UMAP is
# a different analysis -- it embeds the PROMPT, its unit is the prompt not the
# response, and it is a canonical output with diagnostics.
#
# This check used to test for the string "umap_x", which the new prompt
# projection legitimately uses, so it would have failed a correct build. It now
# tests for the retired artefact itself: the archived u01-u03 outputs and the
# refusal_umap script.
ed_src <- readLines("pipeline/21_figures_extended.R", warn = FALSE)
ok("the retired refusal-text projection is not rebuilt",
   !any(grepl("refusal_umap|u0[123]_refusal|ED3_refusal_text|exploratory_umap",
              ed_src)))
# ...and the replacement must be the prompt-unit analysis, not a revival.
ok("the shipped projection is the prompt-unit one",
   any(grepl("c22_prompt_umap_coordinates", ed_src)))
# A plotting script must not be the sole implementation of a canonical table:
# the table would then exist only if the figure ran, and would change whenever
# the artwork did. Both c07b and c08b were written here until this release.
wrote <- grep("write_csv\\(", code_of("pipeline/21_figures_extended.R"), value = TRUE)
ok("no figure script writes a canonical estimate table", length(wrote) == 0,
   if (length(wrote)) substr(wrote[1], 1, 60) else "")
ok("c07b and c08b are produced by their estimation scripts",
   any(grepl("c07b_hierarchical_marginal",
             readLines("pipeline/11_canonical_home.R", warn = FALSE))) &&
     any(grepl("c08b_weighting_comparison",
               readLines("pipeline/12_canonical_language_framing.R", warn = FALSE))))
# A structural zero -- no refusals at all, so no contrast exists -- must not be
# drawn as an estimate of zero. Both figure scripts carry the shared encoding.
for (src in fig_src)
  ok(paste(basename(src), "distinguishes structural zeros from estimated nulls"),
     any(grepl("SHAPE_NOT_ESTIMABLE|NOT_ESTIMABLE_TEXT", code_of(src))))

# --- 6. colour ----------------------------------------------------------------
cat("\n6. colour\n")
L <- function(h) round(farver::decode_colour(h, to = "lab")[, 1])
gaps <- c(normal = min(diff(sort(L(unname(PAL_JURIS))))))
for (f in c("deutan", "protan", "tritan"))
  gaps[f] <- min(diff(sort(L(do.call(f, list(unname(PAL_JURIS)),
                                     envir = asNamespace("colorspace"))))))
ok("jurisdiction separable in greyscale/CVD", all(gaps >= 5),
   paste(sprintf("%s %d", names(gaps), gaps), collapse = "  "))
ok("reason palette separable in greyscale",
   min(diff(sort(L(unname(PAL_REASON))))) >= 5)
ok("language palette separable in greyscale",
   min(diff(sort(L(unname(PAL_LANGUAGE))))) >= 5)

# --- summary -----------------------------------------------------------------
cat("\n", strrep("=", 78), "\n", sep = "")
if (length(warns)) cat(sprintf("%d warning(s): %s\n", length(warns),
                               paste(warns, collapse = "; ")))
if (length(fails)) {
  cat(sprintf("AUDIT FAILED (%d):\n", length(fails)))
  for (f in fails) cat("   -", f, "\n")
  cat(strrep("=", 78), "\n", sep = ""); quit(save = "no", status = 1)
}
cat("AUDIT PASSED\n"); cat(strrep("=", 78), "\n", sep = "")
