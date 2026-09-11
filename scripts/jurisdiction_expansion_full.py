#!/usr/bin/env python3
"""Freeze, cost and guard full-corpus generation for three new models.

Each model has an independent payload, currency, authorization and ledger.
All 2,496 prompt meanings are crossed with the five canonical languages.
Provider/transport failures remain separate from response behavior.

Technical record: docs/JURISDICTION_MODEL_EXPANSION_V1.md
"""

from __future__ import annotations

import argparse
from collections import deque
import json
import math
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from env_utils import load_env_from_file
from jurisdiction_expansion_pilot import load_all_prompts, now
from jurisdiction_expansion_smoke import (
    HF_BASE_URL, LANGUAGES, ROSTER_PATH, atomic_json, load_roster,
    parse_response, read_jsonl, sha_file, sha_object, token_count, write_jsonl,
)

BASE_DIR = ROOT / "annotations/model_expansion_v4/full_generation_v1"
EXPECTED_PROMPTS = 2496
EXPECTED_REQUESTS = EXPECTED_PROMPTS * len(LANGUAGES)
MAX_ATTEMPTS = 2
USER_AGENT = "huggingface_hub/0.34.0 refusal-audit/1.0"
_LOCK = threading.Lock()

MODELS = {
    "t-pro-it-2.0": {
        "model_id": "t-tech/T-pro-it-2.0:featherless-ai", "provider": "huggingface",
        "provider_tag": "featherless-ai", "developer": "T-Bank AI Research",
        "jurisdiction": "Russia", "temperature": 1.0, "max_tokens": 5000,
        "workers": 4, "currency": "USD", "input_price": 0.408,
        "output_price": 1.972, "hard_ceiling": 65.0,
        "pilot_dir": ROOT / "annotations/model_expansion_v4/jurisdiction_pilot_v1",
    },
    "bielik-11b-v3.0": {
        "model_id": "speakleash/Bielik-11B-v3.0-Instruct:publicai", "provider": "huggingface",
        "provider_tag": "publicai", "developer": "SpeakLeash",
        "jurisdiction": "Europe", "temperature": 1.0, "max_tokens": 5000,
        "workers": 8, "currency": "USD", "input_price": 0.4,
        "output_price": 0.4, "hard_ceiling": 8.0,
        "pilot_dir": ROOT / "annotations/model_expansion_v4/jurisdiction_pilot_v1",
    },
    "sarvam-105b": {
        "model_id": "sarvam-105b", "provider": "sarvam-native",
        "provider_tag": "sarvam-native", "developer": "Sarvam AI",
        "jurisdiction": "India", "temperature": 1.0, "max_tokens": 4096,
        "workers": 5, "currency": "INR", "input_price": 29.28,
        "output_price": 73.2, "hard_ceiling": 1250.0,
        "pilot_dir": ROOT / "annotations/model_expansion_v4/sarvam_105b_pilot_v1",
    },
}


def model_dir(model: str) -> Path:
    return BASE_DIR / model


def pilot_rows(model: str) -> list[dict]:
    config = MODELS[model]
    path = config["pilot_dir"] / "provider_responses.jsonl"
    rows = read_jsonl(path)
    latest = {r["provider_request_id"]: r for r in rows}
    return [r for r in latest.values() if r.get("model") == model and r.get("status") == "success"]


def empirical(model: str) -> dict[str, Any]:
    config = MODELS[model]; rows = pilot_rows(model)
    expected = 200 if model != "t-pro-it-2.0" else 191
    if len(rows) != expected:
        raise ValueError(f"{model} successful pilot count changed")
    inputs = [int((r.get("usage") or {}).get("prompt_tokens") or 0) for r in rows]
    outputs = [int((r.get("usage") or {}).get("completion_tokens") or 0) for r in rows]
    latencies = [float(r.get("latency_seconds") or 0) for r in rows]
    quantile = lambda values, p: sorted(values)[min(len(values) - 1, math.ceil(p * len(values)) - 1)]
    projected = EXPECTED_REQUESTS * (
        statistics.mean(inputs) * config["input_price"]
        + statistics.mean(outputs) * config["output_price"]
    ) / 1_000_000
    p95_projected = EXPECTED_REQUESTS * (
        quantile(inputs, .95) * config["input_price"]
        + quantile(outputs, .95) * config["output_price"]
    ) / 1_000_000
    return {
        "pilot_success_n": len(rows), "pilot_response_ledger_sha256": sha_file(config["pilot_dir"] / "provider_responses.jsonl"),
        "mean_input_tokens": statistics.mean(inputs), "mean_output_tokens": statistics.mean(outputs),
        "p95_input_tokens": quantile(inputs, .95), "p95_output_tokens": quantile(outputs, .95),
        "mean_latency_seconds": statistics.mean(latencies),
        "empirical_projected_cost": projected, "p95_per_response_projected_cost": p95_projected,
        "estimated_runtime_hours": EXPECTED_REQUESTS * statistics.mean(latencies) / config["workers"] / 3600,
    }


