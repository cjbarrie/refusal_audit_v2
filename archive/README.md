# archive/

Files moved out of the working tree during the 2026-07-20 cleanup. Nothing here
is referenced by production code or the R analysis pipeline; it is retained as
provenance / validation evidence, not as a live dependency.

Later dated cleanups are self-documented in their own directories. In
particular, `2026-09-04_post_v24_rationalization/` removes superseded documents,
stale mutable 11-model analysis files and unrelated material from the live
surface after promotion of `canon_024`; it does not contain any raw-response or
canonical-release deletion.

## Contents

### `annotations/smoke_test/`
A minimal end-to-end validation run (English only, perennial battery, one issue)
used to confirm the `sample -> generate -> annotate -> assemble` wiring before
the pilot. Includes `annotations_all.jsonl`, one boundary file, prompt metadata,
and a `*_prompts_responses.csv` spot-check. Superseded by `annotations/pilot_v1/`.

### `annotations/smoke_mena/`
An aborted/partial smoke of the MENA HF-endpoint dispatch path (perennial, ar+en,
responses only — no annotations). Kept as evidence that endpoint dispatch was
exercised; the full credential-gated smoke is documented in
`docs/EXPANSION_RU_MENA.md` and had not been run at archive time.

### `sourcing/run.log`
Console log from the five-edition Wikipedia harvest (en/zh/ar/ja/id) — per-edition
candidate counts, Q-ID hit rates, and wall times. Provenance for the sourcing
stage; the harvest itself is reproducible via `sourcing/run_pipeline.py`.

## Not archived (deleted as regenerable)
`.DS_Store`, `__pycache__/`, and LaTeX build byproducts (`.aux/.log/.out/.toc`,
per-section `pN.log`) were moved to Trash during the same cleanup — all regenerate
on the next run/build.

## 2026-07-20 (second pass) — stale pilot outputs cleared for the full run

The full run writes generations/annotations to `annotations/full_v1/` (fresh,
run-id-keyed, disjoint from `pilot_v1/`), so that tree was already clean. But
three spots held pilot outputs that are NOT run-id-keyed and were cleared so the
full run starts from empty output dirs:

### `prompts_sampled_pilot/`
The pilot's sampled prompt subset (20 issues/battery, 6 languages — **no Hindi**),
formerly `prompts/sampled/`. `generate` reads from this shared (non-run-keyed)
dir, so a stale subset here is a footgun. The full run's `sample` stage
regenerates all 7 languages at `--n-issues 1000`; `prompts/sampled/` was emptied
so that regeneration is clean.

### `pilot_analysis/`
The pilot R-analysis products, written to fixed paths (not run-keyed):
`plots/` (50 files), `tables/` (48), `figures/` (3), and `data_clean.RData`.
The full-run R pass (Pass-1-only, trimmed script set) produces a *subset* of
these, so overwriting in place would leave pilot-only stragglers. Cleared to
avoid mixing pilot and full-run figures/tables.

### Left in place (validated pilot record, clearly labeled — not stale/ambiguous)
- `annotations/pilot_v1/` — the validated pilot run (disjoint run-id).
- `docs/pilot_v1_*.csv`, `docs/fig_pilot_refusal.png` — explicitly pilot-named.

## 2026-07-20 (third pass) — superseded probe-stage prompts

### `prompts_probe/`
`probe_prompts_en.json` and `probe_review_sheet.csv` — the 40-prompt "v2-probe"
stage used to validate the sourcing→format pipeline before scaling up. The
full batteries (perennial 1548, temporal 3199, all 7 languages) superseded
them, and no run/analysis code reads them. Formerly in `prompts/`.

### Deliberately KEPT (frozen run inputs + provenance — do NOT clear)
- `prompts/full_prompts_*.json`, `prompts/temporal_prompts_*.json` — the study
  instrument the run reads (perennial + temporal batteries × 7 languages).
- `prompts/*_review_*.csv`, `prompts/excluded_issues.yaml` — review sheets + denylist.
- `data/*` — Wikipedia-harvest provenance (candidate_issues, issue_records,
  raw_wiki_fetch, *_probe.json) AND Study A/B config that the R scripts read
  (`study_a_prompt_subset.csv`, `prompt_narrative_map.yaml`,
  `study_a_prompt_subset_cn_addon.csv`). Clearing these would break
  reproducibility and Study A/B analysis.
