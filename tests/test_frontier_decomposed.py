"""Fail-closed tests for the frontier v2.2 annotation payload."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from refusal_audit.response_validity.frontier_decomposed import (
    authorize_frontier_decomposed,
    estimate_frontier_decomposed,
    prepare_frontier_decomposed,
    record_frontier_bulk_agreement,
)
from refusal_audit.response_validity.human_pilot import sha_file

ROOT = Path(__file__).resolve().parents[1]


def test_frontier_payload_is_blinded_frozen_and_locally_priced(tmp_path: Path) -> None:
    output = tmp_path / "frontier"
    manifest = prepare_frontier_decomposed(ROOT, output)
    costs = estimate_frontier_decomposed(ROOT, output)
    assert manifest["n_requests"] == 158
    assert manifest["model_id"] == "openai/gpt-5.6-sol"
    assert manifest["provider_tag"] == "openai"
    assert manifest["allow_fallbacks"] is False
    assert manifest["network_call_made"] is False
    assert costs["planning_cost_usd"] < costs["suggested_hard_ceiling_usd"]
    rows = [json.loads(line) for line in (output / "provider_requests.jsonl").read_text().splitlines()]
    assert len(rows) == 158
    assert len({row["provider_request_id"] for row in rows}) == 158
    text = json.dumps(rows, ensure_ascii=False)
    for forbidden in [
        "reason_human_refusal", "luna_primary_class", "human_sample_source",
        "prior human label", '"model":', "selection_reason",
    ]:
        assert forbidden not in text


def test_frontier_authorization_requires_exact_hash_and_ceiling(tmp_path: Path) -> None:
    output = tmp_path / "frontier"
    prepare_frontier_decomposed(ROOT, output)
    costs = estimate_frontier_decomposed(ROOT, output)
    payload_sha = sha_file(output / "provider_requests.jsonl")
    with pytest.raises(RuntimeError):
        authorize_frontier_decomposed(
            output, payload_sha, costs["suggested_hard_ceiling_usd"], False
        )
    with pytest.raises(ValueError):
        authorize_frontier_decomposed(
            output, "0" * 64, costs["suggested_hard_ceiling_usd"], True
        )
    with pytest.raises(ValueError):
        authorize_frontier_decomposed(output, payload_sha, 999, True)


def test_bulk_agreement_is_explicit_append_only_and_idempotent(tmp_path: Path) -> None:
    output = tmp_path / "review"
    output.mkdir()
    run_dir = (
        ROOT / "annotations" / "response_validity_human_v2"
        / "decomposed_review_v2_2" / "frontier_sol_v2_2"
    )
    with pytest.raises(RuntimeError):
        record_frontier_bulk_agreement(ROOT, "Sol", False, output, run_dir)
    first = record_frontier_bulk_agreement(ROOT, "Sol", True, output, run_dir)
    assert first["existing_interactive_submissions"] == 0
    assert first["bulk_affirmed_submissions_appended"] == 158
    second = record_frontier_bulk_agreement(ROOT, "Sol", True, output, run_dir)
    assert second["existing_interactive_submissions"] == 158
    assert second["bulk_affirmed_submissions_appended"] == 0
    records = [
        json.loads(line)
        for line in (output / "frontier_human_reviews.jsonl").read_text().splitlines()
    ]
    assert len(records) == 158
    assert all(record["bulk_confirmation"] for record in records)
