#!/usr/bin/env python3
"""Plan and assemble design-based supervised learning (DSL) refusal outcomes.

This module contains no paid API call.  It freezes a stratified probability
sample for future GPT-5.6 Sol reference coding, constructs issue-cross-fitted
DSL pseudo-outcomes after those labels exist, and records the complete design.

The scientific contract is documented in docs/RESPONSE_VALIDITY_DSL.md.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from audit_response_validity import analysis_frame, diagnostics

ROOT = Path(__file__).resolve().parents[1]
V10 = ROOT / "annotations" / "response_validity_v1" / "assembled_labels.parquet"
V11_PILOT = ROOT / "annotations" / "response_validity_v11_pilot" / "assembled_pilot.parquet"
OUT = ROOT / "annotations" / "response_validity_dsl_v1"
SEED = 20260819
KEY = ["prompt_id", "prompt_language", "model"]
MODEL_JURIS = {
    "deepseek-chat-v3.1": "CN", "qwen3-max": "CN",
    "allam-7b": "MENA", "falcon3-10b": "MENA", "jais-8b": "MENA",
    "sarvam-30b": "India",
    "claude-opus-4.5": "US", "gpt-4o": "US", "gpt-5.1": "US",
    "grok-4.3": "US", "mistral-large-2512": "EU",
}
HOME_REGION = {"CN": "China", "MENA": "Arab", "India": "India",
               "US": "US", "EU": "Europe"}
STRATA = ["model", "prompt_language", "home_status", "engagement_code"]
CATEGORICAL = [
    "model", "prompt_language", "jurisdiction", "home_status",
    "controversy_tier", "topic_domain", "route", "region_focus",
    "prompt_origin_language", "prompt_origin_form", "response_language",
    "refusal_justification", "control_length_band",
]
NUMERIC = [
    "engagement_code", "diag_char_count", "diag_token_count",
    "diag_replacement_rate", "diag_control_rate", "diag_target_script_share",
    "diag_target_script_mismatch", "diag_unique_token_ratio",
    "diag_repeated_trigram_ratio", "diag_prompt_echo_overlap",
    "diag_punctuation_rate", "diag_repetition_loop", "diag_truncation_suspect",
    "diag_metadata_language_disagreement",
]
OUTCOMES = ["clean_genuine_refusal", "capability_failure", "coherent_pivot"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def frame_hash(frame: pd.DataFrame) -> str:
    values = frame.sort_values(KEY)[KEY].astype(str).agg("\0".join, axis=1)
    return sha_text("\n".join(values))


def _diagnose_one(values: tuple[str, str, str]) -> dict:
    return diagnostics(*values)


def add_design_fields(frame: pd.DataFrame) -> pd.DataFrame:
    """Recreate canonical design fields without reading an R-derived output."""
    x = frame.copy()
    x["jurisdiction"] = x.model.map(MODEL_JURIS)
    if x.jurisdiction.isna().any():
        raise ValueError("unknown model jurisdiction")
    x["home_status"] = np.where(
        x.region_focus.eq("General"), "general",
        np.where(x.region_focus.eq(x.jurisdiction.map(HOME_REGION)), "home", "away"),
    )
    x["control_length_band"] = pd.qcut(
        x.response_text.str.len(), 4, labels=["q1", "q2", "q3", "q4"],
        duplicates="drop",
    ).astype("string")
    x["prompt_hash"] = [sha_text(f"{en}\0{prompt}\0{response}")
                        for en, prompt, response in zip(
                            x.prompt_text_en, x.prompt_text, x.response_text)]
    return x


def full_frame() -> pd.DataFrame:
    """Load the exact 137,186-row response frame and wall-to-wall predictors."""
    base = add_design_fields(analysis_frame())
    source_hash = frame_hash(base)
    cache = OUT / "wall_to_wall_features.parquet"
    cache_meta = OUT / "wall_to_wall_features.json"
    if cache.exists() and cache_meta.exists():
        metadata = json.loads(cache_meta.read_text())
        if metadata.get("frame_key_sha256") == source_hash:
            x = pd.read_parquet(cache)
            if len(x) == 137_186 and not x.duplicated(KEY).any():
                if "prompt_hash" not in x:
                    x["prompt_hash"] = [sha_text(f"{en}\0{prompt}\0{response}")
                                        for en, prompt, response in zip(
                                            x.prompt_text_en, x.prompt_text,
                                            x.response_text)]
                    x.to_parquet(cache, index=False)
                return x
    x = base
    diagnostic_inputs = list(x[["prompt_text", "response_text", "prompt_language"]]
                             .itertuples(index=False, name=None))
    # The deterministic text diagnostics are CPU-bound.  Process chunks keep a
    # clean first build from taking several minutes; the resulting hash-guarded
    # parquet is reused thereafter.
    try:
        with ProcessPoolExecutor(max_workers=4) as pool:
            diag = pd.DataFrame(pool.map(_diagnose_one, diagnostic_inputs, chunksize=250))
    except (PermissionError, OSError):
        # Some reproducibility sandboxes disallow POSIX semaphores.  The serial
        # path is slower but byte-identical and is paid only on the first build.
        diag = pd.DataFrame(map(_diagnose_one, diagnostic_inputs))
    # analysis_frame contains original annotation diagnostics only on audit rows;
    # recomputation makes the predictor contract wall-to-wall and deterministic.
    x = pd.concat([x.reset_index(drop=True), diag.reset_index(drop=True)], axis=1)
    x["diag_metadata_language_disagreement"] = (
        x.response_language.notna()
        & x.response_language.astype(str).ne(x.prompt_language.astype(str))
    )
    if len(x) != 137_186 or x.duplicated(KEY).any():
        raise ValueError("canonical response frame differs from 137,186 unique keys")
    OUT.mkdir(parents=True, exist_ok=True)
    x.to_parquet(cache, index=False)
    cache_meta.write_text(json.dumps({
        "created_at": now(), "n": len(x), "frame_key_sha256": source_hash,
        "note": "derived deterministic wall-to-wall DSL predictors; reproducible from raw responses",
    }, indent=2), encoding="utf-8")
    return x


def learner() -> Pipeline:
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=2)),
    ])
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    return Pipeline([
        ("features", ColumnTransformer([
            ("categorical", categorical, CATEGORICAL),
            ("numeric", numeric, NUMERIC),
        ])),
        ("model", LogisticRegression(
            penalty="l2", C=1.0, solver="liblinear", max_iter=1000,
            class_weight=None, random_state=SEED,
        )),
    ])


def pilot_selection_weights(v10: pd.DataFrame, pilot: pd.DataFrame) -> np.ndarray:
    """Recover the v1.1 pilot's known conflict/comparator selection weights."""
    strata = ["audit_stratum", "primary_class", "model", "prompt_language"]
    nonconf = v10.loc[~v10.primary_component_conflict]
    sizes = nonconf.groupby(strata, dropna=False).size().rename("pilot_cell_n")
    p = pilot.merge(sizes.reset_index(), on=strata, how="left", validate="many_to_one")
    weight = np.where(p.primary_component_conflict, 1.0, p.pilot_cell_n)
    if not np.isfinite(weight).all():
        raise ValueError("pilot selection weight recovery failed")
    return weight.astype(float)


def provisional_risk(frame: pd.DataFrame) -> tuple[np.ndarray, dict]:
    """Predict Sol clean-refusal risk solely for sample-allocation planning.

    The fitted risk is not an analytic outcome.  It uses the probability-weighted
    1,306-row Sol pilot and is frozen only to allocate future reference labels.
    """
    v10 = pd.read_parquet(V10)
    pilot = add_design_fields(pd.read_parquet(V11_PILOT))
    weights = pilot_selection_weights(v10, pilot)
    fit = learner()
    fit.fit(pilot[CATEGORICAL + NUMERIC], pilot.sol_clean_genuine_refusal.astype(int),
            model__sample_weight=weights)
    pred = fit.predict_proba(frame[CATEGORICAL + NUMERIC])[:, 1]
    pilot_pred = fit.predict_proba(pilot[CATEGORICAL + NUMERIC])[:, 1]
    diag = {
        "weighted_brier_apparent": float(np.average(
            (pilot.sol_clean_genuine_refusal.astype(float) - pilot_pred) ** 2,
            weights=weights)),
        "weighted_log_loss_apparent": float(log_loss(
            pilot.sol_clean_genuine_refusal.astype(int), pilot_pred,
            sample_weight=weights, labels=[0, 1])),
        "warning": "apparent pilot fit; used for allocation only, never inference",
    }
    return pred, diag


def analysis_coefficients(frame: pd.DataFrame) -> dict[str, tuple[str, np.ndarray]]:
    """Linear coefficients for every refusal finding that drives allocation."""
    n = len(frame)
    out = {"overall prevalence": ("overall", np.repeat(1 / n, n))}
    models = sorted(frame.model.unique())
    for language in sorted(set(frame.prompt_language) - {"en"}):
        common = frame.loc[frame.prompt_language.isin(["en", language]),
                           ["model", "prompt_id", "prompt_language"]]
        counts = common.groupby(["model", "prompt_id"]).prompt_language.nunique()
        keys = counts[counts.eq(2)].index
        use = pd.MultiIndex.from_frame(frame[["model", "prompt_id"]]).isin(keys)
        a = np.zeros(n)
        for model in models:
            for lang, sign in [(language, 1), ("en", -1)]:
                cell = use & frame.model.eq(model) & frame.prompt_language.eq(lang)
                if cell.sum():
                    a[cell] = sign / (len(models) * cell.sum())
        out[f"language {language}-en equal-model"] = ("language", a)
    english = frame.prompt_language.eq("en")
    for jurisdiction in ["CN", "MENA", "India", "US", "EU"]:
        jm = sorted(frame.loc[frame.jurisdiction.eq(jurisdiction), "model"].unique())
        a = np.zeros(n)
        for model in jm:
            for arm, sign in [("home", 1), ("away", -1)]:
                cell = english & frame.model.eq(model) & frame.home_status.eq(arm)
                if cell.sum():
                    a[cell] = sign / (len(jm) * cell.sum())
        out[f"home descriptive {jurisdiction}"] = ("home", a)
    for model in models:
        for language in sorted(frame.prompt_language.unique()):
            cell = frame.model.eq(model) & frame.prompt_language.eq(language)
            a = np.zeros(n)
            a[cell] = 1 / cell.sum()
            out[f"cell rate {model} {language}"] = ("cell_rate", a)
    return out


def add_allocation_leverage(frame: pd.DataFrame) -> pd.DataFrame:
    """Give each analysis family equal influence on the label allocation."""
    registry = analysis_coefficients(frame)
    tolerances = {"overall": .005, "language": .01, "home": .01,
                  "cell_rate": .02}
    family_n = pd.Series([family for family, _ in registry.values()]).value_counts()
    leverage = np.zeros(len(frame))
    for family, coefficient in registry.values():
        leverage += (coefficient / tolerances[family]) ** 2 / family_n[family]
    out = frame.copy()
    out["allocation_leverage"] = leverage
    return out


def integer_neyman_allocation(controls: pd.DataFrame, budget: int,
                              min_per_stratum: int = 1) -> pd.DataFrame:
    """Allocate a fixed control budget by bounded integer Neyman allocation."""
    if budget <= 0 or budget > len(controls):
        raise ValueError("control budget must be within the control population")
    controls = controls.copy()
    controls["risk_variance"] = controls.provisional_risk * (1 - controls.provisional_risk)
    if "allocation_leverage" in controls:
        controls["objective_variance"] = controls.risk_variance * controls.allocation_leverage
    else:
        controls["objective_variance"] = controls.risk_variance
    cells = controls.groupby(STRATA, dropna=False).agg(
        N=("provisional_risk", "size"), risk_mean=("provisional_risk", "mean"),
        objective_variance_sum=("objective_variance", "sum"),
    ).reset_index()
    cells["n"] = np.minimum(cells.N, min_per_stratum).astype(int)
    if cells.n.sum() > budget:
        raise ValueError(f"budget {budget} is below {cells.n.sum()} populated-stratum minimum")
    # A small variance floor prevents a pilot-predicted zero cell from receiving
    # no precision allocation beyond its positive-probability minimum.
    # n_h proportional to N_h*S_h minimizes the declared weighted sum of
    # stratified SRS variances.  The floor preserves useful allocation when the
    # small pilot predicts a cell to be constant.
    cells["allocation_score"] = cells.N * np.sqrt(
        cells.objective_variance_sum / np.maximum(cells.N - 1, 1) + 1e-10
    )
    remaining = budget - int(cells.n.sum())
    while remaining:
        open_ = cells.n.lt(cells.N)
        if not open_.any():
            break
        score = cells.allocation_score.where(open_, 0.0)
        quota = remaining * score / score.sum()
        add = np.floor(quota).astype(int)
        add = np.minimum(add, (cells.N - cells.n).astype(int))
        if add.sum() == 0:
            order = (quota - np.floor(quota)).where(open_, -1).sort_values(
                ascending=False, kind="mergesort").index
            add.loc[order[:remaining]] = 1
        cells.n += add
        remaining = budget - int(cells.n.sum())
    if cells.n.sum() != budget or (cells.n < 1).any() or (cells.n > cells.N).any():
        raise ValueError("bounded allocation did not reach the requested budget")
    cells["inclusion_probability"] = cells.n / cells.N
    cells["sampling_weight"] = 1 / cells.inclusion_probability
    return cells


def draw_stratified_srs(controls: pd.DataFrame, allocation: pd.DataFrame,
                        seed: int) -> pd.DataFrame:
    merged = controls.merge(allocation[STRATA + ["N", "n", "inclusion_probability",
                                                 "sampling_weight"]],
                            on=STRATA, how="left", validate="many_to_one")
    rng = np.random.default_rng(seed)
    chosen = []
    for _, g in merged.groupby(STRATA, dropna=False, sort=True):
        take = int(g.n.iloc[0])
        chosen.append(g.iloc[rng.choice(len(g), size=take, replace=False)])
    out = pd.concat(chosen, ignore_index=True)
    if len(out) != int(allocation.n.sum()) or out.duplicated(KEY).any():
        raise ValueError("stratified SRS draw failed")
    return out


def prepare(budget: int, seed: int = SEED) -> None:
    """Freeze the future Sol reference-label universe; makes no API call."""
    OUT.mkdir(parents=True, exist_ok=True)
    frame = full_frame()
    frame["provisional_risk"], risk_diag = provisional_risk(frame)
    frame = add_allocation_leverage(frame)
    positives = frame.loc[frame.engagement_code.ge(4)].copy()
    controls = frame.loc[frame.engagement_code.lt(4)].copy()
    allocation = integer_neyman_allocation(controls, budget)
    sampled = draw_stratified_srs(controls, allocation, seed)
    positives["reference_stratum"] = "original_nonengagement_census"
    positives["inclusion_probability"] = 1.0
    positives["sampling_weight"] = 1.0
    positives["N"] = 1
    positives["n"] = 1
    sampled["reference_stratum"] = "stratified_original_engagement_control"
    universe = pd.concat([positives, sampled], ignore_index=True)
    universe["reference_id"] = [sha_text("\0".join(map(str, k)))[:24]
                                for k in universe[KEY].itertuples(index=False, name=None)]
    universe = universe.sample(frac=1, random_state=seed).reset_index(drop=True)
    universe.to_parquet(OUT / "reference_universe.parquet", index=False)
    allocation.to_csv(OUT / "reference_allocation.csv", index=False)
    manifest = {
        "version": "response-validity-dsl-v1.0",
        "created_at": now(), "seed": seed,
        "sampling_design": "all engagement_code>=4 plus stratified SRSWOR controls",
        "strata": STRATA, "control_budget": budget,
        "n_positive_census": len(positives), "n_sampled_controls": len(sampled),
        "n_reference_total": len(universe), "n_population": len(frame),
        "frame_key_sha256": frame_hash(frame),
        "reference_key_sha256": frame_hash(universe),
        "allocation_sha256": sha_bytes((OUT / "reference_allocation.csv").read_bytes()),
        "pilot_allocation_diagnostics": risk_diag,
        "paid_run_authorized": False,
    }
    (OUT / "reference_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


@dataclass
class DSLResult:
    frame: pd.DataFrame
    diagnostics: pd.DataFrame


def cross_fitted_dsl(frame: pd.DataFrame, labels: pd.DataFrame, outcome: str,
                     folds: int = 5, seed: int = SEED,
                     repeat: int = 0) -> DSLResult:
    """Construct issue-cross-fitted DSL pseudo-outcomes on a fixed population."""
    required = {*KEY, "issue_id", "inclusion_probability", outcome}
    missing = required - set(labels)
    if missing:
        raise ValueError(f"reference labels lack {sorted(missing)}")
    if labels.duplicated(KEY).any() or not labels.inclusion_probability.gt(0).all():
        raise ValueError("reference labels require unique keys and positive probabilities")
    x = frame.merge(labels[KEY + [outcome, "inclusion_probability"]],
                    on=KEY, how="left", validate="one_to_one")
    x["reference_observed"] = x[outcome].notna()
    observed_pi = x.loc[x.reference_observed, "inclusion_probability"].to_numpy(float)
    if not np.isfinite(observed_pi).all() or not ((observed_pi > 0) & (observed_pi <= 1)).all():
        raise ValueError("invalid inclusion probabilities")
    groups = x.issue_id.astype(str)
    unique_issues = np.array(sorted(groups.unique()))
    rng = np.random.default_rng(seed)
    rng.shuffle(unique_issues)
    fold_of = {issue: i % folds for i, issue in enumerate(unique_issues)}
    x["dsl_fold"] = groups.map(fold_of).astype(int)
    pred = np.full(len(x), np.nan)
    rows = []
    for fold in range(folds):
        test = x.dsl_fold.eq(fold)
        train = x.reference_observed & ~test
        y = x.loc[train, outcome].astype(int)
        if y.nunique() < 2:
            raise ValueError(f"outcome {outcome} has one class outside fold {fold}")
        fit = learner()
        fit.fit(x.loc[train, CATEGORICAL + NUMERIC], y,
                model__sample_weight=1 / x.loc[train, "inclusion_probability"])
        pred[test] = fit.predict_proba(x.loc[test, CATEGORICAL + NUMERIC])[:, 1]
        held = test & x.reference_observed
        rows.append({
            "outcome": outcome, "repeat": repeat, "fold": fold,
            "n_population": int(test.sum()), "n_reference": int(held.sum()),
            "weighted_brier": float(np.average(
                (x.loc[held, outcome].astype(float) - pred[held]) ** 2,
                weights=1 / x.loc[held, "inclusion_probability"])),
            "weighted_log_loss": float(log_loss(
                x.loc[held, outcome].astype(int), pred[held],
                sample_weight=1 / x.loc[held, "inclusion_probability"],
                labels=[0, 1])),
        })
    if not np.isfinite(pred).all():
        raise ValueError("cross-fitted predictions are incomplete")
    residual = np.zeros(len(x))
    observed = x.reference_observed.to_numpy()
    pi = x.inclusion_probability.fillna(1.0).to_numpy(float)
    residual[observed] = (
        x.loc[x.reference_observed, outcome].to_numpy(float) - pred[observed]
    ) / pi[observed]
    x[f"dsl_prediction_{outcome}"] = pred
    x[f"dsl_residual_correction_{outcome}"] = residual
    x[f"dsl_pseudo_{outcome}"] = pred + residual
    return DSLResult(x, pd.DataFrame(rows))


def repeated_cross_fitted_dsl(frame: pd.DataFrame, labels: pd.DataFrame,
                              outcome: str, folds: int = 5,
                              repeats: int = 10) -> DSLResult:
    """Average repeated issue-cross-fitted predictions, then rectify once."""
    if repeats < 1:
        raise ValueError("repeats must be positive")
    fits = [cross_fitted_dsl(frame, labels, outcome, folds=folds,
                             seed=SEED + 1009 * repeat, repeat=repeat)
            for repeat in range(repeats)]
    pred_col = f"dsl_prediction_{outcome}"
    predictions = np.column_stack([fit.frame[pred_col].to_numpy() for fit in fits])
    result = fits[0].frame.copy()
    pred = predictions.mean(axis=1)
    observed = result.reference_observed.to_numpy()
    pi = result.inclusion_probability.fillna(1.0).to_numpy(float)
    correction = np.zeros(len(result))
    correction[observed] = (
        result.loc[result.reference_observed, outcome].to_numpy(float) - pred[observed]
    ) / pi[observed]
    result[pred_col] = pred
    result[f"dsl_prediction_sd_{outcome}"] = predictions.std(axis=1, ddof=1)
    result[f"dsl_residual_correction_{outcome}"] = correction
    result[f"dsl_pseudo_{outcome}"] = pred + correction
    # Retain each split-specific rectified pseudo-outcome. Downstream estimands
    # need these columns to propagate the predeclared ten-split variation; a
    # per-row prediction SD alone loses covariance across rows and cannot do so.
    for repeat, fit in enumerate(fits):
        result[f"dsl_pseudo_r{repeat:02d}_{outcome}"] = fit.frame[
            f"dsl_pseudo_{outcome}"
        ].to_numpy()
    return DSLResult(result, pd.concat([fit.diagnostics for fit in fits], ignore_index=True))


def assemble(labels_path: Path, folds: int = 5, repeats: int = 10) -> None:
    """Create wall-to-wall DSL pseudo-outcomes from completed Sol labels."""
    manifest = json.loads((OUT / "reference_manifest.json").read_text())
    frame = full_frame()
    if frame_hash(frame) != manifest["frame_key_sha256"]:
        raise ValueError("response frame hash differs from frozen reference design")
    universe = pd.read_parquet(OUT / "reference_universe.parquet")
    raw_labels = pd.read_parquet(labels_path)
    missing_outcomes = set(OUTCOMES) - set(raw_labels)
    if missing_outcomes:
        raise ValueError(f"reference labels lack outcomes {sorted(missing_outcomes)}")
    # The assembled runner output already carries universe metadata. Select the
    # key and adjudicated outcomes explicitly so merging it back cannot create
    # issue_id_x/inclusion_probability_x suffixes and violate the DSL contract.
    labels = universe[KEY + ["issue_id", "inclusion_probability"]].merge(
        raw_labels[KEY + OUTCOMES], on=KEY, how="inner", validate="one_to_one")
    if len(labels) != len(universe):
        raise ValueError(f"reference-label coverage incomplete: {len(labels)}/{len(universe)}")
    # The full feature frame contains prompt/response text and is already
    # preserved separately. The downstream contract needs only canonical keys
    # and DSL analysis columns; keeping text here made this derived artifact
    # roughly 400 MB without adding inferential information.
    output = frame[KEY].copy()
    diagnostics_rows = []
    for outcome in OUTCOMES:
        result = repeated_cross_fitted_dsl(
            frame, labels, outcome, folds=folds, repeats=repeats)
        cols = [c for c in result.frame if c.startswith("dsl_") and c.endswith(outcome)]
        output = output.merge(result.frame[KEY + cols], on=KEY, validate="one_to_one")
        diagnostics_rows.append(result.diagnostics)
    output.to_parquet(OUT / "dsl_pseudo_outcomes.parquet", index=False)
    pd.concat(diagnostics_rows).to_csv(OUT / "dsl_crossfit_diagnostics.csv", index=False)
    manifest["dsl_assembled_at"] = now()
    manifest["reference_labels_path"] = str(labels_path)
    manifest["reference_labels_sha256"] = sha_bytes(labels_path.read_bytes())
    manifest["folds"] = folds
    manifest["crossfit_repeats"] = repeats
    (OUT / "reference_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="stage", required=True)
    p_prepare = sub.add_parser("prepare")
    p_prepare.add_argument("--control-budget", type=int, required=True)
    p_prepare.add_argument("--seed", type=int, default=SEED)
    p_assemble = sub.add_parser("assemble")
    p_assemble.add_argument("--labels", type=Path, required=True)
    p_assemble.add_argument("--folds", type=int, default=5)
    p_assemble.add_argument("--repeats", type=int, default=10)
    p_assemble.add_argument("--design-dir", type=Path, default=OUT)
    args = parser.parse_args()
    if args.stage == "prepare":
        prepare(args.control_budget, args.seed)
    else:
        OUT = args.design_dir
        assemble(args.labels, args.folds, args.repeats)


if __name__ == "__main__":
    main()
