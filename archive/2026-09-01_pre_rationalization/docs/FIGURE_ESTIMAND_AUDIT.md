# Figure–estimand crosswalk (superseded figure system)

> Historical review of pre-validity artwork. Current specifications are in [`CANONICAL_FIGURE_LEGENDS.md`](CANONICAL_FIGURE_LEGENDS.md); current findings are in [`CODE_ANALYSIS_AUDIT.md`](CODE_ANALYSIS_AUDIT.md).


> **⚠ DATED RECORD — this audits release `canon_009`.** Its findings drove the
> redesign in `canon_010` and the estimand-driven restructure in `canon_011`,
> after which most of the panels described below no longer exist. It is kept
> because it is the evidence for why they changed, and because its
> panel-by-panel traces are the reason the current figures can be checked
> against their tables at all. **For the current figure set, read
> `docs/CANONICAL_FIGURE_LEGENDS.md`; for the current estimands,
> `docs/CANONICAL_ANALYSES.md`.**

Forensic trace of every panel shipped in release **`canon_009`** (git
`3af636e`, branch `audit/inference-pipeline-review`), performed before any
redesign. Every displayed number was traced back to a canonical table, a row
filter, a weighting target and an uncertainty method. Where that trace could
not be completed mechanically, the panel is marked **NOT PUBLICATION-READY**
and the reason is named.

Source of truth: executable code in `pipeline/20_figures_main.R` and
`pipeline/21_figures_extended.R`, and the CSVs in
`pipeline/estimates/canonical/`. Where `docs/` prose disagreed with the code,
the code was taken as authoritative.

---

## 1. Figure 1 — `Fig1_home_jurisdiction.png` (183 × 109 mm)

### 1a — locator map

| field | value |
|---|---|
| displayed number | none |
| canonical table | none |
| estimand | none — the panel is a coding schematic |
| sample | `rnaturalearth` `ne_countries(scale = "small")`, recoded in the figure script |
| graph type appropriate | yes, but the panel occupies ≈35% of the figure area for zero estimates |
| status | **descriptive, non-inferential; over-allocated area** |

The shaded regions are recoded **in the plotting script** (`20_figures_main.R:57–63`)
from a hard-coded 22-element `ARAB` ISO-3 vector plus `continent == "Europe" &
iso_a3 != "RUS"`. That mapping is *not* read from the analysis data, so nothing
guarantees it matches `region_focus` as coded in `data_clean.RData`. It happens
to agree, but the agreement is unenforced.

### 1b — unadjusted rates

| field | value |
|---|---|
| displayed numbers | 19.6 / 13.6 / 7.5 / 2.6 / 0.0 (filled) and unlabelled hollow points |
| canonical table | `c02_home_descriptive_english.csv` |
| exact row filter | `grouping == "jurisdiction" & quantity == "observed_rate" & weighting == "response" & home_status %in% c("home","away")` |
| estimand | observed refusal rate, `refused_strict = engagement_code >= 4` |
| sample | English only (27,449 rows), General excluded from both arms |
| weighting target | **response-weighted** (every response counts once) |
| conditioning | none |
| estimator | direct sample mean |
| uncertainty | **none displayed** |
| bootstrap cluster | n/a |
| descriptive/inferential | descriptive |
| main or ED | main |

**Forensic answer to the high-priority question.** The values 19.6 / 13.6 / 7.5
/ 2.6 / 0 **are** the canonical Family-A observed *home* rates. They are not
diagonal jurisdiction × region cells and not an `e08`-style historical
quantity. They come from `c02` rows selected on `home_status == "home"`, and
the hollow points come from the same table, same weighting, `home_status ==
"away"`. Confirmed against the raw counts stored on the same rows: CN home
163/832 = 0.19591, CN away 119/3328 = 0.03576.

**Three defects found.**

1. **Only the home endpoint is labelled.** The panel exists to show a contrast
   and numerically annotates an absolute level. Reading it, CN's salient number
   is 19.6, not the +16.0 gap.
