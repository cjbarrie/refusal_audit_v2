import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.translation_runner import (  # noqa: E402
    MODEL,
    _text_chunks,
    _usage_cost,
    record_chunked_fallback_authorization,
    run_translations,
    validate_translation,
)


def test_translation_schema_validation_uses_frozen_metadata():
    request = {"review_id": "r", "source_hash": "s"}
    label = {
        "review_id": "r", "source_hash": "s",
        "response_translation_en": "Literal text", "translation_status": "complete",
        "uncertain_spans": [], "detected_language": "Russian",
        "translator_model": MODEL, "translation_prompt_hash": "p",
    }
    assert validate_translation(label, request, "p") == label
    label["translation_prompt_hash"] = "wrong"
    with pytest.raises(ValueError, match="translation_prompt_hash"):
        validate_translation(label, request, "p")


def test_paid_translation_requires_both_authorization_gates(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    with pytest.raises(RuntimeError, match="requires --authorize-paid-translation"):
        run_translations(ROOT, tmp_path, tmp_path / "prompt", 1, 3.0, False)


def test_byok_upstream_cost_is_not_mistaken_for_zero_spend():
    usage = {
        "cost": 0,
        "is_byok": True,
        "cost_details": {"upstream_inference_cost": 0.0123},
    }
    assert _usage_cost(usage) == pytest.approx(0.0123)


def test_chunking_is_lossless_and_bounded_near_target():
    source = ("alpha beta\n" * 800) + "tail"
    chunks = _text_chunks(source, target_chars=3000)
    assert "".join(chunks) == source
    assert len(chunks) > 1
    assert max(map(len, chunks)) <= 3000


def test_chunk_authorization_requires_explicit_confirmation(tmp_path):
    with pytest.raises(RuntimeError, match="confirm-user-authorization"):
        record_chunked_fallback_authorization(tmp_path, ["r"], 3.0, False)
