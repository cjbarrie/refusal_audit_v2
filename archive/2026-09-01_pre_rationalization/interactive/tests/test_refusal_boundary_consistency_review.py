"""Regression test for the 20-case refusal-boundary review page."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]


def test_boundary_review_page_loads_frozen_queue_and_direct_decision_form() -> None:
    at = AppTest.from_file(
        str(ROOT / "interactive/pages/10_Refusal_boundary_consistency_review.py"),
        default_timeout=10,
    ).run()
    at.text_input[0].set_value("boundary-app-test-coder").run()
    assert not at.exception
    assert at.title[0].value == "Is this a genuine refusal?"
    assert at.radio[0].label == "Final genuine-refusal judgment"
    assert at.radio[0].value is None
    assert at.selectbox[0].label == "Main reason for that judgment"
    assert at.radio[1].label == "Confidence"
    assert at.button[0].label == "Save decision and continue"
    displayed = at.dataframe[0].value
    assert set(displayed["Annotator"]) == {"Luna", "Sol"}
