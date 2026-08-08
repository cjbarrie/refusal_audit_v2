# =============================================================================
# CANONICAL ACCEPTANCE TESTS
# =============================================================================
# These are adversarial by design: each test tries to make a canonical claim
# fail, and several of them exist because an earlier version of this analysis
# did fail them. A test that cannot fail is worse than no test, so anything
# structural (weights, multiplicity, run-id hygiene) is checked against a
# constructed counter-case rather than against itself.
#
# Run AFTER 51-55. Exits non-zero if any test fails.

source("pipeline/10_canonical_common.R")
cat(strrep("=", 78), "\nCANONICAL ACCEPTANCE TESTS\n", strrep("=", 78), "\n", sep = "")

CAN_FIG <- Sys.getenv("CANON_FIG_DIR", "pipeline/figures/main")
RES <- list()
# A test whose condition evaluates to logical(0) or NA (a mistyped column name,
# an empty filter) must FAIL loudly. An earlier version let those become
# zero-row tibbles, and the test vanished from the report entirely -- silently
# passing by disappearing is the worst possible behaviour for a check.
chk <- function(id, what, pass, detail = "") {
  if (length(pass) != 1L || is.na(pass) || !is.logical(pass)) {
    detail <- paste0("TEST BROKEN: condition returned ",
                     ifelse(length(pass) != 1L,
                            paste0("length ", length(pass)), "NA"),
                     ifelse(nzchar(detail), paste0(" | ", detail), ""))
    pass <- FALSE
  }
  RES[[length(RES) + 1]] <<- tibble(test = id, description = what,
                                    result = ifelse(pass, "PASS", "FAIL"),
                                    detail = detail)
  cat(sprintf("  [%s] %-4s %s%s\n", ifelse(pass, "PASS", "FAIL"), id, what,
              ifelse(nzchar(detail), paste0("  -- ", detail), "")))
  invisible(pass)
}
rd <- function(f) {
  p <- file.path(CAN_EST, f)
  if (!file.exists(p)) return(NULL)
  read_csv(p, show_col_types = FALSE)
}
tbls <- list.files(CAN_EST, pattern = "^c\\d+.*\\.csv$", full.names = TRUE)

# --- A. structure -------------------------------------------------------------
cat("\nA. analysis-sample structure\n")
chk("A1", "canonical sample is 137,186 rows", nrow(canon) == 137186L,
    format(nrow(canon), big.mark = ","))
chk("A2", "one row per model x prompt_id x language",
    !anyDuplicated(canon[c("model", "prompt_id", "prompt_language")]))
chk("A3", "624 issues / 11 models / 5 languages / 2 tiers",
    n_distinct(canon$issue_id) == 624 && n_distinct(canon$model) == 11 &&
      n_distinct(canon$prompt_language) == 5 && n_distinct(canon$tier) == 2)
# The issue region lives in region_focus; General issues are held in their own
# home_status level so they can never be counted as another power's away issue.
stopifnot("region_focus" %in% names(canon))
chk("A4", "General issues never enter the home or away arms",
    all(canon$home_status[canon$region_focus == "General"] == "general") &&
      !any(canon$region_focus[canon$home_status %in% c("home", "away")] == "General"),
    sprintf("%s General rows, all held at home_status='general'",
            format(sum(canon$region_focus == "General"), big.mark = ",")))
chk("A5", "refused_strict is exactly engagement_code >= 4",
    all(canon$refused_strict == as.integer(canon$engagement_code >= 4)))

# --- B. weighting (non-vacuous) -----------------------------------------------
cat("\nB. weighting\n")
d <- canon %>% filter(prompt_language == "en", home_status == "home")
w <- w_nested(d)
chk("B1", "nested weights sum to 1", abs(sum(w) - 1) < 1e-9,
    sprintf("sum = %.12f", sum(w)))
per_model <- tapply(w, as.character(d$model), sum)
chk("B2", "nested weights give every model equal total mass",
    diff(range(per_model)) < 1e-9,
    sprintf("range %.2e across %d models", diff(range(per_model)), length(per_model)))
# The test above passes trivially if the design happens to be balanced, so
# force an imbalance and confirm the weights still equalise while raw counts
# do not -- this is what makes B2 meaningful.
d_imb <- bind_rows(d, d %>% filter(model == sort(unique(d$model))[1]))
w_imb <- w_nested(d_imb)
raw_imb <- table(as.character(d_imb$model)) / nrow(d_imb)
chk("B3", "weights equalise an artificially imbalanced roster (raw shares do not)",
    diff(range(tapply(w_imb, as.character(d_imb$model), sum))) < 1e-9 &&
      diff(range(raw_imb)) > 1e-6,
    sprintf("weighted range %.2e; raw share range %.4f",
            diff(range(tapply(w_imb, as.character(d_imb$model), sum))),
            diff(range(raw_imb))))
