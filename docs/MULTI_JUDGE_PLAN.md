# Multi-judge annotation and reliability plan

Status: **PLUMBING IMPLEMENTED AND TESTED; NO API SPEND YET.** Written and
built 2026-08-04.

Implemented (all $0):
- judge identity on every annotation record (`judge_model`,
  `judge_prompt_version`, `annotation_run_id`)
- reasoning explicitly **disabled** on every judge call
- observed token usage recorded per call, so the budget can be re-calibrated
  from actuals
- `run_pilot.py --judge-panel [MODEL ...]` (bare flag = recommended panel),
  `--limit N` for pilot scoping
- panel judges write to `<run_dir>/panel/<judge>/`; assemble emits
  `annotations_panel.jsonl` (long format). **`annotations_all.jsonl` keeps its
  exact previous contract**, so `01_data_loading.R` and scripts 02–30 are
  untouched — verified by a full pipeline run: 12 ok, 1 skipped, 0 failed
- `pipeline/24_measurement.R` — k-rater reliability + robustness, validated
  end-to-end against a synthetic 4-judge panel
- `pipeline/16_irr_analysis.R` retired to a stub; `sample_for_second_judge.py`
  deleted (both were two-rater / v1-era)
- `ASSUMED_ENGAGE_RATE` corrected 0.83 → 0.944 (measured), which had been
  understating passes 2/3 volume by ~14%
- `TOK["judge"]` corrected (620, 60) → (1500, 90), calibrated; the old value
  under-priced judging roughly four-fold

**Not yet run: anything that costs money.** The pilot is the next step and needs
explicit go-ahead.

Goal: annotate refusal (Pass 1), ideology (Pass 2) and moral foundations
(Pass 3) with **several independent low-cost judges**, derive reliability
statistics, and re-integrate them so that every substantive conclusion carries a
measurement-error assessment. Must work with the existing pipeline and be
cost-effective, with a pilot gate before any full run.

All costs below are computed from **live OpenRouter pricing pulled 2026-08-04**
and a token model **calibrated against actual observed spend** (see §2).

---

## 1. What exists today, and the three gaps

| | current state |
|---|---|
| Primary judge | `google/gemini-2.5-flash-lite`, temp 0 |
| Pass 1 coverage | 100% of responses |
| Pass 2/3 coverage | 25% issue subsample, engaged responses only |
| Pass 4 (stance) | `openai/gpt-oss-120b`, not run on the full battery |
| Second judge | **none** — `16_irr_analysis.R` skips |
| True parse-failure rate | **0.35%** (525 / 149,948; the other 2,824 errors were one "insufficient credit" event, not judge failures) |

**Gap 1 — schema.** Annotation records carry **no judge identity**. Their `model`
field is the *subject* model. Nothing in the current schema can distinguish two
judges' verdicts on the same response. This is blocking and must be fixed first.

**Gap 2 — `16_irr_analysis.R` is two-rater only.** It uses `irr::kappa2` (Cohen's
kappa, exactly two raters) and expects a single file
`annotations_second_judge.jsonl`. It also covers Pass 1 and Pass 2 only —
**no moral-foundation reliability at all** — and its DeepSeek re-test reads
`prompts/test_prompts_<lang>.json`, a v1 path that no longer exists.

**Gap 3 — `scripts/sample_for_second_judge.py` is v1-era.** Hardcoded
`refusal_audit/…` paths and a language list including `ja`/`id`, both dropped.

---

## 2. Cost model (calibrated, not assumed)

Measured from the actual battery: **mean prompt + response = 3,696 characters**
(en 4,953; zh 2,177). At ~3.6 chars/token that is ~1,027 content tokens, plus the
judge template (Pass 1 ~300, Pass 2 ~800, Pass 3 ~740 tokens).

| pass | input tok | output tok |
|---|---|---|
| 1 engagement | ~1,327 | ~60 |
| 2 ideology | ~1,827 | ~120 |
| 3 moral foundations | ~1,767 | ~100 |

**Calibration check.** This model gives **$0.000605** per engaged response for all
three passes at flash-lite rates. Actual observed spend on the slant subsample
was **$0.000616/call-set**. The model is accurate to ~2%, so the projections
below can be trusted.

