# =============================================================================
# Script 23: Measurement and coverage diagnostics  (ESTIMATION ONLY)
# =============================================================================
# Input : pipeline/data_clean.RData
# Output: pipeline/estimates/d01..d08*.csv
#
# These tables exist so that graph precision cannot be mistaken for measurement
# precision. Every quantity plotted anywhere in the figure system rests on a
# SINGLE LLM judge with no inter-rater reliability estimate, and the judge's
# behaviour is not uniform across its own code set: two of the seven refusal
# justification codes fire twice in the entire English sample, while a third
# ("other") absorbs 15.7% of refusals and is internally heterogeneous.
#
# Nothing here is plotted directly. It is the evidence a reader or reviewer
# needs to decide how much weight the figures can carry.

suppressPackageStartupMessages({ library(tidyverse) })
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())
source("pipeline/_theme.R")
load("pipeline/data_clean.RData")
EST <- "pipeline/estimates"; dir.create(EST, showWarnings = FALSE, recursive = TRUE)

cat(strrep("=", 78), "\nMEASUREMENT + COVERAGE DIAGNOSTICS\n", strrep("=", 78), "\n", sep = "")
d <- data_clean

# --- d01 engagement code frequency -------------------------------------------
d01 <- d %>% count(prompt_language, engagement_code) %>%
  group_by(prompt_language) %>% mutate(share = n / sum(n)) %>% ungroup() %>%
  bind_rows(d %>% count(engagement_code) %>% mutate(prompt_language = "ALL",
                                                    share = n / sum(n)))
write_csv(d01, file.path(EST, "d01_engagement_codes.csv"))
cat("d01 engagement codes\n")
print(as.data.frame(d01 %>% filter(prompt_language == "ALL") %>%
                      select(engagement_code, n, share)), digits = 3, row.names = FALSE)

# --- d02 justification codes, raw and collapsed -------------------------------
# The collapse is the step most likely to mislead, so both sides are exported
# and the mapping is carried in the table rather than living only in code.
J5 <- c(A = "neutrality", C = "harm", B = "epistemic", D = "epistemic",
        E = "epistemic", F = "none given", G = "other")
CODE_LAB <- c(A = "A neutrality", B = "B complexity", C = "C harm avoidance",
              D = "D expertise limitation", E = "E user autonomy",
              F = "F none given", G = "G other")
ref <- d %>% filter(prompt_language == "en", refused, !is.na(refusal_justification))
d02 <- ref %>% count(refusal_justification) %>%
  mutate(code_label = CODE_LAB[refusal_justification],
         collapsed_group = unname(J5[refusal_justification]),
         share = n / sum(n)) %>% arrange(desc(n))
write_csv(d02, file.path(EST, "d02_justification_codes.csv"))
cat("\nd02 justification codes (English refusals)\n")
print(as.data.frame(d02 %>% select(code_label, n, share, collapsed_group)),
      digits = 3, row.names = FALSE)

# Per-model, so the caption can name which models depend on the thin categories.
d02b <- ref %>% count(model, refusal_justification) %>%
  group_by(model) %>% mutate(n_refusals = sum(n), share = n / n_refusals) %>%
  ungroup() %>% mutate(collapsed_group = unname(J5[refusal_justification]))
write_csv(d02b, file.path(EST, "d02b_justification_by_model.csv"))
thin <- d02 %>% filter(n < 10)
cat(sprintf("  codes with < 10 observations: %s\n",
            if (nrow(thin)) paste(thin$code_label, collapse = ", ") else "none"))

# --- d03/d04 ideology distribution and neutral prevalence ---------------------
IDEO <- c(economic_left_right = "Economic", social_left_right = "Social",
          authoritarian_libertarian = "Authority", populist_elitist = "Populism")
sl <- d %>% filter(has_slant, prompt_language == "en", !is.na(jurisdiction_f)) %>%
  mutate(juris = factor(as.character(jurisdiction_f), levels = JURIS_LEVELS))
