#!/usr/bin/env python3
"""Run GigaChat's matched 40-meaning pilot through raw local completion.

The request construction and runtime repair are documented in
docs/LOCAL_GGUF_MODEL_EXPANSION_V1.md. This enriched pilot is for admission and
diagnosis; it does not estimate population prevalence.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

from gigachat_local_template_repair import SERVER, PORT, blob_path, completion, official_prompt, wait_ready
from jurisdiction_expansion_pilot import load_selection
from local_gguf_expansion_smoke import (
    CONFIG_PATH, LANGUAGES, ROOT, SOURCE_SELECTION, atomic_json, load_prompt,
    now, prompt_paths, read_jsonl, sha_file, sha_object, write_jsonl,
)


OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_pilot_v1/gigachat_raw_v1"
MODEL = "gigachat3-10b-a1.8b-local-q8"
EXPECTED = 200


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def prepare() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    model = next(row for row in config["models"] if row["name"] == MODEL)
    selection = load_selection()
    input_hashes = {
        "config": sha_file(CONFIG_PATH),
        "source_selection": sha_file(SOURCE_SELECTION),
        **{f"prompt_{language}": sha_file(path) for language, path in prompt_paths().items()},
        "repair_script": sha_file(ROOT / "scripts/gigachat_local_template_repair.py"),
    }
    request_path = OUTPUT_DIR / "requests.jsonl"
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("frozen GigaChat pilot inputs have changed")
        if manifest["logical_payload_sha256"] != sha_file(request_path):
            raise ValueError("frozen GigaChat pilot payload has changed")
        return manifest

    requests: list[dict[str, Any]] = []
    for selected in selection:
        for language in LANGUAGES:
            prompt = load_prompt(language, selected["prompt_id"])
            key = {
                "version": "gigachat-local-pilot-v1",
                "model": MODEL,
                "prompt_id": selected["prompt_id"],
                "prompt_language": language,
            }
            requests.append({
                **key,
                "request_id": sha_object(key)[:24],
                "source_model": model["source_model"],
                "gguf_repository": model["gguf_repository"],
                "developer": model["developer"],
                "developer_jurisdiction": model["developer_jurisdiction"],
                "quantization": config["runtime"]["quantization"],
                "raw_prompt": official_prompt(prompt["text"]),
                "settings": {
                    "temperature": config["runtime"]["temperature"],
                    "n_predict": config["runtime"]["max_output_tokens"],
                    "repeat_penalty": config["runtime"]["repeat_penalty"],
                    "context_tokens": config["runtime"]["context_tokens"],
                    "stop": ["<|message_sep|>"],
                },
                "pilot_band": selected["pilot_band"],
                "prompt_metadata": {name: prompt.get(name) for name in (
                    "issue_id", "qid", "topic_domain", "controversy_tier",
                    "region_focus", "position_side", "route", "battery",
                    "prompt_origin_language", "prompt_origin_form",
                )},
            })
    if len(requests) != EXPECTED or len({row["request_id"] for row in requests}) != EXPECTED:
        raise ValueError("GigaChat pilot does not contain 200 unique requests")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(request_path, requests)
    manifest = {
        "version": "gigachat-local-pilot-v1",
        "created_at": now(),
        "status": "frozen_not_run",
        "scientific_role": "enriched model-language admission pilot; not prevalence estimation",
        "model": MODEL,
        "languages": list(LANGUAGES),
        "n_prompt_meanings": 40,
        "n_requests": EXPECTED,
        "local_only": True,
        "paid_provider_calls": False,
        "execution_concurrency": 1,
        "transport": "llama-server raw completion with official GigaChat role tokens",
        "input_sha256": input_hashes,
        "logical_payload_sha256": sha_file(request_path),
    }
    atomic_json(manifest_path, manifest)
    return manifest


def run() -> None:
    manifest = prepare()
    args = [
        str(SERVER), "--model", str(blob_path()), "--alias", MODEL,
        "--host", "127.0.0.1", "--port", str(PORT), "--ctx-size", "8192",
        "--no-jinja", "--chat-template", "chatml", "--no-webui", "--parallel", "1",
    ]
    response_path = OUTPUT_DIR / "responses.jsonl"
    completed = {row["request_id"] for row in read_jsonl(response_path) if (row.get("response_text") or "").strip()}
    manifest.update({"status": "running", "started_at": manifest.get("started_at") or now(), "server_args": args})
    atomic_json(OUTPUT_DIR / "manifest.json", manifest)
    with (OUTPUT_DIR / "server.log").open("a", encoding="utf-8") as log:
        process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, text=True)
        try:
            wait_ready()
            rows = read_jsonl(OUTPUT_DIR / "requests.jsonl")
            for index, row in enumerate(rows, start=1):
                if row["request_id"] in completed:
                    continue
                started = time.monotonic()
                try:
                    settings = row["settings"]
                    result = completion({
                        "prompt": row["raw_prompt"], "n_predict": settings["n_predict"],
                        "temperature": settings["temperature"], "repeat_penalty": settings["repeat_penalty"],
                        "stop": settings["stop"], "stream": False,
                    })
                    text = result.get("content") or ""
                    record = {
                        **{key: value for key, value in row.items() if key != "raw_prompt"},
                        "completed_at": now(), "elapsed_seconds": time.monotonic() - started,
                        "response_text": text, "output_tokens": result.get("tokens_predicted"),
                        "stop_type": result.get("stop_type"), "timings": result.get("timings"),
                        "error": None if text.strip() else "empty_response",
                    }
                except Exception as exc:
                    record = {
                        **{key: value for key, value in row.items() if key != "raw_prompt"},
                        "completed_at": now(), "elapsed_seconds": time.monotonic() - started,
                        "response_text": "", "error": f"{type(exc).__name__}: {exc}",
                    }
                append_jsonl(response_path, record)
                manifest.update({"status": "running", "latest_record_count": len(read_jsonl(response_path)), "last_progress_at": now()})
                atomic_json(OUTPUT_DIR / "manifest.json", manifest)
                print(json.dumps({"progress": f"{index}/{EXPECTED}", "language": row["prompt_language"], "prompt_id": row["prompt_id"], "output_tokens": record.get("output_tokens"), "elapsed_seconds": round(record["elapsed_seconds"], 2), "error": record.get("error")}, ensure_ascii=False), flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    latest = {row["request_id"]: row for row in read_jsonl(response_path)}
    audit = {
        "version": "gigachat-local-pilot-audit-v1", "created_at": now(),
        "expected_requests": EXPECTED, "records": len(latest),
        "successful": sum(bool((row.get("response_text") or "").strip()) for row in latest.values()),
        "by_language": [{
            "language": language,
            "records": sum(row["prompt_language"] == language for row in latest.values()),
            "successful": sum(row["prompt_language"] == language and bool((row.get("response_text") or "").strip()) for row in latest.values()),
        } for language in LANGUAGES],
        "interpretation": "Enriched admission pilot; not a prevalence estimate.",
    }
    atomic_json(OUTPUT_DIR / "audit.json", audit)
    manifest.update({
        "status": "complete" if audit["successful"] == EXPECTED else "incomplete", "completed_at": now(),
        "responses_sha256": sha_file(response_path), "audit_sha256": sha_file(OUTPUT_DIR / "audit.json"),
        "server_log_sha256": sha_file(OUTPUT_DIR / "server.log"),
    })
    atomic_json(OUTPUT_DIR / "manifest.json", manifest)
    print(json.dumps(audit, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run", "audit"))
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare(), indent=2, ensure_ascii=False))
    elif args.command == "run":
        run()
    else:
        print(json.dumps({"manifest": prepare(), "records": len(read_jsonl(OUTPUT_DIR / "responses.jsonl"))}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
