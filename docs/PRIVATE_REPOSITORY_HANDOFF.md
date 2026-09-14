# Git repository handoff and disclosure checks

The configured GitHub repository, `cjbarrie/refusal_audit_v2`, is public
(verified 14 September 2026). The filename is retained because other manifests
and documents already point to it. This document governs commits and pushes of
the rationalized replication tree. It does not itself authorize a commit, push
or release promotion.

## Before committing

Run:

```bash
git lfs install
make baseline-check PYTHON=.venv/bin/python
make private-repo-preflight PYTHON=.venv/bin/python
make python-tests PYTHON=.venv/bin/python
make r-candidate-test CANDIDATE_RELEASE=canon_031
make web-test PYTHON=.venv/bin/python
git diff --cached --check -- . \
  ':(exclude)archive/**' \
  ':(exclude)docs/ARCHIVE_MANIFEST.csv' \
  ':(exclude)docs/archive/**'
```

The preflight examines files already tracked and files Git would add. It fails
if `.env` is tracked, if a high-specificity credential pattern appears in a
prospective text file, if the `origin` remote is absent, or if a file reaches
GitHub's 100 MiB hard limit. It reports paths but never matched values.

Files between 10 and 100 MiB produce warnings. The promoted `data_clean.RData`
and three archived binary analysis snapshots are assigned to Git LFS by the
root `.gitattributes`; the exact paths remain in the repository while ordinary
Git stores pointers. The remaining warnings are large text prompt/provenance
files. They remain in ordinary Git because they are scientific inputs that
benefit from transparent paths and content inspection. Revisit that decision
before wider dissemination or if repository growth becomes material. Do not delete
scientific inputs without first recording their hashes and access route.

## Commit boundary

The first rationalized commit should include source code, current documentation,
registries, tests, environment locks, the promoted estimate/figure tree and the
dated archive map. It should not include:

- `.env` or any account credential;
- unrelated personal contact lists retained locally in dated archives;
- raw response or annotation ledgers ignored under `annotations/`;
- provider logs or NYU Torch scratch outputs;
- `pipeline/releases/`, which duplicates the promoted tree locally;
- browser dependencies, build directories or generated interactive data; or
- temporary render, cache or LaTeX-intermediate files.

The large-data decision must be made before staging the entire tree. Review the
candidate set with `git status --short` and `git diff --stat`; do not use a blind
`git add .` until the warnings from the preflight have been resolved.

## Final archival release

`canon_024` remains the promoted working baseline and `canon_031` is the
accepted, unpromoted 24-model candidate. Neither was built from a clean Git tree. After
the model roster and estimands are frozen, commit the rationalized source tree,
build a newly named candidate from that commit, run all gates, and promote only
that new immutable release. Record its commit SHA in the release manifest.

## Webpage

Keep `interactive/web/` in this repository for now. Before a separate site
deployment, produce a minimal browser-data export, check every exposed field,
update dependencies, resolve the current production-audit warnings, and perform
a disclosure review. The site repository must not inherit raw annotation or
provider-run history.