if (nrow(sl)) {
  d03 <- map_dfr(names(IDEO), function(f) {
    sl %>% filter(!is.na(.data[[f]])) %>% count(juris, code = .data[[f]]) %>%
      group_by(juris) %>% mutate(share = n / sum(n)) %>% ungroup() %>%
      mutate(dimension = unname(IDEO[f]), field = f)
  })
  write_csv(d03, file.path(EST, "d03_ideology_distribution.csv"))

  d04 <- map_dfr(names(IDEO), function(f) {
    x <- sl[[f]]; x <- x[!is.na(x)]
    tibble(dimension = unname(IDEO[f]), field = f, n = length(x),
           neutral_share = mean(x == 0), neg_share = mean(x < 0),
           pos_share = mean(x > 0), mean = mean(x), median = median(x))
  })
  write_csv(d04, file.path(EST, "d04_ideology_neutral_prevalence.csv"))
  cat("\nd04 ideology neutral prevalence\n")
  print(as.data.frame(d04 %>% select(dimension, n, neutral_share, neg_share,
                                     pos_share, mean)), digits = 3, row.names = FALSE)

  # --- d05 moral-foundation co-occurrence -----------------------------------
  # Foundations are NOT mutually exclusive; this is the evidence for that, and
  # the reason no stacked or composition form may be used for them.
  MFT <- c("care_harm", "fairness_cheating", "liberty_oppression",
           "authority_subversion", "loyalty_betrayal", "sanctity_degradation")
  M <- as.matrix(sl[, MFT]); M[is.na(M)] <- 0
  d05 <- tibble(n_foundations = 0:6,
                n = as.integer(table(factor(rowSums(M), levels = 0:6)))) %>%
    mutate(share = n / sum(n))
  write_csv(d05, file.path(EST, "d05_moral_cooccurrence.csv"))
  pairs <- expand_grid(a = MFT, b = MFT) %>% filter(a < b) %>%
    mutate(joint = map2_dbl(a, b, ~ mean(M[, .x] == 1 & M[, .y] == 1)),
           pa = map_dbl(a, ~ mean(M[, .x])), pb = map_dbl(b, ~ mean(M[, .y])),
           lift = joint / (pa * pb))
  write_csv(pairs, file.path(EST, "d05b_moral_pairwise.csv"))
  cat(sprintf("\nd05 mean foundations per engaged response: %.2f  (0 foundations: %.1f%%)\n",
              mean(rowSums(M)), 100 * mean(rowSums(M) == 0)))
}

# --- d06 missingness and coverage --------------------------------------------
# Distinguishes STRUCTURAL missingness (passes 2/3 skip refusals by design; the
# subsample deliberately covers 25% of issues) from INCIDENTAL missingness
# (responses generated after the annotation pass ran). Only the latter is a
# defect, and only the latter will shrink.
elig <- d %>% filter(slant_eligible)
d06 <- tibble(
  quantity = c("rows total", "issues", "models", "languages",
               "engagement_code missing", "refused rows missing justification",
               "slant-eligible rows", "slant-eligible AND engaged",
               "slant-eligible, engaged, coded",
               "slant-eligible, engaged, NOT coded (incidental)",
               "slant-eligible, refused, coded (should be 0; structural)"),
  value = c(nrow(d), n_distinct(d$issue_id), n_distinct(d$model),
            n_distinct(d$prompt_language), sum(is.na(d$engagement_code)),
            sum(d$refused & is.na(d$refusal_justification)),
            nrow(elig), sum(elig$engaged), sum(elig$engaged & elig$has_slant),
            sum(elig$engaged & !elig$has_slant),
            sum(!elig$engaged & elig$has_slant)))
write_csv(d06, file.path(EST, "d06_missingness.csv"))
cat("\nd06 missingness / coverage\n")
print(as.data.frame(d06), row.names = FALSE)

# --- d07 events and denominators for every plotted cell -----------------------
# Rare-outcome guard: any cell a figure draws should be checkable here for how
# many refusals it actually rests on.
en <- d %>% filter(prompt_language == "en", !is.na(jurisdiction_f))
d07 <- bind_rows(
  en %>% group_by(cell = "jurisdiction x region", a = as.character(jurisdiction_f),
                  b = as.character(region_focus)) %>%
    summarise(n = n(), events = sum(refused), .groups = "drop"),
  en %>% group_by(cell = "model x tier", a = model, b = as.character(dataset_type)) %>%
    summarise(n = n(), events = sum(refused), .groups = "drop"),
  en %>% group_by(cell = "domain x tier", a = as.character(prompt_category),
                  b = as.character(dataset_type)) %>%
    summarise(n = n(), events = sum(refused), .groups = "drop")) %>%
  mutate(rate = events / n, zero_events = events == 0)
write_csv(d07, file.path(EST, "d07_cell_denominators.csv"))
cat(sprintf("\nd07 %d plotted cells; %d with zero events\n",
            nrow(d07), sum(d07$zero_events)))

# --- d08 weighting -----------------------------------------------------------
# Models per jurisdiction differ (US 4, MENA 3, CN 2, India 1, EU 1), so every
# jurisdiction average carries an implicit weighting. Recorded once, here.
d08 <- en %>% group_by(jurisdiction = as.character(jurisdiction_f)) %>%
  summarise(n_models = n_distinct(model), n_responses = n(),
            events = sum(refused), .groups = "drop") %>%
  mutate(single_model = n_models == 1,
         responses_per_model = n_responses / n_models)
write_csv(d08, file.path(EST, "d08_weighting_structure.csv"))
cat("\nd08 weighting structure\n")
print(as.data.frame(d08), row.names = FALSE)

cat("\n", strrep("=", 78), "\nDIAGNOSTICS COMPLETE\n", strrep("=", 78), "\n", sep = "")
