"""Multipage regression tests for Sol-prefilled human review."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[2]


def test_sol_coder_opens_prefilled_review_or_completed_state() -> None:
    at = AppTest.from_file(str(ROOT / "interactive" / "app.py"), default_timeout=10).run()
    at.switch_page("pages/4_Decomposed_response_review.py").run()
    at.text_input[0].set_value("Sol").run()
    assert not at.exception
    assert at.title[0].value == "Review GPT-5.6 Sol annotations"
    assert at.text_input[0].value == "Sol"
    if at.selectbox:
        assert at.selectbox[0].value is not None
        assert all(widget.value is not None for widget in at.radio)
        assert at.button[0].label == "Save reviewed annotation and continue"
    else:
        assert any(
            message.value
            in {
                "All 158 boundary-review responses are stored.",
                "All 158 Sol annotations have been human-reviewed and stored.",
            }
            for message in at.success
        )
