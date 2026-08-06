# =============================================================================
# CANONICAL PART 2 -- prompt-delivery effects
#   c08 language paired        c10 framing paired
#   c09 language by model      c11 framing by model and domain
# =============================================================================
# Both estimands here are PAIRED and computed directly from observed outcomes:
# no model is required, and each reproduces a direct tabulation exactly.
#
# A. LANGUAGE. block_id = model x prompt_id; for a non-English language L,
#    delta_L = mean over complete blocks of ( Y[block,L] - Y[block,English] ).
#    Holds the model and the exact prompt fixed and varies only delivery language.
#
#    INTERPRETATION: the effect of delivering the tested translated prompt
#    version, conditional on (i) translation equivalence -- a translation that is
#    harder, more ambiguous or differently loaded carries that difference inside
#    the estimate -- and (ii) no language-specific run-time, provider or
#    annotation drift, since languages were generated in separate runs, sometimes
#    through different provider routings, and judged by the same judge whose
#    behaviour may itself vary by language. It is NOT the causal effect of a
#    user's language.
#
# B. FRAMING. For each issue x model x language block,
#    delta = mean(boundary outcomes) - mean(regular outcomes), then averaged with
#    equal model weighting. Regular and boundary prompts derive from the same
#    issue by design, so the pairing is real.
#
#    A causal reading of framing requires the generated regular and boundary
#    variants to be EXCHANGEABLE given the issue -- i.e. that the two prompt
#    templates differ only in framing and not in difficulty, specificity or
#    loadedness. They were produced by a generation template, not randomised, so
#    that is an assumption, not a design guarantee.

source("pipeline/50_canonical_common.R")
cat(strrep("=", 78), "\nCANONICAL PART 2: PROMPT DELIVERY\n", strrep("=", 78), "\n", sep = "")

B_HEAD <- as.integer(Sys.getenv("CANON_B_HEAD", "2000"))
B_SENS <- as.integer(Sys.getenv("CANON_B_SENS", "500"))
NONEN <- setdiff(LANGS_C, "en")
LANG_LAB <- c(en = "English", zh = "Chinese", ar = "Arabic", ru = "Russian", hi = "Hindi")

LANG_INTERP <- paste(
  "effect of delivering the tested translated prompt version, among the tested",
  "prompt/model set; conditional on translation equivalence and on no",
  "language-specific run-time, provider or annotation drift;",
  "NOT the causal effect of user language")
FRAME_INTERP <- paste(
  "paired boundary-minus-regular difference within issue x model x language;",
  "a causal reading requires the generated regular and boundary prompt variants",
  "to be exchangeable given the issue, which is an assumption about the",
  "generation template, not a randomisation")

# -----------------------------------------------------------------------------
# Generic paired bootstrap: resample ISSUES, carrying every block for a drawn
# issue together, with multiplicity preserved.
# -----------------------------------------------------------------------------
boot_paired <- function(df, stat, B, label) {
  iss <- split(seq_len(nrow(df)), df$issue_id)
  keys <- names(iss)
  d0 <- df; d0$bootstrap_issue_instance <- as.character(d0$issue_id)
  point <- stat(d0)
  set.seed(CAN_SEED)
  vals <- numeric(0); att <- 0L; fail <- 0L
  while (length(vals) < B && att < B * 1.5 + 50) {
    att <- att + 1L
    drawn <- sample(keys, length(keys), replace = TRUE)
    rows <- unlist(iss[drawn], use.names = FALSE)
    dd <- df[rows, , drop = FALSE]
    dd$bootstrap_issue_instance <- rep(paste0(drawn, "#", seq_along(drawn)),
                                       times = lengths(iss[drawn]))
    v <- stat(dd)
    if (!is.finite(v)) { fail <- fail + 1L; next }
    vals <- c(vals, v)
  }
  record_diag(tibble(canonical_run_id = CANONICAL_RUN_ID, label = label,
                     bootstrap_unit = "issue_id", multiplicity_preserved = TRUE,
                     copy_id_column = "bootstrap_issue_instance", seed = CAN_SEED,
                     replicates_requested = B, replicates_attempted = att,
                     replicates_successful = length(vals), replicates_failed = fail,
                     failure_rate = fail / max(att, 1), interval_method = "percentile",
                     n_rows = nrow(df), n_issues = length(keys)))
  list(estimate = point, conf_low = unname(quantile(vals, .025)),
       conf_high = unname(quantile(vals, .975)))
}

# Three weightings of a per-block difference `d`.
wmean_blocks <- function(df, how) {
  ic <- if ("bootstrap_issue_instance" %in% names(df)) "bootstrap_issue_instance" else "issue_id"
  if (how == "pooled") return(mean(df$d))
  if (how == "equal_model") {
    m <- tapply(df$d, as.character(df$model), mean)
    return(mean(m))
  }
  # equal_model_issue: within model, each issue equal; then models equal
  key <- paste(as.character(df$model), df[[ic]], sep = "\r")
  cell <- tapply(df$d, key, mean)
  mod <- sub("\r.*$", "", names(cell))
  mean(tapply(cell, mod, mean))
}

