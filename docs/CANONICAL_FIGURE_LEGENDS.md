# Canonical figure legends

Publication legends for `pipeline/figures/main/` (Fig 1–3) and
`pipeline/figures/extended/` (ED1–ED4). The figures carry short panel titles
only; everything a reader needs beyond the axes is here.

Every figure is exported as **PDF, SVG and PNG from the same ggplot object**:
editable vector art with text kept as text and Helvetica embedded, plus a 600 dpi
RGB preview. Widths are 183 mm (double column). Type is 5–7 pt at final size,
panel labels 8 pt bold; nothing is below 5 pt.

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

**c**, Covariate-standardized home−away contrast, from `c04`.
*Outcome*: `refused_strict`, the judge's engagement code 4 or 5.
*Sample*: English only, home and away arms, General excluded.
*Estimand*: per jurisdiction, `refused_strict ~ home * model + tier +
topic_domain + route` fitted by maximum likelihood, then g-computation on the
probability scale — predict every observation as if home, again as if away, and
take the weighted difference.
*Weighting*: nested — equal mass per model, then equal per issue within model,
then equal per prompt within model×issue.
*Two estimands are shown.* **Full target** (circle) standardizes over the whole
arm and **extrapolates** into covariate cells observed in only one arm; the share
of target weight in such cells is reported per jurisdiction in `c04`
(`degenerate_prediction_weight`) and is substantial for India. **Common support**
(triangle) first restricts to cells present in both arms, defined jointly over
model × topic domain × route × tier, then standardizes; `c06b` reports the rows,
issues, cells and target weight retained.
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

---

## Figure 2 · Language and prompt framing

**a**, Paired difference in refusal between each tested language and English,
from `c08`.
*Block*: model × prompt_id. Within a block the same prompt reaches the same model
in both languages, so prompt content is held fixed by construction.
*Estimand*: mean paired difference, **equal weight per model** — the predeclared
primary weighting. Pooled and equal-per-model×issue weightings are ED4.
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
printed number. Intervals are ED4.

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
interval and the five sum to one within each dimension. The signed mean is
reported in `c12` as secondary only.
*Endpoints are dimension-specific*: economic left↔right, social
progressive↔traditional, authority authoritarian↔libertarian, populism
populist↔elitist. Generic left/right labels are not used on the last three,
because the codebook makes no such mapping.
*Sample*: English engaged boundary responses in the slant subsample, 156 of the
624 issues. Other languages are excluded for incomplete coverage (`c12b`).
*Interval*: issue-cluster bootstrap for the issue superpopulation; `c12` also
reports a frozen-battery interval from a delete-one-issue jackknife with a finite
population correction for f = 156/624.
**Descriptive and exploratory.** Panel Krippendorff's α by dimension is roughly
economic 0.36, social 0.13, authority 0.20, populism −0.04. Social, authority and
populism carry no substantive weight.

**b**, Moral foundations invoked, from `c14`. Six **non-exclusive binary
indicators** — a response can invoke several or none — so they do not form a
composition and are never plotted as shares of a whole. Equal weight per model;
issue-cluster bootstrap intervals.
*PSA* printed beside each point is **pairwise positive specific agreement**,
2a/(2a+b+c), averaged over judge pairs (`e23b`, `e25`). It is reported as a
number with no acceptance threshold: no such threshold is preregistered, and an
earlier version's 0.35 cut-off was invented here.

---

## ED1 · Judge sensitivity

The standardized contrast of Fig 1c recomputed under each judge, from `c17b`.
**Every judge is recomputed on ONE common-support sample** — the intersection of
all four judges' coverage, 27,429 of 27,449 English responses — so a difference
between judges is not a difference in sample. `c17c` reports rows, issues,
models, events by arm, response coverage and retained target weight for every
comparison, including the pairwise ones.
Coloured hairlines are 95% issue-cluster bootstrap intervals with the instrument
held fixed. The shaded band is the **observed judge sensitivity envelope**: the
range of what these four instruments produced on that shared sample.
**It is not a confidence interval, not a statistical bound, and has no coverage
guarantee.** Four judges chosen for cost and speed are not a sample from a
population of judges and none is known to be correct. It is never combined with a
sampling interval. `c17b` reports two distinct claims separately:
`point_sign_stable` (all judges agree on direction) and `envelope_excludes_zero`
(strictly stronger).

## ED2 · Sensitivity of the standardized contrast

Grouped by **what is being varied** — model composition, prompt tier, language,
outcome definition, support restriction, data quality — rather than strung along
a single specification curve, which would imply every row is an alternative way
of estimating one quantity. Two rows are different in kind and are separated:
the **hierarchical marginal** row is a *different estimand* (it integrates over
the issue random effect instead of standardizing over the observed issues), and
the **response-length** rows condition on a post-outcome property of the response
and are therefore a data-quality diagnostic, not a design robustness check.
The dashed rule in each panel is the primary estimate for that jurisdiction.

## ED3 · Refusal-text projection (diagnostic)

Every refusal embedded with a local sentence-transformer
(`paraphrase-multilingual-MiniLM-L12-v2`, revision pinned and recorded in the
CSV; opening 800 characters), then projected with UMAP and coloured by the
judge's stated reason.
**Neighbourhood purity is computed in the original embedding space, not in the
2-D projection**, because UMAP rearranges neighbourhoods to satisfy a layout
objective. The projection value is reported separately in the CSV. Truncation is
validated at 400/800/1600 characters with no material change.
A UMAP layout has **no units**: cluster sizes and between-cluster gaps carry no
meaning and only local distances are faithful, which is why the axes are
unlabelled and a purity statistic is quoted instead of a visual impression.
**This is a diagnostic. It is not evidence that the judge taxonomy is valid, and
no estimate in the paper derives from it.**

## ED4 · Language detail

**a**, the three weightings for the paired language effect; the main figure shows
the predeclared primary one only. **b**, per-model intervals — the values behind
the Fig 2b heatmap.

---

## What each legend must state

Every legend above states: exact n and number of issues (in the referenced
table); sample and exclusions; outcome definition; estimand and weighting;
interval and bootstrap unit; the incomplete-block rule where one applies;
conditioning on engagement where it applies; the judge and common-support caveat;
and the meaning of every visual encoding.
