# Canonical analyses

**This document is the specification for the analyses the paper reports.** If a
number appears in the manuscript, it comes from `pipeline/estimates/canonical/`
and is described here. Everything else — the `e`-series, the `d`-series, `FIG1`–`FIG5`,
`FIGA`–`FIGC` — is superseded provenance, catalogued in
[`ESTIMANDS.md`](ESTIMANDS.md) and archived under `pipeline/archive/` with a
file-by-file mapping in [`pipeline/archive/README.md`](../pipeline/archive/README.md).

Run it:

```bash
CANONICAL_RUN_ID=canon_004 Rscript pipeline/make_release.R
```

That is the whole command. It runs inputs → reliability → estimation → appendix
descriptives → figures → manifest → acceptance → figure audit, builds into
`pipeline/releases/<run_id>/`, and promotes to the live directories **only if
every check passes**. `CANONICAL_RUN_ID` is mandatory; the default run directory
is `annotations/full_v1`.

Nothing in this layer calls an API, and nothing it does mutates prompts,
responses, annotations, sampling files, or `data_clean.RData`.

---

## 1. What the design can and cannot support

The analysis sample is **137,186 responses**: 11 models × 624 issues × 5
languages × 2 prompt tiers, one row per (model, prompt, language), minus the
cells no model returned. English alone is 27,449 rows.

Three features of the design determine every estimand below.

**Issues are the sampling unit, not prompts.** Each issue generates a regular and
a boundary prompt, and each prompt goes to every model in every language. A
prompt-level or response-level standard error would treat those as independent
and be far too small. Every interval in this layer is an **issue-cluster
bootstrap** percentile interval.

**Home status is a property of the issue-model pair, not a treatment.** A model
is "at home" on an issue when the issue's region matches the model's
jurisdiction. Nobody randomised which issues are Chinese issues. Home and away
issues differ in topic, contentiousness, and seed route, so a raw home–away gap
mixes the model's behaviour with the composition of the issue set. This is why
Part 1 reports *two* quantities and never collapses them into one.

**General issues are held out of both arms.** 22,868 rows concern issues with no
regional focus. They are neither home nor away for anyone, and folding them into
"away" would silently define every model's away set differently. They sit at
`home_status == "general"` and are reported separately.

**What is not identified.** Jurisdiction is a property of the model roster —
the CN jurisdiction *is* DeepSeek and Qwen. There is no design that separates "a
Chinese model" from "these two Chinese models", so every jurisdiction-level
statement is a statement about the models tested, not about jurisdictions as
populations. The canonical tables carry this in a `jurisdiction_caveat` field
rather than in a footnote.

---

## 2. Part 1 — home-jurisdiction asymmetry (`c02`–`c07`)

**Question.** Do models refuse more on issues concerning their own jurisdiction?

Two estimands. They answer different questions and neither is a check on the
other, so they are reported separately: the standardized contrast is the primary
quantity and carries the main figure, and the descriptive rates are reported in
`c02` and plotted in appendix S1. They were shown side by side in one figure
until it became clear that the layout itself invited the wrong reading — that
these are two attempts at one number, with the "adjusted" one to be preferred.

### 2a. Descriptive (`c02`, `c03`)

The observed refusal rate on home issues minus the observed rate on away issues,
in English, with no adjustment. This is a *fact about the corpus*: it is what you
would see if you read the responses. It is confounded with issue composition by
construction, and that is not a flaw — it is the quantity a reader wants when
asking "what does this corpus look like?"

Reported at `weighting = "response"` (every response counts once) and
`weighting = "equal_model"` (every model counts once). `c03` repeats it in all
five languages as a supplement. Plotted in **S1**, not in the main figure.

### 2b. Covariate-standardized (`c04`–`c07`) — the primary estimand

A logistic regression per jurisdiction,

```
refused_strict ~ home * model + tier + topic_domain + route
```

then **g-computation on the probability scale**: predict every observation as if
home, again as if away, take the weighted difference. Weights are **nested** —
equal mass per model, then per issue within model, then per prompt within
model×issue. Region fixed effects are excluded: within a jurisdiction region
determines home status, so the two are not separately identified.

