# Exploratory: refusal-text projection (retired)

`refusal_umap.py` and its outputs `u01`–`u03` produced a UMAP projection of
refusal text coloured by the judge's justification code. It shipped briefly as an
Extended Data figure and has been **retired**.

## Why

- **It answered its question in the negative, and the figure did not show that.**
  The point was to ask whether refusals given for different stated reasons differ.
  Neighbourhood purity in the embedding space was 0.57 against 0.44 at random —
  and the *lexical* TF-IDF representation reached 0.58, i.e. at least as high.
  A projection built to show that the codes track meaning showed that they track
  wording at least as well.
- **It was visually uninformative**: a diffuse cloud with heavy overlap between
  every reason group, at a size where individual points were sub-pixel.
- **It was outside the release.** `make_release.R` never rebuilt it, so the
  shipped figure could date from a different run than every other artefact while
  the manifest recorded the whole tree as one release.

## Status

Nothing in the canonical layer reads these files. They are kept only so a reader
who finds the figure in an earlier draft can trace it. The purity statistics
quoted above are in the `purity_group_observed` / `purity_group_baseline`
columns of the CSVs.

To re-run it (from the repository root, no API calls, writes here):

```bash
python pipeline/archive/exploratory_umap/refusal_umap.py --out /tmp/u01.csv
```
