# =============================================================================
# EXPANDED V3 18-MODEL ESTIMATES
# =============================================================================
# Applies the paper's current estimands to the accepted 11 models plus six fully
# annotated expansion models. Genuine refusal and capability failure are always
# separate outcomes. This remains separate from the canonical release machinery.
#
# Home point estimates use the same logistic g-computation and nested target as
# the canonical analysis: equal model weight, then equal issue weight within
# model, then equal prompt weight within model-issue. For timely provisional
# inference, 95% intervals use an issue-cluster sandwich covariance and the
# delta method rather than the canonical 2,000-draw percentile bootstrap.
# Prompt-fixed language and within-issue framing estimates use an issue-cluster
# percentile bootstrap; these resamples are computationally inexpensive.

suppressPackageStartupMessages({
  library(tidyverse)
  library(sandwich)
})
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())

IN_PATH <- "pipeline/expanded/derived/expanded_panel_v3.rds"
OUT <- "pipeline/expanded/estimates_v3"
dir.create(OUT, recursive = TRUE, showWarnings = FALSE)
SEED <- 20260903L
LANGS <- c("en", "zh", "ar", "ru", "hi")
JURIS <- c("CN", "MENA", "India", "US", "EU")
HOME_REGION <- c(CN = "China", MENA = "Arab", India = "India",
                 US = "US", EU = "Europe")
MODEL_ORDER <- c(
  "deepseek-chat-v3.1", "glm-4.7-flash", "hunyuan-a13b", "kimi-k2.5", "qwen3-max",
  "allam-7b", "falcon3-10b", "jais-8b", "sarvam-30b",
  "claude-opus-4.5", "gemini-2.5-flash-lite", "gpt-4o", "gpt-5.1",
  "grok-4.3", "llama-4-scout", "nova-lite",
  "ministral-14b", "mistral-large-2512")
OUTCOMES <- c("genuine_refusal", "capability_failure")

x <- readRDS(IN_PATH) |>
  mutate(
    juris = factor(jurisdiction, levels = JURIS),
    lang = factor(prompt_language, levels = LANGS),
    model = factor(model, levels = MODEL_ORDER),
    tier = factor(dataset_type, levels = c("base", "boundary"),
                  labels = c("regular", "boundary")),
    domain = factor(prompt_category), route_f = factor(route),
    home_status = case_when(
      region_focus == "General" ~ "general",
      region_focus == unname(HOME_REGION[jurisdiction]) ~ "home",
      TRUE ~ "away"),
    home = as.integer(home_status == "home"))
stopifnot(nrow(x) == 224544L, n_distinct(x$model) == 18L,
          !anyNA(x$juris), !anyNA(x$lang),
          !any(x$home_status == "away" & x$region_focus == "General"))

w_nested <- function(d) {
  m <- as.character(d$model); iss <- as.character(d$issue_id)
  mi <- paste(m, iss, sep = "\r")
  issues_per_m <- tapply(iss, m, function(z) length(unique(z)))
  rows_per_mi <- table(mi)
  (1 / length(unique(m))) * (1 / as.numeric(issues_per_m[m])) *
    (1 / as.numeric(rows_per_mi[mi]))
}

gcomp_cluster <- function(d, outcome, by_model = FALSE) {
  d <- droplevels(d)
  events <- sum(d[[outcome]])
  if (!nrow(d) || events == 0L || events == nrow(d) ||
      length(unique(d$home)) < 2L)
    return(tibble(estimate = NA_real_, conf_low = NA_real_,
                  conf_high = NA_real_, std_error = NA_real_, estimable = FALSE,
                  n = nrow(d), events = events, n_issues = n_distinct(d$issue_id)))
  rhs <- if (n_distinct(d$model) > 1L)
    "home * model + tier + domain + route_f" else
    "home + tier + domain + route_f"
  fit <- tryCatch(glm(as.formula(paste(outcome, "~", rhs)), data = d,
                      family = binomial()), error = function(e) NULL)
  if (is.null(fit) || any(!is.finite(coef(fit))))
    return(tibble(estimate = NA_real_, conf_low = NA_real_,
                  conf_high = NA_real_, std_error = NA_real_, estimable = FALSE,
                  n = nrow(d), events = events, n_issues = n_distinct(d$issue_id)))
  d1 <- d; d1$home <- 1L
  d0 <- d; d0$home <- 0L
  tt <- delete.response(terms(fit))
  X1 <- model.matrix(tt, d1, contrasts.arg = fit$contrasts)
  X0 <- model.matrix(tt, d0, contrasts.arg = fit$contrasts)
  b <- coef(fit)
  X1 <- X1[, names(b), drop = FALSE]; X0 <- X0[, names(b), drop = FALSE]
  p1 <- plogis(drop(X1 %*% b)); p0 <- plogis(drop(X0 %*% b))
  w <- w_nested(d)
  est <- sum(w * (p1 - p0))
  grad <- colSums(X1 * (w * p1 * (1 - p1))) -
    colSums(X0 * (w * p0 * (1 - p0)))
  V <- tryCatch(sandwich::vcovCL(fit, cluster = d$issue_id, type = "HC1"),
                error = function(e) NULL)
  se <- if (is.null(V)) NA_real_ else sqrt(max(0, drop(t(grad) %*% V %*% grad)))
  tibble(estimate = est, conf_low = est - 1.96 * se,
         conf_high = est + 1.96 * se, std_error = se, estimable = is.finite(se),
         standardized_home_risk = sum(w * p1),
         standardized_away_risk = sum(w * p0),
         n = nrow(d), events = events, n_issues = n_distinct(d$issue_id))
}

