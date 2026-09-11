# =============================================================================
# PENDING -- not run by the release driver; see pipeline/pending/README.md
# Historical technical reference: docs/r_pipeline/pending/02_original_judge_reliability.md
# Script 24: Measurement reliability and robustness  (ESTIMATION ONLY)
# =============================================================================
# Input : <run_dir>/annotations_panel.jsonl   (long: one row per response x judge)
# Output: <CANON_EST_DIR or pipeline/estimates>/e2*.csv
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

# RELEASE ISOLATION. When a release build is in progress, the e-series lands in
# that release's estimate directory, not in the mutable global one. Writing to
# pipeline/estimates during a build meant a FAILED release still mutated the
# live reliability tables, and the canonical scripts then read those unmanifested
# global files -- so a release could depend on inputs no manifest recorded.
EST <- Sys.getenv("CANON_EST_DIR", "pipeline/estimates")
dir.create(EST, showWarnings = FALSE, recursive = TRUE)

# Every reliability table carries the run id, like every canonical table. The
# manifest already hashes them, but a table that names its own run can be traced
# without the manifest in hand -- and acceptance can then require it uniformly.
write_rel <- function(x, file) {
  if (!"canonical_run_id" %in% names(x))
    x <- dplyr::mutate(x, canonical_run_id = Sys.getenv("CANONICAL_RUN_ID", "unset"))
  readr::write_csv(x, file.path(EST, file))
  invisible(x)
}
run_dir <- Sys.getenv("REFUSAL_RUN_DIR", "annotations/pilot_v1")
panel_file <- file.path(run_dir, "annotations_panel.jsonl")

cat(strrep("=", 78), "\nMEASUREMENT: RELIABILITY + ROBUSTNESS\n", strrep("=", 78), "\n", sep = "")
cat("run dir:", run_dir, "\n")

if (!file.exists(panel_file) && !dir.exists(file.path(run_dir, "panel"))) {
  cat(sprintf("SKIP: neither %s nor %s/panel/ is present.\n", panel_file, run_dir))
  cat("  Produce it with:\n")
  cat("    python scripts/run_pilot.py --run-id <id> --stages annotate assemble \\\n")
  cat("        --resume --batteries rebalanced --all-passes --judge-panel\n")
  cat("  See archive/2026-09-01_pre_rationalization/docs/MULTI_JUDGE_PLAN.md.\n")
  quit(save = "no", status = 0)
}

has_cac <- requireNamespace("irrCAC", quietly = TRUE)
if (!has_cac)
  cat("NOTE: package 'irrCAC' not installed -- Gwet's AC1 will be NA.\n",
      "      install.packages('irrCAC') to enable the prevalence-robust statistic.\n")

# ONE loader, shared with 14_canonical_judge_uncertainty.R. Two loaders with
# different de-duplication meant the reliability number and the judge
# re-estimate could be computed on different rows with nothing failing.
source("pipeline/10_canonical_common.R")

# THE SHARED LOADER, not a second reading of a different file.
#
# This used to stream annotations_panel.jsonl directly while
# 14_canonical_judge_uncertainty.R read <run_dir>/panel/<judge>/. Those two
# sources disagree: the assembled panel file is STALE, holding 16,576 English
# rows for nemotron-3-super against 27,551 in the per-judge directory. So
# reliability was computed on a smaller, older sample than the judge
# re-estimation, and nothing failed. load_judge_panel() prefers the per-judge
# directories and applies one resume-key rule, so both scripts now see the same
# rows by construction.
REL_LANG_INIT <- "en"
REL_FIELDS <- c("engagement_code", "refusal_justification", "issue_id",
                "economic_left_right", "social_left_right",
                "authoritarian_libertarian", "populist_elitist",
                "care_harm", "fairness_cheating", "liberty_oppression",
                "loyalty_betrayal", "authority_subversion", "sanctity_degradation",
                "judge_prompt_version")
panel <- load_judge_panel(run_dir = run_dir, language = "en", fields = REL_FIELDS)
if (is.null(panel) || !nrow(panel)) {
  cat("SKIP: the shared loader found no panel records.\n"); quit(save = "no", status = 0)
}
# RESTRICT TO THE CANONICAL KEY UNIVERSE. The loader returns whatever each judge
# rated; the analysis sample is 27,449 English responses. Without this
# intersection e23 reported 27,450 units -- one key that is not in the canonical
# sample -- so the reliability sample and the estimation sample were not the
# same set of responses.
UNIVERSE <- canon %>% filter(prompt_language == REL_LANG_INIT) %>%
  distinct(prompt_id, prompt_language, model)
n_before_universe <- nrow(panel)
panel_out <- panel %>% anti_join(UNIVERSE, by = c("prompt_id", "prompt_language", "model"))
panel <- panel %>% semi_join(UNIVERSE, by = c("prompt_id", "prompt_language", "model"))
if (nrow(panel_out)) {
  write_rel(panel_out %>% count(judge_model, name = "n_excluded"),
            "e22c_out_of_universe_keys.csv")
  cat(sprintf("excluded %d records outside the canonical key universe (see e22c)\n",
              nrow(panel_out)))
}
cat(sprintf("reliability universe: %d canonical English responses\n", nrow(UNIVERSE)))

n_dup <- attr(panel, "duplicates_collapsed")
if (is.null(n_dup)) n_dup <- 0L
cat(sprintf("panel rows: %d after resume-key collapse (%d duplicates removed)\n",
            nrow(panel), n_dup))
cat(sprintf("source: %s\n", if (dir.exists(file.path(run_dir, "panel")))
  file.path(run_dir, "panel/<judge>/") else panel_file))
cat(sprintf("judges: %d   responses: %d\n",
            n_distinct(panel$judge_model),
            n_distinct(paste(panel$prompt_id, panel$prompt_language, panel$model))))

# The judge panel exists for ENGLISH. Restrict before checking codebook
# versions: the file also holds a later Russian re-annotation made under a
# different codebook, and a whole-file check refuses to run because of rows this
# analysis never uses.
REL_LANG <- "en"   # the loader was already asked for English

# Verdicts made under different codebooks are not comparable: alpha would be
# measuring template drift rather than rater disagreement. Refuse to pool two
# DIFFERENT STAMPED versions.
#
# Unstamped rows are a separate matter and are reported, not silently pooled
# away. The anchor judge's labels predate version stamping, so they carry NA
# while the panel judges carry a hash. Whether the codebook text actually
# differed cannot be established from the file, so the composition is written
# into every reliability table and the limitation is stated rather than assumed
# away in either direction.
VER <- tibble(judge_model = character(), version = character(), n = integer())
if ("judge_prompt_version" %in% names(panel)) {
  VER <- panel %>% count(judge_model, version = judge_prompt_version, name = "n")
  vs <- unique(na.omit(panel$judge_prompt_version))
  if (length(vs) > 1)
    stop("English panel spans multiple stamped judge_prompt_version values (",
         paste(vs, collapse = ", "), "). Re-annotate under one codebook.")
  n_unstamped <- sum(is.na(panel$judge_prompt_version))
  cat(sprintf("codebook: %s stamped version(s) [%s]; %d unstamped rows (%.0f%%)\n",
              length(vs), paste(vs, collapse = ", "), n_unstamped,
              100 * n_unstamped / nrow(panel)))
  VERSION_NOTE <- sprintf(
    "stamped version(s): %s; %d of %d rows unstamped (anchor labels predate version stamping)",
    paste(vs, collapse = ", "), n_unstamped, nrow(panel))
} else {
  VERSION_NOTE <- "judge_prompt_version absent from the panel file"
}
write_rel(VER, "e22b_panel_version_composition.csv")

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
    pivot_wider(names_from = judge_model, values_from = value)
  # No values_fn: duplicates were resolved once, by the resume key, above. If
  # any survive, pivot_wider produces list columns and this fails loudly, which
  # is the point -- values_fn = first would silently choose one.
  stopifnot(!any(vapply(w, is.list, logical(1))))
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

# psa_pair / psa_summary / all_rater_positive_unanimity come from
# 10_canonical_common.R.
#
# WHAT CHANGED AND WHY. A function called pos_agree() used to be reported in the
# column positive_specific_agreement. It computed, among units ANY judge coded
# positive, the share where ALL judges agreed positive. That is not positive
# specific agreement: PSA is a pairwise quantity, 2a/(2a+b+c). The old statistic
# falls mechanically as judges are added -- with four judges it is closer to a
# unanimity rate -- so it was not comparable across constructs rated by
# different numbers of judges, and it was being read as if it were the standard
# measure. It is retained under the name all_rater_positive_unanimity, and the
# reported quantity is now the mean and range of true pairwise PSA.

# Gwet's AC1/AC2. The WEIGHTING MUST BE STATED: unweighted AC1 treats an ordinal
# scale as nominal, so a 1-vs-5 disagreement counts the same as 1-vs-2. Presenting
# that as an ordinal reliability coefficient overstates agreement on the 1-5
# engagement scale and on the -2..+2 ideology scales. Ordinal constructs use
# AC2 with ordinal weights; binary and nominal constructs use AC1.
gwet_ac1 <- function(m, scale = c("nominal", "ordinal")) {
  scale <- match.arg(scale)
  if (!has_cac || is.null(m) || nrow(m) < 2) return(NA_real_)
  out <- tryCatch(
    if (scale == "ordinal")
      irrCAC::gwet.ac1.raw(as.data.frame(m), weights = "ordinal")
    else irrCAC::gwet.ac1.raw(as.data.frame(m)),
    error = function(e) NULL)
  if (is.null(out)) NA_real_ else out$est$coeff.val
}


# Issue-cluster bootstrap for any of the above.
unit_issue <- panel %>% distinct(unit, issue_id) %>% deframe()
# Seeded, with the seed and replicate counts recorded. An unseeded reliability
# interval cannot be reproduced, and an interval whose failure count is unknown
# cannot be interpreted.
REL_SEED <- 20260807L
REL_B    <- 500L
.rel_diag <- list()
boot_stat <- function(m, fn, B = REL_B, label = NA_character_) {
  if (is.na(label)) stop("every reliability bootstrap must carry a label")
  if (is.null(m) || nrow(m) < 2) return(c(NA_real_, NA_real_))
  iss <- unit_issue[rownames(m)]
  groups <- split(seq_len(nrow(m)), iss)
  u <- names(groups)
  set.seed(REL_SEED)
  vals <- vapply(seq_len(B), function(b) {
    tk <- sample(u, length(u), replace = TRUE)
    v <- tryCatch(fn(m[unlist(groups[tk]), , drop = FALSE]), error = function(e) NA_real_)
    if (length(v) != 1L || !is.finite(v)) NA_real_ else v
  }, numeric(1))
  .rel_diag[[length(.rel_diag) + 1]] <<- tibble(
    label = label, seed = REL_SEED, replicates_drawn = B,
    replicates_successful = sum(!is.na(vals)), replicates_failed = sum(is.na(vals)),
    bootstrap_unit = "issue_id", n_units = nrow(m))
  quantile(vals, c(.025, .975), na.rm = TRUE)
}

# One bootstrap, both endpoints, memoised by label. Calling boot_stat() twice --
# once for [[1]] and once for [[2]] -- ran the identical 500-replicate bootstrap
# twice and wrote two diagnostic rows for one quantity.
.boot_cache <- new.env(parent = emptyenv())
boot_ci <- function(m, fn, label) {
  if (is.null(label) || is.na(label)) stop("boot_ci() requires a label")
  if (!is.null(.boot_cache[[label]])) return(.boot_cache[[label]])
  v <- boot_stat(m, fn, label = label)
  .boot_cache[[label]] <- v
  v
}

# --- e23 Pass 1 reliability ---------------------------------------------------
cat("e23 Pass 1 (engagement + refusal)\n")
m_eng <- rater_matrix(panel, "engagement_code")
m_ref <- rater_matrix(panel, "refused")
# The all-judge complete case is the PRIMARY multi-rater sample, so it is built
# here, next to the matrix it comes from, and used by e23 below.
m_ref_complete <- m_ref[rowSums(!is.na(m_ref)) == ncol(m_ref), , drop = FALSE]
ci_a <- boot_ci(m_ref, function(x) kripp(x, "nominal"), "e23|alpha|refused")
ci_g <- boot_ci(m_ref, function(x) gwet_ac1(x, "nominal"), "e23|ac1|refused")
e23 <- tibble(
  construct = c("engagement code (1-5)", "refused (>=4)"),
  scale = c("ordinal", "binary"),
  n_units = c(nrow(m_eng), nrow(m_ref)),
  n_judges = c(ncol(m_eng), ncol(m_ref)),
  raw_agreement = c(raw_agree(m_eng), raw_agree(m_ref)),
  krippendorff_alpha = c(kripp(m_eng, "ordinal"), kripp(m_ref, "nominal")),
  alpha_low = c(NA, ci_a[[1]]), alpha_high = c(NA, ci_a[[2]]),
  gwet_ac1 = c(gwet_ac1(m_eng, "ordinal"), gwet_ac1(m_ref, "nominal")),
  gwet_statistic = c("AC2, ordinal weights", "AC1, unweighted (binary)"),
  ac1_low = c(NA, ci_g[[1]]), ac1_high = c(NA, ci_g[[2]]),
  # TRUE pairwise positive specific agreement, 2a/(2a+b+c): mean over judge
  # pairs, with the range, and an issue-clustered interval on the mean.
  psa_mean = c(NA, psa_summary(m_ref)$psa_mean),
  psa_min  = c(NA, psa_summary(m_ref)$psa_min),
  psa_max  = c(NA, psa_summary(m_ref)$psa_max),
  n_pairs  = c(NA, psa_summary(m_ref)$n_pairs),
  psa_conf_low  = c(NA, boot_ci(m_ref, function(x) psa_summary(x)$psa_mean,
                                "e23|psa|refused")[[1]]),
  psa_conf_high = c(NA, boot_ci(m_ref, function(x) psa_summary(x)$psa_mean,
                                "e23|psa|refused")[[2]]),
  # The old statistic, under a name that says what it is.
  all_rater_positive_unanimity = c(NA, all_rater_positive_unanimity(m_ref)),
  prevalence = c(NA, mean(m_ref, na.rm = TRUE)),
  psa_definition = "pairwise 2a/(2a+b+c), mean over judge pairs (Cicchetti-Feinstein)",
  n_units_complete = c(sum(rowSums(!is.na(m_eng)) == ncol(m_eng)),
                       sum(rowSums(!is.na(m_ref)) == ncol(m_ref))))
e23 <- e23 %>% mutate(codebook = VERSION_NOTE, language = REL_LANG,
                      primary_sample = "all-judge complete case",
                      n_units_primary = nrow(m_ref_complete),
                      sample_note = paste("n_units is pairwise-available;",
                        "n_units_complete is the PRIMARY all-judge complete-case",
                        "sample. They are different samples and are not pooled."))
write_rel(e23, "e23_reliability_pass1.csv")
print(as.data.frame(e23 %>% select(construct, n_units, n_units_complete,
                                   raw_agreement, krippendorff_alpha, gwet_ac1,
                                   psa_mean, psa_min, psa_max)),
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
              gwet_ac1 = gwet_ac1(m_just, "nominal"),
              gwet_statistic = "AC1, unweighted (nominal A-G codes)")
