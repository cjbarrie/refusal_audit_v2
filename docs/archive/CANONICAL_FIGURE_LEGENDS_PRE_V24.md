# Canonical figure legends

**This is the single authoritative caption document.** Publication legends for
`pipeline/figures/main/` (Fig 1–3) and `pipeline/figures/extended/` (ED1–ED10).

The figures carry **panel letters, axis labels, tick labels, category names,
facet headings, compact legends and direct numeric labels — and nothing else**.
No titles, no subtitles, no methodological prose inside a plotting region.
Everything a reader needs beyond the axes is here. `audit_figures.R` fails the
build if any figure script passes `title=`, `subtitle=` or `caption=`, or if a
banned prose string appears in a plotting specification.

Every figure is a **single 600 dpi RGB PNG** and nothing else — no PDF, no SVG,
no EPS, no TIFF, and no one-column variant. Width is 183 mm (double column) for
all thirteen. Height is one of four approved canvases — 62, 85, 125 or 165 mm —
and the audit checks both the pixel dimensions and the `pHYs` resolution
metadata, because a large raster without `pHYs` is placed at 72 dpi by a
journal's layout software.

Numbers below are filled from the release named in
`pipeline/estimates/canonical/c00_manifest.csv`. Where a legend quotes an n, it
is the n on which that panel's estimate was computed.

**Three encodings are constant across the whole set and carry no legend:**
* an **interval** is thin, dark and centred on its estimate; a **paired
  connector** is thicker, much paler, and runs only between two paired
  endpoints;
* a **structural zero** — a model or jurisdiction that produced no original judge-coded non-engagement events at
  all, so the contrast does not exist — is drawn as a hollow square with the
  words `not estimable`, never as a point at zero with a zero-width interval;
* **colour never carries two meanings in one figure.** Jurisdiction hues are
  reserved for jurisdictions and for models keyed to their developer's
  jurisdiction (ED4, ED6); ideology bins have their own diverging palette
  (Fig 3a, ED5); original non-engagement propensity has a perceptually-uniform sequential scale
  (ED8, ED9); Fig 1 and Fig 2 use red and blue redundantly with circle and
  triangle to separate genuine refusal from capability failure; ED1, ED2 and
  ED3 use no hue because position, shape and fill already carry the distinction.

**Row order is fixed centrally** in `pipeline/_orders.R` — models, languages,
jurisdictions, ideology bins and foundations — and is never re-derived from the
estimates being displayed. An order computed from the data makes the ranking a
property of the thing shown, so the strongest cells always drift to one end and
the layout implies a finding.

---

## Figure 1 · Home-jurisdiction asymmetry under corrected measurement

183 × 85 mm. One horizontal forest compares the same covariate-standardized
home-minus-away association under three outcome measurements: original
judge-coded non-engagement (grey square), GPT-5.6 Sol-reference DSL genuine
refusal (red circle), and DSL capability failure (blue triangle). Marks are
dodged within each of five developer jurisdictions and share a percentage-point
axis and zero line. The display range is −15 to +25 percentage points. An
outward arrow marks an interval endpoint beyond that range; the exact uncapped
bounds remain in `c25` and must be reported in the source-data table.

*Sample*: English home/away responses, with `General` excluded. *Estimand*: per
jurisdiction, solve the linear moment equation
`X'(Y-X beta)-1e-8 P beta=0`, where `X = home*model + tier + domain + route`,
then g-compute the home-minus-away difference over the full eligible target
using equal-model → equal-issue → equal-prompt weights. For corrected outcomes,
`Y` is the rectified DSL pseudo-outcome; for the original row it is
`engagement_code >= 4`. Pseudo-outcomes are not clipped to `[0,1]`.

DSL uncertainty combines whole-issue bootstrap, Rao–Wu phase-two SRSWOR
replicates, and variance over ten issue-level cross-fitting partitions. Original
rows use the issue bootstrap only. Whiskers are 95% max-|t| simultaneous bands
across the five jurisdictions separately within each outcome family, rather
than pointwise intervals or one joint band over all 15 marks.

