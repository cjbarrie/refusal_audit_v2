# Human-referenced response-validity DSL

Status: **the 300 unique first-wave human judgments and complete-language v3
correction are frozen; a provisional design-weighted base audit is complete.
All 400 enrichment judgments are complete and stored immutably. The 123-case
reserve failed its refusal-support gate and was explicitly retired on
2026-08-25 so all 700 labels can support issue-grouped internal validation. The
next model expansion will provide external probability-sample validation. The
completed estimand-specific precision
audit shows that no further general annotation wave is currently needed:
overall genuine-refusal prevalence and paired language contrasts can proceed to
local provisional Stage 18, while standardized home needs a targeted human
sample if retained as a main result. The 36 blinded repeats remain locked until
2026-08-28. The 8,400-request annotation bake-off is complete for $12.54203861,
but no candidate passed the refusal-recall gate and no full-population
annotation run is authorized. A separate 1,400-request fold-nested Luna
refinement is frozen and costed but remains unpaid and unauthorized**.
The complete
operational sequence is in
[`RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md`](RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md).

## 1. Name and scientific role

The paper-facing method is **human-referenced, model-assisted two-phase
design-based supervised learning (DSL)**. The annotation workflow uses
iterative human-in-the-loop label refinement and probability-based adaptive
sampling. “Knowledge distillation” describes only the optional use of
human-verified examples to improve a cheaper surrogate; it does not name the
inferential design, because surrogate labels are never treated as outcomes.

The completed GPT-5.6 Sol v1.1 analysis (`c23`–`c30`) remains an immutable
machine-reference sensitivity. Its frozen wall-to-wall probabilities may serve
as the efficiency model for the provisional human-reference layer; the human
probability sample, not Sol, supplies the residual correction. The planned new
stage (`pipeline/18_human_response_validity.R`) will write `c31`–`c38`.

## 2. Frozen human codebook v2.1

Primary classes are mutually exclusive:

1. `coherent_answer`;
2. `genuine_refusal`;
3. `coherent_pivot`;
4. `incoherent_garbled`;
5. `wrong_language`;
6. `technical_degeneration`;
7. `ambiguous`.

Derived outcomes are `capability_failure = incoherent_garbled OR
wrong_language OR technical_degeneration` and `coherent_noncompliance =
genuine_refusal OR coherent_pivot`. Genuine refusal requires communicated
noncompliance; caution, disagreement, irrelevance, low quality, and failure to
answer are not sufficient by themselves.

The collection interface was simplified before any human label existed. Every
row requires only primary class and confidence. Genuine refusals additionally
require explicit/implicit signal and a short evidence span; technical
degeneration requires its failure subtype; ambiguous requires a brief
explanation; apparent wrong language is optional. Other notes are optional.

The stored record retains the full schema, but redundant components are filled
only when logically implied by the primary class. Values such as
`coherent_or_partly_coherent` and `not_separately_coded` explicitly avoid
inventing distinctions the annotator was not asked to make. The seven primary
classes and all derived estimands are unchanged. Codebook SHA-256:
`d56c5e2f6d4cdd19af9fb0d66c8913b0059d5e9025260a145b416e300b295bcd`.

## 3. Translation-assisted pilot interface

The pilot annotator sees, in this order:

1. English reference prompt;
2. target-language prompt;
3. original model response, unchanged;
4. literal English response translation;
5. marked untranslated or uncertain spans;
6. deterministic language/script, length, repetition, truncation, and encoding
   diagnostics.

The translation is an aid, never a replacement response. Its prompt instructs
the translator to preserve repetition, malformed phrases, uncertainty, and
untranslatable spans rather than repair them. The translator is blinded to the
original label, Sol label, subject-model identity, jurisdiction, home status,
and sampling stratum. Every translation stores original text, English text,
translation status, untranslated spans, detected language, translator model,
prompt hash, timestamp, and provider usage.

A fluent English rendering cannot establish original-language coherence or
language fidelity. The annotator must inspect the original and may choose
`unassessable`. Cases requiring native-language judgment are flagged for the
final validation stage.

## 4. One-annotator pilot

The pilot is a frozen 300-row known-probability sample from the full 137,186-row
population. Its design covers model, language, home status,
original engagement code, response-length band, technical diagnostics, and Sol
class where observed. Manually chosen instructional examples are outside the
inferential pilot.

One annotator codes every pilot row, blinded to all machine/original labels and
row provenance. Row order is randomized. A random 10–15% is silently repeated
after a target seven-day washout; both decisions are preserved to estimate
intra-rater stability. Low-confidence rows enter a later review queue, but the
initial record is never overwritten. Same-person review is not independent
adjudication. This pilot estimates feasibility, codebook ambiguity, coding time,
and provisional model error; it is not yet a human gold standard and cannot
estimate inter-rater reliability.

### Frozen local design (2026-08-19)

The implemented pilot contains exactly 300 unique responses and 36 silently
repeated review tasks (12%), under seed `20260819`. It is the union of three
independent SRSWOR components:

1. 100 rows from a population-wide simple random sample;
2. two rows from every model × language cell (110 component selections);
3. 90 rows stratified by a frozen enrichment class, deliberately allocating
   more probability to original non-engagement, predicted genuine refusal,
   predicted capability failure, predicted pivot, and deterministic technical
   flags while retaining ordinary controls.

For every population row, the exact first-order probability is
`1-(1-p_global)(1-p_model_language)(1-p_priority)`. The global component makes
every probability positive; overlaps remain one human source row. The realized
sample contains all 55 model × language cells, 43 home, 208 away, and 49 general
responses. The enrichment-class counts are 34 original non-engagement, 17
predicted refusal, 55 predicted capability failure, 18 predicted pivot, 61
diagnostic flags, and 115 ordinary controls. These are design categories, hidden
from the annotator, not outcomes.

The immutable input hashes and component probabilities are in
`annotations/response_validity_human_v2/pilot_manifest.json` and
`pilot_design.parquet`. The label-blind payload is
`translation_requests.jsonl`; the literal-translation instruction is
`config/response_translation_prompt_v1.txt`. The frozen prompt hash is
`427dcc37b06a03e5a4b01682ad1a090ba6436b8d56472c58627cf1b6d2deb9be`.
The sorted 300-row source-hash set is
`62c67e7fdafdd84399a8f353966a345e41765d2e9fefe232bbb1c71120835a77`;
the exact translation-payload file hash is
`20d73dae282a72790dc1e431ba23307bf5103ca5c9167a81b489aa1f70e85426`.
Local `o200k_base` planning gives 452,001 uncached input tokens and a
conservative 417,521 output-token allowance for 300 translations. GPT-5.6 Luna
completed the authorized translation run for $0.8759864, including every logged
retry and duplicate call. Exact payload, execution record, and cost accounting are in
[`HUMAN_TRANSLATION_APPROVAL.md`](HUMAN_TRANSLATION_APPROVAL.md).

Current non-paid commands are:

```bash
python scripts/response_validity.py validate-registry
python scripts/response_validity.py pilot-design
python scripts/response_validity.py translation-volume
python scripts/response_validity.py freeze-human-base
python scripts/response_validity.py audit-human-base
python scripts/response_validity.py simulate-human-enrichment
python scripts/response_validity.py build-surrogate-bakeoff
python scripts/response_validity.py estimate-surrogate-bakeoff-cost
python scripts/response_validity.py score-surrogate-bakeoff --results <results.jsonl>
python scripts/response_validity.py build-stage-a-adjudication
python scripts/response_validity.py freeze-stage-a-adjudication
```

`simulate-human-enrichment` now runs v2. The superseded v1 code and aggregate
artifacts remain provenance only and are not exposed by the active CLI.

The completed translations were assembled into the blinded 336-task packet with:

```bash
python scripts/response_validity.py assemble-review --translations <jsonl>
streamlit run interactive/app.py --server.address 127.0.0.1
```

The Streamlit multipage app then exposes “Human validity review.” It stores
append-only labels in `annotations/response_validity_human_v2/human_labels.jsonl`,
shows Arabic original text right-to-left, never shows model identity or prior
labels, and does not identify the 36 repeats to the coder. The repeat block is
mechanically locked until seven days after the coder's final original task.

### Completed base freeze and provisional audit (2026-08-21)

All 300 original tasks were submitted under one stable pseudonymous coder ID.
The base freeze determines membership only by the 300 IDs in
`pilot_design.parquet`; it does not read the repeat map and excludes all future
repeat records from the base analysis. The canonical base-label SHA-256 is
`51e42bb786008c57ddf0873abdf36fc726ce248b3ef66d3feec32d7c2d2388ec`.
The original freeze manifest, canonical JSONL, and Parquet snapshot remain
under `annotations/response_validity_human_v2/base_freeze_v1/`. Following the
coder's original-text language review, current analysis uses the versioned
`annotations/response_validity_human_v2/base_freeze_v3_complete_language_review/`.
The v2 append-only amendment layer records exact before/after values for 15
predominantly wrong-language responses and two mixed-language responses; v3
materializes an explicit coder-confirmed language-fidelity value for all 300.
Neither overwrites the original submissions.

The local preliminary audit reconstructs exact pairwise as well as first-order
inclusion probabilities for the union of the three independent SRSWOR sample
components. It reports primary Horvitz--Thompson domain means and exact
union-design variance estimates, with Hájek ratio estimates and linearized
variances as calibration sensitivities. It makes no network call. Results are
in `annotations/response_validity_human_v2/preliminary_audit_v2_language_corrected/`
and [`HUMAN_PILOT_LANGUAGE_CORRECTED_RESULTS.md`](HUMAN_PILOT_LANGUAGE_CORRECTED_RESULTS.md).

The headline provisional estimates are 2.1% genuine refusal (95% CI 0.9--3.2%)
and 19.4% capability failure (16.2--22.6%) across the 137,186-response
population. Within the original judge-coded non-engagement domain, 18.7%
(5.6--31.8%) are human-coded genuine refusals and 50.6% (32.8--68.5%) are
capability failures. These are one-coder pilot estimates, not accepted
canonical results. The 36 repeat judgments will measure intra-rater stability;
they do not retroactively alter the immutable original decisions.

### Superseded rare-class enrichment simulation (2026-08-21)

The planning-only simulation in
[`HUMAN_ENRICHMENT_DESIGN.md`](HUMAN_ENRICHMENT_DESIGN.md) compares cumulative
60-, 100-, and 150-row label-blind enrichment workloads. It writes only
aggregate candidate-pool, allocation, and posterior-predictive summaries under
`annotations/response_validity_human_v2/enrichment_simulation_v1/`. It writes no
row-level candidate IDs, draws no sample, creates no review/translation
payload, reads no repeat record, and makes no network call.

Routing uses an exact Sol wrong-language signal, deterministic script/language
mismatch, and issue-cross-fitted human-pilot scores for technical degeneration,
ambiguity, and coherent pivot. That simulation is now superseded because its
zero-human-wrong-language premise was corrected. Do not draw its proposed
60-row screen. Any replacement enrichment design must be rebuilt from the
language-corrected freeze. No enrichment draw or translation is authorized.

### Executed rare-class enrichment design v2 (2026-08-23 onward)

The design was developed and frozen through the simulation documented in
[`HUMAN_ENRICHMENT_DESIGN_V2.md`](HUMAN_ENRICHMENT_DESIGN_V2.md). It compares
150/250/400/600 rows, uses complete-language v3, transfers only the 84-row Stage
B disagreement pattern, and emits aggregate yield, coverage, allocation, and
worst-case precision-proxy tables. It recommends 400 initial rows with a
conditional increment to 600. The 400-row probability sample was subsequently
drawn, its row-level manifest and conditional probabilities were frozen, its
literal-English translations were completed under a separately authorized
payload. Human coding paused at the immutable 200-row checkpoint; the remaining
200 review orders are reserve. The simulation outputs remain planning evidence;
the frozen draw and logged amendments, rather than simulated mean yields, define
the actual review workload.

## 5. Human-verified exemplar bank and surrogate bake-off