# On the real English home arm the roster is exactly balanced (104 issues per
# model, 2 prompts each), so weighted and unweighted coincide EXACTLY. That is a
# property of the design, not evidence that the weights work -- so the bite test
# is run on the imbalanced frame, where a decorative weight would show up as no
# change at all.
w_unw <- mean(d_imb$refused_strict); w_wtd <- sum(w_imb * d_imb$refused_strict)
chk("B4", "weighting changes the answer when the roster is imbalanced",
    abs(w_wtd - w_unw) > 1e-6,
    sprintf("imbalanced frame: weighted %.4f vs unweighted %.4f", w_wtd, w_unw))
chk("B5", "on the real (balanced) design, weighted equals unweighted",
    abs(sum(w * d$refused_strict) - mean(d$refused_strict)) < 1e-9,
    sprintf("%.6f both ways; balance is why, and it is not a free pass",
            mean(d$refused_strict)))

# --- C. bootstrap multiplicity ------------------------------------------------
cat("\nC. bootstrap\n")
# Synthetic counter-case. Issue A has 1 row, issue B has 2. If a replicate draws
# A twice, an issue-keyed statistic collapses both copies into one and returns
# the wrong weight; an instance-keyed one keeps them separate. The test asserts
# the instance labels reproduce the correct duplicated-draw answer.
# Three issues are the minimum: with only two, every possible resample gives the
# same answer under both keyings, so a two-issue test would pass even against a
# broken bootstrap.
syn <- tibble(issue_id = c("A", "B", "B", "C"), y = c(1, 0, 0, 1))
probe <- new.env()
probe$has_col <- TRUE; probe$saw_dup <- FALSE; probe$saw_divergence <- FALSE
got <- boot_canon(syn, function(dd) {
  if (!"bootstrap_issue_instance" %in% names(dd)) { probe$has_col <- FALSE; return(0) }
  by_inst  <- mean(tapply(dd$y, dd$bootstrap_issue_instance, mean))
  by_issue <- mean(tapply(dd$y, dd$issue_id, mean))
  if (n_distinct(dd$bootstrap_issue_instance) > n_distinct(dd$issue_id))
    probe$saw_dup <- TRUE
  if (abs(by_inst - by_issue) > 1e-12) probe$saw_divergence <- TRUE
  by_inst
}, B = 400, seed = 1L, label = "acceptance_multiplicity")
chk("C1", "replicate frames carry a per-draw instance label", probe$has_col)
chk("C2", "replicates that draw an issue twice keep the copies distinct",
    probe$saw_dup && probe$saw_divergence,
    sprintf("duplicate draws seen: %s; instance- and issue-keyed answers diverge: %s",
            probe$saw_dup, probe$saw_divergence))
c18 <- rd("c18_bootstrap_diagnostics.csv")
boot_rows <- if (is.null(c18)) NULL else c18 %>% filter(!is.na(replicates_requested))
chk("C3", "every bootstrapped quantity records its seed and replicate counts",
    !is.null(boot_rows) && nrow(boot_rows) > 0 &&
      all(c("seed", "replicates_requested", "replicates_drawn") %in% names(c18)) &&
      all(!is.na(boot_rows$seed)) && all(!is.na(boot_rows$replicates_successful)),
    if (is.null(c18)) "c18 missing" else sprintf("%d entries", nrow(c18)))
# A high failure rate is allowed -- some sensitivities are genuinely hard to
# estimate in every resample -- but it must be DECLARED: the interval is marked
# unreliable and no interval is reported. Requiring <=5% everywhere would ban
# reporting the hard specification rather than flagging it.
# interval_reliable arrives as character whenever jackknife rows leave it blank,
# so isFALSE() never matched and every flagged bootstrap looked undeclared.
bad_boot <- if (is.null(boot_rows)) NULL else
  boot_rows %>%
    mutate(.declared = tolower(as.character(interval_reliable)) %in% c("false")) %>%
    filter(failure_rate > 0.05, !.declared)
chk("C3b", "any bootstrap above the failure threshold is marked unreliable",
    !is.null(bad_boot) && nrow(bad_boot) == 0,
    if (is.null(boot_rows)) "" else
      sprintf("max failure rate %.3f; %d undeclared",
              max(boot_rows$failure_rate, na.rm = TRUE),
              if (is.null(bad_boot)) NA_integer_ else nrow(bad_boot)))
