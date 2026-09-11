"""Freeze the unpaid wall-to-wall Luna v2.4 annotation stage.

The corpus contains 137,186 canonical responses. Two disjoint sets (1,197 and
1,196 rows) already have complete Luna labels produced with the byte-identical
v2.4 prompt and schema. This module reuses those 2,393 labels and freezes only
the remaining 134,793 requests.

To avoid writing about two gigabytes of repeated system-prompt text, the freeze
stores a compact request index. Its logical payload hash is computed over the
same canonical provider-request JSON lines that a paid runner must reconstruct
and verify before making any network call.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import fcntl
import random
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import tiktoken

from .enrichment_design_v2 import build_routing_population
from .human_pilot import KEY, sha_file
from .luna_v23_repair import _schema, _user
from .luna_v24_evaluation import (
    INPUT_PRICE,
    MAX_ATTEMPTS,
    MAX_OUTPUT_TOKENS,
    MODEL,
    OUTPUT_PRICE,
    PLANNING_OUTPUT_TOKENS,
    PRICING_SOURCE,
    PRICING_VERIFIED_AT,
    PROVIDER,
    _call,
    _system_v24,
)
from .luna_v24_human_certification import _input_hashes


DEFAULT_DIR = "annotations/response_validity_v2_4/wall_to_wall_luna_v1"
CODEBOOK = "config/response_validity_decomposed_v2_4.json"
OLD_EXTERNAL_DIR = (
    "annotations/response_validity_human_v2/external_audit_v1/"
    "luna_v2_4_evaluation_v1"
)
FRESH_DIR = (
    "annotations/response_validity_human_v2/"
    "luna_v2_4_human_certification_v1/phase1"
)
EXPECTED_POPULATION_N = 137_186
EXPECTED_REUSE_N = 2_393
EXPECTED_NEW_N = 134_793
LOGICAL_PAYLOAD_FORMAT = "canonical-jsonl-sort-keys-utf8-v1"
INITIAL_CONCURRENCY = 12
MIN_CONCURRENCY = 4
PROGRESS_EVERY_COMPLETIONS = 100
PROGRESS_EVERY_SECONDS = 30


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha_object(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _source_hash(row: dict) -> str:
    return _sha_object({
        "prompt_language": str(row["prompt_language"]),
        "prompt_text_en": str(row["prompt_text_en"]),
        "prompt_text": str(row["prompt_text"]),
        "response_text": str(row["response_text"]),
    })


def _provider_request(row: dict, system: str, schema: dict) -> dict:
    logical_id = _sha_object({
        "key": [str(row[col]) for col in KEY],
        "source_sha256": _source_hash(row),
        "version": "wall-to-wall-luna-v2.4-v1",
    })[:24]
    return {
        "logical_request_id": logical_id,
        "provider_request_id": _sha_object({
            "logical_request_id": logical_id, "model_id": MODEL,
        })[:24],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _user(row, "source_response_only")},
        ],
        "response_schema": schema,
        "model_id": MODEL,
        "provider": {"only": [PROVIDER], "allow_fallbacks": False},
        "reasoning": {"enabled": False, "exclude": True},
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


def _canonical_line(request: dict) -> bytes:
    return (
        json.dumps(
            request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    ).encode("utf-8")


def _load_population(root: Path) -> pd.DataFrame:
    population, _, _ = build_routing_population(
        root, root / "annotations/response_validity_human_v2", 20260823
    )
    required = {*KEY, "prompt_text_en", "prompt_text", "response_text"}
    if missing := required - set(population.columns):
        raise ValueError(f"wall-to-wall population lacks columns: {sorted(missing)}")
    if len(population) != EXPECTED_POPULATION_N or population.duplicated(KEY).any():
        raise ValueError("wall-to-wall population must have 137,186 unique keys")
    if population[list(required)].isna().any().any():
        raise ValueError("wall-to-wall request fields contain missing values")
    return population.sort_values(KEY, kind="mergesort").reset_index(drop=True)


def _reuse_keys(root: Path) -> tuple[pd.DataFrame, dict]:
    old = pd.read_csv(root / OLD_EXTERNAL_DIR / "evaluation_partition.csv")
    # The evaluation partition contains IDs only; the original sample design
    # supplies the canonical response key.
    old_design = pd.read_parquet(
        root / "annotations/response_validity_human_v2/external_audit_v1/"
        "sample_design.parquet", columns=KEY
    )
    fresh_design = pd.read_parquet(root / FRESH_DIR / "sample_design.parquet", columns=KEY)
    if len(old) != len(old_design):
        raise ValueError("old v2.4 evaluation partition and sample differ")
    if len(old_design) != 1_197 or len(fresh_design) != 1_196:
        raise ValueError("reusable v2.4 designs have unexpected sizes")
    old_results = root / OLD_EXTERNAL_DIR / "results.jsonl"
    fresh_results = root / FRESH_DIR / "results.jsonl"
    if sum(1 for line in old_results.open(encoding="utf-8") if line.strip()) != 1_197:
        raise ValueError("old v2.4 results are incomplete")
    if sum(1 for line in fresh_results.open(encoding="utf-8") if line.strip()) != 1_196:
        raise ValueError("fresh v2.4 results are incomplete")
    old_prompt = root / OLD_EXTERNAL_DIR / "prompt.txt"
    fresh_prompt = root / FRESH_DIR / "prompt.txt"
    old_schema = root / OLD_EXTERNAL_DIR / "response_schema.json"
    fresh_schema = root / FRESH_DIR / "response_schema.json"
    if sha_file(old_prompt) != sha_file(fresh_prompt):
        raise ValueError("reusable runs used different v2.4 prompts")
    if sha_file(old_schema) != sha_file(fresh_schema):
        raise ValueError("reusable runs used different response schemas")
    if set(map(tuple, old_design.itertuples(index=False, name=None))) & set(
        map(tuple, fresh_design.itertuples(index=False, name=None))
    ):
        raise ValueError("reusable v2.4 sets unexpectedly overlap")
    reuse = pd.concat([old_design, fresh_design], ignore_index=True)
    if len(reuse) != EXPECTED_REUSE_N or reuse.duplicated(KEY).any():
        raise ValueError("reusable v2.4 key union is invalid")
    return reuse, {
        "old_external_results": sha_file(old_results),
        "fresh_validation_results": sha_file(fresh_results),
        "shared_prompt": sha_file(old_prompt),
        "shared_schema": sha_file(old_schema),
    }


def prepare_wall_to_wall_luna_v24(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Freeze the compact, unpaid 134,793-request annotation stage."""
    output_dir = output_dir or root / DEFAULT_DIR
    manifest_path = output_dir / "manifest.json"
    base_hashes = _input_hashes(root)
    reuse, reuse_hashes = _reuse_keys(root)
    input_hashes = {**base_hashes, **reuse_hashes}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("wall-to-wall freeze no longer matches its inputs")
        for name, expected in manifest.get("artifact_sha256", {}).items():
            if sha_file(output_dir / name) != expected:
                raise ValueError(f"wall-to-wall frozen artifact changed: {name}")
        return manifest
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested directory: {output_dir}")

    population = _load_population(root)
    reuse_set = set(map(tuple, reuse[KEY].itertuples(index=False, name=None)))
    pending = population.loc[
        ~population[KEY].apply(tuple, axis=1).isin(reuse_set)
    ].copy()
    if len(pending) != EXPECTED_NEW_N or pending.duplicated(KEY).any():
        raise ValueError("pending Luna v2.4 population must contain 134,793 rows")

    codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
    system, schema = _system_v24(codebook), _schema()
    encoder = tiktoken.get_encoding("o200k_base")
    logical_hasher = hashlib.sha256()
    index_rows: list[dict] = []
    total_input_tokens = 0
    for row in pending.to_dict("records"):
        request = _provider_request(row, system, schema)
        logical_hasher.update(_canonical_line(request))
        user = request["messages"][1]["content"]
        estimated_tokens = len(encoder.encode(
            system + "\n" + user + "\n" + json.dumps(schema, sort_keys=True)
        ))
        total_input_tokens += estimated_tokens
        index_rows.append({
            **{col: str(row[col]) for col in KEY},
            "logical_request_id": request["logical_request_id"],
            "provider_request_id": request["provider_request_id"],
            "source_sha256": _source_hash(row),
            "estimated_input_tokens": estimated_tokens,
        })

    output_dir.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(index_rows).to_parquet(output_dir / "request_index.parquet", index=False)
    (output_dir / "prompt.txt").write_text(system, encoding="utf-8")
    (output_dir / "response_schema.json").write_text(
        json.dumps(schema, indent=2), encoding="utf-8"
    )
    reuse.to_parquet(output_dir / "reused_response_keys.parquet", index=False)
    artifacts = (
        "request_index.parquet", "prompt.txt", "response_schema.json",
        "reused_response_keys.parquet",
    )
    manifest = {
        "version": "wall-to-wall-luna-v2.4-v1",
        "created_at": _now(),
        "status": "frozen_unpaid",
        "scientific_role": "uniform first-pass v2.4 annotation of the canonical corpus",
        "population_n": EXPECTED_POPULATION_N,
        "reused_exact_v2_4_labels_n": EXPECTED_REUSE_N,
        "new_provider_requests_n": EXPECTED_NEW_N,
        "reuse_rule": (
            "reuse only completed Luna records with byte-identical v2.4 prompt "
            "and response schema"
        ),
        "codebook_version": codebook["codebook_version"],
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_attempts": MAX_ATTEMPTS,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "logical_payload_format": LOGICAL_PAYLOAD_FORMAT,
        "logical_provider_payload_sha256": logical_hasher.hexdigest(),
        "estimated_input_tokens": total_input_tokens,
        "input_sha256": input_hashes,
        "artifact_sha256": {name: sha_file(output_dir / name) for name in artifacts},
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_wall_to_wall_luna_v24_cost(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Price the frozen logical payload locally; never call a provider."""
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare_wall_to_wall_luna_v24(root, output_dir)
    requests = int(manifest["new_provider_requests_n"])
    inputs = int(manifest["estimated_input_tokens"])
    planning = (
        inputs * INPUT_PRICE + requests * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    reserved = (
        inputs * INPUT_PRICE + requests * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    reference_rows = [
        json.loads(line)
        for line in (root / FRESH_DIR / "results.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line
    ]
    reference_cost = sum(
        float(row.get("incremental_provider_cost", 0)) for row in reference_rows
    )
    empirical_projection = reference_cost / len(reference_rows) * requests
    # The hard ceiling allows nearly twice the observed per-row cost while
    # stopping before the uncached maximum-output reservation can be consumed.
    ceiling = math.ceil(max(empirical_projection * 1.9, planning * 1.1) * 2) / 2
    result = {
        "version": "wall-to-wall-luna-v2.4-cost-v1",
        "created_at": _now(),
        "pricing_verified_at": PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": requests,
        "estimated_input_tokens": inputs,
        "planning_output_tokens": requests * PLANNING_OUTPUT_TOKENS,
        "maximum_output_tokens_single_attempt": requests * MAX_OUTPUT_TOKENS,
        "planning_cost_usd": planning,
        "single_attempt_reserved_cost_usd": reserved,
        "empirical_reference": {
            "completed_requests": len(reference_rows),
            "observed_cost_usd": reference_cost,
            "projected_new_request_cost_usd": empirical_projection,
            "note": (
                "projection from the completed fresh v2.4 Luna run; observed "
                "prompt caching is not guaranteed for the full run"
            ),
        },
        "suggested_hard_ceiling_usd": ceiling,
        "logical_provider_payload_sha256": manifest[
            "logical_provider_payload_sha256"
        ],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (output_dir / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    latest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    latest["cost_estimate"] = result
    latest["artifact_sha256"]["cost_estimate.json"] = sha_file(
        output_dir / "cost_estimate.json"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )
    return result


def authorize_wall_to_wall_luna_v24(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
) -> dict:
    """Record exact authorization without making a provider call."""
    if not confirmed:
        raise RuntimeError("explicit authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cost = json.loads((output_dir / "cost_estimate.json").read_text(encoding="utf-8"))
    if payload_sha != manifest["logical_provider_payload_sha256"]:
        raise ValueError("authorized hash does not match the logical payload")
    if float(ceiling) != float(cost["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized ceiling does not match the frozen estimate")
    authorization = {
        "recorded_at": _now(),
        "user_authorized": True,
        "authorization_scope": "wall_to_wall_luna_v2_4_v1",
        "logical_provider_payload_sha256": payload_sha,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": int(manifest["new_provider_requests_n"]),
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _retry_policy(exc: Exception, attempt_number: int) -> dict:
    """Classify an API exception and calculate one explicit retry delay."""
    status = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    retry_after = None
    for name in ("retry-after", "Retry-After"):
        if name in headers:
            try:
                retry_after = max(0.0, float(headers[name]))
            except (TypeError, ValueError):
                retry_after = None
            break
    transient_statuses = {408, 409, 429, 500, 502, 503, 504}
    transient_names = ("timeout", "connection", "ratelimit", "internalserver")
    name = type(exc).__name__.lower()
    transient = status in transient_statuses or any(token in name for token in transient_names)
    base = min(60.0, 2.0 ** max(0, attempt_number - 1))
    delay = max(base + random.uniform(0.0, 0.75), retry_after or 0.0)
    return {
        "http_status": status,
        "is_rate_limit": status == 429,
        "transient": transient,
        "retry_after_seconds": retry_after,
        "retry_delay_seconds": delay if transient else None,
    }


def _write_progress(path: Path, value: dict) -> None:
    """Atomically replace the human-readable progress snapshot."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def _reconstruct_pending(root: Path, output_dir: Path) -> list[dict]:
    """Rebuild and verify every authorized request before network access."""
    population = _load_population(root)
    index = pd.read_parquet(output_dir / "request_index.parquet")
    if len(index) != EXPECTED_NEW_N or index.duplicated(KEY).any():
        raise ValueError("frozen request index is invalid")
    frame = index.merge(
        population[[*KEY, "prompt_text_en", "prompt_text", "response_text"]],
        on=KEY, how="left", validate="one_to_one",
    ).sort_values(KEY, kind="mergesort")
    if len(frame) != EXPECTED_NEW_N or frame.response_text.isna().any():
        raise ValueError("request index no longer joins to the canonical population")
    codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
    system, schema = _system_v24(codebook), _schema()
    hasher = hashlib.sha256()
    requests: list[dict] = []
    for row in frame.to_dict("records"):
        if _source_hash(row) != row["source_sha256"]:
            raise ValueError("canonical source text changed after the freeze")
        request = _provider_request(row, system, schema)
        if request["logical_request_id"] != row["logical_request_id"]:
            raise ValueError("logical request ID changed after the freeze")
        if request["provider_request_id"] != row["provider_request_id"]:
            raise ValueError("provider request ID changed after the freeze")
        request["audit_response_id"] = request["logical_request_id"]
        request["estimated_input_tokens"] = int(row["estimated_input_tokens"])
        hasher.update(_canonical_line({
            key: value for key, value in request.items()
            if key not in {"audit_response_id", "estimated_input_tokens"}
        }))
        requests.append(request)
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    if hasher.hexdigest() != manifest["logical_provider_payload_sha256"]:
        raise ValueError("reconstructed logical payload hash does not match the freeze")
    return requests


def run_wall_to_wall_luna_v24(
    root: Path, output_dir: Path, workers: int, ceiling: float, authorized: bool
) -> dict:
    """Run only the authorized compact payload, resumably and append-only."""
    if not authorized:
        raise RuntimeError("paid run requires --authorize-paid-run")
    if workers < 1 or workers > 32:
        raise ValueError("workers must be between 1 and 32")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    authorization = manifest.get("authorization", {})
    if not (
        authorization.get("user_authorized") is True
        and authorization.get("logical_provider_payload_sha256")
        == manifest.get("logical_provider_payload_sha256")
        and authorization.get("model_id") == MODEL
        and authorization.get("provider_tag") == PROVIDER
        and authorization.get("reasoning_disabled") is True
        and authorization.get("allow_fallbacks") is False
        and float(authorization.get("cost_ceiling_usd", -1)) == float(ceiling)
    ):
        raise RuntimeError("authorization does not match the frozen payload and ceiling")

    results_path = output_dir / "results.jsonl"
    summary_path = output_dir / "run_summary.json"
    if results_path.exists() and summary_path.exists():
        prior = json.loads(summary_path.read_text(encoding="utf-8"))
        if (
            prior.get("n_completed") == EXPECTED_NEW_N
            and prior.get("results_sha256") == sha_file(results_path)
        ):
            return prior

    # This full reconstruction and hash check occurs before importing the API
    # client or reading its key.
    requests = _reconstruct_pending(root, output_dir)
    from openai import OpenAI
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    # Disable SDK-level retries so the append-only ledger contains the exact
    # number of provider attempts. All retry timing is controlled below.
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1", api_key=api_key, max_retries=0
    )
    codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
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
    queue = deque((row, 0.0) for row in pending)
    initial_completed = len(completed)
    run_started = time.monotonic()
    last_progress = run_started
    outcomes_since_progress = 0
    outcomes_since_adjustment = 0
    recent_outcomes: deque[tuple[bool, bool]] = deque(maxlen=100)
    active_concurrency = min(INITIAL_CONCURRENCY, workers)
    global_pause_until = 0.0
    progress_path = output_dir / "progress.json"

    def progress_snapshot(final: bool = False) -> dict:
        elapsed = max(time.monotonic() - run_started, 1e-9)
        session_completed = len(completed) - initial_completed
        rate = session_completed / elapsed
        remaining = EXPECTED_NEW_N - len(completed)
        errors = sum(not success for success, _ in recent_outcomes)
        rate_limits = sum(is_429 for _, is_429 in recent_outcomes)
        return {
            "updated_at": _now(),
            "final": final,
            "n_expected": EXPECTED_NEW_N,
            "n_completed": len(completed),
            "n_remaining": remaining,
            "session_completed": session_completed,
            "session_elapsed_seconds": elapsed,
            "session_requests_per_second": rate,
            "projected_hours_remaining": remaining / rate / 3600 if rate else None,
            "provider_cost_usd": spent,
            "authorized_ceiling_usd": float(ceiling),
            "target_concurrency": workers,
            "active_concurrency": active_concurrency,
            "recent_window_n": len(recent_outcomes),
            "recent_error_rate": errors / len(recent_outcomes) if recent_outcomes else 0.0,
            "recent_429_rate": rate_limits / len(recent_outcomes) if recent_outcomes else 0.0,
            "global_backoff_seconds_remaining": max(
                0.0, global_pause_until - time.monotonic()
            ),
        }
    lock_path = output_dir / ".run.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with attempts_path.open("a", encoding="utf-8") as handle:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures: dict = {}
                reserved = 0.0
                while queue or futures:
                    now = time.monotonic()
                    while (
                        queue
                        and len(futures) < active_concurrency
                        and now >= global_pause_until
                    ):
                        request, ready_at = queue[0]
                        if ready_at > now:
                            break
                        queue.popleft()
                        request_id = request["provider_request_id"]
                        if attempts.get(request_id, 0) >= MAX_ATTEMPTS:
                            continue
                        hold = (
                            request["estimated_input_tokens"] * INPUT_PRICE
                            + request["max_output_tokens"] * OUTPUT_PRICE
                        ) / 1e6
                        if spent + reserved + hold > ceiling + 1e-9:
                            queue.appendleft((request, ready_at))
                            break
                        future = pool.submit(_call, client, request, codebook)
                        futures[future] = (request, hold)
                        reserved += hold
                    if not futures:
                        if queue:
                            next_ready = max(queue[0][1], global_pause_until)
                            time.sleep(min(5.0, max(0.05, next_ready - time.monotonic())))
                            continue
                        break
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        request, hold = futures.pop(future)
                        reserved -= hold
                        try:
                            record = future.result()
                        except Exception as exc:
                            policy = _retry_policy(
                                exc, attempts.get(request["provider_request_id"], 0) + 1
                            )
                            record = {
                                "provider_request_id": request["provider_request_id"],
                                "logical_request_id": request["logical_request_id"],
                                "audit_response_id": request["audit_response_id"],
                                "status": "error",
                                "error_type": type(exc).__name__,
                                "error": str(exc)[:1000],
                                "incremental_provider_cost": 0.0,
                                "created_at": _now(),
                                "raw_provider_content": None,
                                **policy,
                            }
                        handle.write(
                            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                        )
                        handle.flush()
                        os.fsync(handle.fileno())
                        request_id = request["provider_request_id"]
                        attempts[request_id] = attempts.get(request_id, 0) + 1
                        spent += float(record.get("incremental_provider_cost", 0))
                        if spent > ceiling + 1e-9:
                            raise RuntimeError("hard provider-cost ceiling exceeded")
                        if record.get("status") == "complete":
                            completed[request_id] = record
                            recent_outcomes.append((True, False))
                        else:
                            is_429 = bool(record.get("is_rate_limit"))
                            recent_outcomes.append((False, is_429))
                            retryable = bool(record.get("transient", True))
                            if attempts[request_id] < MAX_ATTEMPTS and retryable:
                                delay = float(record.get("retry_delay_seconds") or 1.0)
                                queue.append((request, time.monotonic() + delay))
                            if is_429:
                                active_concurrency = max(
                                    MIN_CONCURRENCY, active_concurrency // 2
                                )
                                global_pause_until = max(
                                    global_pause_until,
                                    time.monotonic()
                                    + float(record.get("retry_delay_seconds") or 2.0),
                                )
                                outcomes_since_adjustment = 0
                        outcomes_since_progress += 1
                        outcomes_since_adjustment += 1

                    if outcomes_since_adjustment >= 50 and len(recent_outcomes) >= 50:
                        recent_error_rate = sum(
                            not success for success, _ in recent_outcomes
                        ) / len(recent_outcomes)
                        if recent_error_rate >= 0.10:
                            active_concurrency = max(
                                MIN_CONCURRENCY, active_concurrency - 2
                            )
                        elif recent_error_rate == 0 and active_concurrency < workers:
                            active_concurrency = min(workers, active_concurrency + 2)
                        outcomes_since_adjustment = 0

                    if (
                        outcomes_since_progress >= PROGRESS_EVERY_COMPLETIONS
                        or time.monotonic() - last_progress >= PROGRESS_EVERY_SECONDS
                    ):
                        _write_progress(progress_path, progress_snapshot())
                        outcomes_since_progress = 0
                        last_progress = time.monotonic()
    ordered = [
        completed[row["provider_request_id"]] for row in requests
        if row["provider_request_id"] in completed
    ]
    _write_jsonl(results_path, ordered)
    _write_progress(progress_path, progress_snapshot(final=True))
    summary = {
        "completed_at": _now(),
        "n_expected": EXPECTED_NEW_N,
        "n_completed": len(ordered),
        "n_incomplete": EXPECTED_NEW_N - len(ordered),
        "schema_success": len(ordered) / EXPECTED_NEW_N,
        "schema_success_gate": 0.995,
        "schema_gate_pass": len(ordered) / EXPECTED_NEW_N >= 0.995,
        "provider_cost_usd": spent,
        "authorized_ceiling_usd": float(ceiling),
        "logical_provider_payload_sha256": manifest[
            "logical_provider_payload_sha256"
        ],
        "attempts_sha256": sha_file(attempts_path),
        "results_sha256": sha_file(results_path),
        "network_call_made": True,
        "raw_provider_content_preserved_before_validation": True,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest["status"] = "completed" if len(ordered) == EXPECTED_NEW_N else "incomplete"
    manifest["network_call_made"] = True
    manifest["run_summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary
