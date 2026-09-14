# Wikipedia prompt-sourcing stages

The numbered files are the construction sequence for the frozen prompt bank.
They explain provenance; rerunning public Wikipedia calls today will not
recreate the historical snapshot bit-for-bit, and stages marked paid require a
new frozen payload and authorization.

| Stage | File | Role | External effects |
|---|---|---|---|
| 01 | `01_harvest_controversial.py` | Harvest perennial controversy seeds by edition. | Wikipedia/Wikidata; no model cost |
| 02 | `02_enrich_issues.py` | Add summaries, positions, entities, region and domain. | Wikipedia plus paid LLM when run |
| 03 | `03_format_prompts.py` | Build regular prompts and symmetric boundary pairs. | Paid LLM for regular phrasing |
| 04 | `04_merge_editions.py` | Deduplicate edition records on Wikidata Q-ID. | Local only |
| 05 | `05_translate_review.py` | Translate frozen prompt text and build review sheets. | Paid LLM when run |
| 06 | `06_harvest_temporal.py` | Harvest the protection-log temporal route. | Wikipedia; no model cost |
| 07 | `07_enrich_temporal.py` | Enrich temporal candidates with batched API reads. | Wikipedia plus paid LLM when run |
| 08 | `08_harvest_current_events.py` | Harvest the current-events breadth supplement. | Wikipedia; no model cost |

Stages 09--14 were amendments, not a second production pipeline. They repaired
the first rebalanced battery in this order: collision-free IDs, English-pivot
back-translation, selective retranslation, boundary-template normalization,
Q-ID recovery and source-revision recovery. Their one-off implementations are
in `archive/2026-09-01_pre_rationalization/sourcing/`. The corrected sample is
now hash-frozen; these stages are recorded for provenance and are not rerun.

`run_pipeline.py` is the driver for stages 01--04 and is safe by default because
paid enrichment requires `--enrich`. `editions.yaml` and
`boundary_templates.json` are frozen configuration. `preflight_providers.py`
checks configured routes and can make small endpoint calls, so it is never part
of a release. `run_rebalance.sh` preserves the completed rebalance recipe.
`run_corrections.sh` is deliberately non-executing: it points to the archived
amendment scripts instead of pretending their former relative paths remain live.

The complete order is `docs/TECHNICAL_PIPELINE.md`. Source-specific detail is in `docs/PIPELINE.md`,
`docs/NATIVE_SOURCING.md`, `docs/TEMPORAL_SOURCING.md`,
`docs/REBALANCE.md`, and `docs/REPRODUCIBILITY.md`.
