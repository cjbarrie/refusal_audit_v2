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
# Bootstrap over the SAMPLED issues, with an explicit statement of target.
# -----------------------------------------------------------------------------
# The 156 slant issues are a random draw from the 624-issue battery. Two targets
# are possible and they are NOT the same:
#   superpopulation -- treat issues as drawn from a wider population of possible
#                      issues; the ordinary cluster bootstrap estimates this;
#   finite battery  -- treat the 624-issue battery as the population of interest;
#                      then sampling 156 of 624 removes 1 - 156/624 = 75% of the
#                      sampling variance, and the interval should shrink by
#                      sqrt(1 - f).
# Both are reported. The superpopulation interval is the conservative default.
SLANT_N_SAMPLED <- n_distinct(SLANT_EN$issue_id)
SLANT_N_TOTAL   <- n_distinct(canon$issue_id)
FPC <- sqrt(1 - SLANT_N_SAMPLED / SLANT_N_TOTAL)

boot_slant <- function(d, stat, B, label) {
  iss <- split(seq_len(nrow(d)), d$issue_id); keys <- names(iss)
  d0 <- d; d0$bootstrap_issue_instance <- as.character(d0$issue_id)
  point <- stat(d0)
  set.seed(CAN_SEED)
  vals <- numeric(0); att <- 0L; fail <- 0L
  while (length(vals) < B && att < B * 1.5 + 50) {
    att <- att + 1L
    drawn <- sample(keys, length(keys), replace = TRUE)
    rows <- unlist(iss[drawn], use.names = FALSE)
    dd <- d[rows, , drop = FALSE]
    dd$bootstrap_issue_instance <- rep(paste0(drawn, "#", seq_along(drawn)),
                                       times = lengths(iss[drawn]))
    v <- stat(dd)
    if (!is.finite(v)) { fail <- fail + 1L; next }
    vals <- c(vals, v)
  }
  record_diag(tibble(canonical_run_id = CANONICAL_RUN_ID, label = label,
                     bootstrap_unit = "issue_id", multiplicity_preserved = TRUE,
                     copy_id_column = "bootstrap_issue_instance", seed = CAN_SEED,
                     replicates_requested = B, replicates_attempted = att,
                     replicates_successful = length(vals), replicates_failed = fail,
                     failure_rate = fail / max(att, 1), interval_method = "percentile",
                     n_rows = nrow(d), n_issues = length(keys)))
  lo <- unname(quantile(vals, .025)); hi <- unname(quantile(vals, .975))
  list(estimate = point, conf_low = lo, conf_high = hi,
       # finite-battery interval: shrink the half-widths by the fpc
       fpc_low = point - (point - lo) * FPC, fpc_high = point + (hi - point) * FPC)
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

c13 <- map_dfr(names(IDEO), function(f) {
  d <- SLANT_EN %>% filter(!is.na(.data[[f]]))
  map_dfr(sort(unique(as.character(d$model))), function(m) {
    dd <- d %>% filter(model == m)
    x <- dd[[f]]
    tibble(dimension = unname(IDEO[f]), field = f, model = m,
           jurisdiction = as.character(dd$juris[1]), n = nrow(dd),
           n_issues = n_distinct(dd$issue_id),
           share_neg2 = mean(x == -2), share_neg1 = mean(x == -1),
           share_zero = mean(x == 0), share_pos1 = mean(x == 1),
           share_pos2 = mean(x == 2),
           share_negative = mean(x < 0), share_positive = mean(x > 0),
           share_neutral = mean(x == 0), signed_mean = mean(x))
  })
}) %>% mutate(conditional = CONDITIONAL, canonical_run_id = CANONICAL_RUN_ID)
write_csv(c13, file.path(CAN_EST, "c13_ideology_by_model.csv"))

c12 <- map_dfr(names(IDEO), function(f) {
  d <- SLANT_EN %>% filter(!is.na(.data[[f]]))
  # equal-model aggregates of each share, each with its own interval
  map_dfr(c("share_neutral", "share_negative", "share_positive", "signed_mean"),
          function(q) {
    st <- function(x) {
      v <- switch(q,
        share_neutral  = tapply(x[[f]] == 0, as.character(x$model), mean),
        share_negative = tapply(x[[f]] <  0, as.character(x$model), mean),
        share_positive = tapply(x[[f]] >  0, as.character(x$model), mean),
        signed_mean    = tapply(x[[f]],      as.character(x$model), mean))
      mean(v)
    }
    bt <- boot_slant(d, st, if (q == "share_neutral") B_HEAD else B_SENS,
                     sprintf("c12|%s|%s", f, q))
    tibble(dimension = unname(IDEO[f]), field = f, quantity = q,
           weighting = "equal-model", estimate = bt$estimate,
           conf_low = bt$conf_low, conf_high = bt$conf_high,
           conf_low_finite_battery = bt$fpc_low,
           conf_high_finite_battery = bt$fpc_high,
           n = nrow(d), n_models = n_distinct(d$model),
           n_issues_sampled = SLANT_N_SAMPLED, n_issues_battery = SLANT_N_TOTAL)
  })
}) %>%
  mutate(primary_estimand = "full distribution over -2..+2; signed mean is SECONDARY",
         inference_target = paste("primary interval targets an issue SUPERPOPULATION;",
           "the finite-battery interval applies fpc sqrt(1 - 156/624) =",
           sprintf("%.3f", FPC)),
         reliability_warning = paste("IDEOLOGY RELIABILITY IS WEAK. Panel alpha by",
           "dimension: economic ~0.41, social ~0.30, authority ~0.24,",
           "populism ~0.14. Social, authority and populism in particular should",
           "not carry substantive weight."),
         conditional = CONDITIONAL, canonical_run_id = CANONICAL_RUN_ID)
write_csv(c12, file.path(CAN_EST, "c12_ideology_distribution.csv"))
cat("  neutral share by dimension (equal-model):\n")
print(as.data.frame(c12 %>% filter(quantity == "share_neutral") %>%
        select(dimension, estimate, conf_low, conf_high)), digits = 3, row.names = FALSE)

# =============================================================================
# C. MORAL FOUNDATIONS  (c14, c15)
# =============================================================================
# Six SEPARATE, NON-EXCLUSIVE binary outcomes. One response can invoke several,
# so they never form a composition and no stacked form is valid.
cat("\nC. moral foundations\n")

c15 <- map_dfr(names(MFT), function(f) {
  d <- SLANT_EN %>% filter(!is.na(.data[[f]]))
  d %>% group_by(model, jurisdiction = as.character(juris)) %>%
    summarise(n = n(), n_issues = n_distinct(issue_id),
              prevalence = mean(.data[[f]]), .groups = "drop") %>%
    mutate(foundation = unname(MFT[f]), field = f)
}) %>% mutate(conditional = CONDITIONAL, canonical_run_id = CANONICAL_RUN_ID)
write_csv(c15, file.path(CAN_EST, "c15_moral_by_model.csv"))

# Equal-model points ALWAYS carry an interval computed on the same weighting.
c14 <- map_dfr(names(MFT), function(f) {
  d <- SLANT_EN %>% filter(!is.na(.data[[f]]))
  overall <- boot_slant(d, function(x) eqm(x, f), B_HEAD, sprintf("c14|%s|all", f))
  rows <- tibble(foundation = unname(MFT[f]), field = f, scope = "overall",
                 level = "all models", weighting = "equal-model",
                 estimate = overall$estimate, conf_low = overall$conf_low,
                 conf_high = overall$conf_high,
                 conf_low_finite_battery = overall$fpc_low,
                 conf_high_finite_battery = overall$fpc_high,
                 n = nrow(d), n_models = n_distinct(d$model))
  # Jurisdiction breakdown -- DESCRIPTIVE, because jurisdiction is defined by
  # model membership, so no model-adjusted jurisdiction contrast is identified.
  juris_rows <- map_dfr(JURIS_C, function(j) {
    dd <- d %>% filter(juris == j)
    if (nrow(dd) < 50) return(NULL)
    b <- boot_slant(dd, function(x) eqm(x, f), B_SENS, sprintf("c14|%s|%s", f, j))
    tibble(foundation = unname(MFT[f]), field = f, scope = "jurisdiction",
           level = j, weighting = "equal-model", estimate = b$estimate,
           conf_low = b$conf_low, conf_high = b$conf_high,
           conf_low_finite_battery = b$fpc_low, conf_high_finite_battery = b$fpc_high,
           n = nrow(dd), n_models = n_distinct(dd$model))
  })
  bind_rows(rows, juris_rows)
}) %>%
  mutate(jurisdiction_caveat = paste("jurisdiction rows are DESCRIPTIVE:",
           "jurisdiction is defined by model membership, so a model-adjusted",
           "jurisdiction contrast is not identified"),
         nonexclusive = "foundations are separate non-exclusive binaries; they do not form a composition",
         conditional = CONDITIONAL, canonical_run_id = CANONICAL_RUN_ID)

# Reliability flag for rare foundations, read from the panel if available.
rel <- tryCatch(read_csv("pipeline/estimates/e25_reliability_slant.csv",
                         show_col_types = FALSE), error = function(e) NULL)
if (!is.null(rel)) {
  c14 <- c14 %>% left_join(
    rel %>% select(field = construct, panel_alpha = krippendorff_alpha,
                   panel_ac1 = gwet_ac1, panel_prevalence = prevalence,
                   panel_pos_specific = positive_specific_agreement),
    by = "field") %>%
    mutate(low_agreement_flag = !is.na(panel_pos_specific) & panel_pos_specific < 0.35,
           reliability_note = ifelse(low_agreement_flag,
             "LOW positive specific agreement: judges rarely agree when this foundation is flagged",
             ""))
}
write_csv(c14, file.path(CAN_EST, "c14_moral_prevalence_equal_model.csv"))
cat("  equal-model prevalence (overall):\n")
print(as.data.frame(c14 %>% filter(scope == "overall") %>%
        select(foundation, estimate, conf_low, conf_high,
               any_of("panel_pos_specific"), any_of("low_agreement_flag"))),
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

flush_diag()
cat("\n", strrep("=", 78), "\nPART 3 DONE\n", strrep("=", 78), "\n", sep = "")
