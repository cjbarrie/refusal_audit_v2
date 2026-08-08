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
ENVELOPE_LABEL <- "OBSERVED JUDGE POINT ENVELOPE"
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
# THREE DISTINCT QUANTITIES, kept apart. An earlier version defined "the
# envelope" as min(conf_low) to max(conf_high) -- the UNION OF PER-JUDGE
# BOOTSTRAP INTERVALS -- and then called it the observed judge envelope. Those
# are not the same thing: the union mixes sampling uncertainty into a quantity
# that is supposed to describe instrument variation, and it is wider than the
# judge disagreement it purports to show.
#
#   1. observed judge point envelope -- min/max of the judge POINT estimates.
#      This is the instrument-variation quantity. No sampling uncertainty in it.
#   2. per-judge sampling interval    -- each judge's own issue-cluster bootstrap.
#   3. union of judge-specific 95% intervals -- reported, but named exactly that,
#      never "envelope", and never treated as an interval with coverage for
#      judge uncertainty.
env <- c17b %>% filter(estimable) %>%
  group_by(jurisdiction) %>%
  summarise(n_judges = n(),
            canonical = estimate[judge_model == CANON_JUDGE][1],
            canonical_low = conf_low[judge_model == CANON_JUDGE][1],
            canonical_high = conf_high[judge_model == CANON_JUDGE][1],
            point_envelope_low  = min(estimate),
            point_envelope_high = max(estimate),
            union_low  = min(conf_low),
            union_high = max(conf_high),
            .groups = "drop") %>%
  mutate(judge_model = ENVELOPE_LABEL, comparison = "all-judge intersection",
         estimate = canonical,
         # conf_low/high on THIS row are the POINT envelope, so anything that
         # plots conf_low..conf_high for the envelope row draws instrument
         # variation, not a mixture.
         conf_low = point_envelope_low, conf_high = point_envelope_high,
         estimable = TRUE, interval_reliable = NA,
         point_sign_stable = (point_envelope_low > 0 & point_envelope_high > 0) |
                             (point_envelope_low < 0 & point_envelope_high < 0),
         point_envelope_excludes_zero = (point_envelope_low > 0) |
                                        (point_envelope_high < 0),
         union_excludes_zero = (union_low > 0) | (union_high < 0),
         note = paste("conf_low/conf_high on this row are the OBSERVED JUDGE",
                      "POINT ENVELOPE: the range of the four judges' point",
                      "estimates on one shared sample. It is not a confidence",
                      "interval. union_low/union_high are the union of the",
                      "judge-specific 95% intervals, reported separately and",
                      "never called an envelope."))

