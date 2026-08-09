# =============================================================================
# make_release.R -- THE release command
# =============================================================================
# One command builds the paper's analysis end to end:
#
#   CANONICAL_RUN_ID=canon_004 Rscript pipeline/make_release.R
#
# It runs inputs -> reliability -> canonical estimation -> appendix descriptives
# -> figures -> manifest -> acceptance -> figure audit, and PROMOTES the result
# to pipeline/estimates/canonical and pipeline/figures ONLY if every check
# passes.
#
# WHAT THIS REPLACES. run_all.R claimed to be "the analysis driver" while
# excluding every canonical script, and its --figures mode selected a stage that
# no longer existed, so it ran nothing and exited 0. A driver that silently does
# nothing is worse than no driver.
#
# FOUR RULES:
#   1. CANONICAL_RUN_ID is MANDATORY. A release is a named thing.
#   2. The build happens in pipeline/releases/<run_id>/, never in the live
#      directories. A failed build cannot leave a half-written canonical
#      directory that looks current.
#   3. Fail fast. If a foundational stage fails, dependent stages do not run on
#      stale inputs.
#   4. Acceptance runs LAST, on the built artefacts, and promotion happens only
#      after it and the figure audit both pass.
#
# Flags:
#   --skip-data      do not rebuild data_clean.RData (it is an input, not output)
#   --allow-dirty    permit a release from a dirty working tree (recorded)
#   --no-promote     build and check, but leave the live directories untouched

t0 <- Sys.time()
suppressPackageStartupMessages({ library(tidyverse); library(digest) })
if (requireNamespace("here", quietly = TRUE)) setwd(here::here())

args <- commandArgs(trailingOnly = TRUE)
has <- function(f) f %in% args

RUN_ID <- Sys.getenv("CANONICAL_RUN_ID", "")
if (!nzchar(RUN_ID)) {
  cat("ERROR: CANONICAL_RUN_ID is required.\n",
      "       CANONICAL_RUN_ID=canon_004 Rscript pipeline/make_release.R\n", sep = "")
  quit(save = "no", status = 2)
}
if (!grepl("^[A-Za-z0-9._-]+$", RUN_ID)) {
  cat("ERROR: CANONICAL_RUN_ID must be a plain identifier.\n"); quit(save = "no", status = 2)
}
# The paper release reads the FULL run, never the pilot.
RUN_DIR <- Sys.getenv("REFUSAL_RUN_DIR", "annotations/full_v1")
Sys.setenv(REFUSAL_RUN_DIR = RUN_DIR)

# --- provenance: git ---------------------------------------------------------
# This gate runs BEFORE any directory is created. When it ran after, a build
# refused for a dirty tree had already made pipeline/releases/<id>/, and the
# immutability check then blocked the retry with a directory the failed run left
# behind.
git <- function(...) tryCatch(system2("git", c(...), stdout = TRUE, stderr = FALSE),
                              error = function(e) NA_character_)
GIT_SHA   <- git("rev-parse", "HEAD")[1]
GIT_SHORT <- git("rev-parse", "--short", "HEAD")[1]
GIT_BRANCH <- git("rev-parse", "--abbrev-ref", "HEAD")[1]
DIRTY_FILES <- git("status", "--porcelain")
DIRTY <- length(DIRTY_FILES) > 0 && any(nzchar(DIRTY_FILES))
if (DIRTY && !has("--allow-dirty")) {
  cat("ERROR: working tree is dirty (", length(DIRTY_FILES), " files).\n", sep = "")
  cat("       A release must be reproducible from a commit. Commit, or pass --allow-dirty.\n")
  quit(save = "no", status = 3)
}
cat(sprintf("git: %s @ %s%s\n", GIT_BRANCH, GIT_SHORT, if (DIRTY) "  [DIRTY]" else ""))

REL   <- file.path("pipeline/releases", RUN_ID)
B_EST <- file.path(REL, "estimates")
B_FIG <- file.path(REL, "figures", "main")
B_APP <- file.path(REL, "figures", "extended")

# RELEASES ARE IMMUTABLE. Reusing an existing release id silently merged new
# output into old output: files no longer produced by the current code survived,
# and the manifest then described a directory that no single run had made.
if (dir.exists(REL) && !has("--rebuild")) {
  cat("ERROR: release ", REL, " already exists.\n",
      "       Releases are immutable. Choose a new CANONICAL_RUN_ID, or pass\n",
      "       --rebuild to destroy and rebuild this one.\n", sep = "")
  quit(save = "no", status = 4)
}
if (dir.exists(REL) && has("--rebuild")) {
  cat("--rebuild: removing existing ", REL, "\n", sep = "")
  unlink(REL, recursive = TRUE)
}
for (d in c(B_EST, B_FIG, B_APP)) dir.create(d, recursive = TRUE, showWarnings = FALSE)
# Clear the figure directories before the build so no stale raster can survive
# into a release even if a figure script stops emitting it.
for (d in c(B_FIG, B_APP)) unlink(list.files(d, full.names = TRUE))

rule <- function(ch = "=") cat(strrep(ch, 78), "\n", sep = "")
rule(); cat("RELEASE BUILD: ", RUN_ID, "\n", sep = ""); rule()
cat("run dir   : ", RUN_DIR, "\n", sep = "")
cat("build dir : ", REL, "\n\n", sep = "")

sha256 <- function(p) if (file.exists(p)) digest(p, algo = "sha256", file = TRUE) else NA_character_

# --- the plan ----------------------------------------------------------------
# needs_data marks stages that read data_clean.RData.
PLAN <- tribble(
  ~id,  ~script,                                    ~what,                              ~foundational,
  "01", "pipeline/01_data_loading.R",               "build data_clean.RData",           TRUE,
  "02", "pipeline/02_judge_reliability.R",          "judge-panel reliability",          TRUE,
  "11", "pipeline/11_canonical_home.R",             "home standardization (c02-c07)",   TRUE,
  "12", "pipeline/12_canonical_language_framing.R", "language + framing (c08-c11)",     TRUE,
  "13", "pipeline/13_canonical_content.R",          "content (c12-c16, c19)",           TRUE,
  "14", "pipeline/14_canonical_judge_uncertainty.R","judge sensitivity (c17-c17d)",     TRUE,
  "15", "pipeline/15_subsample_stability.R",        "issue-subsample stability (c21)",  TRUE,
  # 16 SKIPS cleanly when the embedding cache is absent, so it is not
  # foundational: a machine that has never run scripts/embed_prompts.py still
  # builds a complete release, minus the two UMAP figures.
  "16", "pipeline/16_prompt_umap.R",                "prompt-semantic UMAP (c22)",       FALSE,
  "40", "pipeline/40_appendix_descriptives.R",      "appendix descriptives (a01-a04)",  FALSE,
  "20", "pipeline/20_figures_main.R",               "main figures",                     TRUE,
  "21", "pipeline/21_figures_extended.R",           "Extended Data figures",            TRUE)
if (has("--skip-data")) PLAN <- PLAN %>% filter(id != "01")

CAN_SEED_VALUE <- Sys.getenv("CAN_SEED", "20260807")
ENVV <- c(paste0("CANONICAL_RUN_ID=", RUN_ID),
          "CANON_RELEASE=1",
          paste0("CAN_SEED=", CAN_SEED_VALUE),
          paste0("REFUSAL_RUN_DIR=", RUN_DIR),
          paste0("CANON_EST_DIR=", B_EST),
          paste0("CANON_FIG_DIR=", B_FIG),
          paste0("CANON_APPFIG_DIR=", B_APP))

timings <- list()
for (i in seq_len(nrow(PLAN))) {
  s <- PLAN[i, ]
  cat("\n", strrep("#", 78), "\n# ", s$id, "  ", s$what, "\n", strrep("#", 78), "\n", sep = "")
  ti <- Sys.time()
  st <- system2("Rscript", s$script, env = ENVV)
  el <- as.numeric(difftime(Sys.time(), ti, units = "mins"))
  timings[[length(timings) + 1]] <- tibble(step = s$id, script = s$script,
                                           minutes = el, status = st,
                                           canonical_run_id = RUN_ID)
  cat(sprintf("\n-- %s %s in %.1f min\n", s$id, if (st == 0) "done" else "FAILED", el))
  # Fail fast: a dependent stage must never run on stale inputs.
  if (st != 0 && s$foundational) {
    cat("\nFOUNDATIONAL STAGE ", s$id, " FAILED. Stopping; nothing is promoted.\n", sep = "")
    write_csv(bind_rows(timings), file.path(B_EST, "c00_timings.csv"))
    quit(save = "no", status = st)
  }
}

