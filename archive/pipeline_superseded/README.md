# Archived R scripts — superseded by the rewritten figure set

Archived 2026-08-02, when `11_visualizations.R` was rewritten as the single
publication figure script against the design system in `pipeline/_theme.R`.

## `13_report_figures.R`

Every panel it produced now exists in `11_visualizations.R`, built to the new
standard:

| was | now |
|---|---|
| `fig_r2_deepseek_language` | `fig2_deepseek_language` |
| `fig_r3_safety_thresholds` | `fig1_refusal_by_model` (adds the regular/boundary shift) |
| `fig_r5_justification_patterns` | `fig5_refusal_justifications` (7 codes collapsed to 4 separable groups) |
| `fig_r4_ideology_shifts` | not reproduced — Pass 2 only, and the canonical run is Pass-1-only |
| `fig_r1_doing_vs_discussing` | removed 2026-07-31, legacy task-type taxonomy |

It also carried its own `theme_report`, a second Wilson-CI helper, and its own
`scale_color_manual` values — three separate reasons the same quantity could
render differently here than in `11`. Keeping both would have guaranteed drift.

Restore with `git mv archive/pipeline_superseded/13_report_figures.R pipeline/`,
but note it writes PDF+PNG pairs and predates `save_fig()`.
