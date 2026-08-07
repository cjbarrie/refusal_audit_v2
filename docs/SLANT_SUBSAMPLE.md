# The slant subsample — annotation passes 2 and 3 on 25% of issues

> **⚠ SCRIPT PATHS BELOW ARE OUT OF DATE — 2026-08-07.** The v1 estimand layer
> and the v2 layer were archived to `pipeline/archive/precanonical_v1|v2/`
> (`pipeline/archive/README.md` maps each file to its replacement), and the
> whole pipeline was then **renumbered**.
>
> **The old numbers have been reused and no longer mean what they say here.**
> `10`–`14` are now the canonical estimation layer, `20`–`21` the figure scripts,
> `40`–`44` the appendix analyses. Resolve any script reference below against
> `pipeline/archive/README.md`, never by number alone. The analyses the paper
> reports are specified in **`docs/CANONICAL_ANALYSES.md`**. This document is
> kept as a dated record of what was true when it was written.

**Status: APPLIED 2026-08-04; complete for the primary (English) sample, with a
top-up pending in Russian and Hindi** — see the generation-status section below.
Passes 2 (ideology) and 3 (moral foundations) have been run over a 25% issue
subsample of `annotations/full_v1`, in all five prompt languages. This document supersedes the Pass-1-only decision
recorded in `docs/ANNOTATION_TRIM_FULL_RUN.md` for the *slant* passes; the
reasoning there for why Pass 1 alone answers the study's primary question still
stands, and Pass 1 still runs on **100%** of responses.

---

## What was decided and why

The full run was originally annotated Pass-1-only: refusal (1/0) and the reason
for refusing come entirely from Pass 1, and the slant passes measure a different
thing — how a model leans *when it does answer*. Running passes 2/3 over the
whole run would have roughly tripled judge spend for a secondary question.

The subsample buys the secondary question back at a quarter of the cost. It is
sampled at the **issue** level, not the response level. That matters:

- Every model answers every issue, so responses are **clustered within issue**.
  Sampling responses independently would have broken the clustering the analysis
  depends on, and left ragged, unbalanced model × language × tier cells.
- Sampling whole issues keeps every cell **complete by design**: for a sampled
  issue, every response that exists is annotated, across both tiers — the
  subsample never splits an issue. (Coverage is currently limited by what
  *generation* has produced, not by the subsample; see below.)

Parameters are frozen in `annotations/full_v1/pass23_subsample.json`:

| | |
|---|---|
| Unit | `issue_id` |
| Fraction | 0.25 |
| Seed | 20260803 |
| Issues drawn | 156 |
| Languages | en, zh, ar, ru, hi (all five) |
| Rows carrying slant codes | 29,106 (92.5% of eligible engaged) |

The manifest is written once and **re-read** on every subsequent language and
every resume, so the same 156 issues are used throughout. Re-drawing per
language would have silently inflated the subsample toward 100% as languages
accumulated.

## Running it

Subsampling is a pipeline parameter, not a one-off script:

```bash
python scripts/run_pilot.py --run-id full_v1 --stages annotate --resume \
    --batteries rebalanced --all-passes \
    --pass23-subsample 0.25 --pass23-seed 20260803
```

- `--all-passes` opts into passes 2/3; without it the run stays Pass-1-only.
- `--pass23-subsample` defaults to `1.0` (no subsampling).
- If the manifest already exists it is **reused**, and the `--pass23-*` flags
  are ignored — this is what makes resume safe.
- Pass 1 is unaffected by these flags and always covers everything.

## What the R layer does with it

`pipeline/01_data_loading.R` reads the manifest and derives two columns:

| column | meaning |
|---|---|
| `slant_eligible` | the response's issue was in the 25% draw |
| `has_slant` | the response actually carries ideology codes |

They differ for a legitimate reason: passes 2/3 are **skipped for refusals by
design** (a refusal has no position to score). So `slant_eligible & !has_slant`
is almost entirely refused responses, not missing data. Every slant quantity is
therefore **conditional on engagement** — it describes how models lean when they
answer, never how often they answer.

If the manifest is absent, the loader falls back to detecting whether any
ideology column carries data, so a Pass-1-only run still loads cleanly.

## ~~Generation gap~~ — CLOSED 2026-08-05

**Resolved.** Generation and annotation are now complete for all 11 models in
all 5 languages (137,186 rows). The table below is kept as a record of the gap
that existed on 2026-08-04; every cell has since filled.

A caution worth carrying forward: this gap was twice mis-diagnosed from
`data_clean` alone. `data_clean` is built from *assembled annotations*, so a
language can look absent when the responses and annotations both exist and only
`--stages assemble` has not been re-run. **Re-assemble before diagnosing
coverage.**

| model | ar | en | ru | zh | hi |
|---|---|---|---|---|---|
| allam-7b | 2490 | 2495 | **150** | 2490 | **0** |
| falcon3-10b | 2490 | 2494 | **125** | 2484 | **0** |
| jais-8b | 2489 | 2492 | **149** | 2482 | **0** |
| sarvam-30b | **1643** | 2488 | **0** | 2483 | **0** |
| (7 OpenRouter models) | ~2485 | ~2495 | ~2494 | ~2490 | ~2484 |

Passes 2/3 annotate responses that **exist at the time they run**. When
generation completes, the sampled 156 issues will have new responses in ru/hi
(and ar for sarvam) that carry **no** slant codes. Re-run the annotate stage
with the same flags to fill them:

```bash
python scripts/run_pilot.py --run-id full_v1 --stages annotate --resume \
    --batteries rebalanced --all-passes --pass23-subsample 0.25
```

The manifest is reused, so **the same 156 issues** are topped up — the subsample
does not grow and the draw stays reproducible. Only the missing rows are judged;
already-annotated rows are skipped.

This does **not** affect the primary English tables, which are already complete
(11/11 models).

## Language restriction in the estimates

`pipeline/22_estimates_slant.R` reports its **primary tables in English only**.
The subject-model roster is not constant across prompt languages:

| language | models answering |
|---|---|
| en, zh, ar | 11 |
| ru | 9 |
| hi | 7 |

Pooling all five would confound a jurisdiction's measured slant with which of
its models happen to answer in which language — a composition artefact rather
than a finding. The language comparison (`e20`) is therefore restricted to
**en/zh/ar**, where the 11-model roster is held fixed.

## What it produced

Estimates in `pipeline/estimates/`:

| table | contents |
|---|---|
| `e15_ideology_distribution.csv` | share at each code −2..+2, by jurisdiction × dimension |
| `e16_ideology_means.csv` | mean ideological position, issue-clustered 95% CI |
| `e17_moral_prevalence.csv` | share invoking each foundation, by jurisdiction |
| `e18_moral_by_model.csv` | the same by model |
| `e19_slant_coverage.csv` | sample sizes and subsample parameters |
| `e20_moral_by_language.csv` | foundations by prompt language, fixed roster |

Figures: `FIG4_slant_main.png`, plus `P9_ideology.png`,
`P10_moral_foundations.png`, `P11_moral_by_language.png`.

## The headline: ideology is close to null, moral framing is not

The judge codes **74–93% of engaged responses as exactly 0** on every ideology
dimension (English, the primary sample). Jurisdiction means span roughly +0.03 to −0.16 on a −2..+2 scale.
Read this as a **measurement result**, not a null to be explained away: on this
battery, the models overwhelmingly do not take an ideological side when they
answer, and where they do the tails are small. The largest signals are US models
leaning marginally economically right (+0.032 [0.016, 0.048]) and EU models
leaning progressive (−0.119 [−0.163, −0.074]) and populist (−0.162).

Moral foundations carry far more variance and are where the interesting
variation sits: fairness/cheating is invoked in 58–71% of engaged responses,
sanctity/degradation in under 4%. EU models invoke care, fairness and liberty
most; CN models lead on loyalty and authority. Prompt language moves these
shares only slightly and the intervals largely overlap (`e20`).

## Caveats

- Single LLM judge (`google/gemini-2.5-flash-lite`, temperature 0), **no
  second-judge pass and no inter-rater reliability**. Inherited by every
  quantity here, and more consequential for slant than for refusal: ideology
  coding is a harder judgement than "did it refuse".
- Conditional on engagement, so slant and refusal are **not** directly
  comparable across jurisdictions with different refusal rates.
- 156 issues, so jurisdiction × dimension cells are modest; intervals are
  issue-clustered bootstrap and are correspondingly wide.
