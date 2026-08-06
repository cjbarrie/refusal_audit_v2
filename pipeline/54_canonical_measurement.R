# =============================================================================
# CANONICAL PART 4 -- measurement sensitivity across judges   -> c17
# =============================================================================
# PRINCIPLE. The canonical outcome is the Gemini 2.5 Flash-Lite label. Every
# additional judge is reported SEPARATELY, as a sensitivity dimension.
#
# Majority vote is NOT computed as ground truth. With no human calibration there
# is no basis for asserting the majority is correct, and a consensus label would
# conceal precisely the disagreement this table exists to expose. What is
# reported instead is the RANGE across judges -- which is a statement about
# instrument sensitivity, not sampling error, and must never be pooled with a
# bootstrap interval.
#
# Judge coverage is English-only, so judge-specific versions exist for the
# English headline quantities and nowhere else. Where a judge cannot cover a
# quantity, the row says so rather than silently omitting it.

source("pipeline/50_canonical_common.R")
cat(strrep("=", 78), "\nCANONICAL PART 4: MEASUREMENT\n", strrep("=", 78), "\n", sep = "")

CANON_JUDGE <- "google/gemini-2.5-flash-lite (canonical)"
JUDGES <- judge_labels(language = "en")

if (is.null(JUDGES) || !nrow(JUDGES)) {
  cat("No panel judges found under ", RUN_DIR, "/panel/. Writing an empty c17.\n", sep = "")
  write_csv(tibble(canonical_run_id = CANONICAL_RUN_ID,
                   note = "no additional judges available"),
            file.path(CAN_EST, "c17_measurement_sensitivity.csv"))
} else {

cov <- JUDGES %>% count(judge_model, name = "n_labels") %>%
  mutate(coverage_of_english = n_labels / nrow(CANON_ENGLISH))
cat("judges available (English):\n")
print(as.data.frame(cov %>% mutate(pct = round(100 * coverage_of_english, 1)) %>%
                      select(judge_model, n_labels, pct)), row.names = FALSE)

# Attach a judge's labels to the English analysis sample.
with_judge <- function(j) {
  lab <- JUDGES %>% filter(judge_model == j) %>%
    select(prompt_id, prompt_language, model, jc = engagement_code)
  CANON_ENGLISH %>% inner_join(lab, by = c("prompt_id", "prompt_language", "model")) %>%
    mutate(refused_strict = as.integer(jc >= 4), refused_any = as.integer(jc >= 3))
}
judge_frames <- c(setNames(list(CANON_ENGLISH), CANON_JUDGE),
                  setNames(lapply(sort(unique(JUDGES$judge_model)), with_judge),
                           sort(unique(JUDGES$judge_model))))

# --- headline quantities, recomputed under each judge -------------------------
q_overall_rate <- function(d) mean(d$refused_strict)
q_home_diff <- function(d, j) {
  dd <- d %>% filter(juris == j, home_status %in% c("home", "away"))
  if (!nrow(dd)) return(NA_real_)
  h <- dd %>% filter(home_status == "home"); a <- dd %>% filter(home_status == "away")
  if (!nrow(h) || !nrow(a)) return(NA_real_)
  sum(w_equal_model(h) * h$refused_strict) - sum(w_equal_model(a) * a$refused_strict)
}
q_framing <- function(d) {
  fb <- d %>% group_by(issue_id, model) %>%
    summarise(nr = sum(tier == "regular"), nb = sum(tier == "boundary"),
              mr = mean(refused_strict[tier == "regular"]),
              mb = mean(refused_strict[tier == "boundary"]), .groups = "drop") %>%
    filter(nr > 0, nb > 0) %>% mutate(d = mb - mr)
  mean(tapply(fb$d, as.character(fb$model), mean))
}

rows <- list()
for (j in names(judge_frames)) {
  d <- judge_frames[[j]]
  rows[[length(rows) + 1]] <- tibble(
    judge_model = j, quantity = "overall refusal rate (English)",
    level = NA_character_, estimate = q_overall_rate(d), n = nrow(d))
  for (jj in JURIS_C)
    rows[[length(rows) + 1]] <- tibble(
      judge_model = j, quantity = "descriptive home - away", level = jj,
      estimate = q_home_diff(d, jj), n = sum(d$juris == jj))
  rows[[length(rows) + 1]] <- tibble(
    judge_model = j, quantity = "paired framing (boundary - regular)",
    level = NA_character_, estimate = q_framing(d), n = nrow(d))
}
c17 <- bind_rows(rows) %>% mutate(estimate_pp = pp(estimate))

# --- judge SPREAD: a range, explicitly not an interval ------------------------
spread <- c17 %>% filter(!is.na(estimate)) %>%
  group_by(quantity, level) %>%
  summarise(n_judges = n(), canonical = estimate[judge_model == CANON_JUDGE][1],
            min_across_judges = min(estimate), max_across_judges = max(estimate),
            range_pp = pp(max(estimate) - min(estimate)), .groups = "drop") %>%
  mutate(judge_model = "ACROSS-JUDGE RANGE",
         estimate = canonical, estimate_pp = pp(canonical),
         note = paste("range across judges is INSTRUMENT SENSITIVITY, not sampling",
                      "uncertainty; do not pool it with a bootstrap interval"))

# --- reliability, carried through from the panel layer ------------------------
rel_files <- c("e23_reliability_pass1.csv", "e25_reliability_slant.csv")
rel <- map_dfr(rel_files, function(f) {
  p <- file.path("pipeline/estimates", f)
  if (!file.exists(p)) return(NULL)
  read_csv(p, show_col_types = FALSE) %>%
    transmute(judge_model = "PANEL (all judges)", quantity = "reliability",
              level = construct, estimate = krippendorff_alpha,
              gwet_ac1 = gwet_ac1, raw_agreement = raw_agreement,
              positive_specific_agreement = if ("positive_specific_agreement" %in% names(.))
                positive_specific_agreement else NA_real_,
              n = n_units)
})

c17 <- bind_rows(c17, spread, rel) %>%
  mutate(canonical_outcome = CANON_JUDGE,
         majority_vote_used = FALSE,
         majority_vote_rationale = paste("no human calibration exists, so there is",
           "no basis for treating a majority label as ground truth"),
         annotation_error_layer = "DISABLED; draw_latent_labels() now requires stratum-specific prevalence and refuses to run without validation inputs",
         judge_coverage = "English only; judge-specific versions exist for English headline quantities only",
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(c17, file.path(CAN_EST, "c17_measurement_sensitivity.csv"))

cat("\noverall English refusal rate by judge:\n")
print(as.data.frame(c17 %>% filter(quantity == "overall refusal rate (English)") %>%
        select(judge_model, estimate_pp, n)), digits = 3, row.names = FALSE)
cat("\nacross-judge range on headline quantities (pp):\n")
print(as.data.frame(spread %>% select(quantity, level, canonical, range_pp) %>%
        mutate(canonical_pp = pp(canonical)) %>% select(-canonical)),
      digits = 3, row.names = FALSE)
}

flush_diag()
cat("\n", strrep("=", 78), "\nPART 4 DONE\n", strrep("=", 78), "\n", sep = "")
