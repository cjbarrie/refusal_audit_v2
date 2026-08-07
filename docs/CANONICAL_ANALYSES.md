# Canonical analyses

**This document is the specification for the analyses the paper reports.** If a
number appears in the manuscript, it comes from `pipeline/estimates/canonical/`
and is described here. Everything else — the `e`-series, the `d`-series, `FIG1`–`FIG5`,
`FIGA`–`FIGC` — is superseded provenance, catalogued in
[`ESTIMANDS.md`](ESTIMANDS.md) and archived under `pipeline/archive/` with a
file-by-file mapping in [`pipeline/archive/README.md`](../pipeline/archive/README.md).

Run it:

```bash
CANONICAL_RUN_ID=canon_003 Rscript pipeline/run_canonical.R
```

Nothing in this layer calls an API, and nothing it does mutates prompts,
responses, annotations, sampling files, or `data_clean.RData`. It writes only to
`pipeline/estimates/canonical/` and `pipeline/figures/canonical/`.

---

## 1. What the design can and cannot support

The analysis sample is **137,186 responses**: 11 models × 624 issues × 5
languages × 2 prompt tiers, one row per (model, prompt, language), minus the
cells no model returned. English alone is 27,449 rows.

Three features of the design determine every estimand below.

**Issues are the sampling unit, not prompts.** Each issue generates a regular and
a boundary prompt, and each prompt goes to every model in every language. A
prompt-level or response-level standard error would treat those as independent
and be far too small. Every interval in this layer is an **issue-cluster
bootstrap** percentile interval.

**Home status is a property of the issue-model pair, not a treatment.** A model
is "at home" on an issue when the issue's region matches the model's
jurisdiction. Nobody randomised which issues are Chinese issues. Home and away
issues differ in topic, contentiousness, and seed route, so a raw home–away gap
mixes the model's behaviour with the composition of the issue set. This is why
Part 1 reports *two* quantities and never collapses them into one.

**General issues are held out of both arms.** 22,868 rows concern issues with no
regional focus. They are neither home nor away for anyone, and folding them into
"away" would silently define every model's away set differently. They sit at
`home_status == "general"` and are reported separately.

**What is not identified.** Jurisdiction is a property of the model roster —
the CN jurisdiction *is* DeepSeek and Qwen. There is no design that separates "a
Chinese model" from "these two Chinese models", so every jurisdiction-level
statement is a statement about the models tested, not about jurisdictions as
populations. The canonical tables carry this in a `jurisdiction_caveat` field
rather than in a footnote.

---

## 2. Part 1 — home-jurisdiction asymmetry (`c02`–`c07`)

**Question.** Do models refuse more on issues concerning their own jurisdiction?

Two estimands. They answer different questions and neither is a check on the
other, so they are reported separately: the standardized contrast is the primary
quantity and carries the main figure, and the descriptive rates are reported in
`c02` and plotted in appendix S1. They were shown side by side in one figure
until it became clear that the layout itself invited the wrong reading — that
these are two attempts at one number, with the "adjusted" one to be preferred.

### 2a. Descriptive (`c02`, `c03`)

The observed refusal rate on home issues minus the observed rate on away issues,
in English, with no adjustment. This is a *fact about the corpus*: it is what you
would see if you read the responses. It is confounded with issue composition by
construction, and that is not a flaw — it is the quantity a reader wants when
asking "what does this corpus look like?"

Reported at `weighting = "response"` (every response counts once) and
`weighting = "equal_model"` (every model counts once). `c03` repeats it in all
five languages as a supplement. Plotted in **S1**, not in the main figure.

### 2b. Covariate-standardized (`c04`–`c07`) — the primary estimand

A logistic regression per jurisdiction:

```
refused_strict ~ home * model + tier + topic_domain + route
```

then **g-computation on the probability scale**: predict every observation as if
home, predict every observation as if away, take the weighted difference of the
two averages. The `home * model` interaction is used when a jurisdiction has more
than one model, so the contrast is not forced to be common across models; with a
single model it reduces to `home + ...`.

The weights are **nested**: equal mass per model, then equal per issue within
model, then equal per prompt within model×issue. Without this, a model that
returned more responses, or an issue that generated more prompts, would pull the
average. The acceptance tests verify the weights are doing work by constructing
an imbalanced roster and confirming the weighted answer moves while the
unweighted one does not (test B4); on the *real* English home arm the design is
exactly balanced at 104 issues per model, so weighted and unweighted coincide
exactly, and test B5 asserts that too, so the coincidence is documented rather
than mistaken for a bug.

**Region fixed effects are deliberately excluded.** Region determines home status
within a jurisdiction — for the CN models, "issue is Chinese" and "issue is home"
are the same event. Including region FE, as the v1 analysis did, absorbs the
contrast being estimated.

**What you may infer.** A covariate-standardized contrast: the home–away
difference that would remain if home and away issue sets had the same tier,
domain and route composition. **It is not a causal effect**, not a
difference-in-differences, and not a within-issue effect. Standardization
adjusts for the composition that was measured; it cannot adjust for the ways
home issues differ from away issues that nobody recorded. Every row of `c04`
carries this sentence in `causal_interpretation`.

**Structural zeros.** The EU jurisdiction (Mistral) produced zero refusals in
both arms, so the contrast does not exist. It is reported with
`estimable = FALSE` and a reason, never as `0.000` and never dropped — a dropped
row would read as "no data", which is the opposite of what happened.

**Sensitivities (`c07`).** Leave-one-model-out, tier-restricted, per-language,
`engagement_code >= 3` instead of `>= 4`, minimum-response-length filters,
overlap-restricted (only strata with both arms present, per `c06`), and a
hierarchical GLMM whose marginal predictions are integrated over the random-effect
distribution by 40-point Gauss–Hermite quadrature rather than plug-in at zero.

---

## 3. Part 2 — language and framing (`c08`–`c11`)

**Question.** Does the *language of the prompt* change refusal? Does the
*framing* of the prompt?

Both are answered by **paired within-block differences**, which is what makes
them the strongest designs in the paper: prompt content is held fixed by
construction rather than adjusted for.

### 3a. Language (`c08`, `c09`)

Block = model × prompt_id. Within a block, the same prompt in the same model is
observed in English and in the target language; the estimand is the mean paired
difference. All four non-English languages are estimated — Chinese, Arabic,
Hindi, Russian — **including the ones whose intervals cover zero**. Reporting
only the language that "worked" would be selection on the outcome.

Three weightings are reported (pooled, equal-per-model, equal-per-model-issue).
They agree closely here because the design is balanced; showing all three is how
the reader knows that.

**What you may infer.** The effect of delivering *the tested translation* of the
prompt, among the tested prompt and model set. **It is not the causal effect of
a user's language.** It assumes translation equivalence, and that nothing else
travels with language — provider routing, run-time, judge behaviour on non-English
text. Those assumptions are stated in the `interpretation` column, not buried.

Incomplete blocks are counted (`n_missing_blocks`) rather than dropped silently.

### 3b. Framing (`c10`, `c11`)

Block = issue × model × language. Within a block, the regular and boundary
prompts for the same issue are compared. The pooled effect is near zero with an
interval covering zero; the by-model table shows this is not "no effect
anywhere" — individual models move in opposite directions and cancel. This is
exactly why `c11` exists.

**What you may infer.** A paired boundary-minus-regular difference. A causal
reading requires the regular and boundary variants of an issue to be
exchangeable given the issue — an assumption about the *generation template*,
not a randomisation.

---

## 4. Part 3 — content of engaged responses (`c12`–`c16`)

**Everything in this part is conditional on engagement.** The judge skips the
ideology and moral-foundation passes for refusals, so the denominator is engaged
responses. These tables say nothing about what a refused response would have
contained, and since refusal itself varies by model and jurisdiction, the
conditioning is not ignorable. Every table carries a `conditional` field saying
so.

### 4a. Ideology (`c12`, `c13`)

The primary estimand is the **full distribution over −2..+2**, not the signed
mean. A mean of a five-point scale where ~80–92% of mass sits at zero is
dominated by the neutral share and hides which side the non-neutral responses
fall on. The signed mean is reported as secondary.

**Reliability is weak and this is stated in the table, not just here.** Panel
Krippendorff's α by dimension is roughly: economic 0.41, social 0.30, authority
0.24, populism 0.14. Social, authority and populism should not carry substantive
weight. The `reliability_warning` column is non-empty on every row, and
acceptance test E4 fails the build if it is ever emptied.

**Coverage (`c12b`).** English slant coding is complete: 6,528 of 6,528 eligible
engaged boundary responses. The other languages are not — Chinese 98.9%, Arabic
95.4%, Russian 68.3% — so **only English is used canonically**, and the partial
languages are marked `EXCLUDED: incomplete coverage`. A 68%-covered language
would otherwise contribute a selected subsample.

**Two intervals per estimate.** The primary interval targets an issue
*superpopulation* (what would another draw of issues look like). The
finite-battery interval applies the finite population correction
√(1 − 156/624) = 0.866, because the slant subsample is 156 of the 624 issues in
the frozen battery, and if the battery itself is the population of interest the
superpopulation interval is too wide. Both are reported; neither is hidden.

### 4b. Moral foundations (`c14`–`c16`)

Six **non-exclusive binary indicators** — a response can invoke care and fairness
and neither loyalty nor sanctity. They do not form a composition and must never
be plotted as shares of a whole. Prevalence is reported equal-weighted per model,
always with an interval.

Each foundation carries its own judge-agreement statistics, and a
`low_agreement_flag` set from **positive specific agreement**, not from α or raw
agreement. At the prevalence of sanctity (~3%), raw agreement is ~97% while the
judges essentially never agree on a positive case — the kappa paradox. Under the
current panel, care and fairness clear the bar; liberty, authority, loyalty and
sanctity do not, and are drawn hollow in FIG3b.

`c16` reports joint outcomes — refusal, engaged-with-foundation,
engaged-without-foundation — with **refusal as its own category**. Collapsing
refusals into "foundation absent" would let a model that refuses more look like a
model that moralises less.

---

## 5. Part 4 — measurement and multiple judges (`c17`)

Every response is labelled by more than one judge. The canonical outcome is a
single named judge — **`google/gemini-2.5-flash-lite`** — and the others are a
**sensitivity dimension**, reported separately.

### 5a. Why there is no majority vote

A consensus label would require a reason to believe the majority is right. No
human-validated labels exist for this corpus, so no such reason exists. Worse, a
majority label would *conceal* the disagreement that `c17` is there to expose: if
three judges systematically under-detect refusal, the majority inherits the bias
and reports it with more confidence than any single judge would.

The panel is therefore used to answer one question — **how much does the
conclusion depend on the instrument?** — and `c17` recomputes the headline
quantities under each judge separately.

### 5b. Two kinds of uncertainty, kept apart

A bootstrap interval under one judge answers: *if we drew another sample of
issues and kept this instrument, how much would the estimate move?* It holds the
instrument fixed, so it says nothing about the labels being wrong.

Refitting the **same specification** under each judge adds the second question:
*if we kept this sample of issues and swapped the instrument, how much would the
estimate move?* `c17b` does exactly that for the primary quantity — the
covariate-standardized home−away contrast — using the shared `gcomp()` from
`10_canonical_common.R`, so a difference between judges cannot be a difference
in model.

The reported **envelope** is the union of the per-judge intervals,
[min_j low_j, max_j high_j], widened to contain the canonical `c04` interval.
It is a **sensitivity bound, not a confidence interval**, and `interval_type`
says so on every row. It has no coverage guarantee: four judges chosen for cost
and speed are not a sample from a population of judges, and none of them is
known to be correct. It would be conservative only under an assumption this
project does **not** make — that the true labelling is one of the four. Quoted
as a bound it is honest; quoted as a 95% interval it would be a fabrication.
It is never pooled with a bootstrap interval and never added in quadrature.

`c17b` reports two distinct claims, and conflating them would overstate the
result:

| column | claim |
|---|---|
| `point_sign_stable` | every judge agrees on the direction |
| `envelope_excludes_zero` | the union of their intervals clears zero — strictly stronger |

Under the current panel the headline reads: **CN's envelope clears zero; India's
direction is agreed by every judge but its envelope touches zero; MENA and US
are judge-dependent.** Overall English refusal is 5.14% under the canonical
judge and 2.97–4.43% under the others, so **the sign and ordering of the
findings are stable across judges while the magnitudes are not**. Claims should
be written to survive that: "Chinese models refuse substantially more on home
issues" is supported; "Chinese models refuse 16 percentage points more" is a
statement about the Gemini labels specifically.

Judge coverage is English-only, so judge-specific versions of the *language*
estimands do not exist. `c17` says so rather than omitting the rows.

`S2_judge_multiverse.png` plots this: each judge's estimate and interval per
jurisdiction, with the envelope as a shaded band.

### 5c. The disabled annotation-error layer

`draw_latent_labels()` in `10_canonical_common.R` implements the standard
misclassification correction — given sensitivity, specificity and stratum
prevalence, redraw latent labels and propagate. **It is disabled by a `stop()`
and will not run.** An earlier draft of it also had the prevalence term wrong,
applying a marginal rather than stratum-specific prior, which is precisely the
failure mode that makes such corrections dangerous: they produce confident
numbers from assumed inputs. It stays disabled until real validation data exists.

### 5d. Planned: design-based supervised validation

The principled fix is a validation subsample with gold-standard labels, which
does not yet exist. The intended design, for a later stage:

1. **Sample by design, not convenience.** Draw a stratified probability sample of
   responses — stratified on model, jurisdiction, language, tier and the
   canonical judge's own label, with the rare cells (refusals, non-neutral
   ideology, rare foundations) deliberately oversampled — and record the
   inclusion probability of every sampled unit. Design-based estimation needs
   known π, which convenience sampling destroys.
2. **Gold labels from a frontier model, with human adjudication on a subset.**
   A frontier model produces the reference labels; a human adjudicates a
   sub-subsample to estimate the *gold* standard's own error rate. Treating
   frontier-model labels as error-free would move the problem rather than solve
   it.
3. **Estimate the confusion matrix per stratum**, not marginally. Sensitivity and
   specificity plausibly differ by language and by model — a judge may miss
   refusals in Arabic that it catches in English — and a marginal correction
   applied to a stratum with different error rates makes bias worse.
4. **Propagate through the existing estimators.** Either Rubin-style multiple
   imputation of latent labels within the issue-cluster bootstrap, or a
   measurement-error-corrected estimating equation. Corrected estimates would sit
   *alongside* the canonical ones as `c19+`, never replacing them, so the effect
   of the correction is visible.
5. **Report the correction's own uncertainty.** A corrected point estimate with an
   interval that ignores uncertainty in the confusion matrix is worse than no
   correction at all.

Until steps 1–3 exist, the honest position is the current one: one named judge,
a stated instrument-sensitivity range, and no correction.

---

## 6. Figures

Main-manuscript figures in `pipeline/figures/canonical/`, appendix figures in
`pipeline/figures/appendix/`. All 600 dpi PNG, two-column width, white
background — the repo-wide PNG-only rule applies, and `audit_figures.R` fails on
a missing expected figure *or* a stale extra one.

| Figure | Panels | Source tables |
|---|---|---|
| `FIG1_canonical_home.png` | a locator map; b standardized contrast with judge envelope; c refusal text in semantic space by stated reason | `c04`, `c17b`, `u01` |
| `FIG2_canonical_language_framing.png` | a paired language effects, four languages × three weightings; b by model; c framing by model, ordered by effect | `c08`–`c11` |
| `FIG3_canonical_content.png` | a ideology distribution; b moral-foundation prevalence | `c12`, `c14` |
| `S1_home_descriptive.png` | descriptive home/away rates | `c02` |
| `S2_judge_multiverse.png` | the contrast under each judge, with the envelope | `c17b` |
| `S3_specification_curve.png` | every sensitivity family, one row each | `c07`, `c04` |
| `S4_projection_supplement.png` | all five languages; the same refusals lexically | `u02`, `u03` |

**FIG1 carries the standardized contrast only.** The descriptive rates are still
estimated and reported (`c02`) but are now an appendix figure: printing both in
the main figure invited the reading that they are two estimates of one
parameter, when they are two different estimands answering different questions.

The figure scripts **read the canonical CSVs and never recompute an estimate**,
so every plotted value is traceable to a table row — which is what lets
`audit_figures.R` check figure/table agreement mechanically, including the
requirement that the judge envelope in FIG1b contains the interval drawn inside
it.

## 6b. Refusal-text projection (diagnostic, not an estimand)

`scripts/refusal_umap.py` → `u01` (English, semantic), `u02` (all five
languages, semantic), `u03` (English, lexical), drawn in FIG1c and S4.

Every refusal's text is embedded with a **local sentence-transformer**
(`paraphrase-multilingual-MiniLM-L12-v2`, no API call, one encoder for every
language so the panels are comparable), then projected with UMAP and coloured by
the judge's justification code. Only the opening 800 characters are embedded:
the stated reason comes first, and letting a 1,400-character response dominate
its own embedding buries the justification.

The question is prior to any estimand: **do refusals given for different stated
reasons actually differ?** The A–G codes have the weakest inter-judge agreement
of any construct here, which is why no canonical estimand rests on them (§9).

What it shows: reason groups occupy distinguishable regions but overlap heavily.
Among each point's 15 nearest neighbours, the share sharing its reason group is

| representation | purity | at random |
|---|---|---|
| semantic, English | 0.53 | 0.44 |
| lexical (TF-IDF), English | 0.58 | 0.44 |
| semantic, all five languages | 0.44 | 0.35 |

**The codes track wording more closely than meaning** — the lexical
representation separates them better than the semantic one. That is a finding
about the taxonomy, not a defect in the projection, and it is one more reason
the A–G codes carry no estimand.

A UMAP layout has **no units**: cluster sizes and between-cluster gaps carry no
meaning, only local distances are faithful. That is why the axes are unlabelled
and a neighbourhood-purity statistic is quoted instead of a visual impression.

This is a measurement diagnostic. **No estimate in the paper derives from it.**

## 6c. How this maps onto the manuscript

The script numbering follows the shape of the paper, so it is obvious where a
result belongs:

| range | role | what it produces |
|---|---|---|
| `01`–`02` | inputs | `data_clean.RData`; judge-panel reliability |
| `10`–`14` | estimation | `c00`–`c18` — one script per estimand family |
| `20` | **main manuscript** | `FIG1`–`FIG3` and the tables they read |
| `21` | **appendix** | `S1`–`S4` |
| `30` | tests | `c01b`, 38 acceptance criteria |
| `40`–`44` | appendix analyses | descriptive tabulations, DeepSeek case study |

**Main text** carries one estimate per question: the standardized home contrast
(FIG1b), the paired language and framing effects (FIG2), and the content of
engaged responses (FIG3). **Appendix** carries what a referee will ask for: the
descriptive rates the main figure no longer shows (S1), the instrument
sensitivity (S2), the full specification curve (S3), and the projection
supplement (S4), plus the `40`–`44` tabulations.

The three DeepSeek scripts (`42`–`44`) were left as separate files rather than
merged. They write disjoint tables and each is a working analysis; concatenating
them would have risked live results for a cosmetic gain. The grouping is
expressed in the numbering and in `run_all.R`, which is what a reader needs.

## 7. Table index

| File | Contents |
|---|---|
| `c00_manifest.csv` | every output file, row count, run id, git commit, R version |
| `c00_timings.csv` | per-step wall clock |
| `c01_reconciliation.csv` | canonical vs v2 vs v1 headline numbers, with the reason each differs |
| `c01b_acceptance_tests.csv` | every acceptance test and its result |
| `c02`, `c03` | descriptive home/away rates (English; all languages) |
| `c04` | standardized home−away contrast — **primary** |
| `c05` | by model |
| `c06` | overlap / positivity diagnostics |
| `c07` | sensitivities |
| `c08`, `c09` | paired language effects (overall; by model) |
| `c10`, `c11` | paired framing effects (overall; by model and domain) |
| `c12`, `c12b`, `c13` | ideology distribution, slant coverage, by model |
| `c14`, `c15` | moral-foundation prevalence (equal-model; by model) |
| `c16` | joint outcomes with refusal as its own category |
| `c17` | measurement sensitivity across judges |
| `c17b` | the standardized contrast refit under each judge, plus the envelope |
| `c18` | bootstrap diagnostics — seed, replicates requested/successful/failed per quantity |

---

## 8. Acceptance criteria

`30_acceptance.R` runs 38 tests and exits non-zero on any failure. They
are adversarial where it matters:

- **Weighting** is checked against a *constructed imbalance* (B3, B4), because on
  a balanced design a weighting check passes trivially.
- **Bootstrap multiplicity** is checked against a synthetic three-issue
  counter-case (C2). Two issues are not enough — with two, every resample gives
  the same answer under both keyings, so a two-issue test would pass against a
  broken bootstrap.
- **A test whose condition returns `logical(0)` or `NA` fails.** An earlier
  version let those become zero-row results, and the test vanished from the
  report entirely. Silently passing by disappearing is the worst behaviour a
  check can have.
- **Claim discipline** (E1) scans every character column for causal language and
  flags it unless a negation appears within the surrounding window.
- **Provenance** (D1, D1b) requires every estimate table to carry exactly one
  `canonical_run_id`, and all of them to agree — a canonical release is one run.
  `c18` is exempt because it deliberately accumulates history.
- **Diagnostic completeness** (C3c) requires `c18` to hold rows from every part
  that bootstraps. This exists because `flush_diag()` used to drop the whole
  current run before appending, so each part silently wiped the previous part's
  diagnostics and `c18` ended up holding only the last part's.

---

## 9. Known gaps

- **`annotations_panel.jsonl` is stale** relative to the current run and needs
  re-assembly; `c17` uses what is on disk now.
- **Slant top-up (~5,200 rows)** would complete Chinese and Arabic coverage and
  let Part 3 report more than English.
- **Pass 4 stance coding** is not part of the canonical layer; whether it becomes
  a canonical outcome is undecided.
- **`e20_moral_by_language.csv`** is retired as unsound (unpaired, with
  language-varying denominators); no canonical replacement has been run.
- **Refusal-justification codes (A–G)** have no canonical estimand — inter-judge
  agreement was too weak to support a prevalence claim. Retained as description
  only in `06_refusal_justifications.R`.