boot_issue <- function(d, stat, B = 2000L, seed = SEED) {
  issues <- unique(d$issue_id); idx <- split(seq_len(nrow(d)), d$issue_id)
  point <- stat(d); set.seed(seed)
  vals <- replicate(B, {
    draw <- sample(issues, length(issues), replace = TRUE)
    stat(d[unlist(idx[draw], use.names = FALSE), , drop = FALSE])
  })
  vals <- vals[is.finite(vals)]
  c(estimate = point, conf_low = unname(quantile(vals, .025)),
    conf_high = unname(quantile(vals, .975)), successful = length(vals))
}

# 1. Complete-corpus descriptive rates ---------------------------------------
rates <- x |> group_by(jurisdiction = as.character(juris), model,
                        prompt_language = as.character(lang)) |>
  summarise(n = n(), n_issues = n_distinct(issue_id),
            genuine_refusal_n = sum(genuine_refusal),
            genuine_refusal_rate = mean(genuine_refusal),
            capability_failure_n = sum(capability_failure),
            capability_failure_rate = mean(capability_failure), .groups = "drop")
write_csv(rates, file.path(OUT, "e01_model_language_rates.csv"))

overall <- x |> group_by(jurisdiction = as.character(juris), model) |>
  summarise(n = n(), across(all_of(OUTCOMES), list(n = sum, rate = mean)),
            .groups = "drop")
write_csv(overall, file.path(OUT, "e02_model_overall_rates.csv"))

# 2. English home-region standardized predictive contrasts -----------------
en_home <- x |> filter(lang == "en", home_status %in% c("home", "away"))
home_juris <- map_dfr(JURIS, function(j) {
  d <- en_home |> filter(juris == j)
  map_dfr(OUTCOMES, function(y) gcomp_cluster(d, y) |>
            mutate(jurisdiction = j, outcome = y, .before = 1))
}) |> mutate(
  estimate_pp = 100 * estimate, conf_low_pp = 100 * conf_low,
  conf_high_pp = 100 * conf_high,
  estimand = "standardized home-minus-away predictive risk difference",
  formula = "outcome ~ home * model + tier + domain + route",
  target = "English; equal model, equal issue within model, equal prompt within model-issue",
  uncertainty = "issue-cluster sandwich covariance; delta-method 95% interval",
  causal_interpretation = "predictive standardization, not an identified causal effect")
write_csv(home_juris, file.path(OUT, "e03_home_by_jurisdiction.csv"))

home_model <- map_dfr(MODEL_ORDER, function(m) {
  d <- en_home |> filter(model == m)
  map_dfr(OUTCOMES, function(y) gcomp_cluster(d, y) |>
            mutate(model = m, jurisdiction = as.character(d$juris[1]),
                   outcome = y, .before = 1))
}) |> mutate(estimate_pp = 100 * estimate, conf_low_pp = 100 * conf_low,
            conf_high_pp = 100 * conf_high,
            estimand = "model-specific standardized home-minus-away predictive risk difference",
            formula = "outcome ~ home + tier + domain + route")
write_csv(home_model, file.path(OUT, "e04_home_by_model.csv"))

# 3. Prompt-fixed language contrasts -----------------------------------------
paired_language <- function(language, outcome) {
  meta <- x |> distinct(model, prompt_id, issue_id, juris)
  en <- x |> filter(lang == "en") |> select(model, prompt_id, y_en = all_of(outcome))
  tg <- x |> filter(lang == language) |> select(model, prompt_id, y_tg = all_of(outcome))
  inner_join(meta, en, by = c("model", "prompt_id")) |>
    inner_join(tg, by = c("model", "prompt_id")) |> mutate(d = y_tg - y_en)
}
equal_model_mean <- function(d) mean(tapply(d$d, as.character(d$model), mean))
language_aggregate <- map_dfr(setdiff(LANGS, "en"), function(l) {
  map_dfr(OUTCOMES, function(y) {
    d <- paired_language(l, y)
    z <- boot_issue(d, equal_model_mean, 2000L,
                    SEED + sum(utf8ToInt(paste(l, y))))
    tibble(language = l, outcome = y, estimate = z["estimate"],
           conf_low = z["conf_low"], conf_high = z["conf_high"],
           n_blocks = nrow(d), n_issues = n_distinct(d$issue_id),
           mean_english = mean(tapply(d$y_en, d$model, mean)),
           mean_target = mean(tapply(d$y_tg, d$model, mean)))
  })
}) |> mutate(estimate_pp = 100 * estimate, conf_low_pp = 100 * conf_low,
             conf_high_pp = 100 * conf_high,
             estimand = "paired target-language minus English difference",
             block = "model x prompt_id", weighting = "equal model",
             uncertainty = "issue-cluster percentile bootstrap, 2,000 draws")
write_csv(language_aggregate, file.path(OUT, "e05_language_paired.csv"))

language_model <- map_dfr(setdiff(LANGS, "en"), function(l) {
  map_dfr(OUTCOMES, function(y) {
    d <- paired_language(l, y)
    map_dfr(MODEL_ORDER, function(m) {
      dm <- d |> filter(model == m)
      z <- boot_issue(dm, function(q) mean(q$d), 500L,
                      SEED + sum(utf8ToInt(paste(l, y, m))))
      tibble(language = l, outcome = y, model = m,
             jurisdiction = as.character(dm$juris[1]), estimate = z["estimate"],
             conf_low = z["conf_low"], conf_high = z["conf_high"],
             n_blocks = nrow(dm), n_issues = n_distinct(dm$issue_id))
    })
  })
}) |> mutate(estimate_pp = 100 * estimate, conf_low_pp = 100 * conf_low,
             conf_high_pp = 100 * conf_high,
             evidence_status = "exploratory model heterogeneity")
write_csv(language_model, file.path(OUT, "e06_language_by_model.csv"))

# 4. Within-issue regular/boundary framing contrast --------------------------
framing_blocks <- function(outcome) x |> filter(lang == "en") |>
  group_by(issue_id, model, juris) |>
  summarise(n_regular = sum(tier == "regular"),
            n_boundary = sum(tier == "boundary"),
            mean_regular = mean(.data[[outcome]][tier == "regular"]),
            mean_boundary = mean(.data[[outcome]][tier == "boundary"]),
            .groups = "drop") |>
  filter(n_regular == 2L, n_boundary == 2L) |>
  mutate(d = mean_boundary - mean_regular)

framing <- map_dfr(OUTCOMES, function(y) {
  d <- framing_blocks(y)
  z <- boot_issue(d, equal_model_mean, 2000L, SEED + sum(utf8ToInt(y)))
  tibble(outcome = y, estimate = z["estimate"], conf_low = z["conf_low"],
         conf_high = z["conf_high"], n_blocks = nrow(d),
         n_issues = n_distinct(d$issue_id),
         mean_regular = mean(tapply(d$mean_regular, d$model, mean)),
         mean_boundary = mean(tapply(d$mean_boundary, d$model, mean)))
}) |> mutate(estimate_pp = 100 * estimate, conf_low_pp = 100 * conf_low,
             conf_high_pp = 100 * conf_high,
             estimand = "paired boundary-minus-regular difference within issue x model",
             weighting = "equal model",
             uncertainty = "issue-cluster percentile bootstrap, 2,000 draws")
write_csv(framing, file.path(OUT, "e07_framing_paired.csv"))

framing_model <- map_dfr(OUTCOMES, function(y) {
  d <- framing_blocks(y)
  map_dfr(MODEL_ORDER, function(m) {
    dm <- d |> filter(model == m)
    z <- boot_issue(dm, function(q) mean(q$d), 500L,
                    SEED + sum(utf8ToInt(paste(y, m))))
    tibble(outcome = y, model = m, jurisdiction = as.character(dm$juris[1]),
           estimate = z["estimate"], conf_low = z["conf_low"],
           conf_high = z["conf_high"], n_blocks = nrow(dm))
  })
}) |> mutate(estimate_pp = 100 * estimate, conf_low_pp = 100 * conf_low,
             conf_high_pp = 100 * conf_high,
             evidence_status = "exploratory model heterogeneity")
write_csv(framing_model, file.path(OUT, "e08_framing_by_model.csv"))

cat(sprintf("Wrote expanded v3 estimates for %d models and %s responses\n",
            n_distinct(x$model), format(nrow(x), big.mark = ",")))
