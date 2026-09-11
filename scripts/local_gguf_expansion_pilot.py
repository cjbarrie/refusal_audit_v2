#!/usr/bin/env python3
"""Run the frozen 40-meaning pilot for locally hosted GGUF candidates.

The pilot reuses the exact enriched prompt selection used by earlier expansion
screens. It is for model-language admission, not prevalence estimation.
Technical record: docs/LOCAL_GGUF_MODEL_EXPANSION_V1.md
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import time
import urllib.error
from pathlib import Path
from typing import Any

from jurisdiction_expansion_pilot import load_selection
from local_gguf_expansion_smoke import (
    CONFIG_PATH,
    LANGUAGES,
    ROOT,
    SOURCE_SELECTION,
    atomic_json,
    load_prompt,
    now,
    post_json,
    prompt_paths,
    read_jsonl,
    sha_file,
    sha_object,
    write_jsonl,
)


OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_pilot_v1"
ADVANCING_MODELS = (
    "krutrim-2-instruct-local-q8",
    "eurollm-22b-instruct-2512-local-q8",
    "salamandra-7b-instruct-2606-local-q8",
)
EXPECTED_MEANINGS = 40
EXPECTED_REQUESTS = len(ADVANCING_MODELS) * EXPECTED_MEANINGS * len(LANGUAGES)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def prepare() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    models_by_name = {row["name"]: row for row in config["models"]}
    if set(ADVANCING_MODELS) - set(models_by_name):
        raise ValueError("advancing local model is absent from frozen roster")
    selection = load_selection()
    if len(selection) != EXPECTED_MEANINGS:
        raise ValueError("pilot selection is not the frozen 40-meaning design")
    input_hashes = {
        "config": sha_file(CONFIG_PATH),
        "source_selection": sha_file(SOURCE_SELECTION),
        **{f"prompt_{language}": sha_file(path) for language, path in prompt_paths().items()},
    }
    requests_path = OUTPUT_DIR / "requests.jsonl"
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("frozen local pilot inputs have changed")
        if manifest["logical_payload_sha256"] != sha_file(requests_path):
            raise ValueError("frozen local pilot request payload has changed")
        return manifest

    runtime = config["runtime"]
    requests: list[dict[str, Any]] = []
    for model_name in ADVANCING_MODELS:
        model = models_by_name[model_name]
        for selected in selection:
            prompt_id = selected["prompt_id"]
            for language in LANGUAGES:
                prompt = load_prompt(language, prompt_id)
                key = {
                    "version": "local-gguf-pilot-v1",
                    "model": model_name,
                    "prompt_id": prompt_id,
                    "prompt_language": language,
                }
                requests.append({
                    **key,
                    "request_id": sha_object(key)[:24],
                    "ollama_model": model["ollama_model"],
                    "source_model": model["source_model"],
                    "gguf_repository": model["gguf_repository"],
                    "developer": model["developer"],
                    "developer_jurisdiction": model["developer_jurisdiction"],
                    "quantizer": model["quantizer"],
                    "quantization": runtime["quantization"],
                    "messages": [{"role": "user", "content": prompt["text"]}],
                    "options": {
                        "temperature": runtime["temperature"],
                        "num_predict": runtime["max_output_tokens"],
                        "num_ctx": runtime["context_tokens"],
                        "repeat_penalty": runtime["repeat_penalty"],
                    },
                    "keep_alive": runtime["keep_alive"],
                    "pilot_band": selected["pilot_band"],
                    "prompt_metadata": {name: prompt.get(name) for name in (
                        "issue_id", "qid", "topic_domain", "controversy_tier",
                        "region_focus", "position_side", "route", "battery",
                        "prompt_origin_language", "prompt_origin_form",
                    )},
                })
    if len(requests) != EXPECTED_REQUESTS:
        raise ValueError(f"expected {EXPECTED_REQUESTS} requests, got {len(requests)}")
    if len({row["request_id"] for row in requests}) != EXPECTED_REQUESTS:
        raise ValueError("local pilot request IDs are not unique")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(requests_path, requests)
    manifest = {
        "version": "local-gguf-pilot-v1",
        "created_at": now(),
        "status": "frozen_not_run",
        "scientific_role": "enriched model-language admission pilot; not prevalence estimation",
        "models": list(ADVANCING_MODELS),
        "languages": list(LANGUAGES),
        "n_prompt_meanings": EXPECTED_MEANINGS,
        "n_requests": EXPECTED_REQUESTS,
        "local_only": True,
        "paid_provider_calls": False,
        "execution_concurrency": 1,
        "input_sha256": input_hashes,
        "logical_payload_sha256": sha_file(requests_path),
        "excluded_runtime_failures": ["gigachat3-10b-a1.8b-local-q8"],
    }
    atomic_json(manifest_path, manifest)
    return manifest


def capture_runtime(model: dict[str, Any], api_base: str) -> None:
    path = OUTPUT_DIR / "runtime_provenance.json"
    value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"models": {}}
    version = subprocess.run(["ollama", "--version"], capture_output=True, text=True, check=False)
    value.update({
        "captured_at": now(),
        "ollama_version": (version.stdout or version.stderr).strip(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    })
    value["models"][model["name"]] = post_json(
        f"{api_base}/api/show", {"model": model["ollama_model"]}, timeout=120
    )
    atomic_json(path, value)


def run(only_model: str) -> None:
    manifest = prepare()
    if only_model not in ADVANCING_MODELS:
        raise ValueError("run one advancing model at a time")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    model = next(row for row in config["models"] if row["name"] == only_model)
    api_base = config["runtime"]["api_base"].rstrip("/")
    manifest.update({
        "status": "running",
        "active_model": only_model,
        "run_started_at": manifest.get("run_started_at") or now(),
    })
    atomic_json(OUTPUT_DIR / "manifest.json", manifest)
    capture_runtime(model, api_base)
    responses_path = OUTPUT_DIR / "responses.jsonl"
    completed = {
        row["request_id"] for row in read_jsonl(responses_path)
        if (row.get("response_text") or "").strip()
    }
    rows = [row for row in read_jsonl(OUTPUT_DIR / "requests.jsonl") if row["model"] == only_model]
    for index, row in enumerate(rows, start=1):
        if row["request_id"] in completed:
            continue
        started = time.monotonic()
        try:
            result = post_json(f"{api_base}/api/chat", {
                "model": row["ollama_model"],
                "messages": row["messages"],
                "stream": False,
                "options": row["options"],
                "keep_alive": row["keep_alive"],
            })
            response_text = (result.get("message") or {}).get("content") or ""
            record = {
                **{key: row[key] for key in row if key != "messages"},
                "completed_at": now(),
                "elapsed_seconds": time.monotonic() - started,
                "response_text": response_text,
                "done": result.get("done"),
                "done_reason": result.get("done_reason"),
                "prompt_eval_count": result.get("prompt_eval_count"),
                "eval_count": result.get("eval_count"),
                "total_duration_ns": result.get("total_duration"),
                "load_duration_ns": result.get("load_duration"),
                "error": None if response_text.strip() else "empty_response",
            }
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                body = ""
            record = {
                **{key: row[key] for key in row if key != "messages"},
                "completed_at": now(),
                "elapsed_seconds": time.monotonic() - started,
                "response_text": "",
                "error": f"HTTPError: HTTP {exc.code}" + (f": {body}" if body else ""),
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            record = {
                **{key: row[key] for key in row if key != "messages"},
                "completed_at": now(),
                "elapsed_seconds": time.monotonic() - started,
                "response_text": "",
                "error": f"{type(exc).__name__}: {exc}",
            }
        append_jsonl(responses_path, record)
        # Persist progress after each expensive local request so an interrupted
        # overnight run is self-describing before the final audit is written.
        manifest.update({
            "status": "running",
            "active_model": only_model,
            "last_progress_at": now(),
            "latest_record_count": len(read_jsonl(responses_path)),
        })
        atomic_json(OUTPUT_DIR / "manifest.json", manifest)
        print(json.dumps({
            "model": only_model,
            "progress": f"{index}/{len(rows)}",
            "language": row["prompt_language"],
            "prompt_id": row["prompt_id"],
            "output_tokens": record.get("eval_count"),
            "elapsed_seconds": round(record["elapsed_seconds"], 2),
            "error": record.get("error"),
        }, ensure_ascii=False), flush=True)

    latest = {row["request_id"]: row for row in read_jsonl(responses_path)}
    audit = {
        "version": "local-gguf-pilot-audit-v1",
        "created_at": now(),
        "expected_requests": EXPECTED_REQUESTS,
        "unique_latest_records": len(latest),
        "successful_responses": sum(bool((row.get("response_text") or "").strip()) for row in latest.values()),
        "by_model_language": [],
        "interpretation": "Enriched admission pilot; counts are not prevalence estimates.",
    }
    for model_name in ADVANCING_MODELS:
        for language in LANGUAGES:
            subset = [row for row in latest.values() if row["model"] == model_name and row["prompt_language"] == language]
            audit["by_model_language"].append({
                "model": model_name,
                "language": language,
                "records": len(subset),
                "successful": sum(bool((row.get("response_text") or "").strip()) for row in subset),
            })
    atomic_json(OUTPUT_DIR / "audit.json", audit)
    manifest.update({
        "status": "complete" if audit["successful_responses"] == EXPECTED_REQUESTS else "in_progress",
        "last_updated_at": now(),
        "responses_sha256": sha_file(responses_path),
        "runtime_provenance_sha256": sha_file(OUTPUT_DIR / "runtime_provenance.json"),
        "audit_sha256": sha_file(OUTPUT_DIR / "audit.json"),
    })
    atomic_json(OUTPUT_DIR / "manifest.json", manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run", "audit"))
    parser.add_argument("--model", choices=ADVANCING_MODELS)
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare(), indent=2, ensure_ascii=False))
    elif args.command == "run":
        if not args.model:
            raise SystemExit("run requires --model so local execution remains deliberately sequential")
        run(args.model)
    else:
        manifest = prepare()
        responses = read_jsonl(OUTPUT_DIR / "responses.jsonl")
        print(json.dumps({"manifest": manifest, "records": len(responses)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
