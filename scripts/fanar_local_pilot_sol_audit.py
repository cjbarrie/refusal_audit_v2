#!/usr/bin/env python3
"""Guarded full-census Sol v2.4 audit of the local Fanar-1 9B pilot.

All 196 Luna-coded responses are sent with byte-identical messages and schema.
The census avoids extrapolating from a sample in the small, high-disagreement
admission pilot. Sol remains a frontier-model reference, not human ground truth.

Technical record: docs/FANAR_EXPERIMENTS_V1.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import local_gguf_hpc_benchmark_sol_audit as base
from env_utils import load_env_from_file

LUNA_DIR = ROOT / "annotations/model_expansion_v4/fanar_1_9b_local_pilot_luna_v2_4_v1"
OUTPUT_DIR = ROOT / "annotations/model_expansion_v4/fanar_1_9b_local_pilot_sol_v2_4_audit_v1"
EXPECTED_POPULATION = 196
EXPECTED_FLAGGED = 127
EXPECTED_CLEAN = 69


def configure() -> None:
    base.LUNA_DIR = LUNA_DIR
    base.OUTPUT_DIR = OUTPUT_DIR
    base.SELECTION_SEED = "not_applicable_full_census"
    base.CLEAN_PER_CELL = EXPECTED_POPULATION
    base.EXPECTED_POPULATION = EXPECTED_POPULATION
    base.EXPECTED_FLAGGED = EXPECTED_FLAGGED
    base.EXPECTED_CLEAN_SAMPLE = EXPECTED_CLEAN
    base.EXPECTED_REQUESTS = EXPECTED_POPULATION
    base.select = select


def select() -> pd.DataFrame:
    frame = pd.read_parquet(LUNA_DIR / "assembled_labels.parquet")
    if len(frame) != EXPECTED_POPULATION or frame["audit_response_id"].duplicated().any():
        raise ValueError("Luna frame is not the frozen 196-response Fanar pilot")
    frame["luna_flagged"] = (
        frame["pred_genuine_refusal"]
        | frame["pred_capability_failure"]
        | frame["language_fidelity"].eq("wrong_language")
        | frame["substantive_refusal"].eq("unassessable")
    )
    if int(frame["luna_flagged"].sum()) != EXPECTED_FLAGGED:
        raise ValueError("Fanar Luna flagged count changed")
    frame["selection_stratum"] = "full_census"
    frame["selection_probability"] = 1.0
    frame["design_weight"] = 1.0
    return frame.sort_values("audit_response_id", kind="mergesort").reset_index(drop=True)


def patch_manifest() -> dict:
    path = OUTPUT_DIR / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update({
        "version": "fanar-1-9b-local-pilot-sol-v2.4-audit-v1",
        "scientific_role": "full-census frontier verification of the local Fanar admission pilot",
        "selection": {
            "population_n": EXPECTED_POPULATION,
            "census_n": EXPECTED_POPULATION,
            "luna_flagged_n": EXPECTED_FLAGGED,
            "apparently_clean_n": EXPECTED_CLEAN,
            "selection_probability": 1.0,
            "design_weight": 1.0,
            "all_luna_refusals_included": True,
            "all_luna_capability_failures_included": True,
            "all_apparently_clean_controls_included": True,
        },
    })
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def prepare() -> dict:
    configure()
    base.prepare()
    return patch_manifest()


def cost() -> dict:
    prepare()
    result = base.cost()
    result["version"] = "fanar-1-9b-local-pilot-sol-v2.4-audit-cost-v1"
    (OUTPUT_DIR / "cost_estimate.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    manifest = patch_manifest()
    manifest["cost_estimate"] = result
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


def authorize(payload_sha: str, ceiling: float, confirmed: bool) -> dict:
    configure()
    prepare()
    record = base.authorize(payload_sha, ceiling, confirmed)
    record["authorization_scope"] = "fanar_1_9b_local_pilot_sol_v2_4_audit_v1"
    manifest = patch_manifest()
    manifest["authorization"] = record
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return record


def score() -> dict:
    configure()
    result = base.score()
    # The reused scorer names the second component a probability sample. Here
    # both components are censused, so remove those inherited labels before
    # writing the Fanar-specific summary.
    result.pop("flagged_census_n", None)
    result.pop("clean_probability_sample_n", None)
    result.update({
        "version": "fanar-1-9b-local-pilot-sol-v2.4-audit-summary-v1",
        "audit_n": EXPECTED_POPULATION,
        "weighted_population_n": float(EXPECTED_POPULATION),
        "luna_flagged_n": EXPECTED_FLAGGED,
        "apparently_clean_n": EXPECTED_CLEAN,
        "selection": "full census; every record has weight one",
        "interpretation": "Sol is a frontier-model reference, not human ground truth; this is a census of all 196 Fanar pilot responses.",
    })
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    manifest = patch_manifest()
    manifest["summary"] = result
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


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
        configure()
        load_env_from_file()
        result = base.run_sol_v24(
            ROOT, OUTPUT_DIR, min(args.workers, 32), args.cost_ceiling, args.authorize_paid_run
        )
    else:
        result = score()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
