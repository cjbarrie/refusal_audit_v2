# =============================================================================
# Script 24: Measurement reliability and robustness  (ESTIMATION ONLY)
# =============================================================================
# Input : <run_dir>/annotations_panel.jsonl   (long: one row per response x judge)
# Output: pipeline/estimates/e23..e28*.csv
#
# Supersedes 16_irr_analysis.R, which was structurally limited to TWO raters
# (irr::kappa2 is Cohen's kappa) and covered Pass 1 and Pass 2 only -- no
# moral-foundation reliability at all.
#
# -----------------------------------------------------------------------------
# WHY KRIPPENDORFF'S ALPHA THROUGHOUT
# -----------------------------------------------------------------------------
# Cohen's kappa takes exactly two raters. Fleiss' kappa needs every unit rated by
# the same number of raters and tolerates no missing data. Alpha accepts any
# number of raters, missing cells (a judge's parse failure simply drops), and any
# measurement level. It is the only statistic that covers this design without
# special-casing each construct.
#
# -----------------------------------------------------------------------------
# WHY ALPHA IS NOT REPORTED ALONE  (the part that matters most here)
# -----------------------------------------------------------------------------
# Refusal is ~5.6% prevalent; sanctity_degradation is ~3%. At those marginals,
# chance-corrected agreement is unstable and can sit near zero even when raters
# agree on 97% of cases -- the kappa paradox. Reporting alpha alone would make
# the instrument look far worse than it is; reporting raw agreement alone would
# flatter it. Every binary construct therefore carries FOUR numbers:
#
#   raw agreement        interpretable, but inflated by rare positives
#   Krippendorff alpha   chance-corrected, paradox-prone at low prevalence
#   Gwet's AC1           chance-corrected AND prevalence-robust -> the headline
#   positive specific    agreement among cases at least one judge flagged; for a
#     agreement          rare outcome this is the quantity that actually matters
#
# -----------------------------------------------------------------------------
# UNCERTAINTY
# -----------------------------------------------------------------------------
# Bootstrap by resampling ISSUES, matching every other interval in this pipeline.
# Responses cluster within issue, so resampling responses would understate the
# spread.

suppressPackageStartupMessages({
  library(tidyverse); library(jsonlite); library(irr)
})
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")

EST <- "pipeline/estimates"; dir.create(EST, showWarnings = FALSE, recursive = TRUE)
run_dir <- Sys.getenv("REFUSAL_RUN_DIR", "annotations/pilot_v1")
panel_file <- file.path(run_dir, "annotations_panel.jsonl")

cat(strrep("=", 78), "\nMEASUREMENT: RELIABILITY + ROBUSTNESS\n", strrep("=", 78), "\n", sep = "")
cat("run dir:", run_dir, "\n")

if (!file.exists(panel_file)) {
  cat(sprintf("SKIP: %s not present.\n", panel_file))
  cat("  Produce it with:\n")
  cat("    python scripts/run_pilot.py --run-id <id> --stages annotate assemble \\\n")
  cat("        --resume --batteries rebalanced --all-passes --judge-panel\n")
  cat("  See docs/MULTI_JUDGE_PLAN.md.\n")
  quit(save = "no", status = 0)
}

has_cac <- requireNamespace("irrCAC", quietly = TRUE)
if (!has_cac)
  cat("NOTE: package 'irrCAC' not installed -- Gwet's AC1 will be NA.\n",
      "      install.packages('irrCAC') to enable the prevalence-robust statistic.\n")

panel <- stream_in(file(panel_file), verbose = FALSE) %>% as_tibble()
cat(sprintf("panel rows: %d   judges: %d   responses: %d\n",
            nrow(panel), n_distinct(panel$judge_model),
            n_distinct(paste(panel$prompt_id, panel$prompt_language, panel$model))))

# Verdicts made under different codebooks are not comparable: alpha would be
# measuring template drift rather than rater disagreement. Refuse to pool.
if ("judge_prompt_version" %in% names(panel)) {
  vs <- unique(na.omit(panel$judge_prompt_version))
  if (length(vs) > 1)
    stop("panel spans multiple judge_prompt_version values (",
         paste(vs, collapse = ", "), "). Re-annotate under one codebook.")
}

panel <- panel %>%
  mutate(unit = paste(prompt_id, prompt_language, model, sep = "|"),
         refused = as.integer(engagement_code >= 4))
JUDGES <- sort(unique(panel$judge_model))
cat("judges:", paste(JUDGES, collapse = ", "), "\n\n")

# --- helpers -----------------------------------------------------------------
# Wide rater matrix: units x judges, for one variable.
rater_matrix <- function(d, var) {
  w <- d %>% select(unit, judge_model, value = all_of(var)) %>%
    filter(!is.na(value)) %>%
    pivot_wider(names_from = judge_model, values_from = value,
                values_fn = first)
  m <- as.matrix(w[, setdiff(names(w), "unit"), drop = FALSE])
  rownames(m) <- w$unit
  # A unit rated by only one judge carries no agreement information.
  m[rowSums(!is.na(m)) >= 2, , drop = FALSE]
}

kripp <- function(m, method) {
  if (is.null(m) || nrow(m) < 2) return(NA_real_)
  # kripp.alpha requires a NUMERIC matrix. Nominal constructs here are character
  # (justification codes A-G), and passing them through coerces to NA with a
  # warning and returns a meaningless value. Map the pooled level set to integers
  # first -- for a nominal statistic the particular integers are irrelevant, only
  # the equality pattern matters.
  if (!is.numeric(m)) {
    lev <- sort(unique(as.vector(m[!is.na(m)])))
    m <- matrix(match(as.vector(m), lev), nrow = nrow(m),
                dimnames = dimnames(m))
  }
  out <- tryCatch(irr::kripp.alpha(t(m), method = method), error = function(e) NULL)
  if (is.null(out)) NA_real_ else out$value
}

# Raw agreement = share of units on which ALL available judges agree.
raw_agree <- function(m) {
  if (is.null(m) || !nrow(m)) return(NA_real_)
  mean(apply(m, 1, function(r) { r <- r[!is.na(r)]; length(unique(r)) == 1 }))
}

# Positive specific agreement: among units at least one judge coded positive,
# the share on which all judges agree it is positive. For a rare outcome this is
# the informative quantity; overall agreement is dominated by the common zero.
pos_agree <- function(m) {
  if (is.null(m) || !nrow(m)) return(NA_real_)
  flagged <- apply(m, 1, function(r) any(r == 1, na.rm = TRUE))
  if (!any(flagged)) return(NA_real_)
  mean(apply(m[flagged, , drop = FALSE], 1,
             function(r) { r <- r[!is.na(r)]; all(r == 1) }))
}

gwet_ac1 <- function(m) {
  if (!has_cac || is.null(m) || nrow(m) < 2) return(NA_real_)
  out <- tryCatch(irrCAC::gwet.ac1.raw(as.data.frame(m)), error = function(e) NULL)
  if (is.null(out)) NA_real_ else out$est$coeff.val
}

# Issue-cluster bootstrap for any of the above.
unit_issue <- panel %>% distinct(unit, issue_id) %>% deframe()
boot_stat <- function(m, fn, B = 500) {
  if (is.null(m) || nrow(m) < 2) return(c(NA_real_, NA_real_))
  iss <- unit_issue[rownames(m)]
  groups <- split(seq_len(nrow(m)), iss)
  u <- names(groups)
  vals <- replicate(B, {
    tk <- sample(u, length(u), replace = TRUE)
    fn(m[unlist(groups[tk]), , drop = FALSE])
  })
  quantile(vals, c(.025, .975), na.rm = TRUE)
}

# --- e23 Pass 1 reliability ---------------------------------------------------
cat("e23 Pass 1 (engagement + refusal)\n")
m_eng <- rater_matrix(panel, "engagement_code")
m_ref <- rater_matrix(panel, "refused")
ci_a <- boot_stat(m_ref, function(x) kripp(x, "nominal"))
ci_g <- boot_stat(m_ref, gwet_ac1)
e23 <- tibble(
  construct = c("engagement code (1-5)", "refused (>=4)"),
  scale = c("ordinal", "binary"),
  n_units = c(nrow(m_eng), nrow(m_ref)),
  n_judges = c(ncol(m_eng), ncol(m_ref)),
  raw_agreement = c(raw_agree(m_eng), raw_agree(m_ref)),
  krippendorff_alpha = c(kripp(m_eng, "ordinal"), kripp(m_ref, "nominal")),
  alpha_low = c(NA, ci_a[[1]]), alpha_high = c(NA, ci_a[[2]]),
  gwet_ac1 = c(gwet_ac1(m_eng), gwet_ac1(m_ref)),
  ac1_low = c(NA, ci_g[[1]]), ac1_high = c(NA, ci_g[[2]]),
  positive_specific_agreement = c(NA, pos_agree(m_ref)),
  prevalence = c(NA, mean(m_ref, na.rm = TRUE)))
write_csv(e23, file.path(EST, "e23_reliability_pass1.csv"))
print(as.data.frame(e23 %>% select(construct, n_units, raw_agreement,
                                   krippendorff_alpha, gwet_ac1,
                                   positive_specific_agreement)),
      digits = 3, row.names = FALSE)

# --- e24 justification composition -------------------------------------------
# Defined only where judges agree the response IS a refusal: asking whether two
# judges assign the same reason to something one of them thinks is not a refusal
# is not a well-posed question. This conditioning is itself reported.
cat("\ne24 refusal justification\n")
ref_units <- rownames(m_ref)[apply(m_ref, 1, function(r) all(r[!is.na(r)] == 1))]
m_just <- rater_matrix(panel %>% filter(unit %in% ref_units), "refusal_justification")
e24 <- tibble(construct = "refusal justification (7 codes)", scale = "nominal",
              n_units = if (is.null(m_just)) 0 else nrow(m_just),
              n_judges = if (is.null(m_just)) 0 else ncol(m_just),
              conditioned_on = "units all judges called a refusal",
              raw_agreement = raw_agree(m_just),
              krippendorff_alpha = kripp(m_just, "nominal"),
              gwet_ac1 = gwet_ac1(m_just))
write_csv(e24, file.path(EST, "e24_reliability_justification.csv"))
print(as.data.frame(e24), digits = 3, row.names = FALSE)

# --- e25 slant reliability ----------------------------------------------------
cat("\ne25 Pass 2 ideology + Pass 3 moral foundations\n")
IDEO <- c("economic_left_right", "social_left_right",
          "authoritarian_libertarian", "populist_elitist")
MFT <- c("care_harm", "fairness_cheating", "liberty_oppression",
         "authority_subversion", "loyalty_betrayal", "sanctity_degradation")
e25 <- bind_rows(
  map_dfr(IDEO, function(v) {
    if (!v %in% names(panel)) return(NULL)
    m <- rater_matrix(panel, v)
    tibble(construct = v, pass = "2 ideology", scale = "ordinal -2..+2",
           n_units = if (is.null(m)) 0 else nrow(m),
           raw_agreement = raw_agree(m),
           krippendorff_alpha = kripp(m, "ordinal"),
           gwet_ac1 = gwet_ac1(m), prevalence = NA_real_,
           positive_specific_agreement = NA_real_)
  }),
  map_dfr(MFT, function(v) {
    if (!v %in% names(panel)) return(NULL)
    m <- rater_matrix(panel, v)
    tibble(construct = v, pass = "3 moral foundations", scale = "binary",
           n_units = if (is.null(m)) 0 else nrow(m),
           raw_agreement = raw_agree(m),
           krippendorff_alpha = kripp(m, "nominal"),
           gwet_ac1 = gwet_ac1(m),
           prevalence = if (is.null(m)) NA_real_ else mean(m, na.rm = TRUE),
           positive_specific_agreement = pos_agree(m))
  })) %>% filter(n_units > 0)
write_csv(e25, file.path(EST, "e25_reliability_slant.csv"))
if (nrow(e25)) print(as.data.frame(e25 %>% select(construct, n_units, raw_agreement,
                                                  krippendorff_alpha, gwet_ac1,
                                                  prevalence)),
                     digits = 3, row.names = FALSE)

# --- e26 per-judge marginals --------------------------------------------------
# A judge whose refusal rate is wildly different from the others is not measuring
# the same construct, and would drag alpha down for that reason alone.
cat("\ne26 per-judge marginals\n")
e26 <- panel %>% group_by(judge_model) %>%
  summarise(n = n(), refusal_rate = mean(refused, na.rm = TRUE),
            mean_engagement = mean(engagement_code, na.rm = TRUE),
            pct_code_1 = mean(engagement_code == 1, na.rm = TRUE),
            n_distinct_codes = n_distinct(engagement_code), .groups = "drop") %>%
  mutate(degenerate = n_distinct_codes <= 1)
write_csv(e26, file.path(EST, "e26_judge_marginals.csv"))
print(as.data.frame(e26), digits = 3, row.names = FALSE)

