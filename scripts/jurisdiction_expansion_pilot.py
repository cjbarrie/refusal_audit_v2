#!/usr/bin/env python3
"""Guarded 40-meaning pilot for T-pro-it-2.0 and Bielik 11B v3.

The pilot reuses the exact 40 prompt meanings selected for expansion pilot v1,
crosses them with all five study languages, and changes only the subject model
and pinned inference route. It is enriched for diagnostic variety and is not a
probability sample for estimating refusal prevalence.

Technical record: docs/JURISDICTION_MODEL_EXPANSION_V1.md
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from env_utils import load_env_from_file
from jurisdiction_expansion_smoke import (
    HF_BASE_URL,
    LANGUAGES,
    ROSTER_PATH,
    SOURCE_SELECTION,
    atomic_json,
    load_roster,
    parse_response,
    read_jsonl,
    sha_file,
    sha_object,
    token_count,
    write_jsonl,
)


OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/jurisdiction_pilot_v1"
EXPECTED_PROMPT_MEANINGS = 40
EXPECTED_REQUESTS = 400
MAX_ATTEMPTS = 1
MAX_WORKERS = 8
USER_AGENT = "huggingface_hub/0.34.0 refusal-audit/1.0"
_LEDGER_LOCK = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_selection() -> list[dict[str, str]]:
    with SOURCE_SELECTION.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_PROMPT_MEANINGS:
        raise ValueError("source pilot selection does not contain 40 rows")
    if len({row["prompt_id"] for row in rows}) != EXPECTED_PROMPT_MEANINGS:
        raise ValueError("source pilot selection does not contain 40 unique prompts")
    if len({row["issue_id"] for row in rows}) != EXPECTED_PROMPT_MEANINGS:
        raise ValueError("source pilot selection repeats an issue")
    return sorted(rows, key=lambda row: row["prompt_id"])


def load_all_prompts(roster: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {}
    expected_ids: set[str] | None = None
    for language in LANGUAGES:
        specification = roster["design"]["prompt_files"][language]
        path = ROOT / specification["path"]
        if sha_file(path) != specification["sha256"]:
            raise ValueError(f"frozen prompt hash mismatch for {language}")
        rows = json.loads(path.read_text(encoding="utf-8"))["prompts"]
        indexed = {row["id"]: row for row in rows}
        if expected_ids is None:
            expected_ids = set(indexed)
        elif set(indexed) != expected_ids:
            raise ValueError(f"prompt IDs differ in {language}")
        result[language] = indexed
    return result


def prepare() -> dict[str, Any]:
    roster = load_roster()
    models = [row for row in roster["models"] if row["phase"] == "hf_phase"]
    selection = load_selection()
    all_prompts = load_all_prompts(roster)
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
            raise ValueError("existing pilot no longer matches its frozen inputs")
        if sha_file(requests_path) != manifest["provider_payload_sha256"]:
            raise ValueError("existing provider payload changed")
        return manifest

    requests_rows: list[dict[str, Any]] = []
    selection_by_id = {row["prompt_id"]: row for row in selection}
    for model in models:
        for prompt_id in sorted(selection_by_id):
            selected = selection_by_id[prompt_id]
            for language in LANGUAGES:
                prompt = all_prompts[language][prompt_id]
                logical_key = {
                    "version": "jurisdiction-expansion-pilot-v1",
                    "model": model["name"],
                    "prompt_id": prompt_id,
                    "prompt_language": language,
                }
                requests_rows.append(
                    {
                        **logical_key,
                        "provider_request_id": sha_object(logical_key)[:24],
                        "provider": "Hugging Face Inference Providers",
                        "provider_tag": model["provider_tag"],
                        "provider_fallbacks_disabled": True,
                        "model_id": model["model_id"],
                        "messages": [{"role": "user", "content": prompt["text"]}],
                        "temperature": model["temperature"],
                        "max_tokens": model["max_tokens"],
                        "estimated_input_tokens": token_count(prompt["text"]),
                        "input_usd_per_million": model["input_usd_per_million"],
                        "output_usd_per_million": model["output_usd_per_million"],
                        "reasoning_disabled": model["reasoning_disabled"],
                        "transport_user_agent": USER_AGENT,
                        "pilot_band": selected["pilot_band"],
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
                                "prompt_origin_language",
                                "prompt_origin_form",
                            )
                        },
                    }
                )
    if len(requests_rows) != EXPECTED_REQUESTS:
        raise ValueError(f"expected {EXPECTED_REQUESTS} requests, got {len(requests_rows)}")
    if len({row["provider_request_id"] for row in requests_rows}) != EXPECTED_REQUESTS:
        raise ValueError("provider request IDs are not unique")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(requests_path, requests_rows)
    manifest = {
        "version": "jurisdiction-expansion-pilot-v1",
        "created_at": now(),
        "status": "frozen_unpaid",
        "scientific_role": "enriched operational and behavioral pilot; not prevalence estimation",
        "models": [model["name"] for model in models],
        "languages": list(LANGUAGES),
        "n_prompt_meanings": EXPECTED_PROMPT_MEANINGS,
        "n_requests": EXPECTED_REQUESTS,
        "max_attempts_per_request": MAX_ATTEMPTS,
        "maximum_workers": MAX_WORKERS,
        "provider_fallbacks_disabled": True,
        "reasoning_disabled": True,
        "input_sha256": input_hashes,
        "provider_payload_sha256": sha_file(requests_path),
        "paid_run_authorized": False,
        "network_inference_call_made": False,
        "krutrim_status": "deferred_account_requires_indian_phone_number",
    }
    atomic_json(manifest_path, manifest)
    return manifest


def estimate_cost() -> dict[str, Any]:
    manifest = prepare()
    rows = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    planning = sum(
        (
            row["estimated_input_tokens"] * row["input_usd_per_million"]
            + 1_500 * row["output_usd_per_million"]
        )
        / 1_000_000
        for row in rows
    )
    reserve = sum(
        (
            row["estimated_input_tokens"] * row["input_usd_per_million"]
            + row["max_tokens"] * row["output_usd_per_million"]
        )
        / 1_000_000
        for row in rows
    )
    by_model: dict[str, dict[str, Any]] = {}
    for model in sorted({row["model"] for row in rows}):
        subset = [row for row in rows if row["model"] == model]
        by_model[model] = {
            "requests": len(subset),
            "estimated_input_tokens": sum(row["estimated_input_tokens"] for row in subset),
            "planning_cost_usd": round(
                sum(
                    (
                        row["estimated_input_tokens"] * row["input_usd_per_million"]
                        + 1_500 * row["output_usd_per_million"]
                    )
                    / 1_000_000
                    for row in subset
                ),
                6,
            ),
        }
    result = {
        "version": "jurisdiction-expansion-pilot-cost-v1",
        "created_at": now(),
        "requests": len(rows),
        "estimated_input_tokens": sum(row["estimated_input_tokens"] for row in rows),
        "planning_output_tokens_per_request": 1_500,
        "planning_cost_usd": round(planning, 6),
        "single_attempt_max_token_reserve_usd": round(reserve, 6),
        "hard_ceiling_usd": 3.0,
        "by_model": by_model,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    atomic_json(OUTPUT_DIR / "cost_estimate.json", result)
    return result


def authorize(payload_sha: str, ceiling: float, confirmed: bool) -> dict[str, Any]:
    if not confirmed:
        raise RuntimeError("explicit user authorization flag is required")
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = prepare()
    cost = estimate_cost()
    observed = sha_file(OUTPUT_DIR / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized payload SHA-256 does not match frozen bytes")
    if float(ceiling) != float(cost["hard_ceiling_usd"]):
        raise ValueError("authorized ceiling does not match frozen cost record")
    manifest["status"] = "authorized_not_started"
    manifest["paid_run_authorized"] = True
    manifest["authorization"] = {
        "recorded_at": now(),
        "payload_sha256": payload_sha,
        "hard_ceiling_usd": ceiling,
        "scope": "400 HF-routed requests; one attempt each; no fallback",
    }
    atomic_json(manifest_path, manifest)
    return manifest


def append_record(path: Path, record: dict[str, Any]) -> None:
    with _LEDGER_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def send_one(row: dict[str, Any], token: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": row["model_id"],
        "messages": row["messages"],
        "temperature": row["temperature"],
        "max_tokens": row["max_tokens"],
    }
    if row["model"] == "t-pro-it-2.0":
        body["chat_template_kwargs"] = {"enable_thinking": False}
    record: dict[str, Any] = {
        "provider_request_id": row["provider_request_id"],
        "model": row["model"],
        "model_id": row["model_id"],
        "prompt_id": row["prompt_id"],
        "prompt_language": row["prompt_language"],
        "attempt": 1,
        "requested_at": now(),
    }
    started = time.monotonic()
    try:
        request = urllib.request.Request(
            f"{HF_BASE_URL}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            record["http_status"] = response.status
            provider_payload = json.loads(response.read().decode("utf-8"))
        content, usage = parse_response(provider_payload)
        record.update({"status": "success", "response_text": content, "usage": usage})
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
    return record


def run(workers: int, ceiling: float, authorize_paid_run: bool) -> dict[str, Any]:
    if not authorize_paid_run:
        raise RuntimeError("--authorize-paid-run is required")
    load_env_from_file()
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is not set")
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("paid_run_authorized"):
        raise RuntimeError("pilot has not been explicitly authorized")
    if float(ceiling) != float(manifest["authorization"]["hard_ceiling_usd"]):
        raise ValueError("runtime ceiling does not match authorization")
    if sha_file(OUTPUT_DIR / "provider_requests.jsonl") != manifest["provider_payload_sha256"]:
        raise ValueError("provider payload changed after authorization")
    if workers < 1 or workers > MAX_WORKERS:
        raise ValueError(f"workers must be between 1 and {MAX_WORKERS}")

    response_path = OUTPUT_DIR / "provider_responses.jsonl"
    existing_rows = read_jsonl(response_path)
    completed_ids = {row["provider_request_id"] for row in existing_rows}
    request_rows = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    pending = [row for row in request_rows if row["provider_request_id"] not in completed_ids]
    if len(request_rows) != EXPECTED_REQUESTS:
        raise ValueError("frozen request count changed")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(send_one, row, token): row for row in pending}
        for future in as_completed(futures):
            append_record(response_path, future.result())

    rows = read_jsonl(response_path)
    latest = {row["provider_request_id"]: row for row in rows}
    final_rows = list(latest.values())
    manifest["network_inference_call_made"] = True
    manifest["completed_at"] = now()
    manifest["status"] = "completed" if len(final_rows) == EXPECTED_REQUESTS else "incomplete"
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
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "run"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare()
    elif args.command == "cost":
        result = estimate_cost()
    elif args.command == "authorize":
        if args.payload_sha is None or args.cost_ceiling is None:
            parser.error("authorize requires --payload-sha and --cost-ceiling")
        result = authorize(args.payload_sha, args.cost_ceiling, args.confirm_user_authorization)
    else:
        if args.cost_ceiling is None:
            parser.error("run requires --cost-ceiling")
        result = run(args.workers, args.cost_ceiling, args.authorize_paid_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
