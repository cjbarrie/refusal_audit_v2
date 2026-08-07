# =============================================================================
# APPENDIX DESCRIPTIVES  -> a01 .. a04
# =============================================================================
# Every table here is a DESCRIPTIVE VIEW of the analysis sample, or a labelled
# sensitivity of a named canonical estimand. Nothing here is an independent
# inferential surface, and nothing here contradicts a canonical number.
#
# This replaces five archived scripts whose inferential content was invalid for
# this design -- independent-sample chi-square and Fisher tests on paired
# observations, row-level bootstraps that ignored issue clustering, unclustered
# GLMs, and `response_language` used as the exposure when the estimand concerns
# the ASSIGNED prompt language. See pipeline/archive/precanonical_appendix/README.md.
#
# Two rules this file keeps:
#   1. No hypothesis test. The design supports estimation with issue-clustered
#      intervals; a family of independent-sample tests is not a substitute.
#   2. The exposure is `prompt_language`, never `response_language`. The reply
#      language is post-treatment.

source("pipeline/10_canonical_common.R")
cat(strrep("=", 78), "\nAPPENDIX DESCRIPTIVES\n", strrep("=", 78), "\n", sep = "")

APP <- file.path(CAN_EST)
DESCRIPTIVE <- paste("DESCRIPTIVE composition of the analysis sample.",
                     "No hypothesis test; intervals, where shown, are",
                     "issue-clustered. This is not an estimand.")

# --- a01 engagement composition by model x prompt language --------------------
cat("\na01 engagement composition (model x assigned prompt language)\n")
a01 <- canon %>%
  count(model, prompt_language, engagement_category, name = "n") %>%
  group_by(model, prompt_language) %>%
  mutate(share = n / sum(n), n_total = sum(n)) %>% ungroup() %>%
  mutate(exposure = "assigned prompt_language (NOT response_language)",
         note = DESCRIPTIVE, canonical_run_id = CANONICAL_RUN_ID)
write_csv(a01, file.path(APP, "a01_engagement_composition.csv"))
cat(sprintf("  %d rows; %d models x %d languages\n", nrow(a01),
            n_distinct(a01$model), n_distinct(a01$prompt_language)))

# --- a02 refusal rate by model x language, with issue-clustered intervals ------
# The same quantity the canonical layer estimates paired; here it is the raw
# cell rate, which is what a reader wants for orientation. It is NOT the
# language effect: c08/c09 hold the prompt fixed, this does not.
cat("a02 refusal rates by model x language (descriptive, issue-clustered CI)\n")
cells <- canon %>% group_by(model, prompt_language) %>% group_split()
a02 <- map_dfr(cells, function(d) {
  bt <- boot_canon(d, function(x) mean(x$refused_strict), B = 400,
                   label = sprintf("a02|%s|%s", d$model[1], d$prompt_language[1]))
  record_diag(bt$diag)
  tibble(model = d$model[1], prompt_language = d$prompt_language[1],
         n = nrow(d), n_issues = n_distinct(d$issue_id),
         rate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high,
         interval_reliable = bt$interval_reliable)
}) %>% mutate(rate_pp = pp(rate), conf_low_pp = pp(conf_low), conf_high_pp = pp(conf_high),
              relates_to = "descriptive cell rates; the LANGUAGE EFFECT is c08/c09, which pairs within model x prompt_id",
              note = DESCRIPTIVE, canonical_run_id = CANONICAL_RUN_ID)
write_csv(a02, file.path(APP, "a02_refusal_rates_by_cell.csv"))

# --- a03 refusal justification composition, carried WITH its agreement ---------
# The A-G codes have the weakest inter-judge agreement of any construct in this
# study, so the composition is reported next to that agreement rather than on
# its own. No canonical estimand rests on these codes.
cat("a03 refusal justification composition (with agreement)\n")
J5 <- c(A = "neutrality", B = "epistemic", C = "harm", D = "epistemic",
        E = "epistemic", F = "none given", G = "other")
