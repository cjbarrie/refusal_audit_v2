#!/usr/bin/env python3
"""Freeze the 200-response Fanar-C-2-27B expansion pilot.

This reuses the exact 40 prompt meanings from the completed expansion pilot and
crosses them with the five canonical languages. It follows the successful
20-request Fanar diagnostic but remains a diagnostic/enriched sample, not a
probability sample for estimating population refusal prevalence.

The script prepares immutable inputs, records an exact authorization, runs a
guarded and resumable native-Fanar request loop, and audits returned records.
Provider execution remains impossible unless the authorization matches the
frozen payload SHA-256 and exact provider-request ceiling.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import sys
import threading
import time
import unicodedata
from collections import Counter, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

from fanar_diagnostic import (
    API_URL,
    LANGUAGES,
    MODEL_ID,
    ROOT,
    ROSTER_PATH,
    SOURCE_DIR,
    _call_fanar,
    _response_text,
    append_jsonl,
    read_jsonl,
    read_prompts,
    sha_file,
    sha_object,
    write_jsonl,
)


OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/fanar_c2_27b_pilot_v1"
DIAGNOSTIC_DIR = ROOT / "annotations/model_expansion_v4/fanar_c2_27b_diagnostic_v1"
EXPECTED_PROMPT_MEANINGS = 40
EXPECTED_REQUESTS = 200
MAX_ATTEMPTS_PER_LOGICAL_REQUEST = 2
ABSOLUTE_PROVIDER_REQUEST_CEILING = 240
RETRYABLE_HTTP_STATUS = {429, 500, 503, 504}
NONRETRYABLE_HTTP_STATUS = {400, 401, 403, 404, 409, 410, 413, 422}
MINIMUM_SECONDS_BETWEEN_REQUEST_STARTS = 1.3  # below the documented 50/minute
DEFAULT_WORKERS = 6


def _load_source_selection() -> list[dict[str, str]]:
    path = SOURCE_DIR / "pilot_prompt_index.csv"
    source_manifest = json.loads((SOURCE_DIR / "manifest.json").read_text())
    expected = source_manifest["artifact_sha256"]["pilot_prompt_index.csv"]
    if sha_file(path) != expected:
        raise ValueError("source expansion-pilot selection hash mismatch")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if (
        len(rows) != EXPECTED_PROMPT_MEANINGS
        or len({row["prompt_id"] for row in rows}) != EXPECTED_PROMPT_MEANINGS
        or len({row["issue_id"] for row in rows}) != EXPECTED_PROMPT_MEANINGS
    ):
        raise ValueError("source pilot is not the frozen 40-meaning selection")
    return rows


def _verify_completed_diagnostic() -> dict[str, str]:
    required = ("manifest.json", "run_summary.json", "attempts.jsonl", "results.jsonl")
    for name in required:
        if not (DIAGNOSTIC_DIR / name).exists():
            raise ValueError(f"completed Fanar diagnostic artifact missing: {name}")
    diagnostic_manifest = json.loads((DIAGNOSTIC_DIR / "manifest.json").read_text())
    summary = json.loads((DIAGNOSTIC_DIR / "run_summary.json").read_text())
    if (
        diagnostic_manifest["payload_sha256"]
        != "e21659539313b1a141ea62885a794116e4d87d86c199809cd75678fcd782628a"
        or summary["provider_requests_attempted"] != 20
        or summary["successful_responses"] != 17
        or summary["failed_requests"] != 3
        or summary["status"] != "complete"
    ):
        raise ValueError("Fanar diagnostic does not match the completed decision gate")
    return {
        f"diagnostic_{name}": sha_file(DIAGNOSTIC_DIR / name) for name in required
    }


def prepare() -> dict:
    manifest_path = OUTPUT_DIR / "manifest.json"
    request_path = OUTPUT_DIR / "provider_requests.jsonl"
    selection_path = OUTPUT_DIR / "pilot_prompt_index.csv"
    prompts, prompt_hashes = read_prompts()
    selection = _load_source_selection()
    diagnostic_hashes = _verify_completed_diagnostic()
    input_hashes = {
        "roster": sha_file(ROSTER_PATH),
        "source_pilot_prompt_index": sha_file(SOURCE_DIR / "pilot_prompt_index.csv"),
        **prompt_hashes,
        **diagnostic_hashes,
    }

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("existing frozen Fanar pilot no longer matches inputs")
        if sha_file(request_path) != manifest["payload_sha256"]:
            raise ValueError("existing frozen Fanar pilot payload was modified")
        if sha_file(selection_path) != manifest["artifact_sha256"]["pilot_prompt_index.csv"]:
            raise ValueError("existing frozen Fanar pilot selection was modified")
        return manifest

    requests: list[dict] = []
    for selected in sorted(selection, key=lambda row: row["prompt_id"]):
        prompt_id = selected["prompt_id"]
        for language in LANGUAGES:
            prompt = prompts[language][prompt_id]
            logical_key = {
                "pilot_version": "fanar-c2-27b-pilot-v1",
                "model": MODEL_ID,
                "prompt_id": prompt_id,
                "prompt_language": language,
            }
            requests.append({
                **logical_key,
                "provider_request_id": sha_object(logical_key)[:24],
                "messages": [{"role": "user", "content": prompt["text"]}],
                "temperature": 1.0,
                "max_tokens": 5000,
                "enable_thinking": False,
                "repetition_penalty": 1.0,
                "n": 1,
                "stream": False,
                "pilot_band": selected["pilot_band"],
                "prompt_metadata": {
                    key: prompt.get(key) for key in (
                        "issue_id", "qid", "topic_domain", "controversy_tier",
                        "region_focus", "position_side", "route", "battery",
                        "prompt_origin_language", "prompt_origin_form",
                    )
                },
            })

    if len(requests) != EXPECTED_REQUESTS:
        raise ValueError(f"expected {EXPECTED_REQUESTS} requests, got {len(requests)}")
    if len({row["provider_request_id"] for row in requests}) != EXPECTED_REQUESTS:
        raise ValueError("Fanar pilot request IDs are not unique")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(request_path, requests)
    with selection_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selection[0].keys()))
        writer.writeheader()
        writer.writerows(sorted(selection, key=lambda row: row["prompt_id"]))

    diagnostic_summary = json.loads((DIAGNOSTIC_DIR / "run_summary.json").read_text())
    returned = diagnostic_summary["successful_responses"]
    usage = diagnostic_summary["usage"]
    manifest = {
        "version": "fanar-c2-27b-pilot-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_not_authorized",
        "scientific_role": (
            "same enriched 40-meaning by five-language expansion pilot; "
            "operational and behavioral assessment, not prevalence estimation"
        ),
        "model": MODEL_ID,
        "developer": "Qatar Computing Research Institute (QCRI)",
        "developer_jurisdiction": "MENA",
        "provider": "Fanar native API",
        "endpoint": "https://api.fanar.qa/v1/chat/completions",
        "authentication_env": "FANAR_API_KEY",
        "n_prompt_meanings": EXPECTED_PROMPT_MEANINGS,
        "languages": list(LANGUAGES),
        "n_logical_requests": EXPECTED_REQUESTS,
        "rate_limit_documented_requests_per_minute": 50,
        "published_price_found": False,
        "generation_parameters": {
            "temperature": 1.0,
            "max_tokens": 5000,
            "enable_thinking": False,
            "repetition_penalty": 1.0,
            "n": 1,
            "stream": False,
        },
        "retry_policy_proposed": {
            "maximum_attempts_per_logical_request": 2,
            "retry_only": [429, 500, 503, 504, "transport_error"],
            "never_retry": [400, 401, 403, 404, 409, 410, 413, 422],
            # The logical maximum is 400 (two attempts for every row), but the
            # authorization proposal reserves retries for only 20% of rows.
            # This bounds an API with unpublished monetary pricing.
            "proposed_absolute_provider_request_ceiling": 240,
        },
        "diagnostic_basis": {
            "payload_sha256": "e21659539313b1a141ea62885a794116e4d87d86c199809cd75678fcd782628a",
            "attempted": 20,
            "returned": returned,
            "provider_filter_blocks": 3,
        },
        "empirical_token_projection_from_diagnostic": {
            "projected_prompt_tokens_for_200_calls": round(usage["prompt_tokens"] * 10),
            "projected_completion_tokens_at_observed_return_rate": round(
                usage["completion_tokens"] / returned * EXPECTED_REQUESTS * returned / 20
            ),
            "monetary_cost_not_estimable_without_provider_price": True,
        },
        "input_sha256": input_hashes,
        "payload_sha256": sha_file(request_path),
        "artifact_sha256": {
            "pilot_prompt_index.csv": sha_file(selection_path),
            "provider_requests.jsonl": sha_file(request_path),
        },
        "authorization": None,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def authorize(payload_sha256: str, max_requests: int, confirmed: bool) -> dict:
    """Persist the user's authorization without changing the frozen payload."""
    manifest = prepare()
    if not confirmed:
        raise ValueError("authorization requires --confirm-user-authorization")
    if payload_sha256 != manifest["payload_sha256"]:
        raise ValueError("authorized payload SHA-256 does not match frozen payload")
    if max_requests != ABSOLUTE_PROVIDER_REQUEST_CEILING:
        raise ValueError("authorization must use the frozen 240-request ceiling")
    record = {
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": payload_sha256,
        "model": MODEL_ID,
        "endpoint": API_URL,
        "n_logical_requests": EXPECTED_REQUESTS,
        "max_attempts_per_logical_request": MAX_ATTEMPTS_PER_LOGICAL_REQUEST,
        "max_provider_requests": max_requests,
        "retryable_http_status": sorted(RETRYABLE_HTTP_STATUS),
        "nonretryable_http_status": sorted(NONRETRYABLE_HTTP_STATUS),
        "retry_transport_errors_once": True,
        "monetary_price_published": False,
        "user_acknowledged_unpublished_pricing": True,
        "parameters": manifest["generation_parameters"],
    }
    path = OUTPUT_DIR / "authorization.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        old = {key: value for key, value in existing.items() if key != "authorized_at"}
        new = {key: value for key, value in record.items() if key != "authorized_at"}
        if old != new:
            raise ValueError("existing authorization differs from current authorization")
        return existing
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


class StartRateLimiter:
    """Serialize provider-call starts while allowing responses to overlap."""

    def __init__(self, minimum_interval: float) -> None:
        self.minimum_interval = minimum_interval
        self._lock = threading.Lock()
        self._last_start = 0.0

    def acquire(self) -> None:
        with self._lock:
            delay = self.minimum_interval - (time.monotonic() - self._last_start)
            if delay > 0:
                time.sleep(delay)
            self._last_start = time.monotonic()


def _execute_attempt(
    api_key: str, row: dict, attempt_number: int, limiter: StartRateLimiter
) -> tuple[dict, dict | None]:
    limiter.acquire()
    started = time.monotonic()
    attempt = {
        "provider_request_id": row["provider_request_id"],
        "prompt_id": row["prompt_id"],
        "prompt_language": row["prompt_language"],
        "attempted_at": datetime.now(timezone.utc).isoformat(),
        "attempt_number": attempt_number,
    }
    try:
        http_status, body, headers = _call_fanar(api_key, row)
        attempt.update({
            "http_status": http_status,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "rate_limit_headers": headers,
            "provider_response": body,
        })
        if http_status != 200:
            return attempt, None
        choices = body.get("choices") or []
        if not choices or not isinstance(choices[0].get("message"), dict):
            attempt["response_schema_error"] = "missing choices[0].message"
            return attempt, None
        choice = choices[0]
        message = choice["message"]
        result = {
            **{key: row[key] for key in (
                "provider_request_id", "prompt_id", "prompt_language", "model",
                "pilot_band", "prompt_metadata",
            )},
            "response_text": _response_text(message),
            "response_message": message,
            "finish_reason": choice.get("finish_reason"),
            "provider_response_id": body.get("id"),
            "provider_reported_model": body.get("model"),
            "usage": body.get("usage"),
            "created": body.get("created"),
            "successful_attempt_number": attempt_number,
        }
        return attempt, result
    except Exception as exc:
        attempt.update({
            "http_status": None,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "client_error_type": type(exc).__name__,
            "client_error": str(exc)[:2000],
        })
        return attempt, None


def _is_retryable(attempt: dict) -> bool:
    status = attempt.get("http_status")
    return status is None or status in RETRYABLE_HTTP_STATUS


def run(workers: int) -> dict:
    """Execute authorized rows resumably within all retry and request ceilings."""
    manifest = prepare()
    authorization_path = OUTPUT_DIR / "authorization.json"
    if not authorization_path.exists():
        raise ValueError("no recorded authorization for this Fanar pilot")
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    if (
        authorization["payload_sha256"] != manifest["payload_sha256"]
        or authorization["max_provider_requests"] != ABSOLUTE_PROVIDER_REQUEST_CEILING
    ):
        raise ValueError("authorization does not match the frozen Fanar pilot")
    if not 1 <= workers <= DEFAULT_WORKERS:
        raise ValueError(f"workers must be between 1 and {DEFAULT_WORKERS}")

    sys.path.insert(0, str(ROOT / "scripts"))
    from env_utils import load_env_from_file

    load_env_from_file(ROOT / ".env")
    api_key = os.environ.get("FANAR_API_KEY")
    if not api_key:
        raise ValueError("FANAR_API_KEY is missing")

    attempts_path = OUTPUT_DIR / "attempts.jsonl"
    results_path = OUTPUT_DIR / "results.jsonl"
    requests = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    requests_by_id = {row["provider_request_id"]: row for row in requests}
    if len(requests_by_id) != EXPECTED_REQUESTS:
        raise ValueError("frozen pilot does not contain 200 unique requests")

    lock_path = OUTPUT_DIR / ".run.lock"
    with lock_path.open("w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempts = read_jsonl(attempts_path)
        results = read_jsonl(results_path)
        if len(attempts) > ABSOLUTE_PROVIDER_REQUEST_CEILING:
            raise ValueError("provider request ceiling was already exceeded")
        result_ids = {row["provider_request_id"] for row in results}
        attempts_by_id: dict[str, list[dict]] = {}
        for attempt in attempts:
            attempts_by_id.setdefault(attempt["provider_request_id"], []).append(attempt)

        queue: deque[tuple[dict, int]] = deque()
        for row in requests:
            request_id = row["provider_request_id"]
            if request_id in result_ids:
                continue
            prior = attempts_by_id.get(request_id, [])
            if len(prior) >= MAX_ATTEMPTS_PER_LOGICAL_REQUEST:
                continue
            if prior and not _is_retryable(prior[-1]):
                continue
            queue.append((row, len(prior) + 1))

        limiter = StartRateLimiter(MINIMUM_SECONDS_BETWEEN_REQUEST_STARTS)
        inflight = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            while queue or inflight:
                while (
                    queue
                    and len(inflight) < workers
                    and len(attempts) + len(inflight) < ABSOLUTE_PROVIDER_REQUEST_CEILING
                ):
                    row, attempt_number = queue.popleft()
                    future = executor.submit(
                        _execute_attempt, api_key, row, attempt_number, limiter
                    )
                    inflight[future] = (row, attempt_number)
                if not inflight:
                    break
                done, _ = wait(inflight, return_when=FIRST_COMPLETED)
                for future in done:
                    row, attempt_number = inflight.pop(future)
                    attempt, result = future.result()
                    append_jsonl(attempts_path, attempt)
                    attempts.append(attempt)
                    attempts_by_id.setdefault(row["provider_request_id"], []).append(attempt)
                    if result is not None:
                        append_jsonl(results_path, result)
                        results.append(result)
                        result_ids.add(row["provider_request_id"])
                    elif (
                        _is_retryable(attempt)
                        and attempt_number < MAX_ATTEMPTS_PER_LOGICAL_REQUEST
                        and len(attempts) + len(inflight)
                        < ABSOLUTE_PROVIDER_REQUEST_CEILING
                    ):
                        queue.append((row, attempt_number + 1))

        terminal_ids = set(result_ids)
        for request_id, prior in attempts_by_id.items():
            if prior and (
                not _is_retryable(prior[-1])
                or len(prior) >= MAX_ATTEMPTS_PER_LOGICAL_REQUEST
            ):
                terminal_ids.add(request_id)
        status_counts = Counter(str(row.get("http_status")) for row in attempts)
        summary = {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "payload_sha256": manifest["payload_sha256"],
            "logical_requests": EXPECTED_REQUESTS,
            "provider_requests_attempted": len(attempts),
            "successful_responses": len(results),
            "terminal_without_response": len(terminal_ids - result_ids),
            "unfinished_logical_requests": EXPECTED_REQUESTS - len(terminal_ids),
            "http_status_counts": dict(sorted(status_counts.items())),
            "absolute_provider_request_ceiling": ABSOLUTE_PROVIDER_REQUEST_CEILING,
            "status": "complete" if len(terminal_ids) == EXPECTED_REQUESTS else "incomplete",
            "usage": {
                "prompt_tokens": sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in results),
                "completion_tokens": sum((r.get("usage") or {}).get("completion_tokens", 0) for r in results),
                "total_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) for r in results),
            },
            "monetary_cost": None,
            "monetary_cost_note": "Fanar API schema does not publish a price.",
        }
        (OUTPUT_DIR / "run_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        return summary


def _script_counts(text: str) -> Counter:
    counts: Counter = Counter()
    for character in text:
        codepoint = ord(character)
        name = unicodedata.name(character, "")
        if 0x4E00 <= codepoint <= 0x9FFF:
            counts["han"] += 1
        elif 0x0600 <= codepoint <= 0x06FF:
            counts["arabic"] += 1
        elif 0x0400 <= codepoint <= 0x04FF:
            counts["cyrillic"] += 1
        elif 0x0900 <= codepoint <= 0x097F:
            counts["devanagari"] += 1
        elif "LATIN" in name:
            counts["latin"] += 1
    return counts


def audit() -> dict:
    """Write deterministic transport and script diagnostics, never labels."""
    manifest = prepare()
    summary = json.loads((OUTPUT_DIR / "run_summary.json").read_text())
    if summary["status"] != "complete" or summary["payload_sha256"] != manifest["payload_sha256"]:
        raise ValueError("Fanar pilot is not complete for this frozen payload")
    attempts = read_jsonl(OUTPUT_DIR / "attempts.jsonl")
    results = read_jsonl(OUTPUT_DIR / "results.jsonl")
    requests = {
        row["provider_request_id"]: row
        for row in read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    }
    expected_script = {
        "en": "latin", "zh": "han", "ar": "arabic",
        "ru": "cyrillic", "hi": "devanagari",
    }
    by_language = {}
    mismatch_rows = []
    for language in LANGUAGES:
        language_attempts = [row for row in attempts if row["prompt_language"] == language]
        language_results = [row for row in results if row["prompt_language"] == language]
        mismatches = []
        for row in language_results:
            counts = _script_counts(row["response_text"])
            total = sum(counts.values()) or 1
            share = counts[expected_script[language]] / total
            if share < 0.20:
                mismatches.append(row["provider_request_id"])
                mismatch_rows.append({
                    "provider_request_id": row["provider_request_id"],
                    "prompt_id": row["prompt_id"],
                    "prompt_language": language,
                    "expected_script": expected_script[language],
                    "expected_script_share": round(share, 6),
                    "script_counts": dict(counts),
                })
        blocked = [row for row in language_attempts if row.get("http_status") == 400]
        by_language[language] = {
            "attempted": len(language_attempts),
            "returned": len(language_results),
            "provider_content_filter_blocks": len(blocked),
            "obvious_script_mismatches_among_returned": len(mismatches),
            "returned_rate": len(language_results) / len(language_attempts),
            "content_filter_rate": len(blocked) / len(language_attempts),
            "obvious_script_mismatch_rate_among_returned": (
                len(mismatches) / len(language_results) if language_results else None
            ),
        }
    blocked_issue_counts = Counter(
        (row["prompt_id"], row["prompt_language"])
        for row in attempts if row.get("http_status") == 400
    )
    output = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": manifest["payload_sha256"],
        "scope_note": (
            "Deterministic provider-status and Unicode-script diagnostics only. "
            "Script mismatch is not a human or model-judge language label, and "
            "no quantity here is a population prevalence estimate."
        ),
        "by_language": by_language,
        "obvious_script_mismatch_rows": mismatch_rows,
        "provider_content_filter_rows": [
            {
                "prompt_id": prompt_id,
                "prompt_language": language,
                "count": count,
                "pilot_band": next(
                    requests[row["provider_request_id"]]["pilot_band"]
                    for row in attempts
                    if row.get("http_status") == 400
                    and row["prompt_id"] == prompt_id
                    and row["prompt_language"] == language
                ),
            }
            for (prompt_id, language), count in sorted(blocked_issue_counts.items())
        ],
    }
    path = OUTPUT_DIR / "pilot_diagnostics.json"
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "prepare", "authorize", "run", "audit",
            "prepare-annotations", "cost-annotations", "authorize-annotations",
            "run-annotations", "summarize-annotations",
            "prepare-sol-audit", "cost-sol-audit", "authorize-sol-audit",
            "run-sol-audit", "score-sol-audit",
        ),
    )
    parser.add_argument("--payload-sha")
    parser.add_argument("--max-requests", type=int, default=ABSOLUTE_PROVIDER_REQUEST_CEILING)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        output = prepare()
    elif args.command == "authorize":
        if not args.payload_sha:
            parser.error("authorize requires --payload-sha")
        output = authorize(args.payload_sha, args.max_requests, args.confirm_user_authorization)
    elif args.command == "run":
        output = run(args.workers)
    elif args.command == "audit":
        output = audit()
    else:
        sys.path.insert(0, str(ROOT / "src"))
        from refusal_audit.model_expansion.fanar_annotation import (
            DEFAULT_DIR as ANNOTATION_DIR,
            SOL_DIR,
            authorize as authorize_annotations,
            authorize_sol,
            estimate_cost as estimate_annotation_cost,
            estimate_sol_cost,
            prepare as prepare_annotations,
            prepare_sol,
            run as run_annotations,
            run_sol,
            score_sol,
            summarize as summarize_annotations,
        )

        annotation_dir = ROOT / ANNOTATION_DIR
        sol_dir = ROOT / SOL_DIR
        if args.command == "prepare-annotations":
            output = prepare_annotations(ROOT, annotation_dir)
        elif args.command == "cost-annotations":
            output = estimate_annotation_cost(ROOT, annotation_dir)
        elif args.command == "authorize-annotations":
            if not args.payload_sha or args.cost_ceiling is None:
                parser.error(
                    "authorize-annotations requires --payload-sha and --cost-ceiling"
                )
            output = authorize_annotations(
                annotation_dir,
                args.payload_sha,
                args.cost_ceiling,
                args.confirm_user_authorization,
            )
        elif args.command == "run-annotations":
            if args.cost_ceiling is None:
                parser.error("run-annotations requires --cost-ceiling")
            from env_utils import load_env_from_file

            load_env_from_file()
            output = run_annotations(
                ROOT,
                annotation_dir,
                args.workers,
                args.cost_ceiling,
                args.authorize_paid_run,
            )
        elif args.command == "prepare-sol-audit":
            output = prepare_sol(ROOT, sol_dir)
        elif args.command == "cost-sol-audit":
            output = estimate_sol_cost(ROOT, sol_dir)
        elif args.command == "authorize-sol-audit":
            if not args.payload_sha or args.cost_ceiling is None:
                parser.error("authorize-sol-audit requires --payload-sha and --cost-ceiling")
            output = authorize_sol(
                sol_dir,
                args.payload_sha,
                args.cost_ceiling,
                args.confirm_user_authorization,
            )
        elif args.command == "run-sol-audit":
            if args.cost_ceiling is None:
                parser.error("run-sol-audit requires --cost-ceiling")
            from env_utils import load_env_from_file

            load_env_from_file()
            output = run_sol(
                ROOT,
                sol_dir,
                args.workers,
                args.cost_ceiling,
                args.authorize_paid_run,
            )
        elif args.command == "score-sol-audit":
            output = score_sol(ROOT, sol_dir)
        else:
            output = summarize_annotations(ROOT, annotation_dir)
    print(json.dumps(output, indent=2))
