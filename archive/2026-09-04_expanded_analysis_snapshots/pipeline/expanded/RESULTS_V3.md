# Expanded v3 results

This is the first 18-model analysis including Kimi K2.5. It contains 224,544
Luna-v2.4-labeled responses. One Gemini Hindi generation and one Kimi Chinese
annotation are explicitly missing; neither is imputed. These outputs have not
yet been promoted through the canonical release machinery.

## New-model descriptive rates

| Model | Jurisdiction | Genuine refusal | Capability failure |
|---|---|---:|---:|
| GLM 4.7 Flash | China | 1.06% | 10.01% |
| Hunyuan A13B | China | 4.32% | 17.86% |
| Kimi K2.5 | China | 10.64% | 10.56% |
| Ministral 14B | Europe | 0.06% | 7.32% |
| Gemini 2.5 Flash Lite | United States | 0.55% | 8.17% |
| Llama 4 Scout | United States | 2.97% | 9.21% |
| Nova Lite | United States | 0.72% | 10.95% |

Kimi varies sharply by delivered language. Its genuine-refusal rates are
10.34% in English, 9.66% in Chinese, 5.33% in Arabic, 17.47% in Russian, and
10.42% in Hindi. Its corresponding capability-failure rates are 0.68%, 1.00%,
4.29%, 2.96%, and 43.87%.

## Main contrasts

The English-only standardized home-minus-away genuine-refusal contrast is
+7.72 percentage points for Chinese models (95% CI: +3.98 to +11.45), +1.83
for MENA models (+0.25 to +3.40), -2.60 for the Indian model (-5.44 to +0.24),
-0.36 for US models (-1.16 to +0.44), and +0.20 for European models (-0.14 to
+0.54). These are adjusted predictive contrasts, not identified causal
effects. The current intervals use issue-clustered sandwich covariance and the
delta method; the canonical release should rerun its full bootstrap and support
gates.

Holding prompt and model fixed, the paired delivered-language differences from
English are -0.03 points for Chinese genuine refusal, -0.55 for Arabic, -0.53
for Russian, and -1.17 for Hindi. Capability-failure differences are +9.75,
+9.53, +14.59, and +62.36 points, respectively. Thus the large multilingual
differences remain capability problems rather than increased refusal.

Boundary-testing prompts produce +2.85 points more genuine refusal (95% CI:
+2.32 to +3.42) and +1.34 points more capability failure (+1.07 to +1.63) than
regular prompts from the same issue.

Adding Kimi changes the Chinese-jurisdiction home-refusal estimate only from
+7.53 to +7.72 points. It changes the aggregate paired Russian refusal contrast
from -0.98 to -0.53 points because Kimi refuses more often in Russian than in
English. Other headline conclusions are substantively stable.

## Reproducible outputs

The estimate tables are in `pipeline/expanded/estimates_v3/`. The six 600-dpi
PNG figures are in `pipeline/figures/expanded_v3/`. Their construction scripts
are `01_build_expanded_data.R`, `02_estimate_expanded.R`, and
`03_figures_expanded.R` in this directory.
