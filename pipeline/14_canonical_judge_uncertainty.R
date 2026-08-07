# =============================================================================
# CANONICAL PART 4 -- judge sensitivity   -> c17, c17b, c17c
# =============================================================================
# PRINCIPLE. The canonical outcome is the Gemini 2.5 Flash-Lite label. Every
# other judge is a SENSITIVITY DIMENSION, reported separately and never pooled
# into a consensus.
#
# No majority vote is computed. With no human-validated labels there is no basis
# for asserting the majority is correct, and a consensus label would conceal
# precisely the disagreement these tables exist to expose.
#
# COMMON SUPPORT IS THE WHOLE POINT OF THIS FILE. An earlier version compared
# the canonical judge on the full English sample against each alternative judge
# on whatever that judge happened to have labelled -- nemotron-3-super covers
# 16,576 of 27,450 English responses -- and attributed the whole difference to
# the instrument. Part of it was composition. Every comparison here is computed
# on an explicit common-support sample with BOTH judges recomputed on it.
#
# WHAT THE ENVELOPE IS. The spread across judges is an OBSERVED JUDGE
# SENSITIVITY ENVELOPE: the range of what these four instruments produced on one
# shared sample. It is not a confidence interval, not a statistical bound, and
# has no coverage guarantee. It is never combined with a sampling interval.

source("pipeline/10_canonical_common.R")
cat(strrep("=", 78), "\nCANONICAL PART 4: JUDGE SENSITIVITY\n", strrep("=", 78), "\n", sep = "")

CANON_JUDGE <- "google/gemini-2.5-flash-lite"
CANON_KEY   <- c("prompt_id", "prompt_language", "model")
ENVELOPE_LABEL <- "OBSERVED JUDGE SENSITIVITY ENVELOPE"
B_JUDGE <- as.integer(Sys.getenv("CANON_B_JUDGE", "600"))

JUDGES <- load_judge_panel(language = "en", fields = "engagement_code")
if (is.null(JUDGES) || !nrow(JUDGES)) {
  cat("No panel judges found. Writing empty c17/c17b.\n")
  for (f in c("c17_measurement_sensitivity.csv", "c17b_judge_envelope.csv",
              "c17c_judge_support.csv"))
    write_csv(tibble(canonical_run_id = CANONICAL_RUN_ID,
                     note = "no additional judges available"),
              file.path(CAN_EST, f))
  flush_diag(); quit(save = "no", status = 0)
}

judge_lab <- JUDGES %>% select(all_of(CANON_KEY), judge_model, engagement_code)
alt_judges <- setdiff(sort(unique(judge_lab$judge_model)), CANON_JUDGE)
all_judges <- c(CANON_JUDGE, alt_judges)

cov <- judge_lab %>% count(judge_model, name = "n_labels") %>%
  mutate(coverage_of_english = n_labels / nrow(CANON_ENGLISH))
cat("judge coverage of the English analysis sample:\n")
print(as.data.frame(cov %>% mutate(pct = round(100 * coverage_of_english, 1)) %>%
                      select(judge_model, n_labels, pct)), row.names = FALSE)

# =============================================================================
# Common-support machinery
# =============================================================================
# Keys covered by EVERY judge in `js`, intersected with the analysis sample.
#
# The canonical judge is not in the panel file: its labels ARE the analysis
# sample, produced in the main annotation pass. So its coverage is
# CANON_ENGLISH by construction, and only the alternative judges constrain the
# intersection. Requiring the canonical judge to appear in the panel returned an
# empty set and silently produced n = 0 everywhere.
keys_of <- function(js) {
  alts <- setdiff(js, CANON_JUDGE)
  k_en <- CANON_ENGLISH %>% distinct(across(all_of(CANON_KEY)))
  if (!length(alts)) return(k_en)
  judge_lab %>% filter(judge_model %in% alts) %>%
    distinct(across(all_of(CANON_KEY)), judge_model) %>%
    count(across(all_of(CANON_KEY)), name = "k") %>%
    filter(k == length(alts)) %>% select(all_of(CANON_KEY)) %>%
    inner_join(k_en, by = CANON_KEY)
}

