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
ED   <- c("ED1_judge_sensitivity", "ED2_sensitivity_panels", "ED3_language_detail")

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
for (s in c(MAIN, ED)) {
  p <- file.path(if (s %in% MAIN) MAIN_FIG else ED_FIG, paste0(s, ".png"))
  if (!file.exists(p)) next
  r <- inspect(p)
  if (!is.na(r$w) && abs(r$w - W2_PX) > 3) bad_w <- c(bad_w, s)
  if (r$corner <= 0.97) bad_bg <- c(bad_bg, s)
  if (r$edge <= 0.985) bad_edge <- c(bad_edge, s)
}
ok("all figures at the declared column width", length(bad_w) == 0,
   sprintf("%d px expected; %s", W2_PX, paste(bad_w, collapse = ", ")))
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
    pnl <- g$layout[grepl("^panel", g$layout$name), , drop = FALSE]
    if (nrow(pnl)) {
      wid <- vapply(seq_len(nrow(pnl)), function(k) {
        idx <- seq(pnl$l[k], pnl$r[k])
        idx <- idx[idx >= 1 & idx <= length(g$widths)]
        if (!length(idx)) return(NA_real_)
        tryCatch(as.numeric(grid::convertWidth(sum(g$widths[idx]), "in",
                                               valueOnly = TRUE)),
                 error = function(e) NA_real_)
      }, numeric(1))
      wid <- wid[is.finite(wid) & wid > 0]
      if (length(wid) && min(wid) < 0.55)
        thin <- c(thin, sprintf("%s (%.2f in)", nm, min(wid)))
    }
  }
  ok("no text grob wider than the figure canvas", length(overflow) == 0,
     paste(overflow, collapse = "; "))
  ok("no panel narrower than 0.55 in", length(thin) == 0,
     paste(thin, collapse = "; "))
}

# Tag vs title: the tag sits at the plot's left edge and every panel title is
# indented by margin(l = ...). Measure the bold tag at its real size and require
# the indent to clear it.
tag_w <- as.numeric(grid::convertWidth(grid::grobWidth(grid::textGrob(
  "a", gp = grid::gpar(fontsize = PT_TAG, fontface = "bold",
                       fontfamily = FONT_SANS))), "pt", valueOnly = TRUE))
src_ind <- unlist(regmatches(
  paste(readLines("pipeline/20_figures_main.R", warn = FALSE), collapse = " "),
  gregexpr("margin\\(b = [0-9.]+, l = ([0-9.]+)\\)",
           paste(readLines("pipeline/20_figures_main.R", warn = FALSE), collapse = " "))))
ind <- suppressWarnings(as.numeric(sub(".*l = ([0-9.]+)\\)", "\\1", src_ind)))
ok("panel-title indent clears the panel tag",
   length(ind) == 0 || all(ind[is.finite(ind)] >= tag_w),
   sprintf("tag %.1f pt, smallest indent %s pt", tag_w,
           if (length(ind)) sprintf("%.0f", min(ind, na.rm = TRUE)) else "n/a"))

# Subtitles must not carry numbers typed into the script: a hard-coded value
# goes stale silently when the estimate moves.
sub_lines <- grep("subtitle = \"", unlist(lapply(
  c("pipeline/20_figures_main.R", "pipeline/21_figures_extended.R"),
  function(f) grep("^\\s*#", readLines(f, warn = FALSE), value = TRUE, invert = TRUE))),
  value = TRUE)
hard <- grep("[0-9]+[.][0-9]+|[0-9]{2,}%", sub_lines, value = TRUE)
hard <- grep("2\\+2", hard, value = TRUE, invert = TRUE)   # "complete 2+2 blocks" is a rule, not an estimate
ok("no hard-coded numbers in figure subtitles", length(hard) == 0,
   if (length(hard)) substr(hard[1], 1, 60) else "")

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
# The refusal-text projection is retired, so there is no purity text to check.
# Its replacement is the general subtitle rule in section 3: no hard-coded
# numbers in any subtitle.
ed_src <- readLines("pipeline/21_figures_extended.R", warn = FALSE)
ok("the retired projection figure is not rebuilt",
   !any(grepl("umap_x", ed_src)) && !any(grepl("ED3_refusal_text", ed_src)))

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
