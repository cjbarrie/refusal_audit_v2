#!/usr/bin/env python3
"""Run GigaChat locally while bypassing its incompatible embedded Jinja parser.

Technical record: docs/LOCAL_GGUF_MODEL_EXPANSION_V1.md
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

from local_gguf_expansion_smoke import ROOT, atomic_json, now, read_jsonl, sha_file, sha_object, write_jsonl


SOURCE_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_smoke_v1"
OUTPUT_DIR = SOURCE_DIR / "gigachat_raw_repair_v1"
SERVER = Path("/Applications/Ollama.app/Contents/Resources/llama-server")
MODEL = "gigachat3-10b-a1.8b-local-q8"
PORT = 11435


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def official_prompt(text: str) -> str:
    """Render the no-system, single-user branch of the embedded template."""
    return f"user<|role_sep|>\n{text}<|message_sep|>\n\nassistant<|role_sep|>\n"


def blob_path() -> Path:
    proc = subprocess.run(
        ["ollama", "show", "--modelfile", "hf.co/ai-sage/GigaChat3-10B-A1.8B-GGUF:Q8_0"],
        capture_output=True, text=True, check=True,
    )
    source = next((line[5:].strip() for line in proc.stdout.splitlines() if line.startswith("FROM ")), "")
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError("downloaded GigaChat GGUF blob was not resolved")
    return path


def prepare() -> dict[str, Any]:
    source_path = SOURCE_DIR / "requests.jsonl"
    source = [row for row in read_jsonl(source_path) if row["model"] == MODEL]
    if len(source) != 5 or {row["prompt_language"] for row in source} != {"en", "zh", "ar", "ru", "hi"}:
        raise ValueError("source is not the frozen five-language GigaChat smoke")
    input_hashes = {"source_requests": sha_file(source_path)}
    requests_path = OUTPUT_DIR / "requests.jsonl"
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hashes or manifest["logical_payload_sha256"] != sha_file(requests_path):
            raise ValueError("frozen GigaChat repair contract changed")
        return manifest

    requests = []
    for row in source:
        key = {"version": "gigachat-local-template-repair-v1", "source_request_id": row["request_id"]}
        requests.append({
            **key,
            "request_id": sha_object(key)[:24],
            "model": MODEL,
            "prompt_id": row["prompt_id"],
            "prompt_language": row["prompt_language"],
            "source_model": row["source_model"],
            "gguf_repository": row["gguf_repository"],
            "quantization": row["quantization"],
            "raw_prompt": official_prompt(row["messages"][0]["content"]),
            "settings": {
                "temperature": row["options"]["temperature"],
                "n_predict": row["options"]["num_predict"],
                "repeat_penalty": row["options"]["repeat_penalty"],
                "context_tokens": row["options"]["num_ctx"],
                "stop": ["<|message_sep|>"],
            },
            "prompt_metadata": row["prompt_metadata"],
        })
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(requests_path, requests)
    manifest = {
        "version": "gigachat-local-template-repair-v1",
        "created_at": now(),
        "status": "frozen_not_run",
        "n_requests": 5,
        "local_only": True,
        "paid_provider_calls": False,
        "method": "raw completion with official single-user GigaChat role-token sequence",
        "startup_template": "chatml; startup validation only; never applied to experimental prompts",
        "server_binary": str(SERVER),
        "input_sha256": input_hashes,
        "logical_payload_sha256": sha_file(requests_path),
    }
    atomic_json(manifest_path, manifest)
    return manifest


def wait_ready(timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError("local GigaChat server did not become ready")


def completion(payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/completion",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read().decode("utf-8"))


def run() -> None:
    manifest = prepare()
    server_args = [
        str(SERVER), "--model", str(blob_path()), "--alias", MODEL,
        "--host", "127.0.0.1", "--port", str(PORT), "--ctx-size", "8192",
        "--no-jinja", "--chat-template", "chatml", "--no-webui", "--parallel", "1",
    ]
    log_path = OUTPUT_DIR / "server.log"
    manifest.update({"status": "running", "started_at": now(), "server_args": server_args})
    atomic_json(OUTPUT_DIR / "manifest.json", manifest)
    completed = {row["request_id"] for row in read_jsonl(OUTPUT_DIR / "responses.jsonl") if (row.get("response_text") or "").strip()}
    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(server_args, stdout=log, stderr=subprocess.STDOUT, text=True)
        try:
            wait_ready()
            for row in read_jsonl(OUTPUT_DIR / "requests.jsonl"):
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
                append_jsonl(OUTPUT_DIR / "responses.jsonl", record)
                print(json.dumps({"language": row["prompt_language"], "output_tokens": record.get("output_tokens"), "elapsed_seconds": round(record["elapsed_seconds"], 2), "error": record.get("error")}, ensure_ascii=False), flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    latest = {row["request_id"]: row for row in read_jsonl(OUTPUT_DIR / "responses.jsonl")}
    audit = {
        "version": "gigachat-local-template-repair-audit-v1", "created_at": now(),
        "expected": 5, "records": len(latest),
        "successful": sum(bool((row.get("response_text") or "").strip()) for row in latest.values()),
        "cells": [{"language": row["prompt_language"], "characters": len(row.get("response_text") or ""), "output_tokens": row.get("output_tokens"), "stop_type": row.get("stop_type"), "error": row.get("error")} for row in sorted(latest.values(), key=lambda item: item["prompt_language"])],
    }
    atomic_json(OUTPUT_DIR / "audit.json", audit)
    manifest.update({
        "status": "complete" if audit["successful"] == 5 else "incomplete", "completed_at": now(),
        "responses_sha256": sha_file(OUTPUT_DIR / "responses.jsonl"), "audit_sha256": sha_file(OUTPUT_DIR / "audit.json"),
        "server_log_sha256": sha_file(log_path),
    })
    atomic_json(OUTPUT_DIR / "manifest.json", manifest)
    print(json.dumps(audit, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run"))
    args = parser.parse_args()
    print(json.dumps(prepare(), indent=2, ensure_ascii=False)) if args.command == "prepare" else run()


if __name__ == "__main__":
    main()
