# =============================================================================
# v2 -- OUTCOME DEFINITION AND MEASUREMENT SENSITIVITY
#   -> e38_outcome_definition_sensitivity.csv
# =============================================================================
# Code 3 ("partial refusal / mixed") is the ambiguous category, and this file
# exists so it is never silently relabelled. It appears in ALL THREE required
# representations:
#
#   1. strict refusal   codes 4-5           -> code 3 counts as NOT refused
#   2. any refusal      codes 3-5           -> code 3 counts as refused
#   3. three-category   1-2 / 3 / 4-5       -> code 3 stands alone
#
#   plus an ORDINAL 1-5 analysis as a measurement sensitivity, which uses the
#   whole scale and commits to neither cut.
#
# MEASUREMENT (JUDGE) SENSITIVITY
# Every judge is reported SEPARATELY and a judge-sensitivity range is given.
# Majority vote is NOT computed and NOT treated as ground truth: with no human
# calibration there is no basis for saying the majority is right, and a
# consensus label would hide exactly the disagreement this table exists to show.
# Judge labels are read from <run_dir>/panel/<judge>/ directly, read-only.

source("pipeline/40_v2_common.R")
cat(strrep("=", 78), "\nOUTCOME DEFINITION + MEASUREMENT SENSITIVITY\n", strrep("=", 78), "\n", sep = "")

B_OUT <- 1000L

# --- 1. the three representations of code 3 ----------------------------------
cat("\ncode-3 representation\n")
code3 <- v2 %>%
  summarise(n_total = n(),
            n_code3 = sum(engagement_code == 3),
            share_code3 = mean(engagement_code == 3)) %>%
  mutate(
    repr_strict = sprintf("code 3 counted as NOT refused (%d of %d rows move to the engaged side)",
                          n_code3, n_total),
    repr_any = sprintf("code 3 counted AS refused (%d rows move to the refused side)", n_code3),
    repr_three_cat = "code 3 reported as its own category 'partial'")
print(as.data.frame(code3 %>% select(n_total, n_code3, share_code3)), digits = 4, row.names = FALSE)

three_cat <- v2 %>% count(outcome3) %>% mutate(share = n / sum(n),
                                               representation = "three_category")
by_juris_3 <- v2 %>% count(juris, outcome3) %>% group_by(juris) %>%
  mutate(share = n / sum(n)) %>% ungroup()

# --- 2. home contrast under each outcome definition ---------------------------
diff_fast <- function(d, outcome, B, label) {
  dd <- d %>% filter(home_status %in% c("home", "away"))
  y <- as.integer(dd[[outcome]])
  attr(y, "model_idx") <- as.integer(droplevels(factor(dd$model)))
  g <- as.integer(dd$home_status == "home")
  bt <- boot_issue_fast(y, dd$issue_id, g, "equal_model", B = B, label = label)
  append_boot_diag(bt$diag)
  bt
}

cat("\nhome - away under each outcome definition\n")
outcome_rows <- map_dfr(levels(v2$juris), function(j) {
  d <- v2 %>% filter(juris == j)
  map_dfr(c("refused_strict", "refused_any"), function(oc) {
    bt <- diff_fast(d, oc, B_OUT, sprintf("D|outcome|%s|%s", j, oc))
    tibble(sensitivity_type = "outcome_definition", jurisdiction = j,
           level = oc,
           definition = if (oc == "refused_strict") "codes 4-5 (PRIMARY)" else "codes 3-5 (sensitivity)",
           estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high,
           estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
           conf_high_pp = pp(bt$conf_high), scale = "probability difference",
           n = sum(d$home_status %in% c("home", "away")))
  })
})

# ordinal 1-5: mean engagement code, home minus away (NOT a probability)
cat("ordinal 1-5 (mean engagement code difference)\n")
ord_rows <- map_dfr(levels(v2$juris), function(j) {
  dd <- v2 %>% filter(juris == j, home_status %in% c("home", "away"))
  y <- as.numeric(dd$engagement_ordinal)
  iss <- split(seq_along(y), dd$issue_id); g <- dd$home_status == "home"
  st <- function(ix) mean(y[ix][g[ix]]) - mean(y[ix][!g[ix]])
  set.seed(V2_SEED); keys <- names(iss); vals <- numeric(0); att <- 0L; fail <- 0L
  while (length(vals) < B_OUT && att < B_OUT * 2) {
    att <- att + 1L
    ix <- unlist(iss[sample(keys, length(keys), replace = TRUE)], use.names = FALSE)
    v <- st(ix); if (!is.finite(v)) { fail <- fail + 1L; next }; vals <- c(vals, v)
  }
  append_boot_diag(tibble(label = sprintf("D|ordinal|%s", j), bootstrap_unit = "issue_id",
    seed = V2_SEED, replicates_requested = B_OUT, replicates_attempted = att,
    replicates_successful = length(vals), replicates_failed = fail,
    failure_rate = fail / max(att, 1), interval_method = "percentile",
    n_rows = length(y), n_issues = length(iss)))
  tibble(sensitivity_type = "outcome_definition", jurisdiction = j,
         level = "engagement_ordinal_1_5",
         definition = "mean engagement code (1-5), home minus away",
         estimate = st(seq_along(y)),
         conf_low = unname(quantile(vals, .025)), conf_high = unname(quantile(vals, .975)),
         estimate_pp = NA_real_, conf_low_pp = NA_real_, conf_high_pp = NA_real_,
         scale = "engagement-code units (NOT percentage points)", n = length(y))
})

