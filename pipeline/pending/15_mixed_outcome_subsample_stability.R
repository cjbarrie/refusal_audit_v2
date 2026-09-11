# =============================================================================
# PENDING -- mixed original/content outcomes; see pipeline/pending/README.md
# Historical technical reference: docs/r_pipeline/pending/15_mixed_outcome_subsample_stability.md
# CANONICAL PART 5 -- issue-subsample stability   -> c21
# =============================================================================
# THIS IS NOT A BOOTSTRAP AND ITS RANGES ARE NOT CONFIDENCE INTERVALS.
#
# The question is a DESIGN question: how much of the full-sample conclusion is
# already recovered when the issue battery is smaller? That is what a reader
# planning a replication needs, and it is not what a bootstrap answers. A
# bootstrap resamples WITH replacement at full size to approximate sampling
# uncertainty at the observed n; this resamples WITHOUT replacement at reduced
# size to describe how the answer moves as n grows. The two look similar on a
# page and mean different things, so nothing here is called a confidence
# interval -- the summaries are "across-subsample ranges" and
# "sampling-stability bands".
#
# THE RESAMPLING UNIT IS THE ISSUE. A sampled issue brings all of its prompts,
# tiers, languages, models and annotations with it, so every within-prompt and
# within-issue pairing the design rests on stays intact. Resampling response
# rows would break the paired language and framing blocks that Part 2 is built
# on, and would describe a study nobody ran.
#
# NESTED, STRATIFIED, DETERMINISTIC. Within a replicate the issues of each
# stratum are permuted ONCE; every fraction is a prefix of that permutation. So
# the 20% sample of replicate r contains the 10% sample of replicate r, and a
# trajectory across fractions reads as "what happens as issues are ADDED",
# not as nine unrelated draws. Strata are the topic domains the battery was
# drawn on, so a small sample stays compositionally comparable to a large one.

source("pipeline/10_canonical_common.R")
cat(strrep("=", 78), "\nCANONICAL PART 5: ISSUE-SUBSAMPLE STABILITY\n",
    strrep("=", 78), "\n", sep = "")

MASTER_SEED <- as.integer(Sys.getenv("CANON_SUBSAMPLE_SEED", "20260809"))
R_REPS      <- as.integer(Sys.getenv("CANON_SUBSAMPLE_REPS", "500"))
FRACTIONS   <- c(0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.75, 0.90, 1.00)
# PRESPECIFIED tolerances, fixed before any result was seen. Two scales, because
# the estimands live on two: percentage-point contrasts and [0,1] shares.
TOL_PP    <- c(1.0, 2.0)     # percentage points
TOL_SHARE <- c(0.02, 0.05)   # share units
STRATUM_VAR <- "domain"
MIN_PER_STRATUM <- 1L        # a non-empty stratum is never allowed to vanish

cat(sprintf("seed %d | %d replicates | fractions %s\n", MASTER_SEED, R_REPS,
            paste0(100 * FRACTIONS, "%", collapse = " ")))

# =============================================================================
# A. Precomputed frames -- one subset per replicate, not one per estimand
# =============================================================================
# Every estimand below is expressed as a function of an ISSUE SET. The heavy
# work is done once, here, so a replicate is a filter and an arithmetic pass
# rather than a re-derivation of blocks from 137,186 rows.
EN <- canon %>% filter(lang == "en")

# 1-2. home arms (descriptive + standardized), per jurisdiction
HOME <- EN %>% filter(home_status %in% c("home", "away")) %>%
  select(issue_id, juris, model, model_f, home, home_status, refused_strict,
         tier, domain, route_f)

# 3. paired language blocks: one row per (issue, model, prompt, language)
LANGB <- canon %>%
  filter(lang %in% ORDER_LANG) %>%
  select(issue_id, model, prompt_id, lang, refused_strict) %>%
  pivot_wider(names_from = lang, values_from = refused_strict,
              names_prefix = "y_") %>%
  filter(!is.na(y_en))
