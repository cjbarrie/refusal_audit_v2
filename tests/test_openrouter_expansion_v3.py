import hashlib
import json
from pathlib import Path

from refusal_audit.model_expansion.full_run_v3 import (
    DEFAULT_DIR, EXPECTED_REQUESTS, V31_HUNYUAN_DIR,
    estimate_full_run_cost, estimate_hunyuan_revision_cost,
    prepare_full_run, prepare_hunyuan_all_languages_revision,
)
from refusal_audit.model_expansion.full_run_annotation_v3 import (
    BATCH2_EXPECTED_N, NEXT_DIR, estimate_next_batch_annotation_cost,
    prepare_next_batch_annotations, BATCH3_EXPECTED_N, KIMI_DIR,
    estimate_kimi_batch_annotation_cost, prepare_kimi_batch_annotations,
)


ROOT = Path(__file__).resolve().parents[1]


def test_v3_freeze_is_exactly_the_approved_cells_and_canonical_prompts():
    manifest = prepare_full_run(ROOT, ROOT / DEFAULT_DIR)
    assert manifest["n_cells"] == 33
    assert manifest["n_requests"] == EXPECTED_REQUESTS == 82368
    counts = {stage["model"]: stage["n_requests"] for stage in manifest["stages"]}
    assert counts["hunyuan-a13b"] == 3 * 2496
    assert all(n == 5 * 2496 for model, n in counts.items() if model != "hunyuan-a13b")
    # The original three-language Hunyuan stage was superseded. Gemini remains
    # explicitly incomplete because one Hindi request exhausted both attempts.
    assert manifest["network_inference_call_made"] is True
    completed = {s["stage"] for s in manifest["stages"] if s.get("status") == "completed"}
    assert completed == {1, 2, 3, 5, 7}
    gemini = next(s for s in manifest["stages"] if s["stage"] == 6)
    assert gemini["status"] == "incomplete"

    seen = set()
    prompt_hash_by_key = {}
    for stage in manifest["stages"]:
        with (ROOT / DEFAULT_DIR / stage["payload_path"]).open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                assert row["messages"] == [{"role": "user", "content": row["messages"][0]["content"]}]
                assert row["temperature"] == 1.0
                assert row["max_output_tokens"] == 5000
                assert row["provider"]["allow_fallbacks"] is False
                assert row["provider"]["only"] == [row["provider_tag"]]
                assert row["provider_request_id"] not in seen
                seen.add(row["provider_request_id"])
                text_hash = hashlib.sha256(
                    row["messages"][0]["content"].encode("utf-8")
                ).hexdigest()
                assert row["prompt_text_sha256"] == text_hash
                key = (row["prompt_id"], row["prompt_language"])
                if key in prompt_hash_by_key:
                    assert prompt_hash_by_key[key] == text_hash
                else:
                    prompt_hash_by_key[key] = text_hash
    assert len(seen) == EXPECTED_REQUESTS
    assert len(prompt_hash_by_key) == 5 * 2496


def test_v3_cost_is_stage_specific_and_not_authorized():
    cost = estimate_full_run_cost(ROOT, ROOT / DEFAULT_DIR)
    assert cost["n_requests"] == EXPECTED_REQUESTS
    assert len(cost["stages"]) == 7
    assert cost["planning_cost_usd"] > 0
    assert cost["sum_of_stage_hard_ceilings_usd"] > cost["planning_cost_usd"]
    assert cost["paid_run_authorized"] is False
    assert cost["network_inference_call_made"] is False


def test_v31_hunyuan_revision_retains_all_languages_and_conditional_flags():
    manifest = prepare_hunyuan_all_languages_revision(ROOT, ROOT / V31_HUNYUAN_DIR)
    stage = manifest["stages"][0]
    assert manifest["overall_expansion_after_revision"] == {
        "n_models": 7, "n_cells": 35, "n_requests": 87360,
    }
    assert stage["n_requests"] == 5 * 2496
    assert stage["languages"] == ["en", "zh", "ar", "ru", "hi"]
    assert stage["cell_status"]["en"] == "conditional_retained"
    assert stage["cell_status"]["ru"] == "conditional_retained"
    assert stage["payload_sha256"] == "1fbcd681385d89cdb4e9b64cb82f2c069ba73443cb656f91d25acab39aaa6659"
    if stage["paid_run_authorized"]:
        assert stage["authorization"]["cost_ceiling_usd"] == 16.5
        assert stage["authorization"]["provider_payload_sha256"] == stage["payload_sha256"]
    cost = estimate_hunyuan_revision_cost(ROOT, ROOT / V31_HUNYUAN_DIR)
    assert cost["n_requests"] == 12480
    assert cost["suggested_hard_ceiling_usd"] == 16.5


def test_luna_batch2_freezes_only_returned_responses_and_records_missingness():
    manifest = prepare_next_batch_annotations(ROOT, ROOT / NEXT_DIR)
    assert manifest["n_requests"] == BATCH2_EXPECTED_N == 37_439
    assert manifest["subject_models"] == [
        "hunyuan-a13b", "glm-4.7-flash", "gemini-2.5-flash-lite",
    ]
    assert manifest["input_mode"] == "source_response_only"
    assert manifest["translation_used"] is False
    assert len(manifest["source_missingness"]) == 1
    missing = manifest["source_missingness"][0]
    assert missing["model"] == "gemini-2.5-flash-lite"
    assert missing["prompt_language"] == "hi"
    assert missing["attempts"] == 2
    assert missing["classification"] == "provider_level_missing_response"
    cost = estimate_next_batch_annotation_cost(ROOT, ROOT / NEXT_DIR)
    assert cost["requests"] == BATCH2_EXPECTED_N
    assert cost["paid_run_authorized"] is False


def test_luna_batch3_freezes_completed_kimi_responses():
    manifest = prepare_kimi_batch_annotations(ROOT, ROOT / KIMI_DIR)
    assert manifest["n_requests"] == BATCH3_EXPECTED_N == 12_480
    assert manifest["subject_models"] == ["kimi-k2.5"]
    assert manifest["input_mode"] == "source_response_only"
    assert manifest["translation_used"] is False
    assert manifest["source_missingness"] == []
    cost = estimate_kimi_batch_annotation_cost(ROOT, ROOT / KIMI_DIR)
    assert cost["requests"] == BATCH3_EXPECTED_N
    assert cost["paid_run_authorized"] is False