a03 <- canon %>% filter(refused_strict == 1, !is.na(refusal_justification)) %>%
  count(model, prompt_language, code = refusal_justification, name = "n") %>%
  mutate(group = unname(J5[code])) %>%
  group_by(model, prompt_language) %>%
  mutate(share = n / sum(n), n_refusals = sum(n)) %>% ungroup()
rel <- tryCatch(read_csv(file.path(CAN_EST, "e24_reliability_justification.csv"),
                         show_col_types = FALSE), error = function(e) NULL)
a03 <- a03 %>%
  mutate(panel_alpha = if (!is.null(rel) && "krippendorff_alpha" %in% names(rel))
           rel$krippendorff_alpha[1] else NA_real_,
         agreement_caveat = paste("the A-G taxonomy has the weakest inter-judge",
           "agreement of any construct here; NO canonical estimand rests on it,",
           "and these shares are descriptive only"),
         note = DESCRIPTIVE, canonical_run_id = CANONICAL_RUN_ID)
write_csv(a03, file.path(APP, "a03_justification_composition.csv"))

# --- a04 the DeepSeek language case study, done as a paired estimate ----------
# The archived scripts tested this with independent-sample chi-square on paired
# observations. Here it is the SAME comparison as c09, restricted to DeepSeek:
# paired within model x prompt_id, bootstrapped over issues.
cat("a04 DeepSeek English-vs-Chinese, paired (the c09 quantity, one model)\n")
DS <- "deepseek-chat-v3.1"
en <- canon %>% filter(model == DS, prompt_language == "en") %>%
  select(prompt_id, issue_id, domain, y_en = refused_strict)
zh <- canon %>% filter(model == DS, prompt_language == "zh") %>%
  select(prompt_id, y_zh = refused_strict)
blocks <- inner_join(en, zh, by = "prompt_id") %>% mutate(d = y_zh - y_en)
a04 <- if (!nrow(blocks)) tibble() else {
  bt <- boot_canon(blocks, function(x) mean(x$d), B = 800, label = "a04|deepseek")
  record_diag(bt$diag)
  bind_rows(
    tibble(scope = "overall", level = "all domains", n_blocks = nrow(blocks),
           n_issues = n_distinct(blocks$issue_id),
           estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high),
    map_dfr(sort(unique(blocks$domain)), function(dm) {
      b <- blocks %>% filter(domain == dm)
      if (n_distinct(b$issue_id) < 8) return(NULL)
      r <- boot_canon(b, function(x) mean(x$d), B = 400,
                      label = paste0("a04|dom|", dm))
      record_diag(r$diag)
      tibble(scope = "by topic domain", level = dm, n_blocks = nrow(b),
             n_issues = n_distinct(b$issue_id), estimate = r$estimate,
             conf_low = r$conf_low, conf_high = r$conf_high)
    })) %>%
    mutate(estimate_pp = pp(estimate), conf_low_pp = pp(conf_low),
           conf_high_pp = pp(conf_high), model = DS,
           estimand = "paired zh-minus-en difference within prompt_id, one model",
           relates_to = "identical construction to c09; reported here as a case study",
           interpretation = paste("effect of delivering the tested Chinese",
             "translation of the prompt to this model; NOT the causal effect of",
             "a user's language, and NOT evidence about any other model"),
           bootstrap_unit = "issue_id", canonical_run_id = CANONICAL_RUN_ID)
}
if (nrow(a04)) {
  write_csv(a04, file.path(APP, "a04_deepseek_language_paired.csv"))
  print(as.data.frame(a04 %>% filter(scope == "overall") %>%
          select(model, n_blocks, estimate_pp, conf_low_pp, conf_high_pp)),
        digits = 3, row.names = FALSE)
}

flush_diag()
cat("\n", strrep("=", 78), "\nAPPENDIX DESCRIPTIVES DONE\n", strrep("=", 78), "\n", sep = "")
