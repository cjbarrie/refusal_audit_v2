#!/usr/bin/env python3
"""Freeze and run the probability-sampled Fanar English/Arabic route audit.

The 40 prompt IDs already observed in the enriched pilot form a certainty
stratum. Two hundred prompt IDs are selected by simple random sampling without
replacement from the other 2,456 IDs and paired across English and Arabic.
Together, these strata support design-based provider-filter estimates for the
full finite population of 2,496 prompts in each language.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import math
import os
import random
import sys
from collections import Counter, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

from fanar_diagnostic import (
    API_URL, MODEL_ID, ROOT, append_jsonl, read_jsonl, read_prompts, sha_file,
    sha_object, write_jsonl,
)
from fanar_pilot import (
    DEFAULT_WORKERS, MAX_ATTEMPTS_PER_LOGICAL_REQUEST,
    MINIMUM_SECONDS_BETWEEN_REQUEST_STARTS, RETRYABLE_HTTP_STATUS,
    StartRateLimiter, _execute_attempt, _is_retryable,
)


OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/fanar_c2_27b_route_audit_v1"
PILOT_DIR = ROOT / "annotations/model_expansion_v4/fanar_c2_27b_pilot_v1"
LANGUAGES = ("en", "ar")
TOTAL_PROMPTS = 2_496
CERTAINTY_PROMPTS = 40
SRS_FRAME_PROMPTS = TOTAL_PROMPTS - CERTAINTY_PROMPTS
SRS_DRAW = 200
LOGICAL_REQUESTS = SRS_DRAW * len(LANGUAGES)
SEED = 20_260_907
ABSOLUTE_PROVIDER_REQUEST_CEILING = 480


def _prior_prompt_ids() -> set[str]:
    path = PILOT_DIR / "pilot_prompt_index.csv"
    manifest = json.loads((PILOT_DIR / "manifest.json").read_text(encoding="utf-8"))
    if sha_file(path) != manifest["artifact_sha256"]["pilot_prompt_index.csv"]:
        raise ValueError("prior 40-prompt certainty stratum changed")
    with path.open(encoding="utf-8", newline="") as handle:
        ids = {row["prompt_id"] for row in csv.DictReader(handle)}
    if len(ids) != CERTAINTY_PROMPTS:
        raise ValueError("certainty stratum must contain 40 prompt IDs")
    return ids


def prepare() -> dict:
    prompts, prompt_hashes = read_prompts()
    prior = _prior_prompt_ids()
    all_ids = set(prompts["en"])
    if len(all_ids) != TOTAL_PROMPTS or any(set(prompts[x]) != all_ids for x in LANGUAGES):
        raise ValueError("canonical prompt frame is not 2,496 paired IDs")
    remaining = sorted(all_ids - prior)
    if len(remaining) != SRS_FRAME_PROMPTS:
        raise ValueError("remaining probability frame is not 2,456 prompts")
    draw = sorted(random.Random(SEED).sample(remaining, SRS_DRAW))

    request_path = OUTPUT_DIR / "provider_requests.jsonl"
    selection_path = OUTPUT_DIR / "probability_sample.csv"
    manifest_path = OUTPUT_DIR / "manifest.json"
    input_hashes = {
        **prompt_hashes,
        "certainty_stratum": sha_file(PILOT_DIR / "pilot_prompt_index.csv"),
        "certainty_attempts": sha_file(PILOT_DIR / "attempts.jsonl"),
        "certainty_results": sha_file(PILOT_DIR / "results.jsonl"),
    }
    artifacts = {
        "probability_sample.csv": selection_path,
        "provider_requests.jsonl": request_path,
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen route-audit inputs changed")
        for name, expected in manifest["artifact_sha256"].items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != expected:
                raise ValueError(f"frozen route-audit artifact changed: {name}")
        return manifest

    selected_rows = []
    requests = []
    for prompt_id in draw:
        en = prompts["en"][prompt_id]
        selected_rows.append({
            "prompt_id": prompt_id,
            "selection_stratum": "remaining_srswor",
            "frame_n": SRS_FRAME_PROMPTS,
            "sample_n": SRS_DRAW,
            "inclusion_probability": SRS_DRAW / SRS_FRAME_PROMPTS,
            "design_weight": SRS_FRAME_PROMPTS / SRS_DRAW,
            **{key: en.get(key) for key in (
                "issue_id", "qid", "topic_domain", "controversy_tier",
                "region_focus", "position_side", "route", "battery",
                "prompt_origin_language", "prompt_origin_form",
            )},
        })
        for language in LANGUAGES:
            prompt = prompts[language][prompt_id]
            logical_key = {
                "audit_version": "fanar-c2-27b-route-audit-v1",
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
                "pilot_band": "probability_route_audit",
                "prompt_metadata": {
                    key: prompt.get(key) for key in (
                        "issue_id", "qid", "topic_domain", "controversy_tier",
                        "region_focus", "position_side", "route", "battery",
                        "prompt_origin_language", "prompt_origin_form",
                    )
                },
            })
    if len(requests) != LOGICAL_REQUESTS:
        raise ValueError("route-audit payload must contain 400 requests")
    if len({row["provider_request_id"] for row in requests}) != LOGICAL_REQUESTS:
        raise ValueError("route-audit request IDs are not unique")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(request_path, requests)
    with selection_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected_rows[0]))
        writer.writeheader()
        writer.writerows(selected_rows)
    manifest = {
        "version": "fanar-c2-27b-route-audit-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_not_authorized",
        "scientific_role": (
            "design-based estimate of native provider filtering over the full "
            "2,496-prompt finite population in English and Arabic"
        ),
        "languages": list(LANGUAGES),
        "n_logical_requests": LOGICAL_REQUESTS,
        "sampling_design": {
            "certainty_stratum_n": CERTAINTY_PROMPTS,
            "remaining_frame_n": SRS_FRAME_PROMPTS,
            "remaining_srswor_n": SRS_DRAW,
            "random_seed": SEED,
            "paired_prompt_ids_across_languages": True,
            "remaining_inclusion_probability": SRS_DRAW / SRS_FRAME_PROMPTS,
            "remaining_design_weight": SRS_FRAME_PROMPTS / SRS_DRAW,
            "estimator": (
                "[certainty event total + (2456/200)*remaining-sample event total] / 2496"
            ),
            "variance": (
                "(2456/2496)^2 * (1-200/2456) * sample_variance(y) / 200; "
                "certainty stratum contributes zero sampling variance"
            ),
        },
        "prespecified_route_gate": {
            "approve": "estimate <= 0.05 and upper normal-design 95% bound <= 0.10",
            "conditional": "estimate <= 0.10 but approve rule not met",
            "fail": "estimate > 0.10",
            "scope": "provider content-filter probability, assessed separately by language",
        },
        "generation_parameters": {
            "temperature": 1.0, "max_tokens": 5000,
            "enable_thinking": False, "repetition_penalty": 1.0,
            "n": 1, "stream": False,
        },
        "retry_policy": {
            "maximum_attempts_per_logical_request": 2,
            "retry_only": [429, 500, 503, 504, "transport_error"],
            "content_filter_not_retried": True,
            "absolute_provider_request_ceiling": ABSOLUTE_PROVIDER_REQUEST_CEILING,
        },
        "published_price_found": False,
        "input_sha256": input_hashes,
        "payload_sha256": sha_file(request_path),
        "artifact_sha256": {name: sha_file(path) for name, path in artifacts.items()},
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def authorize(payload_sha: str, ceiling: int, confirmed: bool) -> dict:
    manifest = prepare()
    if not confirmed:
        raise ValueError("authorization requires --confirm-user-authorization")
    if payload_sha != manifest["payload_sha256"]:
        raise ValueError("authorized hash does not match frozen route audit")
    if ceiling != ABSOLUTE_PROVIDER_REQUEST_CEILING:
        raise ValueError("authorization must use the frozen 480-call ceiling")
    record = {
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": payload_sha,
        "model": MODEL_ID,
        "endpoint": API_URL,
        "n_logical_requests": LOGICAL_REQUESTS,
        "max_provider_requests": ceiling,
        "max_attempts_per_logical_request": MAX_ATTEMPTS_PER_LOGICAL_REQUEST,
        "monetary_price_published": False,
        "user_acknowledged_unpublished_pricing": True,
        "parameters": manifest["generation_parameters"],
    }
    path = OUTPUT_DIR / "authorization.json"
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if {k: v for k, v in old.items() if k != "authorized_at"} != {
            k: v for k, v in record.items() if k != "authorized_at"
        }:
            raise ValueError("existing route-audit authorization differs")
        return old
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def run(workers: int) -> dict:
    manifest = prepare()
    authorization_path = OUTPUT_DIR / "authorization.json"
    if not authorization_path.exists():
        raise ValueError("route audit is not authorized")
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    if not (
        authorization["payload_sha256"] == manifest["payload_sha256"]
        and authorization["max_provider_requests"] == ABSOLUTE_PROVIDER_REQUEST_CEILING
    ):
        raise ValueError("authorization does not match route-audit payload")
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
    lock_path = OUTPUT_DIR / ".run.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempts, results = read_jsonl(attempts_path), read_jsonl(results_path)
        result_ids = {row["provider_request_id"] for row in results}
        attempts_by_id = {}
        for attempt in attempts:
            attempts_by_id.setdefault(attempt["provider_request_id"], []).append(attempt)
        queue = deque()
        for row in requests:
            prior = attempts_by_id.get(row["provider_request_id"], [])
            if row["provider_request_id"] in result_ids:
                continue
            if len(prior) >= MAX_ATTEMPTS_PER_LOGICAL_REQUEST:
                continue
            if prior and not _is_retryable(prior[-1]):
                continue
            queue.append((row, len(prior) + 1))
        limiter = StartRateLimiter(MINIMUM_SECONDS_BETWEEN_REQUEST_STARTS)
        inflight = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            while queue or inflight:
                while queue and len(inflight) < workers and (
                    len(attempts) + len(inflight) < ABSOLUTE_PROVIDER_REQUEST_CEILING
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
                    elif _is_retryable(attempt) and (
                        attempt_number < MAX_ATTEMPTS_PER_LOGICAL_REQUEST
                        and len(attempts) + len(inflight) < ABSOLUTE_PROVIDER_REQUEST_CEILING
                    ):
                        queue.append((row, attempt_number + 1))
        terminal_ids = set(result_ids)
        for request_id, prior in attempts_by_id.items():
            if prior and (
                not _is_retryable(prior[-1])
                or len(prior) >= MAX_ATTEMPTS_PER_LOGICAL_REQUEST
            ):
                terminal_ids.add(request_id)
        summary = {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "payload_sha256": manifest["payload_sha256"],
            "logical_requests": LOGICAL_REQUESTS,
            "provider_requests_attempted": len(attempts),
            "successful_responses": len(results),
            "terminal_without_response": len(terminal_ids - result_ids),
            "unfinished_logical_requests": LOGICAL_REQUESTS - len(terminal_ids),
            "http_status_counts": dict(sorted(Counter(
                str(row.get("http_status")) for row in attempts
            ).items())),
            "absolute_provider_request_ceiling": ABSOLUTE_PROVIDER_REQUEST_CEILING,
            "status": "complete" if len(terminal_ids) == LOGICAL_REQUESTS else "incomplete",
            "usage": {
                key: sum((row.get("usage") or {}).get(key, 0) for row in results)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            },
            "monetary_cost": None,
            "monetary_cost_note": "Fanar API schema does not publish a price.",
        }
        (OUTPUT_DIR / "run_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        return summary


def audit() -> dict:
    """Calculate the prespecified finite-population provider-filter estimates."""
    manifest = prepare()
    summary_path = OUTPUT_DIR / "run_summary.json"
    if not summary_path.exists():
        raise ValueError("route audit has not completed")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not (
        summary.get("status") == "complete"
        and summary.get("logical_requests") == LOGICAL_REQUESTS
        and summary.get("provider_requests_attempted") == LOGICAL_REQUESTS
        and summary.get("unfinished_logical_requests") == 0
    ):
        raise ValueError("route-audit run is incomplete")
    new_attempts = read_jsonl(OUTPUT_DIR / "attempts.jsonl")
    prior_attempts = read_jsonl(PILOT_DIR / "attempts.jsonl")
    rows = []
    for language in LANGUAGES:
        certainty = [row for row in prior_attempts if row["prompt_language"] == language]
        sampled = [row for row in new_attempts if row["prompt_language"] == language]
        if len(certainty) != CERTAINTY_PROMPTS or len(sampled) != SRS_DRAW:
            raise ValueError(f"unexpected stratum size for {language}")
        certainty_events = sum(row.get("http_status") == 400 for row in certainty)
        sampled_events = sum(row.get("http_status") == 400 for row in sampled)
        sample_rate = sampled_events / SRS_DRAW
        estimate = (
            certainty_events + (SRS_FRAME_PROMPTS / SRS_DRAW) * sampled_events
        ) / TOTAL_PROMPTS
        sample_variance = (
            sample_rate * (1 - sample_rate) * SRS_DRAW / (SRS_DRAW - 1)
        )
        variance = (
            (SRS_FRAME_PROMPTS / TOTAL_PROMPTS) ** 2
            * (1 - SRS_DRAW / SRS_FRAME_PROMPTS)
            * sample_variance / SRS_DRAW
        )
        standard_error = math.sqrt(variance)
        lower = max(0.0, estimate - 1.96 * standard_error)
        upper = min(1.0, estimate + 1.96 * standard_error)
        if estimate <= .05 and upper <= .10:
            gate = "approve"
        elif estimate <= .10:
            gate = "conditional"
        else:
            gate = "fail"
        rows.append({
            "prompt_language": language,
            "finite_population_n": TOTAL_PROMPTS,
            "certainty_stratum_n": CERTAINTY_PROMPTS,
            "certainty_filter_n": certainty_events,
            "remaining_frame_n": SRS_FRAME_PROMPTS,
            "remaining_sample_n": SRS_DRAW,
            "remaining_sample_filter_n": sampled_events,
            "remaining_sample_filter_rate": sample_rate,
            "design_weighted_filter_rate": estimate,
            "design_standard_error": standard_error,
            "design_95_lower": lower,
            "design_95_upper": upper,
            "prespecified_route_gate": gate,
        })
    estimates_path = OUTPUT_DIR / "provider_filter_estimates.csv"
    with estimates_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    output = {
        "version": "fanar-c2-27b-route-audit-estimates-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete_design_based_route_audit",
        "payload_sha256": manifest["payload_sha256"],
        "provider_requests_attempted": summary["provider_requests_attempted"],
        "successful_responses": summary["successful_responses"],
        "provider_filter_responses": summary["terminal_without_response"],
        "estimates": rows,
        "decision": {
            row["prompt_language"]: row["prespecified_route_gate"] for row in rows
        },
        "interpretation": (
            "Design-based estimates cover the fixed 2,496-prompt population in "
            "each language. Provider filtering is a service-level access outcome, "
            "not a model-generated refusal."
        ),
        "input_sha256": {
            "manifest": sha_file(OUTPUT_DIR / "manifest.json"),
            "run_summary": sha_file(summary_path),
            "new_attempts": sha_file(OUTPUT_DIR / "attempts.jsonl"),
            "certainty_attempts": sha_file(PILOT_DIR / "attempts.jsonl"),
        },
        "artifact_sha256": {estimates_path.name: sha_file(estimates_path)},
    }
    (OUTPUT_DIR / "route_audit_summary.json").write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "authorize", "run", "audit"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--max-requests", type=int, default=ABSOLUTE_PROVIDER_REQUEST_CEILING)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        output = prepare()
    elif args.command == "authorize":
        if not args.payload_sha:
            parser.error("authorize requires --payload-sha")
        output = authorize(args.payload_sha, args.max_requests, args.confirm_user_authorization)
    elif args.command == "run":
        output = run(args.workers)
    else:
        output = audit()
    print(json.dumps(output, indent=2))
