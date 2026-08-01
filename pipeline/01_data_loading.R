# =============================================================================
# Script 01: Data Loading and Preparation
# =============================================================================
# Load multilingual annotation data and prepare for analysis
# Saves clean data as RData for use in subsequent scripts

library(jsonlite)
library(tidyverse)
library(here)

# Set working directory to the repo root portably (replaces a hardcoded path).
# here::here() locates the project root from any subdirectory.
setwd(here::here())

# Run directory holding the annotation-pipeline outputs for this run.
# Override either with an env var, e.g. REFUSAL_RUN_DIR=annotations/pilot_v1
run_dir     <- Sys.getenv("REFUSAL_RUN_DIR", "annotations/pilot_v1")
prompts_dir <- Sys.getenv("REFUSAL_PROMPTS_DIR", file.path(run_dir, "prompts_meta"))
cat(sprintf("Run dir: %s\nPrompts dir: %s\n", run_dir, prompts_dir))

# Create output directories
dir.create("pipeline/tables", showWarnings = FALSE, recursive = TRUE)
dir.create("pipeline/figures", showWarnings = FALSE, recursive = TRUE)

cat(rep("=", 80), "\n", sep = "")
cat("LOADING MULTILINGUAL ANNOTATION DATA\n")
cat(rep("=", 80), "\n", sep = "")

read_jsonl <- function(file_path) {
  lines <- readLines(file_path, warn = FALSE)
  data <- map_dfr(lines, ~ fromJSON(.x, flatten = TRUE))
  return(data)
}

# Load all annotations from annotations_all.jsonl
cat("\nLoading annotations_all.jsonl...\n")
data_all <- read_jsonl(file.path(run_dir, "annotations_all.jsonl"))
cat(sprintf("Total records in annotations_all.jsonl: %d\n", nrow(data_all)))

# Treat all records in annotations_all.jsonl as the base dataset.
# Boundary prompts included in that file will be dropped later using prompt metadata.
data_base <- data_all %>%
  mutate(dataset_type = "base")

cat(sprintf("Base records loaded: %d\n", nrow(data_base)))

# Load boundary annotations
cat("\nLoading boundary annotations...\n")
# Study languages, matching config.SUPPORTED_LANGUAGES. ja/id were dropped in
# 2026-07 and are no longer produced by any run.
boundary_files <- file.path(run_dir, c(
  "annotations_en_boundary.jsonl",
  "annotations_zh_boundary.jsonl",
  "annotations_ar_boundary.jsonl",
  "annotations_ru_boundary.jsonl",
  "annotations_hi_boundary.jsonl"
))

# Only read boundary files that actually exist -- a run may cover a subset of
# languages (e.g. an English-only pilot), so absent files are expected, not errors.
present_boundary <- boundary_files[file.exists(boundary_files)]
missing_boundary <- boundary_files[!file.exists(boundary_files)]
if (length(missing_boundary) > 0) {
  cat(sprintf("Skipping %d absent boundary file(s): %s\n",
              length(missing_boundary),
              paste(basename(missing_boundary), collapse = ", ")))
}

data_boundary <- map_dfr(present_boundary, function(file) {
  lines <- readLines(file, warn = FALSE)
  # Exclude error records (e.g. judge parse failures that dropped the tier field)
  valid_lines <- lines[!grepl('"error"', lines)]
  if (length(valid_lines) == 0) return(tibble())
  map_dfr(valid_lines, ~ fromJSON(.x, flatten = TRUE))
})
if (nrow(data_boundary) > 0) {
  data_boundary <- data_boundary %>% mutate(dataset_type = "boundary")
}

cat(sprintf("Boundary records loaded: %d\n", nrow(data_boundary)))

# Combine
data <- bind_rows(data_base, data_boundary)

cat(sprintf("Total records loaded: %d (base: %d, boundary: %d)\n",
            nrow(data), nrow(data_base), nrow(data_boundary)))

# =============================================================================
# Data Cleaning
# =============================================================================

cat("\nCleaning data...\n")

# Filter valid annotations only
data_clean <- data %>%
  filter(
    !is.na(engagement_code),
    engagement_code >= 1,
    engagement_code <= 5,
    prompt_language != "",
    !is.na(model)
  )

cat(sprintf("Records after filtering: %d (%.1f%% retained)\n",
            nrow(data_clean),
            nrow(data_clean) / nrow(data) * 100))

# =============================================================================
# Create Analysis Variables
# =============================================================================

cat("\nCreating analysis variables...\n")

# Batteries built before the native-sourcing fix carry no prompt_origin_language
# at all, and referring to a missing column inside mutate() is an error rather
# than an NA. Materialise it first so this loader stays able to read older runs.
if (!"prompt_origin_language" %in% names(data_clean)) {
  data_clean$prompt_origin_language <- "en"
}
if (!"prompt_origin_form" %in% names(data_clean)) {
  data_clean$prompt_origin_form <- "authored_en"
}
if (!"route" %in% names(data_clean)) {
  data_clean$route <- "perennial"
}

data_clean <- data_clean %>%
  mutate(
    # Binary engagement/refusal
    engaged = engagement_code <= 3,
    refused = engagement_code >= 4,

    # Categorical engagement. Made an ORDERED factor with explicit levels: the
    # 1-5 scale is a gradient, and as a bare character vector ggplot and table()
    # would sort it alphabetically ("Engagement with caveats" first, "Partial"
    # before "Soft"), silently scrambling the order in any figure that used it.
    # Level labels match PAL_ENGAGEMENT in _theme.R exactly.
    engagement_category = factor(
      case_when(
        engagement_code == 1 ~ "Full engagement",
        engagement_code == 2 ~ "Engagement with caveats",
        engagement_code == 3 ~ "Partial engagement",
        engagement_code == 4 ~ "Soft refusal",
        engagement_code == 5 ~ "Hard refusal",
        TRUE ~ NA_character_
      ),
      levels = c("Full engagement", "Engagement with caveats",
                 "Partial engagement", "Soft refusal", "Hard refusal"),
      ordered = TRUE
    ),

    # Factors for plotting.
    # Model order groups by developer jurisdiction: US (4), CN (2), EU (1),
    # MENA (3 self-hosted HF Inference Endpoints), India (1 self-hosted HF
    # Inference Endpoint: Sarvam). Keep this in sync with scripts/config.py
    # TEST_MODELS + ENDPOINT_MODELS. The endpoint models only appear in runs
    # where their *_ENDPOINT_URL was set; ggplot drops unused levels, so listing
    # them here is harmless when absent.
    model_f = factor(
      model,
      levels = c("gpt-5.1", "claude-opus-4.5", "gpt-4o", "grok-4.3",
                 "deepseek-chat-v3.1", "qwen3-max", "mistral-large-2512",
                 "allam-7b", "jais-8b", "falcon3-10b", "sarvam-30b"),
      labels = c("GPT-5.1", "Claude Opus 4.5", "GPT-4o", "Grok 4.3",
                 "DeepSeek V3.1", "Qwen3-Max", "Mistral Large 2512",
                 "ALLaM 7B", "Jais 8B", "Falcon3 10B", "Sarvam 30B")
    ),

    # Developer jurisdiction of each model (canonical source for downstream
    # scripts; mirrors the jurisdiction field of config.py TEST_MODELS).
    jurisdiction_f = factor(
      case_when(
        model %in% c("gpt-5.1", "claude-opus-4.5", "gpt-4o", "grok-4.3") ~ "US",
        model %in% c("deepseek-chat-v3.1", "qwen3-max")                  ~ "CN",
        model %in% c("mistral-large-2512")                               ~ "EU",
        model %in% c("allam-7b", "jais-8b", "falcon3-10b")               ~ "MENA",
        model %in% c("sarvam-30b")                                       ~ "India",
        TRUE ~ NA_character_
      ),
      levels = c("US", "CN", "EU", "MENA", "India")
    ),

    language_f = factor(
      prompt_language,
      levels = c("en", "zh", "ar", "ru", "hi"),
      labels = c("English", "Chinese", "Arabic", "Russian", "Hindi")
    ),

    dataset_type_f = factor(
      dataset_type,
      levels = c("base", "boundary"),
      labels = c("Regular Prompts", "Boundary Prompts")
    ),

    # Language the prompt was originally AUTHORED in. Almost all prompts are
    # authored in English and translated out; issues harvested from a
    # non-English Wikipedia edition were authored in that edition's language and
    # back-translated into English (sourcing/10_backtranslate_native.py), so
    # their English is a translation rather than the original.
    #
    # This is NOT the same as language_f (the language a response was elicited
    # in) — it is a property of the prompt, constant across all languages a
    # prompt is run in. It exists so the analysis can check that natively
    # sourced prompts do not behave differently from translated-through ones;
    # if they do, the sourcing route is a confound and must be modelled.
    # Batteries predating the field carry no value, so default to "en".
    prompt_origin_language = ifelse(
      is.na(prompt_origin_language) | prompt_origin_language == "",
      "en", prompt_origin_language
    ),
    prompt_origin_f = factor(
      prompt_origin_language,
      levels = c("en", "zh", "ar", "ru", "hi"),
      labels = c("Authored in English", "Authored in Chinese",
                 "Authored in Arabic", "Authored in Russian", "Authored in Hindi")
    ),
    natively_sourced = prompt_origin_language != "en",

    # How a natively-authored prompt reached the English master:
    #   authored_en - written in English to begin with
    #   native      - written wholly in the origin language, then back-translated
    #   hybrid      - only the STANCE was native; Stage 3 wraps every boundary
    #                 prompt in an English template regardless of source edition,
    #                 so these were part-English before back-translation
    # All three are translated the same way into every study language. The tag
    # exists so hybrids can be isolated in a robustness check: their stance has
    # been round-tripped (zh -> en -> zh) and so is one translation step further
    # from the source than a native prompt's is.
    prompt_origin_form = ifelse(
      is.na(prompt_origin_form) | prompt_origin_form == "",
      "authored_en", prompt_origin_form
    ),
    prompt_origin_form_f = factor(
      prompt_origin_form,
      levels = c("authored_en", "native", "hybrid"),
      labels = c("Authored in English", "Native (back-translated)",
                 "Hybrid stance (back-translated)")
    ),

    # Which harvest route surfaced this issue:
    #   perennial       Wikipedia's curated list of controversial issues —
    #                   long-running disputes
    #   temporal        the protection log — what was being fought over in the
    #                   harvest window
    #   current-events  the Current Events portal — same recency, but not gated
    #                   on contentious-topic designations, so it reaches
    #                   economic/environmental/social disputes the others miss
    #
    # The rebalanced frame merges all three, which is what makes the
    # perennial-vs-contested-right-now contrast (NEXT_STEPS Step 7) a covariate
    # inside ONE arm rather than three separate runs. That matters because the
    # rebalanced frame already contains 100% of the perennial battery and 96% of
    # the temporal one — running them separately would re-ask the same issues.
    # Batteries predating the route tag are perennial by definition.
    route = ifelse(is.na(route) | route == "", "perennial", route),
    route_f = factor(
      route,
      levels = c("perennial", "temporal", "current-events"),
      labels = c("Perennial", "Temporal (protection log)", "Current events")
    ),
    contemporary = route != "perennial"
  )

