# =============================================================================
# v2 -- ACCEPTANCE TESTS
# =============================================================================
# Exits non-zero if any criterion fails, so the v2 layer can gate a commit.
# Each test recomputes its target INDEPENDENTLY of the script that produced it;
# a test that merely re-read the output would prove nothing.

source("pipeline/40_v2_common.R")
suppressPackageStartupMessages(library(jsonlite))
cat(strrep("=", 78), "\nv2 ACCEPTANCE TESTS\n", strrep("=", 78), "\n", sep = "")

fails <- character()
ok <- function(name, pass, detail = "") {
  cat(sprintf("  %-58s %s  %s\n", name, if (pass) "PASS" else "FAIL", detail))
  if (!pass) fails <<- c(fails, name)
}
rd <- function(f) read_csv(file.path(EST, f), show_col_types = FALSE)

e32 <- rd("e32_home_descriptive.csv")
e36 <- rd("e36_language_paired_effects.csv")
e38 <- rd("e38_outcome_definition_sensitivity.csv")
e39 <- rd("e39_bootstrap_diagnostics.csv")

# --- 1. descriptive estimates reproduce direct counts EXACTLY -----------------
cat("\n1. descriptive reproduces direct counts\n")
direct <- v2 %>% group_by(jurisdiction = as.character(juris), home_status) %>%
  summarise(n = n(), refusals = sum(refused_strict), rate = mean(refused_strict),
            .groups = "drop")
cmp <- e32 %>% filter(stratum == "overall", quantity == "cell_rate") %>%
  select(jurisdiction, home_status, n_out = n, ref_out = refusals_strict,
         rate_out = rate_strict) %>%
  inner_join(direct, by = c("jurisdiction", "home_status"))
ok("cell n matches direct count", nrow(cmp) == nrow(direct) && all(cmp$n_out == cmp$n),
   sprintf("%d cells", nrow(cmp)))
ok("cell refusals match direct count", all(cmp$ref_out == cmp$refusals))
ok("cell rate matches direct count (exact)", all(abs(cmp$rate_out - cmp$rate) < 1e-12))

# the descriptive difference itself
dd <- v2 %>% filter(home_status %in% c("home", "away")) %>%
  group_by(jurisdiction = as.character(juris)) %>%
  summarise(direct_diff = mean(refused_strict[home_status == "home"]) -
                          mean(refused_strict[home_status == "away"]), .groups = "drop")
cd <- e32 %>% filter(stratum == "overall", quantity == "home_minus_away",
                     weighting == "response") %>%
  select(jurisdiction, estimate) %>% inner_join(dd, by = "jurisdiction")
ok("home-minus-away matches direct difference (exact)",
   all(abs(cd$estimate - cd$direct_diff) < 1e-12), sprintf("%d jurisdictions", nrow(cd)))

# --- 2. paired language estimates reproduce within-block differences ----------
cat("\n2. paired language reproduces within-block differences\n")
blockcheck <- map_dfr(setdiff(LANGS_V2, "en"), function(L) {
  en <- v2 %>% filter(lang == "en") %>% select(block_id, y_en = refused_strict)
  lx <- v2 %>% filter(lang == L)  %>% select(block_id, y_l = refused_strict)
  j <- inner_join(en, lx, by = "block_id")
  tibble(language = L, direct = mean(j$y_l - j$y_en), n_blocks = nrow(j))
})
pc <- e36 %>% select(language, estimate, n_complete_blocks) %>%
  inner_join(blockcheck, by = "language")
ok("paired estimate matches direct within-block mean (exact)",
   all(abs(pc$estimate - pc$direct) < 1e-12), sprintf("%d languages", nrow(pc)))
ok("complete-block counts match", all(pc$n_complete_blocks == pc$n_blocks))
ok("LPM block-FE check agrees with paired estimator", all(e36$lpm_matches_paired))

