"""Guarded API-only v2.4 student-model bake-off.

The builder freezes all potential requests locally. The paid runner first sends
the same 50-case engineering screen to every candidate and continues to the
remaining 1,147 cases only for candidates with at least 49 valid records. The
authorization therefore covers one immutable maximum payload while the runner
can stop unsuitable routes without spending the full reservation.

Sol v2.4 is a machine reference, not human gold. The 24 prompt-development
cases are diagnostics and never enter promotion metrics.
"""

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

import numpy as np
import pandas as pd

from .human_pilot import sha_file
from .luna_v23_repair import _derive, validate_v23
from .luna_v24_evaluation import (
    CODEBOOK,
    EXPECTED_N,
    _binary_metrics,
    _read_jsonl,
    _sha_object,
    _write_jsonl,
)


DEFAULT_DIR = (
    "annotations/response_validity_human_v2/external_audit_v1/"
    "model_bakeoff_v2"
)
EXTERNAL_DIR = "annotations/response_validity_human_v2/external_audit_v1"
LUNA_DIR = EXTERNAL_DIR + "/luna_v2_4_evaluation_v1"
SOL_DIR = EXTERNAL_DIR + "/sol_v2_4_evaluation_v1"
N_PREFLIGHT = 50
MAX_OUTPUT_TOKENS = 500
PLANNING_OUTPUT_TOKENS = 200
MAX_ATTEMPTS = 2
SCHEMA_GATE_OVERALL = 0.995
SCHEMA_GATE_PREFLIGHT_N = 49
BOOTSTRAP_REPS = 2000
BOOTSTRAP_SEED = 20260831
PRICING_VERIFIED_AT = "2026-08-31"


