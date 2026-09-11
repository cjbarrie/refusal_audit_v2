# Frozen prompt artifacts

The analysis uses the five files
`sampled/rebalanced_prompts_{en,zh,ar,ru,hi}_sample.json`. Each contains the
same 2,496 prompt IDs drawn as 624 complete four-prompt issue blocks. The sample
manifest freezes file hashes and selection details.

The larger `full_*`, `temporal_*`, and `rebalanced_*` families are construction
and translation provenance. Japanese and Indonesian files were produced during
sourcing but are not part of the analysed five-language corpus. Review CSVs and
`excluded_issues.yaml` preserve the human review gate.

No analysis script rewrites prompt text. New prompt batteries require a new
versioned manifest rather than replacement in place.