# --- e26b pairwise agreement with the ANCHOR ---------------------------------
# The pilot showed that a judge can pass every specification check and still
# fail to measure the construct: ling-2.6-flash flagged refusal at 1.76% against
# the anchor's 6.53%. Specs do not predict that, so each candidate is compared
# directly with the labels the paper currently uses.
cat("\ne26b pairwise agreement with the anchor\n")
ANCHOR <- "google/gemini-2.5-flash-lite"
if (ANCHOR %in% colnames(m_ref)) {
  e26b <- map_dfr(setdiff(colnames(m_ref), ANCHOR), function(j) {
    pair <- m_ref[, c(ANCHOR, j), drop = FALSE]
    keep <- rowSums(!is.na(pair)) == 2
    pair <- pair[keep, , drop = FALSE]
    a <- pair[, ANCHOR]; b <- pair[, j]
    tibble(judge = j, n = nrow(pair),
           rate_anchor = mean(a), rate_judge = mean(b),
           rate_ratio = mean(b) / mean(a),
           raw_agreement = mean(a == b),
           alpha = kripp(pair, "nominal"), ac1 = gwet_ac1(pair),
           # Of the refusals the anchor found, how many did this judge also
           # find? A judge that systematically under-detects shows up here.
           recall_vs_anchor = if (sum(a == 1)) mean(b[a == 1] == 1) else NA_real_,
           precision_vs_anchor = if (sum(b == 1)) mean(a[b == 1] == 1) else NA_real_)
  }) %>% arrange(desc(ac1))
  write_csv(e26b, file.path(EST, "e26b_pairwise_vs_anchor.csv"))
  print(as.data.frame(e26b %>% select(judge, rate_judge, rate_ratio, raw_agreement,
                                      alpha, ac1, recall_vs_anchor)),
        digits = 3, row.names = FALSE)
}

# --- e26c leave-one-judge-out -------------------------------------------------
# Does dropping a judge IMPROVE agreement? A judge whose removal raises alpha is
# contributing noise rather than an independent read of the same construct.
cat("\ne26c leave-one-judge-out (binary refusal)\n")
if (ncol(m_ref) >= 3) {
  full_a <- kripp(m_ref, "nominal"); full_g <- gwet_ac1(m_ref)
  e26c <- map_dfr(colnames(m_ref), function(j) {
    sub <- m_ref[, setdiff(colnames(m_ref), j), drop = FALSE]
    sub <- sub[rowSums(!is.na(sub)) >= 2, , drop = FALSE]
    tibble(dropped = j, alpha_without = kripp(sub, "nominal"),
           ac1_without = gwet_ac1(sub))
  }) %>% mutate(alpha_full = full_a, ac1_full = full_g,
                alpha_gain_from_dropping = alpha_without - full_a) %>%
    arrange(desc(alpha_gain_from_dropping))
  write_csv(e26c, file.path(EST, "e26c_leave_one_judge_out.csv"))
  print(as.data.frame(e26c %>% select(dropped, alpha_full, alpha_without,
                                      alpha_gain_from_dropping, ac1_without)),
        digits = 3, row.names = FALSE)
}

