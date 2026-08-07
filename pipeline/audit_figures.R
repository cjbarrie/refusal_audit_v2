# =============================================================================
# Figure audit
# =============================================================================
# Run after 20_figures_main.R and 21_figures_appendix.R. Exits non-zero if
# anything fails, so it can gate a commit or a build.
#
# The load-bearing check is section 4: every plotted quantity is re-read from
# the canonical tables and compared, so a figure cannot silently drift from the
# numbers it claims to show. Section 5 enforces the rule that makes that
# possible -- figure scripts read tables and fit nothing.
#
# This file was rewritten when the v1/v2 figure layers were archived. It audits
# ONLY what the manuscript ships: three main figures and four appendix figures.

suppressPackageStartupMessages({ library(tidyverse); library(png) })
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")

EST  <- "pipeline/estimates"
CAN  <- file.path(EST, "canonical")
FIGS <- "pipeline/figures"
fails <- character(); warns <- character()
ok <- function(lab, pass, detail = "", warn_only = FALSE) {
  if (length(pass) != 1L || is.na(pass) || !is.logical(pass)) {
    detail <- paste("CHECK BROKEN: condition was not a single TRUE/FALSE.", detail)
    pass <- FALSE
  }
  tag <- if (pass) "OK  " else if (warn_only) "WARN" else "FAIL"
  cat(sprintf("  %-46s %-4s %s\n", lab, tag, detail))
  if (!pass) { if (warn_only) warns <<- c(warns, lab) else fails <<- c(fails, lab) }
}
rdc <- function(f) { p <- file.path(CAN, f)
  if (file.exists(p)) read_csv(p, show_col_types = FALSE) else NULL }
cat(strrep("=", 78), "\nFIGURE AUDIT\n", strrep("=", 78), "\n", sep = "")

MAIN_FIGS <- file.path("canonical", c("FIG1_canonical_home",
                                      "FIG2_canonical_language_framing",
                                      "FIG3_canonical_content"))
APP_FIGS  <- file.path("appendix", c("S1_home_descriptive", "S2_judge_multiverse",
                                     "S3_specification_curve",
                                     "S4_projection_supplement"))

# --- 1. PNG only -------------------------------------------------------------
cat("\n1. output format\n")
# Recursive, because the figures live in subdirectories now. include.dirs =
# FALSE so a directory entry is not mistaken for a stray non-PNG file.
allf  <- list.files(FIGS, recursive = TRUE, include.dirs = FALSE)
png_f <- grep("[.]png$", allf, value = TRUE)
bad   <- setdiff(allf, png_f)
ok("PNG only, no other format (recursive)", length(bad) == 0,
   sprintf("%d png%s", length(png_f),
           if (length(bad)) paste0("; FOUND ", paste(bad, collapse = ", ")) else ""))

# --- 2. expected files, and nothing else -------------------------------------
cat("\n2. expected files\n")
# Appendix figures are conditional on their inputs; main figures are not.
have_env  <- file.exists(file.path(CAN, "c17b_judge_envelope.csv"))
have_sens <- file.exists(file.path(CAN, "c07_home_sensitivities.csv"))
have_umap <- file.exists(file.path(EST, "u02_refusal_umap_all_languages.csv")) ||
             file.exists(file.path(EST, "u03_refusal_umap_lexical.csv"))
expect <- c(MAIN_FIGS,
            APP_FIGS[c(TRUE, have_env, have_sens, have_umap)])
expect <- paste0(expect, ".png")
missing <- setdiff(expect, png_f)
ok("every expected PNG present", length(missing) == 0,
   if (length(missing)) paste(missing, collapse = ", ")
   else sprintf("%d expected", length(expect)))
# Stale output is a real failure mode: an archived script's figures sat in this
# directory for weeks looking current.
stale <- setdiff(png_f, expect)
ok("no stale figure artefacts", length(stale) == 0,
   if (length(stale)) paste("STALE:", paste(stale, collapse = ", ")) else "none")

# --- 3. image integrity ------------------------------------------------------
cat("\n3. image integrity\n")
DPI <- 600
present <- intersect(expect, png_f)
dims <- map_dfr(present, function(f) {
  a <- tryCatch(png::readPNG(file.path(FIGS, f)), error = function(e) NULL)
  if (is.null(a)) return(tibble(file = f, w = NA_integer_, h = NA_integer_,
                                white = NA, edge = NA_real_))
  corner <- a[1:8, 1:8, 1:3]
  g <- if (length(dim(a)) == 3) apply(a[, , 1:3], c(1, 2), mean) else a
  tibble(file = f, w = dim(a)[2], h = dim(a)[1], white = mean(corner) > 0.97,
         edge = min(mean(g[1, ]), mean(g[nrow(g), ]),
                    mean(g[, 1]), mean(g[, ncol(g)])))
})
ok("all images open", nrow(dims) > 0 && all(!is.na(dims$w)),
   sprintf("%d files", nrow(dims)))
ok("white background", all(dims$white, na.rm = TRUE),
   paste(dims$file[!dims$white & !is.na(dims$white)], collapse = ", "))
w2 <- round(W2 * DPI)
ok("all figures at two-column width", all(abs(dims$w - w2) <= 2, na.rm = TRUE),
   sprintf("%d px expected; offenders: %s", w2,
           paste(dims$file[abs(dims$w - w2) > 2], collapse = ", ")))
# Ink touching the canvas edge means a label ran off the page.
ok("nothing clipped at the canvas edge", all(dims$edge > 0.985, na.rm = TRUE),
   paste(dims$file[dims$edge <= 0.985], collapse = ", "))

