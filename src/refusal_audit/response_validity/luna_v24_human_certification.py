"""Freeze the fresh probability sample for human certification of Luna v2.4.

This first stage is deliberately local-only. It excludes every response in the
700-case codebook-development set and the entire 1,197-case external/model-
selection set, draws a new two-component probability sample, and freezes the
exact unpaid Luna v2.4 payload. Human phase-two sampling occurs only after the
Luna labels exist, so its probabilities can be based on the frozen classifier.
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
from .external_audit_freeze import _draw_indices
from .human_pilot import KEY, sha_file
from .luna_v23_repair import _schema, _user
from .luna_v24_evaluation import (
    INPUT_PRICE,
    MAX_ATTEMPTS,
    MAX_OUTPUT_TOKENS,
    MODEL,
    OUTPUT_PRICE,
    PLANNING_OUTPUT_TOKENS,
    PRICING_SOURCE,
    PRICING_VERIFIED_AT,
    PROVIDER,
    _system_v24,
)
from .external_human_validation import _source_hash, _stream_seed


DEFAULT_DIR = (
    "annotations/response_validity_human_v2/"
    "luna_v2_4_human_certification_v1/phase1"
)
OLD_EXTERNAL_DIR = "annotations/response_validity_human_v2/external_audit_v1"
CODEBOOK = "config/response_validity_decomposed_v2_4.json"
SEED = 20260831
PLAN = "audit_1200"
EXPECTED_FULL_N = 137_186
EXPECTED_DEVELOPMENT_N = 700
EXPECTED_OLD_EXTERNAL_N = 1_197
EXPECTED_ELIGIBLE_N = 135_289
PHASE2_DIR = (
    "annotations/response_validity_human_v2/"
    "luna_v2_4_human_certification_v1/human_phase2"
)
TRANSLATION_PROMPT = "config/response_translation_prompt_v1.txt"
PHASE2_SEED = 20260901
PHASE2_PROBABILITIES = {
    "luna_refusal_positive": 1.0,
    "proxy_refusal_negative": 1.0,
    "boundary_negative": 0.5,
    "capability_failure_negative": 0.25,
    "ordinary_negative": 0.1,
}
SOL_REFERENCE_DIR = (
    "annotations/response_validity_human_v2/"
    "luna_v2_4_human_certification_v1/sol_reference"
)


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
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _input_hashes(root: Path) -> dict[str, str]:
    return {
        "harmonized_development_gold": sha_file(root / GOLD),
        "old_external_sample_design": sha_file(
            root / OLD_EXTERNAL_DIR / "sample_design.parquet"
        ),
        "v2_4_codebook": sha_file(root / CODEBOOK),
        "pilot_manifest": sha_file(
            root / "annotations/response_validity_human_v2/pilot_manifest.json"
        ),
        "wall_to_wall_features": sha_file(
            root / "annotations/response_validity_dsl_v1_1/"
            "wall_to_wall_features.parquet"
        ),
        "dsl_pseudo_outcomes": sha_file(
            root / "annotations/response_validity_dsl_v1_1/"
            "dsl_pseudo_outcomes.parquet"
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
            root / "annotations/response_validity_dsl_v1_1/"
            "sol_augmentation_labels.jsonl"
        ),
    }


def _fresh_population(root: Path) -> tuple[pd.DataFrame, dict]:
    full, _, _ = build_routing_population(
        root, root / "annotations/response_validity_human_v2", 20260823
    )
    development = pd.read_parquet(root / GOLD, columns=KEY)
    old_external = pd.read_parquet(
        root / OLD_EXTERNAL_DIR / "sample_design.parquet", columns=KEY
    )
    if len(full) != EXPECTED_FULL_N or full.duplicated(KEY).any():
        raise ValueError("full response population must contain 137,186 unique keys")
    if len(development) != EXPECTED_DEVELOPMENT_N or development.duplicated(KEY).any():
        raise ValueError("development exclusion must contain 700 unique keys")
    if len(old_external) != EXPECTED_OLD_EXTERNAL_N or old_external.duplicated(KEY).any():
        raise ValueError("old external exclusion must contain 1,197 unique keys")
    development_keys = set(map(tuple, development.itertuples(index=False, name=None)))
    external_keys = set(map(tuple, old_external.itertuples(index=False, name=None)))
    if development_keys & external_keys:
        raise ValueError("development and old external exclusions unexpectedly overlap")
    excluded = development_keys | external_keys
    eligible = full.loc[~full[KEY].apply(tuple, axis=1).isin(excluded)].copy()
    eligible = eligible.sort_values(KEY, kind="mergesort").reset_index(drop=True)
    if len(eligible) != EXPECTED_ELIGIBLE_N or eligible.duplicated(KEY).any():
        raise ValueError("fresh certification population must contain 135,289 rows")
    required = {
        *KEY, "routing_stratum", "prompt_text", "prompt_text_en", "response_text",
    }
    if missing := required - set(eligible.columns):
        raise ValueError(f"certification population lacks columns: {sorted(missing)}")
    if eligible[list(required)].isna().any().any():
        raise ValueError("certification payload fields contain missing values")
    return eligible, {
        "full_population_n": len(full),
        "development_exclusion_n": len(development),
        "old_external_exclusion_n": len(old_external),
        "eligible_untouched_population_n": len(eligible),
        "exclusion_overlap_n": 0,
    }


def _sample(root: Path) -> tuple[pd.DataFrame, dict]:
    eligible, population_facts = _fresh_population(root)
    spec = PLANS[PLAN]
    risk_draw = dict(zip(ROUTING_STRATA, spec["risk_draw"]))
    streams = np.random.SeedSequence(SEED).spawn(2)
    cell_ids = _draw_indices(
        eligible,
        ["model", "prompt_language"],
        int(spec["per_model_language"]),
        np.random.default_rng(streams[0]),
    )
    risk_ids = _draw_indices(
        eligible,
        ["routing_stratum"],
        risk_draw,
        np.random.default_rng(streams[1]),
    )
    union_ids = sorted(cell_ids | risk_ids)
    sample = eligible.loc[union_ids].copy()
    sample["selected_by_cell_component"] = sample.index.isin(cell_ids)
    sample["selected_by_risk_component"] = sample.index.isin(risk_ids)

    cell_n = eligible.groupby(["model", "prompt_language"]).size()
    routing_n = eligible.groupby("routing_stratum").size()
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
    sample["certification_response_id"] = [
        _sha_object({"key": list(key), "version": "luna-v2.4-human-cert-v1"})[:24]
        for key in sample[KEY].itertuples(index=False, name=None)
    ]
    sample = sample.sort_values(
        "certification_response_id", kind="mergesort"
    ).reset_index(drop=True)
    if len(cell_ids) != 550 or len(risk_ids) != 650:
        raise ValueError("certification component sizes differ from the frozen design")
    if sample.certification_response_id.duplicated().any():
        raise ValueError("certification response IDs are not unique")
    if not sample.phase1_inclusion_probability.between(0, 1, inclusive="right").all():
        raise ValueError("invalid phase-one inclusion probability")
    facts = {
        **population_facts,
        "cell_component_draw_n": len(cell_ids),
        "risk_component_draw_n": len(risk_ids),
        "component_overlap_n": len(cell_ids & risk_ids),
        "realized_unique_sample_n": len(sample),
        "model_language_cells": int(
            eligible.groupby(["model", "prompt_language"]).ngroups
        ),
    }
    return sample, facts


def prepare_luna_v24_human_certification(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Freeze the fresh sample and exact unpaid Luna payload."""
    output_dir = output_dir or root / DEFAULT_DIR
    manifest_path = output_dir / "manifest.json"
    artifact_names = (
        "sample_design.parquet",
        "blinded_source_packet.parquet",
        "model_neutral_requests.jsonl",
        "provider_requests.jsonl",
        "response_schema.json",
        "prompt.txt",
        "sample_diagnostics.csv",
    )
    input_hashes = _input_hashes(root)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen certification sample no longer matches its inputs")
        for name, expected in manifest.get("artifact_sha256", {}).items():
            if sha_file(output_dir / name) != expected:
                raise ValueError(f"frozen certification artifact changed: {name}")
        return manifest
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested directory: {output_dir}")

    sample, facts = _sample(root)
    codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
    system, schema = _system_v24(codebook), _schema()
    encoder = tiktoken.get_encoding("o200k_base")
    neutral: list[dict] = []
    provider: list[dict] = []
    for row in sample.to_dict("records"):
        user = _user(row, "source_response_only")
        logical_id = _sha_object({
            "certification_response_id": row["certification_response_id"],
            "version": "luna-v2.4-human-certification-v1",
        })[:24]
        base = {
            "logical_request_id": logical_id,
            "certification_response_id": row["certification_response_id"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_schema": schema,
            "estimated_input_tokens": len(encoder.encode(
                system + "\n" + user + "\n" + json.dumps(schema, sort_keys=True)
            )),
        }
        neutral.append(base)
        provider.append({
            **base,
            "provider_request_id": _sha_object({
                "logical_request_id": logical_id, "model_id": MODEL,
            })[:24],
            "model_id": MODEL,
            "provider": {"only": [PROVIDER], "allow_fallbacks": False},
            "reasoning": {"enabled": False, "exclude": True},
            "temperature": 0,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        })
    leaked = json.dumps(provider, ensure_ascii=False)
    for token in (
        "engagement_code", "refusal_justification", "routing_stratum",
        "sampling_weight", "inclusion_probability", "human_", "sol_",
    ):
        if token in leaked:
            raise ValueError(f"blinded certification payload leaked: {token}")

    output_dir.mkdir(parents=True, exist_ok=False)
    design_columns = [
        "certification_response_id", *KEY, "issue_id", "routing_stratum",
        "selected_by_cell_component", "selected_by_risk_component",
        "cell_population_n", "cell_component_draw_n",
        "cell_component_probability", "routing_population_n",
        "risk_component_draw_n", "risk_component_probability",
        "phase1_inclusion_probability", "phase1_sampling_weight",
    ]
    sample[design_columns].to_parquet(output_dir / "sample_design.parquet", index=False)
    sample[[
        "certification_response_id", "prompt_language", "prompt_text_en",
        "prompt_text", "response_text",
    ]].to_parquet(output_dir / "blinded_source_packet.parquet", index=False)
    _write_jsonl(output_dir / "model_neutral_requests.jsonl", neutral)
    _write_jsonl(output_dir / "provider_requests.jsonl", provider)
    (output_dir / "response_schema.json").write_text(
        json.dumps(schema, indent=2), encoding="utf-8"
    )
    (output_dir / "prompt.txt").write_text(system, encoding="utf-8")
    diagnostics = sample.groupby(
        ["routing_stratum", "prompt_language"], observed=True
    ).size().rename("n").reset_index()
    diagnostics.to_csv(output_dir / "sample_diagnostics.csv", index=False)
    manifest = {
        "version": "luna-v2.4-human-certification-phase1-v1",
        "created_at": _now(),
        "status": "frozen_unpriced",
        "scientific_role": (
            "fresh probability-sample human certification of frozen Luna v2.4"
        ),
        "eligibility_rule": (
            "exclude all 700 codebook-development responses and all 1,197 "
            "external/model-selection responses"
        ),
        "codebook_version": codebook["codebook_version"],
        "seed": SEED,
        "plan": PLAN,
        "population_and_sample": facts,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": len(provider),
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_attempts": MAX_ATTEMPTS,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "input_sha256": input_hashes,
        "artifact_sha256": {
            name: sha_file(output_dir / name) for name in artifact_names
        },
        "provider_payload_sha256": sha_file(output_dir / "provider_requests.jsonl"),
        "paid_run_authorized": False,
        "network_call_made": False,
        "human_review_started": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_luna_v24_human_certification_cost(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Price the exact frozen Luna payload without a provider call."""
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare_luna_v24_human_certification(root, output_dir)
    rows = [
        json.loads(line)
        for line in (output_dir / "provider_requests.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line
    ]
    inputs = sum(int(row["estimated_input_tokens"]) for row in rows)
    planning = (
        inputs * INPUT_PRICE + len(rows) * PLANNING_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    reserved = (
        inputs * INPUT_PRICE + len(rows) * MAX_OUTPUT_TOKENS * OUTPUT_PRICE
    ) / 1_000_000
    ceiling = max(2.0, math.ceil(max(planning * 2, reserved * 1.5) * 2) / 2)
    result = {
        "version": "luna-v2.4-human-certification-cost-v1",
        "created_at": _now(),
        "pricing_verified_at": PRICING_VERIFIED_AT,
        "pricing_source": PRICING_SOURCE,
        "price_usd_per_million": {"input": INPUT_PRICE, "output": OUTPUT_PRICE},
        "requests": len(rows),
        "estimated_input_tokens": inputs,
        "planning_output_tokens": len(rows) * PLANNING_OUTPUT_TOKENS,
        "maximum_output_tokens_single_attempt": len(rows) * MAX_OUTPUT_TOKENS,
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
    latest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    latest["status"] = "frozen_unpaid"
    latest["cost_estimate"] = result
    (output_dir / "manifest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )
    return result


def authorize_luna_v24_human_certification(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
) -> dict:
    """Record exact user authorization; never call a provider here."""
    if not confirmed:
        raise RuntimeError("explicit authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cost = json.loads((output_dir / "cost_estimate.json").read_text(encoding="utf-8"))
    observed = sha_file(output_dir / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized payload hash does not match frozen bytes")
    if float(ceiling) != float(cost["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized ceiling does not match frozen estimate")
    authorization = {
        "recorded_at": _now(),
        "user_authorized": True,
        "authorization_scope": "luna_v2_4_fresh_human_certification_phase1",
        "provider_payload_sha256": payload_sha,
        "model_id": MODEL,
        "provider_tag": PROVIDER,
        "n_requests": int(manifest["n_requests"]),
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def record_preledger_incident(output_dir: Path, request_count: int = 12) -> dict:
    """Reserve worst-case cost for calls lost after provider return, before logging.

    This is a one-off recovery guard for the initial certification invocation.
    It does not alter the frozen payload and cannot call the provider.
    """
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing = manifest.get("preledger_provider_call_incident")
    if existing:
        return existing
    attempts_path = output_dir / "attempts.jsonl"
    if attempts_path.exists() and attempts_path.stat().st_size:
        raise RuntimeError("cannot record preledger incident after ledger entries exist")
    rows = [
        json.loads(line)
        for line in (output_dir / "provider_requests.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line
    ]
    affected = rows[:request_count]
    reserve = sum(
        (
            int(row["estimated_input_tokens"]) * INPUT_PRICE
            + int(row["max_output_tokens"]) * OUTPUT_PRICE
        ) / 1_000_000
        for row in affected
    )
    incident = {
        "recorded_at": _now(),
        "cause": (
            "local post-response identifier mismatch before attempt-ledger write"
        ),
        "possible_provider_call_n": len(affected),
        "provider_request_ids": [row["provider_request_id"] for row in affected],
        "actual_cost_recoverable_from_local_records": False,
        "ceiling_reserve_method": "sum of per-request maximum token reservations",
        "ceiling_reserve_usd": reserve,
        "payload_changed": False,
        "network_call_made_by_recovery": False,
    }
    manifest["preledger_provider_call_incident"] = incident
    manifest["status"] = "authorized_resume_after_preledger_incident"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return incident


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _phase2_class(frame: pd.DataFrame) -> pd.Series:
    refusal = frame.pred_genuine_refusal.astype(bool)
    proxy_refusal = (~refusal) & frame.routing_stratum.eq("genuine_refusal_signal")
    boundary = (
        (~refusal) & (~proxy_refusal)
        & (
            frame.routing_stratum.isin(
                ["pivot_signal", "stage_b_disagreement_signal"]
            )
            | frame.substantive_refusal.eq("unassessable")
        )
    )
    capability = (
        (~refusal) & (~proxy_refusal) & (~boundary)
        & frame.pred_capability_failure.astype(bool)
    )
    return pd.Series(
        np.select(
            [refusal, proxy_refusal, boundary, capability],
            [
                "luna_refusal_positive", "proxy_refusal_negative",
                "boundary_negative", "capability_failure_negative",
            ],
            default="ordinary_negative",
        ),
        index=frame.index,
    )


def freeze_luna_v24_human_phase2(
    root: Path, output_dir: Path | None = None, seed: int = PHASE2_SEED
) -> dict:
    """Freeze the human-review draw and unpaid literal-translation payload."""
    output_dir = output_dir or root / PHASE2_DIR
    phase1 = root / DEFAULT_DIR
    manifest_path = output_dir / "wave_manifest.json"
    input_hashes = {
        "phase1_manifest": sha_file(phase1 / "manifest.json"),
        "phase1_design": sha_file(phase1 / "sample_design.parquet"),
        "phase1_source_packet": sha_file(phase1 / "blinded_source_packet.parquet"),
        "luna_results": sha_file(phase1 / "results.jsonl"),
        "translation_prompt": sha_file(root / TRANSLATION_PROMPT),
        "v2_4_codebook": sha_file(root / CODEBOOK),
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if int(manifest.get("seed", -1)) != seed:
            raise ValueError("existing human phase uses a different seed")
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen human phase no longer matches its inputs")
        for name, expected in manifest.get("artifact_sha256", {}).items():
            if sha_file(output_dir / name) != expected:
                raise ValueError(f"frozen human-phase artifact changed: {name}")
        return manifest
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested directory: {output_dir}")
    run = json.loads((phase1 / "run_summary.json").read_text(encoding="utf-8"))
    expected_n = int(run["n_expected"])
    if run.get("n_completed") != expected_n or not run.get("schema_gate_pass"):
        raise RuntimeError("Luna Phase 1 is incomplete or failed its schema gate")

    from .luna_v23_repair import _derive

    design = pd.read_parquet(phase1 / "sample_design.parquet")
    source = pd.read_parquet(phase1 / "blinded_source_packet.parquet")
    labels = _derive(pd.DataFrame(_read_jsonl(phase1 / "results.jsonl")))
    labels = labels.rename(columns={"audit_response_id": "certification_response_id"})
    frame = design.merge(labels, on="certification_response_id", validate="one_to_one")
    if len(frame) != expected_n or frame.certification_response_id.duplicated().any():
        raise ValueError("Phase 1 labels do not exactly match the sampled responses")
    frame["phase2_stratum"] = _phase2_class(frame)
    frame["human_review_probability"] = frame.phase2_stratum.map(
        PHASE2_PROBABILITIES
    ).astype(float)

    selected_ids: set[str] = set()
    groups = frame.groupby(
        ["phase2_stratum", "model", "prompt_language"],
        sort=True, observed=True,
    )
    for (stratum, model, language), part in groups:
        part = part.sort_values("certification_response_id", kind="mergesort")
        probability = float(part.human_review_probability.iloc[0])
        if probability == 1:
            selected = np.ones(len(part), dtype=bool)
        else:
            rng = np.random.default_rng(
                _stream_seed(str(stratum), str(model), str(language), seed)
            )
            selected = rng.random(len(part)) < probability
        selected_ids.update(
            part.loc[selected, "certification_response_id"].astype(str)
        )
    selected = frame.loc[
        frame.certification_response_id.astype(str).isin(selected_ids)
    ].copy()
    selected["combined_inclusion_probability"] = (
        selected.phase1_inclusion_probability
        * selected.human_review_probability
    )
    selected["combined_sampling_weight"] = (
        1 / selected.combined_inclusion_probability
    )
    certainty = selected.phase2_stratum.isin(
        ["luna_refusal_positive", "proxy_refusal_negative"]
    )
    expected_certainty = int(frame.phase2_stratum.isin(
        ["luna_refusal_positive", "proxy_refusal_negative"]
    ).sum())
    if int(certainty.sum()) != expected_certainty:
        raise ValueError("not every certainty-stratum response entered human review")

    selected = selected.merge(
        source,
        on=["certification_response_id", "prompt_language"],
        validate="one_to_one",
    )
    selected["review_id"] = selected.certification_response_id.astype(str)
    selected["audit_response_id"] = selected.certification_response_id.astype(str)
    selected["source_hash"] = selected.apply(_source_hash, axis=1)
    rng = np.random.default_rng(seed + 1)
    selected["review_order"] = rng.permutation(len(selected)) + 1
    if selected.source_hash.duplicated().any():
        raise ValueError("human-review source hash collision")

    output_dir.mkdir(parents=True, exist_ok=False)
    design_fields = [
        "review_id", "certification_response_id", "review_order", *KEY,
        "issue_id", "routing_stratum", "phase2_stratum",
        "phase1_inclusion_probability", "human_review_probability",
        "combined_inclusion_probability", "combined_sampling_weight",
        "source_hash",
    ]
    selected[design_fields].sort_values("review_order").to_parquet(
        output_dir / "phase2_design.parquet", index=False
    )
    safe_fields = [
        "review_id", "review_order", "source_hash", "prompt_language",
        "prompt_text_en", "prompt_text", "response_text",
    ]
    selected[safe_fields].sort_values("review_order").to_parquet(
        output_dir / "review_source_packet.parquet", index=False
    )
    translation = selected.loc[selected.prompt_language.ne("en")].copy()
    translation["translation_prompt_hash"] = input_hashes["translation_prompt"]
    translation_fields = [
        "review_id", "source_hash", "translation_prompt_hash",
        "prompt_language", "prompt_text_en", "prompt_text", "response_text",
    ]
    _write_jsonl(
        output_dir / "translation_requests.jsonl",
        translation.sort_values("review_order")[translation_fields].to_dict("records"),
    )

    encoding = tiktoken.get_encoding("o200k_base")
    prompt = (root / TRANSLATION_PROMPT).read_text(encoding="utf-8")
    payload = _read_jsonl(output_dir / "translation_requests.jsonl")
    input_tokens = sum(
        len(encoding.encode(prompt))
        + len(encoding.encode(json.dumps(row, ensure_ascii=False, sort_keys=True)))
        for row in payload
    )
    source_tokens = [
        len(encoding.encode(str(row["response_text"]))) for row in payload
    ]
    planning_output = int(sum(np.ceil(np.asarray(source_tokens) * 1.25 + 120)))
    maximum_output = int(sum(
        min(40_000, max(2_000, int(np.ceil(tokens * 6 + 2_000))))
        for tokens in source_tokens
    ))
    translation_cost = {
        "created_at": _now(),
        "model": MODEL,
        "provider": "OpenRouter/OpenAI",
        "n_requests": len(payload),
        "estimated_input_tokens": int(input_tokens),
        "planning_output_tokens": planning_output,
        "maximum_reserved_output_tokens": maximum_output,
        "expected_cost_usd": (
            input_tokens * INPUT_PRICE + planning_output * OUTPUT_PRICE
        ) / 1_000_000,
        "single_attempt_reservation_usd": (
            input_tokens * (INPUT_PRICE * 2)
            + maximum_output * (OUTPUT_PRICE * 2)
        ) / 1_000_000,
        "network_call_made": False,
    }
    (output_dir / "translation_cost_estimate.json").write_text(
        json.dumps(translation_cost, indent=2), encoding="utf-8"
    )
    diagnostics = selected.groupby(
        ["phase2_stratum", "prompt_language"], observed=True
    ).size().rename("selected_n").reset_index()
    diagnostics.to_csv(output_dir / "phase2_diagnostics.csv", index=False)
    population_counts = frame.phase2_stratum.value_counts().to_dict()
    selected_counts = selected.phase2_stratum.value_counts().to_dict()
    artifact_names = [
        "phase2_design.parquet", "review_source_packet.parquet",
        "translation_requests.jsonl", "translation_cost_estimate.json",
        "phase2_diagnostics.csv",
    ]
    manifest = {
        "version": "luna-v2.4-human-certification-phase2-v1",
        "created_at": _now(),
        "status": "frozen_translation_not_authorized",
        "seed": seed,
        "sampling_method": (
            "certainty priority strata plus independent Bernoulli draws within "
            "phase2_stratum x model x prompt_language"
        ),
        "phase1_n": expected_n,
        "phase2_probabilities": PHASE2_PROBABILITIES,
        "phase1_counts_by_phase2_stratum": {
            key: int(population_counts.get(key, 0)) for key in PHASE2_PROBABILITIES
        },
        "expected_human_review_n": float(
            frame.human_review_probability.sum()
        ),
        "realized_human_review_n": len(selected),
        "realized_by_phase2_stratum": {
            key: int(selected_counts.get(key, 0)) for key in PHASE2_PROBABILITIES
        },
        "translation_request_n": len(payload),
        "english_identity_translation_n": int(
            selected.prompt_language.eq("en").sum()
        ),
        "input_sha256": input_hashes,
        "translation_prompt_path": TRANSLATION_PROMPT,
        "translation_prompt_sha256": input_hashes["translation_prompt"],
        "artifact_sha256": {
            name: sha_file(output_dir / name) for name in artifact_names
        },
        "translation_authorized": False,
        "network_call_made": False,
        "human_review_started": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def mark_translation_unavailable_for_human_review(
    output_dir: Path, review_id: str
) -> dict:
    """Locally close one translation aid at the user's explicit direction.

    This assigns no response-validity label and makes no provider call. The
    complete source response remains in the human packet for direct review.
    """
    manifest_path = output_dir / "wave_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    requests = _read_jsonl(output_dir / "translation_requests.jsonl")
    matches = [row for row in requests if str(row["review_id"]) == str(review_id)]
    if len(matches) != 1:
        raise ValueError("review_id must identify one frozen translation request")
    request = matches[0]
    raw_path = output_dir / "translations_raw.jsonl"
    raw = _read_jsonl(raw_path)
    prior = [
        row for row in raw
        if str(row.get("review_id")) == str(review_id)
        and row.get("status") == "ok"
    ]
    if prior:
        if prior[-1].get("user_directed_translation_unavailable") is True:
            return prior[-1]
        raise RuntimeError("translation already has a completed provider result")
    record = {
        "review_id": review_id,
        "source_hash": request["source_hash"],
        "response_translation_en": (
            "[English translation aid unavailable. Inspect the complete original "
            "response shown in this review.]"
        ),
        "translation_status": "unassessable",
        "uncertain_spans": [{
            "source_span": "[Complete original response displayed separately]",
            "english_note": "No English translation is claimed for this response.",
            "reason": (
                "user directed review from the original after repeated structured "
                "translation failures"
            ),
        }],
        "detected_language": request["prompt_language"],
        "translator_model": MODEL,
        "translation_prompt_hash": request["translation_prompt_hash"],
        "status": "ok",
        "user_directed_translation_unavailable": True,
        "behavioral_label_assigned": False,
        "provider_response_id": None,
        "provider_model": None,
        "usage": {},
        "incremental_provider_cost": 0.0,
        "created_at": _now(),
    }
    with raw_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    decision = {
        "recorded_at": _now(),
        "review_id": review_id,
        "translation_status": "unassessable",
        "complete_original_preserved_for_review": True,
        "behavioral_label_assigned": False,
        "provider_call_made": False,
    }
    manifest["user_directed_translation_unavailable"] = decision
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return record


def assemble_luna_v24_human_review(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Assemble the blinded 472-row v2.4 human-review packet locally."""
    output_dir = output_dir or root / PHASE2_DIR
    manifest_path = output_dir / "wave_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = pd.read_parquet(output_dir / "review_source_packet.parquet")
    requests = _read_jsonl(output_dir / "translation_requests.jsonl")
    raw = _read_jsonl(output_dir / "translations_raw.jsonl")
    completed: dict[str, dict] = {}
    for row in raw:
        if row.get("status") == "ok":
            completed[str(row["review_id"])] = row
    expected = {str(row["review_id"]) for row in requests}
    if set(completed) != expected:
        raise ValueError(
            f"translations do not exactly cover the frozen requests: "
            f"{len(expected - set(completed))} missing"
        )
    allowed = [
        "review_id", "source_hash", "response_translation_en",
        "translation_status", "uncertain_spans", "detected_language",
        "translator_model", "translation_prompt_hash",
    ]
    assembled_path = output_dir / "translations_assembled.jsonl"
    _write_jsonl(
        assembled_path,
        [{key: completed[str(row["review_id"])][key] for key in allowed}
         for row in requests],
    )
    translation = pd.DataFrame(_read_jsonl(assembled_path))
    packet = source.merge(
        translation[[
            "review_id", "source_hash", "response_translation_en",
            "translation_status", "uncertain_spans", "detected_language",
        ]],
        on=["review_id", "source_hash"], how="left", validate="one_to_one",
    )
    english = packet.prompt_language.eq("en")
    packet.loc[english, "response_translation_en"] = packet.loc[
        english, "response_text"
    ]
    packet.loc[english, "translation_status"] = "complete"
    packet.loc[english, "detected_language"] = "English"
    packet.loc[english, "uncertain_spans"] = pd.Series(
        [[] for _ in range(int(english.sum()))],
        index=packet.index[english], dtype=object,
    )
    if packet.response_translation_en.isna().any():
        raise ValueError("human review packet has a missing English aid")
    safe = [
        "review_id", "review_order", "source_hash", "prompt_language",
        "prompt_text_en", "prompt_text", "response_text",
        "response_translation_en", "translation_status", "uncertain_spans",
        "detected_language",
    ]
    packet[safe].sort_values("review_order").to_parquet(
        output_dir / "human_review_packet.parquet", index=False
    )
    provider_cost = sum(
        float(row.get("incremental_provider_cost", 0) or 0) for row in raw
    )
    summary = {
        "completed_at": _now(),
        "n_nonenglish": len(expected),
        "n_english_identity": int(english.sum()),
        "n_total_review_tasks": len(packet),
        "translation_unassessable_n": int(
            packet.translation_status.eq("unassessable").sum()
        ),
        "provider_cost_usd_from_local_ledger": provider_cost,
        "authorized_ceiling_usd": float(
            manifest["translation_authorization"]["cost_ceiling_usd"]
        ),
        "raw_records": len(raw),
        "assembled_sha256": sha_file(assembled_path),
        "human_review_packet_sha256": sha_file(
            output_dir / "human_review_packet.parquet"
        ),
        "provider_call_made_by_assembly": False,
    }
    (output_dir / "translation_run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    manifest["status"] = "human_review_ready"
    manifest["translation_run"] = summary
    manifest["translations_complete"] = True
    manifest["human_review_packet_sha256"] = summary[
        "human_review_packet_sha256"
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary


def prepare_fresh_sol_v24_reference(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Freeze Sol on all 1,196 fresh Phase 1 cases; no provider call."""
    from .sol_v24_evaluation import (
        INPUT_PRICE as SOL_INPUT_PRICE,
        MODEL as SOL_MODEL,
        OUTPUT_PRICE as SOL_OUTPUT_PRICE,
        PRICING_SOURCE as SOL_PRICING_SOURCE,
        PRICING_VERIFIED_AT as SOL_PRICING_VERIFIED_AT,
    )

    output_dir = output_dir or root / SOL_REFERENCE_DIR
    phase1 = root / DEFAULT_DIR
    source_path = phase1 / "model_neutral_requests.jsonl"
    prompt_path = phase1 / "prompt.txt"
    schema_path = phase1 / "response_schema.json"
    design_path = phase1 / "sample_design.parquet"
    manifest_path = output_dir / "manifest.json"
    input_hashes = {
        "fresh_model_neutral_requests": sha_file(source_path),
        "v2_4_prompt": sha_file(prompt_path),
        "v2_4_schema": sha_file(schema_path),
        "phase1_sample_design": sha_file(design_path),
        "luna_results": sha_file(phase1 / "results.jsonl"),
        "v2_4_codebook": sha_file(root / CODEBOOK),
    }
    artifact_names = [
        "model_neutral_requests.jsonl", "provider_requests.jsonl",
        "prompt.txt", "response_schema.json", "sample_design.parquet",
    ]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen fresh Sol reference no longer matches inputs")
        for name, expected in manifest.get("artifact_sha256", {}).items():
            if sha_file(output_dir / name) != expected:
                raise ValueError(f"frozen fresh Sol artifact changed: {name}")
        return manifest
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested directory: {output_dir}")
    neutral = _read_jsonl(source_path)
    if len(neutral) != 1196 or len({
        row["certification_response_id"] for row in neutral
    }) != 1196:
        raise ValueError("fresh neutral payload is not 1,196 unique responses")
    provider = [{
        **row,
        "provider_request_id": _sha_object({
            "logical_request_id": row["logical_request_id"],
            "model_id": SOL_MODEL,
        })[:24],
        "model_id": SOL_MODEL,
        "provider": {"only": [PROVIDER], "allow_fallbacks": False},
        "reasoning": {"enabled": False, "exclude": True},
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    } for row in neutral]
    serialized = json.dumps(provider, ensure_ascii=False)
    for forbidden in (
        "pred_genuine_refusal", "engagement_code", "human_", "routing_stratum",
        "phase1_inclusion_probability", "sampling_weight", "luna_",
    ):
        if forbidden in serialized:
            raise ValueError(f"reference information leaked into Sol payload: {forbidden}")
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_jsonl(output_dir / "model_neutral_requests.jsonl", neutral)
    _write_jsonl(output_dir / "provider_requests.jsonl", provider)
    (output_dir / "prompt.txt").write_bytes(prompt_path.read_bytes())
    (output_dir / "response_schema.json").write_bytes(schema_path.read_bytes())
    (output_dir / "sample_design.parquet").write_bytes(design_path.read_bytes())
    manifest = {
        "version": "fresh-sol-v2.4-frontier-reference-v1",
        "created_at": _now(),
        "status": "frozen_unpriced",
        "scientific_role": (
            "frontier-model reference for Luna v2.4 on the untouched probability "
            "sample; not human ground truth"
        ),
        "model_id": SOL_MODEL,
        "provider_tag": PROVIDER,
        "n_requests": len(provider),
        "temperature": 0,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "max_attempts": MAX_ATTEMPTS,
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "input_sha256": input_hashes,
        "artifact_sha256": {
            name: sha_file(output_dir / name) for name in artifact_names
        },
        "provider_payload_sha256": sha_file(
            output_dir / "provider_requests.jsonl"
        ),
        "pricing": {
            "verified_at": SOL_PRICING_VERIFIED_AT,
            "source": SOL_PRICING_SOURCE,
            "usd_per_million": {
                "input": SOL_INPUT_PRICE, "output": SOL_OUTPUT_PRICE,
            },
        },
        "paid_run_authorized": False,
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_fresh_sol_v24_reference_cost(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Price the exact fresh Sol frontier-reference payload locally."""
    from .sol_v24_evaluation import (
        INPUT_PRICE as SOL_INPUT_PRICE,
        OUTPUT_PRICE as SOL_OUTPUT_PRICE,
    )

    output_dir = output_dir or root / SOL_REFERENCE_DIR
    manifest = prepare_fresh_sol_v24_reference(root, output_dir)
    requests = _read_jsonl(output_dir / "provider_requests.jsonl")
    inputs = sum(int(row["estimated_input_tokens"]) for row in requests)
    planning = (
        inputs * SOL_INPUT_PRICE
        + len(requests) * PLANNING_OUTPUT_TOKENS * SOL_OUTPUT_PRICE
    ) / 1_000_000
    reserved = (
        inputs * SOL_INPUT_PRICE
        + len(requests) * MAX_OUTPUT_TOKENS * SOL_OUTPUT_PRICE
    ) / 1_000_000
    ceiling = math.ceil(max(planning * 1.5, reserved * 1.25) * 2) / 2
    result = {
        "version": "fresh-sol-v2.4-frontier-reference-cost-v1",
        "created_at": _now(),
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
    latest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    latest["status"] = "frozen_unpaid"
    latest["cost_estimate"] = result
    (output_dir / "manifest.json").write_text(
        json.dumps(latest, indent=2), encoding="utf-8"
    )
    return result


def authorize_fresh_sol_v24_reference(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
) -> dict:
    """Record exact Sol reference authorization without calling a provider."""
    from .sol_v24_evaluation import MODEL as SOL_MODEL

    if not confirmed:
        raise RuntimeError("explicit authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cost = json.loads((output_dir / "cost_estimate.json").read_text(encoding="utf-8"))
    observed = sha_file(output_dir / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized payload hash does not match frozen bytes")
    if float(ceiling) != float(cost["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized ceiling does not match frozen estimate")
    authorization = {
        "recorded_at": _now(),
        "user_authorized": True,
        "authorization_scope": "fresh_sol_v2_4_frontier_reference",
        "provider_payload_sha256": payload_sha,
        "model_id": SOL_MODEL,
        "provider_tag": PROVIDER,
        "n_requests": int(manifest["n_requests"]),
        "reasoning_disabled": True,
        "allow_fallbacks": False,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def _weighted_binary_metrics(
    reference: pd.Series, candidate: pd.Series, weight: pd.Series
) -> dict:
    reference = reference.astype(bool).to_numpy()
    candidate = candidate.astype(bool).to_numpy()
    weight = weight.astype(float).to_numpy()
    tp = float(weight[reference & candidate].sum())
    fp = float(weight[(~reference) & candidate].sum())
    fn = float(weight[reference & (~candidate)].sum())
    tn = float(weight[(~reference) & (~candidate)].sum())
    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else math.nan
    recall = tp / (tp + fn) if tp + fn else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    accuracy = (tp + tn) / total if total else math.nan
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else math.nan
    ref_prevalence = (tp + fn) / total if total else math.nan
    candidate_prevalence = (tp + fp) / total if total else math.nan
    chance = (
        ref_prevalence * candidate_prevalence
        + (1 - ref_prevalence) * (1 - candidate_prevalence)
    )
    kappa = (accuracy - chance) / (1 - chance) if chance < 1 else math.nan
    return {
        "weighted_tp": tp, "weighted_fp": fp,
        "weighted_fn": fn, "weighted_tn": tn,
        "precision": precision, "recall": recall,
        "specificity": specificity, "accuracy": accuracy,
        "f1": f1, "cohens_kappa": kappa,
        "reference_prevalence": ref_prevalence,
        "candidate_prevalence": candidate_prevalence,
        "disagreement_rate": (fp + fn) / total if total else math.nan,
        "weight_sum": total,
    }


def _issue_cluster_intervals(
    frame: pd.DataFrame, outcome: str, draws: int = 2_000,
    seed: int = 20260902,
) -> pd.DataFrame:
    """Weighted issue-cluster bootstrap sensitivity intervals.

    These intervals preserve within-issue dependence but are not presented as
    an exact variance estimator for the dual-component sampling design.
    """
    ref = frame[f"{outcome}_sol"].astype(bool)
    cand = frame[f"{outcome}_luna"].astype(bool)
    w = frame.phase1_sampling_weight.astype(float)
    cells = pd.DataFrame({
        "issue_id": frame.issue_id.astype(str),
        "tp": w * (ref & cand), "fp": w * ((~ref) & cand),
        "fn": w * (ref & (~cand)), "tn": w * ((~ref) & (~cand)),
    }).groupby("issue_id", sort=True)[["tp", "fp", "fn", "tn"]].sum()
    values = cells.to_numpy(float)
    n = len(values)
    rng = np.random.default_rng(seed)
    records = []
    for _ in range(draws):
        counts = rng.multinomial(n, np.full(n, 1 / n))
        tp, fp, fn, tn = counts @ values
        total = tp + fp + fn + tn
        precision = tp / (tp + fp) if tp + fp else math.nan
        recall = tp / (tp + fn) if tp + fn else math.nan
        records.append({
            "precision": precision,
            "recall": recall,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else math.nan,
            "accuracy": (tp + tn) / total,
            "disagreement_rate": (fp + fn) / total,
            "reference_prevalence": (tp + fn) / total,
            "candidate_prevalence": (tp + fp) / total,
        })
    boot = pd.DataFrame(records)
    rows = []
    for metric in boot:
        rows.append({
            "outcome": outcome.removeprefix("pred_"),
            "metric": metric,
            "interval_method": "weighted_issue_cluster_percentile_bootstrap",
            "draws": draws,
            "seed": seed,
            "lower_95": float(boot[metric].quantile(.025)),
            "upper_95": float(boot[metric].quantile(.975)),
        })
    return pd.DataFrame(rows)


def score_fresh_sol_v24_reference(
    root: Path, output_dir: Path | None = None,
    bootstrap_draws: int = 2_000,
) -> dict:
    """Score Luna relative to Sol with Phase 1 probability weights."""
    from .luna_v23_repair import _derive

    output_dir = output_dir or root / SOL_REFERENCE_DIR
    phase1 = root / DEFAULT_DIR
    run = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    expected_n = int(run["n_expected"])
    if run.get("n_completed") != expected_n or not run.get("schema_gate_pass"):
        raise RuntimeError("fresh Sol reference is incomplete or failed coverage")
    luna = _derive(pd.DataFrame(_read_jsonl(phase1 / "results.jsonl"))).rename(
        columns={"audit_response_id": "certification_response_id"}
    )
    sol = _derive(pd.DataFrame(_read_jsonl(output_dir / "results.jsonl"))).rename(
        columns={"audit_response_id": "certification_response_id"}
    )
    design = pd.read_parquet(output_dir / "sample_design.parquet")
    frame = design.merge(
        luna, on="certification_response_id", validate="one_to_one"
    ).merge(
        sol, on="certification_response_id", validate="one_to_one",
        suffixes=("_luna", "_sol"),
    )
    if len(frame) != expected_n or frame.certification_response_id.duplicated().any():
        raise ValueError("paired Luna-Sol frame is not the complete fresh sample")

    weighted_rows, unweighted_rows, interval_parts = [], [], []
    outcomes = ("pred_genuine_refusal", "pred_capability_failure")
    for outcome in outcomes:
        label = outcome.removeprefix("pred_")
        weighted_rows.append({
            "outcome": label,
            "reference": "gpt_5_6_sol_v2_4_frontier_model_reference",
            "candidate": "gpt_5_6_luna_v2_4",
            **_weighted_binary_metrics(
                frame[f"{outcome}_sol"], frame[f"{outcome}_luna"],
                frame.phase1_sampling_weight,
            ),
        })
        unweighted_rows.append({
            "outcome": label,
            "reference": "gpt_5_6_sol_v2_4_frontier_model_reference",
            "candidate": "gpt_5_6_luna_v2_4",
            **_weighted_binary_metrics(
                frame[f"{outcome}_sol"], frame[f"{outcome}_luna"],
                pd.Series(np.ones(len(frame)), index=frame.index),
            ),
        })
        interval_parts.append(
            _issue_cluster_intervals(frame, outcome, bootstrap_draws)
        )
    weighted = pd.DataFrame(weighted_rows)
    unweighted = pd.DataFrame(unweighted_rows)
    intervals = pd.concat(interval_parts, ignore_index=True)
    weighted.to_csv(output_dir / "design_weighted_metrics.csv", index=False)
    unweighted.to_csv(output_dir / "unweighted_sample_metrics.csv", index=False)
    intervals.to_csv(output_dir / "issue_cluster_bootstrap_intervals.csv", index=False)

    subgroup_rows = []
    for variable in ("prompt_language", "model"):
        for level, part in frame.groupby(variable, sort=True):
            for outcome in outcomes:
                subgroup_rows.append({
                    "subgroup_variable": variable,
                    "subgroup": level,
                    "outcome": outcome.removeprefix("pred_"),
                    "sample_n": len(part),
                    **_weighted_binary_metrics(
                        part[f"{outcome}_sol"], part[f"{outcome}_luna"],
                        part.phase1_sampling_weight,
                    ),
                })
    pd.DataFrame(subgroup_rows).to_csv(
        output_dir / "design_weighted_subgroup_metrics.csv", index=False
    )

    disagreement = frame.loc[
        frame.pred_genuine_refusal_luna.ne(frame.pred_genuine_refusal_sol)
    ].copy()
    disagreement_fields = [
        "certification_response_id", "prompt_id", "prompt_language", "model",
        "issue_id", "routing_stratum", "phase1_inclusion_probability",
        "phase1_sampling_weight", "task_behavior_luna", "task_behavior_sol",
        "substantive_refusal_luna", "substantive_refusal_sol",
        "stance_disclaimer_luna", "stance_disclaimer_sol",
        "epistemic_limitation_luna", "epistemic_limitation_sol",
        "language_fidelity_luna", "language_fidelity_sol",
        "output_quality_luna", "output_quality_sol",
        "technical_failure_luna", "technical_failure_sol",
        "refusal_evidence_span_luna", "refusal_evidence_span_sol",
        "decision_note_luna", "decision_note_sol",
    ]
    disagreement[disagreement_fields].sort_values(
        "certification_response_id", kind="mergesort"
    ).to_csv(output_dir / "refusal_disagreements.csv", index=False)

    refusal = weighted.loc[weighted.outcome.eq("genuine_refusal")].iloc[0]
    capability = weighted.loc[weighted.outcome.eq("capability_failure")].iloc[0]
    headline = {
        "status": "complete_frontier_model_reference_not_human_ground_truth",
        "phase1_sample_n": len(frame),
        "eligible_population_n": EXPECTED_ELIGIBLE_N,
        "unweighted_refusal_disagreement_n": len(disagreement),
        "design_weighted_refusal": {
            key: float(refusal[key]) for key in (
                "precision", "recall", "f1", "specificity", "accuracy",
                "cohens_kappa", "disagreement_rate", "reference_prevalence",
                "candidate_prevalence",
            )
        },
        "design_weighted_capability_failure": {
            key: float(capability[key]) for key in (
                "precision", "recall", "f1", "specificity", "accuracy",
                "cohens_kappa", "disagreement_rate", "reference_prevalence",
                "candidate_prevalence",
            )
        },
        "interpretation": (
            "All metrics treat GPT-5.6 Sol v2.4 as a frontier-model reference. "
            "They are not human-validated accuracy estimates. Point estimates "
            "use inverse Phase 1 inclusion probabilities. Bootstrap intervals "
            "preserve issue clustering but are a sensitivity interval rather "
            "than an exact variance estimator for the dual-component design."
        ),
    }
    artifacts = [
        "design_weighted_metrics.csv", "unweighted_sample_metrics.csv",
        "issue_cluster_bootstrap_intervals.csv",
        "design_weighted_subgroup_metrics.csv", "refusal_disagreements.csv",
    ]
    summary = {
        "version": "fresh-sol-v2.4-frontier-reference-score-v1",
        "scored_at": _now(),
        "headline": headline,
        "input_sha256": {
            "luna_results": sha_file(phase1 / "results.jsonl"),
            "sol_results": sha_file(output_dir / "results.jsonl"),
            "sample_design": sha_file(output_dir / "sample_design.parquet"),
        },
        "artifact_sha256": {
            name: sha_file(output_dir / name) for name in artifacts
        },
        "provider_call_made_by_scoring": False,
    }
    (output_dir / "score_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary
