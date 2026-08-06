# =============================================================================
# Script 16: Inter-rater reliability  -- RETIRED, superseded by 24_measurement.R
# =============================================================================
# This script computed Cohen's kappa (irr::kappa2) between the primary judge and
# a single second judge. That is structurally limited to TWO raters, and it
# covered Pass 1 and Pass 2 only -- moral foundations had no reliability estimate
# at all. It also expected annotations_second_judge.jsonl, produced by
# scripts/sample_for_second_judge.py, which was v1-era (hardcoded refusal_audit/
# paths, languages ja/id that were dropped) and has been deleted.
#
# The replacement is pipeline/24_measurement.R, which:
#   * takes ANY number of judges (Krippendorff's alpha, not Cohen's kappa)
#   * covers Pass 1, justifications, ideology AND moral foundations
#   * reports Gwet's AC1 and positive specific agreement alongside alpha,
#     because refusal (~5.6%) and sanctity (~3%) are rare enough that alpha
#     alone hits the kappa paradox and understates a reliable instrument
#   * tests whether measurement error is DIFFERENTIAL -- i.e. concentrated where
#     the headline finding lives -- which is the check that decides whether the
#     China result is partly an artefact
#
# See docs/MULTI_JUDGE_PLAN.md.

cat("16_irr_analysis.R is RETIRED -- superseded by pipeline/24_measurement.R\n")
cat("  (two-rater Cohen's kappa; the panel design needs k raters)\n")
quit(save = "no", status = 0)
