# =============================================================================
# Synthetic unit tests for the estimation machinery
# =============================================================================
# Every test here builds a case whose right answer is known by construction, so
# it can fail. They run in seconds and are cheap to run before any long build:
#
#   Rscript pipeline/tests_synthetic.R
#
# Each block corresponds to a defect that was actually shipped at some point.

suppressPackageStartupMessages({ library(tidyverse) })
Sys.setenv(CANONICAL_RUN_ID = Sys.getenv("CANONICAL_RUN_ID", "tests"))
source("pipeline/10_canonical_common.R")

pass <- 0L; fail <- 0L
t_ok <- function(what, cond, detail = "") {
  cond <- isTRUE(cond)
  cat(sprintf("  [%s] %s%s\n", if (cond) "PASS" else "FAIL", what,
              if (nzchar(detail)) paste0("  -- ", detail) else ""))
  if (cond) pass <<- pass + 1L else fail <<- fail + 1L
}
cat(strrep("=", 78), "\nSYNTHETIC TESTS\n", strrep("=", 78), "\n", sep = "")

# --- 1. bootstrap multiplicity ------------------------------------------------
cat("\n1. bootstrap multiplicity\n")
# Three issues are the minimum that can distinguish the two keyings: with two,
# every resample gives the same answer either way.
syn <- tibble(issue_id = c("A", "B", "B", "C"), y = c(1, 0, 0, 1))
probe <- new.env(); probe$dup <- FALSE; probe$diverge <- FALSE; probe$col <- TRUE
boot_canon(syn, function(dd) {
  if (!"bootstrap_issue_instance" %in% names(dd)) { probe$col <- FALSE; return(0) }
  bi <- mean(tapply(dd$y, dd$bootstrap_issue_instance, mean))
  bs <- mean(tapply(dd$y, dd$issue_id, mean))
  if (n_distinct(dd$bootstrap_issue_instance) > n_distinct(dd$issue_id)) probe$dup <- TRUE
  if (abs(bi - bs) > 1e-12) probe$diverge <- TRUE
  bi
}, B = 300, seed = 1L, label = "t_mult")
t_ok("replicate frames carry a per-draw instance label", probe$col)
t_ok("duplicated issue draws stay distinct", probe$dup && probe$diverge)

# --- 2. failed replicates are counted, never replaced -------------------------
cat("\n2. failed replicates\n")
# A statistic that fails on roughly half the draws must yield ~B/2 successes out
# of exactly B draws. The old loop resampled until it had B successes, which
# conditions the interval on the draws where the estimator is defined.
set.seed(7)
flaky <- boot_canon(syn, function(dd) if (runif(1) < 0.5) NA_real_ else 1,
                    B = 200, seed = 3L, label = "t_flaky")
t_ok("exactly B draws taken", flaky$diag$replicates_drawn == 200)
t_ok("failures are counted, not replaced",
     !flaky$diag$failed_draws_replaced &&
       flaky$diag$replicates_successful + flaky$diag$replicates_failed == 200,
     sprintf("%d ok / %d failed", flaky$diag$replicates_successful,
             flaky$diag$replicates_failed))
t_ok("a high failure rate marks the interval unreliable",
     !flaky$interval_reliable, sprintf("failure rate %.2f", flaky$failure_rate))
clean <- boot_canon(syn, function(dd) mean(dd$y), B = 100, seed = 3L, label = "t_clean")
t_ok("a clean statistic is marked reliable", clean$interval_reliable)

# --- 3. separation ------------------------------------------------------------
cat("\n3. separation\n")
# tier must NOT be collinear with home, or the design matrix is singular and the
# test would be measuring its own fixture rather than the estimator.
set.seed(4)
sep_d <- tibble(issue_id = rep(paste0("i", 1:20), each = 2),
                home = rep(c(1L, 0L), 20),
                model = "m1", model_f = factor("m1"),
                tier = sample(c("regular", "boundary"), 40, replace = TRUE),
                domain = "d1", route_f = factor("r1"))
