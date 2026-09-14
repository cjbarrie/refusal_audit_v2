#!/usr/bin/env python3
"""Guarded Luna v2.4 annotation of the local Fanar-1 9B Torch pilot.

All 200 generation records remain in the denominator. Only the 196 successful,
non-empty responses are sent to Luna. The four Hindi generation failures stay
explicit and are never treated as semantic refusals or capability failures.

Technical record: docs/FANAR_EXPERIMENTS_V1.md
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
    INPUT_PRICE,
    MAX_ATTEMPTS,
    MAX_OUTPUT_TOKENS,
    MODEL,
    OUTPUT_PRICE,
    PLANNING_OUTPUT_TOKENS,
    PRICING_SOURCE,
    PRICING_VERIFIED_AT,
    PROVIDER,
    _system_v24,
    run_luna_v24,
)

GENERATION_DIR = ROOT / "annotations/model_expansion_v4/fanar_1_9b_local_pilot_hpc_v1"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/fanar_1_9b_local_pilot_luna_v2_4_v1"
CODEBOOK = ROOT / "config/response_validity_decomposed_v2_4.json"
ADOPTED_PROMPT = ROOT / "annotations/response_validity_v2_4/wall_to_wall_luna_v1/prompt.txt"
ADOPTED_SCHEMA = ROOT / "annotations/response_validity_v2_4/wall_to_wall_luna_v1/response_schema.json"
EXPECTED_GENERATIONS = 200
EXPECTED_RESPONSES = 196
EXPECTED_FAILURES = 4
EXPECTED_MODEL = "fanar-1-9b-instruct-local-q8"
EXPECTED_LANGUAGES = {"en", "zh", "ar", "ru", "hi"}
PRIOR_COST_PER_RESPONSE = max(63.27810359000008 / 134_664, 0.7212165099999992 / 1_600)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_sources() -> tuple[list[dict], pd.DataFrame, dict[str, str]]:
    """Verify the transferred Torch ledgers and separate text from failures."""
    base_paths = {
        "generation_manifest": GENERATION_DIR / "manifest.json",
        "generation_audit": GENERATION_DIR / "audit.json",
        "generation_requests": GENERATION_DIR / "requests.jsonl",
        "generation_task_map": GENERATION_DIR / "task_map.json",
    }
    result_paths = sorted(GENERATION_DIR.glob("tasks/task_*/results.jsonl"))
    if len(result_paths) != 5:
        raise ValueError("expected exactly five Fanar language result ledgers")
    hashes = {name: sha_file(path) for name, path in base_paths.items()}
    hashes.update({f"results_{path.parent.name}": sha_file(path) for path in result_paths})

    manifest = json.loads(base_paths["generation_manifest"].read_text(encoding="utf-8"))
    audit = json.loads(base_paths["generation_audit"].read_text(encoding="utf-8"))
    if manifest.get("model") != EXPECTED_MODEL or manifest.get("n_requests") != EXPECTED_GENERATIONS:
        raise ValueError("Fanar generation manifest does not match the frozen pilot")
    expected_audit = {
        "complete": True,
        "expected_requests": EXPECTED_GENERATIONS,
        "result_records": EXPECTED_GENERATIONS,
        "nonempty_responses": EXPECTED_RESPONSES,
        "terminal_errors": EXPECTED_FAILURES,
        "missing_request_records": 0,
    }
    if any(audit.get(key) != value for key, value in expected_audit.items()):
        raise ValueError("Fanar generation audit does not match the accepted counts")

    requests = {row["request_id"]: row for row in read_jsonl(base_paths["generation_requests"])}
    results: dict[str, dict] = {}
    for path in result_paths:
        for row in read_jsonl(path):
            results[row["request_id"]] = row
    if len(requests) != EXPECTED_GENERATIONS or set(requests) != set(results):
        raise ValueError("Fanar request and result ledgers do not have identical 200-key coverage")

    sources: list[dict] = []
    outcomes: list[dict] = []
    for request_id, request in requests.items():
        result = results[request_id]
        text = str(result.get("response_text") or "")
        available = result.get("error") is None and bool(text.strip())
        outcomes.append({
            "generation_request_id": request_id,
            "prompt_id": request["prompt_id"],
            "prompt_language": request["prompt_language"],
            "subject_model": request["model"],
            "subject_model_id": request["source_model"],
            "developer": request["developer"],
            "developer_jurisdiction": request["developer_jurisdiction"],
            "response_available": available,
            "generation_error": result.get("error"),
            "output_tokens": result.get("output_tokens"),
            "pilot_band": request["pilot_band"],
            **request.get("prompt_metadata", {}),
        })
        if available:
            sources.append({"request": request, "response": result})

    outcome_frame = pd.DataFrame(outcomes).sort_values(
        ["prompt_language", "prompt_id"]
    ).reset_index(drop=True)
    if len(sources) != EXPECTED_RESPONSES:
        raise ValueError("Fanar response-bearing count is not 196")
    keys = [(x["request"]["prompt_id"], x["request"]["prompt_language"], x["request"]["model"]) for x in sources]
    if len(set(keys)) != EXPECTED_RESPONSES:
        raise ValueError("Fanar response-bearing keys are not unique")
    if set(outcome_frame["prompt_language"]) != EXPECTED_LANGUAGES:
        raise ValueError("Fanar generation denominator does not cover all five languages")
    return sources, outcome_frame, hashes


def prepare() -> dict:
    sources, outcomes, source_hashes = load_sources()
    prompts, prompt_hashes = prompt_maps()
    input_hashes = {
        **source_hashes,
        **prompt_hashes,
        "v2_4_codebook": sha_file(CODEBOOK),
        "adopted_v2_4_prompt": sha_file(ADOPTED_PROMPT),
        "adopted_v2_4_schema": sha_file(ADOPTED_SCHEMA),
    }
    artifacts = {name: OUTPUT_DIR / name for name in (
        "generation_outcomes.parquet",
        "response_index.parquet",
        "provider_requests.jsonl",
        "prompt.txt",
        "response_schema.json",
    )}
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("frozen Fanar annotation inputs changed")
        for name, digest in manifest["artifact_sha256"].items():
            if sha_file(artifacts[name]) != digest:
                raise ValueError(f"frozen Fanar annotation artifact changed: {name}")
        return manifest

    codebook = json.loads(CODEBOOK.read_text(encoding="utf-8"))
    system, schema = _system_v24(codebook), _schema()
    schema_bytes = json.dumps(schema, indent=2).encode()
    if hashlib.sha256(system.encode()).hexdigest() != input_hashes["adopted_v2_4_prompt"]:
        raise ValueError("constructed prompt differs from the adopted v2.4 prompt")
    if hashlib.sha256(schema_bytes).hexdigest() != input_hashes["adopted_v2_4_schema"]:
        raise ValueError("constructed schema differs from the adopted v2.4 schema")

    encoder = tiktoken.get_encoding("o200k_base")
    requests: list[dict] = []
    index: list[dict] = []
    for item in sorted(sources, key=lambda x: (
        x["request"]["prompt_id"], x["request"]["prompt_language"]
    )):
        source, response = item["request"], item["response"]
        prompt_id, language = source["prompt_id"], source["prompt_language"]
        annotation_row = {
            "prompt_language": language,
            "prompt_text_en": prompts["en"][prompt_id]["text"],
            "prompt_text": prompts[language][prompt_id]["text"],
            "response_text": response["response_text"],
        }
        source_sha = sha_object(annotation_row)
        logical_id = sha_object({
            "response_key": [prompt_id, language, source["model"]],
            "source_sha256": source_sha,
            "version": "fanar-1-9b-local-pilot-luna-v2.4-v1",
        })[:24]
        user = _user(annotation_row, "source_response_only")
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
            "subject_model": source["model"],
            "subject_model_id": source["source_model"],
            "developer": source["developer"],
            "developer_jurisdiction": source["developer_jurisdiction"],
            "generation_request_id": source["request_id"],
            "generation_response_sha256": hashlib.sha256(response["response_text"].encode()).hexdigest(),
            "output_tokens": response.get("output_tokens"),
            "stop_type": response.get("stop_type"),
            "pilot_band": source["pilot_band"],
            "estimated_input_tokens": request["estimated_input_tokens"],
            **source.get("prompt_metadata", {}),
        })
    if len(requests) != EXPECTED_RESPONSES or len({r["provider_request_id"] for r in requests}) != EXPECTED_RESPONSES:
        raise ValueError("Fanar annotation request count or uniqueness failure")
    serialized = json.dumps([r["messages"] for r in requests], ensure_ascii=False)
    for forbidden in (EXPECTED_MODEL, "pilot_band", "developer_jurisdiction"):
        if forbidden in serialized:
            raise ValueError(f"selection metadata leaked into annotation messages: {forbidden}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    outcomes.to_parquet(artifacts["generation_outcomes.parquet"], index=False)
    pd.DataFrame(index).to_parquet(artifacts["response_index.parquet"], index=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    artifacts["prompt.txt"].write_text(system, encoding="utf-8")
    artifacts["response_schema.json"].write_bytes(schema_bytes)
    manifest = {
        "version": "fanar-1-9b-local-pilot-luna-v2.4-v1",
        "created_at": now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": "blinded v2.4 annotation for the local Fanar admission pilot",
        "selection": "census of all 196 response-bearing records from the frozen 200-generation pilot",
        "generation_denominator": EXPECTED_GENERATIONS,
        "response_bearing_requests": EXPECTED_RESPONSES,
        "technical_generation_outcomes": EXPECTED_FAILURES,
        "technical_outcome_policy": "retained in generation denominator; not sent to a text classifier",
        "input_mode": "source_response_only",
        "translation_used": False,
        "subject_model_blinded_in_messages": True,
        "selection_metadata_blinded_in_messages": True,
        "joint_outcome_policy": "refusal and capability failure are independent and may overlap",
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_RESPONSES,
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
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
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
        "version": "fanar-1-9b-local-pilot-luna-v2.4-cost-v1",
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
        "ceiling_rule": "round_up_to_$0.25(max(1.5*planning, 2*empirical))",
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (OUTPUT_DIR / "cost_estimate.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    manifest["status"] = "frozen_costed_not_authorized"
    manifest["cost_estimate"] = result
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
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
        "authorization_scope": "fanar_1_9b_local_pilot_luna_v2_4_v1",
        "provider_payload_sha256": payload_sha,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_RESPONSES,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest.update({"authorization": record, "paid_run_authorized": True, "status": "authorized_not_started"})
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return record


def summarize() -> dict:
    run_summary = json.loads((OUTPUT_DIR / "run_summary.json").read_text(encoding="utf-8"))
    results_path = OUTPUT_DIR / "results.jsonl"
    if not (
        run_summary.get("n_completed") == EXPECTED_RESPONSES
        and run_summary.get("n_incomplete") == 0
        and run_summary.get("schema_gate_pass") is True
        and run_summary.get("results_sha256") == sha_file(results_path)
    ):
        raise ValueError("Fanar Luna annotations are incomplete or hash-invalid")
    labels = _derive(pd.DataFrame(read_jsonl(results_path)))
    index = pd.read_parquet(OUTPUT_DIR / "response_index.parquet")
    frame = index.merge(labels, on="audit_response_id", validate="one_to_one")
    if frame["provider_request_id_x"].ne(frame["provider_request_id_y"]).any():
        raise ValueError("annotation request IDs disagree with the response index")
    frame = frame.drop(columns="provider_request_id_y").rename(columns={"provider_request_id_x": "provider_request_id"})
    frame["wrong_language"] = frame["language_fidelity"].eq("wrong_language")
    frame["refusal_assessable"] = frame["substantive_refusal"].ne("unassessable")
    label_path = OUTPUT_DIR / "assembled_labels.parquet"
    frame.to_parquet(label_path, index=False)
    cell_path = OUTPUT_DIR / "outcomes_by_language.csv"
    frame.groupby("prompt_language", dropna=False).agg(
        response_n=("audit_response_id", "size"),
        genuine_refusal_n=("pred_genuine_refusal", "sum"),
        genuine_refusal_rate=("pred_genuine_refusal", "mean"),
        capability_failure_n=("pred_capability_failure", "sum"),
        capability_failure_rate=("pred_capability_failure", "mean"),
        wrong_language_n=("wrong_language", "sum"),
        wrong_language_rate=("wrong_language", "mean"),
        refusal_unassessable_n=("refusal_assessable", lambda x: int((~x).sum())),
    ).reset_index().to_csv(cell_path, index=False)
    summary = {
        "version": "fanar-1-9b-local-pilot-luna-v2.4-summary-v1",
        "created_at": now(),
        "generation_denominator": EXPECTED_GENERATIONS,
        "response_labels": len(frame),
        "technical_generation_outcomes": EXPECTED_FAILURES,
        "genuine_refusal_n": int(frame["pred_genuine_refusal"].sum()),
        "capability_failure_n": int(frame["pred_capability_failure"].sum()),
        "refusal_unassessable_n": int((~frame["refusal_assessable"]).sum()),
        "interpretation": "enriched admission-pilot diagnostics; not corpus prevalence estimates",
        "artifact_sha256": {
            label_path.name: sha_file(label_path),
            cell_path.name: sha_file(cell_path),
            results_path.name: sha_file(results_path),
        },
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
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
            parser.error("authorize requires --payload-sha and --cost-ceiling")
        result = authorize(args.payload_sha, args.cost_ceiling, args.confirm_user_authorization)
    elif args.command == "run":
        if args.cost_ceiling is None:
            parser.error("run requires --cost-ceiling")
        load_env_from_file()
        result = run_luna_v24(ROOT, OUTPUT_DIR, min(args.workers, 32), args.cost_ceiling, args.authorize_paid_run)
    else:
        result = summarize()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
