#!/usr/bin/env python3
"""Freeze and run one low-concurrency repair of transient pilot failures.

Only HTTP 429/5xx outcomes from the completed T-pro/Bielik pilot are eligible.
The original model input and generation settings are reused byte-for-byte from
the frozen request ledger. No content or deterministic client error is retried.

Technical record: docs/JURISDICTION_MODEL_EXPANSION_V1.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from env_utils import load_env_from_file
from jurisdiction_expansion_pilot import append_record, now, send_one
from jurisdiction_expansion_smoke import atomic_json, read_jsonl, sha_file, write_jsonl

SOURCE_DIR = ROOT / "annotations/model_expansion_v4/jurisdiction_pilot_v1"
OUTPUT_DIR = SOURCE_DIR / "transport_repair_v1"
ELIGIBLE_HTTP = {429, 500, 502, 503, 504}
HARD_CEILING_USD = 2.25


def prepare() -> dict[str, Any]:
    source_manifest = json.loads((SOURCE_DIR / "manifest.json").read_text(encoding="utf-8"))
    source_requests = read_jsonl(SOURCE_DIR / "provider_requests.jsonl")
    source_responses = read_jsonl(SOURCE_DIR / "provider_responses.jsonl")
    latest = {row["provider_request_id"]: row for row in source_responses}
    eligible_ids = {
        key for key, row in latest.items()
        if row.get("status") == "error" and row.get("http_status") in ELIGIBLE_HTTP
    }
    rows = [row for row in source_requests if row["provider_request_id"] in eligible_ids]
    if len(rows) != len(eligible_ids):
        raise ValueError("not every eligible error maps to one frozen request")
    request_path = OUTPUT_DIR / "provider_requests.jsonl"
    manifest_path = OUTPUT_DIR / "manifest.json"
    source_hashes = {
        "source_request_sha256": sha_file(SOURCE_DIR / "provider_requests.jsonl"),
        "source_response_sha256": sha_file(SOURCE_DIR / "provider_responses.jsonl"),
        "source_manifest_result_sha256": source_manifest["result"]["response_sha256"],
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["source_hashes"] != source_hashes:
            raise ValueError("source pilot changed after repair payload was frozen")
        if sha_file(request_path) != manifest["provider_payload_sha256"]:
            raise ValueError("repair payload changed")
        return manifest
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(request_path, rows)
    manifest = {
        "version": "jurisdiction-expansion-pilot-transport-repair-v1",
        "created_at": now(), "status": "frozen_unpaid",
        "scientific_role": "transport repair only; original request content unchanged",
        "eligible_http_statuses": sorted(ELIGIBLE_HTTP),
        "n_requests": len(rows), "models": sorted({r["model"] for r in rows}),
        "maximum_workers": 1, "additional_attempts_per_request": 1,
        "provider_fallbacks_disabled": True, "source_hashes": source_hashes,
        "provider_payload_sha256": sha_file(request_path),
        "paid_run_authorized": False, "network_inference_call_made": False,
    }
    atomic_json(manifest_path, manifest)
    return manifest


def estimate_cost() -> dict[str, Any]:
    manifest = prepare()
    rows = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    planning = sum((r["estimated_input_tokens"] * r["input_usd_per_million"]
                    + 1500 * r["output_usd_per_million"]) / 1_000_000 for r in rows)
    reserve = sum((r["estimated_input_tokens"] * r["input_usd_per_million"]
                   + r["max_tokens"] * r["output_usd_per_million"]) / 1_000_000 for r in rows)
    result = {
        "version": "jurisdiction-expansion-pilot-transport-repair-cost-v1",
        "created_at": now(), "requests": len(rows),
        "planning_output_tokens_per_request": 1500,
        "planning_cost_usd": round(planning, 6),
        "single_attempt_max_token_reserve_usd": round(reserve, 6),
        "hard_ceiling_usd": HARD_CEILING_USD,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False, "network_inference_call_made": False,
    }
    atomic_json(OUTPUT_DIR / "cost_estimate.json", result)
    return result


def authorize(payload_sha: str, ceiling: float, confirmed: bool) -> dict[str, Any]:
    if not confirmed:
        raise RuntimeError("explicit user authorization flag is required")
    manifest = prepare()
    cost = estimate_cost()
    if payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized payload SHA-256 does not match frozen bytes")
    if float(ceiling) != float(cost["hard_ceiling_usd"]):
        raise ValueError("authorized ceiling does not match frozen cost record")
    manifest["status"] = "authorized_not_started"
    manifest["paid_run_authorized"] = True
    manifest["authorization"] = {
        "recorded_at": now(), "payload_sha256": payload_sha,
        "hard_ceiling_usd": ceiling,
        "scope": "one sequential repair attempt per transient failure",
    }
    atomic_json(OUTPUT_DIR / "manifest.json", manifest)
    return manifest


def run(ceiling: float, authorized: bool) -> dict[str, Any]:
    if not authorized:
        raise RuntimeError("--authorize-paid-run is required")
    load_env_from_file()
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is not set")
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("paid_run_authorized"):
        raise RuntimeError("transport repair has not been explicitly authorized")
    if float(ceiling) != float(manifest["authorization"]["hard_ceiling_usd"]):
        raise ValueError("runtime ceiling does not match authorization")
    if sha_file(OUTPUT_DIR / "provider_requests.jsonl") != manifest["provider_payload_sha256"]:
        raise ValueError("repair payload changed after authorization")
    repair_ledger = OUTPUT_DIR / "provider_responses.jsonl"
    existing = {r["provider_request_id"]: r for r in read_jsonl(repair_ledger)}
    for row in read_jsonl(OUTPUT_DIR / "provider_requests.jsonl"):
        if row["provider_request_id"] in existing:
            continue
        result = send_one(row, token)
        result["attempt"] = 2
        result["repair_version"] = manifest["version"]
        append_record(repair_ledger, result)
        append_record(SOURCE_DIR / "provider_responses.jsonl", result)
        existing[row["provider_request_id"]] = result
    repair_rows = list(existing.values())
    manifest["network_inference_call_made"] = True
    manifest["completed_at"] = now()
    manifest["status"] = "completed" if len(repair_rows) == manifest["n_requests"] else "incomplete"
    manifest["result"] = {
        "records": len(repair_rows),
        "successes": sum(r["status"] == "success" for r in repair_rows),
        "errors": sum(r["status"] == "error" for r in repair_rows),
        "response_sha256": sha_file(repair_ledger),
    }
    atomic_json(manifest_path, manifest)
    base = json.loads((SOURCE_DIR / "manifest.json").read_text(encoding="utf-8"))
    all_rows = read_jsonl(SOURCE_DIR / "provider_responses.jsonl")
    latest = {r["provider_request_id"]: r for r in all_rows}
    final = list(latest.values())
    base["status"] = "completed"
    base["result"] = {
        "records": len(final), "successes": sum(r["status"] == "success" for r in final),
        "errors": sum(r["status"] == "error" for r in final),
        "response_sha256": sha_file(SOURCE_DIR / "provider_responses.jsonl"),
    }
    base["transport_repair_v1"] = {
        "manifest": str(manifest_path.relative_to(ROOT)),
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "response_sha256": manifest["result"]["response_sha256"],
    }
    atomic_json(SOURCE_DIR / "manifest.json", base)
    return {"repair": manifest["result"], "combined": base["result"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "run"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare": result = prepare()
    elif args.command == "cost": result = estimate_cost()
    elif args.command == "authorize":
        if args.payload_sha is None or args.cost_ceiling is None:
            parser.error("authorize requires --payload-sha and --cost-ceiling")
        result = authorize(args.payload_sha, args.cost_ceiling, args.confirm_user_authorization)
    else:
        if args.cost_ceiling is None:
            parser.error("run requires --cost-ceiling")
        result = run(args.cost_ceiling, args.authorize_paid_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
