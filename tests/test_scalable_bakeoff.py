import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.scalable_bakeoff import (  # noqa: E402
    EXPECTED_LOGICAL,
    EXPECTED_PROVIDER,
    INPUT_MODES,
    MODELS,
    build_scalable_bakeoff,
    estimate_scalable_bakeoff_cost,
    record_scalable_bakeoff_authorization,
    run_scalable_bakeoff,
    validate_response_validity_documentation,
    _validate_label,
)


PILOT = ROOT / "annotations" / "response_validity_human_v2"


@pytest.fixture(scope="module")
def frozen_bakeoff(tmp_path_factory):
    output = tmp_path_factory.mktemp("scalable") / "freeze"
    manifest = build_scalable_bakeoff(ROOT, PILOT, output)
    return output, manifest


def test_scalable_bakeoff_freezes_all_700_without_issue_leakage(frozen_bakeoff):
    output, manifest = frozen_bakeoff
    gold = pd.read_parquet(output / "evaluation_gold.parquet")
    examples = pd.read_csv(output / "fold_exemplars.csv")
    requests = [json.loads(line) for line in (output / "model_neutral_requests.jsonl").read_text().splitlines()]
    assert manifest["n_human"] == len(gold) == 700
    assert manifest["reserve_decision"]["status"] == "retired_for_internal_validation"
    assert manifest["n_logical_requests"] == len(requests) == EXPECTED_LOGICAL
    assert manifest["n_provider_requests"] == EXPECTED_PROVIDER
    assert set(gold.fold_id) == {1, 2, 3, 4, 5}
    for fold in range(1, 6):
        evaluation_issues = set(gold.loc[gold.fold_id.eq(fold), "issue_id"].astype(str))
        example_issues = set(examples.loc[examples.fold_id.eq(fold), "issue_id"].astype(str))
        assert not evaluation_issues.intersection(example_issues)
        assert len(examples.loc[examples.fold_id.eq(fold)]) == 15


def test_scalable_payload_crosses_models_configs_and_input_modes(frozen_bakeoff):
    output, _ = frozen_bakeoff
    provider = [json.loads(line) for line in (output / "provider_requests.jsonl").read_text().splitlines()]
    frame = pd.DataFrame(provider)
    assert len(frame) == EXPECTED_PROVIDER
    assert set(frame.model_id) == set(MODELS)
    assert set(frame.input_mode) == set(INPUT_MODES)
    assert frame.provider_request_id.nunique() == EXPECTED_PROVIDER
    assert not any("primary_class" in row for row in provider)
    diagnostic = next(row for row in provider if row["input_mode"] == "translation_only_diagnostic")
    assert "ORIGINAL RESPONSE WITHHELD" in diagnostic["messages"][1]["content"]
    assert "TRANSLATOR-REPORTED SOURCE LANGUAGE" in diagnostic["messages"][1]["content"]


def test_scalable_cost_is_frozen_and_non_authorizing(frozen_bakeoff):
    output, manifest = frozen_bakeoff
    cost = estimate_scalable_bakeoff_cost(ROOT, output)
    assert cost["calls"] == EXPECTED_PROVIDER
    assert cost["planning_cost_usd"] > 0
    assert cost["suggested_hard_ceiling_usd"] >= cost["single_attempt_reserved_cost_usd"]
    assert cost["reserved_input_tokens"] > cost["estimated_input_tokens"]
    assert cost["paid_run_authorized"] is False
    assert manifest["paid_run_authorized"] is False


def test_scalable_builder_is_idempotent(frozen_bakeoff):
    output, first = frozen_bakeoff
    second = build_scalable_bakeoff(ROOT, PILOT, output)
    assert first == second


def test_scalable_paid_paths_fail_closed(frozen_bakeoff, tmp_path):
    output, _ = frozen_bakeoff
    copy = tmp_path / "freeze"
    shutil.copytree(output, copy)
    cost = estimate_scalable_bakeoff_cost(ROOT, copy)
    with pytest.raises(RuntimeError, match="explicit confirmation"):
        record_scalable_bakeoff_authorization(
            copy, cost["provider_payload_sha256"],
            cost["suggested_hard_ceiling_usd"], confirmed=False,
        )
    with pytest.raises(ValueError, match="hash differs"):
        record_scalable_bakeoff_authorization(
            copy, "0" * 64, cost["suggested_hard_ceiling_usd"], confirmed=True,
        )
    with pytest.raises(RuntimeError, match="requires --authorize-paid-run"):
        run_scalable_bakeoff(
            ROOT, copy, workers=1,
            ceiling=cost["suggested_hard_ceiling_usd"], authorized=False,
        )


def test_capability_class_preserves_independent_semantic_behavior():
    record = {
        "semantic_behavior": "answer",
        "language_fidelity": "wrong_language",
        "coherence": "coherent",
        "technical_failure": "none",
        "primary_class": "wrong_language",
        "p_genuine_refusal": 0.0,
        "p_capability_failure": 0.99,
        "confidence": "high",
        "evidence_span": "A coherent answer in the wrong language",
    }
    assert _validate_label(record) == record


def test_reader_facing_status_matches_frozen_manifests():
    status = validate_response_validity_documentation(ROOT)
    assert status["status"] == "pass"
    assert status["n_human"] == 700
    assert status["historical_artifacts_verified"] is True
    assert status["historical_v2_3_repair_status"] == "patched_internal_candidate_selected"
    assert status["historical_v2_3_selected_mode"] == "source_response_only"
    assert status["historical_v2_3_external_certification"] is False
    assert status["production_codebook"] == "response-validity-decomposed-v2.4"
    assert status["full_corpus_stage"] == "completed_after_schema_repair"
    assert status["final_annotation_n"] == 137_186
    assert status["final_genuine_refusal_n"] == 3_591
    assert status["final_capability_failure_n"] == 43_317
