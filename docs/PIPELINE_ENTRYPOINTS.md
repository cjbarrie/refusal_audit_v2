# Supported pipeline entry points

Status: 14 September 2026. Run commands from the repository root. Commands in
this document are the supported live interface; scripts preserved elsewhere
may reproduce historical stages but are not general run instructions.

Read `TECHNICAL_PIPELINE.md` first for the global 00--21 sequence. The section
numbers below organize supported commands; they do not replace those global
stage numbers.

## Environment

The retained local Python environment used Python 3.9:

```bash
python3.9 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
PY=python
```

R package requirements are listed in `pipeline/README.md`. `.env` is ignored
and local. No command may print, copy or commit its values.

## 1. Local integrity checks — no network, no cost

```bash
make baseline-check PYTHON=.venv/bin/python
make private-repo-preflight PYTHON=.venv/bin/python
make python-tests PYTHON=.venv/bin/python
make r-candidate-test CANDIDATE_RELEASE=canon_031
```

`make baseline-check` is read-only. `scripts/audit_repository.py` rewrites only
`docs/ARTIFACT_REGISTRY.csv` when invoked separately with `make audit`.
Pytest covers response-validity freeze/validation logic, last-valid-record
assembly, registry contracts and the interactive builder. The R synthetic suite
uses constructed data and does not change a release.

## 2. Prompt sourcing

The only default-safe sourcing command is the public-API harvest:

```bash
$PY sourcing/run_pipeline.py --editions en zh ar ja id
```

It writes candidate JSON under `data/` and can change as live Wikipedia changes;
it does not reproduce the frozen battery bit-for-bit. `--enrich`,
`sourcing/05_translate_review.py`, `07_enrich_temporal.py` and prompt embedding
call external models. They are retained to explain the completed run but are
not current production commands. Before any new battery expansion, they need a
new frozen-payload/cost/authorization wrapper equivalent to the v2.4 response-
validity guard. Do not run them merely because a key is present.

The exact frozen sourcing artifacts used downstream remain in `data/` and
`prompts/`; historical correction scripts are in the dated archive.

## 3. Response generation and original Gemini annotation

The implementations are:

- `scripts/generate_responses.py` — subject-model responses;
- `scripts/annotation_pipeline.py` — original Gemini engagement/slant/moral
  passes;
- `scripts/run_pilot.py` — sampling, generation, annotation and assembly.

They remain necessary to reconstruct `full_v1`, but they are not an authorized
instruction to regenerate it. `scripts/run_pilot.py --dry-run` is local except
when `--refresh-pricing` is supplied:

```bash
$PY scripts/run_pilot.py --dry-run
```

Any future model expansion must first freeze the exact prompt/model/settings
matrix and estimated cost, then add an explicit authorization record. The
completed pilot, all-language v3 expansion, provider pins, hashes, costs and
exceptions are in `docs/OPENROUTER_MODEL_EXPANSION_V1.md`. Discontinued
provider plans have been moved to the dated documentation archive. Current
local checks are:

```bash
$PY scripts/model_roster.py config/model_rosters/openrouter_expansion_v3_1_all_languages.json
$PY scripts/openrouter_expansion_v3.py prepare
$PY scripts/openrouter_expansion_v3.py cost
```

These commands validate the final roster and reconstruct the frozen v3 payload
and cost records locally; they do not call a provider. Pilot-only and failed
provider command wrappers are retained under `scripts/archive/` and are not
part of the supported interface. Any new paid stage requires a separate hash-
and ceiling-bound authorization; see
`docs/OPENROUTER_MODEL_EXPANSION_V1.md` for the current state and exact hashes.

The next-developer access screen has its own fail-closed command surface:

```bash
$PY scripts/jurisdiction_expansion_smoke.py prepare
$PY scripts/jurisdiction_expansion_smoke.py cost
$PY scripts/jurisdiction_expansion_pilot.py prepare
$PY scripts/jurisdiction_expansion_pilot.py cost
$PY scripts/jurisdiction_expansion_pilot_repair.py prepare
$PY scripts/jurisdiction_expansion_pilot_repair.py cost
$PY scripts/sarvam_105b_smoke.py prepare
$PY scripts/sarvam_105b_smoke.py cost
$PY scripts/sarvam_105b_pilot.py prepare
$PY scripts/sarvam_105b_pilot.py cost
$PY scripts/jurisdiction_pilot_annotation.py prepare
$PY scripts/jurisdiction_pilot_annotation.py cost
$PY scripts/jurisdiction_pilot_sol_audit.py prepare
$PY scripts/jurisdiction_pilot_sol_audit.py cost
$PY scripts/jurisdiction_expansion_full.py prepare --model t-pro-it-2.0
$PY scripts/jurisdiction_expansion_full.py cost --model t-pro-it-2.0
$PY scripts/jurisdiction_expansion_full.py prepare --model bielik-11b-v3.0
$PY scripts/jurisdiction_expansion_full.py cost --model bielik-11b-v3.0
$PY scripts/jurisdiction_expansion_full.py prepare --model sarvam-105b
$PY scripts/jurisdiction_expansion_full.py cost --model sarvam-105b
$PY scripts/jurisdiction_full_annotation.py prepare --model sarvam-105b
$PY scripts/jurisdiction_full_annotation.py cost --model sarvam-105b
$PY scripts/local_gguf_expansion_smoke.py audit
$PY scripts/local_gguf_expansion_pilot.py audit
$PY scripts/gigachat_local_pilot.py audit
$PY scripts/local_gguf_pilot_annotation.py prepare
$PY scripts/local_gguf_pilot_annotation.py cost
$PY scripts/local_gguf_pilot_sol_audit.py prepare
$PY scripts/local_gguf_pilot_sol_audit.py cost
$PY scripts/local_gguf_hpc_full_annotation.py prepare
$PY scripts/local_gguf_hpc_full_annotation.py cost
$PY scripts/local_gguf_hpc_full_annotation_repair.py prepare
$PY scripts/local_gguf_hpc_full_annotation_repair.py cost
```

These commands are local. A full-run annotation contract can only be frozen
after its corresponding generation manifest is complete and hash-valid. The
frozen Hugging Face smoke and pilot phases, the frozen native Sarvam smoke,
and the deferred credential-dependent Krutrim phase are documented in
`docs/JURISDICTION_MODEL_EXPANSION_V1.md`.

The local GGUF commands preserve a separate runtime contract because they use
local Ollama chat or GigaChat's versioned raw-completion repair rather than a
hosted subject-model provider. Their completed 800-record generation
denominator, 799 response-bearing cases and frozen Luna annotation payload are
documented in `docs/LOCAL_GGUF_MODEL_EXPANSION_V1.md`. The annotation `prepare`
and `cost` commands are local; its `run` command remains fail-closed until the
exact payload hash and cost ceiling are explicitly authorized.

The Torch production generation ledger completed at 49,920 terminal records:
49,879 response-bearing cases, 28 empty responses and 13 HTTP/runtime failures.
The full annotation commands above freeze a census of all response-bearing
records under the same blinded v2.4 source-response-only contract. The 41
records without response text remain explicit technical generation outcomes
and are not passed to Luna or imputed as semantic outcomes. Exact hashes,
pricing and guarded run commands are in `docs/HPC_LOCAL_GGUF_FULL_V1.md`. The
main run produced 49,867 valid annotations and 12 exhausted logical conflicts.
The separately authorized repair completed all 12 on its first attempt without
overwriting the source attempts. Its local `assemble` command produced 49,879
unique response labels with explicit main-versus-repair provenance. These
models still require analysis admission and a new immutable R release.

The post-census frontier audit is implemented separately and does not replace
the Luna labels:

```bash
python scripts/local_gguf_hpc_full_sol_audit.py prepare
python scripts/local_gguf_hpc_full_sol_audit.py cost
```

It freezes 1,335 Sol v2.4 reviews: censuses of all 381 Luna refusals and 271
refusal-unassessable records, plus model-language-stratified probability
samples of 298 assessable capability failures and 385 apparently clean
controls. The output retains inclusion probabilities and design weights for
full-population scoring. Its main run produced 1,328 valid labels and seven
exhausted consistency conflicts. The separately authorized seven-case
adaptive repair resolved all seven on its first round, producing a complete
1,335-record lossless assembly and design-weighted scores. See
`docs/HPC_LOCAL_GGUF_FULL_V1.md` for hashes, costs, results, the statistical
rationale and guarded commands.

### Fanar provider-filter experiments

The current local commands are:

```bash
$PY scripts/fanar_system_audit.py audit
$PY scripts/fanar_filter_retest.py prepare
$PY scripts/fanar_retest_sol_annotation.py prepare
$PY scripts/fanar_retest_sol_annotation.py cost
$PY hpc/prepare_fanar_local_pilot.py prepare
$PY hpc/prepare_fanar_local_pilot.py audit
$PY scripts/fanar_local_pilot_annotation.py prepare
$PY scripts/fanar_local_pilot_annotation.py cost
$PY scripts/fanar_local_pilot_sol_audit.py prepare
$PY scripts/fanar_local_pilot_sol_audit.py cost
```

The first command only reanalyses retained records. The completed filter retest
has its own immutable ledger. Its 16 newly returned responses were classified
by Sol v2.4 under the authorized frozen payload recorded in
`docs/FANAR_EXPERIMENTS_V1.md`; do not rerun it. The local pilot requires an
explicit Slurm submission after its files are copied to Torch. Full definitions,
hashes and limits are in `docs/FANAR_EXPERIMENTS_V1.md`. The local pilot has
now completed with 196 non-empty responses and four explicit Hindi generation
failures. Its final two commands freeze and price—without running—the blinded
Luna v2.4 census of those 196 response-bearing records. That census is now
complete. The final two commands above freeze and price an independent Sol
v2.4 census of the same 196 records. That census is also complete; the commands
are retained only to reproduce its immutable request and cost records and must
not be treated as authorization to rerun it.

### T-pro recovery and stability probe

The original T-pro run is terminal but incomplete. Recover preserved HTTP-200
response bodies and reproduce the frozen route-stability probe locally with:

```bash
$PY scripts/tpro_full_recovery.py recover
$PY scripts/tpro_full_retry_probe.py prepare
$PY scripts/tpro_full_retry_probe.py cost
```

These commands make no provider call. The 200-request probe has a separate
hash-bound authorization gate. Do not annotate T-pro or launch the 4,240-key
residual retry until the probe has been run and its route-stability result has
been reviewed. Full counts, hashes and rationale are recorded in
`docs/JURISDICTION_MODEL_EXPANSION_V1.md`.

## 4. Response-validity v2.4

The adopted measurement is already complete. Its implementation is exposed
through `scripts/response_validity.py`, but most subcommands reproduce completed
development experiments and should not be rerun. The live local checks are:

```bash
PYTHONPATH=src $PY scripts/response_validity.py validate-registry
PYTHONPATH=src $PY scripts/response_validity.py validate-response-validity-docs
```

The completed production chain, retained for exact provenance, is:

```text
prepare-wall-to-wall-luna-v2-4
estimate-wall-to-wall-luna-v2-4-cost
authorize-wall-to-wall-luna-v2-4
run-wall-to-wall-luna-v2-4
prepare-wall-to-wall-luna-v2-4-repair
estimate-wall-to-wall-luna-v2-4-repair-cost
authorize-wall-to-wall-luna-v2-4-repair
run-wall-to-wall-luna-v2-4-repair
assemble-final-wall-to-wall-luna-v2-4
```

Prepare/estimate/assemble are local. Each paid run refuses to start unless its
own frozen hash, provider route, disabled-fallback settings, cost ceiling and
explicit authorization record agree. The final assembly is the retained output;
do not recreate it unless an integrity check fails and the cause is established.

The Torch-only probability audit above is the sole implemented selective Sol
stage. It is a new versioned audit and cannot silently replace Luna labels.

## 5. Interactive refusal explorer — local, read-only

```bash
$PY interactive/build_data.py
$PY -m streamlit run interactive/app.py --server.address 127.0.0.1
```

The builder verifies the promoted `c22` UMAP geometry, release-scoped analysis
frame, original v2.4 hash and expansion generation hashes. Under the current
18-model contract it must produce 2,496 prompt points and 224,544 responses. It
resolves the promoted `canon_024` working release and therefore exposes the
18-model panel. The app shows v2.4 genuine refusals and writes nothing.
Generated Parquet assets are ignored.

For the standalone Refusal Observatory:

```bash
$PY interactive/build_web_data.py
cd interactive/web
npm install
npm run dev -- --host 127.0.0.1
```

This browser-data build verifies the Streamlit assets and then fits one
outcome-blind 3-D UMAP to the frozen English-prompt embeddings. It writes
ignored JSON plus a hash manifest under `interactive/web/public/data/`. The
React/Three.js page keeps every prompt visible, supports 3-D rotation and the
canonical 2-D view, and exposes only v2.4 genuine-refusal response records.

## 6. R analysis

The live R source is the accepted, unpromoted 24-model `canon_031` candidate,
while the promoted baseline is the
18-model `canon_024`. Test the source against the matching candidate:

```bash
make r-candidate-test CANDIDATE_RELEASE=canon_031
```

The promoted working release is `canon_024`; it contains the agreed v2.4
estimands and figure set and inherits its verified estimates from `canon_021`.
A candidate build uses a new immutable ID:

```bash
CANONICAL_RUN_ID=<new_id> Rscript pipeline/make_release.R --no-promote
```

After inspecting its manifest, acceptance table and figures, remove
`--no-promote` only for a new ID and a stable tree. Never rebuild an existing
release or select one by the largest numeric suffix. `canon_013` is incomplete.

## 7. Repository audit maintenance

The 1 September cleanup is complete. To refresh only the file registry after
future changes:

```bash
$PY scripts/audit_repository.py
```

The former one-off cleanup driver is retained under
`scripts/archive/repository_cleanup/`; it is not a current command. The applied
hash record is `docs/ARCHIVE_MANIFEST.csv`.