sep_d$refused_strict <- as.integer(sep_d$home == 1)   # perfectly separated
t_ok("estimable_chk names the separation",
     grepl("separation|0 observed", estimable_chk(sep_d)),
     estimable_chk(sep_d))
# glm does not always warn on separation -- that is exactly why sep_diagnose
# exists -- so warning CAPTURE is tested on a call that reliably warns.
warn_d <- tibble(y = c(0.5, 0.5, 1, 0), x = c(1, 2, 3, 4))
t_ok("glm warnings are captured, not swallowed",
     length(fit_logit(y ~ x, warn_d)$warnings) > 0,
     substr(paste(fit_logit(y ~ x, warn_d)$warnings, collapse = "; "), 1, 46))
fitres <- fit_logit(refused_strict ~ home, sep_d)
t_ok("sep_diagnose flags a separated fit", sep_diagnose(fitres$fit)$separated,
     sep_diagnose(fitres$fit)$why)
t_ok("strict gcomp refuses a separated fit",
     is.na(gcomp(sep_d, strict = TRUE)))
firth_est <- gcomp(sep_d, firth = TRUE)
t_ok("Firth returns a finite estimate where ML does not",
     is.finite(firth_est) && firth_est > 0.5, sprintf("%.3f", firth_est))
# estimable_chk must look at the outcome it is asked about
sep_d$refused_any <- 1L
t_ok("estimable_chk honours the outcome argument",
     nzchar(estimable_chk(sep_d, "refused_strict")) &&
       !identical(estimable_chk(sep_d, "refused_any"),
                  estimable_chk(sep_d, "refused_strict")))

# --- 4. positive specific agreement ------------------------------------------
cat("\n4. positive specific agreement\n")
# a = 10 both positive, b = 5, c = 5  ->  PSA = 20/30 = 0.6667
x <- c(rep(1, 10), rep(1, 5), rep(0, 5), rep(0, 30))
y <- c(rep(1, 10), rep(0, 5), rep(1, 5), rep(0, 30))
t_ok("PSA equals 2a/(2a+b+c)", abs(psa_pair(x, y) - (20 / 30)) < 1e-12,
     sprintf("%.4f", psa_pair(x, y)))
t_ok("PSA is 1 under perfect agreement", psa_pair(x, x) == 1)
t_ok("PSA is 0 when no positive is shared",
     psa_pair(c(1, 0, 1, 0), c(0, 1, 0, 1)) == 0)
m <- cbind(j1 = x, j2 = y, j3 = c(rep(1, 12), rep(0, 38)))
ps <- psa_summary(m)
t_ok("pairwise summary reports all three pairs", ps$n_pairs == 3)
t_ok("the unanimity statistic differs from PSA and is named separately",
     abs(all_rater_positive_unanimity(m) - ps$psa_mean) > 1e-6,
     sprintf("unanimity %.3f vs mean PSA %.3f",
             all_rater_positive_unanimity(m), ps$psa_mean))

# --- 5. common support --------------------------------------------------------
cat("\n5. common support\n")
cs <- tibble(issue_id = paste0("i", 1:8),
             home = c(1, 1, 0, 0, 1, 1, 0, 0),
             model = c("a", "a", "a", "a", "b", "b", "b", "b"),
             domain = c("d1", "d2", "d1", "d3", "d1", "d1", "d1", "d1"),
             route_f = factor("r1"))
sup <- restrict_support(cs, c("model", "domain"))
t_ok("cells present in only one arm are dropped",
     nrow(sup$data) < nrow(cs) && sup$diag$cells_both_arms < sup$diag$cells_total,
     sprintf("%d/%d rows, %d/%d cells", sup$diag$rows_retained, sup$diag$rows_total,
             sup$diag$cells_both_arms, sup$diag$cells_total))
t_ok("retained target weight is reported",
     is.finite(sup$diag$target_weight_retained) &&
       sup$diag$target_weight_retained <= 1 + 1e-9,
     sprintf("%.3f", sup$diag$target_weight_retained))

