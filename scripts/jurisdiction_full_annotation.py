#!/usr/bin/env python3
"""Guarded Luna v2.4 annotation for completed jurisdiction full runs.

One immutable annotation contract is created per subject model. Only successful,
non-empty model responses are sent for classification; generation failures
remain separate technical outcomes in the full-run denominator.

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

GENERATION_BASE = ROOT / "annotations/model_expansion_v4/full_generation_v1"
ROSTER = ROOT / "config/model_rosters/openrouter_expansion_v1.json"
CODEBOOK = ROOT / "config/response_validity_decomposed_v2_4.json"
ADOPTED_PROMPT = ROOT / "annotations/response_validity_v2_4/wall_to_wall_luna_v1/prompt.txt"
ADOPTED_SCHEMA = ROOT / "annotations/response_validity_v2_4/wall_to_wall_luna_v1/response_schema.json"
MODELS = ("t-pro-it-2.0", "bielik-11b-v3.0", "sarvam-105b")
EXPECTED_REQUESTED = 12_480
PRIOR_COST_PER_RESPONSE = max(63.27810359000008 / 134_664, 0.7212165099999992 / 1_600)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def output_dir(model: str) -> Path:
    return GENERATION_BASE / model / "luna_v2_4_annotations_v1"


def prompt_maps() -> tuple[dict[str, dict[str, dict]], dict[str, str]]:
    roster = json.loads(ROSTER.read_text())
    maps, hashes = {}, {"prompt_roster": sha_file(ROSTER)}
    for language, spec in roster["design"]["prompt_files"].items():
        path = ROOT / spec["path"]
        if sha_file(path) != spec["sha256"]: raise ValueError(f"prompt hash mismatch: {language}")
        maps[language] = {r["id"]: r for r in json.loads(path.read_text())["prompts"]}
        hashes[f"prompt_{language}"] = spec["sha256"]
    return maps, hashes


def sources(model: str) -> tuple[list[dict], dict[str, str], int]:
    directory = GENERATION_BASE / model
    manifest_path = directory / "manifest.json"; request_path = directory / "provider_requests.jsonl"
    attempt_path = directory / "attempts.jsonl"; result_path = directory / "results.jsonl"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("status") != "completed" or not manifest.get("result"):
        raise ValueError(f"{model} generation is not complete")
    result = manifest["result"]
    if result.get("terminal_records") != EXPECTED_REQUESTED or result.get("results_sha256") != sha_file(result_path):
        raise ValueError(f"{model} generation manifest is incomplete or hash-invalid")
    requests = {r["provider_request_id"]: r for r in read_jsonl(request_path)}
    responses = read_jsonl(result_path)
    if len(requests) != EXPECTED_REQUESTED or len(responses) != result["successful_responses"]:
        raise ValueError("generation request/response counts disagree")
    if len({r["provider_request_id"] for r in responses}) != len(responses):
        raise ValueError("generation responses are not unique")
    rows = []
    for response in responses:
        request = requests[response["provider_request_id"]]
        if response.get("status") != "success" or not str(response.get("response_text", "")).strip():
            raise ValueError("results ledger contains a non-response")
        rows.append({"request": request, "response": response})
    hashes = {"generation_manifest": sha_file(manifest_path), "generation_requests": sha_file(request_path),
              "generation_attempts": sha_file(attempt_path), "generation_results": sha_file(result_path)}
    return rows, hashes, EXPECTED_REQUESTED - len(rows)


def prepare(model: str) -> dict:
    rows, generation_hashes, technical_n = sources(model); prompts, prompt_hashes = prompt_maps()
    out = output_dir(model); manifest_path = out / "manifest.json"
    input_hashes = {**generation_hashes, **prompt_hashes, "v2_4_codebook": sha_file(CODEBOOK),
                    "adopted_v2_4_prompt": sha_file(ADOPTED_PROMPT), "adopted_v2_4_schema": sha_file(ADOPTED_SCHEMA)}
    artifacts = {name: out / name for name in ("response_index.parquet", "provider_requests.jsonl", "prompt.txt", "response_schema.json")}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["input_sha256"] != input_hashes: raise ValueError("frozen annotation inputs changed")
        for name, digest in manifest["artifact_sha256"].items():
            if sha_file(artifacts[name]) != digest: raise ValueError(f"frozen annotation artifact changed: {name}")
        return manifest
    codebook = json.loads(CODEBOOK.read_text()); system, schema = _system_v24(codebook), _schema()
    schema_bytes = json.dumps(schema, indent=2).encode()
    if hashlib.sha256(system.encode()).hexdigest() != input_hashes["adopted_v2_4_prompt"]: raise ValueError("adopted prompt mismatch")
    if hashlib.sha256(schema_bytes).hexdigest() != input_hashes["adopted_v2_4_schema"]: raise ValueError("adopted schema mismatch")
    encoder = tiktoken.get_encoding("o200k_base"); requests_out, index = [], []
    for item in sorted(rows, key=lambda x: (x["request"]["prompt_id"], x["request"]["prompt_language"])):
        source, response = item["request"], item["response"]; prompt_id, language = source["prompt_id"], source["prompt_language"]
        annotation = {"prompt_language": language, "prompt_text_en": prompts["en"][prompt_id]["text"],
                      "prompt_text": prompts[language][prompt_id]["text"], "response_text": response["response_text"]}
        source_sha = sha_object(annotation); logical_id = sha_object({"response_key": [prompt_id, language, model],
            "source_sha256": source_sha, "version": f"{model}-full-luna-v2.4-v1"})[:24]
        user = _user(annotation, "source_response_only")
        request = {"logical_request_id": logical_id,
                   "provider_request_id": sha_object({"logical_request_id": logical_id, "model_id": MODEL})[:24],
                   "audit_response_id": logical_id,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                   "response_schema": schema,
                   "estimated_input_tokens": len(encoder.encode(system + "\n" + user + "\n" + json.dumps(schema, sort_keys=True))),
                   "model_id": MODEL, "provider": {"only": [PROVIDER], "allow_fallbacks": False},
                   "reasoning": {"enabled": False, "exclude": True}, "temperature": 0,
                   "max_output_tokens": MAX_OUTPUT_TOKENS}
        requests_out.append(request)
        index.append({"audit_response_id": logical_id, "provider_request_id": request["provider_request_id"],
                      "source_sha256": source_sha, "prompt_id": prompt_id, "prompt_language": language,
                      "subject_model": model, "subject_model_id": source["model_id"],
                      "subject_provider_tag": source["provider_tag"],
                      "generation_provider_request_id": source["provider_request_id"],
                      "generation_response_sha256": hashlib.sha256(response["response_text"].encode()).hexdigest(),
                      "estimated_input_tokens": request["estimated_input_tokens"], **source["prompt_metadata"]})
    if len(requests_out) != len(rows) or len({r["provider_request_id"] for r in requests_out}) != len(rows):
        raise ValueError("annotation count or uniqueness failure")
    serialized = json.dumps([r["messages"] for r in requests_out], ensure_ascii=False)
    # The response itself may name its model, so identity cannot be inferred from
    # response text and must not be treated as a metadata leak.  What we exclude
    # here are repository-only field names that would reveal our local design.
    for forbidden in ("subject_model", "provider_tag", "pilot_band"):
        if forbidden in serialized: raise ValueError(f"metadata leaked into Luna messages: {forbidden}")
    out.mkdir(parents=True, exist_ok=False); pd.DataFrame(index).to_parquet(artifacts["response_index.parquet"], index=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests_out); artifacts["prompt.txt"].write_text(system); artifacts["response_schema.json"].write_bytes(schema_bytes)
    manifest = {"version": "jurisdiction-full-luna-v2.4-v1", "created_at": now(), "status": "frozen_unpriced_not_authorized",
                "scientific_role": f"blinded v2.4 annotation of completed {model} full responses", "subject_model": model,
                "requested_generation_n": EXPECTED_REQUESTED, "n_requests": len(rows), "excluded_generation_technical_outcomes": technical_n,
                "input_mode": "source_response_only", "translation_used": False, "subject_model_blinded_in_messages": True,
                "model_id": MODEL, "provider_tag": PROVIDER, "temperature": 0, "max_output_tokens": MAX_OUTPUT_TOKENS,
                "max_attempts": MAX_ATTEMPTS, "reasoning_disabled": True, "allow_fallbacks": False,
                "input_sha256": input_hashes, "artifact_sha256": {n: sha_file(p) for n,p in artifacts.items()},
                "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]), "paid_run_authorized": False, "network_call_made": False}
    manifest_path.write_text(json.dumps(manifest, indent=2)); return manifest


def cost(model: str) -> dict:
    manifest = prepare(model); requests = read_jsonl(output_dir(model) / "provider_requests.jsonl"); inputs = sum(r["estimated_input_tokens"] for r in requests)
    planning = (inputs * INPUT_PRICE + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE) / 1e6
    reserve = (inputs * INPUT_PRICE + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE) / 1e6
    empirical = len(requests) * PRIOR_COST_PER_RESPONSE; ceiling = math.ceil(max(planning*1.5, empirical*2)*4)/4
    result = {"version": "jurisdiction-full-luna-v2.4-cost-v1", "created_at": now(), "subject_model": model,
              "pricing_verified_at": PRICING_VERIFIED_AT, "pricing_source": PRICING_SOURCE,
              "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE}, "requests": len(requests),
              "estimated_input_tokens": inputs, "planning_cost_usd": planning, "single_attempt_reserved_cost_usd": reserve,
              "empirical_cost_projection_usd": empirical, "suggested_hard_ceiling_usd": ceiling,
              "provider_payload_sha256": manifest["provider_payload_sha256"], "paid_run_authorized": False, "network_call_made": False}
    (output_dir(model)/"cost_estimate.json").write_text(json.dumps(result, indent=2)); manifest["status"]="frozen_costed_not_authorized"; manifest["cost_estimate"]=result
    (output_dir(model)/"manifest.json").write_text(json.dumps(manifest, indent=2)); return result


def authorize(model: str, payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed: raise RuntimeError("explicit user authorization required")
    manifest=prepare(model); estimate=cost(model)
    if payload_sha != manifest["provider_payload_sha256"]: raise ValueError("payload hash mismatch")
    if float(ceiling) != float(estimate["suggested_hard_ceiling_usd"]): raise ValueError("ceiling mismatch")
    record={"recorded_at":now(),"user_authorized":True,"subject_model":model,"provider_payload_sha256":payload_sha,
            "model_id":MODEL,"provider_tag":PROVIDER,"n_requests":manifest["n_requests"],"cost_ceiling_usd":ceiling,
            "reasoning_disabled":True,"allow_fallbacks":False}
    manifest.update({"authorization":record,"paid_run_authorized":True,"status":"authorized_not_started"}); (output_dir(model)/"manifest.json").write_text(json.dumps(manifest,indent=2)); return record


def summarize(model: str) -> dict:
    out=output_dir(model); run=json.loads((out/"run_summary.json").read_text()); results_path=out/"results.jsonl"; manifest=json.loads((out/"manifest.json").read_text())
    if run.get("n_completed")!=manifest["n_requests"] or run.get("n_incomplete")!=0 or not run.get("schema_gate_pass") or run.get("results_sha256")!=sha_file(results_path): raise ValueError("annotations incomplete")
    labels=_derive(pd.DataFrame(read_jsonl(results_path))); index=pd.read_parquet(out/"response_index.parquet"); frame=index.merge(labels,on="audit_response_id",validate="one_to_one")
    path=out/"assembled_labels.parquet"; frame.to_parquet(path,index=False)
    summary={"version":"jurisdiction-full-luna-v2.4-summary-v1","created_at":now(),"subject_model":model,"response_labels":len(frame),
             "excluded_generation_technical_outcomes":manifest["excluded_generation_technical_outcomes"],"genuine_refusal_n":int(frame.pred_genuine_refusal.sum()),
             "capability_failure_n":int(frame.pred_capability_failure.sum()),"assembled_labels_sha256":sha_file(path),"results_sha256":sha_file(results_path)}
    (out/"summary.json").write_text(json.dumps(summary,indent=2)); return summary


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("command",choices=("prepare","cost","authorize","run","summarize")); parser.add_argument("--model",choices=MODELS,required=True)
    parser.add_argument("--payload-sha"); parser.add_argument("--cost-ceiling",type=float); parser.add_argument("--workers",type=int,default=32)
    parser.add_argument("--confirm-user-authorization",action="store_true"); parser.add_argument("--authorize-paid-run",action="store_true"); args=parser.parse_args()
    if args.command=="prepare": result=prepare(args.model)
    elif args.command=="cost": result=cost(args.model)
    elif args.command=="authorize":
        if not args.payload_sha or args.cost_ceiling is None: parser.error("authorize requires hash and ceiling")
        result=authorize(args.model,args.payload_sha,args.cost_ceiling,args.confirm_user_authorization)
    elif args.command=="run":
        if args.cost_ceiling is None: parser.error("run requires ceiling")
        load_env_from_file(); result=run_luna_v24(ROOT,output_dir(args.model),min(args.workers,32),args.cost_ceiling,args.authorize_paid_run)
    else: result=summarize(args.model)
    print(json.dumps(result,indent=2))


if __name__=="__main__": main()
