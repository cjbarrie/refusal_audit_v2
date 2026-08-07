# Archived analysis surfaces (pre-canonical)

The canonical layer (`pipeline/10_canonical_common.R` … `30_acceptance.R`,
driven by `pipeline/run_canonical.R`) replaces two earlier analysis surfaces.
Both are preserved here, unmodified except for `source()` paths, so any number
that appeared in an earlier draft can still be traced to the code that produced
it.

**These scripts are reference-only. Do not run them to produce new results, and
do not cite their outputs.** Where they and the canonical layer disagree, the
canonical layer is correct and `pipeline/estimates/canonical/c01_reconciliation.csv`
explains the difference.

- `precanonical_v1/` — the original estimand layer (`e01`–`e31`, `d01`–`d08`,
  `FIG1`–`FIG5`, `P1`–`P14`).
- `precanonical_v2/` — the three-family revision (`e32`–`e40`, `FIGA`–`FIGC`),
  which separated descriptive, standardized and prompt-fixed estimands but kept
  an issue-keyed bootstrap that dropped multiplicity.

The estimate CSVs themselves stay in `pipeline/estimates/`. They were not moved,
because `c01_reconciliation.csv` reads `e01`, `e33`, `e36` and `e17c` directly to
build the comparison table, and `14_canonical_judge_uncertainty.R` reads the panel
reliability tables. Moving them would break the canonical layer's own provenance.

---

## Why each surface was superseded

**v1.** Its primary home estimate was a log-odds contrast from a pooled GLM that
included region fixed effects. Region determines home status within a
jurisdiction, so the fixed effects absorbed part of the very contrast being
estimated. Results were also reported on the odds scale, which is not
collapsible — the pooled odds ratio was not a weighted average of the
model-specific ones, so "the" home premium had no stable interpretation across
subsets. Language was read off unpaired cell rates, confounding language with
prompt composition.

**v2.** It fixed the scale (probability), the estimand separation (descriptive /
standardized / prompt-fixed), and the language design (paired within
model×prompt blocks). One defect remained: the issue-cluster bootstrap keyed
replicate statistics on `issue_id`, so when a replicate drew the same issue
twice, the two copies collapsed into one unit. This understated between-issue
variance and produced intervals that were too narrow. The canonical layer labels
each *draw* (`bootstrap_issue_instance`), which is what `30_acceptance.R`
test C2 verifies against a synthetic three-issue counter-case.

---

## Mapping: every archived script to its replacement

### precanonical_v1/

| Archived script | Outputs it wrote | Canonical replacement |
|---|---|---|
| `20_estimates_home.R` | `e01`–`e10`, `e21`, `e22` | `11_canonical_home.R` → `c02`–`c07`. Scale changed (log-odds → probability), region FE dropped as non-identified, bootstrap multiplicity repaired. |
| `21_estimates_support.R` | `e11`–`e14` | **Split.** Tier/framing contrasts → `12_canonical_language_framing.R` (`c10`, `c11`), now paired within issue×model×language rather than modelled. Overall rates → `c02`. **`e13`/`e13b` (refusal justification codes A–G) have no canonical replacement** — see "Not carried forward" below. |
| `22_estimates_slant.R` | `e15`–`e20` | `13_canonical_content.R` → `c12`–`c16`. Ideology's primary estimand is now the full −2..+2 distribution rather than a signed mean; foundations carry intervals and per-foundation judge agreement. **`e20_moral_by_language.csv` is retired, not replaced** — see below. |
| `23_diagnostics.R` | `d01`–`d08` | Partly replaced: overlap/estimability → `c06`, bootstrap diagnostics → `c18`. The remaining `d`-series are descriptive tabulations of the annotation file and are still accurate; nothing in the canonical layer contradicts them. |
| `25_estimates_language.R` | `e29`–`e31` | `12_canonical_language_framing.R` → `c08`, `c09`. Unpaired cell rates replaced by within-block paired differences; all four non-English languages estimated, including the null ones. |
| `30_figures.R` | `FIG1`–`FIG5`, `P1`–`P14` | `20_figures_main.R` → `FIG1`–`FIG3` canonical. The locator map is carried over unchanged. |

### precanonical_v2/

| Archived script | Outputs it wrote | Canonical replacement |
|---|---|---|
| `40_v2_common.R` | (shared helpers) | `10_canonical_common.R`. Adds the multiplicity-preserving bootstrap, the multi-judge accessors, run-scoped diagnostics with duplicate-label detection, and a hard row-count assertion on the analysis sample. |
| `41_v2_home_descriptive.R` | `e32` | `11_canonical_home.R` → `c02`, `c03` |
| `42_v2_home_standardized.R` | `e33`, `e34`, `e35` | `11_canonical_home.R` → `c04` (nested weighting), `c05`, `c07` (sensitivities) |
| `43_v2_language_paired.R` | `e36`, `e37` | `12_canonical_language_framing.R` → `c08`, `c09` |
| `44_v2_outcome_sensitivity.R` | `e38` | `11_canonical_home.R` → `c07` (outcome-definition rows) and `52` → `c08` (`codes 3-5` sensitivity rows) |
| `45_v2_reconciliation.R` | `e39`, `e40` | `run_canonical.R` → `c01_reconciliation.csv`; bootstrap diagnostics → `c18`. Note `e39` was written with 412 rows against 332 unique labels — 80 duplicates, caused by unkeyed appends. `record_diag()` now errors on a duplicate (run_id, label). |
| `46_v2_acceptance_tests.R` | (console + exit status) | `30_acceptance.R` → `c01b_acceptance_tests.csv`. Test count 27 → 37, and `chk()` now fails a test whose condition returns `logical(0)` or `NA` instead of silently dropping it. |
| `47_v2_figures.R` | `FIGA`–`FIGC` | `20_figures_main.R` → `FIG1`–`FIG3` canonical |

---

## Not carried forward (and why)

These are the outputs with **no** canonical replacement. Each is a deliberate
omission, not an oversight.

| Output | Status |
|---|---|
| `e20_moral_by_language.csv` | **Retired as unsound.** It compared moral-foundation prevalence across languages without pairing, so language was confounded with which responses happened to be engaged in that language — and engagement rates differ by language, so the denominators are not comparable. A defensible version needs the paired block design of `c08` applied to a content outcome, conditional on engagement *in both languages*. That analysis has not been run. |
| `e13`, `e13b` refusal-justification codes | **No canonical estimand.** The A–G justification taxonomy is still tabulated by `pipeline/06_refusal_justifications.R`, but the canonical layer makes no claim about it: the codes had the weakest inter-judge agreement of any construct, and a prevalence claim over a taxonomy the judges do not agree on is not defensible. Retained as description only. |
| `e02` odds-ratio tables | **Dropped by design.** Non-collapsible scale; see above. |
| `FIG4`, `FIG5`, `P1`–`P14` | Superseded by the three canonical figures. Several were exploratory views of the same DeepSeek finding at different rigour levels. |

## Also archived here

`retired/` holds two scripts that were not superseded by a replacement but
simply stopped being needed:

| file | why |
|---|---|
| `16_irr_analysis.R` | A retired stub. It was structurally limited to two raters and had already been superseded by the judge-reliability script; it stayed as a stub that printed a pointer. |
| `57_refusal_umap_figure.R` | Drew the standalone `P15` refusal-projection figure. Its content now lives in `20_figures_main.R` (FIG1 panel c) and `21_figures_appendix.R` (S4), so keeping it would have meant two scripts drawing the same points. |

**The figures directory was also cleared.** Twenty-three PNGs produced only by
the archived v1 and v2 figure scripts (`FIG1`–`FIG5`, `P1`–`P14`, `FIGA`–`FIGC`,
`P15`) were deleted. They are recoverable from git history and regenerable by
the archived scripts; leaving them in `pipeline/figures/` meant superseded
figures sat next to current ones with nothing to distinguish them.
`audit_figures.R` now fails on any file in that directory that is not one of the
seven the manuscript ships.

## Scripts deliberately NOT archived

| Kept live | Why |
|---|---|
| `01_data_loading.R` | Builds `data_clean.RData`, the input to everything including the canonical layer. |
| `02_judge_reliability.R` (was `24_measurement.R`) | Writes the panel reliability tables (`e23`–`e28`) that `14_canonical_judge_uncertainty.R` reads into `c17`. It is an input producer, not a superseded estimand surface. Re-run it if the judge panel changes. |
| `40`–`44` appendix scripts (were `02`, `06`–`09`) | Descriptive tabulations and the DeepSeek case-study material. They make no headline estimand claim, and are now numbered into the appendix range. |
| `audit_figures.R` | Enforces the PNG-only rule across `pipeline/figures/`, including the canonical subdirectory. |

## Running an archived script

Their `source()` lines were rewritten to point at the archive, so they still run
from the repo root:

```bash
Rscript pipeline/archive/precanonical_v2/41_v2_home_descriptive.R
```

They write to the same `pipeline/estimates/` paths they always did, so a run
**overwrites the historical `e`-series CSVs in place**. Copy them elsewhere first
if the old values matter.
