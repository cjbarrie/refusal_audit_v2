"""Integrity tests for the exhausted-case Luna v2.4 schema repair."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from refusal_audit.response_validity.wall_to_wall_repair_v24 import (
    DEFAULT_DIR,
    EXPECTED_N,
    assemble_final_wall_to_wall_v24,
    authorize_wall_to_wall_repair_v24,
    estimate_wall_to_wall_repair_v24_cost,
    prepare_wall_to_wall_repair_v24,
    run_wall_to_wall_repair_v24,
)


ROOT = Path(__file__).resolve().parents[1]


def test_completed_repair_is_exact_and_hash_bound() -> None:
    output = ROOT / DEFAULT_DIR
    manifest = prepare_wall_to_wall_repair_v24(ROOT, output)
    cost = estimate_wall_to_wall_repair_v24_cost(ROOT, output)
    index = pd.read_parquet(output / "repair_index.parquet")

    assert manifest["n_requests"] == EXPECTED_N == len(index)
    assert not index.duplicated(["prompt_id", "prompt_language", "model"]).any()
    assert manifest["paid_run_authorized"] is True
    assert manifest["network_call_made"] is True
    assert manifest["status"] == "completed"
    assert manifest["run_summary"]["n_completed"] == EXPECTED_N
    assert manifest["run_summary"]["n_incomplete"] == 0
    assert manifest["run_summary"]["provider_cost_usd"] == pytest.approx(0.0741098)
    assert manifest["protocol"]["max_repair_attempts"] == 2
    assert cost["requests"] == EXPECTED_N
    assert cost["max_provider_calls"] == 2 * EXPECTED_N
    assert cost["suggested_hard_ceiling_usd"] == 0.5


def test_final_assembly_covers_every_corpus_response_once() -> None:
    summary = assemble_final_wall_to_wall_v24(ROOT, ROOT / DEFAULT_DIR)
    final = pd.read_parquet(
        ROOT / "annotations/response_validity_v2_4/wall_to_wall_luna_v1/"
        "final_annotations.parquet"
    )
    assert summary["n_responses"] == summary["unique_key_n"] == len(final) == 137_186
    assert not final.duplicated(["prompt_id", "prompt_language", "model"]).any()
    assert summary["source_counts"]["wall_to_wall_v24_schema_repair"] == EXPECTED_N
    assert summary["genuine_refusal_n"] == int(final.pred_genuine_refusal.sum())
    assert summary["capability_failure_n"] == int(final.pred_capability_failure.sum())


def test_repair_prompt_resolves_conflict_without_forcing_field_flip() -> None:
    prompt = (ROOT / DEFAULT_DIR / "prompt.txt").read_text(encoding="utf-8")
    retry = (ROOT / DEFAULT_DIR / "adaptive_retry.txt").read_text(encoding="utf-8")
    assert "do not mechanically edit" in prompt
    assert "coherent or partly coherent" in prompt
    assert "incoherent-garbled or unassessable" in prompt
    assert "preceding draft was rejected for" in retry


def test_repair_authorization_binds_payload_protocol_and_ceiling(tmp_path: Path) -> None:
    source = ROOT / DEFAULT_DIR
    output = tmp_path / "repair"
    shutil.copytree(source, output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    manifest.pop("authorization", None)
    manifest["paid_run_authorized"] = False
    manifest["status"] = "frozen_unpaid"
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    cost = json.loads((output / "cost_estimate.json").read_text(encoding="utf-8"))

    with pytest.raises(RuntimeError, match="explicit authorization"):
        authorize_wall_to_wall_repair_v24(
            output, cost["provider_payload_sha256"], cost["protocol_sha256"], 0.5, False
        )
    with pytest.raises(ValueError, match="payload hash"):
        authorize_wall_to_wall_repair_v24(
            output, "0" * 64, cost["protocol_sha256"], 0.5, True
        )
    with pytest.raises(ValueError, match="protocol hash"):
        authorize_wall_to_wall_repair_v24(
            output, cost["provider_payload_sha256"], "0" * 64, 0.5, True
        )
    with pytest.raises(ValueError, match="ceiling"):
        authorize_wall_to_wall_repair_v24(
            output, cost["provider_payload_sha256"], cost["protocol_sha256"], 1.0, True
        )

    with pytest.raises(RuntimeError, match="paid repair"):
        run_wall_to_wall_repair_v24(ROOT, output, 1, 0.5, False)
