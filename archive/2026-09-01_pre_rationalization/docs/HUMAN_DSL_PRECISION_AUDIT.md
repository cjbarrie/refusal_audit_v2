# Human-label precision audit for the candidate paper results

**Status (2026-08-25): complete local planning audit. No provider call was
made, the 123 protected evaluation labels remained sealed, and no additional
human annotation is currently authorized.**

## Why this audit was run

The previous workflow asked whether a protected test set contained enough
refusals to measure a stand-alone classifier's recall. That is useful if the
paper needs to certify and deploy a new annotation model, but it is not the same
question as whether the existing human probability sample can support the
paper's estimates.

This audit asks the estimand-specific question directly: for each refusal-
dependent analysis already implemented in `pipeline/17_response_validity.R`,
how much uncertainty comes from having human labels for 300 probability-sampled
responses rather than all 137,186 responses? The answer determines whether more
human coding would materially improve a main result.

## Inputs and roles

| Input | Rows | Role |
|---|---:|---|
| Frozen delivered-response population | 137,186 | Population over which every estimand is evaluated |
| Original human probability sample | 300 | The only labels used for population residual correction and design variance |
| Exposed enrichment development cases | 161 | Train one local diagnostic predictor only |
| Enrichment evaluation reserve | 123 | Remains sealed; no row or outcome is read |
| Frozen Sol wall-to-wall probabilities | 137,186 | Pre-human planning predictor used to assess attainable precision |

The 400-row enrichment wave is not pooled with the original 300. Its adaptive
selection makes raw pooling inappropriate, and its protected cases retain their
evaluation role.

## Exact estimator

Every current response-validity result can be written as a weighted sum of the
unknown human outcome:

```text
theta = sum_i a_i Y_i
```

The coefficient `a_i` is fixed by the estimand. For prevalence it is
`1/137186`; for a paired language difference it is positive for the target-
language response and negative for its English partner; for standardized home
it is the exact coefficient implied by the Stage-17 linear moment equation and
g-computation target.

For human label `Y_i`, fixed prediction `m_i`, sample indicator `R_i`, and
known inclusion probability `pi_i`, the audited estimator is:

```text
theta_hat = sum_i a_i m_i
          + sum_i R_i a_i (Y_i - m_i) / pi_i
```

The second term estimates and removes prediction error. The audit reconstructs
the exact pairwise inclusion probabilities of the pilot's union of three
without-replacement samples and applies the corresponding Horvitz--Thompson
variance to the residual term. This variance is conditional on the frozen
137,186-response population: it isolates uncertainty due to human-label
sampling. The final paper analysis must additionally propagate issue-level
uncertainty and prediction-fitting uncertainty.

The planning thresholds are deliberately practical, not inferential acceptance
rules: 2 percentage points for overall prevalence, 3 points for pooled paired
language and framing contrasts, 5 points for jurisdiction-specific standardized
home estimates, and 8 points for exploratory model-level cells. A narrow
estimated interval is not called adequate when the human sample contains too
few outcome events in the relevant positive and negative arms.

## Results that the current 300 support

Using the frozen Sol probabilities as the pre-human planning predictor:

| Candidate main result | Human-corrected planning estimate | Human-sampling 95% half-width | Human event support | Assessment |
|---|---:|---:|---:|---|
| Overall genuine refusal | 2.27% | 0.81 pp | 14 | Adequate for the next local Stage-18 implementation |
| Arabic minus English genuine refusal | -1.97 pp | 2.19 pp | 5 total; 2 target, 3 English | Adequate but still rare-event sensitive |
| Hindi minus English genuine refusal | -3.62 pp | 2.95 pp | 6 total; 3 target, 3 English | Adequate but still rare-event sensitive |
| Russian minus English genuine refusal | -3.02 pp | 2.86 pp | 5 total; 2 target, 3 English | Adequate but still rare-event sensitive |
| Chinese minus English genuine refusal | -0.75 pp | 2.25 pp | 7 total; 4 target, 3 English | Adequate but still rare-event sensitive |
| Overall capability failure | 19.39% | 2.67 pp | 67 | Close to the 2-pp planning target; no urgent new coding |

These are planning calculations, not canonical paper estimates. Their purpose
is to decide whether more labels are needed before building the full inference
stage. In particular, they do not yet include whole-issue uncertainty.

## Results that are not supported well enough

### Standardized home

The original 300 contain no human-confirmed genuine refusal contributing to the
CN, EU, or India standardized home estimates, one for MENA, and two for the US.
Some residual-correction standard errors are numerically narrow because the
fixed predictor varies smoothly and the sampled residuals happen to be small.
Those intervals are not credible evidence of adequate rare-event support. The
support rule correctly fails all five jurisdiction-specific home estimates.

This is the central finding of the audit: **a larger general-purpose human
sample is not needed, but the home analysis cannot yet be promoted as a
human-validated headline finding.** If home remains central, the next human
sample should be designed specifically around English jurisdiction × home/away
arms and should include both a universal random component and refusal-risk
enrichment with known inclusion probabilities.

### Framing and capability-failure language contrasts

The pooled framing estimate has only three human refusals across its two arms
and a 3.91-pp half-width. Capability-failure language contrasts have many
target-language events but only one English-arm event in each contrast, giving
half-widths of 5.89--9.37 pp. These results may remain clearly labelled
exploratory or sensitivity analyses without triggering more coding. They should
drive a targeted sample only if they are retained as main paper claims.

### Model-specific cells

Model × language prevalence and model-specific language, home, and framing
results are diagnostics or exploratory heterogeneity. Sparse cells are not a
reason to expand the human workload unless a specific cell is promoted in
advance to a main estimand.

### Slant and moral foundations

These are not refusal outcomes, so they do not enter the coefficient audit
above. They are currently measured only among responses the original judge
treated as engaged. Human response-validity correction can show that some
excluded responses were actually coherent answers, but it cannot manufacture
the missing slant or moral-foundation annotations for those responses.

Stage 18 should therefore report how the human validity classes intersect the
existing content-analysis denominator and provide a competence-conditioned
selection diagnostic. The canonical slant and moral estimates should remain
explicitly conditional on the original engaged-and-annotated set unless the
newly recovered coherent answers receive the content passes themselves. More
response-validity coding alone does not solve that missing-content problem and
is not justified solely for these outcomes.

## Predictor comparison

The frozen Sol predictor had design-estimated Brier loss 0.0093 for genuine
refusal and 0.0702 for capability failure. A deliberately simple local logistic
model trained only on the 161 enriched development cases had losses 0.0289 and
0.0586 respectively and substantially overpredicted rare classes. It is kept as
a diagnostic, not selected for inference. This demonstrates why classifier
accuracy or an enriched-set class percentage cannot substitute for an
estimand-specific design audit.

No new low-cost surrogate is necessary to begin Stage 18: the existing frozen
Sol probability can serve as the efficiency model, while the probability-
sampled human residuals preserve design validity. A later surrogate can replace
it only after a separately frozen comparison shows a real precision or cost
benefit.

## Decision and next step

1. Stop general human annotation for now.
2. Implement a local provisional Stage 18 using the original 300 and the frozen
   Sol prediction, with issue-level uncertainty added to the exact human-sample
   correction.
3. Report direct human HT, prediction-only, and human-corrected estimates side
   by side; keep original non-engagement and Sol-reference results visibly
   separate.
4. After seeing the full Stage-18 intervals, decide which results are truly main
   paper estimands.
5. Only if standardized home, framing, or capability-failure language remains a
   main result, simulate a new estimand-targeted probability sample and request
   human coding for that design. Do not reopen a generic 400-row workload.
6. Complete the delayed within-coder repeats when they unlock; they inform a
   measurement sensitivity but need not block Stage 18.

## Reproduction

```bash
python scripts/response_validity.py audit-human-estimand-precision
```

Outputs are immutable under
`annotations/response_validity_human_v2/estimand_precision_audit_v1/`:

- `estimand_precision.csv`: every outcome, family, cell, predictor, direct and
  assisted estimate, exact human-sampling standard error, support counts, and
  planning decision;
- `predictor_diagnostics.csv`: design-estimated Brier loss and mean residual;
- `main_estimand_summary.csv`: compact family-level support summary;
- `audit_manifest.json`: hashes, row counts, estimator statement, and explicit
  confirmation that the sealed reserve and network were not used.
