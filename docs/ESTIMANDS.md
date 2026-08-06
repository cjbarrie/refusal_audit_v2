# Every estimand in this repository

> **HISTORICAL CATALOGUE — superseded 2026-08-06.**
> The canonical analyses are specified in
> [`CANONICAL_ANALYSES.md`](CANONICAL_ANALYSES.md), and the scripts that produced
> the v1 and v2 layers described below have been moved to `pipeline/archive/`
> (file-by-file mapping in [`pipeline/archive/README.md`](../pipeline/archive/README.md)).
> **Quote nothing from this document in the paper.** It is kept because every
> number in an earlier draft came from one of these estimands, and a reader who
> finds an old figure needs to be able to work out what it was.

Written 2026-08-06. A complete catalogue of what this project estimated, the
model behind each quantity, and — the part that matters most — **what each one
could and could not support**.

At the time of writing the repository carried **two layers, both live**:

| layer | scripts | tables | figures | status |
|---|---|---|---|---|
| **v1** | `01`–`30` | `e01`–`e31`, `d01`–`d08` | `FIG1`–`FIG5`, `P1`–`P14` | archived → `precanonical_v1/` |
| **v2** | `40`–`47` | `e32`–`e40` | `FIGA`–`FIGC` | archived → `precanonical_v2/` |

They **disagreed on the home-region question**, and both sets of figures were
public at once. Part III below says which to quote and why — that comparison is
now settled by the canonical layer, which supersedes both. The estimate CSVs
themselves remain in `pipeline/estimates/`; `c01_reconciliation.csv` reads
several of them to explain how the canonical numbers differ.

**Conventions that hold everywhere unless a section says otherwise.** Unit of
observation is one model response to one prompt in one language. The judge is
`google/gemini-2.5-flash-lite` at temperature 0. Intervals are 95%. Where a
quantity is clustered, the cluster is `issue_id`. "pp" is always 100 × a
probability difference.

---

# PART 0 — Shared foundations

## 0.1 The analysis sample

| | |
|---|---|
| Rows | **137,186** |
| Structure | 11 models × 2,496 prompts × 5 languages, one row per cell |
| Issues | 624 (4 prompts each: 2 regular, 2 boundary) |
| Assertion | one row per `model × prompt_id × language` — verified, 0 duplicates |

**Reconciliation** (`e40`), traced end to end:

```
137,280  response keys attempted
137,188  responses successful          (92 keys never succeeded)
137,187  clean annotations             (1 response never judged)
137,186  assembled + in data_clean     (1 annotation superseded by a later error row)
```

Every one of those four losses is named in the exclusion ledger, including the
two most recent generation failures. Nothing is silently dropped.

**The mutable `pilot_config.json` is not used as a run manifest.** The
authoritative inputs are the artifacts themselves, hashed in
`v2_analysis_spec.json`.

---

## 0.2 Outcome definitions — and why code 3 is never quietly moved

The judge emits a 1–5 engagement code. Code 3 ("partial refusal / mixed") is the
ambiguous one, and where it is put changes results. It therefore appears in
**all three** representations, never silently relabelled:

| definition | rule | role |
|---|---|---|
| `refused_strict` | codes 4–5 | **primary** |
| `refused_any` | codes 3–5 | sensitivity |
| three-category | 1–2 / 3 / 4–5 | code 3 stands alone |
| ordinal | 1–5 mean | measurement sensitivity, commits to no cut |

Code 3 is **921 of 137,186 rows (0.67%)**, so the strict/any choice moves the
headline very little — CN's descriptive difference is +11.71 pp strict against
+11.68 pp any. That is a finding, not a reason to skip the check: it means the
refusal results do not hinge on where the ambiguous category is placed.

The ordinal analysis is reported in **engagement-code units, not percentage
points**, and the acceptance tests enforce that it never carries a `pp` column.

---

---

# PART I — the v1 estimands (currently plotted in FIG1–FIG5)

Everything in this part is produced by scripts `01`–`30` and is what the current
main figures show. It remains reproducible and untouched.

## I.1 Home region — the v1 treatment

### I.1.a Primary contrast (`e01`, `e02`; FIG1B, `P2`)

```
refused ~ home * jurisdiction + tier + (1 | issue_id)      binomial
```

English, non-General, EU excluded (complete separation). Probability-scale
g-computation, then a **parametric bootstrap over the fixed-effect covariance
with the fitted issue BLUPs held fixed** — so the interval carries fixed-effect
uncertainty only and the estimand is **sample-conditional** (averaged over the
observed issues at their estimated effects), not marginal over a population of
issues. `e02` is the odds-ratio companion.

Result: CN **+17.5** [14.3, 21.1], MENA +0.2, India +3.0, US −0.7 pp; EU not
estimable.

**v1 called this a "within-issue" difference-in-differences.** The reasoning was
that region and domain are constant within issue, so the issue random intercept
absorbs both and `home` is identified from variation *across jurisdictions
answering the same issues*. **v2 retires that label** — see Part III.

### I.1.b Descriptive within-jurisdiction contrast (`e03`, `e04`; FIG1B hollow points, `P3`)

```
glm(refused ~ home + domain)     fitted separately per jurisdiction
```

Issue-resampled bootstrap that **refits inside each replicate**. Reported as
*descriptive*: it cannot separate "this jurisdiction is sensitive about its own
region" from "this region is sensitive to everyone", which is why v1 did not make
it primary. `e04` pairs the two estimands for the FIG1B dumbbell.

### I.1.c Per-model home premium (`e21`; `P12`)

```
refused ~ home * model + tier + (1 | issue_id)
```

Added because the pooled `home × jurisdiction` specification assigns **every
model in a jurisdiction the identical fitted contrast** — DeepSeek and Qwen both
returned exactly 17.5514 — which made the usual "response- vs equal-model
weighting agree" reassurance vacuous. This specification makes the
within-jurisdiction spread visible: Qwen +19.0, DeepSeek +16.1, GPT-5.1 −2.4.

### I.1.d Weighting sensitivity (`e22`)

Response-weighted, equal-model-weighted, and leave-one-model-out jurisdiction
means derived from `e21`. Single-model jurisdictions (India, EU) are flagged as
undefined for both.

### I.1.e Specification sensitivities (`e05`, `e06`, `e06b`, `e07`)

`plus_topic_domain`, regular-only, boundary-only, excluding back-translated
prompts, and leave-one-model-out. `e06` records issue SD, singularity, max SE and
which optimiser converged; `e06b` records specifications that are **not
identified** (e.g. `contention_score` and `route` are constant within issue and
absorbed by the random intercept). `e07` decomposes CN by model.

### I.1.f Region structure (`e08`; FIG1C, `P4_raw`, `P4_excess`)

Two distinct quantities from the same cells, kept apart:

- **raw cell rates** — observed refusal rate per jurisdiction × region, Wilson
  intervals computed;
- **excess** — observed minus a **fitted additive-in-logit baseline**,
  `glm(cbind(events, n−events) ~ jurisdiction + region, binomial)` on cell
  counts, weighted by cell size. It is *not* arithmetic row/column means and
  *not* a residual from the primary mixed model.

## I.2 Prompt framing (`e11`, `e12`, `e12b`; FIG2, `P6`, `P7`)

```
per model:   refused ~ tier + (1 | issue_id)
pooled:      refused ~ tier * domain + (1 | issue_id) + (1 | model)
sensitivity: refused ~ tier * domain + model + (1 | issue_id)
```

Regular and boundary prompts derive from the **same issue by design**, so these
are genuinely paired within-issue comparisons — independent-binomial intervals
would be wrong twice over (pairing, and issue recurrence across models).
Probability-scale g-computation with a parametric bootstrap over fixed effects.

Treating model as **fixed** rather than random moves every domain shift by at
most **0.15 pp** (`e12b`), so the choice is immaterial and documented as such.

**Supports:** that boundary framing shifts refusal in opposite directions across
models and domains, and that for grok-4.3, qwen3-max and allam-7b the shift
includes zero. **Does not support:** a causal claim about framing beyond these
prompts.

## I.3 Refusal rationales (`e13`, `e13b`, `e14`; FIG3, `P8`)

Composition of the judge's justification codes, **conditional on having
refused** — the denominator is that model's refusal count, so a high share says
nothing about how often the model refuses. Wilson intervals; models with <30
refusals omitted.

`e13b` carries the **raw seven codes** so the collapse is auditable. The collapse
is 7 → **5** (`neutrality`, `harm`, `epistemic`, `other`, `none given`), not 4:
code G ("other") is 15.7% of English refusals and its free text mixes degenerate
output, explicit task refusals and epistemic statements, so folding it into
"none given" hid a measurement failure mode — worst for allam-7b, where it is
31.7% of 426 refusals. Codes B and E fire on **two responses each**, so
"epistemic" is effectively code D alone.

## I.4 Slant — ideology and moral foundations (`e15`–`e20`; FIG4, `P9`, `P10`, `P11`)

**Sample: a 25% issue subsample, engaged responses only, English.** Passes 2/3
skip refusals by design, so every slant quantity is **conditional on engagement**
and is not comparable across jurisdictions with different refusal rates.
Intervals are **issue-clustered bootstrap** (800 resamples).

| table | quantity |
|---|---|
| `e15` | ideology distribution across −2..+2, by jurisdiction × dimension |
| `e16` / `e16b` | ideology means; `e16b` adds neutral share, median, pole shares |
| `e16c` | model-level decomposition within jurisdiction |
| `e17` / `e17b` / `e17c` | moral-foundation prevalence; pooled; equal-model-weighted |
| `e18` | prevalence by model |
| `e19` | subsample coverage |
| `e20` | prevalence by prompt language (en/zh/ar — the complete-roster languages) |

**English-only for a different reason than FIG1–3**: the roster is not constant
across languages (11 models in en/zh/ar, 9 ru, 7 hi), so pooling would confound
slant with roster composition.

Ideology is **near-null**: 74–93% of engaged responses are coded exactly 0. That
is reported as a measurement result, and the figure plots the *mean with its
neutral share attached* rather than bars that would exaggerate the non-neutral
remainder. Moral foundations are **not mutually exclusive** (1.83 per response;
13.9% invoke none), so no stacked or composition form is valid.

Jurisdiction is **defined by** model membership, so a model-adjusted jurisdiction
contrast is not identified. These are descriptive averages, labelled as such.

## I.5 Language — the v1 treatment (`e09`, `e10`, `e29`, `e30`, `e31`; FIG5, `P5`, `P13`, `P14`)

```
e29:  refused ~ language + tier + (1 | issue_id)          per model
e31:  refused ~ home * language + tier + (1 | issue_id)   per jurisdiction
e10:  refused ~ home * language + tier + (1 | issue_id)   per CN model
```

`e29` contrasts each language against English **within model**, with the issue
held fixed by the random intercept. `e30` isolates each model's own-sphere
language (CN→zh, MENA→ar, India→hi; US/EU are English-native so no contrast
exists — reported as undefined rather than dropped). `e09`/`e10` are the
CN-specific precursor that `e31` generalises.

⚠ **`e10`, `e31` and FIG5B are within-*jurisdiction* contrasts, not the primary
cross-jurisdiction quantity.** Within one jurisdiction `home` is constant within
issue, so it is identified from *between*-issue variation and the random
intercept shrinks it.

Result: no consistent home-language effect — falcon3 **+24.1**, deepseek +11.2,
jais +1.1, allam −0.4, qwen −0.7, sarvam **−4.8**.

