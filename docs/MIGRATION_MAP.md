# Old → new: every table, figure and script

What happened to each output in the revision that produced release `canon_004`.
Nothing was deleted: superseded code is under `pipeline/archive/` with a README
per group, superseded documentation under `docs/archive/`, and every retired
estimate CSV stays where it was.

## Tables

| old | new | what changed |
|---|---|---|
| `c12_ideology_distribution` (share_negative / share_neutral / share_positive / signed_mean) | `c12_ideology_distribution` (share_neg2 … share_pos2, `role = PRIMARY`; signed_mean `role = SECONDARY`) | **Recomputed.** Five bins with an interval on each; dimension-specific endpoints added; the three-way collapse is gone from the primary estimand. |
| `c12` `conf_*_finite_battery` | `c12` `conf_low_battery` / `conf_high_battery` | **Recomputed.** Delete-one-issue jackknife with FPC replaces √(1−f) shrinkage of a percentile interval. |
| `c04_home_standardized` (one estimand) | `c04_home_standardized` (`support` = full target / common support; `estimator` = ML / Firth) | **Recomputed.** Two estimands, plus GLM warnings, separation diagnosis, `observed_fit_extreme_weight`, `counterfactual_extreme_weight`, `interval_reliable`, `replicate_failure_rate`. |
| — | `c06b_common_support_diagnostics` | **New.** Cells, rows, issues and retained target weight for the support restriction. |
| `c05_home_by_model` (EQUAL-MODEL AVERAGE row without interval) | `c05_home_by_model` (jointly bootstrapped average with interval) | **Recomputed.** |
| `c08_language_paired` (with judge-perturbation rows) | `c08_language_paired` (no judge rows; `primary_weighting` declared; `judge_sensitivity` explains the absence) | **Recomputed.** The one-armed perturbation compared two instruments rather than perturbing one. |
| `c10_framing_paired` (n_reg>0 & n_bnd>0) | `c10_framing_paired` (complete 2+2 primary, loose rule as labelled sensitivity) + `c10b_framing_incomplete_blocks` | **Recomputed.** Seven incomplete English blocks now listed by key. |
| `c14` `low_agreement_flag`, `panel_pos_specific` | `c14` `psa_mean` / `psa_min` / `psa_max` / `n_pairs`, no flag | **Recomputed.** True pairwise PSA; the invented 0.35 threshold removed. |
| `c17_measurement_sensitivity` (unequal samples; "ACROSS-JUDGE RANGE") | `c17` (per-comparison, common support) + `c17b` (envelope) + `c17c` (support description) | **Recomputed.** Pairwise and all-judge common support; envelope renamed and no longer contaminated by the full-sample interval. |
| `e23`/`e25` `positive_specific_agreement` | `e23`/`e25` `psa_mean` … + `all_rater_positive_unanimity`; new `e23b`, `e23c`, `e22b` | **Recomputed.** The old statistic survives under a name that says what it is. |
| `c18` (`replicates_attempted`) | `c18` (`replicates_drawn`, `failed_draws_replaced`, `interval_reliable`, jackknife rows) | **Recomputed.** Fixed-B draws; failures counted. |
| `c00_manifest` (file list) | `c00_manifest` (SHA-256 of outputs, sources, inputs; git SHA + dirty; package/language versions; seeds; B counts; embedding revision) | **Rebuilt.** Never lists itself. |
| `a01`–`a04` | **New.** Descriptive appendix views replacing the archived scripts' tables. |

## Figures

| old | new | what changed |
|---|---|---|
| `FIG1_canonical_home` (map + standardized + UMAP) | `Fig1_home_jurisdiction` (design + unadjusted + both standardized estimands) | Home family only; UMAP and judge sensitivity moved out. |
| `FIG2_canonical_language_framing` (3 weightings + 4-colour forest) | `Fig2_language_framing` (primary weighting + model×language heatmap with printed values + complete-block framing) | Weighting comparison → `c08b` table; colour no longer the only channel. |
| `FIG3_canonical_content` (3-way ideology, "acceptable agreement") | `Fig3_content` (five bins, dimension endpoints, numeric PSA) | Recomputed and relabelled. |
| `S1_home_descriptive` | folded into `Fig1` panel b | The unadjusted rates belong beside the standardized ones. |
| `S2_judge_multiverse` | `ED1_judge_sensitivity` | Common-support samples only; envelope renamed. |
| `S3_specification_curve` | `ED2_sensitivity_panels` | Grouped by what varies; hierarchical separated as a different estimand; response-length labelled post-outcome. |
| `S4_projection_supplement` | **retired** | Moved to `pipeline/archive/exploratory_umap/`: lexical purity matched semantic purity, so the figure did not support its own premise, and it was never rebuilt by the release driver. |
| — | `ED3_language_detail` | **New.** Per-model intervals behind the heatmap; the weighting comparison is the `c08b` table. |
| `P15_refusal_text_umap` | retired | Content lives in ED3. |
| `.pdf` + `.svg` + `.png` | `.png` only | Multi-format export removed for the second and final time; see `docs/CANONICAL_ANALYSES.md` §6a. |

## Scripts

| old | new |
|---|---|
| `run_all.R`, `run_canonical.R` | `make_release.R` (one command; the two partial drivers were removed) |
| `24_measurement.R` | `02_judge_reliability.R` |
| `50`–`56_canonical_*.R` | `10`–`14`, `20`, `30` |
| `21_figures_appendix.R` | `21_figures_extended.R` |
| `02`, `06`–`09` (v1 descriptive) → `40`–`44` | `40_appendix_descriptives.R`; the five originals archived to `pipeline/archive/precanonical_appendix/` |
| `16_irr_analysis.R`, `57_refusal_umap_figure.R` | `pipeline/archive/retired/` |
| — | `tests_synthetic.R` (new) |

## Retired outputs, and why

| output | reason |
|---|---|
| `e20_moral_by_language.csv` | Unpaired cross-language comparison whose denominators are not comparable: both passes condition on engagement and engagement varies by language. |
| `e13`, `e13b` refusal-justification prevalence | The A–G taxonomy has the weakest inter-judge agreement of any construct here; no canonical estimand rests on it. Retained as description in `a03`, carried with its agreement statistics. |
| `e02` odds-ratio tables | Non-collapsible scale. |
| archived `40`–`44` inferential tables (`35`–`44` series) | Independent-sample chi-square/Fisher on paired observations; row-level bootstraps ignoring issue clustering; unclustered GLMs; `response_language` as the exposure. See `pipeline/archive/precanonical_appendix/README.md`. |
| `FIG4`, `FIG5`, `P1`–`P14`, `FIGA`–`FIGC` | Superseded figure generations; regenerable from the archived scripts. |
| `docs/FIGURE_CAPTIONS.md` | Describes a figure set that no longer exists, states the retired PNG-only rule, and claims no second-judge pass exists — untrue once the four-judge panel had run. Archived with that note. |
