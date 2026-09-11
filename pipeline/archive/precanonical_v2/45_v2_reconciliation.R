# =============================================================================
# v2 -- RECONCILIATION, PROVENANCE AND ANALYSIS SPECIFICATION
#   -> e40_analysis_sample_reconciliation.csv
#   -> pipeline/estimates/v2_analysis_spec.json          (machine-readable)
#   -> pipeline/estimates/v2_provenance_judges.json      (sidecar)
#   -> pipeline/estimates/v2_provenance_geographic.json  (sidecar)
# =============================================================================
# Reconciles the artifact chain end to end and records provenance HONESTLY.
#
# The governing rule for the sidecars: state what the artifacts actually contain,
# and mark anything asserted at run level (rather than evidenced per row) as
# exactly that. Row-level provenance is NOT fabricated for legacy labels.

source("pipeline/archive/precanonical_v2/40_v2_common.R")
suppressPackageStartupMessages(library(jsonlite))
cat(strrep("=", 78), "\nRECONCILIATION + PROVENANCE + SPEC\n", strrep("=", 78), "\n", sep = "")

read_keys <- function(paths, pred) {
  out <- list()
  for (p in paths) {
    if (!file.exists(p)) next
    ls <- readLines(p, warn = FALSE); ls <- ls[nzchar(ls)]
    for (l in ls) {
      r <- tryCatch(fromJSON(l), error = function(e) NULL)
      if (is.null(r) || !pred(r)) next
      out[[length(out) + 1L]] <- paste(r$prompt_id, r$prompt_language, r$model, sep = "|")
    }
  }
  unique(unlist(out))
}

# --- artifact chain -----------------------------------------------------------
cat("\nreconciling artifact chain (this reads several hundred MB)\n")
resp_files <- list.files(file.path(RUN_DIR, "responses"), "\\.jsonl$", full.names = TRUE)
ann_files  <- list.files(file.path(RUN_DIR, "ann"), "\\.jsonl$", full.names = TRUE)
bnd_files  <- list.files(RUN_DIR, "^annotations_.*_boundary\\.jsonl$", full.names = TRUE)
all_file   <- file.path(RUN_DIR, "annotations_all.jsonl")

R_ok   <- read_keys(resp_files, function(r) is.null(r$error) && !is.null(r$response_text))
R_all  <- read_keys(resp_files, function(r) TRUE)
A_ok   <- read_keys(ann_files,  function(r) is.null(r$error) && !is.null(r$engagement_code))
ALLJ   <- read_keys(all_file,   function(r) !is.null(r$engagement_code))
BND    <- read_keys(bnd_files,  function(r) !is.null(r$engagement_code))
ASSEMBLED <- union(ALLJ, BND)
RDATA <- paste(v2$prompt_id, v2$prompt_language, v2$model, sep = "|")

chain <- tribble(
  ~stage, ~n, ~note,
  "response keys attempted",        length(R_all),  "any row present in responses/",
  "responses successful",           length(R_ok),   "non-error with response_text",
  "generation never succeeded",     length(setdiff(R_all, R_ok)),
  "attempted but no successful response at any point",
  "clean annotations (ann/)",       length(A_ok),   "non-error with engagement_code",
  "assembled: annotations_all",     length(ALLJ),   "regular tier",
  "assembled: boundary files",      length(BND),    "boundary tier",
  "assembled union",                length(ASSEMBLED), "what data_clean is built from",
  "analysis rows (data_clean)",     length(RDATA),  "AUTHORITATIVE ANALYSIS SET",
  "responses not annotated",        length(setdiff(R_ok, A_ok)), "lost between generation and judging",
  "annotated not assembled",        length(setdiff(A_ok, ASSEMBLED)), "lost in assemble (last-wins picked an error row)",
  "assembled not in data_clean",    length(setdiff(ASSEMBLED, RDATA)), "lost in the R loader")
print(as.data.frame(chain), row.names = FALSE)

# --- required assertions ------------------------------------------------------
cat("\nassertions\n")
dupe <- v2 %>% count(model, prompt_id, prompt_language) %>% filter(n > 1) %>% nrow()
gen_in_away <- v2 %>% filter(home_status == "away", region_focus == "General") %>% nrow()
overlap <- v2 %>% filter(home_status %in% c("home", "away")) %>%
  group_by(jurisdiction = as.character(juris), model) %>%
  summarise(n_home = sum(home_status == "home"), n_away = sum(home_status == "away"),
            both = n_home > 0 & n_away > 0, .groups = "drop")
asserts <- tribble(
  ~assertion, ~pass, ~detail,
  "one row per model x prompt_id x language", dupe == 0, sprintf("%d duplicate keys", dupe),
  "General never enters the away reference",  gen_in_away == 0, sprintf("%d General rows coded away", gen_in_away),
  "home/away overlap in every jurisdiction x model", all(overlap$both),
    sprintf("%d of %d cells have both arms", sum(overlap$both), nrow(overlap)))
print(as.data.frame(asserts), row.names = FALSE)

# --- missing cells by model and language --------------------------------------
expected <- v2 %>% distinct(prompt_id, prompt_language) %>% nrow()
missing_cells <- v2 %>% count(model, prompt_language) %>%
  complete(model, prompt_language, fill = list(n = 0L)) %>%
  left_join(v2 %>% count(prompt_language, name = "n_prompts_lang") %>%
              mutate(n_prompts_lang = n_prompts_lang / n_distinct(v2$model)),
            by = "prompt_language") %>%
  mutate(expected_approx = 2496, missing_approx = pmax(0, expected_approx - n))

# --- bootstrap / fit diagnostics ----------------------------------------------
bootf <- file.path(EST, "e39_bootstrap_diagnostics.csv")
boot_summary <- if (file.exists(bootf)) {
  bd <- read_csv(bootf, show_col_types = FALSE)
  tibble(n_bootstraps = nrow(bd),
         total_replicates_successful = sum(bd$replicates_successful),
         total_replicates_failed = sum(bd$replicates_failed),
         max_failure_rate = max(bd$failure_rate),
         all_unit_issue_id = all(bd$bootstrap_unit == "issue_id"),
         min_successful = min(bd$replicates_successful))
} else tibble(n_bootstraps = 0L)
cat("\nbootstrap diagnostics\n"); print(as.data.frame(boot_summary), row.names = FALSE)

# --- e40 ----------------------------------------------------------------------
e40 <- bind_rows(
  chain %>% transmute(section = "artifact_chain", item = stage,
                      value = as.character(n), note),
  asserts %>% transmute(section = "assertion", item = assertion,
                        value = ifelse(pass, "PASS", "FAIL"), note = detail),
  V2_EXCLUSIONS %>% transmute(section = "exclusion",
                              item = paste(prompt_id, prompt_language, model, sep = "|"),
                              value = reason, note = detail),
  tibble(section = "exclusion", item = "generation_never_succeeded_keys",
         value = as.character(length(setdiff(R_all, R_ok))),
         note = paste(head(setdiff(R_all, R_ok), 5), collapse = " ; ")),
  missing_cells %>% filter(missing_approx > 0) %>%
    transmute(section = "missing_cells", item = paste(model, prompt_language),
              value = as.character(missing_approx),
              note = sprintf("observed %d of ~2496", n)),
  overlap %>% transmute(section = "home_away_overlap",
                        item = paste(jurisdiction, model),
                        value = sprintf("home=%d away=%d", n_home, n_away),
                        note = ifelse(both, "both arms present", "MISSING AN ARM")),
  boot_summary %>% pivot_longer(everything(), names_to = "item",
                                values_to = "value", values_transform = as.character) %>%
    mutate(section = "bootstrap_diagnostics", note = "aggregated over e39"))
write_csv(e40, file.path(EST, "e40_analysis_sample_reconciliation.csv"))
cat(sprintf("\nwrote e40: %d rows\n", nrow(e40)))

# --- provenance sidecar: judges ----------------------------------------------
# The canonical outcome labels were produced by Gemini 2.5 Flash-Lite. That is a
# RUN-LEVEL HISTORICAL FACT confirmed by the project owner, not something
# recoverable from most rows: judge identity was only added to the record schema
# on 2026-08-04, so the great majority of rows carry no judge field. Writing a
# judge_model onto those rows would be fabricated provenance and is not done.
jm <- v2 %>% count(judge_model, name = "rows") %>%
  mutate(judge_model = ifelse(is.na(judge_model), NA_character_, judge_model))
jpv <- v2 %>% count(judge_prompt_version, name = "rows")
prov_judges <- list(
  canonical_outcome_labels = list(
    judge = "google/gemini-2.5-flash-lite",
    temperature = 0,
    evidence_level = "RUN-LEVEL HISTORICAL METADATA, confirmed by the project owner",
    caveat = paste("Row-level judge provenance exists only for rows annotated on or",
                   "after 2026-08-04, when judge_model was added to the schema.",
                   "It has NOT been back-filled: doing so would fabricate row-level",
                   "provenance for legacy labels."),
    rows_with_row_level_judge = as.integer(sum(!is.na(v2$judge_model))),
    rows_without_row_level_judge = as.integer(sum(is.na(v2$judge_model))),
    total_rows = nrow(v2)),
  judge_prompt_version_observed = as.list(setNames(jpv$rows,
      ifelse(is.na(jpv$judge_prompt_version), "NA_legacy", jpv$judge_prompt_version))),
  judge_prompt_version_drift_diagnosis = paste(
    "Two distinct judge_prompt_version hashes appear among rows that carry one.",
    "This is IMPLEMENTATION DRIFT, not codebook drift: the version is a hash over",
    "all large triple-quoted blocks in annotation_pipeline.py, so unrelated edits",
    "(added helper docstrings) changed it while the Pass 1-3 codebooks were",
    "untouched. Treat differing hashes here as manifest drift. It is NOT a reason",
    "to re-run paid annotation."),
  additional_judges = list(
    storage = "long form under <run_dir>/panel/<judge>/, separate from the canonical outcome",
    kept_separate = TRUE,
    majority_vote_used = FALSE,
    note = "Every judge is reported separately in e38 with a judge-sensitivity range. No consensus label is treated as ground truth."),
  panel_judge_id_drift = paste(
    "Judge identifiers in panel artifacts are filesystem-safe slugs (slashes ->",
    "'__'), so they differ textually from the model IDs in the panel config.",
    "The mapping is mechanical and reversible. Config/manifest drift only."))
write_json(prov_judges, file.path(EST, "v2_provenance_judges.json"),
           auto_unbox = TRUE, pretty = TRUE)

# --- provenance sidecar: geographic review ------------------------------------
iss <- stream_in(file(file.path("data", "issue_records_rebalanced.jsonl")), verbose = FALSE)
prov_geo <- list(
  claim = list(
    statement = "Issue geographic classifications received manual review.",
    evidence_level = "RUN-LEVEL ASSERTION recorded at the project owner's direction",
    caveat = paste("The issue records carry NO reviewer, review-date or approval",
                   "field, so this cannot be evidenced per row and no such field",
                   "has been invented.")),
  fields_actually_present = list(
    needs_review = as.list(table(iss$needs_review)),
    source_article_status = as.list(table(iss$source_article_status)),
    region = as.list(table(iss$region))),
  reviewer_fields_present = FALSE,
  review_date_fields_present = FALSE,
  note = paste("`needs_review` is TRUE for all", nrow(iss), "issue records, i.e. it",
               "records a review REQUIREMENT rather than a completed review. The",
               "region field is the classification used to derive home status."))
write_json(prov_geo, file.path(EST, "v2_provenance_geographic.json"),
           auto_unbox = TRUE, pretty = TRUE)

