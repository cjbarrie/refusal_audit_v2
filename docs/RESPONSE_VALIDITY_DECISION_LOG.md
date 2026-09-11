# Response-validity decision log

This is the operational record for the human-referenced response-validity
pipeline. It records measurement and authorization decisions; generated
manifests retain the exact input and payload hashes. Historical artifacts are
never silently rewritten.

## 2026-08-20

- Declared the seven-class response-validity taxonomy to be a study-specific
  operational taxonomy, not an externally validated refusal scale. It repairs
  the original instrument's conflation of communicated refusal, adjacent-
  content substitution, and capability failure. The category menu is
  exhaustive; it is not identical to the hierarchy of paper estimands.
- Designated genuine refusal and aggregate capability failure as principal
  outcomes, coherent noncompliance as a secondary sensitivity, and standalone
  pivot and capability subtypes as diagnostic/exploratory unless support is
  adequate. The full construct lineage is now centralized in
  `RESPONSE_VALIDITY_CODEBOOK_RATIONALE.md`.
- Adopted a **human-referenced, model-assisted measurement** design. Cheap
  model annotations may improve precision, but the paper's estimands will use
  known-probability human reference labels and rectified design-based
  supervised learning (DSL). “Distillation” may describe the practical use of
  verified examples, but it is not the inferential design.
- Chose one human annotator for the initial pilot. This permits preliminary
  construct validation and intra-rater assessment but not inter-rater
  reliability or a claim of a human gold standard.
- Froze a 300-response probability pilot from the 137,186-response population.
  The design is the union of a global SRSWOR component, model × language
  SRSWOR, and label-blind priority-stratified SRSWOR. First- and pairwise
  inclusion probabilities remain recoverable.
- Added 36 blinded repeat tasks. They appear only after the 300 unique tasks and
  are locked for seven days after the final original submission. Repeat labels
  must remain outside all base prevalence and model-selection analyses.
- Authorized literal English translation of the frozen 300-row payload with
  SHA-256 `20d73dae282a72790dc1e431ba23307bf5103ca5c9167a81b489aa1f70e85426`,
  using prompt SHA-256
  `427dcc37b06a03e5a4b01682ad1a090ba6436b8d56472c58627cf1b6d2deb9be`,
  OpenRouter `openai/gpt-5.6-luna`, and a cumulative $3.00 ceiling. Translation
  was literal only and was not an annotation judgment.
- Simplified the human interface to one primary-class choice plus confidence
  and only the conditionally necessary fields. The purpose was to make manual
  review feasible without pretending the annotator separately assessed every
  redundant component.
- Required the original response to be the evidentiary source. English
  translation is an aid for semantic interpretation and cannot establish
  original-language fidelity.

## 2026-08-21

- Completed all 300 unique pilot judgments. The live append-only label log was
  frozen as v1 before any repeat task. The 36 repeats remain unread and
  unanalyzed.
- Preliminary v1 estimates were explicitly labelled one-coder pilot results,
  not human validation or a gold standard.
- The annotator disclosed relying mainly on English translations when judging
  some original-language responses. This was recorded as a protocol limitation:
  translation can support semantic behavior but cannot verify target-language
  fidelity.
- Paused the earlier 60-row rare-class enrichment recommendation. Its assumption
  of zero human wrong-language cases was no longer credible.
- Re-audited all 300 original responses against intended language using original
  text, translation language diagnostics, Unicode/script diagnostics, and
  targeted inspection. The annotator then independently reviewed all 300 and
  confirmed the resulting language judgments, finding no additional cases.
- Final complete language review:
  - 15 predominantly wrong-language responses;
  - 2 mixed-language responses;
  - 283 target-language responses.
- Preserved semantic behavior and language fidelity as separate dimensions.
  The 15 predominantly wrong-language rows take primary class
  `wrong_language`; the two mixed rows retain their semantic primary class and
  receive `language_fidelity = mixed`.
- Preserved the original submission log and v1 freeze. Exact before/after
  changes are in `human_language_amendments_v1.jsonl`; the complete all-300
  declaration is in `human_language_complete_review_v1.json`; current row-level
  analysis input is the v3 complete-language freeze.
- The corrected genuine-refusal estimate remains 2.1% (95% CI 0.9–3.2%). The
  corrected capability-failure estimate is 19.4% (16.2–22.6%). These remain
  preliminary one-coder estimates.
- Decided not to delay development work for the repeat block. Repeats will be
  completed after their scheduled unlock and incorporated as a reliability
  diagnostic, not as a prerequisite for exploratory surrogate development.
- Authorized local preparation—not paid execution—of a surrogate bake-off:
  - split by `prompt_id`, never individual response;
  - evaluation rows are locked and may never enter prompts or exemplar choice;
  - development rows may supply verified in-context examples;
  - compare zero-shot, balanced few-shot, error-targeted few-shot, and
    decomposed-decision configurations;
  - score genuine-refusal precision/recall, refusal–pivot confusion,
    capability/language validity, macro F1, schema failures, language/model
    heterogeneity, and cost;
  - overall accuracy alone is prohibited;
  - early results are configuration-development evidence, not final model
    selection, because ambiguous and technical classes remain sparse.
- Any OpenRouter or other provider call requires a new explicit authorization
  naming the exact model(s), logical payload SHA-256, prompt/configuration
  hashes, number of calls, and hard cumulative provider-cost ceiling.
- Froze surrogate bake-off v1 with 216 development and 84 evaluation rows, all
  grouped by `prompt_id`. Five configurations yield 420 model-neutral requests;
  logical payload SHA-256 is
  `42eb65c4da98631a00f4479a5810ff8b4da044105845631679e021d9e03caafb`.
- Verified listed OpenRouter prices on 2026-08-21. The recommended first paid
  experiment is the five-configuration sweep on `openai/gpt-5.6-luna` only:
  estimated listed-price cost $0.82 and proposed hard ceiling $2.00. No call is
  authorized merely by recording this recommendation.
- The user explicitly authorized the frozen 420-request Stage A payload with
  SHA-256 `42eb65c4da98631a00f4479a5810ff8b4da044105845631679e021d9e03caafb`
  for OpenRouter `openai/gpt-5.6-luna`, covering five configurations and 84
  evaluation responses, under a cumulative provider-cost ceiling of $2.00.
- Stage A completed all 420 requests on the first attempt with no schema or
  provider errors and no retries. OpenRouter was pinned to the OpenAI provider,
  fallbacks and reasoning were disabled, and actual provider cost was
  $0.36666348. The assembled result SHA-256 is
  `10b38be6091a37103f1fc8ef33f23090dadf30ef1a3e79e359fce72db6fed577`.
- The 22-shot error-targeted prompt led on primary accuracy (.881) and macro F1
  (.684), but the 7-shot joint prompt led on the refusal/pivot boundary:
  refusal precision 1.00, refusal F1 .75, pivot F1 .571, and zero direct
  refusal–pivot cross-confusion. The decomposed prompt detected no pivots and
  will not advance unchanged.
- No prompt was selected. Seven rows disagreed with all five configurations,
  and inspection indicates that several frozen one-coder labels or class
  precedence rules may be inconsistent with the codebook. The required next
  gate is blinded human adjudication that preserves the original labels and
  reports performance against both versions. After this error-driven review,
  the current 84 rows are an audit/development set, not the final untouched
  validation holdout.
- Added a blinded Streamlit adjudication workflow for all 18 responses missed
  by at least one configuration. The frozen review packet excludes the first
  human label and note, source-model identity, Luna predictions, and
  disagreement count. New decisions are written to a separate append-only,
  locked and fsynced JSONL log; no original annotation is overwritten.
- The coder completed all 18 Stage A disagreement tasks. Six primary labels
  changed: two ambiguous to incoherent/garbled, two genuine refusals to
  coherent answers, one coherent pivot to coherent answer, and one
  incoherent/garbled response to coherent answer. The immutable freeze has
  canonical adjudicated-label SHA-256
  `377d26e63b959dd366bd52bfeca983bbb5c50f4ff066b2a2f8b498e7374ec53f`.
- Clarified the blinding claim: the Streamlit interface hid previous labels and
  Luna outputs during submission, but the coder had already seen the
  disagreement casebook and preliminary assistant assessments. The rescore is
  measurement-development evidence, not independent blinded validation.
- Under adjudicated labels, the 22-shot prompt leads accuracy (.929), zero-shot
  leads observed-class macro F1 (.825) and pivot F1 (.667), and zero-/7-shot
  prompts have perfect precision and recall on the three remaining refusals.
  These counts are too small and selection-contaminated for final surrogate
  choice; no configuration was promoted.

## 2026-08-23

- Implemented a separate Stage B layer without changing the immutable Stage A
  payload or results. It reuses the exact Stage A zero-, 7-, and 22-shot system
  prompts and all 84 evaluation responses.
- Froze 252 model-neutral tasks and 504 provider requests for
  `google/gemini-3.5-flash-lite` and `anthropic/claude-haiku-4.5`. Exact
  provider-payload SHA-256 is
  `1626469888b4624c9a41f4f14247b9580a78f88fc13f9de019594144fd504c57`.
- Pinned Gemini to `google-ai-studio` and Haiku to `anthropic`, with no
  fallbacks. Gemini uses mandatory minimal reasoning excluded from returned
  data; Haiku reasoning is disabled and excluded. Both use strict structured
  JSON, temperature zero, a 500-token maximum, and at most four attempts.
- Verified standard first-party OpenRouter prices on 2026-08-23. The planning
  estimate is $5.646870, the single-attempt full-output reservation is
  $6.176070, and the proposed cumulative hard ceiling is $8.00. No cache
  discount is assumed.
- Implemented fail-closed authorization, resumable append-only execution, cost
  reservation, dual-label scoring, three-model pairwise agreement, and
  row-disagreement outputs.
- The user explicitly authorized the exact 504-request Stage B payload,
  Gemini through `google-ai-studio`, Haiku through `anthropic`, the frozen
  zero-/7-/22-shot prompts, disabled fallbacks, and an $8.00 cumulative ceiling.
- The initial execution completed 494 unique requests. Anthropic shared
  capacity produced 99 zero-cost rate-limit records and left ten Haiku
  zero-shot requests after the original four-attempt rule. A logged recovery
  permitted at most two additional attempts only for those ten IDs. It changed
  no payload, model, route, fallback, reasoning, or ceiling. All ten completed
  on their next serial attempt.
- Stage B completed 504/504 with 603 raw records for $7.02100588. The assembled
  result SHA-256 is
  `b4229e9faa54eaae203ef7c177b99e716ae4d1302fee90031aef7f54f69ba9ee`.
- Against exposure-limited adjudicated labels, Luna zero-shot leads observed
  macro F1 (.825) at $0.038/84 rows; Luna 22-shot leads accuracy (.929) and
  capability-failure F1 (.958) but misses both pivots. Gemini 7-shot is the
  strongest non-Luna configuration but does not improve the observed frontier;
  Haiku does not advance. Because the 84 rows include only three refusals and
  two pivots, this does not select a final surrogate.
- Advanced only Luna zero-shot and Luna 22-shot as deliberately contrasting
  candidates for a newly sampled untouched evaluation arm. The immediate next
  step is local enrichment simulation; no enrichment draw, translation,
  population labeling, or Stage 18 run is authorized.
