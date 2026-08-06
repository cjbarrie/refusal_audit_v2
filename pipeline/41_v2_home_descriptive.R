# =============================================================================
# v2 FAMILY A -- DESCRIPTIVE home results     -> e32_home_descriptive.csv
# =============================================================================
# NO REGRESSION MODEL ANYWHERE IN THIS SCRIPT. Every number is a count or a
# weighted mean of observed 0/1 outcomes, so each cell reproduces a direct
# tabulation exactly (46_v2_acceptance_tests.R verifies this against
# independently computed counts).
#
# THREE region positions, not two:
#     home     issue region == the model jurisdiction's own region
#     away     a different named region
#     general  no regional focus at all (17% of the battery)
# `general` is reported as its own row and is NEVER part of the away reference.
# Folding it into away would score every model "away" on a sixth of the battery
# and drag the reference rate toward the global average.
#
# The reported contrast is a DESCRIPTIVE DIFFERENCE IN OBSERVED RATES. It is not
# adjusted, not standardized, and not causal.

source("pipeline/40_v2_common.R")
cat(strrep("=", 78), "\nFAMILY A: DESCRIPTIVE HOME RESULTS\n", strrep("=", 78), "\n", sep = "")

OUT <- "e32_home_descriptive.csv"
B_MAIN <- 2000L   # jurisdiction-level
B_FINE <- 1000L   # finer strata (more cells, same estimator)

# --- cell counts --------------------------------------------------------------
cells_for <- function(d, dim_name, dim_col) {
  d %>%
    group_by(jurisdiction = as.character(juris),
             stratum_value = as.character(.data[[dim_col]]),
             home_status) %>%
    summarise(n = n(), refusals_strict = sum(refused_strict),
              refusals_any = sum(refused_any),
              rate_strict = mean(refused_strict), rate_any = mean(refused_any),
              n_issues = n_distinct(issue_id), n_models = n_distinct(model),
              .groups = "drop") %>%
    mutate(stratum = dim_name, quantity = "cell_rate")
}

# --- home - away difference, under a given weighting --------------------------
diff_stat <- function(d, wfun, outcome = "refused_strict") {
  h <- d[d$home_status == "home", , drop = FALSE]
  a <- d[d$home_status == "away", , drop = FALSE]
  if (!nrow(h) || !nrow(a)) return(NA_real_)
  sum(wfun(h) * h[[outcome]]) - sum(wfun(a) * a[[outcome]])
}

contrast_for <- function(d, dim_name, dim_col, B) {
  grid <- d %>% distinct(jurisdiction = as.character(juris),
                         stratum_value = as.character(.data[[dim_col]]))
  map_dfr(seq_len(nrow(grid)), function(i) {
    g <- grid[i, ]
    dd <- d %>% filter(as.character(juris) == g$jurisdiction,
                       as.character(.data[[dim_col]]) == g$stratum_value,
                       home_status %in% c("home", "away"))
    if (!nrow(dd)) return(NULL)
    y <- as.integer(dd$refused_strict)
    attr(y, "model_idx") <- as.integer(droplevels(factor(dd$model)))
    grp <- as.integer(dd$home_status == "home")
    # Estimability of the DIFFERENCE, checked before bootstrapping. A stratum can
    # be large and still carry only one arm (e.g. CN x temporal route contains no
    # China-region issues), in which case home-minus-away does not exist. Such a
    # cell must be reported as non-estimable with the reason, never as a silent NA.
    n_h <- sum(grp == 1L); n_a <- sum(grp == 0L)
    why <- if (n_h == 0L && n_a == 0L) "no rows"
           else if (n_h == 0L) "no home rows in this stratum"
           else if (n_a == 0L) "no away rows in this stratum" else ""
    map_dfr(c("response", "equal_model"), function(wname) {
      if (nzchar(why))
        return(tibble(jurisdiction = g$jurisdiction, stratum = dim_name,
                      stratum_value = g$stratum_value, home_status = NA_character_,
                      quantity = "home_minus_away", weighting = wname,
                      estimate = NA_real_, conf_low = NA_real_, conf_high = NA_real_,
                      estimate_pp = NA_real_, conf_low_pp = NA_real_,
                      conf_high_pp = NA_real_, n = nrow(dd),
                      n_issues = n_distinct(dd$issue_id), n_models = n_distinct(dd$model),
                      n_home = n_h, n_away = n_a, estimable = FALSE,
                      replicate_failure_rate = NA_real_, note = why))
      lab <- sprintf("A|%s|%s|%s|%s", dim_name, g$jurisdiction, g$stratum_value, wname)
      bt <- boot_issue_fast(y, dd$issue_id, grp, wname, B = B,
                            seed = V2_SEED, label = lab)
      append_boot_diag(bt$diag)
      tibble(jurisdiction = g$jurisdiction, stratum = dim_name,
             stratum_value = g$stratum_value, home_status = NA_character_,
             quantity = "home_minus_away", weighting = wname,
             estimate = bt$estimate, conf_low = bt$conf_low,
             conf_high = bt$conf_high,
             estimate_pp = pp(bt$estimate),
             conf_low_pp = pp(bt$conf_low), conf_high_pp = pp(bt$conf_high),
             n = nrow(dd), n_issues = n_distinct(dd$issue_id),
             n_models = n_distinct(dd$model),
             n_home = n_h, n_away = n_a,
             estimable = bt$diag$replicates_successful > 0,
             replicate_failure_rate = bt$diag$failure_rate,
             # A high failure rate means some resamples lost an arm entirely, so
             # the interval is CONDITIONAL ON ESTIMABILITY in those replicates.
             note = ifelse(bt$diag$failure_rate > 0.05,
               sprintf("interval conditional on estimability: %.0f%% of replicates lost an arm",
                       100 * bt$diag$failure_rate), ""))
    })
  })
}

DIMS <- tribble(~name,          ~col,
                "overall",      "battery",        # one level; the jurisdiction row
                "model",        "model",
                "language",     "lang",
                "dataset_type", "tier",
                "route",        "route_f2",
                "domain",       "domain")

cat("\ncell counts\n")
cell_tbl <- map_dfr(seq_len(nrow(DIMS)), function(i)
  cells_for(v2, DIMS$name[i], DIMS$col[i]))
cat(sprintf("  %d cell rows across %d strata\n", nrow(cell_tbl), n_distinct(cell_tbl$stratum)))

cat("\nhome - away differences (issue-cluster bootstrap)\n")
contr_tbl <- map_dfr(seq_len(nrow(DIMS)), function(i) {
  B <- if (DIMS$name[i] == "overall") B_MAIN else B_FINE
  cat(sprintf("  %-13s B=%d\n", DIMS$name[i], B))
  contrast_for(v2, DIMS$name[i], DIMS$col[i], B)
})

e32 <- bind_rows(
  cell_tbl %>% mutate(weighting = "response", estimable = TRUE,
                      note = "", replicate_failure_rate = NA_real_,
                      estimate = rate_strict, conf_low = NA_real_,
                      conf_high = NA_real_, estimate_pp = pp(rate_strict),
                      conf_low_pp = NA_real_, conf_high_pp = NA_real_),
  contr_tbl) %>%
  mutate(
    outcome = "refused_strict (engagement_code >= 4)",
    estimand_family = "A_descriptive",
    estimand_label = ifelse(quantity == "cell_rate",
      "observed refusal rate in cell",
      "DESCRIPTIVE difference in observed refusal rates, home minus away"),
    causal_interpretation = "none: descriptive difference in observed rates; not adjusted, not standardized",
    general_handling = "General reported as its own row; never part of the away reference",
    uncertainty = ifelse(quantity == "cell_rate", "none (exact count)",
                         "issue-cluster bootstrap, percentile"),
    bootstrap_unit = ifelse(quantity == "cell_rate", NA_character_, "issue_id")) %>%
  select(estimand_family, quantity, jurisdiction, stratum, stratum_value,
         home_status, weighting, n, n_issues, n_models,
         refusals_strict, refusals_any, rate_strict, rate_any,
         estimate, conf_low, conf_high, estimate_pp, conf_low_pp, conf_high_pp,
         everything())
write_csv(e32, file.path(EST, OUT))

cat(sprintf("\nwrote %s: %d rows\n", OUT, nrow(e32)))
cat("\noverall home - away by jurisdiction (pp):\n")
print(as.data.frame(
  e32 %>% filter(stratum == "overall", quantity == "home_minus_away") %>%
    select(jurisdiction, weighting, estimate_pp, conf_low_pp, conf_high_pp, n)),
  digits = 3, row.names = FALSE)
cat("\nobserved cell rates by jurisdiction (%):\n")
print(as.data.frame(
  e32 %>% filter(stratum == "overall", quantity == "cell_rate") %>%
    select(jurisdiction, home_status, n, refusals_strict, rate_strict) %>%
    mutate(rate_pct = 100 * rate_strict) %>% select(-rate_strict)),
  digits = 3, row.names = FALSE)
