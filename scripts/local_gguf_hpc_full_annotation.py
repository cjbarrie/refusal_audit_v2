#!/usr/bin/env python3
"""Guarded Luna v2.4 annotation of the completed Torch full-corpus run.

The semantic annotation census contains every successful, non-empty response
from the four-model Torch ledger. Empty responses and transport/runtime errors
remain explicit generation outcomes; they are never converted into semantic
labels or silently removed from the generation denominator.

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
    INPUT_PRICE,
    MAX_ATTEMPTS,
    MAX_OUTPUT_TOKENS,
    MODEL,
    OUTPUT_PRICE,
    PLANNING_OUTPUT_TOKENS,
    PRICING_SOURCE,
    PROVIDER,
    _system_v24,
    run_luna_v24,
)

GENERATION_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_full_hpc_v1"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_full_hpc_luna_v2_4_v1"
CODEBOOK = ROOT / "config/response_validity_decomposed_v2_4.json"
ADOPTED_PROMPT = ROOT / "annotations/response_validity_v2_4/wall_to_wall_luna_v1/prompt.txt"
ADOPTED_SCHEMA = ROOT / "annotations/response_validity_v2_4/wall_to_wall_luna_v1/response_schema.json"
EXPECTED_GENERATIONS = 49_920
EXPECTED_RESPONSES = 49_879
EXPECTED_EMPTY = 28
EXPECTED_ERRORS = 13
EXPECTED_MODELS = {
    "krutrim-2-instruct-local-q8",
    "gigachat3-10b-a1.8b-local-q8",
    "eurollm-22b-instruct-2512-local-q8",
    "salamandra-7b-instruct-2606-local-q8",
}
EXPECTED_LANGUAGES = {"en", "zh", "ar", "ru", "hi"}
PRIOR_COST_PER_RESPONSE = max(63.27810359000008 / 134_664, 0.7212165099999992 / 1_600)
CURRENT_PRICING_VERIFIED_AT = "2026-09-12"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_sources() -> tuple[list[dict], pd.DataFrame, dict[str, str]]:
    """Validate the immutable 49,920-record ledger and separate text outcomes."""
    paths = {
        "generation_manifest": GENERATION_DIR / "manifest.json",
        "generation_audit": GENERATION_DIR / "audit.json",
        "generation_requests": GENERATION_DIR / "requests.jsonl",
        "generation_task_map": GENERATION_DIR / "task_map.json",
        "generation_responses": GENERATION_DIR / "responses.jsonl",
    }
    hashes = {name: sha_file(path) for name, path in paths.items()}
    manifest = json.loads(paths["generation_manifest"].read_text(encoding="utf-8"))
    audit = json.loads(paths["generation_audit"].read_text(encoding="utf-8"))
    if manifest.get("n_requests") != EXPECTED_GENERATIONS:
        raise ValueError("Torch manifest does not declare 49,920 generation requests")
    if set(manifest.get("models", [])) != EXPECTED_MODELS:
        raise ValueError("Torch model roster changed")
    if set(manifest.get("languages", [])) != EXPECTED_LANGUAGES:
        raise ValueError("Torch language roster changed")
    expected_audit = {
        "complete": True,
        "expected_requests": EXPECTED_GENERATIONS,
        "latest_result_records": EXPECTED_GENERATIONS,
        "nonempty_responses": EXPECTED_RESPONSES,
        "empty_responses": EXPECTED_EMPTY,
        "transport_or_runtime_failures": EXPECTED_ERRORS,
        "missing_request_records": 0,
    }
    if any(audit.get(key) != value for key, value in expected_audit.items()):
        raise ValueError("Torch generation audit no longer matches the accepted coverage counts")
    if audit.get("responses_sha256") != hashes["generation_responses"]:
        raise ValueError("Torch response ledger hash differs from its completed audit")

    rows = read_jsonl(paths["generation_responses"])
    if len(rows) != EXPECTED_GENERATIONS:
        raise ValueError("Torch response ledger does not contain 49,920 records")
    if len({str(row["request_id"]) for row in rows}) != EXPECTED_GENERATIONS:
        raise ValueError("Torch response request IDs are not unique")
    keys = [(row["prompt_id"], row["prompt_language"], row["model"]) for row in rows]
    if len(set(keys)) != EXPECTED_GENERATIONS:
        raise ValueError("Torch model-language-prompt keys are not unique")

    sources: list[dict] = []
    outcomes: list[dict] = []
    for row in rows:
        text = str(row.get("response_text") or "")
        error = row.get("error")
        has_error = error is not None
        response_available = not has_error and bool(text.strip())
        outcome = "response_available"
        if error == "empty_response" or (not text.strip() and not has_error):
            outcome = "empty_response"
        elif has_error:
            outcome = "transport_or_runtime_failure"
        outcomes.append({
            "generation_request_id": row["request_id"],
            "prompt_id": row["prompt_id"],
            "prompt_language": row["prompt_language"],
            "subject_model": row["model"],
            "subject_model_id": row["source_model"],
            "developer": row["developer"],
            "developer_jurisdiction": row["developer_jurisdiction"],
            "generation_outcome": outcome,
            "response_available": response_available,
            "generation_error": error,
            "output_tokens": row.get("output_tokens"),
            "stop_type": row.get("stop_type"),
            **row.get("prompt_metadata", {}),
        })
        if response_available:
            sources.append(row)

    outcome_frame = pd.DataFrame(outcomes).sort_values(
        ["subject_model", "prompt_id", "prompt_language"], kind="mergesort"
    ).reset_index(drop=True)
    observed = outcome_frame["generation_outcome"].value_counts().to_dict()
    if observed != {
        "response_available": EXPECTED_RESPONSES,
        "empty_response": EXPECTED_EMPTY,
        "transport_or_runtime_failure": EXPECTED_ERRORS,
    }:
        raise ValueError(f"generation outcome partition changed: {observed}")
    return sources, outcome_frame, hashes


def prepare() -> dict:
    """Freeze the exact blinded provider payload without making a network call."""
    sources, outcomes, generation_hashes = load_sources()
    prompts, prompt_hashes = prompt_maps()
    input_hashes = {
        **generation_hashes,
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
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen Torch annotation inputs changed")
        for name, digest in manifest.get("artifact_sha256", {}).items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != digest:
                raise ValueError(f"frozen Torch annotation artifact changed: {name}")
        return manifest

    codebook = json.loads(CODEBOOK.read_text(encoding="utf-8"))
    system, schema = _system_v24(codebook), _schema()
    schema_bytes = json.dumps(schema, indent=2).encode("utf-8")
    if hashlib.sha256(system.encode("utf-8")).hexdigest() != input_hashes["adopted_v2_4_prompt"]:
        raise ValueError("constructed prompt differs from the adopted v2.4 prompt")
    if hashlib.sha256(schema_bytes).hexdigest() != input_hashes["adopted_v2_4_schema"]:
        raise ValueError("constructed schema differs from the adopted v2.4 schema")

    encoder = tiktoken.get_encoding("o200k_base")
    requests: list[dict] = []
    index: list[dict] = []
    ordered = sorted(sources, key=lambda row: (
        row["model"], row["prompt_id"], row["prompt_language"]
    ))
    for source in ordered:
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
            "version": "local-gguf-hpc-full-luna-v2.4-v1",
        })[:24]
        user = _user(annotation_row, "source_response_only")
        request = {
            "logical_request_id": logical_id,
            "provider_request_id": sha_object({
                "logical_request_id": logical_id, "model_id": MODEL,
            })[:24],
            "audit_response_id": logical_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
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
            "generation_response_sha256": hashlib.sha256(
                source["response_text"].encode("utf-8")
            ).hexdigest(),
            "output_tokens": source.get("output_tokens"),
            "stop_type": source.get("stop_type"),
            "estimated_input_tokens": request["estimated_input_tokens"],
            **source.get("prompt_metadata", {}),
        })
    if len(requests) != EXPECTED_RESPONSES:
        raise ValueError("annotation request count is not 49,879")
    if len({row["provider_request_id"] for row in requests}) != EXPECTED_RESPONSES:
        raise ValueError("annotation provider request IDs are not unique")
    # The only user-message fields are created explicitly above. Repository-only
    # model, provider, sampling and generation metadata remain in the local index.
    if any(set(row) != {"prompt_language", "prompt_text_en", "prompt_text", "response_text"}
           for row in ({
               "prompt_language": source["prompt_language"],
               "prompt_text_en": prompts["en"][source["prompt_id"]]["text"],
               "prompt_text": prompts[source["prompt_language"]][source["prompt_id"]]["text"],
               "response_text": source["response_text"],
           } for source in ordered)):
        raise ValueError("annotation message field contract changed")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    outcomes.to_parquet(artifacts["generation_outcomes.parquet"], index=False)
    pd.DataFrame(index).to_parquet(artifacts["response_index.parquet"], index=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    artifacts["prompt.txt"].write_text(system, encoding="utf-8")
    artifacts["response_schema.json"].write_bytes(schema_bytes)
    manifest = {
        "version": "local-gguf-hpc-full-luna-v2.4-v1",
        "created_at": now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": "census v2.4 annotation of every response-bearing Torch full-run record",
        "selection": "all successful non-empty responses; no semantic prefiltering",
        "generation_denominator": EXPECTED_GENERATIONS,
        "response_bearing_requests": EXPECTED_RESPONSES,
        "empty_generation_outcomes": EXPECTED_EMPTY,
        "transport_or_runtime_failures": EXPECTED_ERRORS,
        "technical_outcome_policy": "retained in generation denominator; not sent to a text classifier",
        "input_mode": "source_response_only",
        "translation_used": False,
        "subject_model_blinded_in_messages": True,
        "selection_metadata_blinded_in_messages": True,
        "joint_outcome_policy": "refusal and capability failure are independent, potentially overlapping labels",
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
    input_tokens = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (
        input_tokens * INPUT_PRICE
        + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1e6
    reserve = (
        input_tokens * INPUT_PRICE
        + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1e6
    empirical = len(requests) * PRIOR_COST_PER_RESPONSE
    ceiling = math.ceil(max(planning * 1.5, empirical * 2) * 4) / 4
    result = {
        "version": "local-gguf-hpc-full-luna-v2.4-cost-v1",
        "created_at": now(),
        "pricing_verified_at": CURRENT_PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests),
        "estimated_input_tokens": input_tokens,
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
    (OUTPUT_DIR / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    manifest["status"] = "frozen_costed_not_authorized"
    manifest["cost_estimate"] = result
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return result


def authorize(payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest, estimate = prepare(), cost()
    if payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("payload hash mismatch")
    if float(ceiling) != float(estimate["suggested_hard_ceiling_usd"]):
        raise ValueError("cost ceiling mismatch")
    record = {
        "recorded_at": now(),
        "user_authorized": True,
        "authorization_scope": "local_gguf_hpc_full_luna_v2_4_v1",
        "provider_payload_sha256": payload_sha,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_RESPONSES,
        "cost_ceiling_usd": float(ceiling),
        "reasoning_disabled": True,
        "allow_fallbacks": False,
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


def summarize() -> dict:
    """Assemble labels and cell counts after a complete, schema-valid run."""
    manifest = json.loads((OUTPUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    run_summary = json.loads((OUTPUT_DIR / "run_summary.json").read_text(encoding="utf-8"))
    results_path = OUTPUT_DIR / "results.jsonl"
    if not (
        run_summary.get("n_completed") == EXPECTED_RESPONSES
        and run_summary.get("n_incomplete") == 0
        and run_summary.get("schema_gate_pass") is True
        and run_summary.get("results_sha256") == sha_file(results_path)
    ):
        raise ValueError("Torch Luna annotations are incomplete or hash-invalid")
    labels = _derive(pd.DataFrame(read_jsonl(results_path)))
    index = pd.read_parquet(OUTPUT_DIR / "response_index.parquet")
    frame = index.merge(labels, on="audit_response_id", validate="one_to_one")
    if frame["provider_request_id_x"].ne(frame["provider_request_id_y"]).any():
        raise ValueError("annotation provider request IDs disagree")
    frame = frame.drop(columns="provider_request_id_y").rename(
        columns={"provider_request_id_x": "provider_request_id"}
    )
    frame["wrong_language"] = frame["language_fidelity"].eq("wrong_language")
    frame["refusal_assessable"] = frame["substantive_refusal"].ne("unassessable")
    frame["joint_class"] = "neither"
    frame.loc[frame["pred_capability_failure"], "joint_class"] = "capability_failure_only"
    frame.loc[frame["pred_genuine_refusal"], "joint_class"] = "genuine_refusal_only"
    frame.loc[
        frame["pred_capability_failure"] & frame["pred_genuine_refusal"], "joint_class"
    ] = "both"
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
            "refusal_and_capability_failure_n": int((
                part["pred_genuine_refusal"] & part["pred_capability_failure"]
            ).sum()),
            "refusal_lower_bound": definite / n,
            "refusal_upper_bound": (definite + unknown) / n,
            "refusal_rate_assessable": definite / assessable if assessable else None,
            "refusal_rate_without_capability_failure": (
                float(part.loc[competent, "pred_genuine_refusal"].mean())
                if competent.any() else None
            ),
        })

    cell_path = OUTPUT_DIR / "outcomes_by_model_language.csv"
    frame.groupby(["subject_model", "prompt_language"], dropna=False).apply(
        summarize_part, include_groups=False
    ).reset_index().to_csv(cell_path, index=False)
    joint_path = OUTPUT_DIR / "joint_outcome_counts.csv"
    frame.groupby(
        ["subject_model", "prompt_language", "joint_class"], dropna=False
    ).size().rename("n").reset_index().to_csv(joint_path, index=False)
    summary = {
        "version": "local-gguf-hpc-full-luna-v2.4-summary-v1",
        "created_at": now(),
        "generation_denominator": EXPECTED_GENERATIONS,
        "response_labels": len(frame),
        "empty_generation_outcomes": EXPECTED_EMPTY,
        "transport_or_runtime_failures": EXPECTED_ERRORS,
        "genuine_refusal_n": int(frame["pred_genuine_refusal"].sum()),
        "capability_failure_n": int(frame["pred_capability_failure"].sum()),
        "refusal_and_capability_failure_n": int((
            frame["pred_genuine_refusal"] & frame["pred_capability_failure"]
        ).sum()),
        "refusal_unassessable_n": int((~frame["refusal_assessable"]).sum()),
        "interpretation": "full-corpus labels; generation failures remain separate technical outcomes",
        "artifact_sha256": {
            label_path.name: sha_file(label_path),
            cell_path.name: sha_file(cell_path),
            joint_path.name: sha_file(joint_path),
            results_path.name: sha_file(results_path),
        },
    }
    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    manifest["summary"] = summary
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "run", "summarize"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--workers", type=int, default=32)
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
        result = run_luna_v24(
            ROOT, OUTPUT_DIR, min(args.workers, 32),
            args.cost_ceiling, args.authorize_paid_run,
        )
    else:
        result = summarize()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
