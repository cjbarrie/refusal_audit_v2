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

CAN_FIG <- "pipeline/figures/canonical"
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
chk("C3", "every bootstrapped quantity records its seed and replicate counts",
    !is.null(c18) && all(c("seed", "replicates_requested", "replicates_successful")
                         %in% names(c18)) &&
      all(!is.na(c18$seed)) && all(!is.na(c18$replicates_successful)),
    if (is.null(c18)) "c18 missing" else sprintf("%d entries", nrow(c18)))
chk("C3b", "no bootstrap lost more than 5% of its replicates",
    !is.null(c18) && all(c18$failure_rate <= 0.05),
    if (is.null(c18)) "" else sprintf("max failure rate %.3f", max(c18$failure_rate)))
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
DESCRIPTIVE_TABLES <- c("c06_home_overlap.csv", "c12b_slant_coverage.csv",
                        "c18_bootstrap_diagnostics.csv", "c00_manifest.csv",
                        "c00_timings.csv", "c01b_acceptance_tests.csv")
need_est <- map_dfr(setdiff(tbls, file.path(CAN_EST, DESCRIPTIVE_TABLES)), function(p) {
  x <- read_csv(p, show_col_types = FALSE)
  if (!any(NAMING %in% names(x))) tibble(file = basename(p)) else NULL
})
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
    !is.null(c14) && all(grepl("non-exclusive", c14$nonexclusive)))

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
chk("F5", "finite-battery intervals are narrower than superpopulation intervals",
    !is.null(c12) && all((c12$conf_high_finite_battery - c12$conf_low_finite_battery) <=
                           (c12$conf_high - c12$conf_low) + 1e-12))

# --- G. measurement -----------------------------------------------------------
cat("\nG. measurement\n")
c17 <- rd("c17_measurement_sensitivity.csv")
chk("G1", "no majority-vote label is used as ground truth",
    !is.null(c17) && (!"majority_vote_used" %in% names(c17) ||
                        all(!c17$majority_vote_used)))
chk("G2", "judge spread is labelled as instrument sensitivity, not an interval",
    !is.null(c17) && "note" %in% names(c17) &&
      any(grepl("not sampling", c17$note, fixed = TRUE), na.rm = TRUE))
err <- tryCatch({ draw_latent_labels(y = c(0, 1), sens = 0.9, spec = 0.9); "" },
                error = function(e) conditionMessage(e))
chk("G3", "the latent-error simulation layer refuses to run without validation data",
    grepl("prevalence", err) && grepl("disabled", err),
    substr(err, 1, 60))
chk("G4", "the canonical outcome is a single named judge",
    !is.null(c17) && "canonical_outcome" %in% names(c17) &&
      n_distinct(c17$canonical_outcome) == 1,
    if (is.null(c17)) "" else unique(c17$canonical_outcome)[1])

# --- H. figure/table agreement ------------------------------------------------
cat("\nH. figures\n")
figs <- list.files(CAN_FIG)
chk("H1", "three canonical figures exist", length(figs) == 3, paste(figs, collapse = ", "))
chk("H2", "figures directory is PNG only",
    length(figs) > 0 && all(grepl("\\.png$", figs)))
# Each figure panel must be reconstructible from the table it claims to plot.
chk("H3", "FIG1c has one row per jurisdiction in c04",
    !is.null(c04) && nrow(filter(c04, weighting == "nested")) == length(JURIS_C))
c10 <- rd("c10_framing_paired.csv")
chk("H4", "FIG2c pooled point exists in c10",
    !is.null(c10) && any(c10$scope == "overall"))
chk("H5", "FIG3a shares sum to 1 within each ideology dimension",
    !is.null(c12) && {
      ss <- c12 %>% filter(grepl("^share_", quantity)) %>%
        group_by(dimension) %>% summarise(s = sum(estimate), .groups = "drop")
      all(abs(ss$s - 1) < 1e-8)
    })

# --- write --------------------------------------------------------------------
res <- bind_rows(RES) %>% mutate(canonical_run_id = CANONICAL_RUN_ID)
write_csv(res, file.path(CAN_EST, "c01b_acceptance_tests.csv"))
nf <- sum(res$result == "FAIL")
cat("\n", strrep("=", 78), "\n", sprintf("%d/%d passed, %d failed\n",
    sum(res$result == "PASS"), nrow(res), nf), strrep("=", 78), "\n", sep = "")
if (nf > 0) {
  print(as.data.frame(res %>% filter(result == "FAIL") %>% select(test, description, detail)),
        row.names = FALSE)
  quit(status = 1)
}
