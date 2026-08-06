# Forensic audit and redesign memo — analysis and figure system

Written 2026-08-04, before implementation. Every numeric claim here was
recomputed from `data_clean.RData` or the estimate tables, not copied from
prior documentation.

Data state at audit time: **119,893 rows**, 624 issues, 2,496 prompts, 11
models, 5 languages. Generation is still running (Russian/Hindi incomplete for
the four self-hosted models), so counts move; **English is complete for all 11
models** and every primary estimate is English-only.

---

## PART 0 — Structural validation (all passed)

| check | result |
|---|---|
| `issue_id` unique and stable | 624 issues, 2,496 prompts = exactly 4 per issue |
| tier pairing within issue | all 624 issues have exactly 2 regular + 2 boundary |
| `region_focus` constant within issue | 0 violations |
| `topic_domain` constant within issue | 0 violations |
| duplicate `(prompt_id, language, model)` | 0 |
| model → jurisdiction mapping | correct; US 4, MENA 3, CN 2, EU 1, India 1 |
| `General` excluded only where home is undefined | confirmed |
| engagement codes | 1: 94,447 · 2: 17,940 · 3: 810 · 4: 4,369 · 5: 2,327 |
| missing `engagement_code` | 0 |
| refused rows missing a justification | 0 of 1,411 (English) |

The identification premise holds: region and domain are constant within issue,
`home` and `tier` vary within issue. The within-issue contrast is therefore
identified from within-issue variation across jurisdictions, exactly as claimed.

---

## PART 1 — Analysis-by-analysis audit

### 1.1 Primary home premium (`e01`, FIG1A)

| | |
|---|---|
| **Question** | On the same issues, do home-jurisdiction models refuse more than others? |
| **Estimand** | Jurisdiction-specific within-issue home premium, probability scale |
| **Unit** | One model response to one prompt |
| **Identifying comparison** | Difference-in-differences: home vs away, *issue held fixed* |
| **Sample** | English, non-General, EU excluded. n=20,796; 520 issues; 1,252 events |
| **Outcome** | `refused = engagement_code >= 4` |
| **Specification** | `refused ~ home * juris + tier + (1｜issue_id)`, binomial |
| **Dependence** | Issue random intercept; responses clustered within issue |
| **Uncertainty** | Parametric bootstrap, 2,000 draws from MVN(fixef, vcov) |
| **Scale** | Probability (reported in percentage points) |
| **Claim** | **Descriptive**, not causal |

**Verification of the probability contrast.** I re-derived it independently.
Findings:

- **Predictions condition on the fitted random effects.** `re` is the BLUP for
  each row's issue, added to both the home and away linear predictors. This is a
  **sample-conditional** contrast, not a population-marginal one. It is *not*
  the "typical issue" (u=0) quantity, and it is *not* marginal over a
  hypothetical population of issues. The current documentation says "sample
  average"; that is right, but the distinction has never been stated crisply.
  **Action: state it explicitly in the caption and the estimate table.**
- **Same observed sample for both predictions.** `X1` and `X0` are built on the
  identical data frame and then subset by jurisdiction. Correct.
- **Jurisdiction-specific interaction applied correctly.** Setting `home=1`
  leaves `juris` untouched, so the `home:juris_j` term activates properly.
  Verified by recomputation: CN +17.55, MENA +0.16, India +3.02, US −0.74 —
  matching `e01` to 4 decimals.
- **Tier is standardized over the observed distribution**, not fixed at a
  reference level: each row retains its own tier in both counterfactuals.
  Correct and worth stating.
- **⚠ The interval reflects fixed-effect uncertainty only.** The BLUPs are held
  at their fitted values across all 2,000 draws. The interval is therefore
  *conditional on the estimated issue effects*. This is defensible for a
  sample-conditional estimand but must not be described as a population
  interval. **Action: label the uncertainty method precisely in the table and
  caption.** I am not switching to a full parametric bootstrap over `theta`:
  it would change the estimand rather than merely widen the interval, and the
  estimand is settled.

**⚠ Finding: the primary model cannot see models within a jurisdiction.**
`home * juris` assigns every model in a jurisdiction the *same* fitted contrast.
I confirmed this: DeepSeek and Qwen both return exactly 17.5514. So the claim
"response weighting and equal-model weighting agree" is **vacuously true** — it
is a property of the specification, not evidence of robustness. The existing
leave-one-out sensitivities (`e05`) and the CN decomposition (`e07`) probe this
only indirectly.

