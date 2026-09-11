from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.refusal_boundary_consistency import (  # noqa: E402
    DEFAULT_DIR,
    freeze_refusal_boundary_consistency,
    summarize_refusal_boundary_consistency,
)


def test_frozen_boundary_review_is_exact_and_reusable() -> None:
    first = freeze_refusal_boundary_consistency(ROOT)
    repeated = freeze_refusal_boundary_consistency(ROOT)
    assert repeated == first
    assert first["n_candidates"] == 24
    assert first["n_carried_forward"] == 4
    assert first["n_new_review"] == 20
    assert first["provider_call_made"] is False

    folder = ROOT / DEFAULT_DIR
    candidates = pd.read_parquet(folder / "candidate_design.parquet")
    queue = pd.read_parquet(folder / "review_packet.parquet")
    carry = pd.read_csv(folder / "carried_forward_decisions.csv")
    assert candidates.audit_response_id.nunique() == 24
    assert queue.audit_response_id.nunique() == 20
    assert carry.audit_response_id.nunique() == 4
    assert set(queue.audit_response_id).isdisjoint(set(carry.audit_response_id))
    assert set(queue.audit_response_id) | set(carry.audit_response_id) == set(
        candidates.audit_response_id
    )
    assert candidates.pred_genuine_refusal_luna.astype(bool).all()
    assert (
        candidates.epistemic_limitation_luna.astype(bool)
        | candidates.stance_disclaimer_luna.astype(bool)
    ).all()


def test_completed_boundary_review_assembles_without_rewriting_sources() -> None:
    first = summarize_refusal_boundary_consistency(ROOT)
    repeated = summarize_refusal_boundary_consistency(ROOT)
    assert repeated == first
    assert first["status"] == "complete_targeted_single_reviewer_consistency_audit"
    assert first["n_rows"] == 24
    assert first["n_carried_forward"] == 4
    assert first["n_newly_reviewed"] == 20
    assert first["n_decided"] == 22
    assert first["n_uncertain"] == 2
    assert first["final_genuine_refusal_n"] == 17
    assert first["source_logs_overwritten"] is False
    assert first["provider_call_made"] is False
