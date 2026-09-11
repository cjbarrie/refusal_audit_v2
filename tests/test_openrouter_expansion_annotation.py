import json
from pathlib import Path
import shutil
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.model_expansion.openrouter_pilot import read_jsonl, sha_file
from refusal_audit.model_expansion.pilot_annotation import (
    ADOPTED_PROMPT,
    ADOPTED_SCHEMA,
    DEFAULT_DIR,
    authorize_pilot_annotations,
    estimate_pilot_annotation_cost,
    prepare_pilot_annotations,
    run_pilot_annotations,
    summarize_pilot_annotations,
)


ANNOTATIONS = ROOT / DEFAULT_DIR
PAYLOAD_SHA = "917b7ecac55ebeec807c812a5254a0d30ae4910373f9ab8977ce073fec027e8c"


def test_frozen_annotation_payload_is_complete_blinded_and_adopted():
    manifest = prepare_pilot_annotations(ROOT, ANNOTATIONS)
    assert manifest["provider_payload_sha256"] == PAYLOAD_SHA
    assert manifest["n_requests"] == 1_600
    assert manifest["input_mode"] == "source_response_only"
    assert manifest["translation_used"] is False
    assert manifest["paid_run_authorized"] == manifest["network_call_made"]
    if manifest["network_call_made"]:
        assert manifest["run_summary"]["n_completed"] == 1_600
        assert manifest["run_summary"]["n_incomplete"] == 0
    assert sha_file(ANNOTATIONS / "prompt.txt") == sha_file(ROOT / ADOPTED_PROMPT)
    assert sha_file(ANNOTATIONS / "response_schema.json") == sha_file(ROOT / ADOPTED_SCHEMA)

    rows = read_jsonl(ANNOTATIONS / "provider_requests.jsonl")
    assert len(rows) == len({row["provider_request_id"] for row in rows}) == 1_600
    assert all(row["model_id"] == "openai/gpt-5.6-luna" for row in rows)
    assert all(row["provider"] == {"only": ["openai"], "allow_fallbacks": False} for row in rows)
    assert all(row["reasoning"] == {"enabled": False, "exclude": True} for row in rows)
    assert all(row["temperature"] == 0 and row["max_output_tokens"] == 500 for row in rows)
    assert all("subject_model" not in row and "pilot_band" not in row for row in rows)
    messages = json.dumps([row["messages"] for row in rows], ensure_ascii=False)
    for forbidden in ("subject_model", "pilot_band", "prior_refusal_prop"):
        assert forbidden not in messages

    index = pd.read_parquet(ANNOTATIONS / "response_index.parquet")
    assert len(index) == index["audit_response_id"].nunique() == 1_600
    assert set(index["prompt_language"]) == {"en", "zh", "ar", "ru", "hi"}
    assert index.groupby("subject_model").size().eq(200).all()


def test_annotation_cost_and_authorization_fail_closed(tmp_path):
    cost = estimate_pilot_annotation_cost(ROOT, ANNOTATIONS)
    assert cost["provider_payload_sha256"] == PAYLOAD_SHA
    assert cost["planning_cost_usd"] < cost["suggested_hard_ceiling_usd"] == 2.5
    copy = tmp_path / "annotations"
    shutil.copytree(ANNOTATIONS, copy)
    with pytest.raises(RuntimeError, match="explicit user authorization"):
        authorize_pilot_annotations(copy, PAYLOAD_SHA, 2.5, False)
    with pytest.raises(ValueError, match="payload hash"):
        authorize_pilot_annotations(copy, "0" * 64, 2.5, True)
    with pytest.raises(ValueError, match="ceiling"):
        authorize_pilot_annotations(copy, PAYLOAD_SHA, 99.0, True)
    with pytest.raises(RuntimeError, match="authorize-paid-run"):
        run_pilot_annotations(ROOT, copy, workers=4, ceiling=2.5, authorized=False)


def test_completed_annotation_summary_keeps_outcomes_separate():
    summary = summarize_pilot_annotations(ROOT, ANNOTATIONS)
    assert summary["n"] == 1_600
    assert summary["genuine_refusal_n"] == 142
    assert summary["capability_failure_n"] == 279
    assert summary["overlap_n"] == 15
    labels = pd.read_parquet(ANNOTATIONS / "assembled_labels.parquet")
    assert len(labels) == labels["audit_response_id"].nunique() == 1_600
    assert labels["pred_genuine_refusal"].sum() == 142
    assert labels["pred_capability_failure"].sum() == 279
    assert labels["both_refusal_and_capability_failure"].sum() == 15
