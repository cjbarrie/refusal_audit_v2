#!/usr/bin/env python3
"""Guarded Luna v2.4 annotation of the 400-response Torch benchmark.

Every benchmark response is annotated on the full decomposed v2.4 codebook.
Capability-failure diagnostics never remove a response from refusal coding.

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
from local_gguf_pilot_annotation import prompt_maps
from refusal_audit.model_expansion.openrouter_pilot import read_jsonl, sha_object, write_jsonl
from refusal_audit.response_validity.human_pilot import sha_file
from refusal_audit.response_validity.luna_v23_repair import _derive, _schema, _user
from refusal_audit.response_validity.luna_v24_evaluation import (
    INPUT_PRICE, MAX_ATTEMPTS, MAX_OUTPUT_TOKENS, MODEL, OUTPUT_PRICE,
    PLANNING_OUTPUT_TOKENS, PRICING_SOURCE, PRICING_VERIFIED_AT, PROVIDER,
    _system_v24, run_luna_v24,
)

BENCHMARK_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_full_hpc_v1/benchmark"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_hpc_benchmark_luna_v2_4_v1"
CODEBOOK = ROOT / "config/response_validity_decomposed_v2_4.json"
ADOPTED_PROMPT = ROOT / "annotations/response_validity_v2_4/wall_to_wall_luna_v1/prompt.txt"
ADOPTED_SCHEMA = ROOT / "annotations/response_validity_v2_4/wall_to_wall_luna_v1/response_schema.json"
EXPECTED_RESPONSES = 400
PRIOR_COST_PER_RESPONSE = max(63.27810359000008 / 134_664, 0.7212165099999992 / 1_600)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_benchmark() -> tuple[list[dict], dict[str, str]]:
    """Load one successful terminal response per benchmark request."""
    paths = sorted(BENCHMARK_DIR.glob("task_*/results.jsonl"))
    if len(paths) != 4:
        raise ValueError("expected exactly four benchmark result ledgers")
    hashes = {f"benchmark_{path.parent.name}": sha_file(path) for path in paths}
    latest: dict[str, dict] = {}
    for path in paths:
        for row in read_jsonl(path):
            latest[str(row["request_id"])] = row
    rows = sorted(latest.values(), key=lambda row: (
        row["model"], row["prompt_id"], row["prompt_language"]
    ))
    if len(rows) != EXPECTED_RESPONSES:
        raise ValueError("benchmark does not contain exactly 400 unique responses")
    if any(row.get("error") is not None or not str(row.get("response_text") or "").strip() for row in rows):
        raise ValueError("all 400 benchmark records must have non-empty successful responses")
    keys = [(row["prompt_id"], row["prompt_language"], row["model"]) for row in rows]
    if len(set(keys)) != EXPECTED_RESPONSES:
        raise ValueError("benchmark model-language-prompt keys are not unique")
    return rows, hashes


def prepare() -> dict:
    sources, source_hashes = load_benchmark()
    prompts, prompt_hashes = prompt_maps()
    input_hashes = {
        **source_hashes, **prompt_hashes,
        "benchmark_audit": sha_file(BENCHMARK_DIR.parent / "benchmark_audit.json"),
        "v2_4_codebook": sha_file(CODEBOOK),
        "adopted_v2_4_prompt": sha_file(ADOPTED_PROMPT),
        "adopted_v2_4_schema": sha_file(ADOPTED_SCHEMA),
    }
    artifacts = {name: OUTPUT_DIR / name for name in (
        "response_index.parquet", "provider_requests.jsonl", "prompt.txt", "response_schema.json"
    )}
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("frozen benchmark annotation inputs changed")
        for name, digest in manifest["artifact_sha256"].items():
            if sha_file(artifacts[name]) != digest:
                raise ValueError(f"frozen benchmark annotation artifact changed: {name}")
        return manifest

    codebook = json.loads(CODEBOOK.read_text())
    system, schema = _system_v24(codebook), _schema()
    schema_bytes = json.dumps(schema, indent=2).encode()
    if hashlib.sha256(system.encode()).hexdigest() != input_hashes["adopted_v2_4_prompt"]:
        raise ValueError("constructed prompt differs from adopted v2.4 prompt")
    if hashlib.sha256(schema_bytes).hexdigest() != input_hashes["adopted_v2_4_schema"]:
        raise ValueError("constructed schema differs from adopted v2.4 schema")

    encoder = tiktoken.get_encoding("o200k_base")
    requests, index = [], []
    for source in sources:
        prompt_id, language = source["prompt_id"], source["prompt_language"]
        annotation_row = {
            "prompt_language": language,
            "prompt_text_en": prompts["en"][prompt_id]["text"],
            "prompt_text": prompts[language][prompt_id]["text"],
            "response_text": source["response_text"],
        }
        source_sha = sha_object(annotation_row)
        logical_id = sha_object({
            "response_key": [prompt_id, language, source["model"]],
            "source_sha256": source_sha,
            "version": "local-gguf-hpc-benchmark-luna-v2.4-v1",
        })[:24]
        user = _user(annotation_row, "source_response_only")
        request = {
            "logical_request_id": logical_id,
            "provider_request_id": sha_object({"logical_request_id": logical_id, "model_id": MODEL})[:24],
            "audit_response_id": logical_id,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_schema": schema,
            "estimated_input_tokens": len(encoder.encode(
                system + "\n" + user + "\n" + json.dumps(schema, sort_keys=True)
            )),
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
            "subject_model": source["model"],
            "subject_model_id": source["source_model"],
            "developer": source["developer"],
            "developer_jurisdiction": source["developer_jurisdiction"],
            "generation_request_id": source["request_id"],
            "generation_response_sha256": hashlib.sha256(source["response_text"].encode()).hexdigest(),
            "output_tokens": source.get("output_tokens"),
            "stop_type": source.get("stop_type"),
            "estimated_input_tokens": request["estimated_input_tokens"],
            **source.get("prompt_metadata", {}),
        })
    serialized = json.dumps([row["messages"] for row in requests], ensure_ascii=False)
    for forbidden in ("subject_model", "developer_jurisdiction", "output_tokens"):
        if forbidden in serialized:
            raise ValueError(f"selection metadata leaked into annotation messages: {forbidden}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(index).to_parquet(artifacts["response_index.parquet"], index=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    artifacts["prompt.txt"].write_text(system)
    artifacts["response_schema.json"].write_bytes(schema_bytes)
    manifest = {
        "version": "local-gguf-hpc-benchmark-luna-v2.4-v1",
        "created_at": now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": "joint refusal and capability-failure annotation of all Torch benchmark responses",
        "selection": "census of all 400 successful benchmark responses; no semantic filtering",
        "n_requests": EXPECTED_RESPONSES,
        "input_mode": "source_response_only",
        "translation_used": False,
        "subject_model_blinded_in_messages": True,
        "selection_metadata_blinded_in_messages": True,
        "joint_outcome_policy": "refusal and capability failure are independent, potentially overlapping labels",
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_attempts": MAX_ATTEMPTS,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "input_sha256": input_hashes,
        "artifact_sha256": {name: sha_file(path) for name, path in artifacts.items()},
        "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


def cost() -> dict:
    manifest = prepare()
    requests = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    inputs = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (inputs * INPUT_PRICE + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE) / 1e6
    reserve = (inputs * INPUT_PRICE + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE) / 1e6
    empirical = len(requests) * PRIOR_COST_PER_RESPONSE
    ceiling = math.ceil(max(planning * 1.5, empirical * 2) * 4) / 4
    result = {
        "version": "local-gguf-hpc-benchmark-luna-v2.4-cost-v1",
        "created_at": now(),
        "pricing_verified_at": PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests),
        "estimated_input_tokens": inputs,
        "planning_output_tokens": len(requests) * PLANNING_OUTPUT_TOKENS,
        "maximum_output_tokens_single_attempt": len(requests) * MAX_OUTPUT_TOKENS,
        "planning_cost_usd": planning,
        "single_attempt_reserved_cost_usd": reserve,
        "empirical_cost_projection_usd": empirical,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (OUTPUT_DIR / "cost_estimate.json").write_text(json.dumps(result, indent=2))
    manifest["status"] = "frozen_costed_not_authorized"
    manifest["cost_estimate"] = result
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return result


def authorize(payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest, estimate = prepare(), cost()
    if payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("payload hash mismatch")
    if float(ceiling) != float(estimate["suggested_hard_ceiling_usd"]):
        raise ValueError("ceiling mismatch")
    record = {
        "recorded_at": now(),
        "user_authorized": True,
        "authorization_scope": "local_gguf_hpc_benchmark_luna_v2_4_v1",
        "provider_payload_sha256": payload_sha,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_RESPONSES,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest.update({"authorization": record, "paid_run_authorized": True, "status": "authorized_not_started"})
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return record


def summarize() -> dict:
    run_summary = json.loads((OUTPUT_DIR / "run_summary.json").read_text())
    results_path = OUTPUT_DIR / "results.jsonl"
    if not (
        run_summary.get("n_completed") == EXPECTED_RESPONSES
        and run_summary.get("n_incomplete") == 0
        and run_summary.get("schema_gate_pass") is True
        and run_summary.get("results_sha256") == sha_file(results_path)
    ):
        raise ValueError("Luna benchmark annotations are incomplete or hash-invalid")
    labels = _derive(pd.DataFrame(read_jsonl(results_path)))
    index = pd.read_parquet(OUTPUT_DIR / "response_index.parquet")
    frame = index.merge(labels, on="audit_response_id", validate="one_to_one")
    if frame["provider_request_id_x"].ne(frame["provider_request_id_y"]).any():
        raise ValueError("annotation request IDs disagree with response index")
    frame = frame.drop(columns="provider_request_id_y").rename(
        columns={"provider_request_id_x": "provider_request_id"}
    )
    frame["wrong_language"] = frame["language_fidelity"].eq("wrong_language")
    frame["refusal_assessable"] = frame["substantive_refusal"].ne("unassessable")
    frame["joint_class"] = "neither"
    frame.loc[frame["pred_capability_failure"], "joint_class"] = "capability_failure_only"
    frame.loc[frame["pred_genuine_refusal"], "joint_class"] = "genuine_refusal_only"
    frame.loc[frame["pred_capability_failure"] & frame["pred_genuine_refusal"], "joint_class"] = "both"
    frame.loc[~frame["refusal_assessable"], "joint_class"] = "refusal_unassessable"
    label_path = OUTPUT_DIR / "assembled_labels.parquet"
    frame.to_parquet(label_path, index=False)

    def summarize_part(part: pd.DataFrame) -> pd.Series:
        n = len(part)
        definite = int(part["pred_genuine_refusal"].sum())
        unknown = int((~part["refusal_assessable"]).sum())
        assessable = int(part["refusal_assessable"].sum())
        competent = ~part["pred_capability_failure"]
        return pd.Series({
            "response_n": n,
            "genuine_refusal_n": definite,
            "refusal_unassessable_n": unknown,
            "capability_failure_n": int(part["pred_capability_failure"].sum()),
            "refusal_and_capability_failure_n": int((part["pred_genuine_refusal"] & part["pred_capability_failure"]).sum()),
            "refusal_lower_bound": definite / n,
            "refusal_upper_bound": (definite + unknown) / n,
            "refusal_rate_assessable": definite / assessable if assessable else None,
            "refusal_rate_without_capability_failure": float(part.loc[competent, "pred_genuine_refusal"].mean()) if competent.any() else None,
        })

    cell_path = OUTPUT_DIR / "outcomes_by_model_language.csv"
    grouped = frame.groupby(["subject_model", "prompt_language"], dropna=False)
    grouped.apply(summarize_part, include_groups=False).reset_index().to_csv(cell_path, index=False)
    joint_path = OUTPUT_DIR / "joint_outcome_counts.csv"
    frame.groupby(["subject_model", "prompt_language", "joint_class"], dropna=False).size().rename(
        "n"
    ).reset_index().to_csv(joint_path, index=False)
    summary = {
        "version": "local-gguf-hpc-benchmark-luna-v2.4-summary-v1",
        "created_at": now(),
        "response_labels": len(frame),
        "genuine_refusal_n": int(frame["pred_genuine_refusal"].sum()),
        "capability_failure_n": int(frame["pred_capability_failure"].sum()),
        "refusal_and_capability_failure_n": int((frame["pred_genuine_refusal"] & frame["pred_capability_failure"]).sum()),
        "refusal_unassessable_n": int((~frame["refusal_assessable"]).sum()),
        "interpretation": "benchmark diagnostics only; all responses were coded jointly and none was discarded",
        "artifact_sha256": {
            label_path.name: sha_file(label_path),
            cell_path.name: sha_file(cell_path),
            joint_path.name: sha_file(joint_path),
            results_path.name: sha_file(results_path),
        },
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "run", "summarize"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare()
    elif args.command == "cost":
        result = cost()
    elif args.command == "authorize":
        if not args.payload_sha or args.cost_ceiling is None:
            parser.error("authorize requires hash and ceiling")
        result = authorize(args.payload_sha, args.cost_ceiling, args.confirm_user_authorization)
    elif args.command == "run":
        if args.cost_ceiling is None:
            parser.error("run requires --cost-ceiling")
        load_env_from_file()
        result = run_luna_v24(
            ROOT, OUTPUT_DIR, min(args.workers, 32), args.cost_ceiling, args.authorize_paid_run
        )
    else:
        result = summarize()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
