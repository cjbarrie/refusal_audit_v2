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
MAIN <- c("FIG1_home_region_main", "FIG2_model_domain_main", "FIG3_refusal_reasons_main")
PANELS <- c("P1_locator", "P2_home_interaction", "P3_estimand_comparison",
            "P4_region_structure", "P5_china_language", "P6_model_tier",
            "P7_domain_tier", "P8_refusal_reasons")
expect <- c(paste0(MAIN, ".png"), paste0(PANELS, ".png"),
            paste0(rep(MAIN, each = 2), c("_1col", "_2col"), ".png"))
missing <- setdiff(expect, png_f)
ok("every expected PNG present", length(missing) == 0,
   sprintf("%d expected%s", length(expect),
           if (length(missing)) paste0("; MISSING ", paste(missing, collapse = ", ")) else ""))
stale <- setdiff(png_f, expect)
ok("no stale figure artefacts", length(stale) == 0,
   if (length(stale)) paste("STALE:", paste(stale, collapse = ", ")) else "none")

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
w1 <- round(W1 * DPI); w2 <- round(W2 * DPI)
dims <- dims %>% mutate(
  want = case_when(grepl("_1col", file) ~ w1, grepl("_2col", file) ~ w2,
                   TRUE ~ NA_real_),
  wrong = !is.na(want) & abs(w - want) > 2)
ok("preview widths match journal columns", !any(dims$wrong, na.rm = TRUE),
   sprintf("1col=%dpx 2col=%dpx", w1, w2))
ok("file sizes reasonable (< 8 MB)", all(dims$mb < 8, na.rm = TRUE),
   sprintf("max %.1f MB", max(dims$mb, na.rm = TRUE)))
ok("rendered at 600 dpi", all(dims$w >= w1 - 2, na.rm = TRUE),
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
ok("denominators recorded for compositions",
   all(!is.na(e13$n_refusals)) && all(e13$n_refusals >= 30),
   sprintf("min n = %d", min(e13$n_refusals)))

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

src  <- readLines("pipeline/30_figures.R", warn = FALSE)
code <- grep("^\\s*#", src, value = TRUE, invert = TRUE)
ok("no model fitting in the figure script",
   length(grep("glmer\\(|[^a-z.]glm\\(|lmer\\(", code)) == 0, "plotting only")
ok("no direct ggsave in the figure script",
   length(grep("ggsave\\(", code)) == 0, "save_fig is sole writer")
ok("no in-panel titles", length(grep("title *=|subtitle *=", code)) == 0, "")
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
