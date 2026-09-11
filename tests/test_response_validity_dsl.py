from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "interactive"))
sys.path.insert(0, str(ROOT / "scripts" / "archive" / "response_validity"))

from response_validity_dsl import (  # noqa: E402
    STRATA, cross_fitted_dsl, draw_stratified_srs, integer_neyman_allocation,
)


def small_controls():
    rows = []
    for model in ["a", "b"]:
        for language in ["en", "zh"]:
            for home in ["home", "away"]:
                for i in range(5):
                    rows.append({
                        "model": model, "prompt_language": language,
                        "home_status": home, "engagement_code": 1,
                        "provisional_risk": .05 + .1 * (language == "zh"),
                        "prompt_id": f"{model}-{language}-{home}-{i}",
                    })
    return pd.DataFrame(rows)


def test_allocation_is_exact_positive_and_bounded():
    controls = small_controls()
    allocation = integer_neyman_allocation(controls, budget=20)
    assert allocation.n.sum() == 20
    assert (allocation.n >= 1).all()
    assert (allocation.n <= allocation.N).all()
    assert np.allclose(allocation.inclusion_probability,
                       allocation.n / allocation.N)


def test_stratified_srs_reproduces_cell_allocations():
    controls = small_controls()
    allocation = integer_neyman_allocation(controls, budget=20)
    draw = draw_stratified_srs(controls, allocation, seed=7)
    got = draw.groupby(STRATA, dropna=False).size().rename("got").reset_index()
    check = allocation.merge(got, on=STRATA)
    assert (check.n == check.got).all()
    assert len(draw) == 20


def test_dsl_pseudo_outcome_rectifies_a_biased_predictor(monkeypatch):
    # Synthetic census with issue-level folds, all positives observed and a
    # probability sample of negatives.  A deliberately intercept-only learner
    # is sufficient to verify the exact pseudo-outcome identity.
    n = 100
    frame = pd.DataFrame({
        "prompt_id": [f"p{i}" for i in range(n)],
        "prompt_language": ["en"] * n,
        "model": ["m"] * n,
        "issue_id": [f"i{i // 2}" for i in range(n)],
        "y": np.array([0, 1] * (n // 2)),
    })
    # Populate the feature contract with constants.
    from response_validity_dsl import CATEGORICAL, NUMERIC
    for c in CATEGORICAL:
        if c not in frame:
            frame[c] = "x"
    for c in NUMERIC:
        if c not in frame:
            frame[c] = 0.0
    observed = frame.index % 4 < 2
    labels = frame.loc[observed, ["prompt_id", "prompt_language", "model", "issue_id", "y"]].copy()
    labels["inclusion_probability"] = .5
    result = cross_fitted_dsl(frame.drop(columns="y"), labels, "y", folds=5)
    pseudo = result.frame.dsl_pseudo_y
    # The HT correction identity holds around the fitted prediction for every
    # observed row, including pseudo-outcomes outside [0,1].
    pred = result.frame.dsl_prediction_y
    assert np.allclose(pseudo[observed], pred[observed] + 2 * (labels.y.to_numpy() - pred[observed]))
    assert np.allclose(pseudo[~observed], pred[~observed])


def test_ht_rectification_is_design_unbiased_with_bad_predictions():
    # Fixed finite population and an intentionally useless prediction of 0.8.
    # Averaging over every possible SRS of two of four units recovers its true
    # mean exactly; prediction quality changes variance, not the target.
    from itertools import combinations
    y = np.array([0., 0., 1., 1.])
    g = np.repeat(.8, 4)
    estimates = []
    for sample in combinations(range(4), 2):
        r = np.zeros(4)
        r[list(sample)] = 1
        pseudo = g + r / .5 * (y - g)
        estimates.append(pseudo.mean())
    assert np.mean(estimates) == np.mean(y)


def test_repeated_dsl_retains_split_specific_pseudo_outcomes(monkeypatch):
    from response_validity_dsl import repeated_cross_fitted_dsl, CATEGORICAL, NUMERIC
    n = 40
    frame = pd.DataFrame({
        "prompt_id": [f"p{i}" for i in range(n)],
        "prompt_language": ["en"] * n, "model": ["m"] * n,
        "issue_id": [f"i{i // 2}" for i in range(n)],
    })
    for c in CATEGORICAL:
        if c not in frame: frame[c] = "x"
    for c in NUMERIC:
        if c not in frame: frame[c] = 0.0
    labels = frame[["prompt_id", "prompt_language", "model", "issue_id"]].copy()
    labels["inclusion_probability"] = 1.0
    labels["y"] = np.array([0, 1] * (n // 2))
    result = repeated_cross_fitted_dsl(frame, labels, "y", folds=2, repeats=2)
    assert {"dsl_pseudo_r00_y", "dsl_pseudo_r01_y"} <= set(result.frame)
    assert np.allclose(result.frame.dsl_pseudo_y,
                       result.frame[["dsl_pseudo_r00_y", "dsl_pseudo_r01_y"]].mean(axis=1))


def test_paid_reference_runner_requires_explicit_authorization():
    from run_response_validity_dsl_reference import run
    with pytest.raises(RuntimeError, match="requires --authorize-paid-run"):
        run(workers=1, ceiling=170, authorized=False)


def test_reference_label_join_contract_avoids_metadata_suffixes():
    # The paid runner's assembled file contains the universe columns already;
    # the DSL join must select outcomes explicitly rather than duplicating its
    # own sampling metadata into *_x and *_y columns.
    from response_validity_dsl import KEY, OUTCOMES
    key = {"prompt_id": "p", "prompt_language": "en", "model": "m"}
    universe = pd.DataFrame([{**key, "issue_id": "i", "inclusion_probability": .5}])
    raw = pd.DataFrame([{**key, "issue_id": "i", "inclusion_probability": .5,
                         **{outcome: False for outcome in OUTCOMES}}])
    joined = universe[KEY + ["issue_id", "inclusion_probability"]].merge(
        raw[KEY + OUTCOMES], on=KEY, validate="one_to_one")
    assert {"issue_id", "inclusion_probability", *OUTCOMES} <= set(joined)
    assert not any(c.endswith(("_x", "_y")) for c in joined)
