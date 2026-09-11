# Replication status

Status: 11 September 2026. This page answers one question: what is part of the
current paper pipeline, and what is still being developed?

## Frozen and promoted

- Prompt sample: 624 complete issue blocks, 2,496 prompt meanings, five
  languages. File hashes are in `config/replication_contract.json`.
- Original response panel: 137,186 observed response keys from 11 models.
- Original-panel production outcome: Luna v2.4, one label per observed response,
  with hash `ce1b6c07de09e96912b034195c2c5ab6f2ef7762fbb103143e02913f1383cf75`.
- Accepted v3 expansion: seven models and 87,358 analysed response keys.
- Promoted analysis: `canon_024`, 224,544 responses and 18 models.
- Promoted figures and both explorers: `canon_024`.

## Complete but not promoted

- Sarvam-105B and Bielik 11B v3.0 have complete-enough full generation and
  Luna v2.4 annotation batches for the declared observed-response analysis.
- `canon_029` includes these models: 249,201 responses across 20 models. It
  passed 29 analysis checks and the figure audit but remains an unpromoted
  candidate because the repository was dirty and the wider expansion is still
  in progress.

## In progress and excluded from every current release

- T-pro-it-2.0 generation is an operational full-corpus run and is not part of
  either `canon_024` or `canon_029`.
- The four NYU Torch GGUF models (Krutrim 2, GigaChat3, EuroLLM 22B and
  Salamandra 7B) passed the 100-response mechanical benchmark. Their full
  49,920-response Slurm array is separate run state and does not enter an R
  release until generation, transfer, annotation and admission checks finish.
- The local Fanar checkpoint is an experimental matched pilot. Native Fanar
  filtering experiments are measurement evidence, not prevalence data and not
  part of the canonical corpus.

## Deferred

- Slant and moral-foundation analyses remain under `pipeline/pending/` because
  no adopted outcome measurement supports them.
- Human certification of the full Luna labels remains incomplete. Sol is a
  frontier machine reference, not a human gold standard.
- A final clean-tree archival release is deferred until the model expansion and
  estimands are frozen.
- Public deployment and separation of `interactive/web/` are deferred until a
  disclosure review can produce a minimal public data bundle.

## Rules for admitting another model

A model enters the paper corpus only after all of the following are true:

1. the canonical five-language prompt payload and generation settings are
   frozen;
2. response records are append-only, unique under
   `(prompt_id, prompt_language, model)` after last-valid assembly, and their
   failures remain explicit;
3. Luna v2.4 annotations cover every response-bearing record, with exhausted
   schema cases reported rather than imputed;
4. model-language capability and wrong-language behavior have been audited;
5. `pipeline/_expansion_input.R` is versioned to name the exact batch hashes;
6. a new immutable R release passes every acceptance and figure gate; and
7. promotion is an explicit decision, never “choose the largest canon number.”
