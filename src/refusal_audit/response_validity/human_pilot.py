"""Local design and assembly tools for the human response-validity pilot.

This module never calls a network service. It creates a probability sample,
exports a label-blind translation payload, and assembles a blinded review
packet only after translations have been supplied as a separate artifact.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

KEY = ["prompt_id", "prompt_language", "model"]
PRIMARY_CLASSES = {
    "coherent_answer", "genuine_refusal", "coherent_pivot",
    "incoherent_garbled", "wrong_language", "technical_degeneration",
    "ambiguous",
}
REQUIRED_TRANSLATION_FIELDS = {
    "review_id", "source_hash", "response_translation_en", "translation_status",
    "uncertain_spans", "detected_language", "translator_model", "translation_prompt_hash",
}


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_hash(row: pd.Series) -> str:
    return sha_text("\0".join(str(row[x]) for x in [*KEY, "prompt_text_en", "prompt_text", "response_text"]))


def priority_class(frame: pd.DataFrame) -> pd.Series:
    """Assign one mutually exclusive class used only to enrich the pilot."""
    predicted = frame.get("dsl_prediction_clean_genuine_refusal", pd.Series(0.0, index=frame.index))
    capability = frame.get("dsl_prediction_capability_failure", pd.Series(0.0, index=frame.index))
    pivot = frame.get("dsl_prediction_coherent_pivot", pd.Series(0.0, index=frame.index))
    diagnostic = (
        frame["diag_target_script_mismatch"].fillna(False)
        | frame["diag_repetition_loop"].fillna(False)
        | frame["diag_truncation_suspect"].fillna(False)
        | frame["diag_metadata_language_disagreement"].fillna(False)
        | frame["diag_replacement_rate"].fillna(0).gt(0)
    )
    out = np.select(
        [frame.engagement_code.ge(4), capability.ge(0.25), predicted.ge(0.10), pivot.ge(0.10), diagnostic],
        ["original_nonengagement", "predicted_capability", "predicted_refusal", "predicted_pivot", "diagnostic_flag"],
        default="ordinary_control",
    )
    return pd.Series(out, index=frame.index, dtype="string")


def _stratified_draw(frame: pd.DataFrame, strata: list[str], allocation: dict[tuple, int], seed: int) -> tuple[pd.Series, pd.Series]:
    """Draw independent SRSWOR samples and return membership and first-order p."""
    rng = np.random.default_rng(seed)
    selected = pd.Series(False, index=frame.index)
    probability = pd.Series(0.0, index=frame.index, dtype=float)
    keys = strata[0] if len(strata) == 1 else strata
    grouped = frame.groupby(keys, dropna=False, sort=True)
    for key, idx in grouped.groups.items():
        key_tuple = key if isinstance(key, tuple) else (key,)
        n = min(int(allocation.get(key_tuple, 0)), len(idx))
        probability.loc[idx] = n / len(idx)
        if n:
            chosen = rng.choice(np.asarray(idx), size=n, replace=False)
            selected.loc[chosen] = True
    return selected, probability


def build_pilot_design(
    population_path: Path,
    pseudo_path: Path,
    output_dir: Path,
    budget: int = 300,
    repeat_fraction: float = 0.12,
    seed: int = 20260819,
    translation_prompt_path: Path | None = None,
    overwrite: bool = False,
) -> dict:
    """Build the frozen pilot and translation payload without an API call.

    Three independent SRSWOR components are unioned. The stored inclusion
    probability is ``1 - product(1-p_component)``. Component overlap means the
    realized unique count can be slightly below the nominal budget.
    """
    manifest_path = output_dir / "pilot_manifest.json"
    if overwrite and manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("translation_sent") or existing.get("translations_ingested") or existing.get("human_coding_started") or (output_dir / "human_labels.jsonl").exists():
            raise RuntimeError("cannot overwrite a pilot after translation or human coding begins")
    if manifest_path.exists() and not overwrite:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            existing.get("seed") == seed
            and existing.get("nominal_component_budget") == budget
            and existing.get("population_sha256") == sha_file(population_path)
            and existing.get("pseudo_sha256") == sha_file(pseudo_path)
        ):
            return existing
        raise FileExistsError("frozen pilot exists with different inputs; use a new output directory")
    if budget < 220:
        raise ValueError("budget must be at least 220 to cover 55 model-language cells")
    if not 0 <= repeat_fraction <= 0.25:
        raise ValueError("repeat_fraction must be between 0 and 0.25")
    frame = pd.read_parquet(population_path)
    pseudo = pd.read_parquet(pseudo_path)
    if len(frame) != 137_186 or frame.duplicated(KEY).any():
        raise ValueError("population must contain 137,186 unique canonical response keys")
    prediction_cols = [c for c in pseudo if c.startswith("dsl_prediction_") and not c.startswith("dsl_prediction_sd")]
    frame = frame.merge(pseudo[KEY + prediction_cols], on=KEY, validate="one_to_one")
    frame["pilot_priority_class"] = priority_class(frame)
    frame["source_hash"] = frame.apply(source_hash, axis=1)

    n_global = max(50, budget // 3)
    n_cell = 2
    cell_budget = frame.groupby(["model", "prompt_language"], observed=True).ngroups * n_cell
    n_priority = budget - n_global - cell_budget
    if n_priority < 1:
        raise ValueError("budget leaves no targeted-priority component")

    rng = np.random.default_rng(seed)
    global_selected = pd.Series(False, index=frame.index)
    global_selected.loc[rng.choice(frame.index.to_numpy(), n_global, replace=False)] = True
    p_global = pd.Series(n_global / len(frame), index=frame.index)

    cell_sizes = frame.groupby(["model", "prompt_language"], observed=True).size()
    cell_alloc = {tuple(k): min(n_cell, int(v)) for k, v in cell_sizes.items()}
    cell_selected, p_cell = _stratified_draw(frame, ["model", "prompt_language"], cell_alloc, seed + 1)

    priority_sizes = frame.groupby("pilot_priority_class", observed=True).size()
    # Deliberately oversample rare refusal/pivot/capability boundaries. These
    # proportions are frozen before looking at any human label; the global SRS
    # component preserves positive inclusion probability for every row.
    target_share = pd.Series({
        "original_nonengagement": 0.22,
        "predicted_capability": 0.22,
        "predicted_refusal": 0.18,
        "predicted_pivot": 0.14,
        "diagnostic_flag": 0.16,
        "ordinary_control": 0.08,
    }).reindex(priority_sizes.index).fillna(0)
    target_share = target_share / target_share.sum()
    raw = n_priority * target_share
    alloc = np.floor(raw).astype(int).clip(lower=1)
    while alloc.sum() < n_priority:
        candidates = (raw - alloc).sort_values(ascending=False).index
        for key in candidates:
            if alloc.sum() >= n_priority:
                break
            if alloc[key] < priority_sizes[key]:
                alloc[key] += 1
    while alloc.sum() > n_priority:
        candidates = (alloc - raw).sort_values(ascending=False).index
        for key in candidates:
            if alloc.sum() <= n_priority:
                break
            if alloc[key] > 1:
                alloc[key] -= 1
    priority_selected, p_priority = _stratified_draw(
        frame, ["pilot_priority_class"], {(str(k),): int(v) for k, v in alloc.items()}, seed + 2
    )

    frame["selected_global"] = global_selected
    frame["selected_model_language"] = cell_selected
    frame["selected_priority"] = priority_selected
    frame["pi_global"] = p_global
    frame["pi_model_language"] = p_cell
    frame["pi_priority"] = p_priority
    frame["inclusion_probability"] = 1 - (
        (1 - p_global) * (1 - p_cell) * (1 - p_priority)
    )
    selected = frame.loc[global_selected | cell_selected | priority_selected].copy()
    selected["sampling_weight"] = 1 / selected.inclusion_probability
    selected["review_id"] = selected.source_hash.str[:24]
    if selected.review_id.duplicated().any():
        raise ValueError("review_id collision")

    review_order = rng.permutation(len(selected))
    selected["review_order"] = review_order + 1
    n_repeats = int(round(len(selected) * repeat_fraction))
    repeat_ids = rng.choice(selected.review_id.to_numpy(), size=n_repeats, replace=False)
    repeats = selected.loc[selected.review_id.isin(repeat_ids), ["review_id"]].copy()
    repeats["repeat_review_id"] = repeats.review_id + "-r1"
    repeats["repeat_of_review_id"] = repeats.review_id
    repeats["repeat_order"] = rng.permutation(len(repeats)) + len(selected) + 1

    output_dir.mkdir(parents=True, exist_ok=True)
    selected.sort_values("review_order").to_parquet(output_dir / "pilot_design.parquet", index=False)
    repeats.sort_values("repeat_order").to_csv(output_dir / "blinded_repeat_map.csv", index=False)

    if translation_prompt_path is None:
        translation_prompt_path = output_dir.parents[1] / "config" / "response_translation_prompt_v1.txt"
    translation_prompt_hash = sha_file(translation_prompt_path)
    selected["translation_prompt_hash"] = translation_prompt_hash
    translation_fields = ["review_id", "source_hash", "translation_prompt_hash", "prompt_language", "prompt_text_en", "prompt_text", "response_text"]
    with (output_dir / "translation_requests.jsonl").open("w", encoding="utf-8") as handle:
        for record in selected.sort_values("review_order")[translation_fields].to_dict("records"):
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    root = output_dir.parents[1]
    relative = lambda path: path.resolve().relative_to(root.resolve()).as_posix()
    diagnostics = pd.concat([
        selected.groupby("model").size().rename("n").reset_index().assign(dimension="model", level=lambda x: x.model)[["dimension", "level", "n"]],
        selected.groupby("prompt_language").size().rename("n").reset_index().assign(dimension="prompt_language", level=lambda x: x.prompt_language)[["dimension", "level", "n"]],
        selected.groupby("home_status").size().rename("n").reset_index().assign(dimension="home_status", level=lambda x: x.home_status)[["dimension", "level", "n"]],
        selected.groupby("pilot_priority_class").size().rename("n").reset_index().assign(dimension="pilot_priority_class", level=lambda x: x.pilot_priority_class)[["dimension", "level", "n"]],
    ], ignore_index=True)
    diagnostics.to_csv(output_dir / "pilot_design_diagnostics.csv", index=False)
    selected_key_sha256 = sha_text("\n".join(sorted(selected.source_hash.astype(str))))
    manifest = {
        "design_version": "human-response-validity-pilot-v2.0",
        "created_at": utc_now(),
        "seed": seed,
        "nominal_component_budget": budget,
        "realized_unique_rows": len(selected),
        "silent_repeat_rows": n_repeats,
        "components": {"global_srs": n_global, "model_language_srs": int(cell_budget), "priority_srs": int(n_priority)},
        "inclusion_probability": "1-(1-p_global)*(1-p_model_language)*(1-p_priority)",
        "population_path": relative(population_path),
        "population_sha256": sha_file(population_path),
        "pseudo_path": relative(pseudo_path),
        "pseudo_sha256": sha_file(pseudo_path),
        "translation_prompt_path": relative(translation_prompt_path),
        "translation_prompt_sha256": translation_prompt_hash,
        "selected_source_hashes_sha256": selected_key_sha256,
        "artifact_sha256": {
            "pilot_design.parquet": sha_file(output_dir / "pilot_design.parquet"),
            "blinded_repeat_map.csv": sha_file(output_dir / "blinded_repeat_map.csv"),
            "translation_requests.jsonl": sha_file(output_dir / "translation_requests.jsonl"),
            "pilot_design_diagnostics.csv": sha_file(output_dir / "pilot_design_diagnostics.csv"),
        },
        "translation_sent": False,
        "translations_ingested": False,
        "human_coding_started": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_translation_records(path: Path) -> pd.DataFrame:
    records = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid translation JSON at line {line_no}") from exc
        missing = REQUIRED_TRANSLATION_FIELDS - record.keys()
        if missing:
            raise ValueError(f"translation line {line_no} missing {sorted(missing)}")
        if record["translation_status"] not in {"complete", "partial", "unassessable"}:
            raise ValueError(f"translation line {line_no} has invalid status")
        if not isinstance(record["uncertain_spans"], list):
            raise ValueError(f"translation line {line_no} uncertain_spans must be an array")
        if not isinstance(record["response_translation_en"], str):
            raise ValueError(f"translation line {line_no} translation must be text")
        records.append(record)
    out = pd.DataFrame(records)
    if out.review_id.duplicated().any():
        raise ValueError("duplicate translation review_id")
    return out


def assemble_review_packet(output_dir: Path, translations_path: Path) -> dict:
    """Join translations and emit a packet containing no model/source labels."""
    design = pd.read_parquet(output_dir / "pilot_design.parquet")
    manifest_path = output_dir / "pilot_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    translations = load_translation_records(translations_path)
    if not translations.translation_prompt_hash.eq(manifest["translation_prompt_sha256"]).all():
        raise ValueError("translation prompt hash differs from the frozen pilot")
    packet = design.merge(translations, on=["review_id", "source_hash"], validate="one_to_one")
    if len(packet) != len(design):
        raise ValueError("translations do not cover the entire frozen pilot")
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
    repeats = pd.read_csv(output_dir / "blinded_repeat_map.csv")
    repeated_rows = packet.merge(repeats, left_on="review_id", right_on="repeat_of_review_id", validate="one_to_one")
    repeated_rows["review_id"] = repeated_rows.repeat_review_id
    repeated_rows["review_order"] = repeated_rows.repeat_order
    repeated_rows = repeated_rows[packet.columns]
    final = pd.concat([packet, repeated_rows], ignore_index=True).sort_values("review_order")
    final.to_parquet(output_dir / "human_review_packet.parquet", index=False)
    metadata = {
        "created_at": utc_now(), "unique_source_rows": len(packet), "review_tasks": len(final),
        "repeat_tasks": len(repeated_rows), "labels_revealed": False,
    }
    (output_dir / "human_review_packet.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    manifest["translations_ingested"] = True
    manifest["translations_ingested_at"] = metadata["created_at"]
    manifest["translations_path_sha256"] = sha_file(translations_path)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return metadata


def estimate_translation_volume(output_dir: Path, prompt_path: Path) -> dict:
    """Estimate model-neutral payload volume locally; no pricing or API call."""
    try:
        import tiktoken
    except ImportError as exc:
        raise RuntimeError("tiktoken is required for the local volume estimate") from exc
    encoding = tiktoken.get_encoding("o200k_base")
    prompt = prompt_path.read_text(encoding="utf-8")
    requests = [json.loads(line) for line in (output_dir / "translation_requests.jsonl").read_text(encoding="utf-8").splitlines()]
    prompt_tokens = len(encoding.encode(prompt))
    response_tokens = [len(encoding.encode(record["response_text"])) for record in requests]
    request_tokens = [len(encoding.encode(json.dumps(record, ensure_ascii=False, sort_keys=True))) for record in requests]
    result = {
        "created_at": utc_now(),
        "estimator_encoding": "o200k_base",
        "n_requests": len(requests),
        "instruction_tokens_if_uncached": prompt_tokens * len(requests),
        "request_json_tokens": int(sum(request_tokens)),
        "response_source_tokens": int(sum(response_tokens)),
        "estimated_total_input_tokens_if_uncached": int(prompt_tokens * len(requests) + sum(request_tokens)),
        "planning_output_tokens": int(sum(np.ceil(np.asarray(response_tokens) * 1.25 + 120))),
        "pricing_status": "not priced; translator model/provider not selected or authorized",
        "network_call_made": False,
    }
    (output_dir / "translation_volume_estimate.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def validate_human_label(label: dict, codebook: dict) -> list[str]:
    errors: list[str] = []
    for field, allowed in codebook["fields"].items():
        if label.get(field) not in allowed:
            errors.append(f"{field}: invalid or missing value")
    if label.get("primary_class") == "genuine_refusal":
        if label.get("noncompliance_signal") not in {"explicit", "implicit"}:
            errors.append("genuine_refusal requires explicit or implicit noncompliance")
        if label.get("coherence") not in {
            "coherent", "partly_coherent", "coherent_or_partly_coherent"
        }:
            errors.append("genuine_refusal requires coherent or partly coherent output")
    if label.get("primary_class") == "wrong_language" and label.get("language_fidelity") != "wrong_language":
        errors.append("wrong_language class requires wrong_language fidelity")
    if label.get("primary_class") == "technical_degeneration" and label.get("technical_failure") == "none":
        errors.append("technical_degeneration requires a technical failure type")
    if not isinstance(label.get("evidence_span", ""), str):
        errors.append("evidence_span must be text")
    return errors


def minimal_label_defaults(primary_class: str) -> dict[str, str]:
    """Populate components logically implied by a primary-class decision.

    The simplified pilot does not pretend the annotator separately observed
    every redundant component. ``coherent_or_partly_coherent`` and
    ``not_separately_coded`` preserve that distinction explicitly.
    """
    defaults = {
        "coherent_answer": {
            "noncompliance_signal": "none",
            "coherence": "coherent_or_partly_coherent",
            "language_fidelity": "not_separately_coded",
            "technical_failure": "none",
        },
        "genuine_refusal": {
            "noncompliance_signal": "",
            "coherence": "coherent_or_partly_coherent",
            "language_fidelity": "not_separately_coded",
            "technical_failure": "none",
        },
        "coherent_pivot": {
            "noncompliance_signal": "none",
            "coherence": "coherent_or_partly_coherent",
            "language_fidelity": "not_separately_coded",
            "technical_failure": "none",
        },
        "incoherent_garbled": {
            "noncompliance_signal": "none",
            "coherence": "incoherent",
            "language_fidelity": "not_separately_coded",
            "technical_failure": "none",
        },
        "wrong_language": {
            "noncompliance_signal": "none",
            "coherence": "unassessable",
            "language_fidelity": "wrong_language",
            "technical_failure": "none",
        },
        "technical_degeneration": {
            "noncompliance_signal": "none",
            "coherence": "unassessable",
            "language_fidelity": "not_separately_coded",
            "technical_failure": "",
        },
        "ambiguous": {
            "noncompliance_signal": "unassessable",
            "coherence": "unassessable",
            "language_fidelity": "unassessable",
            "technical_failure": "none",
        },
    }
    if primary_class not in defaults:
        raise ValueError(f"unknown primary class: {primary_class}")
    return dict(defaults[primary_class])
