#!/usr/bin/env python3
"""Freeze, run, and audit the four-model local-Q8 access smoke.

This is an operational screen, not an analysis sample. It sends one existing
frozen prompt meaning in all five study languages through a local Ollama API.
Technical record: docs/LOCAL_GGUF_MODEL_EXPANSION_V1.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/model_rosters/local_gguf_expansion_v1.json"
SOURCE_SELECTION = ROOT / "annotations/model_expansion_v1/openrouter_pilot_v1/pilot_prompt_index.csv"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_smoke_v1"
LANGUAGES = ("en", "zh", "ar", "ru", "hi")
EXPECTED_REQUESTS = 20


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha_object(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def prompt_paths() -> dict[str, Path]:
    return {language: ROOT / f"prompts/sampled/rebalanced_prompts_{language}_sample.json" for language in LANGUAGES}


def selected_prompt_id() -> str:
    with SOURCE_SELECTION.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 40 or len({row["prompt_id"] for row in rows}) != 40:
        raise ValueError("source selection is not the frozen 40-meaning pilot")
    return min(row["prompt_id"] for row in rows)


def load_prompt(language: str, prompt_id: str) -> dict[str, Any]:
    payload = json.loads(prompt_paths()[language].read_text(encoding="utf-8"))
    matches = [row for row in payload["prompts"] if row["id"] == prompt_id]
    if len(matches) != 1:
        raise ValueError(f"expected one {language} prompt for {prompt_id}")
    return matches[0]


def prepare() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("status") != "local_smoke_only" or len(config["models"]) != 4:
        raise ValueError("local roster must be a four-model smoke")
    runtime = config["runtime"]
    if runtime["quantization"] != "Q8_0":
        raise ValueError("all local smoke models must use Q8_0")
    prompt_id = selected_prompt_id()
    paths = prompt_paths()
    input_hashes = {
        "config": sha_file(CONFIG_PATH),
        "source_selection": sha_file(SOURCE_SELECTION),
        **{f"prompt_{language}": sha_file(path) for language, path in paths.items()},
    }
    request_path = OUTPUT_DIR / "requests.jsonl"
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("frozen local smoke inputs have changed")
        if manifest["logical_payload_sha256"] != sha_file(request_path):
            raise ValueError("frozen local smoke request payload has changed")
        return manifest

    requests: list[dict[str, Any]] = []
    for model in config["models"]:
        for language in LANGUAGES:
            prompt = load_prompt(language, prompt_id)
            key = {"version": "local-gguf-smoke-v1", "model": model["name"], "prompt_id": prompt_id, "prompt_language": language}
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
                "prompt_metadata": {name: prompt.get(name) for name in (
                    "issue_id", "qid", "topic_domain", "controversy_tier",
                    "region_focus", "position_side", "route", "battery")},
            })
    if len(requests) != EXPECTED_REQUESTS or len({row["request_id"] for row in requests}) != EXPECTED_REQUESTS:
        raise ValueError("local smoke request count or keys are invalid")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(request_path, requests)
    manifest = {
        "version": "local-gguf-smoke-v1",
        "created_at": now(),
        "status": "frozen_not_run",
        "scientific_role": config["scientific_role"],
        "prompt_id": prompt_id,
        "languages": list(LANGUAGES),
        "models": [model["name"] for model in config["models"]],
        "n_requests": len(requests),
        "local_only": True,
        "paid_provider_calls": False,
        "execution_concurrency": 1,
        "input_sha256": input_hashes,
        "logical_payload_sha256": sha_file(request_path),
    }
    atomic_json(manifest_path, manifest)
    return manifest


def ollama_version() -> str:
    proc = subprocess.run(["ollama", "--version"], capture_output=True, text=True, check=False)
    return (proc.stdout or proc.stderr).strip()


def post_json(url: str, payload: dict[str, Any], timeout: int = 900) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run(only_model: str | None = None) -> None:
    manifest = prepare()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    api_base = config["runtime"]["api_base"].rstrip("/")
    response_path = OUTPUT_DIR / "responses.jsonl"
    completed = {row["request_id"] for row in read_jsonl(response_path) if (row.get("response_text") or "").strip()}
    selected_models = [model for model in config["models"] if only_model in (None, model["name"])]
    if not selected_models:
        raise ValueError(f"unknown local model name: {only_model}")
    provenance_path = OUTPUT_DIR / "runtime_provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.exists() else {"models": {}}
    provenance.update({"captured_at": now(), "ollama_version": ollama_version(), "platform": platform.platform(), "machine": platform.machine()})
    for model in selected_models:
        provenance["models"][model["name"]] = post_json(f"{api_base}/api/show", {"model": model["ollama_model"]}, timeout=120)
    atomic_json(provenance_path, provenance)

    for row in read_jsonl(OUTPUT_DIR / "requests.jsonl"):
        if only_model is not None and row["model"] != only_model:
            continue
        if row["request_id"] in completed:
            continue
        started = time.monotonic()
        try:
            result = post_json(f"{api_base}/api/chat", {
                "model": row["ollama_model"], "messages": row["messages"],
                "stream": False, "options": row["options"], "keep_alive": row["keep_alive"]})
            text = (result.get("message") or {}).get("content") or ""
            record = {
                **{key: row[key] for key in row if key != "messages"},
                "completed_at": now(), "elapsed_seconds": time.monotonic() - started,
                "response_text": text, "done": result.get("done"),
                "done_reason": result.get("done_reason"),
                "prompt_eval_count": result.get("prompt_eval_count"),
                "eval_count": result.get("eval_count"),
                "total_duration_ns": result.get("total_duration"),
                "load_duration_ns": result.get("load_duration"),
                "error": None if text.strip() else "empty_response",
            }
        except urllib.error.HTTPError as exc:
            # Preserve the local server's diagnostic body. Ollama often puts the
            # actionable loader/template error there while the status itself is
            # only the generic HTTP 500.
            try:
                error_body = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                error_body = ""
            suffix = f": {error_body}" if error_body else ""
            record = {**{key: row[key] for key in row if key != "messages"}, "completed_at": now(), "elapsed_seconds": time.monotonic() - started, "response_text": "", "error": f"HTTPError: HTTP {exc.code}{suffix}"}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            record = {**{key: row[key] for key in row if key != "messages"}, "completed_at": now(), "elapsed_seconds": time.monotonic() - started, "response_text": "", "error": f"{type(exc).__name__}: {exc}"}
        append_jsonl(response_path, record)

    result = audit_rows(read_jsonl(response_path))
    atomic_json(OUTPUT_DIR / "audit.json", result)
    manifest.update({
        "status": "complete" if result["successful_responses"] == EXPECTED_REQUESTS else "incomplete",
        "completed_at": now(), "response_sha256": sha_file(response_path),
        "runtime_provenance_sha256": sha_file(provenance_path),
        "audit_sha256": sha_file(OUTPUT_DIR / "audit.json"),
    })
    atomic_json(OUTPUT_DIR / "manifest.json", manifest)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest = {row["request_id"]: row for row in rows}
    cells = []
    for row in sorted(latest.values(), key=lambda item: (item["model"], item["prompt_language"])):
        text = (row.get("response_text") or "").strip()
        cells.append({"model": row["model"], "language": row["prompt_language"], "success": bool(text), "characters": len(text), "output_tokens": row.get("eval_count"), "elapsed_seconds": row.get("elapsed_seconds"), "error": row.get("error")})
    return {"version": "local-gguf-smoke-audit-v1", "created_at": now(), "expected_requests": EXPECTED_REQUESTS, "unique_latest_records": len(latest), "successful_responses": sum(row["success"] for row in cells), "cells": cells, "interpretation": "Operational smoke only; no prevalence estimate is valid."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run", "audit"))
    parser.add_argument("--model", help="run one canonical local model name")
    args = parser.parse_args()
    if args.command == "prepare":
        print(json.dumps(prepare(), indent=2, ensure_ascii=False))
    elif args.command == "run":
        run(args.model)
    else:
        print(json.dumps(audit_rows(read_jsonl(OUTPUT_DIR / "responses.jsonl")), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