# =============================================================================
# Basic Descriptive Statistics
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("BASIC DESCRIPTIVE STATISTICS\n")
cat(rep("=", 80), "\n", sep = "")

# Overall counts
cat("\nOverall:\n")
cat(sprintf("  Total responses: %d\n", nrow(data_clean)))
cat(sprintf("  Engagement rate: %.1f%%\n", mean(data_clean$engaged) * 100))
cat(sprintf("  Refusal rate: %.1f%%\n", mean(data_clean$refused) * 100))

# By model
cat("\nBy model:\n")
model_summary <- data_clean %>%
  group_by(model_f) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    .groups = "drop"
  ) %>%
  arrange(desc(engagement_rate))

print(model_summary)

# By language
cat("\nBy language:\n")
language_summary <- data_clean %>%
  group_by(language_f) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    .groups = "drop"
  ) %>%
  arrange(desc(engagement_rate))

print(language_summary)

# By category
cat("\nBy category:\n")
category_summary <- data_clean %>%
  group_by(prompt_category) %>%
  summarise(
    n = n(),
    engagement_rate = mean(engaged),
    .groups = "drop"
  ) %>%
  arrange(engagement_rate)

print(category_summary)

# =============================================================================
# Merge Prompts Metadata (to get controversy_tier)
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("MERGING PROMPTS METADATA\n")
cat(rep("=", 80), "\n", sep = "")