**Action — new estimate.** Fit `refused ~ home * model + tier + (1｜issue_id)`
and aggregate to jurisdiction under equal-model weighting. Non-singular, issue
SD 1.23. Results:

| model | home premium (pp) | 95% CI | jurisdiction |
|---|---|---|---|
| qwen3-max | **+19.0** | [14.7, 23.9] | CN |
| deepseek-chat-v3.1 | **+16.2** | [12.4, 20.5] | CN |
| allam-7b | +1.8 | [−2.1, 6.0] | MENA |
| jais-8b | +0.1 | [−1.2, 1.6] | MENA |
| falcon3-10b | −0.1 | [−2.3, 2.5] | MENA |
| sarvam-30b | +3.1 | [0.3, 6.6] | India |
| gpt-4o | +1.1 | [−0.4, 3.3] | US |
| grok-4.3 | −0.1 | [−1.3, 1.7] | US |
| claude-opus-4.5 | −1.7 | [−3.4, 0.5] | US |
| gpt-5.1 | **−2.3** | [−3.9, −0.4] | US |

Equal-model-weighted jurisdiction aggregates: CN +17.6, MENA +0.6, India +3.1,
US −0.8 — materially identical to the response-weighted pooled estimates. The
weighting question is now **answered rather than assumed**.

This *strengthens* the paper: the China result holds independently in both
Chinese models, so it is not a one-model artefact. It also shows US
heterogeneity (GPT-5.1 significantly negative) that the pooled null conceals.

**Graph fidelity.** The horizontal interval plot represents this estimand
correctly. Retain. Add the per-model view as a standalone panel.

### 1.2 Descriptive within-jurisdiction contrast (`e03`, FIG1B)