Home status is a fixed issue property, not randomized. Every mark is therefore
a **covariate-standardized predictive association**, not a causal effect. Sol is
a blinded machine reference rather than human ground truth. The decomposition
shows whether the historical non-engagement pattern is attributable to coherent
noncompliance or to wrong-language, incoherent, or technically degenerated
output; it must not be described as merely changing the refusal denominator.

---

## Figure 2 · Language

183 × 85 mm. One horizontal point-interval plot compares two mechanisms for
each non-English language: **genuine refusal** (circle, red) and **capability
failure** (triangle, blue). Both use one shared percentage-point x scale and a
common zero line. The artwork contains no title, subtitle, caption, prose, or
significance marks.

*Estimand*: rectified DSL target-language minus English prevalence difference on
the fixed common `(model, prompt_id)` roster, first paired within prompt/model
and then averaged with equal weight per model. The reference design includes a
census of original code-4/5 rows and a stratified SRSWOR control sample with
known inclusion probabilities. *Outcomes*: clean genuine refusal and capability
failure from `c24`; original judge-coded non-engagement remains a separately
labelled measurement sensitivity. *Interval*: 95% max-|t| simultaneous band
across the four languages, computed separately for each outcome. DSL uncertainty
combines whole-issue bootstrap, Rao–Wu phase-two SRSWOR replicates, and variance
over ten issue-level cross-fitting partitions.

Colour is semantic and redundant with shape; it does not identify language or
jurisdiction. All four languages use the same axis, so magnitude is directly
comparable. This is the prompt-fixed effect of delivering the tested
translation among tested prompts/models—not the causal effect of a user's
language. Translation equivalence and absence of language-specific routing,
runtime, and measurement drift remain assumptions.

These are GPT-5.6 Sol-reference DSL estimates, not dual-judge adjudications and
not human ground truth. Release-specific values must be quoted only after the
full `canon_014` run passes acceptance and figure audit.

---

## Figure 3 · Content of engaged responses

183 × 85 mm. **All three panels are conditional on engagement.** The judge skips
these passes for refusals, so the denominator is engaged responses; because
refusal itself varies by model and jurisdiction, **this conditioning is not
ignorable** and these panels say nothing about what a refused response would
have contained. They are not unconditional model behaviour.

**a**, Ideological placement, from `c12` (`role == "PRIMARY"`). The estimand is
the **equal-model share in each of five categories** (−2, −1, 0, +1, +2); the
five sum to one within each dimension, enforced by acceptance H5. **All five
bins are drawn** as a 100% stacked distribution, so the neutral category
occupies the row in the proportion it occupies the data: 92% economic, 80%
social, 80% authority, 80% populism. Segments at or above 8% carry their value.
*Cost of this encoding, stated*: a composition cannot carry a per-bin interval.
The intervals are in `c12` — both the issue-cluster bootstrap for the issue
superpopulation and, for the frozen 624-issue battery, a delete-one-issue
jackknife with FPC (f = 156/624) computed on the logit scale.
*Endpoints are dimension-specific* and printed at the row ends: economic
left↔right, social progressive↔traditional, authority authoritarian↔libertarian,
populism populist↔elitist. Generic left/right is not used on the last three.
*Sample*: English engaged boundary responses in the slant subsample, n = 6,528,
**156 of the 624 issues**. See `CANONICAL_ANALYSES.md` §9 on why the content
estimators are English-only.
**Descriptive and exploratory.** Panel Krippendorff's α is read from `e25`:
economic 0.39, social 0.13, authority 0.23, populism 0.02. Social, authority and
populism carry no substantive weight. Per-model detail is ED5.

**b** and **c** are **one aligned compound block**: a single row-label column,
two value columns, one shared row order (descending prevalence).

**b**, Moral foundations invoked, from `c14` (`scope == "overall"`). Six
**non-exclusive binary indicators** — a response may invoke several or none — so
they never form a composition. Equal weight per model; the eleven per-model
prevalences in `c15` average exactly to the plotted value.
*Interval*: 95% issue-cluster bootstrap **sampling** interval. Per-model detail
is ED6.

**c**, Agreement on the same six foundations, on its own 0–1 axis. **Pairwise
positive specific agreement**, PSA = 2a/(2a+b+c), mean over the six judge pairs,
with a **min–max range across pairs** (n = 6,468 units rated by all four judges).
**The range is not a confidence interval** — it is variation across instruments
and has no coverage. It is drawn with end ticks in lighter ink, deliberately
unlike the dark centred sampling intervals in column b.
**PSA is prevalence-sensitive**: ranking the foundations by prevalence and by PSA
gives nearly the same order, so low agreement on the rare foundations is partly a
property of the statistic. The full metric suite is ED7.

---

## ED1 · Judge sensitivity

183 × 62 mm. **The paired difference between each alternative judge and the
canonical judge**, from `c17d`, in one forest with jurisdiction row groups and a
**common x-axis**.

*Quantity*: Δ = θ̂_alternative − θ̂_canonical, where θ̂ is the Fig 1 standardized
contrast.
*Sample*: one **all-judge common-support** sample — the four-judge intersection,
27,429 of 27,449 English responses, 624 issues, 11 models (`c17c`). Per
jurisdiction: CN 4,157 rows, MENA 6,233, India 2,075, US 8,313. Every judge is
recomputed on it, so a difference between judges is not a difference in sample.
*Estimator*: the identical `gcomp()` shared with `11_canonical_home.R`.
*Interval*: 95% **paired** issue-cluster bootstrap, B = 600, percentile. One
issue set is resampled per replicate, **every judge's contrast is recomputed on
that same draw**, and the difference is taken **inside** the replicate. Fixed
draws; failures counted, never replaced; a replicate in which any judge is
undefined fails for all of them. Zero replicates failed.
**This is why it is not the difference of two `c17b` intervals.** The judges
label the same responses, so their estimates are strongly dependent; the paired
intervals are 16–49% as wide as the naive combination, and acceptance H9 fails
the build if they are not narrower.
*Zero* means the alternative judge reproduces the canonical judge on the same
sample. It does **not** mean either is correct: the canonical judge
(`google/gemini-2.5-flash-lite`) is a **reference instrument, not ground truth**.
No human-validated labels exist and no majority vote is computed anywhere.
**No separate canonical reference line is drawn** — zero already is it.
EU is not estimable under any judge and is omitted.
Absolute per-judge estimates, the observed judge point envelope, and the union of
judge intervals are three further quantities, kept apart in `c17b`.

**What it shows**: for MENA all three alternative judges sit below the canonical
judge and all three differences exclude zero; for India none differ from zero.

## ED2 · Focused estimator, support and outcome sensitivity

183 × 62 mm. **Four specifications per jurisdiction, and only four.** Shape marks
what changed:

| mark | specification | what changes |
|---|---|---|
| filled diamond | ML, full target (`c04`) | — the primary estimate |
| hollow circle | Firth penalized logit, full target (`c04`) | **estimator**, same target |
| filled square | common support (`c04`) | **target population** |
| hollow triangle | `refused_any`, codes 3–5 (`c07`) | **outcome definition** |

*Interval*: 95% issue-cluster bootstrap.

**These are not all alternative estimators of one estimand.** Only the Firth row
holds the target fixed. Common support restricts to covariate cells present in
both arms and therefore describes a **different population** — one that retains
41% of CN's nested target weight (`c06b`). `refused_any` changes the label
threshold.

**Overlapping intervals here are not a test of equality** between
specifications, and no such test is offered.

**The full grid is a table, not a figure**: `c07c_sensitivity_catalogue.csv`
classifies every sensitivity row as A estimator / B target population /
C outcome definition / D model roster / E post-outcome diagnostic / F different
estimand, with `difference_from_primary_pp`, counts, convergence and estimability
flags. It holds the language and prompt-tier restrictions, the nine
leave-one-model-out fits, the functional-form specifications and the
response-length thresholds. `difference_from_primary_pp` is a **difference of
point estimates**; no interval is attached to it, because subtracting marginal
endpoints is not a paired contrast and the paired bootstrap that would be
required is not run for those rows.