- Completed a new local enrichment simulation from complete-language v3 and
  Stage B evidence. Stage B covers only 84 rows, so only its label-blind
  disagreement pattern is transferred to population features; its predictions
  are not represented as wall-to-wall annotations.
- Rejected the first internal v2 draft before acceptance because its learned
  technical and pivot strata had zero corresponding human cases and its prior
  fallback could manufacture apparent yield. The corrected v2 requires human
  overlap for every stratum and records zero fallback-allocated rows for all
  scenarios.
- Compared 150/250/400/600 annotation burdens without writing candidate IDs.
  Adopted a planning recommendation of 400 initial rows, with a frozen stopping
  target of 20 refusals, 15 pivots, 20 wrong-language cases, and 12 technical
  degenerations and a conditional stratum-specific extension to 600.
- At 400, posterior planning means are 63.4 refusals, 30.0 pivots, 55.4
  wrong-language outputs, 20.0 technical degenerations, and 112.0 incoherent
  outputs. These are not guaranteed yields, population estimates, or accepted
  intervals. Worst-case phase-two precision rows are explicitly proxies; the
  raw home contrast proxy is not the canonical standardized home estimand.
- No sample, translation payload, review packet, repeat analysis, provider call,
  or new human work was authorized or performed.

## 2026-08-24

- The user approved beginning the 400-row annotation wave. The local freeze
  uses the exact seven-stratum allocation recommended on 2026-08-23 and draws
  independent SRSWOR samples with seed 20260824 from the 136,886 responses not
  present in the completed 300-row pilot.
- Froze 400 unique response keys under
  `annotations/response_validity_human_v2/enrichment_wave_v2_400/`. The sample
  contains 45 wrong-language-signal, 65 technical-signal, 65 pivot-signal, 45
  genuine-refusal-signal, 45 incoherence-signal, 55 Stage-B-disagreement-signal,
  and 80 general-remainder rows.
- Reconstructed the original pilot inclusion probability for all population
  rows and verified it exactly against all 300 frozen first-wave records. The
  new artifact retains the conditional second-wave probability and declared
  sequential bookkeeping probability separately. Because routing strata were
  adaptively learned from phase-one labels, the latter is not yet accepted as
  an ordinary marginal Horvitz--Thompson inclusion probability. Stage 18 must
  predeclare either a conditional wave-two generalized-difference estimator
  with issue-aware cross-fitting/replication or use the original 300 for the
  design-weighted residual correction and the 400 only for development and
  untouched evaluation. Final variance estimation must match that choice; it
  must not treat the combined sample as one-shot SRS.
- Assigned prompt groups before translation or coding: 161 rows are development
  and 239 are untouched evaluation, with no `prompt_id` crossing the split.
  Split membership, routing signals, model identity, and machine predictions
  are absent from the translator and human-facing payloads.
- Created the 400-request literal-English translation payload with SHA-256
  `f91cf3d093a398df03561cb8906e1f45965da87fe76d804ffd2f679bf35d6785`.
  It uses the unchanged translation prompt SHA-256
  `427dcc37b06a03e5a4b01682ad1a090ba6436b8d56472c58627cf1b6d2deb9be`.
  Estimated volume is 585,740 input and 538,325 planned output tokens. No
  translation was authorized or sent and no provider call was made.
- The 2026-08-24 OpenRouter list-price estimate for Luna is $0.763138 without
  cache discounts. A $3.00 new-run ceiling is proposed to accommodate retries
  and conservative in-flight reservations; it is not yet authorized.
- Silent repeats remain deferred by prior user instruction and do not enter the
  enrichment wave. The existing 300 annotations and repeat packet are untouched.
- The user authorized the exact 400-row payload, unchanged literal-translation
  prompt, `openai/gpt-5.6-luna` through the OpenAI provider, disabled reasoning
  and fallbacks, and a $3.00 hard ceiling.
- The first execution stopped safely after 31 completions because an obsolete
  reservation multiplier, not actual spending, would have crossed the ceiling.
  The reservation was corrected to twice current list price. BYOK accounting
  was also repaired: OpenRouter returns platform `cost=0` for BYOK calls but
  supplies `upstream_inference_cost`; the latter is now always counted against
  the ceiling, including when reconstructing immutable prior records.
- Standard translation produced 388 straightforward completions. Twelve long
  outputs repeatedly failed structured JSON. Eight were assembled through
  lossless chunk fallback; four of those used a disclosed loop-aware partial
  rule that translates exact leading/trailing spans and preserves the omitted
  repeated middle as an uncertain source span. Four final rows were locally
  marked translation-unassessable after the hard guard activated; all four were
  independently detected repetition loops with repeated-trigram ratio above
  .90. This local action made no provider call and assigned no validity class.
- Final coverage is 400/400: 289 complete, 107 partial, and four unassessable
  translations. The append-only log contains 690 records: 400 accepted final
  records, 21 full-response errors, 154 successful chunks, 112 failed chunks,
  and three terminal unassessable chunks. Reconstructed upstream spend is
  $2.9852299, below the authorized $3.00 ceiling.
- Assembled a 400-row blinded Streamlit packet with SHA-256
  `bc8dfe97139085fa28051433ebc03f047c812839fb05570362e1037c96d36402`.
  It contains no model identity, routing stratum, development/evaluation split,
  machine prediction, or prior label. At assembly time its separate human label
  log did not yet exist; human annotation is now in progress in that isolated
  append-only log, so the original 300 submissions cannot be overwritten.
- Conducted an aggregate, outcome-informed checkpoint after the first 100
  unique enrichment labels. The first-100-line SHA-256 is
  `0343bc9f1c10e5cda8fc40241e16c4dbadd6e8811c56d36a4ca8838bfa04ee8f`.
  It contained one coherent pivot overall and none among 20 reviewed
  `pivot_signal` rows. This checkpoint was not prespecified and is not called
  preregistered or confirmatory.
- Clarified the workload rule without changing the codebook, frozen 400 IDs,
  ordering, or evaluation arm: complete all 400, but do not extend to 600
  solely because the original 15-pivot surrogate-development target is missed.
  After the 400-label freeze, any additional draw requires a new logged design
  decision based on principal-outcome support and expected scientific value.
  The original fixed increment remains preserved as provenance.
- After 200 contiguous review-order judgments were complete, reconsidered the
  workload because coherent pivot had already been demoted from a principal
  surrogate-selection outcome. The user approved proceeding with a formal
  200-row checkpoint rather than automatically coding all 400. This is an
  outcome-informed protocol amendment, not a prespecified stopping rule.
- Froze exactly `review_order <= 200` without modifying the append-only live
  log. The checkpoint contains 84 development and 116 protected-evaluation
  responses, all five languages and all 11 source models. Its canonical label
  SHA-256 is
  `a75dcb84ca3f146f1a816a0c0ac145c6f044c196266ddb0c8e71bdca91e4df6b`.
  Rows 201--400 remain an unreviewed reserve.
- The 200 labels comprise 95 coherent answers, 27 genuine refusals, 48
  incoherent/garbled outputs, 19 wrong-language outputs, seven technical
  degenerations and four coherent pivots. The protected 116 contain 54
  answers, 18 refusals, 42 aggregate capability failures and two pivots.
- Fixed the inferential role of the checkpoint: it is for surrogate development
  and protected evaluation only. It is not a prevalence sample and will not
  supply the DSL residual correction. The original known-probability 300-row
  sample supplies that correction, avoiding a population estimator that
  depends on this outcome-informed stopping decision.
- Reused, without alteration, the two Stage-B candidates that had advanced:
  Luna zero-shot and Luna 22-shot. Froze 232 OpenRouter/OpenAI provider
  requests over the 116 protected responses. Human outcomes are absent from
  every request. Logical payload SHA-256 is
  `bfec091bc9923c3287426d3fe0eb847a3cb4673f18ee54dc9228cb0073256c96`;
  provider payload SHA-256 is
  `b40db8fcab9a7617cd8216f728724357ae01af187fe7080dd2bace5963c772a9`.
- Reverified the live OpenRouter/OpenAI route price after the first local cost
  build exposed a stale three-day-old snapshot. At $0.20/M input and $1.20/M
  output, the corrected planning estimate is $0.9052336 and the one-attempt
  full-output reservation is $0.9831856. The proposed hard ceiling is $2.22.
  No cache discount is assumed. At this local-freeze step the payload was still
  unpaid and unauthorized, and no network call had been made.
- The user then exactly authorized the 232-request provider payload, Luna model,
  OpenAI-only route, zero-shot and 22-shot configurations, disabled reasoning
  and fallbacks, and a $2.22 hard ceiling. Authorization was recorded in the
  evaluation manifest before execution.
- Completed 232/232 calls with 232 schema-valid records and no retries. The
  assembled-results SHA-256 is
  `3cf5a1e781182a18f55707668993a009e06bc97910291837db378faf5d77b0bc`.
  OpenRouter reported platform `cost=0` because all calls were BYOK. The raw
  usage objects separately report upstream OpenAI inference charges totaling
  $0.20663445; the runner was corrected to count this field against the
  ceiling, including during resumable reconstruction. Raw records were not
  rewritten.
- A resumability check exposed that the generic JSONL reader's transient
  `_live_line` field could enter a reassembled result after restart. The runner
  now strips reader-only metadata before assembly. No provider request was
  repeated and the raw append-only log was unchanged; the stable assembled
  hash above is identical to the first complete assembly.
- Joined the predictions to the protected 116-row gold only after all outputs
  were assembled. The 22-shot prompt scored 0.8103 primary accuracy, 0.7143 genuine-
  refusal F1 and 0.8941 capability-failure F1; zero-shot scored 0.7759, 0.6897
  and 0.8861, respectively. Their equal-weight principal scores were 0.8062
  and 0.7839, so 22-shot advances provisionally. The prompts disagreed in
  correctness on 14 cases: 22-shot repaired nine zero-shot errors and introduced
  five errors.
- The winning candidate's refusal precision was 1.000 but recall only 0.5556:
  it detected ten of 18 human-coded refusals. The eight false negatives were
  four answers, two pivots and two incoherent outputs. Refusal recall was 7/7
  in English but only 3/11 across the four non-English languages; these cell
  counts are small and descriptive, but the pattern is material enough to stop
  population deployment.
- Reviewed the eight refusal false negatives against the frozen v2.1 boundary
  rules. All eight communicate inability or unwillingness to supply a requested
  personal stance or advocacy component and then provide background, balance or
  adjacent discussion. This is exactly the partial-compliance exception to the
  usual “disclaimer plus substantive answer” rule. The error diagnosis is used
  to specify a future prompt revision; it does not recode the human labels or
  alter the completed protected score.
- Language-fidelity accuracy is computed only where the human coder separately
  supplied a language-fidelity judgment. The enrichment form uses
  `not_separately_coded` for most non-wrong-language cases, so treating that
  sentinel as an ordinary class produced a meaningless 0.086 diagnostic. The
  scorer now excludes the sentinel; both prompts identify all ten separately
  human-coded wrong-language cases. This correction does not change primary-
  class metrics or the selected configuration.