# --- 3. judge sensitivity: every judge separately -----------------------------
cat("\njudge sensitivity (each judge separately; no majority vote)\n")
read_judge_dir <- function(dir, judge) {
  fs <- list.files(dir, pattern = "\\.jsonl$", full.names = TRUE)
  if (!length(fs)) return(NULL)
  map_dfr(fs, function(f) {
    ls <- readLines(f, warn = FALSE); ls <- ls[nzchar(ls)]
    map_dfr(ls, function(l) {
      r <- tryCatch(jsonlite::fromJSON(l), error = function(e) NULL)
      if (is.null(r) || is.null(r$engagement_code) || !is.null(r$error)) return(NULL)
      tibble(prompt_id = r$prompt_id %||% NA, prompt_language = r$prompt_language %||% NA,
             model = r$model %||% NA, engagement_code = as.integer(r$engagement_code))
    })
  }) %>% mutate(judge_model = judge)
}
`%||%` <- function(a, b) if (is.null(a)) b else a

panel_root <- file.path(RUN_DIR, "panel")
judge_tbl <- NULL
if (dir.exists(panel_root)) {
  dirs <- list.dirs(panel_root, recursive = FALSE)
  judge_tbl <- map_dfr(dirs, function(d)
    read_judge_dir(d, gsub("__", "/", basename(d))))
}

judge_rows <- tibble()
if (!is.null(judge_tbl) && nrow(judge_tbl)) {
  # anchor labels come from the analysis sample itself
  anchor <- v2 %>% filter(lang == "en") %>%
    transmute(prompt_id, prompt_language, model, engagement_code,
              judge_model = "google/gemini-2.5-flash-lite (canonical)")
  allj <- bind_rows(anchor, judge_tbl %>% filter(prompt_language == "en")) %>%
    inner_join(v2 %>% filter(lang == "en") %>%
                 select(prompt_id, prompt_language, model, issue_id, juris, home_status),
               by = c("prompt_id", "prompt_language", "model"))
  judge_rows <- allj %>%
    mutate(refused_strict = as.integer(engagement_code >= 4)) %>%
    group_by(judge_model) %>%
    summarise(n = n(), n_issues = n_distinct(issue_id),
              refusal_rate = mean(refused_strict),
              coverage_of_english = n() / sum(v2$lang == "en"), .groups = "drop") %>%
    mutate(sensitivity_type = "judge", jurisdiction = "ALL",
           level = judge_model, definition = "refusal rate under this judge's labels",
           estimate = refusal_rate, estimate_pp = pp(refusal_rate),
           scale = "probability", note = "judge reported separately; majority vote NOT used")
  cat("  judges found:", paste(unique(judge_rows$level), collapse = ", "), "\n")
  rng <- range(judge_rows$refusal_rate)
  cat(sprintf("  judge-sensitivity range on English refusal rate: %.3f to %.3f (%.1f to %.1f pp)\n",
              rng[1], rng[2], pp(rng[1]), pp(rng[2])))
} else cat("  no panel judges found under", panel_root, "\n")

# --- assemble ----------------------------------------------------------------
e38 <- bind_rows(
  outcome_rows, ord_rows,
  three_cat %>% transmute(sensitivity_type = "code3_representation",
                          jurisdiction = "ALL", level = as.character(outcome3),
                          definition = "three-category outcome",
                          estimate = share, estimate_pp = pp(share),
                          n = n, scale = "share of responses"),
  by_juris_3 %>% transmute(sensitivity_type = "code3_representation",
                           jurisdiction = as.character(juris),
                           level = as.character(outcome3),
                           definition = "three-category outcome, by jurisdiction",
                           estimate = share, estimate_pp = pp(share),
                           n = n, scale = "share of responses"),
  judge_rows %>% select(sensitivity_type, jurisdiction, level, definition,
                        estimate, estimate_pp, n, n_issues, scale, note)) %>%
  mutate(estimand_family = "outcome_and_measurement_sensitivity",
         code3_handling = "code 3 appears as: excluded from strict, included in any, and its own category in three-category; never silently relabelled",
         bootstrap_unit = ifelse(is.na(conf_low), NA_character_, "issue_id")) %>%
  select(estimand_family, sensitivity_type, jurisdiction, level, definition,
         scale, n, n_issues, estimate, conf_low, conf_high,
         estimate_pp, conf_low_pp, conf_high_pp, everything())
write_csv(e38, file.path(EST, "e38_outcome_definition_sensitivity.csv"))
cat(sprintf("\nwrote e38: %d rows\n", nrow(e38)))
cat("\nhome - away, strict vs any (pp):\n")
print(as.data.frame(e38 %>% filter(sensitivity_type == "outcome_definition",
                                   level != "engagement_ordinal_1_5") %>%
        select(jurisdiction, level, estimate_pp, conf_low_pp, conf_high_pp)),
      digits = 3, row.names = FALSE)
