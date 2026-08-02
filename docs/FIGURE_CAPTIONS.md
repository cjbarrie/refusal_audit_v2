# Figure captions

Publication-ready captions for `pipeline/figures/`. The figures deliberately
carry no titles, subtitles or explanatory prose; everything needed to interpret
them is here. Each figure is exported as PNG at 600 dpi.

Unless stated otherwise: the unit of observation is one model response to one
prompt; refusal is `engagement_code >= 4` on the judge's 1–5 engagement scale
(4 = soft refusal, 5 = hard refusal); and figures are restricted to
English-language prompts, the only language complete for all eleven models at
the time of writing.

---

## FC — Combined

**Refusal tracks the developer's own jurisdiction, and does so independently of
prompt language.**
**(A)** Average marginal effect of an issue falling in a model's home region on
the probability of refusal, by developer jurisdiction, holding topic domain
fixed by g-computation over the observed domain distribution. Points are point
estimates; bars are 95% percentile intervals from 400 nonparametric bootstrap
replicates resampling *issues* (responses are clustered within issue, since all
models answer the same battery). Mistral Large 2512 never refuses in this
sample, so the EU contrast is identically zero and no interval is defined.
**(B)** Refusal rate for every jurisdiction × issue-region cell, with 95% Wilson
intervals. The enlarged, coloured point in each panel is that jurisdiction's
home region; all other cells are shown in grey. Regions appear in the same order
in every panel, so the home cell descends the diagonal from left to right.
**(C)** Refusal rate for the two Chinese-developed models on home-region
(China) versus away-region issues, separately for English and Chinese prompts,
with 95% Wilson intervals. The home–away gap is approximately parallel across
languages, indicating that the regional and linguistic effects are additive
rather than interacting. *n* = 81,724 responses; English-only in A and B.

---

## F1 — Home-region effect

**Chinese-developed models refuse home-region issues ~19 percentage points more
often than comparable issues elsewhere; US and EU models show no such effect.**
Average marginal effect of home-region status on P(refusal), by developer
jurisdiction, adjusted for topic domain by g-computation. Adjustment is
necessary because issue region and topic domain are strongly confounded: 45% of
China-focused issues are territorial-sovereignty and 45% of Arab-focused issues
are security-conflict, both high-refusal domains. Bars are 95% percentile
bootstrap intervals over 400 issue-level resamples. "General" issues, which have
no regional focus, are excluded from the contrast. English prompts only.

---

## F2 — Jurisdiction × issue region

**The home-region effect is visible in the raw cell means and is confined to
Chinese and MENA models.**
Refusal rate for each combination of developer jurisdiction (panels) and issue
region (rows), with 95% Wilson intervals. The enlarged coloured point marks the
jurisdiction's own region. Rows are in a fixed order across panels so that the
home cell traces a descending diagonal. Region is a six-level stratum of the
sampling frame, not a geographic coordinate: "General" issues (17% of the
sample) have no location, and "Arab" is non-contiguous, so no map projection is
used. English prompts only.

---

## F3 — Home effect by prompt language

**The regional and linguistic effects are additive.**
Refusal rate for the two Chinese-developed models on home-region versus
away-region issues, by prompt language, with 95% Wilson intervals. The home–away
gap is ~15–18 percentage points in both English and Chinese for both models. By
contrast the *baseline* (away-region) rate rises sharply in Chinese for
DeepSeek V3.1 but not for Qwen3-Max, indicating that the language effect is
model-specific while the regional effect is shared.

---

## F4 — Between-model heterogeneity

**Refusal rates span two orders of magnitude across models, and boundary framing
does not uniformly increase them.**
Refusal rate by model on regular prompts (grey) and boundary prompts (coloured
by developer jurisdiction), joined by a segment showing the within-model shift.
Models are ordered by regular-tier refusal rate. Boundary prompts ask the model
to argue for a specified position; regular prompts ask an open question about
the same issue. English prompts only.

---

## F5 — Stated reason for refusal

**Models differ in the reason they give for refusing, not only in how often.**
Composition of refusal justifications by model, as a share of that model's
refusals. The judge's seven codes are collapsed to four groups: *neutrality*
(declining to take a political position), *harm* (harm avoidance), *epistemic*
(complexity, expertise limits, or user autonomy), and *unstated* (no reason
given, or other). Models with fewer than 30 refusals are omitted, since a
composition cannot be estimated from a handful of cases. Models are ordered by
neutrality share. English prompts only.

---

## F6 — Topic-domain gradient

**Refusal concentrates in security, governance and territorial topics.**
Refusal rate by topic domain, separately for regular and boundary prompts, with
95% Wilson intervals, pooled over all eleven models. Domains are ordered by
regular-tier rate and appear in the same order in both panels. Topic domain is
a nine-level fixed vocabulary describing what an issue is *about*, assigned at
sourcing. English prompts only.

---

## Notes on coverage

At the time of writing, generation is complete for English across all eleven
models. The seven OpenRouter-served models are complete for Chinese and Arabic
and ~98% complete for Russian; the four self-hosted endpoint models (ALLaM,
Jais, Falcon3, Sarvam) have little non-English data. Every figure above is
therefore restricted to English except F3, which uses only the two
Chinese-developed models, both of which have complete Chinese coverage. Figures
should be regenerated once the remaining languages finish.
