# Figure captions

Publication-ready captions for `pipeline/figures/`. Figures carry no titles,
subtitles or interpretive prose; everything needed to read them is here. All
output is PNG at 600 dpi, rendered directly at **two-column width**. There are
no one-column variants and no duplicate size files.

**Conventions.** Unit of observation is one model response to one prompt.
Refusal is `engagement_code >= 4` on the judge's 1–5 engagement scale.

| visual variable | meaning |
|---|---|
| colour | **model jurisdiction only** (CN deep red, India slate, MENA ochre, US grey-blue, EU light slate); issue regions inherit their jurisdiction's colour |
| circle / triangle | prompt tier: regular / boundary |
| filled / hollow | estimand: primary / descriptive — and language in P5 |
| four-hue palette | refusal reason (distinct from jurisdiction colours) |
| thin light interval | uncertainty |

Analyses are **English-only**, the sole language complete for all eleven models.
Results are **descriptive, not causal**.

---

## Figure 1 — Distinctive home-region sensitivity is a China result

`FIG1_home_region_main.png`

**Chinese-developed models are far more likely than models from other
jurisdictions to refuse China-focused issues; no other jurisdiction shows a
comparable effect on the same comparison, and simpler home-versus-away contrasts
overstate MENA.**

**(A) Regional key.** Locator identifying the five issue regions in the colours
used throughout the figure. It carries no estimates and is subordinate to the
statistical panels. "Arab" is operationalised as the 22 Arab League member
states; "Europe" as countries with continent = *Europe* excluding Russia; China,
India and the US as those single countries. A sixth issue stratum, **General**
(17% of issues; no regional focus), has no geographic location and is not shown.
Shading marks **issue-region classification**, not the location of model
developers — distinct objects that happen to use aligned category names.

**(B) Primary estimand — model-based.** Adjusted **home premium**: the
difference in predicted probability of refusal between a jurisdiction's
own-region issues and other issues, **holding the issue fixed**. From
`refused ~ home × jurisdiction + prompt tier + (1 | issue)`, binomial, on
English non-General responses (*n* = 20,796; 520 issues; 1,239 refusals). Points
are g-computation averages over the observed sample; bars are 95% intervals from
a parametric bootstrap (2,000 draws) over the fixed-effect covariance. Because
issue region and topic domain are constant within issue, the issue random
intercept absorbs both and the contrast compares jurisdictions **answering the
same issues** — the clustering unit is the issue throughout. CN is drawn
slightly heavier because it carries the result. Mistral Large 2512 records **0
refusals in 2,080 responses**, so the EU contrast is not estimable; it is marked
with a hollow square and stated in words, never plotted as an estimate of zero.
India's +3.0 pp rests on a **single model** (Sarvam) and **reverses sign**
between the two estimands in panel C; it should not be read as a finding.

**(C) Why the estimand matters — model-based.** One row per jurisdiction showing
both contrasts: the within-issue premium from panel B (filled point, with its
95% interval) and an adjusted **within-jurisdiction** home-versus-away
difference (hollow point) that does **not** condition on the issue. The
descriptive contrast has no interval drawn, to keep the row readable; its values
are in `pipeline/estimates/e03_home_within_jurisdiction.csv`. Labels give the
descriptive-to-primary transition where the two materially differ. MENA moves
from +2.7 to +0.1 pp and India from −1.4 to +3.0; CN is stable. The
within-jurisdiction contrast cannot distinguish "this jurisdiction is sensitive
about its own region" from "this region is sensitive to everyone", which is why
it is descriptive only.

**(D) Raw regional structure — descriptive.** Observed refusal rate (%) for each
model-jurisdiction × issue-region cell. Fill encodes the same quantity that is
printed, on one sequential scale. Thin grey outlines mark home cells; the single
red outline marks CN × China. **General** issues (no regional focus, 17% of the
battery) are excluded here for consistency with the estimand in panels B and C,
which is undefined for them. The Arab row is elevated across every jurisdiction
— India's models refuse Arab issues at 12.5% against MENA's 13.4%, from a much
lower baseline — which is why MENA's home effect does not survive the
within-issue comparison. The EU column is zero throughout.

---

## Figure 2 — Prompt framing moves refusal in opposite directions

`FIG2_model_domain_main.png`

**Boundary framing has no universal effect: it lowers refusal for some models
and domains and raises it for others.**

