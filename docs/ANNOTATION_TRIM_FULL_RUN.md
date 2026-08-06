# Annotation trim: Pass-1-only full run

> **⚠ SUPERSEDED IN PART, 2026-08-04.** Passes 2 and 3 have since been run over
> a **25% issue subsample** of `full_v1` in all five languages, and the slant
> analysis has been reinstated as `pipeline/22_estimates_slant.R` +
> `FIG4_slant_main.png`. See **`docs/SLANT_SUBSAMPLE.md`**, which is
> authoritative for anything to do with passes 2/3.
>
> What still holds from this document: Pass 1 remains the **default** and still
> runs on **100%** of responses; the reasoning below for why Pass 1 alone
> answers the study's primary question is unchanged; the stance stage (Pass 4)
> is **still not run** on the full run.
>
> What is now out of date: the claim that the slant scripts live only in
> `archive/pipeline_slant/` (a selected subset has been folded into
> `pipeline/22_estimates_slant.R`), and any statement that `full_v1` carries no
> ideology or moral-foundation codes.

**Status: APPLIED 2026-07-31.** Pass 1 is now the default in
`scripts/run_pilot.py` and `scripts/annotation_pipeline.py` (`--all-passes`
opts back in; `--pass1-only` is kept as an accepted no-op). The four
slant-only analysis scripts were moved to `archive/pipeline_slant/`, and
`07_deepseek_language_analysis.R` / `16_irr_analysis.R` were trimmed to their
Pass-1 content. **Scope:** the *full run*. `pilot_v1` was annotated with all
four passes and is unaffected -- run the archived scripts against it if slant
is needed.

## Decision

The study's stated interest is **refusal (1/0)** and **the nature of the
refusal**. Both come entirely from annotation **Pass 1**. The ideology pass,
the moral-foundations pass, and the separate stance stage measure the *slant* of
answers the model *did* give — a different research question. For the full run
we drop them.

- **pilot_v1:** run all four stages (`generate annotate assemble stance`) — no
  change. Keeps ideology/MFT/stance so the pilot can still speak to slant if a
  reviewer asks.
- **full run:** run **Pass 1 only** — `engagement_code` (1–5),
  `refusal_justification` (A–G), `refusal_justification_other`. Skip Pass 2
  (ideology), Pass 3 (moral foundations), and the stance stage.

This is **reversible**: raw responses are stored separately from annotations, so
Pass 2/3/stance can be added back later by re-annotating the stored responses.

## What Pass 1 gives you

| Target | Field | Derivation |
|---|---|---|
| Refusal 1/0 | `engagement_code` | `refused = engagement_code >= 4` (in `01_data_loading.R`) |
| Nature — *how* | `engagement_code` | 3 = partial, 4 = soft, 5 = hard refusal |
| Nature — *why* | `refusal_justification` | A neutrality · B complexity · C harm-avoidance · D expertise · E user-autonomy · F none · G other |
| Nature — *why (free text)* | `refusal_justification_other` | when code = G |

Keep the full 1–5 scale — do **not** collapse to binary at annotation time. It
is the same single judge call whether it emits a binary or the gradient, and the
soft-vs-hard distinction is part of "nature of refusal." Collapse to binary only
in analysis (already done: `refused = engagement_code >= 4`).

## What gets dropped (surplus)

| Stage | Fields removed | Judge calls saved |
|---|---|---|
| Pass 2 — ideology | `economic_left_right`, `social_left_right`, `authoritarian_libertarian`, `populist_elitist` | 1 per engaged response |
| Pass 3 — moral foundations | `care_harm`, `fairness_cheating`, `loyalty_betrayal`, `authority_subversion`, `sanctity_degradation`, `liberty_oppression`, `dominant_foundation` | 1 per engaged response |
| Stance stage | `stance_score`, `brief_rationale` | 1 per boundary prompt |

At the assumed ~83% engagement rate this cuts annotation from ~2.7 judge calls
per response to **1** (~2.7×), and removes the entire stance pass over every
boundary prompt. **Generation is untouched** — same responses, same cost.

## Code changes for the full run

### 1. `scripts/annotation_pipeline.py`
The pipeline already short-circuits Pass 2/3 when `engagement_code >= 4`. For the
full run we want them skipped **unconditionally**. Two clean options:

