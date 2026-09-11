from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.external_audit_design import (  # noqa: E402
    simulate_external_audit_design,
    union_probability,
)


def test_union_probability_matches_independent_component_formula():
    cell = np.array([0.1, 0.25, 0.0])
    risk = np.array([0.2, 0.0, 1.0])
    assert np.allclose(union_probability(cell, risk), [0.28, 0.25, 1.0])


@pytest.fixture(scope="module")
def planned(tmp_path_factory):
    output = tmp_path_factory.mktemp("external-audit")
    manifest = simulate_external_audit_design(
        ROOT, output, seed=20260827, simulations=1_000
    )
    return output, manifest


def test_external_plan_is_aggregate_and_fail_closed(planned):
    output, manifest = planned
    assert manifest["external_population_n"] == 136_486
    assert manifest["previous_human_rows_excluded"] == 700
    assert manifest["recommended_plan"] == "audit_1200"
    assert manifest["sample_drawn"] is False
    assert manifest["response_ids_emitted"] is False
    assert manifest["provider_payload_created"] is False
    assert manifest["paid_run_authorized"] is False
    assert manifest["network_call_made"] is False
    assert not (output / "provider_requests.jsonl").exists()
    assert not (output / "sample.parquet").exists()


def test_external_plan_has_known_probabilities_and_coverage(planned):
    output, _ = planned
    candidates = pd.read_csv(output / "candidate_designs.csv")
    allocations = pd.read_csv(output / "candidate_allocations.csv")
    chosen = candidates.loc[candidates.plan.eq("audit_1200")].iloc[0]
    assert chosen.per_model_language_coverage_draw == 10
    assert chosen.expected_min_model_language_n >= 10
    assert chosen.expected_unique_phase1_n < chosen.nominal_component_total
    assert chosen.genuine_refusal_q05 >= 50
    assert len(allocations.loc[allocations.plan.eq("audit_1200")]) == 7
    assert allocations.risk_component_probability.between(0, 1).all()


def test_external_manifest_hashes_declared_outputs(planned):
    output, manifest = planned
    assert set(manifest["artifact_sha256"]) == {
        "routing_calibration.csv", "candidate_designs.csv",
        "candidate_allocations.csv", "human_workload_scenarios.csv",
        "recommendation.json",
    }
    recommendation = json.loads((output / "recommendation.json").read_text())
    assert recommendation["sol_role"].endswith("never automatic ground truth")


def test_external_plan_is_immutable_on_identical_rerun(planned):
    output, manifest = planned
    before = (output / "design_manifest.json").read_bytes()
    repeated = simulate_external_audit_design(
        ROOT, output, seed=20260827, simulations=1_000
    )
    assert repeated == manifest
    assert (output / "design_manifest.json").read_bytes() == before


def test_aggregate_outputs_do_not_disclose_response_keys(planned):
    output, _ = planned
    forbidden = {"prompt_id", "prompt_language", "model", "review_id"}
    for path in output.glob("*.csv"):
        assert forbidden.isdisjoint(pd.read_csv(path, nrows=0).columns)
