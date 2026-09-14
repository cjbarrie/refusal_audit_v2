# `21_figures_extended.R`

This plotting-only script draws 14 Extended Data figures. Genuine refusal is
red and capability failure blue. It fits no scientific model and every
model-specific estimate is attached to an explicit model label.

## Output inventory

1. `ED1_home_absolute_risks_genuine_refusal.png` and
   `ED2_home_absolute_risks_capability_failure.png`: standardized away and home
   risks from `c04`.
2. `ED3_language_absolute_rates_genuine_refusal.png` and
   `ED4_language_absolute_rates_capability_failure.png`: paired English and
   target-language levels by model from `c09`.
3. `ED5_measurement_reclassification.png`: lollipop summaries of the four final
   response states overall and within each original binary label, from `c24`
   and `c27`. This replaces the former stacked bars.
4. `ED6_annotation_component_profile.png`: separate annotation-field marginals
   from `c25`.
5. `ED7_model_specific_contrasts_genuine_refusal.png` and
   `ED8_model_specific_contrasts_capability_failure.png`: labelled
   model-specific home, language and framing estimates and intervals from
   `c05`, `c09` and `c11`.
6. `ED9_content_fingerprint_genuine_refusal.png` and
   `ED10_content_fingerprint_capability_failure.png`: descriptive topic-domain
   and issue-region rates from `c23`.
7. `ED11_prompt_distribution_genuine_refusal.png` and
   `ED12_prompt_distribution_capability_failure.png`: prompt concentration and
   English cross-model recurrence from `c22b` and `c22d`.
8. `ED13_capability_failure_semantic_atlas.png`: region, language and model
    capability-failure maps using the same geometry and visual grammar as Main
    Figure 1.
9. `ED14_genuine_refusal_semantic_atlas_by_model.png`: the detailed English
   genuine-refusal map for each of the 24 models. It preserves model-level
   inspection after the main figure replaces repeated maps with six exact
   jurisdiction-combination maps.

## Interpretation

ED5--ED6 and ED9--ED14 are descriptive. ED1--ED4 show absolute levels
underlying the reported contrasts. ED7--ED8 are exploratory heterogeneity
analyses with no multiplicity adjustment and describe the 24 tested models.
Subsample-stability tables remain available as c21 diagnostics but are no
longer rendered as generic Extended Data figures.

All UMAP coordinates are fixed. Region facets retain pale points outside the
region as geometry only, medium-grey points identify the 416 prompts in the
facet, and outcome-coloured size gives propensity. Model panels use English
binary outcomes. Apparent neighbourhoods do not imply statistical clusters.

All outputs are 183-mm, 600-DPI PNGs. ED13 uses the 225-mm full-page height and
ED14 the 165-mm tall canvas; other heights follow `_theme.R`. No plot title, subtitle, caption,
numeric callout or explanatory annotation is embedded.
`CANON_LAYOUT_DIR` can redirect the layout-audit RDS during scratch rendering;
release builds write it into the candidate release beside the inherited tables.

## Worked trace

For one Chinese model row in ED7, the point and interval are exactly the
`estimate_pp`, `conf_low_pp` and `conf_high_pp` fields of its `c09` row. In ED5,
the original non-engagement × genuine-refusal-only point is the corresponding
`share_within_original` value in `c27`. Neither is recomputed in this script.

Slant and moral-foundation figures remain pending because the project has not
adopted final outcome measures for them.
