import json
from pathlib import Path
import shutil
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.model_expansion.openrouter_pilot import (
    DEFAULT_DIR,
    authorize_pilot,
    estimate_pilot_cost,
    prepare_pilot,
    read_jsonl,
    run_pilot,
    sha_file,
)


PILOT = ROOT / DEFAULT_DIR
PAYLOAD_SHA = "9e5b2ef03ded2a5c55352fd8f8e6f7a459a4dd917a45567395c4fbfd9e1b3835"


def test_frozen_pilot_is_complete_and_balanced():
    manifest = prepare_pilot(ROOT, PILOT)
    assert manifest["provider_payload_sha256"] == PAYLOAD_SHA
    assert manifest["n_requests"] == 1_600
    assert manifest["paid_run_authorized"] == manifest["network_inference_call_made"]
    if manifest["network_inference_call_made"]:
        assert manifest["run_summary"]["n_completed"] == 1_600
        assert manifest["run_summary"]["n_incomplete"] == 0
    rows = read_jsonl(PILOT / "provider_requests.jsonl")
    assert len(rows) == len({row["provider_request_id"] for row in rows}) == 1_600
    assert all(row["provider"]["allow_fallbacks"] is False for row in rows)
    assert all(row["provider"]["only"] == [row["provider_tag"]] for row in rows)
    assert {row["prompt_language"] for row in rows} == {"en", "zh", "ar", "ru", "hi"}
    assert len({row["model"] for row in rows}) == 8

    selected = pd.read_csv(PILOT / "pilot_prompt_index.csv")
    assert len(selected) == selected["prompt_id"].nunique() == 40
    assert selected["issue_id"].nunique() == 40
    cells = selected.groupby(["controversy_tier", "pilot_band"]).size()
    assert len(cells) == 8 and set(cells) == {5}
    assert set(selected["region_focus"]) == {"Arab", "China", "Europe", "General", "India", "US"}
    assert selected["topic_domain"].nunique() == 9
    assert set(selected["route"]) == {"perennial", "temporal", "current-events"}


def test_pilot_cost_and_authorization_fail_closed(tmp_path):
    cost = estimate_pilot_cost(ROOT, PILOT)
    assert cost["provider_payload_sha256"] == PAYLOAD_SHA
    assert cost["planning_cost_usd"] < cost["suggested_hard_ceiling_usd"] == 6.0
    copy = tmp_path / "pilot"
    shutil.copytree(PILOT, copy)
    with pytest.raises(RuntimeError, match="explicit user authorization"):
        authorize_pilot(copy, PAYLOAD_SHA, 6.0, False)
    with pytest.raises(ValueError, match="payload hash"):
        authorize_pilot(copy, "0" * 64, 6.0, True)
    with pytest.raises(ValueError, match="ceiling"):
        authorize_pilot(copy, PAYLOAD_SHA, 99.0, True)
    with pytest.raises(RuntimeError, match="authorize-paid-run"):
        run_pilot(ROOT, copy, workers=4, ceiling=6.0, authorized=False)


def test_reasoning_is_disabled_only_on_supported_models():
    rows = read_jsonl(PILOT / "provider_requests.jsonl")
    by_model = {row["model"]: row for row in rows}
    for model in ("glm-4.7-flash", "kimi-k2.5", "hunyuan-a13b", "gemini-2.5-flash-lite"):
        assert by_model[model]["reasoning"] == {"enabled": False, "exclude": True}
    for model in ("llama-4-scout", "nova-lite", "mistral-small-3.2", "ministral-14b"):
        assert by_model[model]["reasoning"] is None
