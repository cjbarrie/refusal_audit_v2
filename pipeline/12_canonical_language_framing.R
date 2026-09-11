# =============================================================================
# Technical reference: docs/r_pipeline/12_canonical_language_framing.md
# PAIRED LANGUAGE AND FRAMING ANALYSES -- final Luna v2.4 outcomes
# =============================================================================
# Language estimand: within (model,prompt_id), target-language outcome minus
# English outcome, averaged equally over models. This holds the exact prompt ID
# and subject model fixed. It is the effect of the delivered translation under
# assumptions about translation equivalence and run stability; it is not the
# causal effect of a user's language.
#
# Framing estimand: within English (issue_id,model), mean boundary minus mean
# regular outcome, requiring the intended 2+2 prompt block. Prompt wording is
# not randomized, so causal interpretation requires exchangeability of generated
# variants within issue.
#
# Primary outcome: genuine_refusal. Capability failure is separate. Original
# judge-coded non-engagement is written to dedicated sensitivity tables on the
# original eleven-model roster only.
# Inference: issue-cluster percentile bootstrap with fixed draws and no retries.
# Outputs: c08-c11 plus c10b incomplete blocks and c18 diagnostics.

source("pipeline/10_canonical_common.R")
suppressPackageStartupMessages(library(tidyverse))

B_PRIMARY <- as.integer(Sys.getenv("CANON_B_HEAD", "2000"))
B_SENS <- as.integer(Sys.getenv("CANON_B_SENS", "500"))
NONEN <- setdiff(LANGS_C, "en")
OUTCOMES <- c("genuine_refusal", "capability_failure")
OUTCOME_ROLE <- c(genuine_refusal = "primary",
                  capability_failure = "diagnostic")

cat(strrep("=", 78), "\nPAIRED LANGUAGE AND FRAMING: LUNA v2.4\n",
    strrep("=", 78), "\n", sep = "")

# Resample issues while keeping every response/block for a sampled issue.
boot_paired <- function(d, stat, B, label, max_fail_rate = 0.02) {
  idx <- split(seq_len(nrow(d)), d$issue_id)
  issues <- names(idx)
  point <- tryCatch(stat(d), error = function(e) NA_real_)
  draw_seed <- CAN_SEED + sum(utf8ToInt(label))
  set.seed(draw_seed)
  vals <- rep(NA_real_, B)
  for (b in seq_len(B)) {
    draw <- sample(issues, length(issues), replace = TRUE)
    x <- d[unlist(idx[draw], use.names = FALSE), , drop = FALSE]
    x$bootstrap_issue_instance <- rep(paste0(draw, "#", seq_along(draw)),
                                      times = lengths(idx[draw]))
    vals[b] <- tryCatch(stat(x), error = function(e) NA_real_)
  }
  ok <- vals[is.finite(vals)]
  fail <- 1 - length(ok) / B
  reliable <- fail <= max_fail_rate
  record_diag(tibble(
    canonical_run_id = CANONICAL_RUN_ID, label = label,
    bootstrap_unit = "issue_id", multiplicity_preserved = TRUE,
    copy_id_column = "bootstrap_issue_instance", seed = draw_seed,
    replicates_requested = B, replicates_drawn = B,
    replicates_successful = length(ok), replicates_failed = B - length(ok),
    failure_rate = fail, failed_draws_replaced = FALSE,
    interval_reliable = reliable, interval_method = "percentile",
    n_rows = nrow(d), n_issues = length(issues)))
  list(estimate = point,
       conf_low = if (reliable && length(ok) > 1) unname(quantile(ok, .025)) else NA_real_,
       conf_high = if (reliable && length(ok) > 1) unname(quantile(ok, .975)) else NA_real_,
       failure_rate = fail, interval_reliable = reliable)
}

block_mean <- function(d, weighting = "equal_model") {
  if (!nrow(d)) return(NA_real_)
  if (weighting == "response") return(mean(d$d))
  if (weighting == "equal_model")
    return(mean(tapply(d$d, as.character(d$model), mean)))
  stop("unknown paired weighting: ", weighting)
}

# Paired arm levels use the same complete blocks and equal-model target as the
# difference. They are descriptive levels that explain a contrast's baseline;
# inference remains attached to the paired difference.
paired_levels <- function(d) {
  by_model <- d |> group_by(model) |>
    summarise(mean_english = mean(y_en), mean_target = mean(y_target),
              .groups = "drop")
  c(mean_english = mean(by_model$mean_english),
    mean_target = mean(by_model$mean_target))
}

paired_language_blocks <- function(language, outcome) {
  meta <- canon |> distinct(model, prompt_id, issue_id, juris, domain, tier,
                            home_status)
  en <- canon |> filter(lang == "en") |>
    select(model, prompt_id, y_en = all_of(outcome))
  target <- canon |> filter(lang == language) |>
    select(model, prompt_id, y_target = all_of(outcome))
  universe <- meta |> left_join(en, by = c("model", "prompt_id")) |>
    left_join(target, by = c("model", "prompt_id")) |>
    mutate(pair_status = case_when(
      !is.na(y_en) & !is.na(y_target) ~ "complete",
      !is.na(y_en) ~ "English only",
      !is.na(y_target) ~ "target only",
      TRUE ~ "missing both"))
  list(
    blocks = universe |> filter(pair_status == "complete") |>
      mutate(d = y_target - y_en),
    diagnostics = universe |> count(pair_status, name = "n"))
}

# A. Prompt-fixed language contrasts ------------------------------------------
c08 <- map_dfr(NONEN, function(language) {
  map_dfr(OUTCOMES, function(outcome) {
    p <- paired_language_blocks(language, outcome)
    blocks <- p$blocks
    B <- if (outcome == "genuine_refusal") B_PRIMARY else B_SENS
    bt <- boot_paired(blocks, function(x) block_mean(x, "equal_model"), B,
                      sprintf("c08|%s|%s", language, outcome))
    counts <- setNames(p$diagnostics$n, p$diagnostics$pair_status)
    n_status <- function(k) if (k %in% names(counts)) counts[[k]] else 0L
    lv <- paired_levels(blocks)
    tibble(
      language = language, outcome = outcome,
      outcome_role = unname(OUTCOME_ROLE[outcome]), weighting = "equal_model",
      estimate = bt$estimate, conf_low = bt$conf_low,
      conf_high = bt$conf_high, estimate_pp = pp(bt$estimate),
      conf_low_pp = pp(bt$conf_low), conf_high_pp = pp(bt$conf_high),
      mean_english = unname(lv["mean_english"]),
      mean_target = unname(lv["mean_target"]),
      mean_english_pp = pp(mean_english), mean_target_pp = pp(mean_target),
      n_complete_blocks = nrow(blocks), n_issues = n_distinct(blocks$issue_id),
      n_english_only = n_status("English only"),
      n_target_only = n_status("target only"),
      n_missing_both = n_status("missing both"),
      interval_reliable = bt$interval_reliable,
      replicate_failure_rate = bt$failure_rate)
  })
}) |> mutate(
  estimand = "paired target-language minus English difference",
  block = "model x prompt_id", bootstrap_unit = "issue_id",
  interpretation = paste("effect of delivering the tested translation to the",
    "tested model/prompt set; not the effect of user language"),
  canonical_run_id = CANONICAL_RUN_ID)
write_csv(c08, file.path(CAN_EST, "c08_language_paired.csv"))

# Original-label measurement sensitivity. Complete-pair filtering automatically
# restricts this table to the original eleven models because expansion rows have
# no original Gemini label.
c08c <- map_dfr(NONEN, function(language) {
  p <- paired_language_blocks(language, "original_nonengagement")
  bt <- boot_paired(p$blocks, function(x) block_mean(x, "equal_model"), B_SENS,
                    sprintf("c08c|%s", language))
  lv <- paired_levels(p$blocks)
  tibble(language = language, outcome = "original_nonengagement",
         outcome_role = "measurement sensitivity", weighting = "equal_model",
         estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high,
         estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
         conf_high_pp = pp(bt$conf_high), mean_english = unname(lv["mean_english"]),
         mean_target = unname(lv["mean_target"]), n_complete_blocks = nrow(p$blocks),
         n_models = n_distinct(p$blocks$model), interval_reliable = bt$interval_reliable)
}) |> mutate(
  estimand = "paired target-language minus English difference",
  sample = "original eleven models with Gemini labels",
  changed = "outcome definition and roster relative to the 20-model primary analysis",
  canonical_run_id = CANONICAL_RUN_ID)
