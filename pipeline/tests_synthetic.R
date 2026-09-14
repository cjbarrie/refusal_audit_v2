# =============================================================================
# Technical reference: docs/r_pipeline/tests_synthetic.md
# FAST SYNTHETIC TESTS -- v2.4 outcome and estimator contracts
# =============================================================================
# Uses constructed data plus a read-only count/key check of the current
# 24-model candidate frame. Writes no scientific output and makes no provider
# call. A caller may override CANON_DATA_PATH to test another release.

if (!nzchar(Sys.getenv("CANON_DATA_PATH"))) {
  Sys.setenv(CANON_DATA_PATH =
               "pipeline/releases/canon_031/estimates/data_clean.RData")
}

source("pipeline/10_canonical_common.R")
suppressPackageStartupMessages(library(tidyverse))
passed <- 0L
failed <- 0L
test <- function(name, condition) {
  if (isTRUE(condition)) {
    passed <<- passed + 1L
    cat("PASS", name, "\n")
  } else {
    failed <<- failed + 1L
    cat("FAIL", name, "\n")
  }
}

test("combined response key coverage", nrow(canon) == EXP_EXPECTED_N &&
       n_distinct(canon$model) == EXP_EXPECTED_MODELS &&
       !anyDuplicated(canon[RV_KEY]))
test("combined genuine-refusal count",
     sum(canon$genuine_refusal) == EXP_EXPECTED_REFUSALS)
test("combined capability-failure count",
     sum(canon$capability_failure) == EXP_EXPECTED_CAPABILITY_FAILURES)
original_rows <- canon |> filter(!is.na(original_nonengagement))
test("original outcome is exact and confined to original panel",
     nrow(original_rows) == 137186L &&
       all(original_rows$original_nonengagement ==
             as.integer(original_rows$engagement_code >= 4)))
test("v2.4 outcomes may overlap",
     sum(canon$genuine_refusal & canon$capability_failure) >= 0L)

d <- tibble(model = c("a", "a", "a", "b", "b"),
            issue_id = c("i1", "i1", "i2", "i1", "i2"))
test("nested weights sum to one", abs(sum(w_nested(d)) - 1) < 1e-12)
test("equal-model weights sum to one", abs(sum(w_equal_model(d)) - 1) < 1e-12)

set.seed(10)
s <- expand_grid(issue_id = paste0("i", 1:40), model = c("a", "b"),
                 home = 0:1, rep = 1:3) |>
  mutate(home_status = if_else(home == 1, "home", "away"),
         model_f = factor(model), tier = factor("regular"),
         domain = factor("one"), route_f = factor("perennial"),
         genuine_refusal = rbinom(n(), 1, plogis(-2 + 1.2 * home)))
test("synthetic home outcome has both arms and events",
     !nzchar(estimable_chk(s, "genuine_refusal")))
g <- gcomp(s, w_nested, "genuine_refusal")
test("g-computation returns a finite positive contrast", is.finite(g) && g > 0)
gl <- gcomp(s, w_nested, "genuine_refusal", return_levels = TRUE)
test("g-computation levels reproduce the contrast",
     all(gl[c("home_risk", "away_risk")] >= 0 &
           gl[c("home_risk", "away_risk")] <= 1) &&
       abs((gl["home_risk"] - gl["away_risk"]) - gl["contrast"]) < 1e-12)

b <- boot_canon(s, function(x) mean(x$genuine_refusal), B = 20,
                label = "synthetic|bootstrap")
test("bootstrap plans exactly 20 draws", b$diag$replicates_drawn == 20L)
test("bootstrap records the issue-instance column",
     b$diag$copy_id_column == "bootstrap_issue_instance")

active <- setdiff(list.files("pipeline", pattern = "[.]R$", full.names = TRUE),
                  c("pipeline/01_data_loading.R", "pipeline/10_canonical_common.R"))
code <- paste(vapply(active, function(p)
  paste(readLines(p, warn = FALSE), collapse = "\n"), character(1)), collapse = "\n")
test("active analyses never source pending scripts",
     !grepl("source\\([\"']pipeline/pending", code))

cat(sprintf("\nSynthetic tests: %d passed, %d failed\n", passed, failed))
if (failed) quit(save = "no", status = 1)