**Response-length filters are post-outcome** — they condition on a realized
property of the response — and are class E in `c07c`, not a robustness check and
not a figure. **The hierarchical marginal estimate** is class F, a different
estimand that integrates over the issue random effect; it is in `c07b`, and in
release `canon_012` **none of the five fits converged** (EU is separated, the
other four report `did not converge`). MENA converged in the previous release at
+3.79 pp with no change to the data in between, so the specification is unstable
across runs as well as being a different target.

## ED3 · Issue-subsample stability

183 × 165 mm. **a**, For each estimand, the median across 500 subsample
replicates (dark line) with the **p10–p90** band (mid grey) and **p2.5–p97.5**
band (light grey), against sample fraction; the accent rule is the full-sample
estimate. **b**, An aligned strip showing the **sign-agreement rate** with the
full-sample estimate.

**The bands are NOT confidence intervals.** They are across-subsample ranges
describing design stability: how much the estimate moves when the issue battery
is smaller. A bootstrap resamples with replacement at full size to approximate
sampling uncertainty; this resamples **without** replacement at reduced size to
describe the effect of adding issues.

*Resampling unit*: the **issue**. A sampled issue carries all of its prompts,
tiers, languages, models and annotations, so the paired blocks stay intact.
*Design*: simple random sampling without replacement within each of nine
**topic-domain strata**; allocation `min(n_h, max(1, ⌈f·n_h⌉))`. Within a
replicate each stratum is permuted **once** and every fraction is a **prefix** of
that permutation, so smaller samples are subsets of larger ones and a trajectory
reads as the effect of adding issues.
*Fractions*: 10–90% plus a deterministic 100% endpoint. 500 replicates per
fraction. Master seed 20260809, replicate seeds `MASTER_SEED + r`.
*Refitting*: the full canonical model is refitted inside every sampled issue set;
no full-sample coefficient is held fixed.
*Estimability* 97.8% overall, convergence 99.99% (`c21_subsample_summary.csv`).

**Not shown here**: the content estimands (ideology, foundations, PSA) and the
detailed per-fraction diagnostics — median absolute and RMS deviation from the
full sample, within-tolerance rates at prespecified 1/2 pp and 0.02/0.05
thresholds, failure counts. All are in `c21_subsample_summary.csv`. Structural
zeros (EU) have no stability to display and are omitted.

## ED4 · Model × language heterogeneity

183 × 85 mm. The 44 per-model paired language contrasts from `c09`
(`grouping == "model"`) with **95% issue-cluster bootstrap intervals**, four
language facets, fixed model rows, **one common x-axis**.

The common scale is deliberate: Hindi disperses roughly ten times more than
Chinese, and per-facet scaling would delete exactly that. Cells beyond ±15 pp are
labelled directly. Colour is the model's developer jurisdiction.

**One display, not two.** The heatmap that used to accompany this is gone — the
exact values are in `c09`, so the figure spends its space on the uncertainty the
table cannot show. Interval half-widths range from 0.0 to 2.3 pp (median 1.0), so
cells with equal values do not carry equal precision.

**Exploratory**: these cells are not multiplicity-adjusted, and a cell whose
interval excludes zero is not a confirmatory test. The weighting comparison is
`c08b`.

**Fig 2 now shows these same cells hierarchically; this is the flat, complete
view.** Figure 2 groups the 44 cells under their jurisdiction and pooled
aggregates on one shared scale, which necessarily compresses the near-zero
region. ED4 keeps every cell in a per-language facet at full precision, which is
where to read the small contrasts Figure 2 cannot separate.

**The largest cells are the least interpretable.** allam-7b's Hindi and Russian
contrasts are the extremes of this display, and 53.9% and 78.7% of that model's
refusals in those languages are ones the judge itself calls incoherent. They
measure a capability failure, not a refusal behaviour. See
`docs/RESPONSE_VALIDITY.md` before reading any row of this figure.

## ED5 · Ideological slant by model

183 × 85 mm. The **five-bin composition** for every model × dimension, from
`c13` (`role == "PRIMARY"`). Four dimension facets, eleven fixed model rows,
100% stacked.

The composition is the primary estimand and is what is drawn; a signed mean alone
would collapse a distribution that is 80–92% neutral into one number. The signed
mean is in `c13` as `role == "SECONDARY"`, with its own intervals.

**Every model-level row carries uncertainty in the table**: issue-cluster
bootstrap (`conf_low`/`conf_high`) and delete-one-issue jackknife with FPC
(`conf_low_battery`/`conf_high_battery`), plus `n`, `n_issues`, `n_missing`,
`degenerate_outcome`, `support_ok` and `interval_reliable`. Intervals are not
drawn on a stacked composition; read them from `c13`.

**Conditional on engagement, descriptive and exploratory**, with the weak
reliability of §Fig 3a. **Do not read a developer-jurisdiction effect off these
model comparisons** — jurisdiction is entangled with the observed model roster,
and `c13$jurisdiction_caveat` says so on every row.

## ED6 · Moral foundations by model

183 × 85 mm. Per-model prevalence for each of the six foundations, from `c15`,
with **95% issue-cluster bootstrap intervals**. Six facets, eleven fixed model
rows, common percentage scale. Colour is the model's developer jurisdiction. The
equal-model aggregate (`c14`) is a thin dashed rule, deliberately subordinate to
the model estimates.

Six **non-exclusive** indicators; conditional on engagement. `c15` additionally
carries the frozen-battery jackknife interval and the estimability flags. **Do
not read a jurisdiction effect off these comparisons.**

## ED7 · Measurement reliability

183 × 85 mm. Every annotated construct against **four agreement statistics**,
from `e23` (engagement), `e24` (refusal justification) and `e25` (ideology and
moral foundations): raw agreement, Krippendorff's α, Gwet AC1 (nominal/binary) or
AC2 (ordinal weights), and pairwise positive specific agreement. One shared
row-label column; no stems.

**The statistics are not commensurable and are not put on a shared axis.**
Engagement has α = 0.51 and Gwet AC1 = 0.97 on the same labels, because α's
chance correction collapses when one category dominates and refusal is 4.0%
prevalent. Rare constructs are where the metrics diverge most, which is why they
are shown side by side rather than one being chosen.

**PSA is defined only for binary constructs** — it is agreement on *positive*
labels — so its column carries an em dash for the ordinal ideology scales and the
nominal justification code. That is a property of the statistic.

`all_rater_positive_unanimity` in `e23`/`e25` is a **different statistic**: among
units any judge called positive, the share where all judges agreed. It falls
mechanically as judges are added and is not comparable across constructs rated by
different numbers of judges.

## ED8 · Prompt-semantic geometry

183 × 125 mm. **Five panels, one per delivered language**, over **one fixed set
of prompt coordinates** (`c22`) — the same construction as ED9, which panels the
same geometry by model.

*Unit*: the prompt (2,496), not the response.
*Geometry*: a single 2-D UMAP fitted once on the English prompt text
(`uwot`, seed 20260809, n_neighbors 25, min_dist 0.15, cosine metric) and
**reused in every panel**. No facet refits the projection; separately fitted maps
are not geometrically comparable. `audit_figures.R` enforces this by parsing the
figure script and refusing to find a projection call in it.
*Embedding*: `openai/text-embedding-3-small` at 512 dimensions, on the English
prompt with the boundary directive prefix stripped — it opens all 1,248 boundary
prompts identically and would otherwise separate tiers on template wording.
Cached by `scripts/embed_prompts.py`; the release calls no API.

**Encoding: grey is the semantic universe, red is original judge-coded non-engagement.** Every prompt is a
tiny light-grey point. A prompt with **non-zero** refusal propensity carries a
red disc on top whose **area** is proportional to that propensity; a prompt no
model refused in that language gets no red disc at all. The red is additionally
darkened with propensity — a **redundant** second channel on the same number,
which is why it has no key of its own.