# --- e27 DIFFERENTIAL measurement error --------------------------------------
# The critical test. Non-differential error attenuates estimates toward the null;
# DIFFERENTIAL error can manufacture them. If judges disagree more precisely
# where the headline finding lives (CN models on China issues), then the home
# premium is partly a measurement artefact and must be reported as one.
cat("\ne27 differential-error test\n")
if (all(c("region_focus", "model") %in% names(panel))) {
  JUR <- c("gpt-4o" = "US", "grok-4.3" = "US", "claude-opus-4.5" = "US",
           "gpt-5.1" = "US", "qwen3-max" = "CN", "deepseek-chat-v3.1" = "CN",
           "mistral-large-2512" = "EU", "falcon3-10b" = "MENA",
           "jais-8b" = "MENA", "allam-7b" = "MENA", "sarvam-30b" = "India")
  HOME <- c(US = "US", CN = "China", EU = "Europe", MENA = "Arab", India = "India")
  dis <- tibble(unit = rownames(m_ref),
                disagree = as.integer(apply(m_ref, 1,
                            function(r) length(unique(r[!is.na(r)])) > 1))) %>%
    left_join(panel %>% distinct(unit, model, region_focus, prompt_language),
              by = "unit") %>%
    mutate(juris = unname(JUR[model]),
           home = as.integer(region_focus == unname(HOME[juris])))
  # Two corrections to the naive version of this test.
  #
  # (1) The comparison must be WITHIN jurisdiction. Comparing the CN home cell to
  #     the pooled rate across all jurisdictions is meaningless here, because
  #     MENA disagreement (~25%) dominates the pool and swamps the contrast --
  #     the naive version reported a ratio of 1.04 and "not concentrated" while
  #     CN-home disagreement was in fact ~12x CN-elsewhere.
  #
  # (2) A raw disagreement rate is NOT comparable across cells with different
  #     refusal prevalence. Judges can only disagree where there is something to
  #     disagree about, so a cell that refuses at 20% mechanically shows more
  #     disagreement than one at 3%. POSITIVE SPECIFIC AGREEMENT -- among units
  #     at least one judge flagged, the share where all judges agree -- is the
  #     prevalence-robust quantity and is what the conclusion should rest on.
  refm <- m_ref[rownames(m_ref) %in% dis$unit, , drop = FALSE]
  psa_by <- function(units) {
    mm <- refm[rownames(refm) %in% units, , drop = FALSE]
    if (!nrow(mm)) return(NA_real_)
    flagged <- apply(mm, 1, function(r) any(r == 1, na.rm = TRUE))
    if (!any(flagged)) return(NA_real_)
    mean(apply(mm[flagged, , drop = FALSE], 1,
               function(r) { r <- r[!is.na(r)]; all(r == 1) }))
  }
  e27 <- dis %>% filter(!is.na(juris), region_focus != "General") %>%
    group_by(juris, home) %>%
    summarise(n = n(), disagree_rate = mean(disagree),
              any_flagged = sum(unit %in% rownames(refm)[
                apply(refm, 1, function(r) any(r == 1, na.rm = TRUE))]),
              pos_specific_agreement = psa_by(unit),
              .groups = "drop") %>%
    mutate(cell = ifelse(home == 1, "home region", "elsewhere"))
  # Within-jurisdiction ratio: the quantity the conclusion actually rests on.
  e27 <- e27 %>% group_by(juris) %>%
    mutate(disagree_ratio_home_vs_away =
             disagree_rate[match(1, home)] / disagree_rate[match(0, home)]) %>%
    ungroup()
  write_csv(e27, file.path(EST, "e27_differential_error.csv"))
  print(as.data.frame(e27 %>% select(juris, cell, n, disagree_rate,
                                     any_flagged, pos_specific_agreement)),
        digits = 3, row.names = FALSE)
  cn <- e27 %>% filter(juris == "CN")
  if (nrow(cn) == 2) {
    rh <- cn$disagree_rate[cn$home == 1]; ra <- cn$disagree_rate[cn$home == 0]
    ph <- cn$pos_specific_agreement[cn$home == 1]
    pa <- cn$pos_specific_agreement[cn$home == 0]
    cat(sprintf("\n  CN home %.3f vs CN elsewhere %.3f  (within-jurisdiction ratio %.1fx)\n",
                rh, ra, rh / ra))
    cat(sprintf("  positive specific agreement: home %.3f vs elsewhere %.3f\n",
                ph, pa))
    cat(if (!is.na(ph) && !is.na(pa) && ph < pa - 0.10)
      paste0("  WARNING: among flagged cases judges agree LESS in the CN home\n",
             "  cell. Differential error cannot be ruled out; the home premium\n",
             "  may be partly a measurement artefact.\n") else
      paste0("  Raw disagreement is higher in the CN home cell, but that is\n",
             "  expected from its far higher refusal prevalence. Agreement AMONG\n",
             "  FLAGGED CASES is not worse there, so this is consistent with\n",
             "  non-differential error.\n"))
  }
}

# --- e28 consensus labels for re-estimation ----------------------------------
# Majority and unanimous outcomes, so 20_estimates_home.R can be refitted on them
# and the headline compared. Written as a joinable table, not a modified
# data_clean: the primary contract stays untouched.
cat("\ne28 consensus labels\n")
e28 <- tibble(unit = rownames(m_ref),
              n_judges = apply(m_ref, 1, function(r) sum(!is.na(r))),
              n_refused = apply(m_ref, 1, function(r) sum(r == 1, na.rm = TRUE))) %>%
  mutate(refused_majority = as.integer(n_refused > n_judges / 2),
         refused_unanimous = as.integer(n_refused == n_judges),
         refused_any = as.integer(n_refused > 0)) %>%
  separate(unit, c("prompt_id", "prompt_language", "model"), sep = "\\|",
           remove = FALSE)
write_csv(e28, file.path(EST, "e28_consensus_labels.csv"))
cat(sprintf("  %d units; majority-refused %.2f%%, unanimous-refused %.2f%%\n",
            nrow(e28), 100 * mean(e28$refused_majority),
            100 * mean(e28$refused_unanimous)))

cat("\n", strrep("=", 78), "\nMEASUREMENT COMPLETE\n", strrep("=", 78), "\n", sep = "")