Different estimand: does a jurisdiction refuse more on its own region than on
other regions, *without* reference to how others treat the same issues? Fitted
per jurisdiction as `glm(y ~ home + domain)`, then g-computation; bootstrap
resamples **issues** and **refits the model in each resample** (verified in
code). Domain standardization is identical across jurisdictions (each
jurisdiction's own observed domain mix). It is correctly labelled descriptive.

It is **not** a second estimate of the same parameter, and the figure must not
imply that. It cannot separate "this jurisdiction is sensitive about its own
region" from "this region is sensitive to everyone" — which is precisely why it
is not primary.

### 1.3 Region structure (`e08`, FIG1C / P4)

Two quantities, currently kept properly distinct:

- **Raw cell rates** — `mean(refused)` per jurisdiction × region, Wilson
  intervals computed (not drawn).
- **Excess** — observed minus fitted, where the baseline is
  `glm(cbind(events, n-events) ~ juris + region, binomial)` on cell counts.

**Clarification required.** This is a *fitted additive-in-logit baseline*,
properly weighted by cell size — not arithmetic row/column means, and not a
model residual from the primary mixed model. The current axis label ("Excess
refusal (pp) over jurisdiction + region") is acceptable but imprecise.
**Action:** label it "observed − fitted additive (jurisdiction + region) logit
baseline". EU is excluded from the baseline fit and correctly receives no
fitted value.

### 1.4 Model × tier (`e11`, FIG2A) and domain × tier (`e12`, FIG2B)

Per-model `refused ~ tier + (1｜issue_id)`; pooled
`refused ~ tier * domain + (1｜issue_id) + (1｜model)`. Both are within-issue
paired contrasts, correct given the design (regular and boundary derive from the
same issue).

**On `(1｜model)` vs fixed model effects.** The brief asks whether 11
purposively chosen models justify a random effect. They do not constitute a
random sample. However, for the *domain* contrasts the model term is a nuisance
control, and with 11 groups the random intercept is a reasonable shrinkage
device that does not distort the domain × tier interaction. I checked the
practical question that matters: does treating model as fixed change the domain
conclusions? **Action: fit `refused ~ tier * domain + model + (1｜issue_id)` as
a sensitivity and export both.** Adopt the fixed-model version as primary only
if the domain shifts move materially; otherwise report the sensitivity and keep
the current specification, noting the choice.

**⚠ Finding: FIG2 omits the uncertainty on the estimand it is about.** The
panel plots regular and boundary *levels* and prints the signed shift as bare
text. The shift is the estimand and its interval exists in `e11`/`e12` but is
never shown. Consequences: grok-4.3 (+0.5 [−0.3, +1.6]) and qwen3-max
(+0.4 [−1.0, +2.0]) are indistinguishable from zero yet are drawn exactly like
sarvam-30b (+6.8 [2.4, 11.3]). The figure currently implies eleven real,
differently-signed effects when roughly half are null.

**Action — redesign.** Per the brief's own decision rule: the claim is about
*direction and heterogeneity*, so the shift interval is primary. Use the
hybrid — compact dumbbell for absolute levels on the left, shift with 95%
interval and a zero line on the right, narrower. This keeps the level
information (allam-7b refuses at ~15% regardless of framing, which matters) and
adds the missing inference.

**⚠ Bug: text collision.** In FIG2A the "not estimable" key and the
"shift (pp)" header overprint at the top right. Visible in the rendered PNG and
not caught by any audit check.

**⚠ Ordering bug.** Mistral (not estimable) renders at the **top**, not last:
`ord11` appends it to the factor levels, but a discrete y-axis draws level 1 at
the bottom. Fix by reversing intent explicitly.

### 1.5 Refusal reasons (`e13`, FIG3)

Conditional on refusal; denominator is that model's refusal count. Threshold
≥30 refusals excludes only Mistral (0). Composition sums to 1 (verified).
Segment labels verified programmatically to sit in their own segment with the
printed value equal to the segment width — **correct**, contrary to my initial
visual impression.

**⚠ Finding: the 7→4 collapse is not defensible as it stands.** Raw English
composition: A 62.2%, C 15.1%, **G 15.7%**, F 4.7%, D 2.0%, B 0.1%, E 0.1%.

1. **G ("other") is 15.7% of all refusals and is being folded into
   "unstated".** Reading the free text for all 222 G cases shows it is
   heterogeneous and contains at least three distinct things: degenerate output
   ("the response is a nonsensical and rambling collection…"), explicit task
   refusals ("the model explicitly refuses to write a persuasive argument"), and
   **epistemic** statements ("the model states it lacks reliable information").
   Merging that with F ("no reason given") produces a category that means two
   incompatible things and silently absorbs a measurement failure mode.
   This is worst for **allam-7b**, the highest-refusal model, where G is
   **31.7%** of 426 refusals — i.e. a third of its "refusals" may be degenerate
   output rather than refusal behaviour.
2. **"Epistemic" is nearly empty.** B = 2 and E = 2 responses in the entire
   English refusal set; the category is essentially D alone. Claude's headline
   18% epistemic rests on ~18 responses out of 100 refusals.

**Action.** Move to five categories: `neutrality` (A), `harm` (C),
`epistemic` (B+D+E), `none given` (F), `other / unclassified` (G) — and label G
honestly. Export the raw 7-code table alongside. State the degenerate-output
caveat in the caption and flag allam-7b explicitly.

**⚠ Finding: legend order ≠ stack order.** The legend reads
neutrality → harm → epistemic → unstated; the bars stack
unstated → epistemic → harm → neutrality left-to-right. The brief forbids this
and no audit check catches it. **Action: make them identical and add a check.**

**Plot form.** The 100% stacked horizontal bar is right: the categories are a
complete, mutually exclusive composition (the judge emits one code). Retain.
Reject Marimekko (overweights denominators, harms model comparison) and dot
panels (loses part-to-whole).

### 1.6 China × language (`e09`/`e10`, P5)

Per-model `refused ~ home * lang + tier + (1｜issue_id)`; probability-scale home
premium within each language; the interaction is tested on the log-odds scale
with a p-value carried in the table. Estimates average over the observed tier
mix. This is correctly specified.

The defensible claim is: **similar probability-scale home premiums in both
languages, with a sharply higher Chinese baseline for DeepSeek (2.6% → 14.5%)
and not for Qwen.** The word "additive" must not appear — the interaction is
significant on the log-odds scale for DeepSeek while the probability-scale
premium is slightly larger in Chinese, which is a scale effect of the higher
baseline, not a contradiction.

**⚠ Bug: colliding axis ticks at the panel boundary.** The rendered PNG shows
"400" where DeepSeek's `40` meets Qwen's `0`. **Action: drop the terminal tick
or add panel spacing, and add an audit check for duplicated boundary ticks.**

Retain the dumbbell. Reject the 2×2 interaction plot: it emphasises slopes and
would invite exactly the additivity overreading the analysis warns against.

### 1.7 Slant: ideology (`e15`/`e16`, FIG4A)

25% issue subsample, engaged responses only, English primary. Recomputed:

| dimension | n | neutral | negative | positive | mean | median |
|---|---|---|---|---|---|---|
| Economic | 6,517 | 92.4% | 3.0% | 4.6% | +0.016 | 0 |
| Social | 6,517 | 79.5% | 12.3% | 8.3% | −0.053 | 0 |
| Authority | 6,517 | 80.4% | 13.1% | 6.5% | −0.072 | 0 |
| Populism | 6,517 | 79.5% | 15.5% | 5.1% | −0.104 | 0 |

**⚠ Finding: the current diverging-bar form is the wrong default.** It removes
the neutral category from the bars and prints it as a marginal number. The bar
length then represents *only the non-neutral remainder*, on a ±13% axis. A
reader who does not carefully parse the "% at 0" column will substantially
overread the ideological content. The brief identifies this risk and I agree
with it.

**Action.** Make the main panel **mean score with issue-clustered interval, on a
symmetric axis centred at zero, with a compact neutral-share column adjacent to
the denominator it belongs to** — four small multiples, jurisdictions as rows,
pole labels at the axis ends. This shows the three facts that matter
simultaneously: means are near zero, neutrality dominates, and the intervals are
tight enough to distinguish a few jurisdictions.

The mean *is* substantively meaningful despite 74–93% zeros: it is the average
directional position, and with n≈6,500 and issue-clustered intervals it is
estimated precisely. But it must never be shown without the neutral share.

Move the full five-category distribution to `P9_ideology_distribution.png` as a
supplementary panel — statistically honest, and appropriate where the
distribution itself is the claim.

**Action — decomposition.** Export jurisdiction mean, between-model variation
within jurisdiction, and model-specific means, so jurisdiction aggregation
cannot hide model heterogeneity.

### 1.8 Slant: moral foundations (`e17`, FIG4B)

Binary, **not mutually exclusive** — verified: mean 1.83 foundations per
engaged response; 13.9% invoke none; 0.05% invoke all six. A stacked bar would
therefore be invalid; the current dot-and-interval form is correct.

**Identification limit.** Jurisdiction is *defined by* model membership, so
model fixed effects would absorb jurisdiction entirely. A jurisdiction-level
mixed model `foundation ~ jurisdiction + (1｜issue_id) + (1｜model)` is
estimable but the jurisdiction contrast is identified only across a handful of
models (1–4 per jurisdiction). **The honest quantity is a descriptive
jurisdiction average, labelled as such**, plus the model-level estimates so the
reader can see the within-jurisdiction spread. I will not present a
model-adjusted jurisdiction contrast as if it were identified.

**Action.** Add a **pooled grey estimate per foundation** to establish the
common ranking — the dominant pattern is between-foundation (58–71% fairness vs
<4% sanctity), and the jurisdiction differences are comparatively modest. Add
equal-model-weighted jurisdiction estimates as a sensitivity.

**Coverage note.** Of 29,934 slant-eligible rows, 28,311 are engaged and 27,357
carry codes: **954 engaged eligible rows (3.4%) lack slant codes**. This is
*incidental* missingness — responses generated after the annotation pass ran —
not structural. It must be stated, and it will shrink as the top-up completes.

### 1.9 Moral foundations by language (`e20`, P11)

Restricted to en/zh/ar where all 11 models answer, so a difference cannot be a
roster-composition artefact. Result is a null. Correctly supplementary.

---

## PART 2 — Weighting

US 4 models, MENA 3, CN 2, EU 1, India 1. Every jurisdiction summary is
implicitly **response-weighted**. Because each model answers the same 2,496
English prompts, response weighting equals equal-model weighting *by design* —
but only for quantities that vary by model. For the primary home premium the
equivalence was vacuous (§1.1); with the new per-model specification it is a
genuine, verified result.

**Action:** export all three weightings (response, equal-model,
leave-one-model-out) for the home premium, moral foundations and ideology, and
state the weighting in every caption. Flag India and EU as single-model
jurisdictions wherever they appear.

---

## PART 3 — Rare outcomes and structural zeros

Overall refusal ≈5.4%. EU/Mistral: **0 refusals in 2,496 English responses** —
complete separation, not sparsity. Handling is currently correct (excluded from
estimation, carried as a flagged row, hollow square, no interval, no number) and
will be preserved. The raw matrix prints "0.0" in five EU cells, which risks
reading as five estimated zeros; **action: render the EU column as structurally
empty rather than as five zero-valued cells.**

---

## PART 4 — Final figure system

Emphasis follows evidence: FIG1 strongest → FIG4 exploratory. FIG4 gets a
visibly lighter treatment (no bold lead mark, explicit subsample banner in the
caption).

**FIG1 — `FIG1_home_region_main.png`** (map removed to P1)
- **A** primary within-issue home premium, CN modestly emphasised, EU as
  structural zero. Order CN, MENA, India, US, EU. India *not* visually promoted.
- **B** paired-estimand dumbbell: hollow = descriptive, filled = primary,
  connector in jurisdiction colour, primary interval only, transition labels
  placed **next to the connector**, not in a detached gutter.
- **C** raw rate matrix, full width, sequential scale, printed value = fill,
  home cells marked with a small corner dot, single red outline on China × CN,
  EU column shown as structurally empty.
- Takeaway: *distinctive home-region sensitivity is overwhelmingly a China
  result.*

**FIG2 — `FIG2_model_domain_main.png`**
- **A** model: compact dumbbell (levels) + shift with 95% interval, zero line.
- **B** domain: same structure.
- Ordered by signed shift; Mistral last, marked not estimable.
- Takeaway: *boundary framing moves refusal in opposite directions.*

**FIG3 — `FIG3_refusal_reasons_main.png`**
- One full-width 100% composition, **five** categories, legend order identical
  to stack order, neutrality at the right edge, percentages only, labelled at
  ≥15%, denominators in the row label.
- Takeaway: *neutrality dominates; Jais is harm-dominant; Claude is unusually
  epistemic — with the "other" category flagged.*

**FIG4 — `FIG4_slant_main.png`**
- **A** ideology mean + interval + neutral-share column, four small multiples.
- **B** moral-foundation prevalence with a pooled grey reference.
- Takeaway: *ideological coding is overwhelmingly neutral; moral content shows a
  stable hierarchy with modest jurisdictional differences.*

### Canonical outputs

Main: `FIG1_home_region_main.png`, `FIG2_model_domain_main.png`,
`FIG3_refusal_reasons_main.png`, `FIG4_slant_main.png`.

Standalone: `P1_locator`, `P2_home_interaction`, `P3_estimand_comparison`,
`P4_region_structure_raw`, `P4_region_structure_excess`, `P5_china_language`,
`P6_model_tier`, `P7_domain_tier`, `P8_refusal_reasons`,
`P9_ideology_mean_neutral`, `P9_ideology_distribution`, `P10_moral_foundations`,
`P11_moral_by_language`, plus new `P12_home_by_model`.

All PNG, 7.20 in wide, 600 dpi, white background, rendered directly.
`P4_region_structure.png` is **deleted** (renamed to `_excess`).

### Alternatives considered and rejected

| alternative | verdict |
|---|---|
| Broken-axis dumbbell in FIG1B | rejected — distorts; single axis is legible |
| Cleveland dot matrix for FIG1C | rejected — heatmap reads faster; cells are the point |
| 2×2 interaction plot for P5 | rejected — invites additivity overreading |
| Marimekko for FIG3 | rejected — overweights denominators |
| Stacked bars for moral foundations | rejected — not mutually exclusive |
| Full parametric bootstrap over `theta` for e01 | rejected — changes the estimand |
| Model fixed effects for moral foundations | rejected — absorbs jurisdiction |
| Ridgelines/violins for 5 discrete ideology codes | rejected |

---

## PART 5 — New diagnostic exports (`23_diagnostics.R`)

`d01` engagement-code frequency · `d02` justification codes raw and collapsed ·
`d03` ideology distribution by dimension × jurisdiction · `d04` neutral-share
prevalence · `d05` moral-foundation co-occurrence · `d06` missingness and
coverage · `d07` events and denominators for every plotted cell ·
`d08` weighting sensitivity.

## PART 6 — Audit additions

Fail on: non-PNG; `_1col`/`_2col`; wrong width or dpi; missing/stale outputs;
figure-vs-estimate disagreement; EU plotted as an ordinary zero; raw values over
a residual scale; **legend order ≠ stack order**; shape-meaning collisions;
reason colours reusing jurisdiction colours; clipped labels; **duplicated tick
labels at panel boundaries**; **ideology neutral share missing or detached**.
