#!/usr/bin/env python3
"""Probability-based Sol v2.4 audit of the four Torch full-corpus models.

The audit includes every Luna-coded genuine refusal and every response whose
refusal status is unassessable. It then draws independent deterministic simple
random samples within each model-language cell from (a) assessable capability
failures not already selected and (b) apparently clean non-refusals. Inclusion
probabilities and inverse-probability weights reconstruct all 49,879 returned
responses. Sol sees the exact Luna messages and schema, never Luna's labels or
the selection stratum.

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
    MAX_ATTEMPTS,
    MAX_OUTPUT_TOKENS,
    PLANNING_OUTPUT_TOKENS,
)
from refusal_audit.response_validity.sol_v24_evaluation import (
    INPUT_PRICE,
    MODEL,
    OUTPUT_PRICE,
    PRICING_SOURCE,
    PROVIDER,
    run_sol_v24,
)

LUNA_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_full_hpc_luna_v2_4_v1"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/local_gguf_full_hpc_sol_v2_4_audit_v1"
SELECTION_SEED = "local-gguf-hpc-full-sol-audit-v1-20260912"
SAMPLED_PER_CELL_STRATUM = 20
EXPECTED_POPULATION = 49_879
EXPECTED_REFUSAL_CENSUS = 381
EXPECTED_UNASSESSABLE_CENSUS = 271
EXPECTED_CAPABILITY_SAMPLE = 298
EXPECTED_CLEAN_SAMPLE = 385
EXPECTED_REQUESTS = (
    EXPECTED_REFUSAL_CENSUS
    + EXPECTED_UNASSESSABLE_CENSUS
    + EXPECTED_CAPABILITY_SAMPLE
    + EXPECTED_CLEAN_SAMPLE
)
PRICING_VERIFIED_AT = "2026-09-12"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def deterministic_sample(part: pd.DataFrame, take: int, stratum: str) -> pd.DataFrame:
    """Draw a reproducible equal-probability sample using a hash-based ranking."""
    part = part.copy()
    n = len(part)
    take = min(take, n)
    part["selection_rank"] = part["audit_response_id"].map(
        lambda value: hashlib.sha256(
            f"{SELECTION_SEED}|{stratum}|{value}".encode("utf-8")
        ).hexdigest()
    )
    chosen = part.sort_values("selection_rank", kind="mergesort").head(take).copy()
    chosen["selection_stratum"] = stratum
    chosen["stratum_population_n"] = n
    chosen["stratum_sample_n"] = take
    chosen["selection_probability"] = take / n
    return chosen


def select() -> pd.DataFrame:
    """Create four mutually exclusive audit strata covering the full population."""
    frame = pd.read_parquet(LUNA_DIR / "assembled_labels.parquet")
    keys = ["prompt_id", "prompt_language", "subject_model"]
    if len(frame) != EXPECTED_POPULATION or frame.duplicated(keys).any():
        raise ValueError("final Torch Luna frame is not 49,879 unique response keys")
    frame["luna_refusal_unassessable"] = frame["substantive_refusal"].eq("unassessable")

    refusal = frame.loc[frame["pred_genuine_refusal"]].copy()
    unassessable = frame.loc[
        ~frame["pred_genuine_refusal"] & frame["luna_refusal_unassessable"]
    ].copy()
    census_parts: list[pd.DataFrame] = []
    for census, base_stratum in (
        (refusal, "luna_genuine_refusal_census"),
        (unassessable, "luna_refusal_unassessable_census"),
    ):
        for (model, language), cell in census.groupby(
            ["subject_model", "prompt_language"], sort=True
        ):
            cell = cell.copy()
            cell["selection_stratum"] = f"{base_stratum}|{model}|{language}"
            cell["stratum_population_n"] = len(cell)
            cell["stratum_sample_n"] = len(cell)
            cell["selection_probability"] = 1.0
            census_parts.append(cell)

    remaining = frame.loc[
        ~frame["pred_genuine_refusal"] & ~frame["luna_refusal_unassessable"]
    ].copy()
    sampled_parts: list[pd.DataFrame] = []
    for (model, language), cell in remaining.groupby(
        ["subject_model", "prompt_language"], sort=True
    ):
        for capability, stratum in (
            (True, "luna_capability_failure_probability_sample"),
            (False, "luna_apparently_clean_probability_sample"),
        ):
            pool = cell.loc[cell["pred_capability_failure"].eq(capability)]
            if pool.empty:
                continue
            sampled_parts.append(deterministic_sample(
                pool, SAMPLED_PER_CELL_STRATUM,
                f"{stratum}|{model}|{language}",
            ))
    sampled = pd.concat(sampled_parts, ignore_index=True)
    selected = pd.concat(census_parts + [sampled], ignore_index=True)
    selected["design_weight"] = 1.0 / selected["selection_probability"]
    selected["selection_cell"] = (
        selected["subject_model"].astype(str) + "|" + selected["prompt_language"].astype(str)
    )
    expected = {
        "luna_genuine_refusal_census": EXPECTED_REFUSAL_CENSUS,
        "luna_refusal_unassessable_census": EXPECTED_UNASSESSABLE_CENSUS,
        "luna_capability_failure_probability_sample": EXPECTED_CAPABILITY_SAMPLE,
        "luna_apparently_clean_probability_sample": EXPECTED_CLEAN_SAMPLE,
    }
    # Sampling strata carry the cell suffix after a pipe. Compare their base name.
    observed = {}
    for value, count in selected["selection_stratum"].value_counts().items():
        observed[value.split("|")[0]] = observed.get(value.split("|")[0], 0) + int(count)
    if observed != expected:
        raise ValueError(f"Sol audit selection counts changed: {observed}")
    if len(selected) != EXPECTED_REQUESTS or selected["audit_response_id"].duplicated().any():
        raise ValueError("Sol audit selection is not unique or has the wrong size")
    if abs(float(selected["design_weight"].sum()) - EXPECTED_POPULATION) > 1e-6:
        raise ValueError("audit weights do not reconstruct the response population")
    return selected.sort_values("audit_response_id", kind="mergesort").reset_index(drop=True)


def prepare() -> dict:
    source_paths = {
        "luna_manifest": LUNA_DIR / "manifest.json",
        "luna_payload": LUNA_DIR / "provider_requests.jsonl",
        "luna_response_index": LUNA_DIR / "response_index.parquet",
        "luna_main_results": LUNA_DIR / "results.jsonl",
        "luna_main_run_summary": LUNA_DIR / "run_summary.json",
        "luna_final_results": LUNA_DIR / "final_results.jsonl",
        "luna_final_labels": LUNA_DIR / "assembled_labels.parquet",
        "luna_final_manifest": LUNA_DIR / "final_annotations_manifest.json",
    }
    input_hashes = {name: sha_file(path) for name, path in source_paths.items()}
    artifacts = {name: OUTPUT_DIR / name for name in (
        "provider_requests.jsonl", "response_index.parquet", "prompt.txt",
        "response_schema.json",
    )}
    manifest_path = OUTPUT_DIR / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen Sol audit inputs changed")
        for name, digest in manifest.get("artifact_sha256", {}).items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != digest:
                raise ValueError(f"frozen Sol audit artifact changed: {name}")
        return manifest

    selected = select()
    luna_requests = {
        str(row["audit_response_id"]): row
        for row in read_jsonl(source_paths["luna_payload"])
    }
    requests: list[dict] = []
    id_map: dict[str, str] = {}
    for audit_id in selected["audit_response_id"].astype(str):
        source = luna_requests[audit_id]
        request = dict(source)
        provider_id = sha_object({
            "logical_request_id": source["logical_request_id"], "model_id": MODEL,
        })[:24]
        request.update({
            "provider_request_id": provider_id,
            "model_id": MODEL,
            "provider": {"only": [PROVIDER], "allow_fallbacks": False},
            "reasoning": {"enabled": False, "exclude": True},
            "temperature": 0,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        })
        if request["messages"] != source["messages"] or request["response_schema"] != source["response_schema"]:
            raise ValueError("Sol request changed the Luna messages or schema")
        requests.append(request)
        id_map[audit_id] = provider_id
    selected["luna_provider_request_id"] = selected["provider_request_id"]
    selected["provider_request_id"] = selected["audit_response_id"].astype(str).map(id_map)
    if selected["provider_request_id"].isna().any():
        raise ValueError("not every audit case maps to a Sol provider request")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    selected.to_parquet(artifacts["response_index.parquet"], index=False)
    artifacts["prompt.txt"].write_bytes((LUNA_DIR / "prompt.txt").read_bytes())
    artifacts["response_schema.json"].write_bytes((LUNA_DIR / "response_schema.json").read_bytes())
    manifest = {
        "version": "local-gguf-hpc-full-sol-v2.4-audit-v1",
        "created_at": now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": "frontier distribution-shift audit of the complete Torch Luna v2.4 labels",
        "selection": {
            "seed": SELECTION_SEED,
            "population_n": EXPECTED_POPULATION,
            "refusal_census_n": EXPECTED_REFUSAL_CENSUS,
            "unassessable_census_n": EXPECTED_UNASSESSABLE_CENSUS,
            "capability_failure_sample_n": EXPECTED_CAPABILITY_SAMPLE,
            "apparently_clean_sample_n": EXPECTED_CLEAN_SAMPLE,
            "sample_rule": "up to 20 per model-language cell in each sampled stratum",
            "design_weights_retained": True,
        },
        "n_requests": EXPECTED_REQUESTS,
        "input_mode": "source_response_only",
        "messages_byte_identical_to_luna": True,
        "response_schema_identical_to_luna": True,
        "luna_labels_blinded_in_messages": True,
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


def cost() -> dict:
    manifest = prepare()
    requests = read_jsonl(OUTPUT_DIR / "provider_requests.jsonl")
    input_tokens = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (
        input_tokens * INPUT_PRICE
        + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1e6
    reserve = (
        input_tokens * INPUT_PRICE
        + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1e6
    ceiling = math.ceil(max(planning * 1.5, reserve * 1.25) * 2) / 2
    result = {
        "version": "local-gguf-hpc-full-sol-v2.4-audit-cost-v1",
        "created_at": now(),
        "pricing_verified_at": PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "discount_status": "OpenRouter versioned page reports 50% off",
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests),
        "estimated_input_tokens": input_tokens,
        "planning_output_tokens": len(requests) * PLANNING_OUTPUT_TOKENS,
        "maximum_output_tokens_single_attempt": len(requests) * MAX_OUTPUT_TOKENS,
        "planning_cost_usd": planning,
        "single_attempt_reserved_cost_usd": reserve,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (OUTPUT_DIR / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    manifest["status"] = "frozen_costed_not_authorized"
    manifest["cost_estimate"] = result
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return result


def authorize(payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest, estimate = prepare(), cost()
    if payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("payload hash mismatch")
    if float(ceiling) != float(estimate["suggested_hard_ceiling_usd"]):
        raise ValueError("cost ceiling mismatch")
    record = {
        "recorded_at": now(),
        "user_authorized": True,
        "authorization_scope": "local_gguf_hpc_full_sol_v2_4_audit_v1",
        "provider_payload_sha256": payload_sha,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_REQUESTS,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest.update({
        "authorization": record,
        "paid_run_authorized": True,
        "status": "authorized_not_started",
    })
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return record


def design_mean_and_se(part: pd.DataFrame, value: str, bounded: bool = True) -> dict:
    """Stratified SRSWOR mean and standard error for a numeric audit variable."""
    total_n = 0.0
    total_y = 0.0
    total_variance = 0.0
    for _, stratum in part.groupby("selection_stratum", sort=False):
        n_h = len(stratum)
        N_h = float(stratum["stratum_population_n"].iloc[0])
        if stratum["stratum_population_n"].nunique() != 1:
            raise ValueError("stratum population size is inconsistent")
        values = stratum[value].astype(float)
        total_n += N_h
        total_y += N_h * float(values.mean())
        if n_h > 1 and n_h < N_h:
            total_variance += N_h ** 2 * (1 - n_h / N_h) * float(values.var(ddof=1)) / n_h
    estimate = total_y / total_n
    se = math.sqrt(total_variance) / total_n
    result = {
        "estimate": estimate,
        "standard_error": se,
        "ci_low": estimate - 1.96 * se,
        "ci_high": estimate + 1.96 * se,
    }
    if bounded:
        result["ci_low"] = max(0.0, result["ci_low"])
        result["ci_high"] = min(1.0, result["ci_high"])
    return result


def score() -> dict:
    final_summary_path = OUTPUT_DIR / "final_annotations_manifest.json"
    if final_summary_path.exists():
        run_summary = json.loads(final_summary_path.read_text(encoding="utf-8"))
        results_path = OUTPUT_DIR / "final_results.jsonl"
        expected_digest = run_summary.get("final_results_sha256")
    else:
        run_summary = json.loads((OUTPUT_DIR / "run_summary.json").read_text(encoding="utf-8"))
        results_path = OUTPUT_DIR / "results.jsonl"
        expected_digest = run_summary.get("results_sha256")
    if not (
        run_summary.get("n_completed") == EXPECTED_REQUESTS
        and run_summary.get("n_incomplete") == 0
        and run_summary.get("schema_gate_pass") is True
        and expected_digest == sha_file(results_path)
    ):
        raise ValueError("Sol audit is incomplete or hash-invalid")
    index = pd.read_parquet(OUTPUT_DIR / "response_index.parquet")
    sol = _derive(pd.DataFrame(read_jsonl(results_path)))
    frame = index.merge(
        sol, on="audit_response_id", validate="one_to_one", suffixes=("_luna", "_sol")
    )
    if abs(float(frame["design_weight"].sum()) - EXPECTED_POPULATION) > 1e-6:
        raise ValueError("audit weights do not reconstruct the response population")
    frame["wrong_language_luna"] = frame["language_fidelity_luna"].eq("wrong_language")
    frame["wrong_language_sol"] = frame["language_fidelity_sol"].eq("wrong_language")
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
            "unweighted_disagreement_n": int(
                frame[f"{field}_luna"].ne(frame[f"{field}_sol"]).sum()
            ),
        })
    agreement_path = OUTPUT_DIR / "design_weighted_agreement.csv"
    pd.DataFrame(agreement_rows).to_csv(agreement_path, index=False)

    outcomes = {
        field: binary_metrics(frame, f"{field}_luna", f"{field}_sol")
        for field in ("pred_genuine_refusal", "pred_capability_failure", "wrong_language")
    }
    estimate_rows = []
    models = sorted(frame["subject_model"].unique())
    languages = sorted(frame["prompt_language"].unique())
    scopes = (
        [(None, None)]
        + [(model, None) for model in models]
        + [(None, language) for language in languages]
        + [(model, language) for model in models for language in languages]
    )
    for model, language in scopes:
        keep = pd.Series(True, index=frame.index)
        if model is not None:
            keep &= frame["subject_model"].eq(model)
        if language is not None:
            keep &= frame["prompt_language"].eq(language)
        part = frame.loc[keep].copy()
        row = {
            "subject_model": model or "ALL",
            "prompt_language": language or "ALL",
            "audit_n": len(part),
            "population_n": float(part["design_weight"].sum()),
        }
        for field in ("pred_genuine_refusal", "pred_capability_failure", "wrong_language"):
            for judge in ("luna", "sol"):
                result = design_mean_and_se(part, f"{field}_{judge}")
                for metric, value in result.items():
                    row[f"{field}_{judge}_{metric}"] = value
            part[f"{field}_difference"] = (
                part[f"{field}_luna"].astype(int) - part[f"{field}_sol"].astype(int)
            )
            difference = design_mean_and_se(
                part, f"{field}_difference", bounded=False
            )
            row[f"{field}_luna_minus_sol"] = difference["estimate"]
            row[f"{field}_difference_se"] = difference["standard_error"]
        estimate_rows.append(row)
    estimates_path = OUTPUT_DIR / "design_based_model_language_estimates.csv"
    pd.DataFrame(estimate_rows).to_csv(estimates_path, index=False)

    summary = {
        "version": "local-gguf-hpc-full-sol-v2.4-audit-summary-v1",
        "created_at": now(),
        "audit_n": len(frame),
        "weighted_population_n": float(frame["design_weight"].sum()),
        "selection_counts": {
            str(key): int(value)
            for key, value in frame["selection_stratum"].map(
                lambda value: value.split("|")[0]
            ).value_counts().items()
        },
        "binary_outcomes": outcomes,
        "provider_cost_usd": run_summary["provider_cost_usd"],
        "artifact_sha256": {
            comparison_path.name: sha_file(comparison_path),
            agreement_path.name: sha_file(agreement_path),
            estimates_path.name: sha_file(estimates_path),
            results_path.name: sha_file(results_path),
        },
        "interpretation": "Sol is a frontier-model reference, not independent human ground truth; estimates use the frozen audit probabilities.",
    }
    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
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
            parser.error("authorize requires --payload-sha and --cost-ceiling")
        result = authorize(args.payload_sha, args.cost_ceiling, args.confirm_user_authorization)
    elif args.command == "run":
        if args.cost_ceiling is None:
            parser.error("run requires --cost-ceiling")
        load_env_from_file()
        result = run_sol_v24(
            ROOT, OUTPUT_DIR, min(args.workers, 32),
            args.cost_ceiling, args.authorize_paid_run,
        )
    else:
        result = score()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