# This is here because it failed silently for an entire release: flush_diag()
# dropped every row of the current run before appending, so each part wiped the
# previous part's diagnostics and c18 ended up holding only the LAST part's.
PARTS <- c("c04", "c07", "c08", "c10", "c12", "c14")
have_parts <- if (is.null(c18)) character(0) else
  unique(sub("\\|.*$", "", c18$label[c18$canonical_run_id == CANONICAL_RUN_ID]))
chk("C3c", "c18 holds diagnostics from every bootstrapping part, not just the last",
    all(PARTS %in% have_parts),
    if (is.null(c18)) "c18 missing" else
      paste("missing:", paste(setdiff(PARTS, have_parts), collapse = ", ")))
chk("C4", "c18 labels are unique within the run",
    !is.null(c18) && !anyDuplicated(c18[c("canonical_run_id", "label")]))

# --- D. run-id hygiene --------------------------------------------------------
cat("\nD. provenance\n")
# c18 is a diagnostics LOG: flush_diag deliberately keeps earlier runs' rows so
# a bootstrap's history survives, so it is the one table allowed several ids.
# c00_timings is written by the driver AFTER 56 runs in a full pass, so on a
# re-run it is present with the previous pass's id; it is provenance, not an
# estimate, and is exempt alongside the diagnostics log.
DIAG_TABLES <- c("c18_bootstrap_diagnostics.csv", "c00_timings.csv")
est_tbls <- tbls[!basename(tbls) %in% DIAG_TABLES]
bad_id <- map_dfr(est_tbls, function(p) {
  x <- read_csv(p, show_col_types = FALSE)
  if (!"canonical_run_id" %in% names(x))
    return(tibble(file = basename(p), issue = "no canonical_run_id column"))
  if (n_distinct(x$canonical_run_id) > 1)
    return(tibble(file = basename(p),
                  issue = paste("mixed run ids:",
                                paste(unique(x$canonical_run_id), collapse = ", "))))
  NULL
})
chk("D1", "every estimate table carries exactly one canonical_run_id",
    nrow(bad_id) == 0,
    if (nrow(bad_id)) paste(bad_id$file, bad_id$issue, collapse = "; ") else
      sprintf("%d tables", length(est_tbls)))
# The stronger claim: a canonical release is ONE run, so the ids must all match.
ids <- unique(unlist(lapply(est_tbls, function(p) {
  x <- read_csv(p, show_col_types = FALSE)
  if ("canonical_run_id" %in% names(x)) unique(x$canonical_run_id) else NA_character_ })))
chk("D1b", "all estimate tables come from the same run", length(ids) == 1,
    paste(ids, collapse = ", "))
# Pure diagnostics (overlap counts, coverage counts, bootstrap logs) describe the
# data rather than estimating anything, so they are exempt; everything that
# reports a number a reader could quote must say what that number is.
NAMING <- c("estimand", "quantity", "primary_estimand", "interpretation",
            "conditional", "note")
DESCRIPTIVE_TABLES <- c("c06_home_overlap.csv", "c06b_common_support_diagnostics.csv",
                        "c10b_framing_incomplete_blocks.csv",
                        "c17c_judge_support.csv", "c12b_slant_coverage.csv",
                        "c18_bootstrap_diagnostics.csv", "c00_manifest.csv",
                        "c00_timings.csv", "c01b_acceptance_tests.csv")
need_est <- map_dfr(setdiff(tbls, file.path(CAN_EST, DESCRIPTIVE_TABLES)), function(p) {
  x <- read_csv(p, show_col_types = FALSE)
  if (!any(NAMING %in% names(x))) tibble(file = basename(p)) else NULL
})
# Reliability tables live in the release build and must name their run too.
rel_files <- list.files(CAN_EST, pattern = "^e2.*[.]csv$", full.names = TRUE)
rel_noid <- rel_files[vapply(rel_files, function(f) {
  x <- suppressMessages(read_csv(f, show_col_types = FALSE, n_max = 1))
  !("canonical_run_id" %in% names(x)) }, logical(1))]
chk("D1c", "every reliability table carries the run id",
    length(rel_noid) == 0,
    if (length(rel_noid)) paste(basename(rel_noid), collapse = ", ") else
      sprintf("%d reliability tables", length(rel_files)))
chk("D2", "every canonical table names its estimand", nrow(need_est) == 0,
    if (nrow(need_est)) paste(need_est$file, collapse = ", ") else "")

# --- E. causal-language scan --------------------------------------------------
cat("\nE. claim discipline\n")
# Flags a causal word only when it is NOT inside a nearby negation ("not a
# causal effect", "NOT causal"). The window is wide enough for the sentence
# forms actually used in these tables.
prohibited <- c("causal effect of", "causes ", "the effect of user language",
                "difference-in-differences")
