import json
from pathlib import Path

import pandas as pd

from refusal_audit.model_expansion.full_run_annotation_v3 import (
    DEFAULT_DIR, EXPECTED_N, estimate_completed_batch_annotation_cost,
    prepare_completed_batch_annotations,
)


ROOT = Path(__file__).resolve().parents[1]


def test_completed_batch1_is_complete_blinded_and_authorized():
    manifest = prepare_completed_batch_annotations(ROOT, ROOT / DEFAULT_DIR)
    assert manifest["n_requests"] == EXPECTED_N == 37440
    assert manifest["subject_models"] == [
        "ministral-14b", "nova-lite", "llama-4-scout"
    ]
    assert manifest["input_mode"] == "source_response_only"
    assert manifest["translation_used"] is False
    assert manifest["reasoning_disabled"] is True
    assert manifest["allow_fallbacks"] is False
    # This fixture is the completed, user-authorized production batch.  The
    # earlier preflight test expected False before provider execution; keeping
    # that expectation after completion incorrectly treated valid provenance
    # as a regression.
    assert manifest["paid_run_authorized"] is True
    assert manifest["network_call_made"] is True

    index = pd.read_parquet(ROOT / DEFAULT_DIR / "response_index.parquet")
    assert len(index) == EXPECTED_N
    assert not index.duplicated(["prompt_id", "prompt_language", "subject_model"]).any()
    assert index.groupby("subject_model").size().eq(12480).all()
    assert index.groupby(["subject_model", "prompt_language"]).size().eq(2496).all()

    with (ROOT / DEFAULT_DIR / "provider_requests.jsonl").open(encoding="utf-8") as handle:
        first = json.loads(next(handle))
    serialized = json.dumps(first["messages"], ensure_ascii=False)
    assert "subject_model" not in serialized
    assert first["model_id"] == "openai/gpt-5.6-luna"
    assert first["provider"] == {"only": ["openai"], "allow_fallbacks": False}


def test_completed_batch1_cost_uses_empirical_stop_loss():
    cost = estimate_completed_batch_annotation_cost(ROOT, ROOT / DEFAULT_DIR)
    assert cost["requests"] == EXPECTED_N
    assert cost["empirical_cost_projection_usd"] < cost["planning_cost_usd"]
    assert cost["suggested_hard_ceiling_usd"] == 35.0
    assert cost["paid_run_authorized"] is False
