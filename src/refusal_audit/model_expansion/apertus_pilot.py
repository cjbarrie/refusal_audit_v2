"""Guarded Apertus replacement pilot through Hugging Face's Public AI route."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from .openrouter_pilot import LANGUAGES, read_jsonl, sha_file, sha_object, write_jsonl


DEFAULT_DIR = Path("annotations/model_expansion_v2/apertus_replacement_pilot_v1")
ROSTER_PATH = Path("config/model_rosters/multirouter_expansion_v2.json")
SOURCE_PILOT_DIR = Path("annotations/model_expansion_v1/openrouter_pilot_v1")
MODEL_NAME = "apertus-v1.5-70b"
EXPECTED_N = 200
PLANNING_OUTPUT_TOKENS = 1_500
MAX_ATTEMPTS = 2
HF_ROUTER_BASE_URL = "https://router.huggingface.co/v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_count(text: str) -> int:
    try:
        import tiktoken

        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except Exception:
        return max(1, math.ceil(len(text.encode("utf-8")) / 4))


def _load_inputs(root: Path) -> tuple[dict, dict[str, dict[str, dict]], pd.DataFrame]:
    roster_path = root / ROSTER_PATH
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    if roster.get("provider_calls_authorized") is not False:
        raise ValueError("base v2 expansion roster must remain setup-only")
    matches = [model for model in roster["models"] if model["name"] == MODEL_NAME]
    if len(matches) != 1:
        raise ValueError("v2 roster must contain exactly one Apertus model")
    model = matches[0]
    if not (
        model["provider"] == "hf-router"
        and model["model_id"].endswith(":publicai")
        and model["selected_provider_tag"] == "publicai"
        and model["provider_routing"]
        == {"model_suffix": ":publicai", "allow_fallbacks": False}
    ):
        raise ValueError("Apertus is not pinned to Public AI without fallback")

    prompts: dict[str, dict[str, dict]] = {}
    expected_ids = None
    for language in LANGUAGES:
        spec = roster["design"]["prompt_files"][language]
        path = root / spec["path"]
        if sha_file(path) != spec["sha256"]:
            raise ValueError(f"frozen prompt hash mismatch for {language}")
        rows = json.loads(path.read_text(encoding="utf-8"))["prompts"]
        prompts[language] = {row["id"]: row for row in rows}
        ids = set(prompts[language])
        if expected_ids is None:
            expected_ids = ids
        elif ids != expected_ids:
            raise ValueError(f"prompt IDs differ in {language}")

    source_manifest = json.loads(
        (root / SOURCE_PILOT_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    selection_path = root / SOURCE_PILOT_DIR / "pilot_prompt_index.csv"
    if sha_file(selection_path) != source_manifest["artifact_sha256"][
        "pilot_prompt_index.csv"
    ]:
        raise ValueError("completed v1 pilot selection failed its hash check")
    selection = pd.read_csv(selection_path)
    if (
        len(selection) != 40
        or selection["prompt_id"].nunique() != 40
        or selection["issue_id"].nunique() != 40
    ):
        raise ValueError("source selection is not the frozen 40-prompt pilot")
    return model, prompts, selection


def prepare_apertus_pilot(root: Path, output_dir: Path | None = None) -> dict:
    """Freeze 40 prompt meanings x five languages locally; make no API call."""
    output_dir = output_dir or root / DEFAULT_DIR
    selection_path = root / SOURCE_PILOT_DIR / "pilot_prompt_index.csv"
    roster_path = root / ROSTER_PATH
    model, prompts, selection = _load_inputs(root)
    input_hashes = {
        "v2_roster": sha_file(roster_path),
        "v1_pilot_prompt_index": sha_file(selection_path),
        **{
            f"prompt_{language}": json.loads(roster_path.read_text(encoding="utf-8"))[
                "design"
            ]["prompt_files"][language]["sha256"]
            for language in LANGUAGES
        },
    }
    manifest_path = output_dir / "manifest.json"
    artifacts = {
        "pilot_prompt_index.csv": output_dir / "pilot_prompt_index.csv",
        "provider_requests.jsonl": output_dir / "provider_requests.jsonl",
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen Apertus pilot no longer matches inputs")
        for name, expected in manifest["artifact_sha256"].items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != expected:
                raise ValueError(f"frozen Apertus artifact changed: {name}")
        return manifest

    selection_by_id = selection.set_index("prompt_id").to_dict("index")
    requests = []
    for prompt_id in sorted(selection_by_id):
        selected = selection_by_id[prompt_id]
        for language in LANGUAGES:
            prompt = prompts[language][prompt_id]
            logical = {
                "pilot_version": "apertus-replacement-pilot-v1",
                "prompt_id": prompt_id,
                "prompt_language": language,
                "model": MODEL_NAME,
            }
            requests.append({
                **logical,
                "provider_request_id": sha_object(logical)[:24],
                "messages": [{"role": "user", "content": prompt["text"]}],
                "estimated_input_tokens": _token_count(prompt["text"]),
                "model_id": model["model_id"],
                "canonical_slug": model["canonical_slug"],
                "developer": model["developer"],
                "developer_jurisdiction": model["developer_jurisdiction"],
                "provider_name": model["selected_provider_name"],
                "provider_tag": model["selected_provider_tag"],
                "provider_route_locked_by_model_suffix": True,
                "temperature": model["temperature"],
                "max_output_tokens": model["max_tokens"],
                "input_usd_per_million": model["input_usd_per_million"],
                "output_usd_per_million": model["output_usd_per_million"],
                "thinking_mode": "off_by_model_default",
                "prompt_metadata": {
                    key: prompt.get(key) for key in (
                        "issue_id", "qid", "topic_domain", "controversy_tier",
                        "region_focus", "position_side", "route", "battery",
                        "prompt_origin_language", "prompt_origin_form",
                    )
                },
                "pilot_band": selected["pilot_band"],
            })
    if len(requests) != EXPECTED_N:
        raise ValueError(f"expected {EXPECTED_N} Apertus requests, got {len(requests)}")
    if len({row["provider_request_id"] for row in requests}) != EXPECTED_N:
        raise ValueError("Apertus provider request IDs are not unique")

    output_dir.mkdir(parents=True, exist_ok=False)
    selection.to_csv(artifacts["pilot_prompt_index.csv"], index=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    manifest = {
        "version": "apertus-replacement-pilot-v1",
        "created_at": now(),
        "status": "frozen_unpriced",
        "scientific_role": (
            "direct replacement test on the same enriched 40-prompt, "
            "five-language frame used in expansion pilot v1; not prevalence"
        ),
        "replaces_in_future_roster": "mistral-small-3.2",
        "preserves_historical_v1_response": True,
        "model": MODEL_NAME,
        "model_id": model["model_id"],
        "provider": "Hugging Face router",
        "provider_tag": "publicai",
        "provider_fallbacks_disabled_by_exact_suffix": True,
        "thinking_mode": "off_by_model_default",
        "languages": list(LANGUAGES),
        "n_prompt_meanings": 40,
        "n_requests": EXPECTED_N,
        "max_attempts": MAX_ATTEMPTS,
        "input_sha256": input_hashes,
        "artifact_sha256": {
            name: sha_file(path) for name, path in artifacts.items()
        },
        "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_apertus_cost(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare_apertus_pilot(root, output_dir)
    requests = read_jsonl(output_dir / "provider_requests.jsonl")
    planning = sum(
        (row["estimated_input_tokens"] * row["input_usd_per_million"]
         + PLANNING_OUTPUT_TOKENS * row["output_usd_per_million"]) / 1_000_000
        for row in requests
    )
    reserved = sum(
        (row["estimated_input_tokens"] * row["input_usd_per_million"]
         + row["max_output_tokens"] * row["output_usd_per_million"]) / 1_000_000
        for row in requests
    )
    ceiling = math.ceil(max(planning * 1.5, reserved * 1.25) * 2) / 2
    result = {
        "version": "apertus-replacement-pilot-cost-v1",
        "created_at": now(),
        "pricing_verified_at": "2026-09-02",
        "pricing_source": "https://router.huggingface.co/v1/models",
        "price_usd_per_million": {"input": 0.82, "output": 2.92},
        "requests": len(requests),
        "estimated_input_tokens": sum(r["estimated_input_tokens"] for r in requests),
        "planning_output_tokens": len(requests) * PLANNING_OUTPUT_TOKENS,
        "planning_cost_usd": planning,
        "single_attempt_reserved_cost_usd": reserved,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    (output_dir / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    manifest_path = output_dir / "manifest.json"
    latest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not latest.get("paid_run_authorized") and not latest.get(
        "network_inference_call_made"
    ):
        latest["status"] = "frozen_unpaid"
    latest["cost_estimate"] = result
    manifest_path.write_text(json.dumps(latest, indent=2), encoding="utf-8")
    return result


def authorize_apertus_pilot(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cost = json.loads((output_dir / "cost_estimate.json").read_text(encoding="utf-8"))
    observed = sha_file(output_dir / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized Apertus payload hash does not match frozen bytes")
    if float(ceiling) != float(cost["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized Apertus ceiling does not match frozen estimate")
    authorization = {
        "recorded_at": now(),
        "user_authorized": True,
        "authorization_scope": "apertus_replacement_pilot_v1",
        "provider_payload_sha256": payload_sha,
        "model_id": manifest["model_id"],
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


def _is_transient(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status in {429, 500, 502, 503, 504}:
        return True
    value = str(exc).lower()
    return any(marker in value for marker in (
        "rate limit", "timeout", "timed out", "connection", "overloaded",
        "service unavailable", "bad gateway", "gateway timeout",
    ))


def _call(client, request: dict) -> dict:
    started = time.time()
    response = client.chat.completions.create(
        model=request["model_id"],
        messages=request["messages"],
        temperature=request["temperature"],
        max_tokens=request["max_output_tokens"],
        timeout=180,
    )
    message = response.choices[0].message
    content = message.content or ""
    reasoning = (
        getattr(message, "reasoning_content", None)
        or getattr(message, "reasoning", None)
    )
    inline_thinking = bool(re.search(r"<think>", content, flags=re.I))
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.I | re.S).strip()
    if not content:
        raise ValueError("empty Apertus response content")
    usage = response.usage.model_dump() if response.usage else {}
    cost = usage.get("cost")
    if cost is None:
        cost = (
            float(usage.get("prompt_tokens", 0)) * request["input_usd_per_million"]
            + float(usage.get("completion_tokens", 0))
            * request["output_usd_per_million"]
        ) / 1_000_000
    return {
        "provider_request_id": request["provider_request_id"],
        "prompt_id": request["prompt_id"],
        "prompt_language": request["prompt_language"],
        "model": request["model"],
        "model_id_requested": request["model_id"],
        "provider_tag_requested": request["provider_tag"],
        "provider_response_id": response.id,
        "provider_model": response.model,
        "provider_returned": getattr(response, "provider", None),
        "response_text": content,
        "response_text_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "reasoning_returned_unexpectedly": bool(reasoning),
        "inline_thinking_removed": inline_thinking,
        "usage": usage,
        "incremental_provider_cost": float(cost),
        "elapsed_seconds": time.time() - started,
        "created_at": now(),
        "status": "complete",
        "prompt_metadata": request["prompt_metadata"],
        "pilot_band": request["pilot_band"],
    }


def run_apertus_pilot(
    root: Path, output_dir: Path, workers: int, ceiling: float, authorized: bool
) -> dict:
    if not authorized:
        raise RuntimeError("paid run requires --authorize-paid-run")
    if workers < 1 or workers > 16:
        raise ValueError("workers must be between 1 and 16")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload_path = output_dir / "provider_requests.jsonl"
    auth = manifest.get("authorization", {})
    if not (
        auth.get("user_authorized") is True
        and auth.get("provider_payload_sha256") == sha_file(payload_path)
        and auth.get("model_id") == manifest["model_id"]
        and auth.get("provider_tag") == "publicai"
        and auth.get("provider_fallbacks_disabled_by_exact_suffix") is True
        and float(auth.get("cost_ceiling_usd", -1)) == float(ceiling)
    ):
        raise RuntimeError("authorization does not match exact Apertus payload")

    from openai import OpenAI
    import sys

    sys.path.insert(0, str(root / "scripts"))
    from env_utils import load_env_from_file

    load_env_from_file()
    key = os.environ.get("HF_TOKEN")
    if not key:
        raise RuntimeError("HF_TOKEN is not set")
    client = OpenAI(base_url=HF_ROUTER_BASE_URL, api_key=key)
    requests = read_jsonl(payload_path)
    attempts_path = output_dir / "attempts.jsonl"
    completed: Dict[str, dict] = {}
    attempts: Dict[str, int] = {}
    spent = 0.0
    for record in read_jsonl(attempts_path):
        spent += float(record.get("incremental_provider_cost", 0))
        request_id = record["provider_request_id"]
        attempts[request_id] = attempts.get(request_id, 0) + 1
        if record.get("status") == "complete":
            completed[request_id] = record
    pending = [row for row in requests if row["provider_request_id"] not in completed]
    lock_path = output_dir / ".run.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with attempts_path.open("a", encoding="utf-8") as handle:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {}
                cursor = 0
                reserved = 0.0
                while cursor < len(pending) or futures:
                    while cursor < len(pending) and len(futures) < workers:
                        request = pending[cursor]
                        request_id = request["provider_request_id"]
                        if attempts.get(request_id, 0) >= MAX_ATTEMPTS:
                            cursor += 1
                            continue
                        hold = (
                            request["estimated_input_tokens"]
                            * request["input_usd_per_million"]
                            + request["max_output_tokens"]
                            * request["output_usd_per_million"]
                        ) / 1_000_000
                        if spent + reserved + hold > ceiling + 1e-9:
                            break
                        cursor += 1
                        future = pool.submit(_call, client, request)
                        futures[future] = (request, hold)
                        reserved += hold
                    if not futures:
                        break
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        request, hold = futures.pop(future)
                        reserved -= hold
                        try:
                            record = future.result()
                        except Exception as exc:
                            record = {
                                "provider_request_id": request["provider_request_id"],
                                "prompt_id": request["prompt_id"],
                                "prompt_language": request["prompt_language"],
                                "model": request["model"],
                                "provider_tag_requested": request["provider_tag"],
                                "status": "error",
                                "error_type": type(exc).__name__,
                                "error": str(exc)[:1000],
                                "transient": _is_transient(exc),
                                "incremental_provider_cost": 0.0,
                                "created_at": now(),
                            }
                        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                        request_id = request["provider_request_id"]
                        attempts[request_id] = attempts.get(request_id, 0) + 1
                        spent += float(record.get("incremental_provider_cost", 0))
                        if spent > ceiling + 1e-9:
                            raise RuntimeError("hard provider-cost ceiling exceeded")
                        if record.get("status") == "complete":
                            completed[request_id] = record
                        # A permission or validation failure will not improve on
                        # an immediate identical retry. Only provider/network
                        # failures explicitly classified as transient may use
                        # the second authorized attempt.
                        elif (
                            record.get("transient") is True
                            and attempts[request_id] < MAX_ATTEMPTS
                        ):
                            pending.append(request)

    ordered = [
        completed[row["provider_request_id"]] for row in requests
        if row["provider_request_id"] in completed
    ]
    results_path = output_dir / "results.jsonl"
    write_jsonl(results_path, ordered)
    summary = {
        "completed_at": now(),
        "n_expected": EXPECTED_N,
        "n_completed": len(ordered),
        "n_incomplete": EXPECTED_N - len(ordered),
        "completion_rate": len(ordered) / EXPECTED_N,
        "provider_cost_usd": spent,
        "authorized_ceiling_usd": float(ceiling),
        "provider_payload_sha256": sha_file(payload_path),
        "attempts_sha256": sha_file(attempts_path),
        "results_sha256": sha_file(results_path),
        "network_inference_call_made": True,
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    manifest["status"] = "completed" if len(ordered) == EXPECTED_N else "incomplete"
    manifest["network_inference_call_made"] = True
    manifest["run_summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary
