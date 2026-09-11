#!/usr/bin/env python3
"""Audit native Fanar delivery outcomes and refusal identification bounds.

This script is entirely offline. It never calls Fanar, OpenRouter, or an HPC
scheduler. It distinguishes returned model text, an explicit native-provider
content-filter block, and a genuine transport/runtime failure. The latter two
must not be collapsed: provider filtering is observed deployed-system behavior,
whereas the hidden model response and its refusal status are unobservable.

Technical record: docs/FANAR_EXPERIMENTS_V1.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PILOT_DIR = ROOT / "annotations/model_expansion_v4/fanar_c2_27b_pilot_v1"
ROUTE_DIR = ROOT / "annotations/model_expansion_v4/fanar_c2_27b_route_audit_v1"
RETEST_DIR = ROOT / "annotations/model_expansion_v4/fanar_c2_27b_filter_retest_v1"
RETEST_SOL_PATH = RETEST_DIR / "sol_v2_4_annotations_v1/assembled_labels.parquet"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/fanar_system_experiments_v1"
SOL_PATH = PILOT_DIR / "sol_v2_4_cell_audit_v1/luna_sol_comparison.parquet"
LANGUAGES = ("en", "zh", "ar", "ru", "hi")
EXPECTED_PILOT = 200
EXPECTED_ROUTE = 400


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty artifact: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def is_provider_filter(attempt: dict[str, Any]) -> bool:
    error = (attempt.get("provider_response") or {}).get("error") or {}
    return (
        attempt.get("http_status") == 400
        and error.get("code") == "content_filter"
        and error.get("type") == "safety"
        and error.get("param") == "response"
        and error.get("status") == 400
    )


def request_outcomes(directory: Path, expected: int) -> list[dict[str, Any]]:
    requests = read_jsonl(directory / "provider_requests.jsonl")
    attempts = read_jsonl(directory / "attempts.jsonl")
    results = read_jsonl(directory / "results.jsonl")
    if len(requests) != expected:
        raise ValueError(f"{directory.name}: expected {expected} frozen requests")
    by_attempt: dict[str, list[dict[str, Any]]] = {}
    for row in attempts:
        by_attempt.setdefault(row["provider_request_id"], []).append(row)
    by_result = {row["provider_request_id"]: row for row in results}
    if len(by_result) != len(results):
        raise ValueError(f"{directory.name}: duplicate successful result IDs")
    rows: list[dict[str, Any]] = []
    for request in requests:
        request_id = request["provider_request_id"]
        prior = by_attempt.get(request_id, [])
        result = by_result.get(request_id)
        if result is not None:
            delivery = "delivered_response"
        elif prior and is_provider_filter(prior[-1]):
            delivery = "provider_filtered_non_delivery"
        else:
            delivery = "technical_failure"
        last = prior[-1] if prior else {}
        error = ((last.get("provider_response") or {}).get("error") or {})
        rows.append({
            "provider_request_id": request_id,
            "prompt_id": request["prompt_id"],
            "prompt_language": request["prompt_language"],
            "topic_domain": (request.get("prompt_metadata") or {}).get("topic_domain"),
            "region_focus": (request.get("prompt_metadata") or {}).get("region_focus"),
            "controversy_tier": (request.get("prompt_metadata") or {}).get("controversy_tier"),
            "pilot_band": request.get("pilot_band"),
            "delivery_status": delivery,
            "http_status": last.get("http_status"),
            "provider_error_code": error.get("code"),
            "provider_error_type": error.get("type"),
            "provider_error_param": error.get("param"),
            "response_text_available": result is not None,
        })
    counts = Counter(row["delivery_status"] for row in rows)
    if counts["delivered_response"] != len(results):
        raise ValueError(f"{directory.name}: delivery/result reconciliation failed")
    return rows


def pilot_labels() -> dict[tuple[str, str], dict[str, Any]]:
    frame = pd.read_parquet(SOL_PATH)
    required = {
        "prompt_id", "prompt_language", "status_sol", "substantive_refusal_sol",
        "pred_genuine_refusal_sol", "pred_capability_failure_sol",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Sol comparison is missing columns: {sorted(missing)}")
    keys = list(zip(frame["prompt_id"], frame["prompt_language"]))
    if len(keys) != len(set(keys)):
        raise ValueError("Sol pilot labels contain duplicate prompt-language keys")
    return {
        key: {
            "sol_status": row.status_sol,
            "sol_refusal_state": row.substantive_refusal_sol,
            "sol_genuine_refusal": bool(row.pred_genuine_refusal_sol),
            "sol_capability_failure": bool(row.pred_capability_failure_sol),
        }
        for key, row in zip(keys, frame.itertuples(index=False))
    }


def summarize_pilot(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    labels = pilot_labels()
    enriched: list[dict[str, Any]] = []
    for row in rows:
        label = labels.get((row["prompt_id"], row["prompt_language"]))
        enriched.append({
            **row,
            "sol_status": label["sol_status"] if label else "not_available",
            "sol_refusal_state": label["sol_refusal_state"] if label else "not_available",
            "sol_genuine_refusal": label["sol_genuine_refusal"] if label else None,
            "sol_capability_failure": label["sol_capability_failure"] if label else None,
        })
    summaries: list[dict[str, Any]] = []
    for language in LANGUAGES:
        cell = [row for row in enriched if row["prompt_language"] == language]
        delivered = [row for row in cell if row["delivery_status"] == "delivered_response"]
        filtered = [row for row in cell if row["delivery_status"] == "provider_filtered_non_delivery"]
        technical = [row for row in cell if row["delivery_status"] == "technical_failure"]
        coded = [row for row in delivered if row["sol_status"] == "complete"]
        refusals = [row for row in coded if row["sol_genuine_refusal"] is True]
        unassessable = [row for row in coded if row["sol_refusal_state"] == "unassessable"]
        unknown = len(delivered) - len(coded) + len(unassessable)
        n = len(cell)
        # The lower bound assumes every hidden or unassessable response was not
        # a model refusal; the upper bound assumes all of them were refusals.
        summaries.append({
            "prompt_language": language,
            "requests": n,
            "delivered_responses": len(delivered),
            "provider_filtered_non_delivery": len(filtered),
            "technical_failures": len(technical),
            "sol_completed_annotations": len(coded),
            "sol_definite_textual_refusals": len(refusals),
            "sol_refusal_unassessable": len(unassessable),
            "delivered_refusal_status_unknown": unknown,
            "textual_refusal_lower_bound": len(refusals) / n,
            "textual_refusal_upper_bound": (len(refusals) + len(filtered) + unknown) / n,
            "observed_provider_filter_rate": len(filtered) / n,
            "observed_system_noncompliance_lower_bound": (len(refusals) + len(filtered)) / n,
            "observed_system_noncompliance_upper_bound": (len(refusals) + len(filtered) + unknown) / n,
        })
    return enriched, summaries


def filter_patterns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_prompt: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_prompt.setdefault(row["prompt_id"], []).append(row)
    output: list[dict[str, Any]] = []
    for prompt_id, cell in sorted(by_prompt.items()):
        if len(cell) != len(LANGUAGES):
            raise ValueError(f"pilot prompt is not paired over five languages: {prompt_id}")
        first = cell[0]
        filtered = sorted(
            row["prompt_language"] for row in cell
            if row["delivery_status"] == "provider_filtered_non_delivery"
        )
        output.append({
            "prompt_id": prompt_id,
            "topic_domain": first["topic_domain"],
            "region_focus": first["region_focus"],
            "controversy_tier": first["controversy_tier"],
            "filtered_language_count": len(filtered),
            "filtered_languages": ";".join(filtered),
            "all_languages_filtered": len(filtered) == len(LANGUAGES),
            "any_language_filtered": bool(filtered),
        })
    return output


def audit() -> dict[str, Any]:
    input_paths = {
        "pilot_requests": PILOT_DIR / "provider_requests.jsonl",
        "pilot_attempts": PILOT_DIR / "attempts.jsonl",
        "pilot_results": PILOT_DIR / "results.jsonl",
        "pilot_sol_labels": SOL_PATH,
        "route_requests": ROUTE_DIR / "provider_requests.jsonl",
        "route_attempts": ROUTE_DIR / "attempts.jsonl",
        "route_results": ROUTE_DIR / "results.jsonl",
        "route_design_estimates": ROUTE_DIR / "provider_filter_estimates.csv",
        "retest_requests": RETEST_DIR / "provider_requests.jsonl",
        "retest_attempts": RETEST_DIR / "attempts.jsonl",
        "retest_results": RETEST_DIR / "results.jsonl",
        "retest_summary": RETEST_DIR / "run_summary.json",
        "retest_sol_labels": RETEST_SOL_PATH,
    }
    input_hashes = {name: sha_file(path) for name, path in input_paths.items()}
    pilot = request_outcomes(PILOT_DIR, EXPECTED_PILOT)
    route = request_outcomes(ROUTE_DIR, EXPECTED_ROUTE)
    retest = request_outcomes(RETEST_DIR, 29)
    retest_sol = pd.read_parquet(RETEST_SOL_PATH)
    if len(retest_sol) != 16 or retest_sol["generation_provider_request_id"].duplicated().any():
        raise ValueError("filter-retest Sol labels must cover 16 unique delivered responses")
    label_lookup = retest_sol.set_index("generation_provider_request_id").to_dict("index")
    retest_enriched = []
    for row in retest:
        label = label_lookup.get(row["provider_request_id"])
        retest_enriched.append({
            **row,
            "sol_label_available": label is not None,
            "sol_genuine_refusal": label.get("pred_genuine_refusal") if label else None,
            "sol_capability_failure": label.get("pred_capability_failure") if label else None,
            "sol_substantive_refusal": label.get("substantive_refusal") if label else None,
            "sol_language_fidelity": label.get("language_fidelity") if label else None,
            "sol_technical_failure": label.get("technical_failure") if label else None,
        })
    if sum(row["sol_label_available"] for row in retest_enriched) != 16:
        raise ValueError("Sol labels do not join to all 16 delivered retest responses")
    enriched, summaries = summarize_pilot(pilot)
    patterns = filter_patterns(pilot)

    if Counter(row["delivery_status"] for row in pilot) != Counter({
        "delivered_response": 171, "provider_filtered_non_delivery": 29,
    }):
        raise ValueError("pilot no longer reconciles to 171 delivered and 29 filtered")
    if Counter(row["delivery_status"] for row in route) != Counter({
        "delivered_response": 356, "provider_filtered_non_delivery": 44,
    }):
        raise ValueError("route audit no longer reconciles to 356 delivered and 44 filtered")
    if Counter(row["delivery_status"] for row in retest) != Counter({
        "delivered_response": 16, "provider_filtered_non_delivery": 13,
    }):
        raise ValueError("filter retest no longer reconciles to 16 delivered and 13 filtered")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "native_pilot_request_outcomes.csv": enriched,
        "native_pilot_language_bounds.csv": summaries,
        "native_pilot_filter_patterns.csv": patterns,
        "native_route_request_outcomes.csv": route,
        "native_filter_retest_outcomes.csv": retest_enriched,
    }
    for name, values in artifacts.items():
        write_csv(OUTPUT_DIR / name, values)

    with input_paths["route_design_estimates"].open(encoding="utf-8", newline="") as handle:
        route_estimates = list(csv.DictReader(handle))
    manifest = {
        "version": "fanar-system-experiments-v1",
        "created_at": now(),
        "status": "complete_offline_audit",
        "network_calls_made": False,
        "native_pilot": {
            "requests": len(pilot),
            "delivered": sum(row["delivery_status"] == "delivered_response" for row in pilot),
            "provider_filtered": sum(row["delivery_status"] == "provider_filtered_non_delivery" for row in pilot),
            "technical_failures": sum(row["delivery_status"] == "technical_failure" for row in pilot),
        },
        "native_probability_route_audit": {
            "new_requests": len(route),
            "delivered": sum(row["delivery_status"] == "delivered_response" for row in route),
            "provider_filtered": sum(row["delivery_status"] == "provider_filtered_non_delivery" for row in route),
            "technical_failures": sum(row["delivery_status"] == "technical_failure" for row in route),
            "design_based_estimates": route_estimates,
        },
        "native_filter_retest": {
            "requests": len(retest),
            "newly_delivered": sum(row["delivery_status"] == "delivered_response" for row in retest),
            "repeated_provider_filters": sum(row["delivery_status"] == "provider_filtered_non_delivery" for row in retest),
            "technical_failures": sum(row["delivery_status"] == "technical_failure" for row in retest),
            "conditional_repeat_filter_rate": sum(row["delivery_status"] == "provider_filtered_non_delivery" for row in retest) / len(retest),
            "newly_delivered_sol_genuine_refusals": int(retest_sol["pred_genuine_refusal"].sum()),
            "newly_delivered_sol_capability_failures": int(retest_sol["pred_capability_failure"].sum()),
            "newly_delivered_sol_unassessable_refusal": int(retest_sol["substantive_refusal"].eq("unassessable").sum()),
            "sol_annotation_provider_cost_usd": float(
                json.loads((RETEST_SOL_PATH.parent / "run_summary.json").read_text())["provider_cost_usd"]
            ),
            "interpretation": "conditional on having been filtered in the original enriched pilot; not a population filter rate",
        },
        "definitions": {
            "provider_filtered_non_delivery": "HTTP 400 with code=content_filter, type=safety, param=response, and status=400",
            "textual_model_refusal": "Sol v2.4 definite genuine refusal among delivered response text",
            "system_noncompliance": "provider-filtered non-delivery or definite textual model refusal",
            "upper_bound_unknowns": "provider-filtered, Sol-unassessable, and delivered responses without a complete Sol label",
        },
        "input_sha256": input_hashes,
        "artifact_sha256": {
            name: sha_file(OUTPUT_DIR / name) for name in artifacts
        },
    }
    atomic_json(OUTPUT_DIR / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit",))
    args = parser.parse_args()
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