# Prices are exact pinned-provider list prices per million tokens as returned by
# OpenRouter's endpoint metadata on PRICING_VERIFIED_AT. Quantization is part of
# the treatment and is retained rather than silently allowing provider routing.
CANDIDATES = (
    {
        "candidate_id": "gemini_3_5_flash_lite",
        "model_id": "google/gemini-3.5-flash-lite",
        "provider_tag": "google-ai-studio",
        "provider_name": "Google AI Studio",
        "quantization": "unknown",
        "input_price": 0.30,
        "output_price": 2.50,
        "family_role": "closed_api_comparator",
        "reasoning_mode": "disabled",
        "strict_schema": True,
    },
    {
        "candidate_id": "claude_haiku_4_5",
        "model_id": "anthropic/claude-haiku-4.5",
        "provider_tag": "anthropic",
        "provider_name": "Anthropic",
        "quantization": "unknown",
        "input_price": 1.00,
        "output_price": 5.00,
        "family_role": "closed_api_comparator",
        "reasoning_mode": "disabled",
        "strict_schema": True,
    },
    {
        "candidate_id": "kimi_k3",
        "model_id": "moonshotai/kimi-k3",
        "provider_tag": "fireworks",
        "provider_name": "Fireworks",
        "quantization": "unknown",
        "input_price": 3.00,
        "output_price": 15.00,
        "family_role": "open_weight_frontier",
        "reasoning_mode": "disabled",
        "strict_schema": True,
    },
    {
        "candidate_id": "qwen_3_8_2_4t_a95b",
        "model_id": "qwen/qwen3.8-2.4t-a95b",
        "provider_tag": "modal",
        "provider_name": "Modal",
        "quantization": "unknown",
        "input_price": 2.00,
        "output_price": 6.00,
        "family_role": "open_weight_frontier",
        "reasoning_mode": "disabled",
        "strict_schema": True,
    },
    {
        "candidate_id": "glm_5_3",
        "model_id": "z-ai/glm-5.3",
        "provider_tag": "fireworks",
        "provider_name": "Fireworks",
        "quantization": "unknown",
        "input_price": 1.40,
        "output_price": 4.40,
        "family_role": "open_weight_frontier",
        "reasoning_mode": "low_hidden_required",
        "strict_schema": True,
    },
    {
        "candidate_id": "deepseek_v4_pro_0813",
        "model_id": "deepseek/deepseek-v4-pro-0813",
        "provider_tag": "fireworks",
        "provider_name": "Fireworks",
        "quantization": "unknown",
        "input_price": 1.32,
        "output_price": 3.96,
        "family_role": "open_weight_frontier",
        "reasoning_mode": "disabled",
        "strict_schema": True,
    },
    {
        "candidate_id": "minimax_m3",
        "model_id": "minimax/minimax-m3",
        "provider_tag": "coreweave/fp4",
        "provider_name": "CoreWeave",
        "quantization": "fp4",
        "input_price": 0.23,
        "output_price": 0.96,
        "family_role": "efficient_open_weight",
        "reasoning_mode": "disabled",
        "strict_schema": True,
    },
    {
        "candidate_id": "qwen_3_8_27b",
        "model_id": "qwen/qwen3.8-27b",
        "provider_tag": "akashml/fp8",
        "provider_name": "AkashML",
        "quantization": "fp8",
        "input_price": 0.35,
        "output_price": 2.55,
        "family_role": "efficient_open_weight",
        "reasoning_mode": "disabled",
        "strict_schema": True,
    },
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rank(value: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}|{value}".encode("utf-8")).hexdigest()


def _candidate(candidate_id: str) -> dict:
    matches = [row for row in CANDIDATES if row["candidate_id"] == candidate_id]
    if len(matches) != 1:
        raise ValueError(f"unknown or duplicate candidate: {candidate_id}")
    return matches[0]


def _load_labels(path: Path, suffix: str) -> pd.DataFrame:
    frame = _derive(pd.DataFrame(_read_jsonl(path)))
    keep = [
        "audit_response_id", "task_behavior", "substantive_refusal",
        "stance_disclaimer", "epistemic_limitation", "language_fidelity",
        "output_quality", "technical_failure", "pred_genuine_refusal",
        "pred_capability_failure",
    ]
    return frame[keep].rename(
        columns={name: f"{name}_{suffix}" for name in keep if name != "audit_response_id"}
    )


def _take_ranked(
    frame: pd.DataFrame,
    n: int,
    reason: str,
    selected: set[str],
    salt: str,
) -> pd.DataFrame:
    available = frame.loc[~frame.audit_response_id.astype(str).isin(selected)].copy()
    available["_rank"] = available.audit_response_id.astype(str).map(
        lambda value: _rank(value, salt)
    )
    chosen = available.sort_values("_rank", kind="mergesort").head(n).copy()
    if len(chosen) != n:
        raise ValueError(f"could not select {n} preflight cases for {reason}")
    chosen["preflight_reason"] = reason
    selected.update(chosen.audit_response_id.astype(str))
    return chosen.drop(columns="_rank")


def _build_preflight_cases(root: Path) -> pd.DataFrame:
    external = root / EXTERNAL_DIR
    partition = pd.read_csv(root / LUNA_DIR / "evaluation_partition.csv")
    luna = _load_labels(root / LUNA_DIR / "results.jsonl", "luna")
    sol = _load_labels(root / SOL_DIR / "results.jsonl", "sol")
    frame = partition.merge(luna, on="audit_response_id", validate="one_to_one")
    frame = frame.merge(sol, on="audit_response_id", validate="one_to_one")
    if len(frame) != EXPECTED_N:
        raise ValueError("v2.4 label inputs are not the frozen 1,197 rows")
    protected = frame.evaluation_role.ne("boundary_development")
    selected: set[str] = set()
    pieces: list[pd.DataFrame] = []

    disagreements = frame.loc[
        protected
        & frame.pred_genuine_refusal_luna.ne(frame.pred_genuine_refusal_sol)
    ]
    pieces.append(_take_ranked(
        disagreements, 15, "luna_sol_refusal_disagreement", selected,
        "preflight-refusal-disagreement-v1",
    ))

    capability = frame.loc[protected & frame.pred_capability_failure_sol]
    capability_parts = []
    for language in ("ar", "en", "hi", "ru", "zh"):
        capability_parts.append(_take_ranked(
            capability.loc[capability.prompt_language.eq(language)], 2,
            "capability_failure_diagnostic", selected,
            f"preflight-capability-{language}-v1",
        ))
    pieces.append(pd.concat(capability_parts, ignore_index=True))

    boundary = frame.loc[
        frame.evaluation_role.eq("boundary_development")
        & (
            frame.stance_disclaimer_luna
            | frame.epistemic_limitation_luna
            | frame.stance_disclaimer_sol
            | frame.epistemic_limitation_sol
        )
    ]
    if len(boundary.loc[~boundary.audit_response_id.astype(str).isin(selected)]) < 10:
        boundary = frame.loc[frame.evaluation_role.eq("boundary_development")]
    pieces.append(_take_ranked(
        boundary, 10, "v2_4_boundary_diagnostic", selected,
        "preflight-boundary-v1",
    ))

    ordinary = frame.loc[
        protected
        & ~frame.pred_genuine_refusal_luna
        & ~frame.pred_genuine_refusal_sol
        & ~frame.pred_capability_failure_luna
        & ~frame.pred_capability_failure_sol
    ]
    ordinary_parts = []
    for language in ("ar", "en", "hi", "ru", "zh"):
        ordinary_parts.append(_take_ranked(
            ordinary.loc[ordinary.prompt_language.eq(language)], 3,
            "ordinary_agreement_control", selected,
            f"preflight-ordinary-{language}-v1",
        ))
    pieces.append(pd.concat(ordinary_parts, ignore_index=True))

    out = pd.concat(pieces, ignore_index=True)
    if len(out) != N_PREFLIGHT or out.audit_response_id.duplicated().any():
        raise ValueError("preflight set is not exactly 50 unique responses")
    counts = out.groupby("preflight_reason").size().to_dict()
    expected = {
        "luna_sol_refusal_disagreement": 15,
        "capability_failure_diagnostic": 10,
        "v2_4_boundary_diagnostic": 10,
        "ordinary_agreement_control": 15,
    }
    if counts != expected:
        raise ValueError(f"preflight allocation changed: {counts}")
    return out.sort_values("audit_response_id", kind="mergesort").reset_index(drop=True)


def prepare_model_bakeoff_v2(root: Path, output_dir: Path | None = None) -> dict:
    """Freeze the maximum 8 x 1,197 payload without calling a provider."""
    output_dir = output_dir or root / DEFAULT_DIR
    manifest_path = output_dir / "manifest.json"
    source_neutral = root / LUNA_DIR / "model_neutral_requests.jsonl"
    source_partition = root / LUNA_DIR / "evaluation_partition.csv"
    source_prompt = root / LUNA_DIR / "prompt.txt"
    source_schema = root / LUNA_DIR / "response_schema.json"
    source_luna = root / LUNA_DIR / "results.jsonl"
    source_sol = root / SOL_DIR / "results.jsonl"
    codebook_path = root / CODEBOOK
    input_hashes = {
        "model_neutral_requests": sha_file(source_neutral),
        "evaluation_partition": sha_file(source_partition),
        "prompt": sha_file(source_prompt),
        "schema": sha_file(source_schema),
        "luna_v2_4_results": sha_file(source_luna),
        "sol_v2_4_results": sha_file(source_sol),
        "codebook": sha_file(codebook_path),
        "candidate_registry": hashlib.sha256(json.dumps(
            CANDIDATES, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
    }
    artifacts = {
        "candidate_registry.csv": output_dir / "candidate_registry.csv",
        "preflight_cases.parquet": output_dir / "preflight_cases.parquet",
        "evaluation_partition.csv": output_dir / "evaluation_partition.csv",
        "model_neutral_requests.jsonl": output_dir / "model_neutral_requests.jsonl",
        "provider_requests.jsonl": output_dir / "provider_requests.jsonl",
        "prompt.txt": output_dir / "prompt.txt",
        "response_schema.json": output_dir / "response_schema.json",
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen bake-off no longer matches its inputs")
        for name, expected in manifest.get("artifact_sha256", {}).items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != expected:
                raise ValueError(f"frozen bake-off artifact changed: {name}")
        return manifest

    neutral = _read_jsonl(source_neutral)
    if len(neutral) != EXPECTED_N or len({r["audit_response_id"] for r in neutral}) != EXPECTED_N:
        raise ValueError("source model-neutral payload is not 1,197 unique rows")
    preflight = _build_preflight_cases(root)
    preflight_ids = set(preflight.audit_response_id.astype(str))
    provider_requests: list[dict] = []
    for candidate in CANDIDATES:
        reasoning = (
            {"effort": "low", "exclude": True}
            if candidate["reasoning_mode"] == "low_hidden_required"
            else {"enabled": False, "exclude": True}
        )
        for request in neutral:
            provider_requests.append({
                **request,
                "provider_request_id": _sha_object({
                    "logical_request_id": request["logical_request_id"],
                    "candidate_id": candidate["candidate_id"],
                    "provider_tag": candidate["provider_tag"],
                    "version": "model-bakeoff-v2",
                })[:24],
                "candidate_id": candidate["candidate_id"],
                "model_id": candidate["model_id"],
                "provider": {
                    "only": [candidate["provider_tag"]],
                    "allow_fallbacks": False,
                },
                "reasoning": reasoning,
                "temperature": 0,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "is_preflight": str(request["audit_response_id"]) in preflight_ids,
            })
    if len(provider_requests) != EXPECTED_N * len(CANDIDATES):
        raise ValueError("provider payload has the wrong request count")
    serialized = json.dumps(provider_requests, ensure_ascii=False)
    for forbidden in (
        "pred_genuine_refusal", "final_genuine_refusal", "human_",
        "evaluation_role", "routing_stratum", "phase1_inclusion_probability",
        "preflight_reason",
    ):
        if forbidden in serialized:
            raise ValueError(f"reference or selection data leaked into payload: {forbidden}")

    output_dir.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(CANDIDATES).to_csv(artifacts["candidate_registry.csv"], index=False)
    preflight.to_parquet(artifacts["preflight_cases.parquet"], index=False)
    artifacts["evaluation_partition.csv"].write_bytes(source_partition.read_bytes())
    _write_jsonl(artifacts["model_neutral_requests.jsonl"], neutral)
    _write_jsonl(artifacts["provider_requests.jsonl"], provider_requests)
    artifacts["prompt.txt"].write_bytes(source_prompt.read_bytes())
    artifacts["response_schema.json"].write_bytes(source_schema.read_bytes())
    manifest = {
        "version": "response-validity-model-bakeoff-v2",
        "created_at": _now(),
        "status": "frozen_unpriced",
        "scientific_role": (
            "select a scalable v2.4 student against a frozen Sol v2.4 machine "
            "reference; not final human accuracy"
        ),
        "n_candidates": len(CANDIDATES),
        "n_responses_per_candidate": EXPECTED_N,
        "n_preflight_per_candidate": N_PREFLIGHT,
        "n_maximum_provider_requests": len(provider_requests),
        "preflight_gate_valid_n": SCHEMA_GATE_PREFLIGHT_N,
        "max_attempts": MAX_ATTEMPTS,
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "fallbacks_disabled": True,
        "input_sha256": input_hashes,
        "artifact_sha256": {name: sha_file(path) for name, path in artifacts.items()},
        "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_model_bakeoff_v2_cost(root: Path, output_dir: Path | None = None) -> dict:
    """Price the maximum frozen payload; actual spend can be lower after gates."""
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare_model_bakeoff_v2(root, output_dir)
    requests = _read_jsonl(output_dir / "provider_requests.jsonl")
    rows = []
    for candidate in CANDIDATES:
        subset = [r for r in requests if r["candidate_id"] == candidate["candidate_id"]]
        input_tokens = sum(int(r["estimated_input_tokens"]) for r in subset)
        planning = (
            input_tokens * candidate["input_price"]
            + len(subset) * PLANNING_OUTPUT_TOKENS * candidate["output_price"]
        ) / 1e6
        reserved = (
            input_tokens * candidate["input_price"]
            + len(subset) * MAX_OUTPUT_TOKENS * candidate["output_price"]
        ) / 1e6
        rows.append({
            "candidate_id": candidate["candidate_id"],
            "model_id": candidate["model_id"],
            "provider_tag": candidate["provider_tag"],
            "requests": len(subset),
            "estimated_input_tokens": input_tokens,
            "planning_output_tokens": len(subset) * PLANNING_OUTPUT_TOKENS,
            "maximum_output_tokens_single_attempt": len(subset) * MAX_OUTPUT_TOKENS,
            "input_price_per_million": candidate["input_price"],
            "output_price_per_million": candidate["output_price"],
            "planning_cost_usd": planning,
            "single_attempt_reserved_cost_usd": reserved,
        })
    costs = pd.DataFrame(rows)
    planning_total = float(costs.planning_cost_usd.sum())
    reserved_total = float(costs.single_attempt_reserved_cost_usd.sum())
    ceiling = math.ceil(max(planning_total * 2, reserved_total * 1.5) * 2) / 2
    costs.to_csv(output_dir / "cost_estimate.csv", index=False)
    result = {
        "version": "response-validity-model-bakeoff-v2-cost",
        "created_at": _now(),
        "pricing_verified_at": PRICING_VERIFIED_AT,
        "requests_if_all_candidates_pass_preflight": len(requests),
        "preflight_requests": N_PREFLIGHT * len(CANDIDATES),
        "planning_cost_usd": planning_total,
        "single_attempt_reserved_cost_usd": reserved_total,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (output_dir / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    latest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    latest["status"] = "frozen_unpaid"
    latest["cost_estimate"] = result
    (output_dir / "manifest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )
    return result


def authorize_model_bakeoff_v2(
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
        "recorded_at": _now(),
        "user_authorized": True,
        "authorization_scope": "response_validity_model_bakeoff_v2",
        "provider_payload_sha256": payload_sha,
        "n_maximum_requests": manifest["n_maximum_provider_requests"],
        "candidate_routes": [
            {"model_id": c["model_id"], "provider_tag": c["provider_tag"]}
            for c in CANDIDATES
        ],
        "fallbacks_disabled": True,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def _call(client, request: dict, codebook: dict) -> dict:
    candidate = _candidate(request["candidate_id"])
    started = time.time()
    response = client.chat.completions.create(
        model=request["model_id"],
        messages=request["messages"],
        temperature=request["temperature"],
        max_tokens=request["max_output_tokens"],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "response_validity_v2_4",
                "strict": True,
                "schema": request["response_schema"],
            },
        },
        extra_body={
            "reasoning": request["reasoning"],
            "provider": request["provider"],
        },
        timeout=240,
    )
    message = response.choices[0].message
    message_dump = message.model_dump() if hasattr(message, "model_dump") else {}
    raw = message.content or ""
    usage = response.usage.model_dump() if response.usage else {}
    cost = usage.get("cost")
    if cost is None:
        cost = (
            float(usage.get("prompt_tokens", 0)) * candidate["input_price"]
            + float(usage.get("completion_tokens", 0)) * candidate["output_price"]
        ) / 1e6
    reasoning_present = bool(
        message_dump.get("reasoning") or message_dump.get("reasoning_details")
    )
    base = {
        "provider_request_id": request["provider_request_id"],
        "logical_request_id": request["logical_request_id"],
        "audit_response_id": request["audit_response_id"],
        "candidate_id": request["candidate_id"],
        "model_id": request["model_id"],
        "provider_tag_requested": candidate["provider_tag"],
        "is_preflight": request["is_preflight"],
        "usage": usage,
        "incremental_provider_cost": float(cost),
        "provider_response_id": response.id,
        "provider_model": response.model,
        "reasoning_present_in_response": reasoning_present,
        "raw_provider_content": raw,
        "raw_provider_content_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "elapsed_seconds": time.time() - started,
        "created_at": _now(),
    }
    try:
        label = json.loads(raw)
        errors = validate_v23(label, codebook)
        if reasoning_present:
            errors.append("reasoning content was returned despite exclusion request")
        if errors:
            raise ValueError("; ".join(errors))
        return {**base, **label, "status": "complete"}
    except Exception as exc:
        return {
            **base,
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc)[:1000],
        }


def run_model_bakeoff_v2(
    root: Path,
    output_dir: Path,
    workers: int,
    ceiling: float,
    authorized: bool,
) -> dict:
    """Run the authorized preflight-gated maximum payload resumably."""
    if not authorized:
        raise RuntimeError("paid run requires --authorize-paid-run")
    if workers < 1 or workers > 32:
        raise ValueError("workers must be between 1 and 32")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload_path = output_dir / "provider_requests.jsonl"
    authorization = manifest.get("authorization", {})
    expected_routes = [
        {"model_id": c["model_id"], "provider_tag": c["provider_tag"]}
        for c in CANDIDATES
    ]
    if not (
        authorization.get("user_authorized") is True
        and authorization.get("provider_payload_sha256") == sha_file(payload_path)
        and authorization.get("candidate_routes") == expected_routes
        and authorization.get("fallbacks_disabled") is True
        and float(authorization.get("cost_ceiling_usd", -1)) == float(ceiling)
    ):
        raise RuntimeError("authorization does not match exact payload and ceiling")

    from openai import OpenAI

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    requests = _read_jsonl(payload_path)
    attempts_path = output_dir / "attempts.jsonl"
    results_path = output_dir / "results.jsonl"
    completed: dict[str, dict] = {}
    attempt_counts: dict[str, int] = {}
    spent = 0.0
    for record in _read_jsonl(attempts_path):
        spent += float(record.get("incremental_provider_cost", 0))
        request_id = record["provider_request_id"]
        attempt_counts[request_id] = attempt_counts.get(request_id, 0) + 1
        if record.get("status") == "complete":
            completed[request_id] = record
    codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
    lock_path = output_dir / ".run.lock"
    lock_path.touch(exist_ok=True)

    def execute(group: list[dict], handle) -> None:
        nonlocal spent
        pending = [r for r in group if r["provider_request_id"] not in completed]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures: dict = {}
            cursor = 0
            reserved = 0.0
            while cursor < len(pending) or futures:
                while cursor < len(pending) and len(futures) < workers:
                    request = pending[cursor]
                    request_id = request["provider_request_id"]
                    if attempt_counts.get(request_id, 0) >= MAX_ATTEMPTS:
                        cursor += 1
                        continue
                    candidate = _candidate(request["candidate_id"])
                    hold = (
                        request["estimated_input_tokens"] * candidate["input_price"]
                        + request["max_output_tokens"] * candidate["output_price"]
                    ) / 1e6
                    if spent + reserved + hold > ceiling + 1e-9:
                        break
                    cursor += 1
                    future = pool.submit(_call, client, request, codebook)
                    futures[future] = (request, hold)
                    reserved += hold
                if not futures:
                    break
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    request, hold = futures.pop(future)
                    reserved -= hold
                    try:
                        record = future.result()
                    except Exception as exc:
                        record = {
                            "provider_request_id": request["provider_request_id"],
                            "logical_request_id": request["logical_request_id"],
                            "audit_response_id": request["audit_response_id"],
                            "candidate_id": request["candidate_id"],
                            "model_id": request["model_id"],
                            "provider_tag_requested": _candidate(
                                request["candidate_id"]
                            )["provider_tag"],
                            "is_preflight": request["is_preflight"],
                            "status": "error",
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:1000],
                            "incremental_provider_cost": 0.0,
                            "created_at": _now(),
                            "raw_provider_content": None,
                        }
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                    request_id = request["provider_request_id"]
                    attempt_counts[request_id] = attempt_counts.get(request_id, 0) + 1
                    spent += float(record.get("incremental_provider_cost", 0))
                    if spent > ceiling + 1e-9:
                        raise RuntimeError("hard provider-cost ceiling exceeded")
                    if record.get("status") == "complete":
                        completed[request_id] = record
                    elif attempt_counts[request_id] < MAX_ATTEMPTS:
                        pending.append(request)

    preflight_rows = []
    admitted: list[str] = []
    with lock_path.open("r+") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with attempts_path.open("a", encoding="utf-8") as handle:
            for candidate in CANDIDATES:
                cid = candidate["candidate_id"]
                preflight_group = [
                    r for r in requests
                    if r["candidate_id"] == cid and r["is_preflight"]
                ]
                execute(preflight_group, handle)
                valid = sum(
                    r["provider_request_id"] in completed for r in preflight_group
                )
                passed = valid >= SCHEMA_GATE_PREFLIGHT_N
                preflight_rows.append({
                    "candidate_id": cid,
                    "n_expected": N_PREFLIGHT,
                    "n_valid": valid,
                    "schema_success": valid / N_PREFLIGHT,
                    "gate_valid_n": SCHEMA_GATE_PREFLIGHT_N,
                    "preflight_pass": passed,
                })
                if passed:
                    admitted.append(cid)
            pd.DataFrame(preflight_rows).to_csv(
                output_dir / "preflight_results.csv", index=False
            )
            for cid in admitted:
                continuation = [
                    r for r in requests
                    if r["candidate_id"] == cid and not r["is_preflight"]
                ]
                execute(continuation, handle)

    included_requests = [
        r for r in requests if r["candidate_id"] in admitted
    ]
    ordered = [
        completed[r["provider_request_id"]]
        for r in included_requests
        if r["provider_request_id"] in completed
    ]
    _write_jsonl(results_path, ordered)
    by_candidate = []
    for candidate in CANDIDATES:
        cid = candidate["candidate_id"]
        n_complete = sum(r.get("candidate_id") == cid for r in ordered)
        admitted_flag = cid in admitted
        expected = EXPECTED_N if admitted_flag else N_PREFLIGHT
        by_candidate.append({
            "candidate_id": cid,
            "preflight_pass": admitted_flag,
            "n_expected_after_gate": expected,
            "n_completed": n_complete,
            "schema_success": n_complete / expected,
            "full_schema_gate_pass": (
                admitted_flag
                and n_complete / EXPECTED_N >= SCHEMA_GATE_OVERALL
            ),
        })
    pd.DataFrame(by_candidate).to_csv(
        output_dir / "run_coverage_by_candidate.csv", index=False
    )
    summary = {
        "completed_at": _now(),
        "n_candidates": len(CANDIDATES),
        "n_preflight_passed": len(admitted),
        "admitted_candidate_ids": admitted,
        "n_maximum_requests": len(requests),
        "n_results": len(ordered),
        "provider_cost_usd": spent,
        "authorized_ceiling_usd": float(ceiling),
        "provider_payload_sha256": sha_file(payload_path),
        "attempts_sha256": sha_file(attempts_path),
        "results_sha256": sha_file(results_path),
        "network_call_made": True,
        "raw_provider_content_preserved_before_validation": True,
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    manifest["status"] = "completed"
    manifest["network_call_made"] = True
    manifest["run_summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary


def _f1(reference: pd.Series, candidate: pd.Series) -> float:
    return float(_binary_metrics(reference, candidate)["f1"])


def _bootstrap_f1_difference(
    frame: pd.DataFrame, candidate_col: str, reps: int = BOOTSTRAP_REPS
) -> tuple[float, float, float]:
    # F1 depends only on TP, FP and FN. Aggregate those three counts by issue
    # once, then resample issue rows. This is exactly the same cluster
    # bootstrap as repeatedly concatenating response frames, but is orders of
    # magnitude faster and avoids unnecessary memory allocation.
    reference = frame.pred_genuine_refusal_sol.astype(bool)
    candidate = frame[candidate_col].astype(bool)
    luna = frame.pred_genuine_refusal_luna.astype(bool)
    counts = pd.DataFrame({
        "issue_id": frame.issue_id.astype(str),
        "candidate_tp": (reference & candidate).astype(int),
        "candidate_fp": (~reference & candidate).astype(int),
        "candidate_fn": (reference & ~candidate).astype(int),
        "luna_tp": (reference & luna).astype(int),
        "luna_fp": (~reference & luna).astype(int),
        "luna_fn": (reference & ~luna).astype(int),
    }).groupby("issue_id", sort=True).sum()
    matrix = counts.to_numpy(dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = rng.integers(0, len(matrix), size=(reps, len(matrix)))
    totals = matrix[draws].sum(axis=1)

    def f1_from_counts(tp: np.ndarray, fp: np.ndarray, fn: np.ndarray) -> np.ndarray:
        denominator = 2 * tp + fp + fn
        return np.divide(
            2 * tp, denominator,
            out=np.full_like(denominator, np.nan, dtype=float),
            where=denominator > 0,
        )

    values = (
        f1_from_counts(totals[:, 0], totals[:, 1], totals[:, 2])
        - f1_from_counts(totals[:, 3], totals[:, 4], totals[:, 5])
    )
    point = (
        _f1(frame.pred_genuine_refusal_sol, frame[candidate_col])
        - _f1(frame.pred_genuine_refusal_sol, frame.pred_genuine_refusal_luna)
    )
    return point, float(np.nanquantile(values, 0.025)), float(np.nanquantile(values, 0.975))


def score_model_bakeoff_v2(root: Path, output_dir: Path | None = None) -> dict:
    """Score surviving candidates against Sol and apply frozen promotion gates."""
    output_dir = output_dir or root / DEFAULT_DIR
    run = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    results = _derive(pd.DataFrame(_read_jsonl(output_dir / "results.jsonl")))
    partition = pd.read_csv(output_dir / "evaluation_partition.csv")
    luna = _load_labels(root / LUNA_DIR / "results.jsonl", "luna")
    sol = _load_labels(root / SOL_DIR / "results.jsonl", "sol")
    base = partition.merge(luna, on="audit_response_id", validate="one_to_one")
    base = base.merge(sol, on="audit_response_id", validate="one_to_one")
    protected = base.loc[base.evaluation_role.ne("boundary_development")].copy()
    coverage = pd.read_csv(output_dir / "run_coverage_by_candidate.csv")
    rows = []
    language_rows = []
    paired_rows = []
    decisions = []
    for candidate in CANDIDATES:
        cid = candidate["candidate_id"]
        gate = coverage.loc[coverage.candidate_id.eq(cid)].iloc[0]
        if not bool(gate.preflight_pass):
            decisions.append({
                "candidate_id": cid,
                "eligible": False,
                "decision": "failed_preflight",
            })
            continue
        candidate_results = results.loc[results.candidate_id.eq(cid)].copy()
        candidate_results = candidate_results.rename(columns={
            "pred_genuine_refusal": "pred_genuine_refusal_candidate",
            "pred_capability_failure": "pred_capability_failure_candidate",
        })
        joined = protected.merge(
            candidate_results[[
                "audit_response_id", "pred_genuine_refusal_candidate",
                "pred_capability_failure_candidate",
            ]],
            on="audit_response_id", validate="one_to_one",
        )
        refusal = _binary_metrics(
            joined.pred_genuine_refusal_sol,
            joined.pred_genuine_refusal_candidate,
        )
        capability = _binary_metrics(
            joined.pred_capability_failure_sol,
            joined.pred_capability_failure_candidate,
        )
        for outcome, metrics in (
            ("genuine_refusal", refusal), ("capability_failure", capability)
        ):
            rows.append({"candidate_id": cid, "outcome": outcome, **metrics})
        for language, group in joined.groupby("prompt_language"):
            metrics = _binary_metrics(
                group.pred_genuine_refusal_sol,
                group.pred_genuine_refusal_candidate,
            )
            language_rows.append({
                "candidate_id": cid,
                "prompt_language": language,
                "outcome": "genuine_refusal",
                **metrics,
            })
        point, lower, upper = _bootstrap_f1_difference(
            joined, "pred_genuine_refusal_candidate"
        )
        paired_rows.append({
            "candidate_id": cid,
            "f1_difference_candidate_minus_luna": point,
            "cluster_bootstrap_95_lower": lower,
            "cluster_bootstrap_95_upper": upper,
            "bootstrap_reps": BOOTSTRAP_REPS,
            "bootstrap_seed": BOOTSTRAP_SEED,
        })
        min_language_recall = min(
            row["recall"] for row in language_rows
            if row["candidate_id"] == cid and not math.isnan(row["recall"])
        )
        coverage_eligible = bool(gate.full_schema_gate_pass)
        quality_eligible = (
            refusal["precision"] >= 0.90
            and refusal["recall"] >= 0.90
            and refusal["f1"] >= 0.92
            and lower > -0.02
        )
        eligible = coverage_eligible and quality_eligible
        if eligible:
            decision = "provisionally_noninferior"
        elif not coverage_eligible:
            decision = "failed_full_schema_coverage"
        else:
            decision = "failed_quality_gate"
        decisions.append({
            "candidate_id": cid,
            "eligible": eligible,
            "coverage_eligible": coverage_eligible,
            "refusal_precision": refusal["precision"],
            "refusal_recall": refusal["recall"],
            "refusal_f1": refusal["f1"],
            "minimum_language_recall": min_language_recall,
            "f1_difference_lower": lower,
            "decision": decision,
        })
    metrics = pd.DataFrame(rows)
    languages = pd.DataFrame(language_rows)
    paired = pd.DataFrame(paired_rows)
    promotion = pd.DataFrame(decisions)
    metrics.to_csv(output_dir / "metrics_overall.csv", index=False)
    languages.to_csv(output_dir / "metrics_by_language.csv", index=False)
    paired.to_csv(output_dir / "paired_differences.csv", index=False)
    promotion.to_csv(output_dir / "promotion_decision.csv", index=False)
    eligible = promotion.loc[promotion.eligible.eq(True)].copy()
    selected = None
    if len(eligible):
        costs = []
        attempts = _read_jsonl(output_dir / "attempts.jsonl")
        for cid in eligible.candidate_id:
            total = sum(
                float(r.get("incremental_provider_cost", 0))
                for r in attempts if r.get("candidate_id") == cid
            )
            costs.append({"candidate_id": cid, "observed_cost_usd": total})
        cost_frame = pd.DataFrame(costs)
        eligible = eligible.merge(cost_frame, on="candidate_id", validate="one_to_one")
        eligible["cost_per_1000_valid"] = (
            eligible.observed_cost_usd / 1197 * 1000
        )
        selected = str(eligible.sort_values(
            ["cost_per_1000_valid", "minimum_language_recall"],
            ascending=[True, False], kind="mergesort",
        ).iloc[0].candidate_id)
    summary = {
        "version": "response-validity-model-bakeoff-v2-score",
        "scored_at": _now(),
        "machine_reference": "GPT-5.6 Sol v2.4",
        "human_gold": False,
        "protected_model_selection_n": len(protected),
        "selected_candidate_id": selected,
        "decision": "candidate_selected" if selected else "retain_luna",
        "interpretation": (
            "Selection is agreement with a frozen machine reference. Fresh "
            "probability-sample human certification remains required."
        ),
        "input_sha256": {
            "results": sha_file(output_dir / "results.jsonl"),
            "luna_results": sha_file(root / LUNA_DIR / "results.jsonl"),
            "sol_results": sha_file(root / SOL_DIR / "results.jsonl"),
            "partition": sha_file(output_dir / "evaluation_partition.csv"),
        },
    }
    (output_dir / "score_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary
