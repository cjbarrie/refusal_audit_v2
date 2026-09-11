#!/usr/bin/env python3
"""Freeze, cost, run, and summarize Sol v2.4 labels for the Fanar retest."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import tiktoken


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from refusal_audit.model_expansion.fanar_annotation import (  # noqa: E402
    ADOPTED_PROMPT, ADOPTED_SCHEMA, CODEBOOK, _prompt_maps,
)
from refusal_audit.model_expansion.openrouter_pilot import (  # noqa: E402
    read_jsonl, sha_object, write_jsonl,
)
from refusal_audit.response_validity.human_pilot import sha_file  # noqa: E402
from refusal_audit.response_validity.luna_v23_repair import _derive, _schema, _user  # noqa: E402
from refusal_audit.response_validity.luna_v24_evaluation import (  # noqa: E402
    MAX_ATTEMPTS, MAX_OUTPUT_TOKENS, PLANNING_OUTPUT_TOKENS, _system_v24,
)
from refusal_audit.response_validity.sol_v24_evaluation import (  # noqa: E402
    INPUT_PRICE, MODEL, OUTPUT_PRICE, PRICING_SOURCE, PRICING_VERIFIED_AT,
    PROVIDER, run_sol_v24,
)


SOURCE_DIR = ROOT / "annotations/model_expansion_v4/fanar_c2_27b_filter_retest_v1"
OUTPUT_DIR = SOURCE_DIR / "sol_v2_4_annotations_v1"
EXPECTED_RESPONSES = 16


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def prepare() -> dict:
    summary_path = SOURCE_DIR / "run_summary.json"
    results_path = SOURCE_DIR / "results.jsonl"
    summary = json.loads(summary_path.read_text())
    if not (
        summary.get("status") == "complete"
        and summary.get("attempted") == 29
        and summary.get("newly_delivered") == EXPECTED_RESPONSES
        and summary.get("repeated_provider_filters") == 13
        and summary.get("other_failures") == 0
    ):
        raise ValueError("Fanar filter retest is not the completed 16-return/13-filter run")
    rows = read_jsonl(results_path)
    if len(rows) != EXPECTED_RESPONSES:
        raise ValueError("Fanar retest results must contain 16 responses")
    prompts, prompt_hashes = _prompt_maps(ROOT)
    input_hashes = {
        "retest_summary": sha_file(summary_path),
        "retest_results": sha_file(results_path),
        **prompt_hashes,
        "v2_4_codebook": sha_file(ROOT / CODEBOOK),
        "adopted_v2_4_prompt": sha_file(ROOT / ADOPTED_PROMPT),
        "adopted_v2_4_schema": sha_file(ROOT / ADOPTED_SCHEMA),
    }
    artifacts = {
        "response_index.parquet": OUTPUT_DIR / "response_index.parquet",
        "provider_requests.jsonl": OUTPUT_DIR / "provider_requests.jsonl",
        "prompt.txt": OUTPUT_DIR / "prompt.txt",
        "response_schema.json": OUTPUT_DIR / "response_schema.json",
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("frozen Sol annotation sources changed")
        for name, digest in manifest["artifact_sha256"].items():
            if sha_file(artifacts[name]) != digest:
                raise ValueError(f"frozen annotation artifact changed: {name}")
        return manifest

    codebook = json.loads((ROOT / CODEBOOK).read_text())
    system, schema = _system_v24(codebook), _schema()
    if hashlib.sha256(system.encode()).hexdigest() != input_hashes["adopted_v2_4_prompt"]:
        raise ValueError("constructed v2.4 prompt differs from the adopted prompt")
    schema_bytes = json.dumps(schema, indent=2).encode()
    if hashlib.sha256(schema_bytes).hexdigest() != input_hashes["adopted_v2_4_schema"]:
        raise ValueError("constructed v2.4 schema differs from the adopted schema")

    encoder = tiktoken.get_encoding("o200k_base")
    requests, index = [], []
    for row in sorted(rows, key=lambda item: (item["prompt_language"], item["prompt_id"])):
        language, prompt_id = row["prompt_language"], row["prompt_id"]
        annotation = {
            "prompt_language": language,
            "prompt_text_en": prompts["en"][prompt_id]["text"],
            "prompt_text": prompts[language][prompt_id]["text"],
            "response_text": row["response_text"],
        }
        source_sha = sha_object(annotation)
        logical_id = sha_object({
            "source_provider_request_id": row["source_provider_request_id"],
            "generation_provider_request_id": row["provider_request_id"],
            "source_sha256": source_sha,
            "version": "fanar-filter-retest-sol-v2.4-v1",
        })[:24]
        user = _user(annotation, "source_response_only")
        request = {
            "logical_request_id": logical_id,
            "provider_request_id": sha_object({"logical_request_id": logical_id, "model_id": MODEL})[:24],
            "audit_response_id": logical_id,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_schema": schema,
            "estimated_input_tokens": len(encoder.encode(system + "\n" + user + "\n" + json.dumps(schema, sort_keys=True))),
            "model_id": MODEL,
            "provider": {"only": [PROVIDER], "allow_fallbacks": False},
            "reasoning": {"enabled": False, "exclude": True},
            "temperature": 0,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        }
        requests.append(request)
        index.append({
            "audit_response_id": logical_id,
            "provider_request_id": request["provider_request_id"],
            "source_sha256": source_sha,
            "prompt_id": prompt_id,
            "prompt_language": language,
            "subject_model": row["model"],
            "source_provider_request_id": row["source_provider_request_id"],
            "generation_provider_request_id": row["provider_request_id"],
            "generation_response_sha256": hashlib.sha256(row["response_text"].encode()).hexdigest(),
            **row["prompt_metadata"],
        })
    if len(requests) != EXPECTED_RESPONSES or len({row["provider_request_id"] for row in requests}) != EXPECTED_RESPONSES:
        raise ValueError("Sol payload must contain 16 unique requests")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(index).to_parquet(artifacts["response_index.parquet"], index=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    artifacts["prompt.txt"].write_text(system)
    artifacts["response_schema.json"].write_bytes(schema_bytes)
    manifest = {
        "version": "fanar-filter-retest-sol-v2.4-v1",
        "created_at": now(), "status": "frozen_not_authorized",
        "scientific_role": "frontier classification of every response newly exposed by the native Fanar filter retest",
        "n_requests": EXPECTED_RESPONSES, "input_mode": "source_response_only",
        "translation_used": False, "subject_model_blinded_in_messages": True,
        "model_id": MODEL, "provider_tag": PROVIDER, "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS, "max_attempts": MAX_ATTEMPTS,
        "reasoning_disabled": True, "allow_fallbacks": False,
        "input_sha256": input_hashes,
        "artifact_sha256": {name: sha_file(path) for name, path in artifacts.items()},
        "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "paid_run_authorized": False, "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


def cost() -> dict:
    manifest = prepare()
    requests = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    tokens = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (tokens * INPUT_PRICE + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE) / 1_000_000
    reserved = (tokens * INPUT_PRICE + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE) / 1_000_000
    ceiling = math.ceil(max(planning * 2, 0.01) * 100) / 100
    result = {
        "version": "fanar-filter-retest-sol-v2.4-cost-v1", "created_at": now(),
        "pricing_verified_at": PRICING_VERIFIED_AT, "pricing_source": PRICING_SOURCE,
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests), "estimated_input_tokens": tokens,
        "planning_cost_usd": planning, "single_attempt_reserved_cost_usd": reserved,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False, "network_call_made": False,
    }
    (OUTPUT_DIR / "cost_estimate.json").write_text(json.dumps(result, indent=2))
    return result


def authorize(payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed:
        raise ValueError("authorization requires --confirm-user-authorization")
    manifest = prepare()
    estimate = cost()
    if payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized hash differs from frozen payload")
    if float(ceiling) != float(estimate["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized ceiling differs from frozen cost estimate")
    record = {
        "authorized_at": now(), "user_authorized": True,
        "provider_payload_sha256": payload_sha, "model_id": MODEL,
        "provider_tag": PROVIDER, "n_requests": EXPECTED_RESPONSES,
        "reasoning_disabled": True, "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = record
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return record


def run(workers: int, ceiling: float, authorized: bool) -> dict:
    # Authentication failures occur before OpenRouter accepts an inference
    # request, cost nothing, and are not schema attempts.  Preserve a complete
    # copy of such an incident, then allow the frozen payload to resume after
    # the credential has been corrected.
    attempts_path = OUTPUT_DIR / "attempts.jsonl"
    results_path = OUTPUT_DIR / "results.jsonl"
    summary_path = OUTPUT_DIR / "run_summary.json"
    if attempts_path.exists() and results_path.exists():
        attempts = read_jsonl(attempts_path)
        results = read_jsonl(results_path)
        auth_only = bool(attempts) and not results and all(
            row.get("status") == "error"
            and row.get("error_type") == "AuthenticationError"
            and float(row.get("incremental_provider_cost", 0)) == 0
            for row in attempts
        )
        if auth_only:
            incident_dir = OUTPUT_DIR / "incidents" / "authentication_failure_20260911"
            incident_dir.mkdir(parents=True, exist_ok=True)
            for path in (attempts_path, results_path, summary_path):
                if path.exists():
                    archived = incident_dir / path.name
                    if not archived.exists():
                        shutil.copy2(path, archived)
            attempts_path.write_text("", encoding="utf-8")
            results_path.write_text("", encoding="utf-8")
            if summary_path.exists():
                summary_path.unlink()
            manifest_path = OUTPUT_DIR / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.setdefault("incidents", []).append({
                "type": "authentication_failure",
                "archived_under": str(incident_dir.relative_to(ROOT)),
                "n_zero_cost_rejected_attempts": len(attempts),
                "provider_cost_usd": 0.0,
                "excluded_from_schema_attempt_count": True,
            })
            manifest["status"] = "authorized_not_started"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return run_sol_v24(ROOT, OUTPUT_DIR, min(workers, 16), ceiling, authorized)


def summarize() -> dict:
    manifest = prepare()
    run_summary = json.loads((OUTPUT_DIR / "run_summary.json").read_text())
    if not (run_summary.get("n_completed") == EXPECTED_RESPONSES and run_summary.get("n_incomplete") == 0):
        raise ValueError("Sol annotations are incomplete")
    labels = _derive(pd.DataFrame(read_jsonl(OUTPUT_DIR / "results.jsonl")))
    index = pd.read_parquet(OUTPUT_DIR / "response_index.parquet")
    frame = index.merge(labels, on="audit_response_id", validate="one_to_one")
    output_path = OUTPUT_DIR / "assembled_labels.parquet"
    frame.to_parquet(output_path, index=False)
    result = {
        "version": "fanar-filter-retest-sol-v2.4-summary-v1", "created_at": now(),
        "n": len(frame), "genuine_refusal_n": int(frame.pred_genuine_refusal.sum()),
        "capability_failure_n": int(frame.pred_capability_failure.sum()),
        "refusal_unassessable_n": int(frame.substantive_refusal.eq("unassessable").sum()),
        "provider_cost_usd": run_summary.get("provider_cost_usd"),
        "artifact_sha256": {output_path.name: sha_file(output_path)},
    }
    (OUTPUT_DIR / "annotation_summary.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "run", "summarize"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--cost-ceiling-usd", type=float)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorized", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        output = prepare()
    elif args.command == "cost":
        output = cost()
    elif args.command == "authorize":
        if args.payload_sha is None or args.cost_ceiling_usd is None:
            parser.error("authorize requires --payload-sha and --cost-ceiling-usd")
        output = authorize(args.payload_sha, args.cost_ceiling_usd, args.confirm_user_authorization)
    elif args.command == "run":
        if args.cost_ceiling_usd is None:
            parser.error("run requires --cost-ceiling-usd")
        output = run(args.workers, args.cost_ceiling_usd, args.authorized)
    else:
        output = summarize()
    print(json.dumps(output, indent=2))
