"""Regression test for the final blinded v2.2 harmonization queue."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]


def test_four_case_harmonization_review_loads_form_or_completed_state() -> None:
    at = AppTest.from_file(
        str(ROOT / "interactive/pages/6_Final_harmonization_review.py"),
        default_timeout=10,
    ).run()
    at.text_input[0].set_value("harmonization-test-coder").run()
    assert not at.exception
    assert at.title[0].value == "Resolve the remaining four labels"
    assert at.text_input[0].value == "harmonization-test-coder"
    if at.selectbox:
        assert at.selectbox[0].value == ""
        assert all(widget.value is None for widget in at.radio)
        assert at.button[0].label == "Save annotation and continue"
    else:
        assert any(
            message.value == "All four remaining v2.2 labels are stored."
            for message in at.success
        )
