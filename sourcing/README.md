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

`run_pipeline.py` is the driver for stages 01--04 and is safe by default because
paid enrichment requires `--enrich`. `editions.yaml` and
`boundary_templates.json` are frozen configuration. `preflight_providers.py`
checks configured routes and can make small endpoint calls, so it is never part
of a release. `run_rebalance.sh` and `run_corrections.sh` preserve completed
workflow recipes and should not be treated as general commands.

Current design and reproducibility detail is in `docs/PIPELINE.md`,
`docs/NATIVE_SOURCING.md`, `docs/TEMPORAL_SOURCING.md`,
`docs/REBALANCE.md`, and `docs/REPRODUCIBILITY.md`.
