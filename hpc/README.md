# NYU Torch execution layer

This directory is an operational extension of the replication pipeline. It
contains no paper estimator. Its only scientific output is append-only subject
model response data that must pass the same annotation and admission gates as
API-generated responses before it can enter an R release.

`HPC_REGISTRY.csv` is the exhaustive ordered inventory. The supported sequence
is prepare (`HPC01`), download (`HPC02`/`HPC11`), benchmark (`HPC12`), mechanical
and human review (`HPC04`), then full generation (`HPC13`). The separate Fanar
entries are an experiment and never enter the canonical release automatically.

Jobs run from `/scratch/$USER/refusal_audit_v2` and store large model files
under `/scratch/$USER/refusal_audit_hpc`. Generated logs and weights are ignored
by Git. Exact model revisions, hashes, task construction, Slurm account, GPU
requirements, restart logic and transfer commands are documented in
`../docs/HPC_LOCAL_GGUF_FULL_V1.md`.

No Slurm job is submitted by `make`, the R release driver, or the default test
suite. Submission is always an explicit operational action.
