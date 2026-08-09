# Canonical figure legends

**This is the single authoritative caption document.** Publication legends for
`pipeline/figures/main/` (Fig 1–3) and `pipeline/figures/extended/` (ED1–ED5).

The figures carry **panel letters, axis labels, tick labels, category names,
facet headings, compact legends and direct numeric labels — and nothing else**.
No titles, no subtitles, no methodological prose inside a plotting region.
Everything a reader needs beyond the axes is here. `audit_figures.R` fails the
build if any figure script passes `title=`, `subtitle=` or `caption=`, or if a
banned prose string appears in a plotting specification.

Every figure is a **single 600 dpi RGB PNG** and nothing else — no PDF, no SVG,
no EPS, no TIFF, and no one-column variant. Width is 183 mm (double column) for
all eight. Height is one of four approved canvases — 62, 85, 125 or 165 mm —
and the audit checks both the pixel dimensions and the `pHYs` resolution
metadata, because a large raster without `pHYs` is placed at 72 dpi by a
journal's layout software.

Numbers below are filled from the release named in
`pipeline/estimates/canonical/c00_manifest.csv`. Where a legend quotes an n, it
is the n on which that panel's estimate was computed.

**Two encodings are constant across the whole set and carry no legend:**
* an **interval** is thin, dark and centred on its estimate; a **paired
  connector** is thicker, much paler, and runs only between two paired
  endpoints;
* a **structural zero** — a model or jurisdiction that produced no refusals at
  all, so the contrast does not exist — is drawn as a hollow square with the
  words `not estimable`, never as a point at zero with a zero-width interval.

---

## Figure 1 · Home-jurisdiction asymmetry

183 × 85 mm. Three panels, **row-aligned**: each jurisdiction occupies the same
horizontal band throughout, so one region can be followed across all three.

**The alignment is graphical only. Panels a and b are descriptive and
response-weighted; panel c is model-based and nested-weighted. They are three
different quantities.** The panel letters, the three different axis titles, and
the hollow (descriptive) versus filled (standardized) markers all mark that
apart. Aligning them does not make them the same estimand, and panel c is not
an improved version of panel b.

**a**, **Unadjusted** English refusal rates, from `c02`
(`grouping == "jurisdiction"`, `quantity == "observed_rate"`,
`weighting == "response"`). Hollow point = away issues, filled point = home
issues; **both endpoints are labelled**, and the two marks are named directly on
the top row. Rates are response-weighted over all English responses in that
jurisdiction's arm. *Outcome*: `refused_strict`, the judge's engagement code 4
or 5. **This is a description of the corpus, not an effect**: home and away
issue sets differ in topic domain, prompt tier and seed route, so the gap mixes
model behaviour with issue composition. EU recorded zero refusals in both arms
and is shown as a structural zero.

**b**, The **unadjusted** home-minus-away difference, from `c02`
(`quantity == "home_minus_away"`, `weighting == "response"`).
*Interval*: 95% issue-cluster bootstrap, percentile, bootstrap unit `issue_id`.
Hollow markers, matching panel a: this is the descriptive gap with its sampling
uncertainty, and no adjustment of any kind. It is the deterministic difference
of the two endpoints in panel a.

**c**, **Covariate-standardized** home−away contrast, from `c04`. **The
full-target estimate is the headline and the only one shown here**, and it is
given the most width in the figure.
*Outcome*: `refused_strict`.
*Sample*: English only, home and away arms, General excluded; 520 issues per
jurisdiction.
*Estimand*: per jurisdiction, `refused_strict ~ home * model + tier +
topic_domain + route` fitted by maximum likelihood, then g-computation on the
probability scale — predict every observation as if home, again as if away, and
take the weighted difference.
*Weighting*: nested — equal mass per model, then equal per issue within model,
then equal per prompt within model × issue.
*Interval*: 95% issue-cluster bootstrap, 2,000 draws, percentile. Each replicate
resamples whole issues, labels each draw so a twice-drawn issue keeps its copies
distinct, and refits and re-standardizes inside the replicate. A fixed number of
draws is taken; failures are counted and reported, never replaced.
*Region fixed effects are excluded*: within a jurisdiction, region determines
home status, so the two are not separately identified.
**EU is not estimable** — Mistral produced zero refusals in both arms — and is
shown as a flagged row, never as zero.
**This is not a causal effect.** Home is a fixed property of an issue's region;
nothing randomises it. It is not a difference-in-differences and not a
within-issue contrast. Standardization adjusts for measured composition only.

**The locator map is no longer part of this figure.** It carried no estimate and
occupied roughly a third of the area. The region coding it showed is a
data-coding fact: `China`, `India`, `US`, `Europe` (excluding Russia), and
`Arab` (the 22 Arab League states, displayed as *MENA* so the issue region reads
against the MENA jurisdiction it is the home region of). `General` issues
(22,868 responses) belong to no region and are neither home nor away for any
model.

**The common-support estimand is NOT shown here, and it is not a robustness
check.** It is a different target population: restricting to covariate cells
present in both arms retains only **41% of the nested target weight for CN**,
77% for MENA, 69% for India, 92% for US and 95% for EU (`c06b`,
`unsupported_target_weight`). The CN estimate is numerically almost unchanged
under the restriction (+16.5 → +16.6), which is reassuring about functional
form, but the non-extrapolative target is a substantially smaller population.
That comparison, and the Firth penalized-logit sensitivity, are ED2.

**The inferential pattern to report**: CN and MENA are clearly positive under
the main estimators; India is borderline and changes interval status between
maximum likelihood and Firth; US is uncertain; EU is not estimable. India should
not be presented as a directional headline.

---

## Figure 2 · Language and prompt framing

183 × 125 mm. Panels a and b are the **same estimand at two levels of
aggregation**, on the same four language rows, read across: the aggregate on the
left, the spread it summarises on the right. They are two panels rather than one
because the pooled effects span 1.3–8.5 pp while the per-model effects span
−6 to +61 pp, and one axis cannot serve both.

**a**, Pooled paired difference in refusal between each tested language and
English, from `c08` (`sensitivity == "primary"`, `weighting == "equal_model"`).
*Block*: model × prompt_id. Within a block the same prompt reaches the same model
in both languages, so prompt content is held fixed by construction.
*Estimand*: mean paired difference, **equal weight per model** — the predeclared
primary weighting (`c08$primary_weighting`). Pooled and equal-per-model×issue
weightings are tabulated in `c08b`; the three agree to within 0.03 pp.
*Sample*: all four non-English languages are shown, including those whose
intervals cover zero. Blocks are counted, not silently dropped: of an intended
27,456 blocks (11 models × 2,496 prompts), 16 are missing for Chinese, 19 for
Arabic, 26 for Russian and 54 for Hindi (`c08$n_missing_blocks`).
*Interval*: 95% issue-cluster bootstrap, percentile, bootstrap unit `issue_id`.
*Rows are ordered by the pooled estimate*, derived from the table rather than
typed in. English is the paired reference by design, which is a property of the
estimand, not a ranking of languages.
**This is not the causal effect of a user's language.** It is the effect of
delivering the tested translation, and it assumes translation equivalence and no
language-specific provider, run-time or annotation drift.
**No judge-sensitivity estimate exists for this quantity**: the judge panel
covers English only, and re-labelling one arm compares two instruments rather
than perturbing one.

**b**, The **same paired estimator** applied within each model, from `c09`
(`grouping == "model"`), on **one shared x-axis across all four languages**.
Hindi genuinely disperses about ten times more than Chinese; normalising each
language separately would delete exactly that. Point colour is the model
developer's jurisdiction. Only models beyond ±20 pp are directly labelled.
Vertical offsets within a row are a **deterministic function of rank**, applied
so that the near-zero cluster reads as nine models rather than three; they carry
no meaning. `mistral-large-2512` returned zero refusals in every language, so
its paired difference is undefined rather than null, and it is drawn as a
structural zero. **These 44 model × language cells are exploratory**: they are
not multiplicity-adjusted, and their intervals are ED4.

**c**, Paired boundary-minus-regular framing difference, from `c10`
(`scope == "overall"`, the pooled diamond) and `c11` (`grouping == "model"`).
*Block*: issue × model × language.
*Primary rule*: **complete blocks only — exactly 2 regular and 2 boundary
prompts**; 6,857 English blocks qualify. Seven English blocks are incomplete and
are listed by key in `c10b`; the looser rule that keeps them is a labelled
sensitivity row in `c10`.
*The block holds the issue and the model fixed; it does NOT hold prompt content
fixed* — the regular and boundary variants are different realized prompts about
the same issue, which is the exposure being varied. A causal reading requires the
generated variants to be exchangeable given the issue, which is an assumption
about the generation template, not a randomisation.
**"All models" is the estimate**; it is drawn as a larger accent diamond above a
separator rule. The eleven per-model rows below it are **exploratory
heterogeneity, not eleven findings**, and are ordered by their own estimate.
The pooled estimate conceals complete sign reversal across models — sarvam-30b
+8.3 pp against falcon3-10b −5.6 pp — which is why the per-model rows are shown
rather than summarised. `mistral-large-2512` is again a structural zero.

