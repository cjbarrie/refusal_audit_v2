# Repository replication-readiness audit

Audit date: 11 September 2026. Scope: all top-level directories, every live
Python/R/shell/Slurm entry point, current documentation, promoted and candidate
release pointers, generated-artifact boundaries, dependency specifications and
the private Git remote. No provider call, Slurm submission, release promotion or
Git push was made during this audit.

## Findings and resolutions

| ID | Severity | Finding | Resolution |
|---|---:|---|---|
| C01 | P0 | The promoted artifact is `canon_024` (224,544 responses, 18 models), while live R code targets 249,201 responses and 20 models. A bare test could combine the wrong code and data profile. | Added `config/replication_contract.json`, `docs/REPLICATION_GUIDE.md` and profile-specific Make targets. `make baseline-check` verifies the promoted artifact; `make r-candidate-test` points the live code at `canon_029`. |
| C02 | P1 | Later release directories passed their gates but were neither promoted nor clearly distinguished from the baseline. | `docs/REPLICATION_STATUS.md` names `canon_029` as accepted and unpromoted, and records that both releases were built from dirty trees. Numeric suffixes are never treated as promotion. |
| C03 | P1 | Sourcing, HPC and interactive scripts were absent from the executable registries. | Added exhaustive local registries under each directory and extended the read-only replication check to reject an unregistered live script or a missing companion document. |
| C04 | P1 | Python dependencies had bounded ranges but no exact replication snapshot; R dependencies had no lockfile. | Added `requirements-lock.txt` from the Python 3.9 environment and `renv.lock` from R 4.4.1. The browser already has `package-lock.json`. Historical provider manifests remain authoritative for remote model behavior. |
| C05 | P2 | Root instructions contained a machine-specific Python path and the HPC guide contained a machine-specific local repository path. | Replaced them with a project virtual environment and an explicit `LOCAL_REPO` placeholder. |
| C06 | P2 | Python bytecode, pytest state and technical-writeup render fragments were present in the working tree. | Removed only those reproducible caches and added root ignore rules. Scientific generation logs and append-only annotation ledgers were retained. |
| C07 | P1 | The file registry walked `node_modules` and browser build directories, inflating the inventory to more than 44,000 dependency files. | Excluded dependency/build caches and regenerated a 3,541-row scientific repository registry with zero unresolved files. |
| C08 | P0 | A GitHub remote already existed, while the intended visibility was described as future work. | Verified read-only that `cjbarrie/refusal_audit_v2` is private. Nothing was pushed and visibility was not changed. |
| C09 | P1 | The standalone web page lives beside protected row-level run state and has not had a public disclosure review. | It remains local and private under `interactive/web/`. Public hosting and repository separation are explicitly deferred. |
| C10 | P1 | A blind first commit could include credentials or unsuitable large artifacts. | Added a value-suppressing private-repository preflight and a documented commit boundary. Four large binary analysis frames are assigned to Git LFS; six large text prompt/provenance inputs remain visible in ordinary Git. The check passes credential and 100 MiB gates. |

## Evidence from checks

- Frozen baseline: 17/17 replication checks passed.
- Focused documentation, registry, HPC, interactive and private-repository tests: 21/21 passed.
- Full Python suite: 187/187 passed.
- Current R candidate contract: 13/13 passed against `canon_029`.
- Standalone web lint and production build: passed.
- Artifact registry: 3,541 files; 64 promoted canonical, 518 active
  supporting, 2,959 historical provenance, zero unresolved. Superseded files
  are represented at their archived paths rather than as missing live paths.

The R run emitted macOS sandbox warnings when Arrow queried CPU-cache metadata;
the tests still completed successfully. Several installed R packages were built
under R 4.4.3 although the interpreter is R 4.4.1; `renv.lock` now makes that
dependency state explicit for a clean restore.

## Remaining blockers before a public replication release

1. Finish or formally stop the current T-pro, NYU Torch and Fanar workbench
   runs; admit only models that pass the documented gates.
2. Freeze the final estimands and model roster.
3. Commit the rationalized tree, then build a new release from a clean commit.
   Neither `canon_024` nor `canon_029` meets this final clean-tree standard.
4. Decide which large ignored response and annotation artifacts can be shared,
   and provide a protected-data acquisition or checksum procedure for those
   that cannot.
5. Review and update the standalone browser dependencies before public hosting.
   The current build succeeds but reports a large client chunk, and the local
   dependency audit has previously reported production vulnerabilities.
6. Perform a disclosure review before exporting prompt/response text to a
   separate public site repository.
