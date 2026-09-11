# `16_prompt_umap.R`

This exploratory stage fits one semantic geometry to the cached English prompt
embeddings. Input `data/prompt_embeddings_en.csv.gz` must contain one unique
512-dimensional vector for each of the 2,496 prompt IDs in the analysis frame.
The cache was produced outside the R release; this script makes no API call.
It stops unless all 2,496 prompt IDs match the analysis frame exactly, all 512
embedding coordinates are finite numeric values, every vector has positive
norm, and prompt metadata is unique at the prompt level.

`uwot::umap()` uses cosine distance, 25 neighbours, minimum distance 0.15 and
seed 20260809 unless explicitly overridden. Outcomes never enter the fit. The
same `(umap_x,umap_y)` for a prompt is reused in every language and model view;
separate facet-specific UMAPs are forbidden because their coordinates would not
be comparable.

The long propensity table reports genuine refusal and capability failure by
prompt/language. It gives jurisdictions equal weight
and models equal weight within jurisdiction; the `ALL` row also weights
languages equally. These are descriptive propensities, not effects.

Outputs are `c22_prompt_umap_coordinates.csv`,
`c22_prompt_outcome_propensities.csv`,
`c22_prompt_outcomes_by_model.csv`, `c22b_prompt_concentration.csv`,
`c22c_prompt_cross_model_counts.csv`,
`c22d_prompt_cross_model_distribution.csv`,
`c22_prompt_umap_diagnostics.csv` and `c22_prompt_umap_metadata.json`.

`c22b` ranks prompts by their all-language, equal-jurisdiction/equal-model
outcome propensity and records the cumulative share of all propensity mass.
`c22c` counts, for each English prompt, how many subject models exhibit the
outcome; missing response cells remain missing and cannot inflate the count.
`c22d` summarizes the distribution of those counts. These are descriptive
concentration and cross-model recurrence measures.

Main Figures 1--2, ED11--ED14 and the interactive explorer consume these tables. Language and
model maps always reuse the single coordinate system; the model maps use
English outcomes to avoid changing both model and language at once. A point's
apparent neighbourhood is a qualitative locator, not proof of a substantive
cluster or meaningful Euclidean distance.
