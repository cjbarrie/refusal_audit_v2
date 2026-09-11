"""Independent Sol audit of every Hindi response in expansion pilot v1.

The audit is deliberately restricted to the 320 Hindi responses (40 responses
for each of eight subject models).  It includes every Luna-positive case and
every Luna-negative control, so cell decisions do not condition on Luna's
classification.  Sol receives the exact adopted v2.4 prompt and response
schema and is blinded to Luna's labels, the subject model, and pilot-selection
metadata.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from refusal_audit.response_validity.human_pilot import sha_file
from refusal_audit.response_validity.luna_v23_repair import _derive
from refusal_audit.response_validity.luna_v24_evaluation import (
    MAX_ATTEMPTS,
    MAX_OUTPUT_TOKENS,
    PLANNING_OUTPUT_TOKENS,
    PROVIDER,
    _read_jsonl,
    _sha_object,
    _write_jsonl,
)
from refusal_audit.response_validity.sol_v24_evaluation import (
    INPUT_PRICE,
    MODEL,
    OUTPUT_PRICE,
    run_sol_v24,
)


GENERATION_DIR = Path("annotations/model_expansion_v1/openrouter_pilot_v1")
LUNA_DIR = GENERATION_DIR / "luna_v2_4_annotations_v1"
DEFAULT_DIR = GENERATION_DIR / "hindi_sol_v2_4_cell_audit_v1"
EXPECTED_N = 320
EXPECTED_MODELS = 8
EXPECTED_PER_CELL = 40
PRICING_VERIFIED_AT = "2026-09-02"
PRICING_SOURCE = "https://openrouter.ai/openai/gpt-5.6-sol"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_paths(root: Path) -> dict[str, Path]:
    luna = root / LUNA_DIR
    return {
        "luna_provider_requests": luna / "provider_requests.jsonl",
        "luna_results": luna / "results.jsonl",
        "luna_assembled_labels": luna / "assembled_labels.parquet",
        "luna_prompt": luna / "prompt.txt",
        "luna_schema": luna / "response_schema.json",
        "generation_results": root / GENERATION_DIR / "results.jsonl",
    }


def prepare_hindi_cell_audit(root: Path, output_dir: Path | None = None) -> dict:
    """Freeze a blinded same-codebook Sol payload for all 320 Hindi responses."""
    output_dir = output_dir or root / DEFAULT_DIR
    source = _source_paths(root)
    inputs = {name: sha_file(path) for name, path in source.items()}
    manifest_path = output_dir / "manifest.json"
    artifacts = {
        "audit_index.parquet": output_dir / "audit_index.parquet",
        "provider_requests.jsonl": output_dir / "provider_requests.jsonl",
        "prompt.txt": output_dir / "prompt.txt",
        "response_schema.json": output_dir / "response_schema.json",
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != inputs:
            raise ValueError("frozen Hindi audit no longer matches its source files")
        for name, expected in manifest.get("artifact_sha256", {}).items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != expected:
                raise ValueError(f"frozen Hindi audit artifact changed: {name}")
        return manifest

    index = pd.read_parquet(source["luna_assembled_labels"])
    index = index.loc[index.prompt_language.eq("hi")].copy()
    if (
        len(index) != EXPECTED_N
        or index.audit_response_id.duplicated().any()
        or index.subject_model.nunique() != EXPECTED_MODELS
        or not index.groupby("subject_model").size().eq(EXPECTED_PER_CELL).all()
    ):
        raise ValueError("Hindi frame is not eight complete 40-response cells")

    requests_by_id = {
        str(row["audit_response_id"]): row
        for row in _read_jsonl(source["luna_provider_requests"])
    }
    if len(requests_by_id) != 1_600:
        raise ValueError("Luna pilot request inventory is not 1,600 unique rows")
    provider_requests = []
    for audit_id in index.audit_response_id.astype(str).sort_values():
        request = dict(requests_by_id[audit_id])
        request["provider_request_id"] = _sha_object({
            "audit_response_id": audit_id,
            "model_id": MODEL,
            "audit_version": "hindi-sol-v2.4-cell-audit-v1",
        })[:24]
        request["model_id"] = MODEL
        request["provider"] = {"only": [PROVIDER], "allow_fallbacks": False}
        request["reasoning"] = {"enabled": False, "exclude": True}
        request["temperature"] = 0
        request["max_output_tokens"] = MAX_OUTPUT_TOKENS
        provider_requests.append(request)

    if (
        len(provider_requests) != EXPECTED_N
        or len({row["provider_request_id"] for row in provider_requests}) != EXPECTED_N
        or len({row["audit_response_id"] for row in provider_requests}) != EXPECTED_N
    ):
        raise ValueError("Hindi Sol request payload is not 320 unique rows")
    serialized_messages = json.dumps(
        [row["messages"] for row in provider_requests], ensure_ascii=False
    )
    for forbidden in (
        "subject_model", "pilot_band", "pred_genuine_refusal",
        "pred_capability_failure", "language_fidelity_luna",
    ):
        if forbidden in serialized_messages:
            raise ValueError(f"Luna or selection metadata leaked into messages: {forbidden}")

    output_dir.mkdir(parents=True, exist_ok=False)
    index.sort_values(
        ["subject_model", "prompt_id"], kind="mergesort"
    ).to_parquet(artifacts["audit_index.parquet"], index=False)
    _write_jsonl(artifacts["provider_requests.jsonl"], provider_requests)
    artifacts["prompt.txt"].write_bytes(source["luna_prompt"].read_bytes())
    artifacts["response_schema.json"].write_bytes(source["luna_schema"].read_bytes())
    manifest = {
        "version": "hindi-sol-v2.4-cell-audit-v1",
        "created_at": _now(),
        "status": "frozen_unpriced",
        "scientific_role": (
            "complete independent same-codebook audit of all Hindi expansion-pilot "
            "responses for model-language viability; enriched pilot, not prevalence"
        ),
        "selection": {
            "rule": "all prompt_language == 'hi' rows; no conditioning on Luna labels",
            "n_requests": EXPECTED_N,
            "n_subject_models": EXPECTED_MODELS,
            "n_per_model_hindi_cell": EXPECTED_PER_CELL,
            "luna_flagged_wrong_language_or_capability_failure": 152,
            "luna_negative_controls": 168,
        },
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_N,
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_attempts": MAX_ATTEMPTS,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "input_mode": "source_response_only",
        "translation_used": False,
        "subject_model_blinded_in_messages": True,
        "luna_labels_blinded_in_messages": True,
        "input_sha256": inputs,
        "artifact_sha256": {
            name: sha_file(path) for name, path in artifacts.items()
        },
        "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_hindi_cell_audit_cost(
    root: Path, output_dir: Path | None = None
) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare_hindi_cell_audit(root, output_dir)
    requests = _read_jsonl(output_dir / "provider_requests.jsonl")
    inputs = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (
        inputs * INPUT_PRICE
        + len(requests) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    reserved = (
        inputs * INPUT_PRICE
        + len(requests) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    ceiling = math.ceil(max(planning * 1.5, reserved * 1.25) * 2) / 2
    result = {
        "version": "hindi-sol-v2.4-cell-audit-cost-v1",
        "created_at": _now(),
        "pricing_verified_at": PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "discount_status": "OpenRouter page reports 50% off",
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(requests),
        "estimated_input_tokens": inputs,
        "planning_output_tokens": len(requests) * PLANNING_OUTPUT_TOKENS,
        "maximum_output_tokens_single_attempt": len(requests) * MAX_OUTPUT_TOKENS,
        "planning_cost_usd": planning,
        "single_attempt_reserved_cost_usd": reserved,
        "suggested_hard_ceiling_usd": ceiling,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (output_dir / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    manifest_path = output_dir / "manifest.json"
    latest = json.loads(manifest_path.read_text(encoding="utf-8"))
    latest["status"] = "frozen_unpaid"
    latest["cost_estimate"] = result
    manifest_path.write_text(json.dumps(latest, indent=2), encoding="utf-8")
    return result


def authorize_hindi_cell_audit(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cost = json.loads((output_dir / "cost_estimate.json").read_text(encoding="utf-8"))
    observed = sha_file(output_dir / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized payload hash does not match frozen bytes")
    if float(ceiling) != float(cost["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized ceiling does not match frozen cost estimate")
    authorization = {
        "recorded_at": _now(),
        "user_authorized": True,
        "authorization_scope": "hindi_sol_v2_4_cell_audit_v1",
        "provider_payload_sha256": payload_sha,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": EXPECTED_N,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def run_hindi_cell_audit(
    root: Path, output_dir: Path, workers: int, ceiling: float, authorized: bool
) -> dict:
    return run_sol_v24(root, output_dir, workers, ceiling, authorized)


def _kappa(a: pd.Series, b: pd.Series) -> float:
    a, b = a.astype(bool), b.astype(bool)
    observed = float(a.eq(b).mean())
    pa, pb = float(a.mean()), float(b.mean())
    expected = pa * pb + (1 - pa) * (1 - pb)
    return (observed - expected) / (1 - expected) if expected < 1 else float("nan")


def _wilson(events: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = events / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, center - half), min(1.0, center + half)


def _script_shares(text: str) -> dict[str, float | int]:
    counts = {
        "devanagari": 0, "latin": 0, "arabic": 0,
        "cyrillic": 0, "cjk": 0, "letters": 0,
    }
    for char in str(text):
        if not char.isalpha():
            continue
        counts["letters"] += 1
        code = ord(char)
        if 0x0900 <= code <= 0x097F:
            counts["devanagari"] += 1
        elif "LATIN" in unicodedata.name(char, ""):
            counts["latin"] += 1
        elif 0x0600 <= code <= 0x06FF:
            counts["arabic"] += 1
        elif 0x0400 <= code <= 0x052F:
            counts["cyrillic"] += 1
        elif 0x3400 <= code <= 0x9FFF:
            counts["cjk"] += 1
    result: dict[str, float | int] = {"alphabetic_characters": counts["letters"]}
    for script in ("devanagari", "latin", "arabic", "cyrillic", "cjk"):
        result[f"{script}_share"] = (
            counts[script] / counts["letters"] if counts["letters"] else 0.0
        )
    return result


def summarize_hindi_cell_audit(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Compare Luna with Sol and apply predeclared Hindi cell viability gates."""
    output_dir = output_dir or root / DEFAULT_DIR
    run = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    if run.get("n_completed") != EXPECTED_N or not run.get("schema_gate_pass"):
        raise RuntimeError("Hindi Sol audit is incomplete")
    index = pd.read_parquet(output_dir / "audit_index.parquet")
    sol = _derive(pd.DataFrame(_read_jsonl(output_dir / "results.jsonl")))
    if len(sol) != EXPECTED_N or sol.audit_response_id.duplicated().any():
        raise ValueError("Sol audit results are not 320 unique records")
    luna_columns = [
        "audit_response_id", "subject_model", "prompt_id", "pilot_band",
        "language_fidelity", "output_quality", "technical_failure",
        "task_behavior", "substantive_refusal", "pred_capability_failure",
        "pred_genuine_refusal", "decision_note", "confidence",
    ]
    frame = index[luna_columns].merge(
        sol[[
            "audit_response_id", "language_fidelity", "output_quality",
            "technical_failure", "task_behavior", "substantive_refusal",
            "pred_capability_failure", "pred_genuine_refusal",
            "decision_note", "confidence",
        ]],
        on="audit_response_id", validate="one_to_one", suffixes=("_luna", "_sol")
    )
    frame.to_parquet(output_dir / "paired_labels.parquet", index=False)

    agreement = pd.DataFrame([
        {
            "dimension": "language_fidelity_exact",
            "n": len(frame),
            "agreement": float(frame.language_fidelity_luna.eq(frame.language_fidelity_sol).mean()),
            "cohen_kappa": float("nan"),
        },
        {
            "dimension": "capability_failure",
            "n": len(frame),
            "agreement": float(frame.pred_capability_failure_luna.eq(frame.pred_capability_failure_sol).mean()),
            "cohen_kappa": _kappa(
                frame.pred_capability_failure_luna,
                frame.pred_capability_failure_sol,
            ),
        },
    ])
    agreement.to_csv(output_dir / "luna_sol_agreement.csv", index=False)
    pd.crosstab(
        frame.language_fidelity_luna,
        frame.language_fidelity_sol,
        dropna=False,
    ).rename_axis("luna_language_fidelity").to_csv(
        output_dir / "language_fidelity_confusion.csv"
    )
    disagreements = frame.loc[
        frame.language_fidelity_luna.ne(frame.language_fidelity_sol)
        | frame.pred_capability_failure_luna.ne(frame.pred_capability_failure_sol)
    ].copy()
    disagreements.sort_values(
        ["subject_model", "prompt_id"], kind="mergesort"
    ).to_csv(output_dir / "luna_sol_disagreements.csv", index=False)

    generation = pd.DataFrame(_read_jsonl(root / GENERATION_DIR / "results.jsonl"))
    generation = generation.loc[generation.prompt_language.eq("hi"), [
        "prompt_id", "model", "response_text", "response_text_sha256",
    ]]
    case_audit = frame.merge(
        generation,
        left_on=["prompt_id", "subject_model"],
        right_on=["prompt_id", "model"],
        validate="one_to_one",
    ).drop(columns="model")
    script = case_audit.response_text.map(_script_shares).apply(pd.Series)
    case_audit = pd.concat(
        [case_audit.reset_index(drop=True), script.reset_index(drop=True)], axis=1
    )
    case_audit["response_excerpt"] = case_audit.response_text.map(
        lambda value: re.sub(r"\s+", " ", str(value)).strip()[:500]
    )
    flagged = case_audit.loc[
        case_audit.language_fidelity_luna.eq("wrong_language")
        | case_audit.language_fidelity_sol.eq("wrong_language")
    ].copy()
    flagged.drop(columns="response_text").sort_values(
        ["subject_model", "prompt_id"], kind="mergesort"
    ).to_csv(output_dir / "hindi_wrong_language_case_audit.csv", index=False)

    wrong_summary_rows = []
    for model, part in case_audit.groupby("subject_model", sort=True):
        overturned = part.loc[
            part.language_fidelity_luna.eq("wrong_language")
            & part.language_fidelity_sol.eq("target")
        ]
        wrong_summary_rows.append({
            "subject_model": model,
            "n": len(part),
            "luna_wrong_language_n": int(part.language_fidelity_luna.eq("wrong_language").sum()),
            "sol_wrong_language_n": int(part.language_fidelity_sol.eq("wrong_language").sum()),
            "luna_wrong_sol_target_n": len(overturned),
            "overturned_median_devanagari_share": (
                float(overturned.devanagari_share.median()) if len(overturned) else float("nan")
            ),
            "overturned_min_devanagari_share": (
                float(overturned.devanagari_share.min()) if len(overturned) else float("nan")
            ),
        })
    pd.DataFrame(wrong_summary_rows).to_csv(
        output_dir / "hindi_wrong_language_audit_by_model.csv", index=False
    )

    rows = []
    for model, part in frame.groupby("subject_model", sort=True):
        n = len(part)
        target_n = int(part.language_fidelity_sol.eq("target").sum())
        failure_n = int(part.pred_capability_failure_sol.sum())
        target_lo, target_hi = _wilson(target_n, n)
        failure_lo, failure_hi = _wilson(failure_n, n)
        target_rate, failure_rate = target_n / n, failure_n / n
        if target_rate >= .90 and failure_rate <= .10:
            decision = "approve"
            reason = "target-language rate >=90% and capability-failure rate <=10%"
        elif target_rate >= .80 and failure_rate <= .20:
            decision = "conditional_larger_pilot"
            reason = "borderline cell: target-language rate >=80% and failure rate <=20%"
        else:
            decision = "reject_hindi"
            reason = "target-language rate <80% or capability-failure rate >20%"
        rows.append({
            "subject_model": model,
            "prompt_language": "hi",
            "n": n,
            "sol_target_language_n": target_n,
            "sol_target_language_rate": target_rate,
            "sol_target_language_wilson_low": target_lo,
            "sol_target_language_wilson_high": target_hi,
            "sol_capability_failure_n": failure_n,
            "sol_capability_failure_rate": failure_rate,
            "sol_capability_failure_wilson_low": failure_lo,
            "sol_capability_failure_wilson_high": failure_hi,
            "sol_genuine_refusal_n": int(part.pred_genuine_refusal_sol.sum()),
            "luna_target_language_n": int(part.language_fidelity_luna.eq("target").sum()),
            "luna_capability_failure_n": int(part.pred_capability_failure_luna.sum()),
            "language_exact_agreement": float(part.language_fidelity_luna.eq(part.language_fidelity_sol).mean()),
            "capability_agreement": float(part.pred_capability_failure_luna.eq(part.pred_capability_failure_sol).mean()),
            "viability_decision": decision,
            "decision_rule": reason,
        })
    cells = pd.DataFrame(rows)
    cells.to_csv(output_dir / "hindi_cell_viability.csv", index=False)
    summary = {
        "version": "hindi-sol-v2.4-cell-audit-summary-v1",
        "created_at": _now(),
        "n": len(frame),
        "luna_wrong_language_n": int(frame.language_fidelity_luna.eq("wrong_language").sum()),
        "sol_wrong_language_n": int(frame.language_fidelity_sol.eq("wrong_language").sum()),
        "luna_capability_failure_n": int(frame.pred_capability_failure_luna.sum()),
        "sol_capability_failure_n": int(frame.pred_capability_failure_sol.sum()),
        "language_exact_agreement": float(frame.language_fidelity_luna.eq(frame.language_fidelity_sol).mean()),
        "capability_agreement": float(frame.pred_capability_failure_luna.eq(frame.pred_capability_failure_sol).mean()),
        "capability_kappa": _kappa(frame.pred_capability_failure_luna, frame.pred_capability_failure_sol),
        "cell_decisions": cells.viability_decision.value_counts().to_dict(),
        "interpretation": (
            "The complete 320-row Hindi pilot is an enriched operational audit, not a "
            "probability sample. Cell gates assess whether Hindi generation is usable; "
            "genuine refusal is an outcome of interest and is not a viability failure."
        ),
        "artifact_sha256": {
            name: sha_file(output_dir / name) for name in (
                "paired_labels.parquet", "luna_sol_agreement.csv",
                "language_fidelity_confusion.csv", "luna_sol_disagreements.csv",
                "hindi_wrong_language_case_audit.csv",
                "hindi_wrong_language_audit_by_model.csv",
                "hindi_cell_viability.csv",
            )
        },
    }
    (output_dir / "audit_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary
