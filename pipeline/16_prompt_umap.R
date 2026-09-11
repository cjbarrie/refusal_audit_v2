# =============================================================================
# Technical reference: docs/r_pipeline/16_prompt_umap.md
# FIXED PROMPT-SEMANTIC UMAP -- v2.4 refusal and capability outcomes
# =============================================================================
# Fit one two-dimensional geometry to the 2,496 cached English prompt
# embeddings. Every language/model panel reuses these coordinates. Outcomes
# colour the map but never enter the UMAP fit. This is exploratory description,
# not clustering evidence or a causal estimand. No API call is made.

source("pipeline/10_canonical_common.R")
suppressPackageStartupMessages(library(tidyverse))

EMB_PATH <- Sys.getenv("CANON_EMBEDDINGS", "data/prompt_embeddings_en.csv.gz")
EMB_META <- sub("[.]csv[.]gz$", ".json", EMB_PATH)
UMAP_SEED <- as.integer(Sys.getenv("CANON_UMAP_SEED", "20260809"))
N_NEIGHBORS <- as.integer(Sys.getenv("CANON_UMAP_NN", "25"))
MIN_DIST <- as.numeric(Sys.getenv("CANON_UMAP_MINDIST", "0.15"))

if (!file.exists(EMB_PATH) || !requireNamespace("uwot", quietly = TRUE)) {
  cat("SKIP: cached embeddings or uwot unavailable; no coordinates written\n")
  quit(save = "no", status = 0)
}

E <- read_csv(EMB_PATH, show_col_types = FALSE)
stopifnot("prompt_id" %in% names(E), !anyDuplicated(E$prompt_id))
X <- as.matrix(E[, setdiff(names(E), "prompt_id"), drop = FALSE])
rownames(X) <- E$prompt_id
stopifnot(ncol(X) == 512L, is.numeric(X), all(is.finite(X)))
prompt_meta <- canon |> distinct(prompt_id, issue_id, tier, domain,
                                 region_focus, route, prompt_origin_language)
stopifnot(nrow(prompt_meta) == 2496L,
          setequal(prompt_meta$prompt_id, rownames(X)))
X <- X[prompt_meta$prompt_id, , drop = FALSE]
embedding_norm <- sqrt(rowSums(X^2))
stopifnot(all(is.finite(embedding_norm)), all(embedding_norm > 0))
X <- X / embedding_norm

set.seed(UMAP_SEED)
fit <- uwot::umap(X, n_neighbors = N_NEIGHBORS, min_dist = MIN_DIST,
                  metric = "cosine", n_components = 2, verbose = FALSE)
coords <- prompt_meta |>
  mutate(umap_x = fit[, 1], umap_y = fit[, 2])

# Equal jurisdiction, then equal model within jurisdiction. This prevents the
# four US models from receiving four times the aggregate influence of a
# jurisdiction represented by one model.
propensity <- canon |>
  select(prompt_id, language = lang, juris, model,
         genuine_refusal, capability_failure) |>
  pivot_longer(c(genuine_refusal, capability_failure),
               names_to = "outcome", values_to = "event") |>
  group_by(prompt_id, language, outcome, juris, model) |>
  summarise(model_mean = mean(event), .groups = "drop") |>
  group_by(prompt_id, language, outcome, juris) |>
  summarise(jurisdiction_mean = mean(model_mean), n_models = n(), .groups = "drop") |>
  group_by(prompt_id, language, outcome) |>
  summarise(propensity = mean(jurisdiction_mean),
            n_jurisdictions = n(), n_models = sum(n_models), .groups = "drop")

overall <- propensity |> group_by(prompt_id, outcome) |>
  summarise(propensity = mean(propensity), n_languages = n(), .groups = "drop") |>
  mutate(language = "ALL", n_jurisdictions = NA_integer_, n_models = NA_integer_)
propensity <- bind_rows(propensity, overall) |> mutate(
  estimand = paste("descriptive prompt propensity; jurisdictions equally weighted,",
                   "models equally weighted within jurisdiction; ALL also gives",
                   "languages equal weight"),
  canonical_run_id = CANONICAL_RUN_ID)
stopifnot(all(propensity$propensity >= 0 & propensity$propensity <= 1))

# Wide language columns make the coordinate table directly useful to plotting
# and the local explorer while the long table remains the tidy authority.
wide <- propensity |> filter(outcome %in% c("genuine_refusal", "capability_failure"),
                             language != "ALL") |>
  select(prompt_id, outcome, language, propensity) |>
  unite(name, outcome, language) |> pivot_wider(names_from = name,
                                                values_from = propensity)
coords <- coords |> left_join(wide, by = "prompt_id")

by_model <- canon |> filter(lang == "en") |>
  select(prompt_id, model, genuine_refusal, capability_failure) |>
  mutate(canonical_run_id = CANONICAL_RUN_ID)

# Number of English-evaluated models exhibiting each outcome for each prompt.
# Missing response cells reduce n_models_observed rather than being treated as
# a zero outcome.
cross_model <- by_model |>
  select(-canonical_run_id) |>
  pivot_longer(c(genuine_refusal, capability_failure),
               names_to = "outcome", values_to = "event") |>
  group_by(prompt_id, outcome) |>
  summarise(n_models_observed = n(), n_models_event = sum(event),
            share_models_event = mean(event), .groups = "drop") |>
  mutate(share_models_event_pp = pp(share_models_event),
         sample = "English responses; prompt fixed across observed models",
         canonical_run_id = CANONICAL_RUN_ID)
cross_model_distribution <- cross_model |>
  count(outcome, n_models_event, name = "n_prompts") |>
  group_by(outcome) |>
  mutate(share_prompts = n_prompts / sum(n_prompts),
         share_prompts_pp = pp(share_prompts)) |>
  ungroup() |>
  mutate(sample = "English responses; prompt fixed across observed models",
         canonical_run_id = CANONICAL_RUN_ID)

# Rank prompts by the equal-jurisdiction/equal-model/equal-language propensity
# already defined above. This supports concentration curves without requiring a
# plotting script to compute or redefine a statistical quantity.
concentration <- propensity |>
  filter(language == "ALL",
         outcome %in% c("genuine_refusal", "capability_failure")) |>
  group_by(outcome) |>
  arrange(desc(propensity), prompt_id, .by_group = TRUE) |>
  mutate(rank = row_number(), n_prompts = n(),
         cumulative_prompt_share = rank / n_prompts,
         cumulative_outcome_share = cumsum(propensity) / sum(propensity),
         cumulative_prompt_share_pp = pp(cumulative_prompt_share),
         cumulative_outcome_share_pp = pp(cumulative_outcome_share)) |>
  ungroup() |>
  select(prompt_id, outcome, propensity, rank, n_prompts,
         cumulative_prompt_share, cumulative_outcome_share,
         cumulative_prompt_share_pp, cumulative_outcome_share_pp,
         canonical_run_id)

diag <- tibble(
  n_prompts = nrow(coords), embedding_dimensions = ncol(X),
  n_neighbors = N_NEIGHBORS, min_dist = MIN_DIST, metric = "cosine",
  seed = UMAP_SEED,
  geometry_note = "one English-prompt geometry; outcomes do not enter the fit",
  interpretation = "exploratory locator only; distances and clusters are not estimands",
  canonical_run_id = CANONICAL_RUN_ID)

write_csv(coords, file.path(CAN_EST, "c22_prompt_umap_coordinates.csv"))
write_csv(propensity, file.path(CAN_EST, "c22_prompt_outcome_propensities.csv"))
write_csv(by_model, file.path(CAN_EST, "c22_prompt_outcomes_by_model.csv"))
write_csv(concentration, file.path(CAN_EST, "c22b_prompt_concentration.csv"))
write_csv(cross_model, file.path(CAN_EST, "c22c_prompt_cross_model_counts.csv"))
write_csv(cross_model_distribution,
          file.path(CAN_EST, "c22d_prompt_cross_model_distribution.csv"))
write_csv(diag, file.path(CAN_EST, "c22_prompt_umap_diagnostics.csv"))
jsonlite::write_json(list(
  embeddings = EMB_PATH, embedding_metadata = EMB_META,
  embedding_sha256 = digest::digest(EMB_PATH, "sha256", file = TRUE),
  n_prompts = nrow(coords), seed = UMAP_SEED, n_neighbors = N_NEIGHBORS,
  min_dist = MIN_DIST, metric = "cosine",
  original_response_validity_sha256 = RV_EXPECTED_SHA256,
  analysis_rows = nrow(canon), analysis_models = n_distinct(canon$model),
  canonical_run_id = CANONICAL_RUN_ID),
  file.path(CAN_EST, "c22_prompt_umap_metadata.json"), auto_unbox = TRUE, pretty = TRUE)
cat(sprintf("wrote one fixed geometry for %d prompts\n", nrow(coords)))
