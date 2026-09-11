import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.model_expansion.apertus_8b_pilot import (
    DEFAULT_DIR,
    authorize_apertus_8b_pilot,
    estimate_apertus_8b_cost,
    prepare_apertus_8b_pilot,
    run_apertus_8b_pilot,
)
from refusal_audit.model_expansion.openrouter_pilot import read_jsonl, sha_file


PILOT = ROOT / DEFAULT_DIR


def test_apertus_8b_freeze_is_versioned_and_preserves_the_prompt_frame():
    manifest = prepare_apertus_8b_pilot(ROOT, PILOT)
    rows = read_jsonl(PILOT / "provider_requests.jsonl")
    assert manifest["historical_70b_pilot_unchanged"] is True
    assert manifest["paid_run_authorized"] == manifest["network_inference_call_made"]
    if manifest["network_inference_call_made"]:
        assert manifest["run_summary"]["n_completed"] == 0
        assert manifest["run_summary"]["provider_cost_usd"] == 0
    assert len(rows) == len({r["provider_request_id"] for r in rows}) == 200
    assert {r["prompt_language"] for r in rows} == {"en", "zh", "ar", "ru", "hi"}
    assert {r["model"] for r in rows} == {"apertus-v1.5-8b"}
    assert all(r["model_id"] == "swiss-ai/Apertus-v1.5-8B:publicai" for r in rows)
    assert all(r["temperature"] == 1.0 and r["max_output_tokens"] == 5000 for r in rows)
    source = ROOT / "annotations/model_expansion_v2/apertus_replacement_pilot_v1/pilot_prompt_index.csv"
    assert sha_file(PILOT / "pilot_prompt_index.csv") == sha_file(source)


def test_apertus_8b_cost_and_authorization_fail_closed(tmp_path):
    cost = estimate_apertus_8b_cost(ROOT, PILOT)
    payload_sha = cost["provider_payload_sha256"]
    assert cost["planning_cost_usd"] < cost["single_attempt_reserved_cost_usd"]
    assert cost["two_attempt_reserved_cost_usd"] < cost["suggested_hard_ceiling_usd"]
    copy = tmp_path / "apertus8b"
    shutil.copytree(PILOT, copy)
    with pytest.raises(RuntimeError, match="explicit user authorization"):
        authorize_apertus_8b_pilot(copy, payload_sha, cost["suggested_hard_ceiling_usd"], False)
    with pytest.raises(ValueError, match="payload hash"):
        authorize_apertus_8b_pilot(copy, "0" * 64, cost["suggested_hard_ceiling_usd"], True)
    with pytest.raises(ValueError, match="ceiling"):
        authorize_apertus_8b_pilot(copy, payload_sha, 99.0, True)
    with pytest.raises(RuntimeError, match="authorize-paid-run"):
        run_apertus_8b_pilot(ROOT, copy, workers=4,
                             ceiling=cost["suggested_hard_ceiling_usd"], authorized=False)
