# Python implementation package

`model_expansion/` contains the reusable roster, pilot, generation, annotation
and cell-audit implementations that produced the seven-model expansion.
`full_run_v3.py` and `full_run_annotation_v3.py` are the final expansion path;
the Apertus, pilot and cell-audit modules remain versioned provenance.

`response_validity/` contains the iterative measurement implementation. The
adopted production path is `wall_to_wall_v24.py` plus
`wall_to_wall_repair_v24.py`; earlier human samples, bake-offs and v2.2/v2.3
modules are retained because the technical report documents those exact
experiments. They are imported by the guarded `scripts/response_validity.py`
command surface but are not rerun by the R release.

Tests under `tests/` bind frozen payloads, schemas, resume behavior and output
hashes. Library modules never become paid commands without the explicit CLI
authorization checks.
