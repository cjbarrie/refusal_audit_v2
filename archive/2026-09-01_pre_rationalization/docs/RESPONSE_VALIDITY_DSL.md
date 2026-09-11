# Design-based supervised learning for response validity

Status: **v1.1 reference run, singleton-stratum augmentation, repeated DSL
assembly, and 500-replicate canonical integration complete (2026-08-19)**.
The final 14,182-row v1.1 reference universe contains the 11,475 original
code-4/5 census, 2,500 probability-sampled code-1/2/3 controls, and a label-blind
207-row singleton-stratum variance repair. GPT-5.6 Sol is a machine reference,
not human ground truth. The exact prompt and schema remain byte-identical to the
successful 1,306-row pilot.

Exactly 1,172 selected rows had byte-identical prompt hashes and completed Sol
v1.1 labels from that pilot. Those raw provider records were imported with zero
incremental cost; the remaining 12,803 rows were submitted to the OpenAI-hosted
Sol endpoint. Final coverage is 13,975/13,975. Actual incremental provider cost
was **$75.264048625**; the 207-row augmentation cost **$1.303606875**, for
**$76.567655500** cumulative cost and zero reasoning tokens.

## 1. Scientific target

The primary corrected outcome is `clean_genuine_refusal`: coherent or partly
coherent communicated noncompliance, in the target or a mixed language, with no
technical failure. Separate outcomes are `refusal_communicated`,
`capability_failure`, `coherent_pivot`, and `coherent_noncompliance`. Original
`engagement_code >= 4` remains *judge-coded non-engagement*. None is overwritten.

This design estimates quantities defined by the frozen Sol codebook. It does not
establish that Sol is infallible. Human-review bounds are a separate layer in
Section 7.

## 2. Reference-label sampling design

The fixed response population is the 137,186 unique canonical
`(prompt_id, prompt_language, model)` rows. Inclusion is:

- probability one for every one of the 11,475 original code-4/5 rows;
- stratified simple random sampling without replacement for 2,500 code-1/2/3
  controls;
- strata: `model × prompt_language × home_status × engagement_code`;
- at least one sampled control in every populated stratum;
- the remaining allocation minimizes a predeclared multi-objective approximation
  to phase-two variance across overall prevalence, four pooled language
  contrasts, five home contrasts, and 55 model-language cell rates.

Allocation may use the probability-weighted Sol pilot and wall-to-wall
covariates because those quantities were observed before the reference sample
was drawn. The allocation model never enters a publication estimate. Within
each stratum, every control has inclusion probability `n_h/N_h` and sampling
weight `N_h/n_h`. SRSWOR supplies known joint inclusion probabilities.

Frozen provenance:

| object | value |
|---|---|
| population rows | 137,186 |
| reference rows | 13,975 |
| control budget | 2,500 |
| seed | 20260819 |
| population-key SHA-256 | `2b1f4be22ef82ccbe071dfba766422518107230fcd2e1ccf7602b84f56a538bb` |
| reference-key SHA-256 | `985fd82ea0bda389130b933d5c9969fcff5fcfb56f86755826f4c019b54e87a4` |
| allocation SHA-256 | `a4e612038cda46814b14912b0ef0c396c433471a3ea03916ee1b9c516e3d8cf6` |

The manifest is
`annotations/response_validity_dsl_v1/reference_manifest.json`. Preparing or
pricing this design makes no model call.

## 3. Why 2,500 controls

The cost-free planning calculation is in
[`RESPONSE_VALIDITY_DSL_DESIGN.md`](RESPONSE_VALIDITY_DSL_DESIGN.md). Under its
explicit pilot-based approximation, the 2,500-control multi-objective design
has maximum expected phase-two SE 0.91 percentage points across home contrasts,
0.48 points across pooled language contrasts, and a 90th-percentile SE of 1.69
points across model-language cells. These are planning values, not reported
uncertainty.

## 4. DSL measurement estimator

For response `i`, let `Y_i` be its frozen Sol reference label, `R_i` indicate
reference sampling, `pi_i` be its known inclusion probability, and `g_-k(i)` be
an issue-cross-fitted prediction. Define

```text
Y_tilde_i = g_-k(i) + R_i / pi_i * (Y_i - g_-k(i)).
```

The correction preserves the finite-population target under the labeling design
even if the learner is misspecified. Predictions improve efficiency only. DSL
pseudo-outcomes may lie outside `[0,1]`; clipping would destroy the correction
and is forbidden.

Five folds are assigned by `issue_id`, so translations, tiers and subject-model
responses from one issue never cross from training to prediction. Ten frozen
repeated partitions are averaged. The between-repeat prediction SD is retained.
Every repeat-specific rectified pseudo-outcome is also retained, because
downstream estimands require their joint row-level variation; per-row SDs alone
cannot recover cross-row covariance.

The predeclared learner is L2-penalized logistic regression with one-hot
categorical features, standardized numeric diagnostics, inverse-inclusion
weights, and no use of the target response text embedding. Features are:

- original engagement code and justification;
- model, jurisdiction, language, home status, tier, domain, route and region;
- prompt origin and response-language metadata;
- length, Unicode/script, repetition, echo, punctuation and truncation
  diagnostics.

This deliberately interpretable baseline must pass calibration gates before a
more flexible learner is introduced. Learner selection after seeing downstream
effects is prohibited.

## 5. Downstream inference

Every corrected estimator must publish four points:

1. original judge-coded non-engagement;
2. reference-only Horvitz--Thompson/Hájek estimate;
3. prediction-only estimate, explicitly marked potentially biased;
4. rectified DSL estimate.

Primary intervals are based on the estimating function formed from
`Y_tilde`, clustered at `issue_id`. For SRSWOR controls, the phase-two component
must use the declared stratum finite-population correction or design-matched
replicate weights. Ten cross-fit repetitions contribute split uncertainty using
the median/within-between rule. A smaller nested issue × phase-two bootstrap
must reproduce the analytic interval within a prespecified tolerance before
release.

Pointwise 95% intervals are accompanied by max-t simultaneous 95% bands for the
five home contrasts, four pooled language contrasts, model-specific home
contrasts, and model-language contrasts. Across-subsample ranges in `c21` remain
stability diagnostics and are never relabelled confidence intervals.

## 6. Forensic integration map

| Existing output | DSL disposition |
|---|---|
| `c02`, `c03` | Recompute observed home/away rates and differences from `Y_tilde`; original outcome remains a parallel sensitivity. |
| `c04` | Historical original-label result remains unchanged. Corrected analogue is `c25`: solve a per-jurisdiction linear-probability moment with `Y_tilde` and standardize over the full target. A binomial likelihood is invalid because rectified pseudo-outcomes can leave `[0,1]`. This remains an adjusted association, not causal. |
| `c05` | DSL model-specific home contrasts plus a jointly estimated equal-model average and simultaneous family band. |
| `c06`, `c06b` | Unchanged design/support diagnostics; they contain no measured outcome. |
| `c07`, `c07b`, `c07c` | Rerun estimator/support/roster/functional-form sensitivities. Code-3 becomes a legacy outcome benchmark rather than a refusal definition. |
| `c08`, `c08b`, `c09` | Form DSL target-language minus English differences inside the existing model × prompt blocks; preserve issue clustering and missing-block counts. |
| `c10`, `c10b`, `c11` | Insert DSL outcomes into the existing complete 2+2 framing blocks. Measurement correction does not strengthen the framing identification assumptions. |
| `c12`, `c13` | No automatic change: ideology is another construct and remains conditional on its content-pass sample. |
| `c14`, `c15` | No automatic change: refusal DSL does not validate moral-foundation labels. |
| `c16` | Rebuild joint states to distinguish clean refusal, capability failure, pivot, engaged/content-present and engaged/content-absent. Never code a refusal as foundation absence. |
| `c17`–`c17d` | Preserve historical judge-instrument sensitivity; add original-versus-Sol differences without calling agreement accuracy. |
| `c18` | Add fold balance, weighted calibration, inclusion-weight range, effective sample size, correction influence, split variation and interval-component diagnostics. |
| `c19` | Unchanged unless Sol separately codes ideology/foundations under a new validation design. |
| `c21` | Add DSL home/language/framing point stability; retain its explicit non-CI interpretation. |
| `c22` | Use corrected aggregate propensities where supported. Do not claim design-identified individual-prompt rates when reference support is absent. Geometry is unchanged. |
| `c23` | Replace with reference-design composition, Sol outcome prevalence, calibration and validation diagnostics. |
| `c24` | Replace HT-only correction with prompt-paired DSL language contrasts. |
| `c25` | Replace validation-weighted ridge extrapolation with a cross-fitted, rectified DSL moment followed by declared g-computation. |
| `c26` | DSL model-language competence/refusal rates with pointwise and simultaneous intervals. |
| `c27` | Corrected complete-block English framing contrast. |
| `c28` | Corrected descriptive home heterogeneity by model. |
| `c29` | Corrected prompt-paired language heterogeneity by model. |
| `c30` | Frozen-design, cost, and cross-fit diagnostics. |
| `a01` | Keep original engagement composition as historical measurement. |
| `a02` | Add DSL-corrected cell rates. |
| `a03` | Keep original justification composition; it is not validity evidence. |
| `a04` | Use the DSL-corrected paired DeepSeek Chinese-minus-English contrast. |
| `e22`–`e28` | Preserve as provenance/reliability. Do not merge judge ranges with DSL confidence intervals. |

### Content-selection boundary

Passes 2/3 were skipped for originally refused responses. Sol may recover some
of those as coherent answers or pivots, but they have no ideology/foundation
label. The pipeline must therefore either retain content estimands conditional
on the original content-pass sample, separately annotate recovered answers, or
report explicit worst-case bounds. It must never silently change the denominator.

## 7. Approved human-reference successor

The publication target is now a separate human-referenced, model-assisted
two-phase DSL layer. The approved design includes literal English response
translations shown beside unchanged original text, a blinded 250–300-row
known-probability pilot with one annotator and 10–15% silent repeat coding, a
human-verified exemplar bank, held-out inexpensive-surrogate evaluation,
precision simulation for 800–2,000 final human rows, probability-based adaptive
sampling, and issue-cross-fitted human-reference rectification. It is specified
in [`HUMAN_REFERENCED_DSL.md`](HUMAN_REFERENCED_DSL.md). No translation,
surrogate, or final population API call is authorized by this specification.

Sol c23–c30 remain immutable machine-reference sensitivity. Planned human
c31–c38 become primary only after their own acceptance gates. Repeated Sol calls
measure stability, not truth.

## 8. Gates before any canonical release

- exact 14,182/14,182 Sol coverage, including 207/207 augmentation rows, and
  zero unresolved schema/logic failures;
- zero reasoning tokens and no stored reasoning trace;
- reference manifest hashes unchanged;
- every fold contains all design dimensions and both outcome classes where the
  population permits;
- weighted out-of-fold calibration reported overall and by model/language/home;
- pseudo-outcome design-unbiasedness verified on an enumerated synthetic census;
- reference-only and DSL points agree within their declared design uncertainty;
- no influential correction term can silently dominate a headline estimate;
- analytic and nested-replicate intervals agree within tolerance;
- simultaneous bands cover the declared family, not a post-hoc subset;
- current content analyses retain their original conditioning statement;
- full Sol execution receives a separate, explicit hard-dollar authorization.

## 9. Historical commands and authorization boundary

These commands document the completed Sol run. Their implementations are now
under `scripts/archive/response_validity/`; archival does not authorize rerun.

```bash
# Free and already completed
python3 scripts/archive/response_validity/simulate_response_validity_dsl_design.py
python3 scripts/archive/response_validity/response_validity_dsl.py prepare --control-budget 2500
python3 scripts/archive/response_validity/run_response_validity_dsl_reference.py seed-pilot
python3 scripts/archive/response_validity/run_response_validity_dsl_reference.py estimate

# PAID — completed under the manifest-recorded $95 ceiling
python3 scripts/archive/response_validity/run_response_validity_dsl_reference.py run \
  --workers 24 --cost-ceiling <APPROVED_USD> --authorize-paid-run

# Free after complete labels
python3 scripts/archive/response_validity/run_response_validity_dsl_reference.py assemble
python3 scripts/archive/response_validity/response_validity_dsl.py assemble \
  --labels annotations/response_validity_dsl_v1/assembled_reference_labels.parquet \
  --folds 5 --repeats 10
```

The price was re-verified on 2026-08-19 while OpenRouter advertised a 50%
discount on its OpenAI endpoint. The runner accounts separately for ordinary
input ($2.50/M), cache reads ($0.25/M), cache writes ($3.125/M), and output
($15/M), using billing shares observed in the completed pilot. The resulting
estimate for 12,803 new calls and the 20%-contingency recommendation are recorded
in
`annotations/response_validity_dsl_v1/sol_cost_estimate.json`. The runner will
not accept a command flag alone: the manifest must separately record the exact
authorized ceiling, and completed provider usage plus a worst-case reservation
for in-flight calls may never exceed it. Requests are restricted to the
discounted `openai` provider and provider fallbacks are disabled; the hard guard
nevertheless reserves pre-discount rates so that a mid-run price change cannot
silently exceed the authorization.

At launch, the exact pilot-calibrated expectation was **$75.09**, the computed
20%-contingency recommendation was **$91**, and the recorded hard ceiling was
**$95**. The ceiling is a maximum, not a spending target; the run records actual
provider-reported cost row by row and is resumable if the pinned endpoint is
temporarily unavailable.

The completed run cost **$75.264048625**, reused 1,172 paid pilot judgments, and
contains 13,975 unique successful reference IDs. The downstream assembly writes
three rectified outcomes for all 137,186 population rows and 150 cross-fit
diagnostic rows (3 outcomes × 10 repeats × 5 folds). All repository Python tests
passed after assembly.

The complete execution ledger, token accounting, artifact hashes, repair audit,
measurement prevalences, and cross-fit diagnostic ranges are recorded in
[`RESPONSE_VALIDITY_DSL_RUN.md`](RESPONSE_VALIDITY_DSL_RUN.md).

The runner enforces the v1.1 codebook after schema parsing. If Sol returns the
specifically prohibited combination of `coherence` equal to `incoherent` or
`unassessable` with an `explicit` or `implicit` noncompliance signal, the runner
applies the codebook's conservative rule that unintelligible failure is not a
communicated refusal: it changes the signal to `none` (or `unassessable` when
coherence is unassessable), clears the evidence span, and validates the entire
record again. The untouched model JSON, triggering error, and named repair rule
are retained in `validation_repair`; no other inconsistency is repaired.
