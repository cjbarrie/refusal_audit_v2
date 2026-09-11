"""Simulate label-blind enrichment workloads for the human validity study.

This module is planning-only: it creates no sample IDs, review packet, model
payload, or network request.  Human labels are read exclusively from the
immutable 300-row base freeze, never from the live append-only log or repeat
packet.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta as beta_distribution
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .human_pilot import KEY, sha_file, sha_text


TARGET_CLASS = {
    "wrong_language": "wrong_language",
    "technical_degeneration": "technical_degeneration",
    "ambiguous": "ambiguous",
    "coherent_pivot": "coherent_pivot",
}
TARGET_DEFICIT = {
    "wrong_language": 14,
    "technical_degeneration": 10,
    "ambiguous": 10,
    "coherent_pivot": 6,
}
WORKLOAD_ALLOCATIONS = {
    60: {
        "sol_exact_wrong_signal": 20,
        "diagnostic_wrong_signal": 10,
        "learned_technical_signal": 10,
        "learned_ambiguous_signal": 10,
        "learned_pivot_signal": 10,
    },
    100: {
        "sol_exact_wrong_signal": 30,
        "diagnostic_wrong_signal": 15,
        "learned_technical_signal": 20,
        "learned_ambiguous_signal": 20,
        "learned_pivot_signal": 15,
    },
    150: {
        "sol_exact_wrong_signal": 40,
        "diagnostic_wrong_signal": 20,
        "learned_technical_signal": 30,
        "learned_ambiguous_signal": 30,
        "learned_pivot_signal": 30,
    },
}

NUMERIC_FEATURES = [
    "engagement_code", "diag_char_count", "diag_token_count", "diag_replacement_rate",
    "diag_control_rate", "diag_target_script_share", "diag_unique_token_ratio",
    "diag_repeated_trigram_ratio", "diag_prompt_echo_overlap", "diag_punctuation_rate",
    "diag_target_script_mismatch", "diag_repetition_loop", "diag_truncation_suspect",
    "diag_metadata_language_disagreement", "dsl_prediction_clean_genuine_refusal",
    "dsl_prediction_capability_failure", "dsl_prediction_coherent_pivot",
]
CATEGORICAL_FEATURES = [
    "prompt_language", "model", "jurisdiction", "home_status", "control_length_band",
    "topic_domain", "region_focus", "controversy_tier", "route",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _successful_sol_components(root: Path) -> pd.DataFrame:
    paths = [
        root / "annotations" / "response_validity_dsl_v1" / "sol_reference_labels.jsonl",
        root / "annotations" / "response_validity_dsl_v1_1" / "sol_augmentation_labels.jsonl",
    ]
    rows: list[dict] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("status") != "ok":
                continue
            label = record["label"]
            rows.append({
                **{key: record[key] for key in KEY},
                "sol_language_fidelity": label["language_fidelity"],
                "sol_technical_failure": label["technical_failure"],
                "sol_confidence": label["confidence"],
                "sol_coherent_pivot": bool(record["derived"]["coherent_pivot"]),
            })
    out = pd.DataFrame(rows)
    if len(out) != 14_182 or out.duplicated(KEY).any():
        raise ValueError("successful Sol component labels must cover 14,182 unique response keys")
    return out


def _planning_frame(root: Path, pilot_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    pilot_manifest = json.loads((pilot_dir / "pilot_manifest.json").read_text(encoding="utf-8"))
    population_path = root / pilot_manifest["population_path"]
    pseudo_path = root / pilot_manifest["pseudo_path"]
    if sha_file(population_path) != pilot_manifest["population_sha256"]:
        raise ValueError("population hash differs from the frozen human pilot")
    if sha_file(pseudo_path) != pilot_manifest["pseudo_sha256"]:
        raise ValueError("pseudo-outcome hash differs from the frozen human pilot")
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
        raise ValueError("planning population must contain 137,186 unique response keys")

    design = pd.read_parquet(pilot_dir / "pilot_design.parquet")
    labels = pd.read_parquet(pilot_dir / "base_freeze_v1" / "base_labels.parquet")
    human = design.merge(
        labels[["review_id", "primary_class", "confidence"]], on="review_id", validate="one_to_one"
    ).merge(
        population[KEY + [c for c in population.columns if c.startswith("sol_")]],
        on=KEY, how="left", validate="one_to_one",
    )
    if len(human) != 300:
        raise ValueError("enrichment simulation requires the immutable 300-row base freeze")
    return population, human, pilot_manifest


def _model_pipeline() -> Pipeline:
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("encode", OneHotEncoder(handle_unknown="ignore")),
    ])
    features = ColumnTransformer([
        ("numeric", numeric, NUMERIC_FEATURES),
        ("categorical", categorical, CATEGORICAL_FEATURES),
    ])
    classifier = LogisticRegression(
        C=0.5, class_weight="balanced", max_iter=2_000, solver="lbfgs",
        random_state=20260821,
    )
    return Pipeline([("features", features), ("classifier", classifier)])


def _crossfit_and_population_scores(
    human: pd.DataFrame,
    population: pd.DataFrame,
    target_class: str,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    y = human.primary_class.eq(target_class).astype(int).to_numpy()
    if y.sum() < 4:
        raise ValueError(f"at least four positives required for learned routing: {target_class}")
    weights = 1 / human.inclusion_probability.to_numpy(float)
    weights = np.minimum(weights, np.quantile(weights, .99))
    weights = weights / weights.mean()
    splitter = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed)
    oof = np.full(len(human), np.nan)
    base_model = _model_pipeline()
    for train, held in splitter.split(human, y, groups=human.issue_id):
        if len(np.unique(y[train])) != 2:
            raise ValueError(f"cross-fit training fold lacks a class for {target_class}")
        model = clone(base_model)
        model.fit(human.iloc[train], y[train], classifier__sample_weight=weights[train])
        oof[held] = model.predict_proba(human.iloc[held])[:, 1]
    if not np.isfinite(oof).all():
        raise ValueError(f"incomplete out-of-fold predictions for {target_class}")
    final = clone(base_model)
    final.fit(human, y, classifier__sample_weight=weights)
    population_score = final.predict_proba(population)[:, 1]
    return oof, population_score


def _percentile_rank(values: np.ndarray) -> np.ndarray:
    return pd.Series(values).rank(method="average", pct=True).to_numpy(float)


def _assign_strata(
    frame: pd.DataFrame,
    technical_rank: np.ndarray,
    ambiguous_rank: np.ndarray,
    pivot_rank: np.ndarray,
) -> np.ndarray:
    exact_wrong = frame.sol_language_fidelity.eq("wrong language").fillna(False).to_numpy()
    diagnostic_wrong = (
        frame.diag_target_script_mismatch.fillna(False)
        & frame.diag_metadata_language_disagreement.fillna(False)
    ).to_numpy()
    learned = np.column_stack([technical_rank, ambiguous_rank, pivot_rank])
    learned_name = np.asarray([
        "learned_technical_signal", "learned_ambiguous_signal", "learned_pivot_signal",
    ])
    winner = learned_name[np.argmax(learned, axis=1)]
    winner_score = learned.max(axis=1)
    out = np.full(len(frame), "general", dtype=object)
    out[winner_score >= .90] = winner[winner_score >= .90]
    out[diagnostic_wrong] = "diagnostic_wrong_signal"
    out[exact_wrong] = "sol_exact_wrong_signal"
    return out


def _posterior_parameters(
    human: pd.DataFrame,
    strata: list[str],
    targets: list[str],
) -> pd.DataFrame:
    rows: list[dict] = []
    for stratum in strata:
        domain = human.enrichment_stratum.eq(stratum).to_numpy()
        weights = np.where(domain, 1 / human.inclusion_probability.to_numpy(float), 0.0)
        n = int(domain.sum())
        effective_n = float(weights.sum() ** 2 / np.square(weights).sum()) if n else 0.0
        for target in targets:
            y = human.primary_class.eq(TARGET_CLASS[target]).to_numpy(float)
            if n:
                rate = float(np.sum(weights * y) / weights.sum())
                events = int(np.sum(domain & (y > .5)))
            else:
                rate, events = np.nan, 0
            alpha = np.nan if not n else .5 + rate * effective_n
            beta = np.nan if not n else .5 + (1 - rate) * effective_n
            rows.append({
                "enrichment_stratum": stratum,
                "target_class": target,
                "human_sample_n": n,
                "human_events": events,
                "human_effective_n": effective_n,
                "weighted_rate": rate,
                "posterior_alpha": alpha,
                "posterior_beta": beta,
                "posterior_mean": np.nan if not n else alpha / (alpha + beta),
                "posterior_q05": np.nan if not n else beta_distribution.ppf(.05, alpha, beta),
                "posterior_q95": np.nan if not n else beta_distribution.ppf(.95, alpha, beta),
                "calibration_status": "observed_human_events" if events else (
                    "zero_human_events" if n else "no_human_overlap"
                ),
            })
    return pd.DataFrame(rows)


def _write_report(
    path: Path,
    pool_summary: pd.DataFrame,
    allocations: pd.DataFrame,
    scenarios: pd.DataFrame,
    recommendation: dict,
) -> None:
    lines = [
        "# Human rare-class enrichment design simulation",
        "",
        "> **Status: planning only.** No response IDs were selected, no review packet or translation "
        "payload was created, and no network or paid model call was made. Additional human work is not authorized.",
        "",
        "## Why an enrichment wave is needed",
        "",
        "The immutable 300-row human pilot cannot yet support a clean exemplar/evaluation split for all seven "
        "primary classes. The realized deficits are 14 wrong-language, 10 technical-degeneration, 10 ambiguous, "
        "and 6 coherent-pivot judgments. These are realized-class deficits: a label-blind draw must be larger "
        "because true classes are unknown until coding.",
        "",
        "## Label-blind routing",
        "",
        "Candidate strata are disjoint and applied in this order:",
        "",
        "1. exact GPT-5.6 Sol wrong-language signal;",
        "2. deterministic script plus metadata language mismatch;",
        "3. the maximum of technical, ambiguous, and pivot routing scores when that score is in its population top decile;",
        "4. general remainder.",
        "",
        "The three learned routing scores use four-fold, issue-grouped out-of-fold predictions on the frozen human "
        "pilot and regularized full-sample logistic scores only to define population strata. They are planning tools, "
        "not outcome predictions or validation results. The 300 base response keys are excluded from every pool.",
        "",
        "| Routing stratum | Candidate rows | Models | Languages | Issues |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in pool_summary.itertuples(index=False):
        lines.append(
            f"| {row.enrichment_stratum.replace('_', ' ')} | {int(row.candidate_population_n):,} | "
            f"{int(row.models)} | {int(row.languages)} | {int(row.issues)} |"
        )
    lines.extend([
        "",
        "## Workload scenarios",
        "",
        "Each declared draw would be independent SRSWOR within a frozen routing stratum. The values below are "
        "allocations only; no draw has occurred.",
        "",
        "| Workload | Sol exact wrong | Diagnostic wrong | Technical score | Ambiguous score | Pivot score |",
        "|---:|---:|---:|---:|---:|---:|",
    ])
    for workload in sorted(allocations.workload.unique()):
        x = allocations.loc[allocations.workload.eq(workload)].set_index("enrichment_stratum")
        lines.append(
            f"| {workload} | {int(x.loc['sol_exact_wrong_signal'].planned_draw_n)} | "
            f"{int(x.loc['diagnostic_wrong_signal'].planned_draw_n)} | "
            f"{int(x.loc['learned_technical_signal'].planned_draw_n)} | "
            f"{int(x.loc['learned_ambiguous_signal'].planned_draw_n)} | "
            f"{int(x.loc['learned_pivot_signal'].planned_draw_n)} |"
        )
    lines.extend([
        "",
        "Posterior-predictive yields below include only strata with actual human overlap. Allocations in the exact "
        "Sol wrong-language stratum have no human calibration and are carried as unidentified rather than assigned "
        "an arbitrary prior yield.",
        "",
        "| Workload | Target | Expected calibrated yield | 90% planning range | P(fill current deficit) | Uncalibrated allocated rows |",
        "|---:|---|---:|---:|---:|---:|",
    ])
    for row in scenarios.itertuples(index=False):
        if pd.isna(row.expected_new_labels):
            expected, spread, probability = "unidentified", "unidentified", "unidentified"
        else:
            expected = f"{row.expected_new_labels:.1f}"
            spread = f"{row.q05_new_labels:.0f}–{row.q95_new_labels:.0f}"
            probability = f"{100 * row.probability_fill_deficit:.1f}%"
        lines.append(
            f"| {int(row.workload)} | {row.target_class.replace('_', ' ')} | {expected} | {spread} | "
            f"{probability} | {int(row.uncalibrated_allocated_n)} |"
        )
    lines.extend([
        "",
        "## Recommendation and stopping rule",
        "",
        f"The recommended initial workload is **{recommendation['recommended_initial_workload']} screening rows**, "
        "not 100 or 150 immediately. Wrong-language yield is unidentified because the base pilot observed no human "
        "wrong-language cases and none of its rows overlaps the exact Sol wrong-language pool. The 60-row screen "
        "provides direct calibration while limiting unnecessary coding if the routing signals are poor.",
        "",
        "After the screen is coded: freeze its judgments; estimate realized class yield by stratum; update the "
        "yield distributions; and select either the cumulative 100- or 150-row continuation. Development exemplars "
        "and held-out evaluation must then be split by `prompt_id`, with no prompt family crossing the split.",
        "",
        "## Inferential contract if a draw is approved",
        "",
        "For row `i` in routing stratum `h`, the enrichment-wave conditional probability is `n_h/N_h`. Combined "
        "with the original pilot probability, the final sequential inclusion probability is "
        "`1-(1-p_base_i)(1-p_enrichment_i | frozen history)`. Stratum definitions, pool counts, random seed, and "
        "draw must be frozen before any new response is viewed. Every noncensus variance stratum requires at least "
        "two sampled rows. Deterministic selections may enter inference only as declared certainty units.",
        "",
        "The screen would also require literal English translations under a separately hashed payload and explicit "
        "cost authorization. This simulation does not create that payload or estimate/authorize its cost.",
        "",
        "## Reproduction",
        "",
        "Run `python scripts/response_validity.py simulate-human-enrichment`. The command reads the immutable base "
        "freeze and historical Sol component labels; it does not open the live label log or repeat packet. Outputs "
        "are under `annotations/response_validity_human_v2/enrichment_simulation_v1/`.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def simulate_enrichment_design(
    root: Path,
    pilot_dir: Path,
    output_dir: Path | None = None,
    seed: int = 20260821,
    simulations: int = 10_000,
) -> dict:
    """Compare cumulative 60/100/150-row plans without selecting any rows."""
    output_dir = output_dir or pilot_dir / "enrichment_simulation_v1"
    manifest_path = output_dir / "simulation_manifest.json"
    freeze_manifest_path = pilot_dir / "base_freeze_v1" / "freeze_manifest.json"
    pilot_manifest_path = pilot_dir / "pilot_manifest.json"
    inputs = {
        "base_freeze_manifest_sha256": sha_file(freeze_manifest_path),
        "pilot_manifest_sha256": sha_file(pilot_manifest_path),
        "sol_reference_labels_sha256": sha_file(
            root / "annotations" / "response_validity_dsl_v1" / "sol_reference_labels.jsonl"
        ),
        "sol_augmentation_labels_sha256": sha_file(
            root / "annotations" / "response_validity_dsl_v1_1" / "sol_augmentation_labels.jsonl"
        ),
    }
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("input_sha256") != inputs:
            raise RuntimeError("existing enrichment simulation uses different frozen inputs")
        for name, expected in existing.get("artifact_sha256", {}).items():
            path = output_dir / name
            if not path.exists() or sha_file(path) != expected:
                raise RuntimeError(f"enrichment simulation artifact missing or changed: {path}")
        documentation = existing.get("documentation", {})
        if documentation:
            documentation_path = root / documentation["path"]
            if not documentation_path.exists() or sha_file(documentation_path) != documentation["sha256"]:
                raise RuntimeError("enrichment simulation documentation is missing or changed")
        return existing
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested simulation directory: {output_dir}")

    population, human, pilot_manifest = _planning_frame(root, pilot_dir)
    score_specs = [
        ("technical_degeneration", "score_technical", seed + 1),
        ("ambiguous", "score_ambiguous", seed + 2),
        ("coherent_pivot", "score_pivot", seed + 3),
    ]
    for target, column, model_seed in score_specs:
        oof, population_score = _crossfit_and_population_scores(
            human, population, target, model_seed
        )
        human[column] = oof
        population[column] = population_score
    human["enrichment_stratum"] = _assign_strata(
        human,
        _percentile_rank(human.score_technical.to_numpy()),
        _percentile_rank(human.score_ambiguous.to_numpy()),
        _percentile_rank(human.score_pivot.to_numpy()),
    )
    population["enrichment_stratum"] = _assign_strata(
        population,
        _percentile_rank(population.score_technical.to_numpy()),
        _percentile_rank(population.score_ambiguous.to_numpy()),
        _percentile_rank(population.score_pivot.to_numpy()),
    )

    base_keys = set(map(tuple, human[KEY].itertuples(index=False, name=None)))
    candidate = population.loc[
        ~population[KEY].apply(tuple, axis=1).isin(base_keys)
    ].copy()
    strata = list(next(iter(WORKLOAD_ALLOCATIONS.values())).keys())
    pool_counts = candidate.enrichment_stratum.value_counts()
    if any(pool_counts.get(stratum, 0) < max(x[stratum] for x in WORKLOAD_ALLOCATIONS.values()) for stratum in strata):
        raise ValueError("at least one candidate stratum is too small for a declared workload")

    pool_rows: list[dict] = []
    for stratum in [*strata, "general"]:
        domain = candidate.loc[candidate.enrichment_stratum.eq(stratum)]
        pool_rows.append({
            "enrichment_stratum": stratum,
            "candidate_population_n": len(domain),
            "models": int(domain.model.nunique()),
            "languages": int(domain.prompt_language.nunique()),
            "issues": int(domain.issue_id.nunique()),
            "base_human_overlap_excluded": True,
        })
    pool_summary = pd.DataFrame(pool_rows)

    posterior = _posterior_parameters(human, strata, list(TARGET_CLASS))
    rng = np.random.default_rng(seed)
    scenario_rows: list[dict] = []
    allocation_rows: list[dict] = []
    for workload, allocation in WORKLOAD_ALLOCATIONS.items():
        if sum(allocation.values()) != workload:
            raise ValueError(f"allocation does not sum to workload {workload}")
        for stratum, draw_n in allocation.items():
            N = int(pool_counts[stratum])
            allocation_rows.append({
                "workload": workload,
                "enrichment_stratum": stratum,
                "candidate_population_n": N,
                "planned_draw_n": draw_n,
                "conditional_wave_probability": draw_n / N,
                "draw_status": "not_drawn_simulation_only",
            })
        for target, deficit in TARGET_DEFICIT.items():
            # Zero human target events make a posterior yield highly prior
            # driven.  Keep wrong-language output unidentified rather than
            # manufacturing a planning estimate from Jeffreys' prior.
            target_human_events = int(human.primary_class.eq(TARGET_CLASS[target]).sum())
            if target_human_events == 0:
                scenario_rows.append({
                    "workload": workload,
                    "target_class": target,
                    "current_human_count": target_human_events,
                    "readiness_deficit": deficit,
                    "expected_new_labels": np.nan,
                    "q05_new_labels": np.nan,
                    "q95_new_labels": np.nan,
                    "probability_fill_deficit": np.nan,
                    "uncalibrated_allocated_n": sum(allocation.values()),
                    "simulation_status": "unidentified_zero_human_events_screening_required",
                })
                continue
            total_yield = np.zeros(simulations, dtype=int)
            uncalibrated = False
            uncalibrated_allocated_n = 0
            for stratum, draw_n in allocation.items():
                row = posterior.loc[
                    posterior.enrichment_stratum.eq(stratum)
                    & posterior.target_class.eq(target)
                ].iloc[0]
                if row.calibration_status == "no_human_overlap":
                    uncalibrated = True
                    uncalibrated_allocated_n += draw_n
                    # Do not let an arbitrary prior manufacture expected
                    # events.  Report the posterior-predictive yield only for
                    # strata with actual human calibration and carry these
                    # rows as an explicit unidentified allocation.
                    continue
                p = rng.beta(row.posterior_alpha, row.posterior_beta, size=simulations)
                total_yield += rng.binomial(draw_n, p)
            scenario_rows.append({
                "workload": workload,
                "target_class": target,
                "current_human_count": target_human_events,
                "readiness_deficit": deficit,
                "expected_new_labels": float(total_yield.mean()),
                "q05_new_labels": float(np.quantile(total_yield, .05)),
                "q95_new_labels": float(np.quantile(total_yield, .95)),
                "probability_fill_deficit": float(np.mean(total_yield >= deficit)),
                "uncalibrated_allocated_n": uncalibrated_allocated_n,
                "simulation_status": (
                    "partially_uncalibrated_stratum_overlap" if uncalibrated
                    else "posterior_predictive_planning_only"
                ),
            })
    scenarios = pd.DataFrame(scenario_rows)
    allocations = pd.DataFrame(allocation_rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    pool_path = output_dir / "candidate_pool_summary.csv"
    posterior_path = output_dir / "human_yield_calibration.csv"
    allocation_path = output_dir / "workload_allocations.csv"
    scenario_path = output_dir / "workload_yield_simulation.csv"
    pool_summary.to_csv(pool_path, index=False)
    posterior.to_csv(posterior_path, index=False)
    allocations.to_csv(allocation_path, index=False)
    scenarios.to_csv(scenario_path, index=False)

    recommendation = {
        "status": "screening_wave_recommended_not_drawn",
        "recommended_initial_workload": 60,
        "reason": (
            "wrong-language yield is unidentified because the base pilot contains zero human cases; "
            "start with the 60-row screening allocation and adapt only after observing its class yield"
        ),
        "adaptation_rule": (
            "freeze screening labels, update class-yield posteriors, then choose cumulative 100 or 150; "
            "do not reuse development exemplars in held-out evaluation"
        ),
        "sample_drawn": False,
        "review_packet_created": False,
        "network_call_made": False,
        "additional_human_work_authorized": False,
    }
    recommendation_path = output_dir / "recommendation.json"
    recommendation_path.write_text(json.dumps(recommendation, indent=2), encoding="utf-8")

    report_path = root / "docs" / "HUMAN_ENRICHMENT_DESIGN.md"
    _write_report(report_path, pool_summary, allocations, scenarios, recommendation)

    artifacts = [pool_path, posterior_path, allocation_path, scenario_path, recommendation_path]
    manifest = {
        "simulation_version": "human-enrichment-simulation-v1.0",
        "created_at": _utc_now(),
        "seed": seed,
        "posterior_predictive_draws": simulations,
        "input_sha256": inputs,
        "workloads": sorted(WORKLOAD_ALLOCATIONS),
        "routing": (
            "Sol exact wrong-language signal, then deterministic wrong-language diagnostics, then maximum "
            "90th-percentile issue-cross-fitted human logistic score for technical, ambiguous, or pivot"
        ),
        "future_sampling_contract": (
            "independent SRSWOR within frozen disjoint routing strata; final inclusion probability "
            "1-(1-p_base)*(1-p_enrichment_given_history)"
        ),
        "base_rows_excluded_from_candidate_pools": True,
        "repeat_rows_read_or_analyzed": False,
        "sample_drawn": False,
        "row_level_candidate_ids_written": False,
        "review_packet_created": False,
        "network_call_made": False,
        "paid_call_authorized": False,
        "simulation_hash": sha_text(scenarios.to_csv(index=False)),
        "artifact_sha256": {path.name: sha_file(path) for path in artifacts},
        "documentation": {
            "path": report_path.relative_to(root).as_posix(),
            "sha256": sha_file(report_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
