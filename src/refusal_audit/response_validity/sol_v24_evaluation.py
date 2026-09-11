"""Guarded same-codebook Sol v2.4 comparison for the external sample."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .human_pilot import sha_file
from .luna_v23_repair import _derive, validate_v23
from .luna_v24_evaluation import (
    BOUNDARY_DIR,
    CODEBOOK,
    EXPECTED_N,
    MAX_ATTEMPTS,
    MAX_OUTPUT_TOKENS,
    PLANNING_OUTPUT_TOKENS,
    PROVIDER,
    _binary_metrics,
    _read_jsonl,
    _sha_object,
    _write_jsonl,
)


DEFAULT_DIR = (
    "annotations/response_validity_human_v2/external_audit_v1/"
    "sol_v2_4_evaluation_v1"
)
LUNA_DIR = (
    "annotations/response_validity_human_v2/external_audit_v1/"
    "luna_v2_4_evaluation_v1"
)
MODEL = "openai/gpt-5.6-sol"
INPUT_PRICE = 2.00
OUTPUT_PRICE = 10.00
PRICING_VERIFIED_AT = "2026-08-31"
PRICING_SOURCE = "https://openrouter.ai/openai/gpt-5.6-sol-20260709"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def prepare_sol_v24_evaluation(root: Path, output_dir: Path | None = None) -> dict:
    """Freeze Sol requests from the exact Luna v2.4 model-neutral payload."""
    output_dir = output_dir or root / DEFAULT_DIR
    luna_dir = root / LUNA_DIR
    source_path = luna_dir / "model_neutral_requests.jsonl"
    prompt_path = luna_dir / "prompt.txt"
    schema_path = luna_dir / "response_schema.json"
    partition_path = luna_dir / "evaluation_partition.csv"
    codebook_path = root / CODEBOOK
    manifest_path = output_dir / "manifest.json"
    input_hashes = {
        "luna_v2_4_model_neutral_requests": sha_file(source_path),
        "luna_v2_4_prompt": sha_file(prompt_path),
        "luna_v2_4_schema": sha_file(schema_path),
        "evaluation_partition": sha_file(partition_path),
        "v2_4_codebook": sha_file(codebook_path),
    }
    artifacts = {
        "model_neutral_requests.jsonl": output_dir / "model_neutral_requests.jsonl",
        "provider_requests.jsonl": output_dir / "provider_requests.jsonl",
        "prompt.txt": output_dir / "prompt.txt",
        "response_schema.json": output_dir / "response_schema.json",
        "evaluation_partition.csv": output_dir / "evaluation_partition.csv",
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen Sol v2.4 evaluation no longer matches inputs")
        for name, expected in manifest.get("artifact_sha256", {}).items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != expected:
                raise ValueError(f"frozen Sol v2.4 artifact changed: {name}")
        return manifest

    neutral = _read_jsonl(source_path)
    if len(neutral) != EXPECTED_N or len({r["audit_response_id"] for r in neutral}) != EXPECTED_N:
        raise ValueError("Luna model-neutral payload is not 1,197 unique rows")
    provider = []
    for request in neutral:
        provider.append({
            **request,
            "provider_request_id": _sha_object({
                "logical_request_id": request["logical_request_id"],
                "model_id": MODEL,
            })[:24],
            "model_id": MODEL,
            "provider": {"only": [PROVIDER], "allow_fallbacks": False},
            "reasoning": {"enabled": False, "exclude": True},
            "temperature": 0,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        })
    serialized = json.dumps(provider, ensure_ascii=False)
    for forbidden in (
        "pred_genuine_refusal", "final_genuine_refusal", "human_",
        "evaluation_role", "routing_stratum", "phase1_inclusion_probability",
    ):
        if forbidden in serialized:
            raise ValueError(f"reference information leaked into Sol payload: {forbidden}")

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_jsonl(artifacts["model_neutral_requests.jsonl"], neutral)
    _write_jsonl(artifacts["provider_requests.jsonl"], provider)
    artifacts["prompt.txt"].write_bytes(prompt_path.read_bytes())
    artifacts["response_schema.json"].write_bytes(schema_path.read_bytes())
    artifacts["evaluation_partition.csv"].write_bytes(partition_path.read_bytes())
    manifest = {
        "version": "sol-v2.4-external-evaluation-v1",
        "created_at": _now(), "status": "frozen_unpriced",
        "scientific_role": (
            "same-codebook frontier machine reference for Luna v2.4; "
            "not independent human accuracy"
        ),
        "model_id": MODEL, "provider_tag": PROVIDER,
        "n_requests": EXPECTED_N, "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS, "max_attempts": MAX_ATTEMPTS,
        "reasoning_disabled": True, "allow_fallbacks": False,
        "input_sha256": input_hashes,
        "artifact_sha256": {name: sha_file(path) for name, path in artifacts.items()},
        "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "paid_run_authorized": False, "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_sol_v24_cost(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare_sol_v24_evaluation(root, output_dir)
    requests = _read_jsonl(output_dir / "provider_requests.jsonl")
    tokens = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (
        tokens * INPUT_PRICE
        + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1e6
    reserved = (
        tokens * INPUT_PRICE
        + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1e6
    ceiling = math.ceil(max(planning * 1.5, reserved * 1.25) * 2) / 2
    result = {
        "version": "sol-v2.4-external-evaluation-cost-v1",
        "created_at": _now(), "pricing_verified_at": PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "discount_status": "OpenRouter versioned page reports 50% off",
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests), "estimated_input_tokens": tokens,
        "planning_output_tokens": len(requests) * PLANNING_OUTPUT_TOKENS,
        "maximum_output_tokens_single_attempt": len(requests) * MAX_OUTPUT_TOKENS,
        "planning_cost_usd": planning,
        "single_attempt_reserved_cost_usd": reserved,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False, "network_call_made": False,
    }
    (output_dir / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    manifest_path = output_dir / "manifest.json"
    latest = json.loads(manifest_path.read_text(encoding="utf-8"))
    latest["status"] = "frozen_unpaid"
    latest["cost_estimate"] = result
    manifest_path.write_text(json.dumps(latest, indent=2), encoding="utf-8")
    return result


def authorize_sol_v24(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
) -> dict:
    if not confirmed:
        raise RuntimeError("explicit authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cost = json.loads((output_dir / "cost_estimate.json").read_text(encoding="utf-8"))
    observed = sha_file(output_dir / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized payload hash does not match frozen bytes")
    if float(ceiling) != float(cost["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized ceiling does not match frozen estimate")
    authorization = {
        "recorded_at": _now(), "user_authorized": True,
        "authorization_scope": "sol_v2_4_external_evaluation",
        "provider_payload_sha256": payload_sha, "model_id": MODEL,
        "provider_tag": PROVIDER, "n_requests": EXPECTED_N,
        "reasoning_disabled": True, "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def _call(client, request: dict, codebook: dict) -> dict:
    started = time.time()
    response_id = request.get("audit_response_id") or request.get(
        "certification_response_id"
    )
    if not response_id:
        raise ValueError("provider request lacks a response identifier")
    response = client.chat.completions.create(
        model=request["model_id"], messages=request["messages"],
        temperature=request["temperature"], max_tokens=request["max_output_tokens"],
        response_format={"type": "json_schema", "json_schema": {
            "name": "response_validity_v2_4", "strict": True,
            "schema": request["response_schema"],
        }},
        extra_body={"reasoning": request["reasoning"], "provider": request["provider"]},
        timeout=180,
    )
    usage = response.usage.model_dump() if response.usage else {}
    cost = usage.get("cost")
    if cost is None:
        cost = (
            float(usage.get("prompt_tokens", 0)) * INPUT_PRICE
            + float(usage.get("completion_tokens", 0)) * OUTPUT_PRICE
        ) / 1e6
    raw = response.choices[0].message.content or ""
    base = {
        "provider_request_id": request["provider_request_id"],
        "logical_request_id": request["logical_request_id"],
        "audit_response_id": response_id, "model_id": MODEL,
        "provider_tag_requested": PROVIDER, "usage": usage,
        "incremental_provider_cost": float(cost),
        "provider_response_id": response.id, "provider_model": response.model,
        "raw_provider_content": raw,
        "raw_provider_content_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "elapsed_seconds": time.time() - started, "created_at": _now(),
    }
    try:
        label = json.loads(raw)
        errors = validate_v23(label, codebook)
        if errors:
            raise ValueError("; ".join(errors))
        return {**base, **label, "status": "complete"}
    except Exception as exc:
        return {**base, "status": "error", "error_type": type(exc).__name__, "error": str(exc)[:1000]}


def run_sol_v24(
    root: Path, output_dir: Path, workers: int, ceiling: float, authorized: bool
) -> dict:
    if not authorized:
        raise RuntimeError("paid run requires --authorize-paid-run")
    if workers < 1 or workers > 32:
        raise ValueError("workers must be between 1 and 32")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_n = int(manifest.get("n_requests", EXPECTED_N))
    payload_path = output_dir / "provider_requests.jsonl"
    authorization = manifest.get("authorization", {})
    if not (
        authorization.get("user_authorized") is True
        and authorization.get("provider_payload_sha256") == sha_file(payload_path)
        and authorization.get("model_id") == MODEL
        and authorization.get("provider_tag") == PROVIDER
        and authorization.get("reasoning_disabled") is True
        and authorization.get("allow_fallbacks") is False
        and float(authorization.get("cost_ceiling_usd", -1)) == float(ceiling)
    ):
        raise RuntimeError("authorization does not match exact payload and ceiling")
    summary_path, results_path = output_dir / "run_summary.json", output_dir / "results.jsonl"
    if summary_path.exists() and results_path.exists():
        prior = json.loads(summary_path.read_text(encoding="utf-8"))
        if prior.get("n_completed") == expected_n and prior.get("results_sha256") == sha_file(results_path):
            return prior
    from openai import OpenAI
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    requests = _read_jsonl(payload_path)
    attempts_path = output_dir / "attempts.jsonl"
    completed: dict[str, dict] = {}
    attempts: dict[str, int] = {}
    spent = 0.0
    for record in _read_jsonl(attempts_path):
        spent += float(record.get("incremental_provider_cost", 0))
        request_id = record["provider_request_id"]
        attempts[request_id] = attempts.get(request_id, 0) + 1
        if record.get("status") == "complete":
            completed[request_id] = record
    pending = [row for row in requests if row["provider_request_id"] not in completed]
    codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
    lock_path = output_dir / ".run.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with attempts_path.open("a", encoding="utf-8") as handle:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures: dict = {}; cursor = 0; reserved = 0.0
                while cursor < len(pending) or futures:
                    while cursor < len(pending) and len(futures) < workers:
                        request = pending[cursor]; request_id = request["provider_request_id"]
                        if attempts.get(request_id, 0) >= MAX_ATTEMPTS:
                            cursor += 1; continue
                        hold = (
                            request["estimated_input_tokens"] * INPUT_PRICE
                            + request["max_output_tokens"] * OUTPUT_PRICE
                        ) / 1e6
                        if spent + reserved + hold > ceiling + 1e-9:
                            break
                        cursor += 1
                        future = pool.submit(_call, client, request, codebook)
                        futures[future] = (request, hold); reserved += hold
                    if not futures:
                        break
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        request, hold = futures.pop(future); reserved -= hold
                        try:
                            record = future.result()
                        except Exception as exc:
                            record = {
                                "provider_request_id": request["provider_request_id"],
                                "logical_request_id": request["logical_request_id"],
                                "audit_response_id": (
                                    request.get("audit_response_id")
                                    or request.get("certification_response_id")
                                ),
                                "status": "error", "error_type": type(exc).__name__,
                                "error": str(exc)[:1000], "incremental_provider_cost": 0.0,
                                "created_at": _now(), "raw_provider_content": None,
                            }
                        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                        handle.flush(); os.fsync(handle.fileno())
                        request_id = request["provider_request_id"]
                        attempts[request_id] = attempts.get(request_id, 0) + 1
                        spent += float(record.get("incremental_provider_cost", 0))
                        if spent > ceiling + 1e-9:
                            raise RuntimeError("hard provider-cost ceiling exceeded")
                        if record.get("status") == "complete":
                            completed[request_id] = record
                        elif attempts[request_id] < MAX_ATTEMPTS:
                            pending.append(request)
    ordered = [completed[r["provider_request_id"]] for r in requests if r["provider_request_id"] in completed]
    _write_jsonl(results_path, ordered)
    summary = {
        "completed_at": _now(), "n_expected": expected_n,
        "n_completed": len(ordered), "n_incomplete": expected_n - len(ordered),
        "schema_success": len(ordered) / expected_n,
        "schema_success_gate": .995, "schema_gate_pass": len(ordered) / expected_n >= .995,
        "provider_cost_usd": spent, "authorized_ceiling_usd": float(ceiling),
        "provider_payload_sha256": sha_file(payload_path),
        "attempts_sha256": sha_file(attempts_path), "results_sha256": sha_file(results_path),
        "network_call_made": True, "raw_provider_content_preserved_before_validation": True,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest["status"] = "completed" if len(ordered) == expected_n else "incomplete"
    manifest["network_call_made"] = True; manifest["run_summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary


def score_sol_v24(root: Path, output_dir: Path | None = None) -> dict:
    """Compare Luna and Sol under the identical v2.4 prompt."""
    output_dir = output_dir or root / DEFAULT_DIR
    run = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    if run.get("n_completed") != EXPECTED_N or not run.get("schema_gate_pass"):
        raise RuntimeError("Sol v2.4 run is incomplete")
    sol = _derive(pd.DataFrame(_read_jsonl(output_dir / "results.jsonl")))
    luna = _derive(pd.DataFrame(_read_jsonl(root / LUNA_DIR / "results.jsonl")))
    partition = pd.read_csv(output_dir / "evaluation_partition.csv")
    frame = luna.merge(
        sol, on="audit_response_id", validate="one_to_one", suffixes=("_luna", "_sol")
    ).merge(partition[[
        "audit_response_id", "evaluation_role", "model", "prompt_language",
        "routing_stratum",
    ]], on="audit_response_id")
    rows = []
    for role, part in frame.groupby("evaluation_role", sort=True):
        for outcome, luna_col, sol_col in (
            ("genuine_refusal", "pred_genuine_refusal_luna", "pred_genuine_refusal_sol"),
            ("capability_failure", "pred_capability_failure_luna", "pred_capability_failure_sol"),
        ):
            rows.append({
                "evaluation_role": role, "outcome": outcome,
                "reference": "sol_v2.4_machine_reference",
                **_binary_metrics(part[sol_col], part[luna_col]),
            })
    metrics_path = output_dir / "same_codebook_machine_reference_metrics.csv"
    metrics = pd.DataFrame(rows)
    metrics.to_csv(metrics_path, index=False)
    disagreements = frame.loc[
        frame.pred_genuine_refusal_luna.ne(frame.pred_genuine_refusal_sol)
    ].copy()
    disagreement_path = output_dir / "same_codebook_refusal_disagreements.csv"
    disagreements[[
        "audit_response_id", "evaluation_role", "model", "prompt_language",
        "routing_stratum", "substantive_refusal_luna",
        "substantive_refusal_sol", "task_behavior_luna", "task_behavior_sol",
        "stance_disclaimer_luna", "stance_disclaimer_sol",
        "epistemic_limitation_luna", "epistemic_limitation_sol",
        "refusal_evidence_span_luna", "refusal_evidence_span_sol",
        "decision_note_luna", "decision_note_sol",
    ]].sort_values("audit_response_id", kind="mergesort").to_csv(disagreement_path, index=False)
    protected = metrics.loc[
        metrics.evaluation_role.eq("protected_sol_reference_nonregression")
        & metrics.outcome.eq("genuine_refusal")
    ].iloc[0]
    boundary = pd.read_csv(root / BOUNDARY_DIR / "assembled_boundary_decisions.csv")
    human_development = frame.loc[
        frame.evaluation_role.eq("boundary_development")
    ].merge(
        boundary[["audit_response_id", "final_genuine_refusal"]],
        on="audit_response_id", validate="one_to_one",
    )
    human_development = human_development.loc[
        human_development.final_genuine_refusal.notna()
    ].copy()
    luna_human = _binary_metrics(
        human_development.final_genuine_refusal,
        human_development.pred_genuine_refusal_luna,
    )
    sol_human = _binary_metrics(
        human_development.final_genuine_refusal,
        human_development.pred_genuine_refusal_sol,
    )
    human_path = output_dir / "boundary_human_reference_metrics.csv"
    pd.DataFrame([
        {"candidate_model": "luna_v2.4", **luna_human},
        {"candidate_model": "sol_v2.4", **sol_human},
    ]).to_csv(human_path, index=False)
    headline = {
        "status": "complete_same_codebook_machine_reference_not_human_accuracy",
        "protected_n": int(protected["n"]),
        "protected_refusal_precision": float(protected["precision"]),
        "protected_refusal_recall": float(protected["recall"]),
        "protected_refusal_f1": float(protected["f1"]),
        "protected_refusal_accuracy": float(protected["accuracy"]),
        "same_codebook_refusal_disagreements_n": int(
            disagreements.evaluation_role.eq("protected_sol_reference_nonregression").sum()
        ),
        "boundary_human_reference_decided_n": len(human_development),
        "boundary_human_reference_accuracy": {
            "luna_v2.4": float(luna_human["accuracy"]),
            "sol_v2.4": float(sol_human["accuracy"]),
        },
        "boundary_human_reference_f1": {
            "luna_v2.4": float(luna_human["f1"]),
            "sol_v2.4": float(sol_human["f1"]),
        },
        "human_validation_complete": False,
    }
    headline_path = output_dir / "headline_results.json"
    headline_path.write_text(json.dumps(headline, indent=2), encoding="utf-8")
    summary = {
        "version": "sol-v2.4-external-evaluation-score-v1", "scored_at": _now(),
        "headline": headline,
        "input_sha256": {
            "sol_results": sha_file(output_dir / "results.jsonl"),
            "luna_results": sha_file(root / LUNA_DIR / "results.jsonl"),
            "partition": sha_file(output_dir / "evaluation_partition.csv"),
        },
        "artifact_sha256": {
            metrics_path.name: sha_file(metrics_path),
            disagreement_path.name: sha_file(disagreement_path),
            human_path.name: sha_file(human_path),
            headline_path.name: sha_file(headline_path),
        },
        "provider_call_made_by_scoring": False, "human_validation_complete": False,
    }
    (output_dir / "score_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
