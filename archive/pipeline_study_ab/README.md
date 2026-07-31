# Archived R scripts — Study A / Study B analyses

Archived 2026-07-30. These are **not broken and not superseded**. They analyse
two side experiments that the v2 main path does not run, so they were removed
from `pipeline/` to stop a 23-script directory implying 23 scripts execute.

## Why these seven, and not the others

Every script here reads an input that only the Study A or Study B runners
produce, and none of those runners has been executed in v2:

| Script | Required input | Produced by |
|---|---|---|
| `08_study_a_prompt_variance.R` | `prompts/test_prompts_en.json` | Study A prompt selection |
| `10_study_a_panel.R` | `data/study_a_prompt_subset_cn_addon.csv` | `scripts/study_a_jurisdiction_panel.py` |
| `11_study_b_lang_mechanism.R` | `annotations/annotations_study_b_{orig,refined}.jsonl` | `scripts/study_b_runner.py` |
| `12_stance_analysis.R` | `annotations/stance_study_a_cn.jsonl` | Study A stance pass |
| `13_deepseek_dotplots.R` | `annotations/annotations_study_a.jsonl` | Study A annotation |
| `14_refusal_vs_engaged_stance.R` | `annotations/annotations_study_a.jsonl` | Study A annotation |
| `16_engaged_state_alignment.R` | `annotations/stance_study_a_cn.jsonl` | Study A stance pass |

`MANIFEST.md` records `study_a_jurisdiction_panel.py` as carried over with its
**roster not yet refreshed** — it still names the legacy model list, so its
output would not be comparable with the current 11-model panel even if run.

Six of the seven already carried a `file.exists()` guard that printed `SKIP` and
exited 0. `11_study_b_lang_mechanism.R` did **not**: its internal `safe_ann()`
returns an empty tibble for a missing file, so instead of skipping it would have
proceeded to fit `glmer` and `glm` on zero rows — either erroring inside lme4 or
returning a meaningless model. That inconsistency is part of why the set was
archived rather than left in place with guards.

## What was deliberately kept

- **`16_irr_analysis.R`** (was `08_irr_analysis.R`) stays in `pipeline/`. It also
  skips today, but for a different reason: it needs
  `annotations_second_judge.jsonl`, which is one re-run of the annotation pass
  with a different `--judge-model` on the sample from
  `scripts/sample_for_second_judge.py`. That is reachable from the current run
  and is how inter-rater reliability becomes reportable — a live to-do, not a
  dormant experiment.
- **`14_deepseek_brief_figures.R`** (was `15_pilot_deepseek_dotplots.R`) stays:
  despite "pilot" in its old name it reads `data_clean.RData`, i.e. the main
  audit data, and simply renders figures for a specific brief.

## Consequence for `15_pnas_figures.R`

Four of its panels are wrapped in `file.exists()` checks against tables written
only by scripts now archived here:

| Guard | Table | Written by |
|---|---|---|
| `28_study_a_stratified_marginal.csv` | Study A marginals | `10_study_a_panel.R` |
| `34_deepseek_brief_fig3.csv` | entity swap | `13_deepseek_dotplots.R` |
| `34_deepseek_brief_fig4.csv` | native vs MT | `13_deepseek_dotplots.R` |
| `37_engaged_state_alignment.csv` | stance alignment | `16_engaged_state_alignment.R` |

So `fig_pnas_3_study_a`, `fig_pnas_4_entity_swap`, `fig_pnas_5_native_mt` and
`fig_pnas_6_stance` are **not produced on the main path** — silently, since the
guard is a plain `if`. That was already true before archiving; archiving makes
it permanent until Study A/B is run. If the PNAS figure set needs to be complete
rather than quietly partial, either run those experiments or drop the four
panels from `15_pnas_figures.R`.

## Restoring one

```bash
git mv archive/pipeline_study_ab/<script>.R pipeline/
```

The scripts were moved unmodified. Note their internal `# Script NN` headers and
any sibling references still use the **pre-2026-07-30 numbering**, which no
longer matches `pipeline/`; see the mapping in `docs/R_PIPELINE_WALKTHROUGH.md`.
