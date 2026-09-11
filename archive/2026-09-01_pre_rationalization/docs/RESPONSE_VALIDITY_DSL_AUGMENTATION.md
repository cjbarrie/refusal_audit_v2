# DSL v1.1 singleton-stratum variance repair

Status: **authorized, completed, assembled, and verified on 2026-08-19**.

## Why this is required

The completed v1.0 reference design guarantees at least one sampled control in
each populated `model × prompt_language × home_status × engagement_code`
stratum. Post-run inference review found 236 strata with `n=1`. Twenty-nine have
`N=1` and are censuses. The remaining **207 noncensus singleton strata** yield
design-unbiased HT/DSL point estimates but cannot supply an empirical within-
stratum SRSWOR variance. Treating them as certainty units or ordinary bootstrap
strata would understate phase-two uncertainty.

## Frozen repair

The archived `scripts/archive/response_validity/augment_response_validity_dsl_reference.py prepare` drew one additional
control uniformly from the remaining `N-1` rows in each of the 207 strata,
without reading Sol outcomes. Sequential SRS(1) followed by SRS(1) from the
remainder is exactly an unordered SRS(2): every pair has probability
`1 / choose(N, 2)`, and every row has final inclusion probability `2/N`.

- Parent reference rows: 13,975.
- Added rows: 207.
- Final v1.1 reference rows: 14,182.
- Seed: 20260820.
- Selection uses reference labels: false.
- Parent reference-key hash:
  `985fd82ea0bda389130b933d5c9969fcff5fcfb56f86755826f4c019b54e87a4`.
- Augmentation-key hash:
  `1d3f258dd89d60f2d420295c8bd716a8cf6e0e9bff1186ae0a98ccdf4229f730`.
- Final v1.1 reference-key hash:
  `9f4991f88a6d94720c98b151eb79729e872a1fc36e87248e5db6d49d82dd0bf9`.

All v1.0 raw and assembled artifacts remain unchanged. The repair lives under
`annotations/response_validity_dsl_v1_1/` and becomes a new design version only
if explicitly authorized and completed.

## Completed external call and cost

The same 207-row prompt payload would be sent to the same OpenRouter model and
provider as v1.0:

- model: `openai/gpt-5.6-sol`;
- provider allowlist: `openai` only;
- fallbacks: disabled;
- reasoning: disabled;
- prompt/schema: unchanged response-validity v1.1;
- fields sent: target language, English reference prompt, target-language
  prompt, and model response;
- fields withheld: original label, justification, subject-model identity,
  jurisdiction, sampling stratum, prior judges, secrets, and account metadata.

The frozen payload contains approximately 377,084 prompt tokens. Charging every
prompt token at the higher promotional cache-write rate and assuming 72 output
tokens per row gives a conservative expected incremental cost of **$1.4019475**.
The completed parent cost is $75.264048625, so expected cumulative cost is about
$76.67 under the unchanged $95 ceiling.

The first attempted execution on 2026-08-19 was rejected before process launch because
the user had authorized the parent frozen reference set, not these 207 newly
selected records. Therefore zero augmentation records have been transmitted and
zero augmentation cost had then been incurred. The user subsequently supplied
the required explicit authorization. The completed augmentation has:

- 207/207 unique successful labels;
- incremental provider cost **$1.303606875**;
- cumulative v1.0 + v1.1 provider cost **$76.567655500**;
- zero reasoning tokens;
- zero validation repairs;
- zero remaining noncensus strata with `n < 2`;
- 14,182 unique final reference keys and 137,186 DSL population keys;
- 30 repeat-specific pseudo-outcome columns and 150 cross-fit diagnostics;
- 19/19 passing repository Python tests at verification.

Final artifact hashes:

| Artifact | SHA-256 |
|---|---|
| `augmentation_universe.parquet` | `1d3122087006acbf1f4962054d71ffff2b92f7abf0c43f969a9fa9dba867bdc2` |
| `reference_universe.parquet` | `b38800fb1c00371a3dcca6c7d5fc425ad992a63677e4d447a2bca223ecb20964` |
| `sol_augmentation_labels.jsonl` | `2f6005abba13861eef297949d0619e4336912f4fcfac66759df5fccc805a8d81` |
| `assembled_reference_labels.parquet` | `705c3cf4fed6bc5648231be1b552483a54d0cbcc8d8b1490498f1622dc30b5f1` |
| `dsl_pseudo_outcomes.parquet` | `166b4f68fd54c03676ac48b1d108b8e8de54d704e75136e98a586a52994f0007` |
| `dsl_crossfit_diagnostics.csv` | `045097189bea6a5a15f54bd1a60231a762837661d08d0366742095f86e70ea3f` |

## Completed steps

1. Ran the 207 calls append-only and resumably.
2. Required 207/207 valid records and zero unresolved errors.
3. Assembled v1.1 labels while preserving the v1.0 label files.
4. Refit the 5-fold × 10-repeat DSL learner using final `2/N` probabilities.
5. Verified every noncensus stratum has `n >= 2`.
6. Canonical integration now uses empirical stratum residual variance and finite-population correction
   in canonical home, language, framing, and model-level intervals.
7. v1.0 point estimates remain a version sensitivity.
