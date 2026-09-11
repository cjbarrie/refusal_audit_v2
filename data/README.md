# Prompt-sourcing data and fixed geometry

This directory contains Wikipedia/Wikidata harvests, enriched issue records,
route diagnostics and the cached English prompt embeddings. Files are retained
as construction provenance even when only the final sampled battery is analysed.

The R semantic atlas reads `prompt_embeddings_en.csv.gz` and its metadata file.
It fits one 2D UMAP over the 2,496 English prompt embeddings; outcomes never
enter the geometry. Candidate and issue-record families correspond to the
perennial, temporal and current-events routes documented under `docs/` and
`sourcing/README.md`.

PNG files here are sourcing diagnostics, not publication figures. Canonical
figures live only under `pipeline/figures/`.
