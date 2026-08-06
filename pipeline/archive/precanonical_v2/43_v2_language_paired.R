# =============================================================================
# v2 FAMILY C -- PROMPT-FIXED language effects
#   -> e36_language_paired_effects.csv
#   -> e37_language_paired_by_model.csv
#   (bootstrap diagnostics append to e39)
# =============================================================================
# ESTIMAND
#   block_id = model x prompt_id. Each block contains at most one response per
#   language, so for a non-English language L the paired difference is
#
#       delta_L = mean over COMPLETE blocks of ( Y[block, L] - Y[block, English] )
#
#   This holds the model and the exact prompt fixed and varies only the language
#   the prompt was delivered in. It is a within-block paired difference, computed
#   directly from the observed 0/1 outcomes -- no model is required, and the
#   estimate reproduces a direct tabulation exactly.
#
#   An LPM with block fixed effects, refused ~ language + factor(block_id),
#   is algebraically the same number on complete blocks. It is fitted here as a
#   CHECK, not as a separate estimator, and 46_ asserts the two agree.
#
# WHAT IT MEANS -- stated carefully
#   This is the effect of DELIVERING THE TESTED TRANSLATED PROMPT VERSION, among
#   the tested prompt/model set, conditional on:
#     * translation equivalence -- the translated prompt asks the same thing; if
#       a translation is harder, more ambiguous or differently loaded, that is
#       inside the estimate and cannot be separated from a language effect;
#     * no run-order or provider confounding -- languages were generated in
#       different runs and sometimes through different provider routings, so any
#       drift in serving is also inside the estimate.
#   It is NOT the causal effect of a user's language, and it does not generalise
#   beyond these prompts and models.
#
# SECONDARY ESTIMATORS. Conditional logistic and GLMM target different subsets
# (discordant blocks only) and different scales (log-odds, conditional). They are
# reported as secondary and are NOT the headline.

source("pipeline/archive/precanonical_v2/40_v2_common.R")
cat(strrep("=", 78), "\nFAMILY C: PROMPT-FIXED LANGUAGE EFFECTS\n", strrep("=", 78), "\n", sep = "")

B_LANG <- 2000L
LANG_LABEL_V2 <- c(en = "English", zh = "Chinese", ar = "Arabic",
                   ru = "Russian", hi = "Hindi")
NONEN <- setdiff(LANGS_V2, "en")

INTERPRETATION <- paste(
  "effect of delivering the tested translated prompt version, among the tested",
  "prompt/model set; conditional on translation equivalence and on no run-order",
  "or provider confounding; NOT a causal effect of user language")

# --- build the paired block table --------------------------------------------
# One row per (block, language). A block is complete for L iff it has BOTH the
# English and the L response.
wide <- v2 %>%
  select(block_id, model, prompt_id, issue_id, lang, juris, home_status,
         tier, refused_strict, refused_any, engagement_ordinal) %>%
  mutate(lang = as.character(lang))

paired_for <- function(L, outcome = "refused_strict") {
  en <- wide %>% filter(lang == "en") %>%
    select(block_id, model, prompt_id, issue_id, juris, home_status, tier,
           y_en = all_of(outcome))
  lx <- wide %>% filter(lang == L) %>% select(block_id, y_l = all_of(outcome))
  full <- inner_join(en, lx, by = "block_id") %>% mutate(d = y_l - y_en)
  list(complete = full,
       n_blocks_en = nrow(en), n_blocks_l = nrow(lx),
       n_complete = nrow(full),
       n_missing = nrow(en) + nrow(lx) - 2 * nrow(full))
}

# Paired mean over complete blocks; bootstrap resamples ISSUES, carrying all
# models and prompts for a drawn issue together.
paired_stat <- function(df) mean(df$d)

boot_paired <- function(df, B, label) {
  y <- df$d
  iss <- split(seq_along(y), df$issue_id)
  point <- mean(y)
  set.seed(V2_SEED)
  keys <- names(iss); vals <- numeric(0); att <- 0L; fail <- 0L
  maxatt <- ceiling(B * 1.5) + 50
  while (length(vals) < B && att < maxatt) {
    att <- att + 1L
    ix <- unlist(iss[sample(keys, length(keys), replace = TRUE)], use.names = FALSE)
    v <- mean(y[ix])
    if (!is.finite(v)) { fail <- fail + 1L; next }
    vals <- c(vals, v)
  }
  list(estimate = point,
       conf_low = unname(quantile(vals, .025)), conf_high = unname(quantile(vals, .975)),
       diag = tibble(label = label, bootstrap_unit = "issue_id", seed = V2_SEED,
                     replicates_requested = B, replicates_attempted = att,
                     replicates_successful = length(vals), replicates_failed = fail,
                     failure_rate = fail / max(att, 1), interval_method = "percentile",
                     n_rows = length(y), n_issues = length(iss)))
}

# --- e36 primary: pooled paired effect per language --------------------------
cat("\nprimary paired effects (B =", B_LANG, ")\n")
e36 <- map_dfr(NONEN, function(L) {
  P <- paired_for(L)
  bt <- boot_paired(P$complete, B_LANG, sprintf("C|paired|%s", L))
  append_boot_diag(bt$diag)
  # LPM with block fixed effects -- ALGEBRAIC CHECK, not a second estimator.
  #
  # With exactly two observations per block the within (block-FE) estimator is
  # identically the mean paired difference: demeaning gives x~ = -+0.5 and
  # y~ = -+d/2, so beta = sum(d/2) / sum(0.5) = mean(d). The two are the same
  # number by construction, not approximately.
  #
  # It is verified numerically rather than asserted -- but on a random SUBSET of
  # blocks. Fitting factor(block_id) over all ~27,000 blocks would build a design
  # matrix with 27,000 dummy columns, which is not merely slow but the wrong way
  # to compute a quantity that has a closed form.
  set.seed(V2_SEED)
  chk_blocks <- sample(P$complete$block_id, min(400L, nrow(P$complete)))
  lg <- P$complete %>% filter(block_id %in% chk_blocks) %>%
    select(block_id, y_en, y_l) %>%
    pivot_longer(c(y_en, y_l), names_to = "which", values_to = "y") %>%
    mutate(is_L = as.integer(which == "y_l"))
  lpm <- tryCatch(coef(lm(y ~ is_L + factor(block_id), data = lg))[["is_L"]],
                  error = function(e) NA_real_)
  paired_on_subset <- mean(P$complete$d[P$complete$block_id %in% chk_blocks])
  cat(sprintf("  %-8s complete blocks %6d  missing %5d  delta %+0.4f\n",
              L, P$n_complete, P$n_missing, bt$estimate))
  tibble(language = L, language_label = unname(LANG_LABEL_V2[L]),
         n_blocks_english = P$n_blocks_en, n_blocks_language = P$n_blocks_l,
         n_complete_blocks = P$n_complete, n_missing_blocks = P$n_missing,
         n_issues = n_distinct(P$complete$issue_id),
         n_models = n_distinct(P$complete$model),
         raw_mean_english = mean(P$complete$y_en),
         raw_mean_language = mean(P$complete$y_l),
         estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high,
         estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
         conf_high_pp = pp(bt$conf_high),
         lpm_block_fe_check = lpm,
         paired_on_lpm_subset = paired_on_subset,
         n_blocks_lpm_check = length(chk_blocks),
         lpm_matches_paired = isTRUE(abs(lpm - paired_on_subset) < 1e-8))
}) %>% mutate(estimand_family = "C_prompt_fixed_language",
              estimand_label = "paired within-block difference, language minus English",
              block_definition = "block_id = model x prompt_id",
              interpretation = INTERPRETATION,
              outcome = "refused_strict (engagement_code >= 4)",
              uncertainty = "issue-cluster bootstrap, percentile",
              bootstrap_unit = "issue_id")
write_csv(e36, file.path(EST, "e36_language_paired_effects.csv"))

# --- e37 heterogeneity: by model, jurisdiction, and home status ---------------
cat("\nheterogeneity by model / jurisdiction / home status\n")
het <- function(L, group_col, group_name) {
  P <- paired_for(L)
  d <- P$complete
  map_dfr(sort(unique(as.character(d[[group_col]]))), function(g) {
    dd <- d[as.character(d[[group_col]]) == g, , drop = FALSE]
    if (nrow(dd) < 20) return(NULL)
    bt <- boot_paired(dd, 800L, sprintf("C|het|%s|%s|%s", L, group_name, g))
    append_boot_diag(bt$diag)
    tibble(language = L, language_label = unname(LANG_LABEL_V2[L]),
           grouping = group_name, group = g,
           # Carried so the figure layer can colour by jurisdiction without
           # re-deriving a model->jurisdiction map of its own. Estimates should
           # travel with the keys their plots need.
           jurisdiction = if (group_name == "model")
             as.character(dd$juris[1]) else NA_character_,
           n_complete_blocks = nrow(dd), n_issues = n_distinct(dd$issue_id),
           raw_mean_english = mean(dd$y_en), raw_mean_language = mean(dd$y_l),
           estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high,
           estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
           conf_high_pp = pp(bt$conf_high))
  })
}
e37 <- bind_rows(
  map_dfr(NONEN, ~ het(.x, "model", "model")),
  map_dfr(NONEN, ~ het(.x, "juris", "jurisdiction")),
  # language x home-status heterogeneity. This is a DESCRIPTIVE interaction:
  # whether the language effect differs on home-region issues. It is explicitly
  # NOT a home causal effect and must not be read as one.
  map_dfr(NONEN, ~ het(.x, "home_status", "home_status"))) %>%
  mutate(estimand_family = "C_prompt_fixed_language",
         estimand_label = "paired within-block language difference, by subgroup",
         interpretation = INTERPRETATION,
         home_status_note = paste(
           "where grouping = home_status this is a descriptive interaction:",
           "how the language difference varies with the issue's home status.",
           "It is NOT a home-region causal effect."),
         outcome = "refused_strict (engagement_code >= 4)",
         bootstrap_unit = "issue_id")
write_csv(e37, file.path(EST, "e37_language_paired_by_model.csv"))

cat(sprintf("\nwrote e36 (%d languages) and e37 (%d subgroup rows)\n",
            nrow(e36), nrow(e37)))
cat("\npaired language effects (pp), pooled:\n")
print(as.data.frame(e36 %>% select(language_label, n_complete_blocks, n_missing_blocks,
                                   estimate_pp, conf_low_pp, conf_high_pp,
                                   lpm_matches_paired, n_blocks_lpm_check)),
      digits = 3, row.names = FALSE)
cat("\nlargest by model:\n")
print(as.data.frame(e37 %>% filter(grouping == "model") %>%
        arrange(desc(abs(estimate_pp))) %>% head(8) %>%
        select(language_label, group, n_complete_blocks, estimate_pp,
               conf_low_pp, conf_high_pp)), digits = 3, row.names = FALSE)
