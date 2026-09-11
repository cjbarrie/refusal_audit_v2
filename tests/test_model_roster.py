from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_responses import generate_response
from model_roster import estimate_cost, load_roster, request_extra_body, select_models


ROSTER_PATH = ROOT / "config" / "model_rosters" / "openrouter_expansion_v1.json"


def test_expansion_roster_is_opt_in_and_complete():
    roster = load_roster(str(ROSTER_PATH))
    assert roster["provider_calls_authorized"] is False
    assert len(roster["models"]) == 8
    assert {m["developer_jurisdiction"] for m in roster["models"]} == {
        "CN", "US", "EU"
    }
    assert len(roster["_sha256"]) == 64


def test_full_matrix_planning_cost_is_reproducible():
    roster = load_roster(str(ROSTER_PATH))
    estimate = estimate_cost(roster["models"], 12_480, 100, 1_500)
    assert estimate["total_estimated_usd"] == 86.84208
    by_name = {row["name"]: row["estimated_usd"] for row in estimate["models"]}
    assert by_name["kimi-k2.5"] == 42.6816
    assert by_name["mistral-small-3.2"] == 3.8376


def test_unknown_model_filter_fails_instead_of_silently_selecting_none():
    roster = load_roster(str(ROSTER_PATH))
    try:
        select_models(roster, only_models=["misspelled-model"])
    except ValueError as exc:
        assert "Unknown roster model" in str(exc)
    else:
        raise AssertionError("unknown model filter should have failed")


def test_reasoning_control_is_only_sent_to_models_that_support_it():
    roster = load_roster(str(ROSTER_PATH))
    models = {model["name"]: model for model in roster["models"]}
    assert request_extra_body(models["glm-4.7-flash"])["reasoning"] == {
        "enabled": False, "exclude": True
    }
    assert "reasoning" not in request_extra_body(models["llama-4-scout"])


def test_generate_response_forwards_controls_and_returns_usage():
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            message = SimpleNamespace(
                content="answer", reasoning_content=None, reasoning=None
            )
            usage = SimpleNamespace(
                prompt_tokens=10, completion_tokens=20, total_tokens=30, cost=0.001
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=message)],
                model="canonical/model", provider="fixed-provider", usage=usage
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    extra = {
        "provider": {"only": ["deepinfra/bf16"], "allow_fallbacks": False},
        "reasoning": {"enabled": False, "exclude": True},
    }
    text, reasoning, metadata = generate_response(
        client=client,
        model_id="requested/model",
        prompt_text="test",
        extra_body=extra,
    )
    assert text == "answer"
    assert reasoning is None
    assert captured["extra_body"] == extra
    assert metadata == {
        "resolved_model_id": "canonical/model",
        "resolved_provider": "fixed-provider",
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
        "provider_cost_usd": 0.001,
    }
