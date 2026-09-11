#!/usr/bin/env python3
"""Freeze and audit the matched 200-response local Fanar-1 pilot.

This is a distinct checkpoint from the native Fanar-C-2-27B service. Preparing
the ledger makes no inference request and submits no Slurm job.

Technical record: docs/FANAR_EXPERIMENTS_V1.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/model_rosters/fanar_experiments_v1.json"
SOURCE_SELECTION = ROOT / "annotations/model_expansion_v1/openrouter_pilot_v1/pilot_prompt_index.csv"
SOURCE_MANIFEST = ROOT / "annotations/model_expansion_v1/openrouter_pilot_v1/manifest.json"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/fanar_1_9b_local_pilot_hpc_v1"
PROMPT_PATTERN = "prompts/sampled/rebalanced_prompts_{language}_sample.json"
LANGUAGES = ("en", "zh", "ar", "ru", "hi")
EXPECTED_MEANINGS = 40
EXPECTED_REQUESTS = 200


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
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def model_spec() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    models = [row for row in config["systems"] if row["name"] == "fanar-1-9b-instruct-local-q8"]
    if len(models) != 1:
        raise ValueError("local Fanar model is not unique in the experiment roster")
    return models[0]


def prepare() -> dict[str, Any]:
    source = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    expected_selection_hash = source["artifact_sha256"]["pilot_prompt_index.csv"]
    if sha_file(SOURCE_SELECTION) != expected_selection_hash:
        raise ValueError("shared 40-meaning pilot selection hash changed")
    with SOURCE_SELECTION.open(encoding="utf-8", newline="") as handle:
        selection = list(csv.DictReader(handle))
    if len(selection) != EXPECTED_MEANINGS or len({row["prompt_id"] for row in selection}) != EXPECTED_MEANINGS:
        raise ValueError("shared pilot selection is not 40 unique prompt meanings")

    prompts: dict[str, dict[str, dict[str, Any]]] = {}
    prompt_hashes: dict[str, str] = {}
    for language in LANGUAGES:
        path = ROOT / PROMPT_PATTERN.format(language=language)
        rows = json.loads(path.read_text(encoding="utf-8"))["prompts"]
        prompts[language] = {row["id"]: row for row in rows}
        prompt_hashes[f"prompt_{language}"] = sha_file(path)
    selected_ids = {row["prompt_id"] for row in selection}
    if any(not selected_ids <= set(prompts[language]) for language in LANGUAGES):
        raise ValueError("a selected prompt is absent from a language file")

    spec = model_spec()
    input_hashes = {
        "config": sha_file(CONFIG),
        "source_selection": sha_file(SOURCE_SELECTION),
        **prompt_hashes,
    }
    requests_path = OUTPUT_DIR / "requests.jsonl"
    tasks_path = OUTPUT_DIR / "task_map.json"
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("frozen local Fanar pilot inputs changed; create a new version")
        if sha_file(requests_path) != manifest["logical_payload_sha256"]:
            raise ValueError("frozen local Fanar request ledger changed")
        if sha_file(tasks_path) != manifest["task_map_sha256"]:
            raise ValueError("frozen local Fanar task map changed")
        return manifest

    shared = json.loads(CONFIG.read_text(encoding="utf-8"))["shared_design"]
    requests: list[dict[str, Any]] = []
    for selected in sorted(selection, key=lambda row: row["prompt_id"]):
        for language in LANGUAGES:
            prompt = prompts[language][selected["prompt_id"]]
            key = {
                "version": "fanar-1-9b-local-pilot-hpc-v1",
                "model": spec["name"],
                "prompt_id": selected["prompt_id"],
                "prompt_language": language,
            }
            requests.append({
                **key,
                "request_id": sha_object(key)[:24],
                "source_model": spec["model"],
                "source_revision": spec["source_revision"],
                "gguf_repository": spec["gguf_repository"],
                "gguf_revision": spec["gguf_revision"],
                "gguf_filename": spec["gguf_filename"],
                "developer": spec["developer"],
                "developer_jurisdiction": spec["developer_jurisdiction"],
                "quantizer": spec["quantizer"],
                "quantization": spec["quantization"],
                "raw_prompt": spec["raw_prompt_prefix"] + prompt["text"] + spec["raw_prompt_suffix"],
                "stop": spec["stop"],
                "settings": {
                    "temperature": shared["temperature"],
                    "n_predict": shared["max_output_tokens"],
                    "repeat_penalty": shared["repeat_penalty"],
                    "context_tokens": spec["context_tokens_per_slot"],
                },
                "pilot_band": selected["pilot_band"],
                "prompt_metadata": {name: prompt.get(name) for name in (
                    "issue_id", "qid", "topic_domain", "controversy_tier",
                    "region_focus", "position_side", "route", "battery",
                    "prompt_origin_language", "prompt_origin_form",
                )},
            })
    if len(requests) != EXPECTED_REQUESTS or len({row["request_id"] for row in requests}) != EXPECTED_REQUESTS:
        raise ValueError("local Fanar pilot must contain 200 unique requests")
    tasks = [
        {"task_id": index, "model": spec["name"], "language": language}
        for index, language in enumerate(LANGUAGES)
    ]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    with requests_path.open("w", encoding="utf-8") as handle:
        for row in requests:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    atomic_json(tasks_path, tasks)
    manifest = {
        "version": "fanar-1-9b-local-pilot-hpc-v1",
        "created_at": now(),
        "status": "frozen_not_run",
        "scientific_role": "matched local-checkpoint comparison; enriched admission pilot, not prevalence estimation",
        "model": spec["name"],
        "source_model": spec["model"],
        "native_api_comparator": "Fanar-C-2-27B",
        "comparability_warning": "different Fanar checkpoints; differences cannot be attributed solely to provider filtering",
        "languages": list(LANGUAGES),
        "n_prompt_meanings": EXPECTED_MEANINGS,
        "n_requests": EXPECTED_REQUESTS,
        "n_array_tasks": len(tasks),
        "generation_settings": {
            "temperature": shared["temperature"],
            "max_output_tokens": shared["max_output_tokens"],
            "repeat_penalty": shared["repeat_penalty"],
            "context_tokens_per_slot": spec["context_tokens_per_slot"],
            "parallel_slots": spec["parallel_slots"],
            "maximum_attempts": shared["maximum_attempts"],
        },
        "input_sha256": input_hashes,
        "logical_payload_sha256": sha_file(requests_path),
        "task_map_sha256": sha_file(tasks_path),
        "network_inference_call_made": False,
        "slurm_job_submitted": False,
    }
    atomic_json(manifest_path, manifest)
    return manifest


def audit() -> dict[str, Any]:
    manifest = prepare()
    tasks = json.loads((OUTPUT_DIR / "task_map.json").read_text())
    expected = {row["request_id"] for row in read_jsonl(OUTPUT_DIR / "requests.jsonl")}
    latest: dict[str, dict[str, Any]] = {}
    missing_tasks: list[int] = []
    for task in tasks:
        path = OUTPUT_DIR / "tasks" / f"task_{task['task_id']:02d}" / "results.jsonl"
        if not path.exists():
            missing_tasks.append(task["task_id"])
            continue
        for row in read_jsonl(path):
            latest[row["request_id"]] = row
    if set(latest) - expected:
        raise ValueError("local Fanar results contain unexpected request IDs")
    report = {
        "version": "fanar-1-9b-local-pilot-hpc-audit-v1",
        "created_at": now(),
        "expected_requests": manifest["n_requests"],
        "result_records": len(latest),
        "nonempty_responses": sum(bool((row.get("response_text") or "").strip()) for row in latest.values()),
        "terminal_errors": sum(bool(row.get("error")) for row in latest.values()),
        "missing_request_records": len(expected - set(latest)),
        "missing_task_files": missing_tasks,
        "complete": set(latest) == expected and not missing_tasks,
    }
    atomic_json(OUTPUT_DIR / "audit.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "audit"))
    args = parser.parse_args()
    print(json.dumps(prepare() if args.command == "prepare" else audit(), indent=2))
