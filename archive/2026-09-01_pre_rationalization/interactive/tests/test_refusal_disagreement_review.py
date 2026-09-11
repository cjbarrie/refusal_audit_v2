"""Regression test for the visible-label nine-case refusal review."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]


def test_refusal_disagreement_page_loads_original_labels_and_form() -> None:
    at = AppTest.from_file(
        str(ROOT / "interactive/pages/9_Refusal_disagreement_review.py"),
        default_timeout=10,
    ).run()
    at.text_input[0].set_value("disagreement-review-test-coder").run()
    assert not at.exception
    assert at.title[0].value == "Who was correct on the nine refusal disagreements?"
    if at.radio:
        assert at.radio[0].label == "Who was correct about genuine refusal?"
        assert at.radio[0].value is None
        assert at.radio[1].label == "Confidence"
        assert at.button[0].label == "Save decision and continue"
        assert len(at.dataframe) == 1
        displayed = at.dataframe[0].value
        assert set(displayed["Annotator"]) == {"Luna", "Sol"}
    else:
        assert any(
            message.value == "All nine disagreement decisions are safely stored."
            for message in at.success
        )