scan_txt <- function(x) {
  x <- x[!is.na(x)]
  hits <- character(0)
  for (p in prohibited) {
    for (s in x[grepl(p, x, fixed = TRUE)]) {
      i <- regexpr(p, s, fixed = TRUE)
      win <- substr(s, max(1, i - 220), i + nchar(p))
      if (!grepl("\\b(not|never|NOT|NEVER|cannot|rather than)\\b", win)) hits <- c(hits, p)
    }
  }
  unique(hits)
}
bad_claim <- map_dfr(tbls, function(p) {
  x <- read_csv(p, show_col_types = FALSE)
  ch <- x %>% select(where(is.character))
  h <- unique(unlist(lapply(ch, scan_txt)))
  if (length(h)) tibble(file = basename(p), hit = paste(h, collapse = "; ")) else NULL
})
chk("E1", "no un-negated causal claim in any canonical table",
    nrow(bad_claim) == 0,
    if (nrow(bad_claim)) paste(bad_claim$file, bad_claim$hit, collapse = " | ") else "")

c04 <- rd("c04_home_standardized.csv")
chk("E2", "standardized contrast is labelled non-causal",
    !is.null(c04) && all(grepl("NOT causal", c04$causal_interpretation)))
c12 <- rd("c12_ideology_distribution.csv"); c14 <- rd("c14_moral_prevalence_equal_model.csv")
chk("E3", "content tables declare conditioning on engagement",
    !is.null(c12) && !is.null(c14) &&
      all(grepl("CONDITIONAL ON ENGAGEMENT", c12$conditional)) &&
      all(grepl("CONDITIONAL ON ENGAGEMENT", c14$conditional)))
chk("E4", "ideology tables carry the weak-reliability warning",
    !is.null(c12) && all(nzchar(c12$reliability_warning)))
chk("E5", "moral foundations are declared non-exclusive",
    !is.null(c14) && all(grepl("non-exclusive", c14$nonexclusive, ignore.case = TRUE)))

# --- F. estimability and coverage ---------------------------------------------
cat("\nF. estimability\n")
chk("F1", "non-estimable jurisdictions are flagged, not silently dropped",
    !is.null(c04) && all(JURIS_C %in% c04$jurisdiction) && any(!c04$estimable),
    if (is.null(c04)) "" else
      paste("not estimable:", paste(unique(c04$jurisdiction[!c04$estimable]),
                                    collapse = ", ")))
c12b <- rd("c12b_slant_coverage.csv")
en_cov <- if (is.null(c12b)) NULL else
  c12b %>% filter(scope == "language", language == "en")
chk("F2", "English slant coverage is complete, and partial languages are excluded",
    !is.null(en_cov) && nrow(en_cov) == 1 &&
      en_cov$coded == en_cov$eligible_engaged &&
      all(grepl("EXCLUDED", c12b$canonical_use[c12b$scope == "language" &
                                                 c12b$coverage < 1])),
    if (is.null(en_cov) || !nrow(en_cov)) "no English coverage row" else
      sprintf("en %d/%d; excluded: %s", en_cov$coded, en_cov$eligible_engaged,
              paste(c12b$language[c12b$scope == "language" & c12b$coverage < 1],
                    collapse = ", ")))
c08 <- rd("c08_language_paired.csv")
chk("F3", "all four non-English languages are estimated, nulls included",
    !is.null(c08) && setequal(unique(c08$language[c08$sensitivity == "primary"]),
                              c("zh", "ar", "hi", "ru")),
    if (is.null(c08)) "" else paste(sort(unique(c08$language)), collapse = ", "))
chk("F4", "paired tables report incomplete blocks rather than dropping silently",
    !is.null(c08) && "n_missing_blocks" %in% names(c08) &&
      all(!is.na(c08$n_missing_blocks[c08$sensitivity == "primary"])))
# The frozen-battery interval is a delete-one-issue jackknife with an FPC; the
# superpopulation interval is a bootstrap percentile. They are DIFFERENT
# estimators, so "battery interval is narrower" is not a theorem and must not be
# asserted per bin -- with f = 0.25 the FPC removes only a quarter of the
# variance, and a noisy percentile interval can be the narrower of the two for a
# particular bin. What is checked is that the design correction is actually
# applied and that it bites on average.
jk <- if (is.null(c18)) NULL else c18 %>% filter(!is.na(fpc))
chk("F5", "a design-based FPC jackknife is recorded with the right sampling fraction",
    !is.null(jk) && nrow(jk) > 0 &&
      all(abs(jk$sampling_fraction - jk$n_issues_sampled / jk$n_issues_frame) < 1e-9) &&
      all(abs(jk$fpc - (1 - jk$sampling_fraction)) < 1e-9),
    if (is.null(jk)) "no jackknife rows" else
      sprintf("%d jackknives, f = %.3f", nrow(jk), jk$sampling_fraction[1]))