**Two standardized estimands are reported, not one.**

| | what it standardizes over | cost |
|---|---|---|
| **full target** | the whole jurisdiction arm | **extrapolates** into covariate cells present in only one arm; the outcome model supplies those predictions |
| **common support** | cells present in BOTH arms, defined jointly over model × topic domain × route × tier | no extrapolation, but the target population is now those cells |

`c06b` reports what the restriction costs: cells, rows, issues and **retained
nested target weight**. `c04` reports, per jurisdiction,
`degenerate_prediction_weight` — the share of target weight sitting in cells
where the fitted probability is numerically 0 or 1. **The full-target result
extrapolates heavily for CN and India** and that is a number in the table, not
an adjective.

**Estimator diagnostics are recorded, not swallowed.** `fit_logit()` captures
GLM warnings; `sep_diagnose()` reports separation symptoms — non-finite
parameters, |coef| > 15, SE > 25, fitted probabilities at 0 or 1, failure to
converge. A *blocking* failure (non-finite parameters or non-convergence) makes
the replicate fail; quasi-separation confined to a nuisance cell does not,
because discarding it would throw away the estimate whose extrapolation the
diagnostics exist to quantify. A **Firth penalized-logit sensitivity** is
declared for every jurisdiction, because Firth has a defined estimator where
maximum likelihood does not.

**The bootstrap draws a fixed number of replicates.** Failures are counted and
reported (`replicates_failed`, `failure_rate`, `interval_reliable`), never
replaced. Resampling until B successes — which is what an earlier version did —
conditions the interval on the replicates where the estimator happened to be
defined, i.e. the ones with more events, and biases it inward.

**Structural zeros.** EU produced zero refusals in both arms, so the contrast
does not exist. Reported with `estimable = FALSE` and a reason.

**Model-specific contrasts (`c05`)** carry intervals, and the equal-model average
is **bootstrapped jointly** in the same replicates. Averaging point estimates
afterwards produced a number with no uncertainty at all, and averaging the
per-model intervals would have been wrong anyway: within a jurisdiction the
model-specific contrasts are estimated on the same issues and are strongly
dependent.

**What you may infer.** The home−away difference that would remain if the two
issue sets had the same measured composition. **Not a causal effect**, not a
difference-in-differences, not a within-issue effect.

## 3. Part 2 — language and framing (`c08`–`c11`)

**Question.** Does the *language of the prompt* change refusal? Does the
*framing* of the prompt?

Both are answered by **paired within-block differences**, which is what makes
them the strongest designs in the paper: prompt content is held fixed by
construction rather than adjusted for.

### 3a. Language (`c08`, `c09`)

Block = model × prompt_id. Within a block, the same prompt in the same model is
observed in English and in the target language; the estimand is the mean paired
difference. All four non-English languages are estimated — Chinese, Arabic,
Hindi, Russian — **including the ones whose intervals cover zero**. Reporting
only the language that "worked" would be selection on the outcome.

Three weightings are reported (pooled, equal-per-model, equal-per-model-issue).
They agree closely here because the design is balanced; showing all three is how
the reader knows that.

**What you may infer.** The effect of delivering *the tested translation* of the
prompt, among the tested prompt and model set. **It is not the causal effect of
a user's language.** It assumes translation equivalence, and that nothing else
travels with language — provider routing, run-time, judge behaviour on non-English
text. Those assumptions are stated in the `interpretation` column, not buried.

Incomplete blocks are counted (`n_missing_blocks`) rather than dropped silently.

### 3b. Framing (`c10`, `c10b`, `c11`)

Block = issue × model × language. **Primary blocks require exactly 2 regular and
2 boundary prompts** — the design puts that many in every block, and averaging
over whatever survived makes the comparison depend on which prompt survived. The
**seven incomplete English blocks are listed by key in `c10b`**; the looser
`n_reg > 0 & n_bnd > 0` rule is retained as a labelled sensitivity row.

**The block holds the issue and the model fixed. It does NOT hold prompt content
fixed** — the regular and boundary variants are different realized prompts about
the same issue, and that difference is the exposure. A causal reading requires
the generated variants to be exchangeable given the issue: an assumption about
the generation template, not a randomisation.

## 4. Part 3 — content of engaged responses (`c12`–`c16`)

**Everything here is conditional on engagement.** The judge skips these passes
for refusals, so the denominator is engaged responses. Refusal itself varies by
model and jurisdiction, so the conditioning is not ignorable.

### 4a. Ideology (`c12`, `c13`)

**The primary estimand is the equal-model share in EACH of the five categories**
(−2, −1, 0, +1, +2), with an interval on every bin; the five sum to one within
each dimension and acceptance fails if they do not. The signed mean is
**secondary** and flagged as such on the row (`role`).

What this replaces: a three-way negative/neutral/positive collapse that was
declared "the full distribution over −2..+2" while discarding the distinction
between −2 and −1 — the only place the strength of a placement lives.

**Endpoints are dimension-specific**, because "left/right" is meaningful for the
economic scale and misleading for the others:

| dimension | −2 | +2 |
|---|---|---|
| Economic | left | right |
| Social | progressive | traditional |
| Authority | authoritarian | libertarian |
| Populism | populist | elitist |

**Reliability is weak** (panel α: economic ≈ 0.36, social ≈ 0.13, authority
≈ 0.20, populism ≈ −0.04). These are **descriptive and exploratory**; social,
authority and populism carry no substantive weight.

### 4b. Two inference targets, and a design-based estimator

The 156 slant issues were drawn **without replacement** from the frozen
624-issue battery. Two targets, reported side by side:

- **superpopulation** — issues exchangeable with a wider population; ordinary
  issue-cluster bootstrap, percentile. The conservative default.
- **frozen battery** — the 624 issues *are* the population; f = 156/624 matters.
  Estimated by a **delete-one-issue jackknife with an explicit finite-population
  correction**, normal approximation.

What this replaces: shrinking the superpopulation percentile interval's
half-widths by √(1−f) after the fact. That is not a design-based correction — the
percentile interval's shape comes from a with-replacement resampling model that
does not match sampling 156 of 624 without replacement, and rescaling it does not
make it match. The jackknife is tested against a census (f = 1 must give zero
variance) and against the (1−f) variance scaling.

Neither interval is a correction of the other; they answer different questions.

### 4c. Moral foundations (`c14`–`c16`)

Six **non-exclusive binary indicators**: a response can invoke several or none,
so they do not form a composition and are never plotted as shares of a whole.
Equal weight per model, always with an interval.

**Agreement is reported as a number, not a verdict.** Each foundation carries
pairwise positive specific agreement (§5a) with its range and interval. The
`low_agreement_flag` and the "acceptable agreement" label are gone: the 0.35
threshold behind them was invented here, is not preregistered, and has no
external justification.

`c16` reports joint outcomes with **refusal as its own category** — collapsing
refusals into "foundation absent" would let a model that refuses more look like
a model that moralises less.

## 5. Part 4 — measurement and multiple judges (`c17`, `c17b`, `c17c`)

The canonical outcome is one named judge, `google/gemini-2.5-flash-lite`. Every
other judge is a sensitivity dimension. **No majority vote is computed**: with no
human-validated labels there is no basis for calling a majority correct, and a
consensus label would conceal the disagreement these tables exist to expose.

### 5a. Agreement statistics

**Positive specific agreement is pairwise: PSA = 2a/(2a+b+c)**, computed for each
judge pair and summarised by its mean and range over pairs, with an
issue-clustered interval.

What this replaces: a function named `pos_agree()` reported in a column named
`positive_specific_agreement`, which computed — among units *any* judge called
positive — the share where *all* judges agreed. That is a unanimity rate. It
falls mechanically as judges are added, so it was not comparable across
constructs rated by different numbers of judges, and it was being read as the
standard measure. It survives under the honest name
`all_rater_positive_unanimity`.

The correction changes the substantive picture. Under the old statistic four
foundations looked "weakly agreed" at 0.39–0.47; under true pairwise PSA they
are:

| foundation | prevalence | PSA (mean) | range |
|---|---|---|---|
| fairness / cheating | 0.68 | 0.86 | 0.81–0.91 |
| care / harm | 0.51 | 0.85 | 0.82–0.88 |
| liberty / oppression | 0.51 | 0.76 | 0.70–0.85 |
| loyalty / betrayal | 0.15 | 0.56 | 0.46–0.69 |
| authority / subversion | 0.20 | 0.51 | 0.45–0.62 |
| sanctity / degradation | 0.03 | 0.47 | 0.39–0.51 |

**Complete-case and pairwise samples are kept apart.** Units rated by two judges
and units rated by four do not carry comparable agreement information, so `e23b`
reports every judge pair separately alongside the all-judge complete-case sample,
with both sizes.

**One panel loader, one resume key.** `load_judge_panel()` in
`10_canonical_common.R` is shared by the reliability script and the judge
re-estimation. The resume key is (prompt_id, language, model) within a judge,
last wins, matching the annotator; uniqueness is **asserted** afterwards rather
than absorbed by `values_fn = first`, which would hide an inconsistent duplicate
instead of resolving it. Reliability bootstraps are seeded and their replicate
counts recorded (`e23c`).

**Codebook versions.** The panel is restricted to English before the version
check, because the file also holds a later Russian re-annotation under a
different codebook. Within English there is one stamped version; the anchor's
labels predate version stamping and are unstamped. That composition is written
into every reliability table (`e22b`) rather than assumed away in either
direction.

### 5b. Common support — the point of `c17`

An earlier version compared the canonical judge on the **full** English sample
against each alternative judge on **whatever that judge had labelled**.
nemotron-3-super covers 16,576 of 27,450 English responses, so part of the
apparent instrument difference was composition.

Now every comparison is computed on an explicit common-support sample with
**both judges recomputed on it**:

- **pairwise** — the intersection of the canonical judge and that one judge;
- **all-judge** — the four-judge intersection, 27,429 of 27,449 English responses.

`c17c` reports rows, issues, models, events by arm, response coverage and
retained nested target weight for every comparison.

### 5c. The envelope

The union of the per-judge intervals, computed on the all-judge sample, is the
**observed judge sensitivity envelope**: the range of what these four instruments
produced on one shared sample.

**It is not a confidence interval, not a statistical bound, and has no coverage
guarantee.** Four judges chosen for cost and speed are not a sample from a
population of judges, and none is known to be correct. It is never combined with
a sampling interval, and the full-sample `c04` interval is **not** inserted into
it — that interval comes from a different, larger sample, and mixing it in would
produce a range no single comparison supports.

`c17b` reports two distinct claims separately, because conflating them would
overstate the result:

| column | claim |
|---|---|
| `point_sign_stable` | every judge agrees on the direction |
| `envelope_excludes_zero` | the union of their intervals clears zero — strictly stronger |

**There is no judge-sensitivity estimate for the paired language effect.** The
panel covers English only; re-labelling one arm of a paired difference compares
two instruments rather than perturbing one. Those rows are retired from `c08`.

### 5d. The disabled annotation-error layer

`draw_latent_labels()` implements the standard misclassification correction and
is **disabled by a `stop()`**. It requires stratum-specific sensitivity,
specificity and prevalence; none exist.

### 5e. Planned: design-based supervised validation

Unchanged from the previous version of this document: a stratified probability
sample with known inclusion probabilities, frontier-model gold labels with human
adjudication of a sub-subsample, per-stratum confusion matrices, propagation
through the existing estimators as `c19+` alongside — never replacing — the
canonical numbers, and reporting the correction's own uncertainty. Until steps
1–3 exist, the honest position is the current one.

## 6. Figures

Main figures in `pipeline/figures/main/`, Extended Data in
`pipeline/figures/extended/`. Full legends, with every n, exclusion, estimand,
weighting, interval and encoding: **`docs/CANONICAL_FIGURE_LEGENDS.md`**.

