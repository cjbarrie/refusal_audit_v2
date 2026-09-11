import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import refusal_audit.response_validity.human_audit as human_audit  # noqa: E402
from refusal_audit.response_validity.human_audit import (  # noqa: E402
    exact_union_pairwise_inclusion,
)


def test_exact_union_pairwise_inclusion_for_independent_srs_components():
    population = pd.DataFrame({
        "model": ["m1", "m1", "m2", "m2"],
        "prompt_language": ["en", "en", "zh", "zh"],
    })
    design = pd.DataFrame({
        "model": ["m1", "m2"],
        "prompt_language": ["en", "zh"],
        "pilot_priority_class": ["a", "b"],
        "selected_priority": [True, True],
        "pi_model_language": [.5, .5],
        "pi_priority": [.5, .5],
        "inclusion_probability": [.8125, .8125],
    })
    pairwise = exact_union_pairwise_inclusion(
        design, population, {"components": {"global_srs": 1}}
    )
    assert np.allclose(np.diag(pairwise), .8125)
    assert np.allclose(pairwise[0, 1], .65625)
    assert np.allclose(pairwise, pairwise.T)


def test_completed_base_freeze_excludes_repeat_tasks_and_is_complete():
    pilot = ROOT / "annotations" / "response_validity_human_v2"
    freeze = json.loads((pilot / "base_freeze_v1" / "freeze_manifest.json").read_text())
    design = pd.read_parquet(pilot / "pilot_design.parquet")
    labels = pd.read_parquet(pilot / "base_freeze_v1" / "base_labels.parquet")
    assert freeze["n_base_labels"] == 300
    assert freeze["repeat_records_read"] is False
    assert len(labels) == len(design) == 300
    assert set(labels.review_id) == set(design.review_id)
    assert labels.review_id.nunique() == 300


def test_existing_freeze_does_not_reopen_live_label_log(monkeypatch):
    pilot = ROOT / "annotations" / "response_validity_human_v2"

    def fail_if_called(_path):
        raise AssertionError("live label log must not be read after base freeze")

    monkeypatch.setattr(human_audit, "_read_jsonl", fail_if_called)
    result = human_audit.freeze_completed_base_labels(ROOT, pilot)
    assert result["n_base_labels"] == 300


def test_preliminary_audit_is_provisional_and_reproduces_headlines():
    audit = ROOT / "annotations" / "response_validity_human_v2" / "preliminary_audit_v1"
    manifest = json.loads((audit / "audit_manifest.json").read_text())
    qa = json.loads((audit / "qa_summary.json").read_text())
    prevalence = pd.read_csv(audit / "design_weighted_prevalence.csv")
    original = pd.read_csv(audit / "original_label_audit.csv")
    assert manifest["repeat_records_read_or_analyzed"] is False
    assert manifest["network_call_made"] is False
    assert qa["n_base_labels"] == 300 and qa["n_repeat_labels_analyzed"] == 0
    assert qa["negative_variance_rows"] == 0

    overall_refusal = prevalence.loc[
        prevalence.dimension.eq("overall") & prevalence.outcome.eq("genuine_refusal")
    ].iloc[0]
    assert np.isclose(overall_refusal.estimate_ht, 0.0205476953144428, atol=1e-12)

    original_refusal = original.loc[
        original.domain.eq("original_nonengagement")
        & original.human_outcome.eq("genuine_refusal")
    ].iloc[0]
    original_false_positive = original.loc[
        original.domain.eq("original_nonengagement")
        & original.human_outcome.eq("not_genuine_refusal_false_positive_for_refusal")
    ].iloc[0]
    assert np.isclose(
        original_refusal.estimate_ht + original_false_positive.estimate_ht, 1.0,
        atol=1e-12,
    )


def test_coder_confirmed_language_review_is_versioned_and_applied():
    pilot = ROOT / "annotations" / "response_validity_human_v2"
    v1_manifest = json.loads((pilot / "base_freeze_v1" / "freeze_manifest.json").read_text())
    result = human_audit.build_language_corrected_base_labels(ROOT, pilot)
    corrected = pd.read_parquet(
        pilot / "base_freeze_v2_language_corrected" / "base_labels.parquet"
    )
    assert result["base_v1_preserved"] is True
    assert result["input_sha256"]["v1_base_labels_sha256"] == v1_manifest["artifact_sha256"]["base_labels.parquet"]
    assert len(corrected) == 300 and corrected.review_id.nunique() == 300
    assert corrected.primary_class.eq("wrong_language").sum() == 15
    assert corrected.language_fidelity.eq("wrong_language").sum() == 15
    assert corrected.language_fidelity.eq("mixed").sum() == 2


def test_language_corrected_audit_reproduces_revised_headlines():
    audit = (
        ROOT / "annotations" / "response_validity_human_v2"
        / "preliminary_audit_v2_language_corrected"
    )
    prevalence = pd.read_csv(audit / "design_weighted_prevalence.csv")
    overall = prevalence.loc[prevalence.dimension.eq("overall")].set_index("outcome")
    assert np.isclose(overall.loc["genuine_refusal", "estimate_ht"], 0.0205476953144428)
    assert np.isclose(overall.loc["capability_failure", "estimate_ht"], 0.1937652074428283)
