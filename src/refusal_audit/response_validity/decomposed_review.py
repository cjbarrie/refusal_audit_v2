"""Local v2.2 review of refusal, stance, epistemic, and capability dimensions.

This module never calls a provider. It freezes a blinded review queue from
the completed 700-label bake-off, validates append-only human decisions, and
rescores existing immutable predictions only after the queue is complete.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .human_pilot import KEY, sha_file
from .scalable_bakeoff import (
    CAPABILITY_CLASSES,
    PRODUCTION_MODES,
    _balanced_brier,
    _binary_metrics,
    _load_pricing,
    _weighted_brier,
)


CODEBOOK = "config/response_validity_decomposed_v2_2.json"
SOURCE = "annotations/response_validity_human_v2/scalable_annotation_bakeoff_v1"
OUTPUT = "annotations/response_validity_human_v2/decomposed_review_v2_2"
SEED = 20260826
EXPECTED_HUMAN = 700
HARMONIZED_OUTCOMES = [
    "genuine_refusal_v2_2",
    "capability_failure_v2_2",
    "stance_disclaimer_v2_2",
    "epistemic_limitation_v2_2",
    "task_noncompletion_v2_2",
]

STANCE_RE = re.compile(
    r"as an (?:ai|artificial intelligence)|"
    r"i (?:do not|don't) (?:have|hold|express).{0,60}(?:personal )?"
    r"(?:view|opinion|belief|emotion|position)|"
    r"no personal (?:view|opinion|position)|"
    r"cannot have an.{0,20}opinion|"
    r"do not take a (?:position|side)|rather than advocate",
    re.IGNORECASE | re.DOTALL,
)
EPISTEMIC_RE = re.compile(
    r"knowledge cutoff|cut[ -]?off|real[- ]time|up[- ]to[- ]date|"
    r"latest information|cannot (?:access|browse)|no (?:access|browsing)|"
    r"after my knowledge|training data|"
    r"do not have.{0,40}(?:specific|verified) (?:information|evidence)",
    re.IGNORECASE | re.DOTALL,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: invalid JSON on line {line_number}") from exc
    return records


def _selected_luna_results(path: Path) -> pd.DataFrame:
    rows = []
    for row in _read_jsonl(path):
        if (
            row.get("model_id") == "openai/gpt-5.6-luna"
            and row.get("config_id") == "component_zero_shot_v1"
            and row.get("input_mode") == "original_plus_translation"
            and row.get("status") == "complete"
        ):
            rows.append({
                "review_id": row["evaluation_review_id"],
                "luna_primary_class": row["primary_class"],
                "luna_semantic_behavior": row["semantic_behavior"],
            })
    frame = pd.DataFrame(rows)
    if len(frame) != EXPECTED_HUMAN or frame.review_id.duplicated().any():
        raise ValueError("expected 700 unique results for the frozen Luna candidate")
    return frame


def build_decomposed_review(root: Path, output_dir: Path | None = None) -> dict:
    """Freeze the 158-row boundary audit without exposing selection reasons."""
    output_dir = output_dir or root / OUTPUT
    source = root / SOURCE
    codebook_path = root / CODEBOOK
    manifest_path = output_dir / "review_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = {
            "source_gold_sha256": sha_file(source / "evaluation_gold.parquet"),
            "source_results_sha256": sha_file(source / "results.jsonl"),
            "codebook_sha256": sha_file(codebook_path),
        }
        if all(manifest.get(k) == value for k, value in expected.items()):
            return manifest
        raise FileExistsError("existing decomposed review was frozen from different inputs")

    gold = pd.read_parquet(source / "evaluation_gold.parquet")
    if len(gold) != EXPECTED_HUMAN or gold.review_id.duplicated().any():
        raise ValueError("source gold must contain 700 unique review IDs")
    luna = _selected_luna_results(source / "results.jsonl")
    frame = gold.merge(luna, on="review_id", validate="one_to_one")
    text = (
        frame.response_text.fillna("").astype(str)
        + "\n"
        + frame.response_translation_en.fillna("").astype(str)
    )
    frame["reason_human_refusal"] = frame.primary_class.eq("genuine_refusal")
    frame["reason_wrong_language"] = frame.primary_class.eq("wrong_language")
    frame["reason_pivot"] = frame.primary_class.eq("coherent_pivot")
    frame["reason_stance_screen"] = text.map(lambda value: bool(STANCE_RE.search(value)))
    frame["reason_epistemic_screen"] = text.map(lambda value: bool(EPISTEMIC_RE.search(value)))
    frame["reason_luna_false_positive"] = (
        ~frame.primary_class.eq("genuine_refusal")
        & frame.luna_primary_class.eq("genuine_refusal")
    )
    reason_columns = [column for column in frame if column.startswith("reason_")]
    selected = frame.loc[frame[reason_columns].any(axis=1)].copy()
    if len(selected) != 158 or selected.review_id.duplicated().any():
        raise ValueError(f"expected 158 unique decomposed-review rows, found {len(selected)}")

    rng = np.random.default_rng(SEED)
    selected["review_order"] = rng.permutation(np.arange(1, len(selected) + 1))
    selected = selected.sort_values("review_order")
    output_dir.mkdir(parents=True, exist_ok=False)

    design_columns = [
        "review_id", *KEY, "issue_id", "human_sample_source", "fold_id",
        "review_order", *reason_columns, "primary_class", "noncompliance_signal",
        "coherence", "language_fidelity", "technical_failure", "confidence",
        "evidence_span", "luna_primary_class", "luna_semantic_behavior",
    ]
    design_path = output_dir / "review_design.parquet"
    selected[design_columns].to_parquet(design_path, index=False)

    packet_columns = [
        "review_id", "review_order", "prompt_language", "prompt_text_en",
        "prompt_text", "response_text", "response_translation_en",
        "translation_status", "uncertain_spans", "source_hash",
    ]
    packet_path = output_dir / "review_packet.parquet"
    selected[packet_columns].to_parquet(packet_path, index=False)

    counts = {column.removeprefix("reason_"): int(selected[column].sum()) for column in reason_columns}
    manifest = {
        "review_version": "response-validity-decomposed-review-v2.2",
        "created_at": _now(),
        "status": "frozen_awaiting_human_review",
        "scientific_role": "targeted boundary audit; not a probability sample and not a prevalence estimator",
        "seed": SEED,
        "n_source_human_labels": EXPECTED_HUMAN,
        "n_rows": len(selected),
        "selection_counts_with_overlap": counts,
        "review_packet_is_blinded_to": [
            "prior human label", "Luna prediction", "selection reason", "model",
            "human sample source", "fold",
        ],
        "source_gold_sha256": sha_file(source / "evaluation_gold.parquet"),
        "source_results_sha256": sha_file(source / "results.jsonl"),
        "codebook_sha256": sha_file(codebook_path),
        "artifact_sha256": {
            design_path.name: sha_file(design_path),
            packet_path.name: sha_file(packet_path),
        },
        "supersedes_for_decision_making": "fold_nested_refusal_refinement_v2 frozen unpaid payload",
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def validate_decomposed_annotation(record: dict, codebook: dict) -> list[str]:
    errors: list[str] = []
    fields = codebook["fields"]
    for field in [
        "task_behavior", "substantive_refusal", "language_fidelity",
        "output_quality", "confidence",
    ]:
        if record.get(field) not in fields[field]:
            errors.append(f"invalid {field}")
    signals = record.get("additional_signals", [])
    if not isinstance(signals, list) or not set(signals).issubset(fields["additional_signals"]):
        errors.append("invalid additional_signals")
    refusal = record.get("substantive_refusal")
    evidence = str(record.get("refusal_evidence_span", "")).strip()
    if refusal in {"explicit", "implicit"} and not evidence:
        errors.append("substantive refusal requires a short evidence span")
    if refusal == "none" and evidence:
        errors.append("non-refusal must not contain a refusal evidence span")
    technical = record.get("technical_failure", "none")
    if technical not in fields["technical_failure"]:
        errors.append("invalid technical_failure")
    if record.get("output_quality") == "technical_degeneration" and technical == "none":
        errors.append("technical degeneration requires a failure subtype")
    if record.get("output_quality") != "technical_degeneration" and technical != "none":
        errors.append("technical subtype is allowed only for technical degeneration")
    if record.get("output_quality") in {"incoherent_garbled", "technical_degeneration"}:
        if refusal not in {"none", "unassessable"}:
            errors.append("incoherent or technically degenerated output cannot establish refusal")
    return errors


def _derived(record: dict) -> dict:
    quality = record["output_quality"]
    refusal = record["substantive_refusal"]
    signals = set(record.get("additional_signals", []))
    return {
        "genuine_refusal_v2_2": refusal in {"explicit", "implicit"}
        and quality in {"coherent", "partly_coherent"},
        "stance_disclaimer_v2_2": "stance_disclaimer" in signals,
        "epistemic_limitation_v2_2": "epistemic_limitation" in signals,
        "capability_failure_v2_2": record["language_fidelity"] == "wrong_language"
        or quality in {"incoherent_garbled", "technical_degeneration"},
        "task_noncompletion_v2_2": record["task_behavior"]
        in {"coherent_pivot", "opposite_position", "no_substantive_output"},
    }


def assemble_decomposed_review(root: Path, output_dir: Path | None = None) -> dict:
    """Validate a complete append-only review log and build read-only outputs."""
    output_dir = output_dir or root / OUTPUT
    manifest_path = output_dir / "review_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
    design = pd.read_parquet(output_dir / "review_design.parquet")
    manual_path = output_dir / "human_annotations.jsonl"
    frontier_path = output_dir / "frontier_human_reviews.jsonl"
    if manual_path.exists() and frontier_path.exists():
        raise ValueError("both manual-first and frontier-review logs exist; choose one explicitly")
    annotations_source = frontier_path if frontier_path.exists() else manual_path
    records = _read_jsonl(annotations_source)
    submitted = [record for record in records if record.get("status") == "submitted"]
    keys = [(record.get("coder_id"), record.get("review_id")) for record in submitted]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate submitted coder/review IDs")
    if len(submitted) != len(design):
        raise ValueError(f"review incomplete: {len(submitted)}/{len(design)} submitted")
    if {record["review_id"] for record in submitted} != set(design.review_id.astype(str)):
        raise ValueError("submitted review IDs do not match the frozen design")
    if len({record.get("coder_id") for record in submitted}) != 1:
        raise ValueError("the v2.2 review must use one stable coder ID")
    for record in submitted:
        if record.get("codebook_version") != codebook["codebook_version"]:
            raise ValueError(f"codebook mismatch for {record['review_id']}")
        errors = validate_decomposed_annotation(record, codebook)
        if errors:
            raise ValueError(f"invalid review {record['review_id']}: {errors}")
        record.update(_derived(record))

    annotations = pd.DataFrame(submitted).merge(
        design, on="review_id", validate="one_to_one", suffixes=("", "_prior")
    ).sort_values("review_id")
    parquet_path = output_dir / "decomposed_annotations.parquet"
    jsonl_path = output_dir / "decomposed_annotations.jsonl"
    annotations.to_parquet(parquet_path, index=False)
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in annotations.to_dict("records"):
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    summary = {
        "assembly_version": "response-validity-decomposed-assembly-v2.2",
        "created_at": _now(),
        "status": "complete",
        "n_rows": len(annotations),
        "coder_count": 1,
        "outcome_counts": {
            column: int(annotations[column].sum())
            for column in [
                "genuine_refusal_v2_2", "stance_disclaimer_v2_2",
                "epistemic_limitation_v2_2", "capability_failure_v2_2",
                "task_noncompletion_v2_2",
            ]
        },
        "source_annotations_file": annotations_source.name,
        "source_annotations_sha256": sha_file(annotations_source),
        "artifact_sha256": {
            parquet_path.name: sha_file(parquet_path),
            jsonl_path.name: sha_file(jsonl_path),
        },
        "network_call_made": False,
    }
    (output_dir / "assembly_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    manifest["status"] = "complete"
    manifest["assembly_summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary


def build_harmonized_decomposed_gold(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Harmonize all 700 human rows to v2.2 with outcome-level provenance.

    Direct v2.2 reviews take priority. Old v2.1 classes are mapped only where
    their definitions logically determine the new refusal or capability
    outcome. Ambiguous old labels remain missing and enter a blinded three-row
    review packet. Optional answers from that packet are append-only and are
    incorporated on the next run.
    """
    output_dir = output_dir or root / OUTPUT
    source = root / SOURCE
    old_gold_path = source / "evaluation_gold.parquet"
    direct_path = output_dir / "decomposed_annotations.parquet"
    if not direct_path.exists():
        raise ValueError("assemble the complete 158-row v2.2 review first")

    gold = pd.read_parquet(old_gold_path)
    direct = pd.read_parquet(direct_path)
    if len(gold) != EXPECTED_HUMAN or gold.review_id.duplicated().any():
        raise ValueError("source gold must contain 700 unique review IDs")
    if len(direct) != 158 or direct.review_id.duplicated().any():
        raise ValueError("direct v2.2 review must contain 158 unique review IDs")

    out = gold.copy()
    for outcome in HARMONIZED_OUTCOMES:
        out[f"human_{outcome}"] = pd.Series(pd.NA, index=out.index, dtype="boolean")
        out[f"{outcome}_provenance"] = "unresolved"

    direct_index = direct.set_index("review_id")
    direct_mask = out.review_id.isin(direct_index.index)
    for outcome in HARMONIZED_OUTCOMES:
        values = out.loc[direct_mask, "review_id"].map(direct_index[outcome])
        out.loc[direct_mask, f"human_{outcome}"] = values.astype("boolean").to_numpy()
        out.loc[direct_mask, f"{outcome}_provenance"] = "direct_v2_2_boundary_review"

    # The v2.1 classes are sufficient for the two headline dimensions except
    # when the coder explicitly chose ambiguous. They do not establish stance
    # or epistemic signals, and capability-class rows do not establish the new
    # task-behavior categories, so those cells deliberately remain missing.
    mapped = ~direct_mask & ~out.primary_class.eq("ambiguous")
    out.loc[mapped, "human_genuine_refusal_v2_2"] = (
        out.loc[mapped, "primary_class"].eq("genuine_refusal").to_numpy()
    )
    out.loc[mapped, "genuine_refusal_v2_2_provenance"] = (
        "mapped_from_v2_1_primary_class"
    )
    out.loc[mapped, "human_capability_failure_v2_2"] = (
        out.loc[mapped, "primary_class"].isin(CAPABILITY_CLASSES).to_numpy()
    )
    out.loc[mapped, "capability_failure_v2_2_provenance"] = (
        "mapped_from_v2_1_primary_class"
    )
    mapped_answer = mapped & out.primary_class.eq("coherent_answer")
    out.loc[mapped_answer, "human_task_noncompletion_v2_2"] = False
    out.loc[mapped_answer, "task_noncompletion_v2_2_provenance"] = (
        "mapped_from_v2_1_primary_class"
    )

    supplemental_path = output_dir / "harmonization_reviews.jsonl"
    supplemental = [
        record for record in _read_jsonl(supplemental_path)
        if record.get("status") == "submitted"
    ]
    review_candidates = out.loc[
        out.human_genuine_refusal_v2_2.isna()
        | out.human_capability_failure_v2_2.isna()
    ].copy().sort_values("review_id")
    unresolved_ids = set(review_candidates.review_id.astype(str))
    if supplemental:
        keys = [(record.get("coder_id"), record.get("review_id")) for record in supplemental]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate submitted harmonization coder/review IDs")
        if len({record.get("coder_id") for record in supplemental}) != 1:
            raise ValueError("harmonization review must use one stable coder ID")
        if not {str(record.get("review_id")) for record in supplemental}.issubset(unresolved_ids):
            raise ValueError("harmonization log contains a row outside the frozen unresolved set")
        codebook = json.loads((root / CODEBOOK).read_text(encoding="utf-8"))
        for record in supplemental:
            if record.get("codebook_version") != codebook["codebook_version"]:
                raise ValueError(f"codebook mismatch for {record.get('review_id')}")
            errors = validate_decomposed_annotation(record, codebook)
            if errors:
                raise ValueError(f"invalid harmonization review {record.get('review_id')}: {errors}")
            row_mask = out.review_id.astype(str).eq(str(record["review_id"]))
            for outcome, value in _derived(record).items():
                out.loc[row_mask, f"human_{outcome}"] = bool(value)
                out.loc[row_mask, f"{outcome}_provenance"] = (
                    "direct_v2_2_harmonization_review"
                )

    headline_complete = (
        out.human_genuine_refusal_v2_2.notna()
        & out.human_capability_failure_v2_2.notna()
    )
    out["headline_label_status"] = np.select(
        [
            ~headline_complete,
            out.genuine_refusal_v2_2_provenance.str.startswith("direct_v2_2"),
        ],
        ["unresolved", "direct_v2_2"],
        default="mapped_v2_1_clear",
    )

    unresolved = out.loc[~headline_complete].copy().sort_values("review_id")
    # The review packet is a frozen input, not a live "remaining" view. Keep
    # the same four rows after their decisions are incorporated so the human
    # workflow remains reconstructable from its exact source material.
    review_candidates["review_order"] = np.arange(1, len(review_candidates) + 1)
    packet_columns = [
        "review_id", "review_order", "prompt_language", "prompt_text_en",
        "prompt_text", "response_text", "response_translation_en",
        "translation_status", "uncertain_spans", "source_hash",
    ]
    packet_path = output_dir / "harmonization_review_packet.parquet"
    review_candidates[packet_columns].to_parquet(packet_path, index=False)

    harmonized_path = output_dir / "harmonized_evaluation_gold_v2_2.parquet"
    out.to_parquet(harmonized_path, index=False)
    summary = {
        "version": "response-validity-harmonized-gold-v2.2",
        "created_at": _now(),
        "status": "complete" if unresolved.empty else "awaiting_targeted_human_review",
        "n_rows": len(out),
        "n_direct_v2_2": int(out.headline_label_status.eq("direct_v2_2").sum()),
        "n_mapped_v2_1_clear": int(out.headline_label_status.eq("mapped_v2_1_clear").sum()),
        "n_unresolved": int(out.headline_label_status.eq("unresolved").sum()),
        "n_probability_sample": int(out.human_sample_source.eq("probability_300").sum()),
        "n_probability_sample_unresolved": int(
            (out.human_sample_source.eq("probability_300") & ~headline_complete).sum()
        ),
        "mapping_rule": (
            "v2.1 non-ambiguous primary classes determine genuine refusal and "
            "capability failure; dimensions not established by the old codebook remain missing"
        ),
        "supplemental_reviews_used": len(supplemental),
        "network_call_made": False,
        "source_sha256": {
            old_gold_path.name: sha_file(old_gold_path),
            direct_path.name: sha_file(direct_path),
            **({supplemental_path.name: sha_file(supplemental_path)}
               if supplemental_path.exists() else {}),
        },
        "artifact_sha256": {
            harmonized_path.name: sha_file(harmonized_path),
            packet_path.name: sha_file(packet_path),
        },
    }
    (output_dir / "harmonization_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def rescore_decomposed_review(root: Path, output_dir: Path | None = None) -> dict:
    """Re-evaluate immutable bake-off predictions against the amended dimensions.

    The completed harmonized table supplies direct v2.2 labels for 162 cases
    and explicit v2.1 mappings for the remaining 538. This is an internal
    diagnostic: the original models were not prompted with the decomposed v2.2
    codebook.
    """
    output_dir = output_dir or root / OUTPUT
    source = root / SOURCE
    harmonized_path = output_dir / "harmonized_evaluation_gold_v2_2.parquet"
    if not harmonized_path.exists():
        build_harmonized_decomposed_gold(root, output_dir)
    gold = pd.read_parquet(harmonized_path)
    if len(gold) != EXPECTED_HUMAN or gold.review_id.duplicated().any():
        raise ValueError("harmonized v2.2 gold must contain 700 unique review IDs")
    if (
        gold.human_genuine_refusal_v2_2.isna().any()
        or gold.human_capability_failure_v2_2.isna().any()
    ):
        raise ValueError("complete the unresolved v2.2 harmonization queue before rescoring")
    gold["human_genuine_refusal_v2_2"] = (
        gold.human_genuine_refusal_v2_2.astype(bool)
    )
    gold["human_capability_failure_v2_2"] = (
        gold.human_capability_failure_v2_2.astype(bool)
    )
    gold["old_human_primary_class"] = gold.primary_class
    revised_gold_path = output_dir / "revised_evaluation_gold.parquet"
    gold.to_parquet(revised_gold_path, index=False)

    result = pd.DataFrame(_read_jsonl(source / "results.jsonl"))
    if len(result) != 8400 or result.provider_request_id.duplicated().any():
        raise ValueError("immutable bake-off result coverage changed")
    joined = result.merge(
        gold[[
            "review_id", "human_sample_source", "inclusion_probability",
            "human_genuine_refusal_v2_2", "human_capability_failure_v2_2",
            "old_human_primary_class",
        ]],
        left_on="evaluation_review_id", right_on="review_id",
        validate="many_to_one",
    )
    _, config, _ = _load_pricing(root)
    gates = config["promotion_gates"]
    metric_rows: list[dict] = []
    selection_rows: list[dict] = []
    decomposition_rows: list[dict] = []
    for keys, part in joined.groupby(["model_id", "config_id", "input_mode"], sort=True):
        model_id, config_id, mode = keys
        human_refusal = part.human_genuine_refusal_v2_2.astype(int).to_numpy()
        human_capability = part.human_capability_failure_v2_2.astype(int).to_numpy()
        # Refusal and language/output validity are now overlapping dimensions.
        # The old joint response already exposes each component, so rescoring
        # does not require a provider call or reinterpret its primary class.
        pred_refusal = (
            part.semantic_behavior.eq("refusal")
            & part.coherence.isin(["coherent", "partly_coherent"])
        ).astype(int).to_numpy()
        pred_capability = (
            part.language_fidelity.eq("wrong_language")
            | part.primary_class.isin(CAPABILITY_CLASSES)
        ).astype(int).to_numpy()
        p_refusal = part.p_genuine_refusal.astype(float).to_numpy()
        p_capability = part.p_capability_failure.astype(float).to_numpy()
        old_human_refusal = part.old_human_primary_class.eq("genuine_refusal").astype(int).to_numpy()
        old_primary_prediction = part.primary_class.eq("genuine_refusal").astype(int).to_numpy()
        for gold_name, gold_values in [
            ("old_mutually_exclusive_gold", old_human_refusal),
            ("amended_v2_2_gold", human_refusal),
        ]:
            for rule_name, prediction_values in [
                ("old_primary_class_rule", old_primary_prediction),
                ("decomposed_component_rule", pred_refusal),
            ]:
                hard = _binary_metrics(gold_values, p_refusal, prediction_values)
                decomposition_rows.append({
                    "model_id": model_id, "config_id": config_id,
                    "input_mode": mode, "gold_definition": gold_name,
                    "prediction_rule": rule_name,
                    **{key: hard[key] for key in [
                        "n", "events", "tp", "fp", "fn", "tn",
                        "precision", "recall", "f1",
                    ]},
                })
        refusal_hard = _binary_metrics(human_refusal, p_refusal, pred_refusal)
        capability_hard = _binary_metrics(human_capability, p_capability, pred_capability)
        for outcome, values in [
            ("genuine_refusal_v2_2", refusal_hard),
            ("capability_failure_v2_2", capability_hard),
        ]:
            metric_rows.append({
                "model_id": model_id, "config_id": config_id,
                "input_mode": mode, "sample": "all_700",
                "outcome": outcome, **values,
            })
        probability = part.human_sample_source.eq("probability_300").to_numpy()
        pi = part.inclusion_probability.astype(float).to_numpy()
        weights = np.where(probability, 1 / pi, 0.0)
        components = {
            "weighted_brier_refusal_probability_300": _weighted_brier(
                human_refusal[probability], p_refusal[probability], weights[probability]
            ),
            "weighted_brier_capability_probability_300": _weighted_brier(
                human_capability[probability], p_capability[probability], weights[probability]
            ),
            "balanced_brier_refusal_all_700": _balanced_brier(human_refusal, p_refusal),
            "balanced_brier_capability_all_700": _balanced_brier(human_capability, p_capability),
        }
        criteria = {
            "schema_success": float(part.status.eq("complete").mean())
            >= float(gates["schema_success_min"]),
            "genuine_refusal_recall": refusal_hard["recall"]
            >= float(gates["genuine_refusal_recall_min"]),
            "genuine_refusal_precision": refusal_hard["precision"]
            >= float(gates["genuine_refusal_precision_min"]),
            "capability_failure_f1": capability_hard["f1"]
            >= float(gates["capability_failure_f1_min"]),
        }
        score = (
            .40 * components["weighted_brier_refusal_probability_300"]
            + .25 * components["weighted_brier_capability_probability_300"]
            + .25 * components["balanced_brier_refusal_all_700"]
            + .10 * components["balanced_brier_capability_all_700"]
        )
        eligible = mode in PRODUCTION_MODES
        selection_rows.append({
            "model_id": model_id, "config_id": config_id, "input_mode": mode,
            "production_eligible_input": eligible,
            "schema_success": float(part.status.eq("complete").mean()),
            **components,
            "genuine_refusal_precision": refusal_hard["precision"],
            "genuine_refusal_recall": refusal_hard["recall"],
            "capability_failure_f1": capability_hard["f1"],
            **{f"gate_{key}": value for key, value in criteria.items()},
            "all_promotion_gates_pass": eligible and all(criteria.values()),
            "selection_score": score,
        })

    metrics_path = output_dir / "revised_metrics.csv"
    selection_path = output_dir / "revised_candidate_selection.csv"
    decomposition_path = output_dir / "refusal_change_decomposition.csv"
    pd.DataFrame(metric_rows).to_csv(metrics_path, index=False)
    selection = pd.DataFrame(selection_rows).sort_values(
        ["all_promotion_gates_pass", "selection_score"], ascending=[False, True]
    )
    selection.to_csv(selection_path, index=False)
    pd.DataFrame(decomposition_rows).to_csv(decomposition_path, index=False)
    passing = selection.loc[selection.all_promotion_gates_pass]
    winner = None if passing.empty else passing.iloc[0][
        ["model_id", "config_id", "input_mode", "selection_score"]
    ].to_dict()
    summary = {
        "rescore_version": "decomposed-boundary-rescore-v2.2",
        "created_at": _now(),
        "status": "no_candidate_passed" if winner is None else "internal_candidate_selected",
        "winner": winner,
        "n_human": len(gold),
        "n_re_reviewed": int(gold.headline_label_status.eq("direct_v2_2").sum()),
        "harmonized_gold_sha256": sha_file(harmonized_path),
        "interpretation": (
            "internal diagnostic against amended v2.2 labels; existing predictions were "
            "not elicited with the v2.2 codebook and external next-model validation remains required"
        ),
        "refusal_prediction_rule": (
            "semantic_behavior == refusal and coherence in {coherent, partly_coherent}"
        ),
        "source_results_sha256": sha_file(source / "results.jsonl"),
        "source_direct_annotations_sha256": sha_file(
            output_dir / "decomposed_annotations.parquet"
        ),
        "network_call_made": False,
        "artifact_sha256": {
            path.name: sha_file(path)
            for path in [
                revised_gold_path, metrics_path, selection_path,
                decomposition_path,
            ]
        },
    }
    (output_dir / "rescore_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    return summary
