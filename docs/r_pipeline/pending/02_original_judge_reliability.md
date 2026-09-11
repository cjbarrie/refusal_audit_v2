# Pending: `02_original_judge_reliability.R`

This is not a current release stage. It evaluates the original Gemini
engagement/justification/content instruments, not Luna v2.4.

**Purpose.** Quantify measurement agreement for pass-1, justifications, slant, and moral-foundation labels using the shared panel loader also used by stage 14.

**Inputs/unit.** Per-judge panel JSONL under `REFUSAL_RUN_DIR`, restricted to canonical English response keys from `data_clean`. Required: response key, `judge_model`, codebook version, engagement/justification and available content fields. Unit is response × judge. Last valid record wins per response × judge; invalid parses remain diagnostics. Comparisons use pairwise or all-judge common support rather than filling missing ratings.

**Statistics.** Binary constructs report raw agreement, Krippendorff's alpha, Gwet AC1, and positive-specific agreement; categorical justification reports corresponding nominal agreement. Uncertainty resamples `issue_id` clusters with the canonical seed; rare-positive marginals are reported alongside chance-corrected metrics. These measure consistency, not truth.

**Outputs.** `e22b_panel_version_composition.csv`; `e23_reliability_pass1.csv`; `e23b_pairwise_agreement.csv`; `e24_reliability_justification.csv`; `e25_reliability_slant.csv`; `e26_judge_marginals.csv`; `e26b_pairwise_vs_anchor.csv`; `e26c_leave_one_judge_out.csv`; `e28_consensus_labels.csv`; run-scoped diagnostics. Stage 13 consumes e25; stage 14 consumes the panel and reliability tables; figures consume e23–e25.

**Failure policy.** Mixed stamped codebooks on the analysis support stop execution. Fewer judges or missing optional comparisons produce explicit skips/empty tables. Bootstrap failures are counted, not redrawn.

**Worked trace.** For one English response rated `5,5,4`, pairwise exact agreement is recorded, the nominal disagreement contributes to alpha/AC1, and the response remains on all-judge support; no majority vote silently replaces its three ratings.

**May infer:** reproducibility and sensitivity across these instruments. **May not infer:** correctness or human validity.
