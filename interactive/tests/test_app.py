"""Smoke tests for the current read-only refusal explorer."""

from pathlib import Path

import pytest


def test_app_loads_promoted_v24_assets():
    root = Path(__file__).resolve().parents[2]
    assets = root / "interactive" / "data"
    if not (assets / "responses.parquet").exists():
        pytest.skip("derived app assets not built")
    import pandas as pd

    columns = pd.read_parquet(assets / "responses.parquet").columns
    if "genuine_refusal" not in columns:
        pytest.skip("app assets predate the v2.4 rebuild")

    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(root / "interactive" / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert not app.tabs
    assert app.header[0].value == "Refusal explorer"
    assert app.sidebar.header[0].value == "Filter genuine refusals"
