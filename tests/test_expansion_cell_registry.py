import json
from pathlib import Path

import pandas as pd

from refusal_audit.model_expansion.cell_viability_registry import (
    AUDIT_DIR, DEFAULT_DIR, EXPECTED_AUDIT_N,
    estimate_approved_expansion_cost, prepare_borderline_audit,
    prepare_cell_registry,
)


ROOT = Path(__file__).resolve().parents[1]


def test_registry_and_borderline_payload_are_complete_and_blinded():
    prepare_cell_registry(ROOT, ROOT / DEFAULT_DIR)
    prepare_borderline_audit(ROOT, ROOT / AUDIT_DIR)
    registry = pd.read_csv(ROOT / DEFAULT_DIR / "provisional_cell_registry.csv")
    assert len(registry) == 40
    assert registry.cell_decision.value_counts().to_dict() == {
        "approved": 33, "removed_model": 5, "pending_sol": 2,
    }
    pending = registry.loc[registry.cell_decision.eq("pending_sol")]
    assert set(zip(pending.subject_model, pending.prompt_language)) == {
        ("hunyuan-a13b", "en"), ("hunyuan-a13b", "ru")
    }
    requests = [
        json.loads(line)
        for line in (ROOT / AUDIT_DIR / "provider_requests.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(requests) == EXPECTED_AUDIT_N
    assert len({row["provider_request_id"] for row in requests}) == EXPECTED_AUDIT_N
    messages = json.dumps([row["messages"] for row in requests], ensure_ascii=False)
    assert "subject_model" not in messages
    assert "pred_capability_failure" not in messages


def test_final_registry_and_approved_cost_exclude_conditional_cells():
    final = pd.read_csv(ROOT / DEFAULT_DIR / "final_cell_registry.csv")
    assert final.cell_decision.value_counts().to_dict() == {
        "approved": 33, "removed_model": 5, "conditional": 2,
    }
    cost = estimate_approved_expansion_cost(ROOT, ROOT / DEFAULT_DIR)
    primary = cost["primary_approved_cells"]
    assert primary["n_cells"] == 33
    assert primary["n_requests"] == 33 * 2496
    assert cost["optional_conditional_cells"]["n_requests"] == 2 * 2496