## I.6 Engagement and DeepSeek-specific analyses (scripts `02`, `06`–`09`)

- `02` — `glm(engaged ~ language × model, binomial)` with `ggpredict` marginals.
- `06` — justification composition by model and model × language.
- `07` — DeepSeek en-vs-zh tables; its ideology table (37) is guarded on
  `has_slant` because the means rest on the 25% subsample, not on every row.
- `08` — per-domain χ²/Fisher (Fisher when min expected < 5) plus
  `glmer(refused ~ language × domain + (1|issue_id))`.
- `09` — bootstrap odds ratios, Cramér's V, **BH-corrected** p-values.

These are exploratory and precede the estimand discipline of the later scripts.

## I.7 Measurement reliability (`e23`–`e28`; from `24_measurement.R`)

Multi-judge panel. **Krippendorff's α** throughout (the only statistic that takes
k raters, missing cells and mixed measurement levels), plus **Gwet's AC1** and
**positive specific agreement**, because refusal (~5.6%) and sanctity (~3%) are
rare enough that α alone hits the kappa paradox.

| table | quantity |
|---|---|
| `e23` | Pass 1 reliability — engagement (ordinal) and refusal (binary) |
| `e24` | justification codes, conditional on all judges calling it a refusal |
| `e25` | ideology (ordinal) and moral foundations (binary) |
| `e26` / `e26b` / `e26c` | per-judge marginals; pairwise vs anchor; leave-one-judge-out |
| `e27` | **differential-error test** — is disagreement concentrated where the finding lives? |
| `e28` | consensus labels (majority / unanimous), for re-estimation only |

`e23`–`e28` currently hold the **7-judge bake-off on the 12-issue pilot slice**,
not the Tier-1 English sample (which was still annotating when this was written).
Binary refusal: raw agreement **0.908**, α **0.485**, **AC1 0.956**, and
**positive specific agreement 0.0795** — when any judge flags a refusal, all seven
agree only ~8% of the time. The earlier 4-judge pilot gave 0.920 / 0.498 / 0.952 /
0.107; adding judges lowers unanimity-based agreement as expected. Majority vote
is **never** treated as ground truth.

## I.8 Diagnostics (`d01`–`d08`; from `23_diagnostics.R`)

Engagement-code frequencies; justification codes raw and collapsed; ideology
distributions and neutral prevalence; moral co-occurrence and pairwise lift;
missingness split **structural vs incidental**; per-cell denominators and event
counts; weighting structure (models per jurisdiction). Nothing here is plotted —
these exist so graph precision cannot be mistaken for measurement precision.

---

# PART II — the v2 estimand layer

## II.1 Family A — descriptive home results (`e32`, `FIGA`)

**Question.** On issues about a model's own region, how often does it actually
refuse, compared with issues about other regions?

**Model.** None. Counts and weighted means of observed 0/1 outcomes.

**Three region positions, not two.**

```
home     issue region == the model jurisdiction's own region
away     a different named region
general  no regional focus at all (17% of the battery)
```

`general` is reported as its own category and **never enters the away
reference**. Folding it in would score every model "away" on a sixth of the
battery and drag the reference toward the global average. Verified: 0 General
rows coded away.

**Result** (response-weighted; equal-model agrees to 3 decimals because the
design is balanced):

| | home | away | general | home − away |
|---|---|---|---|---|
| CN | 16.73% | 5.02% | 2.88% | **+11.71** [8.82, 14.90] |
| MENA | 26.11% | 21.32% | 19.04% | **+4.78** [2.96, 6.67] |
| India | 3.80% | 3.68% | 2.99% | +0.12 [−0.85, 1.16] |
| US | 1.92% | 2.90% | 1.42% | −0.97 [−2.08, 0.18] |
| EU | 0% | 0% | 0% | 0 refusals anywhere |

**What this supports.** A statement about *these* models on *this* battery: CN
models refused China-focused prompts at 16.7% against 5.0% elsewhere. Nothing
more. It is not adjusted for anything — not prompt tier, not topic domain, not
which models supply the rows.

**What it does not support.** Any claim that the *region* caused the difference.
Home and away issues differ systematically in topic (45% of China issues are
territorial-sovereignty), so this comparison mixes region with everything
correlated with it.

**Three strata are structurally non-estimable** and say so rather than emitting a
silent `NA`: CN × temporal-route, CN × social_moral and India × social_moral each
contain **zero home rows**. Several finer strata carry a note that their interval
is *conditional on estimability* — up to 36% of bootstrap replicates lost an arm
entirely.

---

## II.2 Family B — standardized home contrasts (`e33`/`e34`/`e35`, `FIGB`)

**Question.** Holding prompt tier, topic domain, harvest route and subject model
fixed, how much does home-region status shift the probability of refusal within a
jurisdiction?

**Model**, fitted separately per jurisdiction:

```
refused ~ home + tier + domain + route + model
```

**No region fixed effects.** Within a jurisdiction, region *determines* home, so
a region term would be collinear with the contrast of interest.

**English only.** The specification carries no language term, so pooling five
languages would be misspecified — language effects here reach +62 pp and would
load onto the other terms. Language enters as a sensitivity that repeats the
whole procedure within each language. This is a stated modelling choice.

**Sample.** home vs away. General is excluded entirely from Family B (it has no
home jurisdiction) and appears only in Family A.

**Contrast.** Probability-scale g-computation:

```
mean[ P(Y=1 | home=1, X) − P(Y=1 | home=0, X) ]
```

**Standardization target.** Primary is **equal weight per tested model and
issue**, so a jurisdiction's contrast is not driven by whichever models or issues
supply more rows. Empirical response weighting is the sensitivity.

**Uncertainty.** Issue-cluster bootstrap with the **complete model refit and the
standardization recomputed inside every replicate**; ≥2,000 successful
replicates; percentile intervals. Fixed-coefficient simulation is not used as the
primary interval method anywhere in this family.

**Result:**

| | primary (equal model×issue) | response-weighted | events home / away |
|---|---|---|---|
| CN | **+16.47** [9.32, 24.89] | +16.47 | 163 / 119 |
| MENA | **+3.76** [1.44, 6.34] | +3.76 | 170 / 387 |
| India | −3.07 [−5.81, 0.19] | −3.07 | 31 / 108 |
| US | +1.87 [−0.74, 4.60] | +1.87 | 43 / 231 |
| EU | not estimable | — | 0 / 0 |

### What Family B is NOT

**It is not causal. It is not a difference-in-differences. It is not a
within-issue effect.** `home` is a fixed property of an issue's region; nothing
randomises it, and no comparison here holds an issue fixed while varying home.
Those three descriptions are **banned strings** — `46_v2_acceptance_tests.R`
fails the build if any appears unnegated in a v2 output, and `audit_figures.R`
fails it for the figure layer.

The honest description is: *a covariate-standardized contrast in refusal
probability between home and away issues, within jurisdiction, standardized to a
stated target population.*

### What the sensitivities show

CN is stable across every one; MENA is not:

| sensitivity | CN range | MENA range |
|---|---|---|
| per model | 14.7 – 17.6 | 0.7 – 8.7 |
| leave one model out | 14.7 – 17.6 | 1.3 – 5.4 |
| prompt type | 15.0 – 17.7 | 3.76 – 3.77 |
| language | 15.6 – 27.3 | −1.0 – 4.5 |
| min response length | 14.5 – 16.2 | 3.73 – 3.75 |

MENA's per-model spread (0.7 to 8.7) is wider than its pooled interval, so the
MENA result is a **composite of heterogeneous models**, not a jurisdiction-level
regularity. CN's is not: both Chinese models sit at 14.7 and 17.6.

### The hierarchical sensitivity, and why it differs

```
refused ~ home + tier + domain + route + model + (1 | issue_id) + (1 | prompt_id)
```

with **population-level (marginal) predictions**: the contrast is integrated over
the random-effect *distribution*, drawing u ~ N(0, σ̂²) rather than plugging in
the fitted BLUPs. Holding BLUPs fixed while toggling `home` would answer a
different question — the contrast for these particular issues at their estimated
effects — and would understate the variance being integrated over.

**CN falls from 16.47 to 7.16 pp.** This is expected, not a discrepancy:
marginalising a non-linear link over a large random-effect variance attenuates a
probability-scale contrast. The two numbers are different estimands — conditional
on the covariate profile vs marginal over the issue/prompt population — and both
are reported. **US failed to converge** (degenerate Hessian); it is flagged, not
imputed.

### EU

Mistral Large records **zero refusals in every cell**. That is complete
separation, not a small effect. EU is preserved as **descriptively observed**
(Family A shows the zeros) but **statistically non-estimable** in Family B. It is
never given a fitted contrast and never drawn as a zero estimate.

---

## II.3 Family C — prompt-fixed language effects (`e36`/`e37`, `FIGC`)

**Question.** Delivering the *same prompt* to the *same model* in a different
language, how does the probability of refusal change?

**Block.** `block_id = model × prompt_id`. Each block holds at most one response
per language.

**Estimator.**

```
delta_L = mean over COMPLETE blocks of ( Y[block, L] − Y[block, English] )
```

A paired within-block difference, computed directly from observed outcomes. No
model is required and it reproduces a direct tabulation exactly.

**The LPM equivalence is algebraic, not approximate.** With exactly two
observations per block, demeaning gives x̃ = ±0.5 and ỹ = ±d/2, so
β = Σ(d/2)/Σ(0.5) = mean(d). `refused ~ language + factor(block_id)` is the same
number by construction. It is verified numerically on a 400-block random subset —
fitting 27,000 block dummies is not merely slow, it is the wrong way to compute
something with a closed form.

**Uncertainty.** Issue-cluster bootstrap, carrying all models, prompts and
languages for a drawn issue together.

**Result:**

| language | paired difference | complete blocks | missing |
|---|---|---|---|
| Chinese | **+1.32** [0.93, 1.72] | 27,440 | 16 |
| Arabic | **+2.33** [1.93, 2.72] | 27,437 | 19 |
| Russian | **+3.95** [3.54, 4.32] | 27,430 | 26 |
| Hindi | **+8.52** [8.07, 8.98] | 27,402 | 54 |

By model (`e37`) the pooled figures conceal enormous heterogeneity: allam-7b
**+61.4 pp** in Hindi and **+51.7** in Russian; falcon3-10b +25.3 Hindi, +24.1
Arabic; jais-8b +17.3 Hindi. US models sit near zero throughout.

### What this supports — stated carefully

The effect of **delivering the tested translated prompt version**, among the
tested prompt/model set, **conditional on**:

- **translation equivalence** — if a translated prompt is harder, more ambiguous
  or differently loaded, that is inside the estimate and cannot be separated from
  a language effect;
- **no run-order or provider confounding** — languages were generated in
  different runs and sometimes through different provider routings, so serving
  drift is also inside the estimate.

It is **not** the causal effect of a user's language, and it does not generalise
beyond these prompts and models.

**Secondary estimators.** Conditional logistic and GLMM target different subsets
(discordant blocks only) and different scales (log-odds, conditional). They are
secondary and are not the headline.

**Language × home-status** heterogeneity is reported as a *descriptive
interaction* — how the language difference varies with an issue's home status. It
is explicitly not a home-region causal effect.

---

## II.4 Uncertainty, across all three v2 families

- **Outer bootstrap unit is always `issue_id`.** An issue supplies four prompts
  to every model in every language; resampling rows would badly understate the
  spread. Verified across all **412 bootstraps**.
- **Refit and re-standardize inside every replicate** wherever a model is
  involved.
- **401,028 successful replicates, 5,764 failed** — failures counted, never
  silently dropped, with drawing continued until the target is met.
- Seed `20260806`, percentile intervals, all recorded in `e39`.
- Three weightings reported: response, equal-model, equal-model×issue, plus
  leave-one-model-out.

### The annotation-error layer is architected, not active

`draw_latent_labels()` exists as a hook for a future measurement-error
correction. It **raises if called**. There is no human calibration, and inventing
sensitivity/specificity would manufacture precision the study has not earned.

Until then: **every judge is reported separately and a judge-sensitivity range is
given; majority vote is never treated as ground truth.**

| judge | English refusal rate | n |
|---|---|---|
| gemini-2.5-flash-lite (canonical) | **5.14%** | 27,449 |
| nemotron-3-super-120b | 3.96% | 6,749 (partial) |
| gemma-4-31b | 3.39% | 27,449 |
| nemotron-3-nano-30b | 2.97% | 27,449 |

**The canonical judge is the highest of the four.** Every headline rate in the
study derives from it. Without ground truth the panel cannot say whether it
over-detects or the others under-detect — but the range belongs in any write-up.

---

---

# PART III — how the two layers relate

## III.1 The same question, asked three ways

The home-region question is the one place v1 and v2 genuinely disagree, and the
disagreement is about **what was asked**, not about arithmetic.

| | v1 `e01` | v2 `e32` (A) | v2 `e33` (B) |
|---|---|---|---|
| model | `home × juris + tier + (1｜issue)` | none | `home + tier + domain + route + model`, per jurisdiction |
| adjusts for | tier; issue absorbed | nothing | tier, domain, route, model |
| standardized to | observed sample at fitted BLUPs | observed sample | equal weight per model and issue |
| interval | fixed-effect draws, BLUPs fixed | issue bootstrap | issue bootstrap, **refit + re-standardized per replicate** |
| CN | **+17.5** | **+11.71** | **+16.47** |
| MENA | +0.2 | +4.78 | +3.76 |
| India | +3.0 | +0.12 | **−3.07** |
| US | −0.7 | −0.97 | +1.87 |
| EU | not estimable | 0 observed | not estimable |

**Only China is stable across all three.** India and the US move enough to change
sign depending on which question is asked — which is the honest summary of a
quantity that is small relative to its uncertainty in both jurisdictions.

## III.2 What changed, and why

**"Within-issue" is retired.** v1 justified the label by noting that region and
domain are constant within issue, so the random intercept absorbs them and `home`
is identified from variation across jurisdictions answering the same issues. The
algebra is right; the label is not. Nothing randomises `home` — it is a fixed
property of an issue's region — and a reader hearing "within-issue
difference-in-differences" will infer a design that identifies a causal effect.
It does not. v2 therefore bans the strings *causal*, *difference-in-differences*
and *within-issue* from Family B outputs, enforced by
`46_v2_acceptance_tests.R` and `audit_figures.R`.

**Uncertainty was upgraded.** v1's primary interval drew from the fixed-effect
covariance with the fitted BLUPs held fixed. v2's outer bootstrap resamples whole
issues and **refits the model and re-standardizes inside every replicate**, which
is why v2 intervals are wider (CN [9.32, 24.89] against v1's [14.3, 21.1]). The
wider interval is the more honest one for a quantity whose model is being
estimated from the same data.

**`General` was promoted to a third position.** v1 excluded General from home
contrasts and did not report it as a category. v2 reports it explicitly, because
"no regional focus" is not a kind of "away".

**Covariates were added.** v1's primary model adjusts for tier only (domain being
absorbed by the issue intercept). v2's Family B adjusts for tier, domain, route
*and* model directly, because the per-jurisdiction fit has no issue intercept to
absorb them.

## III.3 Which to quote