---

## Figure 3 · Content of engaged responses

183 × 85 mm. **All three panels are conditional on engagement.** The judge skips
these passes for refusals, so the denominator is engaged responses. Because
refusal itself varies by model and jurisdiction, this conditioning is not
ignorable and these panels say nothing about what a refused response would have
contained.

**a**, Ideological placement, from `c12` (`role == "PRIMARY"`). The estimand is
the **equal-model share in each of the five categories** (−2, −1, 0, +1, +2);
the five sum to one within each dimension, which acceptance test H5 enforces.
**All five bins are drawn**, as a 100% stacked distribution per dimension, so
the neutral category occupies the panel in the proportion it occupies the data:
92% economic, 80% social, 80% authority, 80% populism. A previous version
plotted only the four directional bins and printed the neutral share as an
annotation, which gave 100% of the ink to between 8% and 20% of the
distribution. Segments at or above 8% carry their value printed inside them.
*Cost of this encoding, stated plainly*: a stacked composition cannot carry a
per-bin interval. The intervals are in `c12` — both the issue-cluster bootstrap
for the issue superpopulation and, for the frozen 624-issue battery, a
delete-one-issue jackknife with a finite population correction for f = 156/624,
computed on the logit scale so the limits stay inside [0, 1], with the raw
unbounded normal limits retained in `conf_*_battery_unbounded`.
*Endpoints are dimension-specific* and are printed at the ends of each row:
economic left↔right, social progressive↔traditional, authority
authoritarian↔libertarian, populism populist↔elitist. Generic left/right labels
are not used on the last three, because the codebook makes no such mapping.
*Sample*: English engaged boundary responses in the slant subsample, n = 6,528,
**156 of the 624 issues**. The content estimators are English-only by
construction (`13_canonical_content.R` fixes `lang == "en"`). Coverage is not the
whole reason: it is complete for English *and Hindi*, 98.9% for Chinese, 95.4%
for Arabic and 68.3% for Russian (`c12b`). See `CANONICAL_ANALYSES.md` §9.
**Descriptive and exploratory.** Panel Krippendorff's α is read from `e25` for
the run and written into `c12$reliability_warning`; for the current release it
is economic 0.39, social 0.13, authority 0.23, populism 0.02. Social, authority
and populism carry no substantive weight. Judge sensitivity for these outcomes
is in `c19`. The signed mean is in `c12` as `role == "SECONDARY"` only.

**b** and **c** are **one aligned compound panel**: a single row-label column,
two value columns, one shared row order (descending prevalence). The category
names are written once.

**b**, Moral foundations invoked, from `c14` (`scope == "overall"`). Six
**non-exclusive binary indicators** — a response can invoke several or none — so
they do not form a composition and are never plotted as shares of a whole.
Equal weight per model; the eleven per-model prevalences in `c15` average
exactly to the value plotted here. *Interval*: 95% issue-cluster bootstrap
sampling interval.

**c**, Agreement on the same six foundations, on its **own 0–1 axis**. This is
**pairwise positive specific agreement**, PSA = 2a/(2a+b+c), computed for each of
the six judge pairs and shown as the mean with a **min–max range over pairs**
(`c14$psa_mean`, `psa_min`, `psa_max`, from `e25`; n = 6,468 units rated by all
four judges). **The range is not a confidence interval**: it is variation across
instruments and has no coverage. It is drawn with end ticks in a lighter ink,
deliberately unlike the dark centred sampling intervals in column b. It is
reported as a number with no acceptance threshold: none is preregistered, and an
earlier version's 0.35 cut-off was invented here.
**PSA is prevalence-sensitive.** Ranking the six foundations by prevalence and by
PSA gives nearly the same order, so the low agreement on the rare foundations —
sanctity 3% prevalence, PSA 0.47 — is partly a property of the statistic, not
solely a judge-quality finding. The full metric suite is ED5.

---

## ED1 · Judge sensitivity

183 × 85 mm. **The paired difference between each alternative judge and the
canonical judge**, from `c17d`. Four facets, one per estimable jurisdiction.