write_rel(e24, "e24_reliability_justification.csv")
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
           gwet_ac1 = gwet_ac1(m, "ordinal"),
           gwet_statistic = "AC2, ordinal weights",
           prevalence = NA_real_,
           # PSA is defined for a binary outcome; an ordinal -2..+2 scale has no
           # "positive" cell, so the column is simply absent for these rows.
           n_units_complete = if (is.null(m)) 0L else
             sum(rowSums(!is.na(m)) == ncol(m)),
           n_judges = if (is.null(m)) 0L else ncol(m))
  }),
  map_dfr(MFT, function(v) {
    if (!v %in% names(panel)) return(NULL)
    m <- rater_matrix(panel, v)
    tibble(construct = v, pass = "3 moral foundations", scale = "binary",
           n_units = if (is.null(m)) 0 else nrow(m),
           raw_agreement = raw_agree(m),
           krippendorff_alpha = kripp(m, "nominal"),
           gwet_ac1 = gwet_ac1(m, "nominal"),
           gwet_statistic = "AC1, unweighted (binary)",
           prevalence = if (is.null(m)) NA_real_ else mean(m, na.rm = TRUE),
           psa_mean = psa_summary(m)$psa_mean,
           psa_min  = psa_summary(m)$psa_min,
           psa_max  = psa_summary(m)$psa_max,
           n_pairs  = psa_summary(m)$n_pairs,
           psa_conf_low  = boot_ci(m, function(x) psa_summary(x)$psa_mean,
                                   paste0("e25|psa|", v))[[1]],
           psa_conf_high = boot_ci(m, function(x) psa_summary(x)$psa_mean,
                                   paste0("e25|psa|", v))[[2]],
           all_rater_positive_unanimity = all_rater_positive_unanimity(m),
           # Units rated by ALL judges, kept separate from units rated by two:
           # pooling them mixes samples whose agreement is not comparable.
           n_units_complete = if (is.null(m)) 0L else
             sum(rowSums(!is.na(m)) == ncol(m)),
           n_judges = if (is.null(m)) 0L else ncol(m))
  })) %>% filter(n_units > 0)
e25 <- e25 %>% mutate(codebook = VERSION_NOTE, language = REL_LANG)
write_rel(e25, "e25_reliability_slant.csv")
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
write_rel(e26, "e26_judge_marginals.csv")
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
  write_rel(e26b, "e26b_pairwise_vs_anchor.csv")
  print(as.data.frame(e26b %>% select(judge, rate_judge, rate_ratio, raw_agreement,
                                      alpha, ac1, recall_vs_anchor)),
        digits = 3, row.names = FALSE)
}

# --- e26c leave-one-judge-out -------------------------------------------------
# Does dropping a judge IMPROVE agreement? A judge whose removal raises alpha is
# contributing noise rather than an independent read of the same construct.
cat("\ne26c leave-one-judge-out (binary refusal)\n")
if (ncol(m_ref) >= 3) {
  full_a <- kripp(m_ref, "nominal"); full_g <- gwet_ac1(m_ref, "nominal")
  e26c <- map_dfr(colnames(m_ref), function(j) {
    sub <- m_ref[, setdiff(colnames(m_ref), j), drop = FALSE]
    sub <- sub[rowSums(!is.na(sub)) >= 2, , drop = FALSE]
    tibble(dropped = j, alpha_without = kripp(sub, "nominal"),
           ac1_without = gwet_ac1(sub))
  }) %>% mutate(alpha_full = full_a, ac1_full = full_g,
                alpha_gain_from_dropping = alpha_without - full_a) %>%
    arrange(desc(alpha_gain_from_dropping))
  write_rel(e26c, "e26c_leave_one_judge_out.csv")
  print(as.data.frame(e26c %>% select(dropped, alpha_full, alpha_without,
                                      alpha_gain_from_dropping, ac1_without)),
        digits = 3, row.names = FALSE)
}

