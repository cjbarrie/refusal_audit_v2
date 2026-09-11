# Human rare-class enrichment design simulation

> **Superseded after coder language review.** This simulation used the original
> translation-led labels, which contained zero coded wrong-language cases. The
> corrected freeze contains 15 wrong-language cases and two mixed cases. Do not
> draw the proposed 60-row screen; rebuild any enrichment design from
> `base_freeze_v2_language_corrected/`.

> **Status: planning only.** No response IDs were selected, no review packet or translation payload was created, and no network or paid model call was made. Additional human work is not authorized.

## Why an enrichment wave is needed

The immutable 300-row human pilot cannot yet support a clean exemplar/evaluation split for all seven primary classes. The realized deficits are 14 wrong-language, 10 technical-degeneration, 10 ambiguous, and 6 coherent-pivot judgments. These are realized-class deficits: a label-blind draw must be larger because true classes are unknown until coding.

## Label-blind routing

Candidate strata are disjoint and applied in this order:

1. exact GPT-5.6 Sol wrong-language signal;
2. deterministic script plus metadata language mismatch;
3. the maximum of technical, ambiguous, and pivot routing scores when that score is in its population top decile;
4. general remainder.

The three learned routing scores use four-fold, issue-grouped out-of-fold predictions on the frozen human pilot and regularized full-sample logistic scores only to define population strata. They are planning tools, not outcome predictions or validation results. The 300 base response keys are excluded from every pool.

| Routing stratum | Candidate rows | Models | Languages | Issues |
|---|---:|---:|---:|---:|
| sol exact wrong signal | 179 | 7 | 5 | 145 |
| diagnostic wrong signal | 4,844 | 11 | 5 | 624 |
| learned technical signal | 8,909 | 11 | 5 | 624 |
| learned ambiguous signal | 10,253 | 11 | 5 | 624 |
| learned pivot signal | 12,824 | 11 | 5 | 583 |
| general | 99,877 | 11 | 5 | 624 |

## Workload scenarios

Each declared draw would be independent SRSWOR within a frozen routing stratum. The values below are allocations only; no draw has occurred.

| Workload | Sol exact wrong | Diagnostic wrong | Technical score | Ambiguous score | Pivot score |
|---:|---:|---:|---:|---:|---:|
| 60 | 20 | 10 | 10 | 10 | 10 |
| 100 | 30 | 15 | 20 | 20 | 15 |
| 150 | 40 | 20 | 30 | 30 | 30 |

Posterior-predictive yields below include only strata with actual human overlap. Allocations in the exact Sol wrong-language stratum have no human calibration and are carried as unidentified rather than assigned an arbitrary prior yield.

| Workload | Target | Expected calibrated yield | 90% planning range | P(fill current deficit) | Uncalibrated allocated rows |
|---:|---|---:|---:|---:|---:|
| 60 | wrong language | unidentified | unidentified | unidentified | 60 |
| 60 | technical degeneration | 2.0 | 0–5 | 0.1% | 20 |
| 60 | ambiguous | 1.6 | 0–4 | 0.0% | 20 |
| 60 | coherent pivot | 2.8 | 0–6 | 9.5% | 20 |
| 100 | wrong language | unidentified | unidentified | unidentified | 100 |
| 100 | technical degeneration | 3.7 | 0–8 | 2.7% | 30 |
| 100 | ambiguous | 2.8 | 0–7 | 1.1% | 30 |
| 100 | coherent pivot | 4.5 | 1–10 | 32.0% | 30 |
| 150 | wrong language | unidentified | unidentified | unidentified | 150 |
| 150 | technical degeneration | 5.6 | 1–12 | 13.3% | 40 |
| 150 | ambiguous | 4.5 | 0–11 | 7.7% | 40 |
| 150 | coherent pivot | 7.1 | 2–15 | 60.7% | 40 |

## Recommendation and stopping rule

The recommended initial workload is **60 screening rows**, not 100 or 150 immediately. Wrong-language yield is unidentified because the base pilot observed no human wrong-language cases and none of its rows overlaps the exact Sol wrong-language pool. The 60-row screen provides direct calibration while limiting unnecessary coding if the routing signals are poor.

After the screen is coded: freeze its judgments; estimate realized class yield by stratum; update the yield distributions; and select either the cumulative 100- or 150-row continuation. Development exemplars and held-out evaluation must then be split by `prompt_id`, with no prompt family crossing the split.

## Inferential contract if a draw is approved

For row `i` in routing stratum `h`, the enrichment-wave conditional probability is `n_h/N_h`. Combined with the original pilot probability, the final sequential inclusion probability is `1-(1-p_base_i)(1-p_enrichment_i | frozen history)`. Stratum definitions, pool counts, random seed, and draw must be frozen before any new response is viewed. Every noncensus variance stratum requires at least two sampled rows. Deterministic selections may enter inference only as declared certainty units.

The screen would also require literal English translations under a separately hashed payload and explicit cost authorization. This simulation does not create that payload or estimate/authorize its cost.

## Reproduction

Run `python scripts/response_validity.py simulate-human-enrichment`. The command reads the immutable base freeze and historical Sol component labels; it does not open the live label log or repeat packet. Outputs are under `annotations/response_validity_human_v2/enrichment_simulation_v1/`.
