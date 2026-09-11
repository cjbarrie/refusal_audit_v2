import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.refinement_access import (  # noqa: E402
    freeze_enrichment_storage_400,
    freeze_refinement_access_v1,
    freeze_refinement_access_v2,
    run_sealed_support_gate_v1,
    run_sealed_support_gate_v2,
)
from refusal_audit.response_validity.human_pilot import sha_file  # noqa: E402


WAVE = ROOT / "annotations" / "response_validity_human_v2" / "enrichment_wave_v2_400"


def test_refinement_accessor_emits_development_only(tmp_path):
    output = tmp_path / "access"
    manifest = freeze_refinement_access_v1(ROOT, WAVE, output)
    cases = pd.read_parquet(output / "development_cases.parquet")
    labels = [
        json.loads(line)
        for line in (output / "development_labels.jsonl").read_text().splitlines()
        if line.strip()
    ]
    commitment = json.loads((output / "sealed_evaluation_commitment.json").read_text())
    assert manifest["n_development"] == len(cases) == len(labels) == 122
    assert cases.analysis_split.eq("development").all()
    assert cases.review_id.nunique() == 122
    assert commitment["n_new_evaluation"] == 62
    assert commitment["evaluation_outcome_rows_emitted"] is False
    assert commitment["evaluation_outcome_counts_emitted"] is False
    assert not any("evaluation" in path.name and path.suffix in {".jsonl", ".parquet"}
                   for path in output.iterdir())


def test_sealed_support_gate_emits_booleans_not_counts(tmp_path):
    output = tmp_path / "access"
    result = run_sealed_support_gate_v1(ROOT, WAVE, output)
    assert result["n_evaluation"] == 62
    assert isinstance(result["support_pass"], bool)
    assert all(isinstance(value, bool) for value in result["criteria_met"].values())
    assert result["exact_counts_emitted"] is False
    assert result["evaluation_rows_emitted"] is False
    forbidden = {"actual_counts", "evaluation_rows", "primary_class_counts"}
    assert not forbidden.intersection(result)


def test_completed_400_storage_freeze_is_byte_identical_and_idempotent(tmp_path):
    output = tmp_path / "storage_freeze_400_v1"
    manifest = freeze_enrichment_storage_400(ROOT, WAVE, output)
    frozen = output / "human_labels_all_400.jsonl"
    live = WAVE / "human_labels.jsonl"
    assert manifest["n_records"] == 400
    assert frozen.read_bytes() == live.read_bytes()
    assert manifest["artifact_sha256"][frozen.name] == sha_file(live)
    assert manifest["first_300_equal_storage_freeze_300_v1"] is True
    assert manifest["final_evaluation_labels_opened_for_analysis"] is False
    assert freeze_enrichment_storage_400(ROOT, WAVE, output) == manifest


def test_refinement_accessor_v2_emits_all_development_and_no_evaluation_rows(tmp_path):
    output = tmp_path / "access_v2"
    manifest = freeze_refinement_access_v2(ROOT, WAVE, output)
    cases = pd.read_parquet(output / "development_cases.parquet")
    labels = [
        json.loads(line)
        for line in (output / "development_labels.jsonl").read_text().splitlines()
        if line.strip()
    ]
    commitment = json.loads((output / "sealed_evaluation_commitment.json").read_text())
    assert manifest["n_development"] == len(cases) == len(labels) == 161
    assert manifest["n_added_development"] == 39
    assert cases.analysis_split.eq("development").all()
    assert cases.review_id.nunique() == 161
    assert commitment["n_sealed_evaluation"] == 123
    assert commitment["n_previously_spent_evaluation"] == 116
    assert commitment["orders_201_300_commitment_verified"] is True
    assert commitment["evaluation_outcome_rows_emitted"] is False
    assert commitment["evaluation_outcome_counts_emitted"] is False
    assert not any(
        "evaluation" in path.name and path.suffix in {".jsonl", ".parquet"}
        for path in output.iterdir()
    )


def test_sealed_support_gate_v2_emits_booleans_not_counts(tmp_path):
    output = tmp_path / "access_v2"
    result = run_sealed_support_gate_v2(ROOT, WAVE, output)
    assert result["n_evaluation"] == 123
    assert isinstance(result["support_pass"], bool)
    assert all(isinstance(value, bool) for value in result["criteria_met"].values())
    assert result["exact_counts_emitted"] is False
    assert result["evaluation_rows_emitted"] is False
    forbidden = {"actual_counts", "evaluation_rows", "primary_class_counts"}
    assert not forbidden.intersection(result)
