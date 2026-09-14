# Canonical R analyses: Luna v2.4 specification

Status: `canon_024` is the promoted working release. It inherits the
hash-verified 18-model estimates from `canon_021`, carries the accepted compact
two-main-figure redesign, and passes 29/29 analysis checks plus 16/16 figure
checks. Its manifest records a dirty working tree and explicit `--allow-dirty`
promotion. A clean-tree rebuild is therefore still required for the final
archival paper release; the estimates and figures described here are the live
canonical working outputs.

`canon_029` is the latest accepted but deliberately non-promoted interim release that
adds the completed Sarvam-105B and Bielik 11B v3.0 generations and Luna v2.4
labels. It inherits the fully recomputed estimates from `canon_025` and passes
29/29 numerical and 17/17 figure checks. It is a figure-only successor to the
same 20-model estimates first computed in `canon_025`.
T-pro-it-2.0 remains outside the analysis until its generation and annotation
are complete. Promotion is deferred so an interim roster cannot silently
replace the working paper release.

The accepted, non-promoted `canon_031` candidate adds 49,879 successfully generated and Luna-coded
responses from Krutrim 2, GigaChat3, EuroLLM 22B and Salamandra 7B. It therefore
uses 299,080 observed responses from 24 models. This document describes that
candidate specification. Its numerical estimates were fully recomputed in
`canon_030`; `canon_031` inherits those hash-verified estimates, corrects the
Russia non-estimability glyph, and passes 29/29 numerical and 17/17 figure
checks. It does not replace promoted `canon_024`.

## Measurement

The current candidate response-behavior analyses use one 299,080-response frame: the
hash-verified 137,186-row original Luna v2.4 table plus three hash-verified
v3 batches and three v4 sources containing 161,894 completed annotations for 13
additional models. The roster, paths, counts and hashes are declared in
`config/analysis_roster_v1.json`. `genuine_refusal` is primary. `capability_failure` is a distinct
diagnostic outcome and may overlap refusal. `original_nonengagement`, defined
as original Gemini `engagement_code >= 4`, exists only for the original 11-model
panel and is retained as a separately labelled measurement sensitivity on that
fixed roster. It is never treated as zero for expansion rows. Luna is a scalable
machine annotator, not a human gold standard.

For the four Torch models, a frozen 1,335-response probability audit compares
Luna with GPT-5.6 Sol. It includes censuses of all Luna refusal positives and
refusal-unassessable cases plus probability samples of capability failures and
apparently clean controls. Inverse inclusion probabilities recover the
49,879-response target population. Sol is a frontier-model reference, not human
ground truth, and its labels never overwrite the Luna census used below.

The exact join and integrity rules are implemented in
`pipeline/_response_validity.R` and documented in
`docs/r_pipeline/_response_validity.md`.

## Result family 1: descriptive response behavior

Report raw counts and proportions for genuine refusal, capability failure and
their overlap overall and by model, language, developer jurisdiction, prompt
tier, topic domain and issue region. These describe the realized delivered
corpus and use no outcome model. Raw model/language rates are not language
effects because prompt composition is not held fixed.

Also report the transition from the original binary engagement annotation to
the four final states: neither outcome, capability failure only, genuine
refusal only, and both. This shows why the outcome definition matters; it is
not an accuracy estimate.

Missing generations and the six exhausted expansion annotations (one Kimi and
five Bielik) are reported and never imputed. Transport failures are not
reclassified as behavioral capability failures. Implementations:
`pipeline/17_response_validity.R` and
`pipeline/40_appendix_descriptives.R`.

## Result family 2: home-region association

For each developer jurisdiction `j`, use English home/away rows and fit:

```r
glm(
  genuine_refusal ~ home * model_f + tier + domain + route_f,
  data = jurisdiction_rows,
  family = binomial()
)
```

For a single-model jurisdiction, omit `home * model_f` and retain `home` plus
varying covariates. Predict every target row twice, setting `home=1` and
`home=0`, and calculate

`Delta_j = sum_i w_i [m_j(1,X_i)-m_j(0,X_i)]`.

The primary `w_i` gives equal weight to models, then issues within model, then
prompts within model-issue. The target is the observed English home/away sample
for that jurisdiction. Report capability failure under the same specification.
Store the two standardized risks as well as their difference, with the identity
`risk_home - risk_away = Delta_j` checked at acceptance.
Report response weights and common support as separate sensitivities. Refit the
original Gemini outcome only within the original 11-model panel and label both
the outcome and changed roster.

Inference uses an issue-cluster percentile bootstrap with 2,000 planned draws
for the primary outcome. Repeated issue draws retain distinct instance IDs;
failed draws are counted and never replaced. The result is predictive
standardization controlling measured composition. It is not causal because
home status is not randomized and region remains related to issue substance.

Implementation: `pipeline/11_canonical_home.R`.

GigaChat3 is assigned to the Russia developer jurisdiction for descriptive,
language and semantic-map analyses. The battery contains no Russia-focused
issue stratum, so a Russia home contrast is undefined. The code records
`home_status = not_defined` and does not substitute Europe or any other region.

## Result family 3: delivered-language contrast

Within each `(model,prompt_id)` block, calculate
`D_i(L)=Y_i(L)-Y_i(English)` for Chinese, Arabic, Russian and Hindi. Average
within model and then give models equal weight. This holds the prompt ID and
subject model fixed. Use genuine refusal as primary and report capability
failure separately. Original non-engagement is sensitivity only.

Store paired English and target-language levels under the same equal-model
target. Their difference must exactly reproduce the paired contrast. The levels
show the baseline from which a language difference arises; the difference
remains the estimand.

Resample whole issues with every paired block intact. Use 2,000 planned draws
for genuine refusal and 500 for diagnostics/heterogeneity. The contrast can be
read as the effect of delivering the tested translated prompt only under
translation-equivalence and stable-run assumptions. It is not the effect of a
user's language.

Implementation: `pipeline/12_canonical_language_framing.R`.

## Result family 4: prompt framing

Within English `(issue_id,model)` blocks containing exactly two regular and two
boundary prompts, calculate mean boundary minus mean regular. Average equally
over models and resample issues. Report genuine refusal and capability failure;
retain original non-engagement as an original-panel sensitivity. A causal interpretation
requires exchangeability of generated variants within issue, which is an
assumption rather than random assignment.

Implementation: `pipeline/12_canonical_language_framing.R`.

## Stability and exploratory analyses

Issue-subsample stability repeats the supported home, language and framing
statistics after sampling declared percentages of issues without replacement.
Each draw is expressed as a deviation from the estimate using all issues. Its
5th--95th percentile ranges are not confidence intervals.

The UMAP uses one fixed coordinate pair per English prompt embedding. Outcomes
colour that geometry but never affect it. It supports qualitative exploration,
not cluster or causal claims. Complementary tables report how concentrated each
outcome is among high-propensity prompts and how many English models exhibit it
for each prompt.

Implementations: `pipeline/15_subsample_stability.R` and
`pipeline/16_prompt_umap.R`.

## Pending analyses

Ideological slant, moral foundations, original-judge reliability and original
justification-taxonomy analyses are not canonical. Their scripts are isolated
under `pipeline/pending/` until the construct, measurement, reliability and
estimand are approved. No live figure or acceptance check consumes them.