- **(preferred) add a `--passes 1` / `--pass1-only` flag** that returns after
  Pass 1 and writes only the Pass-1 fields in `to_dict()`. Leaves the pilot code
  path intact (default = all passes). This is the smallest, most reversible
  change and keeps one script serving both runs.
- (alternative) a separate `annotate_pass1.py` — more duplication, avoid.

`to_dict()` currently always emits the slant keys (null when skipped). Under
`--pass1-only`, either omit them or leave them null; the R loader tolerates
absent columns (verified — `01_data_loading.R` references none of them).

### 2. `scripts/run_pilot.py`
For the full run, invoke stages **`generate annotate assemble`** (no `stance`),
and pass the pass-1-only flag through to the annotate stage. Keep the pilot_v1
invocation exactly as-is (`generate annotate assemble stance`).

### 3. `scripts/stance_coding.py`
Not called in the full-run stage list. Leave the file in place (pilot still uses
it); it simply isn't invoked.

## R analysis scripts (apply at the full-run analysis stage)

23 scripts in `pipeline/`. Classification by field dependency:

**KEEP (13) — refusal-only, no slant fields:**
`01_data_loading.R`, `02_engagement_analysis.R`, `11_visualizations.R`,
`12_visualizations_extended.R`, `13_report_figures.R`,
`06_refusal_justifications.R` (the A–G "nature of refusal" script),
`08_deepseek_chinese_analysis.R`, `09_deepseek_stats.R`,
`archive/pipeline_study_ab/08_study_a_prompt_variance.R`, `15_finding_figures.R`,
`14_deepseek_brief_figures.R`, plus study-arm scripts `archive/pipeline_study_ab/10_study_a_panel.R`
and `archive/pipeline_study_ab/11_study_b_lang_mechanism.R` (separate arms — review when those arms run).

**DROP (8) — consume only Pass 2 / Pass 3 / stance:**
`03_ideology_analysis.R`, `04_ideology_extended.R`, `05_moral_extended.R`,
`10_ideology_moral_patterns.R`, `archive/pipeline_study_ab/12_stance_analysis.R`,
`archive/pipeline_study_ab/13_deepseek_dotplots.R`, `archive/pipeline_study_ab/14_refusal_vs_engaged_stance.R`,
`archive/pipeline_study_ab/16_engaged_state_alignment.R`.
"Drop" = exclude from the full-run analysis driver; do **not** delete the files
(the pilot still uses them). If there is a master run-list/driver, comment these
out for the full run.

**TRIM (2) — mixed; keep the refusal half, remove the slant block:**
- `07_deepseek_language_analysis.R` — 10 refusal refs + 8 slant refs. Keep the
  language×refusal analysis; strip the ideology block.
- `16_irr_analysis.R` — inter-rater reliability, primary vs second judge; 12
  refusal + 12 slant refs. Keep engagement/refusal IRR; drop the ideology/MFT
  IRR (with Pass 2/3 gone there's no second-judge slant coding to correlate).

## Order of operations (when the full run is greenlit)

1. Add `--pass1-only` to `annotation_pipeline.py`; default behavior unchanged.
2. Point the full-run `run_pilot.py` invocation at
   `generate annotate assemble` with `--pass1-only`.
3. Run full generation + Pass-1 annotation.
4. For analysis: run the 13 KEEP scripts + the 2 TRIMMED scripts; skip the 8
   DROP scripts. Confirm no KEEP script silently expects a now-absent column.
5. Sanity check: `annotations_all.jsonl` should carry only the Pass-1 fields
   plus provenance; `refused` still derives cleanly in `01_data_loading.R`.

## What the trimmed study can and cannot say

- **Can:** refusal rates and refusal *nature* (soft/hard, A–G reasons) by model,
  developer jurisdiction, and prompt language — the core question.
- **Cannot:** anything about the *direction* of lean when the model engages
  (left/right, authoritarian/libertarian, moral framing, stance on boundary
  prompts). The legacy repo was named `aligned_to_whom`; that alignment/slant
  angle is exactly what Pass 2/3/stance provided. Dropping them narrows the
  study to refusal behavior. Reversible via re-annotation if the paper later
  wants the slant back.
