# `_orders.R`

**Purpose.** Single source of truth for jurisdiction, region, model, language, tier, ideology, and moral-foundation ordering and model-to-jurisdiction/home-region mappings.

**Inputs/unit.** No files; named vectors are constants. `assert_known()` checks observed categories. It is sourced by both estimation and figure layers, so a roster change stops instead of becoming missing factor levels.

**Transformations.** Factor helpers preserve frozen substantive order, never data-dependent effect ranking. Stored region `Arab` is displayed as `MENA` elsewhere without mutating data. No missing-data handling, estimand, model, resampling, seed, or output file applies.

Ideology and moral-foundation constants remain only for readable reconstruction
of scripts in `pipeline/pending/`; no active estimator or figure consumes them.

The active candidate roster is 24 models: five China, one Russia, three MENA,
three India, seven US and five Europe. **Worked trace.** `f_model("gpt-4o")` places it in the frozen US
block; `MODEL_JURIS["gpt-4o"]` returns `US`. An unknown model triggers an
assertion rather than being silently dropped from a plot.

`HOME_REGION_OF["Russia"]` is deliberately missing because the prompt frame has
no Russia-focused region. This makes GigaChat eligible for descriptive and
language analyses without manufacturing a home-topic comparison.

**May infer:** category identity/order only. **May not infer:** magnitude or rank from display order.
