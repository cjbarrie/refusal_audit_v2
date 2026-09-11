# `audit_figures.R`

This read-only gate checks the rendered figure surface. It requires exactly
Figures 1--2 in the main directory and ED1--ED14. Any SVG, PDF or EPS in the
active figure directories fails; every PNG must be nonempty.

The two saved layout RDS files are inspected to ensure no title, subtitle or
caption is embedded. Exact genuine-refusal home and language source-row counts
are checked against `c04` and `c08`. The gate also verifies that capability
failure does not enter the main plotting code and that the jurisdiction atlas
retains model membership in multi-model refusal glyphs.
The plotting source is scanned to ensure it fits no model, performs no
bootstrap, writes no scientific table and does not reference slant, moral or
pending reliability outcomes.

The script prints every named check and exits nonzero on failure. It produces no
scientific output and cannot certify subjective aesthetic quality; that still
requires visual inspection of the PNGs at final size.