*What is plotted*: original non-engagement **propensity**, equal weight per jurisdiction with
models nested equally within jurisdiction. Not a binary "ever refused": a prompt
one of eleven models declined must not look like one all eleven declined.

**The magnitude is never binned.** Area is a continuous function of propensity;
the legend prints four reference sizes (5%, 10%, 25%, 50%) purely so a reader can
calibrate. Cutting propensity into high/low would invent a threshold the
estimand does not have.

**Why this replaced a continuous fill ramp.** The previous version coloured the
entire cloud on a magma scale, which required reading a colour value off every
point and made "no refusal at all" and "a little refusal" nearly indistinguishable.
Under the grey/red split, the absence of refusal is legible at a glance — and in
English that is most of the map.

**Why the pooled map is not a panel.** Only 1.8% of prompts have zero pooled
propensity, so a grey/red contrast over the pooled quantity would be red almost
everywhere and would carry no information. The pooled values remain in `c22`
(`refusal_propensity_all`).

**The zero share is itself the cross-language descriptive pattern**: 68.0% of prompts have
zero original non-engagement propensity in English, 52.4% in Chinese, 44.9% in Arabic, 26.3% in
Russian and **11.9% in Hindi**. The grey visible in each panel is that number.
Read it with `docs/RESPONSE_VALIDITY.md`: red can represent coherent refusal,
substantive pivot, or capability failure.

**Diagnostics, from `c22_prompt_umap_diagnostics.csv`.** Neighbourhood
preservation at k = 15 is 0.395. Topic-domain neighbourhood purity is **0.649
against a shuffled baseline of 0.117**, so the map does recover the topic
structure. Across three alternative seeds, Procrustes RMSE is 0.37–0.42 while
neighbour overlap is 0.65–0.67: **read neighbourhoods, not absolute positions or
distances**. A 3 × 3 hyper-parameter grid gives preservation 0.30–0.44. No
near-duplicate prompts and no missing embeddings.

**Exploratory and descriptive.** It establishes no causal effect and validates no
taxonomy. Representative regions and their medoid prompts are selected
deterministically and tabulated in `c22_prompt_umap_regions.csv`; full prompt
text is never printed on the point cloud.

## ED9 · Prompt-semantic geometry by model

183 × 125 mm. The **same fixed coordinates**, one panel per model in fixed order,
English only. In one language a single model either received an original non-engagement code or did not,
so the encoding is **binary by construction** and is drawn as two levels rather
than a continuous ramp that would imply a gradation that does not exist. The
continuous cross-model propensity is ED8.

## ED10 · Prompt framing

183 × 62 mm. Paired boundary-minus-regular difference in refusal. The pooled
estimate (`c10`, `scope == "overall"`) is the larger ink diamond above a rule;
the eleven per-model estimates (`c11`, `grouping == "model"`) are below it in a
fixed model order and are **exploratory heterogeneity, not eleven findings**.

*Block*: issue × model × language, **complete 2 regular + 2 boundary only**
(6,857 English blocks). Seven incomplete English blocks are listed by key in
`c10b`; the looser rule is a labelled sensitivity row in `c10`.
*Interval*: 95% issue-cluster bootstrap, percentile, bootstrap unit `issue_id`.

*The block holds the issue and the model fixed; it does NOT hold prompt content
fixed* — the regular and boundary variants are different realized prompts about
the same issue, which is the exposure being varied.

**mistral-large-2512 is marked `not estimable`**, not drawn at zero: it refused
in neither arm, so the difference is structural rather than a precise null.

**Moved here from Figure 2, with nothing changed about the estimand.** Framing
is a different exposure answered by a different block from the language
contrast, and pairing the two forced both into a half-height panel. At full
width the per-model rows are legible, which they were not before.

**The pattern to report**: the pooled framing effect is +0.09 pp — effectively
nil, with an interval of [−0.70, +0.84] — while individual models range from
−5.61 (falcon3-10b) to +8.25 (sarvam-30b), and seven of the ten
estimable models have intervals excluding zero in one direction or the other. As with language, the
aggregate conceals the models, and the near-zero pooled estimate is a
cancellation rather than an absence of framing effects.

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