2. **The descriptive difference is tabulated with an interval and not plotted
   at all.** `c02` carries `quantity == "home_minus_away"` with a 95%
   issue-cluster bootstrap interval (CN +16.02 [11.89, 20.25]; MENA +5.87
   [3.12, 8.80]; India +0.95 [−2.12, 3.99]; US −0.89 [−2.47, 0.80]; EU 0
   [0, 0]). None of it reaches the figure.
3. **Weighting differs from panel c and this is not stated.** Panel b is
   response-weighted; panel c is nested-weighted. Both are labelled only
   "home − away".

**EU.** Panel b draws EU as a filled point at 0.0 — visually a measured zero.
Panel c of the same figure correctly declares EU non-estimable. One figure
therefore represents the same structural zero two incompatible ways.

### 1c — standardized contrast

| field | value |
|---|---|
| displayed numbers | +16.5 / +3.8 / −3.1 / +1.9 / "not estimable" |
| canonical table | `c04_home_standardized.csv` |
| exact row filter | `weighting == "nested" & estimator == "maximum likelihood" & support == "full target"` |
| estimand | covariate-standardized predictive home−away contrast, probability scale |
| specification | `refused_strict ~ home * model_f + tier + domain + route_f`, fitted **per jurisdiction**; no region term (region determines home within a jurisdiction) |
| estimator | logistic ML, then g-computation: predict all rows as home, again as away, take the weighted difference |
| sample | English, home and away arms only, General excluded; 520 issues per jurisdiction |
| weighting target | nested `w_i = (1/M)(1/I_m)(1/P_mi)` |
| uncertainty | 95% issue-cluster bootstrap, percentile, B = 2,000, fixed draws, failures counted not replaced (`c18`, `failure_rate = 0` for all four) |
| bootstrap cluster | `issue_id`, with `bootstrap_issue_instance` labelling each draw |
| descriptive/inferential | inferential |
| graph type appropriate | yes — dot and interval is correct for this quantity |
| main or ED | main; **this is the headline and should dominate** |

Verified: no stale v1 or v2 numbers. `c04` also holds `support == "common
support"` and `estimator == "Firth penalized logit"` rows, correctly excluded
from this panel and correctly described as a different target population
rather than a robustness check (`c06b`: CN retains 41.3% of nested target
weight under the restriction, MENA 77.1%, India 69.4%, US 91.7%, EU 95.4%).

**Scale defect.** The common linear axis runs to +30 pp to accommodate CN's
upper limit of 24.8. MENA, India and US then occupy the leftmost sixth of the
panel. Legible, but the area allocation is inverted relative to the number of
estimates each region of the axis carries.

**Terminology.** The panel title reads "Standardized predictive contrast" and
the subtitle "not a causal effect". Correct. `c04$causal_interpretation` and
the acceptance test E1 both enforce the absence of unnegated *causal*,
*difference-in-differences* and *within-issue* claims. No violation found.

---

## 2. Figure 2 — `Fig2_language_framing.png` (183 × 117 mm)

### 2a — pooled language contrast

| field | value |
|---|---|
| displayed numbers | Arabic +2.3, Chinese +1.3, Hindi +8.5, Russian +3.9 |
| canonical table | `c08_language_paired.csv` |
| exact row filter | `sensitivity == "primary" & weighting == "equal_model"` |
| estimand | mean paired within-block difference in `refused_strict`, target language minus English |
| block | `model × prompt_id` — same prompt, same model, two languages |
| weighting target | **equal per model** — the predeclared primary (`c08$primary_weighting == "equal_model"` on every row) |
| estimator | direct paired mean; no regression |
| uncertainty | 95% issue-cluster bootstrap, percentile |
| bootstrap cluster | `issue_id` (`c08$bootstrap_unit`) |
| intended block universe | 27,456 = 11 models × 2,496 prompts; missing blocks 16 (zh), 19 (ar), 26 (ru), 54 (hi), reported in `n_missing_blocks` |
| descriptive/inferential | inferential |
| main or ED | main |

