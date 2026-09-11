#!/usr/bin/env python3
"""Freeze, cost, authorize, and run the v1 jurisdiction-expansion smoke test.

This is an access and response-integrity check, not an analysis sample. Phase 1
uses one already-frozen prompt meaning in all five study languages for T-Tech
T-pro-it-2.0 and SpeakLeash Bielik 11B v3. Provider calls are impossible until
the exact frozen payload hash and cost ceiling have been explicitly authorized.

Technical record: docs/JURISDICTION_MODEL_EXPANSION_V1.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from env_utils import load_env_from_file


OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/jurisdiction_smoke_v1/hf_phase"
ROSTER_PATH = ROOT / "config/model_rosters/jurisdiction_expansion_smoke_v1.json"
SOURCE_SELECTION = (
    ROOT / "annotations/model_expansion_v1/openrouter_pilot_v1/pilot_prompt_index.csv"
)
LANGUAGES = ("en", "zh", "ar", "ru", "hi")
MAX_REQUESTS = 10
HF_BASE_URL = "https://router.huggingface.co/v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha_object(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def token_count(text: str) -> int:
    """Use the same fixed planning tokenizer convention as expansion v1."""
    try:
        import tiktoken

        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except Exception:
        return max(1, math.ceil(len(text.encode("utf-8")) / 4))


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_roster() -> dict[str, Any]:
    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    if roster.get("provider_calls_authorized") is not False:
        raise ValueError("base roster must remain setup-only")
    hf_models = [row for row in roster["models"] if row["phase"] == "hf_phase"]
    if len(hf_models) != 2:
        raise ValueError("HF smoke phase must contain exactly two models")
    for model in hf_models:
        if model["provider"] != "hf-router":
            raise ValueError("HF phase contains a non-HF provider")
        expected_suffix = f":{model['provider_tag']}"
        if not model["model_id"].endswith(expected_suffix):
            raise ValueError(f"model is not pinned to {expected_suffix}")
    return roster


def load_selected_prompt_id() -> str:
    with SOURCE_SELECTION.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 40 or len({row["prompt_id"] for row in rows}) != 40:
        raise ValueError("source pilot index is not the frozen 40-prompt selection")
    # Lexical selection makes the one-meaning smoke frame deterministic.
    return min(row["prompt_id"] for row in rows)


def load_prompts(roster: dict[str, Any], prompt_id: str) -> dict[str, dict[str, Any]]:
    prompts: dict[str, dict[str, Any]] = {}
    for language in LANGUAGES:
        specification = roster["design"]["prompt_files"][language]
        path = ROOT / specification["path"]
        if sha_file(path) != specification["sha256"]:
            raise ValueError(f"frozen prompt hash mismatch for {language}")
        rows = json.loads(path.read_text(encoding="utf-8"))["prompts"]
        matches = [row for row in rows if row["id"] == prompt_id]
        if len(matches) != 1:
            raise ValueError(f"expected one {language} prompt for {prompt_id}")
        prompts[language] = matches[0]
    return prompts


def prepare() -> dict[str, Any]:
    roster = load_roster()
    prompt_id = load_selected_prompt_id()
    prompts = load_prompts(roster, prompt_id)
    input_hashes = {
        "roster": sha_file(ROSTER_PATH),
        "source_selection": sha_file(SOURCE_SELECTION),
        **{
            f"prompt_{language}": roster["design"]["prompt_files"][language]["sha256"]
            for language in LANGUAGES
        },
    }
    requests_path = OUTPUT_DIR / "provider_requests.jsonl"
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("existing frozen smoke frame no longer matches its inputs")
        if sha_file(requests_path) != manifest["provider_payload_sha256"]:
            raise ValueError("existing frozen provider payload changed")
        return manifest

    provider_requests: list[dict[str, Any]] = []
    for model in roster["models"]:
        if model["phase"] != "hf_phase":
            continue
        for language in LANGUAGES:
            prompt = prompts[language]
            logical_key = {
                "version": "jurisdiction-expansion-smoke-v1",
                "model": model["name"],
                "prompt_id": prompt_id,
                "prompt_language": language,
            }
            provider_requests.append(
                {
                    **logical_key,
                    "provider_request_id": sha_object(logical_key)[:24],
                    "provider": "Hugging Face Inference Providers",
                    "provider_tag": model["provider_tag"],
                    "model_id": model["model_id"],
                    "messages": [{"role": "user", "content": prompt["text"]}],
                    "temperature": model["temperature"],
                    "max_tokens": model["max_tokens"],
                    "estimated_input_tokens": token_count(prompt["text"]),
                    "input_usd_per_million": model["input_usd_per_million"],
                    "output_usd_per_million": model["output_usd_per_million"],
                    "reasoning_disabled": model["reasoning_disabled"],
                    "prompt_metadata": {
                        key: prompt.get(key)
                        for key in (
                            "issue_id",
                            "qid",
                            "topic_domain",
                            "controversy_tier",
                            "region_focus",
                            "position_side",
                            "route",
                            "battery",
                        )
                    },
                }
            )
    if len(provider_requests) != MAX_REQUESTS:
        raise ValueError(f"expected {MAX_REQUESTS} HF requests")
    if len({row["provider_request_id"] for row in provider_requests}) != MAX_REQUESTS:
        raise ValueError("provider request IDs are not unique")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(requests_path, provider_requests)
    manifest = {
        "version": "jurisdiction-expansion-smoke-v1",
        "created_at": now(),
        "status": "frozen_unpaid",
        "scientific_role": "route and response-integrity check; not an analysis sample",
        "prompt_id": prompt_id,
        "languages": list(LANGUAGES),
        "models": [row["name"] for row in roster["models"] if row["phase"] == "hf_phase"],
        "n_requests": MAX_REQUESTS,
        "max_attempts_per_request": 1,
        "provider_fallbacks_disabled": True,
        "input_sha256": input_hashes,
        "provider_payload_sha256": sha_file(requests_path),
        "paid_run_authorized": False,
        "network_inference_call_made": False,
        "krutrim_phase": {
            "status": "blocked_on_api_key_and_exact_console_model_id",
            "required_env": ["KRUTRIM_API_KEY", "KRUTRIM_MODEL_ID"],
        },
    }
    atomic_json(manifest_path, manifest)
    return manifest


def estimate_cost() -> dict[str, Any]:
    manifest = prepare()
    request_rows = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    planning = sum(
        (
            row["estimated_input_tokens"] * row["input_usd_per_million"]
            + 500 * row["output_usd_per_million"]
        )
        / 1_000_000
        for row in request_rows
    )
    reserved = sum(
        (
            row["estimated_input_tokens"] * row["input_usd_per_million"]
            + row["max_tokens"] * row["output_usd_per_million"]
        )
        / 1_000_000
        for row in request_rows
    )
    result = {
        "version": "jurisdiction-expansion-smoke-cost-v1",
        "created_at": now(),
        "n_requests": len(request_rows),
        "planning_output_tokens_per_request": 500,
        "planning_cost_usd": round(planning, 6),
        "single_attempt_max_token_reserve_usd": round(reserved, 6),
        "hard_ceiling_usd": 0.10,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "pricing_sources": {
            "t-pro-it-2.0": "Featherless public model-detail API, checked 2026-09-07",
            "bielik-11b-v3.0": "Hugging Face Inference Providers catalogue, checked 2026-09-07",
        },
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    atomic_json(OUTPUT_DIR / "cost_estimate.json", result)
    return result


def authorize(payload_sha: str, cost_ceiling: float, confirmed: bool) -> dict[str, Any]:
    if not confirmed:
        raise RuntimeError("explicit user authorization flag is required")
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = prepare()
    cost = estimate_cost()
    observed = sha_file(OUTPUT_DIR / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized payload SHA-256 does not match frozen bytes")
    if float(cost_ceiling) != float(cost["hard_ceiling_usd"]):
        raise ValueError("authorized cost ceiling does not match the frozen estimate")
    manifest["status"] = "authorized_not_started"
    manifest["paid_run_authorized"] = True
    manifest["authorization"] = {
        "recorded_at": now(),
        "payload_sha256": payload_sha,
        "hard_ceiling_usd": cost_ceiling,
        "scope": "ten HF-routed requests; one attempt each; no fallback",
    }
    atomic_json(manifest_path, manifest)
    return manifest


def authorize_transport_repair(
    payload_sha: str, cost_ceiling: float, confirmed: bool
) -> dict[str, Any]:
    """Authorize one append-only retry after the documented Cloudflare 1010 block."""
    if not confirmed:
        raise RuntimeError("explicit user authorization flag is required")
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    history = read_jsonl(OUTPUT_DIR / "provider_responses.jsonl")
    observed = sha_file(OUTPUT_DIR / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("repair authorization does not match the frozen payload")
    if float(cost_ceiling) != 0.10:
        raise ValueError("transport-repair ceiling must be $0.10")
    if len(history) != MAX_REQUESTS or any(row.get("http_status") != 403 for row in history):
        raise ValueError("transport repair requires exactly ten initial HTTP 403 records")
    if not all(
        "Access denied" in row.get("provider_error_body", "")
        and "Cloudflare" in row.get("provider_error_body", "")
        for row in history
    ):
        raise ValueError("initial failures were not uniformly Cloudflare access denials")
    manifest["status"] = "authorized_transport_repair_not_started"
    manifest["max_attempts_per_request"] = 2
    manifest["transport_repair_authorization"] = {
        "recorded_at": now(),
        "payload_sha256": payload_sha,
        "additional_hard_ceiling_usd": cost_ceiling,
        "additional_attempts_per_request": 1,
        "change": "add a Hugging Face client User-Agent; request content unchanged",
        "evidence": "public Featherless metadata returned 403 with Python-urllib and 200 with the corrected User-Agent",
    }
    atomic_json(manifest_path, manifest)
    return manifest


def parse_response(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("provider response has no choices")
    content = choices[0].get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("provider response has empty message content")
    return content, payload.get("usage") or {}


def run(cost_ceiling: float, authorize_paid_run: bool) -> dict[str, Any]:
    if not authorize_paid_run:
        raise RuntimeError("--authorize-paid-run is required")
    load_env_from_file()
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is not set")
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("paid_run_authorized"):
        raise RuntimeError("frozen smoke payload has not been authorized")
    authorized_ceiling = float(manifest["authorization"]["hard_ceiling_usd"])
    if float(cost_ceiling) != authorized_ceiling:
        raise ValueError("runtime ceiling does not match authorization")
    if sha_file(OUTPUT_DIR / "provider_requests.jsonl") != manifest["provider_payload_sha256"]:
        raise ValueError("provider payload changed after authorization")

    response_path = OUTPUT_DIR / "provider_responses.jsonl"
    history = read_jsonl(response_path)
    by_request: dict[str, list[dict[str, Any]]] = {}
    for history_row in history:
        by_request.setdefault(history_row["provider_request_id"], []).append(history_row)
    request_rows = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    if len(request_rows) > MAX_REQUESTS:
        raise ValueError("request ceiling exceeded")

    for row in request_rows:
        previous = by_request.get(row["provider_request_id"], [])
        if any(item.get("status") == "success" for item in previous):
            continue
        if len(previous) >= int(manifest["max_attempts_per_request"]):
            continue
        body: dict[str, Any] = {
            "model": row["model_id"],
            "messages": row["messages"],
            "temperature": row["temperature"],
            "max_tokens": row["max_tokens"],
        }
        if row["model"] == "t-pro-it-2.0":
            body["chat_template_kwargs"] = {"enable_thinking": False}
        started = time.monotonic()
        record: dict[str, Any] = {
            "provider_request_id": row["provider_request_id"],
            "model": row["model"],
            "model_id": row["model_id"],
            "prompt_id": row["prompt_id"],
            "prompt_language": row["prompt_language"],
            "requested_at": now(),
            "attempt": len(previous) + 1,
        }
        try:
            request = urllib.request.Request(
                f"{HF_BASE_URL}/chat/completions",
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "huggingface_hub/0.34.0 refusal-audit/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                record["http_status"] = response.status
                provider_payload = json.loads(response.read().decode("utf-8"))
            content, usage = parse_response(provider_payload)
            record.update(
                {"status": "success", "response_text": content, "usage": usage}
            )
        except urllib.error.HTTPError as exc:
            record.update(
                {
                    "status": "error",
                    "http_status": exc.code,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1000],
                    "provider_error_body": exc.read().decode("utf-8", errors="replace")[:2000],
                }
            )
        except Exception as exc:
            record.update(
                {"status": "error", "error_type": type(exc).__name__, "error": str(exc)[:1000]}
            )
        record["latency_seconds"] = round(time.monotonic() - started, 3)
        append_jsonl(response_path, record)
        by_request.setdefault(row["provider_request_id"], []).append(record)

    final_rows = [rows[-1] for rows in by_request.values()]
    manifest["network_inference_call_made"] = True
    manifest["completed_at"] = now()
    manifest["status"] = "completed" if len(final_rows) == MAX_REQUESTS else "incomplete"
    manifest["result"] = {
        "records": len(final_rows),
        "successes": sum(row["status"] == "success" for row in final_rows),
        "errors": sum(row["status"] == "error" for row in final_rows),
        "response_sha256": sha_file(response_path),
    }
    atomic_json(manifest_path, manifest)
    return manifest["result"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("prepare", "cost", "authorize", "authorize-repair", "run"),
    )
    parser.add_argument("--payload-sha")
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare()
    elif args.command == "cost":
        result = estimate_cost()
    elif args.command in {"authorize", "authorize-repair"}:
        if args.payload_sha is None or args.cost_ceiling is None:
            parser.error(f"{args.command} requires --payload-sha and --cost-ceiling")
        if args.command == "authorize-repair":
            result = authorize_transport_repair(
                args.payload_sha, args.cost_ceiling, args.confirm_user_authorization
            )
        else:
            result = authorize(
                args.payload_sha, args.cost_ceiling, args.confirm_user_authorization
            )
    else:
        if args.cost_ceiling is None:
            parser.error("run requires --cost-ceiling")
        result = run(args.cost_ceiling, args.authorize_paid_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
