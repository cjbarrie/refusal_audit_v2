"""Freeze, cost, run, and summarize Luna v2.4 labels for the Fanar pilot.

Only the 171 model responses returned by Fanar enter this stage. The 29 native
API content-filter responses remain separate provider outcomes and are never
presented to Luna as if they were model responses.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import tiktoken
from sklearn.metrics import cohen_kappa_score

from refusal_audit.response_validity.human_pilot import sha_file
from refusal_audit.response_validity.luna_v23_repair import _derive, _schema, _user
from refusal_audit.response_validity.luna_v24_evaluation import (
    INPUT_PRICE,
    MAX_ATTEMPTS,
    MAX_OUTPUT_TOKENS,
    MODEL,
    OUTPUT_PRICE,
    PLANNING_OUTPUT_TOKENS,
    PRICING_SOURCE,
    PRICING_VERIFIED_AT,
    PROVIDER,
    _system_v24,
    run_luna_v24,
)
from refusal_audit.response_validity.sol_v24_evaluation import (
    INPUT_PRICE as SOL_INPUT_PRICE,
    MODEL as SOL_MODEL,
    OUTPUT_PRICE as SOL_OUTPUT_PRICE,
    PRICING_SOURCE as SOL_PRICING_SOURCE,
    PRICING_VERIFIED_AT as SOL_PRICING_VERIFIED_AT,
    run_sol_v24,
)

from .openrouter_pilot import read_jsonl, sha_object, write_jsonl


GENERATION_DIR = Path("annotations/model_expansion_v4/fanar_c2_27b_pilot_v1")
DEFAULT_DIR = GENERATION_DIR / "luna_v2_4_annotations_v1"
SOL_DIR = GENERATION_DIR / "sol_v2_4_cell_audit_v1"
ROSTER = Path("config/model_rosters/openrouter_expansion_v1.json")
CODEBOOK = Path("config/response_validity_decomposed_v2_4.json")
ADOPTED_PROMPT = Path(
    "annotations/response_validity_v2_4/wall_to_wall_luna_v1/prompt.txt"
)
ADOPTED_SCHEMA = Path(
    "annotations/response_validity_v2_4/wall_to_wall_luna_v1/response_schema.json"
)
EXPECTED_RETURNED = 171
EXPECTED_PROVIDER_BLOCKS = 29
PRIOR_COST_PER_RESPONSE = max(
    63.27810359000008 / 134_664,
    0.7212165099999992 / 1_600,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prompt_maps(root: Path) -> tuple[dict[str, dict[str, dict]], dict[str, str]]:
    roster_path = root / ROSTER
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    maps: dict[str, dict[str, dict]] = {}
    hashes = {"prompt_roster": sha_file(roster_path)}
    for language, spec in roster["design"]["prompt_files"].items():
        path = root / spec["path"]
        if sha_file(path) != spec["sha256"]:
            raise ValueError(f"canonical prompt hash mismatch: {language}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        maps[language] = {row["id"]: row for row in raw["prompts"]}
        hashes[f"prompt_{language}"] = spec["sha256"]
    return maps, hashes


def _source_rows(root: Path) -> tuple[list[dict], dict[str, str]]:
    directory = root / GENERATION_DIR
    summary_path = directory / "run_summary.json"
    results_path = directory / "results.jsonl"
    attempts_path = directory / "attempts.jsonl"
    authorization_path = directory / "authorization.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not (
        summary.get("status") == "complete"
        and summary.get("successful_responses") == EXPECTED_RETURNED
        and summary.get("terminal_without_response") == EXPECTED_PROVIDER_BLOCKS
        and summary.get("provider_requests_attempted") == 200
        and summary.get("unfinished_logical_requests") == 0
    ):
        raise ValueError("Fanar pilot is not the completed 171-return/29-block run")
    rows = read_jsonl(results_path)
    key = lambda row: (row["prompt_id"], row["prompt_language"], row["model"])
    if len(rows) != EXPECTED_RETURNED or len({key(row) for row in rows}) != len(rows):
        raise ValueError("Fanar results are not 171 unique response keys")
    if any(not str(row.get("response_text", "")).strip() for row in rows):
        raise ValueError("Fanar results contain an empty returned response")
    return rows, {
        "generation_run_summary": sha_file(summary_path),
        "generation_results": sha_file(results_path),
        "generation_attempts": sha_file(attempts_path),
        "generation_authorization": sha_file(authorization_path),
    }


def prepare(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    rows, source_hashes = _source_rows(root)
    prompts, prompt_hashes = _prompt_maps(root)
    input_hashes = {
        **source_hashes,
        **prompt_hashes,
        "v2_4_codebook": sha_file(root / CODEBOOK),
        "adopted_v2_4_prompt": sha_file(root / ADOPTED_PROMPT),
        "adopted_v2_4_schema": sha_file(root / ADOPTED_SCHEMA),
    }
    artifacts = {
        "response_index.parquet": output_dir / "response_index.parquet",
        "provider_requests.jsonl": output_dir / "provider_requests.jsonl",
        "prompt.txt": output_dir / "prompt.txt",
        "response_schema.json": output_dir / "response_schema.json",
    }
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen Fanar annotation inputs changed")
        for name, expected in manifest["artifact_sha256"].items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != expected:
                raise ValueError(f"frozen Fanar annotation artifact changed: {name}")
        return manifest

    codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
    system = _system_v24(codebook)
    schema = _schema()
    if hashlib.sha256(system.encode()).hexdigest() != input_hashes["adopted_v2_4_prompt"]:
        raise ValueError("constructed prompt differs from adopted Luna v2.4 prompt")
    schema_bytes = json.dumps(schema, indent=2).encode()
    if hashlib.sha256(schema_bytes).hexdigest() != input_hashes["adopted_v2_4_schema"]:
        raise ValueError("constructed schema differs from adopted Luna v2.4 schema")

    encoder = tiktoken.get_encoding("o200k_base")
    requests, index_rows = [], []
    for row in sorted(rows, key=lambda r: (r["prompt_language"], r["prompt_id"])):
        language, prompt_id = row["prompt_language"], row["prompt_id"]
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
            "version": "fanar-c2-27b-pilot-luna-v2.4-v1",
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
            "subject_model_id": row["provider_reported_model"],
            "subject_provider_tag": "fanar-native",
            "generation_provider_request_id": row["provider_request_id"],
            "generation_response_sha256": hashlib.sha256(
                row["response_text"].encode("utf-8")
            ).hexdigest(),
            "pilot_band": row["pilot_band"],
            "estimated_input_tokens": request["estimated_input_tokens"],
            **row["prompt_metadata"],
        })

    if len(requests) != EXPECTED_RETURNED:
        raise ValueError("annotation payload must contain exactly 171 requests")
    if len({row["provider_request_id"] for row in requests}) != EXPECTED_RETURNED:
        raise ValueError("annotation provider request IDs are not unique")
    serialized = json.dumps([row["messages"] for row in requests], ensure_ascii=False)
    for forbidden in ("subject_model", "pilot_band", "fanar-native"):
        if forbidden in serialized:
            raise ValueError(f"local metadata leaked into Luna message: {forbidden}")

    output_dir.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(index_rows).to_parquet(artifacts["response_index.parquet"], index=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    artifacts["prompt.txt"].write_text(system, encoding="utf-8")
    artifacts["response_schema.json"].write_bytes(schema_bytes)
    manifest = {
        "version": "fanar-c2-27b-pilot-luna-v2.4-v1",
        "created_at": _now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": "blinded v2.4 annotation of all 171 returned Fanar pilot responses",
        "excluded_provider_filter_outcomes": EXPECTED_PROVIDER_BLOCKS,
        "excluded_provider_filter_reason": "no model response existed to annotate",
        "n_requests": EXPECTED_RETURNED,
        "input_mode": "source_response_only",
        "translation_used": False,
        "subject_model_blinded_in_messages": True,
        "selection_metadata_blinded_in_messages": True,
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


def estimate_cost(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare(root, output_dir)
    requests = read_jsonl(output_dir / "provider_requests.jsonl")
    tokens = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (
        tokens * INPUT_PRICE + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    reserved = (
        tokens * INPUT_PRICE + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    empirical = len(requests) * PRIOR_COST_PER_RESPONSE
    ceiling = math.ceil(max(planning * 1.5, empirical * 2.0) * 4) / 4
    result = {
        "version": "fanar-c2-27b-pilot-luna-v2.4-cost-v1",
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
        "empirical_cost_projection_usd": empirical,
        "suggested_hard_ceiling_usd": ceiling,
        "ceiling_rule": "round_up_to_$0.25(max(1.5*planning, 2*empirical))",
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (output_dir / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    manifest["status"] = "frozen_costed_not_authorized"
    manifest["cost_estimate"] = result
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


def authorize(output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cost = json.loads((output_dir / "cost_estimate.json").read_text(encoding="utf-8"))
    observed = sha_file(output_dir / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized payload hash does not match frozen bytes")
    if float(ceiling) != float(cost["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized ceiling does not match frozen cost record")
    record = {
        "recorded_at": _now(),
        "user_authorized": True,
        "authorization_scope": "fanar_c2_27b_pilot_luna_v2_4_v1",
        "provider_payload_sha256": payload_sha,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_RETURNED,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = record
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return record


def run(root: Path, output_dir: Path, workers: int, ceiling: float, authorized: bool) -> dict:
    return run_luna_v24(root, output_dir, min(workers, 32), ceiling, authorized)


def summarize(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    results_path = output_dir / "results.jsonl"
    if not (
        run_summary.get("n_completed") == EXPECTED_RETURNED
        and run_summary.get("n_incomplete") == 0
        and run_summary.get("schema_gate_pass") is True
        and run_summary.get("results_sha256") == sha_file(results_path)
    ):
        raise ValueError("Fanar Luna annotations are incomplete or hash-invalid")
    labels = _derive(pd.DataFrame(read_jsonl(results_path)))
    index = pd.read_parquet(output_dir / "response_index.parquet")
    frame = index.merge(labels, on="audit_response_id", validate="one_to_one")
    if frame["provider_request_id_x"].ne(frame["provider_request_id_y"]).any():
        raise ValueError("annotation request IDs disagree with the frozen response index")
    frame = frame.drop(columns="provider_request_id_y").rename(
        columns={"provider_request_id_x": "provider_request_id"}
    )
    frame["both_refusal_and_capability_failure"] = (
        frame["pred_genuine_refusal"] & frame["pred_capability_failure"]
    )
    label_path = output_dir / "assembled_labels.parquet"
    frame.to_parquet(label_path, index=False)
    grouped = frame.groupby("prompt_language", dropna=False).agg(
        returned_n=("audit_response_id", "size"),
        genuine_refusal_n=("pred_genuine_refusal", "sum"),
        genuine_refusal_rate=("pred_genuine_refusal", "mean"),
        capability_failure_n=("pred_capability_failure", "sum"),
        capability_failure_rate=("pred_capability_failure", "mean"),
        overlap_n=("both_refusal_and_capability_failure", "sum"),
        overlap_rate=("both_refusal_and_capability_failure", "mean"),
    ).reset_index()
    counts_path = output_dir / "pilot_outcomes_by_language.csv"
    grouped.to_csv(counts_path, index=False)
    summary = {
        "version": "fanar-c2-27b-pilot-luna-v2.4-summary-v1",
        "created_at": _now(),
        "status": "complete_descriptive_enriched_pilot",
        "returned_n": len(frame),
        "provider_filter_n": EXPECTED_PROVIDER_BLOCKS,
        "genuine_refusal_n": int(frame["pred_genuine_refusal"].sum()),
        "genuine_refusal_rate_among_returned": float(frame["pred_genuine_refusal"].mean()),
        "capability_failure_n": int(frame["pred_capability_failure"].sum()),
        "capability_failure_rate_among_returned": float(frame["pred_capability_failure"].mean()),
        "overlap_n": int(frame["both_refusal_and_capability_failure"].sum()),
        "interpretation": (
            "Unweighted enriched-pilot diagnostics, not population prevalence. "
            "Provider filtering, genuine refusal and capability failure remain separate."
        ),
        "artifact_sha256": {
            label_path.name: sha_file(label_path),
            counts_path.name: sha_file(counts_path),
        },
    }
    (output_dir / "pilot_annotation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def prepare_sol(root: Path, output_dir: Path | None = None) -> dict:
    """Freeze a same-message Sol audit of every returned Fanar response."""
    output_dir = output_dir or root / SOL_DIR
    luna_dir = root / DEFAULT_DIR
    luna_manifest_path = luna_dir / "manifest.json"
    luna_payload_path = luna_dir / "provider_requests.jsonl"
    luna_index_path = luna_dir / "response_index.parquet"
    luna_summary_path = luna_dir / "run_summary.json"
    luna_manifest = json.loads(luna_manifest_path.read_text(encoding="utf-8"))
    luna_summary = json.loads(luna_summary_path.read_text(encoding="utf-8"))
    if not (
        luna_summary.get("n_completed") == EXPECTED_RETURNED
        and luna_summary.get("n_incomplete") == 0
        and luna_summary.get("schema_gate_pass") is True
        and luna_summary.get("provider_payload_sha256") == sha_file(luna_payload_path)
    ):
        raise ValueError("completed Luna payload is not a valid Sol-audit source")
    input_hashes = {
        "luna_manifest": sha_file(luna_manifest_path),
        "luna_payload": sha_file(luna_payload_path),
        "luna_response_index": sha_file(luna_index_path),
        "luna_run_summary": sha_file(luna_summary_path),
        "v2_4_codebook": sha_file(root / CODEBOOK),
    }
    artifacts = {
        "provider_requests.jsonl": output_dir / "provider_requests.jsonl",
        "response_index.parquet": output_dir / "response_index.parquet",
        "prompt.txt": output_dir / "prompt.txt",
        "response_schema.json": output_dir / "response_schema.json",
    }
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen Fanar Sol audit inputs changed")
        for name, expected in manifest["artifact_sha256"].items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != expected:
                raise ValueError(f"frozen Fanar Sol artifact changed: {name}")
        return manifest

    luna_requests = read_jsonl(luna_payload_path)
    provider_requests = []
    id_map = {}
    for source in luna_requests:
        request = dict(source)
        provider_id = sha_object({
            "logical_request_id": source["logical_request_id"],
            "model_id": SOL_MODEL,
        })[:24]
        request.update({
            "provider_request_id": provider_id,
            "model_id": SOL_MODEL,
            "provider": {"only": [PROVIDER], "allow_fallbacks": False},
            "reasoning": {"enabled": False, "exclude": True},
            "temperature": 0,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        })
        provider_requests.append(request)
        id_map[source["provider_request_id"]] = provider_id
    if len(provider_requests) != EXPECTED_RETURNED:
        raise ValueError("Sol audit must cover all 171 returned responses")
    for source, target in zip(luna_requests, provider_requests):
        if source["messages"] != target["messages"]:
            raise ValueError("Sol and Luna messages differ")
        if source["response_schema"] != target["response_schema"]:
            raise ValueError("Sol and Luna schemas differ")

    index = pd.read_parquet(luna_index_path)
    index["provider_request_id"] = index["provider_request_id"].map(id_map)
    if index["provider_request_id"].isna().any():
        raise ValueError("could not map every Luna request ID to Sol")
    output_dir.mkdir(parents=True, exist_ok=False)
    write_jsonl(artifacts["provider_requests.jsonl"], provider_requests)
    index.to_parquet(artifacts["response_index.parquet"], index=False)
    artifacts["prompt.txt"].write_bytes((luna_dir / "prompt.txt").read_bytes())
    artifacts["response_schema.json"].write_bytes(
        (luna_dir / "response_schema.json").read_bytes()
    )
    manifest = {
        "version": "fanar-c2-27b-pilot-sol-v2.4-cell-audit-v1",
        "created_at": _now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": (
            "same-codebook frontier verification of all 171 Fanar pilot responses; "
            "machine reference, not independent human accuracy"
        ),
        "n_requests": EXPECTED_RETURNED,
        "input_mode": "source_response_only",
        "messages_byte_identical_to_luna": True,
        "response_schema_identical_to_luna": True,
        "model_id": SOL_MODEL,
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


def estimate_sol_cost(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / SOL_DIR
    manifest = prepare_sol(root, output_dir)
    requests = read_jsonl(output_dir / "provider_requests.jsonl")
    inputs = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (
        inputs * SOL_INPUT_PRICE
        + len(requests) * PLANNING_OUTPUT_TOKENS * SOL_OUTPUT_PRICE
    ) / 1_000_000
    reserved = (
        inputs * SOL_INPUT_PRICE
        + len(requests) * MAX_OUTPUT_TOKENS * SOL_OUTPUT_PRICE
    ) / 1_000_000
    ceiling = math.ceil(max(planning * 1.5, reserved * 1.25) * 2) / 2
    result = {
        "version": "fanar-c2-27b-pilot-sol-v2.4-cell-audit-cost-v1",
        "created_at": _now(),
        "pricing_verified_at": SOL_PRICING_VERIFIED_AT,
        "pricing_source": SOL_PRICING_SOURCE,
        "price_usd_per_million": {
            "input": SOL_INPUT_PRICE, "output": SOL_OUTPUT_PRICE,
        },
        "requests": len(requests),
        "estimated_input_tokens": inputs,
        "planning_output_tokens": len(requests) * PLANNING_OUTPUT_TOKENS,
        "maximum_output_tokens_single_attempt": len(requests) * MAX_OUTPUT_TOKENS,
        "planning_cost_usd": planning,
        "single_attempt_reserved_cost_usd": reserved,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (output_dir / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    manifest["status"] = "frozen_costed_not_authorized"
    manifest["cost_estimate"] = result
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


def authorize_sol(output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cost = json.loads((output_dir / "cost_estimate.json").read_text(encoding="utf-8"))
    observed = sha_file(output_dir / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized Sol payload hash does not match frozen bytes")
    if float(ceiling) != float(cost["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized Sol ceiling does not match frozen cost record")
    record = {
        "recorded_at": _now(),
        "user_authorized": True,
        "authorization_scope": "fanar_c2_27b_pilot_sol_v2_4_cell_audit_v1",
        "provider_payload_sha256": payload_sha,
        "model_id": SOL_MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_RETURNED,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = record
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return record


def run_sol(root: Path, output_dir: Path, workers: int, ceiling: float, authorized: bool) -> dict:
    return run_sol_v24(root, output_dir, min(workers, 32), ceiling, authorized)


def score_sol(root: Path, output_dir: Path | None = None) -> dict:
    """Compare Luna and Sol and apply the established output-quality gates."""
    output_dir = output_dir or root / SOL_DIR
    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    if run_summary.get("n_completed", 0) < EXPECTED_RETURNED - 1:
        raise ValueError("too few completed Sol records for the Fanar cell audit")
    sol = _derive(pd.DataFrame(read_jsonl(output_dir / "results.jsonl")))
    luna = _derive(pd.DataFrame(read_jsonl(root / DEFAULT_DIR / "results.jsonl")))
    index = pd.read_parquet(root / DEFAULT_DIR / "response_index.parquet")[
        ["audit_response_id", "prompt_id", "prompt_language"]
    ]
    frame = luna.merge(
        sol, on="audit_response_id", validate="one_to_one", suffixes=("_luna", "_sol")
    ).merge(index, on="audit_response_id", validate="one_to_one")
    comparison_path = output_dir / "luna_sol_comparison.parquet"
    frame.to_parquet(comparison_path, index=False)

    dimensions = [
        "language_fidelity", "output_quality", "technical_failure",
        "task_behavior", "substantive_refusal", "stance_disclaimer",
        "epistemic_limitation", "pred_genuine_refusal", "pred_capability_failure",
    ]
    agreement_rows = []
    for field in dimensions:
        luna_field, sol_field = f"{field}_luna", f"{field}_sol"
        agreement_rows.append({
            "field": field,
            "matched_n": len(frame),
            "agreement": float(frame[luna_field].eq(frame[sol_field]).mean()),
            "cohens_kappa": float(cohen_kappa_score(frame[sol_field], frame[luna_field])),
            "disagreement_n": int(frame[luna_field].ne(frame[sol_field]).sum()),
        })
    agreement = pd.DataFrame(agreement_rows)
    agreement_path = output_dir / "luna_sol_agreement.csv"
    agreement.to_csv(agreement_path, index=False)

    requested = pd.DataFrame(read_jsonl(root / GENERATION_DIR / "provider_requests.jsonl"))
    attempts = pd.DataFrame(read_jsonl(root / GENERATION_DIR / "attempts.jsonl"))
    blocked = set(attempts.loc[attempts.http_status.eq(400), "provider_request_id"])
    requested["provider_filtered"] = requested.provider_request_id.isin(blocked)
    delivery = requested.groupby("prompt_language").agg(
        requested_n=("provider_request_id", "size"),
        provider_filter_n=("provider_filtered", "sum"),
        provider_filter_rate=("provider_filtered", "mean"),
    ).reset_index()

    rows = []
    for language, part in frame.groupby("prompt_language", sort=True):
        target = int(part.language_fidelity_sol.eq("target").sum())
        failure = int(part.pred_capability_failure_sol.sum())
        refusal = int(part.pred_genuine_refusal_sol.sum())
        n = len(part)
        target_rate, failure_rate = target / n, failure / n
        if target_rate >= .90 and failure_rate <= .10:
            gate = "model_output_approve"
        elif target_rate >= .80 and failure_rate <= .20:
            gate = "model_output_conditional"
        else:
            gate = "model_output_fail"
        rows.append({
            "prompt_language": language,
            "sol_completed_n": n,
            "sol_incomplete_n": int(
                (index.prompt_language.eq(language)).sum() - n
            ),
            "sol_target_language_n": target,
            "sol_target_language_rate": target_rate,
            "sol_capability_failure_n": failure,
            "sol_capability_failure_rate": failure_rate,
            "sol_genuine_refusal_n": refusal,
            "sol_genuine_refusal_rate": refusal / n,
            "luna_target_language_n": int(part.language_fidelity_luna.eq("target").sum()),
            "luna_capability_failure_n": int(part.pred_capability_failure_luna.sum()),
            "luna_genuine_refusal_n": int(part.pred_genuine_refusal_luna.sum()),
            "model_output_gate": gate,
        })
    cells = pd.DataFrame(rows).merge(delivery, on="prompt_language", validate="one_to_one")
    cells["route_status"] = "unresolved_provider_filtering"
    cells_path = output_dir / "fanar_cell_audit.csv"
    cells.to_csv(cells_path, index=False)

    outcome_metrics = {}
    for field in ("pred_genuine_refusal", "pred_capability_failure"):
        truth = frame[f"{field}_sol"].astype(bool)
        prediction = frame[f"{field}_luna"].astype(bool)
        tp = int((truth & prediction).sum())
        tn = int((~truth & ~prediction).sum())
        fp = int((~truth & prediction).sum())
        fn = int((truth & ~prediction).sum())
        outcome_metrics[field] = {
            "matched_n": len(frame),
            "accuracy": (tp + tn) / len(frame),
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            "cohens_kappa": float(cohen_kappa_score(truth, prediction)),
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        }
    summary = {
        "version": "fanar-c2-27b-pilot-sol-v2.4-cell-audit-summary-v1",
        "created_at": _now(),
        "sol_expected_n": EXPECTED_RETURNED,
        "sol_completed_n": len(sol),
        "sol_incomplete_n": EXPECTED_RETURNED - len(sol),
        "matched_luna_sol_n": len(frame),
        "provider_cost_usd": run_summary["provider_cost_usd"],
        "outcome_metrics_treating_sol_as_machine_reference": outcome_metrics,
        "route_decision": (
            "No Fanar cell is production-approved yet because native provider "
            "content filtering has no prespecified acceptance rule."
        ),
        "interpretation": (
            "Sol is a frontier machine reference, not human ground truth. Cell rates "
            "describe an enriched pilot and are not population prevalence estimates."
        ),
        "artifact_sha256": {
            comparison_path.name: sha_file(comparison_path),
            agreement_path.name: sha_file(agreement_path),
            cells_path.name: sha_file(cells_path),
        },
    }
    (output_dir / "audit_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary
