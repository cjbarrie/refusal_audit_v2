# Analytical audit — home-region sensitivity

> **⚠ SCRIPT PATHS BELOW ARE OUT OF DATE — 2026-08-06c.** The v1 estimand layer
> (`20`, `21`, `22`, `23`, `25`, `30`) and the v2 layer (`40`–`47`) have been
> archived to `pipeline/archive/precanonical_v1|v2/`; `pipeline/archive/README.md`
> maps each to its replacement. The analyses the paper reports are specified in
> **`docs/CANONICAL_ANALYSES.md`**. This document is kept as a dated record of
> what was true when it was written.

Written 2026-08-03; slant section added 2026-08-04. Supersedes the estimand
treatment in `ANALYSIS_HANDOFF.md`. Generation is still running; regenerate
with

```bash
REFUSAL_RUN_DIR=annotations/full_v1 Rscript pipeline/run_all.R
```

---

## 1. Recommendation

**Treat the within-issue interaction contrast as primary.** On that estimand,
distinctive home-region sensitivity is a **China result and essentially only a
China result**.

| jurisdiction | primary (within-issue) | descriptive (within-jurisdiction) |
|---|---|---|
| **CN** | **+17.7 pp [14.5, 21.3]** | +18.8 pp |
| MENA | +0.1 pp [−1.7, 2.0] | +2.7 pp [0.7, 5.0] |
| India | +3.0 pp [0.2, 6.8] | −1.4 pp [−3.9, 1.5] |
| US | −0.8 pp [−1.7, 0.2] | +1.6 pp [−0.9, 4.6] |
| EU | 0 observed refusals; not estimable | — |

MENA's apparent home effect **does not survive** the within-issue comparison.
The raw structure shows why: Arab-focused issues are broadly sensitive, and
India's models refuse them at 12.5% against MENA's 13.4% from a much lower
baseline. Once the issue is held fixed, MENA models are not unusual on Arab
issues relative to everyone else answering the same issues.

India's +3.0 pp is nominally positive but rests on a single model (Sarvam) and
2,076 observations, and it flips sign between estimands. It should not be
reported as a finding.

## 2. Estimands and model equations

### Primary — within-issue, between-jurisdiction

```
refused ~ home * juris + tier + (1 | issue_id)
family = binomial, English, region_focus != "General", EU excluded
```

Contrast algebra, reference jurisdiction CN:

```
logit P(refuse) = b0 + b_home·home + b_j + b_hj·(home × juris_j) + b_tier·tier + u_issue
home log-odds effect:   CN = b_home ;   j = b_home + b_hj
```

**Why this is the interaction contrast.** `region_focus` and `topic_domain` are
**constant within `issue_id`** (verified by assertion in `20_estimates_home.R`;
the script aborts if that ceases to hold). `home` and `tier` vary within issue.
The random intercept therefore holds the issue fixed, and `home` is identified
only from variation across jurisdictions answering *the same issue*. That is a
difference-in-differences.

**Why not `juris * region`.** The brief's suggested parameterisation is not
estimable here: with `(1 | issue_id)`, region main effects are collinear with
the random intercept and `lme4` fails with `Downdated VtV is not positive
definite`. The `home` parameterisation is the identified equivalent and is more
transparent about which comparison is being made.

**Adjustment.** The issue random intercept absorbs region, topic domain, route,
contention score and any unmeasured issue characteristic — a stronger control
than adjusting for topic domain. `+ domain` is fitted as a sensitivity check; it
converges (issue SD 0.98 vs 1.17) and does not change conclusions.

### Descriptive — within-jurisdiction (NOT primary)

Separate logistic fits per jurisdiction, `refused ~ home + domain`, followed by
g-computation. Labelled throughout as *adjusted within-jurisdiction home-versus-away
difference*. Retained solely to show why the estimands diverge.

### Uncertainty

Probability-scale contrasts by g-computation over the observed sample with
fitted random effects; 95% intervals from a parametric bootstrap over the
fixed-effect covariance (2,000 MVN draws; 800 for sensitivity fits). The
descriptive specification uses an issue-cluster bootstrap (500 resamples of
issues) because it has no random effect to carry the clustering.

**Clustering unit is the issue throughout.** Responses are not independent: all
eleven models answer the same battery, regular and boundary prompts are paired
within issue, and languages repeat within prompt.

## 3. Diagnostics

| specification | issue SD | singular | max SE | warnings |
|---|---|---|---|---|
| primary | 1.17 | no | 0.29 | none |
| + topic domain | 0.98 | no | 0.50 | none |

**Structural zero.** Mistral Large 2512 produces **0 refusals in all five region
cells** (2,080 responses). This is complete separation, not sparsity. EU is
excluded from every model and reported as `0 observed refusals; contrast not
estimable`. It is never plotted as a point estimate at zero.

**Sparse cells.** Excluding EU, the smallest cell has 15 events (India × China).
India rests on one model.

**Not estimable, with reasons** (`e06b_not_estimable.csv`):

| specification | reason |
|---|---|
| `plus_contention_score` | constant within issue; absorbed by the issue RE |
| `plus_route` | constant within issue; absorbed by the issue RE |
| `boundary_prompts_only` | `Downdated VtV is not positive definite` |
| `drop_allam-7b` | `Downdated VtV is not positive definite` |

The first two are structural, not numerical: an issue-level attribute cannot be
separately identified alongside an issue random intercept.

## 4. Robustness

All in `e05_home_sensitivity.csv`; CN estimate shown.

| specification | CN home premium |
|---|---|
| primary | +17.7 pp |
| + topic domain | converges, conclusions unchanged |
| regular prompts only | converges |
| exclude the 300 back-translated prompts | converges |
| leave-one-model-out (8 of 10 fits) | converges |

**China decomposition** (`e07_cn_model_decomposition.csv`) — the result is not
driven by one model:

| | home premium |
|---|---|
| DeepSeek only | +16.2 pp [12.4, 21.0] |
| Qwen only | +19.2 pp [14.8, 23.8] |

**US and MENA** leave-one-out fits converge for all models except ALLaM, and no
jurisdiction's null result becomes positive when any single model is removed.

## 5. Language: do NOT claim additivity

`refused ~ home * lang + tier + (1 | issue_id)`, fitted per CN model.

| model | home premium, English | home premium, Chinese | interaction (log-odds) | p |
|---|---|---|---|---|
| qwen3-max | +16.9 pp [11.5, 23.8] | +16.5 pp [11.4, 22.6] | +0.20 | 0.48 |
| deepseek-chat-v3.1 | +15.1 pp [10.9, 20.3] | +20.4 pp [13.6, 27.5] | **−1.11** | **2.6e-05** |

**These are scale-dependent and must be reported as such.** For Qwen the home
gap is statistically indistinguishable across languages. For DeepSeek the
probability-scale premium is *larger* in Chinese while the log-odds interaction
is significantly *negative* — a consequence of DeepSeek's much higher Chinese
baseline (14.5% away vs 2.6% in English) compressing the odds ratio.

The defensible statement is: **the home premium is of similar magnitude in both
languages, while the baseline shifts sharply for DeepSeek and not at all for
Qwen.** The earlier claim of additivity was not supported by any estimate.

## 6. Disagreements with the previous interpretation

1. **"CN and MENA show home effects"** — wrong on the primary estimand. MENA is
   +0.1 pp [−1.7, 2.0].
2. **"The regional and linguistic effects are additive"** — not established;
   DeepSeek's interaction is significant on the log-odds scale.
3. **"Adjusted for topic domain"** — understates the design. The issue random
   intercept absorbs domain *and* region *and* unmeasured issue characteristics.
