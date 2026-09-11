"""Freeze the 200-row enrichment checkpoint and its protected evaluation.

Everything in this module is local and network-free.  The live append-only
human log is copied into an immutable checkpoint without modification.  The
protected-evaluation builder then reuses two already-frozen Stage A prompts;
human outcomes are written to a separate gold file and never enter a request.
"""

from __future__ import annotations

import hashlib
import json
import fcntl
import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .human_pilot import KEY, sha_file, sha_text, validate_human_label
from .surrogate_bakeoff import (
    _format_query,
    _response_schema,
    _validate_bakeoff_label,
    score_surrogate_results,
)


CHECKPOINT_N = 200
ADVANCING_CONFIGS = ("zero_shot_joint_v1", "fewshot_error_targeted_22_v1")
EXPECTED_DEVELOPMENT = 84
EXPECTED_EVALUATION = 116
EXPECTED_REQUESTS = EXPECTED_EVALUATION * len(ADVANCING_CONFIGS)
CHECKPOINT_VERSION = "human-enrichment-checkpoint-200-v1.0"
EVALUATION_VERSION = "human-surrogate-protected-evaluation-v1.0"
AUTHORIZED_PAYLOAD_SHA256 = "b40db8fcab9a7617cd8216f728724357ae01af187fe7080dd2bace5963c772a9"
AUTHORIZED_MODEL = "openai/gpt-5.6-luna"
AUTHORIZED_PROVIDER = "openai"
AUTHORIZED_CEILING = 2.22


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: invalid JSON on line {line_no}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}: line {line_no} is not an object")
        row["_live_line"] = line_no
        rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _canonical_hash(rows: list[dict]) -> str:
    serialized = [
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for row in rows
    ]
    return sha_text("\n".join(sorted(serialized)))


def _verify_frozen_artifacts(output_dir: Path, manifest: dict) -> dict:
    for name, expected in manifest.get("artifact_sha256", {}).items():
        path = output_dir / name
        if not path.exists() or sha_file(path) != expected:
            raise RuntimeError(f"frozen artifact missing or changed: {path}")
    return manifest


