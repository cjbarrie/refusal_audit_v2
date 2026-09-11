# Forensic R analysis audit: Luna v2.4 and model integration

Updated: 11 September 2026. Scope: every root-level R file in `pipeline/`, its
release-driver entry, declared inputs and outputs, companion technical document,
and a scratch execution of all active estimators and figures. Historical and
unsupported scripts were inspected to determine their status but were not used
to produce current estimates.

The promoted working release is now `canon_024`. It is a figure-only successor
to the hash-verified 18-model estimates in `canon_021`; the manifest records
the explicitly permitted dirty tree. `canon_018` records the final 11-model
v2.4 integration and `canon_019` records the first full 18-model audit build.
The accepted, non-promoted `canon_029` release adds completed Sarvam-105B and
Bielik 11B v3.0 inputs, producing a 20-model interim frame; it inherits the
fully recomputed estimates from `canon_025`. T-pro remains excluded.

## Findings and resolutions

| ID | Severity | Evidence | Consequence | Resolution and regression evidence |
|---|---:|---|---|---|
| R01 | P0 | The former active stages mixed original Gemini `engagement_code >= 4`, intermediate Sol/DSL labels and final Luna labels. | Two scripts could call different constructs “refusal,” and figures could mix them. | `_response_validity.R` binds the exact original file hash; `_expansion_input.R` binds the five expansion batches. All active outcome scripts use `genuine_refusal` and `capability_failure`. The original label is named `original_nonengagement`, remains missing for expansion models and is refitted only on its original 137,186-row domain. Current tests reproduce 249,201 keys, 6,794 refusals and 60,968 capability failures. |
| R02 | P1 | The final Parquet contains five `refusal_evidence_span` strings with an embedded NUL byte. R failed while dplyr sliced Arrow's lazy character vector. | Every R estimator stopped before analysis despite valid structured labels. | `_response_validity.R:62-72,117-123` activates `arrow.skip_nul` at read and join time, restoring the caller's option afterward. The source file and verified hash remain unchanged; only invalid bytes in in-memory evidence text are stripped. The full data loader and all downstream scripts then ran. |
| R03 | P0 | Old active content scripts estimated ideological slant and moral foundations from original passes 2/3, for which no final adopted outcome measure exists. | Their outputs could appear equally canonical to final response-behaviour outcomes. | These scripts and their mixed plotting/stability consumers are under `pipeline/pending/`; `make_release.R:257-269` contains none of them. `30_acceptance.R:117-136` and `audit_figures.R:22-35,71-73` enforce the supported figure inventory and pending separation. |
| R04 | P1 | The old home, language, UMAP, acceptance and figure stages were written against mixed pre-v2.4 tables. | Merely changing a variable name would leave incompatible table schemas and figure-selection rules. | Replaced stages 11, 12, 15, 16, 17, 20, 21, 30 and 40 with v2.4-specific implementations. The replaced versions are retained under `pipeline/archive/pre_v24_luna/` or `pipeline/pending/`, not silently overwritten as current code. |
| R05 | P1 | A cluster bootstrap can draw one issue several times. If each copy retains only `issue_id`, issue-nested weights collapse repeated draws. | Bootstrap intervals use the wrong empirical distribution. | `10_canonical_common.R:160-208` creates a distinct `bootstrap_issue_instance` for every draw and passes it into the weighting functions. `tests_synthetic.R` checks the declared copy key and fixed number of planned draws. |
| R06 | P0 | A home association is undefined when an outcome has no events in one arm. In the expanded sample this occurs for EU capability failure. | A fitted numerical value would be separation-driven extrapolation rather than an estimable contrast. | Stage 11 records the capability-failure row as `estimable = FALSE` and the appendix retains it as a grey cross rather than zero. EU genuine refusal has a finite point estimate, but 55.4% of planned bootstrap fits fail; Main Figure 1 therefore uses an open diamond and suppresses that unreliable interval. The figure audit enforces the main display rule. |
| R07 | P0 | Raw model/language rates do not hold the prompt fixed, and raw home/away rates do not control observed prompt composition. | Descriptive differences could be misstated as effects. | Stage 12 forms complete `(model,prompt_id)` language pairs and complete English `(issue_id,model)` 2+2 framing blocks. Stage 11 separates raw descriptives (`c02/c03`) from logistic g-computation (`c04-c07`). Documentation consistently calls the home quantity a standardized predictive association rather than causal. |
| R08 | P2 | The current R index and pipeline README still named retired stages 02, 13 and 14 and described stage 17 as a historical Sol analysis. | A manual reviewer would follow nonexistent paths and misunderstand the outcome. | Both indexes now list the 18 active root R files, including the expansion-input contract, and link one companion document per file. Every active R header carries the same link, and acceptance check G1 enforces this. |
| R09 | P1 | The figure audit originally searched comments as executable source, while comments explicitly documented that slant/moral work was pending. | A correct script failed simply for explaining an exclusion. | `audit_figures.R` removes comment lines before its executable-code scan. The redesigned candidate figure audit passed 16/16 checks. |
| R10 | P2 | The figure layer could silently retain stale files, merge refusal with failure, or leave grey marks unexplained. | Readers could mistake unusable generation for deliberate refusal or receive an old raster. | The revised design has two genuine-refusal main PNGs. Figure 1 links five exact jurisdiction-level semantic maps to descriptive, standardized and model-specific home contrasts. Figure 2 links language maps to paired aggregate and model-specific language contrasts. Fourteen Extended Data PNGs contain all capability-failure artwork, measurement checks and detailed model-level maps. Grey in the main atlas is labelled “No genuine refusal,” not engagement. Exact inventory, outcome-separation and PNG-only gates pass. |
| R11 | P2 | Appendix stage 40 hard-coded 500 issue-bootstrap draws for `a04` instead of reading the sensitivity setting recorded in the release manifest. | A release built with a non-default `CANON_B_SENS` would record one setting while a04 used another. | Stage 40 now reads `CANON_B_SENS` once as `B_APPENDIX` and passes it to `boot_canon`; its companion page states the same rule. |
| R12 | P1 | UMAP stage 16 asserted prompt IDs but not the expected embedding width, finiteness or positive vector norms before normalization. | A malformed cache could create `NaN` coordinates or an undocumented representation change. | Stage 16 now requires 512 finite numeric dimensions and strictly positive norms before cosine normalization. |
| R13 | P2 | Stage 12 offset the random seed by statistic label but wrote only the unmodified base seed to bootstrap diagnostics. | The resampling sequence could not be recreated from `c18` alone. | `boot_paired()` now stores its exact `draw_seed`, derived deterministically from `CAN_SEED` and the label, and the technical reference explains the rule. |
| R14 | P2 | Stage 15's issue-subsample seed was reproducible from code but absent from each saved draw. | A reviewer could not recreate one selected subset directly from the output row. | Each draw now carries `draw_seed`, and the metadata stores the exact deterministic seed formula. |
| R15 | P1 | Stage 01 joined frozen prompt metadata but did not assert that its category/tier agreed with the same fields carried by annotation records. | Sample filtering and later covariate adjustment could use contradictory provenance without stopping. | Stage 01 now requires exact category and tier equality after the metadata join; the current 137,186 rows pass with zero mismatches. |
| R16 | P2 | Four mixed pre-v2.4 scripts moved to `pipeline/pending/` had status banners but no individual companion page. | A manual reviewer could see why the directory was pending but not what each retained file historically consumed and produced. | Every pending R file now links to an individual page under `docs/r_pipeline/pending/`; the registry records those pages and no pending file is executable through the release plan. |
| R17 | P0 | The original Gemini outcome is unavailable for all nine expansion models. | Treating missing values as zero or mixing the 11- and 20-model targets would confound an outcome-definition sensitivity with roster composition. | Main c04/c08/c10 tables contain only the two current Luna outcomes. `c07`, `c08c` and `c10c` isolate the original outcome and label the changed original-panel roster. Acceptance checks exactly 137,186 nonmissing original labels. |
| R18 | P1 | The former stage-01 output path was mutable and a release could overwrite `pipeline/data_clean.RData`. | A historical release could not prove which assembled frame its estimates used. | `CANON_DATA_PATH` and `CANON_SUMMARY_DIR` now route the assembled RData and summaries into the candidate release. The file is included in the release output manifest and the interactive builder reads that exact copy. |
| R19 | P1 | An earlier aggregate figure's fixed item order omitted `EU`, so a valid EU estimate could silently become an `NA` factor and disappear even while table acceptance passed. | The paper plot could omit a jurisdiction without failing the numerical gate. | The replacement Figure 1 iterates directly over all five frozen `ORDER_JURIS` values, and acceptance checks the five-row source contract. |
| R20 | P1 | Four mutable figure directories represented different data vintages. | A reader could not infer which pictures belonged to the promoted release. | `main/` and `extended/` remain only as the promoted pointer. The pre-Kimi and ad hoc expanded directories are retired to a dated archive after the replacement release surface is validated. |
| R21 | P1 | An initial scratch figure render pointed `CANON_EST_DIR` directly at `canon_019`, so the plotting scripts replaced that candidate's two `c20` layout-audit RDS files. The release manifest caught the mismatch before inheritance. Scientific CSVs and PNGs were not changed. | A plotting proof should never be able to modify an inherited release, even when the scientific files are read-only in intent. | The extended layout was restored byte-for-byte from its identical child-release copy. The main layout was restored from the corrected `canon_020` child; its old `canon_019` manifest hash therefore remains intentionally diagnostic and `canon_019` must not be used as an inheritance source. `canon_021` remains hash-clean and is the source for the redesign. Both plotting scripts now accept a separate `CANON_LAYOUT_DIR`, so scratch renders can read immutable estimates while writing audit objects elsewhere. |
| R22 | P1 | `pipeline/PIPELINE_REGISTRY.csv` still declared the retired three-main-figure and 13-appendix inventory after `canon_024` adopted two main and 14 Extended Data figures. | The machine-readable registry contradicted the accepted release and could drive an incomplete downstream copy or review. | Stages 20 and 21 now declare the exact `Fig1`–`Fig2` and `ED1`–`ED14` inventories and their current source tables. Documentation-contract tests compare the registry, scripts and release outputs. |
| R23 | P0 | Mutable root artifacts included an 11-model `pipeline/data_clean.RData` and matching `pipeline/tables/00_*` summaries. `make_release.R --skip-data` could silently consume that stale frame while constructing a nominally current release. | A new release could combine 11-model data with 18-model analysis code without a hash or row-count failure at the point of selection. | The stale root artifacts are preserved with explicit names under `archive/2026-09-04_post_v24_rationalization/pipeline/`. `--skip-data` is now rejected; full builds always assemble a release-scoped frame, while figure-only releases inherit hash-verified files. A regression test enforces the rejection and the current technical page documents the supported modes. |
| R24 | P1 | The generated interactive Parquet files still represented 137,186 responses and 11 models although the promoted release contains 224,544 responses and 18 models. | The explorer could display a materially obsolete corpus while appearing to use canonical UMAP coordinates. | `interactive/build_data.py` was rerun against the promoted manifest. Its metadata now records `canon_024`, 2,496 fixed prompt points, 224,544 unique response rows, 18 models, zero missing response texts and zero duplicate response keys. |
| R25 | P2 | Live documentation contained broken references to retired correction scripts, probe outputs and experiment memos; active Python entry points had no compact registry; caches and unrelated root material remained. | Manual review required guesswork about which files were executable, historical, pending or disposable. | Current documents now link directly to dated archive locations; root and subdirectory READMEs distinguish live, pending, generated and historical material. `scripts/SCRIPT_REGISTRY.csv` assigns stable stage IDs to every supported Python entry point. Superseded documents, obsolete wrappers, stale tables and unrelated material were moved to the dated archive; interpreter/test caches and empty directories were removed. Repository-audit and documentation-contract tests enforce the resulting surface. |
| R26 | P1 | The first 18-model rebuild of `interactive/umap_points.parquet` omitted `prompt_text`, although the app requires that field for gray-point hover text. | The Streamlit landing page raised a `KeyError` instead of drawing the map. | The builder now joins one complete English prompt string to every fixed coordinate and stops if any are missing. The app test loads the promoted assets, and the asset test requires 2,496 unique prompt IDs with nonmissing hover text. |
| R27 | P2 | After retiring the mutable root data file, direct `Rscript pipeline/tests_synthetic.R` still inherited the common layer's obsolete default path. | The advertised standalone regression command failed before running a test. | The test entry point now defaults explicitly to `pipeline/estimates/canonical/data_clean.RData`, while preserving `CANON_DATA_PATH` for candidate-release checks. All 13 checks pass from the repository root. |
| R28 | P1 | The Luna v2.4 JSONL reader used `str.splitlines()`, which treats embedded Unicode line and paragraph separators (U+2028/U+2029) as record boundaries. A valid Bielik response containing such a character was therefore reported as a truncated JSON record even though the frozen file and SHA-256 were intact. | Full-corpus annotation could not start for multilingual responses containing valid Unicode separators; repeated retries would fail before any provider call. | `_read_jsonl()` now iterates over physical LF-delimited file records. A regression test writes both Unicode separators inside JSON strings and verifies exact round-trip recovery. The 12,184-row Bielik payload retained its authorized bytes and hash and began successfully after the fix. |
| R29 | P0 | The active expansion helper and model ordering stopped at the seven v3 additions even though Sarvam-105B and Bielik had completed immutable generation and Luna annotation ledgers. | Running the old pipeline would silently omit both finished models; manually appending them downstream would bypass hashes, missingness and release gates. | `_expansion_input.R` now verifies both v4 payloads and their result hashes, carries five exhausted Bielik annotations as missing, and enforces 112,015 expansion rows. `_orders.R`, acceptance checks and technical references use the 20-model roster. `canon_029` passes 29/29 numerical and 17/17 figure checks without promotion; unfinished T-pro is outside every input list. |
| R30 | P1 | Sarvam-105B's reliable model-specific home interval reaches −11.73 pp, outside the former main-figure limit of −10 pp. | The accepted estimate was visually clipped even though numerical and structural checks passed. | Main Figure 1 now uses a shared −15 to +25 pp range. The figure audit verifies both the declared scale and that every reliable genuine-refusal interval lies inside it; `canon_029` passes the new 17th gate. |

## Current scientific specifications checked

- **Descriptive response behaviour:** census counts and realized-corpus rates;
  no sampling interval is attached to a complete-corpus proportion.
- **Home-region association:** English home/away rows within developer
  jurisdiction; logistic outcome model with `home * model_f + tier + domain +
  route_f` when several models are present; g-computation to a target that gives
  equal total weight to models, then issues within model, then prompts within
  model-issue; issue-cluster percentile bootstrap.
- **Delivered-language contrast:** target-language minus English within the
  identical model/prompt block, averaged within model and then equally over
  models; issues resampled with pairs intact.
- **Prompt framing:** boundary mean minus regular mean within complete English
  2+2 issue/model blocks; equal-model aggregation and issue resampling.
- **Stability:** issues sampled without replacement at declared fractions;
  empirical 5th-95th percentile ranges are explicitly not confidence intervals.
- **UMAP:** one geometry fitted to the 2,496 cached English prompt embeddings;
  outcome labels are overlays and never enter the embedding or UMAP fit.

The formulas, target populations and limits on interpretation are expanded in
`docs/CANONICAL_ANALYSES.md` and the per-script pages under `docs/r_pipeline/`.

## Verification performed

1. Parsed all 18 active root R files and all seven pending R files successfully;
   all 26 registry rows (including the validity CLI) resolve to an existing
   script and technical document.
2. Rebuilt the release-scoped `data_clean.RData`; exact combined counts were
   224,544 responses, 6,127 genuine refusals, 52,563 capability failures and
   11,475 original judge-coded non-engagements on the original panel.
3. Passed 13/13 fast synthetic and measurement-contract tests, including the
   standardized-risk accounting identity.
4. Retained non-promoted `canon_018` as the full-bootstrap 11-model v2.4
   candidate; it is not relabelled as the expansion release.
5. Built `canon_019` at the full 2,000/500/100 resampling settings; all nine
   registered stages completed successfully.
6. Rendered two main and 14 Extended Data figures and inspected the raster
   artwork at production resolution.
7. Passed 175/175 Python tests, 13/13 R synthetic tests, 29/29 numerical
   acceptance checks and 16/16 figure-audit checks.
8. Rebuilt the interactive data against the promoted manifest: 2,496 prompt
   points, 224,544 unique responses and 18 models, with no missing response text
   or duplicate canonical keys.
9. Re-ran the repository inventory after the 4 September rationalization; all
   supported Python and R scripts have registry/documentation coverage and no
   disposable cache or root plotting artifact remains.

`canon_021` contains the complete 224,544-row frame and hash-verified estimates.
`canon_024` inherits those estimates and carries the accepted compact
two-main-figure redesign; it passed 29/29 numerical acceptance checks plus
16/16 figure checks and was promoted as the canonical working release. Because
it was built with `--allow-dirty`, the manifest preserves that limitation and
a committed clean-tree rebuild with a fresh release ID remains necessary for
the final archival paper release.