LANG_D <- map_dfr(setdiff(ORDER_LANG, "en"), function(L) {
  col <- paste0("y_", L)
  LANGB %>% filter(!is.na(.data[[col]])) %>%
    transmute(issue_id, model, language = unname(LANG_LABEL[L]),
              d = .data[[col]] - y_en)
})

# 4. framing blocks: complete 2 regular + 2 boundary, English
FRAME_D <- EN %>%
  group_by(issue_id, model) %>%
  summarise(nr = sum(tier == "regular"), nb = sum(tier == "boundary"),
            mr = mean(refused_strict[tier == "regular"]),
            mb = mean(refused_strict[tier == "boundary"]), .groups = "drop") %>%
  filter(nr == 2, nb == 2) %>% transmute(issue_id, model, d = mb - mr)

# 5-6. content, on the slant subsample
IDEO <- c(economic_left_right = "Economic", social_left_right = "Social",
          authoritarian_libertarian = "Authority", populist_elitist = "Populism")
MFT <- c(care_harm = "Care / harm", fairness_cheating = "Fairness / cheating",
         liberty_oppression = "Liberty / oppression",
         authority_subversion = "Authority / subversion",
         loyalty_betrayal = "Loyalty / betrayal",
         sanctity_degradation = "Sanctity / degradation")
SLANT <- canon %>% filter(slant_eligible, engaged, has_slant, lang == "en") %>%
  select(issue_id, model, all_of(names(IDEO)), all_of(names(MFT)))
IDEO_BINS <- c(share_neg2 = -2L, share_neg1 = -1L, share_zero = 0L,
               share_pos1 = 1L, share_pos2 = 2L)

# 7. PSA: per-unit judge labels for the six foundations, English panel
# load_judge_panel() already carries issue_id; joining it on again produced
# issue_id.x / issue_id.y and a subscript of length zero.
#
# The judge matrix is pivoted ONCE, per foundation, into a plain numeric matrix
# with an issue index alongside. Pivoting inside the replicate loop -- six
# pivot_wider() calls on ~110,000 rows, 4,000 times -- was most of the runtime.
PANEL <- load_judge_panel(language = "en", fields = names(MFT))
PSA_MATS <- NULL
if (!is.null(PANEL) && nrow(PANEL)) {
  # THE PIVOT KEY IS THE RESPONSE, AND ONLY THE RESPONSE.
  # `issue_id` is populated for one judge in the panel and NA for the others, so
  # including it among the id columns split every unit into two rows -- one
  # carrying the canonical judge, one carrying the rest -- and every judge pair
  # then had zero complete cases and a PSA of NA. issue_id is attached after the
  # pivot, from canon, where it is defined for every prompt.
  RKEY <- c("prompt_id", "prompt_language", "model")
  ISS_OF_PROMPT <- canon %>% distinct(prompt_id, issue_id) %>%
    mutate(across(everything(), as.character))
  PSA_MATS <- lapply(names(MFT), function(f) {
    w <- PANEL %>%
      select(all_of(RKEY), judge_model, .y = all_of(f)) %>%
      filter(!is.na(.y)) %>%
      pivot_wider(names_from = judge_model, values_from = .y) %>%
      mutate(prompt_id = as.character(prompt_id)) %>%
      left_join(ISS_OF_PROMPT, by = "prompt_id")
    js <- setdiff(names(w), c(RKEY, "issue_id"))
    list(issue = as.character(w$issue_id),
         M = as.matrix(w[, js, drop = FALSE]),
         pairs = if (length(js) >= 2) utils::combn(js, 2, simplify = FALSE) else list())
  })
  names(PSA_MATS) <- names(MFT)
  # Assert the pivot actually collapsed judges onto shared rows: if it did not,
  # every pair is empty and PSA silently becomes NA everywhere.
  .m1 <- PSA_MATS[[1]]
  stopifnot(length(.m1$pairs) >= 1,
            sum(rowSums(!is.na(.m1$M)) >= 2) > 0)
  cat(sprintf("  PSA panel: %s rows -> %s units, %d judges, %d pairs; %s units rated by >=2\n",
              format(nrow(PANEL), big.mark = ","),
              format(nrow(.m1$M), big.mark = ","),
              n_distinct(PANEL$judge_model), length(.m1$pairs),
              format(sum(rowSums(!is.na(.m1$M)) >= 2), big.mark = ",")))
}

