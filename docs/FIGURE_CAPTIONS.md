# Figure captions

Publication-ready captions for `pipeline/figures/`. The figures carry no titles,
subtitles or explanatory prose; everything needed to interpret them is here.
Each is exported as PNG (600 dpi) and PDF (vector).

Unless stated otherwise: the unit of observation is one model response to one
prompt; refusal is `engagement_code >= 4` on the judge's 1-5 engagement scale;
and figures use English prompts, the only language complete for all eleven
models. Colour is semantic by developer jurisdiction throughout -- **CN** deep
red, **India** slate blue, **MENA** burnt ochre, **US** grey-blue, **EU** light
slate -- and the locator map in FIG1A introduces that palette.

---

## FIG1 — Hero figure

**Refusal tracks the developer's own jurisdiction, and does so independently of
prompt language.**

**(A)** Locator map identifying the five issue regions used throughout, coloured
as they are in every other panel. The map is a key: it carries no quantities.
Countries outside the five regions are unshaded. A sixth stratum, "General"
(17% of issues), has no geographic location and so does not appear here.

**(B)** Average marginal effect of an issue falling in a model's home region on
the probability of refusal, by developer jurisdiction, holding topic domain
fixed by g-computation over the observed domain distribution. Points are point
estimates, bars 95% percentile intervals from 400 nonparametric bootstrap
replicates resampling *issues* — all models answer the same battery, so
responses are clustered within issue. Chinese-developed models refuse
home-region issues 18.8 pp more often; MENA models 2.7 pp; US, India and EU
intervals span zero. Mistral Large 2512 never refuses in this sample, so the EU
contrast is identically zero with no interval. Right-hand column gives *n*.

**(C)** Refusal rate (%) for every jurisdiction × issue-region cell. Cells are
shaded by rate; the home cell of each jurisdiction is filled in that
jurisdiction's colour with reversed type. Three patterns: the coloured diagonal
(each jurisdiction's own region), the uniformly darker Arab row (Arab-focused
issues are broadly sensitive, including to models with no stake in them — India's
models refuse them at 12.7% against 7.6% for their own region), and CN's
China-specific spike (19.6% against 1.9–6.7% elsewhere) rather than a general
elevation.

**(D)** Refusal rate for the two Chinese-developed models on home-region versus
away-region issues, by prompt language. The two lines are near-parallel in both
panels: the home–away gap is 14.7–18.1 pp regardless of language. What changes
is the baseline — DeepSeek's away rate rises from 2.6% to 14.5% in Chinese while
Qwen's does not (4.6% to 3.6%). The regional and linguistic effects are
therefore additive, and the language effect is model-specific.

---

## FIG2 — Supporting figure

**(A)** Refusal rate by model, regular prompts (grey point) to boundary prompts
(arrowhead), coloured by developer jurisdiction, ordered by regular-tier rate.
The right-hand column gives the signed shift in percentage points. Boundary
prompts ask the model to argue for a specified position; regular prompts ask an
open question about the same issue. **The shift is not one-directional**: six
models refuse less when asked to advocate (GPT-4o falls 4.3% to 0.1%) and four
refuse more (Sarvam rises 2.1% to 10.4%).

**(B)** Refusal rate by topic domain, regular to boundary, ordered by
regular-tier rate. Direction is carried by the arrowhead and redundantly by
lightness. Security and governance fall under boundary framing; religion,
social-moral and civil-rights roughly double.

**(C)** Composition of refusal justifications, as a share of each model's own
refusals, faceted by reason on a common scale. The judge's seven codes are
collapsed to four: neutrality (declining to take a political position), harm
(harm avoidance), unstated (no reason given, or other), epistemic (complexity,
expertise limits, user autonomy). Models ordered by neutrality share; those with
fewer than 30 refusals omitted. Neutrality dominates for most models; Jais 8B is
the exception at 81% harm avoidance and 17% neutrality, and Claude Opus 4.5 is
the only model with a substantial epistemic share (18%).

---

## Standalone panels

`P0_locator`, `P1_home_effect`, `P2_region_matrix`, `P3_home_by_language`,
`P4_model_tier`, `P5_refusal_reasons`, `P6_topic_domain` are the same panels
sized for individual use.

---

## Notes on coverage and inference

Generation is complete for English across all eleven models. The seven
OpenRouter-served models are complete for Chinese and Arabic and ~98% for
Russian; the four self-hosted endpoint models have little non-English data.
FIG1D uses Chinese only for the two CN models, both of which have complete
Chinese coverage.

Only FIG1B accounts for clustering of responses within issues; the Wilson
intervals in FIG1C–D are computed per cell and are correspondingly optimistic.
FIG1B adjusts for topic domain only — region could still proxy for unmeasured
properties of the issues themselves, so the estimates are descriptive rather
than causal. "No home effect for EU" means Mistral never refuses at all, which
is a different fact from an estimated null.
