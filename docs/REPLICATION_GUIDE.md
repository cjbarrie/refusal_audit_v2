# Replication guide

This is the shortest supported route through the repository. It separates the
frozen paper pipeline from ongoing model-expansion work. Commands in this guide
are read-only or local unless they are explicitly marked as an external call.

## What is being replicated

There are currently three accepted analysis states:

1. **Promoted baseline (`canon_024`)** — 224,544 observed responses from 18
   models. This is the release shown by `pipeline/estimates/canonical/`, the
   committed figure tree and both interactive explorers.
2. **Earlier unpromoted candidate (`canon_029`)** — 249,201 observed responses from 20
   models, adding Sarvam-105B and Bielik 11B v3.0. It passed the current gates,
   but was built from a dirty tree and has not replaced the promoted baseline.

3. **Accepted 24-model candidate (`canon_031`)** — 299,080 observed responses
   after adding the four completed Torch models. It passes 29/29 numerical and
   17/17 figure checks but remains unpromoted.

The live R source describes the 24-model candidate. It should not be used to
claim that `canon_024` was rebuilt from the present checkout. These releases
record `git_dirty=TRUE`; neither is the final clean-tree archival release.
`config/replication_contract.json` records these facts in machine-readable form.

## 1. Create the local environments

The retained Python work used Python 3.9. Install the exact direct dependencies
into an isolated environment:

```bash
python3.9 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
```

The R analysis used R 4.4.1. Restore the project library with:

```bash
Rscript -e 'if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv")'
Rscript -e 'renv::restore(prompt = FALSE)'
```

The standalone browser requires Node 22.13 or newer. Its exact JavaScript
dependency graph is pinned by `interactive/web/package-lock.json`.

## 2. Verify the frozen baseline

```bash
make baseline-check PYTHON=.venv/bin/python
```

This makes no network or provider call. It verifies:

- the five sampled prompt-file hashes;
- the original-panel Luna v2.4 outcome hash;
- the promoted release pointer, row count, model count and 29 acceptance gates;
- byte identity between the promoted and immutable `canon_024` manifests;
- byte identity of the promoted and `canon_024` PNGs;
- exhaustive registration of live sourcing, Python, R, HPC and interactive
  scripts; and
- that `.env` is not tracked by Git.

The baseline is a frozen artifact replication. Its paid upstream calls are not
reissued. Exact provider inputs, model routes and generation settings are
retained in the relevant manifests and technical documents.

## 3. Follow the scientific pipeline

The complete narrative is `TECHNICAL_PIPELINE.md`; the ordered,
machine-readable map is `config/REPLICATION_STAGES.csv`.

| Stage | Input | Transformation | Retained output |
|---|---|---|---|
| 01–07 | Wikipedia/Wikidata pages | harvest three routes, enrich, merge, construct, amend, translate, review and sample | five frozen 2,496-prompt batteries |
| 08 | frozen prompts and original subject-model roster | generate one response per available model-language-prompt key | append-only original response JSONL |
| 09 | original responses | original Gemini annotation | non-engagement sensitivity labels |
| 10–12 | reviewed development cases, response text and v2.4 codebook | refine the codebook, select Luna and annotate the original panel | one v2.4 label per original response key |
| 13–15 | accepted hosted and Torch models | generate, annotate and audit expansions | hash-registered expansion batches |
| 16 | original and accepted expansion batches | hash checks, metadata joins and exact-key assembly | release-scoped `data_clean.RData` |
| 17 | analysis frame | home standardization, paired language contrasts and descriptive measurement analyses | numbered CSV estimate tables |
| 18 | estimates and fixed UMAP geometry | render, accept and freeze without refitting in figure code | immutable release and 600-dpi PNGs |
| 19 | promoted release | build read-only explorer assets | local Streamlit and web interfaces |

Detailed inputs, outputs and inference limits are in
`CANONICAL_ANALYSES.md`, `R_PIPELINE_WALKTHROUGH.md` and `r_pipeline/`.

## 4. Test the current 24-model code

Because the live R code has advanced beyond the promoted baseline, its tests
must point explicitly at the matching candidate data:

```bash
make r-candidate-test CANDIDATE_RELEASE=canon_031
```

To build another candidate without promotion:

```bash
make candidate-release RUN_ID=canon_032
```

Never reuse a release ID. Inspect the new manifest, acceptance table and PNGs
before considering promotion. The final paper freeze must come from a clean Git
tree and use a new release ID.

## 5. Build the explorers

```bash
make interactive-data PYTHON=.venv/bin/python
make web-test PYTHON=.venv/bin/python
make interactive-web
```

Both explorers resolve the promoted pointer, so they deliberately remain on
`canon_024` until a later release is explicitly promoted. Generated Parquet,
JSON, build and dependency directories are ignored.

## 6. Paid and external stages

No `make` target submits a Slurm job or calls a model provider. Wikipedia
harvesting, response generation, translation and model annotation are separate
operational stages. A paid stage is runnable only after it has a frozen payload
hash, pinned model/provider route, request or cost ceiling, retry rule and
explicit authorization. The presence of a key in `.env` is never authorization.

Ongoing API and HPC expansion work is described in `REPLICATION_STATUS.md`.
Those records do not enter the paper pipeline until their generation is
complete, their v2.4 annotations pass the declared quality gate, and a new R
release explicitly includes them.

## 7. Public repository and eventual site split

The configured GitHub repository, `cjbarrie/refusal_audit_v2`, is public. This
was verified on 14 September 2026. The standalone webpage remains under
`interactive/web/` for now. When it is split into a site repository, export
only the minimal browser assets after a disclosure review; do not copy `.env`,
raw ledgers, endpoint URLs, account identifiers or hidden reasoning text.

Before staging or pushing, run:

```bash
make private-repo-preflight PYTHON=.venv/bin/python
```

The exact commit boundary and large-file decisions are documented in
`docs/PRIVATE_REPOSITORY_HANDOFF.md`. The filename is retained for link
stability; the document now governs public-repository disclosure checks.