cat(sprintf("  frames: home %s | lang blocks %s | framing %s | slant %s\n",
            format(nrow(HOME), big.mark = ","),
            format(nrow(LANG_D), big.mark = ","),
            format(nrow(FRAME_D), big.mark = ","),
            format(nrow(SLANT), big.mark = ",")))

# =============================================================================
# B. The estimand battery -- every one a function of an issue set
# =============================================================================
# equal-model mean: model means first, then an unweighted mean over models, so a
# model that answered more prompts does not weigh more.
eqm <- function(v, m) { t <- tapply(v, as.character(m), mean); mean(t) }

est_home_descriptive <- function(iss) {
  d <- HOME[HOME$issue_id %in% iss, ]
  map_dfr(ORDER_JURIS, function(j) {
    dd <- d[d$juris == j, ]
    h <- dd[dd$home_status == "home", ]; a <- dd[dd$home_status == "away", ]
    ok <- nrow(h) > 0 && nrow(a) > 0
    tibble(family = "home", estimand = "descriptive home-away (equal-model)",
           level = j, scale = "pp",
           value = if (ok) 100 * (eqm(h$refused_strict, h$model) -
                                  eqm(a$refused_strict, a$model)) else NA_real_,
           estimable = ok, converged = NA)
  })
}

est_home_standardized <- function(iss) {
  d <- HOME[HOME$issue_id %in% iss, ]
  map_dfr(ORDER_JURIS, function(j) {
    dd <- droplevels(d[d$juris == j, ])
    why <- estimable_chk(dd, "refused_strict")
    if (nzchar(why))
      return(tibble(family = "home", estimand = "standardized home-away (full target)",
                    level = j, scale = "pp", value = NA_real_,
                    estimable = FALSE, converged = NA))
    v <- suppressWarnings(tryCatch(gcomp(dd, w_nested), error = function(e) NA_real_))
    tibble(family = "home", estimand = "standardized home-away (full target)",
           level = j, scale = "pp", value = if (is.finite(v)) 100 * v else NA_real_,
           estimable = is.finite(v), converged = is.finite(v))
  })
}

est_language <- function(iss) {
  d <- LANG_D[LANG_D$issue_id %in% iss, ]
  map_dfr(ORDER_LANG_CONTRAST, function(L) {
    dd <- d[d$language == L, ]
    ok <- nrow(dd) > 0
    tibble(family = "language", estimand = "paired language vs English (equal-model)",
           level = L, scale = "pp",
           value = if (ok) 100 * eqm(dd$d, dd$model) else NA_real_,
           estimable = ok, converged = NA)
  })
}

est_framing <- function(iss) {
  dd <- FRAME_D[FRAME_D$issue_id %in% iss, ]
  ok <- nrow(dd) > 0
  tibble(family = "framing", estimand = "paired boundary-regular (equal-model)",
         level = "all models", scale = "pp",
         value = if (ok) 100 * eqm(dd$d, dd$model) else NA_real_,
         estimable = ok, converged = NA)
}

est_ideology <- function(iss) {
  d <- SLANT[SLANT$issue_id %in% iss, ]
  if (!nrow(d)) return(NULL)
  map_dfr(names(IDEO), function(f) {
    x <- d[[f]]; keep <- !is.na(x)
    map_dfr(names(IDEO_BINS), function(q) {
      k <- IDEO_BINS[[q]]
      ok <- any(keep)
      tibble(family = "ideology",
             estimand = paste0("equal-model share ", IDEO[[f]]),
             level = q, scale = "share",
             value = if (ok) eqm(as.integer(x[keep] == k), d$model[keep]) else NA_real_,
             estimable = ok, converged = NA)
    })
  })
}