# =============================================================================
# A. LANGUAGE  (c08, c09)
# =============================================================================
cat("\nA. paired language effects\n")

paired_blocks <- function(L, outcome = "refused_strict", d = canon) {
  en <- d %>% filter(lang == "en") %>%
    select(block_id, model, prompt_id, issue_id, juris, home_status, tier,
           y_en = all_of(outcome))
  lx <- d %>% filter(lang == L) %>% select(block_id, y_l = all_of(outcome))
  full <- inner_join(en, lx, by = "block_id") %>% mutate(d = y_l - y_en)
  list(blocks = full, n_en = nrow(en), n_l = nrow(lx), n_complete = nrow(full),
       n_missing = nrow(en) + nrow(lx) - 2 * nrow(full))
}

c08 <- map_dfr(NONEN, function(L) {
  P <- paired_blocks(L)
  map_dfr(c("pooled", "equal_model", "equal_model_issue"), function(how) {
    bt <- boot_paired(P$blocks, function(x) wmean_blocks(x, how),
                      if (how == "pooled") B_HEAD else B_SENS,
                      sprintf("c08|%s|%s", L, how))
    tibble(language = L, language_label = unname(LANG_LAB[L]), weighting = how,
           estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high,
           estimate_pp = pp(bt$estimate), conf_low_pp = pp(bt$conf_low),
           conf_high_pp = pp(bt$conf_high),
           n_complete_blocks = P$n_complete, n_missing_blocks = P$n_missing,
           n_blocks_english = P$n_en, n_blocks_language = P$n_l,
           n_issues = n_distinct(P$blocks$issue_id),
           raw_mean_english = mean(P$blocks$y_en),
           raw_mean_language = mean(P$blocks$y_l))
  })
})

cat("  sensitivities: any-refusal, response length, prompt type, home status\n")
lang_sens <- bind_rows(
  map_dfr(NONEN, function(L) {
    P <- paired_blocks(L, "refused_any")
    bt <- boot_paired(P$blocks, function(x) wmean_blocks(x, "pooled"), B_SENS,
                      sprintf("c08s|any|%s", L))
    tibble(language = L, sensitivity = "outcome_any_refusal", level = "codes 3-5",
           estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high)
  }),
  map_dfr(NONEN, function(L) map_dfr(c("regular", "boundary"), function(t) {
    P <- paired_blocks(L); b <- P$blocks %>% filter(tier == t)
    bt <- boot_paired(b, function(x) wmean_blocks(x, "pooled"), B_SENS,
                      sprintf("c08s|tier|%s|%s", L, t))
    tibble(language = L, sensitivity = "prompt_type", level = t,
           estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high)
  })),
  map_dfr(NONEN, function(L) map_dfr(c("home", "away", "general"), function(h) {
    P <- paired_blocks(L); b <- P$blocks %>% filter(home_status == h)
    if (nrow(b) < 50) return(NULL)
    bt <- boot_paired(b, function(x) wmean_blocks(x, "pooled"), B_SENS,
                      sprintf("c08s|home|%s|%s", L, h))
    tibble(language = L, sensitivity = "home_status", level = h,
           estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high)
  })))
if (!is.null(CANON_LEN)) {
  lang_sens <- bind_rows(lang_sens, map_dfr(NONEN, function(L) {
    en <- canon %>% filter(lang == "en") %>%
      left_join(CANON_LEN, by = c("prompt_id", "prompt_language", "model")) %>%
      select(block_id, model, issue_id, y_en = refused_strict, len_en = response_chars)
    lx <- canon %>% filter(lang == L) %>%
      left_join(CANON_LEN, by = c("prompt_id", "prompt_language", "model")) %>%
      select(block_id, y_l = refused_strict, len_l = response_chars)
    j <- inner_join(en, lx, by = "block_id") %>%
      filter(!is.na(len_en), !is.na(len_l), pmin(len_en, len_l) >= 50) %>%
      mutate(d = y_l - y_en)
    bt <- boot_paired(j, function(x) wmean_blocks(x, "pooled"), B_SENS,
                      sprintf("c08s|len|%s", L))
    tibble(language = L, sensitivity = "min_response_chars", level = "50 (both sides)",
           estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high)
  }))
}

# Judge sensitivity: recompute the pooled paired effect under each judge.
cat("  judge sensitivity\n")
JUDGES <- judge_labels(language = "en")
lang_judge <- tibble()
if (!is.null(JUDGES) && nrow(JUDGES)) {
  lang_judge <- map_dfr(sort(unique(JUDGES$judge_model)), function(j) {
    lab <- JUDGES %>% filter(judge_model == j) %>%
      transmute(block_id = paste(model, prompt_id, sep = "||"),
                y_en_j = as.integer(engagement_code >= 4))
    map_dfr(NONEN, function(L) {
      P <- paired_blocks(L)
      # Only the ENGLISH side has panel coverage, so this varies the English
      # reference label while holding the language-side label at the canonical
      # judge. Reported as a bound on judge influence, not a full recomputation.
      b <- P$blocks %>% inner_join(lab, by = "block_id") %>%
        mutate(d = y_l - y_en_j)
      if (nrow(b) < 100) return(NULL)
      tibble(language = L, sensitivity = "judge (English side only)", level = j,
             estimate = mean(b$d), conf_low = NA_real_, conf_high = NA_real_,
             n_blocks = nrow(b))
    })
  })
}

c08 <- bind_rows(
  c08 %>% mutate(sensitivity = "primary", level = weighting),
  lang_sens %>% mutate(weighting = "pooled",
                       estimate_pp = pp(estimate), conf_low_pp = pp(conf_low),
                       conf_high_pp = pp(conf_high),
                       language_label = unname(LANG_LAB[language])),
  lang_judge %>% mutate(weighting = "pooled", estimate_pp = pp(estimate),
                        language_label = unname(LANG_LAB[language]))) %>%
  mutate(estimand = "paired within-block difference, language minus English",
         block_definition = "block_id = model x prompt_id",
         interpretation = LANG_INTERP, outcome = "refused_strict (codes 4-5)",
         bootstrap_unit = "issue_id", canonical_run_id = CANONICAL_RUN_ID)
write_csv(c08, file.path(CAN_EST, "c08_language_paired.csv"))
cat("\n  primary (pooled):\n")
print(as.data.frame(c08 %>% filter(sensitivity == "primary", weighting == "pooled") %>%
        select(language_label, estimate_pp, conf_low_pp, conf_high_pp,
               n_complete_blocks, n_missing_blocks)), digits = 3, row.names = FALSE)

cat("\n  heterogeneity by model and jurisdiction\n")
c09 <- map_dfr(NONEN, function(L) {
  P <- paired_blocks(L)
  bind_rows(
    map_dfr(sort(unique(as.character(P$blocks$model))), function(m) {
      b <- P$blocks %>% filter(model == m)
      bt <- boot_paired(b, function(x) mean(x$d), B_SENS, sprintf("c09|m|%s|%s", L, m))
      tibble(language = L, grouping = "model", group = m,
             jurisdiction = as.character(b$juris[1]), n_blocks = nrow(b),
             estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high)
    }),
    map_dfr(JURIS_C, function(j) {
      b <- P$blocks %>% filter(juris == j)
      if (!nrow(b)) return(NULL)
      bt <- boot_paired(b, function(x) wmean_blocks(x, "equal_model"), B_SENS,
                        sprintf("c09|j|%s|%s", L, j))
      tibble(language = L, grouping = "jurisdiction", group = j, jurisdiction = j,
             n_blocks = nrow(b), estimate = bt$estimate,
             conf_low = bt$conf_low, conf_high = bt$conf_high)
    }))
}) %>% mutate(language_label = unname(LANG_LAB[language]),
              estimate_pp = pp(estimate), conf_low_pp = pp(conf_low),
              conf_high_pp = pp(conf_high), interpretation = LANG_INTERP,
              canonical_run_id = CANONICAL_RUN_ID)
write_csv(c09, file.path(CAN_EST, "c09_language_by_model.csv"))
cat(sprintf("  c09: %d rows\n", nrow(c09)))

# =============================================================================
# B. FRAMING  (c10, c11)
# =============================================================================
cat("\nB. paired framing effects (English primary)\n")

frame_blocks <- function(d, outcome = "refused_strict") {
  d %>% group_by(issue_id, model, lang, juris, domain) %>%
    summarise(n_reg = sum(tier == "regular"), n_bnd = sum(tier == "boundary"),
              mean_reg = mean(.data[[outcome]][tier == "regular"]),
              mean_bnd = mean(.data[[outcome]][tier == "boundary"]),
              .groups = "drop") %>%
    filter(n_reg > 0, n_bnd > 0) %>% mutate(d = mean_bnd - mean_reg)
}

FB_EN <- frame_blocks(CANON_ENGLISH)
bt <- boot_paired(FB_EN, function(x) wmean_blocks(x, "equal_model"), B_HEAD, "c10|overall")
c10 <- tibble(scope = "overall", level = "all models", n_blocks = nrow(FB_EN),
              n_issues = n_distinct(FB_EN$issue_id),
              mean_regular = mean(FB_EN$mean_reg), mean_boundary = mean(FB_EN$mean_bnd),
              estimate = bt$estimate, conf_low = bt$conf_low, conf_high = bt$conf_high)

for (how in c("pooled", "equal_model_issue")) {
  b2 <- boot_paired(FB_EN, function(x) wmean_blocks(x, how), B_SENS,
                    sprintf("c10|w|%s", how))
  c10 <- bind_rows(c10, tibble(scope = "weighting sensitivity", level = how,
    n_blocks = nrow(FB_EN), n_issues = n_distinct(FB_EN$issue_id),
    estimate = b2$estimate, conf_low = b2$conf_low, conf_high = b2$conf_high))
}
# any-refusal outcome
FB_ANY <- frame_blocks(CANON_ENGLISH, "refused_any")
b3 <- boot_paired(FB_ANY, function(x) wmean_blocks(x, "equal_model"), B_SENS, "c10|any")
c10 <- bind_rows(c10, tibble(scope = "outcome sensitivity", level = "refused_any (codes 3-5)",
  n_blocks = nrow(FB_ANY), estimate = b3$estimate, conf_low = b3$conf_low,
  conf_high = b3$conf_high))

c10 <- c10 %>% mutate(estimate_pp = pp(estimate), conf_low_pp = pp(conf_low),
                      conf_high_pp = pp(conf_high),
                      estimand = "paired boundary-minus-regular framing difference",
                      block_definition = "issue_id x model x language",
                      sample = "English", weighting = "equal-model unless stated",
                      interpretation = FRAME_INTERP, bootstrap_unit = "issue_id",
                      canonical_run_id = CANONICAL_RUN_ID)
write_csv(c10, file.path(CAN_EST, "c10_framing_paired.csv"))
print(as.data.frame(c10 %>% select(scope, level, estimate_pp, conf_low_pp, conf_high_pp)),
      digits = 3, row.names = FALSE)

cat("\n  framing by model and domain\n")
c11 <- bind_rows(
  map_dfr(sort(unique(as.character(FB_EN$model))), function(m) {
    b <- FB_EN %>% filter(model == m)
    r <- boot_paired(b, function(x) mean(x$d), B_SENS, sprintf("c11|m|%s", m))
    tibble(grouping = "model", group = m, jurisdiction = as.character(b$juris[1]),
           n_blocks = nrow(b), estimate = r$estimate,
           conf_low = r$conf_low, conf_high = r$conf_high)
  }),
  map_dfr(sort(unique(as.character(FB_EN$domain))), function(dm) {
    b <- FB_EN %>% filter(domain == dm)
    r <- boot_paired(b, function(x) wmean_blocks(x, "equal_model"), B_SENS,
                     sprintf("c11|d|%s", dm))
    tibble(grouping = "domain", group = dm, jurisdiction = NA_character_,
           n_blocks = nrow(b), estimate = r$estimate,
           conf_low = r$conf_low, conf_high = r$conf_high)
  })) %>%
  mutate(estimate_pp = pp(estimate), conf_low_pp = pp(conf_low),
         conf_high_pp = pp(conf_high), interpretation = FRAME_INTERP,
         canonical_run_id = CANONICAL_RUN_ID)

# Legacy GLMMs retained as SENSITIVITIES only.
cat("  legacy GLMM sensitivities\n")
suppressPackageStartupMessages(library(lme4))
glmm_rows <- tibble()
for (spec in c("refused ~ tier + (1|issue_id)",
               "refused ~ tier * domain + model + (1|issue_id)")) {
  m <- tryCatch(glmer(as.formula(sub("refused", "refused_strict", spec)),
                      data = CANON_ENGLISH, family = binomial,
                      control = glmerControl(optimizer = "bobyqa",
                                             optCtrl = list(maxfun = 2e5))),
                error = function(e) NULL)
  glmm_rows <- bind_rows(glmm_rows, tibble(
    grouping = "legacy GLMM sensitivity", group = spec, jurisdiction = NA_character_,
    n_blocks = nrow(CANON_ENGLISH),
    estimate = if (is.null(m)) NA_real_ else unname(fixef(m)["tierboundary"]),
    conf_low = NA_real_, conf_high = NA_real_, estimate_pp = NA_real_,
    interpretation = paste("LOG-ODDS coefficient, not a probability difference;",
                           "retained as a sensitivity only")))
}
c11 <- bind_rows(c11, glmm_rows) %>% mutate(canonical_run_id = CANONICAL_RUN_ID)
write_csv(c11, file.path(CAN_EST, "c11_framing_by_model_domain.csv"))
cat(sprintf("  c11: %d rows\n", nrow(c11)))

flush_diag()
cat("\n", strrep("=", 78), "\nPART 2 DONE\n", strrep("=", 78), "\n", sep = "")
