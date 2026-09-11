import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.enrichment_design_v2 import (  # noqa: E402
    READINESS_TARGETS,
    ROUTING_STRATA,
    simulate_enrichment_design_v2,
)


OUTPUT = (
    ROOT / "annotations" / "response_validity_human_v2"
    / "enrichment_simulation_v2"
)


def test_enrichment_v2_is_simulation_only_and_uses_current_inputs():
    manifest = json.loads((OUTPUT / "simulation_manifest.json").read_text())
    assert manifest["simulation_version"] == "human-enrichment-simulation-v2.0"
    assert manifest["sample_drawn"] is False
    assert manifest["row_level_candidate_ids_written"] is False
    assert manifest["translation_payload_created"] is False
    assert manifest["repeat_rows_read_or_analyzed"] is False
    assert manifest["network_call_made"] is False
    assert manifest["paid_call_authorized"] is False
    assert "complete_language_v3_labels" in manifest["input_sha256"]
    assert "stage_b_disagreements" in manifest["input_sha256"]
    assert set(manifest["routing_strata"]) == set(ROUTING_STRATA)
    assert set(manifest["artifact_sha256"]) == {
        "candidate_pool_summary.csv",
        "human_yield_calibration.csv",
        "workload_allocations.csv",
        "workload_yield_simulation.csv",
        "estimand_precision_proxy.csv",
        "coverage_expectations.csv",
        "recommendation.json",
    }


def test_enrichment_v2_allocations_are_valid_stratified_srs_plans():
    pools = pd.read_csv(OUTPUT / "candidate_pool_summary.csv")
    allocation = pd.read_csv(OUTPUT / "workload_allocations.csv")
    assert pools.candidate_population_n.sum() == 137_186 - 300
    assert allocation.groupby("workload").planned_draw_n.sum().to_dict() == {
        150: 150, 250: 250, 400: 400, 600: 600,
    }
    assert np.allclose(
        allocation.conditional_wave_probability,
        allocation.planned_draw_n / allocation.candidate_population_n,
    )
    assert allocation.planned_draw_n.le(allocation.candidate_population_n).all()
    assert allocation.draw_status.eq("not_drawn_simulation_only").all()
    for stratum in ROUTING_STRATA:
        cumulative = allocation.loc[allocation.routing_stratum.eq(stratum)].sort_values("workload")
        assert cumulative.planned_draw_n.is_monotonic_increasing


def test_enrichment_v2_yields_have_observed_calibration_not_hidden_priors():
    calibration = pd.read_csv(OUTPUT / "human_yield_calibration.csv")
    yields = pd.read_csv(OUTPUT / "workload_yield_simulation.csv")
    assert calibration.groupby("routing_stratum").human_sample_n.first().gt(0).all()
    assert yields.global_fallback_allocated_n.eq(0).all()
    assert np.isfinite(yields.expected_new_labels).all()
    for target, threshold in READINESS_TARGETS.items():
        row = yields.loc[(yields.workload.eq(400)) & yields.target_class.eq(target)].iloc[0]
        assert row.expected_new_labels >= threshold


def test_enrichment_v2_precision_is_explicitly_a_nonaccepted_proxy():
    precision = pd.read_csv(OUTPUT / "estimand_precision_proxy.csv")
    assert precision.accepted_interval.eq(False).all()
    assert precision.method.str.contains("proxy").all()
    for _, values in precision.groupby(["estimand_family", "estimand_cell"]):
        ordered = values.sort_values("workload").worst_case_95_half_width
        assert ordered.is_monotonic_decreasing


def test_enrichment_v2_is_idempotent_and_recommends_sequential_400_to_600():
    pilot = ROOT / "annotations" / "response_validity_human_v2"
    manifest = simulate_enrichment_design_v2(ROOT, pilot)
    recommendation = json.loads((OUTPUT / "recommendation.json").read_text())
    assert manifest["sample_drawn"] is False
    assert recommendation["recommended_workload"] == 400
    assert recommendation["conditional_continuation_workload"] == 600
    assert recommendation["sample_drawn"] is False
    assert recommendation["additional_human_work_authorized"] is False
