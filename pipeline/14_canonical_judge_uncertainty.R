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

source("pipeline/10_canonical_common.R")
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

# =============================================================================
# c17b -- the standardized contrast refit under every judge, and the envelope
# =============================================================================
# WHAT UNCERTAINTY THE PANEL CAN AND CANNOT BUY.
#
# A bootstrap interval under one judge answers: if we drew another sample of
# issues, and kept this instrument, how much would the estimate move? It holds
# the instrument FIXED, so it says nothing about the labels being wrong.
#
# Refitting under each judge adds the second question: if we kept this sample of
# issues and swapped the instrument, how much would the estimate move? The
# reported envelope is the UNION of the per-judge intervals,
#     [ min_j conf_low_j , max_j conf_high_j ],
# which is a SENSITIVITY BOUND, not a confidence interval. It has no coverage
# guarantee, because four judges chosen for cost and speed are not a sample from
# a population of judges and none of them is known to be correct. It would be
# conservative only under an assumption we do NOT make -- that the true labelling
# is one of the four. Quoted as a bound it is honest; quoted as a 95% interval it
# would be a fabrication, so `interval_type` says which it is on every row.
#
# The specification is the shared gcomp() from 10_canonical_common.R -- the same
# one 51 uses -- so a difference between judges here cannot be a difference in
# model.
B_JUDGE <- as.integer(Sys.getenv("CANON_B_JUDGE", "600"))
cat("\nc17b: standardized home contrast under each judge (B =", B_JUDGE, ")\n")

std_under <- function(d, j, tag) {
  why <- estimable_chk(d)
  base <- tibble(judge_model = j, jurisdiction = tag,
                 n = nrow(d), n_issues = n_distinct(d$issue_id),
                 events_home = sum(d$refused_strict[d$home == 1]),
                 events_away = sum(d$refused_strict[d$home == 0]))
  if (nzchar(why))
    return(bind_cols(base, tibble(estimate = NA_real_, conf_low = NA_real_,
                                  conf_high = NA_real_, estimable = FALSE,
                                  note = why)))
  bt <- boot_canon(d, function(x) gcomp(x, w_nested), B = B_JUDGE,
                   label = sprintf("c17b|%s|%s", tag, j))
  record_diag(bt$diag)
  bind_cols(base, tibble(estimate = bt$estimate, conf_low = bt$conf_low,
                         conf_high = bt$conf_high, estimable = TRUE, note = ""))
}

c17b <- map_dfr(names(judge_frames), function(j) {
  dj <- judge_frames[[j]] %>% filter(home_status %in% c("home", "away"))
  map_dfr(JURIS_C, function(jj) {
    d <- dj %>% filter(juris == jj) %>% droplevels()
    cat(sprintf("    %-34s %-6s n=%d\n", substr(j, 1, 34), jj, nrow(d)))
    std_under(d, j, jj)
  })
})

# The canonical judge's own interval enters the union from c04, not from the
# pass above: c04 is fit with the full B (2,000) while these judge refits use a
# smaller B for runtime, and an envelope that failed to contain the interval the
# paper actually quotes would be incoherent -- the union must nest it.
c04_ref <- if (file.exists(file.path(CAN_EST, "c04_home_standardized.csv")))
  read_csv(file.path(CAN_EST, "c04_home_standardized.csv"), show_col_types = FALSE) %>%
    filter(weighting == "nested", estimable) %>%
    select(jurisdiction, c04_est = estimate, c04_low = conf_low,
           c04_high = conf_high) else NULL

env <- c17b %>% filter(estimable) %>%
  group_by(jurisdiction) %>%
  summarise(n_judges = n(),
            canonical = estimate[judge_model == CANON_JUDGE][1],
            canonical_low = conf_low[judge_model == CANON_JUDGE][1],
            canonical_high = conf_high[judge_model == CANON_JUDGE][1],
            point_min = min(estimate), point_max = max(estimate),
            envelope_low = min(conf_low), envelope_high = max(conf_high),
            .groups = "drop") %>%
  { if (is.null(c04_ref)) . else
      left_join(., c04_ref, by = "jurisdiction") %>%
      mutate(canonical = coalesce(c04_est, canonical),
             canonical_low = coalesce(c04_low, canonical_low),
             canonical_high = coalesce(c04_high, canonical_high),
             envelope_low = pmin(envelope_low, coalesce(c04_low, envelope_low)),
             envelope_high = pmax(envelope_high, coalesce(c04_high, envelope_high))) %>%
      select(-any_of(c("c04_est", "c04_low", "c04_high"))) } %>%
  mutate(judge_model = "ENVELOPE (union across judges)",
         estimate = canonical, conf_low = envelope_low, conf_high = envelope_high,
         estimable = TRUE,
         # Two different claims, and conflating them would overstate the
         # result: every judge agreeing on the direction is weaker than the
         # union of their intervals clearing zero.
         point_sign_stable = (point_min > 0 & point_max > 0) |
                             (point_min < 0 & point_max < 0),
         envelope_excludes_zero = (envelope_low > 0) | (envelope_high < 0),
         note = paste("union of per-judge bootstrap intervals: sampling AND",
                      "instrument variation; NOT a 95% confidence interval"))

c17b <- bind_rows(
  c17b %>% mutate(interval_type = "95% issue-cluster bootstrap, instrument held fixed"),
  env %>% mutate(interval_type = "SENSITIVITY ENVELOPE, no coverage guarantee")) %>%
  mutate(estimate_pp = pp(estimate), conf_low_pp = pp(conf_low),
         conf_high_pp = pp(conf_high),
         quantity = "standardized home - away refusal contrast",
         spec = "refused_strict ~ home * model + tier + domain + route; nested weights; g-computation",
         canonical_run_id = CANONICAL_RUN_ID)
stopifnot(all(env$envelope_low <= env$canonical_low + 1e-12),
          all(env$envelope_high >= env$canonical_high - 1e-12))
write_csv(c17b, file.path(CAN_EST, "c17b_judge_envelope.csv"))

cat("\nstandardized contrast (pp) by judge:\n")
print(as.data.frame(c17b %>% filter(estimable) %>%
        transmute(jurisdiction, judge = substr(judge_model, 1, 34),
                  est = round(estimate_pp, 2), lo = round(conf_low_pp, 2),
                  hi = round(conf_high_pp, 2))), row.names = FALSE)
cat("\nevery judge agrees on direction:",
    paste(env$jurisdiction[env$point_sign_stable], collapse = ", "), "\n")
cat("envelope clears zero          :",
    paste(env$jurisdiction[env$envelope_excludes_zero], collapse = ", "), "\n")

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