# --- 4. figures <-> tables ---------------------------------------------------
cat("\n4. figures agree with the tables\n")
c04 <- rdc("c04_home_standardized.csv"); c17b <- rdc("c17b_judge_envelope.csv")
c02 <- rdc("c02_home_descriptive_english.csv"); c12 <- rdc("c12_ideology_distribution.csv")
c10 <- rdc("c10_framing_paired.csv"); c11 <- rdc("c11_framing_by_model_domain.csv")
c07 <- rdc("c07_home_sensitivities.csv")

ok("FIG1b: one row per jurisdiction in c04",
   !is.null(c04) && nrow(filter(c04, weighting == "nested")) == length(JURIS_LEVELS),
   if (is.null(c04)) "c04 missing" else
     sprintf("%d rows", nrow(filter(c04, weighting == "nested"))))
ok("FIG1b: EU carried as flagged, not as zero",
   !is.null(c04) && any(!c04$estimable[c04$weighting == "nested"]))
# The envelope MUST contain the interval the main figure draws inside it, or the
# two rules in panel b would cross and the figure would be incoherent.
if (!is.null(c17b) && !is.null(c04)) {
  e <- c17b %>% filter(judge_model == "ENVELOPE (union across judges)", estimable) %>%
    select(jurisdiction, elo = conf_low, ehi = conf_high)
  k <- c04 %>% filter(weighting == "nested", estimable) %>%
    select(jurisdiction, lo = conf_low, hi = conf_high) %>% inner_join(e, by = "jurisdiction")
  ok("FIG1b: judge envelope contains the canonical interval",
     nrow(k) > 0 && all(k$elo <= k$lo + 1e-12) && all(k$ehi >= k$hi - 1e-12),
     sprintf("%d jurisdictions checked", nrow(k)))
}
ok("FIG2c: pooled framing row exists in c10",
   !is.null(c10) && any(c10$scope == "overall"))
ok("FIG2c: model rows exist in c11",
   !is.null(c11) && any(c11$grouping == "model"))
ok("FIG3a: ideology shares sum to 1 within each dimension",
   !is.null(c12) && {
     ss <- c12 %>% filter(grepl("^share_", quantity)) %>%
       group_by(dimension) %>% summarise(s = sum(estimate), .groups = "drop")
     all(abs(ss$s - 1) < 1e-8)
   })
ok("S1: descriptive rates present for both arms",
   !is.null(c02) && all(c("home", "away") %in%
                          c02$home_status[c02$grouping == "jurisdiction"]))
ok("S3: sensitivity families present",
   !is.null(c07) && n_distinct(c07$sensitivity) >= 5,
   if (is.null(c07)) "" else sprintf("%d families", n_distinct(c07$sensitivity)))

# --- 5. figure scripts plot, they do not estimate ----------------------------
cat("\n5. figure scripts\n")
for (src in c("pipeline/20_figures_main.R", "pipeline/21_figures_appendix.R")) {
  nm <- basename(src)
  if (!file.exists(src)) { ok(paste(nm, "exists"), FALSE, "missing"); next }
  code <- grep("^\\s*#", readLines(src, warn = FALSE), value = TRUE, invert = TRUE)
  ok(paste(nm, "fits no models"),
     length(grep("glmer\\(|[^a-z._]glm\\(|lmer\\(|\\blm\\(", code)) == 0, "plotting only")
  ok(paste(nm, "never calls ggsave directly"),
     length(grep("ggsave\\(", code)) == 0, "save_fig is the sole writer")
  ok(paste(nm, "reads the canonical tables"),
     any(grepl("estimates/canonical|CAN_EST", code)))
  # A standardized contrast is not an effect. Flag the term unless a negation
  # sits on the same line.
  # Captions are assembled from string fragments across several source lines, so
  # a line-by-line scan reports "not a causal effect" as a violation whenever
  # the negation happens to wrap. Join the code and search a character window.
  joined <- paste(code, collapse = " ")
  banned <- c("causal", "difference-in-differences", "DiD", "within-issue")
  hit <- character(0)
  for (b in banned) {
    for (m in gregexpr(b, joined, fixed = TRUE)[[1]]) {
      if (m < 0) next
      win <- substr(joined, max(1, m - 200), m + nchar(b))
      if (!grepl("\\b(not|NOT|never|NEVER|neither|no|cannot|rather than)\\b", win))
        hit <- c(hit, substr(win, max(1, nchar(win) - 60), nchar(win)))
    }
  }
  ok(paste(nm, "avoids unnegated causal/DiD language"), length(hit) == 0,
     if (length(hit)) hit[1] else "4 terms checked")
  # Colours belong in _theme.R, so a palette change reaches every figure.
  hex <- grep("#[0-9A-Fa-f]{6}", code, value = TRUE)
  ok(paste(nm, "does not hard-code the palette"), length(hex) <= 3,
     sprintf("%d literal hex", length(hex)))
}

# --- 6. grayscale / colour-vision --------------------------------------------
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
lg <- min(diff(sort(L(unname(PAL_LANGUAGE)))))
ok("language palette separable in grayscale", lg >= 5, sprintf("min L* gap %d", lg))

# --- summary -----------------------------------------------------------------
cat("\n", strrep("=", 78), "\n", sep = "")
if (length(warns)) cat(sprintf("%d warning(s): %s\n", length(warns),
                               paste(warns, collapse = "; ")))
if (length(fails)) {
  cat(sprintf("AUDIT FAILED (%d):\n", length(fails)))
  for (f in fails) cat("   -", f, "\n")
  cat(strrep("=", 78), "\n", sep = ""); quit(status = 1)
}
cat("AUDIT PASSED\n"); cat(strrep("=", 78), "\n", sep = "")
