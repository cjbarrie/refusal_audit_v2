"""Plan the fresh external response-validity audit without selecting row IDs.

The design combines an equal model-by-language coverage draw with an
independent risk-stratified draw.  This module emits aggregate planning tables
only.  It never creates a review packet, provider request, or response-level
sample and it never accesses the network.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .enrichment_design_v2 import ROUTING_STRATA, build_routing_population
from .human_pilot import KEY, sha_file
from .luna_v23_repair import _derive, _read_jsonl


DEFAULT_DIR = (
    "annotations/response_validity_human_v2/external_audit_planning_v1"
)
GOLD = (
    "annotations/response_validity_human_v2/decomposed_review_v2_2/"
    "harmonized_evaluation_gold_v2_2.parquet"
)
WAVE = (
    "annotations/response_validity_human_v2/enrichment_wave_v2_400/"
    "wave_design.parquet"
)
V22_RESULTS = (
    "annotations/response_validity_human_v2/luna_exact_v2_2_internal_test_v1/"
    "results.jsonl"
)
V23_RESULTS = (
    "annotations/response_validity_human_v2/luna_v2_3_repair_test_v1/"
    "results.jsonl"
)

# Each plan is an independent model-language coverage draw plus an independent
# routing-stratum draw.  The union may be a few rows smaller than the nominal
# sum because a response can enter both components.
PLANS = {
    "audit_800": {
        "per_model_language": 6,
        "risk_draw": (70, 70, 35, 150, 70, 55, 20),
    },
    "audit_1000": {
        "per_model_language": 8,
        "risk_draw": (85, 85, 45, 180, 85, 65, 20),
    },
    "audit_1200": {
        "per_model_language": 10,
        "risk_draw": (100, 100, 50, 200, 100, 70, 30),
    },
    "audit_1500": {
        "per_model_language": 12,
        "risk_draw": (130, 130, 65, 260, 130, 100, 35),
    },
}

# Human verification after Luna and Sol have both labelled the selected rows.
# Priority rows are reviewed with certainty.  The remaining probabilities are
# compared here rather than pretending that the not-yet-observed Sol labels
# are known.
VERIFICATION_SCENARIOS = {
    "lean": {"priority": 1.0, "capability_positive_agreement": 0.35,
             "ordinary_agreement": 0.08},
    "recommended": {"priority": 1.0, "capability_positive_agreement": 0.50,
                    "ordinary_agreement": 0.10},
    "conservative": {"priority": 1.0, "capability_positive_agreement": 0.75,
                     "ordinary_agreement": 0.20},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def union_probability(p_cell: np.ndarray, p_risk: np.ndarray) -> np.ndarray:
    """First-order probability for the union of two independent draws."""
    return 1 - (1 - p_cell) * (1 - p_risk)


def _reuse_frozen_design(
    root: Path, output_dir: Path, seed: int, simulations: int
) -> dict | None:
    """Return a verified existing design instead of silently replacing it."""
    manifest_path = output_dir / "design_manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("seed") != seed:
        raise ValueError("existing external design uses a different seed")
    if manifest.get("posterior_predictive_draws") != simulations:
        raise ValueError(
            "existing external design uses a different simulation count"
        )
    expected_inputs = {
        "harmonized_gold": sha_file(root / GOLD),
        "enrichment_wave_design": sha_file(root / WAVE),
        "luna_v2_2_results": sha_file(root / V22_RESULTS),
        "luna_v2_3_repair_results": sha_file(root / V23_RESULTS),
    }
    if manifest.get("input_sha256") != expected_inputs:
        raise ValueError("existing external design no longer matches its inputs")
    for name, expected_hash in manifest.get("artifact_sha256", {}).items():
        path = output_dir / name
        if not path.exists() or sha_file(path) != expected_hash:
            raise ValueError(f"frozen external design artifact changed: {name}")
    for closed_flag in (
        "sample_drawn", "response_ids_emitted", "provider_payload_created",
        "paid_run_authorized", "network_call_made",
    ):
        if manifest.get(closed_flag) is not False:
            raise ValueError(f"aggregate design has unsafe state: {closed_flag}")
    return manifest


def _patched_source_predictions(root: Path) -> pd.DataFrame:
    """Reconstruct the immutable patched source-only diagnostic in memory."""
    v22 = _derive(pd.DataFrame(_read_jsonl(root / V22_RESULTS)))
    v23 = _derive(pd.DataFrame(_read_jsonl(root / V23_RESULTS)))
    v22 = v22.loc[v22.input_mode.eq("original_only")].copy()
    v22["analysis_mode"] = "source_response_only"
    v23 = v23.loc[v23.input_mode.eq("source_response_only")].copy()
    old_ids = set(v22.evaluation_review_id.astype(str))
    fill = v23.loc[~v23.evaluation_review_id.astype(str).isin(old_ids)].copy()
    combined = pd.concat([v22, fill], ignore_index=True)
    if len(combined) != 700 or combined.evaluation_review_id.duplicated().any():
        raise ValueError("patched source-only predictions are not 700 unique rows")
    return combined[[
        "evaluation_review_id", "pred_genuine_refusal",
        "pred_capability_failure", "confidence",
    ]]


def _calibration(root: Path, population: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use the randomized 400-case wave for aggregate planning calibration."""
    gold = pd.read_parquet(root / GOLD)
    wave = pd.read_parquet(root / WAVE)
    patched = _patched_source_predictions(root)
    frame = wave[KEY + ["routing_stratum"]].merge(
        gold[[
            "review_id", *KEY, "human_genuine_refusal_v2_2",
            "human_capability_failure_v2_2",
        ]], on=KEY, validate="one_to_one",
    ).merge(
        patched, left_on="review_id", right_on="evaluation_review_id",
        validate="one_to_one",
    )
    if len(frame) != 400:
        raise ValueError("external planning calibration must contain 400 rows")

    human_refusal = frame.human_genuine_refusal_v2_2.astype(bool)
    human_capability = frame.human_capability_failure_v2_2.astype(bool)
    luna_refusal = frame.pred_genuine_refusal.astype(bool)
    luna_capability = frame.pred_capability_failure.astype(bool)
    priority = (
        human_refusal | luna_refusal | human_refusal.ne(luna_refusal)
        | human_capability.ne(luna_capability)
        | frame.confidence.astype(str).eq("low")
    )
    frame["verification_proxy_class"] = np.select(
        [priority, human_capability & luna_capability],
        ["priority", "capability_positive_agreement"],
        default="ordinary_agreement",
    )

    rows = []
    population_counts = population.routing_stratum.value_counts()
    for stratum in ROUTING_STRATA:
        part = frame.loc[frame.routing_stratum.eq(stratum)]
        if part.empty:
            raise ValueError(f"400-case calibration lacks {stratum}")
        rows.append({
            "routing_stratum": stratum,
            "external_population_n": int(population_counts[stratum]),
            "calibration_n": len(part),
            "human_genuine_refusal_n": int(
                part.human_genuine_refusal_v2_2.astype(bool).sum()
            ),
            "human_capability_failure_n": int(
                part.human_capability_failure_v2_2.astype(bool).sum()
            ),
            "verification_priority_proxy_n": int(
                part.verification_proxy_class.eq("priority").sum()
            ),
            "verification_capability_agreement_proxy_n": int(
                part.verification_proxy_class.eq(
                    "capability_positive_agreement"
                ).sum()
            ),
            "verification_ordinary_proxy_n": int(
                part.verification_proxy_class.eq("ordinary_agreement").sum()
            ),
        })
    return pd.DataFrame(rows), frame


def _candidate_probabilities(
    population: pd.DataFrame, per_cell: int, risk_draw: dict[str, int]
) -> pd.DataFrame:
    frame = population.copy()
    cell_n = frame.groupby(["model", "prompt_language"])["model"].transform("size")
    if int(cell_n.min()) < per_cell:
        raise ValueError("a model-language cell cannot support its coverage draw")
    routing_n = frame.groupby("routing_stratum")["routing_stratum"].transform("size")
    frame["cell_component_probability"] = per_cell / cell_n
    frame["risk_draw_n"] = frame.routing_stratum.map(risk_draw).astype(int)
    if (frame.risk_draw_n > routing_n).any():
        raise ValueError("a routing stratum cannot support its risk draw")
    frame["risk_component_probability"] = frame.risk_draw_n / routing_n
    frame["phase1_inclusion_probability"] = union_probability(
        frame.cell_component_probability.to_numpy(float),
        frame.risk_component_probability.to_numpy(float),
    )
    return frame


def simulate_external_audit_design(
    root: Path,
    output_dir: Path | None = None,
    seed: int = 20260827,
    simulations: int = 10_000,
) -> dict:
    """Compare aggregate designs without emitting any response-level record."""
    output_dir = output_dir or root / DEFAULT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    if simulations < 1_000:
        raise ValueError("at least 1,000 simulations are required")
    frozen = _reuse_frozen_design(root, output_dir, seed, simulations)
    if frozen is not None:
        return frozen

    full, _, _ = build_routing_population(
        root, root / "annotations" / "response_validity_human_v2", 20260823
    )
    gold = pd.read_parquet(root / GOLD)
    reviewed = set(map(tuple, gold[KEY].itertuples(index=False, name=None)))
    external = full.loc[
        ~full[KEY].apply(tuple, axis=1).isin(reviewed)
    ].copy()
    if len(full) != 137_186 or len(external) != 136_486:
        raise ValueError("external planning population must exclude exactly 700 rows")
    if external.duplicated(KEY).any():
        raise ValueError("external planning population has duplicate response keys")

    calibration, _ = _calibration(root, external)
    calibration_path = output_dir / "routing_calibration.csv"
    calibration.to_csv(calibration_path, index=False)
    cal = calibration.set_index("routing_stratum")
    rng = np.random.default_rng(seed)
    candidate_rows, allocation_rows, workload_rows = [], [], []

    for plan_name, spec in PLANS.items():
        risk_draw = dict(zip(ROUTING_STRATA, spec["risk_draw"]))
        planned = _candidate_probabilities(
            external, int(spec["per_model_language"]), risk_draw
        )
        expected_n = float(planned.phase1_inclusion_probability.sum())
        by_routing = planned.groupby("routing_stratum").agg(
            expected_selected=("phase1_inclusion_probability", "sum"),
            population_n=("routing_stratum", "size"),
        )
        by_cell = planned.groupby(["model", "prompt_language"])[
            "phase1_inclusion_probability"
        ].sum()

        outcome_draws: dict[str, np.ndarray] = {}
        for outcome, event_column in (
            ("genuine_refusal", "human_genuine_refusal_n"),
            ("capability_failure", "human_capability_failure_n"),
        ):
            total = np.zeros(simulations, dtype=int)
            for stratum in ROUTING_STRATA:
                n = int(cal.loc[stratum, "calibration_n"])
                y = int(cal.loc[stratum, event_column])
                p = rng.beta(0.5 + y, 0.5 + n - y, simulations)
                sample_n = int(round(by_routing.loc[stratum, "expected_selected"]))
                total += rng.binomial(sample_n, p)
            outcome_draws[outcome] = total

        candidate_rows.append({
            "plan": plan_name,
            "nominal_component_total": (
                55 * int(spec["per_model_language"]) + sum(risk_draw.values())
            ),
            "expected_unique_phase1_n": expected_n,
            "per_model_language_coverage_draw": int(spec["per_model_language"]),
            "expected_min_model_language_n": float(by_cell.min()),
            "expected_median_model_language_n": float(by_cell.median()),
            "genuine_refusal_expected": float(outcome_draws["genuine_refusal"].mean()),
            "genuine_refusal_q05": float(np.quantile(outcome_draws["genuine_refusal"], .05)),
            "genuine_refusal_q95": float(np.quantile(outcome_draws["genuine_refusal"], .95)),
            "capability_failure_expected": float(outcome_draws["capability_failure"].mean()),
            "capability_failure_q05": float(np.quantile(outcome_draws["capability_failure"], .05)),
            "capability_failure_q95": float(np.quantile(outcome_draws["capability_failure"], .95)),
            "provider_annotations_if_two_models": int(round(2 * expected_n)),
        })

        for stratum in ROUTING_STRATA:
            allocation_rows.append({
                "plan": plan_name,
                "routing_stratum": stratum,
                "external_population_n": int(by_routing.loc[stratum, "population_n"]),
                "risk_component_draw_n": int(risk_draw[stratum]),
                "risk_component_probability": (
                    risk_draw[stratum] / by_routing.loc[stratum, "population_n"]
                ),
                "expected_union_selected_n": float(
                    by_routing.loc[stratum, "expected_selected"]
                ),
            })

        for scenario, probabilities in VERIFICATION_SCENARIOS.items():
            expected_human = 0.0
            proxy_counts = {
                "priority": 0.0,
                "capability_positive_agreement": 0.0,
                "ordinary_agreement": 0.0,
            }
            for stratum in ROUTING_STRATA:
                exposure = float(by_routing.loc[stratum, "expected_selected"])
                denom = float(cal.loc[stratum, "calibration_n"])
                rates = {
                    "priority": (
                        0.5 + cal.loc[stratum, "verification_priority_proxy_n"]
                    ) / (1 + denom),
                    "capability_positive_agreement": (
                        0.5 + cal.loc[
                            stratum, "verification_capability_agreement_proxy_n"
                        ]
                    ) / (1 + denom),
                    "ordinary_agreement": (
                        0.5 + cal.loc[stratum, "verification_ordinary_proxy_n"]
                    ) / (1 + denom),
                }
                scale = sum(rates.values())
                for category in rates:
                    proxy_counts[category] += exposure * rates[category] / scale
            for category, count in proxy_counts.items():
                expected_human += count * probabilities[category]
            workload_rows.append({
                "plan": plan_name,
                "scenario": scenario,
                "expected_phase1_n": expected_n,
                "expected_priority_rows": proxy_counts["priority"],
                "expected_capability_positive_agreements": proxy_counts[
                    "capability_positive_agreement"
                ],
                "expected_ordinary_agreements": proxy_counts["ordinary_agreement"],
                "q_priority": probabilities["priority"],
                "q_capability_positive_agreement": probabilities[
                    "capability_positive_agreement"
                ],
                "q_ordinary_agreement": probabilities["ordinary_agreement"],
                "expected_human_reviews": expected_human,
                "planning_proxy_note": (
                    "uses human outcomes in place of not-yet-observed Sol labels "
                    "only to project workload; it is not an accuracy estimate"
                ),
            })

    candidates = pd.DataFrame(candidate_rows)
    allocations = pd.DataFrame(allocation_rows)
    workloads = pd.DataFrame(workload_rows)
    candidates.to_csv(output_dir / "candidate_designs.csv", index=False)
    allocations.to_csv(output_dir / "candidate_allocations.csv", index=False)
    workloads.to_csv(output_dir / "human_workload_scenarios.csv", index=False)

    selected = "audit_1200"
    chosen = candidates.loc[candidates.plan.eq(selected)].iloc[0]
    chosen_workload = workloads.loc[
        workloads.plan.eq(selected) & workloads.scenario.eq("recommended")
    ].iloc[0]
    recommendation = {
        "version": "external-response-validity-audit-design-v1",
        "created_at": _now(),
        "status": "aggregate_design_recommended_not_drawn",
        "recommended_plan": selected,
        "reason": (
            "ten guaranteed coverage selections in every model-language cell, "
            "substantial refusal and capability-failure support, and a projected "
            "human workload that remains materially below full double coding"
        ),
        "external_population_n": len(external),
        "expected_unique_phase1_n": float(chosen.expected_unique_phase1_n),
        "provider_annotations_if_two_models": int(
            chosen.provider_annotations_if_two_models
        ),
        "expected_genuine_refusals": float(chosen.genuine_refusal_expected),
        "genuine_refusal_90_percent_planning_range": [
            float(chosen.genuine_refusal_q05), float(chosen.genuine_refusal_q95)
        ],
        "expected_capability_failures": float(
            chosen.capability_failure_expected
        ),
        "capability_failure_90_percent_planning_range": [
            float(chosen.capability_failure_q05),
            float(chosen.capability_failure_q95),
        ],
        "recommended_verification_probabilities": VERIFICATION_SCENARIOS[
            "recommended"
        ],
        "expected_human_reviews": float(chosen_workload.expected_human_reviews),
        "phase2_priority_definition": (
            "certainty review for any model-identified refusal, any Luna-Sol "
            "headline disagreement, schema failure, or low-confidence label"
        ),
        "sol_role": "independent strong annotator; never automatic ground truth",
        "sample_drawn": False,
        "response_ids_emitted": False,
        "provider_payload_created": False,
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    recommendation_path = output_dir / "recommendation.json"
    recommendation_path.write_text(
        json.dumps(recommendation, indent=2), encoding="utf-8"
    )
    manifest = {
        **recommendation,
        "seed": seed,
        "posterior_predictive_draws": simulations,
        "population_rows_before_exclusion": len(full),
        "previous_human_rows_excluded": 700,
        "design": (
            "union of independent equal model-language SRSWOR and routing-stratum "
            "SRSWOR; pi=1-(1-p_cell)(1-p_risk)"
        ),
        "calibration_role": (
            "400-case randomized enrichment wave used for planning only; no row "
            "in that wave can enter the external audit"
        ),
        "input_sha256": {
            "harmonized_gold": sha_file(root / GOLD),
            "enrichment_wave_design": sha_file(root / WAVE),
            "luna_v2_2_results": sha_file(root / V22_RESULTS),
            "luna_v2_3_repair_results": sha_file(root / V23_RESULTS),
        },
        "artifact_sha256": {
            name: sha_file(output_dir / name) for name in (
                "routing_calibration.csv", "candidate_designs.csv",
                "candidate_allocations.csv", "human_workload_scenarios.csv",
                "recommendation.json",
            )
        },
    }
    manifest_path = output_dir / "design_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