*Quantity*: Δ_{j,r} = θ̂_{j,r} − θ̂_{canonical,r}, where θ̂ is the Fig 1c
standardized contrast.
*Sample*: **one all-judge common-support sample** — the four-judge intersection,
27,429 of 27,449 English responses, 624 issues, 11 models (`c17c`). Per
jurisdiction: CN 4,157 rows, MENA 6,233, India 2,075, US 8,313. Every judge is
recomputed on it, so a difference between judges is not a difference in sample.
*Estimator*: the identical `gcomp()` from `10_canonical_common.R`, shared with
`11_canonical_home.R`, so a judge-sensitivity result can never be a
specification difference wearing a judge's name.
*Interval*: **95% paired issue-cluster bootstrap**, B = 600, percentile. In each
replicate one issue set is resampled, **every judge's contrast is recomputed on
that same draw**, and the difference is taken **inside the replicate**. Fixed
number of draws; failures counted, never replaced; a replicate in which any
judge is undefined fails for all of them.
**This is why the interval is not the difference of two intervals in `c17b`.**
The four judges label the same responses, so their estimates are strongly
positively dependent; differencing point estimates and carrying marginal
intervals would give an interval far too wide. Acceptance test H9 fails the
build if the paired interval is not narrower than the naive combination.
*Zero* means the alternative judge reproduces the canonical judge's estimate on
the same sample. It does **not** mean either is correct: **the canonical judge
(`google/gemini-2.5-flash-lite`) is a reference instrument, not ground truth.**
No human-validated labels exist, no judge is known to be correct, and no
majority vote is computed anywhere in this layer.
EU is not estimable under any judge and is omitted from the facets.

**Three related quantities are kept apart, and only one of them is plotted
here.** `c17b` holds the other two: each judge's **own** issue-cluster sampling
interval with the instrument held fixed, and the **observed judge point
envelope** (`point_envelope_low`/`_high`, the min and max of the four point
estimates — instrument variation, containing no sampling uncertainty). `c17b`
additionally records `union_low`/`union_high`, the union of the judge-specific
95% intervals, under exactly that name; **the union is never called an envelope**
and is never treated as an interval with coverage for judge uncertainty.
`c17b` reports `point_sign_stable`, `point_envelope_excludes_zero` and
`union_excludes_zero` as three separate columns.

The bracket spanning the range of judge point estimates has been removed from
the figure: with every judge's deviation drawn, it restated the spread of the
points beneath it.

## ED2 · Inferential robustness of the standardized contrast

183 × 165 mm. **Organised by jurisdiction, not by specification family**, from
`c07` with the primary estimate from `c04` as the dashed accent rule in each
facet. The reader's question is "is the CN conclusion robust?", and the previous
layout required visiting six family facets and picking the CN rows out of each.

Within each jurisdiction, rows are grouped by what is being varied: **model
composition** (leave one model out), **prompt tier**, **language**, **outcome
definition** (`refused_any`, codes 3–5), **functional form** (`home × domain`,
`home × route`) and the **support restriction**. Row order inside a family is
fixed by the table, not by the estimates, so the layout never implies a finding.
*Interval*: 95% issue-cluster bootstrap, B = 500.

**These are alternative but comparable estimators of the same target.**
Post-outcome diagnostics are not here — they are ED3.

**Rows without an estimate are omitted and counted, not given empty space.** A
row is drawn only if it has both a point and an interval. `c07$estimable`
records that a fit was attempted, not that an estimate exists: five
functional-form rows carry `estimable = TRUE` with no estimate (MENA and US
`home × domain` failed in 47.2% and 16.8% of draws respectively; MENA, India and
US `home × route` produced none). A previous version filtered on that flag and
reserved a whole empty facet for them. The count per family is printed in the
facet corner.

The **hierarchical marginal** estimate is in neither this figure nor ED3. It is a
different estimand — it integrates over the issue random effect instead of
standardizing over the observed issue set — and it has no comparable interval,
so it is tabulated in `c07b`. Four of five jurisdictions did not converge; only
MENA has a value (+3.79 pp, point only).

## ED3 · Post-outcome data-quality diagnostics

183 × 62 mm. The standardized contrast recomputed on responses above a minimum
character length (20, 50, 100), from `c07` (`sensitivity == "min_response_chars"`),
one facet per jurisdiction, with the primary estimate as the dashed accent rule.

