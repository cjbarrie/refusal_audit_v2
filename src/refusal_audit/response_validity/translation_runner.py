"""Authorized, resumable literal-English translation for the frozen pilot.

The caller must first record the exact user authorization in the pilot manifest
and must also pass the paid-run flag. This module sends only the frozen fields
declared in ``docs/HUMAN_TRANSLATION_APPROVAL.md``.
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import json
import math
import os
import fcntl
from pathlib import Path
import threading
import time

import pandas as pd
import tiktoken

from .human_pilot import sha_file

MODEL = "openai/gpt-5.6-luna"
PROVIDER = "openai"
INPUT_PRICE = 0.20
OUTPUT_PRICE = 1.20
# Reserve each request's full output allowance at twice the dated list price.
# A much larger multiplier can deadlock an authorized long-response batch even
# when realized spend remains far below its ceiling.
RESERVE_INPUT_PRICE = 0.40
RESERVE_OUTPUT_PRICE = 2.40
MAX_ATTEMPTS = 6


def _manifest_path(output_dir: Path) -> Path:
    """Resolve either the original pilot or a later frozen translation wave."""
    matches = [
        path for path in [output_dir / "pilot_manifest.json", output_dir / "wave_manifest.json"]
        if path.exists()
    ]
    if len(matches) != 1:
        raise RuntimeError("translation directory must contain exactly one recognized manifest")
    return matches[0]

SCHEMA = {
    "name": "literal_response_translation_v1",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "review_id": {"type": "string"},
            "source_hash": {"type": "string"},
            "response_translation_en": {"type": "string"},
            "translation_status": {
                "type": "string", "enum": ["complete", "partial", "unassessable"]
            },
            "uncertain_spans": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "source_span": {"type": "string"},
                        "english_note": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["source_span", "english_note", "reason"],
                },
            },
            "detected_language": {"type": "string"},
            "translator_model": {"type": "string"},
            "translation_prompt_hash": {"type": "string"},
        },
        "required": [
            "review_id", "source_hash", "response_translation_en",
            "translation_status", "uncertain_spans", "detected_language",
            "translator_model", "translation_prompt_hash",
        ],
    },
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def validate_translation(label: dict, request: dict, prompt_hash: str) -> dict:
    expected = {
        "review_id": request["review_id"],
        "source_hash": request["source_hash"],
        "translation_prompt_hash": prompt_hash,
        "translator_model": MODEL,
    }
    for field, value in expected.items():
        if label.get(field) != value:
            raise ValueError(f"{field} differs from frozen request")
    if label.get("translation_status") not in {"complete", "partial", "unassessable"}:
        raise ValueError("invalid translation_status")
    if not isinstance(label.get("response_translation_en"), str):
        raise ValueError("response_translation_en must be text")
    if not isinstance(label.get("uncertain_spans"), list):
        raise ValueError("uncertain_spans must be an array")
    for span in label["uncertain_spans"]:
        if set(span) != {"source_span", "english_note", "reason"}:
            raise ValueError("invalid uncertain-span schema")
        if not all(isinstance(span[x], str) for x in span):
            raise ValueError("uncertain-span values must be text")
    if not isinstance(label.get("detected_language"), str):
        raise ValueError("detected_language must be text")
    return label


def _usage_cost(usage: dict) -> float:
    reported = usage.get("cost")
    # OpenRouter reports cost=0 for BYOK calls but exposes the actual upstream
    # charge. Count that charge so BYOK routing cannot bypass the hard ceiling.
    details = usage.get("cost_details") or {}
    upstream = details.get("upstream_inference_cost")
    if usage.get("is_byok") and upstream is not None:
        return float(upstream)
    if reported is not None and float(reported) > 0:
        return float(reported)
    if upstream is not None:
        return float(upstream)
    return (
        float(usage.get("prompt_tokens", 0)) * INPUT_PRICE
        + float(usage.get("completion_tokens", 0)) * OUTPUT_PRICE
    ) / 1_000_000


def _record_cost(record: dict) -> float:
    """Recover spend from immutable records, including BYOK cost details."""
    stored = float(record.get("incremental_provider_cost", 0) or 0)
    return max(stored, _usage_cost(record.get("usage") or {}))


def _max_output_tokens(request: dict, encoding) -> int:
    source = len(encoding.encode(request["response_text"]))
    # Literal English plus JSON escaping and uncertain-span metadata can be
    # much longer than the source tokenization, especially for non-Latin text.
    # The first authorized pass showed exact-limit truncation at the former
    # 1.5x/10k cap on three rows; 3x + 1k prevents semantic repair while giving
    # the identical prompt room to close its structured response.
    return min(40_000, max(2_000, math.ceil(source * 6 + 2_000)))


def _reservation(request: dict, prompt: str, encoding) -> tuple[float, int]:
    input_tokens = len(encoding.encode(prompt)) + len(
        encoding.encode(json.dumps(request, ensure_ascii=False, sort_keys=True))
    )
    output_tokens = _max_output_tokens(request, encoding)
    cost = (
        input_tokens * RESERVE_INPUT_PRICE + output_tokens * RESERVE_OUTPUT_PRICE
    ) / 1_000_000
    return cost, output_tokens


def record_authorization(
    output_dir: Path,
    payload_sha: str,
    prompt_sha: str,
    model: str,
    ceiling: float,
    confirmed: bool,
) -> dict:
    if not confirmed:
        raise RuntimeError("recording authorization requires --confirm-user-authorization")
    manifest_path = _manifest_path(output_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = output_dir / "translation_requests.jsonl"
    if payload_sha != sha_file(payload) or payload_sha != manifest["artifact_sha256"][payload.name]:
        raise ValueError("authorized payload hash does not match frozen payload")
    if prompt_sha != manifest["translation_prompt_sha256"]:
        raise ValueError("authorized prompt hash does not match frozen prompt")
    if model != MODEL or not 0 < float(ceiling) <= 100:
        raise ValueError("authorization requires the frozen model and a positive bounded ceiling")
    manifest["translation_authorization"] = {
        "recorded_at": now(),
        "payload_sha256": payload_sha,
        "prompt_sha256": prompt_sha,
        "model": model,
        "provider": "OpenRouter",
        "provider_allowlist": [PROVIDER],
        "allow_fallbacks": False,
        "purpose": "literal English translation only",
        "cost_ceiling_usd": float(ceiling),
        "user_authorized": True,
    }
    manifest["translation_authorized"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest["translation_authorization"]


def record_chunked_fallback_authorization(
    output_dir: Path,
    review_ids: list[str],
    ceiling: float,
    confirmed: bool,
) -> dict:
    """Bind a second user authorization to the exact exhausted source rows."""
    if not confirmed:
        raise RuntimeError(
            "recording chunk authorization requires --confirm-user-authorization"
        )
    manifest_path = _manifest_path(output_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    auth = manifest.get("translation_authorization", {})
    if not (
        auth.get("user_authorized") is True
        and auth.get("model") == MODEL
        and auth.get("provider_allowlist") == [PROVIDER]
        and auth.get("allow_fallbacks") is False
        and float(auth.get("cost_ceiling_usd", -1)) == float(ceiling)
    ):
        raise RuntimeError("original translation authorization is absent or different")
    requests = read_jsonl(output_dir / "translation_requests.jsonl")
    requested = sorted(set(map(str, review_ids)))
    if len(requested) != len(review_ids):
        raise ValueError("chunk authorization contains duplicate review IDs")
    request_ids = {str(row["review_id"]) for row in requests}
    if not set(requested).issubset(request_ids):
        raise ValueError("chunk authorization includes a non-frozen review ID")
    raw = read_jsonl(output_dir / "translations_raw.jsonl")
    completed = {
        str(row["review_id"]) for row in raw if row.get("status") == "ok"
    }
    exhausted = {
        review_id for review_id in requested
        if review_id not in completed
        and sum(
            str(row.get("review_id")) == review_id
            and row.get("status") == "error"
            for row in raw
        ) >= MAX_ATTEMPTS
    }
    if exhausted != set(requested):
        raise RuntimeError("every chunk-authorized row must be incomplete and exhausted")
    record = {
        "recorded_at": now(),
        "review_ids": requested,
        "method": "deterministic lossless chunking of the frozen response_text",
        "model": MODEL,
        "provider": "OpenRouter",
        "provider_allowlist": [PROVIDER],
        "allow_fallbacks": False,
        "reasoning_enabled": False,
        "prompt_sha256": auth["prompt_sha256"],
        "cumulative_cost_ceiling_usd": float(ceiling),
        "user_authorized": True,
    }
    manifest["chunked_fallback_authorization"] = record
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return record


def _call(client, request: dict, prompt: str, prompt_hash: str, max_tokens: int) -> dict:
    started = time.time()
    user_payload = {
        key: request[key]
        for key in [
            "review_id", "source_hash", "translation_prompt_hash",
            "prompt_language", "prompt_text_en", "prompt_text", "response_text",
        ]
    }
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        temperature=0,
        max_tokens=max_tokens,
        response_format={"type": "json_schema", "json_schema": SCHEMA},
        extra_body={
            "reasoning": {"enabled": False},
            "provider": {"only": [PROVIDER], "allow_fallbacks": False},
        },
        timeout=180,
    )
    usage = response.usage.model_dump() if response.usage else {}
    cost = _usage_cost(usage)
    try:
        raw_label = json.loads(response.choices[0].message.content)
        model_output_metadata = {
            key: raw_label.get(key)
            for key in ["review_id", "source_hash", "translator_model", "translation_prompt_hash"]
        }
        # These four fields are immutable request metadata, not translation
        # judgments. Normalize them deterministically while preserving what the
        # model emitted for audit, so a harmless model-name spelling does not
        # trigger a second paid translation.
        raw_label.update({
            "review_id": request["review_id"],
            "source_hash": request["source_hash"],
            "translator_model": MODEL,
            "translation_prompt_hash": prompt_hash,
        })
        label = validate_translation(raw_label, request, prompt_hash)
    except Exception as exc:
        return {
            "review_id": request["review_id"],
            "source_hash": request["source_hash"],
            "translation_prompt_hash": prompt_hash,
            "translator_model": MODEL,
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc)[:1000],
            "provider_response_id": response.id,
            "provider_model": response.model,
            "usage": usage,
            "incremental_provider_cost": cost,
            "elapsed_seconds": time.time() - started,
            "created_at": now(),
        }
    return {
        **label,
        "model_output_metadata": model_output_metadata,
        "status": "ok",
        "provider_response_id": response.id,
        "provider_model": response.model,
        "usage": usage,
        "incremental_provider_cost": cost,
        "elapsed_seconds": time.time() - started,
        "created_at": now(),
    }


def run_translations(
    root: Path,
    output_dir: Path,
    prompt_path: Path,
    workers: int,
    ceiling: float,
    authorized: bool,
) -> dict:
    # An advisory OS lock is released automatically if the process exits or is
    # interrupted. It prevents two resumptions from paying for the same row.
    lock_handle = (output_dir / ".translation_run.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_handle.close()
        raise RuntimeError("another translation process already holds the run lock") from exc
    if not authorized:
        raise RuntimeError("paid translation requires --authorize-paid-translation")
    manifest_path = _manifest_path(output_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    auth = manifest.get("translation_authorization", {})
    payload_path = output_dir / "translation_requests.jsonl"
    payload_sha = sha_file(payload_path)
    prompt_sha = sha_file(prompt_path)
    expected_auth = (
        auth.get("user_authorized") is True
        and auth.get("payload_sha256") == payload_sha
        and auth.get("prompt_sha256") == prompt_sha
        and auth.get("model") == MODEL
        and float(auth.get("cost_ceiling_usd", -1)) == float(ceiling)
    )
    if not expected_auth:
        raise RuntimeError("manifest does not contain the exact paid-translation authorization")
    if payload_sha != manifest["artifact_sha256"].get(payload_path.name):
        raise RuntimeError("payload hash differs from the frozen design artifact")
    if prompt_sha != manifest["translation_prompt_sha256"]:
        raise RuntimeError("translation prompt differs from the frozen design artifact")

    # Record that external transmission has begun before opening a client.  A
    # partial or interrupted run must never remain described as network-free.
    if not manifest.get("network_call_made"):
        manifest["network_call_made"] = True
        manifest["translation_started_at"] = now()
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    scripts = root / "scripts"
    if str(scripts) not in os.sys.path:
        os.sys.path.insert(0, str(scripts))
    from env_utils import get_openrouter_client

    client = get_openrouter_client()
    requests = read_jsonl(payload_path)
    raw_path = output_dir / "translations_raw.jsonl"
    existing = read_jsonl(raw_path) if raw_path.exists() else []
    completed = {
        row["review_id"]: row for row in existing
        if row.get("status") == "ok"
        and row.get("source_hash")
        and row.get("translation_prompt_hash") == prompt_sha
    }
    attempts = {}
    for row in existing:
        attempts[row.get("review_id")] = attempts.get(row.get("review_id"), 0) + 1
    actual_cost = sum(_record_cost(row) for row in existing)
    if actual_cost >= ceiling:
        raise RuntimeError("completed provider cost already reaches the authorized ceiling")

    prompt = prompt_path.read_text(encoding="utf-8")
    encoding = tiktoken.get_encoding("o200k_base")
    queue = [row for row in requests if row["review_id"] not in completed]
    lock = threading.Lock()

    def append(record: dict) -> None:
        with lock, raw_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()

    futures = {}
    reserved = 0.0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while queue or futures:
            while queue and len(futures) < workers:
                request = queue.pop(0)
                reservation, max_tokens = _reservation(request, prompt, encoding)
                if actual_cost + reserved + reservation > ceiling:
                    raise RuntimeError("conservative in-flight reservation would cross cost ceiling")
                reserved += reservation
                future = pool.submit(_call, client, request, prompt, prompt_sha, max_tokens)
                futures[future] = (request, reservation)
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                request, reservation = futures.pop(future)
                reserved -= reservation
                try:
                    record = future.result()
                except Exception as exc:
                    record = {
                        "review_id": request["review_id"],
                        "source_hash": request["source_hash"],
                        "translation_prompt_hash": prompt_sha,
                        "translator_model": MODEL,
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:1000],
                        "incremental_provider_cost": 0.0,
                        "created_at": now(),
                    }
                append(record)
                actual_cost += _record_cost(record)
                attempts[request["review_id"]] = attempts.get(request["review_id"], 0) + 1
                if actual_cost > ceiling:
                    raise RuntimeError("provider-reported cost crossed the authorized ceiling")
                if record["status"] == "ok":
                    completed[request["review_id"]] = record
                elif attempts[request["review_id"]] < MAX_ATTEMPTS:
                    queue.append(request)

    missing = [row["review_id"] for row in requests if row["review_id"] not in completed]
    if missing:
        raise RuntimeError(f"translation incomplete after retries: {len(missing)} rows")
    assembled_path = output_dir / "translations_assembled.jsonl"
    allowed = [
        "review_id", "source_hash", "response_translation_en", "translation_status",
        "uncertain_spans", "detected_language", "translator_model",
        "translation_prompt_hash",
    ]
    with assembled_path.open("w", encoding="utf-8") as handle:
        for request in requests:
            record = completed[request["review_id"]]
            handle.write(json.dumps({key: record[key] for key in allowed}, ensure_ascii=False) + "\n")
    summary = {
        "completed_at": now(),
        "n": len(completed),
        "model": MODEL,
        "provider_allowlist": [PROVIDER],
        "allow_fallbacks": False,
        "payload_sha256": payload_sha,
        "prompt_sha256": prompt_sha,
        "assembled_sha256": sha_file(assembled_path),
        "provider_cost_usd": actual_cost,
        "authorized_ceiling_usd": ceiling,
        "raw_records": len(read_jsonl(raw_path)),
    }
    (output_dir / "translation_run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    manifest["translation_sent"] = True
    manifest["translation_run"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary


def finalize_ceiling_guarded_loops(output_dir: Path, ceiling: float) -> dict:
    """Locally mark unresolved extreme loops unassessable after the hard cap.

    This makes no provider call and creates no behavioral validity label. It is
    allowed only when at least 95% of the authorized ceiling is already spent
    and every unresolved response is a deterministic repetition loop.
    """
    manifest_path = _manifest_path(output_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    auth = manifest.get("translation_authorization", {})
    if not auth.get("user_authorized") or float(auth.get("cost_ceiling_usd", -1)) != float(ceiling):
        raise RuntimeError("local loop finalization requires the exact recorded ceiling")
    requests = read_jsonl(output_dir / "translation_requests.jsonl")
    raw_path = output_dir / "translations_raw.jsonl"
    raw = read_jsonl(raw_path)
    actual_cost = sum(_record_cost(row) for row in raw)
    if actual_cost < .95 * ceiling or actual_cost >= ceiling:
        raise RuntimeError("local loop finalization is permitted only at 95-100% of the ceiling")
    completed = {row["review_id"] for row in raw if row.get("status") == "ok"}
    missing = [row for row in requests if row["review_id"] not in completed]
    if not missing:
        return {"locally_finalized_rows": 0, "provider_cost_usd": actual_cost}
    design = pd.read_parquet(
        output_dir / "wave_design.parquet",
        columns=["review_id", "diag_repetition_loop", "diag_repeated_trigram_ratio"],
    ).set_index("review_id")
    ids = [row["review_id"] for row in missing]
    checks = design.loc[ids]
    if not (
        checks.diag_repetition_loop.fillna(False).all()
        and checks.diag_repeated_trigram_ratio.fillna(0).ge(.90).all()
    ):
        raise RuntimeError("every locally finalized row must be an independently detected extreme loop")
    with raw_path.open("a", encoding="utf-8") as handle:
        for request in missing:
            record = {
                "review_id": request["review_id"],
                "source_hash": request["source_hash"],
                "response_translation_en": (
                    "[Literal English translation unavailable after the authorized cost ceiling; "
                    "inspect the complete original repetition-loop response.]"
                ),
                "translation_status": "unassessable",
                "uncertain_spans": [{
                    "source_span": request["response_text"],
                    "english_note": "Complete source preserved; no translation claimed.",
                    "reason": "authorized cost ceiling reached during extreme repetition-loop fallback",
                }],
                "detected_language": request["prompt_language"],
                "translator_model": MODEL,
                "translation_prompt_hash": request["translation_prompt_hash"],
                "status": "ok",
                "local_unassessable_no_provider_call": True,
                "provider_response_id": None,
                "provider_model": None,
                "usage": {},
                "incremental_provider_cost": 0.0,
                "created_at": now(),
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    result = {
        "locally_finalized_rows": len(missing),
        "review_ids": ids,
        "eligibility_rule": "diag_repetition_loop and repeated_trigram_ratio>=0.90",
        "behavioral_label_assigned": False,
        "provider_call_made": False,
        "provider_cost_usd": actual_cost,
    }
    (output_dir / "ceiling_loop_finalization.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    manifest["ceiling_loop_finalization"] = result
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


def _text_chunks(text: str, target_chars: int = 3_000) -> list[str]:
    """Split losslessly at newlines where possible, never altering source text."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + target_chars)
        if end < len(text):
            newline = text.rfind("\n", start + target_chars // 2, end)
            if newline > start:
                end = newline + 1
        chunks.append(text[start:end])
        start = end
    if "".join(chunks) != text:
        raise AssertionError("chunking altered source text")
    return chunks


def run_chunked_fallback(
    root: Path,
    output_dir: Path,
    prompt_path: Path,
    review_id: str,
    ceiling: float,
    authorized: bool,
) -> dict:
    """Translate one exhausted long row losslessly in deterministic chunks."""
    if not authorized:
        raise RuntimeError("chunked fallback requires the exact paid authorization")
    lock_handle = (output_dir / ".translation_run.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_handle.close()
        raise RuntimeError("another translation process already holds the run lock") from exc
    manifest = json.loads(_manifest_path(output_dir).read_text(encoding="utf-8"))
    auth = manifest.get("translation_authorization", {})
    chunk_auth = manifest.get("chunked_fallback_authorization", {})
    payload_path = output_dir / "translation_requests.jsonl"
    prompt_sha = sha_file(prompt_path)
    if not (
        auth.get("user_authorized") is True
        and auth.get("payload_sha256") == sha_file(payload_path)
        and auth.get("prompt_sha256") == prompt_sha
        and auth.get("model") == MODEL
        and float(auth.get("cost_ceiling_usd", -1)) == float(ceiling)
        and chunk_auth.get("user_authorized") is True
        and review_id in chunk_auth.get("review_ids", [])
        and chunk_auth.get("model") == MODEL
        and chunk_auth.get("provider_allowlist") == [PROVIDER]
        and chunk_auth.get("allow_fallbacks") is False
        and chunk_auth.get("reasoning_enabled") is False
        and chunk_auth.get("prompt_sha256") == prompt_sha
        and float(chunk_auth.get("cumulative_cost_ceiling_usd", -1))
        == float(ceiling)
    ):
        raise RuntimeError("manifest authorization does not match chunked fallback")
    requests = read_jsonl(payload_path)
    matches = [row for row in requests if row["review_id"] == review_id]
    if len(matches) != 1:
        raise ValueError("chunk fallback review_id must identify one frozen row")
    request = matches[0]
    raw_path = output_dir / "translations_raw.jsonl"
    raw = read_jsonl(raw_path) if raw_path.exists() else []
    if any(row.get("review_id") == review_id and row.get("status") == "ok" for row in raw):
        raise RuntimeError("row already has a successful full translation")
    actual_cost = sum(_record_cost(row) for row in raw)
    source_text = request["response_text"]
    loop_aware_partial = False
    omitted_loop_span = ""
    design_path = output_dir / "wave_design.parquet"
    if design_path.exists():
        design = pd.read_parquet(design_path, columns=["review_id", "diag_repetition_loop"])
        matches = design.loc[design.review_id.eq(review_id)]
        loop_aware_partial = (
            len(matches) == 1
            and bool(matches.iloc[0].diag_repetition_loop)
            and len(source_text) > 6_000
        )
    if loop_aware_partial:
        # A literal rendering of thousands of repeated loop tokens repeatedly
        # broke structured JSON and adds no semantic coverage. Translate the
        # exact leading/trailing spans and disclose the exact omitted middle as
        # untranslated. The complete original remains in the human packet.
        edge = 1_500
        chunks = [source_text[:edge], source_text[-edge:]]
        omitted_loop_span = source_text[edge:-edge]
    else:
        chunks = _text_chunks(source_text)
    prompt = prompt_path.read_text(encoding="utf-8")
    encoding = tiktoken.get_encoding("o200k_base")
    scripts = root / "scripts"
    if str(scripts) not in os.sys.path:
        os.sys.path.insert(0, str(scripts))
    from env_utils import get_openrouter_client
    client = get_openrouter_client()

    def translate_piece(piece: str, label: int | str) -> dict:
        nonlocal actual_cost
        chunk_request = dict(request, response_text=piece)
        chunk_sha = __import__("hashlib").sha256(piece.encode("utf-8")).hexdigest()
        prior = [
            row for row in raw
            if row.get("review_id") == review_id
            and row.get("status") in {"chunk_ok", "chunk_unassessable"}
            and row.get("chunk_index") == label
            and row.get("chunk_source_sha256") == chunk_sha
        ]
        if prior:
            return prior[-1]
        prior_errors = [
            row for row in raw
            if row.get("review_id") == review_id
            and row.get("status") == "chunk_error"
            and row.get("chunk_index") == label
            and row.get("chunk_source_sha256") == chunk_sha
        ]
        # Do not repay for a parent chunk already known to fail. Subdivide it
        # immediately. At the terminal size, preserve the exact untranslated
        # source span and mark the assembled translation partial.
        if prior_errors:
            if len(piece) <= 100:
                terminal = {
                    "review_id": review_id,
                    "source_hash": request["source_hash"],
                    "response_translation_en": "[Untranslated source span; inspect original response.]",
                    "translation_status": "partial",
                    "uncertain_spans": [{
                        "source_span": piece,
                        "english_note": "No valid structured translation after recursive subdivision.",
                        "reason": "translator structured-output failure",
                    }],
                    "detected_language": request["prompt_language"],
                    "translator_model": MODEL,
                    "translation_prompt_hash": prompt_sha,
                    "status": "chunk_unassessable",
                    "chunk_index": label,
                    "chunk_count": len(chunks),
                    "chunk_source_sha256": chunk_sha,
                    "usage": {},
                    "incremental_provider_cost": 0.0,
                    "created_at": now(),
                }
                with raw_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(terminal, ensure_ascii=False) + "\n")
                raw.append(terminal)
                return terminal
            midpoint = len(piece) // 2
            left = translate_piece(piece[:midpoint], f"{label}.a")
            right = translate_piece(piece[midpoint:], f"{label}.b")
            return {
                "response_translation_en": left["response_translation_en"] + "\n" + right["response_translation_en"],
                "translation_status": (
                    "complete" if {left["translation_status"], right["translation_status"]} == {"complete"}
                    else "partial"
                ),
                "uncertain_spans": left["uncertain_spans"] + right["uncertain_spans"],
                "detected_language": "; ".join(dict.fromkeys([left["detected_language"], right["detected_language"]])),
                "chunk_index": label,
            }
        source_tokens = len(encoding.encode(piece))
        max_tokens = min(30_000, max(5_000, source_tokens * 12 + 4_000))
        input_tokens = len(encoding.encode(prompt)) + len(
            encoding.encode(json.dumps(chunk_request, ensure_ascii=False, sort_keys=True))
        )
        reservation = (
            input_tokens * RESERVE_INPUT_PRICE + max_tokens * RESERVE_OUTPUT_PRICE
        ) / 1_000_000
        if actual_cost + reservation > ceiling:
            raise RuntimeError("chunk reservation would cross cost ceiling")
        candidate = _call(client, chunk_request, prompt, prompt_sha, max_tokens)
        candidate["status"] = "chunk_ok" if candidate["status"] == "ok" else "chunk_error"
        candidate["chunk_index"] = label
        candidate["chunk_count"] = len(chunks)
        candidate["chunk_source_sha256"] = chunk_sha
        with raw_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
        raw.append(candidate)
        actual_cost += _record_cost(candidate)
        if candidate["status"] == "chunk_ok":
            return candidate
        if len(piece) <= 100:
            # The next resumable pass converts this recorded terminal failure
            # to an explicit untranslated span without another provider call.
            return translate_piece(piece, label)
        midpoint = len(piece) // 2
        left = translate_piece(piece[:midpoint], f"{label}.a")
        right = translate_piece(piece[midpoint:], f"{label}.b")
        return {
            "response_translation_en": left["response_translation_en"] + "\n" + right["response_translation_en"],
            "translation_status": (
                "complete" if {left["translation_status"], right["translation_status"]} == {"complete"}
                else "partial"
            ),
            "uncertain_spans": left["uncertain_spans"] + right["uncertain_spans"],
            "detected_language": "; ".join(dict.fromkeys([left["detected_language"], right["detected_language"]])),
            "chunk_index": label,
        }

    chunk_results = [translate_piece(chunk, index) for index, chunk in enumerate(chunks, 1)]

    combined_uncertain = []
    for result in chunk_results:
        for span in result["uncertain_spans"]:
            combined_uncertain.append({
                "source_span": f"[chunk {result['chunk_index']}] {span['source_span']}",
                "english_note": span["english_note"],
                "reason": span["reason"],
            })
    if loop_aware_partial:
        combined_uncertain.append({
            "source_span": omitted_loop_span,
            "english_note": "Middle span omitted from literal translation because deterministic diagnostics identify an extreme repetition loop; inspect the preserved original response.",
            "reason": "loop-aware partial translation",
        })
    statuses = {row["translation_status"] for row in chunk_results}
    translated_parts = [row["response_translation_en"] for row in chunk_results]
    if loop_aware_partial:
        translated_parts.insert(1, "[Repeated middle source span omitted; inspect original response.]")
    combined = {
        "review_id": review_id,
        "source_hash": request["source_hash"],
        "response_translation_en": "\n\n".join(translated_parts),
        "translation_status": (
            "complete" if statuses == {"complete"} and not loop_aware_partial else "partial"
        ),
        "uncertain_spans": combined_uncertain,
        "detected_language": "; ".join(dict.fromkeys(row["detected_language"] for row in chunk_results)),
        "translator_model": MODEL,
        "translation_prompt_hash": prompt_sha,
        "status": "ok",
        "chunked_fallback": True,
        "loop_aware_partial": loop_aware_partial,
        "omitted_loop_characters": len(omitted_loop_span),
        "chunk_count": len(chunks),
        "chunk_source_recombined_sha256": __import__("hashlib").sha256(
            source_text.encode("utf-8")
        ).hexdigest(),
        "usage": {},
        "incremental_provider_cost": 0.0,
        "created_at": now(),
    }
    with raw_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(combined, ensure_ascii=False) + "\n")
    return {
        "review_id": review_id,
        "chunks": len(chunks),
        # Adaptive parent objects aggregate already-costed child calls and
        # therefore correctly carry no additional provider cost.
        "chunk_cost_usd": sum(float(row.get("incremental_provider_cost", 0) or 0) for row in chunk_results),
        "cumulative_cost_usd": actual_cost,
    }
