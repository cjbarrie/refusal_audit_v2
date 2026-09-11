# Expanded-model analysis

This directory contains the analysis of seven expansion models together with
the original eleven-model panel. It is deliberately separate from the
canonical release machinery. The current `v3` outputs include Kimi K2.5; the
retained `pre_kimi` outputs are an explicitly historical interim snapshot.

## Included observations

The current assembled file has 224,544 labeled responses from 18 models. The
seven new models are GLM 4.7 Flash, Hunyuan A13B, Kimi K2.5, Ministral 14B,
Gemini 2.5 Flash Lite, Llama 4 Scout, and Nova Lite. One Gemini Hindi request is
absent because the generation provider returned empty content on both
authorized attempts. One Kimi Chinese response is absent because its Luna
annotation failed the evidence-span schema requirement on all three authorized
attempts. Neither record is imputed.

`01_build_expanded_data.R` validates the frozen generation and three annotation
manifests, hashes, and keys before joining the new observations to the existing
analysis data. It writes `derived/expanded_panel_v3.rds` and a build
manifest. `02_estimate_expanded.R` writes the CSV estimates to `estimates_v3/`. Run
`03_figures_expanded.R` only after both prior scripts succeed; it writes six
600-dpi PNG files to `pipeline/figures/expanded_v3/`.

## Outcomes

The two outcomes are never combined:

- `genuine_refusal`: Luna v2.4 classified the behavior as an explicit or
  implicit substantive refusal and the output as coherent or partly coherent.
- `capability_failure`: the response was in the wrong language, incoherent or
  garbled, or had a non-`none` technical-failure code.

These are model-generated annotations. Their measurement basis is documented
in `docs/RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md`.

## Estimands

- Model and language rates are plain realized-sample proportions.
- The home result is an English-only, home-minus-away standardized predictive
  risk difference. For each jurisdiction the logistic model is
  `outcome ~ home * model + tier + domain + route` (without the interaction for
  a one-model jurisdiction). Predictions give equal weight to models, issues
  within models, and prompts within model-issue cells. It adjusts observed
  composition; it is not an identified causal effect. This provisional run
  uses an issue-cluster sandwich covariance matrix and a delta-method 95%
  interval. The final release should restore the canonical issue bootstrap and
  its separation/support gates.
- Language contrasts pair each translated response with the English response
  for the same prompt and model, give models equal weight, and use a 2,000-draw
  issue-cluster bootstrap for the aggregate contrasts.
- Framing contrasts pair boundary-testing and regular prompts within issue and
  model, give models equal weight, and use a 2,000-draw issue-cluster bootstrap.

## Outputs

The current estimate files `e01`--`e08` contain, respectively, model-language rates,
model-pooled rates, jurisdiction home contrasts, model home contrasts,
aggregate paired-language contrasts, model-specific language contrasts,
aggregate framing contrasts, and model-specific framing contrasts. Figures
`E1`--`E6` show the two model-language outcome surfaces, the three main
estimand families, model-specific home contrasts, and fixed-geometry UMAPs for
the seven new models. The UMAP coordinates are reused from the accepted canonical
release; they are not refitted by model or language.
