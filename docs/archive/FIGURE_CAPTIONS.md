# Figure captions

Publication-ready captions for `pipeline/figures/`. Figures carry no titles,
subtitles or interpretive prose; everything needed to read them is here. All
output is **PNG at 600 dpi, two-column width (7.20 in), white background,
rendered directly at final size**. There are no one-column variants, no `_2col`
duplicates and no resized derivatives.

**Conventions.** Unit of observation is one model response to one prompt.
Refusal is `engagement_code >= 4` on the judge's 1–5 engagement scale.

| visual variable | meaning |
|---|---|
| colour | **model jurisdiction only** (CN deep red, India slate, MENA ochre, US grey-blue, EU pale slate); issue regions inherit their jurisdiction's colour |
| circle / triangle | prompt tier: regular / boundary |
| filled / hollow circle | estimand: primary / descriptive; in P5, home region / elsewhere |
| hollow square | contrast not estimable (0 observed refusals) |
| five-hue palette | refusal reason (disjoint from jurisdiction colours) |
| circle / hollow circle / diamond | prompt language en / zh / ar (P11 only, where tier is not encoded) |
| thin light interval | uncertainty |

**Sample.** The battery is **complete**: 11 models × 5 languages × 2,496
prompts = 137,186 annotated responses over 624 issues. Primary estimates
(Figures 1–4) are **English-only for comparability**; Figure 5 uses all five
languages. Analyses are **descriptive, not causal**.

**Weighting.** Jurisdictions contain different numbers of models (US 4, MENA 3,
CN 2, India 1, EU 1). Every jurisdiction summary is response-weighted; because
each model answers the same 2,496 English prompts this coincides with equal-model
weighting, and `pipeline/estimates/e22_weighting_sensitivity.csv` reports both
plus leave-one-model-out.

---

## Figure 1 — Distinctive home-region sensitivity is a China result

`FIG1_home_region_main.png`

**Chinese-developed models refuse China-focused issues far more than other
jurisdictions refuse the same issues; no other jurisdiction shows a comparable
effect, and the simpler within-jurisdiction contrast overstates MENA.**

**(A) Regional key.** Locator identifying the five issue regions in the colours
used throughout. It carries no estimates and is deliberately the shortest panel.
**MENA** is operationalised as the 22 Arab League member states (the underlying
region variable is named `Arab`, which is how it appears on the panel C axis);
"Europe" as countries with continent = *Europe* excluding Russia; China, India
and the US as those single countries. A sixth issue stratum, **General** (17% of
issues; no regional focus), has no location and is not shown. Shading marks
**issue-region classification**, not the location of model developers.

**(B) Why the estimand matters — model-based.** One row per jurisdiction with
both contrasts: the **primary** within-issue home premium (filled circle, with
its 95% interval) and the **descriptive** within-jurisdiction home-versus-away
difference (hollow circle). The connector carries an arrowhead pointing at the
primary estimate; values are labelled `○ descriptive` and `● primary`.

The primary estimand comes from `refused ~ home × jurisdiction + tier +
(1 | issue)`, binomial, on English non-General responses (*n* = 20,796;
520 issues; 1,252 refusals). Because issue region and topic domain are constant
within issue, the issue random intercept absorbs both and the contrast compares
jurisdictions **answering the same issues** — a difference-in-differences. Points
are g-computation averages **over the observed sample, at the fitted issue random
effects**; the estimand is therefore **sample-conditional**, not marginal over a
population of issues. Bars are 95% intervals from a parametric bootstrap (2,000
draws) over the **fixed-effect** covariance with the random effects held fixed —
consistent with a sample-conditional estimand, and not a population interval.

The descriptive contrast is a per-jurisdiction `glm(refused ~ home + domain)`
with issue-resampled bootstrap intervals (the model is refitted in each
resample). It is **not** a second estimate of the same parameter, and it cannot
distinguish "this jurisdiction is sensitive about its own region" from "this
region is sensitive to everyone".

MENA moves from +2.9 to +0.2 pp and India from −1.4 to +3.0; CN is stable
(+18.8 → +17.5). **India's +3.0 rests on a single model (Sarvam) and reverses
sign between estimands; it should not be read as a finding.** Mistral Large 2512
records **0 refusals in 2,496 English responses**, so the EU contrast is not
estimable; it is shown as a hollow square with the reason stated, never as an
estimate of zero.

