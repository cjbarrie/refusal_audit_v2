# =============================================================================
# Technical reference: docs/r_pipeline/audit_figures.md
# RASTER AND TABLE-FIGURE AUDIT -- v2.4 supported inventory
# =============================================================================
# Reads finished PNGs, layout RDS objects and source tables. It never estimates,
# renders, annotates or calls a provider. Any failed check exits non-zero.

source("pipeline/_theme.R")
suppressPackageStartupMessages(library(tidyverse))
CAN_EST <- Sys.getenv("CANON_EST_DIR", "pipeline/estimates/canonical")
MAIN <- Sys.getenv("CANON_FIG_DIR", "pipeline/figures/main")
EXT <- Sys.getenv("CANON_APPFIG_DIR", "pipeline/figures/extended")
checks <- list()
ok <- function(name, pass, detail = "") {
  pass <- isTRUE(pass)
  checks[[length(checks) + 1L]] <<- tibble(
    check = name, status = if (pass) "PASS" else "FAIL", detail = detail)
  cat(sprintf("[%s] %s%s\n", if (pass) "PASS" else "FAIL", name,
              if (nzchar(detail)) paste0(" -- ", detail) else ""))
}

main_expected <- c("Fig1_jurisdiction_refusal_atlas_home.png",
                   "Fig2_language_refusal_atlas_contrasts.png")
ext_expected <- c(
  "ED1_home_absolute_risks_genuine_refusal.png",
  "ED2_home_absolute_risks_capability_failure.png",
  "ED3_language_absolute_rates_genuine_refusal.png",
  "ED4_language_absolute_rates_capability_failure.png",
  "ED5_measurement_reclassification.png",
  "ED6_annotation_component_profile.png",
  "ED7_model_specific_contrasts_genuine_refusal.png",
  "ED8_model_specific_contrasts_capability_failure.png",
  "ED9_content_fingerprint_genuine_refusal.png",
  "ED10_content_fingerprint_capability_failure.png",
  "ED11_prompt_distribution_genuine_refusal.png",
  "ED12_prompt_distribution_capability_failure.png")
if (file.exists(file.path(CAN_EST, "c22_prompt_umap_coordinates.csv")))
  ext_expected <- c(ext_expected,
    "ED13_capability_failure_semantic_atlas.png",
    "ED14_genuine_refusal_semantic_atlas_by_model.png")

main_found <- sort(list.files(MAIN, pattern = "[.]png$"))
ext_found <- sort(list.files(EXT, pattern = "[.]png$"))
ok("exact main PNG inventory", identical(sort(main_expected), main_found),
   paste(main_found, collapse = ", "))
ok("exact extended PNG inventory", identical(sort(ext_expected), ext_found),
   paste(ext_found, collapse = ", "))
non_png <- c(list.files(MAIN, pattern = "[.](svg|pdf|eps)$", ignore.case = TRUE),
             list.files(EXT, pattern = "[.](svg|pdf|eps)$", ignore.case = TRUE))
ok("PNG only", !length(non_png), paste(non_png, collapse = ", "))
all_png <- c(file.path(MAIN, main_found), file.path(EXT, ext_found))
ok("every PNG is nonempty", length(all_png) > 0 && all(file.info(all_png)$size > 10000))

layouts <- c(file.path(CAN_EST, "c20_figure_layout_main.rds"),
             file.path(CAN_EST, "c20_figure_layout_extended.rds"))
ok("both structural layout artifacts exist", all(file.exists(layouts)))
if (all(file.exists(layouts))) {
  grobs <- c(readRDS(layouts[1]), readRDS(layouts[2]))
  titles <- vapply(grobs, function(g)
    !is.null(g$labels$title) || !is.null(g$labels$subtitle) || !is.null(g$labels$caption),
    logical(1))
  ok("no plot title, subtitle, or caption inside artwork", !any(titles),
     paste(names(titles)[titles], collapse = ", "))
}

c04 <- read_csv(file.path(CAN_EST, "c04_home_standardized.csv"), show_col_types = FALSE)
c08 <- read_csv(file.path(CAN_EST, "c08_language_paired.csv"), show_col_types = FALSE)
main_home_n <- c04 %>% filter(outcome == "genuine_refusal") %>% count(outcome)
main_lang_n <- c08 %>% filter(outcome == "genuine_refusal") %>% count(outcome)
ok("main home outcome has exactly five jurisdiction rows",
   nrow(main_home_n) == 1L && main_home_n$n == 5L)
unreliable_home <- c04 %>% filter(estimable, !interval_reliable)
main_code <- paste(readLines("pipeline/20_figures_main.R", warn = FALSE),
                   collapse = "\n")
ok("unreliable home intervals are not drawn as ordinary intervals",
   all(!is.na(c04$interval_reliable[c04$estimable])) &&
     grepl('filter(adjusted, interval_reliable)', main_code, fixed = TRUE),
   if (nrow(unreliable_home))
     paste(unreliable_home$jurisdiction, unreliable_home$outcome, collapse = ", ")
   else "all current aggregate intervals are reliable")
home_model <- read_csv(file.path(CAN_EST, "c05_home_by_model.csv"),
                       show_col_types = FALSE) %>%
  filter(outcome == "genuine_refusal", estimable, interval_reliable)
ok("main home axis contains every reliable refusal interval",
   all(home_model$conf_low_pp >= -15 & home_model$conf_high_pp <= 25) &&
     grepl("HOME_X_LIMITS <- c(-15, 25)", main_code, fixed = TRUE),
   sprintf("observed interval range %.2f to %.2f pp",
           min(home_model$conf_low_pp), max(home_model$conf_high_pp)))
ok("main language outcome has exactly four contrast rows",
   nrow(main_lang_n) == 1L && main_lang_n$n == 4L)

plot_lines <- c(readLines("pipeline/20_figures_main.R", warn = FALSE),
                readLines("pipeline/21_figures_extended.R", warn = FALSE))
# Audit executable code, not explanatory comments. The headers deliberately say
# that slant and moral-foundation figures are pending; treating that sentence as
# an active reference would make the gate fail for documenting the exclusion.
plot_code <- paste(plot_lines[!grepl("^\\s*#", plot_lines)], collapse = "\n")
ok("figure scripts fit no statistical model",
   !grepl("glm\\(|glmer\\(|lm\\(|boot_canon\\(|boot_paired\\(", plot_code))
ok("figure scripts do not write CSV or Parquet",
   !grepl("write_csv\\(|write_parquet\\(", plot_code))
ok("figure scripts do not reference pending content outcomes",
   !grepl("slant|ideolog|moral|foundation|e25_reliability", plot_code,
          ignore.case = TRUE))
ok("refusal and capability failure are not mapped to one aesthetic",
   !grepl("aes\\([^\\n]*(colour|color|fill|shape)\\s*=\\s*(outcome|outcome_label)",
          plot_code))
main_exec <- readLines("pipeline/20_figures_main.R", warn = FALSE)
main_exec <- paste(main_exec[!grepl("^\\s*#", main_exec)], collapse = "\n")
ok("capability failure is absent from main artwork",
   !grepl("capability_failure", main_exec, fixed = TRUE))
ok("main jurisdiction atlas preserves exact multi-model membership",
   grepl("make_wedges", main_exec, fixed = TRUE) &&
     grepl("fill = model", main_exec, fixed = TRUE))
ok("figure scripts contain no explanatory text annotations",
   !grepl("geom_text\\(|annotate\\(", plot_code))

result <- bind_rows(checks)
cat(sprintf("\nFigure audit: %d/%d passed\n", sum(result$status == "PASS"), nrow(result)))
if (any(result$status == "FAIL")) quit(save = "no", status = 1)
