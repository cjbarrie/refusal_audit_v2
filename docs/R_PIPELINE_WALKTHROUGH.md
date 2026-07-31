# The R analysis pipeline — what each script does, and why

> **Reorganised 2026-07-30.** The directory was 23 scripts of which 7 could
> never run (Study A/B side experiments whose runners have not been executed in
> v2) and the numbering had a collision — two scripts were numbered `08`. The
> seven are now in `archive/pipeline_study_ab/` with a README explaining each;
> the remaining 16 are renumbered `01`–`16` in execution order: **01 load ·
> 02–10 estimation and tables · 11–15 figures · 16 reliability.**
>
> | was | is now |
> |---|---|
> | `01_data_loading.R` | `01_data_loading.R` |
> | `02_engagement_analysis.R` | `02_engagement_analysis.R` |
> | `03_ideology_analysis.R` | `03_ideology_analysis.R` |
> | `03b_ideology_extended.R` | `04_ideology_extended.R` |
> | `03c_moral_extended.R` | `05_moral_extended.R` |
> | `05_refusal_justifications.R` | `06_refusal_justifications.R` |
> | `06_deepseek_language_analysis.R` | `07_deepseek_language_analysis.R` |
> | `07_deepseek_chinese_analysis.R` | `08_deepseek_chinese_analysis.R` |
> | `07b_pnas_stats.R` | `09_deepseek_stats.R` |
> | `06b_ideology_moral_patterns.R` | `10_ideology_moral_patterns.R` |
> | `04_visualizations.R` | `11_visualizations.R` |
> | `04b_visualizations_extended.R` | `12_visualizations_extended.R` |
> | `04c_report_figures.R` | `13_report_figures.R` |
> | `15_pilot_deepseek_dotplots.R` | `14_deepseek_brief_figures.R` |
> | `09_pnas_figures.R` | `15_pnas_figures.R` |
> | `08_irr_analysis.R` | `16_irr_analysis.R` |
> | `08_study_a_prompt_variance.R` | archived |
> | `10_study_a_panel.R` | archived |
> | `11_study_b_lang_mechanism.R` | archived |
> | `12_stance_analysis.R` | archived |
> | `13_deepseek_dotplots.R` | archived |
> | `14_refusal_vs_engaged_stance.R` | archived |
> | `16_engaged_state_alignment.R` | archived |
>
> All 16 share one publication theme and validated palette
> (`pipeline/_theme.R`); none sets its own theme any more.

This is a plain-English map of the 23 R scripts in `pipeline/`, inherited from
the former collaborator. The goal is to understand them well enough to decide
which logic to **keep and re-implement in Python** and which is dead weight
(paper-specific figures, one-off briefs) we can drop.

**The big picture.** These scripts are the *analysis layer*. They sit
**downstream** of everything we've rebuilt (sourcing → prompts → model
generation → LLM-as-judge annotation). They take one input — a table of
*annotated model responses* — and turn it into tables, statistical tests, and
figures for the papers. None of them call any model or touch the sourcing
pipeline. They are pure read-analyze-plot.

Everything hangs off **one script**: `01_data_loading.R`. It builds the clean
analysis table (`data_clean.RData`); all 22 others load that table and slice it.
So the port is really: **re-implement `01` faithfully in pandas, then decide
which of the 22 downstream analyses we still want.**

---

## The data model `01_data_loading.R` builds (the thing to port first)

It reads `annotations/annotations_all.jsonl` — one row per *annotated model
response* — and derives the columns every other script relies on:

| derived column | rule | meaning |
|---|---|---|
| `engaged` | `engagement_code <= 3` | model answered the question |
| `refused` | `engagement_code >= 4` | model declined |
| `engagement_category` | 1=Full, 2=Caveats, 3=Partial, 4=Soft refusal, 5=Hard refusal | the 5-point scale |
| `dataset_type` | `"base"` (regular) vs `"boundary"` | which prompt tier |
| `model_f`, `language_f`, `dataset_type_f` | factors with fixed level order | so models/languages plot in a stable order |

It filters to valid rows (`engagement_code` in 1–5), drops the contradiction
where a base row is tagged boundary, and writes three descriptive summary
tables (by model, by language, by category). **This is the contract**: the
judge must emit `engagement_code` (1–5), and — for the ideology/moral/stance
analyses — `ideology_score`, moral-foundation flags, `refusal_justification`,
and `stance_score`. Porting `01` means reproducing these derivations exactly so
the numbers match.

---

## The 23 scripts, grouped by what they're for

### Core — you almost certainly want these ported

| script | what it does | motivation |
|---|---|---|
| **01_data_loading.R** | Builds `data_clean` from the raw annotations; writes the by-model / by-language / by-category summaries. | The foundation. Everything else needs it. |
| **02_engagement_analysis.R** | The headline **refusal/engagement** analysis: engagement rate per model × language, the DeepSeek Chinese effect, refusal by category, controversial-vs-domestic splits. Fits a logistic mixed model (`glm`/`lme4`). 10 tables. | This is the paper's central result — who refuses, in which language, on what. |
| **03_ideology_analysis.R** | For *engaged* answers, scores **ideological lean** and **moral-foundations** usage per model × language; fits models; predicts marginal means. 8 tables. | The second research question: not just *whether* models engage, but *how they slant* when they do. |
| **06_refusal_justifications.R** | Among refusals, tabulates the **stated reason** (refusal-code A–G) per model × language, and for strategic/controversial/domestic subsets. 5 tables. | Characterizes *how* models refuse, not just how often. |

### Extended analyses — keep if the corresponding result is in the paper

| script | what it does | keep? |
|---|---|---|
| **04_ideology_extended.R** | Ideology consistency across categories and base-vs-boundary; ideology "shifts". | If the base-vs-boundary ideology-shift result is reported. |
| **05_moral_extended.R** | Moral foundations by language × category; foundation co-occurrence. | If the moral co-occurrence result is reported. |

### Study A / Study B — separate experiments, port only if you're re-running them

| script | what it does |
|---|---|
| **archive/pipeline_study_ab/08_study_a_prompt_variance.R** | Picks Study A's frozen 30-prompt subset by cross-model refusal variance. |
| **archive/pipeline_study_ab/10_study_a_panel.R** | Study A jurisdiction-panel `glmer` (45 prompts × 13 models × 3 languages). |
| **archive/pipeline_study_ab/11_study_b_lang_mechanism.R** | Study B: language-register + entity-swap paired mixed models. |

### DeepSeek deep-dive — one finding, many scripts (candidates to consolidate)

| script | what it does |
|---|---|
| **07_deepseek_language_analysis.R** | DeepSeek Chinese-vs-English refusal, tables 35–38 + 1 figure. |
| **08_deepseek_chinese_analysis.R** | Formal tests (chi-square, Fisher, `glmer`, odds ratios) for the DeepSeek gap. |
| **09_deepseek_stats.R** | Re-does those tests PNAS-grade: bootstrap OR CIs, Cramér's V, BH-corrected p-values. |
| **10_ideology_moral_patterns.R** | Ideology variance + moral co-occurrence beyond the libertarian shift. |

These four all interrogate the **same** result (DeepSeek refuses more in
Chinese). If we port, this collapses to **one** Python module: compute the
2×2 tables once, run the tests once, with bootstrap CIs and multiple-comparison
correction built in.

### Inter-rater reliability — port (it's your judge-quality check)

| script | what it does |
|---|---|
| **16_irr_analysis.R** | Cohen's κ (engagement) and Krippendorff's α (ordinal) between the primary judge and a second judge. |
| **archive/pipeline_study_ab/12_stance_analysis.R** | Also computes inter-judge κ for the *stance* pass (primary vs secondary stance judge), plus state-alignment. |

Any credible audit needs an IRR number, so this logic ports regardless of which
figures survive.

### Figure/paper scripts — mostly droppable

| script | what it does | keep? |
|---|---|---|
| **11_visualizations.R** (14 figs) | The main figure set — dotplots with Wilson CIs. | Re-implement in matplotlib **from the ported tables**, not 1:1. |
| **04b / 04c** | Extended + KEY_FINDINGS report figures. | Drop unless those exact figures are needed. |
| **15_pnas_figures.R**, **13**, **14**, **15**, **16** | Paper-specific standalone dotplots for `pnas_paper.tex` / `deepseek_brief.tex`. | **Drop.** These are figure-production for specific old manuscripts. Regenerate fresh figures for the new battery. |

---

## Recommended port (my proposal)

Re-implement as a small Python package, not a 1:1 script translation:

1. **`load.py`** ← `01`. Reads `annotations_all.jsonl`, builds the clean
   DataFrame with the exact `engaged`/`refused`/`dataset_type` derivations and
   fixed categorical orders. **The single source of truth.** Now carries the
   new `topic_domain` field and the `battery` arm tag.
2. **`engagement.py`** ← `02`. Refusal/engagement rates + logistic mixed model
   (`statsmodels`/`bambi`), the DeepSeek language contrast, category splits.
3. **`ideology.py`** ← `03` (+`03b`/`03c` if reported). Ideology + moral
   foundations on engaged answers.
4. **`justifications.py`** ← `05`. Refusal-reason tabulations.
5. **`deepseek.py`** ← `06`+`07`+`07b`+`06b` collapsed. One module: 2×2 tables,
   chi-square/Fisher, bootstrap OR CIs, Cramér's V, BH correction.
6. **`irr.py`** ← `08_irr`+the κ part of `12`. Cohen's κ + Krippendorff's α.
7. **`figures.py`** — fresh matplotlib dotplots (Wilson CIs) built from the
   tables above, replacing `04`/`09`/`13`/`14`/`15`/`16` wholesale.

**Drop:** the Study A/B scripts unless we re-run those experiments; all the
`*_pnas_*` / `*_brief_*` figure scripts (manuscript-specific).

The heavy statistical lift is the **mixed-effects logistic model** (R's
`lme4::glmer`). In Python that's `statsmodels` (`BinomialBayesMixedGLM` /
GEE) or `bambi` (PyMC) — the one dependency choice worth deciding up front.