# --- timings (second) --------------------------------------------------------
tim <- bind_rows(timings)
stopifnot(nrow(tim) > 0, all(is.finite(tim$minutes)))
write_csv(tim, file.path(B_EST, "c00_timings.csv"))

# --- manifest (third) --------------------------------------------------------
# Built AFTER everything else and never including a previous manifest: a
# manifest that lists itself is describing the last release, not this one.
cat("\n", strrep("#", 78), "\n# manifest\n", strrep("#", 78), "\n", sep = "")
MANIFEST_NAME <- "c00_manifest.csv"
unlink(file.path(B_EST, MANIFEST_NAME))

out_files <- c(
  file.path(B_EST, setdiff(list.files(B_EST), MANIFEST_NAME)),
  file.path(B_FIG, list.files(B_FIG)),
  file.path(B_APP, list.files(B_APP)))

src_files <- list.files("pipeline", pattern = "[.]R$", full.names = TRUE)
py_files  <- list.files("scripts", pattern = "[.]py$", full.names = TRUE)
# Specification and legend documents are part of what a release asserts, so
# their hashes belong in the manifest too: a spec edited after the build is a
# different claim about the same numbers.
doc_files <- c(list.files("docs", pattern = "[.]md$", full.names = TRUE),
               "CLAUDE.md", "pipeline/README.md")
doc_files <- doc_files[file.exists(doc_files)]
ann_inputs <- c(file.path(RUN_DIR, "annotations_all.jsonl"),
                list.files(RUN_DIR, pattern = "^annotations_.*_boundary[.]jsonl$",
                           full.names = TRUE),
                file.path(RUN_DIR, "annotations_panel.jsonl"))
ann_inputs <- ann_inputs[file.exists(ann_inputs)]
# The prompt-embedding cache is an INPUT, produced once outside the release by
# scripts/embed_prompts.py (which calls an API; the release never does). Its
# hash belongs in the manifest so the UMAP is traceable to the vectors it used.
emb_inputs <- c("data/prompt_embeddings_en.csv.gz", "data/prompt_embeddings_en.json")
emb_inputs <- emb_inputs[file.exists(emb_inputs)]

pkgs <- c("tidyverse", "ggplot2", "dplyr", "lme4", "logistf", "irr", "umap",
          "digest", "svglite", "ragg", "statmod")
pkg_ver <- map_dfr(pkgs, function(p) tibble(
  kind = "package", path = p,
  sha256 = NA_character_,
  detail = tryCatch(as.character(utils::packageVersion(p)), error = function(e) NA_character_)))

emb_model <- tryCatch({
  u <- list.files("pipeline/estimates", pattern = "^u0", full.names = TRUE)
  if (!length(u)) NA_character_ else {
    x <- read_csv(u[1], show_col_types = FALSE, n_max = 1)
    if ("representation" %in% names(x)) as.character(x$representation[1]) else NA_character_ }
}, error = function(e) NA_character_)

man <- bind_rows(
  tibble(kind = "output", path = out_files, sha256 = map_chr(out_files, sha256),
         detail = as.character(file.size(out_files))),
  tibble(kind = "source", path = src_files, sha256 = map_chr(src_files, sha256),
         detail = NA_character_),
  tibble(kind = "source_py", path = py_files, sha256 = map_chr(py_files, sha256),
         detail = NA_character_),
  tibble(kind = "documentation", path = doc_files,
         sha256 = map_chr(doc_files, sha256), detail = NA_character_),
  tibble(kind = "input_data", path = "pipeline/data_clean.RData",
         sha256 = sha256("pipeline/data_clean.RData"), detail = NA_character_),
  tibble(kind = "input_annotations", path = ann_inputs,
         sha256 = map_chr(ann_inputs, sha256), detail = NA_character_),
  tibble(kind = "input_embeddings", path = emb_inputs,
         sha256 = map_chr(emb_inputs, sha256), detail = NA_character_),
  pkg_ver,
  tibble(kind = "environment", path = c("R", "python", "embedding_model", "seed",
                                        "B_head", "B_sens", "B_judge"),
         sha256 = NA_character_,
         detail = c(paste(R.version$major, R.version$minor, sep = "."),
                    tryCatch(system2("python3", "--version", stdout = TRUE)[1],
                             error = function(e) NA_character_),
                    emb_model,
                    CAN_SEED_VALUE,
                    Sys.getenv("CANON_B_HEAD", "2000"),
                    Sys.getenv("CANON_B_SENS", "500"),
                    Sys.getenv("CANON_B_JUDGE", "600")))) %>%
  mutate(canonical_run_id = RUN_ID, git_sha = GIT_SHA, git_branch = GIT_BRANCH,
         git_dirty = DIRTY,
         generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S"))

# --- did the tree move under us? ---------------------------------------------
# The cleanliness gate runs before the build; the build then takes over an hour,
# and a source file edited during it is used by every stage that has not run
# yet. That happened: an edit to a figure script landed while stage 11 was
# running, so the figures were produced by code the recorded git_sha does not
# describe. The SHA-256 entries above were still correct -- they are hashed at
# manifest time, i.e. after the edit -- so the release was reproducible, but
# `git_sha` alone would have sent a reader to the wrong commit.
#
# Record both endpoints and say plainly whether they agree. A mid-build edit is
# not automatically fatal (the hashes remain the authoritative record), so this
# reports rather than fails, but it can never again be invisible.
GIT_SHA_END <- git("rev-parse", "HEAD")[1]
DIRTY_END   <- { s <- git("status", "--porcelain"); length(s) > 0 && any(nzchar(s)) }
MOVED <- !identical(GIT_SHA, GIT_SHA_END) || !identical(DIRTY, DIRTY_END)
man <- man %>% mutate(git_sha_at_start = GIT_SHA, git_sha_at_end = GIT_SHA_END,
                      tree_moved_during_build = MOVED)
if (MOVED) {
  cat("\n", strrep("!", 78), "\n", sep = "")
  cat("WARNING: the working tree moved during the build.\n")
  cat("  HEAD at start: ", GIT_SHA, if (DIRTY) " [DIRTY]" else "", "\n", sep = "")
  cat("  HEAD at end  : ", GIT_SHA_END, if (DIRTY_END) " [DIRTY]" else "", "\n", sep = "")
  cat("  The SHA-256 columns describe the files that actually produced these\n")
  cat("  outputs; git_sha_at_start does not. Verify the source hashes before\n")
  cat("  citing a commit for this release.\n")
  cat(strrep("!", 78), "\n", sep = "")
}
write_csv(man, file.path(B_EST, MANIFEST_NAME))
cat(sprintf("manifest: %d entries (%d outputs, %d sources, %d inputs)\n",
            nrow(man), sum(man$kind == "output"),
            sum(man$kind %in% c("source", "source_py")),
            sum(grepl("^input", man$kind))))

# --- acceptance (LAST) -------------------------------------------------------
cat("\n", strrep("#", 78), "\n# acceptance\n", strrep("#", 78), "\n", sep = "")
acc <- system2("Rscript", "pipeline/30_acceptance.R", env = ENVV)
cat("\n", strrep("#", 78), "\n# figure audit\n", strrep("#", 78), "\n", sep = "")
aud <- system2("Rscript", "pipeline/audit_figures.R", env = ENVV)

ok <- acc == 0 && aud == 0
cat("\n"); rule()
cat(sprintf("acceptance: %s   figure audit: %s\n",
            if (acc == 0) "PASS" else "FAIL", if (aud == 0) "PASS" else "FAIL"))

if (!ok) {
  cat("NOT PROMOTED. The build remains in ", REL, " for inspection.\n", sep = "")
  rule(); quit(save = "no", status = 1)
}
if (has("--no-promote")) {
  cat("Checks passed; --no-promote given, live directories untouched.\n"); rule()
  quit(save = "no", status = 0)
}

# --- atomic promotion --------------------------------------------------------
# THE BUG THIS REPLACES. The old promote() copied the build directory into the
# PARENT of the live directory. R's file.copy(recursive = TRUE) MERGES into an
# existing directory, so any live file the new release no longer produces
# survived promotion -- after the release itself had passed audit. The live tree
# could therefore contain files from three different runs while every check
# reported green.
#
# Now: stage into an empty, uniquely named sibling, verify the staged contents
# against the release by name and SHA-256, then swap directories. Nothing is
# ever merged into the live tree.
verify_same <- function(a, b) {
  fa <- sort(list.files(a, recursive = TRUE))
  fb <- sort(list.files(b, recursive = TRUE))
  if (!identical(fa, fb)) return(sprintf("file lists differ (%d vs %d)",
                                         length(fa), length(fb)))
  bad <- fa[vapply(fa, function(f)
    !identical(sha256(file.path(a, f)), sha256(file.path(b, f))), logical(1))]
  if (length(bad)) return(paste("hash mismatch:", paste(head(bad, 3), collapse = ", ")))
  ""
}

promote <- function(from, to) {
  if (!dir.exists(from)) return(invisible(FALSE))
  stage <- paste0(to, ".staging-", RUN_ID)
  retired <- paste0(to, ".retired-", RUN_ID)
  unlink(stage, recursive = TRUE); unlink(retired, recursive = TRUE)
  dir.create(stage, recursive = TRUE, showWarnings = FALSE)
  # Copy CONTENTS into the empty stage, never the directory into a parent.
  src <- list.files(from, full.names = TRUE, recursive = FALSE)
  ok1 <- all(file.copy(src, stage, recursive = TRUE, overwrite = TRUE))
  why <- verify_same(from, stage)
  if (!ok1 || nzchar(why)) {
    cat("PROMOTION ABORTED for ", to, ": ", if (nzchar(why)) why else "copy failed",
        "\n", sep = "")
    unlink(stage, recursive = TRUE); return(invisible(FALSE))
  }
  if (dir.exists(to)) file.rename(to, retired)
  ok2 <- file.rename(stage, to)
  if (!ok2) {                       # put the old tree back rather than leave none
    if (dir.exists(retired)) file.rename(retired, to)
    cat("PROMOTION ABORTED for ", to, ": swap failed\n", sep = "")
    return(invisible(FALSE))
  }
  unlink(retired, recursive = TRUE)
  invisible(TRUE)
}

pr <- c(promote(B_EST, "pipeline/estimates/canonical"),
        promote(B_FIG, "pipeline/figures/main"),
        promote(B_APP, "pipeline/figures/extended"))
if (!all(pr)) { cat("One or more promotions failed; live tree unchanged.\n"); quit(save = "no", status = 5) }

# Verify the PROMOTED tree, not only the release tree: the point of failure this
# guards against happens during promotion, after every earlier check has passed.
for (pair in list(c(B_EST, "pipeline/estimates/canonical"),
                  c(B_FIG, "pipeline/figures/main"),
                  c(B_APP, "pipeline/figures/extended"))) {
  why <- verify_same(pair[1], pair[2])
  if (nzchar(why)) { cat("PROMOTED TREE DIFFERS from the release: ", pair[2], " -- ",
                         why, "\n", sep = ""); quit(save = "no", status = 6) }
}
cat("promoted trees match the release exactly (names + SHA-256)\n")

# Re-run the figure audit against the LIVE directories.
aud2 <- system2("Rscript", "pipeline/audit_figures.R",
                env = c(paste0("CANONICAL_RUN_ID=", RUN_ID),
                        "CANON_EST_DIR=pipeline/estimates/canonical",
                        "CANON_FIG_DIR=pipeline/figures/main",
                        "CANON_APPFIG_DIR=pipeline/figures/extended"))
if (aud2 != 0) { cat("POST-PROMOTION FIGURE AUDIT FAILED\n"); quit(save = "no", status = 7) }
cat("post-promotion figure audit: PASS\n")

cat("PROMOTED to pipeline/estimates/canonical and pipeline/figures/\n")
cat(sprintf("RELEASE %s COMPLETE in %.1f min\n", RUN_ID,
            as.numeric(difftime(Sys.time(), t0, units = "mins"))))
rule()
