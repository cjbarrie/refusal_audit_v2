import json
import hashlib
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.fold_nested_refinement import (  # noqa: E402
    EXPECTED_REQUESTS,
    INPUT_MODES,
    build_fold_nested_refinement,
    estimate_fold_nested_refinement_cost,
    record_fold_nested_refinement_authorization,
    run_fold_nested_refinement,
    score_fold_nested_refinement,
)


PILOT = ROOT / "annotations" / "response_validity_human_v2"


@pytest.fixture(scope="module")
def frozen_refinement(tmp_path_factory):
    output = tmp_path_factory.mktemp("fold_nested_refinement") / "freeze"
    manifest = build_fold_nested_refinement(ROOT, PILOT, output)
    return output, manifest


def test_refinement_is_complete_and_issue_nested(frozen_refinement):
    output, manifest = frozen_refinement
    gold = pd.read_parquet(output / "evaluation_gold.parquet")
    examples = pd.read_csv(output / "fold_exemplars.csv")
    thresholds = pd.read_csv(output / "transferred_thresholds.csv")
    requests = [
        json.loads(line)
        for line in (output / "provider_requests.jsonl").read_text().splitlines()
    ]
    assert manifest["status"] == "frozen_unpaid"
    assert manifest["paid_run_authorized"] is False
    assert manifest["network_call_made"] is False
    assert len(requests) == EXPECTED_REQUESTS == 1400
    assert len({row["provider_request_id"] for row in requests}) == EXPECTED_REQUESTS
    assert set(row["input_mode"] for row in requests) == set(INPUT_MODES)
    assert len(thresholds) == 10
    assert thresholds.groupby("evaluation_fold_id").size().eq(2).all()
    assert thresholds.threshold.between(0, 1).all()
    assert manifest["thresholds_frozen_before_provider_run"] is True
    for fold in range(1, 6):
        evaluation_issues = set(gold.loc[gold.fold_id.eq(fold), "issue_id"].astype(str))
        fold_examples = examples.loc[examples.fold_id.eq(fold)]
        assert len(fold_examples) == 15
        assert set(fold_examples.example_role) == {
            "hard_refusal", "boundary_nonrefusal", "hard_capability_failure"
        }
        assert not evaluation_issues.intersection(set(fold_examples.issue_id.astype(str)))
        assert set(fold_examples.prompt_language) == {"ar", "en", "hi", "ru", "zh"}


def test_refinement_queries_never_contain_evaluation_labels(frozen_refinement):
    output, _ = frozen_refinement
    requests = [
        json.loads(line)
        for line in (output / "provider_requests.jsonl").read_text().splitlines()
    ]
    for row in requests:
        query = row["messages"][1]["content"]
        assert "CORRECT JSON" not in query
        assert row["provider"]["allow_fallbacks"] is False
        assert row["reasoning"]["exclude"] is True


def test_refinement_cost_is_local_and_fail_closed(frozen_refinement):
    output, manifest = frozen_refinement
    cost = estimate_fold_nested_refinement_cost(ROOT, output)
    assert cost["calls"] == EXPECTED_REQUESTS
    assert cost["provider_payload_sha256"] == manifest["provider_payload_sha256"]
    assert cost["planning_cost_usd"] > 0
    assert cost["suggested_hard_ceiling_usd"] >= cost["single_attempt_reserved_cost_usd"]
    assert cost["paid_run_authorized"] is False
    assert cost["network_call_made"] is False


def test_refinement_builder_is_idempotent(frozen_refinement):
    output, first = frozen_refinement
    second = build_fold_nested_refinement(ROOT, PILOT, output)
    assert second == first


def test_refinement_paid_paths_fail_closed(frozen_refinement, tmp_path):
    source, _ = frozen_refinement
    output = tmp_path / "freeze"
    shutil.copytree(source, output)
    cost = estimate_fold_nested_refinement_cost(ROOT, output)
    with pytest.raises(RuntimeError, match="explicit confirmation"):
        record_fold_nested_refinement_authorization(
            output, cost["provider_payload_sha256"],
            cost["suggested_hard_ceiling_usd"], confirmed=False,
        )
    with pytest.raises(ValueError, match="hash differs"):
        record_fold_nested_refinement_authorization(
            output, "0" * 64, cost["suggested_hard_ceiling_usd"], confirmed=True,
        )
    with pytest.raises(RuntimeError, match="requires --authorize-paid-run"):
        run_fold_nested_refinement(
            ROOT, output, workers=1,
            ceiling=cost["suggested_hard_ceiling_usd"], authorized=False,
        )


def test_refinement_scorer_applies_pre_run_fold_thresholds(frozen_refinement, tmp_path):
    source, _ = frozen_refinement
    output = tmp_path / "scoring"
    shutil.copytree(source, output)
    requests = [
        json.loads(line)
        for line in (output / "provider_requests.jsonl").read_text().splitlines()
    ]
    gold = pd.read_parquet(output / "evaluation_gold.parquet").set_index("review_id")
    capability = {"incoherent_garbled", "wrong_language", "technical_degeneration"}
    rows = []
    for request in requests:
        human = gold.loc[request["evaluation_review_id"]]
        refusal = human.primary_class == "genuine_refusal"
        failure = human.primary_class in capability
        rows.append({
            "provider_request_id": request["provider_request_id"],
            "logical_request_id": request["logical_request_id"],
            "evaluation_review_id": request["evaluation_review_id"],
            "evaluation_fold_id": request["evaluation_fold_id"],
            "config_id": request["config_id"],
            "input_mode": request["input_mode"],
            "model_id": request["model_id"],
            "primary_class": human.primary_class,
            "p_genuine_refusal": 0.99 if refusal else 0.01,
            "p_capability_failure": 0.99 if failure else 0.01,
            "status": "complete",
        })
    results = output / "results.jsonl"
    results.write_text("".join(json.dumps(row) + "\n" for row in rows))
    digest = hashlib.sha256(results.read_bytes()).hexdigest()
    (output / "run_summary.json").write_text(json.dumps({
        "n_completed": EXPECTED_REQUESTS,
        "results_sha256": digest,
    }))
    score = score_fold_nested_refinement(ROOT, output)
    assert score["status"] == "internal_candidate_selected"
    assert score["external_validation_required"] is True
    selected = pd.read_csv(output / "candidate_selection.csv")
    assert selected.all_promotion_gates_pass.all()