chk("F5b", "the frozen-battery interval is narrower on average",
    !is.null(c12) && all(c("conf_low_battery", "conf_high_battery") %in% names(c12)) &&
      median((c12$conf_high_battery - c12$conf_low_battery) /
               (c12$conf_high - c12$conf_low), na.rm = TRUE) < 1,
    if (is.null(c12)) "" else sprintf("median width ratio %.3f",
      median((c12$conf_high_battery - c12$conf_low_battery) /
               (c12$conf_high - c12$conf_low), na.rm = TRUE)))

# --- G. measurement -----------------------------------------------------------
cat("\nG. measurement\n")
c17 <- rd("c17_measurement_sensitivity.csv")
chk("G1", "no majority-vote label is used as ground truth",
    !is.null(c17) && (!"majority_vote_used" %in% names(c17) ||
                        all(!c17$majority_vote_used, na.rm = TRUE)))
chk("G2", "judge spread is labelled as an observed envelope, not an interval",
    !is.null(c17) && "note" %in% names(c17) &&
      any(grepl("NOT a confidence interval", c17$note, fixed = TRUE), na.rm = TRUE))
err <- tryCatch({ draw_latent_labels(y = c(0, 1), sens = 0.9, spec = 0.9); "" },
                error = function(e) conditionMessage(e))
chk("G3", "the latent-error simulation layer refuses to run without validation data",
    grepl("prevalence", err) && grepl("disabled", err),
    substr(err, 1, 60))
chk("G4", "the canonical outcome is a single named judge",
    !is.null(c17) && "canonical_outcome" %in% names(c17) &&
      n_distinct(na.omit(c17$canonical_outcome)) == 1,
    if (is.null(c17)) "" else unique(c17$canonical_outcome)[1])

# --- H. figure/table agreement ------------------------------------------------
cat("\nH. figures\n")
c10 <- rd("c10_framing_paired.csv")
MAIN_FIG <- Sys.getenv("CANON_FIG_DIR", "pipeline/figures/main")
ED_FIG   <- Sys.getenv("CANON_APPFIG_DIR", "pipeline/figures/extended")
MAINF <- c("Fig1_home_jurisdiction", "Fig2_language_framing", "Fig3_content")
EDF   <- c("ED1_judge_sensitivity", "ED2_inferential_robustness",
           "ED3_postoutcome_diagnostics", "ED4_language_heterogeneity",
           "ED5_measurement_reliability")
# PNG ONLY: exactly one raster per expected figure, and nothing else.
chk("H1", "main figures are exactly the expected PNGs",
    setequal(list.files(MAIN_FIG, recursive = TRUE), paste0(MAINF, ".png")),
    paste(list.files(MAIN_FIG), collapse = ", "))
chk("H2", "Extended Data figures are exactly the expected PNGs",
    setequal(list.files(ED_FIG, recursive = TRUE), paste0(EDF, ".png")),
    paste(list.files(ED_FIG), collapse = ", "))
chk("H3", "no non-PNG artefact in any active figure directory",
    length(grep("[.]png$", c(list.files(MAIN_FIG, recursive = TRUE),
                             list.files(ED_FIG, recursive = TRUE)),
                value = TRUE, invert = TRUE)) == 0)
chk("H3b", "obsolete figure directories are gone",
    !dir.exists("pipeline/figures/canonical") &&
      !dir.exists("pipeline/figures/appendix"))
chk("H4", "FIG2c pooled framing row exists in c10",
    !is.null(c10) && any(c10$scope == "overall"))
chk("H5", "ideology bins sum to one within each dimension",
    !is.null(c12) && {
      ss <- c12 %>% filter(role == "PRIMARY") %>% group_by(dimension) %>%
        summarise(s = sum(estimate), .groups = "drop")
      all(abs(ss$s - 1) < 1e-8) })

# --- H6-H11: the paired judge-difference estimand -----------------------------
# c17d is a NEW canonical quantity introduced with this figure set, so it gets
# adversarial checks rather than a presence test.
c17d <- rd("c17d_judge_paired_differences.csv")
c17b <- rd("c17b_judge_envelope.csv")
chk("H6", "c17d exists and declares itself paired",
    !is.null(c17d) && "paired" %in% names(c17d) && all(c17d$paired))
