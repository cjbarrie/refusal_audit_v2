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

## `14_deepseek_brief_figures.R` and `15_finding_figures.R`

Archived 2026-08-02. Both produced standalone, title-free panels for manuscripts
that do not exist in this repository — `deepseek_brief.tex` and the former
`pnas_paper.tex`. The only writeup here is `writeup/pipeline_technical.tex`,
which references neither. Every panel they produced now exists in
`11_visualizations.R` or `08_deepseek_chinese_analysis.R`, built to the design
system and generally better:

| was | now | why the replacement is better |
|---|---|---|
| `fig_f1_tasktype` | `fig4_refusal_by_domain` | f1 left domains in fixed order and accented two of them arbitrarily; fig4 orders by rate and shows Wilson intervals |
| `fig_f2_deepseek_pilot` | `fig3_language_gap_by_model` | common x scale across models, panels ordered by within-model spread |
| `deepseek_brief_pilot_fig1` | `fig3_language_gap_by_model` | same comparison, complete-coverage models only |
| `deepseek_brief_pilot_fig2` | `fig22_deepseek_language_gap_by_category` | estimates with intervals instead of bars; axis stops at the data |

`15` additionally guarded four of its six panels (`fig_f3`–`fig_f6`) on tables
written only by scripts in `archive/pipeline_study_ab/`, so two-thirds of it
never ran on the main path.

Restoring either brings back a script that predates `save_fig()` and writes its
own PDF/PNG pairs.

## `12_visualizations_extended.R`

Archived 2026-08-02. It produced exactly three figures and no tables:

- **fig12 (base vs boundary)** — the same comparison as `fig1_refusal_by_model`,
  but as grouped bars with model names on the x-axis, where eleven labels
  collided into an unreadable run ("GPT-5.1 Claude Opus 4.5 GPT-4o" overprinted),
  a y-axis to 60% for a 20% maximum, and value labels overlapping each other
  ("4.1%4.2%"). fig1 shows it as a dumbbell, ordered by rate, models in
  monospace on the y-axis where they have room.
- **fig13, fig14** — annotation Pass 2 only, guarded, and the canonical run is
  Pass-1-only.

So on the main path the script drew one broken duplicate and skipped twice.
