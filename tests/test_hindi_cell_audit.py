import json
from pathlib import Path

import pandas as pd

from refusal_audit.model_expansion.hindi_cell_audit import (
    DEFAULT_DIR,
    EXPECTED_N,
    MODEL,
    prepare_hindi_cell_audit,
)


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_hindi_audit_is_complete_and_blinded():
    manifest = prepare_hindi_cell_audit(ROOT, ROOT / DEFAULT_DIR)
    requests = [
        json.loads(line)
        for line in (ROOT / DEFAULT_DIR / "provider_requests.jsonl")
        .read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    index = pd.read_parquet(ROOT / DEFAULT_DIR / "audit_index.parquet")
    assert len(requests) == EXPECTED_N == len(index)
    assert index.prompt_language.eq("hi").all()
    assert index.groupby("subject_model").size().eq(40).all()
    assert {row["model_id"] for row in requests} == {MODEL}
    assert all(row["provider"] == {"only": ["openai"], "allow_fallbacks": False}
               for row in requests)
    messages = json.dumps([row["messages"] for row in requests], ensure_ascii=False)
    for forbidden in ("subject_model", "pilot_band", "pred_capability_failure"):
        assert forbidden not in messages
    assert manifest["selection"]["rule"].startswith("all prompt_language")
