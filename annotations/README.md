# Response and annotation evidence

These directories are run state and scientific provenance. They are ignored by
Git because they contain large row-level prompts and responses, but they must
not be casually deleted or rewritten.

- `full_v1/`: original 11-model generation, original Gemini annotations and
  copied prompt metadata;
- `model_expansion_v3/`: seven added models, their generation ledgers and three
  completed Luna v2.4 annotation batches used by the R pipeline;
- `response_validity_v2_4/`: adopted codebook evaluations and the final
  137,186-row original-panel Luna v2.4 assembly;
- other `response_validity_*`, `model_expansion_v1|v2|v4`, pilot and smoke
  directories: development, validation or failed-route evidence. They are not
  silently pooled into the canonical analysis.

Within `model_expansion_v4`, `fanar_system_experiments_v1` is an offline audit
derived from retained native Fanar ledgers. `fanar_c2_27b_filter_retest_v1` and
`fanar_1_9b_local_pilot_hpc_v1` are frozen but unrun experimental contracts.
None currently enters the canonical analysis.

The authoritative inclusion rules and hashes are in
`pipeline/_response_validity.R`, `pipeline/_expansion_input.R`, and the promoted
release manifest. Append-only/last-valid-record logic applies throughout.
