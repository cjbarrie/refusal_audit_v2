# Response-validity codebase rationalization

## Current authority

The only active operational entry point for response-validity work is
`scripts/response_validity.py`. The active and planned analysis surface is
declared in `pipeline/PIPELINE_REGISTRY.csv`; both Python tests and the R release
driver reject an unregistered root-level R script, missing active script,
missing technical reference, or active paid-call stage.

The new human-reference implementation is split into small importable modules
under `src/refusal_audit/response_validity/`. No release command imports a
provider SDK or makes a network call. The local pilot command only freezes a
sample and writes a payload; transmission requires a separately implemented and
authorized command.

`human_pilot.py` owns sampling, translation assembly, label validation, and the
collection schema. `human_audit.py` owns the immutable 300-label base freeze,
exact union-design pairwise inclusion probabilities, provisional HT/Hájek
estimation, and deterministic disagreement extraction. The live append-only
label log is never rewritten by either module. Repeat records are outside the
base-freeze membership set and cannot enter the preliminary audit.

`decomposed_review.py` owns the 700-row harmonized human-reference table. It
gives direct decomposed reviews priority over explicit mappings and records the
provenance of every derived headline outcome. `luna_v22_test.py` reproduces the
completed exact-v2.2 internal test. `luna_v23_repair.py` owns the current schema
repair, raw-output preservation, and patched internal scoring. None of these
commands authorizes a wall-to-wall annotation run.

`scalable_bakeoff.py`, `enrichment_design.py`, and `enrichment_design_v2.py`
remain reproducibility code for completed or superseded development
experiments. Their artifacts are checked for integrity, but they do not define
the current scientific run sequence. `external_audit_design.py` now owns the
aggregate simulation for the fresh probability-based audit outside the 700
development cases. That module is deliberately unable to emit response IDs,
review packets, or provider payloads. Its current output recommends a design
that was approved on 2026-08-27. `external_audit_freeze.py` owns the resulting
reproducible draw and blinded Luna/Sol payload freeze. It has no provider client
and cannot make a network call. `external_audit_run.py` is the separately
guarded paid runner and post-run pairing code. The exact authorized run is now
complete; its current outputs remain machine labels pending the frozen human
verification phase.

## Pre-consolidation provenance

`docs/archive/RESPONSE_VALIDITY_MIGRATION_MANIFEST_PRECONSOLIDATION.csv` hashes every identified
legacy, superseded, completed-run, and duplicate implementation. Its companion
pre-consolidation JSON records the Git head, branch, dirty status, rule hash, inventory hash, and
counts. At baseline there were 35 files, including 11 files not protected by
the current Git commit. These files must not be deleted before the inventory and
their final archival locations are committed or otherwise durably preserved.

## Retention classes

- **Active:** one CLI, importable current modules, canonical R stages, tests,
  frozen schemas, and current technical documents.
- **Completed provenance:** exact prompts/runners/manifests/results needed to
  audit a historical paid run. Retain read-only under an explicit archive; do
  not advertise as a current command.
- **Superseded implementation:** retain by content hash through the migration
  commit, then remove from the runnable tree. Git history is its archive.
- **Generated artifact:** keep only when it is a declared immutable input or
  accepted output. Regenerable tables, caches, and figures do not belong in
  `docs/`.

## Safe migration sequence

1. Freeze the hash-addressed pre-consolidation inventory (completed).
2. Introduce and test the single active CLI and module boundaries.
3. Move completed paid-run code to `scripts/archive/response_validity/` with a
   README fixing model, prompt, payload, cost, and output hashes (completed).
4. Remove superseded generated documentation artifacts after their hashes and
   Git provenance are durable.
5. Rebuild a post-consolidation inventory and require zero unexpected runnable
   validity scripts outside the registry (completed; the scripts root now has
   only `scripts/response_validity.py` matching `*response*validity*`).
6. Commit the migration, frozen codebook, prompt, design code, and sample hashes
   before transmitting the payload or beginning human annotation. The local
   draw exists, but it is not an inferential human dataset until that provenance
   boundary is durable.

No historical canonical release is rebuilt, deleted, or mutated during this
migration. `canon_012` remains the accepted historical release; `canon_013`
remains incomplete and cannot be promoted by numeric ordering.
