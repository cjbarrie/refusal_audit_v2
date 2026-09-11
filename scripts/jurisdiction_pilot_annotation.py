#!/usr/bin/env python3
"""Guarded Luna v2.4 annotation of the T-pro, Bielik and Sarvam pilots.

Only successful, non-empty subject-model responses enter the annotation
payload. Provider errors and empty generation outcomes remain in the generation
denominator and are not presented to Luna as text to classify.

Technical record: docs/JURISDICTION_MODEL_EXPANSION_V1.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import tiktoken

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from env_utils import load_env_from_file
from refusal_audit.model_expansion.openrouter_pilot import read_jsonl, sha_object, write_jsonl
from refusal_audit.response_validity.human_pilot import sha_file
from refusal_audit.response_validity.luna_v23_repair import _derive, _schema, _user
from refusal_audit.response_validity.luna_v24_evaluation import (
    INPUT_PRICE, MAX_ATTEMPTS, MAX_OUTPUT_TOKENS, MODEL, OUTPUT_PRICE,
    PLANNING_OUTPUT_TOKENS, PRICING_SOURCE, PRICING_VERIFIED_AT, PROVIDER,
    _system_v24, run_luna_v24,
)

TB_DIR = ROOT / "annotations/model_expansion_v4/jurisdiction_pilot_v1"
SARVAM_DIR = ROOT / "annotations/model_expansion_v4/sarvam_105b_pilot_v1"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/jurisdiction_pilot_luna_v2_4_v1"
ROSTER = ROOT / "config/model_rosters/openrouter_expansion_v1.json"
CODEBOOK = ROOT / "config/response_validity_decomposed_v2_4.json"
ADOPTED_PROMPT = ROOT / "annotations/response_validity_v2_4/wall_to_wall_luna_v1/prompt.txt"
ADOPTED_SCHEMA = ROOT / "annotations/response_validity_v2_4/wall_to_wall_luna_v1/response_schema.json"
EXPECTED_RESPONSES = 591
EXPECTED_TECHNICAL_OUTCOMES = 9
PRIOR_COST_PER_RESPONSE = max(63.27810359000008 / 134_664, 0.7212165099999992 / 1_600)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def prompt_maps() -> tuple[dict[str, dict[str, dict]], dict[str, str]]:
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    maps, hashes = {}, {"prompt_roster": sha_file(ROSTER)}
    for language, spec in roster["design"]["prompt_files"].items():
        path = ROOT / spec["path"]
        if sha_file(path) != spec["sha256"]:
            raise ValueError(f"canonical prompt hash mismatch: {language}")
        maps[language] = {r["id"]: r for r in json.loads(path.read_text())["prompts"]}
        hashes[f"prompt_{language}"] = spec["sha256"]
    return maps, hashes


def load_sources() -> tuple[list[dict], dict[str, str]]:
    paths = {
        "tb_requests": TB_DIR / "provider_requests.jsonl",
        "tb_responses": TB_DIR / "provider_responses.jsonl",
        "tb_repair_requests": TB_DIR / "transport_repair_v1/provider_requests.jsonl",
        "tb_repair_responses": TB_DIR / "transport_repair_v1/provider_responses.jsonl",
        "sarvam_requests": SARVAM_DIR / "provider_requests.jsonl",
        "sarvam_responses": SARVAM_DIR / "provider_responses.jsonl",
    }
    hashes = {name: sha_file(path) for name, path in paths.items()}
    requests = {r["provider_request_id"]: r for r in read_jsonl(paths["tb_requests"])}
    latest = {r["provider_request_id"]: r for r in read_jsonl(paths["tb_responses"])}
    tb_rows = []
    for key, response in latest.items():
        request = requests[key]
        if response.get("status") != "success" or not str(response.get("response_text", "")).strip():
            continue
        tb_rows.append({"request": request, "response": response})
    technical = len(requests) - len(tb_rows)
    if len(requests) != 400 or len(tb_rows) != 391 or technical != EXPECTED_TECHNICAL_OUTCOMES:
        raise ValueError("T-pro/Bielik latest-record assembly is not 391 responses plus 9 technical outcomes")

    s_requests = {r["provider_request_id"]: r for r in read_jsonl(paths["sarvam_requests"])}
    s_responses = {r["provider_request_id"]: r for r in read_jsonl(paths["sarvam_responses"])}
    if len(s_requests) != 200 or set(s_requests) != set(s_responses):
        raise ValueError("Sarvam pilot keys are incomplete")
    sarvam_rows = []
    for key, response in s_responses.items():
        if response.get("status") != "success" or not str(response.get("response_text", "")).strip():
            raise ValueError("Sarvam pilot contains a non-response")
        sarvam_rows.append({"request": s_requests[key], "response": response})
    rows = tb_rows + sarvam_rows
    if len(rows) != EXPECTED_RESPONSES:
        raise ValueError(f"expected {EXPECTED_RESPONSES} response-bearing records")
    keys = [(x["request"]["prompt_id"], x["request"]["prompt_language"], x["request"]["model"]) for x in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("combined subject-response keys are not unique")
    return rows, hashes


def prepare() -> dict:
    sources, source_hashes = load_sources()
    prompts, prompt_hashes = prompt_maps()
    input_hashes = {
        **source_hashes, **prompt_hashes, "v2_4_codebook": sha_file(CODEBOOK),
        "adopted_v2_4_prompt": sha_file(ADOPTED_PROMPT),
        "adopted_v2_4_schema": sha_file(ADOPTED_SCHEMA),
    }
    artifacts = {name: OUTPUT_DIR / name for name in (
        "response_index.parquet", "provider_requests.jsonl", "prompt.txt", "response_schema.json"
    )}
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("frozen annotation sources changed")
        for name, digest in manifest["artifact_sha256"].items():
            if sha_file(artifacts[name]) != digest:
                raise ValueError(f"frozen annotation artifact changed: {name}")
        return manifest

    codebook = json.loads(CODEBOOK.read_text())
    system, schema = _system_v24(codebook), _schema()
    schema_bytes = json.dumps(schema, indent=2).encode()
    if hashlib.sha256(system.encode()).hexdigest() != input_hashes["adopted_v2_4_prompt"]:
        raise ValueError("constructed prompt differs from adopted v2.4 prompt")
    if hashlib.sha256(schema_bytes).hexdigest() != input_hashes["adopted_v2_4_schema"]:
        raise ValueError("constructed schema differs from adopted v2.4 schema")
    encoder = tiktoken.get_encoding("o200k_base")
    requests, index = [], []
    for item in sorted(sources, key=lambda x: (
        x["request"]["model"], x["request"]["prompt_id"], x["request"]["prompt_language"]
    )):
        source, response = item["request"], item["response"]
        prompt_id, language = source["prompt_id"], source["prompt_language"]
        annotation_row = {
            "prompt_language": language,
            "prompt_text_en": prompts["en"][prompt_id]["text"],
            "prompt_text": prompts[language][prompt_id]["text"],
            "response_text": response["response_text"],
        }
        source_sha = sha_object(annotation_row)
        logical_id = sha_object({
            "response_key": [prompt_id, language, source["model"]],
            "source_sha256": source_sha,
            "version": "jurisdiction-pilot-luna-v2.4-v1",
        })[:24]
        user = _user(annotation_row, "source_response_only")
        request = {
            "logical_request_id": logical_id,
            "provider_request_id": sha_object({"logical_request_id": logical_id, "model_id": MODEL})[:24],
            "audit_response_id": logical_id,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_schema": schema,
            "estimated_input_tokens": len(encoder.encode(system + "\n" + user + "\n" + json.dumps(schema, sort_keys=True))),
            "model_id": MODEL, "provider": {"only": [PROVIDER], "allow_fallbacks": False},
            "reasoning": {"enabled": False, "exclude": True},
            "temperature": 0, "max_output_tokens": MAX_OUTPUT_TOKENS,
        }
        requests.append(request)
        metadata = source.get("prompt_metadata", {})
        index.append({
            "audit_response_id": logical_id, "provider_request_id": request["provider_request_id"],
            "source_sha256": source_sha, "prompt_id": prompt_id, "prompt_language": language,
            "subject_model": source["model"], "subject_model_id": source.get("model_id", source["model"]),
            "subject_provider_tag": source.get("provider_tag", "sarvam-native"),
            "generation_provider_request_id": source["provider_request_id"],
            "generation_response_sha256": hashlib.sha256(response["response_text"].encode()).hexdigest(),
            "pilot_band": source["pilot_band"], "estimated_input_tokens": request["estimated_input_tokens"],
            **metadata,
        })
    if len(requests) != EXPECTED_RESPONSES or len({r["provider_request_id"] for r in requests}) != EXPECTED_RESPONSES:
        raise ValueError("annotation request count or uniqueness failure")
    serialized = json.dumps([r["messages"] for r in requests], ensure_ascii=False)
    for forbidden in ("subject_model", "pilot_band", "sarvam-native", "featherless-ai", "publicai"):
        if forbidden in serialized:
            raise ValueError(f"local metadata leaked into annotation messages: {forbidden}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    pd.DataFrame(index).to_parquet(artifacts["response_index.parquet"], index=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    artifacts["prompt.txt"].write_text(system)
    artifacts["response_schema.json"].write_bytes(schema_bytes)
    manifest = {
        "version": "jurisdiction-pilot-luna-v2.4-v1", "created_at": now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": "blinded v2.4 annotation of 591 response-bearing jurisdiction-pilot records",
        "excluded_technical_generation_outcomes": EXPECTED_TECHNICAL_OUTCOMES,
        "input_mode": "source_response_only", "translation_used": False,
        "subject_model_blinded_in_messages": True, "selection_metadata_blinded_in_messages": True,
        "model_id": MODEL, "provider_tag": PROVIDER, "n_requests": EXPECTED_RESPONSES,
        "temperature": 0, "max_output_tokens": MAX_OUTPUT_TOKENS, "max_attempts": MAX_ATTEMPTS,
        "reasoning_disabled": True, "allow_fallbacks": False, "input_sha256": input_hashes,
        "artifact_sha256": {name: sha_file(path) for name, path in artifacts.items()},
        "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "paid_run_authorized": False, "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


def cost() -> dict:
    manifest = prepare()
    requests = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    tokens = sum(r["estimated_input_tokens"] for r in requests)
    planning = (tokens * INPUT_PRICE + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE) / 1e6
    reserve = (tokens * INPUT_PRICE + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE) / 1e6
    empirical = len(requests) * PRIOR_COST_PER_RESPONSE
    ceiling = math.ceil(max(planning * 1.5, empirical * 2) * 4) / 4
    result = {
        "version": "jurisdiction-pilot-luna-v2.4-cost-v1", "created_at": now(),
        "pricing_verified_at": PRICING_VERIFIED_AT, "pricing_source": PRICING_SOURCE,
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests), "estimated_input_tokens": tokens,
        "planning_output_tokens": len(requests) * PLANNING_OUTPUT_TOKENS,
        "maximum_output_tokens_single_attempt": len(requests) * MAX_OUTPUT_TOKENS,
        "planning_cost_usd": planning, "single_attempt_reserved_cost_usd": reserve,
        "empirical_cost_projection_usd": empirical, "suggested_hard_ceiling_usd": ceiling,
        "ceiling_rule": "round_up_to_$0.25(max(1.5*planning, 2*empirical))",
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False, "network_call_made": False,
    }
    (OUTPUT_DIR / "cost_estimate.json").write_text(json.dumps(result, indent=2))
    manifest["status"] = "frozen_costed_not_authorized"; manifest["cost_estimate"] = result
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return result


def authorize(payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed: raise RuntimeError("explicit user authorization confirmation is required")
    manifest = prepare(); estimate = cost()
    if payload_sha != manifest["provider_payload_sha256"]: raise ValueError("payload hash mismatch")
    if float(ceiling) != float(estimate["suggested_hard_ceiling_usd"]): raise ValueError("ceiling mismatch")
    record = {"recorded_at": now(), "user_authorized": True,
              "authorization_scope": "jurisdiction_pilot_luna_v2_4_v1",
              "provider_payload_sha256": payload_sha, "model_id": MODEL,
              "provider_tag": PROVIDER, "n_requests": EXPECTED_RESPONSES,
              "reasoning_disabled": True, "allow_fallbacks": False,
              "cost_ceiling_usd": float(ceiling)}
    manifest.update({"authorization": record, "paid_run_authorized": True, "status": "authorized_not_started"})
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return record


def summarize() -> dict:
    run_summary = json.loads((OUTPUT_DIR / "run_summary.json").read_text())
    results_path = OUTPUT_DIR / "results.jsonl"
    if not (
        run_summary.get("n_completed") == EXPECTED_RESPONSES
        and run_summary.get("n_incomplete") == 0
        and run_summary.get("schema_gate_pass") is True
        and run_summary.get("results_sha256") == sha_file(results_path)
    ):
        raise ValueError("Luna annotations are incomplete or hash-invalid")
    labels = _derive(pd.DataFrame(read_jsonl(results_path)))
    index = pd.read_parquet(OUTPUT_DIR / "response_index.parquet")
    frame = index.merge(labels, on="audit_response_id", validate="one_to_one")
    if frame["provider_request_id_x"].ne(frame["provider_request_id_y"]).any():
        raise ValueError("annotation request IDs disagree with response index")
    frame = frame.drop(columns="provider_request_id_y").rename(
        columns={"provider_request_id_x": "provider_request_id"}
    )
    frame["wrong_language"] = frame["language_fidelity"].eq("wrong_language")
    frame["mixed_language"] = frame["language_fidelity"].eq("mixed")
    frame["refusal_capability_overlap"] = (
        frame["pred_genuine_refusal"] & frame["pred_capability_failure"]
    )
    label_path = OUTPUT_DIR / "assembled_labels.parquet"
    frame.to_parquet(label_path, index=False)
    grouped = frame.groupby(["subject_model", "prompt_language"], dropna=False).agg(
        response_n=("audit_response_id", "size"),
        genuine_refusal_n=("pred_genuine_refusal", "sum"),
        genuine_refusal_rate=("pred_genuine_refusal", "mean"),
        capability_failure_n=("pred_capability_failure", "sum"),
        capability_failure_rate=("pred_capability_failure", "mean"),
        wrong_language_n=("wrong_language", "sum"),
        wrong_language_rate=("wrong_language", "mean"),
        mixed_language_n=("mixed_language", "sum"),
        overlap_n=("refusal_capability_overlap", "sum"),
    ).reset_index()
    counts_path = OUTPUT_DIR / "pilot_outcomes_by_model_language.csv"
    grouped.to_csv(counts_path, index=False)
    summary = {
        "version": "jurisdiction-pilot-luna-v2.4-summary-v1",
        "created_at": now(), "response_labels": len(frame),
        "excluded_generation_technical_outcomes": EXPECTED_TECHNICAL_OUTCOMES,
        "assembled_labels_sha256": sha_file(label_path),
        "cell_summary_sha256": sha_file(counts_path),
        "results_sha256": sha_file(results_path),
        "interpretation": "pilot diagnostics only; Luna classifications require the prespecified Sol audit",
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "run", "summarize"))
    parser.add_argument("--payload-sha"); parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare": result = prepare()
    elif args.command == "cost": result = cost()
    elif args.command == "authorize":
        if not args.payload_sha or args.cost_ceiling is None: parser.error("authorize requires hash and ceiling")
        result = authorize(args.payload_sha, args.cost_ceiling, args.confirm_user_authorization)
    elif args.command == "run":
        if args.cost_ceiling is None: parser.error("run requires --cost-ceiling")
        load_env_from_file(); result = run_luna_v24(ROOT, OUTPUT_DIR, min(args.workers, 32), args.cost_ceiling, args.authorize_paid_run)
    else: result = summarize()
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