**(C) Raw regional structure — descriptive.** Observed refusal rate (%) for each
model-jurisdiction × issue-region cell. Fill encodes the same quantity that is
printed, on one sequential scale. A small dot in the jurisdiction's colour marks
home cells; a single red outline marks CN × China. The EU column is rendered as
structurally empty because Mistral never refuses. **General** issues are excluded
here, for consistency with the estimand in panel B. The Arab row is elevated
across every jurisdiction — India's models refuse Arab issues at 12.5% against
MENA's 13.6%, from a much lower baseline — which is why MENA's home effect does
not survive the within-issue comparison. Cell denominators and event counts are
in `pipeline/estimates/d07_cell_denominators.csv`.

---

## Figure 2 — Prompt framing moves refusal in opposite directions

`FIG2_model_domain_main.png`

**Boundary framing has no universal effect: it lowers refusal for some models
and domains and raises it for others — and for several the shift is
indistinguishable from zero.**

Each row pairs the **levels** (left) with the **shift and its 95% interval**
(right). The shift is the estimand; the levels are shown because absolute refusal
rate is substantive (allam-7b refuses at ~15% under either framing). Both panels
of a row use an identical, explicitly stated category order.

**(A) By model.** Per-model mixed models `refused ~ tier + (1 | issue)`, so each
contrast is a **within-issue paired** comparison: regular and boundary prompts
derive from the same issue by design, and independent-binomial intervals would be
wrong both for the pairing and for the recurrence of issues across models. Rows
are ordered by signed shift, largest increase at the top; Mistral Large 2512 is
last and marked not estimable (0 refusals). Note that grok-4.3
(+0.5 [−0.3, +1.6]), qwen3-max (+0.4 [−1.0, +2.0]) and allam-7b
(−0.9 [−3.7, +1.8]) all include zero. Values in `e11_model_tier.csv`.

**(B) By topic domain.** Pooled across models from `refused ~ tier × domain +
(1 | issue) + (1 | model)`. The model random intercept prevents a few
high-refusal models from driving apparent domain differences. Treating model as a
**fixed** effect instead moves every domain shift by at most **0.15 pp**
(`e12b_domain_tier_model_fixed.csv`), so the choice is immaterial.
Security-and-conflict and governance-and-democracy **fall** under boundary
framing, while religion, social-and-moral and civil-rights **rise**. Values in
`e12_domain_tier.csv`.

---

## Figure 3 — Models differ in the reasons they state for refusing

`FIG3_refusal_reasons_main.png`

**Neutrality dominates most stated rationales; Jais is a harm-avoidance outlier;
Claude has an unusually large epistemic component.**

Composition of refusal justifications by model, as a share of that model's own
refusals — **conditional on having refused**, so this describes rationale, not
propensity. A high share of one reason says nothing about how often that model
refuses. Denominators are printed in the row label (`model · n=…`); models with
fewer than 30 refusals are omitted (only Mistral, which has none). Denominators
range from 51 to 426, so shares for the smaller models are imprecise. Ordered by
neutrality share, highest at the top, Jais last. Legend order is identical to the
drawn stack order; segments carry their percentage only where they exceed 15%.

**The judge's seven codes are collapsed to five, not four.** `neutrality` (A),
`harm` (C), `epistemic` (B + D + E), `none given` (F), `other` (G). Two cautions
follow from the raw distribution (`d02_justification_codes.csv`):

- **`other` (code G) is 15.7% of English refusals and is internally
  heterogeneous.** Its free text mixes degenerate output ("the response is a
  nonsensical and rambling collection…"), explicit task refusals, and epistemic
  statements. It is **not** the same as "no reason given", and an earlier version
  of this figure merged the two. It matters most for **allam-7b**, where `other`
  is 31.7% of 426 refusals — so a substantial share of that model's "refusals"
  may be degenerate output rather than refusal behaviour.
- **`epistemic` is thin.** Codes B and E fire on **two responses each** in the
  entire English refusal set; the category is effectively D (expertise
  limitation) alone, and Claude's 18% rests on ~18 responses.

Uncertainty is not drawn on the segments (it would destroy readability); Wilson
intervals for every share are in `e13_refusal_reasons.csv`, and the raw seven-code
composition per model is in `e13b_refusal_codes_raw.csv`.

---

## Figure 4 — Engaged answers are ideologically neutral; moral content is ordered

`FIG4_slant_main.png`

**On every ideology dimension the judge codes the large majority of engaged
responses as exactly neutral; the moral vocabulary models reach for shows a
stable hierarchy with comparatively modest jurisdictional differences.**

This figure is deliberately the least emphasised of the four. It rests on
annotation **Passes 2 and 3**, run on a **25% subsample of issues** (156 issues,
seed 20260803) rather than the full battery — see `docs/SLANT_SUBSAMPLE.md`.
Sampling is at the **issue** level, so within a sampled issue every model × tier
cell is complete and issue-level clustering is preserved. Both panels are
**conditional on engagement**: passes 2/3 are skipped for refusals by design, so
these describe how models lean *when they answer*, never how often they answer,
and they are **not comparable across jurisdictions with different refusal rates**.
Estimates are **English-only** because the model roster is not constant across
languages (11 models in en/zh/ar, 9 in ru, 7 in hi) and pooling would confound
slant with roster composition. Intervals are **issue-clustered bootstrap** (800
resamples, percentile method). Of 28,311 slant-eligible engaged responses, 27,357
carry codes; the 954 without (3.4%) are **incidental** — generated after the
annotation pass ran — not structural.

**(A) Ideology — descriptive.** Mean of the judge's −2..+2 code on each of four
dimensions, by developer jurisdiction, with the **neutral share printed in the
adjacent `% at 0` column**. The two must be read together: 74–93% of engaged
responses are coded exactly 0, so the means are small by construction. Both poles
are named under every facet because the direction of each dimension is not
recoverable from its name: −2 is left / progressive / authoritarian / populist,
+2 is right / traditional / libertarian / elitist, following the judge codebook
in `scripts/annotation_pipeline.py` (Pass 2). Note the axis is ±0.225, not ±2.
The largest signals are US economic +0.032 [0.016, 0.048] and EU social
−0.119 [−0.163, −0.074] — statistically distinguishable from zero, substantively
tiny. Between-model variation within a jurisdiction reaches 0.070
(`e16c_ideology_by_model.csv`), comparable to the jurisdiction differences
themselves. Full five-category distributions: `P9_ideology_distribution.png`.

**(B) Moral foundations — descriptive.** Share of engaged responses invoking each
of Haidt's six foundations, by jurisdiction, with a **grey rule marking the
pooled estimate** — because the dominant pattern is *between foundations*
(fairness 61% vs sanctity 3%), not between jurisdictions. The foundations are
**not mutually exclusive**: engaged responses invoke 1.83 on average and 13.9%
invoke none (`d05_moral_cooccurrence.csv`), so shares within a jurisdiction do not
sum to 1 and no stacked or composition form is valid. Jurisdiction is **defined
by** model membership, so a model-adjusted jurisdiction contrast is not
identified; these are descriptive averages. Equal-model weighting reproduces them
to within 0.001 (`e17c_moral_equal_model.csv`).

---

## Figure 5 — Prompt language moves refusal far more than model origin does

`FIG5_language_main.png`

**Refusal is highly sensitive to the language a prompt is asked in, and the
largest effects in the study are language effects, not jurisdiction effects.**

Estimated for **every model in every language**, nulls included. An earlier
version of this analysis covered only the two Chinese models, which left the
biggest effects in the dataset unreported.

**(A) Language effect per model.** Difference in refusal probability between
prompts in language L and English prompts **on the same issue**, from per-model
`refused ~ language + tier + (1 | issue)`, probability-scale g-computation with
parametric-bootstrap intervals. Prompts are translations of one issue, so the
issue is the natural blocking factor and the contrast is within-issue.

The pattern is coherent and large: the three MENA models over-refuse
dramatically in languages outside their training focus, while handling Arabic
normally. **allam-7b refuses 78.4% of Hindi prompts (+62.6 pp over English)** and
68.8% of Russian (+52.8 pp); falcon3-10b +25.4 pp in Hindi and +24.1 pp in
Arabic; jais-8b +16.8 pp in Hindi. DeepSeek's much-discussed Chinese effect
(+11.2 pp) is only the **seventh** largest. Cells never generated are marked
*not generated* and left blank rather than drawn as zero; mistral-large-2512 is
shown as a row marked *0 refusals* rather than omitted. Values in
`e29_language_by_model.csv`.

**(B) Home-region premium by prompt language.** The generalisation of `P5`,
which covered CN only. `refused ~ home × language + tier + (1 | issue)` fitted
**per jurisdiction**.

⚠ **This is a within-*jurisdiction* contrast, not the primary
difference-in-differences of Figure 1.** Within one jurisdiction `home` is a
property of the issue's region and therefore constant within issue, so it is
identified from *between*-issue variation and the issue random intercept shrinks
it. It must not be read as the primary estimand. China's premium persists in
every language (+9.6 to +20.3 pp); MENA is small and positive except in Russian;
India and US are near zero; EU is a structural zero. Values in
`e31_home_premium_by_language.csv`.

**The home-language story is not uniform.** `e30_home_language.csv` isolates each
model's own-sphere language (CN→zh, MENA→ar, India→hi; US/EU are English-native
so no contrast exists): falcon3 **+24.1**, deepseek **+11.2**, jais +1.1, allam
−0.4, qwen −0.7, **sarvam −4.8** — Sarvam refuses *less* in Hindi. There is no
consistent "home language → more refusal" effect.

