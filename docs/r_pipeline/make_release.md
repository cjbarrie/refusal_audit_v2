# `make_release.R`

This is the sole release driver. It requires an explicit `CANONICAL_RUN_ID`,
creates an immutable candidate directory, runs the registered active stages,
hashes inputs/source/docs/outputs, and promotes only after acceptance and figure
audit pass. It makes no external call.

Current execution order is 01, 11, 12, 15, 16, 17, 40, 20 and 21. Stage 16 is
foundational because its fixed geometry supplies Main Figure 1.
Pending scripts are absent from this plan. The manifest includes the original
final v2.4 Parquet, the five expansion annotation batches and their response
indexes, the nine raw expansion model directories and their run manifests,
exact prompts/schemas, original annotation inputs, embedding cache, package
versions, seeds and resampling counts. A full build stores
`data_clean.RData` inside the immutable release; no mutable root analysis frame
is produced or reused.

`--figures-only --from <id>` is allowed only when every estimation-path source,
seed, resampling setting, original annotation input, final original-panel v2.4
hash, expansion annotation artifact and expansion generation artifact matches
the source release. `--no-promote` builds and gates a candidate without
changing the promoted pointer.

A dirty tree is rejected unless explicitly allowed, existing release IDs are
immutable, and promotion swaps complete directories rather than merging files.
The promoted working release is `canon_024`: a figure-only successor that
inherits the completed, hash-verified 18-model estimates from `canon_021` and
passes 29/29 analysis plus 16/16 figure gates. Its manifest records the
explicitly permitted dirty tree. A final archival paper release requires a
committed clean tree and a new release ID.

The latest non-promoted `canon_029` release exercises this same contract on
the 20-model interim roster containing Sarvam-105B and Bielik 11B v3.0. It
inherits fully recomputed estimates from `canon_025` and passes 29/29 numerical
and 17/17 figure checks. T-pro is absent because its generation is incomplete.

The retired `--skip-data` mode is deliberately rejected. It depended on a mutable
root `pipeline/data_clean.RData` that could belong to an older roster. Full
releases always rebuild a release-scoped data file; figure-only releases inherit
already verified estimates and data from an immutable source release.
