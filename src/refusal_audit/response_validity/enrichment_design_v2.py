"""Plan the post-Stage-B human enrichment wave without selecting any rows.

This module is deliberately simulation-only.  It reads immutable human and
machine-development artifacts, fits label-blind routing scores, and compares
fixed annotation workloads.  It never writes response-level candidate IDs,
creates a translation payload, reads silent repeats, or makes a network call.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.model_selection import StratifiedGroupKFold

from .enrichment_design import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    _model_pipeline,
    _percentile_rank,
    _successful_sol_components,
)
from .human_pilot import KEY, sha_file, sha_text


WORKLOADS = (150, 250, 400, 600)
ROUTING_TARGETS = (
    "wrong_language",
    "technical_degeneration",
    "coherent_pivot",
    "genuine_refusal",
    "incoherent_garbled",
)
ROUTING_STRATA = (
    "wrong_language_signal",
    "technical_signal",
    "pivot_signal",
    "genuine_refusal_signal",
    "incoherent_signal",
    "stage_b_disagreement_signal",
    "general_remainder",
)
ALLOCATIONS = {
    150: (20, 25, 25, 20, 20, 20, 20),
    250: (30, 40, 40, 30, 30, 35, 45),
    400: (45, 65, 65, 45, 45, 55, 80),
    600: (65, 100, 95, 65, 65, 75, 135),
}
READINESS_TARGETS = {
    "genuine_refusal": 20,
    "coherent_pivot": 15,
    "wrong_language": 20,
    "technical_degeneration": 12,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _planning_frame(root: Path, pilot_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    manifest = json.loads((pilot_dir / "pilot_manifest.json").read_text(encoding="utf-8"))
    population_path = root / manifest["population_path"]
    pseudo_path = root / manifest["pseudo_path"]
    if sha_file(population_path) != manifest["population_sha256"]:
        raise ValueError("wall-to-wall feature hash differs from the frozen pilot")
    if sha_file(pseudo_path) != manifest["pseudo_sha256"]:
        raise ValueError("pseudo-outcome hash differs from the frozen pilot")
    population = pd.read_parquet(population_path)
    pseudo = pd.read_parquet(pseudo_path)
    prediction_columns = [
        "dsl_prediction_clean_genuine_refusal",
        "dsl_prediction_capability_failure",
        "dsl_prediction_coherent_pivot",
    ]
    population = population.merge(
        pseudo[KEY + prediction_columns], on=KEY, validate="one_to_one"
    ).merge(_successful_sol_components(root), on=KEY, how="left", validate="one_to_one")
    if len(population) != 137_186 or population.duplicated(KEY).any():
        raise ValueError("v2 planning population must contain 137,186 unique response keys")

    design = pd.read_parquet(pilot_dir / "pilot_design.parquet")
    labels_path = pilot_dir / "base_freeze_v3_complete_language_review" / "base_labels.parquet"
    labels = pd.read_parquet(labels_path)
    human = design.merge(
        labels[["review_id", "primary_class", "confidence", "language_fidelity"]],
        on="review_id", validate="one_to_one",
    ).merge(
        population[KEY + [c for c in population.columns if c.startswith("sol_")]],
        on=KEY, how="left", validate="one_to_one",
    )
    if len(human) != 300 or human.duplicated(KEY).any():
        raise ValueError("v2 enrichment requires the 300-row complete-language freeze")
    if human.primary_class.isna().any() or human.language_fidelity.isna().any():
        raise ValueError("v2 human labels must be complete")
    return population, human, manifest


def _crossfit_scores(
    human: pd.DataFrame,
    population: pd.DataFrame,
    y: np.ndarray,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    if int(y.sum()) < 4:
        raise ValueError("routing targets require at least four observed positives")
    weights = 1 / human.inclusion_probability.to_numpy(float)
    weights = np.minimum(weights, np.quantile(weights, .99))
    weights /= weights.mean()
    splitter = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed)
    oof = np.full(len(human), np.nan)
    base = _model_pipeline()
    for train, held in splitter.split(human, y, groups=human.issue_id):
        if len(np.unique(y[train])) != 2:
            raise ValueError("a routing fold lacks one class")
        fitted = clone(base)
        fitted.fit(human.iloc[train], y[train], classifier__sample_weight=weights[train])
        oof[held] = fitted.predict_proba(human.iloc[held])[:, 1]
    if not np.isfinite(oof).all():
        raise ValueError("incomplete issue-grouped out-of-fold routing scores")
    fitted = clone(base)
    fitted.fit(human, y, classifier__sample_weight=weights)
    return oof, fitted.predict_proba(population)[:, 1]


def _stage_b_disagreement_target(pilot_dir: Path, human: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    path = pilot_dir / "surrogate_bakeoff_stage_b_v1" / "stage_b_row_disagreements.csv"
    disagreement = pd.read_csv(path)
    by_review = disagreement.groupby("evaluation_review_id", as_index=False).agg(
        stage_b_any_disagreement=("unanimous", lambda x: not bool(np.all(x))),
        stage_b_disagreeing_configs=("unanimous", lambda x: int((~x.astype(bool)).sum())),
        stage_b_max_unique_predictions=("n_unique_predictions", "max"),
    ).rename(columns={"evaluation_review_id": "review_id"})
    evaluation = human.merge(by_review, on="review_id", how="inner", validate="one_to_one")
    if len(evaluation) != 84:
        raise ValueError("Stage B disagreement signal must join exactly 84 evaluation rows")
    return evaluation.stage_b_any_disagreement.astype(int).to_numpy(), evaluation


def _fit_stage_b_disagreement(
    population: pd.DataFrame, evaluation: pd.DataFrame, y: np.ndarray, seed: int
) -> np.ndarray:
    if y.sum() < 4 or (1 - y).sum() < 4:
        raise ValueError("Stage B disagreement outcome lacks support")
    model = _model_pipeline()
    model.fit(evaluation, y)
    return model.predict_proba(population)[:, 1]


def _assign_strata(frame: pd.DataFrame, ranks: dict[str, np.ndarray], disagreement_rank: np.ndarray) -> np.ndarray:
    exact_wrong = (
        frame.sol_language_fidelity.eq("wrong language").fillna(False)
        | (frame.diag_target_script_mismatch.fillna(False)
           & frame.diag_metadata_language_disagreement.fillna(False))
    ).to_numpy()
    exact_technical = (
        frame.sol_technical_failure.notna()
        & frame.sol_technical_failure.ne("none")
    ).to_numpy()
    refusal_rank = _percentile_rank(
        frame.dsl_prediction_clean_genuine_refusal.to_numpy(float)
    )
    capability_rank = _percentile_rank(
        frame.dsl_prediction_capability_failure.to_numpy(float)
    )
    out = np.full(len(frame), "general_remainder", dtype=object)
    out[disagreement_rank >= .85] = "stage_b_disagreement_signal"
    incoherent = np.maximum(capability_rank, ranks["incoherent_garbled"]) >= .90
    out[incoherent] = "incoherent_signal"
    pivot = ((refusal_rank >= .90) & (refusal_rank < .97)) | (ranks["coherent_pivot"] >= .98)
    out[pivot] = "pivot_signal"
    out[refusal_rank >= .97] = "genuine_refusal_signal"
    out[exact_technical | (ranks["technical_degeneration"] >= .98)] = "technical_signal"
    out[ranks["wrong_language"] >= .98] = "wrong_language_signal"
    out[exact_wrong] = "wrong_language_signal"
    return out


def build_routing_population(
    root: Path, pilot_dir: Path, seed: int = 20260823
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """Recreate the frozen v2 routing strata used by planning and sampling.

    The returned mask identifies rows eligible for the next wave after the
    completed 300-row probability pilot is excluded.  Keeping this logic in
    one function prevents the realized draw from drifting from the approved
    simulation's routing rules.
    """
    population, human, _ = _planning_frame(root, pilot_dir)
    ranks_human: dict[str, np.ndarray] = {}
    ranks_population: dict[str, np.ndarray] = {}
    for offset, target in enumerate(ROUTING_TARGETS, start=1):
        y = human.primary_class.eq(target).astype(int).to_numpy()
        oof, pop = _crossfit_scores(human, population, y, seed + offset)
        ranks_human[target] = _percentile_rank(oof)
        ranks_population[target] = _percentile_rank(pop)

    stage_b_y, evaluation = _stage_b_disagreement_target(pilot_dir, human)
    disagreement_population = _fit_stage_b_disagreement(
        population, evaluation, stage_b_y, seed + 50
    )
    disagreement_human = _fit_stage_b_disagreement(
        human, evaluation, stage_b_y, seed + 50
    )
    human["routing_stratum"] = _assign_strata(
        human, ranks_human, _percentile_rank(disagreement_human)
    )
    population["routing_stratum"] = _assign_strata(
        population, ranks_population, _percentile_rank(disagreement_population)
    )
    base_keys = set(map(tuple, human[KEY].itertuples(index=False, name=None)))
    candidate_mask = ~population[KEY].apply(tuple, axis=1).isin(base_keys).to_numpy()
    return population, human, candidate_mask


def _yield_calibration(human: pd.DataFrame) -> pd.DataFrame:
    rows = []
    weights_all = 1 / human.inclusion_probability.to_numpy(float)
    for stratum in ROUTING_STRATA:
        domain = human.routing_stratum.eq(stratum).to_numpy()
        weights = np.where(domain, weights_all, 0.0)
        n = int(domain.sum())
        effective_n = float(weights.sum() ** 2 / np.square(weights).sum()) if n else 0.0
        for target in ROUTING_TARGETS:
            y = human.primary_class.eq(target).to_numpy(float)
            events = int(np.sum(domain & (y > .5)))
            if n:
                rate = float(np.sum(weights * y) / weights.sum())
                alpha = .5 + rate * effective_n
                beta = .5 + (1 - rate) * effective_n
            else:
                rate = alpha = beta = np.nan
            rows.append({
                "routing_stratum": stratum,
                "target_class": target,
                "human_sample_n": n,
                "human_events": events,
                "human_effective_n": effective_n,
                "weighted_rate": rate,
                "posterior_alpha": alpha,
                "posterior_beta": beta,
                "calibration_status": "observed" if n else "no_human_overlap",
            })
    return pd.DataFrame(rows)


def _simulate_yields(calibration: pd.DataFrame, allocations: pd.DataFrame, seed: int, simulations: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    # Reconstruct a conservative Jeffreys fallback from all 300 labels.
    global_lookup = {}
    for target in ROUTING_TARGETS:
        part = calibration.loc[calibration.target_class.eq(target)]
        events = int(part.human_events.sum())
        total = int(part.human_sample_n.sum())
        global_lookup[target] = (.5 + events, .5 + total - events)
    for workload in WORKLOADS:
        plan = allocations.loc[allocations.workload.eq(workload)]
        for target in ROUTING_TARGETS:
            draws = np.zeros(simulations, dtype=int)
            fallback_n = 0
            for item in plan.itertuples(index=False):
                cal = calibration.loc[
                    calibration.routing_stratum.eq(item.routing_stratum)
                    & calibration.target_class.eq(target)
                ].iloc[0]
                if cal.calibration_status == "observed":
                    alpha, beta = float(cal.posterior_alpha), float(cal.posterior_beta)
                else:
                    alpha, beta = global_lookup[target]
                    fallback_n += int(item.planned_draw_n)
                p = rng.beta(alpha, beta, size=simulations)
                draws += rng.binomial(int(item.planned_draw_n), p)
            rows.append({
                "workload": workload,
                "target_class": target,
                "expected_new_labels": float(draws.mean()),
                "q05_new_labels": float(np.quantile(draws, .05)),
                "q95_new_labels": float(np.quantile(draws, .95)),
                "probability_meet_readiness_target": (
                    float(np.mean(draws >= READINESS_TARGETS[target]))
                    if target in READINESS_TARGETS else np.nan
                ),
                "readiness_target": READINESS_TARGETS.get(target),
                "global_fallback_allocated_n": fallback_n,
                "simulation_status": "posterior_predictive_planning_only",
            })
    return pd.DataFrame(rows)


def _allocation_frame(candidate: pd.DataFrame) -> pd.DataFrame:
    counts = candidate.routing_stratum.value_counts()
    rows = []
    for workload, values in ALLOCATIONS.items():
        if sum(values) != workload:
            raise ValueError(f"allocation does not sum to {workload}")
        for stratum, n in zip(ROUTING_STRATA, values):
            N = int(counts.get(stratum, 0))
            if N < n:
                raise ValueError(f"routing stratum {stratum} cannot support workload {workload}")
            rows.append({
                "workload": workload,
                "routing_stratum": stratum,
                "candidate_population_n": N,
                "planned_draw_n": n,
                "conditional_wave_probability": n / N,
                "draw_status": "not_drawn_simulation_only",
            })
    return pd.DataFrame(rows)


def _coefficient_specs(population: pd.DataFrame) -> list[tuple[str, str, np.ndarray]]:
    specs: list[tuple[str, str, np.ndarray]] = []

    def mean_coeff(mask: np.ndarray) -> np.ndarray:
        n = int(mask.sum())
        return np.where(mask, 1 / n, 0.0) if n else np.zeros(len(mask))

    specs.append(("overall_prevalence", "all", mean_coeff(np.ones(len(population), dtype=bool))))
    english = population.prompt_language.eq("en").to_numpy()
    for language in sorted(set(population.prompt_language) - {"en"}):
        other = population.prompt_language.eq(language).to_numpy()
        specs.append(("language_difference_vs_english", language, mean_coeff(other) - mean_coeff(english)))
    for jurisdiction in sorted(population.jurisdiction.dropna().unique()):
        home = (population.jurisdiction.eq(jurisdiction) & population.home_status.eq("home")).to_numpy()
        away = (population.jurisdiction.eq(jurisdiction) & population.home_status.eq("away")).to_numpy()
        if home.sum() and away.sum():
            specs.append(("home_minus_away_proxy", jurisdiction, mean_coeff(home) - mean_coeff(away)))
    boundary = population.controversy_tier.eq("boundary_testing").to_numpy()
    regular = population.controversy_tier.eq("regular").to_numpy()
    specs.append(("boundary_minus_regular_proxy", "all", mean_coeff(boundary) - mean_coeff(regular)))
    temporal = population.route.eq("temporal").to_numpy()
    perennial = population.route.eq("perennial").to_numpy()
    specs.append(("temporal_minus_perennial_proxy", "all", mean_coeff(temporal) - mean_coeff(perennial)))
    for model in sorted(population.model.unique()):
        specs.append(("model_prevalence", model, mean_coeff(population.model.eq(model).to_numpy())))
    for model in sorted(population.model.unique()):
        for language in sorted(population.prompt_language.unique()):
            mask = (population.model.eq(model) & population.prompt_language.eq(language)).to_numpy()
            if mask.sum():
                specs.append(("model_language_prevalence", f"{model}|{language}", mean_coeff(mask)))
    return specs


def _precision_proxies(population: pd.DataFrame, candidate_mask: np.ndarray, allocations: pd.DataFrame) -> pd.DataFrame:
    candidate = population.loc[candidate_mask].copy()
    specs = _coefficient_specs(population)
    rows = []
    for workload in WORKLOADS:
        plan = allocations.loc[allocations.workload.eq(workload)].set_index("routing_stratum")
        for family, cell, coefficients in specs:
            coeff = coefficients[candidate_mask]
            variance = 0.0
            for stratum in ROUTING_STRATA:
                mask = candidate.routing_stratum.eq(stratum).to_numpy()
                N = int(mask.sum())
                n = int(plan.loc[stratum, "planned_draw_n"])
                # Conditional worst-case Bernoulli residual variance.  The
                # coefficient may be zero for rows outside the estimand domain.
                second_moment = float(np.mean(np.square(coeff[mask]) * .25))
                variance += (N ** 2) * (1 - n / N) * second_moment / n
            se = float(np.sqrt(max(variance, 0)))
            rows.append({
                "workload": workload,
                "estimand_family": family,
                "estimand_cell": cell,
                "worst_case_phase2_se": se,
                "worst_case_95_half_width": 1.96 * se,
                "method": "conditional stratified-SRS residual proxy with Var(Y-m)<=0.25",
                "accepted_interval": False,
            })
    return pd.DataFrame(rows)


def _coverage(candidate: pd.DataFrame, allocations: pd.DataFrame) -> pd.DataFrame:
    rows = []
    families = {
        "language": ["prompt_language"],
        "model": ["model"],
        "model_language": ["model", "prompt_language"],
        "jurisdiction_home": ["jurisdiction", "home_status"],
        "tier": ["controversy_tier"],
        "route": ["route"],
    }
    for workload in WORKLOADS:
        plan = allocations.loc[allocations.workload.eq(workload)].set_index("routing_stratum")
        for family, columns in families.items():
            grouped = candidate.groupby(columns, dropna=False)
            for key, part in grouped:
                expected = 0.0
                for stratum, sub in part.groupby("routing_stratum"):
                    N = int((candidate.routing_stratum == stratum).sum())
                    expected += float(plan.loc[stratum, "planned_draw_n"]) * len(sub) / N
                key_tuple = key if isinstance(key, tuple) else (key,)
                rows.append({
                    "workload": workload,
                    "coverage_family": family,
                    "coverage_cell": "|".join(map(str, key_tuple)),
                    "expected_new_rows": expected,
                })
    return pd.DataFrame(rows)


def _write_report(
    path: Path,
    pools: pd.DataFrame,
    yields: pd.DataFrame,
    precision: pd.DataFrame,
    coverage: pd.DataFrame,
    recommendation: dict,
) -> None:
    lines = [
        "# Human rare-class enrichment design simulation v2",
        "",
        "> **Planning only.** No response IDs were selected, no translation or review payload was created, "
        "and no network or paid call was made.",
        "",
        "This replaces the superseded v1 simulation. It uses the complete-language v3 human freeze and "
        "the completed Stage B disagreement evidence. Stage B covers only 84 rows, so its predictions are "
        "not misrepresented as population labels: a classifier transfers only the label-blind pattern of "
        "cross-model disagreement to population features.",
        "",
        "## Candidate routing pools",
        "",
        "| Stratum | Candidate rows | Models | Languages | Issues |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in pools.itertuples(index=False):
        lines.append(
            f"| {row.routing_stratum.replace('_', ' ')} | {row.candidate_population_n:,} | "
            f"{row.models} | {row.languages} | {row.issues} |"
        )
    lines.extend(["", "## Expected rare-class yield", "", "Posterior-predictive ranges are planning quantities, not confidence intervals.", "",
                  "| Workload | Class | Expected | 90% range | P(meet target) |",
                  "|---:|---|---:|---:|---:|"])
    for row in yields.itertuples(index=False):
        probability = "--" if pd.isna(row.probability_meet_readiness_target) else f"{100*row.probability_meet_readiness_target:.1f}%"
        lines.append(f"| {row.workload} | {row.target_class.replace('_', ' ')} | {row.expected_new_labels:.1f} | {row.q05_new_labels:.0f}-{row.q95_new_labels:.0f} | {probability} |")
    summary = precision.groupby(["workload", "estimand_family"]).worst_case_95_half_width.max().reset_index()
    lines.extend(["", "## Worst-case phase-two precision proxies", "", "These are conditional design-planning half-widths under stratified SRS and the conservative bound Var(Y-m) <= 0.25. They are not accepted confidence intervals and do not include first-wave, cross-fit, or issue-bootstrap uncertainty.", "",
                  "| Workload | Estimand family | Maximum 95% half-width |",
                  "|---:|---|---:|"])
    for row in summary.itertuples(index=False):
        lines.append(f"| {row.workload} | {row.estimand_family.replace('_', ' ')} | {row.worst_case_95_half_width:.3f} |")
    coverage_min = coverage.groupby(["workload", "coverage_family"]).expected_new_rows.min().reset_index()
    lines.extend(["", "## Minimum expected coverage", "", "| Workload | Family | Minimum expected new rows in any cell |", "|---:|---|---:|"])
    for row in coverage_min.itertuples(index=False):
        lines.append(f"| {row.workload} | {row.coverage_family.replace('_', ' ')} | {row.expected_new_rows:.1f} |")
    lines.extend(["", "## Recommendation", "", recommendation["narrative"], "", "The next gate is approval of the workload and sequential sampling contract. Only after approval may IDs be drawn and a separately hashed translation payload be prepared.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def simulate_enrichment_design_v2(
    root: Path,
    pilot_dir: Path,
    output_dir: Path | None = None,
    seed: int = 20260823,
    simulations: int = 10_000,
) -> dict:
    """Compare 150/250/400/600-row plans without drawing response IDs."""
    output_dir = output_dir or pilot_dir / "enrichment_simulation_v2"
    manifest_path = output_dir / "simulation_manifest.json"
    stage_b = pilot_dir / "surrogate_bakeoff_stage_b_v1"
    inputs = {
        "pilot_manifest": sha_file(pilot_dir / "pilot_manifest.json"),
        "complete_language_v3_manifest": sha_file(pilot_dir / "base_freeze_v3_complete_language_review" / "freeze_manifest.json"),
        "complete_language_v3_labels": sha_file(pilot_dir / "base_freeze_v3_complete_language_review" / "base_labels.parquet"),
        "stage_b_manifest": sha_file(stage_b / "stage_b_manifest.json"),
        "stage_b_results": sha_file(stage_b / "stage_b_results.jsonl"),
        "stage_b_disagreements": sha_file(stage_b / "stage_b_row_disagreements.csv"),
    }
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("input_sha256") != inputs:
            raise RuntimeError("existing v2 enrichment simulation has different frozen inputs")
        for name, expected in existing["artifact_sha256"].items():
            if sha_file(output_dir / name) != expected:
                raise RuntimeError(f"v2 enrichment artifact changed: {name}")
        return existing
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested v2 simulation directory: {output_dir}")

    population, human, candidate_mask = build_routing_population(root, pilot_dir, seed)
    candidate = population.loc[candidate_mask].copy()
    allocations = _allocation_frame(candidate)
    calibration = _yield_calibration(human)
    yields = _simulate_yields(calibration, allocations, seed, simulations)
    precision = _precision_proxies(population, candidate_mask, allocations)
    coverage = _coverage(candidate, allocations)

    pools = candidate.groupby("routing_stratum", as_index=False).agg(
        candidate_population_n=("prompt_id", "size"),
        models=("model", "nunique"), languages=("prompt_language", "nunique"),
        issues=("issue_id", "nunique"),
    ).set_index("routing_stratum").reindex(ROUTING_STRATA).reset_index()
    if pools.candidate_population_n.isna().any():
        raise ValueError("every declared v2 routing stratum must be nonempty")
    pools.candidate_population_n = pools.candidate_population_n.astype(int)

    recommended = 400
    continuation = 600
    recommendation = {
        "status": "simulation_only_design_approval_required",
        "recommended_workload": recommended,
        "candidate_surrogates_for_future_evaluation": [
            "openai/gpt-5.6-luna|zero_shot_joint_v1",
            "openai/gpt-5.6-luna|fewshot_error_targeted_22_v1",
        ],
        "conditional_continuation_workload": continuation,
        "decision_rule": "start at 400; stop if realized rare-class targets are met, otherwise draw the predeclared incremental allocation to 600",
        "narrative": (
            "Use **400 new human-coded responses as the initial wave**, then stop if the frozen realized counts reach "
            "20 genuine refusals, 15 pivots, 20 wrong-language outputs, and 12 technical degenerations. If any target "
            "is missed, use the predeclared stratum-specific increment to a cumulative **600**. This recommendation "
            "balances burden and rare-class support; it does not claim that the conservative cell-level precision "
            "proxies meet a publication threshold. It is not authorization to draw either wave."
        ),
        "sample_drawn": False,
        "row_level_candidate_ids_written": False,
        "translation_payload_created": False,
        "network_call_made": False,
        "additional_human_work_authorized": False,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "candidate_pool_summary.csv": pools,
        "workload_allocations.csv": allocations,
        "human_yield_calibration.csv": calibration,
        "workload_yield_simulation.csv": yields,
        "estimand_precision_proxy.csv": precision,
        "coverage_expectations.csv": coverage,
    }
    for name, frame in artifacts.items():
        frame.to_csv(output_dir / name, index=False)
    (output_dir / "recommendation.json").write_text(json.dumps(recommendation, indent=2), encoding="utf-8")
    report_path = root / "docs" / "HUMAN_ENRICHMENT_DESIGN_V2.md"
    _write_report(report_path, pools, yields, precision, coverage, recommendation)
    artifact_paths = [output_dir / name for name in artifacts] + [output_dir / "recommendation.json"]
    manifest = {
        "simulation_version": "human-enrichment-simulation-v2.0",
        "created_at": _now(),
        "seed": seed,
        "posterior_predictive_draws": simulations,
        "input_sha256": inputs,
        "workloads": list(WORKLOADS),
        "routing_targets": list(ROUTING_TARGETS),
        "routing_strata": list(ROUTING_STRATA),
        "stage_b_use": "84-row disagreement pattern only; no population Stage B labels exist",
        "human_score_use": "issue-grouped OOF on the 300-row complete-language v3 freeze",
        "sampling_contract_if_approved": "independent SRSWOR in mutually exclusive frozen routing strata; sequential inclusion probability retained",
        "repeat_rows_read_or_analyzed": False,
        "sample_drawn": False,
        "row_level_candidate_ids_written": False,
        "translation_payload_created": False,
        "network_call_made": False,
        "paid_call_authorized": False,
        "simulation_hash": sha_text(yields.to_csv(index=False) + precision.to_csv(index=False)),
        "recommendation": recommendation,
        "artifact_sha256": {path.name: sha_file(path) for path in artifact_paths},
        "documentation": {"path": report_path.relative_to(root).as_posix(), "sha256": sha_file(report_path)},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
