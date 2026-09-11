from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.external_human_validation import (  # noqa: E402
    SEED,
    assemble_external_human_review,
    assemble_external_sol_reference,
    freeze_external_human_phase2,
)


@pytest.fixture(scope="module")
def frozen(tmp_path_factory):
    output = tmp_path_factory.mktemp("external-human-phase2") / "frozen"
    manifest = freeze_external_human_phase2(ROOT, output, seed=SEED)
    return output, manifest


def test_phase2_realization_is_frozen_and_design_valid(frozen):
    output, manifest = frozen
    assert manifest["external_phase1_n"] == 1197
    assert manifest["realized_human_review_n"] == 458
    assert manifest["realized_by_phase2_stratum"] == {
        "priority": 229,
        "capability_positive_agreement": 173,
        "ordinary_agreement": 56,
    }
    assert manifest["translation_request_n"] == 410
    assert manifest["translation_authorized"] is False
    assert manifest["network_call_made"] is False

    design = pd.read_parquet(output / "phase2_design.parquet")
    assert design.review_id.nunique() == 458
    assert (design.loc[design.phase2_stratum.eq("priority"),
                       "human_review_probability"] == 1).all()
    expected = (
        design.phase1_inclusion_probability * design.human_review_probability
    )
    assert design.combined_inclusion_probability.equals(expected)
    assert design.combined_inclusion_probability.between(0, 1).all()


def test_identical_rerun_does_not_redraw_or_rewrite(frozen):
    output, manifest = frozen
    before = (output / "wave_manifest.json").read_bytes()
    repeated = freeze_external_human_phase2(ROOT, output, seed=SEED)
    assert repeated == manifest
    assert (output / "wave_manifest.json").read_bytes() == before
    with pytest.raises(RuntimeError, match="different seed"):
        freeze_external_human_phase2(ROOT, output, seed=SEED + 1)


def test_review_source_is_blinded_and_translation_payload_is_exact(frozen):
    output, manifest = frozen
    source = pd.read_parquet(output / "review_source_packet.parquet")
    assert set(source) == {
        "review_id", "review_order", "source_hash", "prompt_language",
        "prompt_text_en", "prompt_text", "response_text",
    }
    requests = [
        json.loads(line) for line in
        (output / "translation_requests.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert len(requests) == manifest["translation_request_n"]
    assert all(row["prompt_language"] != "en" for row in requests)
    assert all(set(row) == {
        "review_id", "source_hash", "translation_prompt_hash",
        "prompt_language", "prompt_text_en", "prompt_text", "response_text",
    } for row in requests)


def test_assembly_requires_exact_translation_coverage_and_remains_blinded(frozen):
    output, _ = frozen
    requests = [
        json.loads(line) for line in
        (output / "translation_requests.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    records = [{
        "status": "ok",
        "review_id": row["review_id"],
        "source_hash": row["source_hash"],
        "response_translation_en": f"literal translation {row['review_id']}",
        "translation_status": "complete",
        "uncertain_spans": [],
        "detected_language": row["prompt_language"],
    } for row in requests]
    (output / "translations_raw.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8"
    )
    result = assemble_external_human_review(ROOT, output)
    assert result["n_review_tasks"] == 458
    packet = pd.read_parquet(output / "human_review_packet.parquet")
    assert len(packet) == 458
    assert not any(
        token in column
        for column in packet.columns
        for token in ("model", "routing", "luna", "sol", "probability", "weight")
    )
    english = packet.prompt_language.eq("en")
    assert (packet.loc[english, "response_translation_en"]
            == packet.loc[english, "response_text"]).all()


def test_existing_sol_reference_is_complete_and_separate_from_human_log(frozen):
    output, _ = frozen
    result = assemble_external_sol_reference(ROOT, output)
    assert result["n"] == 458
    assert result["provider_call_made"] is False
    assert result["human_label_log_modified"] is False
    labels = pd.read_parquet(output / "sol_reference_labels.parquet")
    assert labels.review_id.nunique() == 458
    assert labels.annotation_source.eq("machine_reference").all()
    assert labels.annotator_id.eq("openai/gpt-5.6-sol").all()
    assert labels.review_status.eq("complete").all()
    assert not (output / "human_labels.jsonl").exists()