# --- 3. no v2 output calls a standardized contrast causal / DiD / within-issue -
cat("\n3. prohibited descriptions absent\n")
v2files <- list.files(EST, pattern = "^e3[2-9]|^e40|^v2_", full.names = TRUE)
banned <- c("causal effect", "difference-in-differences", "\\bDiD\\b", "within-issue")
hits <- map_dfr(v2files, function(f) {
  txt <- paste(readLines(f, warn = FALSE), collapse = "\n")
  map_dfr(banned, function(b) {
    # A NEGATED mention ("NOT causal", "not a difference-in-differences") is
    # exactly what these files are required to say, so only unnegated uses count.
    m <- gregexpr(b, txt, ignore.case = TRUE, perl = TRUE)[[1]]
    if (m[1] == -1) return(NULL)
    bad <- 0L
    for (pos in m) {
      # Look back far enough to see the enclosing JSON key. `prohibited_
      # descriptions` is an array that ENUMERATES the banned terms, which is the
      # opposite of asserting them; a 60-character window sat inside the array
      # and could not see the key, so the test flagged its own guard rail.
      pre <- substr(txt, max(1, pos - 220), pos - 1)
      if (!grepl("not|never|NOT|Never|prohibited|is not a|NOT causal", pre))
        bad <- bad + 1L
    }
    if (bad == 0L) NULL else tibble(file = basename(f), term = b, unnegated = bad)
  })
})
ok("no unnegated causal/DiD/within-issue language in v2 outputs", nrow(hits) == 0,
   if (nrow(hits)) paste(hits$file, hits$term, collapse = "; ") else "checked 4 terms")

# --- 4. code 3 in all three representations ----------------------------------
cat("\n4. code 3 representation\n")
n3 <- sum(v2$engagement_code == 3)
in_any    <- sum(v2$refused_any) - sum(v2$refused_strict) == n3
in_strict <- all(v2$refused_strict[v2$engagement_code == 3] == 0)
in_three  <- "partial" %in% e38$level[e38$sensitivity_type == "code3_representation"]
ok("code 3 excluded from strict refusal", in_strict, sprintf("n=%d", n3))
ok("code 3 included in any-refusal", in_any)
ok("code 3 present as its own category", in_three)
ok("ordinal 1-5 analysis present",
   any(e38$level == "engagement_ordinal_1_5"))

# --- 5. equal-model weights sum equally within jurisdiction -------------------
cat("\n5. weighting\n")
wchk <- map_dfr(levels(v2$juris), function(j) {
  d <- v2 %>% filter(juris == j, home_status %in% c("home", "away"))
  if (!nrow(d)) return(NULL)
  w <- w_equal_model(d)
  s <- tapply(w, d$model, sum)
  tibble(juris = j, n_models = length(s), max_dev = max(abs(s - 1 / length(s))),
         total = sum(w))
})
ok("equal-model weights sum equally within jurisdiction",
   all(wchk$max_dev < 1e-12), sprintf("max deviation %.2e", max(wchk$max_dev)))
ok("all weight schemes sum to 1", all(abs(wchk$total - 1) < 1e-12))

# --- 6. every bootstrap resamples entire issues -------------------------------
cat("\n6. bootstrap unit\n")
ok("every recorded bootstrap uses issue_id", all(e39$bootstrap_unit == "issue_id"),
   sprintf("%d bootstraps", nrow(e39)))
b2000 <- e39 %>% filter(replicates_requested >= 2000)
ok("all >=2000-replicate bootstraps achieved >=2000 successes",
   nrow(b2000) == 0 || all(b2000$replicates_successful >= 2000),
   sprintf("%d such bootstraps", nrow(b2000)))
ok("bootstrap seed recorded", all(!is.na(e39$seed)))
ok("attempts, successes and failures all recorded",
   all(!is.na(e39$replicates_attempted)) && all(!is.na(e39$replicates_successful)) &&
     all(!is.na(e39$replicates_failed)))

# --- 7. row-order invariance ---------------------------------------------------
cat("\n7. row-order invariance\n")
set.seed(1); shuffled <- v2[sample(nrow(v2)), ]
d1 <- v2 %>% filter(juris == "CN", home_status %in% c("home", "away"))
d2 <- shuffled %>% filter(juris == "CN", home_status %in% c("home", "away"))
desc1 <- mean(d1$refused_strict[d1$home_status == "home"]) -
         mean(d1$refused_strict[d1$home_status == "away"])
