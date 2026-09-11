import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_responses import load_existing_responses
from annotation_pipeline import load_existing_annotations


def write_rows(path, rows):
    path.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")


def test_response_error_does_not_erase_last_valid(tmp_path):
    p = tmp_path / "responses.jsonl"
    key = {"prompt_id": "p", "prompt_language": "ar", "model": "m"}
    write_rows(p, [{**key, "response_text": "valid"}, {**key, "error": "retry"}])
    assert load_existing_responses(str(p))[("p", "ar", "m")]["response_text"] == "valid"


def test_annotation_error_does_not_erase_last_valid(tmp_path):
    p = tmp_path / "ann.jsonl"
    key = {"prompt_id": "p", "prompt_language": "ar", "model": "m"}
    write_rows(p, [{**key, "engagement_code": 5}, {**key, "error": "retry"}])
    assert load_existing_annotations(str(p))[("p", "ar", "m")]["engagement_code"] == 5