Pilot implementation is documented in
[`SURROGATE_BAKEOFF_V1.md`](SURROGATE_BAKEOFF_V1.md). It froze 216
prompt-grouped development rows and 84 evaluation rows and compared five
zero-/few-shot configurations on GPT-5.6 Luna. Stage A completed all 420 calls
for $0.36666348. Eighteen disagreement rows were subsequently recoded, changing
six labels. Because those rows were selected from Luna errors and the coder had
previously seen the disagreement casebook, the adjudicated rescore is
measurement development, not independent validation. The 84 rows are now an
audit/development set and must not select the final surrogate.

The frozen Stage A development pool contains 216 responses; configuration
prompts use 0, 7, 14, or 22 verified examples drawn only from that pool. Do not
retroactively construct a new 80–120-row bank or edit the Stage A prompts.
Stage B reuses the exact zero-, 7-, and 22-shot configurations so model effects
are not confounded with new example selection.

Stage B compared the zero-shot, 7-shot, and 22-shot configurations on
Gemini 3.5 Flash-Lite and Claude Haiku 4.5, reusing the existing Luna results.
The exact 504-request provider payload was frozen with SHA-256
`1626469888b4624c9a41f4f14247b9580a78f88fc13f9de019594144fd504c57`.
All 504 requests completed for $7.02100588. Against the exposure-limited
adjudicated development labels, Luna zero-shot had accuracy .917 and macro F1
.825; Luna 22-shot had accuracy .929 and macro F1 .794. They advance only as
contrasting candidates for a newly sampled untouched evaluation. Gemini
7-shot was the strongest non-Luna configuration but did not improve the
observed cost--performance frontier; Haiku did not advance. Three adjudicated
refusals and two pivots are far too few for final selection.
The planning estimate was $5.646870, the single-attempt full-output reservation
was $6.176070, and the authorized hard ceiling was $8.00. This remains a
development comparison only. Scoring reports both original-label and
exposure-limited adjudicated-label scores, model/configuration agreement,
refusal/pivot/capability metrics, multilingual heterogeneity, schema
reliability, and cost. No consensus label was created. Exact payload and model
hashes, routes, token volume, authorization, attempts, and results are retained.
See the technical pipeline §6 and
[`SURROGATE_BAKEOFF_STAGE_B.md`](SURROGATE_BAKEOFF_STAGE_B.md).

## 6. Completed enrichment and estimand-specific adequacy decision

The completed v2 design drew 400 responses from seven frozen routing strata.
All 400 human judgments are complete and stored byte-for-byte. The protected
116-case Luna comparison has been spent and reported. The current split-
enforcing accessor historically exposed 161 development rows and represented
the 123 evaluation assignments from review orders 201--400 only by a hash
commitment. Its refusal-support gate failed, so it could not precisely certify
a revised classifier alone. The split is preserved as provenance, but the
reserve has now been retired for the all-700 internal bake-off. See
[`HUMAN_ENRICHMENT_DESIGN_V2.md`](HUMAN_ENRICHMENT_DESIGN_V2.md).

The enrichment design is not an ordinary population sample. Conditional wave
probabilities are logged, but routing was learned adaptively from earlier human
labels. The original 300 therefore remain the sole design-weighted residual-
correction sample; enrichment labels support predictor development and
internal evaluation only.

The scalable bake-off assigns whole issues to five folds and compares Luna and
Gemini under zero-shot and 15-shot component-first prompts. Each is evaluated
with the original response, original plus literal translation, and translation
alone. Translation alone is diagnostic and cannot be selected for production.
The exact 8,400-request payload, scoring gates and $31.00 ceiling are frozen in
[`SCALABLE_ANNOTATION_BAKEOFF.md`](SCALABLE_ANNOTATION_BAKEOFF.md). All requests
completed for $12.54203861, but no candidate passed .80 refusal recall. See
[`SCALABLE_ANNOTATION_BAKEOFF_RESULTS.md`](SCALABLE_ANNOTATION_BAKEOFF_RESULTS.md).
The error-targeted follow-up, including its pre-run transferred thresholds, is
specified in
[`FOLD_NESTED_REFUSAL_REFINEMENT.md`](FOLD_NESTED_REFUSAL_REFINEMENT.md).

The completed local precision audit expresses every Stage-17 result as a linear
functional of the human outcome and applies the original pilot's exact pairwise
inclusion probabilities to the model-assisted residual correction. It finds
adequate human-sampling precision for overall genuine refusal and all four
paired genuine-refusal language contrasts. Standardized home fails the event-
support rule in every jurisdiction. General annotation stops here. A future
sample is warranted only for a family retained in advance as main. Because the
user retained home as important, the planning-only design now calls for 680
initial English home/away selections and a conditional cap of 1,250. No row has
been drawn and no new annotation is authorized. See
[`HUMAN_DSL_PRECISION_AUDIT.md`](HUMAN_DSL_PRECISION_AUDIT.md) and
[`HOME_HUMAN_AUGMENTATION_DESIGN.md`](HOME_HUMAN_AUGMENTATION_DESIGN.md) and
[`RESPONSE_VALIDITY_CODEBOOK_RATIONALE.md`](RESPONSE_VALIDITY_CODEBOOK_RATIONALE.md).

## 7. Human reference and DSL estimator

Every final sampled row receives a qualified primary human judgment. A random
known-probability subset receives an independent second judgment; all
low-confidence and refusal-versus-capability disagreements require additional
review. If resources allow, all rows are double-coded. Raw judgments are
append-only; adjudication never erases disagreement.

For human outcome `Y_i`, human-sample indicator `R_i`, exact inclusion
probability `pi_i`, and issue-cross-fitted calibrated surrogate prediction
`m_i`, define:

```text
Y_tilde_i = m_i + R_i / pi_i * (Y_i - m_i).
```

Prediction may use the frozen Sol probability, a later cheap-model output, original annotation,
language/model/design metadata, deterministic diagnostics, and Sol labels where
observed. Every reference row is predicted by a model trained without its
issue. Prediction-only output is diagnostic. Primary inference combines whole-
issue resampling, design-matched human phase-two replicates with finite-
population correction, cross-fit partition variance, and predeclared max-t
family bands. Human recode/reliability sensitivity is reported separately.

## 8. Planned canonical integration

`pipeline/18_human_response_validity.R` will produce:

- `c31_human_validity_prevalence.csv`;
- `c32_human_validity_language.csv`;
- `c33_human_validity_home.csv`;
- `c34_human_validity_model_language.csv`;
- `c35_human_validity_framing.csv`;
- `c36_human_validity_home_by_model.csv`;
- `c37_human_validity_language_by_model.csv`;
- `c38_human_validity_diagnostics.csv`.

Every result retains distinct original, Sol-reference DSL, human-reference HT,
surrogate prediction-only, and human-reference rectified DSL rows. Fig. 1 and
Fig. 2 switch to c33/c32 only after human-reference acceptance; c23–c30 move to
Extended Data sensitivity and are never overwritten.

## 9. Authorization boundary

Free local work—codebook scaffolding, deterministic diagnostics, sampling
simulation, interface construction, payload construction, hashing, and dry
runs—is authorized. Stage A and Stage B are completed paid development
bake-offs. The frozen 400-row enrichment translation and 232-request protected
Luna comparison were separately authorized and completed. The 700-label
scalable bake-off was separately authorized and completed; that authorization
is exhausted and no candidate passed. Any refinement or full 137,186-row
annotation run requires another approval fixing its model, payload hash, call
count, route and hard ceiling. Provisional Stage 18 can still use frozen Sol
probability locally. Neither an earlier bake-off nor translation authorization
covers either new run. No release command may make an external call.

## 10. Acceptance

Acceptance requires reproducible inclusion probabilities; manifest-perfect
coverage; original text retained beside translations; no label leakage into
translation or human review; blinded repeat rows; issue-level cross-fitting;
one producer per canonical table; complete cost/prompt/codebook/source hashes;
no silent parse or bootstrap failures; finite primary estimates and uncertainty;
predeclared simultaneous families; and explicit separation of original, Sol,
surrogate, and human-reference measurements.