# --- machine-readable analysis specification ----------------------------------
file_hash <- function(p) if (file.exists(p)) substr(digest::digest(file = p, algo = "sha256"), 1, 16) else NA_character_
commit <- tryCatch(system("git rev-parse HEAD", intern = TRUE)[1], error = function(e) NA_character_)
spec <- list(
  generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
  code_commit = commit,
  run_dir = RUN_DIR,
  note_on_run_manifest = paste(
    "pilot_config.json is mutable and is NOT used as a run manifest. The",
    "authoritative inputs are the artifacts themselves, hashed below."),
  source_artifact_hashes = list(
    data_clean_RData = file_hash("pipeline/data_clean.RData"),
    annotations_all = file_hash(all_file),
    issue_records_rebalanced = file_hash("data/issue_records_rebalanced.jsonl"),
    response_lengths_cache = file_hash("pipeline/response_lengths.csv")),
  analysis_sample = list(
    rows = nrow(v2), issues = n_distinct(v2$issue_id),
    models = n_distinct(v2$model), languages = LANGS_V2,
    unit = "one model response to one prompt in one language"),
  outcome_definitions = list(
    primary = "refused_strict = engagement_code >= 4",
    sensitivity_any = "refused_any = engagement_code >= 3",
    three_category = "1-2 engaged | 3 partial | 4-5 refusal",
    ordinal = "engagement_code 1-5",
    code3_rule = "never silently relabelled; appears in all three representations"),
  estimand_families = list(
    A = list(label = "descriptive home results", model = "none (counts and weighted means)",
             causal = FALSE, general_handling = "reported separately, never in the away reference",
             outputs = "e32"),
    B = list(label = "covariate-standardized home-region contrast",
             formula = "refused ~ home + tier + domain + route + model (per jurisdiction)",
             region_fixed_effects = "EXCLUDED: region deterministically defines home within jurisdiction",
             language = "English only; the specification carries no language term",
             sample = "home vs away; General excluded",
             standardization_primary = "equal weight per tested model and issue",
             standardization_sensitivity = "empirical response weighting",
             contrast = "mean[P(Y=1|home=1,X) - P(Y=1|home=0,X)] on the probability scale",
             hierarchical_sensitivity = "refused ~ ... + (1|issue_id) + (1|prompt_id) with POPULATION-LEVEL (marginal) predictions; fitted BLUPs are NOT held fixed while toggling home",
             causal = FALSE,
             prohibited_descriptions = c("causal", "difference-in-differences", "DiD", "within-issue"),
             outputs = c("e33", "e34", "e35")),
    C = list(label = "prompt-fixed language effect",
             block = "block_id = model x prompt_id",
             estimator = "mean(Y[block,language] - Y[block,English]) over complete blocks",
             equivalent = "LPM with block fixed effects (algebraically identical for 2-observation blocks)",
             secondary = c("conditional logistic", "GLMM"),
             interpretation = paste("effect of delivering the tested translated prompt version,",
                                    "among the tested prompt/model set; conditional on translation",
                                    "equivalence and no run-order or provider confounding"),
             causal = FALSE, outputs = c("e36", "e37"))),
  weighting = list(response = "every response counts once",
                   equal_model = "every model contributes equally within the group",
                   equal_model_issue = "every (model, issue) cell contributes equally (Family B primary)"),
  uncertainty = list(
    outer_bootstrap_unit = "issue_id",
    seed = V2_SEED,
    refit_inside_replicate = TRUE,
    restandardize_inside_replicate = TRUE,
    interval = "percentile (2.5%, 97.5%)",
    fixed_coefficient_simulation_used_as_primary = FALSE,
    diagnostics = "e39"),
  exclusions = list(
    recorded = as.list(split(V2_EXCLUSIONS, seq_len(nrow(V2_EXCLUSIONS)))),
    generation_never_succeeded_keys = length(setdiff(R_all, R_ok))),
  annotation_error_layer = V2_ANNOTATION_ERROR_LAYER,
  judges = list(canonical = "google/gemini-2.5-flash-lite",
                additional_reported_separately = TRUE,
                majority_vote_as_ground_truth = FALSE),
  outputs = c("e32", "e33", "e34", "e35", "e36", "e37", "e38", "e39", "e40"),
  preserved_untouched = c("e01", "e29", "e30", "e31", "and all other pre-existing estimates"),
  api_calls_made = 0L)
write_json(spec, file.path(EST, "v2_analysis_spec.json"), auto_unbox = TRUE, pretty = TRUE)

cat("\nwrote v2_analysis_spec.json, v2_provenance_judges.json, v2_provenance_geographic.json\n")
cat(strrep("=", 78), "\nDONE\n", strrep("=", 78), "\n", sep = "")
