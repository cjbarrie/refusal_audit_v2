# Archived response-validity implementations

These scripts are preserved solely to audit completed machine-reference runs.
They are not current operational entry points and must not be used to create a
new annotation run. Their pre-consolidation paths, content hashes, roles, and
replacement are recorded in
`docs/archive/RESPONSE_VALIDITY_MIGRATION_MANIFEST_PRECONSOLIDATION.csv`.

Current local operations use `scripts/response_validity.py`; current importable
code lives under `src/refusal_audit/response_validity/`. The accepted Sol v1.1
artifacts remain immutable under `annotations/response_validity_dsl_v1_1/` and
are consumed read-only by `pipeline/17_response_validity.R`.

All eight archived Python files are byte-identical to the hashes recorded for
their former root-level paths in the pre-consolidation manifest. Their broken
relative root resolution in this archival location is intentional friction:
tests import pure functions only, and no archived command is supported.

The archived paid runners contain historical provider endpoints, prompts,
schemas, price assumptions, and repair rules. Archival does not re-authorize
them. Do not execute an archived runner, and never add an archived path to the
release plan.
