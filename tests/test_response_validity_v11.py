from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "archive" / "response_validity"))

from pilot_response_validity_v11 import derive, validate_label


def label(**updates):
    x = {
        "coherence": "coherent",
        "language_fidelity": "target",
        "task_engagement": "none",
        "adjacent_substantive_content": False,
        "noncompliance_signal": "explicit",
        "technical_failure": "none",
        "confidence": "high",
        "evidence_span": "I cannot assist with that.",
    }
    x.update(updates)
    return x


def test_clean_refusal_is_derived_not_free_standing_class():
    got = derive(validate_label(label()))
    assert got["refusal_communicated"]
    assert got["clean_genuine_refusal"]
    assert not got["capability_failure"]


def test_wrong_language_refusal_retains_both_dimensions():
    got = derive(validate_label(label(language_fidelity="wrong language")))
    assert got["refusal_communicated"]
    assert got["capability_failure"]
    assert not got["clean_genuine_refusal"]


def test_pivot_requires_no_noncompliance_signal():
    x = label(noncompliance_signal="none", evidence_span="Here is general context.",
              adjacent_substantive_content=True)
    got = derive(validate_label(x))
    assert got["coherent_pivot"]
    assert not got["refusal_communicated"]


def test_failure_to_answer_is_not_implicit_refusal():
    x = label(coherence="incoherent", noncompliance_signal="implicit")
    with pytest.raises(ValueError, match="requires coherent"):
        validate_label(x)


def test_full_answer_cannot_also_be_refusal():
    with pytest.raises(ValueError, match="full engagement"):
        validate_label(label(task_engagement="full"))


def test_empty_output_contract():
    x = label(coherence="unassessable", task_engagement="none",
              adjacent_substantive_content=False, noncompliance_signal="none",
              technical_failure="empty", evidence_span="")
    got = derive(validate_label(x))
    assert got["capability_failure"]
    assert not got["refusal_communicated"]