Full battery = 11 models × 2,496 prompts × 5 languages = **137,280 responses**;
~94.6% engaged. Per judge: 137,280 Pass-1 calls + 2 × 129,867 slant calls =
**~397,000 calls**.

### Candidate judges — full catalogue scan, 2026-08-04

**Superseded once already.** A first pass priced a hand-picked list from memory
and produced recommendations that a full scan of all **338 OpenRouter models**
showed to be dominated. The list below comes from enumerating the catalogue and
filtering on what a judge actually needs, not from recall.

**Filters applied**, each for a reason:

| filter | why |
|---|---|
| `structured_outputs` supported | the judge must emit a fixed JSON schema; without it parse failures dominate |
| reasoning **not mandatory** | reasoning tokens bill as output. Our output budget is 60–120 tokens; a reasoning model emits hundreds to thousands, inflating cost several-fold and latency with it |
| context ≥ 32k | comfortably clears the ~1,800-token Pass-2 input |
| paid tier | `:free` variants are rate-limited and unusable for ~80k calls |

**Quality signal.** OpenRouter exposes an `artificial_analysis.intelligence_index`
(AAI) for many models. This matters more than it might seem: **a weak judge
depresses α for reasons unrelated to construct difficulty**, so reliability would
be measuring judge incompetence rather than how hard the coding task is. A
quality floor is a design parameter, not a nicety.

| model | in | out | EN tier | full | AAI | developer | note |
|---|---|---|---|---|---|---|---|
| `inclusionai/ling-2.6-flash` | 0.010 | 0.030 | **$1.5** | $8 | 14.1 | Ant/InclusionAI | cheapest usable by a wide margin |
| `cohere/command-r7b-12-2024` | 0.037 | 0.150 | $6.0 | $30 | – | Cohere | no quality index; 7B, 2024 |
| `nvidia/nemotron-3-nano-30b-a3b` | 0.050 | 0.200 | $8.0 | $40 | 14.2 | NVIDIA | |
| `ibm-granite/granite-4.1-8b` | 0.050 | 0.100 | $7.2 | $36 | – | IBM | |
| `google/gemma-4-26b-a4b-it` | 0.070 | 0.340 | $11.6 | $58 | 25.7 | Google | |
| `nvidia/nemotron-3-super-120b-a12b` | 0.085 | 0.400 | $14.0 | $70 | **25.4** | NVIDIA | reasoning default-ON, must disable |
| `google/gemma-4-31b-it` | 0.100 | 0.340 | $15.5 | $77 | **29.4** | Google | best quality-per-dollar in the cheap tier |
| `google/gemini-2.5-flash-lite` | 0.100 | 0.400 | $15.9 | $80 | – | Google | **incumbent** |
| `nvidia/nemotron-3-ultra-550b` | 0.600 | 3.600 | $104 | $522 | 37.8 | NVIDIA | too expensive for a panel |

**What this overturns from the first draft:**

- **`amazon/nova-lite-v1` — dropped.** It does **not** support structured outputs
  or `response_format`. It would have been the parse-failure source.
- **`meta-llama/llama-3.3-70b` — dropped.** AAI 9.4 at $15.4/EN, strictly
  dominated by `gemma-4-31b` (AAI **29.4** at $15.5).
- **`microsoft/phi-4` — dropped.** 16k context, no published quality index,
  dominated on both axes.
- **`openai/gpt-oss-120b` — dropped, and a live problem flagged.** Its reasoning
  is `mandatory: true` — it **cannot be disabled**. Every call pays for reasoning
  tokens. This model is **currently the stance-pass (Pass 4) judge**, so the
  stance budget in `run_pilot.py` — which assumes 60 output tokens — is
  understated, probably several-fold. Worth re-pricing independently of this plan.
- **The incumbent is now the most expensive sensible option** and has no
  published quality index. It is retained purely for **continuity**: Pass 1 is
  already complete at 100% under it, and changing the anchor would invalidate
  that work.

### Recommended panel

Quality floor AAI ≥ 14, structured outputs, reasoning explicitly disabled:

| role | model | AAI | EN tier | full |
|---|---|---|---|---|
| anchor (incumbent) | `google/gemini-2.5-flash-lite` | – | $9 top-up¹ | $44 top-up¹ |
| B | `google/gemma-4-31b-it` | 29.4 | $15.5 | $77 |
| C | `nvidia/nemotron-3-super-120b-a12b` | 25.4 | $14.0 | $70 |
| D | `inclusionai/ling-2.6-flash` | 14.1 | $1.5 | $8 |
| **total** | | | **~$40** | **~$199** |

¹ Pass 1 is already complete under the anchor; it needs only passes 2/3 on the
remaining 75% of issues.

**The one tradeoff to accept or reject: two Google models.** The anchor (Gemini,
proprietary API) and judge B (Gemma, open weights) share a developer, so their
errors may be more correlated than the panel implies. They are different model
lineages, which mitigates it, but it is a real caveat. Two alternatives:

- **Swap B for `cohere/command-r7b`** (−$9.50, four distinct developers) — but it
  has no published quality index and is a 2024-vintage 7B, so it risks becoming
  the judge that drags α down.
- **Add it as a fifth judge** (+$6, five developers, keeps the quality floor).
  At these prices this is nearly free and is the safer choice if the Google
  correlation is a reviewer concern.

**Implementation requirement.** Judges C and B have reasoning **on by default**.
It must be explicitly disabled in the request (`reasoning: {enabled: false}` or
minimum effort). Left on, output tokens rise from ~100 to several hundred per
call and the panel cost roughly doubles, with latency to match. The pilot must
verify actual output-token counts per judge, not assume them.

**Speed.** OpenRouter routes to providers sustaining ≥50 tok/s at p90, so all of
these clear the throughput bar. Published figures put Gemma 4 at ~3,958 output
tok/s with 210 ms time-to-first-token, against GPT-OSS-120B's 3,443 tok/s and
504 ms — another reason to prefer Gemma over the reasoning-mandatory option.

**Free tiers for smoke-testing only.** `:free` variants exist for `gemma-4-31b`,
`gemma-4-26b`, `nemotron-3-nano` and `nemotron-3-super`. They are rate-limited
and may be served at different quantization, so they are unsuitable for the α
pilot — but they are useful for validating prompt templates and JSON parsing at
zero cost before spending anything.

**One experimental option worth a pilot slot:** `nvidia/nemotron-3.5-content-safety`
is a purpose-built safety-classification model. Refusal detection (Pass 1) is
close to its design task, so it may outperform general models on that pass
specifically. It is free-tier only, so it cannot join the paid panel, but it
would be informative to include in the pilot for Pass 1 alone.

### Tiered rollout — the main cost lever

**Every primary estimate in the paper is English-only.** Non-English labels feed
only `P11` and the DeepSeek language analysis. So:

- **Tier 1 — English panel, ~$44.** Covers FIG1, FIG2, FIG3, FIG4 and every
  headline claim.
- **Tier 2 — add zh + ar, ~$130 cumulative.** The complete-roster languages;
  covers `P11` and the DeepSeek zh-vs-en analysis.
- **Tier 3 — add ru + hi, ~$220 cumulative.** Only worth it once generation for
  the self-hosted models finishes.

Recommendation: **run Tier 1, analyse, then decide.** The reliability picture
from 27,456 English responses × 4 judges will not change materially by adding
languages, and Tier 1 is cheap enough to run twice if the design needs revising.

---

## 3. Pilot (gate before any full run)

**Design.** 2% of issues (13 issues), drawn with the existing issue-level
sampler, all 11 models, all 5 languages, all 4 judges, all 3 passes.

- 13 issues × 4 prompts × 11 models × 5 languages = **2,860 responses**
- ~8,270 calls per judge → **~33,000 calls** across the panel
- **~$5 total**, roughly 1–2 hours wall-clock at current concurrency

**Decision gates — proceed to Tier 1 only if all pass:**

| gate | threshold | why |
|---|---|---|
| parse-failure rate per judge | < 2% after one retry | a judge that cannot emit the schema is unusable |
| cost per call vs projection | within ±25% | validates the token model on this workload |
| refusal-rate sanity per judge | within ~2× of the incumbent's 5.4% | a judge calling 30% refusal is not measuring the same construct |
| Krippendorff α, binary refusal | point estimate > 0.4 | below this the construct is not reliably measurable and the design needs rethinking, not more data |
| no judge is degenerate | no judge emits a constant code | catches a model that always answers "1" |

The pilot also produces the first **α confidence intervals**, which tell us
whether the full run will estimate reliability precisely enough to be worth
reporting. It is deliberately a *small slice of everything* rather than a large
slice of English, because its purpose is operational validation across the whole
matrix.

---

## 3b. PILOT RESULTS (run 2026-08-04, 12 issues x 5 languages x 4 judges)

10,446 panel rows over 2,615 responses. Cost ~$4.50.

### Gates: four passed, one failed

| gate | threshold | result |
|---|---|---|
| parse failures | < 2% | **PASS** — 0.0–0.4% per judge |
| cost vs projection | ±25% | **PASS** — measured 1,865 input tok/call vs 1,640 modelled (+14%) |
| binary refusal α | > 0.4 | **PASS** — α 0.498, AC1 0.952, raw agreement 0.920 |
| no degenerate judge | — | PASS (ling borderline: 96.7% of codes = "1") |
| refusal rate within ~2× | | **FAIL — `inclusionai/ling-2.6-flash`** |

`ling-2.6-flash` flags refusal at **1.76%** against the anchor's 6.53% — 3.7×
apart. It passed every *specification* check (structured outputs, no reasoning,
AAI 14.1) and still failed to measure the construct, which is the single most
important lesson from the pilot: **judge suitability cannot be read off the
model card, only measured.**

### What the panel says about the instrument

| construct | raw agreement | α | AC1 |
|---|---|---|---|
| engagement 1–5 | 0.771 | 0.432 | 0.858 |
| **refused (≥4)** | **0.920** | **0.498** | **0.952** |
| fairness/cheating | 0.746 | 0.716 | 0.717 |
| care/harm | 0.649 | 0.607 | 0.605 |
| sanctity/degradation | 0.905 | 0.604 | 0.941 |
| ideology (4 dims) | 0.29–0.52 | 0.19–0.41 | 0.48–0.70 |
| justification (7 codes) | 0.24 | 0.248 | 0.388 |

The prevalence argument in §4.2 is vindicated: for binary refusal α = 0.50 while
AC1 = 0.95 on 92% raw agreement. Reporting α alone would have understated a
usable instrument.

**The sobering number is positive specific agreement: 0.107.** When any judge
flags a refusal, all four agree only 10.7% of the time. The panel's majority-vote
refusal rate is **3.06%** against the anchor's 6.53%, so the labels the paper
currently uses flag roughly twice what a majority of judges would. This belongs
in the limitations regardless of what the full run shows.

**MENA labels are the least reliable in the study** (positive specific agreement
0.05–0.09). That bears directly on the language findings in `25_estimates_language.R`:
allam-7b's 68.8% Russian refusal rate rests on labels the panel barely agrees on.

### Differential-error test — and a flaw in its first version

The first implementation compared the CN home cell to the **pooled** rate across
all jurisdictions. MENA disagreement (~25%) dominates that pool, so the test
reported "ratio 1.04, not concentrated" while CN-home disagreement was in fact
**11.7× CN-elsewhere**. It would have cleared the headline result on a comparison
incapable of detecting a problem. Corrected on two counts:

1. the contrast is **within jurisdiction**;
2. it reports **positive specific agreement per cell**, because raw disagreement
   scales mechanically with prevalence — a cell refusing at 20% shows more
   disagreement than one at 3% whatever the judges do.

On the corrected test: CN-home raw disagreement is 11.7× CN-elsewhere, but
agreement among *flagged* cases is higher in the home cell (0.444 vs 0.000).
Consistent with **non-differential** error — but the elsewhere cell has only 2
flagged units, so this is **not yet decisive** and needs the Tier 1 sample.

## 3c. BAKE-OFF AND FINAL PANEL (2026-08-05)

Ling failed the refusal-rate gate, so three replacements were tested on the
identical 12-issue pilot slice (7 judges, 18,335 panel rows, ~$3).

| judge | refusal rate | ratio to anchor | recall vs anchor | pairwise α | drop → α gain |
|---|---|---|---|---|---|
| nemotron-3-super | 6.65% | **1.02** | **0.725** | **0.699** | −0.013 |
| gemma-4-31b | 3.33% | 0.51 | 0.433 | 0.552 | **−0.019** |
| **nemotron-3-nano** | 4.36% | 0.61 | 0.476 | 0.567 | −0.011 |
| mistral-small-3.2 | 2.55% | 0.36 | 0.328 | 0.458 | −0.005 |
| granite-4.1-8b | 1.60% | 0.24 | 0.218 | 0.325 | **+0.018** |
| ling-2.6-flash | 1.76% | 0.27 | 0.200 | 0.285 | **+0.038** |

`mistral-small-3.2` — the pick from the specification sheet — **failed**: lowest
recall of the three and the highest parse-error rate of any judge (1.9%, at the
gate). `granite-4.1-8b` failed like Ling: dropping it *raises* α. Only
`nemotron-3-nano` earned its place.

**This is the methodological lesson of the whole exercise: judge suitability
cannot be read off a model card.** Two candidates passed every specification
check and still failed to measure the construct. Always bake off on a pilot slice
and select on measured recall/α.

**A finding beyond judge selection.** Five of seven judges detect roughly *half*
the refusals the anchor does (ratios 1.02, 0.61, 0.51, 0.36, 0.27, 0.24). The
paper's headline ~5.4% refusal rate comes entirely from the anchor. Without
ground truth the panel cannot say whether the anchor over-detects or the cheap
models under-detect, but the question belongs in the limitations.

### Final panel — Tier 1 English, $48.22

`gemini-2.5-flash-lite` (anchor) + `gemma-4-31b` + `nemotron-3-super` +
`nemotron-3-nano`. Leave-one-out confirms all four contribute.

**Status as of 2026-08-06:** anchor ✅ and `gemma-4-31b` ✅ complete
(27,395/27,450, 0.20% errors); `nemotron-3-nano` running; `nemotron-3-super`
queued last.

⚠ **`nemotron-3-super` is unreliable in production.** Its provider began
returning null payloads and the run **stalled for 2h19m**. It responds again but
at **10–14 s/call against 0.5 s** for every other judge. Two fixes followed: the
judge client now sets an explicit **90 s timeout** (its absence was what turned a
provider stall into an indefinite hang), and the panel is ordered so the reliable
judges finish first — a 3-judge panel answers every Tier 1 question, and Super is
a bonus rather than a dependency.

## 4. Statistical plan

### 4.1 Reliability estimands, by construct

The pipeline has four distinct measurement types and they need different
statistics. Using one statistic for all of them would be wrong.

| construct | scale | statistic | why |
|---|---|---|---|
| engagement code | ordinal 1–5 | **Krippendorff's α, ordinal** | k raters, handles missing, respects order (a 1-vs-2 disagreement is less severe than 1-vs-5) |
| refused (≥4) | binary | **α nominal + raw agreement + Gwet's AC1** | see §4.2 |
| refusal justification | nominal 7, and collapsed 5 | **α nominal** | unordered categories |
| ideology ×4 | ordinal −2..+2 | **α ordinal**, per dimension | order is meaningful |
| moral foundations ×6 | binary | **α nominal + AC1**, per foundation | see §4.2 |

**Why Krippendorff's α throughout and not Cohen's/Fleiss'.** Cohen's κ is
two-rater only. Fleiss' κ requires every unit rated by the same number of raters
and handles no missing data. α accepts any number of raters, missing values (a
judge's parse failure just drops that cell), and any measurement level. It is the
only statistic that covers this design without special-casing.

**Uncertainty.** Bootstrap α by **resampling issues**, not responses — consistent
with every other interval in the pipeline, and necessary because responses are
clustered within issue. 2,000 resamples, percentile intervals.

### 4.2 The prevalence problem — this is the important one

Refusal is **5.4% prevalent**; `sanctity_degradation` is **3.1%**. At these
marginals, chance-corrected agreement statistics are unstable and can be near
zero even when raters agree on 97% of cases — the well-known **kappa paradox**.

Reporting α alone would make the instrument look far worse than it is; reporting
raw agreement alone would make it look far better. The plan therefore reports
**three numbers for every binary construct**:

1. **raw percent agreement** — interpretable, but inflated by rare positives
2. **Krippendorff's α** — chance-corrected, but paradox-prone at low prevalence
3. **Gwet's AC1** — chance-corrected and *prevalence-robust*; the right headline
   number for rare-outcome constructs

Plus **positive specific agreement** (the agreement among cases at least one
judge flagged) — for a rare outcome this is the quantity that actually matters,
because it asks "when a judge says refusal, do the others agree?" rather than
"do they agree on the overwhelming majority of non-refusals?".

### 4.3 Robustness of substantive conclusions — beyond reliability

**IRR alone does not tell you whether any conclusion changes.** A judge panel is
worth its cost only if it is used to re-estimate. Four analyses, in order of
importance:

**(a) Per-judge replication of the headline estimate.** Refit the primary model
`refused ~ home × jurisdiction + tier + (1 | issue)` **separately on each
judge's labels**, giving four independent estimates of each jurisdiction's home
premium. This is the single most persuasive robustness check available and is
trivially interpretable: if China's ~+17.6 pp holds at +14 to +21 across four
unrelated judges, the finding is not an artefact of one model's idiosyncrasy.
Presented as a small-multiple forest plot.

**(b) Consensus-label re-estimation.** Construct two alternative outcomes —
**majority vote** (≥3 of 4) and **unanimous** — and refit. Unanimous labels are a
high-specificity outcome; if the effect survives on them it is not driven by
marginal cases.

**(c) Differential-error test — critical for the China result.** Non-differential
measurement error attenuates estimates toward the null; **differential** error
can manufacture them. The question is whether judges disagree *more* precisely
where the finding lives. Fit

```
disagree ~ home × jurisdiction + tier + (1 | issue)
```

where `disagree` = 1 if judges are not unanimous on `refused`. **If disagreement
is elevated in the CN × China cell, the home premium is partly a measurement
artefact and must be reported as such.** This test is the main scientific
justification for the whole exercise and should be run first on the pilot.

**(d) Attenuation bounding.** Under non-differential error with sensitivity/
specificity estimated from the panel, the observed effect is a known
under-statement of the true one. Report the naive estimate and a
misclassification-corrected estimate (matrix method) as a range.

**(e) Optional — latent-class true labels.** A Dawid–Skene / MACE model estimates
each judge's sensitivity and specificity and a posterior "true" label per
response. Worth doing only if the panel disagrees substantially (α < ~0.6);
otherwise majority vote and the latent estimate coincide and it adds complexity
for nothing. **Flagged as optional, not baseline.**

### 4.4 What is *not* worth doing

- **Sampling for IRR.** At Tier 1 prices, annotating all English responses with
  all four judges costs ~$44. Designing, drawing and defending a stratified IRR
  subsample would cost more analyst time than the compute it saves, and it would
  make (a)–(d) above weaker by restricting them to a subsample. **Annotate
  everything in the tier; do not subsample within it.** The existing
  `--pass23-subsample` machinery stays for cost control across *tiers*, not
  within one.
- **Adding a fifth or sixth judge.** α gains little past four raters, and each
  extra judge multiplies the whole cost.
- **Judge as a random effect** in the main models. Four groups is far too few to
  estimate a variance component; per-judge refits (a) are the correct approach.

---

## 5. Pipeline integration

Design principle: **the existing contract must not change.** `01_data_loading.R`
and scripts `02`–`30` continue to read `annotations_all.jsonl` produced by the
anchor judge, so nothing downstream breaks. The panel is strictly **additive**.

### 5.1 Schema (Gap 1 — do this first)

Add to every annotation record:

| field | purpose |
|---|---|
| `judge_model` | which judge produced this verdict |
| `judge_pass` | 1 / 2 / 3 (for per-pass failure accounting) |
| `annotation_run_id` | ties a verdict to a panel run |
| `judge_prompt_version` | guards against comparing verdicts made under different templates |

`judge_prompt_version` matters: if the codebook is edited between judges, α
measures template drift rather than rater disagreement.

### 5.2 File layout

```
annotations/<run_id>/
  ann/<battery>_<lang>.jsonl              anchor judge (UNCHANGED)
  annotations_all.jsonl                   anchor judge (UNCHANGED contract)
  panel/<judge_slug>/<battery>_<lang>.jsonl    one dir per judge
  annotations_panel.jsonl                 LONG format: one row per (response × judge)
```

`annotations_panel.jsonl` is the single new surface the R layer reads.

### 5.3 Script changes

| file | change |
|---|---|
| `scripts/annotation_pipeline.py` | write `judge_model` etc.; `--judge-model` already exists |
| `scripts/run_pilot.py` | new `--judge-panel a,b,c`; loop the annotate stage per judge into `panel/<slug>/`; extend the dry-run budget model to price the panel |
| `scripts/run_pilot.py` (assemble) | additionally emit `annotations_panel.jsonl`; leave `annotations_all.jsonl` untouched |
| `scripts/sample_for_second_judge.py` | **delete** — v1-era and superseded by panel mode |
| `pipeline/01_data_loading.R` | optional loader for the panel file behind a guard; no change to `data_clean` |
| `pipeline/16_irr_analysis.R` | **rewrite** for k raters (α + AC1 + agreement, all constructs incl. moral foundations), or retire in favour of the new script below |
| `pipeline/24_measurement.R` | **new** — reliability (§4.1–4.2) → `e23`–`e25`; robustness (§4.3) → `e26`–`e28` |
| `pipeline/30_figures.R` | new `FIG5_measurement_main.png`: (A) per-judge replication forest, (B) reliability by construct, (C) differential-error test |
| `pipeline/audit_figures.R` | register FIG5 + panels; add a check that reliability figures always show n and the judge count |
| `pipeline/run_all.R` | register `24` |

R package additions: `irrCAC` (Gwet's AC1) alongside the existing `irr`.

### 5.4 Reruns and idempotency

Panel annotation must reuse the existing resume predicate (a row counts as done
only if it has a verdict and no error), keyed on
`(prompt_id, prompt_language, model, judge_model)`. This makes the panel
restartable and lets judges be added incrementally — the same property that makes
the current pipeline safe to stop and resume.

---

## 6. Sequence

| step | action | cost | gate |
|---|---|---|---|
| 1 | Schema fields + panel file layout + `run_pilot --judge-panel` | $0 | dry-run prints a correct panel budget |
| 2 | Rewrite `16` → `24_measurement.R` (k-rater) | $0 | runs and skips cleanly with no panel present |
| 3 | **Pilot**: 13 issues × 5 langs × 4 judges × 3 passes | **~$5** | §3 gates |
| 4 | Review pilot α, AC1, differential-error test | $0 | **decision point** |
| 5 | **Tier 1**: full English panel | **~$44** | parse failures < 2% |
| 6 | Re-estimate; add FIG5; update captions and docs | $0 | `audit_figures.R` passes |
| 7 | Tier 2 (zh + ar) if the language analyses need it | +$85 | optional |
| 8 | Tier 3 (ru + hi) once generation completes | +$90 | optional |

**Total to a fully defensible English result: ~$50.**

---

## 7. Risks and how the plan handles them

| risk | handling |
|---|---|
| Judge/subject family conflict → self-preference | panel chosen with zero conflicts; conflicted judges' verdicts on siblings reported separately if used |
| Prevalence paradox makes α look catastrophic | AC1 + positive specific agreement reported alongside |
| A judge cannot emit the schema | pilot gate at 2% parse failure; named substitutes ready |
| Template drift between judges | `judge_prompt_version` recorded; α refuses to compare across versions |
| Differential error inflates the China result | explicit test (§4.3c), run on the pilot before any spend |
| Chinese tokenizes heavier than the 3.6 ch/tok model | zh is Tier 2; re-calibrate cost from Tier 1 actuals first |
| Panel disagrees so much the construct is unusable | that is itself the finding, and the pilot surfaces it for $5 |

## 8. What this buys

At ~$50 for English, the study moves from *"single LLM judge, no reliability
estimate — the principal measurement limitation"* to a quantified error model
with per-judge replication of every headline estimate. That is currently the
largest open weakness in the paper, and it is the cheapest of the remaining
things to fix.