chk("H7", "the canonical judge's own paired difference is exactly zero",
    !is.null(c17d) && {
      s <- c17d %>% filter(estimable, is_canonical_judge)
      nrow(s) > 0 && all(abs(s$estimate) < 1e-12) },
    "theta_canonical - theta_canonical must be 0 by construction")
chk("H8", "c17d point estimates reproduce c17b on the same sample",
    !is.null(c17d) && !is.null(c17b) && {
      a <- c17d %>% filter(estimable) %>%
        transmute(judge_model, jurisdiction, p = judge_estimate_pp)
      b <- c17b %>% filter(estimable,
                           judge_model != "OBSERVED JUDGE POINT ENVELOPE") %>%
        transmute(judge_model, jurisdiction, q = estimate_pp)
      m <- inner_join(a, b, by = c("judge_model", "jurisdiction"))
      nrow(m) > 0 && max(abs(m$p - m$q)) < 1e-8 },
    "both must come from the identical gcomp() on the identical sample")
# THE POINT OF THE PAIRING. Because the judges label the same responses, the
# paired interval must be materially narrower than differencing two marginal
# intervals. If it is not, the replicate-level pairing was not actually used.
chk("H9", "paired intervals are narrower than combined marginal intervals",
    !is.null(c17d) && !is.null(c17b) && {
      m <- c17b %>% filter(estimable,
                           judge_model != "OBSERVED JUDGE POINT ENVELOPE") %>%
        transmute(judge_model, jurisdiction, mw = conf_high_pp - conf_low_pp)
      can <- m %>% filter(grepl("gemini", judge_model)) %>%
        transmute(jurisdiction, cw = mw)
      j <- c17d %>% filter(estimable, !is_canonical_judge) %>%
        transmute(judge_model, jurisdiction, pw = conf_high_pp - conf_low_pp) %>%
        inner_join(m, by = c("judge_model", "jurisdiction")) %>%
        inner_join(can, by = "jurisdiction")
      nrow(j) > 0 && all(j$pw < j$mw + j$cw) })
chk("H10", "c17d records a fixed draw count with failures counted",
    !is.null(c17d) && all(c("replicates_drawn", "replicates_failed",
                            "failure_rate") %in% names(c17d)))
chk("H11", "c17d never calls the canonical judge ground truth",
    !is.null(c17d) && any(grepl("not ground truth", c17d$interpretation)) &&
      !any(grepl("ground truth", c17d$quantity)))
# The canonical tables the plotting scripts used to write must now come from
# their estimation scripts, or they exist only when the artwork is rebuilt.
chk("H12", "c07b and c08b are written by estimation scripts, not figure scripts",
    any(grepl("c07b_hierarchical_marginal",
              readLines("pipeline/11_canonical_home.R", warn = FALSE))) &&
      any(grepl("c08b_weighting_comparison",
                readLines("pipeline/12_canonical_language_framing.R", warn = FALSE))) &&
      !any(grepl("write_csv",
                 grep("^\\s*#",
                      readLines("pipeline/21_figures_extended.R", warn = FALSE),
                      value = TRUE, invert = TRUE))))

# =============================================================================
# I. ADVERSARIAL CHECKS ADDED AFTER REVIEW
# =============================================================================
# Each of these fails on a defect that was actually present in a shipped build.
cat("\nI. review findings\n")

c12 <- rd("c12_ideology_distribution.csv")
IDEO_BINS <- c("share_neg2", "share_neg1", "share_zero", "share_pos1", "share_pos2")
chk("I1", "ideology has EXACTLY five bins per dimension",
    !is.null(c12) && {
      k <- c12 %>% filter(role == "PRIMARY") %>% count(dimension)
      nrow(k) > 0 && all(k$n == 5) },
    if (is.null(c12)) "c12 missing" else
      paste(unique((c12 %>% filter(role == "PRIMARY") %>% count(dimension))$n),
            collapse = ","))
chk("I2", "the five bins are the five categories, not a 3-way collapse",
    !is.null(c12) && setequal(unique(c12$quantity[c12$role == "PRIMARY"]), IDEO_BINS))
chk("I3", "each dimension's bins sum to one",
    !is.null(c12) && {
      ss <- c12 %>% filter(role == "PRIMARY") %>% group_by(dimension) %>%
        summarise(s = sum(estimate), .groups = "drop"); all(abs(ss$s - 1) < 1e-8) })
chk("I4", "every ideology bin carries an interval",
    !is.null(c12) && all(is.finite(c12$conf_low[c12$role == "PRIMARY"])))
chk("I5", "signed_mean is secondary, not the declared primary",
    !is.null(c12) && all(c12$role[c12$quantity == "signed_mean"] == "SECONDARY") &&
      !any(grepl("signed mean", c12$primary_estimand, ignore.case = TRUE)))
# Generic left/right labels on the authority or populism scale assert a mapping
# the codebook does not make.
chk("I6", "authority and populism do not carry generic left/right endpoints",
    !is.null(c12) && {
      bad <- c12 %>% filter(dimension %in% c("Authority", "Populism")) %>%
        filter(endpoint_neg %in% c("left", "right") |
               endpoint_pos %in% c("left", "right"))
      nrow(bad) == 0 })

rel <- rd("e25_reliability_slant.csv")   # from this release's build
chk("I7", "reliability reports PAIRWISE positive specific agreement",
    !is.null(rel) && all(c("psa_mean", "psa_min", "psa_max", "n_pairs") %in% names(rel)))
chk("I8", "the mis-named positive_specific_agreement column is gone",
    is.null(rel) || !("positive_specific_agreement" %in% names(rel)))
# 2a/(2a+b+c) on a constructed case: a=10, b=5, c=5 -> 0.6667.
psa_ref <- psa_pair(c(rep(1,10), rep(1,5), rep(0,5), rep(0,30)),
                    c(rep(1,10), rep(0,5), rep(1,5), rep(0,30)))
chk("I9", "the PSA formula is 2a/(2a+b+c)", abs(psa_ref - 2/3) < 1e-12,
    sprintf("%.4f on the reference case", psa_ref))
c14 <- rd("c14_moral_prevalence_equal_model.csv")
chk("I10", "no arbitrary agreement threshold or verdict is stored",
     !is.null(c14) && !("low_agreement_flag" %in% names(c14)) &&
       !any(grepl("acceptable agreement",
                  unlist(c14[vapply(c14, is.character, logical(1))]), ignore.case = TRUE)))

c17b <- rd("c17b_judge_envelope.csv"); c17c <- rd("c17c_judge_support.csv")
chk("I11", "judge comparisons state their common support",
     !is.null(c17c) && all(c("n_rows", "n_issues", "n_models", "response_coverage",
                             "target_weight_retained") %in% names(c17c)))
chk("I12", "every judge in a comparison uses the SAME sample",
     !is.null(c17b) && {
       k <- c17b %>% filter(estimable, !grepl("ENVELOPE", judge_model)) %>%
         group_by(jurisdiction) %>% summarise(u = n_distinct(n), .groups = "drop")
       nrow(k) > 0 && all(k$u == 1) },
     if (is.null(c17b)) "" else "one n per jurisdiction across judges")
# The label must not ASSERT that it is a confidence interval; saying "NOT a
# confidence interval" is the required disclaimer, so the check has to be
# negation-aware rather than matching the phrase anywhere.
env_types <- if (is.null(c17b)) character(0) else
  unique(c17b$interval_type[grepl("ENVELOPE", c17b$judge_model)])
chk("I13", "the judge envelope is not called a bound or an interval",
     !is.null(c17b) && any(grepl("OBSERVED JUDGE POINT ENVELOPE", c17b$judge_model)) &&
       length(env_types) > 0 &&
       all(grepl("NOT a confidence interval", env_types, fixed = TRUE)),
     paste(substr(env_types, 1, 60), collapse = " | "))
chk("I13b", "the point envelope and the union of intervals are separate columns",
     !is.null(c17b) && all(c("point_envelope_low_pp", "point_envelope_high_pp",
                             "union_low_pp", "union_high_pp") %in% names(c17b)))
chk("I14", "no full-sample estimate is inserted into the envelope",
     !is.null(c17b) && all(c17b$sample[!is.na(c17b$sample)] ==
                             "all-judge common support (see c17c)"))
c08 <- rd("c08_language_paired.csv")
chk("I15", "the one-armed judge perturbation of c08 is retired",
     !is.null(c08) && !any(grepl("judge", c08$sensitivity, ignore.case = TRUE)))

c10 <- rd("c10_framing_paired.csv"); c10b <- rd("c10b_framing_incomplete_blocks.csv")
chk("I16", "primary framing uses complete 2+2 blocks only",
     !is.null(c10) && any(grepl("complete 2", c10$block_rule)))
chk("I17", "incomplete framing blocks are listed by key",
     !is.null(c10b) && all(c("issue_id", "model", "n_regular", "n_boundary") %in% names(c10b)),
     if (is.null(c10b)) "" else sprintf("%d incomplete blocks", nrow(c10b)))
