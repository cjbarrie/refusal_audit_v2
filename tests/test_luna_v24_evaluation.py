from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.luna_v24_evaluation import (  # noqa: E402
    DEFAULT_DIR,
    _read_jsonl,
    estimate_luna_v24_cost,
    prepare_luna_v24_evaluation,
    score_luna_v24,
)


def test_jsonl_reader_preserves_unicode_line_separators(tmp_path: Path) -> None:
    path = tmp_path / "unicode.jsonl"
    rows = [{"text": "before\u2028after"}, {"text": "before\u2029after"}]
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    assert _read_jsonl(path) == rows


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_v24_payload_is_frozen_blinded_and_partitioned() -> None:
    manifest = prepare_luna_v24_evaluation(ROOT)
    repeated = prepare_luna_v24_evaluation(ROOT)
    assert repeated["provider_payload_sha256"] == manifest["provider_payload_sha256"]
    assert manifest["n_requests"] == 1197
    assert manifest["n_boundary_development"] == 24
    assert manifest["n_protected_nonregression"] == 1173
    assert manifest["paid_run_authorized"] is True
    assert manifest["network_call_made"] is True
    assert manifest["authorization"]["provider_payload_sha256"] == (
        manifest["provider_payload_sha256"]
    )
    assert manifest["run_summary"]["n_completed"] == 1197

    folder = ROOT / DEFAULT_DIR
    payload = _jsonl(folder / "provider_requests.jsonl")
    assert len(payload) == 1197
    assert len({row["provider_request_id"] for row in payload}) == 1197
    assert all(row["provider"] == {"only": ["openai"], "allow_fallbacks": False} for row in payload)
    assert all(row["reasoning"] == {"enabled": False, "exclude": True} for row in payload)
    serialized = json.dumps(payload)
    for forbidden in (
        "pred_genuine_refusal_sol", "final_genuine_refusal", "evaluation_role",
        "routing_stratum", "phase1_inclusion_probability",
    ):
        assert forbidden not in serialized

    partition = pd.read_csv(folder / "evaluation_partition.csv")
    assert partition.audit_response_id.nunique() == 1197
    assert partition.evaluation_role.value_counts().to_dict() == {
        "protected_sol_reference_nonregression": 1173,
        "boundary_development": 24,
    }


def test_v24_cost_estimate_is_local_and_bound_to_payload() -> None:
    cost = estimate_luna_v24_cost(ROOT)
    manifest = prepare_luna_v24_evaluation(ROOT)
    assert cost["requests"] == 1197
    assert cost["provider_payload_sha256"] == manifest["provider_payload_sha256"]
    assert cost["planning_cost_usd"] < cost["single_attempt_reserved_cost_usd"]
    assert cost["suggested_hard_ceiling_usd"] == 2.0
    assert cost["paid_run_authorized"] is False
    assert cost["network_call_made"] is False


def test_completed_v24_run_scores_development_and_protected_sets_separately() -> None:
    score = score_luna_v24(ROOT)
    headline = score["headline"]
    assert headline["protected_n"] == 1173
    assert headline["development_n"] == 24
    assert headline["development_decided_n"] == 22
    assert headline["protected_refusal_decisions_changed_from_v2_3_n"] == 21
    assert headline["protected_v2_4_sol_refusal_disagreements_n"] == 18
    assert headline["protected_f1_noninferiority_pass"] is False
    assert score["human_validation_complete"] is False

    folder = ROOT / DEFAULT_DIR
    changes = pd.read_csv(folder / "protected_refusal_change_inventory.csv")
    disagreements = pd.read_csv(folder / "protected_v24_sol_refusal_disagreements.csv")
    development = pd.read_csv(folder / "boundary_development_case_results.csv")
    assert changes.audit_response_id.nunique() == 21
    assert disagreements.audit_response_id.nunique() == 18
    assert development.audit_response_id.nunique() == 24
