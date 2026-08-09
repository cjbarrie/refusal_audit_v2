# =============================================================================
# CANONICAL PART 3 -- answer content, CONDITIONAL ON ENGAGEMENT
#   c12 ideology distribution     c15 moral by model
#   c13 ideology by model         c16 joint outcomes (refusal / absent / present)
#   c14 moral prevalence, equal-model
# =============================================================================
# EVERYTHING HERE IS CONDITIONAL ON ENGAGEMENT. Passes 2 and 3 are not run on
# refusals -- a refusal has no position to score -- so these describe how models
# lean WHEN THEY ANSWER, never how often they answer. A jurisdiction that refuses
# more contributes a differently selected set of responses, so content
# comparisons across jurisdictions are not like-for-like on the underlying
# population of prompts.
#
# REFUSALS ARE NEVER CODED AS FOUNDATION ABSENCE. A refusal is a third outcome,
# reported in c16 as its own category. Treating "did not invoke care/harm"
# and "refused to answer" as the same zero would be a category error.

source("pipeline/10_canonical_common.R")
cat(strrep("=", 78), "\nCANONICAL PART 3: CONTENT | ENGAGED\n", strrep("=", 78), "\n", sep = "")

B_HEAD <- as.integer(Sys.getenv("CANON_B_HEAD", "2000"))
B_SENS <- as.integer(Sys.getenv("CANON_B_SENS", "500"))

IDEO <- c(economic_left_right = "Economic", social_left_right = "Social",
          authoritarian_libertarian = "Authority", populist_elitist = "Populism")
MFT <- c(care_harm = "Care / harm", fairness_cheating = "Fairness / cheating",
         liberty_oppression = "Liberty / oppression",
         authority_subversion = "Authority / subversion",
         loyalty_betrayal = "Loyalty / betrayal",
         sanctity_degradation = "Sanctity / degradation")

CONDITIONAL <- "CONDITIONAL ON ENGAGEMENT: passes 2/3 skip refusals by design"

# =============================================================================
# A. COVERAGE -- recomputed, not assumed
# =============================================================================
cat("\nA. slant coverage (recomputed)\n")
elig <- canon %>% filter(slant_eligible, engaged)
cov_lang <- elig %>% group_by(language = as.character(lang)) %>%
  summarise(eligible_engaged = n(), coded = sum(has_slant),
            coverage = mean(has_slant), .groups = "drop")
cov_model <- elig %>% group_by(language = as.character(lang), model) %>%
  summarise(eligible_engaged = n(), coded = sum(has_slant),
            coverage = mean(has_slant), .groups = "drop")
print(as.data.frame(cov_lang %>% mutate(pct = round(100 * coverage, 1))), row.names = FALSE)

EN_OK <- cov_lang$eligible_engaged[cov_lang$language == "en"] ==
         cov_lang$coded[cov_lang$language == "en"]
stopifnot(EN_OK)
cat(sprintf("  English complete: %d/%d\n",
            cov_lang$coded[cov_lang$language == "en"],
            cov_lang$eligible_engaged[cov_lang$language == "en"]))
# Explicitly NOT claiming all-language completeness.
incomplete <- cov_lang %>% filter(coverage < 0.999) %>% pull(language)
cat("  INCOMPLETE languages (excluded from canonical content results):",
    paste(incomplete, collapse = ", "), "\n")

SLANT_EN <- canon %>% filter(slant_eligible, engaged, has_slant, lang == "en")
cat(sprintf("  canonical content sample: %d responses, %d issues, %d models\n",
            nrow(SLANT_EN), n_distinct(SLANT_EN$issue_id), n_distinct(SLANT_EN$model)))

# -----------------------------------------------------------------------------
# Two inference targets, and a design-based estimator for the second
# -----------------------------------------------------------------------------
# The 156 slant issues were drawn WITHOUT REPLACEMENT from the frozen 624-issue
# battery. Two targets are possible and they are not the same:
#
#   superpopulation -- issues are exchangeable draws from a wider population of
#                      possible issues. The ordinary issue-cluster bootstrap
#                      estimates this. It is the conservative default.
#   frozen battery  -- the 624 issues ARE the population of interest. Then the
#                      sampling fraction f = 156/624 matters and the variance
#                      carries a finite-population correction.
#
# WHAT THIS REPLACES. The previous version took the superpopulation percentile
# interval and shrank its half-widths by sqrt(1-f) after the fact. That is not a
# design-based correction: the percentile interval's shape comes from a
# with-replacement resampling model that does not match sampling 156 of 624
# without replacement, and rescaling it does not make it match. The
# finite-battery interval is now a delete-one-issue JACKKNIFE with an explicit
# FPC (jack_fpc in 10_canonical_common.R), which is a standard estimator for
# exactly this design and is tested against a census (f = 1 must give zero
# variance) and against the (1-f) variance scaling.
SLANT_N_SAMPLED <- n_distinct(SLANT_EN$issue_id)
SLANT_N_TOTAL   <- n_distinct(canon$issue_id)
cat(sprintf("  slant subsample: %d of %d issues (f = %.3f)\n",
            SLANT_N_SAMPLED, SLANT_N_TOTAL, SLANT_N_SAMPLED / SLANT_N_TOTAL))

TARGET_NOTE <- paste0(
  "conf_low/conf_high target an issue SUPERPOPULATION (issue-cluster bootstrap, ",
  "percentile). conf_low_battery/conf_high_battery target the frozen ",
  SLANT_N_TOTAL, "-issue battery (delete-one-issue jackknife with finite-",
  "population correction, normal approximation). They answer different ",
  "questions; neither is a correction of the other.")

# Superpopulation interval: the shared, multiplicity-preserving, fixed-B
# bootstrap. Failures are counted, never resampled past.
boot_slant <- function(d, stat, B, label) {
  bt <- boot_canon(d, stat, B = B, label = label)
  record_diag(bt$diag)
  bt
}

# Frozen-battery interval: design-based.
jack_slant <- function(d, stat, label) {
  jk <- jack_fpc(d, stat, n_total = SLANT_N_TOTAL, label = paste0(label, "|jack"))
  record_diag(jk$diag)
  jk
}

# Both, in one row.
both_intervals <- function(d, stat, B, label, bounded = FALSE) {
  bt <- boot_slant(d, stat, B, label)
  jk <- jack_slant(d, stat, label)
  # The frozen-battery interval is a NORMAL APPROXIMATION, so for a rare share
  # it can extend below zero. For a proportion the limits are computed on the
  # logit scale and mapped back, which keeps them inside [0, 1]; the raw
  # unbounded limits are retained alongside and labelled, because a reader
  # comparing to an older table needs to see both. A negative probability limit
  # is never plotted as a meaningful value.
  lo <- jk$conf_low; hi <- jk$conf_high
  if (bounded && is.finite(jk$se) && jk$estimate > 0 && jk$estimate < 1) {
    z <- stats::qnorm(0.975)
    se_l <- jk$se / (jk$estimate * (1 - jk$estimate))       # delta method
    eta <- stats::qlogis(jk$estimate)
    lo <- stats::plogis(eta - z * se_l); hi <- stats::plogis(eta + z * se_l)
  }
  list(estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high,
       battery_low = lo, battery_high = hi,
       battery_low_unbounded = jk$conf_low, battery_high_unbounded = jk$conf_high,
       battery_scale = if (bounded) "logit, mapped back to [0,1]" else "identity (unbounded normal)",
       battery_se = jk$se, interval_reliable = bt$interval_reliable)
}

# equal-model weighting: model means first, then unweighted mean of models
eqm <- function(d, col) mean(tapply(d[[col]], as.character(d$model), mean))

# =============================================================================
# B. IDEOLOGY  (c12, c13)
# =============================================================================
# PRIMARY ESTIMAND: the full distribution over -2,-1,0,1,2. The signed mean is
# SECONDARY -- with 74-93% of codes at exactly 0 a mean compresses a highly
# concentrated distribution into one number and invites over-reading.
cat("\nB. ideology (model-level first, then equal-model aggregates)\n")

# -----------------------------------------------------------------------------
# Model-level content estimands CARRY UNCERTAINTY
# -----------------------------------------------------------------------------
# c13 and c15 used to be point estimates and nothing else, which made them
# unusable for the model-comparison figures they exist to support: eleven bare
# numbers invite ranking, and nothing on the row said whether the gap between
# first and last was larger than the noise.
#
# Every model-level row now carries BOTH inference targets, exactly as the
# aggregate tables do -- the issue-cluster bootstrap for an issue
# superpopulation, and the delete-one-issue jackknife with FPC for the frozen
# battery. Issues remain the resampling unit; a row-level bootstrap would treat
# the four prompts of one issue as independent and be far too narrow.
#
# The frame handed to the bootstrap is slimmed to the three columns the statistic
# needs. boot_canon() rebuilds a data frame on every replicate, and carrying
# forty unused columns through 500 replicates x 264 quantities is the difference
# between a minute and an hour.
#
# `both_intervals()` is the shared helper; nothing here re-implements it.
model_level <- function(d, f, stat, label, bounded = FALSE) {
  slim <- d %>% transmute(issue_id, model, .y = .data[[f]])
  r <- both_intervals(slim, stat, B_SENS, label, bounded = bounded)
  y <- slim$.y
  tibble(estimate = r$estimate, conf_low = r$conf_low, conf_high = r$conf_high,
         conf_low_battery = r$battery_low, conf_high_battery = r$battery_high,
         conf_low_battery_unbounded = r$battery_low_unbounded,
         conf_high_battery_unbounded = r$battery_high_unbounded,
         battery_se = r$battery_se, battery_scale = r$battery_scale,
         n = length(y), n_issues = n_distinct(slim$issue_id),
         # A constant outcome has a defined point and a degenerate interval.
         # Flagged, not silently reported as a precisely estimated value.
         degenerate_outcome = length(unique(y)) < 2,
         # Two clusters cannot support a jackknife; the flag says so rather than
         # letting a meaningless width through.
         support_ok = n_distinct(slim$issue_id) >= 10,
         estimable = length(y) > 0,
         interval_reliable = r$interval_reliable)
}

IDEO_BINS <- c(share_neg2 = -2L, share_neg1 = -1L, share_zero = 0L,
               share_pos1 = 1L, share_pos2 = 2L)

# Dimension-specific endpoints. "left/right" is meaningful for the economic
# scale and misleading for the other three: the authority scale runs
# authoritarian-libertarian and the populism scale populist-elitist, and
# labelling either "left" or "right" asserts a mapping the codebook does not
# make.
IDEO_ENDPOINTS <- tribble(
  ~field,                      ~endpoint_neg,     ~endpoint_pos,
  "economic_left_right",       "left",            "right",
  "social_left_right",         "progressive",     "traditional",
  "authoritarian_libertarian", "authoritarian",   "libertarian",
  "populist_elitist",          "populist",        "elitist")

# Panel alphas are read from THIS release's e25 and formatted into the warning,
# so the table can never claim a reliability figure the run did not produce.
.rel25 <- tryCatch(read_csv(file.path(CAN_EST, "e25_reliability_slant.csv"),
                            show_col_types = FALSE), error = function(e) NULL)
IDEO_ALPHA <- setNames(rep(NA_real_, length(IDEO)), names(IDEO))
if (!is.null(.rel25))
  for (f in names(IDEO)) {
    v <- .rel25$krippendorff_alpha[.rel25$construct == f]
    if (length(v)) IDEO_ALPHA[f] <- v[1]
  }
IDEO_ALPHA_NOTE <- setNames(vapply(names(IDEO), function(f) sprintf(
  paste("IDEOLOGY RELIABILITY IS WEAK. Panel Krippendorff alpha for this",
        "dimension (%s) is %.3f in e25 for this run. DESCRIPTIVE/EXPLORATORY:",
        "this quantity should not carry substantive weight."),
  unname(IDEO[f]), IDEO_ALPHA[f]), character(1)), names(IDEO))


cat("  c13: model-level ideology with intervals (B =", B_SENS, ")\n")
c13 <- map_dfr(names(IDEO), function(f) {
  d_all <- SLANT_EN
  d <- d_all %>% filter(!is.na(.data[[f]]))
  map_dfr(ORDER_MODEL, function(m) {
    dd  <- d     %>% filter(model == m)
    all_m <- d_all %>% filter(model == m)
    if (!nrow(dd)) return(NULL)
    juris <- as.character(dd$juris[1])
    # The five bins PLUS the signed mean. The bins are the primary estimand and
    # sum to one within (dimension, model); the signed mean is secondary and is
    # labelled as such on the row, so a reader cannot mistake it for the
    # distribution it summarises.
    bins <- map_dfr(names(IDEO_BINS), function(q) {
      k <- IDEO_BINS[[q]]
      model_level(dd, f, function(x) mean(x$.y == k),
                  sprintf("c13|%s|%s|%s", f, m, q), bounded = TRUE) %>%
        mutate(quantity = q, category = as.character(k), role = "PRIMARY")
    })
    sm <- model_level(dd, f, function(x) mean(x$.y),
                      sprintf("c13|%s|%s|signed_mean", f, m)) %>%
      mutate(quantity = "signed_mean", category = NA_character_,
             role = "SECONDARY")
    bind_rows(bins, sm) %>%
      mutate(dimension = unname(IDEO[f]), field = f, model = m,
             jurisdiction = juris,
             # Missingness is REPORTED, never collapsed into a zero: a model
             # whose slant pass failed on 40 responses is not a model that
             # placed 40 responses at neutral.
             n_missing = nrow(all_m) - nrow(dd),
             reliability_warning = unname(IDEO_ALPHA_NOTE[f]))
  })
}) %>%
  mutate(weighting = "within-model (unweighted over that model's responses)",
         inference_target = TARGET_NOTE,
         jurisdiction_caveat = paste("jurisdiction is a property of the model",
           "roster; do NOT read a developer-region effect off these",
           "model comparisons"),
         conditional = CONDITIONAL, canonical_run_id = CANONICAL_RUN_ID) %>%
  select(dimension, field, model, jurisdiction, quantity, category, role,
         estimate, conf_low, conf_high, conf_low_battery, conf_high_battery,
         everything())
stopifnot(nrow(c13) == length(IDEO) * length(ORDER_MODEL) * (length(IDEO_BINS) + 1))
# The five bins must still sum to one within every (dimension, model).
.chk13 <- c13 %>% filter(role == "PRIMARY") %>%
  group_by(dimension, model) %>% summarise(s = sum(estimate), .groups = "drop")
stopifnot(all(abs(.chk13$s - 1) < 1e-9))
write_csv(c13, file.path(CAN_EST, "c13_ideology_by_model.csv"))

# PRIMARY ESTIMAND: the equal-model share in EACH of the five categories, with
# an interval on every bin. The collapsed negative/neutral/positive split is
# gone from the primary table: it threw away the distinction between -2 and -1
# (and between +1 and +2), which is the only place the strength of a placement
# lives, and it was declared "the full distribution" while being a three-way
# summary of it.
c12 <- map_dfr(names(IDEO), function(f) {
  d <- SLANT_EN %>% filter(!is.na(.data[[f]]))
  bins <- map_dfr(names(IDEO_BINS), function(q) {
    v <- IDEO_BINS[[q]]
    st <- function(x) mean(tapply(x[[f]] == v, as.character(x$model), mean))
    r <- both_intervals(d, st, B_HEAD, sprintf("c12|%s|%s", f, q), bounded = TRUE)
    tibble(quantity = q, category = v, estimate = r$estimate,
           conf_low = r$conf_low, conf_high = r$conf_high,
           conf_low_battery = r$battery_low, conf_high_battery = r$battery_high,
           conf_low_battery_unbounded = r$battery_low_unbounded,
           conf_high_battery_unbounded = r$battery_high_unbounded,
           battery_scale = r$battery_scale,
           battery_se = r$battery_se, interval_reliable = r$interval_reliable)
  })
  # Secondary only, and labelled as such on the row.
  st_mean <- function(x) mean(tapply(x[[f]], as.character(x$model), mean))
  r <- both_intervals(d, st_mean, B_SENS, sprintf("c12|%s|signed_mean", f))
  sec <- tibble(quantity = "signed_mean", category = NA_integer_,
                estimate = r$estimate, conf_low = r$conf_low,
                conf_high = r$conf_high, conf_low_battery = r$battery_low,
                conf_high_battery = r$battery_high, battery_se = r$battery_se,
                interval_reliable = r$interval_reliable)
  bind_rows(bins, sec) %>%
    mutate(dimension = unname(IDEO[f]), field = f,
           role = ifelse(quantity == "signed_mean", "SECONDARY", "PRIMARY"),
           weighting = "equal-model", n = nrow(d),
           n_models = n_distinct(d$model),
           n_issues_sampled = SLANT_N_SAMPLED, n_issues_battery = SLANT_N_TOTAL)
}) %>%
  left_join(IDEO_ENDPOINTS, by = "field") %>%
  mutate(scale_label = paste0(endpoint_neg, " (-2) <-> ", endpoint_pos, " (+2)"),
         primary_estimand = "equal-model share in each of the five categories -2..+2",
         inference_target = TARGET_NOTE,
         # DERIVED, never typed. The hard-coded alphas that used to sit here
         # (0.41/0.30/0.24/0.14) had drifted from the values e25 actually
         # reports (0.39/0.13/0.23/0.02), so the table asserted reliability the
         # data did not show.
         reliability_warning = IDEO_ALPHA_NOTE[field],
         conditional = CONDITIONAL, canonical_run_id = CANONICAL_RUN_ID)
write_csv(c12, file.path(CAN_EST, "c12_ideology_distribution.csv"))

# The five bins must sum to one within each dimension -- asserted here as well
# as in acceptance, because a silent renormalisation would be invisible.
chk <- c12 %>% filter(role == "PRIMARY") %>% group_by(dimension) %>%
  summarise(s = sum(estimate), k = n(), .groups = "drop")
stopifnot(all(chk$k == 5), all(abs(chk$s - 1) < 1e-9))
cat("  five-bin distribution by dimension (equal-model):\n")
print(as.data.frame(c12 %>% filter(role == "PRIMARY") %>%
        select(dimension, quantity, estimate) %>%
        pivot_wider(names_from = quantity, values_from = estimate)),
      digits = 3, row.names = FALSE)

# =============================================================================
# C. MORAL FOUNDATIONS  (c14, c15)
# =============================================================================
# Six SEPARATE, NON-EXCLUSIVE binary outcomes. One response can invoke several,
# so they never form a composition and no stacked form is valid.
cat("\nC. moral foundations\n")

# Model-level prevalence with BOTH inference targets, on the same footing as
# c13. The point column is `estimate`, matching every other canonical table;
# it was called `prevalence` while the table carried no interval, and a rename
# is safe because nothing read it (see docs/MIGRATION_MAP.md).
cat("  c15: model-level foundations with intervals (B =", B_SENS, ")\n")
c15 <- map_dfr(names(MFT), function(f) {
  d_all <- SLANT_EN
  d <- d_all %>% filter(!is.na(.data[[f]]))
  map_dfr(ORDER_MODEL, function(m) {
    dd <- d %>% filter(model == m)
    if (!nrow(dd)) return(NULL)
    model_level(dd, f, function(x) mean(x$.y),
                sprintf("c15|%s|%s", f, m), bounded = TRUE) %>%
      mutate(model = m, jurisdiction = as.character(dd$juris[1]),
             foundation = unname(MFT[f]), field = f,
             n_missing = nrow(d_all %>% filter(model == m)) - nrow(dd))
  })
}) %>%
  mutate(weighting = "within-model (unweighted over that model's responses)",
         nonexclusive = paste("six NON-EXCLUSIVE indicators: a response may",
                              "invoke several or none, so these never form a",
                              "composition"),
         inference_target = TARGET_NOTE,
         jurisdiction_caveat = paste("jurisdiction is a property of the model",
           "roster; do NOT read a developer-region effect off these",
           "model comparisons"),
         conditional = CONDITIONAL, canonical_run_id = CANONICAL_RUN_ID) %>%
  select(foundation, field, model, jurisdiction, estimate, conf_low, conf_high,
         conf_low_battery, conf_high_battery, everything())
stopifnot(nrow(c15) == length(MFT) * length(ORDER_MODEL))
write_csv(c15, file.path(CAN_EST, "c15_moral_by_model.csv"))

# Equal-model points ALWAYS carry an interval computed on the same weighting.
c14 <- map_dfr(names(MFT), function(f) {
  d <- SLANT_EN %>% filter(!is.na(.data[[f]]))
  overall <- both_intervals(d, function(x) eqm(x, f), B_HEAD,
                            sprintf("c14|%s|all", f), bounded = TRUE)
  rows <- tibble(foundation = unname(MFT[f]), field = f, scope = "overall",
                 level = "all models", weighting = "equal-model",
                 estimate = overall$estimate, conf_low = overall$conf_low,
                 conf_high = overall$conf_high,
                 conf_low_battery = overall$battery_low,
                 conf_high_battery = overall$battery_high,
                 n = nrow(d), n_models = n_distinct(d$model))
  # Jurisdiction breakdown -- DESCRIPTIVE, because jurisdiction is defined by
  # model membership, so no model-adjusted jurisdiction contrast is identified.
  juris_rows <- map_dfr(JURIS_C, function(j) {
    dd <- d %>% filter(juris == j)
    if (nrow(dd) < 50) return(NULL)
    b <- both_intervals(dd, function(x) eqm(x, f), B_SENS,
                        sprintf("c14|%s|%s", f, j), bounded = TRUE)
    tibble(foundation = unname(MFT[f]), field = f, scope = "jurisdiction",
           level = j, weighting = "equal-model", estimate = b$estimate,
           conf_low = b$conf_low, conf_high = b$conf_high,
           conf_low_battery = b$battery_low, conf_high_battery = b$battery_high,
           n = nrow(dd), n_models = n_distinct(dd$model))
  })
  bind_rows(rows, juris_rows)
}) %>%
  mutate(jurisdiction_caveat = paste("jurisdiction rows are DESCRIPTIVE:",
           "jurisdiction is defined by model membership, so a model-adjusted",
           "jurisdiction contrast is not identified"),
         nonexclusive = "foundations are separate NON-EXCLUSIVE binaries; a response can invoke several or none, so they do not form a composition and must never be plotted as shares of a whole",
         inference_target = TARGET_NOTE,
         conditional = CONDITIONAL, canonical_run_id = CANONICAL_RUN_ID)

# Reliability for each foundation, carried as NUMBERS.
#
# There used to be a low_agreement_flag set at positive specific agreement <
# 0.35. That threshold was invented here: it is not a preregistered criterion,
# it has no external justification, and dichotomising at it turned a continuous
# measurement-quality statistic into a verdict ("acceptable agreement") that the
# figure then repeated. The value and its interval are reported instead, and any
# tiering is left to the reader.
# Read the reliability table from THIS release's estimate directory, so the
# canonical layer never depends on an unmanifested global file.
rel <- tryCatch(read_csv(file.path(CAN_EST, "e25_reliability_slant.csv"),
                         show_col_types = FALSE), error = function(e) NULL)
if (!is.null(rel)) {
  keep <- intersect(c("construct", "krippendorff_alpha", "gwet_ac1", "prevalence",
                      "psa_mean", "psa_min", "psa_max", "psa_conf_low",
                      "psa_conf_high", "n_pairs", "n_units_complete"),
                    names(rel))
  c14 <- c14 %>% left_join(
    rel %>% select(all_of(keep)) %>% rename(field = construct),
    by = "field") %>%
    mutate(reliability_statistic = "pairwise positive specific agreement, 2a/(2a+b+c), mean over judge pairs",
           reliability_note = paste("reported as a number with its interval;",
             "no acceptance threshold is applied because none is preregistered"),
           evidence_status = "DESCRIPTIVE/EXPLORATORY for rare foundations")
}
write_csv(c14, file.path(CAN_EST, "c14_moral_prevalence_equal_model.csv"))
cat("  equal-model prevalence (overall):\n")
print(as.data.frame(c14 %>% filter(scope == "overall") %>%
        select(foundation, estimate, conf_low, conf_high,
               any_of("psa_mean"), any_of("prevalence"))),
      digits = 3, row.names = FALSE)

# =============================================================================
# D. JOINT OUTCOMES  (c16)
# =============================================================================
# Three mutually exclusive categories per foundation, over ALL slant-eligible
# responses -- so a refusal is visible as a refusal and is never silently
# counted as "foundation absent".
cat("\nD. joint outcomes (refusal / engaged-absent / engaged-present)\n")
elig_en <- canon %>% filter(slant_eligible, lang == "en")
c16 <- map_dfr(names(MFT), function(f) {
  elig_en %>%
    mutate(joint = case_when(
      !engaged                       ~ "refusal",
      engaged & !has_slant           ~ "engaged, not yet coded",
      .data[[f]] == 1                ~ "engaged, foundation present",
      TRUE                           ~ "engaged, foundation absent")) %>%
    count(model, jurisdiction = as.character(juris), joint) %>%
    group_by(model) %>% mutate(share = n / sum(n)) %>% ungroup() %>%
    mutate(foundation = unname(MFT[f]), field = f)
}) %>% mutate(note = "refusals are a SEPARATE category and are never coded as foundation absence",
              canonical_run_id = CANONICAL_RUN_ID)
write_csv(c16, file.path(CAN_EST, "c16_content_joint_outcomes.csv"))
cat(sprintf("  c16: %d rows\n", nrow(c16)))

# Coverage table travels with the content results.
write_csv(bind_rows(
  cov_lang %>% mutate(scope = "language", model = NA_character_),
  cov_model %>% mutate(scope = "language x model")) %>%
    mutate(canonical_run_id = CANONICAL_RUN_ID,
           canonical_use = ifelse(coverage >= 0.999, "eligible for canonical content results",
                                  "EXCLUDED: incomplete coverage")),
  file.path(CAN_EST, "c12b_slant_coverage.csv"))

# =============================================================================
# c19 -- content outcomes under each judge, on an all-judge common sample
# =============================================================================
# The home contrast has a judge-sensitivity table (c17b); the content outcomes
# did not, so a reader had no way to tell whether the five-bin ideology shares
# or the foundation prevalences depend on the instrument. Observed judge POINT
# ranges are kept separate from issue-bootstrap intervals throughout.
cat("\nD. content outcomes under each judge (common support)\n")
CONTENT_FIELDS <- c(names(IDEO), names(MFT))
JP <- tryCatch(load_judge_panel(language = "en", fields = CONTENT_FIELDS),
               error = function(e) NULL)

