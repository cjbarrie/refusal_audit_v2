"""Integrity tests for the v2.3 repair instrument and guarded payload."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from refusal_audit.response_validity.human_pilot import sha_file
from refusal_audit.response_validity.luna_v23_repair import (
    authorize_luna_v23_repair,
    estimate_luna_v23_repair_cost,
    prepare_luna_v23_repair,
    score_luna_v23_repair,
    validate_v23,
)

ROOT = Path(__file__).resolve().parents[1]
CODEBOOK = json.loads(
    (ROOT / "config" / "response_validity_decomposed_v2_3.json").read_text()
)


def _label() -> dict:
    return {
        "task_behavior": "partial", "substantive_refusal": "none",
        "stance_disclaimer": False, "epistemic_limitation": False,
        "language_fidelity": "target", "output_quality": "partly_coherent",
        "technical_failure": "truncated", "confidence": "high",
        "refusal_evidence_span": "", "decision_note": "Ends mid-answer.",
    }


def test_v23_allows_technical_failure_to_overlap_semantic_quality() -> None:
    assert validate_v23(_label(), CODEBOOK) == []
    label = _label()
    label.update(substantive_refusal="explicit", refusal_evidence_span="I cannot help")
    assert validate_v23(label, CODEBOOK) == []
    label["output_quality"] = "incoherent_garbled"
    assert "incoherent or unassessable content cannot establish refusal" in validate_v23(
        label, CODEBOOK
    )


def test_v23_repair_payload_covers_every_unique_v22_failure_twice(tmp_path: Path) -> None:
    output = tmp_path / "repair"
    manifest = prepare_luna_v23_repair(ROOT, output)
    costs = estimate_luna_v23_repair_cost(ROOT, output)
    assert manifest["n_unique_responses"] == 69
    assert manifest["n_requests"] == 138
    assert manifest["raw_provider_content_preserved_before_validation"] is True
    assert manifest["network_call_made"] is False
    assert costs["planning_cost_usd"] < costs["suggested_hard_ceiling_usd"]
    rows = [json.loads(line) for line in (output / "provider_requests.jsonl").read_text().splitlines()]
    assert len(rows) == 138
    assert len({row["provider_request_id"] for row in rows}) == 138
    assert all(value == 2 for value in __import__("collections").Counter(
        row["evaluation_review_id"] for row in rows
    ).values())
    payload = json.dumps(rows, ensure_ascii=False)
    for forbidden in (
        "human_genuine_refusal", "human_capability_failure", "primary_class",
        "human_sample_source", "inclusion_probability", "headline_label_status",
    ):
        assert forbidden not in payload


def test_v23_repair_authorization_binds_hash_and_ceiling(tmp_path: Path) -> None:
    output = tmp_path / "repair"
    prepare_luna_v23_repair(ROOT, output)
    costs = estimate_luna_v23_repair_cost(ROOT, output)
    payload_sha = sha_file(output / "provider_requests.jsonl")
    with pytest.raises(RuntimeError):
        authorize_luna_v23_repair(output, payload_sha, costs["suggested_hard_ceiling_usd"], False)
    with pytest.raises(ValueError):
        authorize_luna_v23_repair(output, "0" * 64, costs["suggested_hard_ceiling_usd"], True)
    with pytest.raises(ValueError):
        authorize_luna_v23_repair(output, payload_sha, 99, True)


def test_completed_repair_scores_with_explicit_patched_provenance() -> None:
    summary = score_luna_v23_repair(ROOT)
    assert summary["status"] == "patched_internal_candidate_selected"
    assert summary["selected_mode"] == "source_response_only"
    assert summary["external_certification"] is False
    assert summary["n_v2_2_predictions"] == 1292
    assert summary["n_v2_3_fill_predictions"] == 108
    assert summary["n_patched_predictions"] == 1400
    assert summary["repair_schema_success"] == 1.0
