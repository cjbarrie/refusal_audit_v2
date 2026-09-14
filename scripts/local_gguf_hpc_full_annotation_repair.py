#!/usr/bin/env python3
"""Repair the 12 exhausted consistency conflicts in the Torch Luna v2.4 run.

This is an instrument repair, not a codebook change. It selects all and only
responses that exhausted three attempts because Luna simultaneously described
the output as incoherent/unassessable and assigned a substantive refusal.

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
from refusal_audit.response_validity.luna_v23_repair import _derive, _schema
from refusal_audit.response_validity.luna_v24_evaluation import (
    INPUT_PRICE,
    MAX_OUTPUT_TOKENS,
    MODEL,
    OUTPUT_PRICE,
    PLANNING_OUTPUT_TOKENS,
    PRICING_SOURCE,
    PROVIDER,
)
from refusal_audit.response_validity.wall_to_wall_repair_v24 import (
    ADAPTIVE_RETRY,
    MAX_REPAIR_ATTEMPTS,
    REPAIR_ADDENDUM,
    run_wall_to_wall_repair_v24,
)

SOURCE_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_full_hpc_luna_v2_4_v1"
OUTPUT_DIR = SOURCE_DIR / "repair_v1"
CODEBOOK = ROOT / "config/response_validity_decomposed_v2_4.json"
EXPECTED_SOURCE_N = 49_879
EXPECTED_COMPLETED_N = 49_867
EXPECTED_REPAIR_N = 12
VALIDATOR_ERROR = "incoherent or unassessable content cannot establish refusal"
PRICING_VERIFIED_AT = "2026-09-12"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def unresolved() -> tuple[list[dict], pd.DataFrame, dict[str, str]]:
    """Recover the complete exhausted-case universe and verify its provenance."""
    paths = {
        "source_manifest": SOURCE_DIR / "manifest.json",
        "source_requests": SOURCE_DIR / "provider_requests.jsonl",
        "source_attempts": SOURCE_DIR / "attempts.jsonl",
        "source_results": SOURCE_DIR / "results.jsonl",
        "source_run_summary": SOURCE_DIR / "run_summary.json",
        "source_response_index": SOURCE_DIR / "response_index.parquet",
        "codebook": CODEBOOK,
    }
    hashes = {name: sha_file(path) for name, path in paths.items()}
    summary = json.loads(paths["source_run_summary"].read_text(encoding="utf-8"))
    if not (
        summary.get("n_expected") == EXPECTED_SOURCE_N
        and summary.get("n_completed") == EXPECTED_COMPLETED_N
        and summary.get("n_incomplete") == EXPECTED_REPAIR_N
        and summary.get("attempts_sha256") == hashes["source_attempts"]
        and summary.get("results_sha256") == hashes["source_results"]
    ):
        raise ValueError("source annotation completion state changed")

    requests = {row["provider_request_id"]: row for row in read_jsonl(paths["source_requests"])}
    completed = {row["provider_request_id"] for row in read_jsonl(paths["source_results"])}
    groups: dict[str, list[dict]] = {}
    for record in read_jsonl(paths["source_attempts"]):
        groups.setdefault(str(record["provider_request_id"]), []).append(record)
    missing_ids = sorted(set(requests) - completed)
    if len(missing_ids) != EXPECTED_REPAIR_N:
        raise ValueError("repair universe is not exactly 12 requests")

    selected: list[dict] = []
    index_rows: list[dict] = []
    source_index = pd.read_parquet(paths["source_response_index"])
    index_by_request = source_index.set_index("provider_request_id", drop=False)
    for source_request_id in missing_ids:
        attempts = groups.get(source_request_id, [])
        if len(attempts) != 3 or any(row.get("status") == "complete" for row in attempts):
            raise ValueError("an unresolved request did not exhaust exactly three attempts")
        for attempt in attempts:
            if attempt.get("error") != VALIDATOR_ERROR:
                raise ValueError("repair candidate contains an unexpected failure")
            raw = json.loads(attempt["raw_provider_content"])
            if raw.get("output_quality") not in {"incoherent_garbled", "unassessable"}:
                raise ValueError("repair candidate lacks the quality side of the conflict")
            if raw.get("substantive_refusal") not in {"explicit", "implicit"}:
                raise ValueError("repair candidate lacks the refusal side of the conflict")

        original = requests[source_request_id]
        logical_id = sha_object({
            "source_provider_request_id": source_request_id,
            "source_attempts_sha256": hashlib.sha256(
                "".join(row["raw_provider_content_sha256"] for row in attempts).encode("utf-8")
            ).hexdigest(),
            "version": "local-gguf-hpc-full-luna-v2.4-schema-repair-v1",
        })[:24]
        repair_request_id = sha_object({
            "logical_request_id": logical_id, "model_id": MODEL,
        })[:24]
        user = original["messages"][1]["content"] + "\n\n" + REPAIR_ADDENDUM
        selected.append({
            "logical_request_id": logical_id,
            "provider_request_id": repair_request_id,
            "audit_response_id": logical_id,
            "source_provider_request_id": source_request_id,
            "source_audit_response_id": original["audit_response_id"],
            "messages": [original["messages"][0], {"role": "user", "content": user}],
            "response_schema": original["response_schema"],
            "estimated_input_tokens": len(tiktoken.get_encoding("o200k_base").encode(
                original["messages"][0]["content"] + "\n" + user + "\n"
                + json.dumps(original["response_schema"], sort_keys=True)
            )),
            "model_id": MODEL,
            "provider": {"only": [PROVIDER], "allow_fallbacks": False},
            "reasoning": {"enabled": False, "exclude": True},
            "temperature": 0,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        })
        meta = index_by_request.loc[source_request_id].to_dict()
        index_rows.append({
            **meta,
            "repair_audit_response_id": logical_id,
            "repair_provider_request_id": repair_request_id,
            "source_provider_request_id": source_request_id,
            "prior_validation_error": VALIDATOR_ERROR,
            "prior_attempts": 3,
            "prior_invalid_annotation_sha256": [
                row["raw_provider_content_sha256"] for row in attempts
            ],
        })
    return selected, pd.DataFrame(index_rows), hashes


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
            raise ValueError("repair freeze no longer matches its source run")
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
        "version": "local-gguf-hpc-full-luna-v2.4-schema-repair-v1",
        "created_at": now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": "repair exhausted logical conflicts without changing v2.4 definitions",
        "selection_rule": "all and only 12 source requests that exhausted three attempts on the incoherent/unassessable-refusal consistency rule",
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
    inputs = sum(int(row["estimated_input_tokens"]) for row in requests)
    retry_extra = len(tiktoken.get_encoding("o200k_base").encode(
        ADAPTIVE_RETRY.format(error=VALIDATOR_ERROR)
    ))
    maximum_inputs = inputs * MAX_REPAIR_ATTEMPTS + retry_extra * len(requests)
    planning = (
        maximum_inputs * INPUT_PRICE
        + len(requests) * MAX_REPAIR_ATTEMPTS * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    reserved = (
        maximum_inputs * INPUT_PRICE
        + len(requests) * MAX_REPAIR_ATTEMPTS * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    ceiling = math.ceil(max(planning * 1.5, reserved) * 4) / 4
    result = {
        "version": "local-gguf-hpc-full-luna-v2.4-schema-repair-cost-v1",
        "created_at": now(),
        "pricing_verified_at": PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests),
        "max_provider_calls": len(requests) * MAX_REPAIR_ATTEMPTS,
        "estimated_input_tokens_first_attempt": inputs,
        "planning_cost_usd_max_two_attempts": planning,
        "reserved_cost_usd_max_two_attempts": reserved,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["protocol"]["initial_provider_payload_sha256"],
        "protocol_sha256": manifest["protocol_sha256"],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (OUTPUT_DIR / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    manifest["status"] = "frozen_costed_not_authorized"
    manifest["cost_estimate"] = result
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
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
        "recorded_at": now(),
        "user_authorized": True,
        "authorization_scope": "local_gguf_hpc_full_luna_v2_4_schema_repair_v1",
        "provider_payload_sha256": payload_sha,
        "protocol_sha256": protocol_sha,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_REPAIR_N,
        "max_provider_calls": EXPECTED_REPAIR_N * MAX_REPAIR_ATTEMPTS,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest.update({
        "authorization": record,
        "paid_run_authorized": True,
        "status": "authorized_not_started",
    })
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return record


def assemble() -> dict:
    """Combine the valid source and repair results without overwriting either."""
    source_summary = json.loads((SOURCE_DIR / "run_summary.json").read_text(encoding="utf-8"))
    repair_summary = json.loads((OUTPUT_DIR / "run_summary.json").read_text(encoding="utf-8"))
    if source_summary.get("n_completed") != EXPECTED_COMPLETED_N:
        raise ValueError("source results are no longer the frozen 49,867-label set")
    if repair_summary.get("n_completed") != EXPECTED_REPAIR_N or repair_summary.get("n_incomplete") != 0:
        raise ValueError("all 12 repairs must complete before assembly")
    if sha_file(SOURCE_DIR / "results.jsonl") != source_summary.get("results_sha256"):
        raise ValueError("source result ledger changed")
    if sha_file(OUTPUT_DIR / "results.jsonl") != repair_summary.get("results_sha256"):
        raise ValueError("repair result ledger changed")

    source_results = read_jsonl(SOURCE_DIR / "results.jsonl")
    repair_results = read_jsonl(OUTPUT_DIR / "results.jsonl")
    repair_index = pd.read_parquet(OUTPUT_DIR / "repair_index.parquet")
    source_index = pd.read_parquet(SOURCE_DIR / "response_index.parquet")
    repair_to_source = dict(zip(
        repair_index["repair_provider_request_id"],
        repair_index["source_provider_request_id"],
    ))
    repair_to_source_audit = dict(zip(
        repair_index["repair_provider_request_id"],
        repair_index["audit_response_id"],
    ))
    final = [
        {**row, "annotation_source": "local_gguf_hpc_full_luna_v24_main"}
        for row in source_results
    ]
    for row in repair_results:
        repaired = dict(row)
        repaired["repair_provider_request_id"] = repaired["provider_request_id"]
        repaired["repair_audit_response_id"] = repaired["audit_response_id"]
        repaired["provider_request_id"] = repair_to_source[repaired["provider_request_id"]]
        repaired["audit_response_id"] = repair_to_source_audit[
            repaired["repair_provider_request_id"]
        ]
        repaired["annotation_source"] = "local_gguf_hpc_full_luna_v24_schema_repair"
        final.append(repaired)
    final.sort(key=lambda row: row["provider_request_id"])
    if len(final) != EXPECTED_SOURCE_N or len({row["provider_request_id"] for row in final}) != EXPECTED_SOURCE_N:
        raise ValueError("final repaired result set is not 49,879 unique source requests")
    final_path = SOURCE_DIR / "final_results.jsonl"
    write_jsonl(final_path, final)

    labels = _derive(pd.DataFrame(final))
    frame = source_index.merge(
        labels, on=["provider_request_id", "audit_response_id"], validate="one_to_one"
    )
    if frame["annotation_source"].isna().any():
        raise ValueError("final label provenance is incomplete")
    assembled_path = SOURCE_DIR / "assembled_labels.parquet"
    frame.to_parquet(assembled_path, index=False)
    summary = {
        "version": "local-gguf-hpc-full-luna-v2.4-final-v1",
        "assembled_at": now(),
        "generation_denominator": 49_920,
        "response_labels": len(frame),
        "source_provider_valid_labels": EXPECTED_COMPLETED_N,
        "schema_repaired_labels": EXPECTED_REPAIR_N,
        "empty_generation_outcomes": 28,
        "transport_or_runtime_failures": 13,
        "genuine_refusal_n": int(frame["pred_genuine_refusal"].sum()),
        "capability_failure_n": int(frame["pred_capability_failure"].sum()),
        "final_results_sha256": sha_file(final_path),
        "assembled_labels_sha256": sha_file(assembled_path),
        "component_sha256": {
            "source_results": sha_file(SOURCE_DIR / "results.jsonl"),
            "repair_results": sha_file(OUTPUT_DIR / "results.jsonl"),
        },
        "network_call_made": False,
    }
    (SOURCE_DIR / "final_annotations_manifest.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "run", "assemble"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--protocol-sha")
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare()
    elif args.command == "cost":
        result = cost()
    elif args.command == "authorize":
        if not args.payload_sha or not args.protocol_sha or args.cost_ceiling is None:
            parser.error("authorize requires payload hash, protocol hash and cost ceiling")
        result = authorize(
            args.payload_sha, args.protocol_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
    elif args.command == "run":
        if args.cost_ceiling is None:
            parser.error("run requires --cost-ceiling")
        load_env_from_file()
        result = run_wall_to_wall_repair_v24(
            ROOT, OUTPUT_DIR, min(args.workers, 24),
            args.cost_ceiling, args.authorize_paid_run,
        )
    else:
        result = assemble()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
