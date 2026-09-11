import numpy as np
import pandas as pd

from refusal_audit.response_validity.estimand_precision import (
    _sol_predictors,
    build_estimand_coefficients,
)


def _balanced_population() -> pd.DataFrame:
    rows = []
    for model, jurisdiction in [("a", "J1"), ("b", "J2")]:
        for issue in ["i1", "i2"]:
            home = (model == "a" and issue == "i1") or (model == "b" and issue == "i2")
            for tier in ["regular", "boundary_testing"]:
                for replicate in [1, 2]:
                    prompt_id = f"{issue}-{tier}-{replicate}"
                    for language in ["en", "ar"]:
                        rows.append({
                            "prompt_id": prompt_id,
                            "prompt_language": language,
                            "model": model,
                            "issue_id": issue,
                            "controversy_tier": tier,
                            "topic_domain": "domain",
                            "route": "route",
                            "home_status": "home" if home else "away",
                            "jurisdiction": jurisdiction,
                        })
    return pd.DataFrame(rows)


def test_candidate_estimands_are_normalized_linear_statistics():
    population = _balanced_population()
    specs = build_estimand_coefficients(population)
    assert len(specs) == 15
    for spec in specs:
        expected = 1.0 if spec["family"] in {
            "prevalence", "model_language_prevalence",
        } else 0.0
        assert np.isclose(spec["coefficients"].sum(), expected, atol=1e-8), spec
        assert np.isfinite(spec["coefficients"]).all()


def test_sol_noncompliance_is_sum_of_disjoint_probabilities_with_safe_bound():
    frame = pd.DataFrame({
        "dsl_prediction_clean_genuine_refusal": [0.1, 0.8],
        "dsl_prediction_capability_failure": [0.2, 0.1],
        "dsl_prediction_coherent_pivot": [0.3, 0.5],
    })
    got = _sol_predictors(frame)
    assert np.allclose(got["coherent_noncompliance"], [0.4, 1.0])
