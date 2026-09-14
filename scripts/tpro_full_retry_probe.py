#!/usr/bin/env python3
"""Guarded 200-request stability probe for unresolved T-pro full-run keys.

The probe uses the frozen recovery output, sends each selected key at most once,
and retains its own append-only ledger. It never edits the original T-pro run.

Technical record: docs/JURISDICTION_MODEL_EXPANSION_V1.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import jurisdiction_expansion_full as base
import tpro_full_recovery as recovery
from env_utils import load_env_from_file
from jurisdiction_expansion_smoke import atomic_json, read_jsonl, sha_file, write_jsonl

SOURCE = recovery.OUTPUT
OUTPUT = SOURCE / "retry_probe_v1"
EXPECTED = 200
HARD_CEILING = 2.0


def prepare() -> dict:
    parent = recovery.recover()
    source_path = SOURCE / "retry_probe_provider_requests.jsonl"
    rows = read_jsonl(source_path)
    if len(rows) != EXPECTED or len({row["provider_request_id"] for row in rows}) != EXPECTED:
        raise ValueError("retry probe is not the frozen 200 unique requests")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    payload_path = OUTPUT / "provider_requests.jsonl"
    if payload_path.exists() and sha_file(payload_path) != sha_file(source_path):
        raise ValueError("existing retry-probe payload differs from recovered freeze")
    write_jsonl(payload_path, rows)
    existing = OUTPUT / "manifest.json"
    manifest = json.loads(existing.read_text()) if existing.exists() else {}
    manifest.update({
        "version": "t-pro-full-retry-probe-v1",
        "status": manifest.get("status", "frozen_not_authorized"),
        "scientific_role": "route-stability test before residual full-run repair",
        "selection": parent["retry_probe_contract"]["selection"],
        "selection_seed": parent["retry_probe_contract"]["selection_seed"],
        "n_requests": EXPECTED,
        "requests_per_language": 40,
        "model_id": "t-tech/T-pro-it-2.0:featherless-ai",
        "provider_tag": "featherless-ai",
        "temperature": 1.0,
        "max_tokens": 5000,
        "reasoning_disabled": True,
        "provider_fallbacks_disabled": True,
        "max_attempts_per_request": 1,
        "maximum_workers": 4,
        "provider_payload_sha256": sha_file(payload_path),
        "source_recovery_manifest_sha256": sha_file(SOURCE / "manifest.json"),
        "cost_estimate": parent["retry_probe_contract"],
        "paid_run_authorized": manifest.get("paid_run_authorized", False),
        "network_call_made": manifest.get("network_call_made", False),
    })
    atomic_json(existing, manifest)
    return manifest


def authorize(payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization is required")
    manifest = prepare()
    if payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("payload hash mismatch")
    if float(ceiling) != HARD_CEILING:
        raise ValueError("cost ceiling mismatch")
    record = {
        "user_authorized": True,
        "provider_payload_sha256": payload_sha,
        "n_requests": EXPECTED,
        "model_id": manifest["model_id"],
        "provider_tag": manifest["provider_tag"],
        "cost_ceiling_usd": ceiling,
    }
    manifest.update({"authorization": record, "paid_run_authorized": True,
                     "status": "authorized_not_started"})
    atomic_json(OUTPUT / "manifest.json", manifest)
    return record


def run(ceiling: float, authorized: bool) -> dict:
    if not authorized:
        raise RuntimeError("--authorize-paid-run is required")
    manifest = prepare()
    if not manifest.get("paid_run_authorized"):
        raise RuntimeError("retry probe is not authorized")
    if float(ceiling) != HARD_CEILING:
        raise ValueError("runtime ceiling mismatch")
    load_env_from_file()
    secret = os.environ.get("HF_TOKEN")
    if not secret:
        raise RuntimeError("HF_TOKEN is not set")
    rows = read_jsonl(OUTPUT / "provider_requests.jsonl")
    attempts_path = OUTPUT / "attempts.jsonl"
    prior = read_jsonl(attempts_path) if attempts_path.exists() else []
    done = {row["provider_request_id"] for row in prior}
    queue = [row for row in rows if row["provider_request_id"] not in done]
    if prior and base.actual_cost(prior, base.MODELS["t-pro-it-2.0"]) > ceiling:
        raise RuntimeError("recorded cost already exceeds ceiling")

    # The authorized probe is small. Four workers match the route's last safe
    # concurrency, and each selected key receives exactly one new call.
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(base.send, row, secret, 3): row for row in queue}
        for future in as_completed(futures):
            record = future.result()
            base.append(attempts_path, record)

    attempts = read_jsonl(attempts_path)
    latest = {row["provider_request_id"]: row for row in attempts}
    results = [row for row in latest.values() if row.get("status") == "success"]
    write_jsonl(OUTPUT / "results.jsonl", sorted(
        results, key=lambda row: (row["prompt_id"], row["prompt_language"])
    ))
    errors = [row for row in latest.values() if row.get("status") != "success"]
    actual = base.actual_cost(attempts, base.MODELS["t-pro-it-2.0"])
    if actual > ceiling:
        raise RuntimeError("provider-reported cost exceeds authorized ceiling")
    summary = {
        "n_expected": EXPECTED,
        "n_terminal": len(latest),
        "n_success": len(results),
        "n_error": len(errors),
        "success_rate": len(results) / EXPECTED,
        "provider_cost_usd": actual,
        "attempts_sha256": sha_file(attempts_path),
        "results_sha256": sha_file(OUTPUT / "results.jsonl"),
    }
    manifest.update({"status": "completed", "network_call_made": True,
                     "run_summary": summary})
    atomic_json(OUTPUT / "manifest.json", manifest)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "run"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command in {"prepare", "cost"}:
        result = prepare()
        if args.command == "cost":
            result = result["cost_estimate"]
    elif args.command == "authorize":
        if not args.payload_sha or args.cost_ceiling is None:
            parser.error("authorize requires --payload-sha and --cost-ceiling")
        result = authorize(args.payload_sha, args.cost_ceiling,
                           args.confirm_user_authorization)
    else:
        if args.cost_ceiling is None:
            parser.error("run requires --cost-ceiling")
        result = run(args.cost_ceiling, args.authorize_paid_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
