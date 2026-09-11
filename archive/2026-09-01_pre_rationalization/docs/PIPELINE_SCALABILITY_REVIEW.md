# Pipeline scalability review and decision memo

**Status (2026-08-26): the versioned-population strategy and 700-label internal
bake-off have been adopted. The bake-off completed for $12.54203861, but no
candidate passed the refusal-recall gate. A 1,400-request fold-nested Luna
refinement is frozen and costed but unpaid. No new sampling, generation,
refinement provider run, full-population
annotation, or canonical promotion is authorized by this memo.**

## Executive conclusion

The project does not need to repeat the entire human-validity exercise whenever
a model is added. It does, however, need human probability coverage of rows that
did not exist in the population against which the current sample was drawn.

The scalable design is a **versioned population with incremental calibration**:

1. keep the current 700 human-reviewed responses as a reusable development and
   boundary-case corpus;
2. retain the original 300-row probability sample as the design-valid correction
   sample for the current 137,186-response population;
3. when models are added, draw a new probability sample from the new rows, with
   a small population-wide component and estimand-targeted components;
4. combine old and new samples using their actual multi-phase inclusion rules;
5. periodically draw a fresh global audit sample to detect drift.

The proposed 680-selection home augmentation should therefore be drawn only
after the model roster intended for the paper is frozen. If the ten-model
expansion will be part of this paper, drawing against the current 11-model frame
now would answer the old population and would have to be supplemented after the
expansion. The completed low-cost bake-off did not approve an instrument; a
fold-nested implicit-refusal refinement is now required before population use.

## 1. End-to-end map of the project

| Layer | Current authoritative object | What is frozen | Main unresolved issue |
|---|---|---|---|
| Issue sourcing | `sourcing/` and the 2,773-issue rebalanced frame | Wikipedia provenance and issue metadata | Top-level documentation still foregrounds earlier perennial/temporal counts |
| Study battery | `prompts/sampled/` | 624 issues, 2,496 prompts per language, five languages | A model expansion should reuse these prompt keys unless the scientific target changes |
| Subject generation | `scripts/generate_responses.py` and `annotations/full_v1/responses/` | 137,186 valid delivered responses from 11 models | The scientific roster is partly determined by endpoint environment variables rather than one versioned roster manifest |
| Original annotation | `scripts/annotation_pipeline.py` and `annotations/full_v1/ann/` | Gemini 2.5 Flash-Lite Pass-1 engagement labels; content labels on an issue subsample | `engagement_code >= 4` mixes refusal and capability failure |
| Canonical estimation | registered R stages 01--17 | Accepted historical release `canon_012`; Sol-reference Stage 17 is a candidate sensitivity | Human-referenced Stage 18 is planned but not implemented |
| Human validity | `annotations/response_validity_human_v2/` | 300 probability labels plus 400 enriched labels and literal translations | The sparse reserve was retired; 700-label internal bake-off is frozen, external validation awaits new-model sampling |
| Figures/release | `pipeline/make_release.R` and acceptance gates | Immutable historical releases and promoted PNG-only figure trees | Current main claims still await human-reference integration |
| Exploration/review | `interactive/` | Fixed 2,496-prompt UMAP geometry and append-only human reviews | This is a review surface, not an inferential stage |

The strongest part of the repository is the back end: estimands, issue-level
uncertainty, immutable releases, and acceptance tests are explicit. The weakest
seam is between generation and measurement: model rosters, original annotation,
response-validity correction, and expansion planning are documented in several
places but are not yet governed by one population manifest.

## 2. What adding models changes

A population is defined by at least the prompt-battery hash, language set,
subject-model roster and exact provider identifiers, generation policy, and
delivered response keys. Adding a model creates as many as 12,480 new response
rows (2,496 prompts times five languages). Those rows had zero probability of
selection into the current 300-row human sample.

This has three consequences:

- Results for the existing 11-model population remain valid and reproducible.
- A pooled or equal-model estimate for an enlarged roster is a new estimand and
  needs human calibration for the new rows.
- A new model can change a home contrast even if it belongs to an existing
  jurisdiction; a model from a new jurisdiction creates a new home/away target.

The existing labels do not become useless. They continue to train the shared
surrogate, define boundary examples, and correct the old part of the population.
Only the added rows need incremental probability coverage. Full re-annotation
is warranted only if the prompt battery, language set, response-validity
codebook, or generation policy changes enough to redefine the measurement task.

### Required scalable roster contract

Replace the import-time, environment-dependent scientific roster with a
versioned file such as `config/study_rosters/<roster_id>.json`. It should record
display name, exact provider model identifier, developer jurisdiction, provider
route, generation parameters, and model/revision date. Environment variables
should provide credentials and private endpoint locations only; they should not
decide which models belong to the study.

Every generation run should freeze:

- `population_id` and `roster_id`;
- hashes of every prompt-language file;
- intended and delivered response-key counts;
- model/provider identity and decoding settings;
- retry and last-valid-record rules;
- exact parent population when the run is an incremental expansion.

## 3. Completed all-700 bake-off

There are 700 completed human decisions:

| Class | Original probability sample | Enriched sample | Total |
|---|---:|---:|---:|
| Coherent answer | 208 | 171 | 379 |
| Genuine refusal | 14 | 49 | 63 |
| Coherent pivot | 7 | 5 | 12 |
| Incoherent or garbled | 48 | 114 | 162 |
| Wrong language | 15 | 46 | 61 |
| Technical degeneration | 4 | 14 | 18 |
| Ambiguous | 4 | 1 | 5 |

This supported a materially stronger internal comparison of genuine refusal
and capability failure. It remained too sparse for seven-class or pivot model
selection.

### Why all 700 are now used for internal validation

The original pilot and parts of the enrichment sample influenced the codebook,
examples, prompts, and earlier model comparisons. The 123-row reserve failed
its refusal-support gate. The project considered two honest choices:

1. preserve the reserve and run a smaller comparison; or
2. explicitly retire the reserve, use all 700 under issue-grouped nested
   cross-validation, call the result internal validation, and obtain the next
   untouched external test from the new-model probability sample.

The user approved the second option on 2026-08-25. The reserve is now retired
for internal validation and cannot later be called untouched. A stand-alone
classifier certification is not required for design-valid supervised learning:
an imperfect annotation model affects precision, while the probability-sampled
human residual correction protects the target estimate. The next model
expansion will supply a fresh probability-sampled external audit.

### Bake-off estimands and leakage control

Primary selection metrics should be tied to the paper outcomes:

- genuine-refusal probability: Brier loss, calibration, sensitivity, precision,
  and the residual variance of the planned DSL estimands;
- capability-failure probability: the same metrics;
- language-fidelity error by target language;
- schema/parse success, latency, and observed provider cost.

Seven-class accuracy and macro F1 remain diagnostics. Pivot is retained in the
codebook and confusion matrix but cannot select the winner with only 12 events.

All folds must be grouped by issue, so related prompts, tiers, models and
languages cannot leak across training and evaluation. Candidate choice and
few-shot example choice must occur inside the training side of each fold. At a
minimum, all rows from an evaluation issue must be excluded from its examples.
Report pooled and language-specific uncertainty rather than a single accuracy.

## 4. Translation-assisted annotation should be tested directly

The human reviewer saw the original response and a literal English aid. The
previous Stage A and Stage B surrogate requests did **not** include the English
response translation: the builder loaded it for provenance, but formatted only
the target-language prompt, English reference prompt, and original response.
The completed bake-off provides the first direct test of translation-assisted
surrogate annotation.

The frozen bake-off uses three input conditions:

1. **Original only**: multilingual classification from the source response.
2. **Original plus literal English translation**: the likely production
   candidate.
3. **Translation only**: a diagnostic upper bound on how much source-text
   information is lost; never eligible for production language-fidelity coding.

All three use the same codebook, folds and schema; within a model/prompt pair,
the comparison isolates the translation's contribution. Exact design, hashes,
costs and selection rules are in
[`SCALABLE_ANNOTATION_BAKEOFF.md`](SCALABLE_ANNOTATION_BAKEOFF.md).

### Recommended component routine

For each response:

1. compute deterministic Unicode, script, repetition, truncation, echo, and
   length diagnostics on the original text;
2. classify semantic behavior from the original response plus, where used, the
   literal translation;
3. classify language fidelity from the original text, target language, and
   language/script diagnostics;
4. combine the components under the frozen class-precedence rules;
5. retain class probabilities, not only a hard label, for DSL efficiency and
   uncertainty analysis.

Translation must remain an aid. A translator can accidentally repair malformed
text, hide code-switching, or make a wrong-language response readable. That is
why the original response and deterministic diagnostics remain mandatory.

The 700 existing translations made this ablation possible without another
translation run. Logged translation spend was $0.876 for the population-like
300 and $2.985 for the longer, difficult 400, so the bake-off should also decide
whether translating every future response is worth the cost. If original-only
performance is adequate, translate only human-review cases and uncertain or
diagnostically flagged machine cases. If translation materially reduces
estimand residual variance, translate the full new population once and cache it
by response hash.

## 5. Human sampling for future model additions

Each expansion should have two probability components, drawn only after all new
responses and deterministic diagnostics exist:

- **Coverage component:** a positive-probability sample spanning every new
  model x language cell and ordinary as well as difficult responses.
- **Estimand component:** extra cases allocated to the analyses that remain
  primary, currently English home/away genuine refusal. Allocation uses frozen
  surrogate risk and estimator leverage, never revealed human outcomes.

The sample size should be simulated from the delivered new-model frame rather
than fixed per model in advance. Stop when predeclared event-support and
estimand half-width gates pass. Active-learning or disagreement cases may be
added for model development, but they cannot replace the probability component.

For continuing data collection, add a small fresh global probability audit at
each major roster release and a larger periodic refresh. Monitor surrogate
calibration, residuals, language-specific errors, and shifts in capability
failure. A material drift gate—not the mere passage of time—triggers prompt or
model redevelopment.

## 6. Timing of the home augmentation

Two scientifically valid paths exist:

| Intended paper roster | Action |
|---|---|
| Current 11 models | Draw the planned 680-selection home wave now, match existing labels after the draw, and stop or augment under the declared gate |
| Current 11 plus the planned expansion | Do the surrogate bake-off now, complete generation and assembly, recompute the enlarged home coefficients, and then draw one home-targeted sample from the final roster |

The second path is recommended if model expansion is imminent. It avoids asking
the annotator to revisit the same estimand twice and produces one interpretable
paper population. The existing 680 calculation remains a workload benchmark,
not the final expanded-roster sample size.

## 7. Place of slant and moral foundations

Slant and moral-foundation validity remain deferred. Their present labels are
conditional on the original Gemini engagement screen. Correcting refusal can
change who should have been eligible for content coding, and recovered coherent
answers have no slant or moral labels. Do not let those exploratory outcomes
determine current human sampling. Preserve their code and provenance, then
revisit denominator repair only if they return as paper claims.

## 8. Adopted decision sequence

1. The reserve has been retired and the five-fold, 700-label design is frozen.
2. The 8,400-request Luna/Gemini bake-off completed, but no candidate passed.
3. A 1,400-request fold-nested implicit-refusal refinement is frozen and costed
   under a separate payload. It remains unpaid and requires a new exact
   authorization; the completed bake-off authorization cannot be reused.
4. If the refinement passes, freeze the instrument and its probabilities. If
   it fails, test a stronger scalable model without relaxing the gates.
5. Implement provisional human-referenced Stage 18 for the current population;
   this is useful regardless of roster choice and does not require a provider
   run if frozen Sol probabilities remain the efficiency model.
6. Decide whether the ten planned models belong in this paper's estimand or a
   later replication. Do not draw the home wave until this is settled.
7. If expanding now, generate and assemble the final roster under a versioned
   population manifest, then run the chosen surrogate on the new rows.
8. Re-plan and draw one final-roster home probability augmentation. Future
   model releases receive incremental rather than wholesale calibration.
9. Integrate accepted human-reference tables into a new immutable canonical
   release. Keep original non-engagement and Sol-reference results as labelled
   measurement sensitivities.

## 9. Documentation rationalization required before expansion

`README.md`, `MANIFEST.md`, `docs/ANNOTATION_CONTRACT.md`, and parts of
`docs/NEXT_STEPS.md` still describe earlier language and model rosters or old
operational states. They should be replaced by a short current entry point plus
archived dated histories. The active authority chain should be:

1. one study-population/roster manifest;
2. one generation and annotation run manifest per population;
3. `pipeline/PIPELINE_REGISTRY.csv` for active analysis stages;
4. `CANONICAL_ANALYSES.md` for estimands;
5. `RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md` for measurement correction;
6. immutable release manifests for paper outputs.

Until this rationalization is complete, the accepted release manifest and the
frozen annotation/sample manifests take precedence over narrative counts in
top-level documentation.
