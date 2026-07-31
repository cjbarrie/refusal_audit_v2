# Archived R scripts — ideology & moral-foundations (slant) analyses

Archived 2026-07-31. These scripts are **not broken**. They analyse annotation
Passes 2 and 3, which the study deliberately does not run.

## Why

`docs/ANNOTATION_TRIM_FULL_RUN.md` settled this:

> The study's stated interest is **refusal (1/0)** and **the nature of the
> refusal**. Both come entirely from annotation **Pass 1**. The ideology pass,
> the moral-foundations pass, and the separate stance stage measure the *slant*
> of answers the model *did* give — a different research question. For the full
> run we drop them.

That decision was recorded with status *"planned, not yet applied"*. The
`--pass1-only` flag was built, but the analysis layer was never trimmed to
match, so `pipeline/` kept advertising six scripts that the canonical run
produces no data for. This archive completes the decision.

As of the same date, **Pass 1 is the default** in `run_pilot.py` and
`annotation_pipeline.py` — `--all-passes` opts back in, and `--pass1-only` is
kept as an accepted no-op so existing commands and docs keep working.

## What is here

| Script | Reads | Outputs no longer produced |
|---|---|---|
| `03_ideology_analysis.R` | Pass 2 + Pass 3 | tables 11–18 |
| `04_ideology_extended.R` | Pass 2 | tables 24–28 |
| `05_moral_extended.R` | Pass 3 | tables 29–34 |
| `10_ideology_moral_patterns.R` | Pass 2 + Pass 3 | tables 39–40, figs 20–21 |

## What was deliberately kept in `pipeline/`

Two scripts touch slant fields but are mostly Pass 1, so they were **trimmed
rather than archived** — archiving them would have thrown away main-path
analysis:

- **`07_deepseek_language_analysis.R`** — tables 35 (refusal by language ×
  category), 36 (engagement distribution), 38 (justifications) and figure 19
  are all Pass 1. Only table 37 is ideology, and it is now guarded by
  `all(is.na(economic_left_right))`, which is `TRUE` both when the column is
  all-NA and when it is absent entirely.
- **`16_irr_analysis.R`** — **Cohen's kappa on Pass 1 is the primary IRR
  statistic** and is exactly what a reviewer asks for in a judge-based
  instrument. Krippendorff's alpha over the four ideology dimensions is
  secondary; those rows are now filtered out when `n == 0` rather than printed
  as four NA lines beside the two real kappas.

## Running these against a slant-annotated run

They still work — nothing was modified. They need a run annotated with every
pass, which `annotations/pilot_v1` is:

```bash
python scripts/run_pilot.py --run-id <id> --all-passes --stages generate annotate assemble
REFUSAL_RUN_DIR=annotations/<id> Rscript pipeline/01_data_loading.R
Rscript archive/pipeline_slant/03_ideology_analysis.R
```

This is **reversible by design**: raw responses are stored separately from
annotations, so Passes 2/3 can be added later by re-annotating stored responses
without regenerating anything. On the drawn study battery that costs roughly
$22 in judge calls, not another generation run.

## Restoring one

```bash
git mv archive/pipeline_slant/<script>.R pipeline/
```

Their internal `# Script NN` headers use the numbering in force before this
archiving; `pipeline/` no longer matches. See `docs/R_PIPELINE_WALKTHROUGH.md`.

## Related

`archive/pipeline_study_ab/` archives a different set for a different reason —
those analyse Study A/B side experiments whose runners have never been executed
in v2.