write_csv(c08c, file.path(CAN_EST, "c08c_original_nonengagement_sensitivity.csv"))

# Same complete blocks under empirical-response rather than equal-model weights.
c08b <- map_dfr(NONEN, function(language) {
  p <- paired_language_blocks(language, "genuine_refusal")
  bt <- boot_paired(p$blocks, function(x) block_mean(x, "response"), B_SENS,
                    sprintf("c08b|%s", language))
  tibble(language = language, outcome = "genuine_refusal",
         weighting = "response", estimate = bt$estimate,
         conf_low = bt$conf_low, conf_high = bt$conf_high,
         estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
         conf_high_pp = pp(bt$conf_high), n_complete_blocks = nrow(p$blocks))
}) |> mutate(note = "weighting sensitivity; primary c08 gives models equal weight",
             canonical_run_id = CANONICAL_RUN_ID)
write_csv(c08b, file.path(CAN_EST, "c08b_weighting_comparison.csv"))

# Exploratory model-specific heterogeneity; no multiplicity-adjusted claims.
c09 <- map_dfr(NONEN, function(language) {
  map_dfr(c("genuine_refusal", "capability_failure"), function(outcome) {
    p <- paired_language_blocks(language, outcome)$blocks
    map_dfr(sort(unique(p$model)), function(m) {
      d <- p |> filter(model == m)
      bt <- boot_paired(d, function(x) mean(x$d), B_SENS,
                        sprintf("c09|%s|%s|%s", language, outcome, m))
      tibble(language = language, outcome = outcome, model = m,
             jurisdiction = as.character(d$juris[1]), n_blocks = nrow(d),
             n_issues = n_distinct(d$issue_id), estimate = bt$estimate,
             conf_low = bt$conf_low, conf_high = bt$conf_high,
             estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
             conf_high_pp = pp(bt$conf_high),
             mean_english = mean(d$y_en), mean_target = mean(d$y_target),
             mean_english_pp = pp(mean_english), mean_target_pp = pp(mean_target),
             interval_reliable = bt$interval_reliable)
    })
  })
}) |> mutate(
  estimand = "model-specific paired language minus English difference",
  evidence_status = "exploratory heterogeneity; no multiplicity adjustment",
  canonical_run_id = CANONICAL_RUN_ID)
write_csv(c09, file.path(CAN_EST, "c09_language_by_model.csv"))

# B. Issue/model-paired framing contrasts -------------------------------------
framing_blocks <- function(outcome, complete_only = TRUE) {
  x <- CANON_ENGLISH |> filter(!is.na(.data[[outcome]])) |>
    group_by(issue_id, model, juris, domain) |>
    summarise(n_regular = sum(tier == "regular"),
              n_boundary = sum(tier == "boundary"),
              mean_regular = ifelse(n_regular > 0,
                mean(.data[[outcome]][tier == "regular"]), NA_real_),
              mean_boundary = ifelse(n_boundary > 0,
                mean(.data[[outcome]][tier == "boundary"]), NA_real_),
              .groups = "drop") |>
    filter(n_regular > 0, n_boundary > 0) |>
    mutate(d = mean_boundary - mean_regular)
  if (complete_only) x |> filter(n_regular == 2, n_boundary == 2) else x
}

