"""Freeze the approved external validity sample and blinded model payloads.

This module performs local deterministic work only.  It draws the two approved
probability samples with independent random streams, retains exact first-order
inclusion probabilities, and creates separate unpaid Luna and Sol payloads.
It contains no provider client and cannot make a network call.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import tiktoken

from .enrichment_design_v2 import ROUTING_STRATA, build_routing_population
from .external_audit_design import GOLD, PLANS, union_probability
from .human_pilot import KEY, sha_file
from .luna_v23_repair import _schema, _system, _user


DEFAULT_DIR = "annotations/response_validity_human_v2/external_audit_v1"
PLANNING_DIR = (
    "annotations/response_validity_human_v2/external_audit_planning_v1"
)
CODEBOOK = "config/response_validity_decomposed_v2_3.json"
SEED = 20260827
PLAN = "audit_1200"
PROVIDER = "openai"
MAX_OUTPUT_TOKENS = 500
PLANNING_OUTPUT_TOKENS = 200
MODELS = {
    "luna": {
        "model_id": "openai/gpt-5.6-luna",
        "input_price": 0.20,
        "output_price": 1.20,
        "pricing_source": "https://openrouter.ai/openai/gpt-5.6-luna-20260709",
    },
    "sol": {
        "model_id": "openai/gpt-5.6-sol",
        "input_price": 2.00,
        "output_price": 10.00,
        "pricing_source": "https://openrouter.ai/openai/gpt-5.6-sol-20260709",
    },
}


def _input_hashes(root: Path) -> dict[str, str]:
    """Bind the draw to every file used to recreate routing or payload text."""
    return {
        "aggregate_design_manifest": sha_file(
            root / PLANNING_DIR / "design_manifest.json"
        ),
        "harmonized_gold": sha_file(root / GOLD),
        "codebook": sha_file(root / CODEBOOK),
        "pilot_manifest": sha_file(
            root / "annotations/response_validity_human_v2/pilot_manifest.json"
        ),
        "wall_to_wall_features": sha_file(
            root / "annotations/response_validity_dsl_v1_1/wall_to_wall_features.parquet"
        ),
        "dsl_pseudo_outcomes": sha_file(
            root / "annotations/response_validity_dsl_v1_1/dsl_pseudo_outcomes.parquet"
        ),
        "pilot_design": sha_file(
            root / "annotations/response_validity_human_v2/pilot_design.parquet"
        ),
        "complete_language_base_labels": sha_file(
            root / "annotations/response_validity_human_v2/"
            "base_freeze_v3_complete_language_review/base_labels.parquet"
        ),
        "stage_b_disagreements": sha_file(
            root / "annotations/response_validity_human_v2/"
            "surrogate_bakeoff_stage_b_v1/stage_b_row_disagreements.csv"
        ),
        "sol_reference_labels": sha_file(
            root / "annotations/response_validity_dsl_v1/sol_reference_labels.jsonl"
        ),
        "sol_augmentation_labels": sha_file(
            root / "annotations/response_validity_dsl_v1_1/sol_augmentation_labels.jsonl"
        ),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha_object(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            )


def _verify_existing(root: Path, output_dir: Path) -> dict | None:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_inputs = _input_hashes(root)
    if manifest.get("input_sha256") != expected_inputs:
        raise ValueError("frozen external audit no longer matches its inputs")
    for name, expected in manifest.get("artifact_sha256", {}).items():
        path = output_dir / name
        if not path.exists() or sha_file(path) != expected:
            raise ValueError(f"frozen external audit artifact changed: {name}")
    if manifest.get("paid_run_authorized") is not False:
        raise ValueError("external audit unexpectedly records paid authorization")
    if manifest.get("network_call_made") is not False:
        raise ValueError("external audit unexpectedly records a network call")
    approval = manifest.get("design_approval", {})
    if approval.get("scope") != "local_draw_and_unpaid_payload_freeze_only":
        raise ValueError("external audit lacks the approved local-freeze scope")
    return manifest


def _draw_indices(
    frame: pd.DataFrame, group_columns: list[str], draws: dict | int,
    rng: np.random.Generator,
) -> set[int]:
    selected: set[int] = set()
    grouped = frame.groupby(group_columns, sort=True, dropna=False)
    for key, part in grouped:
        lookup = key if len(group_columns) > 1 else (
            key[0] if isinstance(key, tuple) else key
        )
        n = int(draws if isinstance(draws, int) else draws[lookup])
        candidates = np.sort(part.index.to_numpy(int))
        if len(candidates) < n:
            raise ValueError(f"sampling cell {key!r} cannot support draw {n}")
        selected.update(map(int, rng.choice(candidates, size=n, replace=False)))
    return selected


def _approved_external_population(root: Path) -> pd.DataFrame:
    full, _, _ = build_routing_population(
        root, root / "annotations" / "response_validity_human_v2", 20260823
    )
    gold = pd.read_parquet(root / GOLD)
    reviewed = set(map(tuple, gold[KEY].itertuples(index=False, name=None)))
    external = full.loc[
        ~full[KEY].apply(tuple, axis=1).isin(reviewed)
    ].copy()
    external = external.sort_values(KEY, kind="mergesort").reset_index(drop=True)
    if len(full) != 137_186 or len(external) != 136_486:
        raise ValueError("approved audit population must exclude exactly 700 rows")
    if external.duplicated(KEY).any():
        raise ValueError("approved audit population has duplicate response keys")
    required = {
        *KEY, "routing_stratum", "prompt_text", "prompt_text_en",
        "response_text",
    }
    if missing := required - set(external.columns):
        raise ValueError(f"audit population lacks columns: {sorted(missing)}")
    if external[list(required)].isna().any().any():
        raise ValueError("audit payload fields contain missing values")
    return external


def _sample(root: Path) -> tuple[pd.DataFrame, dict]:
    external = _approved_external_population(root)
    spec = PLANS[PLAN]
    risk_draw = dict(zip(ROUTING_STRATA, spec["risk_draw"]))
    streams = np.random.SeedSequence(SEED).spawn(2)
    cell_ids = _draw_indices(
        external, ["model", "prompt_language"],
        int(spec["per_model_language"]), np.random.default_rng(streams[0]),
    )
    risk_ids = _draw_indices(
        external, ["routing_stratum"], risk_draw,
        np.random.default_rng(streams[1]),
    )
    union_ids = sorted(cell_ids | risk_ids)
    sample = external.loc[union_ids].copy()
    sample["selected_by_cell_component"] = sample.index.isin(cell_ids)
    sample["selected_by_risk_component"] = sample.index.isin(risk_ids)

    cell_n = external.groupby(["model", "prompt_language"]).size()
    routing_n = external.groupby("routing_stratum").size()
    sample["cell_population_n"] = [
        int(cell_n.loc[(model, language)])
        for model, language in zip(sample.model, sample.prompt_language)
    ]
    sample["cell_component_draw_n"] = int(spec["per_model_language"])
    sample["cell_component_probability"] = (
        sample.cell_component_draw_n / sample.cell_population_n
    )
    sample["routing_population_n"] = sample.routing_stratum.map(routing_n).astype(int)
    sample["risk_component_draw_n"] = sample.routing_stratum.map(risk_draw).astype(int)
    sample["risk_component_probability"] = (
        sample.risk_component_draw_n / sample.routing_population_n
    )
    sample["phase1_inclusion_probability"] = union_probability(
        sample.cell_component_probability.to_numpy(float),
        sample.risk_component_probability.to_numpy(float),
    )
    sample["phase1_sampling_weight"] = 1 / sample.phase1_inclusion_probability
    sample["audit_response_id"] = [
        _sha_object({"key": list(key), "version": "external-audit-v1"})[:24]
        for key in sample[KEY].itertuples(index=False, name=None)
    ]
    sample = sample.sort_values("audit_response_id", kind="mergesort").reset_index(drop=True)
    if sample.audit_response_id.duplicated().any():
        raise ValueError("external audit identifiers are not unique")
    if len(cell_ids) != 550 or len(risk_ids) != 650:
        raise ValueError("external audit component sizes differ from approval")
    if not sample.phase1_inclusion_probability.between(0, 1, inclusive="right").all():
        raise ValueError("invalid external audit inclusion probability")
    facts = {
        "external_population_n": len(external),
        "cell_component_draw_n": len(cell_ids),
        "risk_component_draw_n": len(risk_ids),
        "component_overlap_n": len(cell_ids & risk_ids),
        "realized_unique_sample_n": len(sample),
        "model_language_cells": int(
            external.groupby(["model", "prompt_language"]).ngroups
        ),
    }
    return sample, facts


def _requests(sample: pd.DataFrame, root: Path) -> tuple[list[dict], dict, str]:
    codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
    system, schema = _system(codebook), _schema()
    encoder = tiktoken.get_encoding("o200k_base")
    neutral: list[dict] = []
    for row in sample.to_dict("records"):
        user = _user(row, "source_response_only")
        logical_id = _sha_object({
            "audit_response_id": row["audit_response_id"],
            "instrument": "response-validity-decomposed-v2.3",
        })[:24]
        neutral.append({
            "logical_request_id": logical_id,
            "audit_response_id": row["audit_response_id"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_schema": schema,
            "estimated_input_tokens": len(encoder.encode(
                system + "\n" + user + "\n" + json.dumps(schema, sort_keys=True)
            )),
        })
    leaked = json.dumps(neutral, ensure_ascii=False)
    forbidden = (
        "engagement_code", "refusal_justification",
        "routing_stratum", "sampling_weight", "inclusion_probability",
        "human_", "dsl_prediction", "sol_",
    )
    for value in forbidden:
        if value in leaked:
            raise RuntimeError(f"blinded external payload leaked: {value}")
    return neutral, schema, system


def _provider_rows(neutral: list[dict], model_key: str) -> list[dict]:
    model = MODELS[model_key]["model_id"]
    return [{
        **row,
        "provider_request_id": _sha_object({
            "logical_request_id": row["logical_request_id"], "model_id": model,
        })[:24],
        "model_id": model,
        "provider": {"only": [PROVIDER], "allow_fallbacks": False},
        "reasoning": {"enabled": False, "exclude": True},
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    } for row in neutral]


def _costs(provider_rows: dict[str, list[dict]]) -> dict:
    by_model = {}
    for key, rows in provider_rows.items():
        model = MODELS[key]
        inputs = sum(int(row["estimated_input_tokens"]) for row in rows)
        planning = (
            inputs * model["input_price"] / 1e6
            + len(rows) * PLANNING_OUTPUT_TOKENS * model["output_price"] / 1e6
        )
        single_max = (
            inputs * model["input_price"] / 1e6
            + len(rows) * MAX_OUTPUT_TOKENS * model["output_price"] / 1e6
        )
        by_model[key] = {
            "model_id": model["model_id"],
            "provider_tag": PROVIDER,
            "requests": len(rows),
            "estimated_input_tokens": inputs,
            "planning_output_tokens": len(rows) * PLANNING_OUTPUT_TOKENS,
            "maximum_output_tokens_single_attempt": len(rows) * MAX_OUTPUT_TOKENS,
            "price_usd_per_million": {
                "input": model["input_price"], "output": model["output_price"],
            },
            "pricing_source": model["pricing_source"],
            "planning_cost_usd": planning,
            "single_attempt_reserved_cost_usd": single_max,
        }
    planning_total = sum(item["planning_cost_usd"] for item in by_model.values())
    reserved_total = sum(
        item["single_attempt_reserved_cost_usd"] for item in by_model.values()
    )
    return {
        "version": "external-audit-cost-v1",
        "created_at": _now(),
        "pricing_verified_at": "2026-08-27",
        "discount_assumption": (
            "Sol uses the OpenRouter 50%-discounted $2/$10 list price; "
            "no prompt-cache saving is assumed"
        ),
        "by_model": by_model,
        "planning_cost_usd": planning_total,
        "single_attempt_reserved_cost_usd": reserved_total,
        "suggested_combined_hard_ceiling_usd": max(
            15.0, math.ceil(max(planning_total * 1.5, reserved_total * 1.25))
        ),
        "paid_run_authorized": False,
        "network_call_made": False,
    }


def freeze_external_audit(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Draw and hash the approved sample without authorizing transmission."""
    output_dir = output_dir or root / DEFAULT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    if existing := _verify_existing(root, output_dir):
        return existing
    if any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested audit directory: {output_dir}")

    planning = json.loads(
        (root / PLANNING_DIR / "design_manifest.json").read_text(encoding="utf-8")
    )
    if planning.get("recommended_plan") != PLAN:
        raise ValueError("aggregate recommendation no longer matches approved plan")
    if planning.get("sample_drawn") is not False:
        raise ValueError("aggregate planning manifest has unsafe draw state")

    sample, facts = _sample(root)
    neutral, schema, system = _requests(sample, root)
    providers = {key: _provider_rows(neutral, key) for key in MODELS}

    design_columns = [
        "audit_response_id", *KEY, "issue_id", "routing_stratum",
        "selected_by_cell_component", "selected_by_risk_component",
        "cell_population_n", "cell_component_draw_n",
        "cell_component_probability", "routing_population_n",
        "risk_component_draw_n", "risk_component_probability",
        "phase1_inclusion_probability", "phase1_sampling_weight",
    ]
    packet_columns = [
        "audit_response_id", "prompt_language", "prompt_text_en",
        "prompt_text", "response_text",
    ]
    sample[design_columns].to_parquet(output_dir / "sample_design.parquet", index=False)
    sample[packet_columns].to_parquet(output_dir / "blinded_review_packet.parquet", index=False)
    _write_jsonl(output_dir / "model_neutral_requests.jsonl", neutral)
    for key, rows in providers.items():
        _write_jsonl(output_dir / f"{key}_provider_requests.jsonl", rows)
    (output_dir / "prompt.txt").write_text(system, encoding="utf-8")
    (output_dir / "response_schema.json").write_text(
        json.dumps(schema, indent=2), encoding="utf-8"
    )
    costs = _costs(providers)
    for key in MODELS:
        costs["by_model"][key]["provider_payload_sha256"] = sha_file(
            output_dir / f"{key}_provider_requests.jsonl"
        )
    (output_dir / "cost_estimate.json").write_text(
        json.dumps(costs, indent=2), encoding="utf-8"
    )

    artifacts = (
        "sample_design.parquet", "blinded_review_packet.parquet",
        "model_neutral_requests.jsonl", "luna_provider_requests.jsonl",
        "sol_provider_requests.jsonl", "prompt.txt", "response_schema.json",
        "cost_estimate.json",
    )
    manifest = {
        "version": "external-response-validity-audit-v1",
        "created_at": _now(),
        "status": "sample_and_payloads_frozen_unpaid",
        "approved_plan": PLAN,
        "design_approval": {
            "date": "2026-08-27",
            "user_approval_text": "Okay I approve",
            "scope": "local_draw_and_unpaid_payload_freeze_only",
            "paid_provider_call_authorized": False,
        },
        "seed": SEED,
        **facts,
        "sampling_design": (
            "union of independent model-language SRSWOR and routing-stratum "
            "SRSWOR; pi=1-(1-p_cell)(1-p_risk)"
        ),
        "judging_instrument": "response-validity-decomposed-v2.3",
        "input_mode": "source_response_only",
        "blinding": [
            "source model", "prior human labels", "prior machine labels",
            "original engagement code", "routing stratum", "sampling reason",
            "other external judge result",
        ],
        "model_ids": {key: value["model_id"] for key, value in MODELS.items()},
        "provider_tag": PROVIDER,
        "allow_fallbacks": False,
        "reasoning_disabled": True,
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "input_sha256": _input_hashes(root),
        "artifact_sha256": {
            name: sha_file(output_dir / name) for name in artifacts
        },
        "provider_payload_sha256": {
            key: costs["by_model"][key]["provider_payload_sha256"]
            for key in MODELS
        },
        "cost_estimate": costs,
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest
