"""Validate and cost explicit model rosters used outside the legacy panel.

The default subject-model panel remains in :mod:`config`. Expansion rosters are
separate JSON files so adding a candidate never silently changes an ordinary
generation command. This module performs only local file reads and arithmetic;
it never contacts a provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


REQUIRED_MODEL_FIELDS = {
    "name",
    "model_id",
    "canonical_slug",
    "developer",
    "developer_jurisdiction",
    "provider",
    "context_length",
    "temperature",
    "max_tokens",
    "input_usd_per_million",
    "output_usd_per_million",
    "selected_provider_name",
    "selected_provider_tag",
    "selected_quantization",
    "provider_routing",
    "reasoning",
}


def sha256_file(path: Path) -> str:
    """Return the SHA-256 of the exact roster bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_roster(path: str) -> Dict[str, Any]:
    """Load and strictly validate an opt-in roster JSON file.

    The returned dictionary adds ``_path`` and ``_sha256`` runtime fields.
    Those fields are not part of the file and are stamped into response records
    so a run can be tied to the exact roster bytes that configured it.
    """
    roster_path = Path(path).expanduser().resolve()
    with roster_path.open("r", encoding="utf-8") as handle:
        roster = json.load(handle)

    for field in (
        "schema_version",
        "roster_version",
        "status",
        "provider_calls_authorized",
        "pricing_verified_at",
        "pricing_source",
        "models",
    ):
        if field not in roster:
            raise ValueError(f"Roster is missing required top-level field {field!r}")

    if not isinstance(roster["models"], list) or not roster["models"]:
        raise ValueError("Roster 'models' must be a non-empty list")

    names: List[str] = []
    model_ids: List[str] = []
    for index, model in enumerate(roster["models"]):
        missing = sorted(REQUIRED_MODEL_FIELDS - set(model))
        if missing:
            raise ValueError(
                f"Roster model {index} is missing required fields: {', '.join(missing)}"
            )
        names.append(model["name"])
        model_ids.append(model["model_id"])
        if model["provider"] not in {"openrouter", "hf-router"}:
            raise ValueError(
                f"Expansion roster supports OpenRouter and the Hugging Face "
                f"router; got "
                f"{model['provider']!r} for {model['name']!r}"
            )
        if model["developer_jurisdiction"] not in {"CN", "US", "EU"}:
            raise ValueError(
                f"Unexpected jurisdiction for {model['name']!r}: "
                f"{model['developer_jurisdiction']!r}"
            )
        for price_field in ("input_usd_per_million", "output_usd_per_million"):
            if float(model[price_field]) < 0:
                raise ValueError(f"{price_field} must be non-negative")
        if int(model["max_tokens"]) <= 0:
            raise ValueError("max_tokens must be positive")
        routing = model["provider_routing"]
        if routing.get("allow_fallbacks") is not False:
            raise ValueError(
                f"{model['name']!r} must set provider_routing.allow_fallbacks=false"
            )
        if model["provider"] == "openrouter":
            if routing.get("only") != [model["selected_provider_tag"]]:
                raise ValueError(
                    f"{model['name']!r} must restrict provider_routing.only to its "
                    "single selected_provider_tag"
                )
        elif routing.get("model_suffix") != f":{model['selected_provider_tag']}":
            raise ValueError(
                f"{model['name']!r} must pin its Hugging Face provider through "
                "the model suffix"
            )

    if len(names) != len(set(names)):
        raise ValueError("Roster display names are not unique")
    if len(model_ids) != len(set(model_ids)):
        raise ValueError("Roster model IDs are not unique")

    roster["_path"] = str(roster_path)
    roster["_sha256"] = sha256_file(roster_path)
    return roster


def select_models(
    roster: Dict[str, Any],
    only_models: Optional[Iterable[str]] = None,
    exclude_models: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """Apply display-name filters and reject misspelled model names."""
    models = list(roster["models"])
    known = {model["name"] for model in models}
    only = set(only_models or [])
    exclude = set(exclude_models or [])
    unknown = (only | exclude) - known
    if unknown:
        raise ValueError("Unknown roster model(s): " + ", ".join(sorted(unknown)))
    if only:
        models = [model for model in models if model["name"] in only]
    if exclude:
        models = [model for model in models if model["name"] not in exclude]
    if not models:
        raise ValueError("No models remain after roster filtering")
    return models


def estimate_cost(
    models: Iterable[Dict[str, Any]],
    responses_per_model: int,
    input_tokens_per_response: int,
    output_tokens_per_response: int,
) -> Dict[str, Any]:
    """Estimate provider charges from a transparent token-use scenario."""
    rows = []
    total = 0.0
    for model in models:
        cost = responses_per_model * (
            input_tokens_per_response * float(model["input_usd_per_million"])
            + output_tokens_per_response * float(model["output_usd_per_million"])
        ) / 1_000_000
        rows.append(
            {
                "name": model["name"],
                "model_id": model["model_id"],
                "responses": responses_per_model,
                "estimated_usd": round(cost, 6),
            }
        )
        total += cost
    return {
        "input_tokens_per_response": input_tokens_per_response,
        "output_tokens_per_response": output_tokens_per_response,
        "models": rows,
        "total_estimated_usd": round(total, 6),
    }


def request_extra_body(model: Dict[str, Any]) -> Dict[str, Any]:
    """Build the OpenRouter-only controls for one subject model."""
    if model["provider"] != "openrouter":
        raise ValueError("request_extra_body is defined only for OpenRouter models")
    body: Dict[str, Any] = {"provider": dict(model["provider_routing"])}
    if model.get("reasoning") is not None:
        body["reasoning"] = dict(model["reasoning"])
    return body


def _print_cost(estimate: Dict[str, Any]) -> None:
    print(
        "Assumption: "
        f"{estimate['input_tokens_per_response']} input + "
        f"{estimate['output_tokens_per_response']} output tokens per response"
    )
    for row in estimate["models"]:
        print(f"  {row['name']:<30} ${row['estimated_usd']:>9.4f}")
    print(f"  {'TOTAL':<30} ${estimate['total_estimated_usd']:>9.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roster", help="Path to a roster JSON file")
    parser.add_argument("--responses-per-model", type=int, default=12_480)
    parser.add_argument("--input-tokens", type=int, default=100)
    parser.add_argument("--output-tokens", type=int, default=1_500)
    args = parser.parse_args()

    roster = load_roster(args.roster)
    estimate = estimate_cost(
        roster["models"],
        responses_per_model=args.responses_per_model,
        input_tokens_per_response=args.input_tokens,
        output_tokens_per_response=args.output_tokens,
    )
    print(f"Roster: {roster['roster_version']}")
    print(f"SHA-256: {roster['_sha256']}")
    print(f"Status: {roster['status']}")
    print(f"Provider calls authorized: {roster['provider_calls_authorized']}")
    _print_cost(estimate)


if __name__ == "__main__":
    main()
