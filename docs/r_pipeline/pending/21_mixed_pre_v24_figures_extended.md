# Pending `21_mixed_pre_v24_figures_extended.R`

Status: retained pre-v2.4 artwork code; not run by `make_release.R`.

This script assembled the former Extended Data set from home, language,
stability, judge-sensitivity, ideological-slant, moral-foundation, reliability,
UMAP and framing tables. It performed no estimation, but it placed supported
and unsupported measurement families in one apparently canonical inventory.

Its source tables included old `c12`--`c17` and `e23`--`e25` products, and it
wrote ED1--ED9 PNGs plus a layout RDS. The live replacement is
`pipeline/21_figures_extended.R`, whose exact supported inventory is checked by
both acceptance and figure audit. Any future content figure requires an adopted
outcome, a current estimator and a new explicit inventory; this file cannot be
copied back wholesale.
