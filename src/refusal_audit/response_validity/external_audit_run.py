"""Authorize and run the paired external response-validity audit.

Unlike the local freeze module, this module contains the paid OpenRouter
runner.  Execution is bound to both frozen payload hashes, the OpenAI provider,
disabled fallbacks/reasoning, and one cumulative cost ceiling.  Every attempt
is appended and fsynced before it can be retried.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .human_pilot import sha_file
from .luna_v23_repair import _derive, validate_v23


DEFAULT_DIR = "annotations/response_validity_human_v2/external_audit_v1"
CODEBOOK = "config/response_validity_decomposed_v2_3.json"
PROVIDER = "openai"
MAX_ATTEMPTS = 3
EXPECTED_N = 1197
EXPECTED_CEILING = 16.0
EXPECTED_HASHES = {
    "luna": "6d4f26dc9d2d668d5875720b3d008e5ac20b6fe4940dc6db74392349a7affee4",
    "sol": "d60874cfe3d52c07644be37f36fa9da8891b68a0c42ab1d65da7e07cbc59f8b6",
}
PRICES = {
    "openai/gpt-5.6-luna": (0.20, 1.20),
    "openai/gpt-5.6-sol": (2.00, 10.00),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: invalid JSON line {number}") from exc
    return rows


def authorize_external_audit(
    output_dir: Path, luna_sha: str, sol_sha: str, ceiling: float,
    confirmed: bool,
) -> dict:
    """Record the exact user authorization without making a provider call."""
    if not confirmed:
        raise RuntimeError("explicit authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    supplied = {"luna": luna_sha, "sol": sol_sha}
    observed = {
        key: sha_file(output_dir / f"{key}_provider_requests.jsonl")
        for key in EXPECTED_HASHES
    }
    if supplied != EXPECTED_HASHES or observed != EXPECTED_HASHES:
        raise ValueError("authorized external payload hashes do not match frozen bytes")
    if manifest.get("provider_payload_sha256") != EXPECTED_HASHES:
        raise ValueError("manifest external payload hashes do not match authorization")
    if float(ceiling) != EXPECTED_CEILING:
        raise ValueError("authorized ceiling does not match the frozen $16 ceiling")
    if manifest.get("network_call_made") is not False:
        raise ValueError("external audit already records a network call")
    authorization = {
        "recorded_at": _now(),
        "user_authorized": True,
        "authorization_scope": "paired_external_model_annotation",
        "n_unique_responses": EXPECTED_N,
        "n_requests_by_model": {"luna": EXPECTED_N, "sol": EXPECTED_N},
        "model_ids": {
            "luna": "openai/gpt-5.6-luna", "sol": "openai/gpt-5.6-sol",
        },
        "provider_tag": PROVIDER,
        "allow_fallbacks": False,
        "reasoning_disabled": True,
        "provider_payload_sha256": supplied,
        "cumulative_cost_ceiling_usd": float(ceiling),
        "user_authorization_text": (
            "I authorize sending the frozen 1,197-response external validity "
            "audit to OpenRouter for 1,197 Luna and 1,197 Sol requests through "
            "OpenAI, with reasoning and fallbacks disabled, under a cumulative "
            "$16 hard ceiling."
        ),
    }
    (output_dir / "authorization.json").write_text(
        json.dumps(authorization, indent=2), encoding="utf-8"
    )
    manifest["authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def _call(client, request: dict, codebook: dict) -> dict:
    started = time.time()
    response = client.chat.completions.create(
        model=request["model_id"], messages=request["messages"],
        temperature=request["temperature"],
        max_tokens=request["max_output_tokens"],
        response_format={"type": "json_schema", "json_schema": {
            "name": "external_response_validity_v2_3", "strict": True,
            "schema": request["response_schema"],
        }},
        extra_body={
            "reasoning": request["reasoning"], "provider": request["provider"],
        },
        timeout=180,
    )
    usage = response.usage.model_dump() if response.usage else {}
    cost = usage.get("cost")
    input_price, output_price = PRICES[request["model_id"]]
    if cost is None:
        cost = (
            float(usage.get("prompt_tokens", 0)) * input_price
            + float(usage.get("completion_tokens", 0)) * output_price
        ) / 1e6
    raw = response.choices[0].message.content or ""
    base = {
        "provider_request_id": request["provider_request_id"],
        "logical_request_id": request["logical_request_id"],
        "audit_response_id": request["audit_response_id"],
        "model_id": request["model_id"],
        "provider_tag_requested": PROVIDER,
        "usage": usage,
        "incremental_provider_cost": float(cost),
        "unreconciled_reserved_cost": 0.0,
        "provider_response_id": response.id,
        "provider_model": response.model,
        "raw_provider_content": raw,
        "raw_provider_content_sha256": hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest(),
        "elapsed_seconds": time.time() - started,
        "created_at": _now(),
    }
    try:
        label = json.loads(raw)
        errors = validate_v23(label, codebook)
        if errors:
            raise ValueError("; ".join(errors))
        return {**base, **label, "status": "complete"}
    except Exception as exc:
        return {
            **base, "status": "error", "error_type": type(exc).__name__,
            "error": str(exc)[:1000],
        }


def _load_requests(output_dir: Path) -> list[dict]:
    by_model = {
        key: _read_jsonl(output_dir / f"{key}_provider_requests.jsonl")
        for key in EXPECTED_HASHES
    }
    for key, rows in by_model.items():
        if len(rows) != EXPECTED_N:
            raise ValueError(f"external {key} payload is not {EXPECTED_N} rows")
    # Interleave the two judges case-by-case so a ceiling interruption cannot
    # leave one model systematically farther through the sample.
    combined = []
    for luna, sol in zip(by_model["luna"], by_model["sol"]):
        if luna["logical_request_id"] != sol["logical_request_id"]:
            raise ValueError("paired external payload ordering changed")
        combined.extend((luna, sol))
    return combined


def _reserve(request: dict) -> float:
    input_price, output_price = PRICES[request["model_id"]]
    return (
        float(request["estimated_input_tokens"]) * input_price
        + float(request["max_output_tokens"]) * output_price
    ) / 1e6


def run_external_audit(
    root: Path, output_dir: Path, workers: int, ceiling: float,
    authorized: bool,
) -> dict:
    """Run the exact authorized paired payload resumably under one ceiling."""
    if not authorized:
        raise RuntimeError("paid run requires --authorize-paid-run")
    if workers < 1 or workers > 32:
        raise ValueError("workers must be between 1 and 32")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    authorization = manifest.get("authorization", {})
    observed = {
        key: sha_file(output_dir / f"{key}_provider_requests.jsonl")
        for key in EXPECTED_HASHES
    }
    if not (
        authorization.get("user_authorized") is True
        and authorization.get("provider_payload_sha256") == EXPECTED_HASHES
        and observed == EXPECTED_HASHES
        and authorization.get("provider_tag") == PROVIDER
        and authorization.get("allow_fallbacks") is False
        and authorization.get("reasoning_disabled") is True
        and float(authorization.get("cumulative_cost_ceiling_usd", -1))
        == float(ceiling) == EXPECTED_CEILING
    ):
        raise RuntimeError("authorization does not match both payloads and ceiling")
    summary_path = output_dir / "run_summary.json"
    if summary_path.exists():
        prior = json.loads(summary_path.read_text(encoding="utf-8"))
        if prior.get("n_completed") == 2 * EXPECTED_N:
            for key in EXPECTED_HASHES:
                if prior["results_sha256"][key] != sha_file(
                    output_dir / f"{key}_results.jsonl"
                ):
                    raise ValueError("completed external result hash changed")
            return prior

    from openai import OpenAI
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    requests = _load_requests(output_dir)
    attempts_path = output_dir / "attempts.jsonl"
    completed: dict[str, dict] = {}
    attempts: dict[str, int] = {}
    actual_spent = 0.0
    unreconciled_reserved = 0.0
    for row in _read_jsonl(attempts_path):
        actual_spent += float(row.get("incremental_provider_cost", 0))
        unreconciled_reserved += float(row.get("unreconciled_reserved_cost", 0))
        request_id = row["provider_request_id"]
        attempts[request_id] = attempts.get(request_id, 0) + 1
        if row.get("status") == "complete":
            completed[request_id] = row
    pending = [
        row for row in requests if row["provider_request_id"] not in completed
    ]
    codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
    lock_path = output_dir / ".run.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with attempts_path.open("a", encoding="utf-8") as handle:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures: dict = {}
                cursor = 0
                inflight_reserved = 0.0
                while cursor < len(pending) or futures:
                    while cursor < len(pending) and len(futures) < workers:
                        request = pending[cursor]
                        request_id = request["provider_request_id"]
                        if attempts.get(request_id, 0) >= MAX_ATTEMPTS:
                            cursor += 1
                            continue
                        hold = _reserve(request)
                        guarded = actual_spent + unreconciled_reserved
                        if guarded + inflight_reserved + hold > ceiling + 1e-9:
                            break
                        cursor += 1
                        future = pool.submit(_call, client, request, codebook)
                        futures[future] = (request, hold)
                        inflight_reserved += hold
                    if not futures:
                        break
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        request, hold = futures.pop(future)
                        inflight_reserved -= hold
                        try:
                            record = future.result()
                        except Exception as exc:
                            # The upstream may have processed an HTTP request
                            # before the local exception. Reserve its full
                            # maximum permanently unless usage is reconciled.
                            record = {
                                "provider_request_id": request["provider_request_id"],
                                "logical_request_id": request["logical_request_id"],
                                "audit_response_id": request["audit_response_id"],
                                "model_id": request["model_id"],
                                "status": "error",
                                "error_type": type(exc).__name__,
                                "error": str(exc)[:1000],
                                "incremental_provider_cost": 0.0,
                                "unreconciled_reserved_cost": hold,
                                "raw_provider_content": None,
                                "created_at": _now(),
                            }
                        handle.write(
                            json.dumps(record, ensure_ascii=False, sort_keys=True)
                            + "\n"
                        )
                        handle.flush()
                        os.fsync(handle.fileno())
                        request_id = request["provider_request_id"]
                        attempts[request_id] = attempts.get(request_id, 0) + 1
                        actual_spent += float(
                            record.get("incremental_provider_cost", 0)
                        )
                        unreconciled_reserved += float(
                            record.get("unreconciled_reserved_cost", 0)
                        )
                        if actual_spent + unreconciled_reserved > ceiling + 1e-9:
                            raise RuntimeError("hard provider-cost ceiling exceeded")
                        if record.get("status") == "complete":
                            completed[request_id] = record
                        elif attempts[request_id] < MAX_ATTEMPTS:
                            pending.append(request)

    results_sha = {}
    counts = {}
    for model_key in EXPECTED_HASHES:
        payload = _read_jsonl(
            output_dir / f"{model_key}_provider_requests.jsonl"
        )
        ordered = [
            completed[row["provider_request_id"]]
            for row in payload if row["provider_request_id"] in completed
        ]
        result_path = output_dir / f"{model_key}_results.jsonl"
        with result_path.open("w", encoding="utf-8") as handle:
            for row in ordered:
                handle.write(
                    json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                )
        results_sha[model_key] = sha_file(result_path)
        counts[model_key] = len(ordered)
    n_completed = sum(counts.values())
    summary = {
        "completed_at": _now(),
        "n_expected": 2 * EXPECTED_N,
        "n_completed": n_completed,
        "n_incomplete": 2 * EXPECTED_N - n_completed,
        "n_completed_by_model": counts,
        "schema_success": n_completed / (2 * EXPECTED_N),
        "schema_success_gate": 0.995,
        "schema_gate_pass": n_completed / (2 * EXPECTED_N) >= 0.995,
        "provider_reported_cost_usd": actual_spent,
        "unreconciled_reserved_cost_usd": unreconciled_reserved,
        "ceiling_guard_cost_usd": actual_spent + unreconciled_reserved,
        "authorized_cumulative_ceiling_usd": float(ceiling),
        "provider_payload_sha256": EXPECTED_HASHES,
        "attempts_sha256": sha_file(attempts_path),
        "results_sha256": results_sha,
        "network_call_made": True,
        "raw_provider_content_preserved_before_validation": True,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest["status"] = (
        "completed" if n_completed == 2 * EXPECTED_N else "incomplete"
    )
    manifest["network_call_made"] = True
    manifest["run_summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary


def summarize_external_audit(root: Path, output_dir: Path) -> dict:
    """Validate and pair the completed machine labels without treating them as gold."""
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    if run.get("n_completed") != 2 * EXPECTED_N:
        raise RuntimeError("external model audit is incomplete")
    frozen_summary_path = output_dir / "machine_comparison_summary.json"
    frozen_paired_path = output_dir / "paired_machine_labels.parquet"
    if frozen_summary_path.exists():
        existing = json.loads(frozen_summary_path.read_text(encoding="utf-8"))
        if (
            not frozen_paired_path.exists()
            or existing.get("paired_machine_labels_sha256")
            != sha_file(frozen_paired_path)
        ):
            raise ValueError("frozen external machine summary artifact changed")
        return existing
    codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
    frames = {}
    label_fields = [
        "task_behavior", "substantive_refusal", "stance_disclaimer",
        "epistemic_limitation", "language_fidelity", "output_quality",
        "technical_failure", "confidence", "refusal_evidence_span",
        "decision_note",
    ]
    for key in EXPECTED_HASHES:
        path = output_dir / f"{key}_results.jsonl"
        if sha_file(path) != run["results_sha256"][key]:
            raise ValueError(f"external {key} result hash changed")
        rows = _read_jsonl(path)
        if len(rows) != EXPECTED_N:
            raise ValueError(f"external {key} result count changed")
        for row in rows:
            raw = row.get("raw_provider_content")
            if raw is None or hashlib.sha256(raw.encode("utf-8")).hexdigest() != row.get(
                "raw_provider_content_sha256"
            ):
                raise ValueError(f"external {key} raw content hash mismatch")
            errors = validate_v23({name: row[name] for name in label_fields}, codebook)
            if errors:
                raise ValueError(f"external {key} result fails v2.3: {errors}")
        frame = _derive(pd.DataFrame(rows))
        keep = ["audit_response_id", *label_fields,
                "pred_genuine_refusal", "pred_capability_failure"]
        frames[key] = frame[keep].rename(columns={
            name: f"{name}_{key}" for name in keep if name != "audit_response_id"
        })
    paired = frames["luna"].merge(
        frames["sol"], on="audit_response_id", validate="one_to_one"
    )
    design = pd.read_parquet(output_dir / "sample_design.parquet")
    paired = design.merge(paired, on="audit_response_id", validate="one_to_one")
    paired["refusal_disagreement"] = paired.pred_genuine_refusal_luna.ne(
        paired.pred_genuine_refusal_sol
    )
    paired["capability_disagreement"] = paired.pred_capability_failure_luna.ne(
        paired.pred_capability_failure_sol
    )
    attempts = _read_jsonl(output_dir / "attempts.jsonl")
    error_ids = {
        row["audit_response_id"] for row in attempts
        if row.get("status") != "complete"
    }
    paired["any_schema_attempt_error"] = paired.audit_response_id.isin(error_ids)
    paired["phase2_priority"] = (
        paired.pred_genuine_refusal_luna
        | paired.pred_genuine_refusal_sol
        | paired.refusal_disagreement
        | paired.capability_disagreement
        | paired.confidence_luna.eq("low")
        | paired.confidence_sol.eq("low")
        | paired.any_schema_attempt_error
    )
    paired["phase2_stratum"] = "ordinary_agreement"
    capability_agreement = (
        ~paired.phase2_priority
        & ~paired.pred_genuine_refusal_luna
        & ~paired.pred_genuine_refusal_sol
        & paired.pred_capability_failure_luna
        & paired.pred_capability_failure_sol
    )
    paired.loc[capability_agreement, "phase2_stratum"] = (
        "capability_positive_agreement"
    )
    paired.loc[paired.phase2_priority, "phase2_stratum"] = "priority"
    q = {"priority": 1.0, "capability_positive_agreement": .5,
         "ordinary_agreement": .1}
    paired["planned_phase2_probability"] = paired.phase2_stratum.map(q)
    paired_path = frozen_paired_path
    paired.to_parquet(paired_path, index=False)
    counts = paired.phase2_stratum.value_counts()
    result = {
        "version": "external-audit-machine-summary-v1",
        "created_at": _now(),
        "status": "machine_labels_complete_human_reference_pending",
        "n_responses": len(paired),
        "genuine_refusal_n": {
            "luna": int(paired.pred_genuine_refusal_luna.sum()),
            "sol": int(paired.pred_genuine_refusal_sol.sum()),
        },
        "genuine_refusal_disagreement_n": int(paired.refusal_disagreement.sum()),
        "capability_failure_n": {
            "luna": int(paired.pred_capability_failure_luna.sum()),
            "sol": int(paired.pred_capability_failure_sol.sum()),
        },
        "capability_failure_disagreement_n": int(
            paired.capability_disagreement.sum()
        ),
        "any_headline_disagreement_n": int(
            (paired.refusal_disagreement | paired.capability_disagreement).sum()
        ),
        "low_confidence_n": int(
            (paired.confidence_luna.eq("low") | paired.confidence_sol.eq("low")).sum()
        ),
        "schema_attempt_error_response_n": len(error_ids),
        "phase2_stratum_n": {
            name: int(counts.get(name, 0)) for name in q
        },
        "expected_human_reviews_before_realized_phase2_draw": float(
            paired.planned_phase2_probability.sum()
        ),
        "provider_reported_cost_usd": run["provider_reported_cost_usd"],
        "human_reference_complete": False,
        "external_certification_complete": False,
        "paired_machine_labels_sha256": sha_file(paired_path),
    }
    summary_path = frozen_summary_path
    summary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    manifest["status"] = "machine_labels_complete_human_reference_pending"
    manifest["machine_comparison_summary"] = result
    manifest.setdefault("postrun_artifact_sha256", {}).update({
        "paired_machine_labels.parquet": sha_file(paired_path),
        "machine_comparison_summary.json": sha_file(summary_path),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result