all_blocks <- framing_blocks("genuine_refusal", complete_only = FALSE)
c10b <- all_blocks |> filter(n_regular != 2 | n_boundary != 2) |>
  mutate(reason = "primary framing estimand requires 2 regular and 2 boundary prompts",
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(c10b, file.path(CAN_EST, "c10b_framing_incomplete_blocks.csv"))

c10 <- map_dfr(OUTCOMES, function(outcome) {
  d <- framing_blocks(outcome)
  B <- if (outcome == "genuine_refusal") B_PRIMARY else B_SENS
  bt <- boot_paired(d, function(x) block_mean(x, "equal_model"), B,
                    sprintf("c10|%s", outcome))
  mean_regular_equal_model <- mean(tapply(d$mean_regular, d$model, mean))
  mean_boundary_equal_model <- mean(tapply(d$mean_boundary, d$model, mean))
  tibble(outcome = outcome, outcome_role = unname(OUTCOME_ROLE[outcome]),
         n_blocks = nrow(d), n_issues = n_distinct(d$issue_id),
         mean_regular = mean_regular_equal_model,
         mean_boundary = mean_boundary_equal_model, estimate = bt$estimate,
         conf_low = bt$conf_low, conf_high = bt$conf_high,
         estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
         conf_high_pp = pp(bt$conf_high),
         interval_reliable = bt$interval_reliable)
}) |> mutate(
  estimand = "paired boundary minus regular mean within issue x model",
  sample = "English complete 2+2 blocks", weighting = "equal model",
  causal_interpretation = paste("requires exchangeability of generated regular",
    "and boundary variants within issue; variants were not randomized"),
  canonical_run_id = CANONICAL_RUN_ID)
write_csv(c10, file.path(CAN_EST, "c10_framing_paired.csv"))

d_original_framing <- framing_blocks("original_nonengagement")
bt_original_framing <- boot_paired(
  d_original_framing, function(x) block_mean(x, "equal_model"), B_SENS,
  "c10c|original_nonengagement")
c10c <- tibble(
  outcome = "original_nonengagement", outcome_role = "measurement sensitivity",
  n_blocks = nrow(d_original_framing),
  n_issues = n_distinct(d_original_framing$issue_id),
  n_models = n_distinct(d_original_framing$model),
  mean_regular = mean(tapply(d_original_framing$mean_regular,
                             d_original_framing$model, mean)),
  mean_boundary = mean(tapply(d_original_framing$mean_boundary,
                              d_original_framing$model, mean)),
  estimate = bt_original_framing$estimate,
  conf_low = bt_original_framing$conf_low,
  conf_high = bt_original_framing$conf_high,
  estimate_pp = pp(estimate), conf_low_pp = pp(conf_low), conf_high_pp = pp(conf_high),
  interval_reliable = bt_original_framing$interval_reliable,
  estimand = "paired boundary minus regular mean within issue x model",
  sample = "original eleven English models with Gemini labels; complete 2+2 blocks",
  changed = "outcome definition and roster relative to the 20-model primary analysis",
  canonical_run_id = CANONICAL_RUN_ID)
write_csv(c10c, file.path(CAN_EST, "c10c_original_nonengagement_sensitivity.csv"))

c11 <- map_dfr(c("genuine_refusal", "capability_failure"), function(outcome) {
  d <- framing_blocks(outcome)
  map_dfr(sort(unique(d$model)), function(m) {
    z <- d |> filter(model == m)
    bt <- boot_paired(z, function(x) mean(x$d), B_SENS,
                      sprintf("c11|%s|%s", outcome, m))
    tibble(outcome = outcome, model = m,
           jurisdiction = as.character(z$juris[1]), n_blocks = nrow(z),
           n_issues = n_distinct(z$issue_id), estimate = bt$estimate,
           conf_low = bt$conf_low, conf_high = bt$conf_high,
           estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
           conf_high_pp = pp(bt$conf_high),
           interval_reliable = bt$interval_reliable)
  })
}) |> mutate(
  estimand = "model-specific paired boundary minus regular difference",
  evidence_status = "exploratory heterogeneity; no multiplicity adjustment",
  canonical_run_id = CANONICAL_RUN_ID)
write_csv(c11, file.path(CAN_EST, "c11_framing_by_model.csv"))

flush_diag()
cat(sprintf("wrote c08-c11; %d primary language rows\n",
            sum(c08$outcome == "genuine_refusal")))
