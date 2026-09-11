from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.model_bakeoff_v2 import (  # noqa: E402
    CANDIDATES,
    N_PREFLIGHT,
    _build_preflight_cases,
)


def test_candidate_registry_is_api_only_unique_and_current():
    assert len(CANDIDATES) == 8
    assert len({row["candidate_id"] for row in CANDIDATES}) == 8
    assert len({(row["model_id"], row["provider_tag"]) for row in CANDIDATES}) == 8
    model_ids = {row["model_id"] for row in CANDIDATES}
    assert "moonshotai/kimi-k3" in model_ids
    assert "qwen/qwen3.8-2.4t-a95b" in model_ids
    assert "z-ai/glm-5.3" in model_ids
    assert "deepseek/deepseek-v4-pro-0813" in model_ids
    assert not any("eurollm" in value.lower() for value in model_ids)
    assert not any("apertus" in value.lower() for value in model_ids)
    assert all(row["provider_tag"] for row in CANDIDATES)
    assert all(row["input_price"] > 0 for row in CANDIDATES)
    assert all(row["output_price"] > 0 for row in CANDIDATES)


def test_preflight_is_frozen_balanced_and_nonoverlapping():
    frame = _build_preflight_cases(ROOT)
    assert len(frame) == N_PREFLIGHT == 50
    assert not frame.audit_response_id.duplicated().any()
    assert frame.preflight_reason.value_counts().to_dict() == {
        "luna_sol_refusal_disagreement": 15,
        "ordinary_agreement_control": 15,
        "capability_failure_diagnostic": 10,
        "v2_4_boundary_diagnostic": 10,
    }
    ordinary = frame.loc[
        frame.preflight_reason.eq("ordinary_agreement_control")
    ]
    capability = frame.loc[
        frame.preflight_reason.eq("capability_failure_diagnostic")
    ]
    assert ordinary.prompt_language.value_counts().to_dict() == {
        "ar": 3, "en": 3, "hi": 3, "ru": 3, "zh": 3,
    }
    assert capability.prompt_language.value_counts().to_dict() == {
        "ar": 2, "en": 2, "hi": 2, "ru": 2, "zh": 2,
    }
