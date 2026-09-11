#!/usr/bin/env python3
"""Run one benchmark or full-generation shard through a private llama.cpp server."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from prepare_local_gguf_full import CONFIG_PATH, OUTPUT_DIR, ROOT, atomic_json, now, prepare, read_jsonl, sha_file, sha_object

WRITE_LOCK = threading.Lock()
TRANSIENT_HTTP = {408, 429, 500, 502, 503, 504}


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with WRITE_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def post_json(url: str, payload: dict[str, Any], timeout: int = 1800) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_ready(port: int, process: subprocess.Popen[Any], timeout: int = 900) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"llama-server exited during startup with code {process.returncode}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError("llama-server did not become healthy within 15 minutes")


def select_task_rows(mode: str, task_id: int, config: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    tasks = json.loads((OUTPUT_DIR / "task_map.json").read_text(encoding="utf-8"))
    if mode == "benchmark":
        model = config["models"][task_id]
        task = {"task_id": task_id, "model": model["name"], "language": "mixed", "shard": 0, "shards": 1}
        pool = [row for row in read_jsonl(OUTPUT_DIR / "requests.jsonl") if row["model"] == model["name"]]
        ranked = sorted(pool, key=lambda row: sha_object({"seed": "torch-benchmark-v1", "request_id": row["request_id"]}))
        by_language = {language: [] for language in config["languages"]}
        for row in ranked:
            if len(by_language[row["prompt_language"]]) < 20:
                by_language[row["prompt_language"]].append(row)
        rows = [row for language in config["languages"] for row in by_language[language]]
        return task, rows
    if task_id < 0 or task_id >= len(tasks):
        raise ValueError(f"full-run task ID must be between 0 and {len(tasks) - 1}")
    task = tasks[task_id]
    rows = [
        row for row in read_jsonl(OUTPUT_DIR / "requests.jsonl")
        if row["model"] == task["model"]
        and row["prompt_language"] == task["language"]
        and int(sha_object(row["request_id"]), 16) % task["shards"] == task["shard"]
    ]
    return task, sorted(rows, key=lambda row: row["request_id"])


def run(mode: str, task_id: int) -> None:
    wall_started = time.monotonic()
    prepare()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    task, rows = select_task_rows(mode, task_id, config)
    model = next(item for item in config["models"] if item["name"] == task["model"])
    run_root = OUTPUT_DIR / ("benchmark" if mode == "benchmark" else "shards") / f"task_{task_id:02d}"
    run_root.mkdir(parents=True, exist_ok=True)
    result_path = run_root / "results.jsonl"
    attempt_path = run_root / "attempts.jsonl"
    completed = {row["request_id"] for row in read_jsonl(result_path)}
    attempts_used: dict[str, int] = {}
    for row in read_jsonl(attempt_path):
        attempts_used[row["request_id"]] = max(attempts_used.get(row["request_id"], 0), int(row["attempt"]))
    pending = [row for row in rows if row["request_id"] not in completed and attempts_used.get(row["request_id"], 0) < 2]
    if not pending:
        print(json.dumps({"status": "nothing_pending", "task": task, "expected_rows": len(rows)}))
        return

    task_root = Path(os.environ.get("REFUSAL_HPC_ROOT", f"/scratch/{os.environ['USER']}/refusal_audit_hpc"))
    container = task_root / "containers" / "llama-server-cuda-b10335.sif"
    weights = task_root / "models" / model["name"] / model["gguf_filename"]
    if not container.is_file() or not weights.is_file():
        raise FileNotFoundError("container or pinned model weights are absent; run bootstrap and download jobs first")
    port = free_port()
    runtime = config["runtime"]
    server_args = [
        # The pinned llama.cpp image stores its shared libraries in /app but
        # does not declare that directory to Apptainer's dynamic loader. Keep
        # Apptainer's injected NVIDIA path as well as the image library path.
        "apptainer", "exec", "--nv", "--env",
        "LD_LIBRARY_PATH=/app:/.singularity.d/libs", str(container), "/app/llama-server",
        "--model", str(weights), "--alias", model["name"],
        "--host", "127.0.0.1", "--port", str(port),
        "--ctx-size", str(runtime["context_tokens_per_slot"] * runtime["parallel_slots"]),
        "--parallel", str(runtime["parallel_slots"]), "--n-gpu-layers", "999",
        "--no-jinja", "--chat-template", "chatml", "--no-webui",
    ]
    metadata = {
        "version": "local-gguf-hpc-task-v1",
        "started_at": now(), "mode": mode, "task": task,
        "expected_requests": len(rows), "pending_at_start": len(pending),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
        "slurm_node": os.environ.get("SLURMD_NODENAME"),
        "server_args": server_args,
        "container_sha256": sha_file(container), "weights_sha256": sha_file(weights),
        "logical_payload_sha256": sha_file(OUTPUT_DIR / "requests.jsonl"),
    }
    atomic_json(run_root / "runtime.json", metadata)
    with (run_root / "server.log").open("a", encoding="utf-8") as server_log:
        process = subprocess.Popen(server_args, stdout=server_log, stderr=subprocess.STDOUT, text=True)
        try:
            wait_ready(port, process)

            def execute(row: dict[str, Any]) -> dict[str, Any]:
                first_attempt = attempts_used.get(row["request_id"], 0) + 1
                last_error = "attempt_limit_exhausted"
                for attempt in range(first_attempt, 3):
                    started = time.monotonic()
                    try:
                        result = post_json(f"http://127.0.0.1:{port}/completion", {
                            "prompt": row["raw_prompt"], "n_predict": row["settings"]["n_predict"],
                            "temperature": row["settings"]["temperature"],
                            "repeat_penalty": row["settings"]["repeat_penalty"],
                            "stop": row["stop"], "stream": False,
                        })
                        text = result.get("content") or ""
                        attempt_record = {
                            "request_id": row["request_id"], "attempt": attempt, "completed_at": now(),
                            "elapsed_seconds": time.monotonic() - started, "status": "success",
                            "http_status": 200, "error": None,
                        }
                        append_jsonl(attempt_path, attempt_record)
                        return {
                            **{key: value for key, value in row.items() if key != "raw_prompt"},
                            "completed_at": attempt_record["completed_at"],
                            "attempt": attempt, "elapsed_seconds": attempt_record["elapsed_seconds"],
                            "response_text": text, "output_tokens": result.get("tokens_predicted"),
                            "stop_type": result.get("stop_type"), "timings": result.get("timings"),
                            "error": None if text.strip() else "empty_response",
                        }
                    except urllib.error.HTTPError as exc:
                        body = exc.read().decode("utf-8", errors="replace")[:2000]
                        transient = exc.code in TRANSIENT_HTTP
                        last_error = f"HTTP {exc.code}: {body}"
                        append_jsonl(attempt_path, {
                            "request_id": row["request_id"], "attempt": attempt, "completed_at": now(),
                            "elapsed_seconds": time.monotonic() - started, "status": "error",
                            "http_status": exc.code, "transient": transient, "error": last_error,
                        })
                        if not transient:
                            break
                    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                        last_error = f"{type(exc).__name__}: {exc}"
                        append_jsonl(attempt_path, {
                            "request_id": row["request_id"], "attempt": attempt, "completed_at": now(),
                            "elapsed_seconds": time.monotonic() - started, "status": "error",
                            "http_status": None, "transient": True, "error": last_error,
                        })
                return {
                    **{key: value for key, value in row.items() if key != "raw_prompt"},
                    "completed_at": now(), "attempt": min(2, max(first_attempt, 1)),
                    "elapsed_seconds": None, "response_text": "", "output_tokens": None,
                    "stop_type": None, "timings": None, "error": last_error,
                }

            with ThreadPoolExecutor(max_workers=runtime["parallel_slots"]) as executor:
                futures = {executor.submit(execute, row): row for row in pending}
                for index, future in enumerate(as_completed(futures), start=1):
                    record = future.result()
                    append_jsonl(result_path, record)
                    print(json.dumps({
                        "task_id": task_id, "progress": f"{index}/{len(pending)}",
                        "request_id": record["request_id"], "language": record["prompt_language"],
                        "output_tokens": record.get("output_tokens"), "error": record.get("error"),
                    }, ensure_ascii=False), flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    latest = {row["request_id"]: row for row in read_jsonl(result_path)}
    metadata.update({
        "finished_at": now(), "result_records": len(latest),
        "wall_elapsed_seconds": time.monotonic() - wall_started,
        "nonempty_responses": sum(bool((row.get("response_text") or "").strip()) for row in latest.values()),
        "results_sha256": sha_file(result_path), "attempts_sha256": sha_file(attempt_path),
        "server_log_sha256": sha_file(run_root / "server.log"),
    })
    atomic_json(run_root / "runtime.json", metadata)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("benchmark", "full"))
    parser.add_argument("--task-id", type=int, default=int(os.environ.get("SLURM_ARRAY_TASK_ID", "0")))
    args = parser.parse_args()
    run(args.mode, args.task_id)


if __name__ == "__main__":
    main()
