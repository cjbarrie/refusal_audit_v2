#!/usr/bin/env python3
"""Compare planned Sol control-sample budgets using expected design precision.

No API call is made.  The calculation uses the probability-weighted v1.1 Sol
pilot only to approximate residual variance for allocation and planning.  It is
not an analysis result and never enters a publication estimate.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from response_validity_dsl import (
    OUT, STRATA, add_allocation_leverage, analysis_coefficients, full_frame,
    integer_neyman_allocation, provisional_risk,
)

ROOT = Path(__file__).resolve().parents[1]
BUDGETS = [1250, 2500, 5000, 10000, 20000]


def expected_phase_two_se(controls: pd.DataFrame, allocation: pd.DataFrame,
                          coefficient: np.ndarray) -> float:
    """Expected SRSWOR variance of the DSL residual-correction total."""
    x = controls.copy()
    x["a"] = coefficient[x.index]
    x["expected_z2"] = x.a.pow(2) * x.provisional_risk * (1 - x.provisional_risk)
    cells = x.groupby(STRATA, dropna=False).agg(
        sum_z2=("expected_z2", "sum"), N=("a", "size")
    ).reset_index().merge(allocation[STRATA + ["n"]], on=STRATA,
                          validate="one_to_one")
    # With residual mean approximately zero, S_z^2 is sum(z_i^2)/(N_h-1).
    denom = np.maximum(cells.N - 1, 1)
    s2 = cells.sum_z2 / denom
    var = np.sum(cells.N ** 2 * (1 - cells.n / cells.N) * s2 / cells.n)
    return float(np.sqrt(max(var, 0)))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frame = full_frame().reset_index(drop=True)
    frame["provisional_risk"], fit_diag = provisional_risk(frame)
    frame = add_allocation_leverage(frame)
    controls = frame.loc[frame.engagement_code.lt(4)].copy()
    registry = analysis_coefficients(frame)
    rows = []
    allocations = []
    for budget in BUDGETS:
        allocation = integer_neyman_allocation(controls, budget)
        allocation["control_budget"] = budget
        allocations.append(allocation)
        for name, (family, a) in registry.items():
            rows.append({
                "control_budget": budget, "family": family, "estimand": name,
                "expected_phase_two_se": expected_phase_two_se(controls, allocation, a),
            })
    result = pd.DataFrame(rows)
    result["expected_phase_two_se_pp"] = 100 * result.expected_phase_two_se
    result.to_csv(OUT / "design_precision_by_estimand.csv", index=False)
    pd.concat(allocations).to_csv(OUT / "candidate_allocations.csv", index=False)
    summary = result.groupby(["control_budget", "family"]).expected_phase_two_se_pp.agg(
        median="median", p90=lambda x: x.quantile(.9), maximum="max"
    ).reset_index()
    summary.to_csv(OUT / "design_precision_summary.csv", index=False)
    recommended = 2500
    report = f"""# DSL reference-sample precision planning

This is a **cost-free design calculation, not a scientific result**. It uses the
probability-weighted 1,306-row GPT-5.6 Sol pilot to approximate the conditional
variance of clean-refusal residuals. It compares phase-two reference-label
sampling error while holding the 624-issue response corpus fixed. It does not
include issue-sampling uncertainty, cross-fit variation, or residual Sol error.

## Candidate designs

Every design labels all 11,475 original code-4/5 responses and draws controls by
stratified SRS without replacement from the code-1/2/3 population. Strata are
`model × prompt language × home status × original engagement code`. Every
populated stratum receives at least one control, after which bounded Neyman
allocation uses the pilot risk with a variance floor.

{summary.to_markdown(index=False, floatfmt='.3f')}

The current planning recommendation is **{recommended:,} controls**, subject to
the predeclared rule that the maximum expected phase-two SE for each headline
home/language family should be below 1 percentage point and the 90th percentile
of model × language cell-rate SEs below 2 percentage points. If this gate fails
in the table above, use 5,000 rather than selectively altering strata.

## Allocation-model diagnostics

- Apparent probability-weighted pilot Brier score:
  {fit_diag['weighted_brier_apparent']:.4f}.
- Apparent probability-weighted pilot log loss:
  {fit_diag['weighted_log_loss_apparent']:.4f}.
- These are deliberately labelled apparent and never support an accuracy claim.

Exact per-estimand calculations are in
`annotations/response_validity_dsl_v1/design_precision_by_estimand.csv`; every
candidate stratum allocation is in `candidate_allocations.csv`.
"""
    (ROOT / "docs" / "RESPONSE_VALIDITY_DSL_DESIGN.md").write_text(report, encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