**Caveat that travels with this figure.** The judge panel found MENA labels the
least reliable in the study (positive specific agreement 0.05–0.09), and the
largest effects here are all MENA models. The effects are far too large to be
noise, but their magnitudes should be read with that attached. Some of these
refusals may also be **degenerate output** rather than refusal behaviour — judge
code G ("other") is 31.7% of allam's refusals and its free text includes
"nonsensical and rambling".

---

# v2 figure set — alongside, not replacing

`FIGA`/`FIGB`/`FIGC` present the three v2 estimand families
(`docs/ESTIMANDS.md`). They **sit alongside FIG1–FIG5** while the canonical
set is undecided; the earlier figures remain reproducible from the earlier
tables. Where the two disagree, the v2 tables are the later analysis.

⚠ **Known disagreements with FIG1/FIG5**, which a reader comparing them will
notice:

| FIG1/FIG5 shows | v2 says |
|---|---|
| CN home premium **+17.5**, labelled "within-issue" | `e33` **+16.47**; "within-issue" is a prohibited description |
| India **+3.0**, US **−0.7** | `e33` India **−3.07**, US **+1.87** — both flip sign |
| FIG5B "within-jurisdiction premium by language" | superseded by `e35`'s language sensitivity |

## Figure A — Descriptive home results

`FIGA_home_descriptive.png` · from `e32` · **no model of any kind**

**Models refuse more on issues about their own region — but the size of that gap
differs enormously by jurisdiction, and for three of five it is indistinguishable
from zero.**

**(A) Observed refusal rates, three region positions.** `home` (own region),
`away` (a different named region) and **`General`** (no regional focus, 17% of
the battery). General is its own position and is **never part of the away
reference** — folding it in would score every model "away" on a sixth of the
battery. All five languages pooled, 137,186 responses. Home rates printed.

**(B) Descriptive difference, home − away**, under response weighting and
equal-model weighting. The two coincide to three decimals because the design is
balanced (every model answers the same battery), which is worth knowing rather
than assuming. Issue-cluster bootstrap intervals. EU is drawn as a hollow square
reading "0 refusals observed" — Mistral Large records none anywhere, so there is
no rate to plot and no interval to draw.

CN +11.71 [8.82, 14.90] · MENA +4.78 [2.96, 6.67] · India +0.12 [−0.85, 1.16] ·
US −0.97 [−2.08, 0.18].

**Supports:** a description of these models on this battery. **Does not
support:** any claim that region *caused* the difference — home and away issues
differ systematically in topic (45% of China issues are territorial sovereignty).

## Figure B — Covariate-standardized home contrasts

`FIGB_home_standardized.png` · from `e33`/`e34`/`e35`

**Only China's home-region contrast survives adjustment and every sensitivity;
MENA's is a composite of heterogeneous models; India and the US are consistent
with zero.**

**This is a covariate-standardized contrast. It is NOT causal, NOT a
difference-in-differences, and NOT a within-issue effect** — `home` is a fixed
property of an issue's region and nothing randomises it. The axis says
"covariate-standardized" for that reason, and `audit_figures.R` fails the build
if the prohibited descriptions appear in the figure source.

**(A) Primary contrast per jurisdiction.** `refused ~ home + tier + domain +
route + model`, fitted separately by jurisdiction, English only (the
specification carries no language term, so pooling languages would be
misspecified). No region fixed effects: within a jurisdiction region
*determines* home. Probability-scale g-computation, standardized to **equal
weight per tested model and issue** (primary) and to empirical response
composition (sensitivity). Intervals are issue-cluster bootstrap with the
**complete model refit and re-standardized inside every one of 2,000
replicates**. EU is marked not estimable — zero refusals is complete separation,
not a small effect.

CN **+16.47** [9.32, 24.89] · MENA **+3.76** [1.44, 6.34] · India −3.07
[−5.81, 0.19] · US +1.87 [−0.74, 4.60].

**(B) Sensitivity ladder**, faceted by jurisdiction: per model, leave-one-model-
out, prompt type, language, minimum response length, and the hierarchical
specification. CN holds throughout (14.5–27.3 across every cut, both Chinese
models at 14.7 and 17.6). **MENA's per-model spread (0.7 to 8.7) is wider than
its pooled interval**, so MENA is a composite of heterogeneous models rather than
a jurisdiction-level regularity.

The **hierarchical row is drawn as a triangle** because it has no bootstrap
interval. It uses `+ (1|issue_id) + (1|prompt_id)` with **population-level
(marginal) predictions** — integrating over the random-effect distribution rather
than plugging in fitted BLUPs, which would answer a different question. CN falls
from 16.47 to **7.16 pp**: expected, since marginalising a non-linear link over a
large random-effect variance attenuates a probability-scale contrast. The two are
different estimands, both reported. **US did not converge** (degenerate Hessian)
and is omitted rather than imputed.

## Figure C — Prompt-fixed language effects

`FIGC_language_paired.png` · from `e36`/`e37`

**Language moves refusal far more than jurisdiction does, and almost all of that
movement comes from three models.**

Paired within `block_id = model × prompt_id`: the same model, the same prompt,
delivered in a different language. Computed directly from observed outcomes; an
LPM with block fixed effects is algebraically the same number and is verified as
a check.

**(A) Pooled paired difference per language**, with complete/missing block counts
printed on the panel (missing blocks are 16–54 of ~27,440, i.e. <0.2%).
Chinese +1.32 · Arabic +2.33 · Russian +3.95 · Hindi **+8.52**.

**(B) By model**, coloured by developer jurisdiction. The pooled figures conceal
the actual pattern: allam-7b **+61.4 pp** in Hindi and **+51.7** in Russian;
falcon3-10b +25.3 Hindi and +24.1 Arabic; jais-8b +17.3 Hindi — while the four US
models sit near zero in every language. The three MENA models over-refuse
dramatically outside their training focus.

**Supports:** the effect of delivering the tested translated prompt version,
among the tested prompt/model set, **conditional on translation equivalence and
on no run-order or provider confounding**. If a translation is harder or
differently loaded, that is inside the estimate. **Does not support:** a causal
effect of a user's language, or generalisation beyond these prompts and models.

**Caveat carried from the judge panel:** MENA labels are the least reliable in
the study (positive specific agreement 0.05–0.09), and the largest effects here
are all MENA models. The effects are far too large to be noise, but their
magnitudes should be read with that attached.

---

## Standalone panels

All two-column, 600 dpi, rendered directly.

- **`P1_locator.png`** — the Figure 1A locator with a wider crop.
- **`P2_home_interaction.png`** — the primary within-issue home premium on its
  own, with 95% intervals and the EU structural zero. This is the single
  strongest quantity in the study.
- **`P3_estimand_comparison.png`** — Figure 1B standalone.
- **`P4_region_structure_raw.png`** — Figure 1C at full width, with the colourbar.
- **`P4_region_structure_excess.png`** — the same cells showing **excess refusal
  (pp) over a fitted additive jurisdiction + region baseline**, on a diverging
  scale centred at zero. The baseline is `glm(cbind(events, n−events) ~
  jurisdiction + region, binomial)` on cell counts — a **fitted additive-in-logit
  model**, weighted by cell size; it is *not* arithmetic row/column means and
  *not* a residual from the primary mixed model. CN × China is strongly positive;
  MENA × Arab is near zero.
- **`P5_china_language.png`** — refusal rate for the two Chinese-developed models
  on **home-region (China) issues** versus **elsewhere**, separately for English
  and Chinese prompts. Hollow = elsewhere, filled = home; the connector is the
  home premium and is labelled. Wilson intervals on each rate. Premiums from
  `refused ~ home × language + tier + (1 | issue)` per model, averaged over the
  observed tier mix, with parametric-bootstrap intervals in
  `e10_cn_home_by_language.csv`. Shape distinguishes home from elsewhere, not
  language — language is the y-axis — so it cannot collide with the tier encoding
  in Figure 2. The premium is of similar magnitude in both languages for both
  models, while the **baseline** rises sharply in Chinese for DeepSeek
  (2.6% → 14.5%) and not for Qwen (4.6% → 3.6%). The home × language interaction
  is not significant for Qwen (*p* = 0.48); for DeepSeek it is significant on the
  log-odds scale (*p* = 2.6e-05) while its probability-scale premium is slightly
  *larger* in Chinese — a scale effect of the higher baseline, not a
  contradiction. These results are **consistent with similar home gaps across
  languages**; they do **not** establish additivity.
- **`P6_model_tier.png`** / **`P7_domain_tier.png`** — Figure 2 levels panels.
- **`P8_refusal_reasons.png`** — Figure 3 standalone.
- **`P9_ideology_mean_neutral.png`** — Figure 4A standalone.
- **`P9_ideology_distribution.png`** — the **full five-category** ideology
  distribution including the neutral category, by jurisdiction and dimension.
  Statistically the most complete view; supplementary because the neutral category
  dominates and compresses the directional tails.
- **`P10_moral_foundations.png`** — Figure 4B standalone.
- **`P11_moral_by_language.png`** — moral-foundation prevalence by **prompt
  language**, restricted to English, Chinese and Arabic — the three languages in
  which **all eleven models** answer. That restriction is the point: a difference
  across these three cannot be a roster-composition artefact. The result is a
  **null**: intervals overlap for every foundation. Values in
  `e20_moral_by_language.csv`.
- **`P13_language_by_model.png`** / **`P14_home_premium_by_language.png`** —
  Figure 5A and 5B standalone.
- **`P12_home_by_model.png`** — the within-issue home premium **per subject
  model**, from `refused ~ home × model + tier + (1 | issue)`. This is the panel
  that shows the China result is carried by **both** Chinese models
  (Qwen +19.0 [14.7, 23.9]; DeepSeek +16.2 [12.4, 20.5]), that MENA is null for
  all three of its models, and that the US null conceals real heterogeneity
  (GPT-5.1 −2.3 [−3.9, −0.4]). The pooled `home × jurisdiction` specification
  cannot show any of this: it assigns every model in a jurisdiction the identical
  fitted contrast.

---

## Measurement limitations

All codes come from a **single LLM judge** (`google/gemini-2.5-flash-lite`,
temperature 0). **No second-judge pass exists and no inter-rater reliability has
been estimated**; this is the study's principal measurement limitation and every
quantity inherits it.

It bites hardest where the judgement is hardest:

- **Ideological direction.** A near-total concentration at 0 is consistent with
  genuinely neutral answers *and* with a judge reluctant to assign a side. This
  design cannot separate the two.
- **Refusal justification.** One code ("other") absorbs 15.7% of refusals and is
  internally heterogeneous; two others fire on two responses each.
- **Moral foundations.** Six binary judgements per response, none validated.

Refusal is rare (~5.4% overall), one model records none at all, and generation is
incomplete for Russian and Hindi on the four self-hosted models, so counts will
change. English is complete and the primary estimates will not move.

Diagnostic tables backing all of the above are in `pipeline/estimates/d01`–`d08`.
Every plotted quantity's specification, sample restriction, contrast definition,
*n*, event count, estimand type and uncertainty method are carried in the `e*`
tables.
