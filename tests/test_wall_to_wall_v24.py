import json
from pathlib import Path

import pandas as pd
import pytest

from refusal_audit.response_validity.human_pilot import KEY, sha_file
from refusal_audit.response_validity.wall_to_wall_v24 import (
    DEFAULT_DIR,
    EXPECTED_NEW_N,
    EXPECTED_POPULATION_N,
    EXPECTED_REUSE_N,
    _retry_policy,
    authorize_wall_to_wall_luna_v24,
    run_wall_to_wall_luna_v24,
)


ROOT = Path(__file__).resolve().parents[1]


def test_wall_to_wall_freeze_reconciles_population_without_duplicate_payment():
    out = ROOT / DEFAULT_DIR
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    pending = pd.read_parquet(out / "request_index.parquet")
    reused = pd.read_parquet(out / "reused_response_keys.parquet")
    assert manifest["population_n"] == EXPECTED_POPULATION_N
    assert manifest["reused_exact_v2_4_labels_n"] == len(reused) == EXPECTED_REUSE_N
    assert manifest["new_provider_requests_n"] == len(pending) == EXPECTED_NEW_N
    assert len(pending) + len(reused) == EXPECTED_POPULATION_N
    assert not pending.duplicated(KEY).any()
    assert not reused.duplicated(KEY).any()
    assert not set(map(tuple, pending[KEY].itertuples(index=False, name=None))) & set(
        map(tuple, reused[KEY].itertuples(index=False, name=None))
    )


def test_wall_to_wall_completed_run_remains_hash_bound_and_auditable():
    out = ROOT / DEFAULT_DIR
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["logical_provider_payload_sha256"]) == 64
    assert manifest["paid_run_authorized"] is True
    assert manifest["network_call_made"] is True
    assert manifest["status"] == "incomplete"
    assert manifest["authorization"]["cost_ceiling_usd"] == 117.5
    assert manifest["run_summary"]["n_completed"] == 134_664
    assert manifest["run_summary"]["n_incomplete"] == 129
    assert manifest["run_summary"]["schema_gate_pass"] is True
    assert manifest["run_summary"]["provider_cost_usd"] == pytest.approx(63.27810359)
    assert manifest["reasoning_disabled"] is True
    assert manifest["allow_fallbacks"] is False
    for name, expected in manifest["artifact_sha256"].items():
        assert sha_file(out / name) == expected
    assert sha_file(out / "prompt.txt") == (
        "d8b64963f77bd796f8bfc7d778ca2437c6fb5c572c9af0f7398955adaf3eb8af"
    )
    assert sha_file(out / "response_schema.json") == (
        "51ff1ebb6cf77fa05202b7391f0d0e2ba01e0c39caeafc2a10feaeea747d9c16"
    )


def test_wall_to_wall_paid_paths_fail_closed_without_explicit_authorization():
    out = ROOT / DEFAULT_DIR
    with pytest.raises(RuntimeError, match="explicit authorization"):
        authorize_wall_to_wall_luna_v24(out, "not-authorized", 117.5, False)
    with pytest.raises(RuntimeError, match="authorize-paid-run"):
        run_wall_to_wall_luna_v24(ROOT, out, 1, 117.5, False)


def test_retry_policy_backs_off_rate_limits_but_not_permanent_errors(monkeypatch):
    monkeypatch.setattr("random.uniform", lambda low, high: 0.25)
    response = type("Response", (), {"headers": {"Retry-After": "7"}})()
    rate_limit = type(
        "RateLimitError", (Exception,), {"status_code": 429, "response": response}
    )("busy")
    policy = _retry_policy(rate_limit, 2)
    assert policy["transient"] is True
    assert policy["is_rate_limit"] is True
    assert policy["retry_delay_seconds"] == 7.0

    permanent = type(
        "BadRequestError", (Exception,), {"status_code": 400, "response": response}
    )("bad")
    policy = _retry_policy(permanent, 1)
    assert policy["transient"] is False
    assert policy["retry_delay_seconds"] is None
