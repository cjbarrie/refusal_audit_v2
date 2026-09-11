"""Guarded Luna v2.4 annotation stage for the OpenRouter expansion pilot."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import tiktoken

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

from .openrouter_pilot import (
    DEFAULT_DIR as GENERATION_DIR,
    LANGUAGES,
    ROSTER_PATH,
    read_jsonl,
    sha_object,
    write_jsonl,
)


DEFAULT_DIR = GENERATION_DIR / "luna_v2_4_annotations_v1"
CODEBOOK = Path("config/response_validity_decomposed_v2_4.json")
ADOPTED_PROMPT = Path(
    "annotations/response_validity_v2_4/wall_to_wall_luna_v1/prompt.txt"
)
ADOPTED_SCHEMA = Path(
    "annotations/response_validity_v2_4/wall_to_wall_luna_v1/response_schema.json"
)
EXPECTED_N = 1_600


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_hash(row: dict) -> str:
    return sha_object({
        "prompt_language": row["prompt_language"],
        "prompt_text_en": row["prompt_text_en"],
        "prompt_text": row["prompt_text"],
        "response_text": row["response_text"],
    })


def _load_source_frame(root: Path) -> pd.DataFrame:
    generation_dir = root / GENERATION_DIR
    manifest = json.loads((generation_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((generation_dir / "run_summary.json").read_text(encoding="utf-8"))
    results_path = generation_dir / "results.jsonl"
    if not (
        manifest.get("status") == "completed"
        and summary.get("n_completed") == EXPECTED_N
        and summary.get("n_incomplete") == 0
        and sha_file(results_path) == summary.get("results_sha256")
    ):
        raise ValueError("expansion pilot generation is not complete and hash-valid")
    results = pd.DataFrame(read_jsonl(results_path))
    key = ["prompt_id", "prompt_language", "model"]
    if len(results) != EXPECTED_N or results.duplicated(key).any():
        raise ValueError("generation results are not 1,600 unique response keys")
    if results.response_text.isna().any() or results.response_text.str.strip().eq("").any():
        raise ValueError("generation results contain empty response text")

    roster = json.loads((root / ROSTER_PATH).read_text(encoding="utf-8"))
    prompt_maps: Dict[str, Dict[str, dict]] = {}
    for language in LANGUAGES:
        spec = roster["design"]["prompt_files"][language]
        path = root / spec["path"]
        if sha_file(path) != spec["sha256"]:
            raise ValueError(f"prompt hash mismatch for {language}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        prompt_maps[language] = {row["id"]: row for row in raw["prompts"]}

    english = prompt_maps["en"]
    records = []
    for row in results.to_dict("records"):
        language = row["prompt_language"]
        prompt_id = row["prompt_id"]
        records.append({
            "prompt_id": prompt_id,
            "prompt_language": language,
            "subject_model": row["model"],
            "subject_model_id": row["model_id_requested"],
            "subject_provider_tag": row["provider_tag_requested"],
            "generation_provider_request_id": row["provider_request_id"],
            "generation_response_sha256": row["response_text_sha256"],
            "prompt_text_en": english[prompt_id]["text"],
            "prompt_text": prompt_maps[language][prompt_id]["text"],
            "response_text": row["response_text"],
            "pilot_band": row["pilot_band"],
            **row["prompt_metadata"],
        })
    return pd.DataFrame(records).sort_values(
        ["prompt_id", "prompt_language", "subject_model"], kind="mergesort"
    ).reset_index(drop=True)


def prepare_pilot_annotations(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    generation_dir = root / GENERATION_DIR
    source_results = generation_dir / "results.jsonl"
    codebook_path = root / CODEBOOK
    input_hashes = {
        # The generation manifest contains mutable run/cost timestamps. Bind this
        # stage to immutable request and result bytes instead.
        "generation_provider_payload": sha_file(
            generation_dir / "provider_requests.jsonl"
        ),
        "generation_results": sha_file(source_results),
        "generation_run_summary": sha_file(generation_dir / "run_summary.json"),
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
        stored_inputs = dict(manifest.get("input_sha256", {}))
        # Migrate the first local freeze, which incorrectly recorded the mutable
        # generation manifest. This changes provenance metadata only; every
        # frozen annotation artifact is checked below before the update.
        stored_inputs.pop("generation_manifest", None)
        stored_inputs.setdefault(
            "generation_provider_payload",
            input_hashes["generation_provider_payload"],
        )
        if stored_inputs != input_hashes:
            raise ValueError("frozen pilot annotation payload no longer matches inputs")
        for name, expected in manifest["artifact_sha256"].items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != expected:
                raise ValueError(f"frozen annotation artifact changed: {name}")
        if manifest.get("input_sha256") != input_hashes:
            manifest["input_sha256"] = input_hashes
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    frame = _load_source_frame(root)
    codebook = json.loads(codebook_path.read_text(encoding="utf-8"))
    system = _system_v24(codebook)
    schema = _schema()
    if hashlib.sha256(system.encode("utf-8")).hexdigest() != input_hashes[
        "adopted_v2_4_prompt"
    ]:
        raise ValueError("constructed v2.4 prompt differs from adopted prompt")
    schema_bytes = json.dumps(schema, indent=2).encode("utf-8")
    if hashlib.sha256(schema_bytes).hexdigest() != input_hashes["adopted_v2_4_schema"]:
        raise ValueError("constructed v2.4 schema differs from adopted schema")

    encoder = tiktoken.get_encoding("o200k_base")
    requests: List[dict] = []
    index_rows: List[dict] = []
    for row in frame.to_dict("records"):
        source_sha = _source_hash(row)
        logical_id = sha_object({
            "response_key": [
                row["prompt_id"], row["prompt_language"], row["subject_model"]
            ],
            "source_sha256": source_sha,
            "version": "openrouter-expansion-pilot-luna-v2.4-v1",
        })[:24]
        user = _user(row, "source_response_only")
        request = {
            "logical_request_id": logical_id,
            "provider_request_id": sha_object({
                "logical_request_id": logical_id, "model_id": MODEL
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
            "estimated_input_tokens": request["estimated_input_tokens"],
            **{key: row[key] for key in (
                "prompt_id", "prompt_language", "subject_model",
                "subject_model_id", "subject_provider_tag",
                "generation_provider_request_id", "generation_response_sha256",
                "pilot_band", "issue_id", "topic_domain", "controversy_tier",
                "region_focus", "position_side", "route",
            )},
        })

    serialized_messages = json.dumps(
        [request["messages"] for request in requests], ensure_ascii=False
    )
    for forbidden in (
        "prior_refusal_prop", "prior_capability_failure_prop",
        "pilot_band", "subject_model", "provider_tag_requested",
    ):
        if forbidden in serialized_messages:
            raise ValueError(f"selection/source metadata leaked into messages: {forbidden}")
    if len(requests) != EXPECTED_N:
        raise ValueError("annotation payload must contain 1,600 requests")
    if len({row["provider_request_id"] for row in requests}) != EXPECTED_N:
        raise ValueError("annotation provider request IDs are not unique")

    output_dir.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(index_rows).to_parquet(artifacts["response_index.parquet"], index=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    artifacts["prompt.txt"].write_text(system, encoding="utf-8")
    artifacts["response_schema.json"].write_bytes(schema_bytes)
    manifest = {
        "version": "openrouter-expansion-pilot-luna-v2.4-v1",
        "created_at": now(),
        "status": "frozen_unpriced",
        "scientific_role": (
            "uniform blinded v2.4 annotation of all 1,600 expansion pilot responses"
        ),
        "codebook_version": codebook["codebook_version"],
        "input_mode": "source_response_only",
        "translation_used": False,
        "subject_model_blinded_in_messages": True,
        "selection_metadata_blinded_in_messages": True,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_N,
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_attempts": MAX_ATTEMPTS,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "input_sha256": input_hashes,
        "artifact_sha256": {
            name: sha_file(path) for name, path in artifacts.items()
        },
        "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_pilot_annotation_cost(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare_pilot_annotations(root, output_dir)
    requests = read_jsonl(output_dir / "provider_requests.jsonl")
    tokens = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (
        tokens * INPUT_PRICE
        + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    reserved = (
        tokens * INPUT_PRICE
        + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    ceiling = math.ceil(max(planning * 1.5, reserved * 1.25) * 2) / 2
    result = {
        "version": "openrouter-expansion-pilot-luna-v2.4-cost-v1",
        "created_at": now(),
        "pricing_verified_at": PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests),
        "estimated_input_tokens": tokens,
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
    manifest_path = output_dir / "manifest.json"
    latest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not latest.get("paid_run_authorized") and not latest.get("network_call_made"):
        latest["status"] = "frozen_unpaid"
    latest["cost_estimate"] = result
    manifest_path.write_text(json.dumps(latest, indent=2), encoding="utf-8")
    return result


def authorize_pilot_annotations(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
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
        raise ValueError("authorized annotation ceiling does not match frozen estimate")
    authorization = {
        "recorded_at": now(),
        "user_authorized": True,
        "authorization_scope": "openrouter_expansion_pilot_luna_v2_4_v1",
        "provider_payload_sha256": payload_sha,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_N,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def run_pilot_annotations(
    root: Path, output_dir: Path, workers: int, ceiling: float, authorized: bool
) -> dict:
    """Use the already-tested generic v2.4 runner on the frozen pilot payload."""
    return run_luna_v24(root, output_dir, workers, ceiling, authorized)


def summarize_pilot_annotations(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Assemble derived v2.4 outcomes and descriptive pilot diagnostics locally."""
    output_dir = output_dir or root / DEFAULT_DIR
    run_path = output_dir / "run_summary.json"
    results_path = output_dir / "results.jsonl"
    index_path = output_dir / "response_index.parquet"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if not (
        run.get("n_completed") == EXPECTED_N
        and run.get("n_incomplete") == 0
        and run.get("schema_gate_pass") is True
        and run.get("results_sha256") == sha_file(results_path)
    ):
        raise RuntimeError("pilot annotations are incomplete or failed integrity checks")

    labels = _derive(pd.DataFrame(read_jsonl(results_path)))
    index = pd.read_parquet(index_path)
    if (
        len(labels) != EXPECTED_N
        or labels["audit_response_id"].duplicated().any()
        or len(index) != EXPECTED_N
        or index["audit_response_id"].duplicated().any()
    ):
        raise ValueError("pilot labels or response index are not 1,600 unique rows")
    frame = index.merge(labels, on="audit_response_id", validate="one_to_one")
    if frame["provider_request_id_x"].ne(frame["provider_request_id_y"]).any():
        raise ValueError("annotation request IDs do not agree with the response index")
    frame = frame.drop(columns=["provider_request_id_y"]).rename(
        columns={"provider_request_id_x": "provider_request_id"}
    )
    frame["both_refusal_and_capability_failure"] = (
        frame["pred_genuine_refusal"] & frame["pred_capability_failure"]
    )

    label_path = output_dir / "assembled_labels.parquet"
    frame.to_parquet(label_path, index=False)

    outcomes = (
        frame[[
            "pred_genuine_refusal", "pred_capability_failure",
            "both_refusal_and_capability_failure",
        ]]
        .agg(["sum", "mean"])
        .T.reset_index()
        .rename(columns={"index": "outcome", "sum": "event_n", "mean": "rate"})
    )
    outcomes.insert(1, "n", len(frame))
    overall_path = output_dir / "pilot_outcome_counts.csv"
    outcomes.to_csv(overall_path, index=False)

    def grouped(columns: list[str], path: Path) -> pd.DataFrame:
        table = frame.groupby(columns, dropna=False).agg(
            n=("audit_response_id", "size"),
            genuine_refusal_n=("pred_genuine_refusal", "sum"),
            genuine_refusal_rate=("pred_genuine_refusal", "mean"),
            capability_failure_n=("pred_capability_failure", "sum"),
            capability_failure_rate=("pred_capability_failure", "mean"),
            overlap_n=("both_refusal_and_capability_failure", "sum"),
            overlap_rate=("both_refusal_and_capability_failure", "mean"),
        ).reset_index()
        table.to_csv(path, index=False)
        return table

    model_path = output_dir / "pilot_outcomes_by_model.csv"
    language_path = output_dir / "pilot_outcomes_by_language.csv"
    cell_path = output_dir / "pilot_outcomes_by_model_language.csv"
    grouped(["subject_model"], model_path)
    grouped(["prompt_language"], language_path)
    grouped(["subject_model", "prompt_language"], cell_path)

    summary = {
        "version": "openrouter-expansion-pilot-luna-v2.4-summary-v1",
        "created_at": now(),
        "status": "complete_descriptive_enriched_pilot",
        "n": len(frame),
        "genuine_refusal_n": int(frame["pred_genuine_refusal"].sum()),
        "genuine_refusal_rate": float(frame["pred_genuine_refusal"].mean()),
        "capability_failure_n": int(frame["pred_capability_failure"].sum()),
        "capability_failure_rate": float(frame["pred_capability_failure"].mean()),
        "overlap_n": int(frame["both_refusal_and_capability_failure"].sum()),
        "overlap_rate": float(frame["both_refusal_and_capability_failure"].mean()),
        "interpretation": (
            "These are unweighted diagnostics for an enriched 40-prompt pilot. "
            "They are not population prevalence estimates and do not support "
            "jurisdiction comparisons. Genuine refusal and capability failure "
            "are separate, potentially overlapping outcomes."
        ),
        "input_sha256": {
            "run_summary": sha_file(run_path),
            "results": sha_file(results_path),
            "response_index": sha_file(index_path),
        },
        "artifact_sha256": {
            path.name: sha_file(path)
            for path in (
                label_path, overall_path, model_path, language_path, cell_path
            )
        },
        "provider_call_made_by_summary": False,
    }
    (output_dir / "pilot_annotation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary
