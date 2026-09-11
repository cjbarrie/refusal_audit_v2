# Test suite

Run the local Python suite from the repository root:

```bash
/Users/christopherbarrie/.pyenv/shims/python3.9 -m pytest -q
```

Tests cover frozen response-validity designs, schema repair, last-valid-record
assembly, model-expansion payloads and costs, documentation registries, the
interactive build, and the retired/active separation. They use fixtures and
retained local artifacts; no test authorizes a provider call.

`test_fanar_experiments.py` additionally verifies that native provider filters
remain distinct from transport failures, the retest reproduces exactly the 29
original provider-facing requests, and the local QCRI pilot uses the same 40
prompt meanings with an explicit single-user wrapper.

R estimator tests are separate at `pipeline/tests_synthetic.R` because they run
inside the R dependency environment.
