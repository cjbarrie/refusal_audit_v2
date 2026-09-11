import json
from pathlib import Path

import pandas as pd

from refusal_audit.response_validity.human_pilot import KEY, sha_file
from refusal_audit.response_validity.luna_v24_human_certification import (
    DEFAULT_DIR,
    GOLD,
    OLD_EXTERNAL_DIR,
    PHASE2_DIR,
    SOL_REFERENCE_DIR,
)
from refusal_audit.response_validity.luna_v23_repair import _schema
from refusal_audit.response_validity.luna_v24_evaluation import _call


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_certification_sample_is_fresh_and_probability_weighted():
    out = ROOT / DEFAULT_DIR
    design = pd.read_parquet(out / "sample_design.parquet")
    development = pd.read_parquet(ROOT / GOLD, columns=KEY)
    old_external = pd.read_parquet(
        ROOT / OLD_EXTERNAL_DIR / "sample_design.parquet", columns=KEY
    )
    sample_keys = set(map(tuple, design[KEY].itertuples(index=False, name=None)))
    assert len(design) == 1196
    assert design.certification_response_id.is_unique
    assert not sample_keys.intersection(
        map(tuple, development.itertuples(index=False, name=None))
    )
    assert not sample_keys.intersection(
        map(tuple, old_external.itertuples(index=False, name=None))
    )
    assert design.phase1_inclusion_probability.between(0, 1, inclusive="right").all()
    assert (1 / design.phase1_inclusion_probability).equals(
        design.phase1_sampling_weight
    )


def test_frozen_certification_payload_is_blinded_and_manifest_bound():
    out = ROOT / DEFAULT_DIR
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    payload = (out / "provider_requests.jsonl").read_text(encoding="utf-8")
    assert manifest["population_and_sample"]["eligible_untouched_population_n"] == 135289
    assert manifest["n_requests"] == 1196
    assert manifest["provider_payload_sha256"] == sha_file(
        out / "provider_requests.jsonl"
    )
    for forbidden in (
        "engagement_code", "refusal_justification", "routing_stratum",
        "sampling_weight", "inclusion_probability", "human_", "sol_",
    ):
        assert forbidden not in payload


def test_runner_accepts_certification_identifier_after_provider_return():
    class Usage:
        def model_dump(self):
            return {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0}

    class Message:
        content = json.dumps({
            "task_behavior": "complete_answer",
            "substantive_refusal": "none",
            "stance_disclaimer": False,
            "epistemic_limitation": False,
            "language_fidelity": "target_language",
            "output_quality": "coherent",
            "technical_failure": "none",
            "confidence": "high",
            "refusal_evidence_span": "",
            "decision_note": "Direct answer.",
        })

    class Response:
        usage = Usage()
        choices = [type("Choice", (), {"message": Message()})()]
        id = "test-response"
        model = "test-model"

    class Completions:
        @staticmethod
        def create(**kwargs):
            return Response()

    client = type(
        "Client", (), {"chat": type("Chat", (), {"completions": Completions()})()}
    )()
    request = {
        "certification_response_id": "cert-1",
        "provider_request_id": "provider-1",
        "logical_request_id": "logical-1",
        "model_id": "test-model",
        "messages": [],
        "temperature": 0,
        "max_output_tokens": 500,
        "reasoning": {"enabled": False},
        "provider": {"only": ["openai"]},
        "response_schema": _schema(),
    }
    codebook = json.loads(
        (ROOT / "config/response_validity_decomposed_v2_4.json").read_text()
    )
    result = _call(client, request, codebook)
    assert result["status"] in {"complete", "error"}
    assert result["audit_response_id"] == "cert-1"


def test_phase2_review_draw_has_known_probabilities_and_is_blinded():
    out = ROOT / PHASE2_DIR
    design = pd.read_parquet(out / "phase2_design.parquet")
    source = pd.read_parquet(out / "review_source_packet.parquet")
    manifest = json.loads((out / "wave_manifest.json").read_text())
    assert len(design) == len(source) == 472
    assert design.review_id.is_unique and source.review_id.is_unique
    assert set(design.review_id) == set(source.review_id)
    assert set(design.loc[
        design.phase2_stratum.isin(
            ["luna_refusal_positive", "proxy_refusal_negative"]
        ), "human_review_probability"
    ]) == {1.0}
    assert (
        1 / design.combined_inclusion_probability
    ).equals(design.combined_sampling_weight)
    assert manifest["expected_human_review_n"] == 450.20000000000005
    assert manifest["translation_request_n"] == 375
    assert not any(
        token in source.columns
        for token in ["model", "routing_stratum", "pred_genuine_refusal"]
    )


def test_fresh_sol_reference_covers_phase1_and_remains_blinded():
    out = ROOT / SOL_REFERENCE_DIR
    manifest = json.loads((out / "manifest.json").read_text())
    requests = [
        json.loads(line)
        for line in (out / "provider_requests.jsonl").read_text().splitlines()
        if line
    ]
    assert manifest["n_requests"] == len(requests) == 1196
    assert len({row["certification_response_id"] for row in requests}) == 1196
    assert manifest["provider_payload_sha256"] == sha_file(
        out / "provider_requests.jsonl"
    )
    assert all(row["model_id"] == "openai/gpt-5.6-sol" for row in requests)
    serialized = json.dumps(requests)
    for forbidden in (
        "pred_genuine_refusal", "engagement_code", "human_", "routing_stratum",
        "phase1_inclusion_probability", "sampling_weight", "luna_",
    ):
        assert forbidden not in serialized


def test_fresh_sol_score_uses_phase1_weights_and_frontier_wording():
    out = ROOT / SOL_REFERENCE_DIR
    summary = json.loads((out / "score_summary.json").read_text())
    refusal = summary["headline"]["design_weighted_refusal"]
    assert summary["headline"]["status"] == (
        "complete_frontier_model_reference_not_human_ground_truth"
    )
    assert summary["headline"]["unweighted_refusal_disagreement_n"] == 22
    assert abs(refusal["precision"] - 0.8971868115455922) < 1e-12
    assert abs(refusal["recall"] - 0.8946680839565039) < 1e-12
    assert abs(refusal["f1"] - 0.8959256775215826) < 1e-12
    intervals = pd.read_csv(out / "issue_cluster_bootstrap_intervals.csv")
    assert set(intervals.outcome) == {"genuine_refusal", "capability_failure"}
    assert intervals.draws.eq(2000).all()
