# `12_canonical_language_framing.R`

## Language contrast

For each Chinese, Arabic, Russian or Hindi response, the script locates the
English response from the same `(model,prompt_id)` block. It forms
`Y_target-Y_English` and averages block differences equally over subject
models. Missing arms are counted explicitly and never imputed.

`c08` also stores the equal-model paired English and target-language mean for
each language. `c09` stores the same two levels separately by model. In each
case `mean_target - mean_english` exactly reproduces the reported paired
difference. These levels supply context for the contrast; they do not replace
the prompt-paired estimand.

The primary outcome is Luna v2.4 genuine refusal. Capability failure is a
separate diagnostic; original Gemini non-engagement is a measurement
sensitivity. `c09` repeats the current outcomes separately by model as
exploratory heterogeneity.

Because the exact prompt ID and model are fixed, this is stronger than comparing
unpaired cell rates. A causal reading is nevertheless conditional on the
translations representing the same task and on stable language-specific
generation/provider conditions. It is not the effect of a user's language.

## Framing contrast

For English responses, each `(issue_id,model)` block must contain exactly two
regular and two boundary prompts. The block statistic is mean boundary minus
mean regular, then averaged equally over models. Incomplete blocks are written
to `c10b` and excluded. The prompts were generated, not randomized, so a causal
framing interpretation requires exchangeability of variants within issue.
The regular and boundary levels in `c10` use the same equal-model target as the
contrast, so their difference is an exact accounting identity.

## Inference and outputs

Both analyses resample whole issues, preserving all paired blocks and repeated
issue instances. Primary rows use 2,000 planned draws by default; diagnostic
and model-specific rows use 500. Each statistic uses the release seed plus a
deterministic offset derived from its diagnostic label; `c18` records the exact
resulting seed rather than only the common base seed. The outputs are:

- `c08_language_paired.csv` and `c08b_weighting_comparison.csv`;
- `c09_language_by_model.csv`;
- `c10_framing_paired.csv` and `c10b_framing_incomplete_blocks.csv`;
- `c11_framing_by_model.csv`.

`c08c_original_nonengagement_sensitivity.csv` and
`c10c_original_nonengagement_sensitivity.csv` repeat the original Gemini
measure only for the original 11-model panel. They are kept out of `c08` and
`c10` so an unavailable expansion label cannot be silently interpreted as zero.

## Worked example

If model m genuinely refuses Arabic prompt p but not its English counterpart,
that complete block contributes `1-0=1`. If the Arabic response is instead
garbled without refusal, the refusal difference is zero while the capability-
failure difference may be one. The two mechanisms therefore remain visible.
