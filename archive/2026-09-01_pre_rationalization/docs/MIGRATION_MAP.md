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
| `S3_specification_curve` | `ED2_sensitivity_panels` → `ED2_inferential_robustness` | Grouped by what varies; hierarchical separated as a different estimand; response-length labelled post-outcome. Then reorganised by jurisdiction — see below. |
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

## The figure redesign

A later revision audited every shipped panel against its source table
([`FIGURE_ESTIMAND_AUDIT.md`](../FIGURE_ESTIMAND_AUDIT.md)) and compared at least
two graphical forms for each ([`FIGURE_REDESIGN_MEMO.md`](../FIGURE_REDESIGN_MEMO.md)).
**No stale v1 or v2 estimate was found in any figure.** Every change below is
classified by how much of the analysis it touches.

| final panel | previous | classification | what changed |
|---|---|---|---|
| Fig 1a rates | Fig 1b | graphical re-expression | Both endpoints labelled, not just home; EU drawn as a structural zero rather than a point at 0. Same table, filter, weighting and (absent) uncertainty. |
| Fig 1b unadjusted difference | **not plotted** | previously-unplotted table row | `c02 quantity == "home_minus_away"` already carried a bootstrap interval and never reached a figure. No new estimation. |
| Fig 1c standardized | Fig 1c | graphical re-expression | Same row filter, more width. |
| Fig 1 locator map | Fig 1a | **panel retirement** | Carried no estimate and took ≈35% of the area; its region coding was recoded in the plotting script from a hard-coded ISO-3 list rather than read from the analysis data. Region coding now documented in the legends. |
| Fig 2a pooled language | Fig 2 (pooled row) | graphical re-expression | Rows ordered by magnitude, derived from the table. |
| Fig 2b model distribution | **replaces** the heatmap | derived graphical summary | Plots `c09` cells as points on one shared axis. Deterministic transformation of an existing table; no new estimation, no new uncertainty. |
| Fig 2b heatmap | Fig 2b | **panel relocation** → ED4a | Colour was scaled to max\|estimate\| = 61.4 pp, so 30 of 44 cells were indistinguishable; it showed an inferential quantity with no uncertainty at all. |
| Fig 2c framing | Fig 2c | graphical re-expression | Pooled row made visually primary; structural zero separated from estimated nulls; row order made explicit rather than resting on a reversed factor. |
| Fig 3a ideology | Fig 3a | **graphical re-expression, estimand/graphic mismatch corrected** | The estimand is a five-bin distribution summing to one; the panel plotted four bins and annotated the fifth, giving all its ink to 8–20% of the distribution. All five bins are now drawn. Same table, same rows. |
| Fig 3b/c foundations + PSA | Fig 3b, Fig 3c | graphical re-expression | Merged into one aligned compound panel with a single row-label column; PSA range redrawn with end ticks so it cannot be mistaken for the sampling interval beside it. |
| ED1 judge sensitivity | ED1 | **new statistical estimand** | Now plots `c17d`, the paired judge-minus-canonical difference with a paired bootstrap. Absolute estimates stay tabulated in `c17b`. The point-envelope bracket is removed as redundant. |
| ED2 | ED2 panel a | graphical re-expression | Reorganised by jurisdiction; five functional-form rows carrying `estimable = TRUE` with no estimate are omitted and counted instead of being given an empty facet. |
| ED3 post-outcome | ED2 panel b | **panel relocation** | Own figure number: a shared one is a claim of kinship, and these condition on a realized property of the response. |
| ED4 language | ED3 | **renamed output**, plus the relocated heatmap | Heatmap and interval panel now share model order, language order and spelling. Free x-scales in panel b retained deliberately. |
| ED5 reliability | **new** | derived graphical summary | Construct × metric matrix from `e23`/`e24`/`e25`, all four statistics already computed. No new estimation. |

New and renamed outputs:

| output | change |
|---|---|
| `c17d_judge_paired_differences.csv` | **New canonical table.** The only genuinely new estimand in the redesign. |
| `c07b_hierarchical_marginal.csv` | Unchanged content; **now written by `11_canonical_home.R`** instead of by the figure script. |
| `c08b_weighting_comparison.csv` | Unchanged content; **now written by `12_canonical_language_framing.R`** instead of by the figure script. |
| `ED2_sensitivity_panels.png` | → `ED2_inferential_robustness.png` (content changed; the legacy name is not kept). |
| `ED3_language_detail.png` | → `ED4_language_heterogeneity.png`. |
| — | `ED3_postoutcome_diagnostics.png`, `ED5_measurement_reliability.png` are new. |

`FIGURE_ESTIMAND_AUDIT.md` and `FIGURE_REDESIGN_MEMO.md` are the working record
of that audit. **`docs/CANONICAL_FIGURE_LEGENDS.md` remains the single
authoritative caption document**; no separate caption file was created.

## The estimand-driven restructure (`canon_011`)

The figure architecture was rebuilt from the inferential questions rather than
inherited. Two analyses that the documentation implied but the repository did not
contain were added.

| final figure | previous | classification | what changed |
|---|---|---|---|
| `Fig1_home_jurisdiction` | 3 panels (rates, unadjusted Δ, standardized Δ) | **panel retirement + graphical re-expression** | Rates removed from the figure — an absolute rate and a difference are different quantities and do not belong on one axis; they remain in `c02`. The two differences now share one forest. Descriptive weighting switched to `equal_model` to match the standardized target, and declared. EU is a structural zero, not a point at zero. |
| `Fig2_language` | `Fig2_language_framing` (a pooled language forest, b framing) | **panel relocation + graphical re-expression** | Framing left the figure entirely and became `ED10` at full width — it is a different exposure on a different block, and pairing it with language forced both into a half-height panel. The language contrast became four panels on one hierarchical spine, adding the jurisdiction and model levels from `c09` under the pooled `c08` estimate. Nothing about any estimand, weighting, block rule or bootstrap changed. |
| `ED10_framing` | `Fig2_language_framing` panel b | **panel relocation** | Same estimand, same tables (`c10`, `c11`), drawn at full width so the eleven per-model rows are legible. |
| `Fig3_content` | unchanged | — | Row order now comes from `_orders.R`. |
| `ED1_judge_sensitivity` | 2×2 free-scale grid | graphical re-expression | One forest, common x-axis, jurisdiction row groups, no redundant canonical rule. |
| `ED2_focused_sensitivity` | `ED2_inferential_robustness` (multiverse forest) | **renamed + scope reduced** | Four comparable specifications per jurisdiction; the classified grid moves to `c07c`. |
| `ED3_sample_size_stability` | `ED3_postoutcome_diagnostics` | **replaced** | Response-length diagnostics become `c07c` class E; ED3 is now the new stability analysis. |
| `ED4_language_heterogeneity` | heatmap + interval forest | **display halved** | One interval forest on a common axis; the exact values were always in `c09`. |
| `ED5_slant_by_model` | — | **new** | Five-bin composition per model × dimension. |
| `ED6_foundations_by_model` | — | **new** | Per-model prevalence with intervals. |
| `ED7_measurement_reliability` | `ED5_measurement_reliability` | **renumbered** | Same content. |
| `ED8_prompt_semantic_umap` | retired refusal-text UMAP | **new estimand and unit** | Prompt geometry, not refusal text; one fixed projection; diagnostics reported first. |
| `ED9_prompt_semantic_umap_by_model` | — | **new, optional** | Same geometry, binary per-model refusal. |

New and changed outputs:

| output | change |
|---|---|
| `c13_ideology_by_model.csv` | **Reshaped and recomputed.** Was 44 wide rows of point estimates with no uncertainty; now 264 long rows carrying the issue-cluster bootstrap, the jackknife-FPC battery interval, `n`, `n_issues`, `n_missing`, and `degenerate_outcome` / `support_ok` / `interval_reliable`. |
| `c15_moral_by_model.csv` | **Recomputed.** Same additions; the point column is renamed `prevalence` → `estimate` for consistency with every other canonical table. Nothing read the old shape. |
| `c07c_sensitivity_catalogue.csv` | **New.** Every sensitivity row classified A–F by what it changes, with `difference_from_primary_pp` and a `plottable` flag distinct from `estimable`. |
| `c21_*` | **New.** Issue-subsample stability: draws (parquet), summary, failures, metadata. |
| `c22_*` | **New.** Prompt UMAP: coordinates, propensities, per-model indicators, diagnostics, regions, metadata. |
| `data/prompt_embeddings_en.csv.gz` | **New input**, produced once by `scripts/embed_prompts.py` (the only step that calls an API) and hashed in the release manifest. |
| `pipeline/_orders.R` | **New.** One declaration of every ordering, shared by the estimation and figure layers, which had each kept their own. |
| `ED2_inferential_robustness.png`, `ED3_postoutcome_diagnostics.png`, `ED5_measurement_reliability.png` | **Retired filenames.** `audit_figures.R` now fails if any of them reappears. |

## Retired outputs, and why

| output | reason |
|---|---|
| `e20_moral_by_language.csv` | Unpaired cross-language comparison whose denominators are not comparable: both passes condition on engagement and engagement varies by language. |
| `e13`, `e13b` refusal-justification prevalence | The A–G taxonomy has the weakest inter-judge agreement of any construct here; no canonical estimand rests on it. Retained as description in `a03`, carried with its agreement statistics. |
| `e02` odds-ratio tables | Non-collapsible scale. |
| archived `40`–`44` inferential tables (`35`–`44` series) | Independent-sample chi-square/Fisher on paired observations; row-level bootstraps ignoring issue clustering; unclustered GLMs; `response_language` as the exposure. See `pipeline/archive/precanonical_appendix/README.md`. |
| `FIG4`, `FIG5`, `P1`–`P14`, `FIGA`–`FIGC` | Superseded figure generations; regenerable from the archived scripts. |
| `docs/FIGURE_CAPTIONS.md` | Describes a figure set that no longer exists, states the retired PNG-only rule, and claims no second-judge pass exists — untrue once the four-judge panel had run. Archived with that note. |