def prepare(model: str) -> dict:
    config = MODELS[model]; output_dir = model_dir(model)
    roster = load_roster(); prompts = load_all_prompts(roster)
    prompt_ids = sorted(prompts["en"])
    if len(prompt_ids) != EXPECTED_PROMPTS:
        raise ValueError("canonical prompt frame is not 2,496 meanings")
    input_hashes = {
        "prompt_roster": sha_file(ROSTER_PATH),
        **{f"prompt_{lang}": roster["design"]["prompt_files"][lang]["sha256"] for lang in LANGUAGES},
        "pilot_response_ledger": empirical(model)["pilot_response_ledger_sha256"],
    }
    request_path = output_dir / "provider_requests.jsonl"; manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["input_sha256"] != input_hashes: raise ValueError("frozen full-run inputs changed")
        if sha_file(request_path) != manifest["provider_payload_sha256"]: raise ValueError("frozen full-run payload changed")
        return manifest
    rows = []
    for prompt_id in prompt_ids:
        for language in LANGUAGES:
            prompt = prompts[language][prompt_id]
            logical = {"version": "jurisdiction-expansion-full-v1", "model": model,
                       "prompt_id": prompt_id, "prompt_language": language}
            rows.append({
                **logical, "provider_request_id": sha_object(logical)[:24],
                "model_id": config["model_id"], "provider": config["provider"],
                "provider_tag": config["provider_tag"], "provider_fallbacks_disabled": True,
                "messages": [{"role": "user", "content": prompt["text"]}],
                "temperature": config["temperature"], "max_tokens": config["max_tokens"],
                "reasoning_disabled": True, "estimated_input_tokens": token_count(prompt["text"]),
                "input_price_per_million": config["input_price"],
                "output_price_per_million": config["output_price"], "currency": config["currency"],
                "prompt_metadata": {k: prompt.get(k) for k in (
                    "issue_id", "qid", "topic_domain", "controversy_tier", "region_focus",
                    "position_side", "route", "battery", "prompt_origin_language", "prompt_origin_form")},
            })
    if len(rows) != EXPECTED_REQUESTS or len({r["provider_request_id"] for r in rows}) != EXPECTED_REQUESTS:
        raise ValueError("full-run request count or uniqueness failure")
    output_dir.mkdir(parents=True, exist_ok=False); write_jsonl(request_path, rows)
    manifest = {
        "version": "jurisdiction-expansion-full-v1", "created_at": now(), "status": "frozen_unpaid",
        "scientific_role": "full canonical subject-model response generation",
        "model": model, "model_id": config["model_id"], "developer": config["developer"],
        "developer_jurisdiction": config["jurisdiction"], "provider": config["provider"],
        "provider_tag": config["provider_tag"], "languages": list(LANGUAGES),
        "n_prompt_meanings": EXPECTED_PROMPTS, "n_requests": EXPECTED_REQUESTS,
        "temperature": config["temperature"], "max_tokens": config["max_tokens"],
        "max_attempts_per_request": MAX_ATTEMPTS, "maximum_workers": config["workers"],
        "reasoning_disabled": True, "provider_fallbacks_disabled": True,
        "currency": config["currency"], "input_sha256": input_hashes,
        "provider_payload_sha256": sha_file(request_path),
        "paid_run_authorized": False, "network_inference_call_made": False,
    }
    atomic_json(manifest_path, manifest); return manifest


def cost(model: str) -> dict:
    manifest = prepare(model); config = MODELS[model]; rows = read_jsonl(model_dir(model) / "provider_requests.jsonl")
    stats = empirical(model)
    theoretical = sum((r["estimated_input_tokens"] * config["input_price"]
                       + r["max_tokens"] * config["output_price"]) / 1e6 for r in rows)
    result = {
        "version": "jurisdiction-expansion-full-cost-v1", "created_at": now(), "model": model,
        "currency": config["currency"], "requests": len(rows), "pilot_empirical": stats,
        "empirical_projected_cost": round(stats["empirical_projected_cost"], 6),
        "p95_per_response_projected_cost": round(stats["p95_per_response_projected_cost"], 6),
        "all_requests_max_token_cost": round(theoretical, 6),
        "hard_ceiling": config["hard_ceiling"],
        "ceiling_rule": "conservative margin over pilot mean; executor stops before ceiling",
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False, "network_inference_call_made": False,
    }
    atomic_json(model_dir(model) / "cost_estimate.json", result); return result


def authorize(model: str, payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed: raise RuntimeError("explicit user authorization is required")
    manifest = prepare(model); estimate = cost(model); output_dir = model_dir(model)
    if payload_sha != manifest["provider_payload_sha256"]: raise ValueError("payload hash mismatch")
    if float(ceiling) != float(estimate["hard_ceiling"]): raise ValueError("ceiling mismatch")
    record = {"recorded_at": now(), "user_authorized": True, "model": model,
              "provider_payload_sha256": payload_sha, "hard_ceiling": ceiling,
              "currency": MODELS[model]["currency"], "n_requests": EXPECTED_REQUESTS}
    manifest.update({"authorization": record, "paid_run_authorized": True, "status": "authorized_not_started"})
    atomic_json(output_dir / "manifest.json", manifest); return record


def append(path: Path, record: dict) -> None:
    with _LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"); handle.flush(); os.fsync(handle.fileno())


def send(row: dict, secret: str, attempt: int) -> dict:
    config = MODELS[row["model"]]
    body = {"model": row["model_id"], "messages": row["messages"],
            "temperature": row["temperature"], "max_tokens": row["max_tokens"]}
    if row["model"] == "t-pro-it-2.0": body["chat_template_kwargs"] = {"enable_thinking": False}
    if config["provider"] == "sarvam-native": body["reasoning_effort"] = None
    url = "https://api.sarvam.ai/v1/chat/completions" if config["provider"] == "sarvam-native" else f"{HF_BASE_URL}/chat/completions"
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if config["provider"] == "sarvam-native": headers["api-subscription-key"] = secret
    else: headers["Authorization"] = f"Bearer {secret}"
    record = {"provider_request_id": row["provider_request_id"], "model": row["model"],
              "prompt_id": row["prompt_id"], "prompt_language": row["prompt_language"],
              "attempt": attempt, "requested_at": now()}; started = time.monotonic()
    raw_payload_text = ""
    try:
        request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=300) as response:
            record["http_status"] = response.status
            raw_payload_text = response.read().decode()
            payload = json.loads(raw_payload_text)
        content, usage = parse_response(payload)
        if not content.strip(): raise ValueError("provider response has empty message content")
        record.update({"status": "success", "response_text": content, "usage": usage})
    except urllib.error.HTTPError as exc:
        record.update({"status": "error", "http_status": exc.code, "error_type": type(exc).__name__,
                       "error": str(exc)[:1000], "provider_error_body": exc.read().decode(errors="replace")[:2000]})
    except json.JSONDecodeError as exc:
        # Preserve malformed HTTP-200 envelopes for deterministic diagnosis and
        # possible lossless recovery; these can contain valid model text even
        # though the provider transport wrapper is not valid JSON.
        record.update({"status": "error", "error_type": type(exc).__name__,
                       "error": str(exc)[:1000], "provider_error_body": raw_payload_text[:100000]})
    except Exception as exc:
        record.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc)[:1000]})
    record["latency_seconds"] = round(time.monotonic() - started, 3); return record


def actual_cost(rows: list[dict], config: dict) -> float:
    total = 0.0
    for r in rows:
        if r.get("status") != "success": continue
        usage = r.get("usage") or {}
        total += ((usage.get("prompt_tokens") or 0) * config["input_price"]
                  + (usage.get("completion_tokens") or 0) * config["output_price"]) / 1e6
    return total


def drain_continuous_queue(
    queue: deque,
    workers: int,
    can_submit,
    submit_attempt,
    finish_attempt,
) -> None:
    """Keep worker slots occupied without ever exceeding ``workers``.

    ``finish_attempt`` may return a retry item, which is appended to the same
    queue. Keeping this primitive separate makes the concurrency limit testable
    without making provider calls.
    """
    inflight = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        while queue or inflight:
            while queue and len(inflight) < workers and can_submit(len(inflight)):
                item = queue.popleft()
                future = executor.submit(submit_attempt, item)
                inflight[future] = item
            if not inflight:
                break
            done, _ = wait(inflight, return_when=FIRST_COMPLETED)
            for future in done:
                item = inflight.pop(future)
                retry = finish_attempt(item, future.result())
                if retry is not None:
                    queue.append(retry)


def authorized_worker_cap(manifest: dict) -> int:
    amendment = manifest.get("concurrency_amendment") or {}
    if amendment.get("trial_outcome", "").startswith("failed_"):
        return int(amendment.get("effective_maximum_workers", manifest["maximum_workers"]))
    if amendment.get("user_authorized"):
        return int(amendment["maximum_workers"])
    return int(manifest["maximum_workers"])


def authorize_concurrency_amendment(
    model: str, amendment_sha: str, confirmed: bool
) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization required")
    if model != "t-pro-it-2.0":
        raise ValueError("the current amendment applies only to T-pro")
    output_dir = model_dir(model)
    candidates = sorted(output_dir.glob("concurrency_amendment_v*.json"))
    matches = [path for path in candidates if sha_file(path) == amendment_sha]
    if len(matches) != 1:
        raise ValueError("concurrency amendment hash mismatch")
    amendment_path = matches[0]
    protocol = json.loads(amendment_path.read_text())
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if protocol["provider_payload_sha256"] != manifest["provider_payload_sha256"]:
        raise ValueError("amendment is bound to a different payload")
    record = {
        "recorded_at": now(),
        "user_authorized": True,
        "protocol_sha256": amendment_sha,
        "maximum_workers": int(protocol["trial_maximum_workers"]),
        "trial_minutes": int(protocol["trial_minutes"]),
        "hard_ceiling": manifest["authorization"]["hard_ceiling"],
    }
    prior = manifest.get("concurrency_amendment")
    if prior:
        history = manifest.setdefault("concurrency_amendment_history", [])
        if prior not in history:
            history.append(prior)
    manifest["concurrency_amendment"] = record
    atomic_json(manifest_path, manifest)
    return record


def run(
    model: str,
    ceiling: float,
    authorized: bool,
    workers: int | None = None,
    trial_minutes: float | None = None,
    halt_on_429: bool = False,
) -> dict:
    if not authorized: raise RuntimeError("--authorize-paid-run is required")
    load_env_from_file(); config = MODELS[model]; output_dir = model_dir(model)
    secret = os.environ.get("SARVAM_API_KEY" if config["provider"] == "sarvam-native" else "HF_TOKEN")
    if not secret: raise RuntimeError("required provider credential is not set")
    manifest_path = output_dir / "manifest.json"; manifest = json.loads(manifest_path.read_text())
    if not manifest.get("paid_run_authorized"): raise RuntimeError("full run is not authorized")
    if float(ceiling) != float(manifest["authorization"]["hard_ceiling"]): raise ValueError("runtime ceiling mismatch")
    requested_workers = int(workers or config["workers"])
    if requested_workers < 1 or requested_workers > authorized_worker_cap(manifest):
        raise ValueError("requested workers exceed the authorized concurrency cap")
    if trial_minutes is not None and trial_minutes <= 0:
        raise ValueError("trial minutes must be positive")
    if sha_file(output_dir / "provider_requests.jsonl") != manifest["provider_payload_sha256"]: raise ValueError("payload changed")
    requests = read_jsonl(output_dir / "provider_requests.jsonl"); attempt_path = output_dir / "attempts.jsonl"
    attempts = read_jsonl(attempt_path); by_id: dict[str, list[dict]] = {}
    for record in attempts: by_id.setdefault(record["provider_request_id"], []).append(record)
    transient = lambda r: r.get("http_status") in {429, 500, 502, 503, 504} or r.get("error_type") in {"URLError", "TimeoutError"}
    queue = deque()
    for row in requests:
        history = by_id.get(row["provider_request_id"], [])
        if any(r.get("status") == "success" for r in history): continue
        if not history: queue.append((row, 1))
        elif len(history) < MAX_ATTEMPTS and transient(history[-1]): queue.append((row, len(history) + 1))
    stopped_for_ceiling = False
    stopped_for_trial = False
    stopped_for_rate_limit = False
    trial_deadline = time.monotonic() + trial_minutes * 60 if trial_minutes else None
    spent = actual_cost(attempts, config)
    max_one = max(
        (row["estimated_input_tokens"] * config["input_price"]
         + row["max_tokens"] * config["output_price"]) / 1e6
        for row, _ in queue
    ) if queue else 0.0

    def can_submit(inflight_count: int) -> bool:
        nonlocal stopped_for_ceiling, stopped_for_trial
        if stopped_for_rate_limit:
            return False
        if trial_deadline is not None and time.monotonic() >= trial_deadline:
            stopped_for_trial = True
            return False
        # Reserve the maximum possible charge for every call already in flight
        # and for the call about to start. This retains the original hard gate.
        allowed = spent + (inflight_count + 1) * max_one <= ceiling
        if not allowed and inflight_count == 0:
            stopped_for_ceiling = True
        return allowed

    def submit_attempt(item: tuple[dict, int]) -> dict:
        row, attempt = item
        return send(row, secret, attempt)

    def finish_attempt(item: tuple[dict, int], result: dict):
        nonlocal spent, stopped_for_rate_limit
        row, attempt = item
        append(attempt_path, result)
        attempts.append(result)
        spent = actual_cost(attempts, config)
        if halt_on_429 and result.get("http_status") == 429:
            stopped_for_rate_limit = True
        if result.get("status") != "success" and attempt < MAX_ATTEMPTS and transient(result):
            return row, attempt + 1
        return None

    drain_continuous_queue(
        queue,
        requested_workers,
        can_submit,
        submit_attempt,
        finish_attempt,
    )
    attempts = read_jsonl(attempt_path); latest = {r["provider_request_id"]: r for r in attempts}
    results = [r for r in latest.values() if r.get("status") == "success"]
    write_jsonl(output_dir / "results.jsonl", sorted(results, key=lambda r: (r["prompt_id"], r["prompt_language"])))
    manifest["network_inference_call_made"] = True; manifest["updated_at"] = now()
    manifest["status"] = ("rate_limit_trial_stopped" if stopped_for_rate_limit else
                          "cost_ceiling_reached" if stopped_for_ceiling else
                          "concurrency_trial_complete" if stopped_for_trial else
                          ("completed" if len(latest) == EXPECTED_REQUESTS else "incomplete"))
    manifest["result"] = {"terminal_records": len(latest), "successful_responses": len(results),
                          "errors": sum(r.get("status") == "error" for r in latest.values()),
                          "actual_cost": actual_cost(attempts, config), "currency": config["currency"],
                          "workers": requested_workers, "trial_minutes": trial_minutes,
                          "halt_on_429": halt_on_429,
                          "attempts_sha256": sha_file(attempt_path), "results_sha256": sha_file(output_dir / "results.jsonl")}
    atomic_json(manifest_path, manifest); return manifest["result"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "authorize-concurrency", "run")); parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--payload-sha"); parser.add_argument("--amendment-sha"); parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--workers", type=int); parser.add_argument("--trial-minutes", type=float)
    parser.add_argument("--halt-on-429", action="store_true")
    parser.add_argument("--confirm-user-authorization", action="store_true"); parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare": result = prepare(args.model)
    elif args.command == "cost": result = cost(args.model)
    elif args.command == "authorize":
        if not args.payload_sha or args.cost_ceiling is None: parser.error("authorize requires hash and ceiling")
        result = authorize(args.model, args.payload_sha, args.cost_ceiling, args.confirm_user_authorization)
    elif args.command == "authorize-concurrency":
        if not args.amendment_sha: parser.error("authorize-concurrency requires --amendment-sha")
        result = authorize_concurrency_amendment(args.model, args.amendment_sha, args.confirm_user_authorization)
    else:
        if args.cost_ceiling is None: parser.error("run requires --cost-ceiling")
        result = run(args.model, args.cost_ceiling, args.authorize_paid_run, args.workers, args.trial_minutes, args.halt_on_429)
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
