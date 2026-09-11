import json
from pathlib import Path
import shutil
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.model_expansion.apertus_pilot import (
    DEFAULT_DIR,
    authorize_apertus_pilot,
    estimate_apertus_cost,
    prepare_apertus_pilot,
    run_apertus_pilot,
)
from refusal_audit.model_expansion.openrouter_pilot import read_jsonl


PILOT = ROOT / DEFAULT_DIR
PAYLOAD_SHA = "dd52cafb9ec771f04e1f8a93ce48f52e4ae0320719fd6e72f6e928f0b0f46e0a"


def test_v2_roster_replaces_mistral_small_with_apertus():
    roster = json.loads(
        (ROOT / "config/model_rosters/multirouter_expansion_v2.json").read_text()
    )
    names = {model["name"] for model in roster["models"]}
    assert len(names) == 8
    assert "mistral-small-3.2" not in names
    assert "apertus-v1.5-70b" in names
    apertus = next(m for m in roster["models"] if m["name"] == "apertus-v1.5-70b")
    assert apertus["model_id"] == "swiss-ai/Apertus-v1.5-70B:publicai"
    assert apertus["provider_routing"] == {
        "model_suffix": ":publicai", "allow_fallbacks": False,
    }


def test_frozen_apertus_pilot_reuses_exact_v1_prompt_frame():
    manifest = prepare_apertus_pilot(ROOT, PILOT)
    assert manifest["provider_payload_sha256"] == PAYLOAD_SHA
    assert manifest["n_requests"] == 200
    assert manifest["provider_fallbacks_disabled_by_exact_suffix"] is True
    assert manifest["paid_run_authorized"] == manifest["network_inference_call_made"]
    rows = read_jsonl(PILOT / "provider_requests.jsonl")
    assert len(rows) == len({row["provider_request_id"] for row in rows}) == 200
    assert {row["prompt_language"] for row in rows} == {"en", "zh", "ar", "ru", "hi"}
    assert {row["model"] for row in rows} == {"apertus-v1.5-70b"}
    assert all(row["model_id"] == "swiss-ai/Apertus-v1.5-70B:publicai" for row in rows)
    assert all(row["thinking_mode"] == "off_by_model_default" for row in rows)
    source = pd.read_csv(
        ROOT / "annotations/model_expansion_v1/openrouter_pilot_v1/pilot_prompt_index.csv"
    )
    current = pd.read_csv(PILOT / "pilot_prompt_index.csv")
    assert set(source.prompt_id) == set(current.prompt_id)


def test_apertus_cost_and_authorization_fail_closed(tmp_path):
    cost = estimate_apertus_cost(ROOT, PILOT)
    assert cost["provider_payload_sha256"] == PAYLOAD_SHA
    assert cost["planning_cost_usd"] < cost["suggested_hard_ceiling_usd"] == 4.0
    copy = tmp_path / "apertus"
    shutil.copytree(PILOT, copy)
    with pytest.raises(RuntimeError, match="explicit user authorization"):
        authorize_apertus_pilot(copy, PAYLOAD_SHA, 4.0, False)
    with pytest.raises(ValueError, match="payload hash"):
        authorize_apertus_pilot(copy, "0" * 64, 4.0, True)
    with pytest.raises(ValueError, match="ceiling"):
        authorize_apertus_pilot(copy, PAYLOAD_SHA, 99.0, True)
    with pytest.raises(RuntimeError, match="authorize-paid-run"):
        run_apertus_pilot(ROOT, copy, workers=4, ceiling=4.0, authorized=False)
