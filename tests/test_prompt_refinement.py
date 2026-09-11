import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.prompt_refinement import (  # noqa: E402
    BOUNDARY_EXEMPLARS,
    build_partial_refusal_prompt_drafts,
)


WAVE = ROOT / "annotations" / "response_validity_human_v2" / "enrichment_wave_v2_400"


def test_partial_refusal_prompt_drafts_use_development_only(tmp_path):
    output = tmp_path / "prompt_development_v1"
    manifest = build_partial_refusal_prompt_drafts(ROOT, WAVE, output)
    examples = pd.read_parquet(output / "boundary_exemplars.parquet")
    prompts = json.loads((output / "candidate_system_prompts.json").read_text())
    configs = pd.read_csv(output / "candidate_configurations.csv")

    assert manifest["protected_evaluation_rows_read"] is False
    assert manifest["provider_requests_built"] is False
    assert manifest["network_call_made"] is False
    assert len(examples) == len(BOUNDARY_EXEMPLARS) == 10
    assert examples.review_id.tolist() == BOUNDARY_EXEMPLARS
    assert set(examples.prompt_language) == {"ar", "en", "hi", "ru", "zh"}
    assert set(examples.primary_class) == {"coherent_answer", "genuine_refusal"}
    assert len(configs) == len(prompts) == 2
    assert all("requested substantive component" in prompt for prompt in prompts.values())
    assert not any("request" in path.name for path in output.iterdir())


def test_partial_refusal_prompt_drafts_are_idempotent(tmp_path):
    output = tmp_path / "prompt_development_v1"
    first = build_partial_refusal_prompt_drafts(ROOT, WAVE, output)
    second = build_partial_refusal_prompt_drafts(ROOT, WAVE, output)
    assert first == second
