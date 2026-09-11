# =============================================================================
# Technical reference: docs/r_pipeline/17_response_validity.md
# CANONICAL PART 7 -- Sol v1.1 design-based response-validity integration
# =============================================================================
# Original engagement_code >= 4 is "judge-coded non-engagement", never
# "refusal" without qualification. Sol is a machine reference, not human truth.
# Corrected families report original, reference-HT, prediction-only, and
# rectified DSL points separately. DSL inference combines an issue bootstrap,
# Rao-Wu SRSWOR phase-two replicates, and ten-split cross-fit variation.

source("pipeline/10_canonical_common.R")
suppressPackageStartupMessages({ library(arrow); library(tidyverse); library(digest) })

B_VALID <- as.integer(Sys.getenv("CANON_B_VALID", "500"))
VALID_CORES <- max(1L, as.integer(Sys.getenv("CANON_VALID_CORES", "4")))
DSL_DIR <- Sys.getenv("RESPONSE_VALIDITY_DSL_DIR",
                      "annotations/response_validity_dsl_v1_1")
DSL_PATH <- file.path(DSL_DIR, "dsl_pseudo_outcomes.parquet")
REF_PATH <- file.path(DSL_DIR, "assembled_reference_labels.parquet")
UNI_PATH <- file.path(DSL_DIR, "reference_universe.parquet")
MAN_PATH <- file.path(DSL_DIR, "reference_manifest.json")
for (p in c(DSL_PATH, REF_PATH, UNI_PATH, MAN_PATH))
  if (!file.exists(p)) stop("required Sol DSL v1.1 input absent: ", p)

KEY <- c("prompt_id", "prompt_language", "model")
OUTCOMES <- c("clean_genuine_refusal", "capability_failure", "coherent_pivot")
OUTCOME_LABEL <- c(clean_genuine_refusal = "genuine_refusal",
                   capability_failure = "capability_failure",
                   coherent_pivot = "coherent_pivot")
METHODS <- c("reference_ht", "prediction", "dsl")
CONTROL_STRATA <- c("model", "prompt_language", "home_status", "engagement_code")

dsl <- arrow::read_parquet(DSL_PATH) %>% as_tibble()
ref <- arrow::read_parquet(REF_PATH) %>% as_tibble()
uni <- arrow::read_parquet(UNI_PATH) %>% as_tibble()
manifest <- jsonlite::fromJSON(MAN_PATH, simplifyVector = TRUE)
stopifnot(manifest$version == "response-validity-dsl-v1.1-singleton-variance-repair",
          manifest$n_reference_total == 14182L, manifest$n_population == 137186L,
          nrow(dsl) == nrow(canon), !anyDuplicated(dsl[KEY]),
          nrow(ref) == 14182L, !anyDuplicated(ref[KEY]),
          nrow(uni) == 14182L, !anyDuplicated(uni[KEY]),
          all(OUTCOMES %in% names(ref)),
          all(paste0("dsl_pseudo_", OUTCOMES) %in% names(dsl)))
repeat_cols <- unlist(lapply(OUTCOMES, function(y)
  sprintf("dsl_pseudo_r%02d_%s", 0:9, y)), use.names = FALSE)
stopifnot(all(repeat_cols %in% names(dsl)))

# Sampling metadata are present only for reference-observed rows.
ref_keep <- ref %>% select(all_of(KEY), all_of(OUTCOMES)) %>%
  rename_with(~paste0("reference_", .x), all_of(OUTCOMES))
uni_keep <- uni %>% select(all_of(KEY), reference_stratum,
                           inclusion_probability, sampling_weight, N, n)
AN <- canon %>% left_join(dsl, by = KEY) %>%
  left_join(ref_keep, by = KEY) %>%
  left_join(uni_keep, by = KEY) %>%
  mutate(reference_observed = !is.na(inclusion_probability),
         original_nonengagement = refused_strict)
stopifnot(nrow(AN) == 137186L, !anyDuplicated(AN[KEY]),
          sum(AN$reference_observed) == 14182L,
          all(AN$inclusion_probability[AN$reference_observed] > 0),
          all(AN$inclusion_probability[AN$reference_observed] <= 1),
          !any(AN$reference_observed & AN$N > 1 & AN$n < 2))

