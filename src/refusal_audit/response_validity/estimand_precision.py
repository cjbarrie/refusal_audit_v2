"""Local, design-based precision audit for human response-validity estimands.

This module answers a narrow planning question: does the frozen 300-response
probability sample already give adequate *human-label* precision for each
candidate paper estimand?  It makes no provider call and never reads the sealed
enrichment evaluation reserve.  The 161 exposed enrichment-development cases
may train a prediction rule, but only the original 300 known-probability human
labels enter residual correction or design-variance estimation.

Every audited statistic is represented as ``theta = sum_i a_i Y_i``.  The
model-assisted estimator is therefore

    sum_i a_i m_i + sum_{i in S} a_i (Y_i - m_i) / pi_i,

with exact first- and second-order inclusion probabilities for the frozen union
sample.  The audit conditions on the delivered 137,186-response population; it
isolates phase-two human-label uncertainty and does not replace the canonical
whole-issue uncertainty calculation.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .human_audit import exact_union_pairwise_inclusion
from .human_pilot import KEY, sha_file


OUTCOME_CLASSES = {
    "genuine_refusal": {"genuine_refusal"},
    "capability_failure": {
        "incoherent_garbled", "wrong_language", "technical_degeneration",
    },
    "coherent_pivot": {"coherent_pivot"},
    "coherent_noncompliance": {"genuine_refusal", "coherent_pivot"},
}

SOL_COLUMNS = {
    "genuine_refusal": "dsl_prediction_clean_genuine_refusal",
    "capability_failure": "dsl_prediction_capability_failure",
    "coherent_pivot": "dsl_prediction_coherent_pivot",
}

NUMERIC_FEATURES = [
    "engagement_code", "diag_char_count", "diag_token_count",
    "diag_replacement_rate", "diag_control_rate", "diag_target_script_share",
    "diag_unique_token_ratio", "diag_repeated_trigram_ratio",
    "diag_prompt_echo_overlap", "diag_punctuation_rate",
    "dsl_prediction_clean_genuine_refusal",
    "dsl_prediction_capability_failure", "dsl_prediction_coherent_pivot",
]

BOOLEAN_FEATURES = [
    "diag_target_script_mismatch", "diag_repetition_loop",
    "diag_truncation_suspect", "diag_metadata_language_disagreement",
]

CATEGORICAL_FEATURES = [
    "model", "prompt_language", "topic_domain", "region_focus",
    "controversy_tier", "route", "home_status", "control_length_band",
    "response_language", "refusal_justification",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _outcomes(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    for name, classes in OUTCOME_CLASSES.items():
        out[name] = frame.primary_class.isin(classes).astype(float)
    return out


def _feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = set(NUMERIC_FEATURES + BOOLEAN_FEATURES + CATEGORICAL_FEATURES)
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"prediction features absent: {missing}")
    out = frame[NUMERIC_FEATURES + BOOLEAN_FEATURES + CATEGORICAL_FEATURES].copy()
    for col in BOOLEAN_FEATURES:
        out[col] = out[col].fillna(False).astype(int)
    for col in CATEGORICAL_FEATURES:
        out[col] = out[col].fillna("<missing>").astype(str)
    return out


def _fit_development_predictors(
    development: pd.DataFrame, population: pd.DataFrame,
) -> dict[str, np.ndarray]:
    """Fit fixed local logistic rules using exposed development labels only."""
    x_dev = _feature_frame(development)
    x_pop = _feature_frame(population)
    y_dev = _outcomes(development)
    numeric = NUMERIC_FEATURES + BOOLEAN_FEATURES
    transformer = ColumnTransformer([
        ("numeric", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), numeric),
        ("categorical", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore", min_frequency=2)),
        ]), CATEGORICAL_FEATURES),
    ])
    predictions: dict[str, np.ndarray] = {}
    for outcome in OUTCOME_CLASSES:
        y = y_dev[outcome].to_numpy(int)
        if np.unique(y).size < 2:
            predictions[outcome] = np.repeat(float(y.mean()), len(population))
            continue
        model = Pipeline([
            ("features", transformer),
            ("classifier", LogisticRegression(
                C=0.5, class_weight="balanced", max_iter=2_000,
                solver="liblinear", random_state=20260825,
            )),
        ])
        model.fit(x_dev, y)
        predictions[outcome] = model.predict_proba(x_pop)[:, 1]
    return predictions


def _sol_predictors(population: pd.DataFrame) -> dict[str, np.ndarray]:
    out = {
        name: population[column].to_numpy(float)
        for name, column in SOL_COLUMNS.items()
    }
    out["coherent_noncompliance"] = np.clip(
        out["genuine_refusal"] + out["coherent_pivot"], 0, 1
    )
    return out


def _add_spec(
    specs: list[dict], family: str, cell: str, coefficients: np.ndarray,
    paper_role: str, target_half_width_pp: float,
) -> None:
    coefficients = np.asarray(coefficients, dtype=float)
    if not np.isfinite(coefficients).all() or np.allclose(coefficients, 0):
        return
    specs.append({
        "family": family,
        "cell": str(cell),
        "paper_role": paper_role,
        "target_half_width_pp": float(target_half_width_pp),
        "coefficients": coefficients,
    })


def build_estimand_coefficients(population: pd.DataFrame) -> list[dict]:
    """Build response-level linear coefficients matching Stage 17 families."""
    n = len(population)
    specs: list[dict] = []
    _add_spec(specs, "prevalence", "overall", np.repeat(1 / n, n), "main", 2.0)

    # Prompt-fixed language contrasts: average pairs within model, then models.
    languages = sorted(set(population.prompt_language.astype(str)) - {"en"})
    models = sorted(population.model.astype(str).unique())
    keyed = population.reset_index().set_index(["model", "prompt_id", "prompt_language"])
    for language in languages:
        a = np.zeros(n)
        valid_models: list[tuple[str, list[tuple[str, str]]]] = []
        for model in models:
            m = population.model.astype(str).eq(model)
            en = set(population.loc[m & population.prompt_language.eq("en"), "prompt_id"])
            target = set(population.loc[m & population.prompt_language.eq(language), "prompt_id"])
            pairs = sorted(en & target)
            if pairs:
                valid_models.append((model, pairs))
        for model, pairs in valid_models:
            w = 1 / (len(valid_models) * len(pairs))
            for prompt_id in pairs:
                a[int(keyed.loc[(model, prompt_id, language), "index"])] += w
                a[int(keyed.loc[(model, prompt_id, "en"), "index"])] -= w
        _add_spec(specs, "paired_language", language, a, "main", 3.0)

        for model, pairs in valid_models:
            am = np.zeros(n); w = 1 / len(pairs)
            for prompt_id in pairs:
                am[int(keyed.loc[(model, prompt_id, language), "index"])] += w
                am[int(keyed.loc[(model, prompt_id, "en"), "index"])] -= w
            _add_spec(
                specs, "paired_language_by_model", f"{language}||{model}", am,
                "exploratory", 8.0,
            )

    # Unpaired model-language prevalence is a competence diagnostic.
    for model in models:
        for language in sorted(population.prompt_language.astype(str).unique()):
            mask = population.model.astype(str).eq(model) & population.prompt_language.astype(str).eq(language)
            a = np.zeros(n); a[mask.to_numpy()] = 1 / int(mask.sum())
            _add_spec(
                specs, "model_language_prevalence", f"{model}||{language}", a,
                "diagnostic", 8.0,
            )

    # Complete English issue x model framing blocks: two prompts per tier.
    en = population.loc[population.prompt_language.eq("en")].copy()
    counts = en.groupby(["issue_id", "model", "controversy_tier"]).size().unstack()
    valid = counts.index[(counts.get("regular", 0) == 2) & (counts.get("boundary_testing", 0) == 2)]
    framing_by_model: dict[str, np.ndarray] = {}
    for model in models:
        blocks = [issue for issue, m in valid if str(m) == model]
        if not blocks:
            continue
        a = np.zeros(n)
        for issue in blocks:
            base = population.issue_id.eq(issue) & population.model.astype(str).eq(model) & population.prompt_language.eq("en")
            a[(base & population.controversy_tier.eq("boundary_testing")).to_numpy()] += 1 / (len(blocks) * 2)
            a[(base & population.controversy_tier.eq("regular")).to_numpy()] -= 1 / (len(blocks) * 2)
        framing_by_model[model] = a
        _add_spec(specs, "paired_framing", f"model||{model}", a, "exploratory", 8.0)
    if framing_by_model:
        overall = sum(framing_by_model.values()) / len(framing_by_model)
        _add_spec(specs, "paired_framing", "overall", overall, "main", 3.0)

    # Descriptive home-minus-away within each model.
    en_ha = population.prompt_language.eq("en") & population.home_status.isin(["home", "away"])
    for model in models:
        home = en_ha & population.model.astype(str).eq(model) & population.home_status.eq("home")
        away = en_ha & population.model.astype(str).eq(model) & population.home_status.eq("away")
        if not home.any() or not away.any():
            continue
        a = np.zeros(n)
        a[home.to_numpy()] = 1 / int(home.sum())
        a[away.to_numpy()] = -1 / int(away.sum())
        _add_spec(specs, "home_by_model_descriptive", model, a, "exploratory", 8.0)

    # Standardized home association. The Stage 17 ridge linear moment and
    # g-computation are linear in Y, so their exact response coefficients are
    # c'(X'X + lambda P)^-1 X'.
    jurisdictions = sorted(population.jurisdiction.dropna().astype(str).unique())
    for jurisdiction in jurisdictions:
        mask = (
            population.prompt_language.eq("en")
            & population.jurisdiction.astype(str).eq(jurisdiction)
            & population.home_status.isin(["home", "away"])
        )
        z = population.loc[mask].copy()
        if z.empty or z.home_status.nunique() < 2:
            continue
        z["home"] = z.home_status.eq("home").astype(int)
        terms = ["home"]
        if z.model.nunique() > 1:
            terms[0] = "home * C(model)"
        for col in ["controversy_tier", "topic_domain", "route"]:
            if z[col].nunique(dropna=False) > 1:
                terms.append(f"C({col})")
        formula = "1 + " + " + ".join(terms)
        x = np.asarray(patsy.dmatrix(formula, z, return_type="dataframe"), dtype=float)
        z1 = z.copy(); z1["home"] = 1
        z0 = z.copy(); z0["home"] = 0
        x1 = np.asarray(patsy.dmatrix(formula, z1, return_type="dataframe"), dtype=float)
        x0 = np.asarray(patsy.dmatrix(formula, z0, return_type="dataframe"), dtype=float)
        # Equal model -> equal issue -> equal prompt target weights.
        w = np.zeros(len(z))
        for model, dm in z.groupby("model", sort=False):
            for issue, di in dm.groupby("issue_id", sort=False):
                w[di.index.map(dict(zip(z.index, range(len(z))))).to_numpy()] = (
                    1 / z.model.nunique() / dm.issue_id.nunique() / len(di)
                )
        contrast = (w[:, None] * (x1 - x0)).sum(axis=0)
        penalty = np.eye(x.shape[1]); penalty[0, 0] = 0
        beta_map = np.linalg.solve(x.T @ x + 1e-8 * penalty, x.T)
        local_a = contrast @ beta_map
        a = np.zeros(n); a[np.flatnonzero(mask.to_numpy())] = local_a
        _add_spec(specs, "standardized_home", jurisdiction, a, "main", 5.0)

    return specs


def _variance(
    sample_contribution: np.ndarray, variance_coefficient: np.ndarray,
) -> float:
    value = float(sample_contribution @ variance_coefficient @ sample_contribution)
    return max(0.0, value)


def run_estimand_precision_audit(
    root: Path,
    pilot_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Run the frozen, local audit and write immutable planning artifacts."""
    pilot_dir = pilot_dir or root / "annotations" / "response_validity_human_v2"
    output_dir = output_dir or pilot_dir / "estimand_precision_audit_v1"
    population_path = root / "annotations" / "response_validity_dsl_v1_1" / "wall_to_wall_features.parquet"
    pseudo_path = root / "annotations" / "response_validity_dsl_v1_1" / "dsl_pseudo_outcomes.parquet"
    design_path = pilot_dir / "pilot_design.parquet"
    pilot_manifest_path = pilot_dir / "pilot_manifest.json"
    labels_path = pilot_dir / "base_freeze_v3_complete_language_review" / "base_labels.parquet"
    dev_path = pilot_dir / "enrichment_wave_v2_400" / "refinement_v2" / "access_v2" / "development_cases.parquet"
    access_manifest_path = dev_path.parent / "access_manifest.json"
    inputs = [population_path, pseudo_path, design_path, pilot_manifest_path, labels_path, dev_path, access_manifest_path]
    for path in inputs:
        if not path.exists():
            raise FileNotFoundError(path)

    input_hashes = {str(path.relative_to(root)): sha_file(path) for path in inputs}
    manifest_path = output_dir / "audit_manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("input_sha256") != input_hashes:
            raise RuntimeError("existing precision audit was built from different frozen inputs")
        for name, expected in existing.get("artifact_sha256", {}).items():
            path = output_dir / name
            if not path.exists() or sha_file(path) != expected:
                raise RuntimeError(f"precision-audit artifact missing or changed: {path}")
        return existing
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested precision-audit directory: {output_dir}")

    pilot_manifest = json.loads(pilot_manifest_path.read_text(encoding="utf-8"))
    access_manifest = json.loads(access_manifest_path.read_text(encoding="utf-8"))
    if access_manifest.get("n_development") != 161 or access_manifest.get("evaluation_rows_deserialized"):
        raise ValueError("development access is not the frozen 161-row, evaluation-sealed artifact")

    population = pd.read_parquet(population_path).merge(
        pd.read_parquet(pseudo_path)[KEY + list(SOL_COLUMNS.values())],
        on=KEY, validate="one_to_one",
    )
    if len(population) != 137_186 or population.duplicated(KEY).any():
        raise ValueError("precision audit requires 137,186 unique population rows")
    design = pd.read_parquet(design_path).sort_values("review_order").reset_index(drop=True)
    labels = pd.read_parquet(labels_path)
    label_keep = labels[["review_id", "primary_class"]]
    sample = design.merge(label_keep, on="review_id", validate="one_to_one")
    if len(sample) != 300:
        raise ValueError("precision audit requires exactly 300 frozen base labels")
    development = pd.read_parquet(dev_path)
    if len(development) != 161:
        raise ValueError("unexpected exposed development-row count")

    pairwise = exact_union_pairwise_inclusion(sample, population, pilot_manifest)
    pi = sample.inclusion_probability.to_numpy(float)
    variance_coefficient = (pairwise - np.outer(pi, pi)) / pairwise
    pop_index = pd.MultiIndex.from_frame(population[KEY])
    sample_positions = pop_index.get_indexer(pd.MultiIndex.from_frame(sample[KEY]))
    if (sample_positions < 0).any():
        raise ValueError("sample key absent from population")

    candidates = {
        "sol_reference_probability": _sol_predictors(population),
        "development_calibrated_local": _fit_development_predictors(development, population),
    }
    human = _outcomes(sample)
    specs = build_estimand_coefficients(population)
    rows: list[dict] = []
    for spec in specs:
        a = spec["coefficients"]
        a_s = a[sample_positions]
        active = np.abs(a_s) > 1e-15
        for outcome in OUTCOME_CLASSES:
            y = human[outcome].to_numpy(float)
            direct_contribution = a_s * y / pi
            direct_estimate = float(direct_contribution.sum())
            direct_se = math.sqrt(_variance(direct_contribution, variance_coefficient))
            for candidate_name, candidate in candidates.items():
                m = np.asarray(candidate[outcome], dtype=float)
                residual_contribution = a_s * (y - m[sample_positions]) / pi
                estimate = float(a @ m + residual_contribution.sum())
                se = math.sqrt(_variance(residual_contribution, variance_coefficient))
                half_width_pp = 1.96 * se * 100
                event_count = int(np.sum(active & (y > 0.5)))
                positive_events = int(np.sum((a_s > 1e-15) & (y > 0.5)))
                negative_events = int(np.sum((a_s < -1e-15) & (y > 0.5)))
                contrast = bool(np.any(a < 0) and np.any(a > 0))
                support_ok = int(active.sum()) >= 20 and event_count >= 5
                if contrast:
                    support_ok = support_ok and positive_events >= 2 and negative_events >= 2
                width_ok = half_width_pp <= spec["target_half_width_pp"]
                if support_ok and width_ok:
                    decision = "adequate_now"
                elif spec["paper_role"] == "main":
                    decision = "targeted_labels_only_if_retained_as_main"
                else:
                    decision = "do_not_expand_for_exploratory_cell"
                rows.append({
                    "family": spec["family"], "cell": spec["cell"],
                    "paper_role": spec["paper_role"], "outcome": outcome,
                    "predictor": candidate_name,
                    "prediction_only_estimate": float(a @ m),
                    "direct_ht_estimate": direct_estimate,
                    "direct_ht_se": direct_se,
                    "assisted_estimate": estimate, "assisted_se": se,
                    "assisted_ci_low_unbounded": estimate - 1.96 * se,
                    "assisted_ci_high_unbounded": estimate + 1.96 * se,
                    "assisted_half_width_pp": half_width_pp,
                    "target_half_width_pp": spec["target_half_width_pp"],
                    "relative_variance_vs_direct": (se / direct_se) ** 2 if direct_se > 0 else np.nan,
                    "sample_contributing_rows": int(active.sum()),
                    "sample_events": event_count,
                    "positive_arm_events": positive_events,
                    "negative_arm_events": negative_events,
                    "support_adequate": support_ok,
                    "width_target_met": width_ok,
                    "planning_decision": decision,
                })
    estimates = pd.DataFrame(rows)

    diagnostics: list[dict] = []
    overall = next(s for s in specs if s["family"] == "prevalence")
    for candidate_name, candidate in candidates.items():
        for outcome in OUTCOME_CLASSES:
            y = human[outcome].to_numpy(float)
            m = candidate[outcome]
            residual = y - m[sample_positions]
            # Population MSE is estimated directly from the probability sample.
            mse_contribution = np.square(residual) / pi / len(population)
            mse_se = math.sqrt(_variance(mse_contribution, variance_coefficient))
            correction_contribution = residual / pi / len(population)
            correction_se = math.sqrt(_variance(correction_contribution, variance_coefficient))
            diagnostics.append({
                "predictor": candidate_name, "outcome": outcome,
                "prediction_population_mean": float(overall["coefficients"] @ m),
                "design_estimated_brier": float(mse_contribution.sum()),
                "design_estimated_brier_se": mse_se,
                "design_estimated_mean_residual": float(correction_contribution.sum()),
                "design_estimated_mean_residual_se": correction_se,
                "human_sample_events": int(y.sum()),
            })
    diagnostics_df = pd.DataFrame(diagnostics)

    # The frozen Sol prediction is the planning reference. It predates these
    # human labels and has materially better design-estimated Brier loss than
    # the deliberately simple enrichment-only diagnostic. We do not choose a
    # candidate by searching the 300 human outcomes.
    decision_rows = estimates.loc[
        estimates.predictor.eq("sol_reference_probability")
        & estimates.paper_role.eq("main")
        & estimates.outcome.isin(["genuine_refusal", "capability_failure"])
    ].copy()
    summary = (decision_rows.groupby(["family", "outcome"], as_index=False)
        .agg(
            n_cells=("cell", "size"),
            n_adequate_now=("planning_decision", lambda x: int((x == "adequate_now").sum())),
            max_half_width_pp=("assisted_half_width_pp", "max"),
            median_half_width_pp=("assisted_half_width_pp", "median"),
            min_sample_events=("sample_events", "min"),
        ))
    summary["all_cells_adequate_now"] = summary.n_cells.eq(summary.n_adequate_now)

    output_dir.mkdir(parents=True, exist_ok=False)
    estimates_path = output_dir / "estimand_precision.csv"
    diagnostics_path = output_dir / "predictor_diagnostics.csv"
    summary_path = output_dir / "main_estimand_summary.csv"
    estimates.to_csv(estimates_path, index=False)
    diagnostics_df.to_csv(diagnostics_path, index=False)
    summary.to_csv(summary_path, index=False)
    manifest = {
        "audit_version": "human-dsl-estimand-precision-v1.0",
        "created_at": _utc_now(),
        "status": "planning_audit; one_coder; repeat_reliability_pending",
        "purpose": "test phase-two human-label precision before requesting any more annotation",
        "population_n": len(population),
        "human_reference_n": len(sample),
        "development_training_n": len(development),
        "sealed_evaluation_rows_read": False,
        "provider_or_network_call_made": False,
        "estimator": "linear estimand-specific model-assisted HT residual correction with exact union-design pairwise variance",
        "conditioning": "frozen delivered-response population; human-label sampling uncertainty only",
        "selection_rule": "frozen pre-human Sol probability is the planning reference; development-only local candidate is diagnostic and both are reported",
        "planning_thresholds_are_not_acceptance_gates": True,
        "input_sha256": input_hashes,
        "artifact_sha256": {
            estimates_path.name: sha_file(estimates_path),
            diagnostics_path.name: sha_file(diagnostics_path),
            summary_path.name: sha_file(summary_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
