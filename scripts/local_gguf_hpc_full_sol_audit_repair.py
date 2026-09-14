#!/usr/bin/env python3
"""Repair exhausted consistency conflicts in the Torch Sol v2.4 audit.

This is an instrument repair, not a codebook change. It preserves the three
invalid base drafts, re-presents the source response with the established
v2.4 clarification, and permits at most two new Sol attempts.

Technical record: docs/HPC_LOCAL_GGUF_FULL_V1.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import tiktoken

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from env_utils import load_env_from_file
from refusal_audit.model_expansion.openrouter_pilot import read_jsonl, sha_object, write_jsonl
from refusal_audit.response_validity.human_pilot import sha_file
from refusal_audit.response_validity.luna_v24_evaluation import (
    MAX_OUTPUT_TOKENS,
    PLANNING_OUTPUT_TOKENS,
)
from refusal_audit.response_validity.sol_v24_evaluation import (
    INPUT_PRICE,
    MODEL,
    OUTPUT_PRICE,
    PRICING_SOURCE,
    PROVIDER,
)
from refusal_audit.response_validity.wall_to_wall_repair_v24 import (
    ADAPTIVE_RETRY,
    MAX_REPAIR_ATTEMPTS,
    REPAIR_ADDENDUM,
    run_wall_to_wall_repair_v24,
)

SOURCE_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_full_hpc_sol_v2_4_audit_v1"
OUTPUT_DIR = SOURCE_DIR / "repair_v1"
EXPECTED_SOURCE_N = 1_335
EXPECTED_COMPLETED_N = 1_328
EXPECTED_REPAIR_N = 7
VALIDATOR_ERROR = "incoherent or unassessable content cannot establish refusal"
PRICING_VERIFIED_AT = "2026-09-12"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def unresolved() -> tuple[list[dict], pd.DataFrame, dict[str, str]]:
    paths = {
        "source_manifest": SOURCE_DIR / "manifest.json",
        "source_requests": SOURCE_DIR / "provider_requests.jsonl",
        "source_attempts": SOURCE_DIR / "attempts.jsonl",
        "source_results": SOURCE_DIR / "results.jsonl",
        "source_summary": SOURCE_DIR / "run_summary.json",
        "source_index": SOURCE_DIR / "response_index.parquet",
    }
    hashes = {name: sha_file(path) for name, path in paths.items()}
    summary = json.loads(paths["source_summary"].read_text(encoding="utf-8"))
    if not (
        summary.get("n_expected") == EXPECTED_SOURCE_N
        and summary.get("n_completed") == EXPECTED_COMPLETED_N
        and summary.get("n_incomplete") == EXPECTED_REPAIR_N
        and summary.get("attempts_sha256") == hashes["source_attempts"]
        and summary.get("results_sha256") == hashes["source_results"]
    ):
        raise ValueError("source Sol audit completion state changed")

    requests = {row["provider_request_id"]: row for row in read_jsonl(paths["source_requests"])}
    completed = {row["provider_request_id"] for row in read_jsonl(paths["source_results"])}
    attempts: dict[str, list[dict]] = {}
    for row in read_jsonl(paths["source_attempts"]):
        attempts.setdefault(str(row["provider_request_id"]), []).append(row)
    missing = sorted(set(requests) - completed)
    if len(missing) != EXPECTED_REPAIR_N:
        raise ValueError("repair universe is not exactly seven requests")

    source_index = pd.read_parquet(paths["source_index"]).set_index(
        "provider_request_id", drop=False
    )
    repair_requests, index_rows = [], []
    encoding = tiktoken.get_encoding("o200k_base")
    for source_request_id in missing:
        drafts = attempts.get(source_request_id, [])
        if len(drafts) != 3 or any(row.get("error") != VALIDATOR_ERROR for row in drafts):
            raise ValueError("repair candidate did not exhaust the expected validator rule")
        for draft in drafts:
            raw = json.loads(draft["raw_provider_content"])
            if raw.get("output_quality") not in {"incoherent_garbled", "unassessable"}:
                raise ValueError("repair candidate lacks the quality side of the conflict")
            if raw.get("substantive_refusal") not in {"explicit", "implicit"}:
                raise ValueError("repair candidate lacks the refusal side of the conflict")

        original = requests[source_request_id]
        logical_id = sha_object({
            "source_provider_request_id": source_request_id,
            "source_drafts_sha256": hashlib.sha256(
                "".join(row["raw_provider_content_sha256"] for row in drafts).encode()
            ).hexdigest(),
            "version": "local-gguf-hpc-full-sol-v2.4-audit-repair-v1",
        })[:24]
        repair_id = sha_object({"logical_request_id": logical_id, "model_id": MODEL})[:24]
        user = original["messages"][1]["content"] + "\n\n" + REPAIR_ADDENDUM
        request = {
            "logical_request_id": logical_id,
            "provider_request_id": repair_id,
            "audit_response_id": logical_id,
            "source_provider_request_id": source_request_id,
            "source_audit_response_id": original["audit_response_id"],
            "messages": [original["messages"][0], {"role": "user", "content": user}],
            "response_schema": original["response_schema"],
            "model_id": MODEL,
            "provider": {"only": [PROVIDER], "allow_fallbacks": False},
            "reasoning": {"enabled": False, "exclude": True},
            "temperature": 0,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        }
        request["estimated_input_tokens"] = len(encoding.encode(
            request["messages"][0]["content"] + "\n" + user + "\n"
            + json.dumps(request["response_schema"], sort_keys=True)
        ))
        repair_requests.append(request)
        meta = source_index.loc[source_request_id].to_dict()
        index_rows.append({
            **meta,
            "repair_audit_response_id": logical_id,
            "repair_provider_request_id": repair_id,
            "source_provider_request_id": source_request_id,
            "prior_validation_error": VALIDATOR_ERROR,
            "prior_attempts": 3,
            "prior_invalid_annotation_sha256": [
                row["raw_provider_content_sha256"] for row in drafts
            ],
        })
    return repair_requests, pd.DataFrame(index_rows), hashes


def prepare() -> dict:
    requests, index, input_hashes = unresolved()
    manifest_path = OUTPUT_DIR / "manifest.json"
    artifacts = {name: OUTPUT_DIR / name for name in (
        "provider_requests.jsonl", "repair_index.parquet", "prompt.txt",
        "adaptive_retry.txt", "response_schema.json",
    )}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen repair no longer matches its source audit")
        for name, digest in manifest.get("artifact_sha256", {}).items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != digest:
                raise ValueError(f"frozen repair artifact changed: {name}")
        return manifest
    if OUTPUT_DIR.exists() and any(OUTPUT_DIR.iterdir()):
        raise FileExistsError(f"nonempty unmanifested repair directory: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    index.to_parquet(artifacts["repair_index.parquet"], index=False)
    artifacts["prompt.txt"].write_text(
        requests[0]["messages"][0]["content"] + "\n\n" + REPAIR_ADDENDUM,
        encoding="utf-8",
    )
    artifacts["adaptive_retry.txt"].write_text(ADAPTIVE_RETRY, encoding="utf-8")
    artifacts["response_schema.json"].write_text(
        json.dumps(requests[0]["response_schema"], indent=2), encoding="utf-8"
    )
    protocol = {
        "initial_provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "adaptive_retry_template_sha256": sha_file(artifacts["adaptive_retry.txt"]),
        "max_repair_attempts": MAX_REPAIR_ATTEMPTS,
        "retry_condition": "only a failed API call or v2.4 validation failure",
    }
    manifest = {
        "version": "local-gguf-hpc-full-sol-v2.4-audit-repair-v1",
        "created_at": now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": "repair exhausted Sol audit conflicts without changing v2.4 definitions",
        "selection_rule": "all and only seven source requests that exhausted the incoherent/unassessable-refusal consistency rule",
        "n_requests": EXPECTED_REPAIR_N,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "protocol": protocol,
        "protocol_sha256": sha_object(protocol),
        "input_sha256": input_hashes,
        "artifact_sha256": {name: sha_file(path) for name, path in artifacts.items()},
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def cost() -> dict:
    manifest = prepare()
    requests = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    first_inputs = sum(int(row["estimated_input_tokens"]) for row in requests)
    retry_extra = len(tiktoken.get_encoding("o200k_base").encode(
        ADAPTIVE_RETRY.format(error=VALIDATOR_ERROR)
    ))
    maximum_inputs = first_inputs * MAX_REPAIR_ATTEMPTS + retry_extra * len(requests)
    planning = (
        maximum_inputs * INPUT_PRICE
        + len(requests) * MAX_REPAIR_ATTEMPTS * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    reserve = (
        maximum_inputs * INPUT_PRICE
        + len(requests) * MAX_REPAIR_ATTEMPTS * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    ceiling = math.ceil(max(planning * 1.5, reserve) * 4) / 4
    result = {
        "version": "local-gguf-hpc-full-sol-v2.4-audit-repair-cost-v1",
        "created_at": now(),
        "pricing_verified_at": PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests),
        "max_provider_calls": len(requests) * MAX_REPAIR_ATTEMPTS,
        "estimated_input_tokens_first_attempt": first_inputs,
        "planning_cost_usd_max_two_attempts": planning,
        "reserved_cost_usd_max_two_attempts": reserve,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["protocol"]["initial_provider_payload_sha256"],
        "protocol_sha256": manifest["protocol_sha256"],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (OUTPUT_DIR / "cost_estimate.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    manifest.update({"status": "frozen_costed_not_authorized", "cost_estimate": result})
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


def authorize(payload_sha: str, protocol_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest, estimate = prepare(), cost()
    if payload_sha != manifest["protocol"]["initial_provider_payload_sha256"]:
        raise ValueError("payload hash mismatch")
    if protocol_sha != manifest["protocol_sha256"]:
        raise ValueError("protocol hash mismatch")
    if float(ceiling) != float(estimate["suggested_hard_ceiling_usd"]):
        raise ValueError("cost ceiling mismatch")
    record = {
        "recorded_at": now(), "user_authorized": True,
        "authorization_scope": "local_gguf_hpc_full_sol_v2_4_audit_repair_v1",
        "provider_payload_sha256": payload_sha, "protocol_sha256": protocol_sha,
        "model_id": MODEL, "provider_tag": PROVIDER,
        "n_requests": EXPECTED_REPAIR_N,
        "max_provider_calls": EXPECTED_REPAIR_N * MAX_REPAIR_ATTEMPTS,
        "reasoning_disabled": True, "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest.update({"authorization": record, "paid_run_authorized": True,
                     "status": "authorized_not_started"})
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return record


def assemble() -> dict:
    source_summary = json.loads((SOURCE_DIR / "run_summary.json").read_text())
    repair_summary = json.loads((OUTPUT_DIR / "run_summary.json").read_text())
    if source_summary.get("n_completed") != EXPECTED_COMPLETED_N:
        raise ValueError("source Sol results changed")
    if repair_summary.get("n_completed") != EXPECTED_REPAIR_N:
        raise ValueError("all seven repairs must complete before assembly")
    source = read_jsonl(SOURCE_DIR / "results.jsonl")
    repaired = read_jsonl(OUTPUT_DIR / "results.jsonl")
    index = pd.read_parquet(OUTPUT_DIR / "repair_index.parquet")
    repair_to_source = dict(zip(index.repair_provider_request_id, index.source_provider_request_id))
    repair_to_audit = dict(zip(index.repair_provider_request_id, index.audit_response_id))
    final = [{**row, "annotation_source": "torch_sol_v24_audit_main"} for row in source]
    for row in repaired:
        row = dict(row)
        repair_id = row["provider_request_id"]
        row.update({
            "repair_provider_request_id": repair_id,
            "repair_audit_response_id": row["audit_response_id"],
            "provider_request_id": repair_to_source[repair_id],
            "audit_response_id": repair_to_audit[repair_id],
            "annotation_source": "torch_sol_v24_audit_schema_repair",
        })
        final.append(row)
    final.sort(key=lambda row: row["provider_request_id"])
    if len(final) != EXPECTED_SOURCE_N or len({r["provider_request_id"] for r in final}) != EXPECTED_SOURCE_N:
        raise ValueError("final Sol audit is not 1,335 unique requests")
    final_path = SOURCE_DIR / "final_results.jsonl"
    write_jsonl(final_path, final)
    summary = {
        "version": "local-gguf-hpc-full-sol-v2.4-audit-final-v1",
        "assembled_at": now(), "n_completed": len(final), "n_incomplete": 0,
        "schema_gate_pass": True,
        "source_provider_valid_labels": EXPECTED_COMPLETED_N,
        "schema_repaired_labels": EXPECTED_REPAIR_N,
        "provider_cost_usd": float(source_summary["provider_cost_usd"]) + float(repair_summary["provider_cost_usd"]),
        "final_results_sha256": sha_file(final_path),
        "component_sha256": {
            "source_results": sha_file(SOURCE_DIR / "results.jsonl"),
            "repair_results": sha_file(OUTPUT_DIR / "results.jsonl"),
        },
        "network_call_made": False,
    }
    (SOURCE_DIR / "final_annotations_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "run", "assemble"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--protocol-sha")
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--workers", type=int, default=7)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare()
    elif args.command == "cost":
        result = cost()
    elif args.command == "authorize":
        if not args.payload_sha or not args.protocol_sha or args.cost_ceiling is None:
            parser.error("authorize requires payload hash, protocol hash and ceiling")
        result = authorize(args.payload_sha, args.protocol_sha, args.cost_ceiling,
                           args.confirm_user_authorization)
    elif args.command == "run":
        if args.cost_ceiling is None:
            parser.error("run requires --cost-ceiling")
        load_env_from_file()
        result = run_wall_to_wall_repair_v24(
            ROOT, OUTPUT_DIR, min(args.workers, 24), args.cost_ceiling,
            args.authorize_paid_run, expected_model=MODEL,
            expected_provider=PROVIDER, input_price=INPUT_PRICE,
            output_price=OUTPUT_PRICE,
        )
    else:
        result = assemble()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
