# =============================================================================
# Script 08a: Select Study A's 30-prompt frozen subset
# =============================================================================
# Rank prompts by cross-model refusal-rate variance in the existing English
# regular-prompt battery, cap at 4 per category, pick top 30. Emit a frozen
# CSV that is committed to the repo before any Study A API spend.
# =============================================================================

suppressPackageStartupMessages({
  library(tidyverse)
  library(jsonlite)
})

if (requireNamespace("here", quietly = TRUE)) setwd(here::here())  # portable root (was hardcoded)
# --- STUDY-A/B INPUT GUARD (v2) ---------------------------------------
if (!file.exists("prompts/test_prompts_en.json")) {
  cat("SKIP 08_study_a_prompt_variance.R: required input (Study A prompt subset) not present in this run.\n")
  quit(save = "no", status = 0)
}
# ---------------------------------------------------------------------


# Load the cleaned annotation data (built by 01_data_loading.R).
load("pipeline/data_clean.RData")

# Pool English regular + boundary observations. Regular-only pool has most
# categories at ~0% refusal and yields too few high-variance prompts. Pooling
# regular and boundary gives a richer candidate set and lets Study A cover
# prompts that actually elicit cross-model disagreement — which is the
# selection criterion in the plan.
pool <- data_clean %>%
  filter(prompt_language == "en") %>%
  select(prompt_id, prompt_category, controversy_tier, dataset_type, model, refused)

cat(sprintf("English pool (regular + boundary): %d observations across %d prompts\n",
            nrow(pool), n_distinct(pool$prompt_id)))

# Per-prompt refusal rate and across-model variance within each tier.
# With binary outcomes across 5 models, variance peaks at 0.25 when 2 or 3 of
# the 5 models refuse. We rank by variance, then by mean refusal rate as a
# tiebreaker (favoring prompts closer to a 2/5-3/5 split rather than 0/5 or 5/5).
# dataset_type is kept so the frozen subset can record whether a given prompt
# came from the regular or boundary tier.
prompt_stats <- pool %>%
  group_by(prompt_id, prompt_category, controversy_tier, dataset_type) %>%
  summarise(
    n_models = n(),
    mean_refusal = mean(refused),
    var_refusal = var(refused),
    .groups = "drop"
  ) %>%
  filter(n_models == 5) %>%   # all 5 models coded; drop partials
  arrange(desc(var_refusal), desc(mean_refusal * (1 - mean_refusal)))

cat("\nTop 20 by variance:\n")
print(prompt_stats %>% head(20))

# Pick top 30 with a cap of 4 per category.
PROMPTS_TARGET <- 30
PER_CATEGORY_CAP <- 4

selected <- prompt_stats %>%
  group_by(prompt_category) %>%
  mutate(within_cat_rank = row_number()) %>%
  ungroup() %>%
  filter(within_cat_rank <= PER_CATEGORY_CAP) %>%
  arrange(desc(var_refusal)) %>%
  head(PROMPTS_TARGET)

cat(sprintf("\nSelected %d prompts across %d categories\n",
            nrow(selected), n_distinct(selected$prompt_category)))

cat("\nCategory distribution in selected subset:\n")
print(selected %>% count(prompt_category, sort = TRUE))

# Attach original English prompt text for the frozen CSV.
en_prompts <- fromJSON("prompts/test_prompts_en.json", flatten = TRUE)$prompts %>%
  as_tibble() %>%
  select(prompt_id = id, prompt_text = text, category, controversy_tier)

frozen <- selected %>%
  left_join(en_prompts, by = c("prompt_id",
                                "prompt_category" = "category",
                                "controversy_tier")) %>%
  select(prompt_id, prompt_category, controversy_tier,
         prompt_text, mean_refusal, var_refusal)

cat("\nTier distribution in selected subset:\n")
print(selected %>% count(controversy_tier))

# Sanity check: every selected prompt has text attached.
stopifnot(all(!is.na(frozen$prompt_text)))

# Write the frozen subset. This file is the in-repo record of the Study A
# sample, committed before any API spend.
dir.create("data", showWarnings = FALSE, recursive = TRUE)
write_csv(frozen, "data/study_a_prompt_subset.csv")

cat(sprintf("\nWrote refusal_audit/data/study_a_prompt_subset.csv (%d prompts)\n",
            nrow(frozen)))
cat("Study A runner should read prompt_id + prompt_text from this file.\n")
