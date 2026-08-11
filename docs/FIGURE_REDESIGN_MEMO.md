# Graph-type challenge: what was compared, and what won


> **⚠ DATED RECORD — this compares graph types for release `canon_010`.** The
> later restructure (`canon_011`) revisited several of these decisions: Figure 1
> became a single overlaid forest with the rates removed entirely, the language
> model-distribution strip was dropped in favour of ED4, and ED2/ED3 were
> re-scoped. The comparison logic below is why each form was chosen at the time.
> **For what actually ships, read `docs/CANONICAL_FIGURE_LEGENDS.md`.**

Companion to [`FIGURE_ESTIMAND_AUDIT.md`](FIGURE_ESTIMAND_AUDIT.md). For every
panel, at least two visual forms were considered before any code was written.
The selection criteria, applied in this order:

1. **correspondence to the estimand** — does the mark encode the quantity the
   table holds, at the same level of aggregation and conditioning?
2. **uncertainty visibility** — is the interval as legible as the point?
3. **perceptual accuracy** — position beats length beats area beats colour.
4. **final-size legibility** at 183 mm, checked on the rendered raster.
5. **cognitive load** — how many lookups before the panel can be read?
6. **graphical economy** — ink that is neither data nor required structure.

A panel was kept unchanged wherever the incumbent won. Four did.

---

## 1. Home observed rates (Fig 1a)

| form | correspondence | uncertainty | perception | verdict |
|---|---|---|---|---|
| **dumbbell, both endpoints labelled** | exact — two rates, one row | none available at this level | position on a common scale; the gap is the visual object | **chosen** |
| two-column dot table | exact | none | loses the gap as a single perceptual object; the reader differences two columns | rejected |
| paired slope | exact | none | slope encodes the difference as an angle, the least accurate channel here | rejected |
| grouped bars | exact | none | bars encode a rate as length from a zero that is not the comparison point | rejected outright |

The incumbent geometry was right. What changed is that **both** endpoints are
now labelled, so the panel stops privileging the absolute home rate over the
contrast it exists to show, and EU is drawn as a hollow square with the words
`no refusals` rather than as a filled point at 0.

## 2. Unadjusted home−away difference (Fig 1b) — newly plotted

This quantity was in `c02` with a bootstrap interval and was not displayed
anywhere.

| form | verdict |
|---|---|
| **dot + 95% interval, one row per jurisdiction, hollow marker** | **chosen** — same geometry as the adjusted panel so the two are directly comparable, hollow marker so they are not confusable |
| printed number only, at the right of panel a | rejected: discards the interval |
| omit, as before | rejected: an estimated interval that never reaches the reader |

**Risk accepted and mitigated.** Placing the descriptive and the standardized
difference in adjacent aligned panels is what the audit warned about — it can
read as two attempts at one number. Mitigations: different x-axis titles
(`Unadjusted difference` vs `Standardized difference`), hollow vs filled
markers using the theme's existing `SHAPE_ESTIMAND`, separate panel letters,
and no shared axis.

## 3. Standardized contrast (Fig 1c)

| form | verdict |
|---|---|
| **dot + interval on a common linear axis** | **chosen** |
| common axis + magnified near-zero inset | rejected — MENA/India/US remain readable at 183 mm once the panel gets the width the map was using; an inset would add a second scale to buy nothing |
| two aligned scale zones | rejected — a broken axis for a four-estimate panel |
| bars / lollipops | rejected — a bar from zero misencodes a difference that is itself measured from zero |
| odds-ratio axis | rejected — non-collapsible, and the estimand is on the probability scale |

Scale decision: **Option 1**, common linear axis. Removing the map frees enough
width that CN's interval to +24.8 and MENA's +1.3 to +6.3 coexist legibly.

## 4. Language effects (Fig 2)

The central question: is the result the pooled shift, or the heterogeneity?
The data answer it — pooled effects span 1.3 to 8.5 pp, per-model effects span
−6.0 to +61.4 pp. Heterogeneity is an order of magnitude larger and is the
substantive finding.

