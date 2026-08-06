# =============================================================================
# CANONICAL DRIVER -- runs the whole canonical layer, then reconciles it
# =============================================================================
#   51 home  ->  52 language/framing  ->  53 content  ->  54 measurement
#   -> 55 figures -> 56 acceptance -> c01 reconciliation + c18 flush + manifest
#
# Reads annotations and data_clean.RData; writes only under
# pipeline/estimates/canonical/ and pipeline/figures/canonical/. It calls no
# API and mutates no input.
#
#   Rscript pipeline/run_canonical.R              # everything
#   CANON_ONLY=53,54 Rscript pipeline/run_canonical.R   # a subset, then c01

t0 <- Sys.time()
suppressPackageStartupMessages({ library(tidyverse) })

CAN_EST <- "pipeline/estimates/canonical"
CAN_FIG <- "pipeline/figures/canonical"
dir.create(CAN_EST, showWarnings = FALSE, recursive = TRUE)

STEPS <- tribble(
  ~id, ~script, ~what,
  "51", "pipeline/51_canonical_home.R",              "home-jurisdiction (c02-c07)",
  "52", "pipeline/52_canonical_language_framing.R",  "language + framing (c08-c11)",
  "53", "pipeline/53_canonical_content.R",           "content (c12-c16)",
  "54", "pipeline/54_canonical_measurement.R",       "measurement (c17)",
  "55", "pipeline/55_canonical_figures.R",           "figures (FIG1-3)",
  "56", "pipeline/56_canonical_acceptance.R",        "acceptance tests")

only <- Sys.getenv("CANON_ONLY", "")
if (nzchar(only)) STEPS <- STEPS %>% filter(id %in% trimws(strsplit(only, ",")[[1]]))

# Each part runs in its own R process. They share nothing but the CSVs on disk,
# which is the point: if a canonical number cannot be reproduced from the tables
# alone, the layer is not doing its job.
run_id <- Sys.getenv("CANONICAL_RUN_ID", "")
timings <- list()
for (i in seq_len(nrow(STEPS))) {
  s <- STEPS[i, ]
  cat("\n", strrep("#", 78), "\n# ", s$id, "  ", s$what, "\n", strrep("#", 78), "\n", sep = "")
  ti <- Sys.time()
  st <- system2("Rscript", s$script,
                env = if (nzchar(run_id)) paste0("CANONICAL_RUN_ID=", run_id) else character())
  el <- as.numeric(difftime(Sys.time(), ti, units = "mins"))
  timings[[length(timings) + 1]] <- tibble(step = s$id, script = s$script,
                                           minutes = el, status = st)
  if (st != 0) {
    cat("\nSTEP ", s$id, " FAILED (status ", st, "). Stopping.\n", sep = "")
    quit(status = st)
  }
  cat(sprintf("\n-- %s done in %.1f min\n", s$id, el))
}

# =============================================================================
# c01 -- reconciliation against the superseded v1 and v2 surfaces
# =============================================================================
# Canonical numbers differ from their predecessors, and every difference has a
# reason. This table states the reason next to the numbers so a reader who finds
# an older figure elsewhere can see why it moved, rather than concluding that
# one of them is a mistake.
cat("\n", strrep("#", 78), "\n# c01 reconciliation\n", strrep("#", 78), "\n", sep = "")

rdc <- function(f) { p <- file.path(CAN_EST, f)
  if (file.exists(p)) read_csv(p, show_col_types = FALSE) else NULL }
rde <- function(f) { p <- file.path("pipeline/estimates", f)
  if (file.exists(p)) read_csv(p, show_col_types = FALSE) else NULL }
pick <- function(d, ...) {
  if (is.null(d)) return(NA_real_)
  r <- filter(d, ...); if (!nrow(r)) NA_real_ else r$estimate[1]
}

c04 <- rdc("c04_home_standardized.csv"); c08 <- rdc("c08_language_paired.csv")
c14 <- rdc("c14_moral_prevalence_equal_model.csv")
e01 <- rde("e01_home_premium_primary.csv"); e33 <- rde("e33_home_standardized_equal_weight.csv")
e36 <- rde("e36_language_paired_effects.csv"); e17b <- rde("e17b_moral_pooled.csv")

if (!is.null(e01) && "scale" %in% names(e01) &&
    !all(e01$scale == "probability"))
  stop("e01 is not on the probability scale; the c01 comparison would mix units")

rec <- bind_rows(
  tibble(
    quantity = "CN home - away, standardized",
    canonical = pick(c04, jurisdiction == "CN", weighting == "nested"),
    v2 = pick(e33, jurisdiction == "CN"),
    v1 = pick(e01, jurisdiction == "CN"),
    why_they_differ = paste(
      "All three are on the probability scale, so the numbers are directly",
      "comparable. v1 (e01) is a SAMPLE-CONDITIONAL premium from a hierarchical",
      "model, averaged over the observed issues at the fitted BLUPs, and it is",
      "conditional on the estimated issue effects. It is NOT, despite the label",
      "v1 gave it, a within-issue effect or a difference-in-differences: home",
      "status is a fixed property of an issue's region, so within a jurisdiction",
      "an issue is home or away for a model and no within-issue variation in",
      "home status exists to difference out. v2 moved to a marginal,",
      "covariate-standardized contrast with equal-model weighting; canonical",
      "keeps that estimand, drops region fixed effects (region determines home",
      "within a jurisdiction, so the two are not separately identified), and",
      "preserves issue multiplicity in the bootstrap, which widens the",
      "interval rather than moving the point.")),
  tibble(
    quantity = "Chinese-vs-English paired language difference",
    canonical = pick(c08, language == "zh", sensitivity == "primary",
                     weighting == "pooled"),
    v2 = pick(e36, language == "zh"), v1 = NA_real_,
    why_they_differ = paste(
      "v1 had no paired language estimand at all -- language was read off",
      "unpaired cell rates, which confound language with prompt composition.",
      "Canonical matches v2's block definition; residual differences are the",
      "bootstrap multiplicity repair only.")),
  tibble(
    quantity = "Care / harm prevalence, equal-model",
    canonical = pick(c14, foundation == "Care / harm", scope == "overall"),
    v2 = NA_real_,
    v1 = if (is.null(e17b)) NA_real_ else
      { r <- filter(e17b, field == "care_harm"); if (nrow(r)) r$equal_model[1] else NA_real_ },
    why_they_differ = paste(
      "same estimand, same equal-model weighting, and the same slant subsample,",
      "so the points agree to the digit shown; canonical adds a bootstrap",
      "interval to every point, a finite-battery interval alongside the",
      "superpopulation one, and per-foundation judge agreement, which is what",
      "downgrades the four rarest foundations to low_agreement_flag."))
) %>%
  mutate(canonical_pp = 100 * canonical, v2_pp = 100 * v2, v1_pp = 100 * v1,
         canonical_run_id = Sys.getenv("CANONICAL_RUN_ID", "unset"),
         note = "v1/v2 rows are retained for provenance only; they are superseded")
write_csv(rec, file.path(CAN_EST, "c01_reconciliation.csv"))
print(as.data.frame(rec %>% select(quantity, canonical_pp, v2_pp, v1_pp)),
      digits = 3, row.names = FALSE)

# =============================================================================
# manifest
# =============================================================================
tb <- tibble(file = list.files(CAN_EST, pattern = "\\.csv$"))
tb <- tb %>% mutate(
  path = file.path(CAN_EST, file),
  rows = map_int(path, ~ nrow(read_csv(.x, show_col_types = FALSE))),
  bytes = file.size(path),
  run_id = map_chr(path, function(p) {
    x <- read_csv(p, show_col_types = FALSE)
    if ("canonical_run_id" %in% names(x)) paste(unique(x$canonical_run_id), collapse = ",")
    else NA_character_ }))
fg <- tibble(file = list.files(CAN_FIG), path = file.path(CAN_FIG, list.files(CAN_FIG))) %>%
  mutate(rows = NA_integer_, bytes = file.size(path), run_id = NA_character_)

man <- bind_rows(tb, fg) %>%
  mutate(canonical_run_id = Sys.getenv("CANONICAL_RUN_ID", "unset"),
         generated_at = format(Sys.time(), "%Y-%m-%d %H:%M:%S"),
         git_commit = tryCatch(system2("git", c("rev-parse", "--short", "HEAD"),
                                       stdout = TRUE)[1],
                               error = function(e) NA_character_),
         r_version = paste(R.version$major, R.version$minor, sep = "."))
write_csv(man, file.path(CAN_EST, "c00_manifest.csv"))
# Stamped like every other table: the acceptance tests require one run id per
# estimate table, and an unstamped file in the same directory fails that check.
write_csv(bind_rows(timings) %>%
            mutate(canonical_run_id = Sys.getenv("CANONICAL_RUN_ID", "unset")),
          file.path(CAN_EST, "c00_timings.csv"))

cat("\n", strrep("=", 78), "\n", sep = "")
cat(sprintf("CANONICAL LAYER COMPLETE in %.1f min -- %d tables, %d figures\n",
            as.numeric(difftime(Sys.time(), t0, units = "mins")), nrow(tb), nrow(fg)))
cat(strrep("=", 78), "\n", sep = "")
