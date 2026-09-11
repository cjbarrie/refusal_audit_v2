"""Integrity checks for the frozen preliminary v2.2 design-based estimates."""

import json
from pathlib import Path

import pandas as pd

from refusal_audit.response_validity.human_pilot import sha_file


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "annotations/response_validity_human_v2/stage18_preliminary_v2_2"


def test_preliminary_stage18_artifacts_are_complete_and_hash_locked() -> None:
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete_provisional_diagnostic"
    assert manifest["n_population"] == 137_186
    assert manifest["n_probability_sample"] == 300
    assert manifest["n_direct_v2_2_in_probability_sample"] == 45
    assert manifest["n_mapped_v2_1_clear_in_probability_sample"] == 255
    assert manifest["network_call_made"] is False
    for name, expected in manifest["artifact_sha256"].items():
        assert sha_file(OUTPUT / name) == expected

    main = pd.read_csv(OUTPUT / "main_estimands.csv")
    overall = main.loc[main.family.eq("prevalence")].set_index("outcome")
    assert overall.loc["genuine_refusal", "sample_events"] == 13
    assert overall.loc["capability_failure", "sample_events"] == 71
    assert abs(overall.loc["genuine_refusal", "estimate"] - 0.018318) < 1e-6
    home = main.loc[main.family.eq("standardized_home")]
    assert not home.ready_on_direct_human_labels.any()
    assert home.loc[home.outcome.eq("genuine_refusal"), "sample_events"].sum() == 2