4. **The raw-rate heatmap was presented as evidence for the home effect.** It
   confounds jurisdiction propensity, region sensitivity and their interaction.
   It is replaced by an excess-over-additive-baseline matrix, on which MENA's
   Arab cell is near zero.

## 7. Slant (passes 2/3) — added 2026-08-04

Ideology and moral-foundation coding was reinstated over a **25% issue
subsample** (156 issues, seed 20260803) after having been dropped in the
Pass-1-only trim. `pipeline/22_estimates_slant.R`, figures `FIG4` / `P9`–`P11`,
rationale in `docs/SLANT_SUBSAMPLE.md`.

**Three design points a reviewer will press on, and the answers.**

1. **Why subsample at the issue level rather than the response level?** Because
   responses are clustered within issue — every model answers every issue.
   Response-level sampling would have broken the clustering every interval here
   depends on and left ragged model × language × tier cells. Issue-level
   sampling leaves the cell structure intact.
2. **Why are the slant tables English-only when FIG1–3 are English for a
   different reason?** FIG1–3 use English for comparability. FIG4 must, because
   the roster is not constant across languages (11 models answer in en/zh/ar, 9
   in ru, 7 in hi). Pooling would confound a jurisdiction's measured slant with
   which of its models happen to answer in which language. `e20` compares the
   three complete-roster languages and finds no meaningful difference.
3. **Are slant and refusal comparable?** **No.** Passes 2/3 skip refusals by
   design, so slant is conditional on engagement. A jurisdiction that refuses
   more contributes a differently selected set of responses. Do not read FIG1
   and FIG4 as two views of one quantity.

**The ideology result is a near-null, and should be presented as one.** The
judge codes 74–93% of engaged responses as exactly 0 on every dimension.
Jurisdiction means span about +0.03 to −0.16 on a −2..+2 scale. The largest
signals — US economic +0.032 [0.016, 0.048], EU social −0.119 [−0.163, −0.074],
EU populist −0.162 — are statistically distinguishable from zero but
substantively tiny.

This is why FIG4A plots the **distribution** and not the mean: a
mean-with-interval panel would put five dots on the origin and read as a failed
instrument, when the actual result is that the instrument fired and found
neutrality. The neutral category is removed from the bars and printed as a
number so the tails are visible at the scale they occur.

**The honest caveat**: a near-total concentration at 0 is consistent with
genuinely neutral answers *and* with a judge reluctant to assign a side. This
design cannot separate them. A second judge or a human-coded validation subset
would; neither exists. State this whenever the ideology null is reported.

**Moral foundations are where the variation is.** Prevalence ranges from 58–71%
(fairness/cheating) to under 4% (sanctity/degradation), with clear jurisdiction
ordering: EU models invoke care, fairness and liberty most; CN models lead on
loyalty/betrayal and authority/subversion. The foundations are **not mutually
exclusive**, so shares within a jurisdiction do not sum to 1 — do not present
them as a composition.

## 8. Limitations that shape presentation

- **No inter-rater reliability.** Single Gemini judge; `16_irr_analysis.R` skips
  because no second-judge file exists. The pipeline reads that file from
  `REFUSAL_RUN_DIR`, so adding it requires no redesign.
- **Rare outcome** (~5.4% in the primary sample) and one jurisdiction with zero
  events.
- **English only.** Non-English coverage is complete for the seven OpenRouter
  models but not the four self-hosted ones.
- **Descriptive, not causal.** The issue random intercept controls issue-level
  confounding; it does not licence a causal reading of jurisdiction.
- **Counts will change.** Generation is incomplete: the four self-hosted models
  are still missing most Russian and Hindi responses. The primary English
  estimates are complete (11/11 models) and will not move.
- **Slant rests on 156 issues** and is conditional on engagement; its intervals
  are issue-clustered bootstrap (800 resamples) and are correspondingly wide.
  When generation finishes, the subsample needs a top-up annotate pass to cover
  the new ru/hi responses — the manifest is reused, so the draw does not change.
