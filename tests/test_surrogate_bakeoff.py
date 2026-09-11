import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.human_audit import build_complete_language_review_labels  # noqa: E402
from refusal_audit.response_validity.surrogate_bakeoff import (  # noqa: E402
    build_surrogate_bakeoff,
    build_stage_a_adjudication_packet,
    estimate_surrogate_bakeoff_cost,
    freeze_and_score_stage_a_adjudications,
    score_surrogate_results,
)
from refusal_audit.response_validity.stage_b_bakeoff import (  # noqa: E402
    STAGE_B_CONFIGS,
    STAGE_B_MODELS,
    build_stage_b_bakeoff,
    estimate_stage_b_cost,
    record_stage_b_authorization,
    run_stage_b,
)


def test_complete_language_review_covers_all_300_without_touching_repeats():
    pilot = ROOT / "annotations" / "response_validity_human_v2"
    manifest = build_complete_language_review_labels(ROOT, pilot)
    labels = pd.read_parquet(
        pilot / "base_freeze_v3_complete_language_review" / "base_labels.parquet"
    )
    assert manifest["repeat_records_read"] is False
    assert len(labels) == labels.review_id.nunique() == 300
    assert labels.language_fidelity.value_counts().to_dict() == {
        "target": 283, "wrong_language": 15, "mixed": 2,
    }


def test_bakeoff_split_has_no_prompt_leakage_and_all_classes_in_both_arms():
    pilot = ROOT / "annotations" / "response_validity_human_v2"
    output = pilot / "surrogate_bakeoff_v1"
    before = json.loads((output / "bakeoff_manifest.json").read_text())
    manifest = build_surrogate_bakeoff(ROOT, pilot)
    assignments = pd.read_parquet(output / "split_assignments.parquet")
    development = assignments.loc[assignments.split.eq("development")]
    evaluation = assignments.loc[assignments.split.eq("evaluation")]
    # Rebuilding the deterministic design must preserve, not erase, an already
    # completed paid-run provenance record.
    assert manifest.get("paid_or_network_call_made", False) == before.get(
        "paid_or_network_call_made", False
    )
    assert manifest.get("stage_a_run") == before.get("stage_a_run")
    assert len(development) == 216 and len(evaluation) == 84
    assert not (set(development.prompt_id) & set(evaluation.prompt_id))
    assert set(development.primary_class) == set(evaluation.primary_class)
    assert evaluation.prompt_language.nunique() == 5
    assert evaluation.model.nunique() == 11


def test_bakeoff_payload_never_uses_evaluation_rows_as_exemplars():
    output = ROOT / "annotations" / "response_validity_human_v2" / "surrogate_bakeoff_v1"
    assignments = pd.read_parquet(output / "split_assignments.parquet")
    exemplars = pd.read_csv(output / "exemplar_assignments.csv")
    requests = [
        json.loads(line)
        for line in (output / "model_neutral_requests.jsonl").read_text().splitlines()
        if line.strip()
    ]
    evaluation_ids = set(assignments.loc[assignments.split.eq("evaluation"), "review_id"])
    assert not (evaluation_ids & set(exemplars.review_id))
    assert len(requests) == 420
    assert len({row["request_id"] for row in requests}) == 420
    assert {row["evaluation_review_id"] for row in requests} == evaluation_ids
    assert all("evaluation_gold" not in json.dumps(row) for row in requests)


def test_cost_gate_is_unpaid_and_stage_a_is_below_two_dollars():
    output = ROOT / "annotations" / "response_validity_human_v2" / "surrogate_bakeoff_v1"
    summary = estimate_surrogate_bakeoff_cost(ROOT, output)
    assert summary["network_call_made"] is False
    assert summary["paid_run_authorized"] is False
    assert summary["stage_a_calls"] == 420
    assert summary["stage_a_worst_case_list_cost_usd"] < 1.0
    assert summary["stage_a_suggested_hard_ceiling_usd"] == 2.0


def test_perfect_results_score_one(tmp_path):
    source = ROOT / "annotations" / "response_validity_human_v2" / "surrogate_bakeoff_v1"
    for name in ["bakeoff_manifest.json", "evaluation_gold.parquet"]:
        shutil.copy2(source / name, tmp_path / name)
    gold = pd.read_parquet(source / "evaluation_gold.parquet")
    records = []
    for row in gold.itertuples(index=False):
        records.append({
            "model_id": "test/perfect",
            "config_id": "test_config",
            "evaluation_review_id": row.review_id,
            "primary_class": row.primary_class,
            "language_fidelity": row.language_fidelity,
            "confidence": "high",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "incremental_provider_cost": 0.0,
            "elapsed_seconds": 0.0,
            "status": "complete",
        })
    results = tmp_path / "results.jsonl"
    results.write_text("\n".join(json.dumps(row) for row in records) + "\n")
    metrics = score_surrogate_results(tmp_path, results)
    macro = metrics.loc[metrics.metric.eq("macro_f1"), "value"].iloc[0]
    accuracy = metrics.loc[metrics.metric.eq("primary_accuracy"), "value"].iloc[0]
    assert np.isclose(macro, 1.0) and np.isclose(accuracy, 1.0)