est_moral <- function(iss) {
  d <- SLANT[SLANT$issue_id %in% iss, ]
  if (!nrow(d)) return(NULL)
  map_dfr(names(MFT), function(f) {
    x <- d[[f]]; keep <- !is.na(x); ok <- any(keep)
    tibble(family = "moral", estimand = "equal-model foundation prevalence",
           level = unname(MFT[f]), scale = "share",
           value = if (ok) eqm(as.integer(x[keep]), d$model[keep]) else NA_real_,
           estimable = ok, converged = NA)
  })
}

# PSA = 2a/(2a+b+c), averaged over judge pairs, recomputed on the sampled issues.
est_psa <- function(iss) {
  if (is.null(PSA_MATS)) return(NULL)
  map_dfr(names(MFT), function(f) {
    P <- PSA_MATS[[f]]
    sel <- P$issue %in% iss
    out <- tibble(family = "psa",
                  estimand = "pairwise PSA (mean over judge pairs)",
                  level = unname(MFT[f]), scale = "share",
                  value = NA_real_, estimable = FALSE, converged = NA)
    if (!any(sel) || !length(P$pairs)) return(out)
    M <- P$M[sel, , drop = FALSE]
    v <- vapply(P$pairs, function(pp) {
      x <- M[, pp[1]]; y <- M[, pp[2]]; k <- !is.na(x) & !is.na(y)
      x <- x[k]; y <- y[k]
      a <- sum(x == 1 & y == 1); b <- sum(x == 1 & y == 0); cc <- sum(x == 0 & y == 1)
      den <- 2 * a + b + cc
      if (den == 0) NA_real_ else 2 * a / den
    }, numeric(1))
    if (!any(is.finite(v))) return(out)
    out$value <- mean(v[is.finite(v)]); out$estimable <- TRUE
    out
  })
}

ALL_ESTIMANDS <- function(iss) {
  bind_rows(est_home_descriptive(iss), est_home_standardized(iss),
            est_language(iss), est_framing(iss), est_ideology(iss),
            est_moral(iss), est_psa(iss))
}

# =============================================================================
# C. The deterministic nested stratified design
# =============================================================================
ISSUES <- canon %>% distinct(issue_id, .keep_all = TRUE) %>%
  transmute(issue_id, stratum = as.character(.data[[STRATUM_VAR]])) %>%
  arrange(issue_id)
STRATA <- split(ISSUES$issue_id, ISSUES$stratum)
cat(sprintf("  %d issues in %d strata (%s): %s\n", nrow(ISSUES), length(STRATA),
            STRATUM_VAR,
            paste(sprintf("%s=%d", names(STRATA), lengths(STRATA)), collapse = " ")))

# Allocation: proportional, rounded up, with a floor of MIN_PER_STRATUM and
# capped at the stratum size. Documented rather than left to rounding luck.
alloc <- function(n_h, f) min(n_h, max(MIN_PER_STRATUM, ceiling(f * n_h)))

# One permutation per (replicate, stratum), from a seed derived from the master
# seed and the replicate index -- so any single replicate can be reproduced
# without replaying the others.
perm_for <- function(r) {
  set.seed(MASTER_SEED + r)
  lapply(STRATA, function(v) sample(v, length(v), replace = FALSE))
}
issues_at <- function(perms, f)
  unlist(lapply(perms, function(v) v[seq_len(alloc(length(v), f))]),
         use.names = FALSE)

# =============================================================================
# D. Run
# =============================================================================
FULL <- ALL_ESTIMANDS(ISSUES$issue_id) %>%
  transmute(family, estimand, level, scale, full_value = value,
            full_estimable = estimable)
cat(sprintf("\nfull-sample reference: %d estimands\n", nrow(FULL)))

