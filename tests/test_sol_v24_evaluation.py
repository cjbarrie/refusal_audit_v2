from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.sol_v24_evaluation import (  # noqa: E402
    DEFAULT_DIR,
    estimate_sol_v24_cost,
    prepare_sol_v24_evaluation,
    score_sol_v24,
)


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_sol_v24_payload_matches_luna_content_without_label_leakage() -> None:
    manifest = prepare_sol_v24_evaluation(ROOT)
    repeated = prepare_sol_v24_evaluation(ROOT)
    assert repeated["provider_payload_sha256"] == manifest["provider_payload_sha256"]
    assert manifest["n_requests"] == 1197
    assert manifest["paid_run_authorized"] is True
    assert manifest["network_call_made"] is True
    assert manifest["authorization"]["provider_payload_sha256"] == manifest["provider_payload_sha256"]
    assert manifest["run_summary"]["n_completed"] == 1197
    folder = ROOT / DEFAULT_DIR
    sol = _jsonl(folder / "provider_requests.jsonl")
    luna = _jsonl(
        ROOT / "annotations/response_validity_human_v2/external_audit_v1/"
        "luna_v2_4_evaluation_v1/provider_requests.jsonl"
    )
    assert len(sol) == len(luna) == 1197
    for left, right in zip(sol, luna):
        assert left["audit_response_id"] == right["audit_response_id"]
        assert left["messages"] == right["messages"]
        assert left["response_schema"] == right["response_schema"]
        assert left["model_id"] == "openai/gpt-5.6-sol"
        assert left["provider"] == {"only": ["openai"], "allow_fallbacks": False}
        assert left["reasoning"] == {"enabled": False, "exclude": True}
    serialized = json.dumps(sol)
    for forbidden in (
        "pred_genuine_refusal", "final_genuine_refusal", "evaluation_role",
        "routing_stratum", "phase1_inclusion_probability",
    ):
        assert forbidden not in serialized


def test_sol_v24_cost_is_bound_to_completed_authorized_payload() -> None:
    cost = estimate_sol_v24_cost(ROOT)
    manifest = prepare_sol_v24_evaluation(ROOT)
    assert cost["requests"] == 1197
    assert cost["provider_payload_sha256"] == manifest["provider_payload_sha256"]
    assert cost["planning_cost_usd"] == 8.487646
    assert cost["single_attempt_reserved_cost_usd"] == 12.078646
    assert cost["suggested_hard_ceiling_usd"] == 15.5
    assert cost["paid_run_authorized"] is False
    assert cost["network_call_made"] is False


def test_completed_same_codebook_score_preserves_machine_and_human_roles() -> None:
    score = score_sol_v24(ROOT)
    headline = score["headline"]
    assert headline["protected_n"] == 1173
    assert headline["same_codebook_refusal_disagreements_n"] == 15
    assert headline["protected_refusal_f1"] == 0.9333333333333333
    assert headline["boundary_human_reference_decided_n"] == 22
    assert headline["boundary_human_reference_accuracy"] == {
        "luna_v2.4": 0.9090909090909091,
        "sol_v2.4": 0.8636363636363636,
    }
    assert headline["human_validation_complete"] is False
