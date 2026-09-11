# Codebase rationalization audit

> Historical checkpoint from 1 September 2026. It records the repository state
> at that audit and deliberately retains its then-current 11-model counts. For
> the live 18-model analysis surface, use `REPOSITORY_MAP.md` and
> `CODE_ANALYSIS_AUDIT.md`.

Audit date: 1 September 2026  
Working branch: `audit/inference-pipeline-review`  
Pre-audit HEAD: `41543ad`

## Executive summary

The repository now has a small live interface and a provenance-preserving
archive. The current measurement state is explicit: 137,186 corpus responses
have complete Luna v2.4 annotations; the promoted `canon_012` analysis predates
that measurement and is not presented as the final paper release.

The audit inventoried 2,040 initial files (excluding Git internals, virtual
environments and dependency caches), traced direct path references and
entry-point dependencies, and created a file-level registry. It moved 211 files
(390,856,507 bytes) into `archive/2026-09-01_pre_rationalization/`. It moved 448
disposable files (49,514,937 bytes) to the recoverable holding tree
`/tmp/refusal_audit_v2_cleanup_2026-09-01`; no broad or irreversible delete was
used. Every moved file retained its pre-move SHA-256. Raw data, responses,
annotation ledgers, human reviews, codebooks, run manifests and accepted
releases were not moved or rewritten.

No paid API call, response generation, model annotation or external data
transfer occurred.

## Repository state before cleanup

The initial working tree was already materially dirty: 30 tracked files were
modified, one tracked document (`docs/ANALYSIS_HANDOFF.md`) was deleted, and 62
paths were untracked. Those changes were treated as user work and preserved.
The deleted handoff has an exact superseded copy under
`docs/archive/superseded_pipeline/`; it was not silently restored over the
user's deletion.

The largest substantive trees were `annotations/` (about 5.7 GB), `prompts/`
(503 MB), `interactive/` (393 MB) and `pipeline/` (189 MB). Size was never used
as evidence of obsolescence. In particular, the apparently duplicated
`annotations/panel_pilot/` and `annotations/full_v1/` records were retained
because they preserve run-level response/annotation provenance.

The root README and manifest described a six-language, at-most-ten-model state,
a root response directory and an R pipeline with unresolved path patches. The
actual corpus has five languages, 11 models and all material response files
under `annotations/full_v1/responses/`. The former root `responses` object was a
zero-byte placeholder.

## Reconstructed production pipeline

The readable reconstruction is `docs/REPOSITORY_MAP.md`; supported commands are
in `docs/PIPELINE_ENTRYPOINTS.md`.

1. Wikipedia/Wikidata sourcing code in `sourcing/` created retained issue
   records in `data/` and multilingual prompt artifacts in `prompts/`.
2. `scripts/generate_responses.py` produced append-only subject-model JSONL.
   Generation parameters and endpoint-conditioned roster construction are in
   `scripts/config.py` (roster begins at lines 21–45; endpoint models at lines
   57–71; token overrides at lines 115–118).
3. `scripts/annotation_pipeline.py` produced the original Gemini measurement.
   This is now consistently called judge-coded non-engagement when codes 4–5
   are used.
4. `scripts/response_validity.py` and
   `src/refusal_audit/response_validity/` preserve the v2.1–v2.4 development,
   guarded model runs and assembly logic.
5. The final v2.4 repair and merge are documented at
   `docs/RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md:596` and
   `docs/RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md:637`. All 129 initial logical
   conflicts were resolved by Luna; the final hash and counts are at lines
   642–646. Sol was not used for this repair.
6. `pipeline/make_release.R` remains the only R release driver. Stage 17 still
   reads the historical Sol/DSL artifacts (`pipeline/17_response_validity.R:16`)
   and therefore does not integrate the final Luna census.
7. `interactive/build_data.py` now binds the exact v2.4 path/hash at lines
   27–31, enforces 137,186 unique keys at lines 122–139 and requires a complete
   one-to-one join at lines 166–172. `interactive/app.py:204` now filters on the
   v2.4 genuine-refusal field; the fixed gray context geometry and red overlay
   are built at lines 81–128.

## Major provenance and dependency findings

### Final v2.4 assembly is intact

Independent local reading confirmed 137,186 rows and unique response keys,
3,591 `pred_genuine_refusal` positives and 43,317
`pred_capability_failure` positives. SHA-256 remains
`ce1b6c07de09e96912b034195c2c5ab6f2ef7762fbb103143e02913f1383cf75`.
The final manifest attributes 134,664 rows to the main run, 129 to repair and
2,393 to two retained v2.4 reference sets. Component ledgers and manifests were
not altered.

### Accepted analysis and live code have diverged

`pipeline/estimates/canonical/c00_manifest.csv` resolves to `canon_012` and is
byte-identical to that release's manifest. `canon_013` lacks the manifest and
acceptance chain required for promotion. Current acceptance code expects
`Fig2_language.png`, `ED10_framing.png` and `c23`–`c30` response-validity tables
(`pipeline/30_acceptance.R:355` and `pipeline/30_acceptance.R:687`). The promoted
release instead contains `Fig2_language_framing.png`, no ED10 and no c23–c30.
This is why a read-only post-promotion audit fails 12 of 113 checks. It is not
evidence that the stored `canon_012` build changed; it is evidence that the
live code moved ahead of the accepted release.

The figure audit reports the same mismatch plus the expected missing v2.4
figure inputs. The audit passed raster dimensions, 600 DPI, white background,
edge clipping, PNG-only format, table checks that have inputs, plotting/fit
separation and palette checks. No figure was regenerated or renamed.

### Historical interfaces were mixed into the live surface

The Streamlit app directory held nine completed annotation/review pages plus a
read-only explorer. Their durable ledgers live under `annotations/`, so the
pages and UI-specific tests were archived. Pytest is now explicitly restricted
to `tests/` and `interactive/tests/`; it no longer executes archived tests as
if they were live. The two source-module tests that inspected retired pages
were removed, while all data-freeze and assembly tests remain.

### Generated previews and mutable outputs duplicated preserved copies

Every file under the former `preview/` tree was byte-identical to either the
promoted figure tree or the retained incomplete `canon_013` build. Temporary PDF
renders and LaTeX byproducts were reproducible. Mutable root-level `e`/`d`
estimate tables and old appendix tables were retained in the dated archive;
canonical/release copies were not touched.

### Environment reproducibility was implicit

There was no root Python dependency file. `requirements.txt` now records the
tested package families, and `pytest.ini` records the live test roots and
`src/` import path. `.env` remains ignored; the artifact registry intentionally
omits its hash so it does not expose a stable secret-file fingerprint.

## Documentation rationalization

The root `README.md` and new `MANIFEST.md` now state the actual corpus,
measurement and release state. `docs/REPOSITORY_MAP.md` supplies the workflow;
`docs/PIPELINE_ENTRYPOINTS.md` distinguishes local commands, historical
implementations and paid/external stages. `CLAUDE.md` was reduced to scientific
invariants and safety rules.

Sixty-five stale or completed root documentation/data/figure files were moved
to the dated archive. The current response-validity technical pipeline retains
the adopted codebook chronology and exact production settings; separate failed
bake-off, enrichment and planning reports are no longer in the live docs index.
References to retired review pages now resolve to their archive location.
Frozen historical manifests were not rewritten.

The subsequent v2.4 R refactor and expansion integration leave 18 active R
files, each with a header linking to a companion reference under
`docs/r_pipeline/`; `pipeline/PIPELINE_REGISTRY.csv` is the machine-readable
index. Slant, moral-foundation, original-judge and mixed pre-v2.4 scripts now
live under `pipeline/pending/`. Stage 17 describes the final Luna v2.4 census.
The full later audit is `docs/CODE_ANALYSIS_AUDIT.md`.

## Source-code rationalization

Archived source wrappers comprise five superseded root `scripts/` programs and
seven one-off sourcing correction/migration programs. Historical
response-validity modules under `src/` were retained because the guarded CLI
imports them and because they reproduce completed design/model-comparison
records. Removing them would destroy executable provenance without materially
simplifying the supported interface.

The current explorer defect was repaired: the builder no longer reads
`annotations/response_validity_v1/assembled_labels.parquet`; it verifies and
joins the final v2.4 census. Its app no longer presents original Gemini codes
4–5 as the refusal overlay. Tests were updated accordingly.

`pipeline/30_acceptance.R:717` was changed to fail a missing response-validity
family cleanly instead of calling `dplyr::filter()` on `NULL` and aborting before
the acceptance summary. This changes test failure handling, not an estimate.

## Files retained despite appearing obsolete

- All `annotations/response_validity_*` run trees: unique prompts, raw provider
  content, authorization/cost records, translations, human decisions and
  model-comparison provenance.
- `annotations/panel_pilot/`: logically duplicative in places but a distinct
  completed run record.
- `pipeline/releases/canon_012` and incomplete `canon_013`: accepted and failed/
  incomplete release provenance, respectively.
- Japanese and Indonesian prompt/sourcing artifacts: excluded from the current
  corpus but part of the sourcing history.
- `prompts/AI Workshop Invite List.csv`: no live consumer was found, but its
  provenance is unresolved. It was retained as `unknown_requires_review`.
- Historical codebooks/configurations in `config/`: each binds a completed run
  or explains an observed schema boundary.

## Archive and removal results

`docs/ARCHIVE_MANIFEST.csv` contains 659 applied rows:

- 211 `archive` actions: 129 tracked files moved with `git mv`, 82 ignored or
  untracked files moved with their relative paths preserved;
- 448 `delete_recoverably` actions: OS metadata, bytecode/pytest caches,
  accidental `Rplots.pdf`, empty placeholder, temporary renders, preview
  duplicates, LaTeX byproducts and one retired derived app packet.

For every row, `sha256_before == sha256_after`. The script refused to apply if
any source changed after planning. The first sandboxed `git mv` attempt failed
before moving a tracked file; the one already moved `.DS_Store` was restored and
all 333 original sources were revalidated before the approved rerun.

Empty `preview/`, `responses/`, `tmp/` and cache directories were removed after
their files were classified. The R synthetic test recreated `Rplots.pdf`; that
second accidental instance was separately hashed and recoverably removed.

## Scientific or computational behavior changed

No prompt, response, annotation, sample member, estimate, accepted release or
figure changed. The only live computational changes were:

- the local UMAP explorer now uses final v2.4 outcomes;
- pytest ignores archived test trees and imports `src/` explicitly;
- the acceptance gate now reports missing v2.4 tables instead of crashing;
- the main validity CLI help lists only the three current local operations,
  while completed experiment commands remain callable for provenance;
- a pilot budget estimate, if deliberately rerun, writes to ignored `logs/`
  rather than repopulating `docs/`.

## Validation results

| Check | Result |
|---|---|
| Full live Python suite | **145 passed** in 86.88 seconds on the final live tree |
| Interactive tests | **2 passed**; builder/app load v2.4 assets |
| Response-validity registry validator | **PASS** |
| Response-validity documentation validator | **PASS**; final n/counts and historical manifests agree |
| R synthetic estimators | **43 passed, 0 failed** |
| Interactive asset rebuild | **PASS**: 2,496 points, 137,186 responses/labels, zero missing/duplicates |
| Read-only `canon_012` acceptance | **101/113 passed, 12 failed** because current code requires new figure names and absent c23–c30 |
| Figure audit | **failed 7 checks, 1 warning** for the same code/release mismatch; all raster/format/style integrity checks passed |
| Final v2.4 hash/count | **PASS** |
| `git diff --check` | **PASS** after final documentation/registry refresh |

The R acceptance/figure failures are deliberately not “fixed” by generating
new estimates. The next scientific step is to specify the v2.4 estimands and
their uncertainty, implement a new versioned R integration, then build a fresh
non-promoting release. That decision changes paper results and requires owner
approval.

## Unresolved items

1. Agree the exact v2.4 home, paired-language, framing and competence estimands;
   decide which original-Gemini and historical Sol/DSL results remain only as
   sensitivities.
2. Decide whether a selective Sol cascade is scientifically and economically
   useful. It is not needed to claim complete Luna coverage and must not be
   described as already run.
3. Human validation remains incomplete; all “accuracy” claims must specify the
   machine reference used.
4. Resolve or remove `prompts/AI Workshop Invite List.csv` after its owner and
   purpose are established.
5. Before future response generation or prompt enrichment, add the same exact
   payload/cost/authorization guard used by v2.4. The historical generation and
   sourcing scripts are preserved implementations, not blanket authorization.
6. Add an R environment lockfile when the next analysis release is agreed; the
   present release manifest records package versions but the repository has no
   `renv.lock`.

## Final live directory structure

```text
annotations/   retained raw responses, original/revised labels and run evidence
archive/       dated rationalization archive plus earlier stage archives
config/        frozen codebooks and experiment/run specifications
data/          retained sourcing artifacts and embedding cache
docs/          current references, registries and R companions
interactive/   read-only v2.4 refusal explorer and two live tests
logs/          ignored operational logs/estimates
pipeline/      R source, promoted outputs, immutable releases and R archives
prompts/       frozen batteries and review/provenance files
scripts/       supported/provenance entry points, checks and archived wrappers
sourcing/      live sourcing implementation and configuration
src/           response-validity implementation modules
tests/         live Python regression suite
writeup/       current technical source/PDF and archived versions
```

The next supported command is local and non-mutating:

```bash
/Users/christopherbarrie/.pyenv/shims/python3.9 -m pytest -q
```

After estimand approval, the next analysis command should be a fresh candidate
release with `--no-promote`, not a rebuild of `canon_012`.
