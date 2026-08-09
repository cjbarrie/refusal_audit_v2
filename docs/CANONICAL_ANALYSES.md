# Canonical analyses

**This document is the specification for the analyses the paper reports.** If a
number appears in the manuscript, it comes from `pipeline/estimates/canonical/`
and is described here. Everything else — the `e`-series, the `d`-series, `FIG1`–`FIG5`,
`FIGA`–`FIGC` — is superseded provenance, catalogued in
[`ESTIMANDS.md`](ESTIMANDS.md) and archived under `pipeline/archive/` with a
file-by-file mapping in [`pipeline/archive/README.md`](../pipeline/archive/README.md).

> **Current as of release `canon_011`.** Every number quoted below was checked
> against the promoted tables in `pipeline/estimates/canonical/` when this
> document was last revised. The authoritative release id is the
> `canonical_run_id` column of `c00_manifest.csv`; where a figure or interval is
> described, the full legend is in
> [`CANONICAL_FIGURE_LEGENDS.md`](CANONICAL_FIGURE_LEGENDS.md). **Known gaps and
> unresolved inconsistencies are in §9** — read it before relying on `c07`'s
> `estimable` flag or on `c12b`'s eligibility label.

Run it:

```bash
CANONICAL_RUN_ID=<new_id> Rscript pipeline/make_release.R
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

## 2. Part 1 — home-jurisdiction asymmetry (`c02`–`c07b`)

**Question.** Do models refuse more on issues concerning their own jurisdiction?

Two estimands. They answer different questions and neither is a check on the
other, so they are reported separately: the standardized contrast is the primary
quantity, and the descriptive rates are reported in `c02` and **not plotted at
all** — an absolute rate and a difference are different quantities and do not
belong on one axis. The two DIFFERENCES share the single forest of Fig 1.

### 2a. Descriptive (`c02`, `c03`)

The observed refusal rate on home issues minus the observed rate on away issues,
in English, with no adjustment. This is a *fact about the corpus*: it is what you
would see if you read the responses. It is confounded with issue composition by
construction, and that is not a flaw — it is the quantity a reader wants when
asking "what does this corpus look like?"

Reported at `weighting = "response"` (every response counts once) and
`weighting = "equal_model"` (every model counts once). `c03` repeats it in all
five languages as a supplement.

**Figure 1 plots the `equal_model` descriptive difference.** This is a
deliberate choice, not the default: the standardized contrast standardizes to a
target in which every model carries equal weight, so the descriptive point it is
overlaid against must weight models the same way, or the two marks would differ
in *two* respects at once. The two weightings differ by at most 0.001 pp here,
but they are different targets and the figure states which it draws.

**The two marks in Figure 1 are not two estimates of one effect.** They differ
in adjustment *and* nothing else only because the weighting was matched; the
standardized point remains a covariate-standardized predictive contrast, not a
causal effect. Overlaying them shows how the descriptive gap moves once measured
composition is held fixed.

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
nested target weight** (CN keeps 41.3%, MENA 77.1%, India 69.4%, US 91.7%, EU
95.4%). `c04` reports two extrapolation diagnostics per jurisdiction, and they
measure different things:

- `observed_fit_extreme_weight` — the share of target weight whose **observed**
  fitted probability is numerically 0 or 1;
- `counterfactual_extreme_weight` — the share for which **either** counterfactual
  prediction, `p(home=1)` or `p(home=0)`, is numerically 0 or 1. This is the one
  that matches the estimand, because the contrast is built from both prediction
  vectors: a unit with a comfortable observed fit can still have a degenerate
  counterfactual, and that is precisely the extrapolation common support avoids.

**The full-target result extrapolates heavily for CN and India** and that is a
number in the table, not an adjective.

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

## 3. Part 2 — language and framing (`c08`–`c11`, `c08b`)

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

## 4. Part 3 — content of engaged responses (`c12`–`c16`, `c19`)

**Everything here is conditional on engagement.** The judge skips these passes
for refusals, so the denominator is engaged responses. Refusal itself varies by
model and jurisdiction, so the conditioning is not ignorable.

### 4a. Ideology (`c12`, `c12b`, `c13`, `c19`)

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

**Reliability is weak.** Panel Krippendorff's α for the current release is
economic 0.392, social 0.126, authority 0.232, populism 0.017 — read out of
`e25` at build time and written into `c12$reliability_warning`, not typed in
here. These are **descriptive and exploratory**; social, authority and populism
carry no substantive weight.

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

### 4c. Moral foundations (`c14`–`c16`, `c19`)

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

## 5. Part 4 — measurement and multiple judges (`c17`–`c17d`)

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
nemotron-3-super covers 16,576 of 27,449 English responses, so part of the
apparent instrument difference was composition.

Now every comparison is computed on an explicit common-support sample with
**both judges recomputed on it**:

- **pairwise** — the intersection of the canonical judge and that one judge;
- **all-judge** — the four-judge intersection, 27,429 of 27,449 English responses.

`c17c` reports rows, issues, models, events by arm, response coverage and
retained nested target weight for every comparison.

### 5c. The envelope — and the three things it is not

`c17b` carries **four distinct quantities**, and the whole point of the table is
that they are never merged.

| quantity | columns | what it is |
|---|---|---|
| per-judge point estimate | `estimate` | the Fig 1c contrast under judge *j* on the shared sample |
| per-judge sampling interval | `conf_low`, `conf_high` | judge *j*'s own 95% issue-cluster bootstrap, **instrument held fixed** |
| **observed judge point envelope** | `point_envelope_low`, `point_envelope_high` | `min`/`max` of the four **point** estimates — pure instrument variation, containing **no sampling uncertainty** |
| union of judge intervals | `union_low`, `union_high` | `min(conf_low)` to `max(conf_high)` — reported under exactly that name and **never called an envelope** |

**The envelope is the range of the point estimates, not the union of the
intervals.** An earlier version of this document, and an earlier version of the
figure, called the union "the observed judge sensitivity envelope". That
conflated two different things: the union mixes sampling uncertainty into a
quantity meant to describe instrument variation, and it is always wider than the
judge disagreement it purports to show. On the envelope row of `c17b`,
`conf_low`/`conf_high` hold the **point** envelope, so anything that plots that
row's interval draws instrument variation and not a mixture.

**Neither is a confidence interval, a statistical bound, or a quantity with a
coverage guarantee.** Four judges chosen for cost and speed are not a sample
from a population of judges, and none is known to be correct. Neither is ever
combined with a sampling interval, and the full-sample `c04` interval is **not**
inserted into either — it comes from a different, larger sample, and mixing it
in would produce a range no single comparison supports.

Three claims are reported as three separate columns, because they are different
and strictly ordered in strength:

| column | claim |
|---|---|
| `point_sign_stable` | every judge agrees on the direction |
| `point_envelope_excludes_zero` | the range of the **point estimates** clears zero |
| `union_excludes_zero` | the union of their **intervals** clears zero — strictly stronger |

For the current release: `point_sign_stable` and `point_envelope_excludes_zero`
hold for CN, MENA and India; `union_excludes_zero` holds for CN only.

### 5c-bis. The paired judge difference (`c17d`)

`c17b` answers *what does each judge produce*. The sensitivity question is *how
far does the estimate move when the judge changes*, and `c17d` estimates that
directly:

```
Delta_{j,r} = theta_{j,r} - theta_{canonical,r}
```

**It cannot be obtained by subtracting two rows of `c17b`.** On the all-judge
common-support sample the four judges label *the same responses*, so their
estimates are strongly positively dependent; differencing point estimates and
carrying either marginal interval — or combining the two — gives an interval far
too wide. The difference is therefore formed **inside** each bootstrap
replicate: one issue set is resampled, every judge's contrast is recomputed on
that same draw, and the difference is taken within the draw. Same bootstrap unit
(`issue_id`), same multiplicity labelling, same fixed-B rule with failures
counted and never replaced. A replicate in which any judge is undefined fails
for all of them. Acceptance H7–H9 check that the canonical judge's own
difference is exactly zero, that the point estimates reproduce `c17b`, and that
the paired interval is narrower than the naive combination.

**Zero means the alternative judge reproduces the canonical judge**, not that
either is correct. The canonical judge is a **reference instrument, not ground
truth** — which is the same reason no majority vote is computed.

For the current release the paired differences are, in percentage points:

| jurisdiction | gemma-4-31b-it | nemotron-3-nano | nemotron-3-super |
|---|---|---|---|
| CN | −5.16 [−10.84, 2.76] | −3.62 [−8.35, 1.92] | −2.12 [−5.77, 1.90] |
| MENA | −1.54 [−2.91, −0.24] | −2.58 [−4.53, −0.77] | −1.38 [−2.83, −0.11] |
| India | +0.05 [−0.82, 0.99] | +0.35 [−0.90, 1.49] | +0.44 [−0.46, 1.56] |
| US | −0.67 [−1.95, 0.56] | −1.75 [−3.17, −0.22] | −1.96 [−3.35, −0.65] |

**The pairing is what makes this readable.** For MENA all three alternative
judges sit below the canonical judge and all three differences exclude zero —
a pattern the overlapping absolute intervals in `c17b` cannot show. EU is not
estimable under any judge. Zero replicates failed.

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

## 5f. Part 5 — issue-subsample stability (`c21`)

**Question.** Not "how uncertain is the estimate" — that is the bootstrap. This
asks a **design** question: how much of the full-sample conclusion is already
recovered when the issue battery is smaller?

**It is not a bootstrap and its ranges are not confidence intervals.** A
bootstrap resamples *with* replacement at full size to approximate sampling
uncertainty at the observed n. This resamples *without* replacement at reduced
size to describe how the answer moves as issues are added. The summaries are
called **across-subsample ranges** and **sampling-stability bands** and never
anything else; acceptance J11 fails the build on the word "confidence".

**Unit.** The issue. A sampled issue carries all of its prompts, tiers,
languages, models and annotations, so the paired language and framing blocks
Part 2 rests on stay intact. Resampling response rows would describe a study
nobody ran.

**Design.** Simple random sampling without replacement within each of the nine
**topic-domain strata**, allocation `min(n_h, max(1, ceil(f·n_h)))`. Within a
replicate the issues of each stratum are permuted **once** and every fraction is
a *prefix* of that permutation, so the 20% sample contains the 10% sample and a
trajectory reads as the effect of adding issues. Fractions 10–90% plus a
deterministic 100% endpoint; 500 replicates per fraction; master seed with
`set.seed(MASTER_SEED + replicate)` so any replicate is reproducible alone.
Acceptance J15 re-derives the nesting from the recorded rule rather than trusting
it.

**Estimands refitted inside each sample** (never held fixed at full-sample
coefficients): descriptive home−away, standardized full-target home contrast,
the four pooled language contrasts, the framing contrast, the five-bin ideology
composition, foundation prevalence, and pairwise PSA. Model-level heterogeneity
is **not** refitted — it is too expensive, and that restriction is stated rather
than hidden.

**Prespecified tolerances**, fixed before any result was seen: 1 pp and 2 pp for
percentage-point contrasts, 0.02 and 0.05 for shares.

**Result for the current release.** 188,047 replicate-estimand rows; overall
estimability 97.8%, convergence 99.99%. The median tracks the full-sample value
at every fraction and the bands narrow monotonically. Sign agreement reaches 1.00
by 20% of the battery for CN and by 40% for MENA; the US framing contrast, which
is near zero, does not stabilise in sign at any fraction — which is the honest
reading of an estimate whose interval covers zero.

## 5g. Part 6 — prompt-semantic geometry (`c22`)

**Question.** Which regions of prompt-meaning space attract refusal, and does the
pattern move with the language the prompt is delivered in? Not "do the prompts
form clusters" — a projection always shows clusters.

**One geometry, reused everywhere.** Exactly one 2-D coordinate pair per prompt,
fitted once on the English prompt text. Every panel of ED8 and ED9 reuses it.
Fitting a separate projection per language or per model would make the axes mean
different things in each facet, so a point that appeared to move would be an
artefact of the fit. Acceptance J20–J21 assert one coordinate pair per prompt
and one seed.

**Embedding.** `openai/text-embedding-3-small` at 512 of its 1,536 dimensions
(the model is Matryoshka-trained, so a truncated prefix is a valid embedding).
The input is the English prompt as delivered, with the boundary directive
`"Write a persuasive argument defending the following position:"` **stripped** —
it opens all 1,248 boundary prompts identically and, left in, the map separates
tiers on template wording rather than on subject matter. Produced once by
`scripts/embed_prompts.py` and cached in `data/`; **the release itself never
calls an API**, and `16_prompt_umap.R` skips cleanly when the cache is absent.

**Refusal propensity** is equal per jurisdiction with models nested equally
within jurisdiction, so the four-model US arm cannot outvote the two-model CN
arm; the `ALL` row additionally weights every language equally. Numerator and
denominator are carried alongside. Bounded in [0,1], asserted.

**Diagnostics, reported before any semantic claim.** Neighbourhood preservation
at k = 15 is 0.395. Topic-domain neighbourhood purity is **0.649 against a
shuffled baseline of 0.117**, so the map does recover the topic structure. Across
three alternative seeds, Procrustes RMSE is 0.37–0.42 while neighbour overlap is
0.65–0.67: **read neighbourhoods, not absolute positions**. A 3 × 3
hyper-parameter grid gives preservation 0.30–0.44. No near-duplicate prompts
(cosine ≥ 0.995) and no missing embeddings.

**Representative regions are selected deterministically** — highest local
refusal, highest between-language disagreement, highest between-model
disagreement, each taking the top non-overlapping neighbourhood and its medoid.
Full prompt text is in the companion table, never printed on the point cloud.

**Exploratory and descriptive.** It establishes no causal effect and validates no
taxonomy.

## 6. Figures

Main figures in `pipeline/figures/main/`, Extended Data in
`pipeline/figures/extended/`. Full legends, with every n, exclusion, estimand,
weighting, interval and encoding: **`docs/CANONICAL_FIGURE_LEGENDS.md`**.

| figure | content | tables |
|---|---|---|
| `Fig1_home_jurisdiction` | **one forest**: the unadjusted (equal-model) difference and the standardized full-target contrast, overlaid on a shared axis, one row per jurisdiction. Absolute rates are **not** plotted — they are a different quantity and live in `c02` | `c02`, `c04` |
| `Fig2_language_framing` | a pooled paired language contrasts · b framing, pooled estimate plus per-model heterogeneity | `c08`, `c10`, `c11` |
| `Fig3_content` | a **all five** ideology bins as a distribution · b foundation prevalence · c agreement, aligned to b on its own 0–1 axis | `c12`, `c14` |
| `ED1_judge_sensitivity` | **paired** difference from the canonical judge, one compact forest, common axis | `c17d` (`c17b`, `c17c` for absolutes and support) |
| `ED2_focused_sensitivity` | **four** specifications per jurisdiction: primary ML, Firth (estimator), common support (target), `refused_any` (outcome). The full grid is `c07c` | `c04`, `c07` |
| `ED3_sample_size_stability` | issue-subsample stability bands and sign agreement | `c21` |
| `ED4_language_heterogeneity` | model × language paired contrasts **with intervals**, common axis, one display | `c09` |
| `ED5_slant_by_model` | five-bin ideology composition per model × dimension | `c13` |
| `ED6_foundations_by_model` | per-model foundation prevalence with issue-clustered intervals | `c15`, `c14` |
| `ED7_measurement_reliability` | construct × metric: raw agreement, α, Gwet AC1/AC2, PSA | `e23`, `e24`, `e25` |
| `ED8_prompt_semantic_umap` | one fixed prompt geometry; overall and per-language refusal propensity | `c22` |
| `ED9_prompt_semantic_umap_by_model` | the same geometry, refusal by model | `c22` |

**Moved to tables rather than forced into figures**: the full specification grid
and leave-one-model-out (`c07c`), response-length thresholds (`c07c`, class E),
the hierarchical marginal estimand (`c07b`), the weighting comparison (`c08b`),
detailed reliability entries (`e23`–`e25`), complete subsampling diagnostics
(`c21_subsample_summary.csv`), and exact model-level content estimates
(`c13`, `c15`).

**Fig 1 carries the home family only.** Judge sensitivity and the projection were
in it and did not belong: a main figure should carry one result family. The
locator map has also left it — it carried no estimate and took roughly a third
of the area; the region coding is documented in the legends instead.

**No figure carries a title, a subtitle or a caption.** Panel letters, axes,
tick labels, category names, facet headings, compact legends and direct numeric
labels only. `audit_figures.R` fails the build if a figure script passes
`title=`, `subtitle=` or `caption=`. Full legends: `docs/CANONICAL_FIGURE_LEGENDS.md`.

**A figure script must not write a canonical table.** `c07b` and `c08b` were
produced by `21_figures_extended.R` until this release, so they existed only if
the artwork ran. They are now written by `11_canonical_home.R` and
`12_canonical_language_framing.R`; acceptance test H12 enforces it.

### 6a. Production artwork

**PNG ONLY.** Every figure is a single 600 dpi RGB PNG through ragg and nothing
else — no PDF, no SVG, no EPS, no TIFF.

- `save_fig()` refuses a destination that is not `.png`, and deletes any sibling
  left by an earlier multi-format design before writing.
- Widths are 89 mm or 183 mm; type is 5–7 pt at final size with 8 pt bold panel
  labels, and nothing falls below 5 pt.
- The active figure tree is exactly `pipeline/figures/main/*.png` and
  `pipeline/figures/extended/*.png`. `audit_figures.R` fails on any other file in
  either directory, and on the presence of the obsolete `canonical/` or
  `appendix/` trees.
- Multi-format export was tried twice and removed twice: the formats drifted,
  stale siblings accumulated, and the second attempt left the theme header
  asserting PNG-only while the exporter wrote three formats and the audit
  *required* all three.

## 6b. Refusal-text projection — RETIRED

The UMAP projection of refusal text no longer ships. Neighbourhood purity in the
embedding space was 0.57 against 0.44 at random, and the **lexical** TF-IDF
representation reached 0.58 — so a figure built to show that the judge's reason
codes track meaning showed that they track wording at least as well. It was also
never rebuilt by the release driver, so the shipped image could date from a
different run than every other artefact. `scripts/refusal_umap.py` and `u01`–`u03`
are in `pipeline/archive/exploratory_umap/` with a README. Nothing in the
canonical layer reads them.

## 6c. How this maps onto the manuscript

| range | role | produces |
|---|---|---|
| `01`–`02` | inputs | `data_clean.RData`; `e22b`–`e28` reliability |
| `10`–`16` | estimation | `c00`–`c22` |
| `20` | **main manuscript** | Fig 1–3 |
| `21` | **Extended Data** | ED1–ED9 |
| `30` | acceptance | `c01b` |
| `40` | appendix | `a01`–`a04`, descriptive views only |

The archived appendix scripts (`pipeline/archive/precanonical_appendix/`) were
retired for invalid inference — independent-sample tests on paired observations,
row-level bootstraps ignoring issue clustering, unclustered GLMs,
`response_language` used as the exposure. Their README names each defect.

## 7. Table index

| file | contents |
|---|---|
| `c00_manifest.csv` | every output, source, documentation file and input with SHA-256; **`git_sha_at_start`, `git_sha_at_end`, `tree_moved_during_build`**; package and language versions; seeds; replicate counts |
| `c00_timings.csv` | per-stage wall clock |
| `c01b_acceptance_tests.csv` | every acceptance test and its result |
| `c02`, `c03` | unadjusted home/away rates |
| `c04` | standardized contrast — full target, common support, Firth sensitivity |
| `c05` | model-specific contrasts + jointly bootstrapped equal-model average |
| `c06`, `c06b` | overlap and common-support diagnostics |
| `c07` | sensitivities |
| `c07b` | hierarchical marginal — a **different estimand**, tabulated because it has no comparable interval |
| `c07c` | the sensitivity **catalogue**, every row classified by what it changes: A estimator / B target population / C outcome definition / D model roster / E post-outcome diagnostic / F different estimand, with the difference from the primary point |
| `c08b` | weighting comparison for the paired language effect |
| `c08`, `c09` | paired language effects |
| `c10`, `c10b`, `c11` | framing; incomplete blocks by key; by model and domain |
| `c12`, `c12b`, `c13` | five-bin ideology, slant coverage, by model |
| `c14`, `c15` | foundation prevalence with agreement statistics |
| `c16` | joint outcomes, refusal as its own category |
| `c17`, `c17b`, `c17c` | judge sensitivity, envelope, common-support description |
| `c17d` | **paired** judge-minus-canonical difference, bootstrapped in the same replicates |
| `c18` | bootstrap and jackknife diagnostics |
| `c19` | content outcomes (ideology bins, foundation prevalence) recomputed under each judge |
| `c21_subsample_draws.parquet` | every replicate-level subsample estimate |
| `c21_subsample_summary.csv` | per fraction and estimand: median, p10–p90 and p2.5–p97.5 **across-subsample ranges**, deviation from full sample, sign agreement, within-tolerance rates, estimability and convergence |
| `c21_subsample_failures.csv` | non-estimable replicate cells by fraction |
| `c21_subsample_metadata.json` | seed, fractions, strata, sampling and nesting algorithms, tolerances, versions, git SHA, input hashes |
| `c22_prompt_umap_coordinates.csv` | one fixed 2-D coordinate pair per prompt, plus per-language propensities and neighbourhood diagnostics |
| `c22_prompt_refusal_propensities.csv` | prompt × language refusal propensity with numerator and denominator |
| `c22_prompt_refusal_by_model.csv` | per-prompt English refusal indicator by model |
| `c22_prompt_umap_diagnostics.csv` | neighbourhood preservation, topic purity against a shuffled baseline, hyper-parameter grid, seed stability |
| `c22_prompt_umap_regions.csv` | deterministically selected representative regions and their medoid prompts |
| `c22_prompt_umap_metadata.json` | embedding model and preprocessing, UMAP implementation and parameters, hashes |
| `a01`–`a04` | appendix descriptive views |

**Not tables.** `c20_figure_layout_main.rds` and `c20_figure_layout_extended.rds`
hold the assembled plot objects so `audit_figures.R` can *measure* the rendered
layout instead of grepping source for font sizes. They are audit artefacts, not
estimates and not artwork; they live in the estimates directory because the
figure tree holds PNGs and nothing else.

## 8. Acceptance criteria

`30_acceptance.R` runs **79 checks** and exits non-zero on any failure;
`tests_synthetic.R` adds **34 fast unit tests** that need no data. They are
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
- **The paired judge difference (H6–H11)** must declare itself paired; the
  canonical judge's own difference must be exactly zero; its point estimates must
  reproduce `c17b` to machine precision; and **its interval must be narrower than
  the naive combination of the two marginal intervals** — a paired interval that
  is not narrower has not used the pairing. It must also record a fixed draw
  count with failures counted, and must never call the canonical judge ground
  truth.
- **No figure script may write a canonical table (H12).** `c07b` and `c08b` were
  produced only by `21_figures_extended.R` until release `canon_010`, so they
  existed only when the artwork was rebuilt.

The figure gate `audit_figures.R` adds its own checks, run before and after
promotion: exactly the expected PNGs and nothing else; every width and height on
an approved two-column canvas; **`pHYs` resolution metadata present and equal to
600 dpi**, because a large raster without it is placed at 72 dpi by a journal's
layout software; no `title=`, `subtitle=` or `caption=` in any figure script; no
banned explanatory prose in a plotting specification; no model fitted and no CSV
written by a plotting script; and structural zeros distinguished from estimated
nulls.

## 9. Known gaps

- **The judge panel covers English only.** No judge-sensitivity estimate exists
  for the language estimand, and none is fabricated.
- **The content results are English-only, and the stated reason has gone stale.**
  Slant coverage of eligible engaged responses is now English 100%
  (6,528/6,528), **Hindi 100%** (5,905/5,905), Chinese 98.9%, Arabic 95.4%,
  Russian 68.3% (`c12b`). Two consequences:
  * The earlier claim that a top-up of "roughly 5,200 rows would let Chinese and
    Arabic in" is wrong by an order of magnitude — the outstanding gaps are 73
    rows (zh) and 289 rows (ar).
  * A roster argument that used to justify the restriction is also stale.
    `docs/SLANT_SUBSAMPLE.md` records "en/zh/ar 11 models, ru 9, hi 7", which was
    true while generation was still running. **In the completed run all 11 models
    answer in all five languages.** Only Russian is short on *coded* slant rows,
    where allam-7b and sarvam-30b have none.
  * **Unresolved inconsistency, reported not fixed:** `c12b` labels a language
    `eligible for canonical content results` on a coverage-only rule
    (`coverage >= 0.999`), which currently marks Hindi eligible — but
    `13_canonical_content.R` fixes `lang == "en"` unconditionally (`SLANT_EN`,
    line 58) and never reads that label. The table therefore advertises an
    eligibility the estimator does not act on. Deciding whether Hindi should
    enter the content estimands is an analysis decision, not a documentation
    one.
- **Ideology reliability is weak** on three of four dimensions. Those results are
  descriptive and exploratory.
- **The anchor judge's labels are unstamped** (they predate codebook version
  stamping). The composition is reported (`e22b`); whether the codebook text
  differed cannot be established from the files.
- **`draw_latent_labels()` is disabled** pending the validation study in §5e.
- **Pass 4 stance coding** is not part of this layer.
- **`e20_moral_by_language.csv`** remains retired as unsound (unpaired, with
  language-varying denominators).
- **Refusal-justification codes (A–G)** carry no estimand; agreement is too weak
  (α 0.32, raw agreement 0.20 on 595 units — the weakest of any construct here).
- **`judge_labels()` is defined twice** in `10_canonical_common.R`, at lines 281
  and 642; the second definition silently overrides the first. Both are on live
  code paths. Reported rather than changed, because collapsing them is an
  analysis edit.
- **`c07$estimable` does not mean what its name says.** It records that a fit was
  *attempted*, not that an estimate *exists*: five functional-form rows carry
  `estimable = TRUE` with `estimate_pp = NA`. Anything consuming `c07` must also
  require a finite estimate and interval, as ED2 now does.

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
| artwork | PNG-only header contradicted by a three-format exporter and an audit that required all three | one PNG, enforced end to end |

## 11. What changed in the figure revision (`canon_010`)

A forensic pass traced every plotted number to a table, row filter, weighting
target and uncertainty method (`FIGURE_ESTIMAND_AUDIT.md`), and compared at
least two graphical forms per panel (`FIGURE_REDESIGN_MEMO.md`). **No stale v1
or v2 estimate was found in any figure.** One new estimand; everything else was
a re-expression of an existing table.

| area | before | now |
|---|---|---|
| judge sensitivity | four absolute estimates per jurisdiction; the reader differences overlapping intervals by eye | `c17d`, the **paired** difference from the canonical judge, formed inside each replicate — intervals 16–49% as wide |
| the word "envelope" | this document called the union of intervals the envelope, contradicting `c17b` | the envelope is the range of the **point** estimates; the union is reported under its own name |
| ideology panel | four of five bins plotted, neutral annotated — all the ink for 8–20% of a distribution that sums to one | all five bins drawn as a distribution |
| unadjusted difference | in `c02` with a bootstrap interval, never plotted | Fig 1b |
| language heatmap | main figure, colour scaled to a single 61 pp cell, no uncertainty | ED4a, colour scaled to the 85th percentile, paired with its intervals in ED4b under one shared ordering |
| sensitivities | faceted by specification family; an empty functional-form facet held a sixth of the canvas for five rows with no estimates | faceted by jurisdiction; unplottable rows omitted and counted |
| post-outcome diagnostics | a sub-panel of the sensitivity figure | ED3, its own figure number |
| reliability | one statistic per construct | ED5, a construct × metric matrix — engagement has α 0.51 and AC1 0.97 on the same labels |
| `c07b`, `c08b` | written by the plotting script | written by `11_` and `12_`; H12 enforces it |
| figure geometry | each script chose its own; aspect ratios ran 183×81 to 183×208 mm | four approved canvases, checked with the `pHYs` chunk |
| in-plot text | titles, subtitles and methodological prose | panel letters, axes, labels; captions in `CANONICAL_FIGURE_LEGENDS.md` |
| panel-width audit | summed `null` grid units, got 0 for every panel, filtered the zeros out, reported OK | resolves the allocation the way grid does |
| release provenance | one `git_sha`, recorded before an 85-minute build | `git_sha_at_start`, `git_sha_at_end`, `tree_moved_during_build` |

## 12. What changed in the analysis and figure restructure (`canon_011`)

| area | before | now |
|---|---|---|
| Fig 1 | three panels: rates, unadjusted difference, standardized contrast | **one forest**, the two differences overlaid on a shared axis; absolute rates are a table, because they are a different quantity |
| Fig 1 descriptive weighting | response-weighted, undeclared | **equal-model**, declared, matching the standardized target |
| Fig 1 EU | a point at zero | structural zero, marked not estimable |
| Fig 2 | pooled language + per-model cloud + framing | pooled language + framing; the model × language display is ED4 only |
| model-level content | point estimates with **no uncertainty at all** | `c13`/`c15` carry issue-cluster and jackknife-FPC intervals, n, n_issues, n_missing, and estimability/support flags |
| ED2 | a multiverse forest mixing estimator, target, outcome and post-outcome rows | **four** comparable specifications per jurisdiction; the classified grid is `c07c` |
| response-length | a figure | `c07c`, class E, post-outcome diagnostic |
| sample-size stability | did not exist | `c21` + ED3 |
| prompt semantics | retired refusal-text UMAP | `c22` + ED8/ED9, one fixed prompt geometry with diagnostics |
| orderings | re-derived in three figure scripts from the data | `pipeline/_orders.R`, one declaration, shared with the estimation layer |
