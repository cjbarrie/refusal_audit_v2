from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.external_sol_reference_evaluation import (  # noqa: E402
    evaluate_external_sol_reference,
    joint_inclusion_probabilities,
)


AUDIT = (
    ROOT / "annotations" / "response_validity_human_v2" / "external_audit_v1"
)


def test_second_order_probabilities_match_the_union_design():
    frame = pd.read_parquet(AUDIT / "paired_machine_labels.parquet")
    pi_ij = joint_inclusion_probabilities(frame)
    pi = frame.phase1_inclusion_probability.to_numpy(float)
    assert np.allclose(np.diag(pi_ij), pi)
    assert np.allclose(pi_ij, pi_ij.T)
    assert np.all((pi_ij > 0) & (pi_ij <= 1))

    # For two rows in different strata in both components, component selection
    # is independent and their union indicators are independent too.
    found = False
    for i in range(len(frame)):
        different = (
            frame.model.ne(frame.model.iloc[i])
            | frame.prompt_language.ne(frame.prompt_language.iloc[i])
        ) & frame.routing_stratum.ne(frame.routing_stratum.iloc[i])
        if different.any():
            j = int(np.flatnonzero(different.to_numpy())[0])
            assert np.isclose(pi_ij[i, j], pi[i] * pi[j])
            found = True
            break
    assert found


def test_external_sol_reference_headlines_and_immutability(tmp_path):
    first = evaluate_external_sol_reference(ROOT, output_dir=tmp_path)
    second = evaluate_external_sol_reference(ROOT, output_dir=tmp_path)
    assert second == first
    assert first["provider_call_made"] is False
    assert first["human_validation_complete"] is False
    assert first["status"] == "complete_sol_referenced_not_human_validated"

    headline = json.loads((tmp_path / "headline_results.json").read_text())
    assert np.isclose(
        headline["genuine_refusal_precision"]["estimate"],
        0.9469386172918702,
    )
    assert np.isclose(
        headline["genuine_refusal_recall"]["estimate"],
        0.9717557708111129,
    )
    assert headline["point_gate_refusal_precision_at_least_0_90"] is True
    assert headline["point_gate_refusal_recall_at_least_0_90"] is True
    assert headline["point_gate_capability_f1_at_least_0_85"] is False

    weighted = pd.read_csv(tmp_path / "design_weighted_metrics.csv")
    assert set(weighted.scope) == {"overall", "model", "prompt_language"}
    assert set(weighted.outcome) == {
        "genuine_refusal", "capability_failure", "task_noncompletion",
        "wrong_language", "epistemic_limitation", "stance_disclaimer",
    }
    assert set(weighted.metric) == {
        "precision", "recall", "specificity", "accuracy", "f1",
    }


def test_weighting_changes_the_deliberately_enriched_stress_test(tmp_path):
    evaluate_external_sol_reference(ROOT, output_dir=tmp_path)
    weighted = pd.read_csv(tmp_path / "design_weighted_metrics.csv")
    stress = pd.read_csv(tmp_path / "unweighted_stress_test_metrics.csv")
    key = (
        weighted.scope.eq("overall")
        & weighted.outcome.eq("capability_failure")
        & weighted.metric.eq("precision")
    )
    stress_key = (
        stress.scope.eq("overall")
        & stress.outcome.eq("capability_failure")
        & stress.metric.eq("precision")
    )
    assert weighted.loc[key, "estimate"].iloc[0] < stress.loc[
        stress_key, "estimate"
    ].iloc[0]


def test_forensic_disagreement_review_is_complete_and_non_destructive():
    paired = pd.read_parquet(AUDIT / "paired_machine_labels.parquet")
    path = (
        AUDIT / "sol_reference_evaluation_v1"
        / "refusal_disagreement_forensic_review.csv"
    )
    review = pd.read_csv(path)
    expected = set(paired.loc[paired.refusal_disagreement, "audit_response_id"])
    assert set(review.audit_response_id) == expected
    assert len(review) == 9
    assert review.audit_response_id.is_unique
    assert review.forensic_genuine_refusal.sum() == 1
    assert review.preferred_annotation.value_counts().to_dict() == {
        "sol": 6, "luna": 3,
    }
    assert review.review_status.eq(
        "codex_forensic_recommendation_not_human_gold"
    ).all()
