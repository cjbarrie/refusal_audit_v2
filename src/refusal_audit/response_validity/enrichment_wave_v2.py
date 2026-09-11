"""Freeze the approved 400-row human-enrichment wave without a network call."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .enrichment_design_v2 import (
    ALLOCATIONS,
    ROUTING_STRATA,
    build_routing_population,
)
from .human_pilot import (
    KEY,
    load_translation_records,
    priority_class,
    sha_file,
    sha_text,
    source_hash,
)


WAVE_SIZE = 400
ROUTING_SEED = 20260823
DRAW_SEED = 20260824
EVALUATION_SHARE = 0.60
DESIGN_VERSION = "human-enrichment-wave-v2.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _original_pilot_probabilities(frame: pd.DataFrame) -> pd.Series:
    """Reconstruct the declared first-wave probabilities for all 137,186 rows."""
    priority = priority_class(frame)
    n_global = 100
    n_cell = 2
    n_priority = 90
    p_global = np.full(len(frame), n_global / len(frame), dtype=float)
    cell_n = frame.groupby(["model", "prompt_language"], observed=True)["prompt_id"].transform("size")
    p_cell = n_cell / cell_n.to_numpy(float)

    sizes = priority.value_counts(sort=False)
    target_share = pd.Series({
        "original_nonengagement": .22,
        "predicted_capability": .22,
        "predicted_refusal": .18,
        "predicted_pivot": .14,
        "diagnostic_flag": .16,
        "ordinary_control": .08,
    }).reindex(sizes.index).fillna(0)
    target_share /= target_share.sum()
    raw = n_priority * target_share
    allocation = np.floor(raw).astype(int).clip(lower=1)
    while allocation.sum() < n_priority:
        for level in (raw - allocation).sort_values(ascending=False).index:
            if allocation.sum() >= n_priority:
                break
            if allocation[level] < sizes[level]:
                allocation[level] += 1
    while allocation.sum() > n_priority:
        for level in (allocation - raw).sort_values(ascending=False).index:
            if allocation.sum() <= n_priority:
                break
            if allocation[level] > 1:
                allocation[level] -= 1
    p_priority = priority.map((allocation / sizes).to_dict()).to_numpy(float)
    return pd.Series(1 - (1 - p_global) * (1 - p_cell) * (1 - p_priority), index=frame.index)


def _prompt_group_split(selected: pd.DataFrame, seed: int) -> pd.Series:
    """Choose a label-blind prompt-group split balanced across routing strata."""
    groups = selected.prompt_id.drop_duplicates().to_numpy()
    target = selected.groupby("routing_stratum").size() * EVALUATION_SHARE
    total_target = len(selected) * EVALUATION_SHARE
    rng = np.random.default_rng(seed)
    best: tuple[float, set] | None = None
    # Random search uses routing strata and group IDs only, never outcomes.
    for _ in range(10_000):
        shuffled = rng.permutation(groups)
        cut = int(round(len(groups) * EVALUATION_SHARE))
        evaluation = set(shuffled[:cut])
        counts = selected.loc[selected.prompt_id.isin(evaluation)].groupby("routing_stratum").size()
        deviations = counts.reindex(ROUTING_STRATA, fill_value=0) - target.reindex(ROUTING_STRATA)
        score = float(np.square(deviations).sum() + .25 * (len(selected.loc[selected.prompt_id.isin(evaluation)]) - total_target) ** 2)
        if best is None or score < best[0]:
            best = (score, evaluation)
    assert best is not None
    split = np.where(selected.prompt_id.isin(best[1]), "evaluation", "development")
    return pd.Series(split, index=selected.index, dtype="string")


def freeze_enrichment_wave_v2(
    root: Path,
    pilot_dir: Path,
    output_dir: Path | None = None,
    routing_seed: int = ROUTING_SEED,
    draw_seed: int = DRAW_SEED,
    confirm_design_approval: bool = False,
) -> dict:
    """Draw and hash the approved wave; do not translate or contact a provider."""
    if not confirm_design_approval:
        raise PermissionError("freezing row IDs requires --confirm-design-approval")
    output_dir = output_dir or pilot_dir / "enrichment_wave_v2_400"
    manifest_path = output_dir / "wave_manifest.json"
    simulation_dir = pilot_dir / "enrichment_simulation_v2"
    inputs = {
        "simulation_manifest": sha_file(simulation_dir / "simulation_manifest.json"),
        "workload_allocations": sha_file(simulation_dir / "workload_allocations.csv"),
        "pilot_manifest": sha_file(pilot_dir / "pilot_manifest.json"),
        "pilot_design": sha_file(pilot_dir / "pilot_design.parquet"),
        "complete_language_labels": sha_file(
            pilot_dir / "base_freeze_v3_complete_language_review" / "base_labels.parquet"
        ),
        "stage_b_disagreements": sha_file(
            pilot_dir / "surrogate_bakeoff_stage_b_v1" / "stage_b_row_disagreements.csv"
        ),
    }
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("input_sha256") != inputs:
            raise RuntimeError("existing enrichment wave has different frozen inputs")
        for name, expected in existing["artifact_sha256"].items():
            if sha_file(output_dir / name) != expected:
                raise RuntimeError(f"frozen enrichment artifact changed: {name}")
        return existing
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested wave directory: {output_dir}")

    population, human, candidate_mask = build_routing_population(root, pilot_dir, routing_seed)
    population["source_hash"] = population.apply(source_hash, axis=1)
    population["pilot_priority_class"] = priority_class(population)
    population["pi_pilot"] = _original_pilot_probabilities(population)
    original = pd.read_parquet(pilot_dir / "pilot_design.parquet")
    verified = original[KEY + ["inclusion_probability"]].merge(
        population[KEY + ["pi_pilot"]], on=KEY, validate="one_to_one"
    )
    if not np.allclose(verified.inclusion_probability, verified.pi_pilot, atol=1e-15):
        raise ValueError("reconstructed first-wave probabilities do not match the frozen pilot")

    candidate = population.loc[candidate_mask].copy()
    allocation = dict(zip(ROUTING_STRATA, ALLOCATIONS[WAVE_SIZE]))
    rng = np.random.default_rng(draw_seed)
    selected_parts = []
    for stratum in ROUTING_STRATA:
        pool = candidate.loc[candidate.routing_stratum.eq(stratum)]
        n = allocation[stratum]
        if len(pool) < n:
            raise ValueError(f"{stratum} has insufficient candidates")
        chosen = rng.choice(pool.index.to_numpy(), size=n, replace=False)
        part = candidate.loc[chosen].copy()
        part["routing_population_n"] = len(pool)
        part["wave_draw_n"] = n
        part["pi_wave_given_history"] = n / len(pool)
        selected_parts.append(part)
    selected = pd.concat(selected_parts, ignore_index=True)
    if len(selected) != WAVE_SIZE or selected.duplicated(KEY).any():
        raise ValueError("enrichment wave must contain 400 unique response keys")
    base_keys = set(map(tuple, human[KEY].itertuples(index=False, name=None)))
    if any(key in base_keys for key in selected[KEY].itertuples(index=False, name=None)):
        raise ValueError("enrichment wave overlaps the completed 300-row pilot")

    selected["sequential_inclusion_probability"] = 1 - (
        (1 - selected.pi_pilot) * (1 - selected.pi_wave_given_history)
    )
    selected["sequential_sampling_weight"] = 1 / selected.sequential_inclusion_probability
    selected["review_id"] = "e2-" + selected.source_hash.str[:21]
    if selected.review_id.duplicated().any():
        raise ValueError("review_id collision")
    selected["analysis_split"] = _prompt_group_split(selected, draw_seed + 1)
    selected["review_order"] = rng.permutation(len(selected)) + 1
    if set(selected.loc[selected.analysis_split.eq("development"), "prompt_id"]) & set(
        selected.loc[selected.analysis_split.eq("evaluation"), "prompt_id"]
    ):
        raise ValueError("prompt leakage across development and evaluation")

    prompt_path = root / "config" / "response_translation_prompt_v1.txt"
    prompt_hash = sha_file(prompt_path)
    selected["translation_prompt_hash"] = prompt_hash
    output_dir.mkdir(parents=True, exist_ok=False)
    selected.sort_values("review_order").to_parquet(output_dir / "wave_design.parquet", index=False)
    requests = selected.sort_values("review_order")[[
        "review_id", "source_hash", "translation_prompt_hash", "prompt_language",
        "prompt_text_en", "prompt_text", "response_text",
    ]]
    with (output_dir / "translation_requests.jsonl").open("w", encoding="utf-8") as handle:
        for record in requests.to_dict("records"):
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    selected.groupby(["routing_stratum", "analysis_split"], observed=True).size().rename("n").reset_index().to_csv(
        output_dir / "wave_diagnostics.csv", index=False
    )

    artifacts = ["wave_design.parquet", "translation_requests.jsonl", "wave_diagnostics.csv"]
    manifest = {
        "design_version": DESIGN_VERSION,
        "created_at": _now(),
        "design_approval": "User: 'Okay can we do these annotations now?' (2026-08-24)",
        "routing_seed": routing_seed,
        "draw_seed": draw_seed,
        "population_rows": len(population),
        "prior_human_rows_excluded": len(human),
        "candidate_rows": int(candidate_mask.sum()),
        "selected_rows": len(selected),
        "allocation": allocation,
        "sampling": "independent SRSWOR within seven mutually exclusive frozen routing strata",
        "first_wave_probability_verified": True,
        "sequential_probability_formula": "1-(1-pi_pilot)*(1-pi_wave_given_frozen_history)",
        "adaptive_inference_note": "final variance must use the declared sequential design and frozen history; do not treat the adaptive wave as one-shot SRS",
        "analysis_split": {
            "unit": "prompt_id",
            "target_evaluation_share": EVALUATION_SHARE,
            "development_rows": int(selected.analysis_split.eq("development").sum()),
            "evaluation_rows": int(selected.analysis_split.eq("evaluation").sum()),
            "prompt_overlap": 0,
            "assigned_before_human_labels": True,
        },
        "silent_repeats": 0,
        "translation_prompt_path": prompt_path.relative_to(root).as_posix(),
        "translation_prompt_sha256": prompt_hash,
        "translation_payload_sha256": sha_file(output_dir / "translation_requests.jsonl"),
        "input_sha256": inputs,
        "artifact_sha256": {name: sha_file(output_dir / name) for name in artifacts},
        "human_labels_seen_for_selected_rows": False,
        "translation_authorized": False,
        "translation_sent": False,
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def assemble_enrichment_review_packet(output_dir: Path, translations_path: Path) -> dict:
    """Build the blinded enrichment queue after complete literal translation."""
    manifest_path = output_dir / "wave_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    design = pd.read_parquet(output_dir / "wave_design.parquet")
    translations = load_translation_records(translations_path)
    if not translations.translation_prompt_hash.eq(manifest["translation_prompt_sha256"]).all():
        raise ValueError("translation prompt differs from the frozen enrichment wave")
    packet = design.merge(
        translations, on=["review_id", "source_hash"], validate="one_to_one"
    )
    if len(packet) != len(design):
        raise ValueError("translations do not cover the entire 400-row enrichment wave")
    safe = [
        "review_id", "review_order", "prompt_language", "prompt_text_en", "prompt_text",
        "response_text", "response_translation_en", "translation_status", "uncertain_spans",
        "detected_language", "diag_char_count", "diag_token_count", "diag_replacement_rate",
        "diag_control_rate", "diag_target_script_share", "diag_target_script_mismatch",
        "diag_unique_token_ratio", "diag_repeated_trigram_ratio", "diag_prompt_echo_overlap",
        "diag_punctuation_rate", "diag_repetition_loop", "diag_truncation_suspect",
        "diag_metadata_language_disagreement",
    ]
    packet = packet[safe].sort_values("review_order")
    packet_path = output_dir / "human_review_packet.parquet"
    if packet_path.exists():
        if sha_file(packet_path) != manifest.get("human_review_packet_sha256"):
            raise RuntimeError("existing enrichment review packet differs from its manifest")
    else:
        packet.to_parquet(packet_path, index=False)
    metadata = {
        "created_at": _now(),
        "unique_source_rows": len(packet),
        "review_tasks": len(packet),
        "repeat_tasks": 0,
        "labels_revealed": False,
        "model_identity_revealed": False,
        "analysis_split_revealed": False,
        "routing_stratum_revealed": False,
    }
    (output_dir / "human_review_packet.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    manifest["translations_ingested"] = True
    manifest["translations_ingested_at"] = metadata["created_at"]
    manifest["translations_path_sha256"] = sha_file(translations_path)
    manifest["human_review_packet_sha256"] = sha_file(packet_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return metadata