# Phase-two sampled-control groups. Census rows receive multiplier one.
ctl_idx <- which(AN$reference_observed & AN$engagement_code < 4 &
                   AN$inclusion_probability < 1)
CTL_GROUPS <- split(ctl_idx, interaction(AN[ctl_idx, CONTROL_STRATA],
                                        drop = TRUE, lex.order = TRUE))
stopifnot(length(CTL_GROUPS) > 0,
          all(vapply(CTL_GROUPS, length, integer(1)) >= 2L))

phase2_multiplier <- function(seed) {
  set.seed(seed); q <- rep(1, nrow(AN))
  for (ii in CTL_GROUPS) {
    nh <- length(ii); fh <- unique(AN$inclusion_probability[ii])
    if (length(fh) != 1L || !is.finite(fh) || fh <= 0 || fh >= 1)
      stop("invalid phase-two group inclusion probability")
    m <- tabulate(sample.int(nh, nh - 1L, replace = TRUE), nbins = nh)
    q[ii] <- (1 - sqrt(1 - fh)) + sqrt(1 - fh) * nh / (nh - 1) * m
  }
  q
}

analysis_y <- function(outcome, method, q = rep(1, nrow(AN))) {
  if (method == "original") return(AN$original_nonengagement)
  pred <- AN[[paste0("dsl_prediction_", outcome)]]
  corr <- AN[[paste0("dsl_residual_correction_", outcome)]]
  if (method == "prediction") return(pred)
  if (method == "dsl") return(pred + q * corr)
  if (method == "reference_ht") {
    yy <- AN[[paste0("reference_", outcome)]]; z <- rep(0, nrow(AN))
    obs <- AN$reference_observed
    z[obs] <- yy[obs] / AN$inclusion_probability[obs]
    z[ctl_idx] <- q[ctl_idx] * z[ctl_idx]
    return(z)
  }
  stop("unknown estimator method: ", method)
}

draw_issues <- function(eligible, seed) {
  ii <- which(eligible); by_issue <- split(ii, AN$issue_id[ii]); issues <- names(by_issue)
  set.seed(seed); drawn <- sample(issues, length(issues), replace = TRUE)
  list(rows = unlist(by_issue[drawn], use.names = FALSE),
       instance = rep(paste0(drawn, "#", seq_along(drawn)),
                      times = lengths(by_issue[drawn])))
}

# `stat` returns a named vector and receives unique issue-draw instance IDs so
# repeated bootstrap draws never collapse into a single issue.
boot_family <- function(outcome, method, eligible, stat, label, B = B_VALID) {
  point_rows <- which(eligible)
  point <- stat(analysis_y(outcome, method), point_rows,
                as.character(AN$issue_id[point_rows]))
  if (is.null(names(point))) stop("family statistic must return a named vector")
  infer <- method %in% c("dsl", "original")
  if (!infer) return(list(point = point, se = rep(NA_real_, length(point)),
    low = rep(NA_real_, length(point)), high = rep(NA_real_, length(point)),
    sim_low = rep(NA_real_, length(point)), sim_high = rep(NA_real_, length(point)),
    split_sd = rep(NA_real_, length(point)), failure_rate = NA_real_,
    simultaneous_critical = NA_real_))

  seed0 <- CAN_SEED + strtoi(substr(digest::digest(label, algo = "xxhash32"), 1, 7), 16L)
  # Replicates are independent and every random component receives an explicit
  # seed derived from b. Forking therefore changes wall time only: serial and
  # parallel runs produce the same B rows in the same order. `mc.set.seed` is
  # disabled so the parallel backend cannot add a second RNG stream.
  one_rep <- function(b) {
    q <- if (method == "dsl") phase2_multiplier(seed0 + 100000L + b) else rep(1, nrow(AN))
    dr <- draw_issues(eligible, seed0 + b)
    tryCatch(stat(analysis_y(outcome, method, q), dr$rows, dr$instance),
             error = function(e) rep(NA_real_, length(point)))
  }
  cores <- if (.Platform$OS.type == "windows") 1L else min(VALID_CORES, B)
  rep_list <- if (cores > 1L)
    parallel::mclapply(seq_len(B), one_rep, mc.cores = cores,
                       mc.preschedule = TRUE, mc.set.seed = FALSE) else
    lapply(seq_len(B), one_rep)
  reps <- do.call(rbind, rep_list)
  dimnames(reps) <- list(NULL, names(point))
  ok <- apply(reps, 1, function(z) all(is.finite(z))); failure_rate <- mean(!ok)
  if (failure_rate > .02) warning(label, ": bootstrap failure rate ", failure_rate)
  reps <- reps[ok, , drop = FALSE]; within_se <- apply(reps, 2, sd)
  split_sd <- rep(0, length(point))
  if (method == "dsl") {
    split_points <- sapply(0:9, function(r) {
      yy <- AN[[sprintf("dsl_pseudo_r%02d_%s", r, outcome)]]
      stat(yy, point_rows, as.character(AN$issue_id[point_rows]))
    })
    if (is.null(dim(split_points))) split_points <- matrix(split_points, nrow = length(point))
    split_sd <- apply(split_points, 1, sd)
  }
  total_se <- sqrt(within_se^2 + 1.1 * split_sd^2)
  z <- sweep(sweep(reps, 2, point, "-"), 2, within_se, "/"); z[!is.finite(z)] <- 0
  crit <- unname(quantile(apply(abs(z), 1, max), .95, na.rm = TRUE))
  list(point = point, se = total_se,
       low = point - qnorm(.975) * total_se, high = point + qnorm(.975) * total_se,
       sim_low = point - crit * total_se, sim_high = point + crit * total_se,
       split_sd = split_sd, failure_rate = failure_rate,
       simultaneous_critical = crit)
}

as_rows <- function(x, outcome, method, family) {
  tibble(cell = names(x$point), estimate = as.numeric(x$point),
         std_error = as.numeric(x$se), conf_low = as.numeric(x$low),
         conf_high = as.numeric(x$high), simultaneous_low = as.numeric(x$sim_low),
         simultaneous_high = as.numeric(x$sim_high), split_sd = as.numeric(x$split_sd),
         bootstrap_failure_rate = x$failure_rate,
         simultaneous_critical = x$simultaneous_critical,
         outcome = if (method == "original") "original_nonengagement" else unname(OUTCOME_LABEL[outcome]),
         estimator = method, family = family,
         estimate_pp = pp(estimate), conf_low_pp = pp(conf_low),
         conf_high_pp = pp(conf_high), simultaneous_low_pp = pp(simultaneous_low),
         simultaneous_high_pp = pp(simultaneous_high), canonical_run_id = CANONICAL_RUN_ID)
}

# --- statistics --------------------------------------------------------------
stat_overall <- function(y, rows, instance) setNames(mean(y[rows]), "overall")

stat_language <- function(y, rows, instance) {
  dd <- AN[rows, c("model", "prompt_id", "lang"), drop = FALSE]
  dd$.boot_issue <- instance; dd$y <- y[rows]
  wide <- dd %>% group_by(.boot_issue, model, prompt_id, lang) %>%
    summarise(y = mean(y), .groups = "drop") %>% pivot_wider(names_from = lang, values_from = y)
  v <- sapply(setdiff(LANGS_C, "en"), function(L) {
    z <- wide %>% filter(!is.na(en), !is.na(.data[[L]])) %>%
      mutate(d = .data[[L]] - en) %>% group_by(model) %>% summarise(d = mean(d), .groups = "drop")
    mean(z$d)
  })
  setNames(v, setdiff(LANGS_C, "en"))
}

stat_language_model <- function(y, rows, instance) {
  dd <- AN[rows, c("model", "prompt_id", "lang"), drop = FALSE]
  dd$.boot_issue <- instance; dd$y <- y[rows]
  wide <- dd %>% group_by(.boot_issue, model, prompt_id, lang) %>%
    summarise(y = mean(y), .groups = "drop") %>% pivot_wider(names_from = lang, values_from = y)
  grid <- expand.grid(language = setdiff(LANGS_C, "en"),
                      model = sort(unique(as.character(AN$model))), stringsAsFactors = FALSE)
  v <- mapply(function(L, m) {
    z <- wide %>% filter(model == m, !is.na(en), !is.na(.data[[L]]))
    mean(z[[L]] - z$en)
  }, grid$language, grid$model)
  setNames(v, paste(grid$language, grid$model, sep = "||"))
}

stat_framing <- function(y, rows, instance) {
  dd <- AN[rows, c("model", "tier"), drop = FALSE]; dd$.boot_issue <- instance; dd$y <- y[rows]
  b <- dd %>% group_by(.boot_issue, model, tier) %>%
    summarise(n = n(), value = mean(y), .groups = "drop") %>%
    pivot_wider(names_from = tier, values_from = c(n, value)) %>%
    filter(n_regular == 2, n_boundary == 2) %>% mutate(d = value_boundary - value_regular)
  by_m <- b %>% group_by(model) %>% summarise(d = mean(d), .groups = "drop")
  setNames(c(mean(by_m$d), by_m$d), c("overall", paste0("model||", by_m$model)))
}

stat_home_model <- function(y, rows, instance) {
  dd <- AN[rows, c("model", "home_status"), drop = FALSE]; dd$y <- y[rows]
  z <- dd %>% filter(home_status %in% c("home", "away")) %>%
    group_by(model, home_status) %>% summarise(rate = mean(y), .groups = "drop") %>%
    pivot_wider(names_from = home_status, values_from = rate) %>% mutate(d = home - away)
  setNames(z$d, as.character(z$model))
}

stat_model_language <- function(y, rows, instance) {
  dd <- AN[rows, c("model", "lang"), drop = FALSE]; dd$y <- y[rows]
  z <- dd %>% group_by(model, lang) %>% summarise(rate = mean(y), .groups = "drop")
  grid <- expand.grid(model = sort(unique(as.character(AN$model))), lang = LANGS_C,
                      stringsAsFactors = FALSE)
  z <- grid %>% left_join(z %>% mutate(model = as.character(model), lang = as.character(lang)),
                          by = c("model", "lang"))
  setNames(z$rate, paste(z$model, z$lang, sep = "||"))
}

# Linear-probability estimating equation for rectified pseudo-outcomes:
# X'(Y_tilde-X beta)-lambda P beta=0. Pseudo-outcomes may be outside [0,1], so
# treating them as binomial data is invalid. The direct risk-difference scale is
# also the paper's target. The fixed 1e-8 ridge is numerical only.
moment_fit <- function(X, y, lambda = 1e-8) {
  pen <- diag(c(0, rep(1, ncol(X) - 1)))
  b <- tryCatch(solve(crossprod(X) + lambda * pen, crossprod(X, y)),
                error = function(e) NULL)
  if (is.null(b) || any(!is.finite(b))) NULL else drop(b)
}

stat_home_standardized <- function(y, rows, instance) {
  dd <- AN[rows, , drop = FALSE]; dd$.boot_issue <- instance; dd$y <- y[rows]
  v <- sapply(JURIS_C, function(j) {
    z <- dd %>% filter(lang == "en", juris == j, home_status %in% c("home", "away")) %>% droplevels()
    if (!nrow(z) || n_distinct(z$home) < 2) return(NA_real_)
    rhs <- if (nlevels(droplevels(z$model_f)) > 1) "home * model_f" else "home"
    for (v0 in c("tier", "domain", "route_f"))
      if (nlevels(droplevels(z[[v0]])) > 1) rhs <- paste(rhs, v0, sep = " + ")
    f <- as.formula(paste("~", rhs))
    X <- model.matrix(f, z); b <- moment_fit(X, z$y); if (is.null(b)) return(NA_real_)
    z1 <- z; z0 <- z; z1$home <- 1L; z0$home <- 0L
    w <- w_nested(z, issue_col = ".boot_issue")
    sum(w * drop((model.matrix(f, z1) - model.matrix(f, z0)) %*% b))
  })
  setNames(v, JURIS_C)
}