| form | correspondence | uncertainty | verdict |
|---|---|---|---|
| **pooled forest (4 rows, tight axis) + model-distribution strip (4 rows, shared axis)** | both aggregation levels, each on an axis suited to its range | pooled interval drawn; model intervals in ED | **chosen** |
| heatmap alone, in the main figure | exact values, but colour saturated by two cells and no uncertainty at all | none | **rejected for the main figure; relocated to ED4** |
| four aligned per-language forests | exact | full | 44 rows; at 183 mm the labels fall below 5 pt | rejected for main, **retained as ED4b** |
| pooled + model distribution on one shared axis | forces a ±61 axis on estimates of ±2 | pooled interval invisible | rejected |

**Scale decision for the distribution strip:** one shared x-axis across all
four languages, as required — Hindi genuinely disperses more than Chinese and
per-facet normalisation would destroy that. No log scale (the quantity is a
percentage-point difference and includes negatives and zeros). Extreme models
are directly labelled rather than left to the reader.

**Structural zeros.** `mistral-large-2512` produced no refusals in any
language, so its four "0.0" cells are not estimates of a null effect. It is
drawn as a hollow square, the same encoding used for EU in Fig 1, and excluded
from the heatmap's colour scale.

## 5. Prompt framing (Fig 2c)

| form | verdict |
|---|---|
| **contrast forest, pooled as an accent diamond above a rule, per-model rows below ordered by effect** | **chosen** — the estimand *is* boundary − regular |
| regular/boundary dumbbell of absolute rates | rejected — displays two levels when the canonical quantity is their difference |
| hybrid (rates left, contrast right) | rejected — doubles the width for a baseline the argument does not use |

The pooled row is made visually primary (larger, accent, above a separator);
the eleven per-model rows are neutral grey and explicitly exploratory in the
legend. Sign reversal across models (sarvam +8.3, falcon −5.6) stays visible,
which is the point.

## 6. Ideology (Fig 3a)

| form | correspondence | verdict |
|---|---|---|
| **full five-category 100% stacked distribution per dimension** | exact — the estimand is a five-bin distribution summing to one | **chosen** |
| mean placement + neutral share column | encodes a `SECONDARY` quantity as primary, and hides symmetric tails | rejected |
| four directional bins, neutral annotated (incumbent) | plots 8–20% of a distribution and annotates the rest | **rejected — this is the estimand/graphic mismatch the audit found** |
| five separate dot-and-interval rows per dimension | exact, and carries intervals — but four dimensions × five bins = 20 rows and the neutral bin's dominance is lost | rejected |

The neutral segment now dominates visually exactly as it dominates empirically
(79.5–92.4%). Cost, accepted and stated: a stacked composition cannot carry a
per-bin interval. The intervals remain in `c12`, and the panel is labelled
descriptive/exploratory with its α values in the legend. Direct labels are
printed for the neutral share and for any tail above 3%.

## 7. Moral foundations + agreement (Fig 3b/c)

| form | verdict |
|---|---|
| **one row-label column, two aligned value columns (prevalence, PSA), shared row order** | **chosen** — the incumbent's alignment idea, executed as a single compound panel with the labels written once |
| two independent panels each with its own labels | rejected — repeats six category names and reads as unrelated |
| PSA printed as text beside the prevalence points | rejected — puts two quantities on one axis, which an earlier version did |

The two columns keep separate axes and separate axis titles, because they are
different quantities: the prevalence bar is a 95% issue-cluster sampling
interval; the PSA bar is a min–max over six judge pairs and carries no coverage.
They are drawn with different geometries (interval vs light range whisker with
tick ends) so the distinction survives without a legend.

## 8. Judge sensitivity (ED1)

| form | correspondence | uncertainty | verdict |
|---|---|---|---|
| **paired difference from the canonical judge, bootstrapped in the same replicates** | exact match to the question "how much does the estimate move when the judge changes" | paired interval, correctly narrow | **chosen — requires new estimation** |
| absolute estimates under each judge (incumbent) | answers "what does each judge produce", not the sensitivity question | four marginal intervals the reader must difference by eye | **relocated to a table (`c17b`, already exists)** |
| absolute estimates + subtracted points with inherited marginal intervals | **statistically wrong** — the judges label the same responses, so their estimates are strongly dependent and marginal intervals badly overstate the difference's uncertainty | — | rejected |

Zero on the new axis means the alternative judge reproduces the canonical
judge's estimate. The canonical judge is a **reference instrument, not ground
truth**: no human-validated labels exist, so no judge is known to be correct
and no majority is computed.

The range bracket is deleted. With every judge's deviation plotted, the bracket
was three segments and a text label restating the spread of the points beneath
it.

## 9. Multiverse sensitivity (ED2)

| form | verdict |
|---|---|
| **jurisdiction-centric: one facet per jurisdiction, sensitivity families stacked and separated within** | **chosen** — matches the reader's question, "is the CN conclusion robust?" |
| specification-family facets (incumbent) | rejected — forces a per-facet colour hunt for one jurisdiction's rows |
| specification curve | rejected — a curve asserts that every row is an alternative estimate of one quantity; several rows here change the target |

Non-estimable rows are omitted rather than given empty space, and named in a
terse `not estimable (n)` marker per family so their absence is visible without
costing a labelled row each. The empty functional-form facet disappears.

## 10. Post-outcome diagnostics (ED3)

Split into its own PNG. The comparison was "keep as a labelled sub-panel of
ED2" against "separate figure"; separate won because a shared figure number is
itself a claim of kinship, and response-length filtering conditions on a
realized property of the outcome.

## 11. Reliability (ED5)

| form | verdict |
|---|---|
| **construct × metric matrix (raw agreement, Krippendorff α, Gwet AC1/AC2, PSA)** | **chosen** — makes the divergence between prevalence-sensitive and prevalence-adjusted statistics visible instead of implying they are interchangeable |
| single forest of one statistic | rejected — engagement has α = 0.51 and AC1 = 0.97 on the same data; one number cannot represent that |

Built only because the canonical measurement layer already carries all four
metrics for every construct in `e23`, `e24` and `e25`. No new estimation.

---

## Typography, colour and geometry decisions

**Canvas templates.** Four, and every figure uses one:

| template | size | used by |
|---|---|---|
| `short` | 183 × 62 mm | ED3 |
| `wide` | 183 × 85 mm | Fig 1, Fig 3, ED1 |
| `standard` | 183 × 125 mm | Fig 2, ED4 |
| `tall` | 183 × 165 mm | ED2, ED5 |

No script chooses its own dimensions. `short` was added after review: ED3 has
three rows, and at 85 mm the row pitch was pure whitespace. `audit_figures.R`
checks every rendered height against this list.

**Type.** One sans family everywhere, including model names — the monospaced
model labels were dropped because at 7 pt Courier reads as a different class of
object from the axis text. Sizes are fixed centrally: panel letter 8 pt bold,
facet/category 6 pt, axis and ticks 6 pt, direct annotation 5 pt. Nothing below
5 pt.

**Colour carries one meaning at a time.** Jurisdiction hues are reserved for
jurisdictions and for models keyed to their developer's jurisdiction. Judge
sensitivity is greyscale with one accent for the canonical reference. Ideology
uses a dedicated diverging palette with a very light neutral. Language is
encoded by position, never by the jurisdiction red.

**Connectors versus intervals.** Standardised so no legend is needed: a
confidence interval is thin, dark and centred on its estimate; a dumbbell
connector is thicker, much paler, and runs only between two paired endpoints.

**Precision.** One decimal where the interval half-width is below 1 pp; integer
percentage points for the large model × language effects. `−0.0` and `+0` are
normalised to `0`, and a structural zero is never printed as a numeral at all —
it gets the hollow square and the words.