c19 <- tibble()
if (!is.null(JP) && nrow(JP)) {
  KEY <- c("prompt_id", "prompt_language", "model")
  judges <- sort(unique(JP$judge_model))
  # Keys every judge coded for at least one content field, intersected with the
  # slant analysis sample.
  covered <- JP %>%
    filter(if_any(all_of(CONTENT_FIELDS), ~ !is.na(.x))) %>%
    distinct(across(all_of(KEY)), judge_model) %>%
    count(across(all_of(KEY)), name = "k") %>%
    filter(k == length(judges)) %>% select(all_of(KEY))
  base_keys <- SLANT_EN %>% distinct(across(all_of(KEY))) %>%
    inner_join(covered, by = KEY)
  cat(sprintf("  all-judge content support: %d of %d slant responses\n",
              nrow(base_keys), nrow(SLANT_EN)))

  if (nrow(base_keys) > 50) {
    frame_j <- function(j) {
      lab <- JP %>% filter(judge_model == j) %>%
        select(all_of(KEY), all_of(intersect(CONTENT_FIELDS, names(JP))))
      SLANT_EN %>% select(-any_of(CONTENT_FIELDS)) %>%
        inner_join(base_keys, by = KEY) %>% inner_join(lab, by = KEY)
    }
    c19 <- map_dfr(judges, function(j) {
      d <- frame_j(j)
      if (!nrow(d)) return(NULL)
      ide <- map_dfr(names(IDEO), function(f) {
        if (!f %in% names(d)) return(NULL)
        dd <- d %>% filter(!is.na(.data[[f]]))
        if (!nrow(dd)) return(NULL)
        map_dfr(names(IDEO_BINS), function(q) tibble(
          outcome = "ideology", dimension = unname(IDEO[f]), field = f,
          quantity = q,
          estimate = mean(tapply(dd[[f]] == IDEO_BINS[[q]],
                                 as.character(dd$model), mean)),
          n = nrow(dd)))
      })
      mft <- map_dfr(names(MFT), function(f) {
        if (!f %in% names(d)) return(NULL)
        dd <- d %>% filter(!is.na(.data[[f]]))
        if (!nrow(dd)) return(NULL)
        tibble(outcome = "moral foundation", dimension = unname(MFT[f]),
               field = f, quantity = "prevalence",
               estimate = eqm(dd, f), n = nrow(dd))
      })
      bind_rows(ide, mft) %>% mutate(judge_model = j)
    })
    if (nrow(c19)) {
      env19 <- c19 %>% group_by(outcome, dimension, field, quantity) %>%
        summarise(n_judges = n(),
                  point_envelope_low = min(estimate),
                  point_envelope_high = max(estimate),
                  .groups = "drop") %>%
        mutate(judge_model = "OBSERVED JUDGE POINT ENVELOPE",
               estimate = NA_real_,
               note = paste("range of judge POINT estimates on one shared",
                            "sample; contains no sampling uncertainty and is",
                            "not an interval"))
      c19 <- bind_rows(c19, env19) %>%
        mutate(sample = sprintf("all-judge content common support (n = %d responses)",
                                nrow(base_keys)),
               conditional = CONDITIONAL, canonical_run_id = CANONICAL_RUN_ID)
      write_csv(c19, file.path(CAN_EST, "c19_content_by_judge.csv"))
      cat("  c19 written: ", nrow(c19), " rows\n", sep = "")
    }
  } else {
    cat("  SKIP c19: fewer than 50 responses coded by every judge\n")
  }
}

flush_diag()
cat("\n", strrep("=", 78), "\nPART 3 DONE\n", strrep("=", 78), "\n", sep = "")
