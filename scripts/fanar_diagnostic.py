#!/usr/bin/env python3
"""Freeze the Fanar-C-2-27B diagnostic payload without calling the API.

The diagnostic reuses four prompt meanings from the frozen expansion-pilot
sample and sends each in all five canonical languages.  It is designed to
detect serving/template problems, incoherence, wrong-language output and
refusal behavior before a 200-response pilot.  It is not a probability sample
and must never be used to estimate refusal prevalence.
"""

from __future__ import annotations

import csv
import argparse
import fcntl
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/fanar_c2_27b_diagnostic_v1"
ROSTER_PATH = ROOT / "config/model_rosters/multirouter_expansion_v2.json"
SOURCE_DIR = ROOT / "annotations/model_expansion_v1/openrouter_pilot_v1"
LANGUAGES = ("en", "zh", "ar", "ru", "hi")
MODEL_ID = "Fanar-C-2-27B"
API_URL = "https://api.fanar.qa/v1/chat/completions"
ABSOLUTE_REQUEST_CEILING = 20

# Frozen after deterministic constrained selection from the 40-meaning pilot:
# one meaning from each pilot band, two regular and two boundary-testing cases,
# four distinct regions and four distinct domains, including one Arab case.
PROMPT_IDS = (
    "issue_Q112728845__bndB",
    "issue_yoash_tzidon_Q2778315__bndA",
    "issue_neve_gordon_Q627806__reg1",
    "issue_hal_light_utility_helicopter_Q3124734__reg2",
)


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha_object(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_selection() -> dict[str, dict[str, str]]:
    path = SOURCE_DIR / "pilot_prompt_index.csv"
    source_manifest = json.loads((SOURCE_DIR / "manifest.json").read_text())
    expected = source_manifest["artifact_sha256"]["pilot_prompt_index.csv"]
    if sha_file(path) != expected:
        raise ValueError("source pilot selection hash mismatch")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = {row["prompt_id"]: row for row in csv.DictReader(handle)}
    if any(prompt_id not in rows for prompt_id in PROMPT_IDS):
        raise ValueError("a frozen diagnostic prompt is absent from the pilot")
    return rows


def read_prompts() -> tuple[dict[str, dict[str, dict]], dict[str, str]]:
    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    prompts: dict[str, dict[str, dict]] = {}
    hashes: dict[str, str] = {}
    expected_ids: set[str] | None = None
    for language in LANGUAGES:
        spec = roster["design"]["prompt_files"][language]
        path = ROOT / spec["path"]
        actual_hash = sha_file(path)
        if actual_hash != spec["sha256"]:
            raise ValueError(f"canonical {language} prompt hash mismatch")
        rows = json.loads(path.read_text(encoding="utf-8"))["prompts"]
        prompts[language] = {row["id"]: row for row in rows}
        ids = set(prompts[language])
        if expected_ids is None:
            expected_ids = ids
        elif ids != expected_ids:
            raise ValueError("canonical prompt IDs differ across languages")
        hashes[f"prompt_{language}"] = actual_hash
    return prompts, hashes


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def prepare() -> dict:
    manifest_path = OUTPUT_DIR / "manifest.json"
    request_path = OUTPUT_DIR / "provider_requests.jsonl"
    selection_path = OUTPUT_DIR / "diagnostic_prompt_index.csv"
    source_selection = SOURCE_DIR / "pilot_prompt_index.csv"
    prompts, prompt_hashes = read_prompts()
    selection = read_selection()
    input_hashes = {
        "source_pilot_prompt_index": sha_file(source_selection),
        **prompt_hashes,
    }

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("existing frozen payload no longer matches its inputs")
        if sha_file(request_path) != manifest["payload_sha256"]:
            raise ValueError("existing frozen Fanar payload was modified")
        if sha_file(selection_path) != manifest["artifact_sha256"]["diagnostic_prompt_index.csv"]:
            raise ValueError("existing Fanar selection artifact was modified")
        return manifest

    requests: list[dict] = []
    for prompt_id in PROMPT_IDS:
        selected = selection[prompt_id]
        for language in LANGUAGES:
            prompt = prompts[language][prompt_id]
            logical_key = {
                "diagnostic_version": "fanar-c2-27b-diagnostic-v1",
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

    if len(requests) != 20 or len({r["provider_request_id"] for r in requests}) != 20:
        raise ValueError("Fanar diagnostic must contain 20 unique requests")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(request_path, requests)
    fields = list(next(iter(selection.values())).keys())
    with selection_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selection[prompt_id] for prompt_id in PROMPT_IDS)

    manifest = {
        "version": "fanar-c2-27b-diagnostic-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_not_authorized",
        "scientific_role": "operational and behavioral diagnostic; not prevalence estimation",
        "model": MODEL_ID,
        "developer": "Qatar Computing Research Institute (QCRI)",
        "developer_jurisdiction": "MENA",
        "provider": "Fanar native API",
        "endpoint": "https://api.fanar.qa/v1/chat/completions",
        "authentication_env": "FANAR_API_KEY",
        "n_prompt_meanings": 4,
        "languages": list(LANGUAGES),
        "n_requests": 20,
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
        "selection_rule": (
            "one meaning from each frozen pilot band; exactly two regular and two "
            "boundary-testing cases; maximize distinct regions and domains subject "
            "to including an Arab-region case; deterministic tie-break"
        ),
        "prompt_ids": list(PROMPT_IDS),
        "input_sha256": input_hashes,
        "payload_sha256": sha_file(request_path),
        "artifact_sha256": {
            "diagnostic_prompt_index.csv": sha_file(selection_path),
            "provider_requests.jsonl": sha_file(request_path),
        },
        "authorization": None,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def authorize(payload_sha256: str, max_requests: int, confirmed: bool) -> dict:
    """Record the user's exact authorization separately from frozen inputs."""
    manifest = prepare()
    if not confirmed:
        raise ValueError("authorization requires --confirm-user-authorization")
    if payload_sha256 != manifest["payload_sha256"]:
        raise ValueError("authorized payload SHA-256 does not match frozen payload")
    if max_requests != ABSOLUTE_REQUEST_CEILING:
        raise ValueError("Fanar diagnostic authorization must be exactly 20 requests")
    authorization = {
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": payload_sha256,
        "model": MODEL_ID,
        "endpoint": API_URL,
        "max_provider_requests": max_requests,
        "monetary_price_published": False,
        "user_acknowledged_unpublished_pricing": True,
        "parameters": manifest["generation_parameters"],
    }
    path = OUTPUT_DIR / "authorization.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        comparable = {k: v for k, v in existing.items() if k != "authorized_at"}
        expected = {k: v for k, v in authorization.items() if k != "authorized_at"}
        if comparable != expected:
            raise ValueError("existing authorization differs from requested authorization")
        return existing
    path.write_text(json.dumps(authorization, indent=2) + "\n", encoding="utf-8")
    return authorization


def _response_text(message: dict) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""


def _call_fanar(api_key: str, row: dict) -> tuple[int, dict, dict[str, str]]:
    payload = {
        key: row[key] for key in (
            "model", "messages", "temperature", "max_tokens",
            "enable_thinking", "repetition_penalty", "n", "stream",
        )
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
            headers = {
                key.lower(): value for key, value in response.headers.items()
                if key.lower().startswith("x-ratelimit")
                or key.lower() in {"ratelimit-policy", "retry-after"}
            }
            return response.status, body, headers
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"error": {"message": raw[:2000]}}
        headers = {
            key.lower(): value for key, value in exc.headers.items()
            if key.lower().startswith("x-ratelimit")
            or key.lower() in {"ratelimit-policy", "retry-after"}
        }
        return exc.code, body, headers


def run() -> dict:
    """Run each not-yet-attempted row once; never exceed 20 provider calls."""
    manifest = prepare()
    authorization_path = OUTPUT_DIR / "authorization.json"
    if not authorization_path.exists():
        raise ValueError("no recorded authorization for this payload")
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    if (
        authorization["payload_sha256"] != manifest["payload_sha256"]
        or authorization["max_provider_requests"] != ABSOLUTE_REQUEST_CEILING
    ):
        raise ValueError("authorization does not match frozen Fanar payload")

    sys.path.insert(0, str(ROOT / "scripts"))
    from env_utils import load_env_from_file

    load_env_from_file(ROOT / ".env")
    api_key = os.environ.get("FANAR_API_KEY")
    if not api_key:
        raise ValueError("FANAR_API_KEY is missing")

    lock_path = OUTPUT_DIR / ".run.lock"
    attempts_path = OUTPUT_DIR / "attempts.jsonl"
    results_path = OUTPUT_DIR / "results.jsonl"
    requests = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    with lock_path.open("w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempts = read_jsonl(attempts_path)
        if len(attempts) > ABSOLUTE_REQUEST_CEILING:
            raise ValueError("provider request ceiling was already exceeded")
        attempted_ids = {row["provider_request_id"] for row in attempts}

        for row in requests:
            if row["provider_request_id"] in attempted_ids:
                continue
            if len(attempts) >= ABSOLUTE_REQUEST_CEILING:
                break
            started = time.monotonic()
            attempt = {
                "provider_request_id": row["provider_request_id"],
                "prompt_id": row["prompt_id"],
                "prompt_language": row["prompt_language"],
                "attempted_at": datetime.now(timezone.utc).isoformat(),
                "attempt_number": 1,
            }
            try:
                http_status, body, headers = _call_fanar(api_key, row)
                attempt.update({
                    "http_status": http_status,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "rate_limit_headers": headers,
                    "provider_response": body,
                })
                append_jsonl(attempts_path, attempt)
                attempts.append(attempt)
                attempted_ids.add(row["provider_request_id"])
                if http_status == 200:
                    choices = body.get("choices") or []
                    if not choices or not isinstance(choices[0].get("message"), dict):
                        continue
                    choice = choices[0]
                    message = choice["message"]
                    append_jsonl(results_path, {
                        **{key: row[key] for key in (
                            "provider_request_id", "prompt_id", "prompt_language",
                            "model", "pilot_band", "prompt_metadata",
                        )},
                        "response_text": _response_text(message),
                        "response_message": message,
                        "finish_reason": choice.get("finish_reason"),
                        "provider_response_id": body.get("id"),
                        "provider_reported_model": body.get("model"),
                        "usage": body.get("usage"),
                        "created": body.get("created"),
                    })
            except Exception as exc:
                attempt.update({
                    "http_status": None,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "client_error_type": type(exc).__name__,
                    "client_error": str(exc)[:2000],
                })
                append_jsonl(attempts_path, attempt)
                attempts.append(attempt)
                attempted_ids.add(row["provider_request_id"])

        results = read_jsonl(results_path)
        summary = {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "payload_sha256": manifest["payload_sha256"],
            "provider_requests_attempted": len(attempts),
            "successful_responses": len(results),
            "failed_requests": len(attempts) - len(results),
            "absolute_request_ceiling": ABSOLUTE_REQUEST_CEILING,
            "request_ceiling_exhausted": len(attempts) == ABSOLUTE_REQUEST_CEILING,
            "status": "complete" if len(attempts) == len(requests) else "incomplete",
            "usage": {
                "prompt_tokens": sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in results),
                "completion_tokens": sum((r.get("usage") or {}).get("completion_tokens", 0) for r in results),
                "total_tokens": sum((r.get("usage") or {}).get("total_tokens", 0) for r in results),
            },
        }
        (OUTPUT_DIR / "run_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "authorize", "run"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--max-requests", type=int, default=ABSOLUTE_REQUEST_CEILING)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        output = prepare()
    elif args.command == "authorize":
        if not args.payload_sha:
            parser.error("authorize requires --payload-sha")
        output = authorize(
            args.payload_sha, args.max_requests, args.confirm_user_authorization
        )
    else:
        output = run()
    print(json.dumps(output, indent=2))
