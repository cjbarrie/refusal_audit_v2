from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_data import MODEL_JURISDICTION, last_clean_jsonl


def test_last_clean_error_does_not_erase_valid(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text(
        '{"prompt_id":"p","prompt_language":"en","model":"m","response_text":"ok"}\n'
        '{"prompt_id":"p","prompt_language":"en","model":"m","error":"retry failed"}\n',
        encoding="utf-8",
    )
    got = last_clean_jsonl([p], "response")
    assert got[("p", "en", "m")]["response_text"] == "ok"


def test_current_model_roster_has_18_complete_jurisdiction_mappings():
    assert len(MODEL_JURISDICTION) == 18
    assert set(MODEL_JURISDICTION.values()) == {"CN", "MENA", "India", "US", "EU"}


def test_built_umap_assets_include_hover_text():
    path = Path(__file__).resolve().parents[1] / "data" / "umap_points.parquet"
    if not path.exists():
        return
    import pandas as pd

    points = pd.read_parquet(path, columns=["prompt_id", "prompt_text"])
    assert len(points) == 2496
    assert points["prompt_id"].is_unique
    assert points["prompt_text"].notna().all()
