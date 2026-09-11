# `_theme.R`

**Purpose.** Enforce one publication design and one PNG-only writer for all paper figures.

**Inputs.** Sources `_orders.R`; plotting scripts pass ggplot/patchwork objects and exact output paths. No scientific rows are selected here.

**Plot specification.** Final-size canvases target 89 mm single-column or 183 mm double-column widths. The approved 183-mm heights are 62, 85, 125, 165 and 225 mm; the final size is reserved for a full-page semantic atlas whose small multiples would be illegible on a shorter canvas. `ragg` writes 600-DPI PNG only. Backgrounds/borders/vertical grids are removed; type uses resolved sans fallbacks; jurisdiction/region palettes are fixed, position and direct labels carry primary meaning, and colour is secondary. Structural zeros must be provided by callers and shown distinctly from estimated nulls. Titles, subtitles, and captions belong outside plots.

Figure 1 additionally uses a seven-colour, colour-vision-safe base palette
locally within each developer-jurisdiction block. A colour identifies a model
only within its labelled block and is reused for that model's semantic marks
and standardized estimate. This avoids asking the reader to distinguish 18
colours simultaneously. The minimum pairwise CIEDE2000 separation in the
largest seven-model block is 23.2 normally, 14.0 under simulated deuteranopia,
and 11.8 under simulated protanopia.

The retained ideology palette is pending compatibility only and does not imply
that a slant or moral-foundation figure is current.

**Outputs.** The caller's `.png`; no SVG/PDF/EPS. `save_fig()` rejects non-PNG paths. Figure scripts store layout RDS files separately for rendered-structure auditing.

**Inference/resampling.** None. Scales may transform display units (typically proportions to percentage points) but never estimates.

**Worked trace.** A 0.032 contrast is plotted at 3.2 percentage points on a shared linear scale; its interval endpoints are transformed by the same factor, then exported at the approved pixel dimensions.

**May infer:** values encoded by marks and externally documented scales. **May not infer:** significance from colour or a structural zero from an ordinary zero point.