chk("I18", "framing captions do not claim prompt content is held fixed",
     !is.null(c10) && any(grepl("does NOT hold prompt content fixed|not hold prompt",
                                c10$interpretation, ignore.case = TRUE)))

c04 <- rd("c04_home_standardized.csv")
chk("I19", "GLM warnings and separation are recorded on every standardized row",
     !is.null(c04) && all(c("glm_warnings", "separation_detected",
                            "separation_reason", "observed_fit_extreme_weight",
                            "counterfactual_extreme_weight")
                          %in% names(c04)))
chk("I20", "a penalized-logit sensitivity exists",
     !is.null(c04) && any(grepl("Firth", c04$estimator)))
chk("I21", "both a full-target and a common-support estimand are reported",
     !is.null(c04) && all(c("full target", "common support") %in% c04$support))
sup <- rd("c06b_common_support_diagnostics.csv")
chk("I22", "support restriction reports retained rows, issues, cells and weight",
     !is.null(sup) && all(c("rows_retained", "issues_retained", "cells_both_arms",
                            "target_weight_retained") %in% names(sup)))
c05 <- rd("c05_home_by_model.csv")
chk("I23", "the equal-model average carries an interval",
     !is.null(c05) && {
       r <- c05 %>% filter(model == "EQUAL-MODEL AVERAGE", estimable)
       nrow(r) > 0 && all(is.finite(r$conf_low)) })

chk("I24", "failed bootstrap draws are counted, never replaced",
     !is.null(c18) && "failed_draws_replaced" %in% names(c18) &&
       !any(c18$failed_draws_replaced, na.rm = TRUE))
chk("I25", "every bootstrap draws a fixed number of replicates",
     !is.null(c18) && "replicates_drawn" %in% names(c18) &&
       all(c18$replicates_drawn == c18$replicates_requested, na.rm = TRUE))
chk("I26", "the finite-battery interval is design-based, not a rescaled percentile",
     !is.null(c12) && any(grepl("jackknife", c12$inference_target)) &&
       !any(grepl("sqrt\\(1", c12$inference_target)))

# Release-only provenance. A bare acceptance run has no manifest yet, because
# make_release.R writes it AFTER the stages and BEFORE acceptance; these are
# enforced when CANON_RELEASE=1, which make_release sets.
RELEASE_MODE <- nzchar(Sys.getenv("CANON_RELEASE", ""))
tim <- rd("c00_timings.csv")
if (RELEASE_MODE) {
chk("I27", "timings are present and non-empty",
     !is.null(tim) && nrow(tim) > 0 && all(is.finite(tim$minutes)),
     if (is.null(tim)) "no timings" else sprintf("%d stages", nrow(tim)))
man <- rd("c00_manifest.csv")
chk("I28", "the manifest records git sha, hashes and environment",
     !is.null(man) && all(c("git_sha", "sha256", "kind") %in% names(man)) &&
       any(man$kind == "input_annotations") && any(man$kind == "environment") &&
       all(!is.na(man$sha256[man$kind == "output"])))
chk("I29", "the manifest does not list itself",
     is.null(man) || !any(grepl("c00_manifest", man$path[man$kind == "output"])))
chk("I30", "the release is not built from a dirty tree, or says so",
     !is.null(man) && "git_dirty" %in% names(man) && !any(is.na(man$git_dirty)),
     if (is.null(man)) "" else paste("dirty:", man$git_dirty[1]))
} else {
  cat("  [SKIP] I27-I30 release provenance (set CANON_RELEASE=1 to enforce)\n")
}

# --- write --------------------------------------------------------------------
res <- bind_rows(RES) %>% mutate(canonical_run_id = CANONICAL_RUN_ID)
# WRITING RESULTS MUTATES THE DIRECTORY BEING AUDITED. Pointed at a promoted
# tree, this rewrites c01b there and the tree no longer matches the release it
# was promoted from. Set CANON_ACCEPT_READONLY=1 to run the checks without
# writing -- which is what a post-promotion verification should do.
if (nzchar(Sys.getenv("CANON_ACCEPT_READONLY", ""))) {
  cat("\n(read-only: c01b not written)\n")
} else {
  write_csv(res, file.path(CAN_EST, "c01b_acceptance_tests.csv"))
}
nf <- sum(res$result == "FAIL")
cat("\n", strrep("=", 78), "\n", sprintf("%d/%d passed, %d failed\n",
    sum(res$result == "PASS"), nrow(res), nf), strrep("=", 78), "\n", sep = "")
if (nf > 0) {
  print(as.data.frame(res %>% filter(result == "FAIL") %>% select(test, description, detail)),
        row.names = FALSE)
  quit(status = 1)
}