**These are not robustness checks of the design.** A response-length filter
conditions on a realized property of the response — that is, on something
determined after the outcome — so it can induce exactly the kind of selection it
is meant to rule out. It has its own figure number because sharing one with the
inferential forest is itself a claim of kinship.

## ED4 · Language heterogeneity

183 × 125 mm. The two panels are **designed as a pair** and share model order,
language order and spelling exactly, so the cognitive map between them is
immediate.

**a**, The model × language matrix of paired contrasts from `c09`
(`grouping == "model"`), with the signed value printed in every cell so it never
depends on reading a colour. Rows are grouped by jurisdiction in a **fixed**
order, never ordered by the effects being displayed. **The colour scale is set
by the 85th percentile of |estimate|, not by the maximum**: scaling to
max|estimate| = 61.4 pp pushed the 30 cells below 6 pp into the middle tenth of
the ramp, where they were indistinguishable. Cells beyond the limit are squished
to the endpoint colour and still carry their printed value, so saturation is
lost but no information is. `mistral-large-2512` is a structural zero and is
excluded from the scale.

**b**, The same 44 estimates with their **95% issue-cluster bootstrap
intervals** — the uncertainty the matrix cannot show. Interval half-widths range
from 0.0 to 2.3 pp (median 1.0), so cells with equal values do not carry equal
precision. **Free x-scales across the four language facets are deliberate**:
this panel's task is within-language model comparison and interval width, and
the cross-language magnitude comparison is panel a's job. One panel is not asked
to do both tasks poorly.

**Exploratory.** These cells are not multiplicity-adjusted, and a cell whose
interval excludes zero is not a confirmatory test. The weighting comparison is a
**table** (`c08b`), not a panel: pooled, equal-per-model and
equal-per-model×issue agree to within a fraction of a percentage point.

## ED5 · Measurement reliability

183 × 165 mm. Every annotated construct against **four agreement statistics**,
from `e23` (engagement), `e24` (refusal justification) and `e25` (ideology and
moral foundations): raw agreement, Krippendorff's α, Gwet AC1 (nominal/binary) or
AC2 (ordinal weights), and pairwise positive specific agreement.

**A single "agreement" axis would imply these are interchangeable, and this run
shows plainly that they are not**: engagement has α = 0.51 and Gwet AC1 = 0.97
on the same labels, because α's chance correction collapses when one category
dominates — and refusal is 4.0% prevalent. Rare constructs are where the metrics
diverge most, which is why they are shown side by side rather than one being
chosen.

**PSA is defined only for binary constructs** — it is agreement on *positive*
labels — so its column is empty for the ordinal ideology scales and for the
nominal justification code. That is a property of the statistic and is marked as
such rather than left blank.

`all_rater_positive_unanimity` is reported in `e23`/`e25` alongside PSA and is a
**different statistic**: among units any judge called positive, the share where
all judges agreed. It falls mechanically as judges are added, so it is not
comparable across constructs rated by different numbers of judges. It was once
reported under the name `positive_specific_agreement`; it now carries a name
that says what it is.

**Refusal-justification codes (A–G) carry no canonical estimand.** Their
agreement is the weakest of any construct here (α = 0.32, raw agreement 0.20 on
595 units), which is the reason.

---

## Retired: the refusal-text projection

The UMAP figure no longer ships. Neighbourhood purity in the embedding space was
0.57 against 0.44 at random, and the lexical TF-IDF representation reached 0.58 —
so a figure built to show that the reason codes track meaning showed that they
track wording at least as well. It was also never rebuilt by the release driver.
Script and outputs: `pipeline/archive/exploratory_umap/`.

## Not figures

`c20_figure_layout_main.rds` and `c20_figure_layout_extended.rds` are **audit
artefacts, not publication artwork**. They hold the assembled ggplot/patchwork
objects so `audit_figures.R` can measure the rendered layout — text grobs wider
than the canvas, panels below a usable width — instead of grepping source code
for font sizes. They live in the estimates directory; the figure tree holds PNGs
and nothing else.

## What each legend must state

Every legend above states: exact n and number of issues (in the referenced
table); sample and exclusions; outcome definition; estimand and weighting;
estimator; interval type and bootstrap unit; the block definition and
incomplete-block rule where one applies; the support restriction where one
applies; conditioning on engagement where it applies; exploratory status;
identification limits; the judge and common-support caveat; and the meaning of
every visual encoding.
