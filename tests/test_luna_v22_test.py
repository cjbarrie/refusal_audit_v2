"""Fail-closed tests for the exact-prompt Luna v2.2 readiness test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from refusal_audit.response_validity.human_pilot import sha_file
from refusal_audit.response_validity.luna_v22_test import (
    authorize_luna_v22_test,
    estimate_luna_v22_cost,
    prepare_luna_v22_test,
)

ROOT = Path(__file__).resolve().parents[1]


def test_luna_v22_payload_is_blinded_exact_and_locally_priced(tmp_path: Path) -> None:
    output = tmp_path / "luna_v22"
    manifest = prepare_luna_v22_test(ROOT, output)
    costs = estimate_luna_v22_cost(ROOT, output)
    assert manifest["n_gold_rows"] == 700
    assert manifest["n_requests"] == 1400
    assert manifest["input_modes"] == ["original_only", "original_plus_translation"]
    assert manifest["model_id"] == "openai/gpt-5.6-luna"
    assert manifest["allow_fallbacks"] is False
    assert manifest["network_call_made"] is False
    assert costs["planning_cost_usd"] < costs["suggested_hard_ceiling_usd"]

    rows = [
        json.loads(line)
        for line in (output / "provider_requests.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1400
    assert len({row["provider_request_id"] for row in rows}) == 1400
    assert {row["input_mode"] for row in rows} == {
        "original_only", "original_plus_translation",
    }
    payload = json.dumps(rows, ensure_ascii=False)
    for forbidden in (
        "human_genuine_refusal", "human_capability_failure", "primary_class",
        "inclusion_probability", "human_sample_source", "headline_label_status",
    ):
        assert forbidden not in payload


def test_luna_v22_authorization_binds_exact_hash_and_ceiling(tmp_path: Path) -> None:
    output = tmp_path / "luna_v22"
    prepare_luna_v22_test(ROOT, output)
    costs = estimate_luna_v22_cost(ROOT, output)
    payload_sha = sha_file(output / "provider_requests.jsonl")
    with pytest.raises(RuntimeError):
        authorize_luna_v22_test(output, payload_sha, costs["suggested_hard_ceiling_usd"], False)
    with pytest.raises(ValueError):
        authorize_luna_v22_test(output, "0" * 64, costs["suggested_hard_ceiling_usd"], True)
    with pytest.raises(ValueError):
        authorize_luna_v22_test(output, payload_sha, 999, True)