c17b <- bind_rows(
  c17b %>% mutate(interval_type = "95% issue-cluster bootstrap, instrument held fixed"),
  env  %>% mutate(interval_type = "OBSERVED JUDGE POINT ENVELOPE (range of judge point estimates); NOT a confidence interval")) %>%
  mutate(estimate_pp = pp(estimate), conf_low_pp = pp(conf_low),
         conf_high_pp = pp(conf_high),
         union_low_pp = pp(union_low), union_high_pp = pp(union_high),
         point_envelope_low_pp = pp(point_envelope_low),
         point_envelope_high_pp = pp(point_envelope_high),
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
cat("\nevery judge agrees on direction      :",
    paste(env$jurisdiction[env$point_sign_stable], collapse = ", "), "\n")
cat("point envelope excludes zero         :",
    paste(env$jurisdiction[env$point_envelope_excludes_zero], collapse = ", "), "\n")
cat("union of judge intervals excludes 0  :",
    paste(env$jurisdiction[env$union_excludes_zero], collapse = ", "), "\n")

# =============================================================================
# c17d -- PAIRED judge-minus-canonical difference
# =============================================================================
# A NEW ESTIMAND, not a re-expression of c17b. c17b answers "what does each
# judge produce"; this answers "how far does the estimate move when the judge
# changes", which is the actual sensitivity question.
#
#     Delta_{j,r} = theta_{j,r} - theta_{canonical,r}
#
# WHY IT CANNOT BE OBTAINED BY SUBTRACTING c17b. The four judges label THE SAME
# RESPONSES on the all-judge common-support sample, so their estimates are
# strongly positively dependent. Differencing two point estimates and carrying
# either one's marginal interval -- or combining the two marginal intervals --
# ignores that dependence and produces an interval far too wide. The difference
# must be formed INSIDE each replicate, on one shared issue draw.
#
# So: one bootstrap, one resampled issue set per replicate, every judge's
# contrast recomputed on that same draw, differences taken within the draw.
# Same bootstrap unit (issue_id), same multiplicity labelling
# (bootstrap_issue_instance), same fixed-B rule -- failures counted, never
# replaced -- as every other interval in this layer.
#
# ZERO on this scale means the alternative judge reproduces the canonical
# judge's estimate. It does NOT mean either is correct. The canonical judge is a
# REFERENCE INSTRUMENT, not ground truth: no human-validated labels exist, which
# is also why no majority vote is computed anywhere in this file.
cat("\nc17d: paired judge-minus-canonical differences (B =", B_JUDGE, ")\n")

# One frame per jurisdiction carrying EVERY judge's label on the same rows, so a
# replicate can refit all four on one draw.
YCOL <- setNames(paste0("y_j", seq_along(all_judges)), all_judges)

paired_frame <- function(jj) {
  base <- frame_for(CANON_JUDGE, K_ALL) %>%
    filter(home_status %in% c("home", "away"), juris == jj) %>% droplevels()
  if (!nrow(base)) return(NULL)
  base[[YCOL[[CANON_JUDGE]]]] <- base$refused_strict
  for (j in alt_judges) {
    lab <- judge_lab %>% filter(judge_model == j) %>%
      select(all_of(CANON_KEY), .jc = engagement_code)
    base <- base %>% left_join(lab, by = CANON_KEY) %>%
      mutate("{YCOL[[j]]}" := as.integer(.jc >= 4)) %>% select(-.jc)
  }
  # K_ALL is the four-judge intersection, so no label may be missing here.
  stopifnot(!anyNA(base[unname(YCOL)]))
  base
}

# All judges' contrasts on ONE data frame. Returns a named vector, or NULL if
# any judge is undefined on this draw -- a replicate in which one judge fails is
# not a valid paired replicate for any comparison, so the whole draw fails.
all_contrasts <- function(dd) {
  v <- vapply(all_judges, function(j)
    suppressWarnings(gcomp(dd, w_nested, outcome = YCOL[[j]])), numeric(1))
  if (any(!is.finite(v))) return(NULL)
  v
}

boot_paired_judges <- function(d, jj, B = B_JUDGE, seed = CAN_SEED) {
  issues <- unique(d$issue_id)
  idx <- split(seq_len(nrow(d)), d$issue_id)
  d0 <- d; d0$bootstrap_issue_instance <- as.character(d0$issue_id)
  point <- tryCatch(all_contrasts(d0), error = function(e) NULL)
  if (is.null(point)) return(NULL)

  set.seed(seed)
  reps <- matrix(NA_real_, nrow = B, ncol = length(all_judges),
                 dimnames = list(NULL, all_judges))
  for (b in seq_len(B)) {
    drawn <- sample(issues, length(issues), replace = TRUE)
    rows <- unlist(idx[drawn], use.names = FALSE)
    dd <- d[rows, , drop = FALSE]
    dd$bootstrap_issue_instance <-
      rep(paste0(drawn, "#", seq_along(drawn)), times = lengths(idx[drawn]))
    v <- tryCatch(all_contrasts(dd), error = function(e) NULL)
    if (!is.null(v)) reps[b, ] <- v
  }
  okrow <- stats::complete.cases(reps)
  nfail <- sum(!okrow); frate <- nfail / B
  # The difference is formed WITHIN the replicate, from the same issue draw.
  diffs <- reps[okrow, , drop = FALSE] - reps[okrow, CANON_JUDGE]
  record_diag(tibble(
    canonical_run_id = CANONICAL_RUN_ID,
    label = sprintf("c17d|paired|%s", jj), bootstrap_unit = "issue_id",
    multiplicity_preserved = TRUE, copy_id_column = "bootstrap_issue_instance",
    seed = seed, replicates_requested = B, replicates_drawn = B,
    replicates_successful = sum(okrow), replicates_failed = nfail,
    failure_rate = frate, failed_draws_replaced = FALSE,
    interval_reliable = frate <= 0.02, interval_method = "percentile (paired)",
    n_rows = nrow(d), n_issues = length(issues)))

  map_dfr(all_judges, function(j) {
    dv <- diffs[, j]
    tibble(judge_model = j, jurisdiction = jj,
           is_canonical_judge = identical(j, CANON_JUDGE),
           judge_estimate = point[[j]], canonical_estimate = point[[CANON_JUDGE]],
           estimate = point[[j]] - point[[CANON_JUDGE]],
           conf_low  = if (length(dv) > 1) unname(quantile(dv, .025)) else NA_real_,
           conf_high = if (length(dv) > 1) unname(quantile(dv, .975)) else NA_real_,
           n = nrow(d), n_issues = length(issues),
           replicates_drawn = B, replicates_failed = nfail,
           failure_rate = frate, interval_reliable = frate <= 0.02)
  })
}

c17d <- map_dfr(JURIS_C, function(jj) {
  d <- paired_frame(jj)
  if (is.null(d)) return(NULL)
  why <- estimable_chk(d, YCOL[[CANON_JUDGE]])
  cat(sprintf("    %-6s n=%-6d %s\n", jj, nrow(d),
              if (nzchar(why)) paste("NOT ESTIMABLE:", why) else ""))
  if (nzchar(why))
    return(tibble(judge_model = all_judges, jurisdiction = jj,
                  is_canonical_judge = all_judges == CANON_JUDGE,
                  estimate = NA_real_, conf_low = NA_real_, conf_high = NA_real_,
                  n = nrow(d), n_issues = n_distinct(d$issue_id),
                  estimable = FALSE, note = why))
  out <- boot_paired_judges(d, jj)
  if (is.null(out))
    return(tibble(judge_model = all_judges, jurisdiction = jj,
                  is_canonical_judge = all_judges == CANON_JUDGE,
                  estimate = NA_real_, conf_low = NA_real_, conf_high = NA_real_,
                  n = nrow(d), n_issues = n_distinct(d$issue_id),
                  estimable = FALSE, note = "point estimate undefined for at least one judge"))
  out %>% mutate(estimable = TRUE, note = "")
}) %>%
  mutate(estimate_pp = pp(estimate), conf_low_pp = pp(conf_low),
         conf_high_pp = pp(conf_high),
         judge_estimate_pp = pp(judge_estimate),
         canonical_estimate_pp = pp(canonical_estimate),
         quantity = "PAIRED difference in the standardized home-away contrast: this judge minus the canonical judge",
         reference_judge = CANON_JUDGE,
         paired = TRUE,
         bootstrap_unit = "issue_id",
         interval_type = paste("95% PAIRED issue-cluster bootstrap: both judges",
                               "recomputed on the SAME resampled issue set in",
                               "every replicate, difference taken within the",
                               "replicate; percentile"),
         sample = "all-judge common support (see c17c)",
         spec = "refused_strict ~ home * model + tier + domain + route; nested weights; g-computation; identical under every judge",
         interpretation = paste("Zero means this judge reproduces the canonical",
                                "judge's estimate on the same sample. The",
                                "canonical judge is a REFERENCE INSTRUMENT, not",
                                "ground truth: no human-validated labels exist,",
                                "so no judge is known to be correct. This is NOT",
                                "the difference of the two marginal intervals in",
                                "c17b, which would ignore the dependence induced",
                                "by both judges labelling the same responses."),
         canonical_run_id = CANONICAL_RUN_ID)
write_csv(c17d, file.path(CAN_EST, "c17d_judge_paired_differences.csv"))

cat("\npaired judge-minus-canonical difference (pp):\n")
print(as.data.frame(c17d %>% filter(estimable, !is_canonical_judge) %>%
        transmute(jurisdiction, judge = substr(judge_model, 1, 36),
                  diff = round(estimate_pp, 2), lo = round(conf_low_pp, 2),
                  hi = round(conf_high_pp, 2))), row.names = FALSE)

# --- reliability, carried through from the panel layer ------------------------
rel_files <- c("e23_reliability_pass1.csv", "e25_reliability_slant.csv")
rel <- map_dfr(rel_files, function(f) {
  p <- file.path(CAN_EST, f)   # this release's build, not the global directory
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
