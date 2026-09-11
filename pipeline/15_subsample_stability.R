# =============================================================================
# Technical reference: docs/r_pipeline/15_subsample_stability.md
# ISSUE-SUBSAMPLE STABILITY -- v2.4 outcome analyses only
# =============================================================================
# This is a design sensitivity exercise. For each declared percentage, sample
# issue IDs without replacement and carry every model/language/prompt response
# for those issues into the draw. Recompute simple versions of the home,
# language and framing headline quantities for genuine refusal and capability
# failure. Quantiles across repeated subsets are stability ranges, not CIs.
# Slant and moral-foundation stability remains in pipeline/pending/.

source("pipeline/10_canonical_common.R")
suppressPackageStartupMessages(library(tidyverse))

FRACTIONS <- as.numeric(strsplit(Sys.getenv("CANON_STABILITY_FRACTIONS",
                                            "0.25,0.50,0.75,1.00"), ",")[[1]])
REPS <- as.integer(Sys.getenv("CANON_STABILITY_REPS", "100"))
STAB_SEED <- as.integer(Sys.getenv("CANON_STABILITY_SEED", "20260812"))
STAB_OUTCOMES <- c("genuine_refusal", "capability_failure")
ALL_ISSUES <- sort(unique(canon$issue_id))

equal_model_mean <- function(d, value) {
  if (!nrow(d)) return(NA_real_)
  mean(tapply(d[[value]], as.character(d$model), mean))
}

home_stat <- function(d, jurisdiction, outcome) {
  x <- d |> filter(lang == "en", juris == jurisdiction,
                   home_status %in% c("home", "away")) |> droplevels()
  if (nzchar(estimable_chk(x, outcome))) return(NA_real_)
  gcomp(x, w_nested, outcome)
}

language_stat <- function(d, language, outcome) {
  en <- d |> filter(lang == "en") |>
    select(model, prompt_id, y_en = all_of(outcome))
  z <- d |> filter(lang == language) |>
    select(model, prompt_id, issue_id, y_target = all_of(outcome)) |>
    inner_join(en, by = c("model", "prompt_id")) |>
    mutate(delta = y_target - y_en)
  equal_model_mean(z, "delta")
}

framing_stat <- function(d, outcome) {
  z <- d |> filter(lang == "en") |> group_by(issue_id, model) |>
    summarise(n_regular = sum(tier == "regular"),
              n_boundary = sum(tier == "boundary"),
              regular = mean(.data[[outcome]][tier == "regular"]),
              boundary = mean(.data[[outcome]][tier == "boundary"]),
              .groups = "drop") |>
    filter(n_regular == 2, n_boundary == 2) |>
    mutate(delta = boundary - regular)
  equal_model_mean(z, "delta")
}

one_draw <- function(fraction, replicate) {
  n_issue <- if (fraction == 1) length(ALL_ISSUES) else
    max(2L, round(fraction * length(ALL_ISSUES)))
  draw_seed <- STAB_SEED + round(1000 * fraction) + replicate
  set.seed(draw_seed)
  selected <- if (fraction == 1) ALL_ISSUES else sample(ALL_ISSUES, n_issue)
  d <- canon |> filter(issue_id %in% selected)
  bind_rows(
    map_dfr(STAB_OUTCOMES, function(y)
      map_dfr(JURIS_C, function(j) tibble(
        family = "standardized home", level = j, outcome = y,
        estimate = home_stat(d, j, y)))),
    map_dfr(STAB_OUTCOMES, function(y)
      map_dfr(setdiff(LANGS_C, "en"), function(lg) tibble(
        family = "paired language", level = lg, outcome = y,
        estimate = language_stat(d, lg, y)))),
    map_dfr(STAB_OUTCOMES, function(y) tibble(
      family = "paired framing", level = "boundary minus regular", outcome = y,
      estimate = framing_stat(d, y)))) |>
    mutate(fraction = fraction, percentage = 100 * fraction,
           replicate = replicate, draw_seed = draw_seed, n_issues = n_issue,
           estimable = is.finite(estimate), estimate_pp = pp(estimate))
}

cat(strrep("=", 78), "\nISSUE-SUBSAMPLE STABILITY\n", strrep("=", 78), "\n", sep = "")
draws <- map_dfr(FRACTIONS, function(f) {
  nrep <- if (f == 1) 1L else REPS
  map_dfr(seq_len(nrep), function(r) one_draw(f, r))
})

full_reference <- draws |>
  filter(fraction == 1) |>
  select(family, level, outcome, full_estimate_pp = estimate_pp)
stopifnot(!anyDuplicated(full_reference[c("family", "level", "outcome")]))
draws <- draws |>
  left_join(full_reference, by = c("family", "level", "outcome")) |>
  mutate(deviation_from_full_pp = estimate_pp - full_estimate_pp,
         absolute_deviation_from_full_pp = abs(deviation_from_full_pp))

summary <- draws |> group_by(fraction, percentage, n_issues, family, level, outcome) |>
  summarise(planned_draws = n(), successful_draws = sum(estimable),
            estimability_rate = mean(estimable),
            median_pp = median(estimate_pp, na.rm = TRUE),
            p05_pp = quantile(estimate_pp, .05, na.rm = TRUE),
            p95_pp = quantile(estimate_pp, .95, na.rm = TRUE),
            full_estimate_pp = first(full_estimate_pp),
            median_deviation_pp = median(deviation_from_full_pp, na.rm = TRUE),
            p05_deviation_pp = quantile(deviation_from_full_pp, .05, na.rm = TRUE),
            p95_deviation_pp = quantile(deviation_from_full_pp, .95, na.rm = TRUE),
            median_absolute_deviation_pp = median(
              absolute_deviation_from_full_pp, na.rm = TRUE),
            .groups = "drop") |>
  mutate(interval_type = "empirical 5th-95th percentile stability range; NOT a confidence interval",
         sampling_unit = "issue_id without replacement; all rows for an issue retained",
         canonical_run_id = CANONICAL_RUN_ID)

failures <- draws |> filter(!estimable) |>
  count(fraction, percentage, family, level, outcome, name = "failed_draws") |>
  mutate(canonical_run_id = CANONICAL_RUN_ID)

write_csv(draws, file.path(CAN_EST, "c21_subsample_draws.csv.gz"))
write_csv(summary, file.path(CAN_EST, "c21_subsample_summary.csv"))
write_csv(failures, file.path(CAN_EST, "c21_subsample_failures.csv"))
jsonlite::write_json(list(
  fractions = FRACTIONS, repetitions_below_100_percent = REPS,
  base_seed = STAB_SEED,
  draw_seed_rule = "base_seed + round(1000 * fraction) + replicate",
  sampling_unit = "issue_id without replacement",
  outcomes = STAB_OUTCOMES,
  estimand_families = c("standardized home", "paired language", "paired framing"),
  interval_warning = "stability ranges are not confidence intervals",
  canonical_run_id = CANONICAL_RUN_ID),
  file.path(CAN_EST, "c21_subsample_metadata.json"), auto_unbox = TRUE, pretty = TRUE)
cat(sprintf("wrote %d draws and %d summary rows\n", nrow(draws), nrow(summary)))