t0 <- Sys.time()
draws <- vector("list", R_REPS * (length(FRACTIONS) - 1))
k <- 0L
for (r in seq_len(R_REPS)) {
  perms <- perm_for(r)
  for (f in FRACTIONS[FRACTIONS < 1]) {
    iss <- issues_at(perms, f)
    res <- ALL_ESTIMANDS(iss)
    k <- k + 1L
    draws[[k]] <- res %>%
      mutate(replicate = r, fraction = f, n_issues = length(iss))
  }
  if (r %% 50 == 0)
    cat(sprintf("  replicate %d/%d  (%.1f min elapsed)\n", r, R_REPS,
                as.numeric(difftime(Sys.time(), t0, units = "mins"))))
}
# The 100% endpoint is DETERMINISTIC -- the observed sample, one row, not a draw.
draws[[k + 1L]] <- ALL_ESTIMANDS(ISSUES$issue_id) %>%
  mutate(replicate = 0L, fraction = 1.0, n_issues = nrow(ISSUES))
DR <- bind_rows(draws)
cat(sprintf("  %s replicate-estimand rows in %.1f min\n",
            format(nrow(DR), big.mark = ","),
            as.numeric(difftime(Sys.time(), t0, units = "mins"))))

# Rows per subsample, for the metadata
rows_at <- DR %>% distinct(replicate, fraction, n_issues)

# =============================================================================
# E. Summaries -- ranges, NOT confidence intervals
# =============================================================================
SUM <- DR %>%
  left_join(FULL, by = c("family", "estimand", "level", "scale")) %>%
  group_by(family, estimand, level, scale, fraction) %>%
  summarise(
    n_replicates      = n(),
    n_estimable       = sum(estimable, na.rm = TRUE),
    estimability_rate = mean(estimable, na.rm = TRUE),
    convergence_rate  = if (all(is.na(converged))) NA_real_ else mean(converged, na.rm = TRUE),
    mean_n_issues     = mean(n_issues),
    full_value        = first(full_value),
    median_estimate   = median(value, na.rm = TRUE),
    p10 = quantile(value, 0.10, na.rm = TRUE), p90 = quantile(value, 0.90, na.rm = TRUE),
    p025 = quantile(value, 0.025, na.rm = TRUE), p975 = quantile(value, 0.975, na.rm = TRUE),
    mad_from_full  = median(abs(value - first(full_value)), na.rm = TRUE),
    rmsd_from_full = sqrt(mean((value - first(full_value))^2, na.rm = TRUE)),
    sign_agreement = mean(sign(value) == sign(first(full_value)), na.rm = TRUE),
    .groups = "drop") %>%
  mutate(
    tol_1 = ifelse(scale == "pp", TOL_PP[1], TOL_SHARE[1]),
    tol_2 = ifelse(scale == "pp", TOL_PP[2], TOL_SHARE[2]))
# Within-tolerance rates need the draws again, so they are computed separately
# and joined rather than approximated from the summary.
TOLR <- DR %>% left_join(FULL, by = c("family", "estimand", "level", "scale")) %>%
  mutate(t1 = ifelse(scale == "pp", TOL_PP[1], TOL_SHARE[1]),
         t2 = ifelse(scale == "pp", TOL_PP[2], TOL_SHARE[2]),
         d = abs(value - full_value)) %>%
  group_by(family, estimand, level, scale, fraction) %>%
  summarise(within_tol_1 = mean(d <= t1, na.rm = TRUE),
            within_tol_2 = mean(d <= t2, na.rm = TRUE), .groups = "drop")
SUM <- SUM %>% left_join(TOLR, by = c("family", "estimand", "level", "scale", "fraction")) %>%
  mutate(
    interval_note = paste("p10-p90 and p2.5-p97.5 are ACROSS-SUBSAMPLE RANGES",
                          "describing design stability. They are NOT confidence",
                          "intervals and have no coverage interpretation."),
    resampling_unit = "issue_id (without replacement, stratified, nested)",
    canonical_run_id = CANONICAL_RUN_ID)

FAIL <- DR %>% filter(!estimable | is.na(value)) %>%
  count(family, estimand, level, fraction, name = "n_failures") %>%
  mutate(canonical_run_id = CANONICAL_RUN_ID)

dir.create(CAN_EST, showWarnings = FALSE, recursive = TRUE)
# Draws go to parquet: 500 x 8 x ~40 estimands is ~1.6M rows, which is a 40 MB
# CSV and a 2 MB parquet.
if (requireNamespace("arrow", quietly = TRUE)) {
  arrow::write_parquet(DR, file.path(CAN_EST, "c21_subsample_draws.parquet"))
} else {
  warning("arrow unavailable; writing draws as csv.gz instead")
  readr::write_csv(DR, file.path(CAN_EST, "c21_subsample_draws.csv.gz"))
}
write_csv(SUM,  file.path(CAN_EST, "c21_subsample_summary.csv"))
write_csv(FAIL, file.path(CAN_EST, "c21_subsample_failures.csv"))

meta <- list(
  canonical_run_id = CANONICAL_RUN_ID,
  master_seed = MASTER_SEED,
  replicate_seed_rule = "set.seed(MASTER_SEED + replicate_index)",
  replicates_per_fraction = R_REPS,
  fractions = FRACTIONS,
  full_sample_is_deterministic = TRUE,
  issue_universe = nrow(ISSUES),
  stratum_variable = STRATUM_VAR,
  strata = as.list(lengths(STRATA)),
  sampling_algorithm = paste("simple random sample WITHOUT replacement within",
                             "each stratum; a sampled issue carries all of its",
                             "prompts, tiers, languages, models and annotations"),
  allocation_rule = sprintf("min(n_h, max(%d, ceiling(f * n_h))) per stratum",
                            MIN_PER_STRATUM),
  nesting_algorithm = paste("one permutation per (replicate, stratum); every",
                            "fraction is a PREFIX of that permutation, so",
                            "smaller samples are subsets of larger ones within",
                            "a replicate"),
  tolerances = list(pp = TOL_PP, share = TOL_SHARE,
                    prespecified = TRUE,
                    note = "fixed before any result was inspected"),
  not_a_bootstrap = paste("ranges are across-subsample stability bands, not",
                          "confidence intervals"),
  estimand_count = nrow(FULL),
  r_version = paste(R.version$major, R.version$minor, sep = "."),
  package_versions = list(
    dplyr = as.character(utils::packageVersion("dplyr")),
    arrow = tryCatch(as.character(utils::packageVersion("arrow")),
                     error = function(e) NA_character_)),
  git_sha = tryCatch(system2("git", c("rev-parse", "HEAD"), stdout = TRUE)[1],
                     error = function(e) NA_character_),
  input_hashes = list(
    data_clean = tryCatch(digest::digest("pipeline/data_clean.RData",
                                         algo = "sha256", file = TRUE),
                          error = function(e) NA_character_)),
  generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S"))
writeLines(jsonlite::toJSON(meta, auto_unbox = TRUE, pretty = TRUE, digits = NA),
           file.path(CAN_EST, "c21_subsample_metadata.json"))

cat("\nstability at the smallest and largest sampled fractions:\n")
print(as.data.frame(SUM %>%
  filter(fraction %in% c(min(FRACTIONS), 0.50, 0.90)) %>%
  filter(family %in% c("home", "language", "framing")) %>%
  transmute(estimand = substr(estimand, 1, 34), level, fraction,
            full = round(full_value, 2), med = round(median_estimate, 2),
            p10 = round(p10, 2), p90 = round(p90, 2),
            sign_agree = round(sign_agreement, 3),
            within_1pp = round(within_tol_1, 3),
            estimable = round(estimability_rate, 3))), row.names = FALSE)

flush_diag()
cat("\n", strrep("=", 78), "\nPART 5 DONE\n", strrep("=", 78), "\n", sep = "")
