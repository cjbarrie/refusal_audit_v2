# Figure captions

Publication-ready captions for `pipeline/figures/`. Figures carry no titles,
subtitles or interpretive prose; everything needed to read them is here. All
output is PNG at 600 dpi, rendered directly at each width (previews are not
downscaled rasters).

**Conventions.** Unit of observation is one model response to one prompt.
Refusal is `engagement_code >= 4` on the judge's 1–5 engagement scale. Colour
encodes **model jurisdiction only** — CN deep red, India slate blue, MENA burnt
ochre, US grey-blue, EU light slate — and issue regions inherit the colour of
the jurisdiction whose home they are. Language is encoded by **shape and line
type**, prompt tier by **circle (regular) versus triangle (boundary)**, and
refusal reasons by a **separate four-colour palette**; no visual variable
carries two meanings. Analyses are **English-only**, the sole language complete
for all eleven models. Results are **descriptive, not causal**.

---

## Figure 1 — Distinctive home-region sensitivity is a China result

`FIG1_home_region_main.png` (also `_1col`, `_2col`)

**Chinese-developed models are markedly more likely than models from other
jurisdictions to refuse China-focused issues; no other jurisdiction shows a
comparable effect on the same comparison.**

**(A)** Locator identifying the five issue regions, coloured as in every other
panel. The map is a key and carries no estimates. "Arab" is operationalised as
the 22 Arab League member states; "Europe" as countries with continent =
*Europe* excluding Russia; China, India and the US as those single countries. A
sixth issue stratum, **General** (17% of issues; no regional focus), has no
geographic location and is not shown. Shading marks **issue-region
classification**, not the location of model developers — distinct objects that
happen to use aligned category names.

**(B) Primary estimand.** Adjusted **home premium**: the difference in predicted
probability of refusal between a jurisdiction's own-region issues and other
issues, **holding the issue fixed**. From
`refused ~ home × jurisdiction + prompt tier + (1 | issue)`, binomial, fitted on
English non-General responses (*n* = 20,796; 520 issues; 1,239 refusals). Points
are g-computation averages over the observed sample; bars are 95% intervals from
a parametric bootstrap (2,000 draws) over the fixed-effect covariance. Because
issue region and topic domain are constant within issue, the issue random
intercept absorbs both, and the contrast compares jurisdictions **answering the
same issues**. Mistral Large 2512 records 0 refusals in 2,080 responses; the EU
contrast is therefore not estimable and appears as a hollow square, not as an
estimate of zero.

**(C) Why the estimand matters.** The same jurisdictions under two contrasts:
the within-issue premium from (B) (circles) and an adjusted
**within-jurisdiction** home-versus-away difference (triangles) that does not
condition on the issue. MENA's effect is +2.7 pp on the descriptive contrast and
+0.1 pp on the primary one; India reverses sign. Only CN is stable across both.

**(D) Where refusal exceeds an additive baseline.** Cells give the observed
refusal rate (printed, %) with fill showing the **excess** over a
jurisdiction-plus-region additive model — how much higher a cell runs than
expected from that jurisdiction's general propensity and that region's general
sensitivity. Home cells are outlined. CN × China is strongly positive; MENA ×
Arab is near zero, because Arab-focused issues are sensitive for everyone. Fill
is a diverging scale centred on zero; the EU column is not estimable and
unshaded. Descriptive.

**(E) The China result across prompt languages.** Home premium for the two
Chinese-developed models, estimated separately in English and Chinese from
`refused ~ home × language + tier + (1 | issue)`; 95% parametric-bootstrap
intervals. Grey annotations give the away-region baseline rate. The premium is
of similar magnitude in both languages for both models, while the *baseline*
rises sharply in Chinese for DeepSeek (2.6% → 14.5%) and not for Qwen
(4.6% → 3.6%). The home × language interaction is not significant for Qwen
(p = 0.48); for DeepSeek it is significant on the log-odds scale (p = 2.6e-05)
while its probability-scale premium is slightly larger in Chinese — a scale
effect of the higher baseline. These results are **consistent with similar home
gaps across languages**; they do not establish additivity.

---

## Figure 2 — Prompt framing moves models in opposite directions

`FIG2_model_domain_main.png` (also `_1col`, `_2col`)

**Boundary framing has no universal effect: it lowers refusal for some models
and domains and raises it for others.**

**(A)** Left: refusal rate by model on regular (circle) and boundary (triangle)
prompts, joined by a segment, coloured by developer jurisdiction. Right: the
signed **shift** (boundary − regular) with 95% intervals. Estimates come from
per-model mixed models `refused ~ tier + (1 | issue)`, so the contrast is a
**within-issue paired** comparison — regular and boundary prompts derive from
the same issue by design, and independent-binomial intervals would be wrong on
two counts. Models are ordered by signed shift. Mistral Large 2512 records no
refusals and appears as a hollow square with no interval. Boundary prompts ask
the model to argue for a stated position; regular prompts ask an open question
about the same issue.

**(B)** The same decomposition by topic domain, pooled across models from
`refused ~ tier × domain + (1 | issue) + (1 | model)`. The model random
intercept prevents a few high-refusal models from driving apparent domain
differences. Security-conflict and governance-democracy refusals **fall** under
boundary framing; religion-state, social-moral and civil-rights **rise**.
Domains ordered by regular-tier rate; endpoint shapes as in panel A.

---

## Figure 3 — Models differ in the reasons they give for refusing

`FIG3_refusal_reasons_main.png` (also `_1col`, `_2col`)

**Refusal rationale varies across models independently of refusal rate.**

Composition of refusal justifications by model, as a share of that model's own
refusals. The judge's seven codes are collapsed to four: **neutrality**
(declining to take a political position), **harm** (harm avoidance),
**unstated** (no reason given, or other) and **epistemic** (complexity,
expertise limits, user autonomy). Reason categories have their own palette;
model jurisdiction appears only as the bullet beside each model name, so
jurisdiction colour never doubles as a reason colour. The right-hand column
gives *n*, the number of refusals forming each denominator. Models with fewer
than 30 refusals are omitted; denominators range from 50 to 418, so shares for
the smaller models are imprecise. Ordered by neutrality share.

Neutrality dominates for most models. Jais 8B is the exception at 81% harm
avoidance; Claude Opus 4.5 is the only model with a substantial epistemic share.
**Conditional on having refused**, so this describes rationale, not propensity —
a model with a distinctive composition may still refuse rarely.

---

## Measurement limitations

Refusal codes come from a **single LLM judge** (`google/gemini-2.5-flash-lite`,
temperature 0). **No second-judge pass exists and no inter-rater reliability has
been estimated**; this is the study's principal measurement limitation and every
refusal quantity inherits it. Refusal is rare (~5% overall), one model records
none at all, and generation is incomplete, so counts will change.

Standalone panels `P1`–`P8` are the same panels sized for individual use.
Estimates live in `pipeline/estimates/`; the specification, sample restriction,
contrast definition, *n* and event count for every plotted quantity are carried
in those tables.