- **Home region** — quote v2. `e32` for a plain description, `e33` for an
  adjusted contrast. Do not quote `e01` without noting the label change.
- **Language** — v2 `e36`/`e37` for the paired effect (it is exact and
  assumption-light); v1 `e29` remains valid and gives the same qualitative
  picture through a mixed model.
- **Prompt framing, refusal rationales, slant, reliability, diagnostics** — v1
  only. **v2 does not restate these**, and they are unaffected by the home-region
  relabelling.

**FIG1 and FIG5 still show v1 quantities**, including the "within-issue" axis
label on FIG1B. Until the canonical figure set is chosen, a reader comparing
FIG1 with FIGB will find CN at +17.5 and +16.47 with no on-figure explanation.
That is the single most important open item in `docs/NEXT_STEPS.md`.

# PART IV — provenance, running, acceptance

## IV.1 Provenance — what is evidenced and what is asserted

**Judge labels.** Gemini 2.5 Flash-Lite produced the canonical outcomes. This is
**run-level historical metadata confirmed by the project owner**, not recoverable
per row: `judge_model` was added to the schema on 2026-08-04, so **119,881 of
137,186 rows carry no judge field**. It has not been back-filled — that would be
fabricated row-level provenance.

**`judge_prompt_version` drift.** Two hashes appear among rows that carry one.
Diagnosed as **implementation drift, not codebook drift**: the hash covers all
large triple-quoted blocks in `annotation_pipeline.py`, so unrelated docstring
edits changed it while the Pass 1–3 codebooks were untouched. Manifest drift.
**Not a reason to re-run paid annotation.**

**Panel judge IDs.** Panel artifacts use filesystem-safe slugs (`/` → `__`), so
they differ textually from the config's model IDs. Mechanical and reversible;
config drift only.

**Geographic review.** Recorded as a **run-level assertion** at the project
owner's direction. The issue records carry `needs_review` (TRUE for all 2,773 —
i.e. a review *requirement*, not a completed review) and `source_article_status`,
but **no reviewer, date or approval field exists anywhere**. None was invented.

---

## IV.2 How to run the v2 layer

```bash
Rscript pipeline/41_v2_home_descriptive.R    # e32          ~2 min
Rscript pipeline/42_v2_home_standardized.R   # e33-e35   ~90 min
Rscript pipeline/43_v2_language_paired.R     # e36-e37     ~8 min
Rscript pipeline/44_v2_outcome_sensitivity.R # e38         ~5 min
Rscript pipeline/45_v2_reconciliation.R      # e40 + spec  ~5 min
Rscript pipeline/47_v2_figures.R             # FIGA-C      ~1 min
Rscript pipeline/46_v2_acceptance_tests.R    # gate
```

Run 41–44 before 45: `e39` accumulates bootstrap diagnostics by appending, and
45 summarises it. Family B dominates the runtime (2,000 refits per contrast).

**Not registered in `run_all.R`** — it would add ~2 hours to every routine run.
Invoke explicitly until the canonical set is decided.

---

## IV.3 Acceptance criteria (all passing)

`46_v2_acceptance_tests.R`, 27 checks, each recomputing its target independently:

- descriptive estimates reproduce direct counts **exactly** (< 1e-12)
- paired language estimates reproduce within-block differences **exactly**
- LPM block-FE check agrees with the paired estimator
- no unnegated causal / DiD / within-issue language in any v2 output
- code 3 present in all three representations; ordinal analysis present
- equal-model weights sum equally within jurisdiction (max deviation 9.7e-14)
- every bootstrap resamples whole issues; all ≥2,000-replicate runs achieved it
- results invariant to input row order (descriptive and model coefficient)
- `estimate_pp` == 100 × `estimate` everywhere; ordinal reports no pp
- General never enters the away reference
- language contrasts compare identical blocks
- legacy `e01`/`e29`/`e30`/`e31` still present
- spec records **zero API calls**
