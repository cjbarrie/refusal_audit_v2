from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.external_audit_freeze import (  # noqa: E402
    freeze_external_audit,
)


@pytest.fixture(scope="module")
def frozen(tmp_path_factory):
    output = tmp_path_factory.mktemp("external-audit-freeze")
    manifest = freeze_external_audit(ROOT, output)
    return output, manifest


def test_external_freeze_matches_approved_components(frozen):
    output, manifest = frozen
    design = pd.read_parquet(output / "sample_design.parquet")
    assert manifest["cell_component_draw_n"] == 550
    assert manifest["risk_component_draw_n"] == 650
    assert manifest["component_overlap_n"] == 1200 - len(design)
    assert len(design) == manifest["realized_unique_sample_n"]
    assert design.phase1_inclusion_probability.between(0, 1).all()
    assert design.audit_response_id.is_unique
    assert design.groupby(["model", "prompt_language"])[
        "selected_by_cell_component"
    ].sum().eq(10).all()
    gold = pd.read_parquet(
        ROOT / "annotations/response_validity_human_v2/decomposed_review_v2_2/"
        "harmonized_evaluation_gold_v2_2.parquet"
    )
    keys = ["prompt_id", "prompt_language", "model"]
    assert design.merge(gold[keys], on=keys, how="inner").empty


def test_external_payloads_are_blinded_and_paired(frozen):
    output, manifest = frozen
    luna = [json.loads(line) for line in (
        output / "luna_provider_requests.jsonl"
    ).read_text(encoding="utf-8").splitlines()]
    sol = [json.loads(line) for line in (
        output / "sol_provider_requests.jsonl"
    ).read_text(encoding="utf-8").splitlines()]
    assert len(luna) == len(sol) == manifest["realized_unique_sample_n"]
    assert {row["logical_request_id"] for row in luna} == {
        row["logical_request_id"] for row in sol
    }
    for left, right in zip(luna, sol):
        assert left["messages"] == right["messages"]
        assert left["response_schema"] == right["response_schema"]
        assert left["audit_response_id"] == right["audit_response_id"]
        assert left["model_id"] != right["model_id"]
    payload = (output / "model_neutral_requests.jsonl").read_text(encoding="utf-8")
    for forbidden in (
        "engagement_code", "refusal_justification", "routing_stratum",
        "inclusion_probability", "dsl_prediction",
    ):
        assert forbidden not in payload


def test_external_freeze_is_unpaid_and_immutable(frozen):
    output, manifest = frozen
    before = (output / "manifest.json").read_bytes()
    repeated = freeze_external_audit(ROOT, output)
    assert repeated == manifest
    assert (output / "manifest.json").read_bytes() == before
    assert manifest["paid_run_authorized"] is False
    assert manifest["network_call_made"] is False
    assert manifest["status"] == "sample_and_payloads_frozen_unpaid"


def test_external_costs_are_bound_to_both_payload_hashes(frozen):
    output, manifest = frozen
    cost = json.loads((output / "cost_estimate.json").read_text())
    assert cost["paid_run_authorized"] is False
    assert cost["network_call_made"] is False
    assert set(cost["by_model"]) == {"luna", "sol"}
    for key in ("luna", "sol"):
        assert cost["by_model"][key]["provider_payload_sha256"] == (
            manifest["provider_payload_sha256"][key]
        )