desc2 <- mean(d2$refused_strict[d2$home_status == "home"]) -
         mean(d2$refused_strict[d2$home_status == "away"])
ok("descriptive estimate invariant to row order", abs(desc1 - desc2) < 1e-12)
g1 <- suppressWarnings(coef(glm(refused_strict ~ home + tier + domain + route_f2 + model_f2,
                                d1, family = binomial))[["home"]])
g2 <- suppressWarnings(coef(glm(refused_strict ~ home + tier + domain + route_f2 + model_f2,
                                d2, family = binomial))[["home"]])
ok("model coefficient invariant to row order", abs(g1 - g2) < 1e-8,
   sprintf("delta %.2e", abs(g1 - g2)))

# --- 8. percentage points equal 100x probability -------------------------------
cat("\n8. units\n")
ppchk <- bind_rows(
  e32 %>% filter(!is.na(estimate), !is.na(estimate_pp)) %>% select(estimate, estimate_pp),
  e36 %>% select(estimate, estimate_pp))
ok("estimate_pp == 100 * estimate everywhere",
   all(abs(ppchk$estimate_pp - 100 * ppchk$estimate) < 1e-9),
   sprintf("%d rows checked", nrow(ppchk)))
ord <- e38 %>% filter(level == "engagement_ordinal_1_5")
ok("ordinal analysis does NOT report percentage points", all(is.na(ord$estimate_pp)),
   "engagement-code units are not pp")

# --- 9. General never in the away reference ------------------------------------
cat("\n9. General handling\n")
ok("no General row is coded away",
   sum(v2$home_status == "away" & v2$region_focus == "General") == 0)
ok("General reported as its own descriptive category",
   "general" %in% e32$home_status)

# --- 10. language contrasts compare the same blocks ----------------------------
cat("\n10. language block matching\n")
blk <- map_dfr(setdiff(LANGS_V2, "en"), function(L) {
  en <- v2 %>% filter(lang == "en") %>% pull(block_id)
  lx <- v2 %>% filter(lang == L) %>% pull(block_id)
  tibble(language = L, shared = length(intersect(en, lx)),
         en_only = length(setdiff(en, lx)), l_only = length(setdiff(lx, en)))
}) %>% inner_join(e36 %>% select(language, n_complete_blocks), by = "language")
ok("complete blocks == intersection of English and language blocks",
   all(blk$shared == blk$n_complete_blocks))
ok("missing blocks reported", all(!is.na(e36$n_missing_blocks)))

# --- 11. existing outputs untouched --------------------------------------------
cat("\n11. preservation\n")
legacy <- c("e01_home_premium_primary.csv", "e29_language_by_model.csv",
            "e30_home_language.csv", "e31_home_premium_by_language.csv")
present <- file.exists(file.path(EST, legacy))
ok("legacy e01/e29/e30/e31 still present", all(present),
   paste(legacy[!present], collapse = ", "))
spec_ok <- file.exists(file.path(EST, "v2_analysis_spec.json"))
ok("machine-readable analysis spec written", spec_ok)
if (spec_ok) {
  sp <- fromJSON(file.path(EST, "v2_analysis_spec.json"))
  needed <- c("source_artifact_hashes", "estimand_families", "outcome_definitions",
              "weighting", "uncertainty", "exclusions", "code_commit", "generated_at")
  ok("spec carries all required sections", all(needed %in% names(sp)),
     paste(setdiff(needed, names(sp)), collapse = ", "))
  ok("spec records zero API calls", identical(as.integer(sp$api_calls_made), 0L))
}

# --- summary -------------------------------------------------------------------
cat("\n", strrep("=", 78), "\n", sep = "")
if (length(fails)) {
  cat("v2 ACCEPTANCE FAILED (", length(fails), "):\n", sep = "")
  for (f in fails) cat("   - ", f, "\n", sep = "")
} else cat("v2 ACCEPTANCE PASSED\n")
cat(strrep("=", 78), "\n", sep = "")
quit(save = "no", status = if (length(fails)) 1 else 0)