**(A) By model — model-based.** Refusal rate on regular (circle) and boundary
(triangle) prompts, joined by a segment coloured by developer jurisdiction, with
the signed shift printed at the right. Estimates come from per-model mixed
models `refused ~ tier + (1 | issue)`, so each contrast is a **within-issue
paired** comparison: regular and boundary prompts derive from the same issue by
design, and independent-binomial intervals would be wrong both for the pairing
and for the recurrence of issues across models. Rows are ordered by signed
shift, largest increase at the top. Mistral Large 2512 is marked `n/e` — no
refusals, so no contrast. 95% intervals for every shift are in
`pipeline/estimates/e11_model_tier.csv`. Boundary prompts ask the model to argue
for a stated position; regular prompts ask an open question about the same
issue.

**(B) By topic domain — model-based.** The same decomposition pooled across
models from `refused ~ tier × domain + (1 | issue) + (1 | model)`. The model
random intercept prevents a few high-refusal models from driving apparent domain
differences. Ordered by signed shift: security-and-conflict and
governance-and-democracy **fall** under boundary framing, while religion,
social-and-moral and civil-rights **rise**. Intervals in
`pipeline/estimates/e12_domain_tier.csv`.

---

## Figure 3 — Models differ in the reasons they state for refusing

`FIG3_refusal_reasons_main.png`

**Neutrality dominates overall, Jais is a harm-avoidance outlier, and Claude is
uniquely epistemic.**

Composition of refusal justifications by model, as a share of that model's own
refusals; **conditional on having refused**, so this describes rationale, not
propensity. The judge's seven codes are collapsed to four: **neutrality**
(declining to take a political position), **harm** (harm avoidance),
**epistemic** (complexity, expertise limits, user autonomy) and **unstated** (no
reason given, or other). Reason categories carry their own four-hue palette;
model jurisdiction appears only as the small bullet beside each model name, so
jurisdiction colour never doubles as a reason colour. Denominators are printed
in the row label (`model · n=…`). Segments are labelled with their percentage
only where they exceed 12% of the bar. Models with fewer than 30 refusals are
omitted; denominators range from 50 to 418, so shares for the smaller models are
imprecise. Ordered by neutrality share, from neutrality-dominant at the top to
harm-dominant at the bottom.

---

## Standalone panels

`P1`–`P8` are two-column PNGs for individual use. `P5` and `P4` carry analyses
that are **not** in the main three-figure sequence:

- **`P1_locator.png`** — the same locator as Figure 1A, sized for standalone or
  presentation use.
- **`P5_china_language.png`** — home premium for the two Chinese-developed
  models, estimated separately in English and Chinese from
  `refused ~ home × language + tier + (1 | issue)`, with 95%
  parametric-bootstrap intervals and the away-region baseline in an aligned
  right-hand column. Language is filled versus hollow here, not circle versus
  triangle, so it cannot be confused with the prompt-tier encoding in Figure 2.
  The premium is of similar magnitude in both languages for both models, while
  the **baseline** rises sharply in Chinese for DeepSeek (2.6% → 14.5%) and not
  for Qwen (4.6% → 3.6%). The home × language interaction is not significant for
  Qwen (*p* = 0.48); for DeepSeek it is significant on the log-odds scale
  (*p* = 2.6e-05) while its probability-scale premium is slightly *larger* in
  Chinese — a scale effect of the higher baseline, not a contradiction. These
  results are **consistent with similar home gaps across languages**; they do
  not establish additivity.
- **`P4_region_structure.png`** — the same cells as Figure 1C but showing
  **excess refusal (pp)** over an additive jurisdiction + region baseline, on a
  diverging scale centred at zero, with the excess printed rather than the raw
  rate. Analytically sharper than the raw matrix and kept out of the main figure
  because raw rates read faster there. CN × China is strongly positive;
  MENA × Arab is near zero.

---

## Measurement limitations

Refusal codes come from a **single LLM judge** (`google/gemini-2.5-flash-lite`,
temperature 0). **No second-judge pass exists and no inter-rater reliability has
been estimated**; this is the study's principal measurement limitation and every
refusal quantity inherits it. Refusal is rare (~5% overall), one model records
none at all, and generation is incomplete, so counts will change.

Estimates live in `pipeline/estimates/`; the specification, sample restriction,
contrast definition, *n* and event count for every plotted quantity are carried
in those tables.
