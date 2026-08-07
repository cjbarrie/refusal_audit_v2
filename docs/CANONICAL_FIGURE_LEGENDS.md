# Canonical figure legends

Publication legends for `pipeline/figures/main/` (Fig 1–3) and
`pipeline/figures/extended/` (ED1–ED3). The figures carry short panel titles
only; everything a reader needs beyond the axes is here.

Every figure is a **single 600 dpi RGB PNG** and nothing else — no PDF, no SVG,
no EPS. Widths are 183 mm (double column). Type is 5–7 pt at final size, panel
labels 8 pt bold; nothing is below 5 pt.

Numbers below are filled from the release named in
`pipeline/estimates/canonical/c00_manifest.csv`. Where a legend quotes an n, it
is the n on which that panel's estimate was computed.

---

## Figure 1 · Home-jurisdiction asymmetry

**a**, Issue regions. The six issue regions used throughout; `General` issues
(22,868 responses) belong to no region and are neither home nor away for any
model. The panel orients the reader and carries no estimate.

**b**, **Unadjusted** English refusal rates on away issues (hollow) and home
issues (filled), one row per jurisdiction, from `c02`. Rates are response-weighted
over all English responses in that jurisdiction's arm. **This is a description of
the corpus, not an effect**: home and away issue sets differ in topic domain,
prompt tier and seed route, so the gap mixes model behaviour with issue
composition.

**c**, Covariate-standardized home−away contrast, from `c04`. **The full-target
estimate is the headline and the only one shown here.**
*Outcome*: `refused_strict`, the judge's engagement code 4 or 5.
*Sample*: English only, home and away arms, General excluded.
*Estimand*: per jurisdiction, `refused_strict ~ home * model + tier +
topic_domain + route` fitted by maximum likelihood, then g-computation on the
probability scale — predict every observation as if home, again as if away, and
take the weighted difference.
*Weighting*: nested — equal mass per model, then equal per issue within model,
then equal per prompt within model×issue.
*Interval*: 95% issue-cluster bootstrap, 2,000 draws, percentile. Each replicate
resamples whole issues, labels each draw so a twice-drawn issue keeps its copies
distinct, and refits and re-standardizes inside the replicate. A fixed number of
draws is taken; failures are counted and reported, never replaced.
*Region fixed effects are excluded*: within a jurisdiction, region determines
home status, so the two are not separately identified.
**EU is not estimable** — Mistral produced zero refusals in both arms — and is
shown as a flagged row, never as zero.
**This is not a causal effect.** Home is a fixed property of an issue's region;
nothing randomises it. Standardization adjusts for measured composition only.

**The common-support estimand is NOT shown here, and it is not a robustness
check.** It is a different target population: restricting to covariate cells
present in both arms retains only **41% of the nested target weight for CN**,
77% for MENA, 69% for India, 92% for US and 95% for EU (`c06b`,
`unsupported_target_weight`). The CN estimate is numerically almost unchanged
under the restriction (+16.5 → +16.6), which is reassuring about functional
form, but the non-extrapolative target is a substantially smaller population.
That comparison, with retained weight annotated, and the Firth penalized-logit
sensitivity, are Extended Data.

**The inferential pattern to report**: CN and MENA are clearly positive under
the main estimators; India is borderline and changes interval status between
maximum likelihood and Firth; US is uncertain; EU is not estimable. India should
not be presented as a directional headline.

---

## Figure 2 · Language and prompt framing

**a**, Paired difference in refusal between each tested language and English,
from `c08`.
*Block*: model × prompt_id. Within a block the same prompt reaches the same model
in both languages, so prompt content is held fixed by construction.
*Estimand*: mean paired difference, **equal weight per model** — the predeclared
primary weighting. Pooled and equal-per-model×issue weightings are tabulated in `c08b`.
*Sample*: all four non-English languages are shown, including those whose
intervals cover zero. Incomplete blocks are counted in `c08`
(`n_missing_blocks`) rather than dropped silently.
*Interval*: 95% issue-cluster bootstrap, percentile, bootstrap unit `issue_id`.
*Languages are listed alphabetically.* English is the paired reference by design,
which is a property of the estimand, not a ranking of languages.
**This is not the causal effect of a user's language.** It is the effect of
delivering the tested translation, and it assumes translation equivalence and no
language-specific provider, run-time or annotation drift.
**No judge-sensitivity estimate exists for this quantity**: the judge panel
covers English only, and re-labelling one arm compares two instruments rather
than perturbing one.

**b**, The same paired differences by model, from `c09`, printed in every cell so
the value does not depend on reading a colour. Shading is redundant with the
printed number. Intervals are ED3. Rows are grouped by jurisdiction in a fixed
order, not ordered by their own effects.

**c**, Paired boundary-minus-regular framing difference, from `c10` and `c11`.
*Block*: issue × model × language.
*Primary rule*: **complete blocks only — exactly 2 regular and 2 boundary
prompts.** Seven English blocks are incomplete and are listed by key in `c10b`;
the looser rule that keeps them is a labelled sensitivity row in `c10`.
*The block holds the issue and the model fixed; it does NOT hold prompt content
fixed* — the regular and boundary variants are different realized prompts about
the same issue, which is the exposure being varied. A causal reading requires the
generated variants to be exchangeable given the issue, which is an assumption
about the generation template, not a randomisation.
Rows are ordered by their own estimate; the pooled row is pinned last.

---

## Figure 3 · Content of engaged responses

**Both panels are conditional on engagement.** The judge skips these passes for
refusals, so the denominator is engaged responses. Because refusal itself varies
by model and jurisdiction, this conditioning is not ignorable and these panels
say nothing about what a refused response would have contained.

**a**, Ideological placement, from `c12`. The estimand is the **equal-model share
in each of the five categories** (−2, −1, 0, +1, +2); every bin carries its own
interval and the five sum to one within each dimension. The panel plots the
**four directional categories** with the neutral share annotated: with 80–92% of
mass at neutral, a stacked bar rendered the directional categories — the ones the
five-bin estimand exists to show — as slivers. The signed mean is in `c12` as
secondary only.
*Endpoints are dimension-specific*: economic left↔right, social
progressive↔traditional, authority authoritarian↔libertarian, populism
populist↔elitist. Generic left/right labels are not used on the last three,
because the codebook makes no such mapping.
*Sample*: English engaged boundary responses in the slant subsample, 156 of the
624 issues. Other languages are excluded for incomplete coverage (`c12b`).
*Interval*: issue-cluster bootstrap for the issue superpopulation. `c12` also
reports a frozen-battery interval from a delete-one-issue jackknife with a finite
population correction for f = 156/624; for a share it is computed on the logit
scale so the limits stay inside [0, 1], and the raw unbounded normal limits are
retained alongside in `conf_*_battery_unbounded`. Negative probability limits are
never plotted.
**Descriptive and exploratory.** Panel Krippendorff's α is read from `e25` for
the run and written into `c12$reliability_warning`; for the current release it is
economic 0.39, social 0.13, authority 0.23, populism 0.02. Social, authority and
populism carry no substantive weight. Judge sensitivity for these outcomes is in
`c19`.

**b**, Moral foundations invoked, from `c14`. Six **non-exclusive binary
indicators** — a response can invoke several or none — so they do not form a
composition and are never plotted as shares of a whole. Equal weight per model;
issue-cluster bootstrap intervals.

**c**, Judge agreement for the same six foundations, on its **own 0–1 axis** in an
aligned column. This is **pairwise positive specific agreement**, 2a/(2a+b+c),
mean and range over judge pairs (`e23b`, `e25`). It is reported as a number with
no acceptance threshold: none is preregistered, and an earlier version's 0.35
cut-off was invented here. Printing it beside the prevalence points, as an
earlier version did, put two different quantities on one axis.

---

## ED1 · Judge sensitivity

The standardized contrast of Fig 1c recomputed under each judge, from `c17b`.
**Every judge is recomputed on ONE common-support sample** — the four-judge
intersection, 27,429 of 27,449 English responses — so a difference between judges
is not a difference in sample. `c17c` reports rows, issues, models, events by arm,
response coverage and retained target weight for every comparison, pairwise and
all-judge.

**Three quantities, kept apart.** Coloured bars are each judge's **own
issue-cluster sampling interval**, with the instrument held fixed. The thin
bracket above them spans the **range of the judges' point estimates** — the
instrument-variation quantity, which contains no sampling uncertainty. `c17b`
additionally records `union_low`/`union_high`, the union of the judge-specific
95% intervals, under exactly that name; it is never called an envelope and never
treated as an interval with coverage for judge uncertainty. An earlier version
shaded that union and labelled it the observed judge envelope, which conflated
the two.

`c17b` reports `point_sign_stable` (all judges agree on direction),
`point_envelope_excludes_zero`, and `union_excludes_zero` as separate columns.

## ED2 · Sensitivity of the standardized contrast

**Split by kind.** Panel a holds **inferential sensitivities** — alternative but
comparable estimators of the same target: model composition, prompt tier,
language, outcome definition, functional form (`home × domain`, `home × route`
where estimable) and the support restriction. Panel b holds **post-outcome
data-quality diagnostics**: response-length filters condition on a property of
the response, i.e. after the outcome, so they are not design robustness.
The dashed rule in each panel is the primary estimate for that jurisdiction, and
only for jurisdictions the panel contains.

The **hierarchical marginal** estimate is not in either forest. It is a different
estimand — it integrates over the issue random effect instead of standardizing
over the observed issue set — and has no comparable interval, so it is tabulated
in `c07b` rather than shown as a competing point.

Some functional-form specifications are hard to estimate in every resample; where
the failure rate exceeds the threshold the interval is withheld and the row is
marked `interval_reliable = FALSE` rather than reported.

## ED3 · Language detail

Per-model paired language contrasts with intervals — the values behind the Fig 2b
heatmap. These 44 model × language cells are **exploratory**: they are not
multiplicity-adjusted, and a cell whose interval excludes zero is not a
confirmatory test.

The weighting comparison is a **table** (`c08b`), not a panel: pooled,
equal-per-model and equal-per-model×issue agree to within a fraction of a
percentage point, so the figure space goes to the per-model intervals instead.

## Retired: the refusal-text projection

The UMAP figure no longer ships. Neighbourhood purity in the embedding space was
0.57 against 0.44 at random, and the lexical TF-IDF representation reached 0.58 —
so a figure built to show that the reason codes track meaning showed that they
track wording at least as well. It was also never rebuilt by the release driver.
Script and outputs: `pipeline/archive/exploratory_umap/`.

---

## What each legend must state

Every legend above states: exact n and number of issues (in the referenced
table); sample and exclusions; outcome definition; estimand and weighting;
interval and bootstrap unit; the incomplete-block rule where one applies;
conditioning on engagement where it applies; the judge and common-support caveat;
and the meaning of every visual encoding.