- The user approved proceeding with the next annotation stage and asked to
  start the app. Opened exactly review orders 201--300 through
  `config/human_enrichment_review_gate_v1.json`; the first 200 remain frozen and
  orders 301--400 remain locked. The block contains 38 development and 62
  evaluation assignments, which remain hidden from the coder. The Streamlit
  page now caps the queue at 300, displays the frozen partial-compliance rule,
  and uses an exclusive file lock, duplicate guard, flush and `fsync` for every
  append. Before launch the live log contained 200 parse-valid, unique submitted
  records with SHA-256
  `cbbbd51c061f97faa4cdd789163239916ae3f771e2f3cec9749bb3ac042dcf3d`;
  the launch and UI tests did not change that hash.
- The coder completed the approved block. Verified 300 parse-valid, unique,
  submitted records under codebook v2.1, with contiguous review orders 1--300,
  no failed design joins, and no validation errors. The first 200 records match
  `checkpoint_200_v1` exactly; no order 301--400 record exists. The live log
  SHA-256 at completion is
  `8bda117ff862e5a423db6a4e365869660bf056106804d4446e7a27ca2d557ac8`.
  Created `storage_freeze_300_v1/` as a byte-identical hash-verified receipt
  before opening either the 38 new development labels or 62 new evaluation
  labels for analysis.
- Froze `refinement_v2/access_v1/` using a split-enforcing reader. It obtains
  membership from the label-blind design, extracts review IDs from raw JSONL
  without deserializing outcomes, and parses only the 122 development records.
  The 62 new evaluation records are represented by commitment SHA-256
  `9b724137af81cb79b0f227612852ca2043c05dedd32e269e1a39dc3e81b05b0e`;
  no evaluation row, class count or example entered a development artifact.
- Ran the frozen boolean-only support gate. Capability-failure support met its
  minimum of 30; genuine-refusal support did not meet 15 and non-English
  genuine-refusal support did not meet 10. The gate emitted no exact counts.
  `support_pass=false` therefore activated the prespecified fallback.
- Created `human_enrichment_review_gate_v2.json` and opened exactly review
  orders 301--400. The UI was tested to resume coder `Chris` at task 301 of
  400. The 300-row live log and storage-freeze hash remained
  `8bda117ff862e5a423db6a4e365869660bf056106804d4446e7a27ca2d557ac8`
  after the gate change and tests. No model API call was made.
- The coder completed review orders 301--400. Verified 400 submitted records,
  400 unique review IDs, no missing required fields, and one coder ID (`Chris`).
  The completed append-only log SHA-256 is
  `af6439b7019951357e9aa87020ff510b5b2cc3184b61439173e75e5b8af64d15`.
- Added the guarded `freeze-enrichment-storage-400` command and created
  `storage_freeze_400_v1/`. Its JSONL is byte-identical to the live log, and
  its first 300 lines match `storage_freeze_300_v1` exactly. The freeze
  validated contiguous review orders, design joins, submitted status, and
  codebook-v2.1 field rules. It emitted no class counts and made no network
  call.
- Froze `config/surrogate_refinement_support_gate_v2.json` before opening the
  added development outcomes. It applies the unchanged v1 minima to evaluation
  assignments in review orders 201--400: 15 genuine refusals, 10 non-English
  genuine refusals, and 30 capability failures. It forbids evaluation rows,
  outcome counts, examples, and provider transmission.
- Created `refinement_v2/access_v2/`. The split-enforcing reader emitted all
  161 development records, including the 39 added by the final review block.
  It emitted no evaluation outcome. The 123-case evaluation reserve is stored
  only as commitment SHA-256
  `4effcd2c6b5a1347842da3d60a1b296b9e49feb49c6c1eb656a128e40fcb97b3`;
  the earlier orders-201--300 commitment was reverified before expansion.
- Ran the version-2 boolean-only support check. Capability-failure support met
  its minimum. Overall genuine-refusal support and non-English genuine-refusal
  support did not meet their minima. No exact outcome count, row, label, or
  example was emitted. `support_pass=false` blocks a new provider comparison
  on this reserve and requires a newly sampled independent evaluation design.
- Built `refinement_v2/prompt_development_v1/` from development data only. It
  contains component-first zero-shot and balanced 10-example prompt drafts.
  The examples comprise one genuine refusal and one coherent answer in each of
  Arabic, Chinese, English, Hindi, and Russian. The drafts explicitly treat
  refusal of any requested substantive component as genuine refusal even when
  useful adjacent content follows, while preserving the negative rule that a
  generic disclaimer is not refusal when the requested task is still done.
  No protected row was read, no provider request or payload was created, and no
  network call was made.
- Reframed the next decision around estimand precision rather than stand-alone
  classifier certification. The failed 123-case support gate means that reserve
  cannot precisely score refusal recall; it does not imply that the human-
  referenced DSL estimands need another general annotation wave.
- Implemented the local `audit-human-estimand-precision` command. It represents
  every Stage-17 response-validity statistic as a response-level linear
  functional and applies the exact union-design pairwise variance to the
  probability-sampled human residual correction. Only the original 300 labels
  enter inference. The 161 exposed enrichment-development labels train a
  diagnostic local predictor; all 123 evaluation outcomes remain sealed.
- Fixed the pre-human Sol probability as the planning efficiency model rather
  than selecting a predictor by searching the 300 human outcomes. The local
  enrichment-only predictor is reported side by side and performs worse for
  genuine-refusal Brier loss; it is not selected for population inference.
- The audit finds adequate human-sampling precision for overall genuine refusal
  and all four paired genuine-refusal language contrasts. Overall capability
  failure is slightly wider than its planning target. Framing is underpowered.
  Standardized home fails the event-support rule in every jurisdiction: the
  original sample contributes zero human refusal events in CN, EU and India,
  one in MENA and two in the US.
- Stopped automatic general-purpose annotation. The next authorized analytical
  step is a no-provider provisional Stage 18 using the original 300 and frozen
  Sol probabilities, with full issue-level uncertainty. Any additional human
  sample must be justified by a result retained in advance as main—especially
  standardized home—and targeted to that estimand's English jurisdiction ×
  home/away support rather than repeating a generic enrichment workload.
- The user confirmed that the home component remains substantively important
  and deferred slant and moral-foundation denominator work. The latter now has
  an explicit restart specification in `DEFERRED_SLANT_MORAL_VALIDITY.md`; no
  content labels or figure changes are currently authorized.
- Added the local `plan-home-human-augmentation` command. It reconstructs the
  exact standardized-home response coefficients, forms five frozen leverage-
  by-risk bands within each non-EU jurisdiction × home/away arm, and applies
  anticipated Neyman allocation under two declared human-event calibrations.
  It reads no sealed outcome, emits no row ID and makes no network call.
- The resulting recommendation is 680 initial English selections: CN 190, EU
  120, India 80, MENA 170 and US 120. EU receives 60 simple-random selections
  per arm as a zero-event verification design. The first-wave gate requires at
  least five genuine refusals per arm outside EU and an estimand-specific 95%
  human-sampling half-width no greater than five percentage points.
- Froze a planning maximum of 1,250 selections under a conservative calibration
  (CN 330, EU 120, India 160, MENA 420, US 220). This is a cap, not an approved
  workload: only predeclared stratum increments may activate if the 680-wave
  gate fails. Existing human labels are matched after selection, so 680 is an
  upper bound on genuinely new first-wave annotation tasks.

### 2026-08-25: scalable annotation instrument takes priority over DSL

- The user confirmed that the subject-model roster will continue expanding and
  that DSL should not block accurate, reusable base annotation. The operational
  order is now: select a human-referenced annotation instrument; use it on
  versioned populations; audit new model rows with probability samples; then
  use DSL for final estimand correction and uncertainty.
- The user approved retiring the inadequate 123-case reserve as a pristine
  holdout. All 700 completed human labels may now be used for explicitly
  internal validation. The historical 161/123 accessor and SHA commitment
  remain preserved, but neither document nor result may call the 123 labels
  untouched after this decision. The next new-model probability sample will be
  the external validation set.
- Implemented `scalable_bakeoff.py` and guarded CLI commands for local build,
  cost freeze, exact authorization, resumable run and scoring. Five folds are
  assigned by whole `issue_id`. An evaluation issue cannot appear in its
  fold-specific 15-example bank.
- Froze two candidates (`component_zero_shot_v1` and
  `component_fewshot_15_v1`), two low-cost models (GPT-5.6 Luna and Gemini 3.5
  Flash-Lite), and three input modes (original only, original plus literal
  translation, and translation-only diagnostic). Translation-only is not
  production eligible because source-language fidelity is unassessable.
- The 700 human labels contain 63 genuine refusals, 162 incoherent/garbled
  responses, 61 wrong-language responses and 18 technical degenerations. The
  five evaluation folds contain 9--16 refusals and 43--53 capability failures.
  Genuine refusal and capability failure select the instrument; the 12 pivots
  remain diagnostic.
- Froze 4,200 logical requests and 8,400 provider requests. The provider
  payload SHA-256 is
  `bcc6725be78d86e0c74a8516ca5cd218ef53ef27c611843a6948bbc95c4ded83`.
  No human outcome appears in an evaluation query.
- Verified current non-batch route prices on 2026-08-25: Luna through OpenAI is
  $0.20/M input and $1.20/M output; Gemini through Google AI Studio is $0.30/M
  input and $2.50/M output. The earlier $0.10/$0.60 Luna figure was the batch
  route and was rejected because the runner uses chat completions.
- The exact cost freeze estimates $20.5187485 at planning output length and
  reserves $22.0072975 for one maximum-output attempt. A 10% plus 256-token
  input-overhead allowance is applied to every request. The suggested hard
  ceiling is $31.00. Provider fallbacks and reasoning output are disabled.
- No provider request was sent and no paid run was authorized. Authorization,
  if granted, must name the exact payload hash, 8,400 calls, both pinned routes,
  and the $31.00 ceiling.
- The first local manifest draft included the mutable decision-log hash as an
  input. Final QA identified the circularity: recording a freeze changes that
  same log. The unpaid artifacts were rebuilt with narrative documents excluded
  from scientific input hashes. Data, codebook, pricing and every payload byte
  were unchanged; the provider payload SHA remained exactly
  `bcc6725be78d86e0c74a8516ca5cd218ef53ef27c611843a6948bbc95c4ded83`.
- The home sample remains deferred until the paper roster is frozen. Retiring
  the classifier reserve does not give those labels a home-sampling inclusion
  probability; they can enter home inference only if independently selected by
  the future probability design.

### 2026-08-25: scalable bake-off executed; no candidate passed

- The user explicitly authorized the exact 8,400-request payload with SHA-256
  `bcc6725be78d86e0c74a8516ca5cd218ef53ef27c611843a6948bbc95c4ded83`,
  Luna pinned to OpenAI, Gemini pinned to Google AI Studio, fallbacks disabled,
  reasoning output excluded, and a $31 hard ceiling.
- The first execution inherited a stale shell `OPENROUTER_API_KEY` rather than
  the different current key in the repository `.env`. OpenRouter returned
  9,906 zero-cost `401 User not found` attempts. The run was stopped. No secret
  value was printed or stored in an artifact.
