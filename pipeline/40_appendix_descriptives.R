# =============================================================================
# Technical reference: docs/r_pipeline/40_appendix_descriptives.md
# APPENDIX DESCRIPTIVES -- final Luna v2.4 fields
# =============================================================================
# These tables orient the reader to realized response composition. They do not
# add hypothesis tests. Language effects remain the paired c08/c09 estimands;
# raw model-language cell rates are not relabelled as effects.

source("pipeline/10_canonical_common.R")
suppressPackageStartupMessages(library(tidyverse))
B_APPENDIX <- as.integer(Sys.getenv("CANON_B_SENS", "500"))

# a01: the two adopted measurements by model and delivered prompt language.
a01 <- canon |> group_by(model, prompt_language) |> summarise(
  n = n(), n_issues = n_distinct(issue_id),
  genuine_refusal_n = sum(genuine_refusal),
  genuine_refusal_rate = mean(genuine_refusal),
  capability_failure_n = sum(capability_failure),
  capability_failure_rate = mean(capability_failure),
  .groups = "drop") |>
  mutate(note = paste("raw cell description; paired language estimands are",
                      "c08/c09; outcomes are separate and may overlap"),
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(a01, file.path(CAN_EST, "a01_outcome_rates_by_model_language.csv"))

# a02: task behavior preserves more information than a binary refusal flag.
a02 <- canon |> count(model, prompt_language, task_behavior = rv_task_behavior,
                      name = "n") |>
  group_by(model, prompt_language) |> mutate(share = n / sum(n),
                                             n_cell = sum(n)) |> ungroup() |>
  mutate(source = "Luna v2.4 task_behavior",
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(a02, file.path(CAN_EST, "a02_task_behavior_composition.csv"))

# a03: explicit versus implicit is defined only among v2.4 genuine refusals.
a03 <- canon |> filter(genuine_refusal == 1) |>
  count(model, prompt_language, refusal_type = rv_substantive_refusal,
        name = "n") |>
  group_by(model, prompt_language) |> mutate(share = n / sum(n),
                                             n_refusals = sum(n)) |> ungroup() |>
  mutate(conditioning = "genuine_refusal == 1",
         note = "descriptive composition; not an independently validated reason taxonomy",
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(a03, file.path(CAN_EST, "a03_refusal_type_composition.csv"))

# a04: one-model case study using the same paired construction as c09.
DS <- "deepseek-chat-v3.1"
a04 <- map_dfr(c("genuine_refusal", "capability_failure"), function(outcome) {
  en <- canon |> filter(model == DS, lang == "en") |>
    select(prompt_id, issue_id, y_en = all_of(outcome))
  zh <- canon |> filter(model == DS, lang == "zh") |>
    select(prompt_id, y_zh = all_of(outcome))
  blocks <- inner_join(en, zh, by = "prompt_id") |> mutate(delta = y_zh - y_en)
  bt <- boot_canon(blocks, function(x) mean(x$delta), B = B_APPENDIX,
                   label = paste0("a04|", outcome))
  record_diag(bt$diag)
  tibble(outcome = outcome, model = DS, n_blocks = nrow(blocks),
         n_issues = n_distinct(blocks$issue_id), estimate = bt$estimate,
         conf_low = bt$conf_low, conf_high = bt$conf_high,
         estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
         conf_high_pp = pp(bt$conf_high),
         estimand = "paired Chinese minus English difference within prompt_id",
         interpretation = "one-model case study; not evidence about other models")
}) |> mutate(canonical_run_id = CANONICAL_RUN_ID)
write_csv(a04, file.path(CAN_EST, "a04_deepseek_paired_outcomes.csv"))

flush_diag()
cat("wrote appendix tables a01-a04 using Luna v2.4 outcomes\n")
