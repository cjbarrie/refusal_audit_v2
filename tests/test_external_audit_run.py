from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.external_audit_freeze import (  # noqa: E402
    freeze_external_audit,
)
from refusal_audit.response_validity.external_audit_run import (  # noqa: E402
    EXPECTED_CEILING,
    EXPECTED_HASHES,
    authorize_external_audit,
    run_external_audit,
)


@pytest.fixture()
def authorized(tmp_path):
    freeze_external_audit(ROOT, tmp_path)
    authorization = authorize_external_audit(
        tmp_path, EXPECTED_HASHES["luna"], EXPECTED_HASHES["sol"],
        EXPECTED_CEILING, True,
    )
    return tmp_path, authorization


def test_external_authorization_is_bound_to_both_payloads(authorized):
    output, authorization = authorized
    assert authorization["provider_payload_sha256"] == EXPECTED_HASHES
    assert authorization["cumulative_cost_ceiling_usd"] == 16
    assert authorization["allow_fallbacks"] is False
    assert authorization["reasoning_disabled"] is True
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["paid_run_authorized"] is True
    assert manifest["network_call_made"] is False


def test_external_authorization_rejects_hash_or_ceiling(tmp_path):
    freeze_external_audit(ROOT, tmp_path)
    with pytest.raises(ValueError):
        authorize_external_audit(
            tmp_path, "0" * 64, EXPECTED_HASHES["sol"], 16, True
        )
    with pytest.raises(ValueError):
        authorize_external_audit(
            tmp_path, EXPECTED_HASHES["luna"], EXPECTED_HASHES["sol"], 15,
            True,
        )


def test_external_run_fails_closed_without_execution_flag(authorized):
    output, _ = authorized
    with pytest.raises(RuntimeError, match="authorize-paid-run"):
        run_external_audit(ROOT, output, 1, 16, False)
