#!/usr/bin/env python3
"""Recover preserved T-pro HTTP-200 bodies and freeze the residual retry set.

This stage is offline. It never edits the original request, attempt, result, or
manifest files and cannot make a provider call. Valid leading JSON objects are
decoded normally. A narrowly defined malformed-wrapper case is recovered only
when the response contains the expected content prefix and provider-metadata
suffix and the intervening JSON string can be decoded without alteration.

Technical record: docs/JURISDICTION_MODEL_EXPANSION_V1.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "annotations/model_expansion_v4/full_generation_v1/t-pro-it-2.0"
OUTPUT = SOURCE / "recovery_v1"
EXPECTED_REQUESTS = 12_480
INPUT_PRICE = 0.408
OUTPUT_PRICE = 1.972
MAX_OUTPUT_TOKENS = 5_000
PROBE_PER_LANGUAGE = 40
PROBE_SEED = "t-pro-residual-retry-probe-v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def recover_body(record: dict) -> tuple[dict | None, str | None]:
    if record.get("error_type") != "JSONDecodeError":
        return None, None
    body = record.get("provider_error_body") or ""
    if not body:
        return None, None

    try:
        payload, end = json.JSONDecoder().raw_decode(body)
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            return None, None
        usage = payload.get("usage") or {}
        method = "leading_valid_json_before_appended_provider_error"
        trailer = body[end:]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        prefix = '\"content\":\"'
        suffix = '],\"system_fingerprint\"'
        if body.count(prefix) != 1 or body.count(suffix) != 1:
            return None, None
        encoded = body.split(prefix, 1)[1].rsplit(suffix, 1)[0]
        try:
            content = json.loads('\"' + encoded + '\"')
        except json.JSONDecodeError:
            return None, None
        if not isinstance(content, str) or not content.strip():
            return None, None
        usage = {}
        method = "lossless_content_string_before_truncated_wrapper"
        trailer = body[body.rfind(suffix):]

    recovered = {
        "attempt": record["attempt"],
        "http_status": 200,
        "latency_seconds": record.get("latency_seconds"),
        "model": record["model"],
        "prompt_id": record["prompt_id"],
        "prompt_language": record["prompt_language"],
        "provider_request_id": record["provider_request_id"],
        "requested_at": record["requested_at"],
        "response_text": content,
        "status": "success",
        "usage": usage,
        "recovery_method": method,
        "recovered_from_attempt_error": record.get("error"),
        "source_body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "provider_trailer_sha256": hashlib.sha256(trailer.encode("utf-8")).hexdigest(),
    }
    return recovered, method


def recover() -> dict:
    requests = read_jsonl(SOURCE / "provider_requests.jsonl")
    attempts = read_jsonl(SOURCE / "attempts.jsonl")
    original_results = read_jsonl(SOURCE / "results.jsonl")
    if len(requests) != EXPECTED_REQUESTS:
        raise ValueError("T-pro request frame is not 12,480 records")
    latest = {row["provider_request_id"]: row for row in attempts}
    if len(latest) != EXPECTED_REQUESTS:
        raise ValueError("T-pro terminal attempt frame is incomplete")
    original = {row["provider_request_id"]: row for row in original_results}

    recovered: dict[str, dict] = {}
    methods: Counter[str] = Counter()
    for request_id, record in latest.items():
        if request_id in original:
            continue
        row, method = recover_body(record)
        if row is not None and method is not None:
            recovered[request_id] = row
            methods[method] += 1

    assembled = {**original, **recovered}
    ordered_results = sorted(
        assembled.values(), key=lambda row: (row["prompt_id"], row["prompt_language"])
    )
    retry_requests = [
        row for row in requests if row["provider_request_id"] not in assembled
    ]
    if len(assembled) + len(retry_requests) != EXPECTED_REQUESTS:
        raise ValueError("recovery does not partition the frozen request frame")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUTPUT / "recovered_responses.jsonl", list(recovered.values()))
    write_jsonl(OUTPUT / "assembled_responses.jsonl", ordered_results)
    write_jsonl(OUTPUT / "retry_provider_requests.jsonl", retry_requests)
    probe_requests = []
    for language in ("en", "zh", "ar", "ru", "hi"):
        cell = [row for row in retry_requests if row["prompt_language"] == language]
        cell.sort(key=lambda row: hashlib.sha256(
            f"{PROBE_SEED}:{row['provider_request_id']}".encode("utf-8")
        ).hexdigest())
        if len(cell) < PROBE_PER_LANGUAGE:
            raise ValueError(f"too few unresolved {language} cases for retry probe")
        probe_requests.extend(cell[:PROBE_PER_LANGUAGE])
    probe_requests.sort(key=lambda row: (row["prompt_id"], row["prompt_language"]))
    write_jsonl(OUTPUT / "retry_probe_provider_requests.jsonl", probe_requests)

    success_output_tokens = [
        int((row.get("usage") or {}).get("completion_tokens") or 0)
        for row in original_results
    ]
    mean_output_tokens = sum(success_output_tokens) / len(success_output_tokens)
    retry_input_tokens = sum(int(row["estimated_input_tokens"]) for row in retry_requests)
    planning_cost = (
        retry_input_tokens * INPUT_PRICE
        + len(retry_requests) * mean_output_tokens * OUTPUT_PRICE
    ) / 1_000_000
    maximum_cost = (
        retry_input_tokens * INPUT_PRICE
        + len(retry_requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    suggested_ceiling = 40.0
    if suggested_ceiling < planning_cost * 1.5 or suggested_ceiling > maximum_cost:
        raise ValueError("predeclared retry ceiling no longer brackets the cost design")
    probe_input_tokens = sum(int(row["estimated_input_tokens"]) for row in probe_requests)
    probe_planning_cost = (
        probe_input_tokens * INPUT_PRICE
        + len(probe_requests) * mean_output_tokens * OUTPUT_PRICE
    ) / 1_000_000
    probe_maximum_cost = (
        probe_input_tokens * INPUT_PRICE
        + len(probe_requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000

    terminal_errors = Counter(
        (latest[row["provider_request_id"]].get("error_type") or "unknown")
        for row in retry_requests
    )
    manifest = {
        "version": "t-pro-full-response-recovery-v1",
        "created_at": now(),
        "status": "recovered_and_retry_frozen_not_authorized",
        "scientific_role": "lossless recovery of preserved HTTP-200 model text and residual transport retry freeze",
        "source_counts": {
            "requests": len(requests),
            "original_successes": len(original),
            "original_terminal_failures": EXPECTED_REQUESTS - len(original),
        },
        "recovery_counts": {
            "recovered_responses": len(recovered),
            "assembled_responses": len(assembled),
            "residual_retry_requests": len(retry_requests),
            "methods": dict(sorted(methods.items())),
            "residual_error_types": dict(sorted(terminal_errors.items())),
        },
        "recovery_policy": {
            "source_ledgers_edited": False,
            "network_call_made": False,
            "leading_json_rule": "decode exactly one valid leading completion object and retain hashes of the appended provider trailer",
            "truncated_wrapper_rule": "decode only the exact JSON string bytes between the unique content prefix and provider-metadata suffix",
        },
        "retry_contract": {
            "requests": len(retry_requests),
            "attempts_per_request": 1,
            "model_id": "t-tech/T-pro-it-2.0:featherless-ai",
            "provider": "huggingface",
            "provider_tag": "featherless-ai",
            "generation_settings_unchanged": True,
            "provider_fallbacks_disabled": True,
            "estimated_input_tokens": retry_input_tokens,
            "planning_output_tokens_per_request": mean_output_tokens,
            "planning_cost_usd": planning_cost,
            "maximum_token_cost_usd": maximum_cost,
            "suggested_hard_ceiling_usd": suggested_ceiling,
            "paid_run_authorized": False,
            "network_call_made": False,
        },
        "retry_probe_contract": {
            "version": "t-pro-residual-retry-probe-v1",
            "selection": "deterministic simple random sample of 40 unresolved keys within each prompt language",
            "selection_seed": PROBE_SEED,
            "requests": len(probe_requests),
            "requests_per_language": PROBE_PER_LANGUAGE,
            "attempts_per_request": 1,
            "generation_settings_unchanged": True,
            "provider_fallbacks_disabled": True,
            "planning_cost_usd": probe_planning_cost,
            "maximum_token_cost_usd": probe_maximum_cost,
            "suggested_hard_ceiling_usd": 2.0,
            "paid_run_authorized": False,
            "network_call_made": False,
        },
        "input_sha256": {
            "provider_requests.jsonl": sha256(SOURCE / "provider_requests.jsonl"),
            "attempts.jsonl": sha256(SOURCE / "attempts.jsonl"),
            "results.jsonl": sha256(SOURCE / "results.jsonl"),
        },
        "artifact_sha256": {
            "recovered_responses.jsonl": sha256(OUTPUT / "recovered_responses.jsonl"),
            "assembled_responses.jsonl": sha256(OUTPUT / "assembled_responses.jsonl"),
            "retry_provider_requests.jsonl": sha256(OUTPUT / "retry_provider_requests.jsonl"),
            "retry_probe_provider_requests.jsonl": sha256(OUTPUT / "retry_probe_provider_requests.jsonl"),
        },
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("recover",))
    args = parser.parse_args()
    if args.command == "recover":
        print(json.dumps(recover(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
