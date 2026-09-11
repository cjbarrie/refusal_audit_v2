#!/usr/bin/env python3
"""Freeze and audit the 49,920-request Torch local-GGUF full-corpus run.

This module performs no inference. See docs/HPC_LOCAL_GGUF_FULL_V1.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/model_rosters/local_gguf_hpc_v1.json"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_full_hpc_v1"
PROMPT_PATTERN = "prompts/sampled/rebalanced_prompts_{language}_sample.json"
EXPECTED_PROMPTS = 2496


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
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_prompts(language: str) -> dict[str, dict[str, Any]]:
    path = ROOT / PROMPT_PATTERN.format(language=language)
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["prompts"]
    keyed = {row["id"]: row for row in rows}
    if len(rows) != EXPECTED_PROMPTS or len(keyed) != EXPECTED_PROMPTS:
        raise ValueError(f"{language} prompt file is not the 2,496-row canonical frame")
    return keyed


def render_prompt(template: str, text: str) -> tuple[str, list[str]]:
    """Render the exact single-user branch frozen during the local pilots."""
    if template == "chatml_single_user":
        return f"<|im_start|>user\n{text}<|im_end|>\n<|im_start|>assistant\n", ["<|im_start|>", "<|im_end|>"]
    if template == "krutrim_single_user":
        return f"<|user|>\n{text}<|assistant|>\n", []
    if template == "gigachat_single_user":
        return f"user<|role_sep|>\n{text}<|message_sep|>\n\nassistant<|role_sep|>\n", ["<|message_sep|>"]
    raise ValueError(f"unknown prompt template: {template}")


def task_map(config: dict[str, Any]) -> list[dict[str, Any]]:
    shards = int(config["slurm"]["shards_per_model_language_cell"])
    return [
        {"task_id": task_id, "model": model["name"], "language": language, "shard": shard, "shards": shards}
        for task_id, (model, language, shard) in enumerate(
            (model, language, shard)
            for model in config["models"]
            for language in config["languages"]
            for shard in range(shards)
        )
    ]


def prepare() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    languages = config["languages"]
    prompts = {language: load_prompts(language) for language in languages}
    prompt_ids = sorted(prompts["en"])
    if any(set(prompts[language]) != set(prompt_ids) for language in languages):
        raise ValueError("canonical prompt IDs differ across languages")
    input_hashes = {
        "config": sha_file(CONFIG_PATH),
        **{
            f"prompt_{language}": sha_file(ROOT / PROMPT_PATTERN.format(language=language))
            for language in languages
        },
    }
    requests_path = OUTPUT_DIR / "requests.jsonl"
    manifest_path = OUTPUT_DIR / "manifest.json"
    tasks_path = OUTPUT_DIR / "task_map.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("frozen HPC inputs changed; use a new versioned run directory")
        if manifest["logical_payload_sha256"] != sha_file(requests_path):
            raise ValueError("frozen HPC request ledger changed")
        if manifest["task_map_sha256"] != sha_file(tasks_path):
            raise ValueError("frozen HPC task map changed")
        return manifest

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    model_by_name = {model["name"]: model for model in config["models"]}
    rows: list[dict[str, Any]] = []
    for model in config["models"]:
        for language in languages:
            for prompt_id in prompt_ids:
                source = prompts[language][prompt_id]
                raw_prompt, stop = render_prompt(model["prompt_template"], source["text"])
                key = {
                    "version": "local-gguf-full-hpc-v1",
                    "model": model["name"],
                    "prompt_id": prompt_id,
                    "prompt_language": language,
                }
                rows.append({
                    **key,
                    "request_id": sha_object(key)[:24],
                    "source_model": model["source_model"],
                    "gguf_repository": model["gguf_repository"],
                    "gguf_revision": model["gguf_revision"],
                    "gguf_filename": model["gguf_filename"],
                    "developer": model["developer"],
                    "developer_jurisdiction": model["developer_jurisdiction"],
                    "quantizer": model["quantizer"],
                    "quantization": "Q8_0",
                    "raw_prompt": raw_prompt,
                    "stop": stop,
                    "settings": {
                        "temperature": config["runtime"]["temperature"],
                        "n_predict": config["runtime"]["max_output_tokens"],
                        "repeat_penalty": config["runtime"]["repeat_penalty"],
                        "context_tokens": config["runtime"]["context_tokens_per_slot"],
                    },
                    "prompt_metadata": {name: source.get(name) for name in (
                        "issue_id", "qid", "topic_domain", "controversy_tier",
                        "region_focus", "position_side", "route", "battery",
                        "prompt_origin_language", "prompt_origin_form",
                    )},
                })
    expected = len(config["models"]) * len(languages) * EXPECTED_PROMPTS
    if len(rows) != expected or len({row["request_id"] for row in rows}) != expected:
        raise ValueError("HPC request count or key uniqueness failure")
    with requests_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tasks = task_map(config)
    atomic_json(tasks_path, tasks)
    manifest = {
        "version": "local-gguf-full-hpc-v1",
        "created_at": now(),
        "status": "frozen_not_run",
        "scientific_role": config["scientific_role"],
        "slurm_account": config["slurm"]["account"],
        "models": list(model_by_name),
        "languages": languages,
        "n_prompt_meanings": EXPECTED_PROMPTS,
        "n_requests": expected,
        "n_array_tasks": len(tasks),
        "generation_settings": config["runtime"],
        "input_sha256": input_hashes,
        "logical_payload_sha256": sha_file(requests_path),
        "task_map_sha256": sha_file(tasks_path),
        "network_inference_call_made": False,
    }
    atomic_json(manifest_path, manifest)
    return manifest


def audit() -> dict[str, Any]:
    manifest = prepare()
    tasks = json.loads((OUTPUT_DIR / "task_map.json").read_text(encoding="utf-8"))
    expected_ids = {row["request_id"] for row in read_jsonl(OUTPUT_DIR / "requests.jsonl")}
    latest: dict[str, dict[str, Any]] = {}
    missing_task_files: list[int] = []
    for task in tasks:
        path = OUTPUT_DIR / "shards" / f"task_{task['task_id']:02d}" / "results.jsonl"
        if not path.exists():
            missing_task_files.append(task["task_id"])
            continue
        for row in read_jsonl(path):
            latest[row["request_id"]] = row
    unexpected = sorted(set(latest) - expected_ids)
    if unexpected:
        raise ValueError(f"unexpected result request IDs: {unexpected[:5]}")
    success = sum(bool((row.get("response_text") or "").strip()) for row in latest.values())
    empty = sum(row.get("error") == "empty_response" for row in latest.values())
    failed = sum(bool(row.get("error")) and row.get("error") != "empty_response" for row in latest.values())
    report = {
        "version": "local-gguf-full-hpc-audit-v1",
        "created_at": now(),
        "expected_requests": manifest["n_requests"],
        "latest_result_records": len(latest),
        "nonempty_responses": success,
        "empty_responses": empty,
        "transport_or_runtime_failures": failed,
        "missing_request_records": len(expected_ids - set(latest)),
        "missing_task_files": missing_task_files,
        "complete": len(latest) == len(expected_ids) and not missing_task_files,
        "interpretation": "Generation coverage only; semantic outcomes require the unchanged v2.4 annotation stage.",
    }
    atomic_json(OUTPUT_DIR / "audit.json", report)
    if report["complete"]:
        merged_path = OUTPUT_DIR / "responses.jsonl"
        with merged_path.open("w", encoding="utf-8") as handle:
            for request_id in sorted(latest):
                handle.write(json.dumps(latest[request_id], ensure_ascii=False, sort_keys=True) + "\n")
        report["responses_sha256"] = sha_file(merged_path)
        atomic_json(OUTPUT_DIR / "audit.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "audit"))
    args = parser.parse_args()
    value = prepare() if args.command == "prepare" else audit()
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
