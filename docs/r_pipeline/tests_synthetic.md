# `tests_synthetic.R`

This fast regression script checks the current measurement and shared estimator
contracts. By default it reads the accepted 24-model `canon_031` frame because
the live constants enforce that roster. `CANON_DATA_PATH` can point it at a
different compatible candidate. The separate Python baseline check verifies the
promoted 18-model `canon_024` artifact. This script writes no scientific output.

The tests assert 299,080 unique keys across 24 models, the two combined outcome
counts, and exact original-label mapping on its 137,186-row domain; verify
nested/equal-model weights sum to one; fit a constructed
positive home effect and require finite positive g-computation; ensure a
20-draw issue bootstrap records all planned draws and distinct issue-instance
keys; and verify that active root scripts never source the pending directory.

The constructed home fixture contains 40 issues, two models and both home arms.
Its outcome probability is generated from `logit^-1(-2+1.2*home)`, so a
non-positive standardized contrast signals a fitting/standardization defect.

A nonzero failure count exits with status one. Passing covers these declared
invariants, not every possible empirical or numerical failure mode.
