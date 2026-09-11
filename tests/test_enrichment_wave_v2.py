import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.enrichment_design_v2 import ALLOCATIONS, ROUTING_STRATA  # noqa: E402
from refusal_audit.response_validity.enrichment_wave_v2 import freeze_enrichment_wave_v2  # noqa: E402
from refusal_audit.response_validity.human_pilot import KEY, sha_file  # noqa: E402


PILOT = ROOT / "annotations" / "response_validity_human_v2"
WAVE = PILOT / "enrichment_wave_v2_400"


def test_wave_is_frozen_local_and_exact():
    manifest = json.loads((WAVE / "wave_manifest.json").read_text())
    design = pd.read_parquet(WAVE / "wave_design.parquet")
    assert manifest["selected_rows"] == len(design) == 400
    assert not design.duplicated(KEY).any()
    assert design.routing_stratum.value_counts().reindex(ROUTING_STRATA).tolist() == list(ALLOCATIONS[400])
    assert manifest["design_approval"].startswith("User:")
    if manifest.get("translation_authorized"):
        assert manifest["translation_authorization"]["payload_sha256"] == manifest["translation_payload_sha256"]
        assert manifest["translation_authorization"]["cost_ceiling_usd"] == 3.0
    assert manifest["silent_repeats"] == 0


def test_wave_excludes_pilot_and_prevents_prompt_leakage():
    wave = pd.read_parquet(WAVE / "wave_design.parquet")
    pilot = pd.read_parquet(PILOT / "pilot_design.parquet")
    assert not set(map(tuple, wave[KEY].to_numpy())).intersection(map(tuple, pilot[KEY].to_numpy()))
    development = set(wave.loc[wave.analysis_split.eq("development"), "prompt_id"])
    evaluation = set(wave.loc[wave.analysis_split.eq("evaluation"), "prompt_id"])
    assert not development.intersection(evaluation)
    assert set(wave.analysis_split) == {"development", "evaluation"}


def test_probabilities_and_payload_are_declared_and_hashed():
    manifest = json.loads((WAVE / "wave_manifest.json").read_text())
    design = pd.read_parquet(WAVE / "wave_design.parquet")
    expected = 1 - (1 - design.pi_pilot) * (1 - design.pi_wave_given_history)
    assert np.allclose(design.sequential_inclusion_probability, expected)
    assert np.allclose(design.sequential_sampling_weight, 1 / expected)
    assert manifest["first_wave_probability_verified"] is True
    assert sha_file(WAVE / "translation_requests.jsonl") == manifest["translation_payload_sha256"]
    assert sum(1 for _ in (WAVE / "translation_requests.jsonl").open()) == 400


def test_freeze_is_idempotent():
    result = freeze_enrichment_wave_v2(ROOT, PILOT, confirm_design_approval=True)
    assert result["translation_payload_sha256"] == "f91cf3d093a398df03561cb8906e1f45965da87fe76d804ffd2f679bf35d6785"