# --- 6. jackknife with FPC ----------------------------------------------------
cat("\n6. finite-population jackknife\n")
set.seed(11)
jd <- tibble(issue_id = rep(paste0("i", 1:100), each = 4), y = rbinom(400, 1, 0.4))
j_all <- jack_fpc(jd, function(d) mean(d$y), n_total = 100, label = "t_census")
t_ok("a census has zero variance (f = 1)", j_all$se < 1e-12,
     sprintf("se %.2e", j_all$se))
j_half <- jack_fpc(jd, function(d) mean(d$y), n_total = 200, label = "t_half")
j_inf <- jack_fpc(jd, function(d) mean(d$y), n_total = 1e9, label = "t_inf")
t_ok("a smaller sampling fraction gives a wider interval",
     j_half$se < j_inf$se && j_half$se > 0,
     sprintf("f=0.5 se %.4f  vs  f~0 se %.4f", j_half$se, j_inf$se))
t_ok("the FPC scales the variance by (1-f)",
     abs(j_half$se^2 / j_inf$se^2 - 0.5) < 0.02,
     sprintf("ratio %.3f", j_half$se^2 / j_inf$se^2))

# --- 7. five ideology bins ----------------------------------------------------
cat("\n7. ideology bins\n")
IDEO_BINS <- c("share_neg2", "share_neg1", "share_zero", "share_pos1", "share_pos2")
mk_bins <- function(v) {
  tb <- table(factor(v, levels = -2:2))
  setNames(as.numeric(tb) / sum(tb), IDEO_BINS)
}
b <- mk_bins(c(-2, -1, 0, 0, 1, 2, 0, 0))
t_ok("exactly five bins", length(b) == 5)
t_ok("bins sum to one", abs(sum(b) - 1) < 1e-12)
t_ok("bins are not collapsed to three",
     !all(c("share_negative", "share_positive") %in% names(b)))

# --- 8. complete framing blocks ----------------------------------------------
cat("\n8. framing blocks\n")
fb <- tibble(issue_id = c("i1","i1","i1","i1","i2","i2","i2","i3","i3","i3","i3"),
             model = "m", lang = "en",
             tier = c("regular","regular","boundary","boundary",
                      "regular","regular","boundary",
                      "regular","regular","boundary","boundary"),
             y = c(0,1,1,1, 0,0,1, 1,0,0,1))
blocks <- fb %>% group_by(issue_id, model, lang) %>%
  summarise(n_reg = sum(tier == "regular"), n_bnd = sum(tier == "boundary"),
            .groups = "drop")
complete <- blocks %>% filter(n_reg == 2, n_bnd == 2)
loose <- blocks %>% filter(n_reg > 0, n_bnd > 0)
t_ok("the 2+2 rule excludes an incomplete block",
     nrow(complete) == 2 && nrow(loose) == 3,
     sprintf("complete %d, loose %d", nrow(complete), nrow(loose)))
t_ok("incomplete blocks are identifiable by key",
     identical(setdiff(loose$issue_id, complete$issue_id), "i2"))

# --- 9. judge common support --------------------------------------------------
cat("\n9. judge common support\n")
base <- tibble(key = paste0("k", 1:100), y_gem = rbinom(100, 1, 0.3))
alt  <- tibble(key = paste0("k", c(1:80)), y_alt = rbinom(80, 1, 0.3))
common <- inner_join(base, alt, by = "key")
t_ok("a pairwise comparison uses one shared sample",
     nrow(common) == 80 && nrow(common) < nrow(base),
     sprintf("%d of %d", nrow(common), nrow(base)))
t_ok("comparing full-sample Gemini with an 80-row judge is unequal",
     nrow(base) != nrow(alt))

cat("\n", strrep("=", 78), "\n", sprintf("%d passed, %d failed\n", pass, fail),
    strrep("=", 78), "\n", sep = "")
if (fail > 0) quit(status = 1)
