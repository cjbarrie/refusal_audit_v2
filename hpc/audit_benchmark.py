#!/usr/bin/env python3
"""Summarize the four-model Torch benchmark before production submission."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from prepare_local_gguf_full import CONFIG_PATH, OUTPUT_DIR, atomic_json, now, read_jsonl


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    rows = []
    ready = True
    for task_id, model in enumerate(config["models"]):
        task_dir = OUTPUT_DIR / "benchmark" / f"task_{task_id:02d}"
        result_path = task_dir / "results.jsonl"
        runtime_path = task_dir / "runtime.json"
        if not result_path.exists() or not runtime_path.exists():
            rows.append({"task_id": task_id, "model": model["name"], "status": "missing"})
            ready = False
            continue
        latest = {row["request_id"]: row for row in read_jsonl(result_path)}
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        elapsed = [float(row["elapsed_seconds"]) for row in latest.values() if row.get("elapsed_seconds") is not None]
        output_tokens = sum(int(row.get("output_tokens") or 0) for row in latest.values())
        maximum = int(config["runtime"]["max_output_tokens"])
        nonempty = sum(bool((row.get("response_text") or "").strip()) for row in latest.values())
        terminal_errors = sum(bool(row.get("error")) and row.get("error") != "empty_response" for row in latest.values())
        wall = float(runtime.get("wall_elapsed_seconds") or 0)
        status = "ready_for_review" if len(latest) == 100 and terminal_errors == 0 else "failed_gate"
        ready = ready and status == "ready_for_review"
        rows.append({
            "task_id": task_id, "model": model["name"], "status": status,
            "terminal_records": len(latest), "nonempty_responses": nonempty,
            "empty_responses": len(latest) - nonempty, "terminal_errors": terminal_errors,
            "wall_elapsed_seconds": wall,
            "responses_per_minute": (len(latest) / wall * 60) if wall else None,
            "output_tokens_per_second": (output_tokens / wall) if wall else None,
            "median_request_latency_seconds": statistics.median(elapsed) if elapsed else None,
            "maximum_output_token_hits": sum(int(row.get("output_tokens") or 0) >= maximum for row in latest.values()),
            "by_language": [
                {
                    "language": language,
                    "records": len(subset),
                    "mean_output_tokens": statistics.mean(int(row.get("output_tokens") or 0) for row in subset),
                    "maximum_output_token_hits": sum(int(row.get("output_tokens") or 0) >= maximum for row in subset),
                }
                for language in config["languages"]
                for subset in [[row for row in latest.values() if row["prompt_language"] == language]]
            ],
        })
    report = {
        "version": "local-gguf-hpc-benchmark-audit-v1", "created_at": now(),
        "mechanical_gate_passed": ready,
        "human_review_still_required": True,
        "models": rows,
        "interpretation": "A mechanical pass permits inspection; it does not authorize or launch the production array.",
    }
    atomic_json(OUTPUT_DIR / "benchmark_audit.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
