import json
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.enrichment_checkpoint import (  # noqa: E402
    ADVANCING_CONFIGS,
    AUTHORIZED_CEILING,
    AUTHORIZED_MODEL,
    AUTHORIZED_PAYLOAD_SHA256,
    AUTHORIZED_PROVIDER,
    _reported_cost,
    build_protected_surrogate_evaluation,
    freeze_enrichment_checkpoint_200,
    record_protected_evaluation_authorization,
)
from refusal_audit.response_validity.human_pilot import sha_file  # noqa: E402


WAVE = ROOT / "annotations" / "response_validity_human_v2" / "enrichment_wave_v2_400"
CHECKPOINT = WAVE / "checkpoint_200_v1"
EVALUATION = CHECKPOINT / "surrogate_evaluation_v1"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_checkpoint_is_exact_append_safe_first_200():
    manifest = freeze_enrichment_checkpoint_200(ROOT, WAVE)
    labels = pd.read_parquet(CHECKPOINT / "checkpoint_labels.parquet")
    assert len(labels) == manifest["n_labels"] == 200
    assert labels.review_order.astype(int).tolist() == list(range(1, 201))
    assert labels.review_id.nunique() == 200
    assert manifest["analysis_split_counts"] == {"development": 84, "evaluation": 116}
    assert manifest["use_for_population_prevalence"] is False
    assert manifest["use_for_dsl_residual_correction"] is False
    for name, digest in manifest["artifact_sha256"].items():
        assert sha_file(CHECKPOINT / name) == digest


def test_protected_payload_has_no_gold_and_reuses_frozen_prompts():
    manifest = build_protected_surrogate_evaluation(ROOT, WAVE)
    requests = _read_jsonl(EVALUATION / "model_neutral_requests.jsonl")
    provider = _read_jsonl(EVALUATION / "provider_requests.jsonl")
    gold = pd.read_parquet(EVALUATION / "evaluation_gold.parquet")
    development = pd.read_parquet(EVALUATION / "development_labels.parquet")
    assert len(gold) == 116 and len(development) == 84
    assert len(requests) == len(provider) == 232
    assert len({row["request_id"] for row in requests}) == 232
    assert set(row["config_id"] for row in requests) == set(ADVANCING_CONFIGS)
    assert set(row["evaluation_review_id"] for row in requests) == set(gold.review_id)
    assert not set(gold.prompt_id).intersection(development.prompt_id)
    assert all("primary_class" not in row and "gold" not in row for row in requests)
    assert manifest["evaluation_gold_excluded_from_payload"] is True
    assert sha_file(EVALUATION / "provider_requests.jsonl") == manifest["provider_payload_sha256"]


def test_protected_authorization_is_exact_and_local(tmp_path):
    copied = tmp_path / "evaluation"
    shutil.copytree(EVALUATION, copied)
    authorization = record_protected_evaluation_authorization(
        copied,
        AUTHORIZED_PAYLOAD_SHA256,
        AUTHORIZED_MODEL,
        AUTHORIZED_PROVIDER,
        AUTHORIZED_CEILING,
        True,
    )
    assert authorization["n_requests"] == 232
    assert authorization["reasoning_enabled"] is False
    assert authorization["allow_fallbacks"] is False
    manifest = json.loads((copied / "evaluation_manifest.json").read_text())
    assert manifest["paid_run_authorized"] is True


def test_byok_ceiling_uses_upstream_inference_cost():
    usage = {
        "cost": 0,
        "is_byok": True,
        "cost_details": {"upstream_inference_cost": 0.0123},
        "prompt_tokens": 1,
        "completion_tokens": 1,
    }
    assert _reported_cost(usage, 0.2, 1.2) == 0.0123
