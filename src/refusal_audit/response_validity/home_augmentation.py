"""Plan, but do not draw, a human augmentation for standardized home effects.

The planner is entirely local. It uses frozen Stage-17 response coefficients
and Sol refusal probabilities to form leverage-by-risk strata, then applies
anticipated Neyman allocation under two declared calibration scenarios. It
never reads the sealed enrichment evaluation outcomes and emits no row IDs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .estimand_precision import build_estimand_coefficients
from .human_pilot import KEY, sha_file


TARGET_HALF_WIDTH_PP = 5.0
TARGET_EVENTS_PER_ARM = 5.0
EU_ZERO_EVENT_N_PER_ARM = 60
TRUTH_SCENARIOS = {
    "moderate_075_sol": (0.75, 0.0),
    "conservative_050_sol_plus_005": (0.50, 0.005),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def allocate_integer_neyman(
    variance_weights: np.ndarray,
    population_sizes: np.ndarray,
    total: int,
    minimum_each: int = 2,
) -> np.ndarray:
    """Integer allocation using the exact next-unit variance reduction."""
    weights = np.asarray(variance_weights, dtype=float)
    sizes = np.asarray(population_sizes, dtype=int)
    allocation = np.minimum(sizes, minimum_each).astype(int)
    remaining = int(total - allocation.sum())
    if remaining < 0:
        raise ValueError("total is below the minimum stratum allocation")
    while remaining:
        eligible = allocation < sizes
        if not eligible.any():
            break
        gain = np.where(
            eligible,
            weights / np.maximum(allocation * (allocation + 1), 1),
            -1,
        )
        choice = int(np.argmax(gain))
        allocation[choice] += 1
        remaining -= 1
    return allocation


def _planning_groups(
    population: pd.DataFrame,
    coefficients: np.ndarray,
    prediction: np.ndarray,
    truth: np.ndarray,
) -> list[dict]:
    active = np.flatnonzero(np.abs(coefficients) > 1e-15)
    frame = population.loc[active, ["home_status", "prompt_id", "model"]].copy()
    frame["population_index"] = active
    frame["priority"] = (
        np.abs(coefficients[active])
        * np.sqrt(np.maximum(truth[active] * (1 - truth[active]), 1e-8))
    )
    # Ties are resolved by the frozen response key, not input row order.
    frame["tie_key"] = frame.prompt_id.astype(str) + "\0" + frame.model.astype(str)
    frame = frame.sort_values(["home_status", "priority", "tie_key"]).copy()
    frame["priority_rank"] = frame.groupby("home_status").cumcount()
    frame["arm_n"] = frame.groupby("home_status").home_status.transform("size")
    frame["band"] = np.minimum(4, np.floor(5 * frame.priority_rank / frame.arm_n)).astype(int)

    groups: list[dict] = []
    for (arm, band), group in frame.groupby(["home_status", "band"], sort=True):
        idx = group.population_index.to_numpy(int)
        expected = coefficients[idx] * (truth[idx] - prediction[idx])
        mean_expected = float(expected.mean())
        if len(idx) > 1:
            anticipated_s2 = float(np.sum(
                coefficients[idx] ** 2 * truth[idx] * (1 - truth[idx])
                + np.square(expected - mean_expected)
            ) / (len(idx) - 1))
        else:
            anticipated_s2 = 0.0
        groups.append({
            "arm": str(arm), "band": int(band), "N": len(idx),
            "anticipated_s2": anticipated_s2,
            "mean_event_probability": float(truth[idx].mean()),
            "priority_min": float(group.priority.min()),
            "priority_max": float(group.priority.max()),
        })
    return groups


def _find_required(
    groups: list[dict], jurisdiction: str,
) -> tuple[int, float, dict[str, float], np.ndarray]:
    sizes = np.array([g["N"] for g in groups], dtype=int)
    weights = np.array([g["N"] ** 2 * g["anticipated_s2"] for g in groups])
    if jurisdiction == "EU":
        allocation = np.array([
            round(EU_ZERO_EVENT_N_PER_ARM * g["N"] / sum(
                x["N"] for x in groups if x["arm"] == g["arm"]
            )) for g in groups
        ], dtype=int)
        # Correct rounding separately within each arm.
        for arm in ["home", "away"]:
            loc = [i for i, g in enumerate(groups) if g["arm"] == arm]
            while allocation[loc].sum() < EU_ZERO_EVENT_N_PER_ARM:
                allocation[loc[-1]] += 1
            while allocation[loc].sum() > EU_ZERO_EVENT_N_PER_ARM:
                allocation[loc[-1]] -= 1
        total = int(allocation.sum())
    else:
        allocation = None
        total = 0
        for candidate in range(50, min(1_500, int(sizes.sum())) + 1, 10):
            trial = allocate_integer_neyman(weights, sizes, candidate)
            event_yield = {
                arm: sum(
                    trial[i] * groups[i]["mean_event_probability"]
                    for i in range(len(groups)) if groups[i]["arm"] == arm
                ) for arm in ["home", "away"]
            }
            variance = float(np.sum(weights * (1 - trial / sizes) / trial))
            half_width = 1.96 * np.sqrt(max(0.0, variance)) * 100
            if half_width <= TARGET_HALF_WIDTH_PP and min(event_yield.values()) >= TARGET_EVENTS_PER_ARM:
                total, allocation = candidate, trial
                break
        if allocation is None:
            raise RuntimeError(f"no feasible allocation found for {jurisdiction}")
    variance = float(np.sum(weights * (1 - allocation / sizes) / allocation))
    half_width = 1.96 * np.sqrt(max(0.0, variance)) * 100
    event_yield = {
        arm: sum(
            allocation[i] * groups[i]["mean_event_probability"]
            for i in range(len(groups)) if groups[i]["arm"] == arm
        ) for arm in ["home", "away"]
    }
    return total, half_width, event_yield, allocation


def plan_home_augmentation(
    root: Path,
    output_dir: Path | None = None,
) -> dict:
    """Write aggregate workload and allocation artifacts without drawing rows."""
    output_dir = output_dir or (
        root / "annotations" / "response_validity_human_v2"
        / "home_augmentation_planning_v1"
    )
    population_path = root / "annotations" / "response_validity_dsl_v1_1" / "wall_to_wall_features.parquet"
    pseudo_path = root / "annotations" / "response_validity_dsl_v1_1" / "dsl_pseudo_outcomes.parquet"
    precision_manifest_path = (
        root / "annotations" / "response_validity_human_v2"
        / "estimand_precision_audit_v1" / "audit_manifest.json"
    )
    inputs = [population_path, pseudo_path, precision_manifest_path]
    for path in inputs:
        if not path.exists():
            raise FileNotFoundError(path)
    input_hashes = {str(path.relative_to(root)): sha_file(path) for path in inputs}
    manifest_path = output_dir / "planning_manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("input_sha256") != input_hashes:
            raise RuntimeError("existing home plan uses different frozen inputs")
        for name, expected in existing.get("artifact_sha256", {}).items():
            path = output_dir / name
            if not path.exists() or sha_file(path) != expected:
                raise RuntimeError(f"home-planning artifact missing or changed: {path}")
        return existing
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested planning directory: {output_dir}")

    population = pd.read_parquet(population_path)
    predictions = pd.read_parquet(
        pseudo_path,
        columns=KEY + ["dsl_prediction_clean_genuine_refusal"],
    )
    population = population.merge(predictions, on=KEY, validate="one_to_one")
    prediction = population.dsl_prediction_clean_genuine_refusal.to_numpy(float)
    home_specs = {
        spec["cell"]: spec["coefficients"]
        for spec in build_estimand_coefficients(population)
        if spec["family"] == "standardized_home"
    }

    summary_rows: list[dict] = []
    allocation_rows: list[dict] = []
    for scenario, (scale, floor) in TRUTH_SCENARIOS.items():
        truth = np.clip(scale * prediction + floor, 0, 1)
        for jurisdiction, coefficients in home_specs.items():
            groups = _planning_groups(population, coefficients, prediction, truth)
            required, half_width, events, allocation = _find_required(groups, jurisdiction)
            summary_rows.append({
                "scenario": scenario, "jurisdiction": jurisdiction,
                "required_annotations": required,
                "anticipated_half_width_pp": half_width,
                "anticipated_home_events": events["home"],
                "anticipated_away_events": events["away"],
                "target_half_width_pp": TARGET_HALF_WIDTH_PP,
                "target_events_per_arm": 0 if jurisdiction == "EU" else TARGET_EVENTS_PER_ARM,
                "eu_zero_event_n_per_arm": EU_ZERO_EVENT_N_PER_ARM if jurisdiction == "EU" else 0,
            })
            for group, n in zip(groups, allocation):
                allocation_rows.append({
                    "scenario": scenario, "jurisdiction": jurisdiction,
                    **group, "draw_n": int(n),
                })
    summary = pd.DataFrame(summary_rows)
    allocation = pd.DataFrame(allocation_rows)
    totals = (summary.groupby("scenario", as_index=False)
              .agg(total_annotations=("required_annotations", "sum")))

    output_dir.mkdir(parents=True, exist_ok=False)
    summary_path = output_dir / "scenario_summary.csv"
    allocation_path = output_dir / "stratum_allocations.csv"
    totals_path = output_dir / "workload_totals.csv"
    summary.to_csv(summary_path, index=False)
    allocation.to_csv(allocation_path, index=False)
    totals.to_csv(totals_path, index=False)
    manifest = {
        "planning_version": "home-human-augmentation-v1.0",
        "created_at": _utc_now(),
        "status": "planning_only; no_rows_drawn; no_annotation_authorized",
        "target_estimand": "jurisdiction-specific English standardized genuine-refusal home-minus-away association",
        "phase_1_scenario": "moderate_075_sol",
        "phase_1_annotations": int(totals.loc[
            totals.scenario.eq("moderate_075_sol"), "total_annotations"
        ].iloc[0]),
        "maximum_scenario": "conservative_050_sol_plus_005",
        "maximum_total_annotations": int(totals.loc[
            totals.scenario.eq("conservative_050_sol_plus_005"), "total_annotations"
        ].iloc[0]),
        "eu_rule": "60 SRSWOR per arm; if zero events, require one-sided 95% rule-of-three upper bound below 5%",
        "non_eu_gate": "at least five genuine refusals in each arm and estimand-specific 95% human-sampling half-width <=5 pp",
        "sealed_evaluation_outcomes_read": False,
        "row_ids_drawn": False,
        "provider_or_network_call_made": False,
        "input_sha256": input_hashes,
        "artifact_sha256": {
            summary_path.name: sha_file(summary_path),
            allocation_path.name: sha_file(allocation_path),
            totals_path.name: sha_file(totals_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
