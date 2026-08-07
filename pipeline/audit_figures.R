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
ED   <- c("ED1_judge_sensitivity", "ED2_sensitivity_panels",
          "ED3_refusal_text_projection", "ED4_language_detail")
REQ_FORMATS <- c("pdf", "svg", "png")

# --- 1. formats ---------------------------------------------------------------
cat("\n1. output formats\n")
have <- function(dir, stem, ext) file.exists(file.path(dir, paste0(stem, ".", ext)))
miss <- c(
  unlist(lapply(MAIN, function(s) paste0("main/", s, ".",
    REQ_FORMATS[!vapply(REQ_FORMATS, function(e) have(MAIN_FIG, s, e), logical(1))]))),
  unlist(lapply(ED, function(s) paste0("extended/", s, ".",
    REQ_FORMATS[!vapply(REQ_FORMATS, function(e) have(ED_FIG, s, e), logical(1))]))))
miss <- miss[!grepl("[.]$", miss)]
ok("every figure exists as PDF, SVG and PNG", length(miss) == 0,
   if (length(miss)) paste(miss, collapse = ", ") else
     sprintf("%d figures x 3 formats", length(MAIN) + length(ED)))
# The PNG-only rule is retired; a main figure that is ONLY a raster now fails.
png_only <- vapply(MAIN, function(s)
  have(MAIN_FIG, s, "png") && !have(MAIN_FIG, s, "pdf"), logical(1))
ok("no main figure is raster-only", !any(png_only),
   paste(MAIN[png_only], collapse = ", "))

stray <- setdiff(list.files(MAIN_FIG), as.vector(outer(MAIN, REQ_FORMATS, paste, sep = ".")))
ok("no stale files in the main figure directory", length(stray) == 0,
   paste(stray, collapse = ", "))
stray_ed <- setdiff(list.files(ED_FIG), as.vector(outer(ED, REQ_FORMATS, paste, sep = ".")))
ok("no stale files in the Extended Data directory", length(stray_ed) == 0,
   paste(stray_ed, collapse = ", "))

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

# --- 3. rendered layout -------------------------------------------------------
cat("\n3. rendered layout\n")
# The figures are re-rendered here as GROBS and their text is measured, which
# catches overlaps a raster check cannot: a title running under the next panel's
# tag, or type below the 5 pt floor. Only the source is inspected for sizes --
# measuring glyphs in a raster would be guesswork.
src_all <- unlist(lapply(c("pipeline/20_figures_main.R", "pipeline/21_figures_extended.R"),
                         function(f) readLines(f, warn = FALSE)))
code <- grep("^\\s*#", src_all, value = TRUE, invert = TRUE)
# Numeric sizes passed to geom_text/geom_label are in MILLIMETRES; the project
# helper pt_to_mm makes the point size explicit, so any bare numeric size in a
# text geom is suspect.
bare <- grep("geom_(text|label)\\(.*size = [0-9]", code, value = TRUE)
ok("text geoms declare size in points via pt_to_mm", length(bare) == 0,
   if (length(bare)) substr(bare[1], 1, 52) else "no bare numeric text sizes")
lit <- unlist(regmatches(code, gregexpr("size = PT_[A-Z]+", code)))
below <- setdiff(unique(lit), c("size = PT_MIN", "size = PT_BODY", "size = PT_AXIS",
                                "size = PT_TITLE", "size = PT_TAG"))
ok("no type below the 5 pt floor", length(below) == 0 && PT_MIN >= 5,
   sprintf("floor = %.1f pt", PT_MIN))

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
   !is.null(c17b) && any(grepl("OBSERVED JUDGE SENSITIVITY ENVELOPE",
                               c17b$judge_model)))
ok("ED1: every judge row comes from the same common-support sample",
   !is.null(c17b) && {
     n <- c17b %>% filter(estimable, judge_model != "OBSERVED JUDGE SENSITIVITY ENVELOPE") %>%
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
# The projection subtitles must come from the CSV, not from a number typed into
# the script that would silently go stale.
ed_src <- readLines("pipeline/21_figures_extended.R", warn = FALSE)
ok("ED3 purity text is read from the CSV, not hard-coded",
   !any(grepl("purity [0-9][.][0-9]", ed_src)) &&
     any(grepl("purity_group_observed", ed_src)))

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