- Repaired the paid CLI boundary to invoke the repository's existing
  authoritative `.env` loader with override enabled. Local builders and scorers
  still do not load credentials. This changed transport setup only; the exact
  provider payload hash remained unchanged.
- After valid responses began, 58 Luna outputs were locally rejected because
  the post-response validator incorrectly required every capability-failure
  class to have `semantic_behavior=no_substantive_output`. That contradicted
  the component codebook: a coherent answer can still be wrong-language. The
  extra restriction was removed and regression-tested. The structured-output
  schema and provider payload already allowed the combination, so no request
  content changed.
- The resumable run completed all 8,400 request IDs. Results SHA-256 is
  `585bd509e8b09ed7b6c148f7324f064123e924c1759cbf0d296eaa59c4c2691e`.
  Actual provider cost was $12.54203861: $2.96793041 for Luna valid results,
  $9.52248070 for Gemini valid results, and $0.05162750 for paid invalid-output
  retries. Authentication failures cost $0.
- Final reconciliation found that the manifest retained its pre-run
  `network_call_made=false` value even though the immutable attempt ledger and
  run summary were complete. The runner now derives this flag from the attempt
  ledger. A network-free reconciliation reproduced the same 8,400 results,
  results hash, attempt count and cost, and set the manifest flag to `true`.
- Frozen scoring returned `no_candidate_passed`. All final requests were
  schema-valid, but every candidate failed the .80 refusal-recall gate. Gemini
  zero-shot also failed capability F1. Thresholds and gates were not changed.
- Luna zero-shot plus translation had the strongest hard refusal result:
  precision .8868, recall .7460, F1 .8103, and capability-failure F1 .9043.
  Luna zero-shot original-only had the lowest registered composite loss but
  recall .7302, so it could not be selected.
- Translation improved Luna zero-shot refusal precision and recall but did not
  make it promotable. Translation-only sharply degraded capability measurement,
  confirming that original source text is required. Fifteen examples generally
  raised precision while lowering recall.
- Of the 16 refusals missed by Luna zero-shot plus translation, 11 were implicit
  noncompliance, 14 were predicted as coherent answers, and five were Russian.
  A same-700 threshold diagnostic can barely cross the gates for Luna zero-shot,
  but is explicitly post hoc and cannot rescue the failed comparison.
- No candidate will be run across the population. The next design must select
  implicit/partial-refusal examples and thresholds inside the training side of
  each fold, then apply them once to the held-out issue fold. That refinement is
  a new payload requiring a new cost freeze and authorization.

### 2026-08-26: technical specification simplified and fold-nested refinement frozen

- Rewrote `RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md` around the active scientific
  pipeline rather than the chronology of experiments. Detailed Stage A/B
  comparisons, review checkpoints, failed support gates, provider incidents,
  and superseded prompts remain in this decision log and their dedicated result
  documents. They are no longer duplicated in the current runbook.
- Replaced the long response-validity section compiled into the technical PDF
  with `writeup/response_validity_current.tex`, a concise statement of outcome
  definitions, sample roles, instrument gates, the design-based estimator,
  estimand readiness, and expansion logic. The former chronological LaTeX block
  was removed from the source; its provenance remains available here, in the
  experiment reports, and in version control.
- Added `validate-response-validity-docs`. It reads the completed bake-off
  manifest, run summary, score summary, result hash, candidate table, request
  count, provider cost, ceiling, and network flag, then fails if the small set
  of repeated reader-facing numbers is stale.
- Built the unpaid v2 refinement around GPT-5.6 Luna, the original response and
  original-plus-translation modes, and five issue folds. Each fold receives one
  hard refusal, one boundary non-refusal, and one hard capability failure in
  every language from the other four folds. Twenty-three of twenty-five
  fold-specific refusal placements are implicit refusals.
- A pre-freeze leakage audit rejected the initial idea of selecting thresholds
  from new predictions on the other four folds: those prompts could themselves
  contain examples drawn from the eventual held-out fold. No provider call had
  been made. The authoritative design instead selects each threshold from the
  already-completed v1 Luna zero-shot predictions on the other four folds and
  transfers it unchanged to the refined prompt.
- A second pre-run diagnostic changed the no-solution threshold fallback from
  maximizing F1 to preserving the known .80 recall target and then maximizing
  precision. This occurred before authorization or model output. Both discarded
  local drafts were moved to `/private/tmp`; neither is a repository artifact or
  paid result.
- The authoritative provider payload contains 1,400 requests and has SHA-256
  `654f90724c940b8f325dd5e4c122bd1bf9e9af70eb4a3bcfc27c5b619e3a7e87`.
  Planning cost is $4.9516954 and the suggested hard ceiling is $7.50 under the
  frozen 2026-08-25 price snapshot. Fallbacks are disabled, reasoning output is
  excluded, `paid_run_authorized=false`, and `network_call_made=false`.
- Authorization, resumable execution, and scoring paths are implemented and
  fail closed. Synthetic perfect predictions pass the scorer; unconfirmed,
  wrong-hash, and execution-without-authorization tests fail as intended.

### 2026-08-26: refusal construct decomposed before another paid experiment

- A case-level review of the 16 apparent false negatives from Luna zero-shot
  plus translation found that the main problem was the target definition, not
  simply a weak prompt. Fourteen responses supplied a coherent, practically
  responsive answer after a persona or stance disclaimer; one argued the
  opposite position without refusing; and one was both wrong-language and an
  explicit refusal. The old mutually exclusive primary class suppressed the
  last combination.
- A separate search found 19 responses mentioning a knowledge cutoff, lack of
  browsing, real-time access, or similar epistemic limits. Two had been coded
  as refusals. Following the user's clarified rule, an epistemic limit is not a
  refusal unless the response separately withholds requested substantive
  political content.
- The construct is now decomposed in
  `config/response_validity_decomposed_v2_2.json`: task behavior, substantive
  refusal, stance disclaimer, epistemic limitation, language fidelity, and
  output quality are recorded separately. Thus a response may be both
  wrong-language and refusal, or contain a stance disclaimer and still be a
  functionally complete answer.
- Froze a blinded 158-response boundary audit under
  `annotations/response_validity_human_v2/decomposed_review_v2_2/`. It includes
  all 63 old human refusals, all 61 wrong-language cases, all 12 pivots, 26
  stance-screen cases, 20 epistemic-screen cases, and six Luna false positives;
  these sets overlap. The packet hides prior labels, Luna output, model,
  sampling source, fold, and selection reason.
- The 158 cases are a targeted construct and error audit, not a probability
  sample. They cannot produce population prevalence. The original 300-case
  probability sample retains that role; revised decisions for its selected
  cases can amend the outcome used in design-based correction.
- The previously frozen 1,400-request fold-nested payload remains unpaid and
  immutable but is superseded for current decision-making. Running it against
  the old target would optimize a definition we no longer endorse. No provider
  call or paid authorization occurred in this step.
- Added local build, assembly, and rescoring commands plus a Streamlit review
  page. Existing 8,400 predictions are never overwritten. After all 158 human
  decisions are stored, rescoring reads their component fields and reports an
  amended internal diagnostic; it cannot by itself certify a v2.2 student,
  because those predictions were elicited with the earlier codebook.
- After initially opting to review all 158 cases manually, the user requested
  a frontier OpenAI-model first pass followed by human review. A separate
  GPT-5.6 Sol payload was frozen under
  `annotations/response_validity_human_v2/decomposed_review_v2_2/frontier_sol_v2_2/`.
  It contains exactly 158 requests and exposes only the target language,
  English reference prompt, target-language prompt, original response, and
  literal English response translation. It hides the source model, all prior
  human and machine labels, sample role, fold, selection reason, and routing
  stratum.
- The Sol payload uses the decomposed v2.2 fields, temperature zero, strict
  JSON schema, a 600-token output ceiling, reasoning disabled and excluded,
  OpenRouter pinned to the OpenAI provider, and provider fallbacks disabled.
  Its provider payload SHA-256 is
  `bb97cc1acdfc486cb1aef11c32b5dd6ebc652f9c48462826622fc63a21cda0e1`.
- The 2026-08-26 OpenRouter promotional price snapshot is $2/M input and $10/M
  output. The exact payload contains an estimated 435,885 input tokens; the
  planning estimate is $1.21937 and the suggested hard ceiling is $2.50. No
  cache discount is assumed. At this point `paid_run_authorized=false` and
  `network_call_made=false`; execution requires a new exact user authorization.
- The user then authorized that exact hash, model route, request count and
  $2.50 ceiling. The resumable run completed all 158 labels. Results SHA-256 is
  `0da8ea50131b069e81113a3f9d14f4221df023263867dc5843da1664a7d1c91c`.
  Sol labelled 47 responses as substantive refusals (46 explicit, one
  implicit), 24 as containing stance disclaimers, 25 as containing epistemic
  limitations, and 60 as wrong-language. These are frontier-model proposals,
  not human truth or prevalence estimates.
- There were 159 provider attempts: one first response violated a cross-field
  rule by supplying a technical-failure subtype without technical degeneration
  and succeeded on retry. The initial runner retained provider usage only after
  label validation, so that billable invalid attempt was mistakenly recorded
  at zero cost. Completed responses report $1.2385306. The missing attempt had
  a prespecified maximum reserved cost of $0.011686, so total provider cost is
  bounded between $1.2385306 and $1.2502166, still well below authorization.
  The runner was repaired immediately to retain usage, response ID and cost
  before validation on any future invalid response. The immutable attempt log
  was not rewritten.
- Added a separate Streamlit accept-or-correct page. Human reviews append to
  `frontier_human_reviews.jsonl`; they never overwrite Sol output, the earlier
  700 labels, or the manual-first review log. Assembly fails if both review
  modes are populated, preventing silent mixing.
- Simplified that page at the user's request: all controls are now visibly
  prefilled with Sol's choices, including confidence and evidence span. The
  reviewer changes only fields they disagree with and submits once. Each record
  stores `agrees_with_sol_all_fields`, the exact `disagreed_fields`, and review
  mode `sol_prefilled_human_review`, so agreement is reconstructed from the
  submitted decisions rather than inferred from button clicks.
- The user stated, "I have reviewed and agree with all of these annotations."
  At that moment 18 decisions had been submitted through the prefilled form;
  all 18 were exact accepts. The remaining 140 Sol labels were appended under
  the same coder ID with review mode
  `explicit_bulk_affirmation_after_full_review` and the quoted confirmation
  statement. Existing interactive records were preserved byte-for-byte. The
  completed log has 158 unique response IDs, one coder ID, no changed fields,
  and SHA-256
  `bd3ef267d1deb591685b67fe7b1706680456f2ec7f83c13ef7e25d6d7f663eac`.
  This is 100% agreement in a model-assisted confirmation workflow, not an
  independent blinded inter-rater reliability estimate.
- The v2.2 assembly therefore contains 47 genuine refusals, 67 capability
  failures, 24 stance disclaimers, 25 epistemic limitations and 55 task
  noncompletions among the 158 targeted cases. Of the 63 old human refusals,
  45 remain refusals and 18 do not; one old pivot and one old wrong-language
  case are also substantive refusals under the overlapping v2.2 dimensions.
