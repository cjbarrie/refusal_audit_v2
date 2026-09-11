# Final audit — what changed, why, and what remains

Companion to `docs/FIGURE_SYSTEM_MEMO.md` (the pre-implementation forensic
memo). Written after implementation, 2026-08-04.

Pipeline state: **11 scripts ok, 1 skipped (IRR — no second judge exists),
0 failed**, 10.1 min. **18 figures**, all PNG / 7.20 in / 600 dpi / white
background, rendered directly. `pipeline/audit_figures.R` **passes**.

---

## 1. Did any conclusion change?

**No headline conclusion changed. Two were strengthened and one caveat was
added.**

| conclusion | before | after |
|---|---|---|
| Home-region sensitivity is a China result | asserted from a pooled jurisdiction contrast | **strengthened** — holds independently in *both* Chinese models |
| MENA's home effect collapses under the primary estimand | stated | unchanged; now also null for all three MENA models separately |
| India reverses sign and rests on one model | stated | unchanged |
| US is approximately null | stated | **qualified** — the null conceals real heterogeneity (GPT-5.1 −2.3 pp, CI excludes 0) |
| EU is a structural zero | stated | unchanged |
| Boundary framing moves refusal in both directions | stated | **qualified** — for 3 of 10 models the shift includes zero |
| Ideology is overwhelmingly neutral | stated | unchanged, but the *graphic* no longer overstates it |

## 2. Statistical corrections made

1. **Per-model home premium added** (`e21`, `P12`). The primary
   `home × jurisdiction` specification assigns every model in a jurisdiction the
   *identical* fitted contrast — DeepSeek and Qwen both returned exactly 17.5514.
   The previous reassurance that "response weighting and equal-model weighting
   agree" was therefore **vacuous**: a property of the specification, not
   evidence. Fitting `home × model` makes the within-jurisdiction spread visible
   and answers the weighting question for real (`e22`).
2. **Estimand and uncertainty now labelled precisely.** The home premium is
   **sample-conditional** (averaged over observed issues at the fitted BLUPs) and
   its interval propagates **fixed-effect uncertainty only**, with the random
   effects held fixed. Both are stated in the estimate tables (`estimand_type`,
   `uncertainty`) and the caption. A full bootstrap over `theta` was considered
   and **rejected**: it would change the estimand to a population-marginal one
   rather than merely widen the interval.
3. **Refusal justification recoded 7 → 5, not 7 → 4.** Judge code G ("other") is
   15.7% of English refusals and its free text is heterogeneous — degenerate
   output, explicit task refusals, and epistemic statements all land there.
   Merging it with F ("none given") created a category meaning two incompatible
   things and hid a measurement failure mode, worst for allam-7b (31.7% of 426
   refusals). Also documented: `epistemic` is effectively code D alone (B and E
   fire on two responses each).
4. **Domain × tier model-specification sensitivity** (`e12b`). Treating the 11
   purposively selected models as fixed rather than random moves every domain
   shift by ≤ **0.15 pp**, so the random intercept is retained and the choice is
   documented as immaterial rather than assumed.
5. **Ideology reported with the full summary it needs** (`e16b`): n, issues,
   models, mean, median, neutral share, non-neutral share, and both pole shares,
   so no figure can show a mean without its denominator context. Model-level
   decomposition added (`e16c`).
6. **Moral foundations: pooled reference and equal-model weighting** (`e17b`,
   `e17c`). Jurisdiction is *defined by* model membership, so a model-adjusted
   jurisdiction contrast is **not identified**; these are labelled descriptive.
7. **Diagnostics exported** (`23_diagnostics.R`, `d01`–`d08`): engagement-code
   frequency, justification codes raw and collapsed, ideology distribution and
   neutral prevalence, moral co-occurrence, missingness split into structural vs
   incidental, per-cell denominators, and weighting structure.

## 3. Bugs found and fixed

Five were live in the previous figures; three were invisible to the old audit.

1. **FIG2A rows were misaligned by one.** The shift panel dropped the
   non-estimable model, so every shift lined up against the wrong model —
   Sarvam's +6.8 appeared on Mistral's row. Two causes: the panels resolved
   different factor orders, and a top legend on one panel only made the panel
   bodies different heights. Fixed with an explicit `limits =` on both panels and
   `guides = "collect"`.
2. **FIG3 segment labels sat on the wrong segments.** Mapping `colour` inside
   `geom_text` introduces a second grouping variable; `position_stack` then
   orders labels by that group while `geom_col` orders by fill. Fixed with an
   explicit `group = reason`. **The old audit check missed this because it
   omitted the `colour` aesthetic** — the check now builds the plot with the
   figure's real aesthetics.
3. **FIG3 legend order was the reverse of the drawn stack order.**
4. **FIG2A had overprinted text** — the "not estimable" key and the "shift (pp)"
   header collided.
5. **P5 had colliding boundary ticks** — DeepSeek's `40` met Qwen's `0` as "400".
6. **P12's legend carried a stray "a" glyph** from the text layer.
7. **Numeric y-positions on discrete scales** errored under ggplot2 4.0
   (annotations now anchor to real factor levels); patchwork's `&` no longer
   dispatches and was replaced with `plot_annotation`.

## 4. Figure-system changes

- **FIG1** is now map / (estimand comparison | raw matrix). The standalone
  primary-premium panel was removed from the figure — panel B already shows the
  primary estimate *with* its interval, so a separate panel of the same numbers
  was redundant. It remains as `P2`. EU appears in both statistical panels.
  Home cells carry a small jurisdiction-coloured dot rather than a heavy outline
  on the whole diagonal; the EU column renders as structurally empty rather than
  as five ordinary zeros. The connector in panel B carries an arrowhead pointing
  at the primary estimate, and the label identifies each value by its own mark
  (`○` / `●`) instead of asserting a direction in text that contradicted the
  geometry.
- **FIG2** gained the interval on the quantity it is about. Previously the shift
  was bare text, so three null shifts were drawn identically to a large one.
- **FIG3** gained a fifth category and a legend that matches the bars.
- **FIG4A** was rebuilt. The previous diverging-bar form removed the neutral
  category from the bars and printed it marginally, so bar length represented
  only the non-neutral remainder on a ±13% axis — overstating ideological content
  to any reader who did not parse the side column. It is now the directional mean
  with its interval, on a ±0.225 axis, with the neutral share adjacent. The full
  five-category distribution moved to `P9_ideology_distribution.png`.
- **FIG4B** gained a pooled reference rule, because the dominant pattern is
  between foundations, not between jurisdictions.

## 5. Alternatives considered and rejected

| alternative | why rejected |
|---|---|
| Broken-axis dumbbell in FIG1B | distorts; the single axis proved legible |
| Cleveland dot matrix for FIG1C | heatmap reads faster and the cells are the point |
| 2×2 interaction plot for P5 | emphasises slopes, inviting the additivity overreading the analysis explicitly warns against |
| Marimekko for FIG3 | overweights denominators, harms model comparison |
| Stacked/composition forms for moral foundations | invalid — not mutually exclusive (1.83 per response) |
| Full parametric bootstrap over `theta` | changes the estimand rather than widening the interval |
| Model fixed effects for moral foundations | absorbs jurisdiction entirely — not identified |
| Ridgelines / violins for 5 discrete ideology codes | inappropriate for 5 discrete levels |
| Dropping the locator map | retained at author's request; kept as a slim, subordinate strip |

## 6. Limitations that remain

1. **No inter-rater reliability.** Single judge, no second pass. The largest gap,
   and worst for ideology, justification and moral foundations.
2. **Ideology's near-null is not self-interpreting.** Consistent with genuinely
   neutral answers *and* with a conservative judge. Undecidable in this design.
3. **Slant rests on 156 issues** and is conditional on engagement.
4. **Rare outcome.** ~5.4% refusal; 8 of 70 plotted cells have zero events.
5. **Single-model jurisdictions.** India and EU are one model each; nothing about
   them generalises to a jurisdiction.
6. **English-only primary estimates.** For FIG1–3 this is comparability; for FIG4
   it is a composition constraint.
7. **Generation incomplete** for Russian and Hindi on the four self-hosted models.
   English is complete and the primary estimates will not move.
8. **Descriptive, not causal**, throughout.

## 7. Known inconsistency awaiting a decision

The FIG1 locator labels the Arab-League region **MENA** (per author request, to
read against the MENA jurisdiction column), while the panel C axis still labels
the same region **Arab** (the underlying `region_focus` level). Both names appear
in one figure for one region. Either rename the region level throughout — which
touches `REGION_LEVELS`, `PAL_REGION` and `HOME_REGION` — or revert the map label.
Flagged rather than resolved unilaterally because it changes a data-level
vocabulary, not just a caption.
