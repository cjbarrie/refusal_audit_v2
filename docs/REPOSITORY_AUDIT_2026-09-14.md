# Sequential-pipeline forensic audit

Audit date: 14 September 2026. Scope: the root execution surface, all component
registries, prompt sourcing, generation, response-validity measurement, hosted
and HPC expansion, R analysis, releases, interactive outputs and current
technical documentation. No provider request, Slurm submission, release build
or promotion was made during this audit.

## Findings and resolutions

| ID | Severity | Finding and evidence | Resolution |
|---|---:|---|---|
| S01 | P0 | The repository had five component registries but no single execution-order account. `config/REPLICATION_STAGES.csv` formerly compressed all sourcing into two rows and all annotation refinement into one. A reader had to reconstruct dependencies from several long operational documents. | Added `docs/TECHNICAL_PIPELINE.md` and expanded `config/REPLICATION_STAGES.csv:2-22` into the production sequence from environment through explorer. Each row names its inputs, output, external-call status and master documentation. |
| S02 | P0 | `sourcing/run_corrections.sh` called `09_migrate_issue_ids.py` through `12_normalize_boundary_templates.py`, but those relative paths no longer existed in `sourcing/`; the implementations were archived on 1 September. The live wrapper therefore advertised a paid command that could not run. | Replaced it with a deliberate non-executing signpost (`sourcing/run_corrections.sh:1-29`), changed its registry status, and documented stages 06A-06E plus the required order in the master pipeline. The historical Python files remain unchanged in the dated archive. |
| S03 | P0 | Current technical prose mixed three analysis states: promoted `canon_024` (18 models), historical candidate `canon_029` (20), and current candidate `canon_031` (24). `writeup/pipeline_technical.tex` still described 249,201 rows as the live frame. | The master pipeline now gives a two-row current-state table. The TeX source now states 299,080 rows, 24 models, 7,175 refusals and 74,598 capability failures for `canon_031`, while preserving `canon_024` as the promoted baseline. |
| S04 | P1 | `docs/REPOSITORY_MAP.md` still stated 112,015 accepted expansion labels even though the declared roster contains 161,894. | Updated the map from `config/analysis_roster_v1.json` and linked it to the master sequence. |
| S05 | P1 | GitHub visibility had changed after the previous audit, but `config/replication_contract.json` and the handoff guide still declared a private repository. | Verified `cjbarrie/refusal_audit_v2` as public through GitHub on 14 September, updated the contract and guide, and reframed `PRIVATE_REPOSITORY_HANDOFF.md` as a public-disclosure preflight while retaining its filename for stable links. |
| S06 | P1 | Prompt corrections appeared as an opaque “repair orchestrator”; their scientific rationale and ordering were not visible beside the main pipeline. | `TECHNICAL_PIPELINE.md`, stage 06, names the collision, English-pivot, stale-translation, template and revision-provenance defects, the exact archived implementation for each, its output, and why the order mattered. |
| S07 | P1 | Hosted APIs, dedicated endpoints, local llama.cpp and Torch/Slurm were documented in separate experiment notes but not compared in one place. | Added a connection-mode table in stage 13 and a six-step Torch sequence in stage 14. Exact provider/model routes remain in the versioned operational documents and roster manifests; secret values and private endpoint URLs remain excluded. |
| S08 | P1 | Codebook development was described in depth, but a new analyst could not see where it sat relative to original Gemini annotation and wall-to-wall Luna production. | Stages 09-12 now distinguish the historical Gemini measure, the 700 development rows, v2.1-v2.4 changes, annotator selection, the 134,793 new Luna calls, the 2,393 reused exact-v2.4 labels and the 129-case schema repair. |
| S09 | P2 | Script filenames use several numbering systems: `sourcing/01-08`, R stages, stable registry IDs (`G`, `E`, `HPC`, `I`) and unnumbered Python modules. Renaming them now would break frozen manifests, imports and citations. | The global order is defined once in `REPLICATION_STAGES.csv`; each component keeps its stable registry numbering. The master document explains this rule rather than renaming provenance-bearing files. New operational entry points must receive a registry ID and a parent global stage. |
| S10 | P2 | The existing September 11 audit accurately records the repository state at that date but is now stale on visibility, model count and Torch completion. Rewriting it would erase the chronology of corrections. | Retained it unchanged as a dated audit and added this new audit. Current navigation points to the 14 September document; historical statements remain explicitly dated. |
| S11 | P1 | The advertised standalone `Rscript pipeline/tests_synthetic.R` command loaded the promoted 18-model frame while the live estimator constants required the 24-model roster. It failed before completing its checks. | The standalone test now defaults to the accepted `canon_031` frame, while `CANON_DATA_PATH` still permits another compatible candidate. The Python baseline check remains the separate verifier for promoted `canon_024`. The direct R command now passes 13/13 checks. |
| S12 | P2 | The artifact inventory still classified the live GitHub Pages workflow as unresolved and found an ignored `.DS_Store` under `writeup/`. | Added a narrow workflow classification rule, removed the disposable Finder file, and rebuilt the registry. All 3,970 inventoried paths now resolve to active canonical, active supporting or historical provenance; no path remains unknown or accidental junk. |

## Directory decisions

| Directory | Current role | Decision |
|---|---|---|
| `sourcing/` | live reconstruction code for stages 01-07 | keep; archived amendments are referenced, not restored as live commands |
| `data/` and `prompts/` | retained source records, corrected masters, fixed sample and embedding input | keep; hashes and role are tracked in the artifact registry |
| `scripts/` | guarded generation/annotation CLIs and checks | keep; `SCRIPT_REGISTRY.csv` is the stable numbering layer |
| `src/refusal_audit/` | versioned implementation modules called by guarded CLIs | keep; modules are implementation detail, not independent pipeline stages |
| `annotations/` | unique response, annotation and validation evidence | keep; admission to R is controlled by `analysis_roster_v1.json`, not directory presence |
| `hpc/` | Torch preparation, Slurm and audit code | keep; no job is submitted by a default Make target |
| `pipeline/` | active R estimators, figures, immutable releases and pending analyses | keep; `pipeline/pending/` never enters `make_release.R` |
| `interactive/` | derived local and web explorers | keep in this repository for now; builders resolve only the promoted release |
| `archive/` | superseded implementations and unique historical evidence | keep immutable and outside all live execution paths |
| `logs/`, `tmp/`, interpreter/test caches | generated operational or disposable local state | ignore; they are not part of the documented scientific sequence |
| `writeup/` | reader-facing technical PDF and LaTeX source | keep synchronized with the master Markdown pipeline |

## Regression checks added or retained

- every global stage ID parses as an integer, is unique and is monotone;
- the last global stage remains the model-expansion workbench;
- every live Python, sourcing, HPC, R and interactive entry point is registered;
- the master pipeline is linked from the root README, documentation index and
  replication guide;
- the historical correction wrapper cannot call a provider or mutate data;
- the standalone R suite selects a data frame compatible with the live roster;
- the public/private visibility statement is machine-readable; and
- the existing baseline hash, release, figure and secret-boundary checks remain
  unchanged.

## Remaining decisions

1. Build the final paper release from a clean Git tree after the model roster
   and estimands are frozen. Neither `canon_024` nor `canon_031` is that release.
2. Decide whether T-pro can be recovered and completed. Its current artifacts
   remain workbench-only.
3. Decide whether the public repository should retain row-level responses or
   move them behind a controlled data-access layer before wider dissemination.
4. Complete an independent human accuracy study if the paper is to claim
   absolute annotation accuracy rather than Luna-Sol agreement.
