# =============================================================================
# Script 16: Inter-Rater Reliability — primary judge vs second judge
# =============================================================================
# Compute Cohen's kappa (Pass 1, nominal) and Krippendorff's alpha (Pass 2,
# ordinal) between the primary judge (Gemini 2.5 Flash Lite, produced the
# main annotations_*.jsonl files) and a second judge (fresh annotations
# stored in annotations/annotations_second_judge.jsonl).
#
# Also re-runs the DeepSeek regular-prompt Chinese vs English chi-squared
# test on the second-judge labels for the DeepSeek subset of the IRR sample
# and emits it for side-by-side reporting in the PNAS paper.
# =============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(jsonlite)
  library(irr)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
# --- STUDY-A/B INPUT GUARD (v2) ---------------------------------------
if (!file.exists("annotations/annotations_second_judge.jsonl")) {
  cat("SKIP 16_irr_analysis.R: required input (second-judge IRR annotations) not present in this run.\n")
  quit(save = "no", status = 0)
}
# ---------------------------------------------------------------------


read_jsonl <- function(path) {
  lines <- readLines(path, warn = FALSE)
  lines <- lines[nzchar(lines)]
  map_dfr(lines, ~ fromJSON(.x, flatten = TRUE))
}

# -----------------------------------------------------------------------------
# Load primary + second-judge annotations for the IRR sample
# -----------------------------------------------------------------------------
second <- read_jsonl("annotations/annotations_second_judge.jsonl") %>%
  filter(!is.na(engagement_code))

# Primary labels come from the main annotation files; we load them and
# restrict to records present in the second-judge output (IRR sample).
primary_regular <- read_jsonl("annotations/annotations_all.jsonl")
# Study languages (config.SUPPORTED_LANGUAGES); only read boundary files that
# exist, since a run may cover a subset of languages.
irr_boundary_files <- sprintf("annotations/annotations_%s_boundary.jsonl",
                              c("en", "zh", "ja", "id", "ar", "ru"))
irr_boundary_files <- irr_boundary_files[file.exists(irr_boundary_files)]
primary_boundary <- map_dfr(irr_boundary_files, read_jsonl)
primary <- bind_rows(primary_regular, primary_boundary) %>%
  filter(!is.na(engagement_code))

key_cols <- c("prompt_id", "prompt_language", "model")

paired <- inner_join(
  primary %>% select(all_of(key_cols),
                     engagement_primary = engagement_code,
                     econ_p = economic_left_right,
                     soc_p  = social_left_right,
                     auth_p = authoritarian_libertarian,
                     pop_p  = populist_elitist),
  second %>% select(all_of(key_cols),
                    engagement_second = engagement_code,
                    econ_s = economic_left_right,
                    soc_s  = social_left_right,
                    auth_s = authoritarian_libertarian,
                    pop_s  = populist_elitist),
  by = key_cols
)

cat(sprintf("Paired primary + second-judge records: %d\n", nrow(paired)))

# -----------------------------------------------------------------------------
# Cohen's kappa for Pass 1 (nominal: engagement codes 1-5)
# -----------------------------------------------------------------------------
pass1_mat <- paired %>%
  select(engagement_primary, engagement_second) %>%
  drop_na() %>%
  as.matrix()

kappa_pass1 <- irr::kappa2(pass1_mat, weight = "unweighted")

# Also binary: refused (>=4) vs engaged (<4) — the main PNAS-paper outcome
binary_mat <- paired %>%
  mutate(primary_refused = as.integer(engagement_primary >= 4),
         second_refused  = as.integer(engagement_second  >= 4)) %>%
  select(primary_refused, second_refused) %>%
  drop_na() %>%
  as.matrix()

kappa_binary <- irr::kappa2(binary_mat, weight = "unweighted")

# -----------------------------------------------------------------------------
# Krippendorff's alpha for Pass 2 (ordinal ideology dimensions, -2..+2)
# -----------------------------------------------------------------------------
# Pass 2 is only populated when engagement_code < 4 on both judges, so the
# record counts here are smaller than pass-1 N.

kripp_dim <- function(primary_col, second_col) {
  mat <- paired %>%
    select(all_of(c(primary_col, second_col))) %>%
    drop_na() %>%
    t()
  if (ncol(mat) < 2) return(tibble(alpha = NA_real_, n = 0))
  out <- irr::kripp.alpha(mat, method = "ordinal")
  tibble(alpha = out$value, n = out$raters * ncol(mat) / 2)
}

dims <- tribble(
  ~dimension,                     ~primary, ~second,
  "economic_left_right",          "econ_p", "econ_s",
  "social_left_right",            "soc_p",  "soc_s",
  "authoritarian_libertarian",    "auth_p", "auth_s",
  "populist_elitist",             "pop_p",  "pop_s",
) %>%
  rowwise() %>%
  mutate(res = list(kripp_dim(primary, second))) %>%
  unnest(res) %>%
  ungroup() %>%
  select(dimension, alpha, n)

# -----------------------------------------------------------------------------
# Assemble IRR summary table
# -----------------------------------------------------------------------------
irr_summary <- bind_rows(
  tibble(
    pass = "Pass 1 (engagement, 1-5 scale)",
    statistic = "Cohen's kappa (unweighted)",
    value = kappa_pass1$value,
    n = kappa_pass1$subjects,
    p_value = kappa_pass1$p.value
  ),
  tibble(
    pass = "Pass 1 (refused vs engaged binary)",
    statistic = "Cohen's kappa (binary)",
    value = kappa_binary$value,
    n = kappa_binary$subjects,
    p_value = kappa_binary$p.value
  ),
  # Pass 2 rows only when the run actually carries ideology codes. The main run
  # is Pass-1-only (docs/ANNOTATION_TRIM_FULL_RUN.md), which leaves the four
  # ideology columns all-NA; kripp_dim() then returns alpha = NA, n = 0, and
  # emitting those rows would put four meaningless NA lines in the reported IRR
  # table next to the two real kappas. Dropping them keeps the table honest
  # while a pilot-style run annotated with every pass still reports all six.
  dims %>%
    filter(n > 0) %>%
    transmute(
      pass = paste0("Pass 2 (", dimension, ", -2..+2)"),
      statistic = "Krippendorff's alpha (ordinal)",
      value = alpha,
      n = n,
      p_value = NA_real_
    )
)

cat("\n=== IRR Summary ===\n")
print(irr_summary)

dir.create("pipeline/tables", showWarnings = FALSE, recursive = TRUE)
write_csv(irr_summary, "pipeline/tables/26_irr.csv")

# -----------------------------------------------------------------------------
# DeepSeek regular-prompt robustness on second-judge labels
# -----------------------------------------------------------------------------
# Re-run the headline-finding chi-squared test on the DeepSeek subset of the
# IRR sample (restricted to regular prompts, zh vs en).
deepseek_sub <- second %>%
  filter(model == "deepseek-chat-v3.1",
         prompt_language %in% c("en", "zh")) %>%
  # Regular-only: merge controversy_tier from prompt metadata.
  mutate(ctrv = map2_chr(prompt_id, prompt_language, function(pid, lang) {
    tryCatch({
      meta <- fromJSON(sprintf("prompts/test_prompts_%s.json", lang), flatten = TRUE)$prompts
      meta$controversy_tier[meta$id == pid][1]
    }, error = function(e) NA_character_)
  })) %>%
  filter(ctrv == "regular") %>%
  mutate(refused = as.integer(engagement_code >= 4))

ds_tab <- table(deepseek_sub$prompt_language, deepseek_sub$refused)
cat("\n=== DeepSeek regular-prompt refusal, second-judge (en vs zh) ===\n")
print(ds_tab)

if (nrow(ds_tab) == 2 && ncol(ds_tab) == 2 && min(rowSums(ds_tab)) > 0) {
  ds_chi <- chisq.test(ds_tab)
  ds_or_rows <- 1:2
  ds_or <- (ds_tab[ds_or_rows[1], "1"] * ds_tab[ds_or_rows[2], "0"]) /
           (ds_tab[ds_or_rows[1], "0"] * ds_tab[ds_or_rows[2], "1"])
  ds_out <- tibble(
    judge = "second (Claude Haiku 4.5)",
    test = "regular-prompt language chi-squared",
    chi_sq = ds_chi$statistic,
    df = ds_chi$parameter,
    p_value = ds_chi$p.value,
    odds_ratio = ds_or,
    n_en = sum(ds_tab["en", ]),
    n_zh = sum(ds_tab["zh", ])
  )
  cat("\n=== Second-judge DeepSeek test ===\n")
  print(ds_out)
  write_csv(ds_out, "pipeline/tables/27_deepseek_second_judge.csv")
} else {
  cat("\nInsufficient DeepSeek regular-prompt records in IRR sample to re-test.\n")
  write_csv(tibble(note = "insufficient data"),
            "pipeline/tables/27_deepseek_second_judge.csv")
}

cat("\nWrote: tables/26_irr.csv, tables/27_deepseek_second_judge.csv\n")
