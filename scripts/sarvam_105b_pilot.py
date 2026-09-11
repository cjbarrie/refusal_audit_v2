#!/usr/bin/env python3
"""Guarded 40-meaning, five-language pilot for native Sarvam-105B.

This uses the same enriched 40-meaning selection as the other jurisdiction
expansion pilots. It tests route and response behavior; it does not estimate
population refusal prevalence.

Technical record: docs/JURISDICTION_MODEL_EXPANSION_V1.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from env_utils import load_env_from_file
from jurisdiction_expansion_pilot import load_all_prompts, load_selection, now
from jurisdiction_expansion_smoke import (
    LANGUAGES, ROSTER_PATH, SOURCE_SELECTION, atomic_json, load_roster,
    parse_response, read_jsonl, sha_file, sha_object, token_count, write_jsonl,
)

OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/sarvam_105b_pilot_v1"
BASE_URL = "https://api.sarvam.ai/v1"
MODEL_ID = "sarvam-105b"
EXPECTED_PROMPTS = 40
EXPECTED_REQUESTS = 200
MAX_TOKENS = 4096
MAX_WORKERS = 5
INPUT_INR_PER_MILLION = 29.28
OUTPUT_INR_PER_MILLION = 73.2
HARD_CEILING_INR = 65.0
_LEDGER_LOCK = threading.Lock()


def append_record(path: Path, record: dict[str, Any]) -> None:
    with _LEDGER_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def prepare() -> dict[str, Any]:
    roster = load_roster()
    selection = load_selection()
    prompts = load_all_prompts(roster)
    input_hashes = {
        "roster": sha_file(ROSTER_PATH),
        "source_selection": sha_file(SOURCE_SELECTION),
        **{f"prompt_{lang}": roster["design"]["prompt_files"][lang]["sha256"]
           for lang in LANGUAGES},
    }
    request_path = OUTPUT_DIR / "provider_requests.jsonl"
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("existing Sarvam pilot no longer matches frozen inputs")
        if sha_file(request_path) != manifest["provider_payload_sha256"]:
            raise ValueError("existing Sarvam pilot payload changed")
        return manifest

    rows: list[dict[str, Any]] = []
    for selected in selection:
        prompt_id = selected["prompt_id"]
        for language in LANGUAGES:
            prompt = prompts[language][prompt_id]
            logical_key = {
                "version": "sarvam-105b-pilot-v1", "model": MODEL_ID,
                "prompt_id": prompt_id, "prompt_language": language,
            }
            rows.append({
                **logical_key,
                "provider_request_id": sha_object(logical_key)[:24],
                "provider": "Sarvam native API",
                "messages": [{"role": "user", "content": prompt["text"]}],
                "temperature": 1.0,
                "max_tokens": MAX_TOKENS,
                "reasoning_effort": None,
                "estimated_input_tokens": token_count(prompt["text"]),
                "input_inr_per_million": INPUT_INR_PER_MILLION,
                "output_inr_per_million": OUTPUT_INR_PER_MILLION,
                "pilot_band": selected["pilot_band"],
                "prompt_metadata": {key: prompt.get(key) for key in (
                    "issue_id", "qid", "topic_domain", "controversy_tier",
                    "region_focus", "position_side", "route", "battery",
                    "prompt_origin_language", "prompt_origin_form",
                )},
            })
    if len(rows) != EXPECTED_REQUESTS:
        raise ValueError(f"expected {EXPECTED_REQUESTS} requests, got {len(rows)}")
    if len({row["provider_request_id"] for row in rows}) != EXPECTED_REQUESTS:
        raise ValueError("Sarvam pilot request IDs are not unique")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(request_path, rows)
    manifest = {
        "version": "sarvam-105b-pilot-v1", "created_at": now(),
        "status": "frozen_unpaid",
        "scientific_role": "enriched operational and behavioral pilot; not prevalence estimation",
        "model": MODEL_ID, "developer": "Sarvam AI",
        "developer_jurisdiction": "India",
        "endpoint": f"{BASE_URL}/chat/completions",
        "languages": list(LANGUAGES), "n_prompt_meanings": EXPECTED_PROMPTS,
        "n_requests": EXPECTED_REQUESTS, "max_attempts_per_request": 1,
        "maximum_workers": MAX_WORKERS, "provider_fallbacks": "not applicable: native API",
        "reasoning_disabled": True, "provider_specific_max_tokens": MAX_TOKENS,
        "provider_cap_rationale": "Sarvam Starter plan maximum documented as 4096 tokens",
        "input_sha256": input_hashes,
        "provider_payload_sha256": sha_file(request_path),
        "paid_run_authorized": False, "network_inference_call_made": False,
    }
    atomic_json(manifest_path, manifest)
    return manifest


def estimate_cost() -> dict[str, Any]:
    manifest = prepare()
    rows = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    planning = sum((r["estimated_input_tokens"] * INPUT_INR_PER_MILLION
                    + 1500 * OUTPUT_INR_PER_MILLION) / 1_000_000 for r in rows)
    reserve = sum((r["estimated_input_tokens"] * INPUT_INR_PER_MILLION
                   + MAX_TOKENS * OUTPUT_INR_PER_MILLION) / 1_000_000 for r in rows)
    result = {
        "version": "sarvam-105b-pilot-cost-v1", "created_at": now(),
        "requests": len(rows),
        "estimated_input_tokens": sum(r["estimated_input_tokens"] for r in rows),
        "planning_output_tokens_per_request": 1500,
        "planning_cost_inr": round(planning, 6),
        "single_attempt_max_token_reserve_inr": round(reserve, 6),
        "hard_ceiling_inr": HARD_CEILING_INR,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "pricing_checked_at": "2026-09-07", "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    atomic_json(OUTPUT_DIR / "cost_estimate.json", result)
    return result


def authorize(payload_sha: str, ceiling: float, confirmed: bool) -> dict[str, Any]:
    if not confirmed:
        raise RuntimeError("explicit user authorization flag is required")
    manifest = prepare()
    cost = estimate_cost()
    observed = sha_file(OUTPUT_DIR / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized payload SHA-256 does not match frozen bytes")
    if float(ceiling) != float(cost["hard_ceiling_inr"]):
        raise ValueError("authorized ceiling does not match frozen cost record")
    manifest["status"] = "authorized_not_started"
    manifest["paid_run_authorized"] = True
    manifest["authorization"] = {
        "recorded_at": now(), "payload_sha256": payload_sha,
        "hard_ceiling_inr": ceiling,
        "scope": "200 native Sarvam requests; one attempt each",
    }
    atomic_json(OUTPUT_DIR / "manifest.json", manifest)
    return manifest


def send_one(row: dict[str, Any], api_key: str) -> dict[str, Any]:
    body = {
        "model": MODEL_ID, "messages": row["messages"],
        "temperature": row["temperature"], "max_tokens": row["max_tokens"],
        "reasoning_effort": None,
    }
    record: dict[str, Any] = {
        "provider_request_id": row["provider_request_id"], "model": MODEL_ID,
        "prompt_id": row["prompt_id"], "prompt_language": row["prompt_language"],
        "attempt": 1, "requested_at": now(),
    }
    started = time.monotonic()
    try:
        request = urllib.request.Request(
            f"{BASE_URL}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"api-subscription-key": api_key, "Content-Type": "application/json",
                     "User-Agent": "sarvamai-python refusal-audit/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            record["http_status"] = response.status
            payload = json.loads(response.read().decode("utf-8"))
        content, usage = parse_response(payload)
        record.update({"status": "success", "response_text": content, "usage": usage})
    except urllib.error.HTTPError as exc:
        record.update({"status": "error", "http_status": exc.code,
                       "error_type": type(exc).__name__, "error": str(exc)[:1000],
                       "provider_error_body": exc.read().decode("utf-8", errors="replace")[:2000]})
    except Exception as exc:
        record.update({"status": "error", "error_type": type(exc).__name__,
                       "error": str(exc)[:1000]})
    record["latency_seconds"] = round(time.monotonic() - started, 3)
    return record


def run(workers: int, ceiling: float, authorized: bool) -> dict[str, Any]:
    if not authorized:
        raise RuntimeError("--authorize-paid-run is required")
    load_env_from_file()
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is not set")
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("paid_run_authorized"):
        raise RuntimeError("Sarvam pilot has not been explicitly authorized")
    if float(ceiling) != float(manifest["authorization"]["hard_ceiling_inr"]):
        raise ValueError("runtime ceiling does not match authorization")
    if sha_file(OUTPUT_DIR / "provider_requests.jsonl") != manifest["provider_payload_sha256"]:
        raise ValueError("provider payload changed after authorization")
    if workers < 1 or workers > MAX_WORKERS:
        raise ValueError(f"workers must be between 1 and {MAX_WORKERS}")
    response_path = OUTPUT_DIR / "provider_responses.jsonl"
    existing = {r["provider_request_id"]: r for r in read_jsonl(response_path)}
    requests = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    pending = [r for r in requests if r["provider_request_id"] not in existing]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(send_one, row, api_key): row for row in pending}
        for future in as_completed(futures):
            append_record(response_path, future.result())
    rows = read_jsonl(response_path)
    latest = {r["provider_request_id"]: r for r in rows}
    final = list(latest.values())
    manifest["network_inference_call_made"] = True
    manifest["completed_at"] = now()
    manifest["status"] = "completed" if len(final) == EXPECTED_REQUESTS else "incomplete"
    manifest["result"] = {
        "records": len(final), "successes": sum(r["status"] == "success" for r in final),
        "errors": sum(r["status"] == "error" for r in final),
        "response_sha256": sha_file(response_path),
    }
    atomic_json(manifest_path, manifest)
    return manifest["result"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "run"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--cost-ceiling-inr", type=float)
    parser.add_argument("--workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare": result = prepare()
    elif args.command == "cost": result = estimate_cost()
    elif args.command == "authorize":
        if args.payload_sha is None or args.cost_ceiling_inr is None:
            parser.error("authorize requires --payload-sha and --cost-ceiling-inr")
        result = authorize(args.payload_sha, args.cost_ceiling_inr,
                           args.confirm_user_authorization)
    else:
        if args.cost_ceiling_inr is None:
            parser.error("run requires --cost-ceiling-inr")
        result = run(args.workers, args.cost_ceiling_inr, args.authorize_paid_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