# --- estimate families -------------------------------------------------------
cat("\nSol DSL v1.1 response-validity families\n")
ROWS23 <- ROWS24 <- ROWS25 <- ROWS26 <- ROWS27 <- ROWS28 <- ROWS29 <- list()
eligible_all <- rep(TRUE, nrow(AN)); eligible_en <- AN$lang == "en"
eligible_en_ha <- eligible_en & AN$home_status %in% c("home", "away")

for (outcome in OUTCOMES) for (method in METHODS) {
  tag <- paste(outcome, method, sep = "|")
  ROWS23[[tag]] <- as_rows(boot_family(outcome, method, eligible_all, stat_overall,
    paste0("c23|", tag)), outcome, method, "overall prevalence")
  ROWS24[[tag]] <- as_rows(boot_family(outcome, method, eligible_all, stat_language,
    paste0("c24|", tag)), outcome, method, "paired language")
  ROWS25[[tag]] <- as_rows(boot_family(outcome, method, eligible_en_ha, stat_home_standardized,
    paste0("c25|", tag)), outcome, method, "standardized home")
  ROWS26[[tag]] <- as_rows(boot_family(outcome, method, eligible_all, stat_model_language,
    paste0("c26|", tag)), outcome, method, "model-language prevalence")
  ROWS27[[tag]] <- as_rows(boot_family(outcome, method, eligible_en, stat_framing,
    paste0("c27|", tag)), outcome, method, "paired framing")
  ROWS28[[tag]] <- as_rows(boot_family(outcome, method, eligible_en_ha, stat_home_model,
    paste0("c28|", tag)), outcome, method, "home by model")
  ROWS29[[tag]] <- as_rows(boot_family(outcome, method, eligible_all, stat_language_model,
    paste0("c29|", tag)), outcome, method, "language by model")
}

STAT_MAP <- list(`23`=stat_overall, `24`=stat_language, `25`=stat_home_standardized,
                 `26`=stat_model_language, `27`=stat_framing,
                 `28`=stat_home_model, `29`=stat_language_model)
ELIG_MAP <- list(`23`=eligible_all, `24`=eligible_all, `25`=eligible_en_ha,
                 `26`=eligible_all, `27`=eligible_en,
                 `28`=eligible_en_ha, `29`=eligible_all)
for (nm in names(STAT_MAP)) {
  x <- as_rows(boot_family(OUTCOMES[1], "original", ELIG_MAP[[nm]], STAT_MAP[[nm]],
                           paste0("c", nm, "|original")),
               OUTCOMES[1], "original", paste0("original family c", nm))
  obj <- get(paste0("ROWS", nm)); obj[["original"]] <- x; assign(paste0("ROWS", nm), obj)
}

COMMON_NOTE <- paste("GPT-5.6 Sol DSL v1.1 is a machine reference, not human ground truth;",
  "DSL is rectified for the known two-phase label design; original code 4/5 is judge-coded non-engagement")
DSL_INF_NOTE <- "issue-cluster + Rao-Wu SRSWOR phase-two bootstrap; ten-split variance; max-t family band"
ORIG_INF_NOTE <- "issue-cluster bootstrap; max-t family band"
inference_note <- function(estimator) case_when(
  estimator == "dsl" ~ DSL_INF_NOTE,
  estimator == "original" ~ ORIG_INF_NOTE,
  TRUE ~ "diagnostic point only; no confidence interval")

c23 <- bind_rows(ROWS23) %>% mutate(estimand = "delivered-response population prevalence",
  weighting = "equal response", inference = inference_note(estimator), human_validated = FALSE,
  measurement_note = COMMON_NOTE)
write_csv(c23, file.path(CAN_EST, "c23_response_validity_prevalence.csv"))

c24 <- bind_rows(ROWS24) %>% rename(language = cell) %>% mutate(
  estimand = "within-model prompt-paired target-language minus English difference; models weighted equally",
  identification = paste("causal language contrast under translation equivalence, no interference,",
                         "and a stable response-generation regime"),
  inference = inference_note(estimator), measurement_note = COMMON_NOTE)
write_csv(c24, file.path(CAN_EST, "c24_language_response_validity.csv"))

c25 <- bind_rows(ROWS25) %>% rename(jurisdiction = cell) %>% mutate(
  specification = paste0("linear-probability estimating equation: X'(Y_tilde-X beta)-1e-8 P beta=0; ",
                         "X=home*model+tier+domain+route; per jurisdiction; g-computation"),
  weighting = "equal model -> equal issue -> equal prompt",
  interpretation = "covariate-standardized association; NOT causal",
  inference = inference_note(estimator), measurement_note = COMMON_NOTE)
write_csv(c25, file.path(CAN_EST, "c25_home_response_validity_sensitivity.csv"))

c26 <- bind_rows(ROWS26) %>% separate(cell, into = c("model", "lang"), sep = "\\|\\|") %>%
  mutate(estimand = "unpaired delivered-response model-language prevalence",
         interpretation = "descriptive competence/measurement diagnostic; not a language effect",
         measurement_note = COMMON_NOTE)
write_csv(c26, file.path(CAN_EST, "c26_model_language_competence.csv"))

c27 <- bind_rows(ROWS27) %>% mutate(scope = if_else(cell == "overall", "overall", "model"),
  group = sub("^model\\|\\|", "", cell),
  estimand = "paired boundary-minus-regular difference in complete 2+2 English issue-model blocks",
  interpretation = "prompt-framing contrast; correction does not strengthen assignment assumptions",
  measurement_note = COMMON_NOTE)
write_csv(c27, file.path(CAN_EST, "c27_framing_response_validity.csv"))

c28 <- bind_rows(ROWS28) %>% rename(model = cell) %>% mutate(
  estimand = "unadjusted English home-minus-away rate difference within model",
  interpretation = "descriptive; NOT causal", measurement_note = COMMON_NOTE)
write_csv(c28, file.path(CAN_EST, "c28_home_by_model_response_validity.csv"))

c29 <- bind_rows(ROWS29) %>% separate(cell, into = c("language", "model"), sep = "\\|\\|") %>%
  mutate(estimand = "within-model prompt-paired target-language minus English difference",
         evidence_status = "exploratory heterogeneity; simultaneous band covers model-language cells within outcome",
         measurement_note = COMMON_NOTE)
write_csv(c29, file.path(CAN_EST, "c29_language_by_model_response_validity.csv"))

diag <- arrow::read_csv_arrow(file.path(DSL_DIR, "dsl_crossfit_diagnostics.csv")) %>% as_tibble()
c30 <- bind_rows(
  tibble(metric = c("population_rows", "reference_rows", "phase2_control_strata",
                    "noncensus_singleton_strata", "crossfit_repeats", "crossfit_folds",
                    "augmentation_cost_usd", "cumulative_cost_usd", "reasoning_tokens"),
         value = c(nrow(AN), sum(AN$reference_observed), length(CTL_GROUPS), 0, 10, 5,
                   manifest$completion$augmentation_incremental_provider_cost,
                   manifest$completion$cumulative_incremental_provider_cost,
                   manifest$completion$reasoning_tokens)),
  diag %>% group_by(outcome) %>% summarise(weighted_brier_mean = mean(weighted_brier),
    weighted_brier_max = max(weighted_brier), weighted_log_loss_mean = mean(weighted_log_loss),
    weighted_log_loss_max = max(weighted_log_loss), .groups = "drop") %>%
    pivot_longer(-outcome, names_to = "metric", values_to = "value") %>%
    mutate(metric = paste(outcome, metric, sep = "|")) %>% select(metric, value)) %>%
  mutate(canonical_run_id = CANONICAL_RUN_ID)
write_csv(c30, file.path(CAN_EST, "c30_response_validity_inference_diagnostics.csv"))

flush_diag()
cat(sprintf("c23-c30 written from Sol DSL v1.1: %d reference / %d population rows\n",
            sum(AN$reference_observed), nrow(AN)))
