"""Stage B cross-model surrogate bake-off.

The builder and cost estimator are network-free. They derive an exact
504-request execution payload from three immutable Stage A configurations,
freeze first-party OpenRouter routing and reasoning policies, and verify that
no human label enters a request. Authorization and execution are separate,
explicitly gated operations.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import pandas as pd

from .human_pilot import sha_file
from .surrogate_bakeoff import (
    _response_schema,
    _validate_bakeoff_label,
    score_surrogate_results,
)


STAGE_B_CONFIGS = (
    "zero_shot_joint_v1",
    "fewshot_joint_7_v1",
    "fewshot_error_targeted_22_v1",
)
STAGE_B_MODELS = (
    "google/gemini-3.5-flash-lite",
    "anthropic/claude-haiku-4.5",
)
EXPECTED_EVALUATION_ROWS = 84
EXPECTED_LOGICAL_REQUESTS = 252
EXPECTED_PROVIDER_REQUESTS = 504


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_sha(record: dict) -> str:
    payload = json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            )


def _load_pricing(root: Path) -> tuple[Path, dict, dict[str, dict]]:
    path = root / "config" / "surrogate_bakeoff_stage_b_models_v1.json"
    pricing = json.loads(path.read_text(encoding="utf-8"))
    models = {row["model_id"]: row for row in pricing["models"]}
    if tuple(models) != STAGE_B_MODELS:
        raise ValueError("Stage B pricing roster or order changed")
    for model in models.values():
        if model["allow_fallbacks"] is not False or not model["provider_tag"]:
            raise ValueError("Stage B requires one named provider and no fallbacks")
    return path, pricing, models


def build_stage_b_bakeoff(
    root: Path,
    pilot_dir: Path,
    output_dir: Path | None = None,
) -> dict:
    """Freeze the exact unpaid Stage B logical and provider request payloads."""
    stage_a = pilot_dir / "surrogate_bakeoff_v1"
    adjudication = pilot_dir / "stage_a_adjudication_v1" / "freeze_v1"
    output_dir = output_dir or pilot_dir / "surrogate_bakeoff_stage_b_v1"
    manifest_path = output_dir / "stage_b_manifest.json"
    required = {
        "stage_a_manifest": stage_a / "bakeoff_manifest.json",
        "stage_a_requests": stage_a / "model_neutral_requests.jsonl",
        "stage_a_configs": stage_a / "prompt_configurations.csv",
        "stage_a_evaluation": stage_a / "evaluation_gold.parquet",
        "stage_a_luna_results": stage_a / "stage_a_luna_results.jsonl",
        "adjudicated_evaluation": adjudication / "evaluation_gold_adjudicated.parquet",
        "adjudication_manifest": adjudication / "freeze_manifest.json",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"cannot build Stage B; missing {missing}")
    pricing_path, pricing, models = _load_pricing(root)

    stage_a_manifest = json.loads(required["stage_a_manifest"].read_text(encoding="utf-8"))
    expected_stage_a_payload = stage_a_manifest["logical_payload_sha256"]
    if sha_file(required["stage_a_requests"]) != expected_stage_a_payload:
        raise RuntimeError("Stage A request payload differs from its manifest")
    if stage_a_manifest.get("stage_a_run", {}).get("n_completed") != 420:
        raise RuntimeError("Stage A must be complete before Stage B is frozen")

    input_sha = {name: sha_file(path) for name, path in required.items()}
    input_sha["pricing_config"] = sha_file(pricing_path)
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("input_sha256") != input_sha:
            raise RuntimeError("existing Stage B freeze uses different inputs")
        for name, digest in existing.get("artifact_sha256", {}).items():
            path = output_dir / name
            if not path.exists() or sha_file(path) != digest:
                raise RuntimeError(f"Stage B artifact missing or changed: {path}")
        return existing
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested Stage B directory: {output_dir}")

    stage_a_requests = _read_jsonl(required["stage_a_requests"])
    logical = [
        row for row in stage_a_requests if row["config_id"] in STAGE_B_CONFIGS
    ]
    logical.sort(key=lambda row: (row["config_id"], row["evaluation_review_id"]))
    if len(logical) != EXPECTED_LOGICAL_REQUESTS:
        raise ValueError(f"expected 252 Stage B logical requests, found {len(logical)}")
    if len({row["request_id"] for row in logical}) != EXPECTED_LOGICAL_REQUESTS:
        raise ValueError("Stage B logical request IDs are not unique")
    if set(row["config_id"] for row in logical) != set(STAGE_B_CONFIGS):
        raise ValueError("Stage B configuration set is incomplete")
    if len({row["evaluation_review_id"] for row in logical}) != EXPECTED_EVALUATION_ROWS:
        raise ValueError("Stage B does not cover exactly 84 evaluation responses")
    if any("gold" in row or "primary_class" in row for row in logical):
        raise ValueError("human outcome leaked into model-neutral Stage B payload")

    configs = pd.read_csv(required["stage_a_configs"])
    configs = configs.loc[configs.config_id.isin(STAGE_B_CONFIGS)].copy()
    if len(configs) != len(STAGE_B_CONFIGS):
        raise ValueError("frozen Stage A prompt configuration metadata is incomplete")
    request_config_hashes = {
        config_id: {row["messages"][0]["content"] for row in logical if row["config_id"] == config_id}
        for config_id in STAGE_B_CONFIGS
    }
    for row in configs.itertuples(index=False):
        prompts = request_config_hashes[row.config_id]
        if len(prompts) != 1:
            raise ValueError(f"{row.config_id} has multiple system prompts")
        observed = hashlib.sha256(next(iter(prompts)).encode("utf-8")).hexdigest()
        if observed != row.system_prompt_sha256:
            raise RuntimeError(f"system prompt hash mismatch for {row.config_id}")

    try:
        import tiktoken

        encoding = tiktoken.get_encoding("o200k_base")
    except ImportError as exc:
        raise RuntimeError("tiktoken is required to freeze Stage B token volume") from exc

    provider_requests: list[dict] = []
    token_rows: list[dict] = []
    schema = _response_schema()
    schema_tokens = len(encoding.encode(json.dumps(schema, sort_keys=True)))
    for model_id in STAGE_B_MODELS:
        policy = models[model_id]
        for request in logical:
            message_tokens = len(encoding.encode("\n".join(
                message["content"] for message in request["messages"]
            )))
            frozen = {
                "source_request_id": request["request_id"],
                "evaluation_review_id": request["evaluation_review_id"],
                "config_id": request["config_id"],
                "model_id": model_id,
                "messages": request["messages"],
                "response_schema": request["response_schema"],
                "temperature": 0,
                "max_output_tokens": int(pricing["max_output_tokens"]),
                "reasoning": policy["reasoning"],
                "provider": {
                    "only": [policy["provider_tag"]],
                    "allow_fallbacks": False,
                },
                "estimated_input_tokens": message_tokens + schema_tokens,
            }
            frozen["stage_b_request_id"] = _canonical_sha(frozen)[:24]
            provider_requests.append(frozen)
            token_rows.append({
                "stage_b_request_id": frozen["stage_b_request_id"],
                "model_id": model_id,
                "config_id": request["config_id"],
                "estimated_input_tokens": frozen["estimated_input_tokens"],
                "planning_output_tokens": int(pricing["planning_output_tokens"]),
                "max_output_tokens": int(pricing["max_output_tokens"]),
                "encoding": "o200k_base",
                "schema_tokens_included": True,
            })
    if len(provider_requests) != EXPECTED_PROVIDER_REQUESTS:
        raise AssertionError("Stage B provider payload is not 504 requests")
    if len({row["stage_b_request_id"] for row in provider_requests}) != EXPECTED_PROVIDER_REQUESTS:
        raise AssertionError("Stage B provider request IDs are not unique")

    output_dir.mkdir(parents=True, exist_ok=False)
    logical_path = output_dir / "model_neutral_requests.jsonl"
    provider_path = output_dir / "stage_b_requests.jsonl"
    configs_path = output_dir / "prompt_configurations.csv"
    token_path = output_dir / "token_volume.csv"
    schema_path = output_dir / "response_schema.json"
    route_path = output_dir / "model_route_policy.json"
    _write_jsonl(logical_path, logical)
    _write_jsonl(provider_path, provider_requests)
    configs.sort_values("config_id").to_csv(configs_path, index=False)
    pd.DataFrame(token_rows).to_csv(token_path, index=False)
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    route_path.write_text(json.dumps({
        "models": pricing["models"],
        "temperature": 0,
        "max_output_tokens": pricing["max_output_tokens"],
        "structured_output": "strict json_schema",
        "retry_rule": f"up to {pricing['max_attempts']} total attempts per logical request",
        "fallbacks": False,
    }, indent=2), encoding="utf-8")
    artifacts = [logical_path, provider_path, configs_path, token_path, schema_path, route_path]
    manifest = {
        "stage_b_version": "human-surrogate-bakeoff-stage-b-v1.0",
        "created_at": _now(),
        "status": "frozen_unpaid_unauthorized",
        "purpose": "cross-model development comparison; not final surrogate selection",
        "n_evaluation": EXPECTED_EVALUATION_ROWS,
        "configurations": list(STAGE_B_CONFIGS),
        "models": list(STAGE_B_MODELS),
        "n_logical_requests": EXPECTED_LOGICAL_REQUESTS,
        "n_provider_requests": EXPECTED_PROVIDER_REQUESTS,
        "split_unit": "prompt_id inherited unchanged from Stage A",
        "original_and_adjudicated_labels_excluded_from_payload": True,
        "existing_luna_results_reused": True,
        "final_model_selection_authorized": False,
        "paid_run_authorized": False,
        "paid_or_network_call_made": False,
        "input_sha256": input_sha,
        "logical_payload_sha256": sha_file(logical_path),
        "provider_payload_sha256": sha_file(provider_path),
        "configuration_sha256": {
            row.config_id: row.system_prompt_sha256 for row in configs.itertuples(index=False)
        },
        "artifact_sha256": {path.name: sha_file(path) for path in artifacts},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_stage_b_cost(root: Path, output_dir: Path) -> dict:
    """Apply the dated first-party route prices to the frozen 504 requests."""
    manifest_path = output_dir / "stage_b_manifest.json"
    token_path = output_dir / "token_volume.csv"
    summary_path = output_dir / "cost_estimate_summary.json"
    costs_path = output_dir / "cost_estimate.csv"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha_file(token_path) != manifest["artifact_sha256"]["token_volume.csv"]:
        raise RuntimeError("Stage B token volume differs from its manifest")
    pricing_path, pricing, models = _load_pricing(root)
    if sha_file(pricing_path) != manifest["input_sha256"]["pricing_config"]:
        raise RuntimeError("Stage B price snapshot changed after payload freeze")
    if summary_path.exists():
        existing = json.loads(summary_path.read_text(encoding="utf-8"))
        if (
            existing.get("pricing_sha256") != sha_file(pricing_path)
            or existing.get("provider_payload_sha256") != manifest["provider_payload_sha256"]
            or not costs_path.exists()
            or sha_file(costs_path) != existing.get("artifact_sha256", {}).get("cost_estimate.csv")
        ):
            raise RuntimeError("existing Stage B cost freeze differs from payload or pricing")
        return existing
    tokens = pd.read_csv(token_path)
    rows: list[dict] = []
    for (model_id, config_id), part in tokens.groupby(["model_id", "config_id"], sort=True):
        model = models[model_id]
        input_tokens = int(part.estimated_input_tokens.sum())
        planning_output = int(part.planning_output_tokens.sum())
        max_output = int(part.max_output_tokens.sum())
        rows.append({
            "model_id": model_id,
            "provider_tag": model["provider_tag"],
            "config_id": config_id,
            "requests": len(part),
            "estimated_input_tokens": input_tokens,
            "planning_output_tokens": planning_output,
            "max_output_tokens": max_output,
            "planning_cost_usd": (
                input_tokens * model["input_usd_per_million"]
                + planning_output * model["output_usd_per_million"]
            ) / 1_000_000,
            "single_attempt_reserved_cost_usd": (
                input_tokens * model["input_usd_per_million"]
                + max_output * model["output_usd_per_million"]
            ) / 1_000_000,
            "pricing_source": model["pricing_source"],
        })
    costs = pd.DataFrame(rows)
    costs.to_csv(costs_path, index=False)
    summary = {
        "estimate_version": "surrogate-bakeoff-stage-b-cost-v1.0",
        "created_at": _now(),
        "pricing_verified_at": pricing["pricing_verified_at"],
        "pricing_sha256": sha_file(pricing_path),
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "models": list(STAGE_B_MODELS),
        "configurations": list(STAGE_B_CONFIGS),
        "calls": int(costs.requests.sum()),
        "planning_cost_usd": float(costs.planning_cost_usd.sum()),
        "single_attempt_reserved_cost_usd": float(costs.single_attempt_reserved_cost_usd.sum()),
        "suggested_hard_ceiling_usd": float(pricing["suggested_hard_ceiling_usd"]),
        "prompt_cache_discount_assumed": False,
        "network_call_made": False,
        "paid_run_authorized": False,
        "artifact_sha256": {"cost_estimate.csv": sha_file(costs_path)},
    }
    summary_path.write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def record_stage_b_authorization(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
) -> dict:
    """Record a future exact user authorization; never infer authorization."""
    if not confirmed:
        raise RuntimeError("Stage B authorization requires explicit confirmation")
    manifest_path = output_dir / "stage_b_manifest.json"
    payload_path = output_dir / "stage_b_requests.jsonl"
    cost_path = output_dir / "cost_estimate_summary.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    costs = json.loads(cost_path.read_text(encoding="utf-8"))
    observed = sha_file(payload_path)
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized hash differs from the frozen Stage B payload")
    if float(ceiling) != float(costs["suggested_hard_ceiling_usd"]):
        raise ValueError("ceiling differs from the frozen suggested Stage B ceiling")
    cost_csv = output_dir / "cost_estimate.csv"
    if (
        costs.get("pricing_sha256") != manifest.get("input_sha256", {}).get("pricing_config")
        or not cost_csv.exists()
        or costs.get("artifact_sha256", {}).get("cost_estimate.csv") != sha_file(cost_csv)
    ):
        raise RuntimeError("Stage B cost freeze is missing or changed")
    authorization = {
        "recorded_at": _now(),
        "user_authorized": True,
        "purpose": "Stage B cross-model development bake-off",
        "provider": "OpenRouter",
        "provider_payload_sha256": payload_sha,
        "models": list(STAGE_B_MODELS),
        "configurations": list(STAGE_B_CONFIGS),
        "n_requests": EXPECTED_PROVIDER_REQUESTS,
        "provider_tags": ["google-ai-studio", "anthropic"],
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_yet_complete"
    manifest["stage_b_authorization"] = authorization
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def _provider_call(client, request: dict, model_prices: dict) -> dict:
    started = time.time()
    response = client.chat.completions.create(
        model=request["model_id"],
        messages=request["messages"],
        temperature=request["temperature"],
        max_tokens=request["max_output_tokens"],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "response_validity_surrogate_v1",
                "strict": True,
                "schema": request["response_schema"],
            },
        },
        extra_body={
            "reasoning": request["reasoning"],
            "provider": request["provider"],
        },
        timeout=180,
    )
    usage = response.usage.model_dump() if response.usage else {}
    cost = usage.get("cost")
    if cost is None:
        cost = (
            float(usage.get("prompt_tokens", 0)) * model_prices["input_usd_per_million"]
            + float(usage.get("completion_tokens", 0)) * model_prices["output_usd_per_million"]
        ) / 1_000_000
    try:
        label = _validate_bakeoff_label(json.loads(response.choices[0].message.content))
        status, error_type, error = "complete", None, None
    except Exception as exc:
        label = {}
        status, error_type, error = "error", type(exc).__name__, str(exc)[:1000]
    return {
        "stage_b_request_id": request["stage_b_request_id"],
        "request_id": request["source_request_id"],
        "evaluation_review_id": request["evaluation_review_id"],
        "config_id": request["config_id"],
        "model_id": request["model_id"],
        **label,
        "status": status,
        "error_type": error_type,
        "error": error,
        "provider_response_id": response.id,
        "provider_model": response.model,
        "provider_tag_requested": request["provider"]["only"][0],
        "usage": usage,
        "incremental_provider_cost": float(cost),
        "elapsed_seconds": time.time() - started,
        "created_at": _now(),
    }


def run_stage_b(
    root: Path, output_dir: Path, workers: int, ceiling: float, authorized: bool
) -> dict:
    """Run the exact authorized 504 requests resumably under a hard ceiling."""
    if not authorized:
        raise RuntimeError("Stage B requires an explicit paid-run flag")
    manifest_path = output_dir / "stage_b_manifest.json"
    payload_path = output_dir / "stage_b_requests.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    auth = manifest.get("stage_b_authorization", {})
    if not (
        auth.get("user_authorized") is True
        and auth.get("provider_payload_sha256") == sha_file(payload_path)
        == manifest["provider_payload_sha256"]
        and float(auth.get("cost_ceiling_usd", -1)) == float(ceiling)
        and int(auth.get("n_requests", -1)) == EXPECTED_PROVIDER_REQUESTS
    ):
        raise RuntimeError("manifest lacks the exact Stage B authorization")
    lock = (output_dir / ".stage_b_run.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock.close()
        raise RuntimeError("another Stage B process holds the run lock") from exc
    try:
        requests = _read_jsonl(payload_path)
        if len(requests) != EXPECTED_PROVIDER_REQUESTS:
            raise ValueError("Stage B payload is not exactly 504 requests")
        _, pricing, model_prices = _load_pricing(root)
        scripts = root / "scripts"
        if str(scripts) not in os.sys.path:
            os.sys.path.insert(0, str(scripts))
        from env_utils import get_openrouter_client

        client = get_openrouter_client()
        raw_path = output_dir / "stage_b_raw.jsonl"
        existing = _read_jsonl(raw_path) if raw_path.exists() else []
        completed = {
            row["stage_b_request_id"]: row
            for row in existing if row.get("status") == "complete"
        }
        attempts: dict[str, int] = {}
        histories: dict[str, list[dict]] = {}
        for row in existing:
            key = row.get("stage_b_request_id")
            attempts[key] = attempts.get(key, 0) + 1
            histories.setdefault(key, []).append(row)
        actual_cost = sum(float(row.get("incremental_provider_cost", 0) or 0) for row in existing)
        if actual_cost >= ceiling:
            raise RuntimeError("existing Stage B cost reaches the authorized ceiling")
        # The initial run exhausted the frozen four-attempt allowance for a small
        # set of zero-cost provider-capacity 429s.  Permit at most two narrowly
        # scoped completion attempts for those requests only.  This does not
        # alter the payload, model, provider route, fallback policy, or ceiling.
        rate_limit_completion_ids = {
            key
            for key, rows in histories.items()
            if key not in completed
            and len(rows) >= int(pricing["max_attempts"])
            and all(row.get("error_type") == "RateLimitError" for row in rows)
        }

        def attempt_limit(request_id: str) -> int:
            base = int(pricing["max_attempts"])
            return base + 2 if request_id in rate_limit_completion_ids else base

        queue = [
            row for row in requests
            if row["stage_b_request_id"] not in completed
            and attempts.get(row["stage_b_request_id"], 0) < attempt_limit(row["stage_b_request_id"])
        ]
        write_lock = threading.Lock()

        def reservation(request: dict) -> float:
            model = model_prices[request["model_id"]]
            return (
                request["estimated_input_tokens"] * model["input_usd_per_million"]
                + request["max_output_tokens"] * model["output_usd_per_million"]
            ) / 1_000_000

        def append(record: dict) -> None:
            with write_lock, raw_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())

        futures = {}
        reserved = 0.0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while queue or futures:
                while queue and len(futures) < workers:
                    request = queue.pop(0)
                    hold = reservation(request)
                    if actual_cost + reserved + hold > ceiling:
                        raise RuntimeError("in-flight reservation would cross the Stage B ceiling")
                    reserved += hold
                    futures[pool.submit(
                        _provider_call, client, request, model_prices[request["model_id"]]
                    )] = (request, hold)
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    request, hold = futures.pop(future)
                    reserved -= hold
                    try:
                        record = future.result()
                    except Exception as exc:
                        record = {
                            "stage_b_request_id": request["stage_b_request_id"],
                            "request_id": request["source_request_id"],
                            "evaluation_review_id": request["evaluation_review_id"],
                            "config_id": request["config_id"],
                            "model_id": request["model_id"],
                            "status": "error",
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:1000],
                            "incremental_provider_cost": 0.0,
                            "created_at": _now(),
                        }
                    append(record)
                    actual_cost += float(record.get("incremental_provider_cost", 0) or 0)
                    key = request["stage_b_request_id"]
                    attempts[key] = attempts.get(key, 0) + 1
                    if actual_cost > ceiling:
                        raise RuntimeError("provider-reported Stage B cost crossed the ceiling")
                    if record["status"] == "complete":
                        completed[key] = record
                    elif attempts[key] < attempt_limit(key):
                        queue.append(request)
        missing = [row["stage_b_request_id"] for row in requests if row["stage_b_request_id"] not in completed]
        if missing:
            raise RuntimeError(f"Stage B incomplete after retries: {len(missing)}")
        assembled_path = output_dir / "stage_b_results.jsonl"
        _write_jsonl(assembled_path, [completed[row["stage_b_request_id"]] for row in requests])
        summary = {
            "run_version": "surrogate-bakeoff-stage-b-v1.0",
            "completed_at": _now(),
            "models": list(STAGE_B_MODELS),
            "provider_tags": [model_prices[model]["provider_tag"] for model in STAGE_B_MODELS],
            "allow_fallbacks": False,
            "provider_payload_sha256": sha_file(payload_path),
            "n_completed": len(completed),
            "raw_records": len(_read_jsonl(raw_path)),
            "provider_cost_usd": actual_cost,
            "authorized_ceiling_usd": ceiling,
            "rate_limit_completion": {
                "policy": "up to two extra attempts only after four RateLimitError records",
                "n_eligible_requests": len(rate_limit_completion_ids),
                "request_ids_sha256": hashlib.sha256(
                    "\n".join(sorted(rate_limit_completion_ids)).encode("utf-8")
                ).hexdigest(),
            },
            "assembled_sha256": sha_file(assembled_path),
        }
        (output_dir / "stage_b_run_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        manifest["paid_or_network_call_made"] = True
        manifest["status"] = "completed_not_yet_scored"
        manifest["stage_b_run"] = summary
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return summary
    finally:
        lock.close()


def score_stage_b(root: Path, pilot_dir: Path) -> dict:
    """Score Luna + Stage B models under both immutable human label versions."""
    stage_a = pilot_dir / "surrogate_bakeoff_v1"
    stage_b = pilot_dir / "surrogate_bakeoff_stage_b_v1"
    stage_b_manifest = json.loads((stage_b / "stage_b_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((stage_b / "stage_b_run_summary.json").read_text(encoding="utf-8"))
    stage_b_results = stage_b / "stage_b_results.jsonl"
    if sha_file(stage_b_results) != summary["assembled_sha256"]:
        raise RuntimeError("Stage B results differ from the completed run summary")
    luna = [
        row for row in _read_jsonl(stage_a / "stage_a_luna_results.jsonl")
        if row["config_id"] in STAGE_B_CONFIGS
    ]
    new = _read_jsonl(stage_b_results)
    combined = luna + new
    if len(combined) != 756:
        raise ValueError("combined three-model comparison must contain 756 rows")
    combined_path = stage_b / "three_model_results.jsonl"
    _write_jsonl(combined_path, combined)

    gold_versions = {
        "original": stage_a / "evaluation_gold.parquet",
        "adjudicated_development": (
            pilot_dir / "stage_a_adjudication_v1" / "freeze_v1"
            / "evaluation_gold_adjudicated.parquet"
        ),
    }
    metric_frames: list[pd.DataFrame] = []
    for version, gold_path in gold_versions.items():
        scoring_dir = stage_b / f"scoring_{version}"
        scoring_dir.mkdir(exist_ok=True)
        gold = pd.read_parquet(gold_path)
        scoring_gold = scoring_dir / "evaluation_gold.parquet"
        gold.to_parquet(scoring_gold, index=False)
        (scoring_dir / "bakeoff_manifest.json").write_text(json.dumps({
            "bakeoff_version": f"stage-b-{version}-score-v1.0",
            "artifact_sha256": {"evaluation_gold.parquet": sha_file(scoring_gold)},
        }, indent=2), encoding="utf-8")
        metrics = score_surrogate_results(scoring_dir, combined_path)
        metrics.insert(0, "human_label_version", version)
        metric_frames.append(metrics)
    all_metrics = pd.concat(metric_frames, ignore_index=True)
    metrics_path = stage_b / "stage_b_metrics_both_label_versions.csv"
    all_metrics.to_csv(metrics_path, index=False)

    result = pd.DataFrame([row for row in combined if row.get("status") == "complete"])
    agreement_rows: list[dict] = []
    disagreement_rows: list[dict] = []
    for config_id, part in result.groupby("config_id", sort=True):
        wide = part.pivot(index="evaluation_review_id", columns="model_id", values="primary_class")
        if len(wide) != EXPECTED_EVALUATION_ROWS or wide.isna().any().any():
            raise ValueError(f"incomplete model comparison for {config_id}")
        for left, right in combinations(sorted(wide.columns), 2):
            agreement_rows.append({
                "config_id": config_id, "model_left": left, "model_right": right,
                "class": "all", "metric": "exact_agreement",
                "value": float(wide[left].eq(wide[right]).mean()), "n": len(wide),
            })
            for primary_class in _response_schema()["properties"]["primary_class"]["enum"]:
                a = wide[left].eq(primary_class)
                b = wide[right].eq(primary_class)
                denominator = int(a.sum() + b.sum())
                agreement_rows.append({
                    "config_id": config_id, "model_left": left, "model_right": right,
                    "class": primary_class, "metric": "positive_agreement",
                    "value": (2 * int((a & b).sum()) / denominator) if denominator else None,
                    "n": denominator,
                })
        for review_id, row in wide.iterrows():
            values = row.to_dict()
            disagreement_rows.append({
                "config_id": config_id,
                "evaluation_review_id": review_id,
                "n_unique_predictions": len(set(values.values())),
                "unanimous": len(set(values.values())) == 1,
                **{f"prediction__{model}": value for model, value in values.items()},
            })
    agreement_path = stage_b / "stage_b_model_agreement.csv"
    disagreement_path = stage_b / "stage_b_row_disagreements.csv"
    pd.DataFrame(agreement_rows).to_csv(agreement_path, index=False)
    pd.DataFrame(disagreement_rows).to_csv(disagreement_path, index=False)
    score_summary = {
        "score_version": "surrogate-bakeoff-stage-b-score-v1.0",
        "created_at": _now(),
        "interpretation": "development evidence only; no consensus truth and no final surrogate selection",
        "label_versions": list(gold_versions),
        "models": sorted(result.model_id.unique()),
        "configurations": list(STAGE_B_CONFIGS),
        "artifact_sha256": {
            path.name: sha_file(path)
            for path in [combined_path, metrics_path, agreement_path, disagreement_path]
        },
        "network_call_made": False,
        "parent_provider_payload_sha256": stage_b_manifest["provider_payload_sha256"],
    }
    (stage_b / "stage_b_score_summary.json").write_text(
        json.dumps(score_summary, indent=2), encoding="utf-8"
    )
    stage_b_manifest["status"] = "completed_and_scored"
    stage_b_manifest["stage_b_score"] = score_summary
    (stage_b / "stage_b_manifest.json").write_text(
        json.dumps(stage_b_manifest, indent=2), encoding="utf-8"
    )
    return score_summary