def test_stage_a_adjudication_packet_is_18_rows_and_blinded():
    pilot = ROOT / "annotations" / "response_validity_human_v2"
    manifest = build_stage_a_adjudication_packet(ROOT, pilot)
    packet = pd.read_parquet(pilot / "stage_a_adjudication_v1" / "adjudication_packet.parquet")
    assert manifest["n_rows"] == len(packet) == packet.review_id.nunique() == 18
    assert manifest["network_call_made"] is False
    forbidden = {
        "primary_class", "confidence", "note", "model", "engagement_code",
        "refusal_justification", "coder_id", "review_order",
    }
    assert not (forbidden & set(packet.columns))


def test_completed_stage_a_adjudications_freeze_without_overwriting_original():
    pilot = ROOT / "annotations" / "response_validity_human_v2"
    labels = pilot / "stage_a_adjudication_v1" / "human_adjudications.jsonl"
    if not labels.exists():
        import pytest
        pytest.skip("human adjudications not complete")
    manifest = freeze_and_score_stage_a_adjudications(ROOT, pilot)
    freeze = pilot / "stage_a_adjudication_v1" / "freeze_v1"
    comparison = pd.read_csv(freeze / "label_comparison.csv")
    adjudicated = pd.read_parquet(freeze / "evaluation_gold_adjudicated.parquet")
    assert manifest["n_adjudicated"] == 18
    assert manifest["n_changed"] == int(comparison.changed.sum()) == 6
    assert manifest["original_labels_overwritten"] is False
    assert len(adjudicated) == 84 and adjudicated.adjudication_applied.sum() == 18


def test_stage_b_freeze_is_exact_authorized_completed_and_label_blind():
    pilot = ROOT / "annotations" / "response_validity_human_v2"
    output = pilot / "surrogate_bakeoff_stage_b_v1"
    manifest = build_stage_b_bakeoff(ROOT, pilot)
    requests = [
        json.loads(line)
        for line in (output / "stage_b_requests.jsonl").read_text().splitlines()
        if line.strip()
    ]
    logical = [
        json.loads(line)
        for line in (output / "model_neutral_requests.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert manifest["n_logical_requests"] == len(logical) == 252
    assert manifest["n_provider_requests"] == len(requests) == 504
    assert manifest["paid_run_authorized"] is True
    assert manifest["paid_or_network_call_made"] is True
    assert manifest["status"] == "completed_and_scored"
    assert manifest["stage_b_authorization"]["provider_payload_sha256"] == (
        manifest["provider_payload_sha256"]
    )
    assert manifest["stage_b_authorization"]["cost_ceiling_usd"] == 8.0
    assert manifest["stage_b_run"]["n_completed"] == 504
    assert manifest["stage_b_run"]["provider_cost_usd"] <= 8.0
    assert manifest["stage_b_run"]["allow_fallbacks"] is False
    assert {row["model_id"] for row in requests} == set(STAGE_B_MODELS)
    assert {row["config_id"] for row in requests} == set(STAGE_B_CONFIGS)
    assert len({row["stage_b_request_id"] for row in requests}) == 504
    assert len({row["evaluation_review_id"] for row in requests}) == 84
    assert all("primary_class" not in row and "gold" not in row for row in requests)
    assert all(row["provider"]["allow_fallbacks"] is False for row in requests)
    assert {
        tuple(row["provider"]["only"]) for row in requests
    } == {("google-ai-studio",), ("anthropic",)}


def test_stage_b_cost_is_current_local_and_below_hard_ceiling():
    output = (
        ROOT / "annotations" / "response_validity_human_v2"
        / "surrogate_bakeoff_stage_b_v1"
    )
    summary = estimate_stage_b_cost(ROOT, output)
    assert summary["pricing_verified_at"] == "2026-08-23"
    assert summary["calls"] == 504
    assert summary["network_call_made"] is False
    assert summary["paid_run_authorized"] is False
    assert summary["planning_cost_usd"] < summary["single_attempt_reserved_cost_usd"]
    assert summary["single_attempt_reserved_cost_usd"] < summary["suggested_hard_ceiling_usd"] == 8.0


def test_stage_b_authorization_and_run_fail_closed(tmp_path):
    source = (
        ROOT / "annotations" / "response_validity_human_v2"
        / "surrogate_bakeoff_stage_b_v1"
    )
    for name in [
        "stage_b_manifest.json", "stage_b_requests.jsonl",
        "cost_estimate.csv", "cost_estimate_summary.json",
    ]:
        shutil.copy2(source / name, tmp_path / name)
    with pytest.raises(RuntimeError, match="explicit confirmation"):
        record_stage_b_authorization(tmp_path, "not-authorized", 8.0, False)
    with pytest.raises(ValueError, match="differs"):
        record_stage_b_authorization(tmp_path, "0" * 64, 8.0, True)
    payload_sha = json.loads((tmp_path / "stage_b_manifest.json").read_text())[
        "provider_payload_sha256"
    ]
    authorization = record_stage_b_authorization(tmp_path, payload_sha, 8.0, True)
    assert authorization["n_requests"] == 504
    assert authorization["allow_fallbacks"] is False
    with pytest.raises(RuntimeError, match="explicit paid-run flag"):
        run_stage_b(ROOT, tmp_path, workers=1, ceiling=8.0, authorized=False)
