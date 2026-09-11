#!/usr/bin/env python3
"""Guarded Sol v2.4 audit of the 400-response Torch benchmark.

The audit is a census of every Luna-flagged capability failure, refusal,
wrong-language output or refusal-unassessable record, plus a deterministic
probability sample of up to ten remaining records per model-language cell. Sol sees
the exact Luna messages and schema, not Luna's labels or selection metadata.

Technical record: docs/HPC_LOCAL_GGUF_FULL_V1.md
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from env_utils import load_env_from_file
from jurisdiction_pilot_sol_audit import binary_metrics, weighted_kappa
from refusal_audit.model_expansion.openrouter_pilot import read_jsonl, sha_object, write_jsonl
from refusal_audit.response_validity.human_pilot import sha_file
from refusal_audit.response_validity.luna_v23_repair import _derive
from refusal_audit.response_validity.luna_v24_evaluation import (
    MAX_ATTEMPTS, MAX_OUTPUT_TOKENS, PLANNING_OUTPUT_TOKENS,
)
from refusal_audit.response_validity.sol_v24_evaluation import (
    INPUT_PRICE, MODEL, OUTPUT_PRICE, PRICING_SOURCE, PRICING_VERIFIED_AT,
    PROVIDER, run_sol_v24,
)

LUNA_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_hpc_benchmark_luna_v2_4_v1"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_hpc_benchmark_sol_v2_4_audit_v1"
SELECTION_SEED = "local-gguf-hpc-benchmark-sol-audit-v1-20260911"
CLEAN_PER_CELL = 10
EXPECTED_POPULATION = 400
EXPECTED_FLAGGED = 110
EXPECTED_CLEAN_SAMPLE = 161
EXPECTED_REQUESTS = 271


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def select() -> pd.DataFrame:
    """Select all flagged records and weighted clean controls."""
    frame = pd.read_parquet(LUNA_DIR / "assembled_labels.parquet")
    if len(frame) != EXPECTED_POPULATION or frame["audit_response_id"].duplicated().any():
        raise ValueError("Luna frame is not the frozen 400-response benchmark")
    frame["luna_flagged"] = (
        frame["pred_genuine_refusal"]
        | frame["pred_capability_failure"]
        | frame["language_fidelity"].eq("wrong_language")
        | frame["substantive_refusal"].eq("unassessable")
    )
    frame["selection_stratum"] = "luna_flagged_census"
    frame["selection_probability"] = 1.0
    flagged = frame.loc[frame["luna_flagged"]].copy()
    clean_parts = []
    for _, part in frame.loc[~frame["luna_flagged"]].groupby(
        ["subject_model", "prompt_language"], sort=True
    ):
        n = len(part)
        take = min(CLEAN_PER_CELL, n)
        part = part.copy()
        part["selection_rank"] = part["audit_response_id"].map(
            lambda value: hashlib.sha256(f"{SELECTION_SEED}|{value}".encode()).hexdigest()
        )
        chosen = part.sort_values("selection_rank", kind="mergesort").head(take).copy()
        chosen["selection_stratum"] = "apparently_clean_probability_sample"
        chosen["selection_probability"] = take / n
        clean_parts.append(chosen)
    clean = pd.concat(clean_parts, ignore_index=True)
    selected = pd.concat([flagged, clean], ignore_index=True)
    selected["design_weight"] = 1 / selected["selection_probability"]
    if len(flagged) != EXPECTED_FLAGGED or len(clean) != EXPECTED_CLEAN_SAMPLE:
        raise ValueError("Sol audit selection count changed")
    if len(selected) != EXPECTED_REQUESTS or selected["audit_response_id"].duplicated().any():
        raise ValueError("Sol audit selection is not unique and complete")
    if abs(float(selected["design_weight"].sum()) - EXPECTED_POPULATION) > 1e-8:
        raise ValueError("design weights do not reconstruct the benchmark")
    return selected.sort_values("audit_response_id", kind="mergesort").reset_index(drop=True)


def prepare() -> dict:
    source_paths = {
        "luna_manifest": LUNA_DIR / "manifest.json",
        "luna_payload": LUNA_DIR / "provider_requests.jsonl",
        "luna_response_index": LUNA_DIR / "response_index.parquet",
        "luna_results": LUNA_DIR / "results.jsonl",
        "luna_run_summary": LUNA_DIR / "run_summary.json",
        "luna_assembled_labels": LUNA_DIR / "assembled_labels.parquet",
    }
    input_hashes = {name: sha_file(path) for name, path in source_paths.items()}
    artifacts = {name: OUTPUT_DIR / name for name in (
        "provider_requests.jsonl", "response_index.parquet", "prompt.txt", "response_schema.json"
    )}
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["input_sha256"] != input_hashes:
            raise ValueError("frozen Sol audit inputs changed")
        for name, digest in manifest["artifact_sha256"].items():
            if sha_file(artifacts[name]) != digest:
                raise ValueError(f"frozen Sol audit artifact changed: {name}")
        return manifest

    selected = select()
    luna_requests = {row["audit_response_id"]: row for row in read_jsonl(source_paths["luna_payload"])}
    requests, id_map = [], {}
    for audit_id in selected["audit_response_id"]:
        source = luna_requests[audit_id]
        request = dict(source)
        provider_id = sha_object({"logical_request_id": source["logical_request_id"], "model_id": MODEL})[:24]
        request.update({
            "provider_request_id": provider_id,
            "model_id": MODEL,
            "provider": {"only": [PROVIDER], "allow_fallbacks": False},
            "reasoning": {"enabled": False, "exclude": True},
            "temperature": 0,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        })
        if source["messages"] != request["messages"] or source["response_schema"] != request["response_schema"]:
            raise ValueError("Sol request changed the Luna messages or schema")
        requests.append(request)
        id_map[audit_id] = provider_id
    selected["luna_provider_request_id"] = selected["provider_request_id"]
    selected["provider_request_id"] = selected["audit_response_id"].map(id_map)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    selected.to_parquet(artifacts["response_index.parquet"], index=False)
    artifacts["prompt.txt"].write_bytes((LUNA_DIR / "prompt.txt").read_bytes())
    artifacts["response_schema.json"].write_bytes((LUNA_DIR / "response_schema.json").read_bytes())
    manifest = {
        "version": "local-gguf-hpc-benchmark-sol-v2.4-audit-v1",
        "created_at": now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": "frontier verification of every Luna flag plus weighted clean controls",
        "selection": {
            "seed": SELECTION_SEED,
            "population_n": EXPECTED_POPULATION,
            "flagged_census_n": EXPECTED_FLAGGED,
            "flag_definition": "refusal or capability failure or wrong language or refusal unassessable",
            "all_capability_failures_included": True,
            "clean_sample_n": EXPECTED_CLEAN_SAMPLE,
            "clean_sample_rule": "up to 10 per model-language cell",
            "design_weights_retained": True,
        },
        "n_requests": EXPECTED_REQUESTS,
        "input_mode": "source_response_only",
        "messages_byte_identical_to_luna": True,
        "response_schema_identical_to_luna": True,
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
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


def cost() -> dict:
    manifest = prepare()
    requests = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    inputs = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (inputs * INPUT_PRICE + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE) / 1e6
    reserve = (inputs * INPUT_PRICE + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE) / 1e6
    ceiling = math.ceil(max(planning * 1.5, reserve * 1.25) * 2) / 2
    result = {
        "version": "local-gguf-hpc-benchmark-sol-v2.4-audit-cost-v1",
        "created_at": now(),
        "pricing_verified_at": PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests),
        "estimated_input_tokens": inputs,
        "planning_output_tokens": len(requests) * PLANNING_OUTPUT_TOKENS,
        "maximum_output_tokens_single_attempt": len(requests) * MAX_OUTPUT_TOKENS,
        "planning_cost_usd": planning,
        "single_attempt_reserved_cost_usd": reserve,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (OUTPUT_DIR / "cost_estimate.json").write_text(json.dumps(result, indent=2))
    manifest["status"] = "frozen_costed_not_authorized"
    manifest["cost_estimate"] = result
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return result


def authorize(payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest, estimate = prepare(), cost()
    if payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("payload hash mismatch")
    if float(ceiling) != float(estimate["suggested_hard_ceiling_usd"]):
        raise ValueError("ceiling mismatch")
    record = {
        "recorded_at": now(),
        "user_authorized": True,
        "authorization_scope": "local_gguf_hpc_benchmark_sol_v2_4_audit_v1",
        "provider_payload_sha256": payload_sha,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_REQUESTS,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest.update({"authorization": record, "paid_run_authorized": True, "status": "authorized_not_started"})
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return record


def score() -> dict:
    run_summary = json.loads((OUTPUT_DIR / "run_summary.json").read_text())
    results_path = OUTPUT_DIR / "results.jsonl"
    if not (
        run_summary.get("n_completed") == EXPECTED_REQUESTS
        and run_summary.get("n_incomplete") == 0
        and run_summary.get("schema_gate_pass") is True
        and run_summary.get("results_sha256") == sha_file(results_path)
    ):
        raise ValueError("Sol audit is incomplete or hash-invalid")
    index = pd.read_parquet(OUTPUT_DIR / "response_index.parquet")
    sol = _derive(pd.DataFrame(read_jsonl(results_path)))
    frame = index.merge(sol, on="audit_response_id", validate="one_to_one", suffixes=("_luna", "_sol"))
    if abs(float(frame["design_weight"].sum()) - EXPECTED_POPULATION) > 1e-8:
        raise ValueError("audit weights do not reconstruct the benchmark")
    comparison_path = OUTPUT_DIR / "luna_sol_comparison.parquet"
    frame.to_parquet(comparison_path, index=False)
    dimensions = [
        "language_fidelity", "output_quality", "technical_failure", "task_behavior",
        "substantive_refusal", "stance_disclaimer", "epistemic_limitation",
        "pred_genuine_refusal", "pred_capability_failure",
    ]
    agreement_rows = []
    for field in dimensions:
        agreement, kappa = weighted_kappa(frame, f"{field}_luna", f"{field}_sol")
        agreement_rows.append({
            "field": field,
            "audit_n": len(frame),
            "weighted_population_n": frame["design_weight"].sum(),
            "design_weighted_agreement": agreement,
            "design_weighted_kappa": kappa,
            "unweighted_disagreement_n": int(frame[f"{field}_luna"].ne(frame[f"{field}_sol"]).sum()),
        })
    agreement_path = OUTPUT_DIR / "design_weighted_agreement.csv"
    pd.DataFrame(agreement_rows).to_csv(agreement_path, index=False)
    frame["wrong_language_luna"] = frame["language_fidelity_luna"].eq("wrong_language")
    frame["wrong_language_sol"] = frame["language_fidelity_sol"].eq("wrong_language")
    outcomes = {
        field: binary_metrics(frame, f"{field}_luna", f"{field}_sol")
        for field in ("pred_genuine_refusal", "pred_capability_failure", "wrong_language")
    }
    cell_rows = []
    for (model, language), part in frame.groupby(["subject_model", "prompt_language"], sort=True):
        total = float(part["design_weight"].sum())
        row = {
            "subject_model": model,
            "prompt_language": language,
            "audit_n": len(part),
            "weighted_population_n": total,
        }
        for outcome in ("pred_genuine_refusal", "pred_capability_failure", "wrong_language"):
            for judge in ("luna", "sol"):
                field = f"{outcome}_{judge}"
                row[f"{outcome}_{judge}_rate"] = float(
                    (part["design_weight"] * part[field].astype(int)).sum() / total
                )
        cell_rows.append(row)
    cells_path = OUTPUT_DIR / "design_weighted_model_language_estimates.csv"
    pd.DataFrame(cell_rows).to_csv(cells_path, index=False)
    summary = {
        "version": "local-gguf-hpc-benchmark-sol-v2.4-audit-summary-v1",
        "created_at": now(),
        "audit_n": len(frame),
        "weighted_population_n": float(frame["design_weight"].sum()),
        "flagged_census_n": int(frame["luna_flagged"].sum()),
        "clean_probability_sample_n": int((~frame["luna_flagged"]).sum()),
        "binary_outcomes": outcomes,
        "provider_cost_usd": run_summary["provider_cost_usd"],
        "artifact_sha256": {
            comparison_path.name: sha_file(comparison_path),
            agreement_path.name: sha_file(agreement_path),
            cells_path.name: sha_file(cells_path),
            results_path.name: sha_file(results_path),
        },
        "interpretation": "Sol is a frontier-model reference, not human ground truth; weights reconstruct the 400-response benchmark.",
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "cost", "authorize", "run", "score"))
    parser.add_argument("--payload-sha")
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare()
    elif args.command == "cost":
        result = cost()
    elif args.command == "authorize":
        if not args.payload_sha or args.cost_ceiling is None:
            parser.error("authorize requires hash and ceiling")
        result = authorize(args.payload_sha, args.cost_ceiling, args.confirm_user_authorization)
    elif args.command == "run":
        if args.cost_ceiling is None:
            parser.error("run requires --cost-ceiling")
        load_env_from_file()
        result = run_sol_v24(
            ROOT, OUTPUT_DIR, min(args.workers, 32), args.cost_ceiling, args.authorize_paid_run
        )
    else:
        result = score()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