Confirmed canonical, not stale. The three weightings agree to within 0.03 pp
(`c08b`), so the choice of primary is not doing work. Panel is sound; the only
issue is that a four-row forest is given equal area to an eleven-row heatmap
carrying far more information.

### 2b — model × language heatmap

| field | value |
|---|---|
| displayed numbers | 44 integer-rounded signed pp values |
| canonical table | `c09_language_by_model.csv` |
| exact row filter | `grouping == "model"` |
| estimand | same paired block difference as 2a, estimated within each model |
| estimator | same direct paired estimator — verified identical, not a regression |
| uncertainty | **not displayed** |
| descriptive/inferential | inferential quantity displayed without uncertainty |
| status | **NOT PUBLICATION-READY as a main panel** |

Four defects, all confirmed numerically.

1. **Colour is dominated by two cells.** `LIM = max|estimate| = 61.36`
   (allam-7b × Hindi). The diverging fill is scaled to ±61.36, so the 30 cells
   with |estimate| < 6 pp occupy the middle 10% of the ramp and are
   indistinguishable.
2. **Precision is hidden.** Per-cell interval half-widths range from 0.00 to
   2.34 pp (median 1.00). The heatmap renders a +4 with a half-width of 2.3
   identically to a +4 with a half-width of 0.5.
3. **Structural zeros are printed as ordinary zeros.** `mistral-large-2512`
   shows `+0` in all four languages. That model produced **zero refusals in any
   language**, so the difference is not a small measured effect — it is
   undefined variation on a constant outcome. The cell is visually identical to
   grok-4.3's genuine −1.
4. **Redundant encoding.** Every cell carries both a printed value and a fill.
   Given (1), the fill adds nothing for 30 of 44 cells.

### 2c — prompt framing

| field | value |
|---|---|
| displayed numbers | All models +0.09; eleven per-model values from −5.61 to +8.25 |
| canonical tables | `c10_framing_paired.csv` (pooled), `c11_framing_by_model_domain.csv` (per model) |
| exact row filters | `c10`: `scope == "overall"`; `c11`: `grouping == "model"` |
| estimand | mean paired boundary-minus-regular difference in `refused_strict` |
| block | `issue × model × language`, **complete 2 regular + 2 boundary only** (6,857 English blocks; 7 incomplete blocks listed by key in `c10b`) |
| weighting | equal per model over block means |
| uncertainty | 95% issue-cluster bootstrap, percentile |
| bootstrap cluster | `issue_id` |
| descriptive/inferential | inferential; per-model rows exploratory |
| main or ED | main |

Sound estimand and correct block rule. The pooled estimate (+0.09 [−0.70,
0.84]) **conceals complete sign reversal across models**: sarvam-30b +8.25
[6.43, 10.03] against falcon3-10b −5.61 [−7.29, −3.61]. The panel does show the
per-model rows, so the reversal is visible, but the display gives the pooled
row and the per-model rows near-equal visual weight and wastes roughly 40% of
its width on empty margin.

`mistral-large-2512` again appears as an exact 0 with a zero-width interval —
a structural zero drawn as a precisely estimated null.

---

## 3. Figure 3 — `Fig3_content.png` (183 × 81 mm)

### 3a — ideology

| field | value |
|---|---|
| displayed numbers | four directional bin shares per dimension; neutral share as text only |
| canonical table | `c12_ideology_distribution.csv` |
| exact row filter | `role == "PRIMARY"`, then `bin != "0"` for the plotted marks |
| estimand | equal-model share in **each of five** categories (−2, −1, 0, +1, +2); the five sum to 1 within dimension (enforced by acceptance H5) |
| sample | English engaged boundary responses in the slant subsample, n = 6,528, **156 of 624 issues** |
| conditioning | **conditional on engagement** — passes 2/3 skip refusals by design |
| weighting | equal per model |
| uncertainty | 95% issue-cluster bootstrap (superpopulation) — plotted; `c12` additionally carries a delete-one-issue jackknife with FPC f = 156/624 on the logit scale (`conf_*_battery`) — not plotted |
| descriptive/inferential | descriptive and explicitly exploratory |
| status | **NOT PUBLICATION-READY — estimand/graphic mismatch** |

**The confirmed defect.** The estimand is a five-category distribution whose
bins sum to one. The graphic plots four of the five bins and prints the fifth
as an annotation. Neutral mass is 92.4% (Economic), 79.5% (Social), 80.5%
(Authority), 79.5% (Populism). The panel therefore allocates 100% of its ink to
between 7.6% and 20.5% of the distribution. A reader who does not read the
grey annotation infers a far more polarised distribution than the estimand
describes. `0` is excluded graphically and included in the denominator.

Reliability is carried correctly and dynamically: `c12$reliability_warning`
reads the panel α out of `e25` per dimension (Economic 0.392, Social 0.126,
Authority 0.232, Populism 0.017).

### 3b — moral-foundation prevalence

| field | value |
|---|---|
| displayed numbers | 60.7 / 49.8 / 47.1 / 14.0 / 8.4 / 3.1 (%) |
| canonical table | `c14_moral_prevalence_equal_model.csv` |
| exact row filter | `scope == "overall"` |
| estimand | prevalence of each of six **non-exclusive** binary indicators |
| weighting | **equal per model** — verified: the eleven `c15` model-level `care_harm` prevalences average to 0.498370, matching `c14` exactly |
| conditioning | conditional on engagement |
| uncertainty | 95% issue-cluster bootstrap, percentile |
| descriptive/inferential | descriptive with sampling uncertainty |
| main or ED | main |

Sound. Ordering is by descending prevalence, which is substantively meaningful.

### 3c — judge agreement

| field | value |
|---|---|
| displayed numbers | PSA mean 0.86 / 0.85 / 0.76 / 0.51 / 0.56 / 0.47 with min–max whiskers |
| canonical tables | `c14` (`psa_mean`, `psa_min`, `psa_max`), sourced from `e25` |
| estimand | **pairwise positive specific agreement**, PSA = 2a/(2a+b+c), mean and range over the 6 judge pairs |
| sample | 6,468 units rated by all four judges |
| uncertainty | **the whiskers are not an interval** — they are the min and max over judge pairs, i.e. instrument variation |
| status | correct quantity, but the in-plot title says only "Judge agreement" |

The panel is on its own 0–1 axis, correctly separated from the prevalence axis.
The min–max range is **not** a confidence interval and the figure does not say
so; the distinction currently lives only in the external legend.

**Prevalence dependence is real and unstated.** Ranking the six foundations by
prevalence and by PSA gives nearly the same order (fairness 0.68/0.86, care
0.50/0.85, liberty 0.49/0.76, authority 0.20/0.51, loyalty 0.15/0.56, sanctity
0.03/0.47). Low agreement on the rare foundations is partly a prevalence
artefact of PSA, not solely a judge-quality finding.

### Layout defect

At final size the panel-a title "Ideological placement: four directional
categories" **collides with the panel-b tag `b`**, and the panel-c title
"Judge agreement" runs to the canvas edge. The rendered-layout section of
`audit_figures.R` measures grob widths against the whole canvas, not against
the panel each grob belongs to, so it does not catch either.

---

## 4. ED1 — `ED1_judge_sensitivity.png` (183 × 86 mm)

| field | value |
|---|---|
| displayed numbers | 16 absolute standardized contrasts (4 judges × 4 estimable jurisdictions), plus a bracket per facet |
| canonical table | `c17b_judge_envelope.csv` |
| exact row filter | points: `estimable & judge_model != "OBSERVED JUDGE POINT ENVELOPE"`; bracket: the envelope row's `point_envelope_low_pp`/`_high_pp` |
| estimand | the Fig 1c standardized contrast, recomputed under each judge |
| sample | **one all-judge common-support sample**: 27,429 of 27,449 English responses, 624 issues, 11 models (`c17c`); per-jurisdiction n identical across judges (CN 4,157; MENA 6,233; India 2,075; US 8,313) — verified by audit check |
| estimator | identical `gcomp()` from `10_canonical_common.R`, shared with `11_canonical_home.R` |
| uncertainty | per-judge 95% issue-cluster bootstrap, B = 600, instrument held fixed |
| bootstrap cluster | `issue_id` |
| descriptive/inferential | inferential |

**Three quantities are stored correctly and kept apart in the table**: each
judge's own sampling interval; the **observed judge point envelope**
(`point_envelope_low/high` = min/max of the four point estimates); and the
**union of the judge-specific 95% intervals** (`union_low/high`), which is
recorded under exactly that name and never called an envelope. `c17b` also
separates `point_sign_stable`, `point_envelope_excludes_zero` and
`union_excludes_zero`. No conflation found.

**But the figure does not answer the sensitivity question.** It plots four
absolute estimates per jurisdiction and asks the reader to difference
overlapping intervals by eye. The quantity of interest —
*how far does the estimate move when the judge changes* — is nowhere
estimated. Differencing the plotted points and reusing their marginal
intervals would be wrong: the four judges label **the same responses**, so
their estimates are strongly positively dependent and a marginal-interval
subtraction would be far too wide.

The "range of judge point estimates" bracket duplicates information already
carried by the four plotted points and adds three line segments and a text
label per facet.

**Consequence:** a paired judge-minus-canonical difference with a *paired*
bootstrap is a **new statistical quantity** and requires an estimation script
and a canonical table. It must not be computed inside a plotting script.

---

## 5. ED2 — `ED2_sensitivity_panels.png` (183 × 208 mm)

| field | value |
|---|---|
| canonical tables | `c07_home_sensitivities.csv` (points), `c04` (dashed primary rules) |
| exact row filter | `estimable`, joined to a seven-row family map; split `kind == "inferential"` (panel a) vs `post-outcome diagnostic` (panel b) |
| estimand | panel a: the same standardized contrast under alternative but comparable specifications; panel b: the same contrast on response-length-filtered subsets |
| uncertainty | 95% issue-cluster bootstrap, B = 500 |
| status | **NOT PUBLICATION-READY** |

**Confirmed defects.**

1. **The "Functional form" facet is empty.** It reserves five labelled rows and
   roughly a sixth of a 208 mm figure, and draws **no marks at all**. The cause
   is a flag inconsistency in `c07`: five rows carry `estimable = TRUE` with
   `estimate_pp = NA`.

   | jurisdiction | level | estimable | estimate_pp | note |
   |---|---|---|---|---|
   | MENA | home × domain | TRUE | NA | UNRELIABLE: 47.2% of draws undefined |
   | MENA | home × route_f | TRUE | NA | — |
   | India | home × route_f | TRUE | NA | — |
   | US | home × domain | TRUE | NA | UNRELIABLE: 16.8% of draws undefined |
   | US | home × route_f | TRUE | NA | — |

   The figure filters on `estimable` and therefore admits rows it cannot draw.
   `estimable` is tracking "the fit was attempted" rather than "an estimate
   exists".

2. **Orientation.** The figure is organised by sensitivity family, so answering
   "is the CN result robust?" requires visiting six facets and picking CN-red
   rows out of each. Jurisdiction is the reader's unit of interest and is the
   within-facet nuisance dimension.

3. **Post-outcome diagnostics share the figure.** Response-length filters
   condition on a realized property of the response. They are correctly
   *labelled* as post-outcome, but placing them under the same figure number as
   the inferential forest invites reading them as robustness checks.

4. The **hierarchical marginal** estimate is correctly excluded and tabulated
   in `c07b`. Verified: it is a different estimand (integrates over the issue
   random effect), and four of five jurisdictions did not converge, so only
   MENA (+3.79, no interval) exists at all.

---

## 6. ED3 — `ED3_language_detail.png` (183 × 107 mm)

| field | value |
|---|---|
| displayed numbers | 44 per-model paired language contrasts with intervals |
| canonical table | `c09_language_by_model.csv`, `grouping == "model"` |
| estimand | identical to Fig 2b — same estimator, same blocks |
| uncertainty | 95% issue-cluster bootstrap, percentile |
| status | correct quantity; **ordering and scale choices conflict with its companion** |

1. **Free x-scales across the four language facets** (`scales = "free_x"`).
   The facets therefore cannot be compared on magnitude, yet magnitude across
   languages — Hindi's dispersion is roughly ten times Chinese's — is the
   pattern the panel exists alongside.
2. **Model ordering does not match Fig 2b.** ED3 orders models by their mean
   effect across languages; Fig 2b orders them by jurisdiction group. The two
   displays of the same 44 numbers cannot be read against each other.
3. The panel is built as `ed4` in the source and saved as `ED3_...`, and the
   weighting-comparison plot `pa` is constructed and then discarded
   (`ed4 <- if (is.null(pb)) pa else pb`). Dead code that a reader of the script
   would take for a shipped panel.
4. `c08b_weighting_comparison.csv` is **written by the plotting script**
   (`21_figures_extended.R:252`), not by an estimation script.

---

## 7. Summary classification

| category | panels |
|---|---|
| **canonical, correct estimand and uncertainty** | Fig1c, Fig2a, Fig2c, Fig3b, Fig3c, ED1 (table), ED3 (values) |
| **canonical values, defective display** | Fig1b (unlabelled contrast, unplotted interval, weighting undeclared), Fig2b (colour saturation, no uncertainty, structural zeros), Fig3a (neutral bin omitted from a distribution estimand), ED2 (empty facet, wrong orientation), ED3 (free scales, ordering mismatch) |
| **stale v1 numbers** | **none found** |
| **historical v2 numbers leaking into a figure** | **none found** |
| **mixed-estimand panel** | **Fig1** — panel b is response-weighted descriptive, panel c is nested-weighted standardized, and the figure labels both "home − away" |
| **inferential quantity displayed without uncertainty** | Fig2b |
| **estimand implemented only in a plotting script** | `c08b` (written by `21_figures_extended.R`); `c07b` (written by `21_figures_extended.R:145`) |

## 8. Panel placement decisions carried into the redesign

| panel | current | decision |
|---|---|---|
| Fig1a map | main, ≈35% area | **remove from the figure set**; region coding documented in the legend and technical reference |
| Fig1b rates | main | keep, both endpoints labelled |
| Fig1b descriptive difference | tabulated only | **promote to a plotted panel** with its existing `c02` interval |
| Fig1c standardized | main | keep, enlarged |
| Fig2a pooled language | main | keep, tightened |
| Fig2b heatmap | main | **relocate to Extended Data**, paired with its intervals |
| model-distribution language plot | does not exist | **new panel**, derived from `c09` + `c08`, no new estimation |
| Fig2c framing | main | keep, pooled made primary |
| Fig3a ideology | main | **re-express as the full five-bin distribution** |
| Fig3b/c foundations + PSA | main | keep, merged into one aligned row-label block |
| ED1 absolute judge estimates | ED | **replace with paired judge-minus-canonical differences** (new estimand, new table) |
| ED2 sensitivities | ED | **re-orient by jurisdiction**; drop non-estimable rows |
| response-length diagnostics | inside ED2 | **separate PNG** |
| ED3 language detail | ED | **merge with the heatmap** into one language-heterogeneity figure |
| reliability metric matrix | does not exist | **new ED figure** from `e23`/`e24`/`e25` — no new estimation |
