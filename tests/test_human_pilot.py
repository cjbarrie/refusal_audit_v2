import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.human_pilot import (  # noqa: E402
    minimal_label_defaults,
    priority_class,
    validate_human_label,
)


def test_priority_class_is_mutually_exclusive_and_ordered():
    x = pd.DataFrame({
        "engagement_code": [4, 1, 1, 1, 1, 1],
        "diag_target_script_mismatch": [False] * 5 + [True],
        "diag_repetition_loop": [False] * 6,
        "diag_truncation_suspect": [False] * 6,
        "diag_metadata_language_disagreement": [False] * 6,
        "diag_replacement_rate": [0.0] * 6,
        "dsl_prediction_capability_failure": [0, .5, 0, 0, 0, 0],
        "dsl_prediction_clean_genuine_refusal": [0, 0, .5, 0, 0, 0],
        "dsl_prediction_coherent_pivot": [0, 0, 0, .5, 0, 0],
    })
    assert priority_class(x).tolist() == [
        "original_nonengagement", "predicted_capability", "predicted_refusal",
        "predicted_pivot", "ordinary_control", "diagnostic_flag",
    ]


def test_codebook_enforces_refusal_consistency():
    codebook = json.loads((ROOT / "config" / "response_validity_codebook_v2.json").read_text())
    valid = {
        "primary_class": "genuine_refusal", "noncompliance_signal": "explicit",
        "coherence": "coherent", "language_fidelity": "target",
        "technical_failure": "none", "confidence": "high", "evidence_span": "I can't help",
    }
    assert validate_human_label(valid, codebook) == []
    invalid = dict(valid, coherence="incoherent", noncompliance_signal="none")
    assert len(validate_human_label(invalid, codebook)) == 2


def test_simplified_form_defaults_preserve_primary_class_logic():
    codebook = json.loads((ROOT / "config" / "response_validity_codebook_v2.json").read_text())
    for primary_class in codebook["fields"]["primary_class"]:
        label = {
            "primary_class": primary_class,
            **minimal_label_defaults(primary_class),
            "confidence": "medium",
            "evidence_span": "",
        }
        if primary_class == "genuine_refusal":
            label["noncompliance_signal"] = "explicit"
            label["evidence_span"] = "I cannot help with that."
        if primary_class == "technical_degeneration":
            label["technical_failure"] = "repetition_loop"
        assert validate_human_label(label, codebook) == []


def test_frozen_pilot_has_positive_exact_union_probabilities():
    design_path = ROOT / "annotations" / "response_validity_human_v2" / "pilot_design.parquet"
    manifest_path = ROOT / "annotations" / "response_validity_human_v2" / "pilot_manifest.json"
    assert design_path.exists() and manifest_path.exists()
    design = pd.read_parquet(design_path)
    expected = 1 - (
        (1 - design.pi_global)
        * (1 - design.pi_model_language)
        * (1 - design.pi_priority)
    )
    assert len(design) == 300
    assert not design.duplicated(["prompt_id", "prompt_language", "model"]).any()
    assert design.inclusion_probability.gt(0).all()
    assert (expected - design.inclusion_probability).abs().max() < 1e-12
    assert design.groupby(["model", "prompt_language"]).size().gt(0).all()
    manifest = json.loads(manifest_path.read_text())
    if manifest["translation_sent"]:
        assert manifest["translation_run"]["n"] == 300
        assert manifest["translation_run"]["provider_cost_usd"] <= 3.0
        assert manifest["translations_ingested"] is True
