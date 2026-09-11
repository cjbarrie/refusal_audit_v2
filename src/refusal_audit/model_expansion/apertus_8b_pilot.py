"""Freeze and guard the Apertus v1.5 8B pilot after a successful access smoke test.

This module deliberately derives the new payload from the already frozen 70B
pilot. That preserves the exact 40 prompt meanings and five language texts while
giving the 8B route new request identifiers, a new manifest, and a new paid-run
authorization boundary. The failed 70B artifacts are never edited.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from .apertus_pilot import run_apertus_pilot
from .openrouter_pilot import read_jsonl, sha_file, sha_object, write_jsonl


DEFAULT_DIR = Path("annotations/model_expansion_v2/apertus_8b_pilot_v2")
SOURCE_DIR = Path("annotations/model_expansion_v2/apertus_replacement_pilot_v1")
SMOKE_PATH = Path(
    "annotations/model_expansion_v2/apertus_8b_access_smoke_v1/metadata.json"
)
SOURCE_PAYLOAD_SHA256 = (
    "dd52cafb9ec771f04e1f8a93ce48f52e4ae0320719fd6e72f6e928f0b0f46e0a"
)
MODEL_NAME = "apertus-v1.5-8b"
MODEL_ID = "swiss-ai/Apertus-v1.5-8B:publicai"
CANONICAL_SLUG = "swiss-ai/Apertus-v1.5-8B"
EXPECTED_N = 200
PLANNING_OUTPUT_TOKENS = 1_500
INPUT_USD_PER_MILLION = 0.10
OUTPUT_USD_PER_MILLION = 0.20


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def prepare_apertus_8b_pilot(root: Path, output_dir: Path | None = None) -> dict:
    """Freeze the 200-request 8B payload locally; make no provider call."""
    output_dir = output_dir or root / DEFAULT_DIR
    source_dir = root / SOURCE_DIR
    source_payload = source_dir / "provider_requests.jsonl"
    source_index = source_dir / "pilot_prompt_index.csv"
    smoke_path = root / SMOKE_PATH
    if sha_file(source_payload) != SOURCE_PAYLOAD_SHA256:
        raise ValueError("historical 70B pilot payload failed its hash check")
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    if not (
        smoke.get("result", {}).get("http_status") == 200
        and smoke.get("model_requested") == MODEL_ID
        and smoke.get("result", {}).get("reasoning_returned") is False
    ):
        raise ValueError("Apertus 8B access smoke test is absent or unsuccessful")

    inputs = {
        "source_70b_payload": SOURCE_PAYLOAD_SHA256,
        "source_pilot_index": sha_file(source_index),
        "access_smoke": sha_file(smoke_path),
    }
    manifest_path = output_dir / "manifest.json"
    artifacts = {
        "pilot_prompt_index.csv": output_dir / "pilot_prompt_index.csv",
        "provider_requests.jsonl": output_dir / "provider_requests.jsonl",
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != inputs:
            raise ValueError("frozen Apertus 8B pilot no longer matches its inputs")
        for name, expected in manifest["artifact_sha256"].items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != expected:
                raise ValueError(f"frozen Apertus 8B artifact changed: {name}")
        return manifest

    source_rows = read_jsonl(source_payload)
    if len(source_rows) != EXPECTED_N:
        raise ValueError(f"expected {EXPECTED_N} historical pilot rows")
    requests = []
    for old in source_rows:
        logical = {
            "pilot_version": "apertus-v1.5-8b-pilot-v2",
            "prompt_id": old["prompt_id"],
            "prompt_language": old["prompt_language"],
            "model": MODEL_NAME,
        }
        row = dict(old)
        row.update({
            **logical,
            "provider_request_id": sha_object(logical)[:24],
            "model_id": MODEL_ID,
            "canonical_slug": CANONICAL_SLUG,
            "input_usd_per_million": INPUT_USD_PER_MILLION,
            "output_usd_per_million": OUTPUT_USD_PER_MILLION,
            "access_smoke_version": smoke["version"],
        })
        requests.append(row)
    if len({row["provider_request_id"] for row in requests}) != EXPECTED_N:
        raise ValueError("Apertus 8B request IDs are not unique")
    if {row["prompt_language"] for row in requests} != {"en", "zh", "ar", "ru", "hi"}:
        raise ValueError("Apertus 8B pilot does not contain all five languages")

    output_dir.mkdir(parents=True, exist_ok=False)
    # Byte-copy the selection table; its hash is part of the frozen inputs.
    artifacts["pilot_prompt_index.csv"].write_bytes(source_index.read_bytes())
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    manifest = {
        "version": "apertus-v1.5-8b-pilot-v2",
        "created_at": _now(),
        "status": "frozen_unpriced",
        "scientific_role": (
            "route and behavioral pilot on the same enriched 40-prompt, "
            "five-language frame as expansion pilot v1; not prevalence"
        ),
        "historical_70b_pilot_unchanged": True,
        "model": MODEL_NAME,
        "model_id": MODEL_ID,
        "provider": "Hugging Face Inference Providers",
        "provider_tag": "publicai",
        "provider_fallbacks_disabled_by_exact_suffix": True,
        "thinking_mode": "off_by_model_default",
        "languages": ["en", "zh", "ar", "ru", "hi"],
        "n_prompt_meanings": 40,
        "n_requests": EXPECTED_N,
        "max_attempts": 2,
        "generation_contract": {
            "messages": "one canonical target-language user message; no system message",
            "temperature": 1.0,
            "max_tokens": 5000,
            "provider_fallbacks": False,
            "thinking_mode": "off",
        },
        "price_usd_per_million": {
            "input": INPUT_USD_PER_MILLION,
            "output": OUTPUT_USD_PER_MILLION,
        },
        "pricing_source": "Public AI published model pricing via HF route",
        "pricing_verified_at": "2026-09-03",
        "input_sha256": inputs,
        "artifact_sha256": {
            name: sha_file(path) for name, path in artifacts.items()
        },
        "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_apertus_8b_cost(root: Path, output_dir: Path | None = None) -> dict:
    """Calculate planning and worst-case reservations without calling a provider."""
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare_apertus_8b_pilot(root, output_dir)
    requests = read_jsonl(output_dir / "provider_requests.jsonl")
    planning = sum(
        (row["estimated_input_tokens"] * INPUT_USD_PER_MILLION
         + PLANNING_OUTPUT_TOKENS * OUTPUT_USD_PER_MILLION) / 1_000_000
        for row in requests
    )
    reserved = sum(
        (row["estimated_input_tokens"] * INPUT_USD_PER_MILLION
         + row["max_output_tokens"] * OUTPUT_USD_PER_MILLION) / 1_000_000
        for row in requests
    )
    # Two attempts are possible. Round the ceiling upward to the next $0.10.
    ceiling = math.ceil(max(planning * 1.5, reserved * 2.0 * 1.1) * 10) / 10
    result = {
        "version": "apertus-v1.5-8b-pilot-cost-v2",
        "created_at": _now(),
        "pricing_verified_at": "2026-09-03",
        "pricing_source": "Public AI published model pricing via HF route",
        "price_usd_per_million": {
            "input": INPUT_USD_PER_MILLION,
            "output": OUTPUT_USD_PER_MILLION,
        },
        "requests": len(requests),
        "estimated_input_tokens": sum(r["estimated_input_tokens"] for r in requests),
        "planning_output_tokens": len(requests) * PLANNING_OUTPUT_TOKENS,
        "planning_cost_usd": planning,
        "single_attempt_reserved_cost_usd": reserved,
        "two_attempt_reserved_cost_usd": reserved * 2,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    (output_dir / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    latest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    latest["status"] = "frozen_unpaid"
    latest["cost_estimate"] = result
    (output_dir / "manifest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )
    return result


def authorize_apertus_8b_pilot(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
) -> dict:
    """Record explicit authorization only when hash and ceiling match exactly."""
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cost = json.loads((output_dir / "cost_estimate.json").read_text(encoding="utf-8"))
    observed = sha_file(output_dir / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized Apertus 8B payload hash does not match frozen bytes")
    if float(ceiling) != float(cost["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized Apertus 8B ceiling does not match frozen estimate")
    authorization = {
        "recorded_at": _now(),
        "user_authorized": True,
        "authorization_scope": "apertus_v1.5_8b_pilot_v2",
        "provider_payload_sha256": payload_sha,
        "model_id": MODEL_ID,
        "provider_tag": "publicai",
        "n_requests": EXPECTED_N,
        "thinking_mode": "off_by_model_default",
        "provider_fallbacks_disabled_by_exact_suffix": True,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def run_apertus_8b_pilot(
    root: Path, output_dir: Path, workers: int, ceiling: float, authorized: bool
) -> dict:
    """Use the tested generic HF/Public AI runner on the frozen 8B payload."""
    return run_apertus_pilot(root, output_dir, workers, ceiling, authorized)
