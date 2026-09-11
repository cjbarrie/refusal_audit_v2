# Superseded expansion-analysis snapshots

Archived 4 September 2026 after the seven completed expansion models were
integrated into the main manifest-driven R pipeline.

- `pipeline/expanded/` is the former standalone 17/18-model scratch analysis.
  It used different estimators and had no canonical release or acceptance gate.
- `pipeline/figures/expanded_pre_kimi/` is the 17-model interim figure set.
- `pipeline/figures/expanded_v3/` is the standalone 18-model figure set.

These files preserve provenance for results inspected during expansion. They
are not live entry points, are not sourced by `pipeline/make_release.R`, and
must not be copied back into `pipeline/figures/main` or `extended`. The current
replacement is the root-level canonical pipeline registered in
`pipeline/PIPELINE_REGISTRY.csv`.