def freeze_enrichment_checkpoint_200(
    root: Path,
    wave_dir: Path,
    output_dir: Path | None = None,
) -> dict:
    """Freeze exactly review orders 1--200; never alter the live label log."""
    output_dir = output_dir or wave_dir / "checkpoint_200_v1"
    manifest_path = output_dir / "checkpoint_manifest.json"
    design_path = wave_dir / "wave_design.parquet"
    wave_manifest_path = wave_dir / "wave_manifest.json"
    labels_path = wave_dir / "human_labels.jsonl"
    codebook_path = root / "config" / "response_validity_codebook_v2.json"
    for path in [design_path, wave_manifest_path, labels_path, codebook_path]:
        if not path.exists():
            raise FileNotFoundError(path)

    # An existing freeze is authoritative.  Later live submissions cannot
    # change it and are deliberately not opened on this path.
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("wave_design_sha256") != sha_file(design_path):
            raise RuntimeError("checkpoint points to a different wave design")
        if existing.get("codebook_sha256") != sha_file(codebook_path):
            raise RuntimeError("checkpoint points to a different codebook")
        return _verify_frozen_artifacts(output_dir, existing)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested checkpoint directory: {output_dir}")

    wave_manifest = json.loads(wave_manifest_path.read_text(encoding="utf-8"))
    expected_design = wave_manifest.get("artifact_sha256", {}).get("wave_design.parquet")
    if expected_design and sha_file(design_path) != expected_design:
        raise RuntimeError("wave design differs from its manifest")
    design = pd.read_parquet(design_path).sort_values("review_order")
    checkpoint_design = design.loc[design.review_order.le(CHECKPOINT_N)].copy()
    if (
        len(checkpoint_design) != CHECKPOINT_N
        or checkpoint_design.review_id.duplicated().any()
        or checkpoint_design.review_order.astype(int).tolist() != list(range(1, CHECKPOINT_N + 1))
    ):
        raise ValueError("checkpoint design is not exactly review orders 1--200")

    codebook = json.loads(codebook_path.read_text(encoding="utf-8"))
    live = _read_jsonl(labels_path)
    checkpoint_ids = set(checkpoint_design.review_id.astype(str))
    selected = [row for row in live if str(row.get("review_id")) in checkpoint_ids]
    keys = [(str(row.get("coder_id")), str(row.get("review_id"))) for row in selected]
    if len(selected) != CHECKPOINT_N or len(set(keys)) != CHECKPOINT_N:
        raise ValueError(
            f"checkpoint coding is incomplete or duplicated: {len(selected)}/{CHECKPOINT_N}"
        )
    if len({row.get("coder_id") for row in selected}) != 1:
        raise ValueError("checkpoint requires one stable coder ID")
    for row in selected:
        if row.get("status") != "submitted":
            raise ValueError(f"non-submitted checkpoint record: {row.get('review_id')}")
        if row.get("codebook_version") != codebook["codebook_version"]:
            raise ValueError(f"codebook mismatch: {row.get('review_id')}")
        clean = {key: value for key, value in row.items() if key != "_live_line"}
        errors = validate_human_label(clean, codebook)
        if clean.get("primary_class") == "genuine_refusal" and not str(
            clean.get("evidence_span", "")
        ).strip():
            errors.append("genuine_refusal lacks evidence span")
        if clean.get("primary_class") == "ambiguous" and not str(clean.get("note", "")).strip():
            errors.append("ambiguous lacks explanation")
        if errors:
            raise ValueError(f"invalid checkpoint record {row.get('review_id')}: {errors}")

    labels = pd.DataFrame(selected).drop(columns=["_live_line"])
    design_extra = [column for column in checkpoint_design.columns if column not in labels.columns]
    joined = labels.merge(
        checkpoint_design[["review_id", *design_extra]], on="review_id", validate="one_to_one"
    ).sort_values("review_order")
    if len(joined) != CHECKPOINT_N or joined.review_order.isna().any():
        raise ValueError("checkpoint labels do not join one-to-one to the design")

    output_dir.mkdir(parents=True, exist_ok=False)
    labels_jsonl = output_dir / "checkpoint_labels.jsonl"
    labels_parquet = output_dir / "checkpoint_labels.parquet"
    design_out = output_dir / "checkpoint_design.parquet"
    counts_path = output_dir / "checkpoint_class_counts.csv"
    records = joined.sort_values("review_id").to_dict("records")
    _write_jsonl(labels_jsonl, records)
    joined.to_parquet(labels_parquet, index=False)
    checkpoint_design.to_parquet(design_out, index=False)
    (
        joined.groupby(["analysis_split", "primary_class"], observed=True)
        .size().rename("n").reset_index().sort_values(["analysis_split", "primary_class"])
        .to_csv(counts_path, index=False)
    )
    artifacts = [labels_jsonl, labels_parquet, design_out, counts_path]
    class_counts = joined.primary_class.value_counts().sort_index().astype(int).to_dict()
    split_counts = joined.analysis_split.value_counts().sort_index().astype(int).to_dict()
    manifest = {
        "freeze_version": CHECKPOINT_VERSION,
        "created_at": _now(),
        "status": "complete_first_200; rows_201_400_held_as_unreviewed_reserve",
        "protocol_amendment": (
            "After coherent pivot was downgraded to diagnostic status, stop at review order "
            "200 for protected surrogate evaluation; use the original 300 for DSL residual correction."
        ),
        "membership_rule": "frozen wave review_order <= 200",
        "review_order_was_randomized_before_human_labels": True,
        "use_for_population_prevalence": False,
        "use_for_dsl_residual_correction": False,
        "allowed_uses": ["surrogate development", "protected surrogate evaluation"],
        "n_labels": len(joined),
        "analysis_split_counts": split_counts,
        "primary_class_counts": class_counts,
        "n_languages": int(joined.prompt_language.nunique()),
        "n_source_models": int(joined.model.nunique()),
        "coder_id_sha256": sha_text(str(joined.coder_id.iloc[0])),
        "first_submission_at": str(joined.submitted_at.min()),
        "last_submission_at": str(joined.submitted_at.max()),
        "codebook_version": codebook["codebook_version"],
        "codebook_sha256": sha_file(codebook_path),
        "wave_design_sha256": sha_file(design_path),
        "wave_manifest_sha256": sha_file(wave_manifest_path),
        "live_label_log_sha256_at_freeze": sha_file(labels_path),
        "live_records_at_freeze": len(live),
        "canonical_checkpoint_sha256": _canonical_hash(records),
        "artifact_sha256": {path.name: sha_file(path) for path in artifacts},
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _load_stage_a_system_prompts(stage_a_dir: Path) -> tuple[dict[str, str], pd.DataFrame]:
    manifest = json.loads((stage_a_dir / "bakeoff_manifest.json").read_text(encoding="utf-8"))
    request_path = stage_a_dir / "model_neutral_requests.jsonl"
    config_path = stage_a_dir / "prompt_configurations.csv"
    if sha_file(request_path) != manifest["artifact_sha256"][request_path.name]:
        raise RuntimeError("Stage A requests differ from their manifest")
    requests = _read_jsonl(request_path)
    configs = pd.read_csv(config_path).set_index("config_id", drop=False)
    prompts: dict[str, str] = {}
    for config_id in ADVANCING_CONFIGS:
        values = {
            row["messages"][0]["content"]
            for row in requests if row.get("config_id") == config_id
        }
        if len(values) != 1 or config_id not in configs.index:
            raise ValueError(f"Stage A configuration is not uniquely recoverable: {config_id}")
        prompt = next(iter(values))
        if sha_text(prompt) != configs.at[config_id, "system_prompt_sha256"]:
            raise RuntimeError(f"Stage A system prompt hash mismatch: {config_id}")
        prompts[config_id] = prompt
    return prompts, configs.loc[list(ADVANCING_CONFIGS)].reset_index(drop=True)


def build_protected_surrogate_evaluation(
    root: Path,
    wave_dir: Path,
    output_dir: Path | None = None,
) -> dict:
    """Freeze 232 Luna requests over the 116 protected evaluation responses."""
    checkpoint_dir = wave_dir / "checkpoint_200_v1"
    checkpoint_manifest = freeze_enrichment_checkpoint_200(root, wave_dir, checkpoint_dir)
    stage_a_dir = wave_dir.parent / "surrogate_bakeoff_v1"
    pricing_path = root / "config" / "surrogate_protected_evaluation_v1.json"
    output_dir = output_dir or checkpoint_dir / "surrogate_evaluation_v1"
    manifest_path = output_dir / "evaluation_manifest.json"
    required = {
        "checkpoint_manifest": checkpoint_dir / "checkpoint_manifest.json",
        "checkpoint_labels": checkpoint_dir / "checkpoint_labels.parquet",
        "stage_a_manifest": stage_a_dir / "bakeoff_manifest.json",
        "stage_a_requests": stage_a_dir / "model_neutral_requests.jsonl",
        "stage_a_configs": stage_a_dir / "prompt_configurations.csv",
        "pricing_config": pricing_path,
    }
    for path in required.values():
        if not path.exists():
            raise FileNotFoundError(path)
    input_sha = {name: sha_file(path) for name, path in required.items()}
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("input_sha256") != input_sha:
            raise RuntimeError("protected evaluation uses different frozen inputs")
        return _verify_frozen_artifacts(output_dir, existing)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested evaluation directory: {output_dir}")

    frame = pd.read_parquet(required["checkpoint_labels"])
    if len(frame) != CHECKPOINT_N or frame.review_id.duplicated().any():
        raise ValueError("protected evaluation requires the immutable 200-row checkpoint")
    development = frame.loc[frame.analysis_split.eq("development")].copy()
    evaluation = frame.loc[frame.analysis_split.eq("evaluation")].copy()
    if len(development) != EXPECTED_DEVELOPMENT or len(evaluation) != EXPECTED_EVALUATION:
        raise ValueError("checkpoint development/evaluation counts changed")
    if set(development.prompt_id) & set(evaluation.prompt_id):
        raise ValueError("prompt leakage across checkpoint arms")

    prompts, configs = _load_stage_a_system_prompts(stage_a_dir)
    schema = _response_schema()
    logical: list[dict] = []
    for config_id in ADVANCING_CONFIGS:
        for _, row in evaluation.sort_values("review_id").iterrows():
            request = {
                "config_id": config_id,
                "evaluation_review_id": str(row.review_id),
                "messages": [
                    {"role": "system", "content": prompts[config_id]},
                    {"role": "user", "content": _format_query(row)},
                ],
                "response_schema": schema,
                "temperature": 0,
                "reasoning": "disabled_or_excluded",
            }
            request["request_id"] = hashlib.sha256(
                json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()[:24]
            logical.append(request)
    if len(logical) != EXPECTED_REQUESTS or len({row["request_id"] for row in logical}) != EXPECTED_REQUESTS:
        raise ValueError("protected logical payload is not 232 unique requests")
    if any("primary_class" in row or "gold" in row for row in logical):
        raise ValueError("human outcome leaked into protected evaluation payload")

    pricing = json.loads(pricing_path.read_text(encoding="utf-8"))
    model = pricing["model"]
    import tiktoken

    encoding = tiktoken.get_encoding(pricing["encoding"])
    schema_tokens = len(encoding.encode(json.dumps(schema, sort_keys=True)))
    provider: list[dict] = []
    token_rows: list[dict] = []
    for request in logical:
        estimated = schema_tokens + len(encoding.encode("\n".join(
            message["content"] for message in request["messages"]
        )))
        frozen = {
            "source_request_id": request["request_id"],
            "evaluation_review_id": request["evaluation_review_id"],
            "config_id": request["config_id"],
            "model_id": model["model_id"],
            "messages": request["messages"],
            "response_schema": request["response_schema"],
            "temperature": 0,
            "max_output_tokens": pricing["max_output_tokens"],
            "reasoning": model["reasoning"],
            "provider": {"only": [model["provider_tag"]], "allow_fallbacks": False},
            "estimated_input_tokens": estimated,
        }
        frozen["evaluation_request_id"] = hashlib.sha256(
            json.dumps(frozen, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
        provider.append(frozen)
        token_rows.append({
            "evaluation_request_id": frozen["evaluation_request_id"],
            "config_id": request["config_id"],
            "estimated_input_tokens": estimated,
            "planning_output_tokens": pricing["planning_output_tokens"],
            "max_output_tokens": pricing["max_output_tokens"],
            "encoding": pricing["encoding"],
            "schema_tokens_included": True,
        })

    output_dir.mkdir(parents=True, exist_ok=False)
    gold_path = output_dir / "evaluation_gold.parquet"
    development_path = output_dir / "development_labels.parquet"
    logical_path = output_dir / "model_neutral_requests.jsonl"
    provider_path = output_dir / "provider_requests.jsonl"
    configs_path = output_dir / "prompt_configurations.csv"
    token_path = output_dir / "token_volume.csv"
    schema_path = output_dir / "response_schema.json"
    summary_path = output_dir / "evaluation_class_counts.csv"
    evaluation.sort_values("review_id").to_parquet(gold_path, index=False)
    development.sort_values("review_id").to_parquet(development_path, index=False)
    _write_jsonl(logical_path, logical)
    _write_jsonl(provider_path, provider)
    configs.to_csv(configs_path, index=False)
    pd.DataFrame(token_rows).to_csv(token_path, index=False)
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    (
        evaluation.groupby(["prompt_language", "primary_class"], observed=True)
        .size().rename("n").reset_index().sort_values(["prompt_language", "primary_class"])
        .to_csv(summary_path, index=False)
    )
    artifacts = [
        gold_path, development_path, logical_path, provider_path, configs_path,
        token_path, schema_path, summary_path,
    ]
    manifest = {
        "evaluation_version": EVALUATION_VERSION,
        "created_at": _now(),
        "status": "frozen_unpaid_unauthorized",
        "purpose": "one protected selection comparison of the two advancing Luna configurations",
        "checkpoint_canonical_sha256": checkpoint_manifest["canonical_checkpoint_sha256"],
        "n_checkpoint": CHECKPOINT_N,
        "n_development": len(development),
        "n_evaluation": len(evaluation),
        "n_evaluation_prompt_groups": int(evaluation.prompt_id.nunique()),
        "configurations": list(ADVANCING_CONFIGS),
        "model": model["model_id"],
        "provider_tag": model["provider_tag"],
        "allow_fallbacks": False,
        "n_logical_requests": len(logical),
        "n_provider_requests": len(provider),
        "evaluation_gold_excluded_from_payload": True,
        "pivot_status": "diagnostic; excluded from the principal selection objective",
        "principal_selection_classes": ["coherent_answer", "genuine_refusal", "capability_failure"],
        "paid_run_authorized": False,
        "network_call_made": False,
        "input_sha256": input_sha,
        "logical_payload_sha256": sha_file(logical_path),
        "provider_payload_sha256": sha_file(provider_path),
        "artifact_sha256": {path.name: sha_file(path) for path in artifacts},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_protected_evaluation_cost(
    root: Path,
    wave_dir: Path,
    output_dir: Path | None = None,
) -> dict:
    """Apply the frozen price snapshot to the exact 232-request payload."""
    output_dir = output_dir or wave_dir / "checkpoint_200_v1" / "surrogate_evaluation_v1"
    manifest_path = output_dir / "evaluation_manifest.json"
    pricing_path = root / "config" / "surrogate_protected_evaluation_v1.json"
    token_path = output_dir / "token_volume.csv"
    costs_path = output_dir / "cost_estimate.csv"
    summary_path = output_dir / "cost_estimate_summary.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha_file(token_path) != manifest["artifact_sha256"][token_path.name]:
        raise RuntimeError("protected-evaluation token volume changed")
    pricing = json.loads(pricing_path.read_text(encoding="utf-8"))
    if sha_file(pricing_path) != manifest["input_sha256"]["pricing_config"]:
        raise RuntimeError("price snapshot changed after payload freeze")
    if summary_path.exists():
        existing = json.loads(summary_path.read_text(encoding="utf-8"))
        if (
            existing.get("provider_payload_sha256") != manifest["provider_payload_sha256"]
            or existing.get("pricing_sha256") != sha_file(pricing_path)
            or not costs_path.exists()
            or existing.get("artifact_sha256", {}).get(costs_path.name) != sha_file(costs_path)
        ):
            raise RuntimeError("existing cost estimate differs from frozen inputs")
        return existing

    tokens = pd.read_csv(token_path)
    model = pricing["model"]
    rows = []
    for config_id, part in tokens.groupby("config_id", sort=True):
        input_tokens = int(part.estimated_input_tokens.sum())
        planning_output = int(part.planning_output_tokens.sum())
        maximum_output = int(part.max_output_tokens.sum())
        rows.append({
            "model_id": model["model_id"],
            "provider_tag": model["provider_tag"],
            "config_id": config_id,
            "requests": len(part),
            "estimated_input_tokens": input_tokens,
            "planning_output_tokens": planning_output,
            "max_output_tokens": maximum_output,
            "planning_cost_usd": (
                input_tokens * model["input_usd_per_million"]
                + planning_output * model["output_usd_per_million"]
            ) / 1_000_000,
            "single_attempt_reserved_cost_usd": (
                input_tokens * model["input_usd_per_million"]
                + maximum_output * model["output_usd_per_million"]
            ) / 1_000_000,
            "pricing_source": model["pricing_source"],
        })
    costs = pd.DataFrame(rows)
    costs.to_csv(costs_path, index=False)
    single_attempt = float(costs.single_attempt_reserved_cost_usd.sum())
    # A rounded ceiling above the single-attempt reservation permits bounded
    # retries while remaining far below the earlier development authorizations.
    suggested_ceiling = max(1.0, round(single_attempt * 2 + 0.25, 2))
    summary = {
        "estimate_version": "human-surrogate-protected-evaluation-cost-v1.0",
        "created_at": _now(),
        "pricing_verified_at": pricing["pricing_verified_at"],
        "pricing_sha256": sha_file(pricing_path),
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "model": model["model_id"],
        "provider_tag": model["provider_tag"],
        "configurations": list(ADVANCING_CONFIGS),
        "calls": int(costs.requests.sum()),
        "planning_cost_usd": float(costs.planning_cost_usd.sum()),
        "single_attempt_reserved_cost_usd": single_attempt,
        "suggested_hard_ceiling_usd": suggested_ceiling,
        "prompt_cache_discount_assumed": False,
        "network_call_made": False,
        "paid_run_authorized": False,
        "artifact_sha256": {costs_path.name: sha_file(costs_path)},
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def record_protected_evaluation_authorization(
    output_dir: Path,
    payload_sha: str,
    model: str,
    provider: str,
    ceiling: float,
    confirmed: bool,
) -> dict:
    """Record the exact user authorization without making a provider call."""
    if not confirmed:
        raise RuntimeError("protected evaluation authorization requires explicit confirmation")
    manifest_path = output_dir / "evaluation_manifest.json"
    payload_path = output_dir / "provider_requests.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    observed = sha_file(payload_path)
    if not (
        payload_sha == observed == manifest.get("provider_payload_sha256")
        == AUTHORIZED_PAYLOAD_SHA256
    ):
        raise ValueError("authorized hash differs from the exact frozen provider payload")
    if (
        model != AUTHORIZED_MODEL
        or provider != AUTHORIZED_PROVIDER
        or float(ceiling) != AUTHORIZED_CEILING
        or manifest.get("model") != AUTHORIZED_MODEL
        or manifest.get("provider_tag") != AUTHORIZED_PROVIDER
        or manifest.get("allow_fallbacks") is not False
        or int(manifest.get("n_provider_requests", -1)) != EXPECTED_REQUESTS
    ):
        raise ValueError("model, provider, request count, fallback policy, or ceiling differs from authorization")
    authorization = {
        "recorded_at": _now(),
        "user_authorized": True,
        "purpose": "protected zero-shot versus 22-shot surrogate evaluation on 116 human-coded responses",
        "provider_payload_sha256": payload_sha,
        "model": model,
        "provider": "OpenRouter",
        "provider_allowlist": [provider],
        "configurations": list(ADVANCING_CONFIGS),
        "n_evaluation_responses": EXPECTED_EVALUATION,
        "n_requests": EXPECTED_REQUESTS,
        "reasoning_enabled": False,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["protected_evaluation_authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_yet_complete"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def _reported_cost(usage: dict, input_price: float, output_price: float) -> float:
    # OpenRouter reports ``cost: 0`` for BYOK traffic but supplies the actual
    # upstream charge separately.  The economic ceiling must apply to that
    # upstream charge, not merely to OpenRouter's own zero-dollar line item.
    details = usage.get("cost_details") or {}
    if usage.get("is_byok") and details.get("upstream_inference_cost") is not None:
        return float(details["upstream_inference_cost"])
    if usage.get("cost") is not None:
        return float(usage["cost"])
    return (
        float(usage.get("prompt_tokens", 0)) * input_price
        + float(usage.get("completion_tokens", 0)) * output_price
    ) / 1_000_000


def _protected_provider_call(client, request: dict, pricing: dict) -> dict:
    started = time.time()
    response = client.chat.completions.create(
        model=request["model_id"],
        messages=request["messages"],
        temperature=0,
        max_tokens=int(request["max_output_tokens"]),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "response_validity_surrogate_v1",
                "strict": True,
                "schema": request["response_schema"],
            },
        },
        extra_body={
            "reasoning": {"enabled": False, "exclude": True},
            "provider": {"only": [AUTHORIZED_PROVIDER], "allow_fallbacks": False},
        },
        timeout=180,
    )
    usage = response.usage.model_dump() if response.usage else {}
    cost = _reported_cost(
        usage,
        float(pricing["input_usd_per_million"]),
        float(pricing["output_usd_per_million"]),
    )
    try:
        label = _validate_bakeoff_label(json.loads(response.choices[0].message.content))
        status, error_type, error = "complete", None, None
    except Exception as exc:
        label = {}
        status, error_type, error = "error", type(exc).__name__, str(exc)[:1000]
    return {
        "evaluation_request_id": request["evaluation_request_id"],
        "request_id": request["source_request_id"],
        "evaluation_review_id": request["evaluation_review_id"],
        "config_id": request["config_id"],
        "model_id": request["model_id"],
        **label,
        "status": status,
        "error_type": error_type,
        "error": error,
        "provider_response_id": response.id,
        "provider_model": response.model,
        "usage": usage,
        "incremental_provider_cost": cost,
        "elapsed_seconds": time.time() - started,
        "created_at": _now(),
    }


def run_protected_surrogate_evaluation(
    root: Path,
    output_dir: Path,
    workers: int,
    ceiling: float,
    authorized: bool,
) -> dict:
    """Run the exact authorized 232-request comparison resumably."""
    if not authorized or float(ceiling) != AUTHORIZED_CEILING:
        raise RuntimeError("protected evaluation requires the exact paid authorization and $2.22 ceiling")
    manifest_path = output_dir / "evaluation_manifest.json"
    payload_path = output_dir / "provider_requests.jsonl"
    pricing_path = root / "config" / "surrogate_protected_evaluation_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    auth = manifest.get("protected_evaluation_authorization", {})
    payload_sha = sha_file(payload_path)
    if not (
        auth.get("user_authorized") is True
        and auth.get("provider_payload_sha256") == payload_sha == AUTHORIZED_PAYLOAD_SHA256
        and auth.get("model") == AUTHORIZED_MODEL
        and auth.get("provider_allowlist") == [AUTHORIZED_PROVIDER]
        and auth.get("reasoning_enabled") is False
        and auth.get("allow_fallbacks") is False
        and float(auth.get("cost_ceiling_usd", -1)) == float(ceiling)
        and int(auth.get("n_requests", -1)) == EXPECTED_REQUESTS
    ):
        raise RuntimeError("manifest lacks the exact protected-evaluation authorization")
    if sha_file(pricing_path) != manifest["input_sha256"]["pricing_config"]:
        raise RuntimeError("pricing snapshot changed after the payload freeze")
    pricing = json.loads(pricing_path.read_text(encoding="utf-8"))
    model_price = pricing["model"]
    requests = [
        {key: value for key, value in row.items() if key != "_live_line"}
        for row in _read_jsonl(payload_path)
    ]
    if (
        len(requests) != EXPECTED_REQUESTS
        or len({row["evaluation_request_id"] for row in requests}) != EXPECTED_REQUESTS
        or {row["config_id"] for row in requests} != set(ADVANCING_CONFIGS)
        or any(row["model_id"] != AUTHORIZED_MODEL for row in requests)
        or any(row["provider"] != {"only": [AUTHORIZED_PROVIDER], "allow_fallbacks": False} for row in requests)
    ):
        raise ValueError("provider payload no longer matches the authorized design")

    lock_handle = (output_dir / ".protected_evaluation_run.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_handle.close()
        raise RuntimeError("another protected-evaluation process holds the run lock") from exc
    try:
        scripts = root / "scripts"
        if str(scripts) not in os.sys.path:
            os.sys.path.insert(0, str(scripts))
        from env_utils import get_openrouter_client
        client = get_openrouter_client()
        raw_path = output_dir / "protected_evaluation_raw.jsonl"
        existing = [
            {key: value for key, value in row.items() if key != "_live_line"}
            for row in _read_jsonl(raw_path)
        ] if raw_path.exists() else []
        completed = {
            row["evaluation_request_id"]: row
            for row in existing if row.get("status") == "complete"
        }
        attempts: dict[str, int] = {}
        for row in existing:
            key = row.get("evaluation_request_id")
            attempts[key] = attempts.get(key, 0) + 1
        actual_cost = sum(
            _reported_cost(
                row.get("usage") or {},
                float(model_price["input_usd_per_million"]),
                float(model_price["output_usd_per_million"]),
            )
            for row in existing
        )
        if actual_cost >= ceiling:
            raise RuntimeError("existing protected-evaluation cost reaches the authorized ceiling")
        maximum_attempts = int(pricing["max_attempts"])
        queue = [
            row for row in requests
            if row["evaluation_request_id"] not in completed
            and attempts.get(row["evaluation_request_id"], 0) < maximum_attempts
        ]
        write_lock = threading.Lock()

        def reservation(request: dict) -> float:
            return (
                int(request["estimated_input_tokens"]) * float(model_price["input_usd_per_million"])
                + int(request["max_output_tokens"]) * float(model_price["output_usd_per_million"])
            ) / 1_000_000

        def append(record: dict) -> None:
            with write_lock, raw_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())

        futures = {}
        reserved = 0.0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while queue or futures:
                while queue and len(futures) < workers:
                    request = queue.pop(0)
                    hold = reservation(request)
                    if actual_cost + reserved + hold > ceiling:
                        raise RuntimeError("in-flight reservation would cross the $2.22 ceiling")
                    reserved += hold
                    futures[pool.submit(_protected_provider_call, client, request, model_price)] = (request, hold)
                if not futures:
                    break
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    request, hold = futures.pop(future)
                    reserved -= hold
                    try:
                        record = future.result()
                    except Exception as exc:
                        record = {
                            "evaluation_request_id": request["evaluation_request_id"],
                            "request_id": request["source_request_id"],
                            "evaluation_review_id": request["evaluation_review_id"],
                            "config_id": request["config_id"],
                            "model_id": request["model_id"],
                            "status": "error",
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:1000],
                            "incremental_provider_cost": 0.0,
                            "created_at": _now(),
                        }
                    append(record)
                    actual_cost += _reported_cost(
                        record.get("usage") or {},
                        float(model_price["input_usd_per_million"]),
                        float(model_price["output_usd_per_million"]),
                    )
                    key = request["evaluation_request_id"]
                    attempts[key] = attempts.get(key, 0) + 1
                    if actual_cost > ceiling:
                        raise RuntimeError("provider-reported cost crossed the authorized ceiling")
                    if record["status"] == "complete":
                        completed[key] = record
                    elif attempts[key] < maximum_attempts:
                        queue.append(request)
        missing = [row["evaluation_request_id"] for row in requests if row["evaluation_request_id"] not in completed]
        if missing:
            raise RuntimeError(f"protected evaluation incomplete after retries: {len(missing)}")
        results_path = output_dir / "protected_evaluation_results.jsonl"
        _write_jsonl(results_path, [completed[row["evaluation_request_id"]] for row in requests])
        summary = {
            "run_version": "human-surrogate-protected-evaluation-run-v1.0",
            "completed_at": _now(),
            "model": AUTHORIZED_MODEL,
            "provider_allowlist": [AUTHORIZED_PROVIDER],
            "reasoning_enabled": False,
            "allow_fallbacks": False,
            "provider_payload_sha256": payload_sha,
            "n_completed": len(completed),
            "raw_records": len(_read_jsonl(raw_path)),
            "economic_inference_cost_usd": actual_cost,
            "openrouter_reported_cost_usd": sum(
                float((row.get("usage") or {}).get("cost") or 0)
                for row in _read_jsonl(raw_path)
            ),
            "byok_upstream_cost_used_for_ceiling": True,
            "authorized_ceiling_usd": ceiling,
            "assembled_sha256": sha_file(results_path),
        }
        (output_dir / "protected_evaluation_run_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        manifest["network_call_made"] = True
        prior_score = manifest.get("protected_evaluation_score", {})
        manifest["status"] = (
            "completed_scored"
            if prior_score.get("results_sha256") == summary["assembled_sha256"]
            else "completed_not_yet_scored"
        )
        manifest["protected_evaluation_run"] = summary
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return summary
    finally:
        lock_handle.close()


def score_protected_surrogate_evaluation(output_dir: Path) -> dict:
    """Open the protected gold only after completion and apply the frozen scorer."""
    manifest_path = output_dir / "evaluation_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results_path = output_dir / "protected_evaluation_results.jsonl"
    run_summary_path = output_dir / "protected_evaluation_run_summary.json"
    run_summary = json.loads(run_summary_path.read_text(encoding="utf-8"))
    if (
        int(run_summary.get("n_completed", -1)) != EXPECTED_REQUESTS
        or sha_file(results_path) != run_summary.get("assembled_sha256")
        or run_summary.get("provider_payload_sha256") != AUTHORIZED_PAYLOAD_SHA256
    ):
        raise RuntimeError("protected results are incomplete or differ from the run summary")
    scoring_dir = output_dir / "scoring_v1"
    scoring_dir.mkdir(exist_ok=True)
    gold_source = output_dir / "evaluation_gold.parquet"
    gold_scoring = scoring_dir / "evaluation_gold.parquet"
    if not gold_scoring.exists():
        import shutil
        shutil.copy2(gold_source, gold_scoring)
    elif sha_file(gold_scoring) != sha_file(gold_source):
        raise RuntimeError("scoring copy of protected gold changed")
    scorer_manifest = {
        "bakeoff_version": "protected-surrogate-score-v1.0",
        "artifact_sha256": {"evaluation_gold.parquet": sha_file(gold_scoring)},
        "parent_results_sha256": sha_file(results_path),
    }
    (scoring_dir / "bakeoff_manifest.json").write_text(
        json.dumps(scorer_manifest, indent=2), encoding="utf-8"
    )
    metrics = score_surrogate_results(scoring_dir, results_path)
    key_metrics = [
        "primary_accuracy", "macro_f1",
        "genuine_refusal_binary_precision", "genuine_refusal_binary_recall",
        "genuine_refusal_binary_f1", "capability_failure_binary_precision",
        "capability_failure_binary_recall", "capability_failure_binary_f1",
    ]
    comparison = metrics.loc[metrics.metric.isin(key_metrics)].copy()
    comparison_path = scoring_dir / "protected_key_metrics.csv"
    comparison.to_csv(comparison_path, index=False)
    objective = comparison.loc[comparison.metric.isin([
        "genuine_refusal_binary_f1", "capability_failure_binary_f1", "primary_accuracy",
    ])].pivot(index="config_id", columns="metric", values="value")
    objective["selection_score"] = objective[[
        "genuine_refusal_binary_f1", "capability_failure_binary_f1", "primary_accuracy",
    ]].mean(axis=1)
    ranked = objective.sort_values(
        ["selection_score", "genuine_refusal_binary_f1", "capability_failure_binary_f1", "primary_accuracy"],
        ascending=False,
    ).reset_index()
    ranked_path = scoring_dir / "configuration_ranking.csv"
    ranked.to_csv(ranked_path, index=False)
    summary = {
        "score_version": "human-surrogate-protected-evaluation-score-v1.0",
        "scored_at": _now(),
        "n_results": EXPECTED_REQUESTS,
        "n_evaluation_responses": EXPECTED_EVALUATION,
        "pivot_status": "diagnostic; excluded from selection score",
        "selection_rule": "mean of genuine-refusal F1, capability-failure F1, and primary-class accuracy; ties broken in that order",
        "selected_config_id": str(ranked.iloc[0].config_id),
        "results_sha256": sha_file(results_path),
        "gold_sha256": sha_file(gold_source),
        "artifact_sha256": {
            path.name: sha_file(path)
            for path in [
                scoring_dir / "bakeoff_metrics.csv",
                scoring_dir / "bakeoff_subgroup_metrics.csv",
                scoring_dir / "bakeoff_primary_confusion.csv",
                scoring_dir / "bakeoff_error_inventory.csv",
                comparison_path,
                ranked_path,
            ]
        },
    }
    summary_path = scoring_dir / "score_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest["status"] = "completed_scored"
    manifest["protected_evaluation_score"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary
