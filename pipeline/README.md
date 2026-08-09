# pipeline/ — how this repository is run

**One command builds the paper:**

```bash
CANONICAL_RUN_ID=canon_004 Rscript pipeline/make_release.R
```

It runs inputs → reliability → canonical estimation → appendix descriptives →
figures → manifest → acceptance → figure audit, builds into
`pipeline/releases/<run_id>/`, and promotes to `pipeline/estimates/canonical`
and `pipeline/figures/` **only if every check passes**.

`run_all.R` and `run_canonical.R` were removed. `run_all.R` called itself "the
analysis driver" while excluding every canonical script, and its `--figures`
mode selected a stage that no longer existed — so it ran nothing and exited 0.
Two partial drivers with a misleading name is worse than one honest one.

## Numbering

| range | role | scripts |
|---|---|---|
| `01`–`02` | inputs | `01_data_loading.R` → `data_clean.RData`; `02_judge_reliability.R` → `e23`–`e28` |
| `10`–`16` | estimation | `10_canonical_common.R` (shared), `11` home, `12` language + framing, `13` content, `14` judge sensitivity, `15` subsample stability, `16` prompt UMAP |
| `20`–`21` | figures | `20_figures_main.R` → Fig 1–3; `21_figures_extended.R` → ED1–ED9 (**PNG only**, 183 mm, 600 dpi, no titles) |
| `30` | acceptance | `30_acceptance.R`, non-zero exit on failure |
| `40` | appendix | `40_appendix_descriptives.R` → `a01`–`a04`, descriptive views only |
| — | tests | `tests_synthetic.R`, seconds to run, no data needed |
| — | audit | `audit_figures.R`, the figure gate |

## Useful flags

```bash
CANONICAL_RUN_ID=x Rscript pipeline/make_release.R --skip-data     # data_clean is current
CANONICAL_RUN_ID=x Rscript pipeline/make_release.R --no-promote    # build + check only
CANONICAL_RUN_ID=x Rscript pipeline/make_release.R --allow-dirty   # release from a dirty tree
Rscript pipeline/tests_synthetic.R                                 # fast unit tests
```

Specification: `docs/CANONICAL_ANALYSES.md`. Figure legends:
`docs/CANONICAL_FIGURE_LEGENDS.md`. Archived surfaces and why:
`pipeline/archive/README.md`.