# --- e27 RETIRED ---------------------------------------------------------------
# The differential-error test that lived here has been retired, not repaired.
#
# It computed, among units any judge flagged, the share where ALL FOUR judges
# agreed -- an all-rater unanimity rate -- and called it positive specific
# agreement, then argued that because PSA is "prevalence-robust" the error was
# non-differential. Both halves are wrong. The statistic is not PSA (which is
# pairwise, 2a/(2a+b+c)), and no agreement statistic on its own establishes that
# measurement error is non-differential with respect to the home contrast.
#
# The strongest available diagnostic for the question e27 was asking -- does the
# measurement instrument move the headline result? -- is to recompute the home
# contrast under every judge on a COMMON SAMPLE. That is exactly what
# 14_canonical_judge_uncertainty.R does (c17b, c17c), and it supersedes this.
# The stale e27_differential_error.csv from earlier runs is deleted.
unlink(file.path(EST, "e27_differential_error.csv"))

# --- e28 consensus labels: AN UNUSED DIAGNOSTIC ------------------------------
# NOTHING IN THE CANONICAL LAYER READS THIS FILE, and nothing should. The
# documentation states that no majority vote is computed, and that is true of
# every estimator: the canonical outcome is one named judge and the panel is a
# sensitivity dimension. These consensus columns exist only so a reader can see
# how often the judges would have agreed on a label, and acceptance test I31
# asserts that no canonical script references e28.
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
e28 <- e28 %>% mutate(
  status = "UNUSED DIAGNOSTIC: no canonical estimator reads this file",
  majority_vote_used_anywhere = FALSE)
write_rel(e28, "e28_consensus_labels.csv")
cat(sprintf("  %d units; majority-refused %.2f%%, unanimous-refused %.2f%%\n",
            nrow(e28), 100 * mean(e28$refused_majority),
            100 * mean(e28$refused_unanimous)))

# --- e23b pairwise agreement, and complete-case vs all-available -------------
# Units rated by TWO judges and units rated by FOUR do not carry comparable
# agreement information, and an alpha computed over a mixture of both is not a
# quantity anyone can interpret. Both samples are reported, separately, with
# their sizes, plus every judge pair on its own.
cat("\ne23b pairwise agreement and complete-case comparison\n")
e23b <- bind_rows(
  psa_matrix(m_ref) %>% mutate(sample = "all available (pairwise complete)",
                               construct = "refused (>=4)"),
  psa_matrix(m_ref_complete) %>% mutate(sample = "units rated by ALL judges",
                                        construct = "refused (>=4)")) %>%
  mutate(n_units_all_available = nrow(m_ref),
         n_units_complete_case = nrow(m_ref_complete),
         n_judges = ncol(m_ref),
         statistic = "positive specific agreement 2a/(2a+b+c)",
         seed = REL_SEED)
write_rel(e23b, "e23b_pairwise_agreement.csv")
print(as.data.frame(e23b %>% select(sample, judge_a, judge_b, n_pair, psa)),
      digits = 3, row.names = FALSE)

# THE PRIMARY multi-rater reliability sample is the ALL-JUDGE COMPLETE CASE.
# Pooling units rated by two judges with units rated by four gives a coefficient
# no one can interpret, so the complete-case value leads and the
# pairwise-complete value is reported beside it.
alpha_complete <- kripp(m_ref_complete, "nominal")
cat(sprintf("\n  alpha, all available (%d units): %.3f\n", nrow(m_ref),
            kripp(m_ref, "nominal")))
cat(sprintf("  alpha, complete case  (%d units): %.3f\n",
            nrow(m_ref_complete), alpha_complete))

# --- reliability bootstrap diagnostics ---------------------------------------
if (length(.rel_diag)) {
  write_rel(bind_rows(.rel_diag) %>% mutate(script = "02_judge_reliability.R"),
            "e23c_reliability_bootstrap_diagnostics.csv")
  cat(sprintf("\n  %d reliability bootstraps recorded (seed %d, B %d)\n",
              length(.rel_diag), REL_SEED, REL_B))
}

cat("\n", strrep("=", 78), "\nMEASUREMENT COMPLETE\n", strrep("=", 78), "\n", sep = "")
