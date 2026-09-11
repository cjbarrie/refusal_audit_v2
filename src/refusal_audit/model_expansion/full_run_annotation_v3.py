"""Freeze and cost Luna v2.4 annotations for completed v3 subject models.

The batch contains only complete, hash-validated generation stages. Subject
model and generation metadata are retained in the local index but blinded from
Luna's messages. This module makes no provider calls during preparation/costing.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import tiktoken

from refusal_audit.response_validity.human_pilot import sha_file
from refusal_audit.response_validity.luna_v23_repair import _schema, _user
from refusal_audit.response_validity.luna_v24_evaluation import (
    INPUT_PRICE, MAX_ATTEMPTS, MAX_OUTPUT_TOKENS, MODEL, OUTPUT_PRICE,
    PLANNING_OUTPUT_TOKENS, PRICING_SOURCE, PRICING_VERIFIED_AT, PROVIDER,
    _system_v24, run_luna_v24,
)

from .openrouter_pilot import read_jsonl, sha_object, write_jsonl


DEFAULT_DIR = Path("annotations/model_expansion_v3/luna_v2_4_completed_batch1")
NEXT_DIR = Path("annotations/model_expansion_v3/luna_v2_4_completed_batch2")
KIMI_DIR = Path("annotations/model_expansion_v3/luna_v2_4_kimi_batch3")
CODEBOOK = Path("config/response_validity_decomposed_v2_4.json")
BASE_ROSTER = Path("config/model_rosters/multirouter_expansion_v2.json")
ADOPTED_PROMPT = Path("annotations/response_validity_v2_4/wall_to_wall_luna_v1/prompt.txt")
ADOPTED_SCHEMA = Path("annotations/response_validity_v2_4/wall_to_wall_luna_v1/response_schema.json")
EXPECTED_PER_MODEL = 12_480
EXPECTED_N = 37_440
# Two completed v2.4 runs give nearly identical realized per-response costs.
# Their immutable run summaries are documented in the technical pipeline.
PRIOR_WALL_COST_PER_RESPONSE = 63.27810359000008 / 134_664
PRIOR_PILOT_COST_PER_RESPONSE = 0.7212165099999992 / 1_600
BATCH1_SOURCES = (
    ("ministral-14b", Path("annotations/model_expansion_v3/full_run_v1/stage_01_ministral-14b"), 12_480, 0),
    ("nova-lite", Path("annotations/model_expansion_v3/full_run_v1/stage_02_nova-lite"), 12_480, 0),
    ("llama-4-scout", Path("annotations/model_expansion_v3/full_run_v1/stage_03_llama-4-scout"), 12_480, 0),
)
BATCH2_SOURCES = (
    ("hunyuan-a13b", Path("annotations/model_expansion_v3/hunyuan_all_languages_v3_1/stage_04_hunyuan-a13b"), 12_480, 0),
    ("glm-4.7-flash", Path("annotations/model_expansion_v3/full_run_v1/stage_05_glm-4.7-flash"), 12_480, 0),
    ("gemini-2.5-flash-lite", Path("annotations/model_expansion_v3/full_run_v1/stage_06_gemini-2.5-flash-lite"), 12_479, 1),
)
BATCH3_SOURCES = (
    ("kimi-k2.5", Path("annotations/model_expansion_v3/full_run_v1/stage_07_kimi-k2.5"), 12_480, 0),
)
SOURCES = BATCH1_SOURCES
BATCH2_EXPECTED_N = 37_439
BATCH3_EXPECTED_N = 12_480


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_sources(
    root: Path, sources=BATCH1_SOURCES, expected_n: int = EXPECTED_N
) -> tuple[pd.DataFrame, dict, list[dict]]:
    rows = []
    hashes = {}
    missingness = []
    for expected_model, relative, expected_completed, expected_incomplete in sources:
        run_dir = root / relative
        summary_path = run_dir / "run_summary.json"
        results_path = run_dir / "results.jsonl"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if not (
            summary.get("model") == expected_model
            and summary.get("n_completed") == expected_completed
            and summary.get("n_incomplete") == expected_incomplete
            and summary.get("results_sha256") == sha_file(results_path)
        ):
            raise ValueError(f"generation source is incomplete or hash-invalid: {expected_model}")
        part = read_jsonl(results_path)
        if len(part) != expected_completed:
            raise ValueError(f"wrong source row count: {expected_model}")
        if any(row.get("model") != expected_model for row in part):
            raise ValueError(f"mixed subject models in source: {expected_model}")
        rows.extend(part)
        hashes[f"{expected_model}_run_summary"] = sha_file(summary_path)
        hashes[f"{expected_model}_results"] = sha_file(results_path)
        if expected_incomplete:
            attempt_rows = read_jsonl(run_dir / "attempts.jsonl")
            complete_ids = {
                row["provider_request_id"] for row in attempt_rows
                if row.get("status") == "complete"
            }
            by_id = {}
            for row in attempt_rows:
                by_id.setdefault(row["provider_request_id"], []).append(row)
            absent = [records for request_id, records in by_id.items() if request_id not in complete_ids]
            if len(absent) != expected_incomplete:
                raise ValueError(f"missing-response reconciliation failed: {expected_model}")
            for records in absent:
                last = records[-1]
                missingness.append({
                    "model": expected_model,
                    "prompt_id": last["prompt_id"],
                    "prompt_language": last["prompt_language"],
                    "provider_request_id": last["provider_request_id"],
                    "attempts": len(records),
                    "error_types": sorted({r.get("error_type") for r in records}),
                    "last_error": last.get("error"),
                    "classification": "provider_level_missing_response",
                })
    frame = pd.DataFrame(rows)
    key = ["prompt_id", "prompt_language", "model"]
    if len(frame) != expected_n or frame.duplicated(key).any():
        raise ValueError(f"batch is not {expected_n:,} unique response keys")
    if frame.response_text.isna().any() or frame.response_text.str.strip().eq("").any():
        raise ValueError("batch contains empty responses")
    return frame, hashes, missingness


def _load_prompt_maps(root: Path) -> tuple[dict, dict]:
    roster_path = root / BASE_ROSTER
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    maps = {}
    hashes = {"base_roster": sha_file(roster_path)}
    for language, spec in roster["design"]["prompt_files"].items():
        path = root / spec["path"]
        if sha_file(path) != spec["sha256"]:
            raise ValueError(f"prompt hash mismatch for {language}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        maps[language] = {row["id"]: row for row in raw["prompts"]}
        if len(maps[language]) != 2496:
            raise ValueError(f"prompt count mismatch for {language}")
        hashes[f"prompt_{language}"] = spec["sha256"]
    return maps, hashes


def prepare_completed_batch_annotations(
    root: Path, output_dir: Path | None = None, *, sources=BATCH1_SOURCES,
    expected_n: int = EXPECTED_N,
    version: str = "openrouter-expansion-v3-luna-v2.4-completed-batch1",
    scientific_role: str = "uniform blinded v2.4 annotation of three completed expansion models",
) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    source, source_hashes, missingness = _load_sources(root, sources, expected_n)
    prompts, prompt_hashes = _load_prompt_maps(root)
    codebook_path = root / CODEBOOK
    input_hashes = {
        **source_hashes, **prompt_hashes,
        "v2_4_codebook": sha_file(codebook_path),
        "adopted_v2_4_prompt": sha_file(root / ADOPTED_PROMPT),
        "adopted_v2_4_schema": sha_file(root / ADOPTED_SCHEMA),
    }
    manifest_path = output_dir / "manifest.json"
    artifacts = {
        "response_index.parquet": output_dir / "response_index.parquet",
        "provider_requests.jsonl": output_dir / "provider_requests.jsonl",
        "prompt.txt": output_dir / "prompt.txt",
        "response_schema.json": output_dir / "response_schema.json",
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen batch annotations no longer match inputs")
        for name, expected in manifest["artifact_sha256"].items():
            if sha_file(artifacts[name]) != expected:
                raise ValueError(f"frozen annotation artifact changed: {name}")
        return manifest

    codebook = json.loads(codebook_path.read_text(encoding="utf-8"))
    system = _system_v24(codebook)
    schema = _schema()
    if hashlib.sha256(system.encode("utf-8")).hexdigest() != input_hashes["adopted_v2_4_prompt"]:
        raise ValueError("constructed v2.4 prompt differs from adopted prompt")
    schema_bytes = json.dumps(schema, indent=2).encode("utf-8")
    if hashlib.sha256(schema_bytes).hexdigest() != input_hashes["adopted_v2_4_schema"]:
        raise ValueError("constructed v2.4 schema differs from adopted schema")
    encoder = tiktoken.get_encoding("o200k_base")
    requests = []
    index_rows = []
    for row in source.sort_values(
        ["model", "prompt_language", "prompt_id"], kind="mergesort"
    ).to_dict("records"):
        language = row["prompt_language"]
        prompt_id = row["prompt_id"]
        annotation_row = {
            "prompt_language": language,
            "prompt_text_en": prompts["en"][prompt_id]["text"],
            "prompt_text": prompts[language][prompt_id]["text"],
            "response_text": row["response_text"],
        }
        source_sha = sha_object(annotation_row)
        logical_id = sha_object({
            "response_key": [prompt_id, language, row["model"]],
            "source_sha256": source_sha,
            "version": version,
        })[:24]
        user = _user(annotation_row, "source_response_only")
        request = {
            "logical_request_id": logical_id,
            "provider_request_id": sha_object({
                "logical_request_id": logical_id, "model_id": MODEL,
            })[:24],
            "audit_response_id": logical_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_schema": schema,
            "estimated_input_tokens": len(encoder.encode(
                system + "\n" + user + "\n" + json.dumps(schema, sort_keys=True)
            )),
            "model_id": MODEL,
            "provider": {"only": [PROVIDER], "allow_fallbacks": False},
            "reasoning": {"enabled": False, "exclude": True},
            "temperature": 0,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        }
        requests.append(request)
        index_rows.append({
            "audit_response_id": logical_id,
            "provider_request_id": request["provider_request_id"],
            "source_sha256": source_sha,
            "prompt_id": prompt_id,
            "prompt_language": language,
            "subject_model": row["model"],
            "subject_model_id": row["model_id_requested"],
            "subject_provider_tag": row["provider_tag_requested"],
            "generation_provider_request_id": row["provider_request_id"],
            "generation_response_sha256": row["response_text_sha256"],
            "estimated_input_tokens": request["estimated_input_tokens"],
        })
    if len(requests) != expected_n or len({r["provider_request_id"] for r in requests}) != expected_n:
        raise ValueError(f"annotation payload is not {expected_n:,} unique requests")
    messages = json.dumps([r["messages"] for r in requests], ensure_ascii=False)
    for forbidden in ("subject_model", "provider_tag_requested", "pilot_band"):
        if forbidden in messages:
            raise ValueError(f"source metadata leaked into Luna messages: {forbidden}")

    output_dir.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(index_rows).to_parquet(artifacts["response_index.parquet"], index=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    artifacts["prompt.txt"].write_text(system, encoding="utf-8")
    artifacts["response_schema.json"].write_bytes(schema_bytes)
    manifest = {
        "version": version,
        "created_at": _now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": scientific_role,
        "subject_models": [name for name, *_ in sources],
        "n_requests": expected_n,
        "source_missingness": missingness,
        "input_mode": "source_response_only",
        "translation_used": False,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_attempts": MAX_ATTEMPTS,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "input_sha256": input_hashes,
        "artifact_sha256": {name: sha_file(path) for name, path in artifacts.items()},
        "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def prepare_next_batch_annotations(root: Path, output_dir: Path | None = None) -> dict:
    """Freeze returned Hunyuan, GLM and Gemini responses; never fabricate Gemini's missing row."""
    return prepare_completed_batch_annotations(
        root, output_dir or root / NEXT_DIR, sources=BATCH2_SOURCES,
        expected_n=BATCH2_EXPECTED_N,
        version="openrouter-expansion-v3-luna-v2.4-completed-batch2",
        scientific_role="uniform blinded v2.4 annotation of returned Hunyuan, GLM and Gemini responses",
    )


def prepare_kimi_batch_annotations(root: Path, output_dir: Path | None = None) -> dict:
    """Freeze all completed Kimi K2.5 responses for unchanged Luna v2.4 annotation."""
    return prepare_completed_batch_annotations(
        root, output_dir or root / KIMI_DIR, sources=BATCH3_SOURCES,
        expected_n=BATCH3_EXPECTED_N,
        version="openrouter-expansion-v3-luna-v2.4-kimi-batch3",
        scientific_role="uniform blinded v2.4 annotation of completed Kimi K2.5 responses",
    )


def estimate_completed_batch_annotation_cost(
    root: Path, output_dir: Path | None = None, *, prepare=prepare_completed_batch_annotations,
    expected_n: int = EXPECTED_N, version: str = "openrouter-expansion-v3-luna-v2.4-completed-batch1-cost",
) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare(root, output_dir)
    requests = read_jsonl(output_dir / "provider_requests.jsonl")
    tokens = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (tokens * INPUT_PRICE + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE) / 1e6
    reserved = (tokens * INPUT_PRICE + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE) / 1e6
    empirical_projection = expected_n * max(
        PRIOR_WALL_COST_PER_RESPONSE, PRIOR_PILOT_COST_PER_RESPONSE
    )
    # A 20% margin over the token-based plan is already almost twice the
    # empirical projection. This is a useful stop-loss; reserving all 500
    # output tokens for every row would create a misleadingly loose ceiling.
    ceiling = math.ceil(max(planning * 1.2, empirical_projection * 1.5) * 2) / 2
    result = {
        "version": version,
        "created_at": _now(),
        "pricing_verified_at": PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests),
        "estimated_input_tokens": tokens,
        "planning_output_tokens": len(requests) * PLANNING_OUTPUT_TOKENS,
        "maximum_output_tokens_single_attempt": len(requests) * MAX_OUTPUT_TOKENS,
        "planning_cost_usd": planning,
        "single_attempt_reserved_cost_usd": reserved,
        "empirical_cost_projection_usd": empirical_projection,
        "empirical_benchmarks": {
            "wall_to_wall_v2_4_cost_per_completed_response": PRIOR_WALL_COST_PER_RESPONSE,
            "expansion_pilot_v2_4_cost_per_completed_response": PRIOR_PILOT_COST_PER_RESPONSE,
        },
        "ceiling_rule": (
            "ceil_to_$0.50(max(1.2 * planning_cost, "
            "1.5 * conservative_empirical_projection))"
        ),
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (output_dir / "cost_estimate.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    latest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    latest["status"] = "frozen_costed_not_authorized"
    latest["cost_estimate"] = result
    (output_dir / "manifest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")
    return result


def estimate_next_batch_annotation_cost(root: Path, output_dir: Path | None = None) -> dict:
    return estimate_completed_batch_annotation_cost(
        root, output_dir or root / NEXT_DIR, prepare=prepare_next_batch_annotations,
        expected_n=BATCH2_EXPECTED_N,
        version="openrouter-expansion-v3-luna-v2.4-completed-batch2-cost",
    )


def estimate_kimi_batch_annotation_cost(root: Path, output_dir: Path | None = None) -> dict:
    return estimate_completed_batch_annotation_cost(
        root, output_dir or root / KIMI_DIR, prepare=prepare_kimi_batch_annotations,
        expected_n=BATCH3_EXPECTED_N,
        version="openrouter-expansion-v3-luna-v2.4-kimi-batch3-cost",
    )


def authorize_completed_batch_annotations(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool,
    *, authorization_scope: str = "openrouter_expansion_v3_luna_v2_4_completed_batch1",
) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cost = json.loads((output_dir / "cost_estimate.json").read_text(encoding="utf-8"))
    observed = sha_file(output_dir / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized annotation payload hash does not match frozen bytes")
    if float(ceiling) != float(cost["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized ceiling does not match frozen estimate")
    authorization = {
        "recorded_at": _now(), "user_authorized": True,
        "authorization_scope": authorization_scope,
        "provider_payload_sha256": payload_sha, "model_id": MODEL,
        "provider_tag": PROVIDER, "n_requests": manifest["n_requests"],
        "reasoning_disabled": True, "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def authorize_next_batch_annotations(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
) -> dict:
    return authorize_completed_batch_annotations(
        output_dir, payload_sha, ceiling, confirmed,
        authorization_scope="openrouter_expansion_v3_luna_v2_4_completed_batch2",
    )


def authorize_kimi_batch_annotations(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
) -> dict:
    return authorize_completed_batch_annotations(
        output_dir, payload_sha, ceiling, confirmed,
        authorization_scope="openrouter_expansion_v3_luna_v2_4_kimi_batch3",
    )


def run_completed_batch_annotations(
    root: Path, output_dir: Path, workers: int, ceiling: float, authorized: bool
) -> dict:
    return run_luna_v24(root, output_dir, workers, ceiling, authorized)