- Local rescoring of the immutable 8,400 predictions now finds six
  production-input configurations passing the old hard gates. The registered
  internal winner is Luna zero-shot using original text only: refusal precision
  .7627, recall .9574 and F1 .8491; capability-failure F1 is .9084. This reverses
  the earlier no-candidate result, but it is not external certification or a
  final promotion: only 158 targeted rows received v2.2 review, that review was
  Sol-assisted, and the candidate predictions were elicited under v2.1 rather
  than the decomposed codebook.
- A four-way decomposition shows why the result changed. For Luna zero-shot
  original-only, old gold plus the old primary-class rule gave recall .7302.
  Merely reading the existing component fields raised it only to .7460. Using
  amended v2.2 gold with the old prediction rule raised recall to .9149, and
  combining amended gold with the component rule raised it to .9574. The main
  reversal therefore comes from correcting the refusal construct, not from a
  post hoc relabelling of the same predictions.

### 2026-08-26: explicit v2.2 harmonization of all 700 human rows

- Added a local harmonization builder rather than silently treating all old
  labels as though they had been collected with v2.2. Each revised outcome has
  its own provenance field.
- The completed 158-row boundary audit is marked `direct_v2_2`. A further 538
  rows have non-ambiguous v2.1 primary classes that determine the two headline
  outcomes, genuine refusal and capability failure, and are marked
  `mapped_from_v2_1_primary_class`. This mapping does not manufacture stance,
  epistemic, or task-behavior judgments that the old form did not collect.
- Four old ambiguous responses remain unresolved. Three belong to the original
  300-case probability sample and therefore block a clean direct population
  estimate; one belongs to the enrichment sample and blocks a fully harmonized
  700-row evaluation set.
- Froze a blinded four-row packet and added the Streamlit page “Final
  harmonization review.” It uses the full decomposed v2.2 form and hides the old
  label, model, sample role and all machine predictions. New decisions append
  to `harmonization_reviews.jsonl`; no earlier human or model record is
  overwritten. No provider or network call was made.
- The initial harmonized table has SHA-256
  `cf6a585201d1dac7dbbaa167b6b2467a5dfb19d39ac2bb0350ba6dafc49f828b`;
  the four-row blinded packet has SHA-256
  `897ff7ee2a5cd2c5a286b5cee094609dba88da559528347f235eb8667c2fbe6a`.
- The reviewer completed all four blank, blinded forms under coder ID `Chris`.
  Three responses were incoherent/garbled capability failures; the fourth was
  a functionally complete, partly coherent answer. None was a genuine refusal.
  The append-only review log SHA-256 is
  `d0b86a37412909721142d2ab4c36dd556a880b4381d1b9eb2a0b1ea223dd2b8b`.
- The completed harmonized table contains 162 direct v2.2 rows, 538 mapped
  rows, and no unresolved headline outcomes. Its SHA-256 is
  `9dbec8ec107305d97326570db2730ab0e602c3d525ff602f8eff64563fc4e1ae`.
- Rescoring leaves Luna zero-shot original-only as the internal candidate.
  Refusal precision is .7627 and recall .9574; capability-failure F1 rises to
  .9150. This remains internal, model-assisted evidence rather than external
  certification.

### 2026-08-26: first direct human-weighted v2.2 diagnostic

- Implemented a local direct Horvitz--Thompson diagnostic using only the
  original 300-case probability sample. It reconstructs exact pairwise
  inclusion probabilities for the global, model-by-language and priority
  sample union. The 400 enrichment rows receive no population weight.
- Genuine-refusal prevalence is 1.83% (95% human-design interval 0.77--2.90%;
  13 events). Capability-failure prevalence is 20.34% (17.15--23.54%; 71
  events).
- Paired genuine-refusal language contrasts are all near zero but remain wider
  than the declared precision target. Capability-failure language contrasts
  are larger but have only one event in each English/negative arm.
- The standardized home estimand is unsupported: only two relevant refusal
  events occur, both in the US coefficient, and CN, EU, India and MENA have
  none. Zero estimates in those cells are zero-event failures, not null
  findings. The previous 680-selection plan remains a workload benchmark and
  must be recalculated after the subject-model roster is final.
- Output hashes are recorded in
  `annotations/response_validity_human_v2/stage18_preliminary_v2_2/manifest.json`.

### 2026-08-26: freeze the exact-v2.2 Luna readiness test

- The immediate target is accurate low-cost refusal annotation for the current
  11-model corpus; model expansion is deferred.
- The repository contains no untouched human-labelled holdout. All 700 reviewed
  cases were opened during codebook or instrument development, so they cannot
  honestly support external certification.
- We therefore adopted a two-stage sequence. First, test GPT-5.6 Luna against
  the 700 harmonized labels using the exact final v2.2 prompt. Compare
  original-only with original-plus-translation input. If neither passes, stop
  before requesting new human work. If one passes, draw and human-code a fresh
  blinded audit outside the 700-case corpus.
- The internal gates were frozen at schema success >= .995, genuine-refusal
  precision >= .90, genuine-refusal recall >= .90, capability-failure F1 >=
  .85, and language-specific refusal recall >= .70 wherever the reference set
  contains at least five refusal events.
- The frozen run contains 1,400 requests. Provider payload SHA-256:
  `a2edee4fb92ae9e515e18bb781312c8e855596d6130c79d8628b9116cda259cb`.
  Planning cost is $1.06427 and the proposed cumulative ceiling is $2.00.
  Preparation made no provider call and did not authorize spending.
- Full specification: `archive/2026-09-01_pre_rationalization/docs/LUNA_V22_INTERNAL_READINESS_TEST.md`.

### 2026-08-27: Luna readiness run fails schema coverage

- The authorized 1,400-request run completed for $1.17194434 under its $2.00
  cumulative ceiling. OpenRouter was pinned to the OpenAI provider; fallbacks
  and reasoning output were disabled.
- 1,292 requests passed local logical validation and 108 exhausted four
  attempts. Each input mode achieved only 92.29% schema success, below the
  frozen 99.5% gate. No mode was selected.
- 579 of 590 rejected attempts attached a technical-failure subtype to an
  output-quality value other than `technical_degeneration`. This exposed an
  annotation-instrument problem rather than a routing or JSON-format problem.
- Missingness is outcome-dependent: 51 of 54 incomplete cases in each arm are
  human capability failures. Completed-subset capability metrics are therefore
  not valid all-700 estimates.
- Completed-subset refusal diagnostics were nevertheless encouraging. The
  source-only arm had precision .939 and recall .979; the translation-assisted
  arm had precision .938 and recall .957. These are not promotion results.
- The v1 runner preserved error metadata and provider response IDs but not the
  rejected structured contents. A corrected runner must preserve raw content
  before logical validation. Any corrected v2.2.1 run requires a newly frozen
  payload, cost estimate and authorization.
- Full results: `docs/LUNA_V22_INTERNAL_READINESS_RESULTS.md`.

### 2026-08-27: freeze v2.3 repair instrument

- Versioned the repair as v2.3 rather than changing the frozen v2.2 codebook.
  V2.3 makes semantic output quality and technical failure independent;
  genuine refusal retains exactly the v2.2 definition.
- The repair packet includes all 69 unique responses involved in the 108 v2.2
  failures, under both source-only and source-plus-translation input. It has
  138 requests and is an instrument-repair test, not external validation.
- The runner now stores raw provider content and its SHA-256 before local
  logical validation, including rejected records.
- Provider-payload SHA-256:
  `9334a354f1c4b454c89b12a504c61af4d2408f3f35c511de2ee53d16dca03693`.
  Planning cost is $0.095212 and the proposed cumulative ceiling is $0.50.
  No provider call or paid authorization was made during preparation.

### 2026-08-27: complete v2.3 repair and patched diagnostic

- The explicitly authorized 138-request repair completed with 138 valid
  records, 100% schema success and $0.0611691 provider cost under the $0.50
  ceiling. Results SHA-256:
  `b6e62f3f03fa76638f13076845cd8413f3828646c72b89823cdef3996bbe2f63`.
- Both input modes correctly returned no refusal for all 69 repair responses.
  Each identified all 66 human capability failures and added three capability
  false positives within this deliberately failure-heavy set.
- The patched internal diagnostic uses 1,292 immutable valid v2.2 predictions
  and v2.3 only for the 108 missing predictions. It contains 700 cases per mode
  and does not pretend to be a uniform v2.3 run.
- Source response only achieves refusal precision .939, recall .979 and F1
  .958; translation-assisted achieves .938, .957 and .947. Capability F1 is
  .861 and .878 respectively. Both pass internal gates. The frozen ordering
  selects source response only on higher refusal F1.
- Luna is now an internal candidate, not externally certified. The next
  scientific step is a fresh probability-based external audit outside the 700
  development cases, with Sol as an independent reference annotator and a
  blinded human verification phase rather than treating Sol as automatic
  truth.

### 2026-08-27: consolidate the reader-facing workflow

- Replaced the reader-facing response-validity account with one current
  sequence: original measurement problem; 300-case probability sample; 400-case
  enrichment sample; 162 direct and 538 mapped harmonized labels; exact-v2.2
  Luna test; v2.3 schema repair; patched internal diagnostic; external audit.
- Moved the pre-v2.3 narrative to
  `docs/archive/RESPONSE_VALIDITY_PRE_V23_HISTORY.md`. Historical dual-judge,
  Sol-reference, Stage A/B and refinement experiments remain auditable through
  frozen manifests but no longer appear as current run instructions.
- Removed the abandoned Sol-machine-reference correction from the prospective
  canonical analysis description. `canon_012` remains the accepted release;
  no human-referenced corrected analysis is canonical yet.
- Updated the technical PDF to use the same current sequence and retained the
  preceding response-validity section under `writeup/archive/`.

### 2026-08-27: simulate the external audit before selecting cases

- Simulated four candidate probability designs on the 136,486 responses that
  are outside all 700 existing human-labelled cases. The simulation wrote only
  aggregate tables: it selected no IDs, created no provider payload and made no
  network call.
- Each candidate combines an independent simple random draw within every one
  of the 55 model-by-language cells with an independent simple random draw
  within the seven pre-specified routing strata. A response's known first-phase
  inclusion probability is
  `1 - (1 - p_cell) * (1 - p_routing)`.
- The recommended design draws 10 responses per model-by-language cell and
  makes 650 additional risk-stratified draws. Overlap gives about 1,197 unique
  responses rather than 1,200 exactly. Planning simulations project about 146
  genuine refusals (90% range 116--177), 415 capability failures (384--447),
  2,395 independent Luna-plus-Sol annotations, and 506 human reviews under the
  recommended second-phase probabilities.
- Human review would include every model-identified refusal, every Luna--Sol
  headline disagreement, every schema failure and every low-confidence label;
  it would additionally sample 50% of capability-positive agreements and 10%
  of ordinary agreements. Sol remains an independent strong annotator, not
  automatic ground truth.
- The aggregate recommendation is frozen in
  `annotations/response_validity_human_v2/external_audit_planning_v1/` with
  input and output hashes. Identical reruns reuse the verified files rather
  than overwriting them. The design is recommended but not yet approved or
  drawn.

### 2026-08-27: approve and freeze the realized external audit

- The user approved the recommended audit design and local payload freeze. The
  approval was interpreted narrowly: it did not authorize an API call or any
  provider spending.
- Seed 20260827 produced exactly 550 model-by-language component selections and
  650 routing-stratum component selections. Three responses entered both
  components, leaving 1,197 unique external responses.
- Every selected response retains both component probabilities, its union
  probability and inverse-probability weight. All 700 instrument-development
  cases remain excluded.
- The paired payloads each contain 1,197 requests under the v2.3 instrument.
  Luna and Sol see the intended language, English reference prompt,
  target-language prompt and source response. They do not receive source-model
  metadata, prior labels, routing information, sampling reasons or each
  other's decisions.
- Exact token counting gives 2,664,980 estimated input tokens for each model.
  At prices checked on 2026-08-27, planned cost is $0.82 for Luna and $7.72 for
  Sol ($8.54 combined). The combined single-attempt reservation is $12.57 and
  the proposed hard ceiling is $16.
- Luna payload SHA-256:
  `6d4f26dc9d2d668d5875720b3d008e5ac20b6fe4940dc6db74392349a7affee4`.
  Sol payload SHA-256:
  `d60874cfe3d52c07644be37f36fa9da8891b68a0c42ab1d65da7e07cbc59f8b6`.
  Both remain unpaid and untransmitted.

### 2026-08-27: complete the paired external model run

- The user explicitly authorized both frozen payload hashes, the OpenAI
  provider route, disabled reasoning and fallbacks, and one cumulative $16
  hard ceiling. The exact authorization is retained in
  `external_audit_v1/authorization.json`.
- The resumable runner completed 1,197 Luna and 1,197 Sol final records. It
  made 2,395 billable attempts because one Luna response identified a refusal
  without the required evidence span. That invalid raw response and its cost
  were appended before the unchanged retry succeeded.
- Schema success over final records is 100%. Provider-reported cost is
  $5.50237871: $0.51783881 for Luna and $4.98453990 for Sol. There is no
  unreconciled cost reserve. The attempts SHA-256 is
  `d4427a649186b36750b42c674cd69ac986fe90f8e60f6187c9025cbfd12e1313`.
- Final Luna results SHA-256:
  `841749f71393dd445b9b6f51815fde3e5598a2130682ce54016790b3efef0560`.
  Final Sol results SHA-256:
  `ac247e179d770ff15fdeb515f77f6d0997953a6a79ec41c27c6b91df42d1d32c`.
- Luna identifies 115 genuine refusals and Sol 114, with nine disagreements.
  Luna identifies 491 capability failures and Sol 383, with 124
  disagreements. These differences are machine comparisons, not estimates of
  either model's accuracy.
- The frozen pre-draw phase-two rules yield 229 certainty rows, 374
  capability-positive agreements eligible at probability .50, and 594
  ordinary agreements eligible at probability .10. Expected human workload is
  475.4 before drawing the second phase.

### 2026-08-27: freeze and translate the external human phase

- The user approved the predeclared second-phase probabilities. Seed 20260828
  was accepted without search and realized 458 reviews: all 229 priority rows,
  173 of 374 capability-positive agreements and 56 of 594 ordinary agreements.
  Each row retains its first-stage probability, human-review probability,
  combined probability and inverse weight.
- Forty-eight English rows use their original response as the identity
  translation. The user separately authorized the exact 410-row non-English
  payload and prompt hashes, OpenAI-only Luna routing, disabled reasoning and
  fallbacks, and a cumulative $3 ceiling.
- Luna produced 406 valid full-response translations. Four rows each exhausted
  six unchanged attempts because the structured JSON ended mid-string. The
  failed raw responses and their costs were preserved. The user then explicitly
  authorized deterministic lossless chunking for exactly those four IDs under
  the same cumulative ceiling.
- The chunk runner retained the complete original, split only source text,
  recursively subdivided failing chunks and appended every result. The final
  raw log contains 410 final `ok` records, 24 exhausted full-response errors,
  56 successful chunk records and 37 failed chunk records. Total provider cost
  was $2.08916954.
- The assembler verified exact ID and source-hash coverage and wrote 458 unique
  blinded tasks. Translation status is complete for 328 and partial for 130;
  this flag concerns translation coverage, not response validity. The full
  original is always visible.
- Raw translation SHA-256:
  `445ab99eeda7db4d8d03eaac2928a4efdeba1446cc7a60f575913fd7a59d7745`.
  Assembled translations SHA-256:
  `35464fe645ed899de290321c3cadae300f44026f26ed53395864dc7d87f0c62a`.
  Human review packet SHA-256:
  `28c15bc13b857a38d0ecb01442d3cfdfe38bab576ee8a000e7afb59648276c66`.
- The external v2.3 Streamlit page is now open. It hides model, routing and both
  machine labels and writes append-only human decisions with a file lock,
  duplicate guard, flush and `fsync`.

### 2026-08-27: expose the existing Sol labels as a separate reference track

- The user preferred to use GPT-5.6 Sol provisionally while deferring human
  review. No new Sol run was needed: the completed external audit already
  contains final v2.3 Sol labels for every one of the selected 458 cases.
- The selected Sol rows were extracted locally to
  `human_phase2_v1/sol_reference_labels.parquet`, with explicit
  `annotation_source=machine_reference`, `annotator_id=openai/gpt-5.6-sol`,
  codebook version and complete status. SHA-256:
  `cde053e4ac52742004187a94861e9dabccc2cd544f2dec77fe58381783743e74`.
- The read-only `External Sol reference` Streamlit page displays these labels.
  It does not write a human annotation, and the blinded human page does not
  reveal them. Sol may support provisional analyses, but final claims about
  annotation accuracy still require an independent human reference.

### 2026-08-27: calculate design-weighted Luna performance against Sol

- Used all 1,197 first-stage external cases, not the 458-case human-review
  subsample. Luna and Sol had already annotated every first-stage case, so this
  was a local calculation with no provider call or additional cost.
- Treated Sol as an independent machine reference, never as human gold. The
  result is a provisional scalability test rather than external human
  certification.
- Recovered each response's exact first-stage probability from the union of
  the independent model--language SRSWOR and routing-stratum SRSWOR draws.
  Estimated confusion totals by Horvitz--Thompson weighting and ratio metrics
  by Hájek estimation. Used exact second-order union inclusion probabilities
  for Taylor-linearized uncertainty and finite-population correction.
- Luna's design-weighted genuine-refusal precision is .9469 (95% CI
  [.8581, .9814]), recall .9718 [.9283, .9892], and F1 .9592
  [.9133, .9813]. All provisional refusal gates pass against Sol.
- Capability-failure precision is .6187, recall .9637 and F1 .7536
  [.7162, .7876]. The .85 capability-F1 gate fails. Wrong-language precision
  is especially weak at .3124 despite recall of .9092.
- Retained unweighted metrics as an enriched difficult-case stress test and
  wrote separate overall, model and language estimates. The current
  recommendation is therefore to continue considering Luna for scalable
  genuine-refusal annotation, while keeping capability-failure measurement on
  a separate validation/improvement track.
- Implementation:
  `src/refusal_audit/response_validity/external_sol_reference_evaluation.py`.
  Frozen outputs:
  `annotations/response_validity_human_v2/external_audit_v1/sol_reference_evaluation_v1/`.
  Regression tests:
  `tests/test_external_sol_reference_evaluation.py`.

### 2026-08-28: forensically inspect the nine refusal disagreements

- Reviewed the original response, literal translation, both decomposed label
  sets, evidence spans and notes against the frozen v2.3 rules.
- Recommended eight non-refusals and one genuine implicit refusal. Luna agrees
  with three recommendations and Sol with six. This is an instrument audit by
  Codex, not independent human gold, and it does not overwrite either source.
- Four Luna positives were clear knowledge-cutoff or insufficient-information
  cases; one additional Luna positive was a coherent pivot without communicated
  withholding. Three Sol positives were stance/uncertainty responses that still
  supplied a functional assessment. The one recommended refusal explicitly
  substituted general principles instead of the requested specific assessment.
- The cases do not justify a new codebook class. They support retaining and
  foregrounding the existing epistemic-limitation, functional-completion and
  communicated-withholding rules.
- Full review: `archive/2026-09-01_pre_rationalization/docs/EXTERNAL_REFUSAL_DISAGREEMENT_REVIEW.md`. Structured
  recommendations:
  `external_audit_v1/sol_reference_evaluation_v1/refusal_disagreement_forensic_review.csv`.
- Added a separate visible-label Streamlit page for the user's own adjudication.
  It displays both original decomposed labels but hides the Codex forensic
  recommendation. User choices append durably to
  `human_refusal_disagreement_choices.jsonl`; no source label or blinded human
  record is modified.

### 2026-08-28: complete the visible-label disagreement review

- The user completed all nine rows. The append-only log contains nine valid,
  unique submissions: six choices for Sol, two for Luna and one uncertain.
  Eight cases have a final binary decision: five refusal and three non-refusal.
  Seven choices are high confidence and two medium confidence.
- On the eight decided rows, the user's choice agrees with Sol six times, Luna
  twice and the earlier Codex forensic recommendation four times. This reveals
  a substantive boundary question about whether withholding the exact requested
  opinion or advocacy counts as refusal when substantial background or a
  qualified assessment follows.
- During live browser QA, the assistant entered the temporary coder ID
  `live-render-check`; it remained in the handed-off tab and was attached to the
  user's submissions. The source log is intact. The local assembler records a
  non-destructive provenance correction identifying these nine as the user's
  completed review and explicitly states that no QA submission was made.
- The review is unblinded and conditional on machine disagreement. It is not
  the final probability-sampled human accuracy study and is not used to relabel
  the 1,188 machine agreements.
- Validated summary:
  `sol_reference_evaluation_v1/human_refusal_disagreement_review_summary.json`.
  Case table:
  `sol_reference_evaluation_v1/human_refusal_disagreement_review_cases.csv`.
  Assembly code:
  `src/refusal_audit/response_validity/external_disagreement_human_review.py`.

### 2026-08-30: freeze the refusal-boundary consistency review

- Before changing the v2.3 codebook, isolated every external response that Luna
  labelled a genuine refusal while also flagging an epistemic limitation or a
  stance disclaimer. This exact rule produces 24 cases.
- Four of the 24 are refusal disagreements already decided in the completed
  nine-case visible-label review. Their final binary decisions are carried
  forward verbatim; the source append-only log is not edited and the reviewer
  is not asked to repeat them.
- The remaining 20 cases form a new visible-label Streamlit queue. The queue
  asks whether the response is genuinely refusing and which boundary rule is
  decisive: withholding the requested task, substituting safer/general
  material, pure epistemic limitation, or a disclaimer followed by functional
  completion. It also records confidence and an optional short note.
- The 24 cases cover Arabic, English, Hindi, Russian and Chinese. They are a
  targeted instrument audit selected using Luna's labels. They cannot estimate
  refusal prevalence or population accuracy and do not replace the blinded
  probability-sampled human validation.
- Frozen manifest and review assets:
  `external_audit_v1/sol_reference_evaluation_v1/refusal_boundary_consistency_v1/`.
  Builder/assembler:
  `src/refusal_audit/response_validity/refusal_boundary_consistency.py`.
  Review page:
  `archive/2026-09-01_pre_rationalization/interactive/pages/10_Refusal_boundary_consistency_review.py`.
- No provider call was made. The v2.3 codebook remains unchanged until the 20
  new decisions have been assembled and the boundary pattern reviewed.

### 2026-08-31: complete the refusal-boundary consistency review

- The user completed all 20 new cases under coder ID `Chris`. The append-only
  log has 20 unique submissions bound to the frozen packet hash: 16 refusal,
  two non-refusal and two uncertain. Sixteen decisions are high confidence and
  four medium confidence.
- Combined with the four carried-forward decisions, the targeted audit contains
  24 cases: 22 have a binary decision, of which 17 are refusals and five are
  non-refusals; two remain uncertain.
- The result rules out a simplistic correction that treats every epistemic
  limitation or stance disclaimer as non-refusal. Fifteen newly reviewed cases
  were refusals because the response withheld the requested opinion, judgment,
  advocacy or task; one refused by substituting safer/general material. The two
  clear new non-refusals were a pure epistemic limitation and a disclaimer
  followed by a functionally complete answer.
- The operative distinction remains: limitation/disclaimer flags are
  descriptive and can coexist with refusal, but they do not establish refusal.
  `genuine_refusal` requires separate evidence that the requested task was
  withheld or replaced. The two uncertain cases show why this must be judged
  from functional behavior rather than trigger phrases.
- Validated summary: `refusal_boundary_consistency_v1/review_summary.json`.
  Case-level assembly:
  `refusal_boundary_consistency_v1/assembled_boundary_decisions.csv`. Neither
  source annotation log was altered and no provider call was made.

### 2026-08-31: freeze the prospective Luna v2.4 evaluation

- Created codebook v2.4 as a prospective wording revision. It changes no field,
  enum, schema or derived outcome. It makes the functional rule explicit:
  epistemic limitations and stance disclaimers are recorded independently;
  refusal requires separate evidence that the exact requested political task
  was withheld or replaced. Four synthetic patterns illustrate the boundary
  without copying a reviewed response into the prompt.
- Frozen one Luna request for each of the existing 1,197 external responses.
  The 24 cases used to develop the clarification are marked as development
  diagnostics. The other 1,173 form the protected non-regression comparison
  against the already-frozen Sol v2.3 machine reference. No reference label,
  human decision, sampling stratum, inclusion probability or evaluation role
  enters the provider payload.
- This comparison cannot yield final human-validated accuracy because the
  blinded external human phase remains incomplete. It can test whether v2.4
  improves the 24-case boundary diagnostic without degrading Luna--Sol
  agreement on the separate 1,173 cases.
- The exact 1,197-request payload has SHA-256
  `9f2b84d5e26913aeadfee5d4294bfac5029b6fde5133afe3afbe4ffcf7495ca5`.
  At the OpenAI-provider price verified on 2026-08-31 ($0.20/M input and
  $1.20/M output), estimated cost is $0.8966, single-attempt maximum reservation
  is $1.3276, and the proposed hard ceiling is $2.00.
- Nothing has been authorized or sent. Builder, guarded runner and scorer:
  `src/refusal_audit/response_validity/luna_v24_evaluation.py`. Frozen files:
  `external_audit_v1/luna_v2_4_evaluation_v1/`.

### 2026-08-31: run and score the Luna v2.4 evaluation

- The user authorized the exact 1,197-request payload with SHA-256
  `9f2b84d5e26913aeadfee5d4294bfac5029b6fde5133afe3afbe4ffcf7495ca5`
  under a $2 hard ceiling. All requests used `openai/gpt-5.6-luna` through the
  OpenAI provider with temperature zero, reasoning disabled and fallbacks
  disabled.
- All 1,197 requests returned valid structured annotations. The schema-success
  rate was 100% and actual provider cost was $0.53063. Raw returned content and
  its hash were stored before local validation; the append-only attempts file
  also retains the one failed attempt that was retried successfully.
- On the 22 decided boundary-development cases, v2.4 improved accuracy against
  the user's visible-label decisions from 77.3% to 90.9% and refusal F1 from
  .872 to .944. It correctly changed three prior Luna false positives involving
  knowledge or future-event limitations. Two false positives remained.
- On the separate 1,173 cases, using the frozen Sol v2.3 labels as a machine
  reference, refusal recall rose from .957 to 1.000 but precision fell from
  .989 to .839; F1 fell from .973 to .913 and failed the predeclared .01
  non-inferiority margin. Capability-failure F1 rose from .861 to .881.
- V2.4 changed 21 protected refusal decisions, all from negative to positive.
  It disagrees with frozen Sol v2.3 on 18 refusal decisions. Seventeen are newly
  recognized cases in which the response withheld an opinion, judgment or
  persuasive task while supplying background, balance, uncertainty or general
  principles; one disagreement already existed under v2.3.
- The protected result does not by itself show that v2.4 is less accurate. The
  reference model applied v2.3, while v2.4 deliberately changed the boundary
  those 18 cases occupy. Calling all 18 false positives would assume the old
  definition rather than test the revision. V2.4 therefore remains a candidate,
  not the production codebook, pending a same-codebook reference or human test.
- Case inventories and metrics are under
  `external_audit_v1/luna_v2_4_evaluation_v1/`. Scoring made no provider call.

### 2026-08-31: freeze the same-codebook Sol v2.4 comparison

- Frozen 1,197 Sol requests using byte-identical system/user messages, schema,
  response order and evaluation partition as the completed Luna v2.4 run. Only
  the model ID and provider-request ID differ.
- The payload contains no Luna result, earlier Sol result, human decision,
  evaluation role, routing stratum or inclusion probability. It pins
  `openai/gpt-5.6-sol` to the OpenAI provider, disables reasoning and fallbacks,
  and uses temperature zero with a 500-token structured-output limit.
- OpenRouter's versioned model page still reported the 50%-discounted $2/M
  input and $10/M output prices on 2026-08-31. For 3,046,823 estimated input
  tokens, planning cost is $8.48765, maximum one-attempt reservation is
  $12.07865, and the proposed hard ceiling is $15.50.
- Exact payload SHA-256:
  `c9d444ee0416f68507107379ab6a52bda2e7beef429422eb5d3f99ccbd287696`.
  No provider call has been authorized or made.

### 2026-08-31: run and score the same-codebook Sol v2.4 comparison

- The user authorized the exact Sol payload with SHA-256
  `c9d444ee0416f68507107379ab6a52bda2e7beef429422eb5d3f99ccbd287696`
  under a $15.50 ceiling. All 1,197 requests completed with valid structured
  output, no incomplete cases and no failed attempts. Actual provider cost was
  $5.12657. Raw content and hashes were persisted before validation.
- On the 1,173 protected cases, Luna v2.4 agrees with Sol v2.4 on 98.72% of
  binary refusal decisions. Treating Sol as a machine reference gives Luna
  precision .938, recall .929 and F1 .933. The 15 disagreements are balanced:
  seven Luna-only positives and eight Sol-only positives. This does not show a
  systematic tendency for Luna alone to overclassify refusal under v2.4.
- The two models identify almost identical numbers of protected refusals: 112
  for Luna and 113 for Sol. Capability-failure F1 is .887 using Sol as the
  reference; capability measurement remains weaker than refusal measurement.
- Against the 22 decided human boundary-development labels, Luna accuracy is
  90.9% and F1 .944; Sol accuracy is 86.4% and F1 .914. These cases shaped the
  prompt and therefore remain development diagnostics rather than an external
  human accuracy estimate.
- The 15 protected disagreements cluster around the intended boundary: whether
  a personal-opinion disclaimer plus balanced background is functionally
  complete; whether substituting an opposite position or neutral summary
  communicates withholding; and whether future-event limitations are purely
  epistemic. The disagreements are preserved case by case in
  `sol_v2_4_evaluation_v1/same_codebook_refusal_disagreements.csv`.
- This is strong same-codebook machine-reference evidence for Luna v2.4, not a
  final claim of human accuracy. Independent probability-sampled human coding
  is still required for a defensible absolute accuracy estimate.

## Pending decisions

- Use the 458 existing Sol labels for explicitly provisional analysis. Complete
  blinded external human review later before treating any annotator's accuracy
  as human-validated.
- Decide whether the external audit supplies enough genuine-refusal support for
  the standardized home estimand. If not, simulate a separate targeted
  probability augmentation before drawing any home-review rows.
- The 36 delayed repeats remain optional within-coder reliability evidence.
  They are deliberately deferred and do not block external validation.
- Model expansion remains deferred. Once it occurs, the external audit and
  calibration rules must be extended prospectively rather than assuming that
  current-corpus accuracy transfers to new models.

### 2026-08-31: freeze the API-only v2.4 student-model bake-off

- The user requested a current bake-off against Luna and removed EuroLLM and
  Apertus. The final candidate field is Gemini 3.5 Flash-Lite, Claude Haiku
  4.5, Kimi K3, Qwen3.8 2.4T-A95B, GLM-5.3, DeepSeek V4 Pro 0813, MiniMax M3,
  and Qwen3.8 27B. Luna and Sol are reused from their completed v2.4 runs.
- Exact OpenRouter provider tags are pinned and fallbacks are disabled. The
  treatment therefore includes the recorded provider and quantization rather
  than an uncontrolled routing mixture. GLM-5.3 uses the lowest available
  hidden reasoning effort because its reasoning cannot be disabled; every
  other candidate requests reasoning disabled and all routes exclude returned
  reasoning.
- One maximum payload contains 9,576 possible requests. The runner first sends
  the same 50 cases to each candidate: 15 protected Luna-Sol refusal
  disagreements, ten capability-failure diagnostics balanced by language, ten
  v2.4 boundary-development diagnostics, and 15 ordinary controls balanced by
  language. A route needs 49 valid records to continue to its other 1,147
  cases. There are at most two unchanged attempts per request.
- Maximum payload SHA-256:
  `4bc54f501f5f8f4867a81ca1ccb4e3058800a0a6ff9e0e8a44b89af966ac7dd1`.
  Planning cost is $38.91408, the single-attempt maximum reservation is
  $53.41095, and the proposed hard ceiling is $80.50. No provider call has
  been authorized or made.
- Design and implementation are in
  `archive/2026-09-01_pre_rationalization/docs/RESPONSE_VALIDITY_MODEL_BAKEOFF_V2.md` and
  `src/refusal_audit/response_validity/model_bakeoff_v2.py`. Frozen artifacts
  are under `external_audit_v1/model_bakeoff_v2/`.

### 2026-08-31: run and score the API-only v2.4 model bake-off

- The user authorized the exact maximum payload under its $80.50 ceiling. The
  run cost $23.66423 and preserved 5,567 append-only attempt records, including
  zero-cost request rejections and every paid invalid or rate-limited attempt.
  The reconciled attempts SHA-256 is
  `49bac4dbecd74e879b55ce46d09306655ac0d84376e366e07ea26d1adf6fb39b`;
  4,734 valid final records have SHA-256
  `c86188161189b3fbb9a894dbc343df6b8b45fe927716cf0e544070727bddc419`.
- Haiku, Kimi K3, DeepSeek V4 Pro and MiniMax M3 passed the 49/50 preflight.
  Gemini Flash-Lite and Qwen3.8 2.4T were rejected because their pinned routes
  required reasoning; GLM-5.3 reached 45/50 under upstream rate limits; and
  Qwen3.8 27B reached 48/50 because two records repeatedly violated a frozen
  semantic consistency rule.
- Kimi, DeepSeek and MiniMax each returned 1,196/1,197 valid records and passed
  the full .995 coverage gate. Haiku returned 1,146/1,197 and failed coverage
  after upstream rate limits exhausted the two-attempt allowance.
- Against Sol v2.4 on the non-development cases, refusal F1 is .824 for Kimi,
  .799 for DeepSeek and .784 for MiniMax, versus .933 for Luna. Their precision
  is .714, .681 and .704 respectively. Paired issue-cluster bootstrap intervals
  put every F1 difference from Luna well below the -.02 non-inferiority margin.
  No alternative passes; Luna remains the student.
- Kimi has a strong secondary capability-failure result (precision .912,
  recall .969, F1 .939), but this does not overcome its refusal overcalling or
  justify promotion. Full results are in
  `archive/2026-09-01_pre_rationalization/docs/RESPONSE_VALIDITY_MODEL_BAKEOFF_V2_RESULTS.md`.

### 2026-08-31: freeze the fresh Luna v2.4 human-certification sample

- Final human accuracy will not be estimated from material used to develop the
  codebook or select the student model. We exclude all 700 development
  responses and all 1,197 responses in the external/model-bakeoff sample,
  leaving 135,289 untouched responses.
- Seed 20260831 independently drew ten cases from each of 55 model-language
  cells and 650 cases across the seven frozen routing strata. Four cases
  overlapped, producing 1,196 unique Phase 1 responses. Exact union inclusion
  probabilities and inverse weights are stored per row.
- The frozen Luna v2.4 payload contains only the target-language prompt, English
  reference prompt and original response. It contains no prior annotation,
  model identity, sampling variable, human label or machine-reference label.
- Payload SHA-256:
  `ad29e0ed09772d5d1cd55d5cfaebebd9d4b47c84d6c3f6af3cc67ea94a978506`.
  Expected cost is $0.91; the proposed hard ceiling is $2.50. No provider call
  has yet been authorized or made.
- Phase 2 will be frozen only after Luna completes. It will review priority
  cases with certainty and probability-sample lower-risk negatives, preserving
  the product of both inclusion probabilities for design-weighted accuracy.

### 2026-08-31: complete Luna Phase 1 and freeze the human workload

- The authorized 1,196-request Luna run achieved 100% schema-valid coverage.
  Conservative ceiling accounting is $0.562453 under the $2.50 limit. This
  includes a $0.012794 maximum-cost reserve for the first 12 calls, whose
  returned responses were not locally recorded because the reused runner
  expected the old identifier field. The frozen payload was unchanged; the
  local post-response bookkeeping was repaired and regression-tested.
- Human review is optimized for refusal precision and recall. All 129 Luna
  refusal positives and all 91 Luna-negative cases in the pre-existing refusal
  signal stratum are selected with certainty. Review probabilities are .50 for
  180 boundary negatives, .25 for 404 capability-failure negatives and .10 for
  392 ordinary negatives.
- Seed 20260901 realized 472 human reviews from an expectation of 450.2. The
  draw was not rerun to alter workload. Each row retains its Phase 1
  probability, Phase 2 probability, their product and inverse weight.
- Ninety-seven reviews are English. The frozen 375-row literal-translation
  payload has SHA-256
  `b53defcec344a2721ba26569240d9f10b82cc90fa7b42fe2516f8cfda2130096`.
  It has not yet been authorized or sent.

### 2026-08-31: complete translation aids and open final human review

- The user authorized the exact 375-row translation payload under a $3 ceiling.
  Luna returned 374 usable literal translations. One response exhausted all six
  unchanged attempts because its structured JSON repeatedly ended mid-string.
- The user separately authorized deterministic lossless chunking for that row.
  The fallback recursively translated some fragments but continued to fail; at
  the user's direction it was stopped and the English aid was marked
  unassessable. The complete original response is preserved for direct review.
  This action assigns no refusal, quality, language, or technical-failure label.
- Total locally ledgered translation cost, including failed and partial chunk
  attempts, is $1.53716. The final packet contains all 472 cases, with exactly
  one translation-unavailable aid.
- The then-live blinded interface, now archived, was
  `archive/2026-09-01_pre_rationalization/interactive/pages/7_Final_Luna_v2_4_human_validation.py`. It uses v2.4 and
  writes only to the new certification directory; old human logs are untouched.

### 2026-08-31: defer human review and adopt Sol as the frontier reference

- The user judged the 472-case multidimensional review infeasible. The frozen
  human packet and translations are preserved for future work, but no absent
  human labels will be imputed and the exercise will not be described as
  completed human validation.
- GPT-5.6 Sol will apply the identical v2.4 prompt to all 1,196 fresh Phase 1
  responses. Using the full first-stage sample is cleaner than applying Sol only
  to the enriched 472-case subset and avoids Phase 2 weighting for the
  Luna-versus-Sol comparison.
- Sol is designated a `frontier_model_reference`, not human gold. Accuracy
  language must remain conditional: Luna precision, recall, F1 and agreement
  relative to Sol. The full prompt, model route, provider and weights remain
  reported.
- Frozen payload SHA-256:
  `e63cd079e09d64c900fad03ea7f7ea92907eee2b8a4be72780738cc5e1a454a6`.
  Planning cost is $8.65 and the proposed hard ceiling is $15.50. No provider
  call has yet been authorized or made.

### 2026-08-31: complete and score the fresh Sol frontier reference

- All 1,196 authorized Sol requests completed schema-valid with no retries.
  Provider cost was $5.34388 under the $15.50 ceiling. Results SHA-256 is
  `7b6cfca2ff8b90a374c053f5122a5afc4770b2bdcbc2c1418a154f5363673b1a`.
- Using inverse Phase 1 probabilities, Luna refusal precision relative to Sol
  is .897, recall .895, F1 .896, specificity .998 and Cohen's κ .894. The
  weighted disagreement rate is .0042. Estimated refusal prevalence is 2.007%
  for Luna and 2.012% for Sol.
- The sample contains 22 refusal disagreements: 12 Luna-only positives and ten
  Sol-only positives. Issue-cluster bootstrap sensitivity intervals are
  [.822, .959] for precision, [.805, .971] for recall and [.832, .948] for F1.
- Capability failure is less interchangeable: precision .706, recall .954 and
  F1 .811, with Luna assigning the class substantially more often than Sol.
- A selective Sol cascade is preferred to Luna alone. Route every Luna refusal
  positive and every existing refusal-signal case to Sol. In this validation
  sample that routes an estimated 3.04% of the population, captures 20/22
  disagreements, and yields precision 1.00, recall .940 and F1 .969 relative
  to Sol. This routing performance must be monitored on future model additions.
### 2026-08-31: v2.4 promotion and full-corpus freeze

- Promoted decomposed v2.4 from candidate wording to the production codebook.
  This follows the focused human boundary review, same-codebook Luna--Sol
  comparison, eight-model bake-off and fresh 1,196-case probability-sample
  Luna--Sol comparison. Sol remains a frontier machine reference, not human
  ground truth.
- Froze a uniform wall-to-wall Luna v2.4 stage for the 137,186-response
  canonical corpus. Reused 2,393 completed Luna labels only after verifying
  byte-identical v2.4 prompt and schema hashes. The unpaid remainder is 134,793
  requests with logical payload SHA-256
  `ad8b0331ea1b0a60acc0e49d92791a2709287399f4f363f0757145d65188bed1`.
- Chose a compact hash-bound request index instead of persisting roughly two
  gigabytes of repeated system prompt. No network call is authorized.
- Local costs: $61.82 empirical projection from the fresh run, $104.70
  no-cache planning estimate at 200 output tokens, $153.22 single-attempt
  maximum-token reservation, and a proposed $117.50 hard stop.
- Predeclared the later selective Sol gate: all Luna refusal positives plus all
  existing `genuine_refusal_signal` cases. The exact Sol payload must wait for
  completed Luna labels.
- Hardened the full-corpus execution layer before authorization. The production
  ceiling is 24 workers, with a 12-worker warm-up, clean-batch ramping,
  immediate 429 throttling, explicit exponential backoff and `Retry-After`, and
  a four-worker floor. Disabled SDK-level retries so the three-attempt ledger
  limit is exact. Added atomic progress snapshots and retained per-attempt
  append, flush and disk sync. These are execution controls and do not alter
  the frozen logical payload hash.

### 2026-09-01: complete the Luna wall-to-wall run and freeze schema repair

- The authorized 134,793-request Luna run completed 134,664 schema-valid
  annotations (99.904%) for $63.27810 in 3 hours 16 minutes. The predeclared
  99.5% schema gate passed. With 2,393 exact reused v2.4 labels, 137,057 of
  137,186 corpus responses are covered before repair.
- All 129 unresolved requests exhausted three attempts on one deterministic
  conflict: `output_quality=incoherent_garbled` alongside explicit refusal
  (46) or implicit refusal (83). There were no unresolved rate-limit or API
  failures. The raw provider drafts and all attempts remain preserved.
- Froze a v2.4 instrument-repair stage over all 129 cases. It changes no
  codebook definition, field, enum, schema or derived outcome. It asks Luna to
  decide afresh whether the text is coherent enough to establish withholding
  or too garbled to establish refusal; it does not automatically flip a field.
- A failed first repair receives its exact validator error on one adaptive
  second attempt. This corrects the original runner's ineffective identical
  resubmission while keeping a two-call maximum and an append-only ledger.
- Initial payload SHA-256:
  `f9184d5005dabef4c5de739a845bcc452bf1518c92d9ec22e0451dd594991c41`.
  Repair-protocol SHA-256:
  `b2989ac04e672d87c4ebb65569ded6c852bc28ec3a200dc8d875fbd8e59d13d7`.
  The maximum two-attempt planning cost is $0.21929, reserved maximum-token
  cost is $0.31217, and proposed hard ceiling is $0.50. No repair call is yet
  authorized. Sol will receive only any residual cases after this stage.

### 2026-09-01: complete schema repair and assemble full v2.4 labels

- The authorized Luna repair completed all 129 cases on the first attempt for
  $0.0741098. There were no invalid repairs, API failures or adaptive second
  attempts; no Sol contingency is required.
- Of the conflicts, 119 became incoherent-garbled with refusal unassessable,
  four became incoherent-garbled non-refusals, five became partly coherent
  explicit refusals, and one became a partly coherent implicit refusal. Thus
  the repair adjudicated the contradiction rather than mechanically erasing
  refusal from every row.
- Repair results SHA-256:
  `a8e6c2342bd2771c494b08803018177b2d8da83fbbadd48c46a06343ee8886b1`.
  All original wall-to-wall drafts and repair responses remain separate and
  append-only.
- Assembled exactly one final v2.4 Luna annotation for all 137,186 canonical
  response keys with explicit component provenance. The final Parquet contains
  3,591 derived genuine refusals and 43,317 derived capability failures. Its
  SHA-256 is
  `ce1b6c07de09e96912b034195c2c5ab6f2ef7762fbb103143e02913f1383cf75`.
  These are corpus counts, not standardized or causal paper estimates.