# One judge's labels on a given key set. The canonical judge's labels come from
# the analysis sample itself; alternative judges' come from the panel.
frame_for <- function(j, keys) {
  base <- CANON_ENGLISH %>% inner_join(keys, by = CANON_KEY)
  if (identical(j, CANON_JUDGE)) return(base)
  lab <- judge_lab %>% filter(judge_model == j) %>%
    select(all_of(CANON_KEY), jc = engagement_code)
  base %>% inner_join(lab, by = CANON_KEY) %>%
    mutate(refused_strict = as.integer(jc >= 4),
           refused_any    = as.integer(jc >= 3))
}

W_EN <- w_nested(CANON_ENGLISH)
KEY_EN <- paste(CANON_ENGLISH$prompt_id, CANON_ENGLISH$prompt_language,
                CANON_ENGLISH$model)

support_desc <- function(d, comparison, js) {
  k <- paste(d$prompt_id, d$prompt_language, d$model)
  tibble(comparison = comparison, judges = paste(js, collapse = " + "),
         n_rows = nrow(d), n_issues = n_distinct(d$issue_id),
         n_models = n_distinct(d$model),
         events_home = sum(d$refused_strict[d$home_status == "home"]),
         events_away = sum(d$refused_strict[d$home_status == "away"]),
         response_coverage = nrow(d) / nrow(CANON_ENGLISH),
         target_weight_retained = sum(W_EN[KEY_EN %in% k]))
}

# =============================================================================
# c17c -- what each comparison is computed on
# =============================================================================
K_PAIR <- setNames(lapply(alt_judges, function(j) keys_of(c(CANON_JUDGE, j))),
                   alt_judges)
K_ALL  <- keys_of(all_judges)
cat(sprintf("\nall-judge common support: %s of %s English responses\n",
            format(nrow(K_ALL), big.mark = ","),
            format(nrow(CANON_ENGLISH), big.mark = ",")))

c17c <- bind_rows(
  map_dfr(alt_judges, function(j)
    support_desc(frame_for(CANON_JUDGE, K_PAIR[[j]]),
                 paste("pairwise:", CANON_JUDGE, "vs", j), c(CANON_JUDGE, j))),
  support_desc(frame_for(CANON_JUDGE, K_ALL), "all-judge intersection", all_judges)
) %>% mutate(canonical_run_id = CANONICAL_RUN_ID)
write_csv(c17c, file.path(CAN_EST, "c17c_judge_support.csv"))
print(as.data.frame(c17c %>% select(comparison, n_rows, n_issues, n_models,
                                    response_coverage, target_weight_retained)),
      digits = 3, row.names = FALSE)

# =============================================================================
# c17 -- headline quantities, every comparison on its own common support
# =============================================================================
q_rate <- function(d) mean(d$refused_strict)
q_home <- function(d, jj) {
  dd <- d %>% filter(juris == jj, home_status %in% c("home", "away"))
  if (!nrow(dd)) return(NA_real_)
  h <- dd %>% filter(home_status == "home"); a <- dd %>% filter(home_status == "away")
  if (!nrow(h) || !nrow(a)) return(NA_real_)
  sum(w_equal_model(h) * h$refused_strict) - sum(w_equal_model(a) * a$refused_strict)
}
q_frame <- function(d) {
  fb <- d %>% group_by(issue_id, model) %>%
    summarise(nr = sum(tier == "regular"), nb = sum(tier == "boundary"),
              mr = mean(refused_strict[tier == "regular"]),
              mb = mean(refused_strict[tier == "boundary"]), .groups = "drop") %>%
    filter(nr == 2, nb == 2) %>% mutate(dd = mb - mr)   # complete blocks only
  if (!nrow(fb)) return(NA_real_)
  mean(tapply(fb$dd, as.character(fb$model), mean))
}

one_comparison <- function(js, keys, comparison) {
  map_dfr(js, function(j) {
    d <- frame_for(j, keys)
    bind_rows(
      tibble(quantity = "overall refusal rate (English)", level = NA_character_,
             estimate = q_rate(d)),
      map_dfr(JURIS_C, function(jj)
        tibble(quantity = "descriptive home - away", level = jj,
               estimate = q_home(d, jj))),
      tibble(quantity = "paired framing (boundary - regular, complete blocks)",
             level = NA_character_, estimate = q_frame(d))) %>%
      mutate(judge_model = j, comparison = comparison, n_rows = nrow(d))
  })
}

c17 <- bind_rows(
  map_dfr(alt_judges, function(j)
    one_comparison(c(CANON_JUDGE, j), K_PAIR[[j]],
                   paste("pairwise:", CANON_JUDGE, "vs", j))),
  one_comparison(all_judges, K_ALL, "all-judge intersection")) %>%
  mutate(estimate_pp = pp(estimate), is_canonical_judge = judge_model == CANON_JUDGE)

# The envelope is computed ONLY on the all-judge intersection, where every judge
# is measured on the same responses.
env_rows <- c17 %>% filter(comparison == "all-judge intersection", !is.na(estimate)) %>%
  group_by(quantity, level) %>%
  summarise(n_judges = n(),
            canonical = estimate[judge_model == CANON_JUDGE][1],
            envelope_min = min(estimate), envelope_max = max(estimate),
            .groups = "drop") %>%
  mutate(judge_model = ENVELOPE_LABEL, comparison = "all-judge intersection",
         estimate = canonical, estimate_pp = pp(canonical),
         envelope_width_pp = pp(envelope_max - envelope_min),
         point_sign_stable = (envelope_min > 0 & envelope_max > 0) |
                             (envelope_min < 0 & envelope_max < 0),
         note = paste("range of what four instruments produced on one shared",
                      "sample; NOT a confidence interval and NOT a statistical",
                      "bound; never combined with a sampling interval"))

c17 <- bind_rows(c17, env_rows) %>%
  mutate(canonical_outcome = CANON_JUDGE,
         majority_vote_used = FALSE,
         majority_vote_rationale = paste("no human-validated labels exist, so",
           "there is no basis for treating a majority label as ground truth"),
         common_support = "every comparison uses a sample both/all judges rated; see c17c",
         judge_coverage = "English only; no judge-sensitivity estimate exists for the language estimand",
         annotation_error_layer = "DISABLED; draw_latent_labels() refuses to run without validation inputs",
         canonical_run_id = CANONICAL_RUN_ID)

# =============================================================================
# c17b -- the standardized contrast under each judge, on common support
# =============================================================================
cat("\nc17b: standardized home contrast under each judge (B =", B_JUDGE, ")\n")

std_under <- function(d, j, jj, comparison) {
  why <- estimable_chk(d, "refused_strict")
  base <- tibble(judge_model = j, jurisdiction = jj, comparison = comparison,
                 n = nrow(d), n_issues = n_distinct(d$issue_id),
                 events_home = sum(d$refused_strict[d$home == 1]),
                 events_away = sum(d$refused_strict[d$home == 0]))
  if (nzchar(why))
    return(bind_cols(base, tibble(estimate = NA_real_, conf_low = NA_real_,
                                  conf_high = NA_real_, estimable = FALSE,
                                  interval_reliable = FALSE, note = why)))
  bt <- boot_canon(d, function(x) gcomp(x, w_nested), B = B_JUDGE,
                   label = sprintf("c17b|%s|%s|%s", substr(comparison, 1, 12), jj, j))
  record_diag(bt$diag)
  bind_cols(base, tibble(estimate = bt$estimate, conf_low = bt$conf_low,
                         conf_high = bt$conf_high, estimable = TRUE,
                         interval_reliable = bt$interval_reliable, note = ""))
}

c17b <- map_dfr(all_judges, function(j) {
  d <- frame_for(j, K_ALL) %>% filter(home_status %in% c("home", "away"))
  map_dfr(JURIS_C, function(jj) {
    dd <- d %>% filter(juris == jj) %>% droplevels()
    cat(sprintf("    %-34s %-6s n=%d\n", substr(j, 1, 34), jj, nrow(dd)))
    std_under(dd, j, jj, "all-judge intersection")
  })
})

# The envelope is the range of the four estimates and of their intervals, all
# from the SAME sample. The full-sample c04 interval is deliberately NOT mixed
# in: it is estimated on a different (larger) sample, and inserting it would
# produce a range that no single comparison supports.
env <- c17b %>% filter(estimable) %>%
  group_by(jurisdiction) %>%
  summarise(n_judges = n(),
            canonical = estimate[judge_model == CANON_JUDGE][1],
            canonical_low = conf_low[judge_model == CANON_JUDGE][1],
            canonical_high = conf_high[judge_model == CANON_JUDGE][1],
            point_min = min(estimate), point_max = max(estimate),
            envelope_low = min(conf_low), envelope_high = max(conf_high),
            .groups = "drop") %>%
  mutate(judge_model = ENVELOPE_LABEL, comparison = "all-judge intersection",
         estimate = canonical, conf_low = envelope_low, conf_high = envelope_high,
         estimable = TRUE, interval_reliable = NA,
         # Two different claims. Every judge agreeing on direction is weaker
         # than the union of their intervals clearing zero.
         point_sign_stable = (point_min > 0 & point_max > 0) |
                             (point_min < 0 & point_max < 0),
         envelope_excludes_zero = (envelope_low > 0) | (envelope_high < 0),
         note = paste("observed range across four instruments on one shared",
                      "sample; NOT a confidence interval"))

c17b <- bind_rows(
  c17b %>% mutate(interval_type = "95% issue-cluster bootstrap, instrument held fixed"),
  env  %>% mutate(interval_type = "OBSERVED JUDGE SENSITIVITY ENVELOPE, no coverage guarantee")) %>%
  mutate(estimate_pp = pp(estimate), conf_low_pp = pp(conf_low),
         conf_high_pp = pp(conf_high),
         quantity = "standardized home - away refusal contrast",
         sample = "all-judge common support (see c17c)",
         spec = "refused_strict ~ home * model + tier + domain + route; nested weights; g-computation",
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(c17b, file.path(CAN_EST, "c17b_judge_envelope.csv"))

cat("\nstandardized contrast (pp), all-judge common support:\n")
print(as.data.frame(c17b %>% filter(estimable) %>%
        transmute(jurisdiction, judge = substr(judge_model, 1, 36),
                  est = round(estimate_pp, 2), lo = round(conf_low_pp, 2),
                  hi = round(conf_high_pp, 2))), row.names = FALSE)
cat("\nevery judge agrees on direction:",
    paste(env$jurisdiction[env$point_sign_stable], collapse = ", "), "\n")
cat("envelope excludes zero        :",
    paste(env$jurisdiction[env$envelope_excludes_zero], collapse = ", "), "\n")

# --- reliability, carried through from the panel layer ------------------------
rel_files <- c("e23_reliability_pass1.csv", "e25_reliability_slant.csv")
rel <- map_dfr(rel_files, function(f) {
  p <- file.path("pipeline/estimates", f)
  if (!file.exists(p)) return(NULL)
  x <- read_csv(p, show_col_types = FALSE)
  tibble(judge_model = "PANEL (all judges)", quantity = "reliability",
         level = x$construct, estimate = x$krippendorff_alpha,
         gwet_ac1 = if ("gwet_ac1" %in% names(x)) x$gwet_ac1 else NA_real_,
         raw_agreement = if ("raw_agreement" %in% names(x)) x$raw_agreement else NA_real_,
         psa_mean = if ("psa_mean" %in% names(x)) x$psa_mean else NA_real_,
         psa_min = if ("psa_min" %in% names(x)) x$psa_min else NA_real_,
         psa_max = if ("psa_max" %in% names(x)) x$psa_max else NA_real_,
         n_rows = x$n_units,
         n_units_complete = if ("n_units_complete" %in% names(x)) x$n_units_complete else NA_integer_)
})
c17 <- bind_rows(c17, rel %>% mutate(comparison = "panel reliability",
                                     canonical_run_id = CANONICAL_RUN_ID))
write_csv(c17, file.path(CAN_EST, "c17_measurement_sensitivity.csv"))

cat("\noverall English refusal rate, all-judge common support:\n")
print(as.data.frame(c17 %>%
        filter(quantity == "overall refusal rate (English)",
               comparison == "all-judge intersection") %>%
        select(judge_model, estimate_pp, n_rows)), digits = 3, row.names = FALSE)

flush_diag()
cat("\n", strrep("=", 78), "\nPART 4 DONE\n", strrep("=", 78), "\n", sep = "")