| figure | content | tables |
|---|---|---|
| `Fig1_home_jurisdiction` | a design/locator · b unadjusted rates · c standardized contrasts, full-target and common-support | `c02`, `c04` |
| `Fig2_language_framing` | a primary-weighting language effect · b model × language heatmap with printed values · c framing, complete 2+2 blocks | `c08`–`c11` |
| `Fig3_content` | a five-bin ideology with dimension-specific endpoints · b foundation prevalence with numeric PSA | `c12`, `c14` |
| `ED1_judge_sensitivity` | the contrast under each judge on ONE common-support sample | `c17b`, `c17c` |
| `ED2_sensitivity_panels` | sensitivities grouped by what varies; hierarchical separated as a different estimand | `c07`, `c04` |
| `ED3_refusal_text_projection` | refusal-text projection, diagnostic only | `u01`–`u03` |
| `ED4_language_detail` | weighting comparison and per-model intervals | `c08`, `c09` |

**Fig 1 carries the home family only.** Judge sensitivity and the projection were
in it and did not belong: a main figure should carry one result family.

### 6a. Production artwork

The PNG-only rule is **retired**. Every figure is exported as **PDF, SVG and PNG
from the same ggplot object**, so the formats cannot drift:

- PDF and SVG keep **text as text** — nothing is outlined or rasterised — so a
  production editor can restyle the type. Helvetica is one of the 14 standard
  PDF fonts and needs no embedding.
- PNG at 600 dpi RGB is a preview, not the deliverable.
- Widths are 89 mm or 183 mm; type is 5–7 pt at final size with 8 pt bold panel
  labels, and nothing falls below 5 pt.
- Stale sibling formats are deleted before each export.
- `audit_figures.R` fails a main figure that exists only as a raster.

## 6b. Refusal-text projection (diagnostic, not an estimand)

`scripts/refusal_umap.py` → `u01` (English, semantic), `u02` (five languages),
`u03` (English, lexical); drawn in ED3.

Text is embedded with a local sentence-transformer
(`paraphrase-multilingual-MiniLM-L12-v2`, **revision pinned and recorded**),
opening 800 characters, then projected with UMAP and coloured by the judge's
justification code.

**Neighbourhood purity is computed in the original embedding space**, not in the
2-D projection: UMAP rearranges neighbourhoods to satisfy a layout objective, so
purity measured on the projection partly measures the projection. The projection
value is reported separately. Truncation is validated at 400/800/1600 characters
(0.568 / 0.565 / 0.565) — the choice is not driving the result.

| representation | purity | at random |
|---|---|---|
| semantic, English (embedding space) | 0.57 | 0.44 |
| semantic, English (2-D projection) | 0.53 | 0.44 |
| lexical, English | 0.58 | 0.44 |
| semantic, five languages | 0.44 | 0.35 |

The codes track wording about as closely as meaning. **This is a diagnostic. It
is never evidence that the judge taxonomy is valid, and no estimate in the paper
derives from it.**

## 6c. How this maps onto the manuscript

| range | role | produces |
|---|---|---|
| `01`–`02` | inputs | `data_clean.RData`; `e22b`–`e28` reliability |
| `10`–`14` | estimation | `c00`–`c18` |
| `20` | **main manuscript** | Fig 1–3 |
| `21` | **Extended Data** | ED1–ED4 |
| `30` | acceptance | `c01b` |
| `40` | appendix | `a01`–`a04`, descriptive views only |

The archived appendix scripts (`pipeline/archive/precanonical_appendix/`) were
retired for invalid inference — independent-sample tests on paired observations,
row-level bootstraps ignoring issue clustering, unclustered GLMs,
`response_language` used as the exposure. Their README names each defect.

## 7. Table index

| file | contents |
|---|---|
| `c00_manifest.csv` | every output, source and input with SHA-256; git SHA and dirty state; package and language versions; seeds; replicate counts; embedding model revision |
| `c00_timings.csv` | per-stage wall clock |
| `c01_reconciliation.csv` | canonical vs superseded headline numbers, with the reason each differs |
| `c01b_acceptance_tests.csv` | every acceptance test and its result |
| `c02`, `c03` | unadjusted home/away rates |
| `c04` | standardized contrast — full target, common support, Firth sensitivity |
| `c05` | model-specific contrasts + jointly bootstrapped equal-model average |
| `c06`, `c06b` | overlap and common-support diagnostics |
| `c07` | sensitivities |
| `c08`, `c09` | paired language effects |
| `c10`, `c10b`, `c11` | framing; incomplete blocks by key; by model and domain |
| `c12`, `c12b`, `c13` | five-bin ideology, slant coverage, by model |
| `c14`, `c15` | foundation prevalence with agreement statistics |
| `c16` | joint outcomes, refusal as its own category |
| `c17`, `c17b`, `c17c` | judge sensitivity, envelope, common-support description |
| `c18` | bootstrap and jackknife diagnostics |
| `a01`–`a04` | appendix descriptive views |

## 8. Acceptance criteria

`30_acceptance.R` runs 65 checks and exits non-zero on any failure;
`tests_synthetic.R` adds 29 fast unit tests that need no data. They are
adversarial where it matters:

- **Weighting** is checked against a constructed imbalance, because on a balanced
  design a weighting check passes trivially.
- **Bootstrap multiplicity** is checked against a synthetic three-issue
  counter-case; two issues cannot distinguish the two keyings.
- **Failed replicates** must be counted, never replaced, and the drawn count must
  equal the requested count.
- **Separation** must be detected and reported; Firth must return a finite
  estimate where ML does not.
- **PSA** must equal 2a/(2a+b+c) on a reference case.
- **Ideology** must have exactly five bins summing to one, with an interval on
  each, and must not carry generic left/right labels on authority or populism.
- **Framing** must use complete 2+2 blocks and list the incomplete ones by key.
- **Judge comparisons** must use one sample per jurisdiction across judges.
- **A test whose condition returns `logical(0)` or `NA` fails.** Silently passing
  by disappearing is the worst behaviour a check can have.
- **Release provenance** (timings, manifest, hashes, dirty state) is enforced when
  `CANON_RELEASE=1`, which `make_release.R` sets.

## 9. Known gaps

- **The judge panel covers English only.** No judge-sensitivity estimate exists
  for the language estimand, and none is fabricated.
- **Slant coverage is English-only** for the canonical content results; a top-up
  of roughly 5,200 rows would let Chinese and Arabic in.
- **Ideology reliability is weak** on three of four dimensions. Those results are
  descriptive and exploratory.
- **The anchor judge's labels are unstamped** (they predate codebook version
  stamping). The composition is reported (`e22b`); whether the codebook text
  differed cannot be established from the files.
- **`draw_latent_labels()` is disabled** pending the validation study in §5e.
- **Pass 4 stance coding** is not part of this layer.
- **`e20_moral_by_language.csv`** remains retired as unsound (unpaired, with
  language-varying denominators).
- **Refusal-justification codes (A–G)** carry no estimand; agreement is too weak.

## 10. What changed in this revision, and why

| area | before | now |
|---|---|---|
| ideology | 3-way collapse declared "the full distribution" | five bins, interval on each, signed mean secondary |
| endpoints | generic left/right on all four scales | dimension-specific |
| agreement | all-rater unanimity mis-named positive specific agreement; 0.35 verdict | pairwise 2a/(2a+b+c) with range and interval; no threshold |
| judge comparison | canonical judge on full sample vs others on their own coverage | explicit pairwise and all-judge common support, both recomputed |
| envelope | "sensitivity bound", full-sample interval inserted | observed judge sensitivity envelope, one sample, nothing inserted |
| framing | any block with ≥1 prompt per arm | complete 2+2; 7 incomplete blocks listed by key |
| home estimand | one standardized contrast | full-target **and** common-support, with extrapolation quantified |
| separation | silently produced finite-looking numbers | diagnosed, reported, Firth sensitivity declared |
| bootstrap | resampled until B successes | fixed B, failures counted and reported |
| `c05` average | point estimate, no interval | jointly bootstrapped |
| finite battery | percentile interval × √(1−f) | delete-one-issue jackknife with FPC |
| appendix | independent-sample tests on paired data | archived; descriptive views only |
| driver | `run_all.R` excluded the canonical layer and `--figures` ran nothing | `make_release.R`, one command, atomic promotion |
| artwork | PNG only | PDF + SVG + PNG from one object |