# Load all prompt files and extract metadata.
# The prompt JSON files contain ALL prompts (both regular and boundary).
# We load metadata twice with different dataset_type labels to align with
# the annotation data structure:
#   - dataset_type = "base": matches annotations from annotations_all.jsonl (regular prompts)
#   - dataset_type = "boundary": matches annotations from boundary files
# Only merge metadata for languages whose prompt file exists in this run.
all_languages <- c("en", "zh", "ar", "ru", "hi")  # ja/id dropped 2026-07 (see config.py)
languages <- all_languages[file.exists(
  file.path(prompts_dir, sprintf("test_prompts_%s.json", all_languages))
)]
cat(sprintf("Prompt-metadata languages present: %s\n",
            paste(languages, collapse = ", ")))

# Load ALL prompts with dataset_type = "base" (will only match regular prompt IDs via join)
prompts_metadata_base <- map_dfr(languages, function(lang) {
  prompt_file <- file.path(prompts_dir, sprintf("test_prompts_%s.json", lang))
  prompt_data <- fromJSON(prompt_file, flatten = TRUE)

  # Extract prompt metadata
  prompts_df <- prompt_data$prompts %>%
    select(id, category, controversy_tier) %>%
    rename(prompt_id = id) %>%
    mutate(prompt_language = lang, dataset_type = "base")

  return(prompts_df)
})

# Load boundary prompts (from the same base file) to align with dataset_type = boundary
prompts_metadata_boundary <- map_dfr(languages, function(lang) {
  prompt_file <- file.path(prompts_dir, sprintf("test_prompts_%s.json", lang))
  prompt_data <- fromJSON(prompt_file, flatten = TRUE)

  prompts_df <- prompt_data$prompts %>%
    filter(controversy_tier == "boundary_testing") %>%
    select(id, category, controversy_tier) %>%
    rename(prompt_id = id) %>%
    mutate(prompt_language = lang, dataset_type = "boundary")

  return(prompts_df)
})

# Combine
prompts_metadata <- bind_rows(prompts_metadata_base, prompts_metadata_boundary)

cat(sprintf("Loaded metadata for %d prompts (base: %d, boundary: %d)\n",
            nrow(prompts_metadata), nrow(prompts_metadata_base), nrow(prompts_metadata_boundary)))

# Merge with prompt metadata.
# In the v2 schema the annotation records already carry `controversy_tier` via
# provenance, so metadata's tier is brought in under a distinct name to avoid a
# join collision. `category` is metadata-only and doubles as the
# metadata-existence marker for the drop-unmatched filter below.
data_clean <- data_clean %>%
  left_join(
    prompts_metadata %>% rename(meta_controversy_tier = controversy_tier),
    by = c("prompt_id", "prompt_language", "dataset_type")
  )

# Drop any base records that are actually boundary prompts (using the
# annotation's authoritative controversy_tier), and any without prompt metadata.
data_clean <- data_clean %>%
  filter(!(dataset_type == "base" & controversy_tier == "boundary_testing")) %>%
  filter(!is.na(category))

cat(sprintf("Merged metadata. Controversy tier distribution:\n"))
print(table(data_clean$controversy_tier, useNA = "ifany"))

# =============================================================================
# Save Clean Data
# =============================================================================

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("SAVING CLEAN DATA\n")
cat(rep("=", 80), "\n", sep = "")

# Save as RData for fast loading in subsequent scripts
save(data_clean, file = "pipeline/data_clean.RData")
cat("Saved: pipeline/data_clean.RData\n")

# Also save summary tables
write_csv(model_summary, "pipeline/tables/00_model_summary.csv")
write_csv(language_summary, "pipeline/tables/00_language_summary.csv")
write_csv(category_summary, "pipeline/tables/00_category_summary.csv")
cat("Saved: pipeline/tables/00_*.csv\n")

cat("\n")
cat(rep("=", 80), "\n", sep = "")
cat("DATA LOADING COMPLETE\n")
cat(rep("=", 80), "\n", sep = "")
cat("\nNext: Run 02_engagement_analysis.R\n\n")
