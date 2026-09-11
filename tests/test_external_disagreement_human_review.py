from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.external_disagreement_human_review import (  # noqa: E402
    summarize_external_disagreement_human_review,
)


def test_completed_visible_label_review_is_valid_and_reusable():
    result = summarize_external_disagreement_human_review(ROOT)
    repeated = summarize_external_disagreement_human_review(ROOT)
    assert repeated == result
    assert result["n_rows"] == 9
    assert result["n_decided"] == 8
    assert result["n_uncertain"] == 1
    assert result["final_genuine_refusal_n"] == 5
    assert result["final_nonrefusal_n"] == 3
    assert result["who_was_correct_n"] == {
        "sol": 6, "luna": 2, "uncertain": 1,
    }
    assert result["agreement_on_eight_decided"] == {
        "luna": 2, "sol": 6, "codex_forensic": 4,
    }
    assert result["reviewer_role"] == "user_primary_reviewer"
    assert result["source_log_overwritten"] is False
    assert result["provider_call_made"] is False
