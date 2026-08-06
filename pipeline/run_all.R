# =============================================================================
# run_all.R -- the analysis driver
# =============================================================================
# Runs the whole R layer in dependency order, in one command.
#
#   Rscript pipeline/run_all.R                        # full run dir from env/default
#   REFUSAL_RUN_DIR=annotations/full_v1 Rscript pipeline/run_all.R
#   Rscript pipeline/run_all.R --run-dir annotations/full_v1
#   Rscript pipeline/run_all.R --figures              # skip re-loading, redraw only
#   Rscript pipeline/run_all.R --only 11,15           # a named subset
#   Rscript pipeline/run_all.R --list                 # show the plan, run nothing
#
# WHY A DRIVER. The scripts have a real dependency order that is not obvious from
# the numbering: 01 writes data_clean.RData that every other script loads, and
# several figure scripts read CSVs that earlier table scripts write. Running them
# by hand in the wrong order fails in ways that look like data problems.
#
# Each script runs in a SEPARATE R process. They are not sourced into one
# session, because several call setwd(), define clashing helpers, and load
# data_clean.RData into the global environment -- sourcing them together would
# let one script's leftovers silently satisfy another's missing object.
#
# A failing script does NOT stop the run. The summary at the end reports every
# script's status, so one broken figure does not hide the state of the other
# fourteen. Exit status is non-zero if anything failed, so CI or a shell && chain
# still notices.

args <- commandArgs(trailingOnly = TRUE)

get_flag <- function(name, default = NULL) {
  i <- match(name, args)
  if (!is.na(i) && length(args) > i) return(args[i + 1])
  default
}
has_flag <- function(name) name %in% args

run_dir <- get_flag("--run-dir", Sys.getenv("REFUSAL_RUN_DIR", "annotations/pilot_v1"))
Sys.setenv(REFUSAL_RUN_DIR = run_dir)

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())

# -----------------------------------------------------------------------------
# The plan. `needs_load` marks scripts that read data_clean.RData.
# -----------------------------------------------------------------------------
PLAN <- list(
  list(id = "01", file = "01_data_loading.R",              stage = "load",
       what = "read run dir, derive engaged/refused + factors, write data_clean.RData"),
  list(id = "02", file = "02_engagement_analysis.R",        stage = "tables",
       what = "engagement by model x language; logistic interaction model"),
  list(id = "06", file = "06_refusal_justifications.R",     stage = "tables",
       what = "refusal justification A-G composition"),
  list(id = "07", file = "07_deepseek_language_analysis.R", stage = "tables",
       what = "DeepSeek language tables 35, 36, 38"),
  list(id = "08", file = "08_deepseek_chinese_analysis.R",  stage = "tables",
       what = "DeepSeek zh-vs-en chi-squared, mixed model, figs 22-23"),
  list(id = "09", file = "09_deepseek_stats.R",             stage = "tables",
       what = "bootstrap ORs, Cramer's V, BH-corrected p-values"),
  list(id = "24", file = "24_measurement.R",                  stage = "estimates",
       what = "judge-panel reliability + measurement robustness (e23-e28); feeds c17"),
  list(id = "16", file = "16_irr_analysis.R",               stage = "irr",
       what = "RETIRED stub; superseded by 24_measurement.R"),
  # Self-skips unless scripts/refusal_umap.py has written its coordinates: the
  # projection is computed in Python and this script only draws it.
  list(id = "57", file = "57_refusal_umap_figure.R",        stage = "figures",
       what = "UMAP of refusal text (P15); needs scripts/refusal_umap.py first")
)

# NOT IN THIS PLAN. The estimand and figure layers -- v1's 20/21/22/23/25/30 and
# v2's 40-47 -- have been superseded by the canonical layer and moved to
# pipeline/archive/ (see pipeline/archive/README.md for the file-by-file
# mapping). Headline estimates and figures now come from:
#
#     Rscript pipeline/run_canonical.R
#
# This driver still runs what the canonical layer depends on or does not cover:
# the data build (01), the descriptive/case-study tabulations (02, 06-09), and
# the judge-panel reliability tables (24) that 54_canonical_measurement.R reads.

only <- get_flag("--only")
if (!is.null(only)) {
  keep <- trimws(strsplit(only, ",")[[1]])
  PLAN <- Filter(function(s) s$id %in% keep, PLAN)
}
if (has_flag("--figures")) {
  # Redraw only. 01 is excluded deliberately: --figures exists precisely for
  # iterating on figure code without paying to rebuild data_clean.RData.
  PLAN <- Filter(function(s) s$stage == "figures", PLAN)
}

if (has_flag("--list")) {
  cat(sprintf("run dir: %s\n\n", run_dir))
  for (s in PLAN) cat(sprintf("  %-3s %-34s %s\n", s$id, s$file, s$what))
  quit(save = "no", status = 0)
}

# data_clean.RData must exist for anything past the load stage.
if (!any(vapply(PLAN, function(s) s$stage == "load", logical(1))) &&
    !file.exists("pipeline/data_clean.RData")) {
  cat("ERROR: pipeline/data_clean.RData is absent and 01 is not in this plan.\n")
  cat("       Run without --figures/--only first, or run 01 explicitly.\n")
  quit(save = "no", status = 1)
}

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
rule <- function(ch = "=") cat(strrep(ch, 78), "\n", sep = "")
rule(); cat("R ANALYSIS PIPELINE\n"); rule()
cat(sprintf("run dir : %s\n", run_dir))
cat(sprintf("scripts : %d\n", length(PLAN)))
cat(sprintf("started : %s\n\n", format(Sys.time(), "%Y-%m-%d %H:%M:%S")))

rscript <- file.path(R.home("bin"), "Rscript")
results <- list()

for (s in PLAN) {
  cat(sprintf("--- %s  %s\n", s$id, s$file))
  t0 <- Sys.time()
  out <- suppressWarnings(system2(rscript, args = file.path("pipeline", s$file),
                                  stdout = TRUE, stderr = TRUE))
  status <- attr(out, "status")
  secs <- as.numeric(difftime(Sys.time(), t0, units = "secs"))

  # A script that quit(status=0) after printing SKIP has not failed; it has
  # correctly declined to run on inputs this run does not have. Distinguishing
  # the two is the whole point of the summary.
  skipped <- any(grepl("^SKIP|SKIP ", out))
  failed  <- !is.null(status) && status != 0
  n_saved <- sum(grepl("saved ", out))

  results[[s$id]] <- list(id = s$id, file = s$file, secs = secs,
                          state = if (failed) "FAIL" else if (skipped) "skip" else "ok",
                          figs = n_saved,
                          err = if (failed) utils::tail(grep("Error", out, value = TRUE), 2) else character(0))

  cat(sprintf("    %-4s  %5.1fs%s\n", results[[s$id]]$state, secs,
              if (n_saved) sprintf("  (%d figures)", n_saved) else ""))
  if (failed) for (e in results[[s$id]]$err) cat("      ", substr(e, 1, 110), "\n")
}

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
cat("\n"); rule(); cat("SUMMARY\n"); rule()
states <- vapply(results, function(r) r$state, character(1))
for (r in results)
  cat(sprintf("  %-4s %-3s %-34s %6.1fs%s\n", r$state, r$id, r$file, r$secs,
              if (r$figs) sprintf("  %d figures", r$figs) else ""))

n_fail <- sum(states == "FAIL"); n_skip <- sum(states == "skip")
cat(sprintf("\n  %d ok, %d skipped, %d failed   (%.1f min total)\n",
            sum(states == "ok"), n_skip, n_fail,
            sum(vapply(results, function(r) r$secs, numeric(1))) / 60))

figs <- list.files("pipeline/figures", pattern = "\\.png$")
tabs <- list.files("pipeline/tables",  pattern = "\\.csv$")
cat(sprintf("  pipeline/figures : %d PNG\n  pipeline/tables  : %d CSV\n",
            length(figs), length(tabs)))
if (n_skip > 0)
  cat("\n  'skip' means the script declined a missing input (Pass 2 tables, a\n",
      "  second-judge pass, or a Study A/B run). Not an error.\n", sep = "")
rule()

quit(save = "no", status = if (n_fail > 0) 1 else 0)
