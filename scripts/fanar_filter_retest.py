#!/usr/bin/env python3
"""Freeze and run a one-shot repeatability test of Fanar provider filters.

The payload contains exactly the 29 prompt-language requests that received the
native API's explicit response-level content-filter outcome in the completed
200-request pilot. A repeat never replaces the original attempt. It measures
whether that deployed-system outcome is deterministic under an otherwise
byte-identical request.

Technical record: docs/FANAR_EXPERIMENTS_V1.md
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fanar_diagnostic import (
    API_URL, MODEL_ID, ROOT, _call_fanar, _response_text, append_jsonl,
    read_jsonl, sha_file, sha_object, write_jsonl,
)


SOURCE_DIR = ROOT / "annotations/model_expansion_v4/fanar_c2_27b_pilot_v1"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/fanar_c2_27b_filter_retest_v1"
EXPECTED_REQUESTS = 29
ABSOLUTE_REQUEST_CEILING = 29


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_provider_filter(row: dict) -> bool:
    error = (row.get("provider_response") or {}).get("error") or {}
    return (
        row.get("http_status") == 400
        and error.get("code") == "content_filter"
        and error.get("type") == "safety"
        and error.get("param") == "response"
        and error.get("status") == 400
    )


def prepare() -> dict:
    source_requests_path = SOURCE_DIR / "provider_requests.jsonl"
    source_attempts_path = SOURCE_DIR / "attempts.jsonl"
    source_manifest_path = SOURCE_DIR / "manifest.json"
    source_requests = {row["provider_request_id"]: row for row in read_jsonl(source_requests_path)}
    filtered = [row for row in read_jsonl(source_attempts_path) if is_provider_filter(row)]
    if len(filtered) != EXPECTED_REQUESTS:
        raise ValueError("source pilot does not contain exactly 29 explicit response filters")
    if len({row["provider_request_id"] for row in filtered}) != EXPECTED_REQUESTS:
        raise ValueError("source filter records are not unique")
    input_hashes = {
        "source_manifest": sha_file(source_manifest_path),
        "source_requests": sha_file(source_requests_path),
        "source_attempts": sha_file(source_attempts_path),
    }
    payload_path = OUTPUT_DIR / "provider_requests.jsonl"
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("frozen filter-retest source changed")
        if sha_file(payload_path) != manifest["payload_sha256"]:
            raise ValueError("frozen filter-retest payload changed")
        return manifest

    requests = []
    for prior in sorted(filtered, key=lambda row: row["provider_request_id"]):
        source = source_requests[prior["provider_request_id"]]
        logical = {
            "version": "fanar-c2-27b-filter-retest-v1",
            "source_provider_request_id": source["provider_request_id"],
            "model": MODEL_ID,
            "prompt_id": source["prompt_id"],
            "prompt_language": source["prompt_language"],
        }
        # Copy the full provider-facing request fields. Only the audit IDs differ.
        requests.append({
            **{key: value for key, value in source.items() if key != "provider_request_id"},
            **logical,
            "provider_request_id": sha_object(logical)[:24],
        })
    if len(requests) != EXPECTED_REQUESTS:
        raise ValueError("filter retest must contain 29 requests")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(payload_path, requests)
    manifest = {
        "version": "fanar-c2-27b-filter-retest-v1",
        "created_at": now(),
        "status": "frozen_not_authorized",
        "scientific_role": "repeatability audit of explicit native-provider response filters; not replacement data",
        "model": MODEL_ID,
        "endpoint": API_URL,
        "n_requests": EXPECTED_REQUESTS,
        "attempts_per_request": 1,
        "absolute_provider_request_ceiling": ABSOLUTE_REQUEST_CEILING,
        "request_content_policy": "provider-facing model, messages, and generation settings copied byte-for-byte from each original request",
        "interpretation_limits": "a repeated filter remains a hidden response; a newly delivered response shows stochastic provider behavior but does not reveal the original hidden text",
        "input_sha256": input_hashes,
        "payload_sha256": sha_file(payload_path),
        "network_call_made": False,
        "authorization": None,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def authorize(payload_sha: str, max_requests: int, confirmed: bool) -> dict:
    manifest = prepare()
    if not confirmed:
        raise ValueError("authorization requires --confirm-user-authorization")
    if payload_sha != manifest["payload_sha256"]:
        raise ValueError("authorized SHA-256 does not match the frozen payload")
    if max_requests != ABSOLUTE_REQUEST_CEILING:
        raise ValueError("authorization must use the exact 29-request ceiling")
    record = {
        "authorized_at": now(), "user_authorized": True,
        "payload_sha256": payload_sha, "model": MODEL_ID, "endpoint": API_URL,
        "max_provider_requests": max_requests, "attempts_per_request": 1,
        "monetary_price_published": False,
        "user_acknowledged_unpublished_pricing": True,
    }
    path = OUTPUT_DIR / "authorization.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    manifest["authorization"] = record
    manifest["status"] = "authorized_not_started"
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return record


def run() -> dict:
    manifest = prepare()
    authorization_path = OUTPUT_DIR / "authorization.json"
    if not authorization_path.exists():
        raise ValueError("filter retest is not authorized")
    authorization = json.loads(authorization_path.read_text())
    if authorization["payload_sha256"] != manifest["payload_sha256"] or authorization["max_provider_requests"] != 29:
        raise ValueError("authorization does not match the frozen filter retest")
    sys.path.insert(0, str(ROOT / "scripts"))
    from env_utils import load_env_from_file
    load_env_from_file(ROOT / ".env")
    api_key = os.environ.get("FANAR_API_KEY")
    if not api_key:
        raise ValueError("FANAR_API_KEY is missing")

    lock_path = OUTPUT_DIR / ".run.lock"
    lock_path.touch(exist_ok=True)
    attempts_path = OUTPUT_DIR / "attempts.jsonl"
    results_path = OUTPUT_DIR / "results.jsonl"
    with lock_path.open("r+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempts = read_jsonl(attempts_path)
        attempted = {row["provider_request_id"] for row in attempts}
        for row in read_jsonl(OUTPUT_DIR / "provider_requests.jsonl"):
            if row["provider_request_id"] in attempted:
                continue
            if len(attempts) >= ABSOLUTE_REQUEST_CEILING:
                break
            started = time.monotonic()
            status, body, headers = _call_fanar(api_key, row)
            attempt = {
                "provider_request_id": row["provider_request_id"],
                "source_provider_request_id": row["source_provider_request_id"],
                "prompt_id": row["prompt_id"], "prompt_language": row["prompt_language"],
                "attempted_at": now(), "attempt_number": 1,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "http_status": status, "provider_response": body,
                "rate_limit_headers": headers,
            }
            append_jsonl(attempts_path, attempt)
            attempts.append(attempt)
            if status == 200:
                choices = body.get("choices") or []
                if choices and isinstance(choices[0].get("message"), dict):
                    message = choices[0]["message"]
                    append_jsonl(results_path, {
                        **{key: row[key] for key in (
                            "provider_request_id", "source_provider_request_id", "prompt_id",
                            "prompt_language", "model", "pilot_band", "prompt_metadata",
                        )},
                        "response_text": _response_text(message), "response_message": message,
                        "finish_reason": choices[0].get("finish_reason"),
                        "provider_response_id": body.get("id"),
                        "provider_reported_model": body.get("model"),
                        "usage": body.get("usage"), "created": body.get("created"),
                    })
            time.sleep(1.3)

    attempts = read_jsonl(attempts_path)
    results = read_jsonl(results_path)
    repeated_filters = sum(is_provider_filter(row) for row in attempts)
    summary = {
        "completed_at": now(), "payload_sha256": manifest["payload_sha256"],
        "requests": EXPECTED_REQUESTS, "attempted": len(attempts),
        "newly_delivered": len(results), "repeated_provider_filters": repeated_filters,
        "other_failures": len(attempts) - len(results) - repeated_filters,
        "status": "complete" if len(attempts) == EXPECTED_REQUESTS else "incomplete",
        "original_records_replaced": False,
    }
    (OUTPUT_DIR / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "authorize", "run"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--max-requests", type=int, default=ABSOLUTE_REQUEST_CEILING)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        output = prepare()
    elif args.command == "authorize":
        if not args.payload_sha:
            parser.error("authorize requires --payload-sha")
        output = authorize(args.payload_sha, args.max_requests, args.confirm_user_authorization)
    else:
        output = run()
    print(json.dumps(output, indent=2))
