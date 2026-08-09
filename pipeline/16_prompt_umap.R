# =============================================================================
# CANONICAL PART 6 -- prompt-semantic geometry   -> c22
# =============================================================================
# THE QUESTION. Not "do the prompts form clusters" -- a projection will always
# show clusters and they mean very little. The question is: WHICH REGIONS OF
# PROMPT-MEANING SPACE ATTRACT REFUSAL, and does that pattern move with the
# language the prompt is delivered in?
#
# ONE GEOMETRY, REUSED EVERYWHERE. Exactly one 2-D coordinate pair is fitted,
# per prompt, on the English prompt text. Every panel of every figure reuses
# those coordinates. Fitting a separate UMAP per language or per model would
# produce maps whose axes mean different things, so a point that "moves" between
# panels would be an artefact of the fit rather than a finding; separately
# fitted embeddings are not comparable and are never produced here.
#
# THE UNIT IS THE PROMPT, NOT THE RESPONSE. Colour is a refusal PROPENSITY
# across models, not a binary "was this ever refused": a prompt refused by one
# of eleven models must not look like a prompt refused by all eleven.
#
# EXPLORATORY AND DESCRIPTIVE. It establishes no causal effect and validates no
# topic taxonomy. The diagnostics below exist so a reader can see how much of
# the visible structure is real before reading anything into it.
#
# NO API CALLS HERE. Embeddings are cached by scripts/embed_prompts.py; if the
# cache is absent this script SKIPS cleanly so a release still builds.

source("pipeline/10_canonical_common.R")
cat(strrep("=", 78), "\nCANONICAL PART 6: PROMPT-SEMANTIC GEOMETRY\n",
    strrep("=", 78), "\n", sep = "")

EMB_PATH  <- Sys.getenv("CANON_EMBEDDINGS", "data/prompt_embeddings_en.csv.gz")
EMB_META  <- sub("[.]csv[.]gz$", ".json", EMB_PATH)
UMAP_SEED <- as.integer(Sys.getenv("CANON_UMAP_SEED", "20260809"))
N_NEIGHBORS <- as.integer(Sys.getenv("CANON_UMAP_NN", "25"))
MIN_DIST    <- as.numeric(Sys.getenv("CANON_UMAP_MINDIST", "0.15"))
METRIC      <- "cosine"

if (!file.exists(EMB_PATH) || !requireNamespace("uwot", quietly = TRUE)) {
  cat("SKIP: embeddings cache or uwot unavailable.\n",
      "  cache: ", EMB_PATH, " exists=", file.exists(EMB_PATH), "\n",
      "  uwot : ", requireNamespace("uwot", quietly = TRUE), "\n",
      "  Build the cache with:  python scripts/embed_prompts.py\n", sep = "")
  quit(save = "no", status = 0)
}

# =============================================================================
# A. Embeddings
# =============================================================================
E <- suppressMessages(readr::read_csv(EMB_PATH, show_col_types = FALSE))
stopifnot("prompt_id" %in% names(E))
X <- as.matrix(E[, setdiff(names(E), "prompt_id"), drop = FALSE])
rownames(X) <- E$prompt_id
cat(sprintf("embeddings: %d prompts x %d dims\n", nrow(X), ncol(X)))

# Prompts in the analysis sample but missing an embedding, and vice versa. Both
# are reported rather than silently inner-joined away.
prompt_meta <- canon %>%
  distinct(prompt_id, issue_id, tier, domain, region_focus, route) %>%
  mutate(prompt_id = as.character(prompt_id))
missing_emb <- setdiff(prompt_meta$prompt_id, rownames(X))
extra_emb   <- setdiff(rownames(X), prompt_meta$prompt_id)
cat(sprintf("  prompts in canon without an embedding: %d | embeddings not in canon: %d\n",
            length(missing_emb), length(extra_emb)))

keep <- intersect(rownames(X), prompt_meta$prompt_id)
X <- X[keep, , drop = FALSE]

# Near-duplicate detection on the embedding itself: cosine >= 0.995 to some
# other prompt. Reported because a tight duplicate cluster is a feature of the
# generator, not of the issue space.
Xn <- X / sqrt(rowSums(X^2))
near_dup <- local({
  S <- Xn %*% t(Xn); diag(S) <- 0
  sum(apply(S, 1, max) >= 0.995)
})
cat(sprintf("  near-duplicate prompts (cosine >= 0.995): %d\n", near_dup))

# =============================================================================
# B. ONE fixed geometry
# =============================================================================
set.seed(UMAP_SEED)
fit <- uwot::umap(Xn, n_neighbors = N_NEIGHBORS, min_dist = MIN_DIST,
                  metric = METRIC, n_components = 2, ret_nn = TRUE,
                  verbose = FALSE)
UM <- fit$embedding
rownames(UM) <- rownames(Xn)
cat(sprintf("umap: n_neighbors=%d min_dist=%.2f metric=%s seed=%d\n",
            N_NEIGHBORS, MIN_DIST, METRIC, UMAP_SEED))

# =============================================================================
# C. Refusal propensity per prompt x language
# =============================================================================
# EQUAL WEIGHT PER MODEL, then equal weight per jurisdiction within the prompt.
# A plain response mean would let the US arm (four models) speak twice as loudly
# as the CN arm (two), so a "high refusal" region could just be a region the
# larger arm happens to dislike.
prop_by_lang <- canon %>%
  filter(prompt_id %in% keep) %>%
  group_by(prompt_id, language = as.character(lang), juris = as.character(juris),
           model) %>%
  summarise(y = mean(refused_strict), .groups = "drop") %>%
  group_by(prompt_id, language, juris) %>%
  summarise(juris_mean = mean(y), n_models = n(), .groups = "drop") %>%
  group_by(prompt_id, language) %>%
  summarise(refusal_propensity = mean(juris_mean),
            n_jurisdictions = n(), n_models = sum(n_models), .groups = "drop")

# Numerator / denominator kept alongside the weighted quantity: the weighted
# propensity is not a count, and a reader checking it needs the raw counts.
raw_counts <- canon %>%
  filter(prompt_id %in% keep) %>%
  group_by(prompt_id, language = as.character(lang)) %>%
  summarise(n_responses = n(), n_refusals = sum(refused_strict), .groups = "drop")

prop_by_lang <- prop_by_lang %>% left_join(raw_counts, by = c("prompt_id", "language"))

# The overall propensity gives every LANGUAGE equal weight, so a prompt is not
# scored mostly by the languages that happened to have more coverage.
prop_overall <- prop_by_lang %>%
  group_by(prompt_id) %>%
  summarise(refusal_propensity = mean(refusal_propensity),
            n_languages = n(),
            n_responses = sum(n_responses), n_refusals = sum(n_refusals),
            .groups = "drop") %>%
  mutate(language = "ALL")

PROP <- bind_rows(prop_overall, prop_by_lang) %>%
  mutate(estimand = paste("refusal propensity for this prompt in this language:",
                          "share of models refusing, equal weight per",
                          "jurisdiction with models nested equally within it"),
         quantity = "refusal_propensity",
         conditional = "unconditional; every delivered response counts",
         support_ok = n_responses > 0,
         weighting = paste("equal weight per jurisdiction, models nested",
                           "equally within jurisdiction; 'ALL' additionally",
                           "gives every language equal weight"),
         canonical_run_id = CANONICAL_RUN_ID)
stopifnot(all(PROP$refusal_propensity >= 0 & PROP$refusal_propensity <= 1,
              na.rm = TRUE))

# Per-model indicators, for the optional model-faceted figure.
prop_by_model <- canon %>%
  filter(prompt_id %in% keep, lang == "en") %>%
  group_by(prompt_id, model) %>%
  summarise(refused = mean(refused_strict), .groups = "drop")

# =============================================================================
# D. Coordinates table
# =============================================================================
COORD <- tibble(prompt_id = rownames(UM), umap_x = UM[, 1], umap_y = UM[, 2]) %>%
  left_join(prompt_meta, by = "prompt_id") %>%
  left_join(prop_overall %>% select(prompt_id, refusal_propensity_all = refusal_propensity),
            by = "prompt_id") %>%
  left_join(prop_by_lang %>%
              select(prompt_id, language, refusal_propensity) %>%
              pivot_wider(names_from = language, values_from = refusal_propensity,
                          names_prefix = "refusal_"),
            by = "prompt_id")

# --- between-language and between-model disagreement -------------------------
lang_spread <- prop_by_lang %>% group_by(prompt_id) %>%
  summarise(lang_range = diff(range(refusal_propensity)), .groups = "drop")
model_spread <- prop_by_model %>% group_by(prompt_id) %>%
  summarise(model_range = diff(range(refused)),
            model_sd = sd(refused), .groups = "drop")
COORD <- COORD %>% left_join(lang_spread, by = "prompt_id") %>%
  left_join(model_spread, by = "prompt_id")

# --- local neighbourhood diagnostics -----------------------------------------
# Computed in the EMBEDDING space, not the 2-D projection: the projection is
# what is being assessed, so using it to assess itself would be circular.
NN <- fit$nn[[1]]$idx
knn_mean <- function(v) vapply(seq_len(nrow(NN)),
  function(i) mean(v[NN[i, -1]], na.rm = TRUE), numeric(1))
COORD$local_refusal <- knn_mean(COORD$refusal_propensity_all[
  match(rownames(UM), COORD$prompt_id)])
COORD$local_lang_range  <- knn_mean(COORD$lang_range)
COORD$local_model_range <- knn_mean(COORD$model_range)

# =============================================================================
# E. Diagnostics -- run BEFORE any semantic claim is made
# =============================================================================
cat("\nE. diagnostics\n")

# 1. Neighbourhood preservation (trustworthiness-style): the share of each
#    point's k nearest neighbours in the EMBEDDING that are still among its k
#    nearest neighbours in the 2-D map.
knn_idx <- function(M, k, cosine = FALSE) {
  if (cosine) { M <- M / sqrt(rowSums(M^2)); D <- 1 - M %*% t(M) }
  else D <- as.matrix(stats::dist(M))
  diag(D) <- Inf
  t(apply(D, 1, function(r) order(r)[seq_len(k)]))
}
K <- 15L
nn_hi <- NN[, 2:(K + 1), drop = FALSE]
nn_lo <- knn_idx(UM, K)
preservation <- mean(vapply(seq_len(nrow(UM)),
  function(i) length(intersect(nn_hi[i, ], nn_lo[i, ])) / K, numeric(1)))
cat(sprintf("  neighbourhood preservation @k=%d: %.3f\n", K, preservation))

# 2. Does visible structure track the known topic labels? Reported as the share
#    of a point's 2-D neighbours sharing its topic domain, against the rate
#    expected if labels were shuffled. A projection that scores at baseline is
#    not recovering the taxonomy.
dom <- COORD$domain[match(rownames(UM), COORD$prompt_id)]
purity <- mean(vapply(seq_len(nrow(UM)),
  function(i) mean(dom[nn_lo[i, ]] == dom[i], na.rm = TRUE), numeric(1)))
set.seed(UMAP_SEED)
purity_base <- mean(replicate(20, {
  s <- sample(dom)
  mean(vapply(seq_len(nrow(UM)),
    function(i) mean(s[nn_lo[i, ]] == s[i], na.rm = TRUE), numeric(1)))
}))
cat(sprintf("  topic-domain neighbourhood purity: %.3f (shuffled baseline %.3f)\n",
            purity, purity_base))

# 3. Hyper-parameter sensitivity: a small grid, scored on preservation.
grid <- expand.grid(n_neighbors = c(10L, 25L, 50L), min_dist = c(0.05, 0.15, 0.40))
sens <- map_dfr(seq_len(nrow(grid)), function(i) {
  set.seed(UMAP_SEED)
  u <- uwot::umap(Xn, n_neighbors = grid$n_neighbors[i], min_dist = grid$min_dist[i],
                  metric = METRIC, n_components = 2, verbose = FALSE)
  lo <- knn_idx(u, K)
  tibble(n_neighbors = grid$n_neighbors[i], min_dist = grid$min_dist[i],
         preservation = mean(vapply(seq_len(nrow(u)),
           function(j) length(intersect(nn_hi[j, ], lo[j, ])) / K, numeric(1))))
})
cat("  hyper-parameter grid (neighbourhood preservation):\n")
print(as.data.frame(sens), row.names = FALSE, digits = 3)

# 4. Seed stability, after Procrustes alignment. UMAP is stochastic; if the
#    layout moves a lot between seeds, nothing about a point's POSITION should
#    be read, only its neighbourhood.
procrustes_rmse <- function(A, B) {
  A <- scale(A, scale = FALSE); B <- scale(B, scale = FALSE)
  s <- svd(t(A) %*% B); R <- s$v %*% t(s$u)
  sqrt(mean((A %*% R - B)^2)) / sqrt(mean(B^2))
}
seeds <- c(UMAP_SEED + 1L, UMAP_SEED + 2L, UMAP_SEED + 3L)
stab <- map_dfr(seeds, function(sd_) {
  set.seed(sd_)
  u <- uwot::umap(Xn, n_neighbors = N_NEIGHBORS, min_dist = MIN_DIST,
                  metric = METRIC, n_components = 2, verbose = FALSE)
  lo <- knn_idx(u, K)
  tibble(seed = sd_,
         procrustes_rmse = procrustes_rmse(u, UM),
         neighbour_overlap = mean(vapply(seq_len(nrow(u)),
           function(j) length(intersect(nn_lo[j, ], lo[j, ])) / K, numeric(1))))
})
cat("  seed stability:\n"); print(as.data.frame(stab), row.names = FALSE, digits = 3)

DIAG <- bind_rows(
  tibble(diagnostic = "neighbourhood_preservation_k15", value = preservation,
         detail = "share of embedding kNN retained in the 2-D map"),
  tibble(diagnostic = "topic_purity_k15", value = purity,
         detail = "share of 2-D neighbours sharing topic_domain"),
  tibble(diagnostic = "topic_purity_shuffled_baseline", value = purity_base,
         detail = "same statistic with topic labels permuted, mean of 20"),
  tibble(diagnostic = "near_duplicate_prompts", value = near_dup,
         detail = "prompts with cosine >= 0.995 to another prompt"),
  tibble(diagnostic = "prompts_missing_embedding", value = length(missing_emb),
         detail = "in canon, absent from the embedding cache"),
  tibble(diagnostic = "embeddings_not_in_canon", value = length(extra_emb),
         detail = "in the cache, absent from canon"),
  sens %>% transmute(diagnostic = sprintf("grid_preservation_nn%d_md%.2f",
                                          n_neighbors, min_dist),
                     value = preservation, detail = "hyper-parameter sensitivity"),
  stab %>% transmute(diagnostic = sprintf("seed_%d_procrustes_rmse", seed),
                     value = procrustes_rmse,
                     detail = "relative RMSE after Procrustes alignment to the canonical fit"),
  stab %>% transmute(diagnostic = sprintf("seed_%d_neighbour_overlap", seed),
                     value = neighbour_overlap,
                     detail = "share of 2-D kNN shared with the canonical fit")) %>%
  mutate(interpretation = paste("EXPLORATORY. The projection establishes no",
                                "causal effect and validates no taxonomy."),
         canonical_run_id = CANONICAL_RUN_ID)

# =============================================================================
# F. Representative regions -- deterministic, not hand-picked
# =============================================================================
# Three criteria, each taking the highest-scoring local neighbourhood that does
# not overlap one already chosen, and then the MEDOID of that neighbourhood as
# the representative. Nothing here is selected by eye.
pick_regions <- function(score, label, n = 3L, min_sep = 8L) {
  ord <- order(score, decreasing = TRUE, na.last = NA)
  chosen <- integer(0)
  for (i in ord) {
    if (length(chosen) >= n) break
    if (length(chosen) &&
        min(sqrt(rowSums((UM[chosen, , drop = FALSE] -
                          matrix(UM[i, ], nrow = length(chosen), ncol = 2,
                                 byrow = TRUE))^2))) < min_sep) next
    chosen <- c(chosen, i)
  }
  map_dfr(chosen, function(i) {
    nb <- c(i, NN[i, -1])
    sub <- UM[nb, , drop = FALSE]
    cen <- colMeans(sub)
    med <- nb[which.min(sqrt(rowSums((sub - matrix(cen, nrow(sub), 2, byrow = TRUE))^2)))]
    tibble(criterion = label, region_rank = which(chosen == i),
           prompt_id = rownames(UM)[med],
           umap_x = UM[med, 1], umap_y = UM[med, 2],
           neighbourhood_size = length(nb), score = score[i])
  })
}
REGIONS <- bind_rows(
  pick_regions(COORD$local_refusal[match(rownames(UM), COORD$prompt_id)],
               "high local refusal"),
  pick_regions(COORD$local_lang_range[match(rownames(UM), COORD$prompt_id)],
               "high between-language disagreement"),
  pick_regions(COORD$local_model_range[match(rownames(UM), COORD$prompt_id)],
               "high between-model disagreement")) %>%
  left_join(COORD %>% select(prompt_id, issue_id, tier, domain, region_focus),
            by = "prompt_id") %>%
  mutate(estimand = paste("deterministically selected representative prompt for",
                          "a local neighbourhood scoring high on the stated",
                          "criterion. DESCRIPTIVE: a locator, not an estimate."),
         quantity = "representative_region_medoid",
         canonical_run_id = CANONICAL_RUN_ID)
COORD$representative_region <- COORD$prompt_id %in% REGIONS$prompt_id

# Canonical prompt text, for the companion table only -- never printed on the
# point cloud.
PTEXT <- local({
  p <- "prompts/sampled/rebalanced_prompts_en_sample.json"
  if (!file.exists(p)) return(NULL)
  j <- jsonlite::fromJSON(p)$prompts
  tibble(prompt_id = j$id, prompt_text = j$text)
})
if (!is.null(PTEXT)) {
  COORD <- COORD %>% left_join(PTEXT, by = "prompt_id")
  REGIONS <- REGIONS %>% left_join(PTEXT, by = "prompt_id")
}

# =============================================================================
# G. Write
# =============================================================================
COORD <- COORD %>% mutate(
  estimand = paste("2-D UMAP coordinates of the English prompt embedding, plus",
                   "that prompt's refusal propensity overall and by language.",
                   "DESCRIPTIVE AND EXPLORATORY: coordinates carry no units,",
                   "distances are not interpretable, and neither establishes an",
                   "effect."),
  quantity = "umap_coordinate_and_refusal_propensity",
  conditional = "unconditional; every delivered response counts",
  umap_seed = UMAP_SEED, umap_n_neighbors = N_NEIGHBORS,
  umap_min_dist = MIN_DIST, umap_metric = METRIC,
  geometry_note = paste("ONE fixed 2-D coordinate per prompt, fitted on the",
                        "English prompt text and reused in every facet of",
                        "every figure. No facet refits the projection."),
  canonical_run_id = CANONICAL_RUN_ID)

write_csv(COORD,   file.path(CAN_EST, "c22_prompt_umap_coordinates.csv"))
write_csv(PROP,    file.path(CAN_EST, "c22_prompt_refusal_propensities.csv"))
write_csv(DIAG,    file.path(CAN_EST, "c22_prompt_umap_diagnostics.csv"))
write_csv(REGIONS, file.path(CAN_EST, "c22_prompt_umap_regions.csv"))
write_csv(prop_by_model %>%
            mutate(estimand = paste("per-prompt English refusal indicator for a",
                                    "single model; BINARY by construction"),
                   quantity = "refused",
                   conditional = "unconditional; English only",
                   canonical_run_id = CANONICAL_RUN_ID),
          file.path(CAN_EST, "c22_prompt_refusal_by_model.csv"))

emb_meta <- if (file.exists(EMB_META))
  jsonlite::fromJSON(EMB_META) else list(note = "embedding sidecar absent")
meta <- list(
  canonical_run_id = CANONICAL_RUN_ID,
  unit = "prompt (one fixed coordinate pair each)",
  n_prompts = nrow(COORD),
  embedding = emb_meta,
  umap = list(implementation = "uwot",
              version = as.character(utils::packageVersion("uwot")),
              seed = UMAP_SEED, n_neighbors = N_NEIGHBORS,
              min_dist = MIN_DIST, metric = METRIC, n_components = 2,
              input = "L2-normalised embedding matrix"),
  refusal_propensity = list(
    weighting = paste("equal per jurisdiction, models nested equally within",
                      "jurisdiction; the ALL row additionally weights every",
                      "language equally"),
    bounded = "[0,1], asserted"),
  diagnostics = list(
    neighbourhood_preservation_k15 = preservation,
    topic_purity_k15 = purity,
    topic_purity_shuffled_baseline = purity_base,
    near_duplicate_prompts = near_dup),
  status = paste("EXPLORATORY AND DESCRIPTIVE. Establishes no causal effect",
                 "and validates no topic taxonomy."),
  r_version = paste(R.version$major, R.version$minor, sep = "."),
  git_sha = tryCatch(system2("git", c("rev-parse", "HEAD"), stdout = TRUE)[1],
                     error = function(e) NA_character_),
  input_hashes = list(
    embeddings = tryCatch(digest::digest(EMB_PATH, algo = "sha256", file = TRUE),
                          error = function(e) NA_character_),
    data_clean = tryCatch(digest::digest("pipeline/data_clean.RData",
                                         algo = "sha256", file = TRUE),
                          error = function(e) NA_character_)),
  generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S"))
writeLines(jsonlite::toJSON(meta, auto_unbox = TRUE, pretty = TRUE, digits = NA),
           file.path(CAN_EST, "c22_prompt_umap_metadata.json"))

cat(sprintf("\nc22: %d coordinates | %d propensity rows | %d diagnostics | %d regions\n",
            nrow(COORD), nrow(PROP), nrow(DIAG), nrow(REGIONS)))
cat("\n", strrep("=", 78), "\nPART 6 DONE\n", strrep("=", 78), "\n", sep = "")
