# `20_figures_main.R`

This plotting-only script draws two main figures about genuine refusal. It does
not draw capability failure, refit a statistical model, calculate an interval,
or alter the fixed UMAP coordinates.

## Inputs

| File | Rows used | Purpose |
|---|---:|---|
| `c02_home_descriptive_english.csv` | Five genuine-refusal home-minus-away rows | Unadjusted jurisdiction differences and bootstrap intervals |
| `c04_home_standardized.csv` | Five nested/full-target genuine-refusal rows | Standardized jurisdiction contrasts |
| `c05_home_by_model.csv` | Twenty-three genuine-refusal rows | Model-specific standardized contrasts; GigaChat has no defined home stratum |
| `c08_language_paired.csv` | Four equal-model genuine-refusal rows | Aggregate target-language-minus-English contrasts |
| `c09_language_by_model.csv` | Ninety-six genuine-refusal rows | Model × language contrast matrix |
| `c22_prompt_umap_coordinates.csv` | 2,496 prompts | The one fixed English-prompt geometry |
| `c22_prompt_outcome_propensities.csv` | Five language rows per prompt | Language-specific genuine-refusal propensity |
| `c22_prompt_outcomes_by_model.csv` | Up to twenty-four model rows per prompt | Binary English genuine-refusal events |

## Figure 1

`Fig1_jurisdiction_refusal_atlas_home.png` contains six equal-height developer-
jurisdiction blocks. Each block places a combined English semantic map beside
the corresponding home-topic forest plot.

Every map begins with all 2,496 prompt coordinates in pale grey. A prompt
refused by one model receives a solid point in that model's colour. If more
than one model refused, the script divides one circular glyph into equal-angle
sectors, one sector per refusing model. Colours therefore retain a single
meaning and the reader does not have to learn the 23 combinations observed in
China or the 31 observed in the United States. Models are ordered by `_orders.R`
and colours come from the jurisdiction-local, colour-vision-safe palettes in
`_theme.R`.

The map receives 52% of each block's width and the coefficient panel 48%.
Placing the local model key to the right of the map, rather than underneath it,
lets the fixed-aspect UMAP use nearly the full row height. Pale-grey points are
drawn first at low opacity to establish the full semantic support; larger,
nearly opaque model-coloured marks then carry the refusal events. UMAP axes and
ticks are suppressed because their arbitrary coordinates have no substantive
scale. These choices make the atlas the visual anchor without changing its
coordinates or allowing dense background points to compete with refusals.

The grey key is deliberately labelled **No genuine refusal**, not “engaged.” A
response can fail for capability reasons without being a genuine refusal.
Fifty-one missing English prompt-model outcomes—twenty-four GigaChat, twenty
Bielik, six Sarvam-30B and one GPT-4o—are not
recoded as non-refusals. A prompt with an incomplete set and no observed refusal
is shown as a hollow grey point.

The forest plot's first row overlays two different quantities:

- hollow grey circle: the descriptive English home-minus-away difference from
  `c02`;
- red diamond: the nested, full-target standardized contrast from `c04`.

The remaining rows show the model-specific standardized `c05` contrasts. Their
colours match the map. Every block uses the same −15 to +25 percentage-point
axis. Reliable stored intervals are drawn; an estimable point with an unreliable
interval is left open and its interval is suppressed. A grey cross is retained
for a non-estimable model row and is not a zero estimate.

Russia is displayed because GigaChat contributes complete-enough refusal and
language outcomes. Both Russia coefficient rows are crosses: the prompt frame
has no Russia-focused issue region, so neither an aggregate nor model-specific
home contrast exists. Europe is not used as a proxy.

The maps are descriptive semantic locators. The adjacent home estimates adjust
for measured prompt composition, but they are predictive standardizations and
not causal effects of developer jurisdiction.

## Figure 2

`Fig2_language_refusal_atlas_contrasts.png` links five delivered-language maps
to the paired language estimand. The top row reuses the fixed geometry and
varies point size by the equal-jurisdiction/equal-model genuine-refusal
propensity in English, Chinese, Arabic, Russian, or Hindi. The lower-left panel
shows the four aggregate target-language-minus-English paired differences and
their issue-bootstrap intervals. The lower-right matrix shows the corresponding
model-specific differences; blue is negative, red positive, and a black dot
marks an interval excluding zero. Model rows are exploratory and have no
multiplicity adjustment.

The language contrasts concern delivery of the tested translations, conditional
on translation equivalence and stable delivery. They are not effects of a
speaker's identity or nationality.

## Outputs and structural checks

- `Fig1_jurisdiction_refusal_atlas_home.png`: 183 × 225 mm, 600 DPI.
- `Fig2_language_refusal_atlas_contrasts.png`: 183 × 125 mm, 600 DPI.
- `c20_figure_layout_main.rds`: both plot objects for structural auditing. A
  scratch render can set `CANON_LAYOUT_DIR` so this audit object is not written
  beside inherited immutable estimates; release builds leave it unset and
  correctly write into the new candidate estimate directory.

PNG is the only image format. The artwork contains no title, subtitle, caption,
explanatory callout, or fitted quantity calculated in the plotting layer. The
Russia design limitation is encoded by the existing non-estimable cross mark
and explained in the external figure caption.

## Worked trace

For the China “All models” row, the hollow mark comes from the China genuine-
refusal `quantity == "home minus away"` row in `c02`; the red diamond comes from
the China genuine-refusal `weighting == "nested"` and `support == "full target"`
row in `c04`. The five rows beneath it are the China records in `c05`. In the map,
the same prompt coordinate is coloured solid when one Chinese model refused and
split into model-coloured sectors when several did. Neither the coordinate nor
any estimate is recomputed.
