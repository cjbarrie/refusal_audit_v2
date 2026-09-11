"""Development-only access and sealed support gating for refinement v2.

The source human log contains both development and evaluation judgments.  This
module obtains evaluation membership from the label-blind frozen design first,
then extracts each review ID from the raw JSONL line without deserializing the
outcome.  Only development lines are parsed into analytical objects.  New
evaluation lines are committed by hash; a separate support gate may inspect
only the three predeclared aggregate support conditions and emits booleans, not
counts, rows, labels, or examples.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .human_pilot import sha_file, validate_human_label


REVIEW_ID_PATTERN = re.compile(r'"review_id"\s*:\s*"([^"\\]+)"')
EXPECTED_LABELS = 300
EXPECTED_DEVELOPMENT = 122
EXPECTED_EVALUATION = 178
EXPECTED_NEW_DEVELOPMENT = 38
EXPECTED_NEW_EVALUATION = 62
EXPECTED_LABELS_FULL = 400
EXPECTED_DEVELOPMENT_FULL = 161
EXPECTED_EVALUATION_FULL = 239
EXPECTED_REFINEMENT_EVALUATION = 123
EXPECTED_FINAL_DEVELOPMENT = 39
EXPECTED_FINAL_EVALUATION = 61
EXPECTED_SPENT_EVALUATION = 116
CAPABILITY_CLASSES = {
    "incoherent_garbled", "wrong_language", "technical_degeneration"
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json_sha(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _line_index(path: Path) -> dict[str, str]:
    """Index exact JSONL text by ID without parsing any outcome field."""
    indexed: dict[str, str] = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = REVIEW_ID_PATTERN.search(line)
        if match is None:
            raise ValueError(f"{path}: no review_id on line {line_no}")
        review_id = match.group(1)
        if review_id in indexed:
            raise ValueError(f"{path}: duplicate review_id {review_id}")
        indexed[review_id] = line
    return indexed


def _record_commitment(lines: dict[str, str], ids: set[str]) -> str:
    entries = [
        f"{review_id}\t{hashlib.sha256(lines[review_id].encode('utf-8')).hexdigest()}"
        for review_id in sorted(ids)
    ]
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def _verify_storage_inputs(root: Path, wave_dir: Path) -> tuple[Path, dict]:
    freeze = wave_dir / "storage_freeze_300_v1"
    labels_path = freeze / "human_labels_first_300.jsonl"
    manifest_path = freeze / "storage_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest["artifact_sha256"][labels_path.name]
    if sha_file(labels_path) != expected:
        raise RuntimeError("300-row storage freeze differs from its manifest")
    if manifest.get("n_records") != EXPECTED_LABELS:
        raise ValueError("storage freeze is not exactly 300 records")
    inputs = {
        "wave_design.parquet": wave_dir / "wave_design.parquet",
        "human_review_packet.parquet": wave_dir / "human_review_packet.parquet",
        "response_validity_codebook_v2.json": (
            root / "config" / "response_validity_codebook_v2.json"
        ),
        "storage_manifest.json": manifest_path,
        "human_labels_first_300.jsonl": labels_path,
        "support_gate_config.json": (
            root / "config" / "surrogate_refinement_support_gate_v1.json"
        ),
    }
    for path in inputs.values():
        if not path.exists():
            raise FileNotFoundError(path)
    return labels_path, {name: sha_file(path) for name, path in inputs.items()}


def freeze_enrichment_storage_400(
    root: Path, wave_dir: Path, output_dir: Path | None = None
) -> dict:
    """Create a byte-identical, hash-verified receipt for all 400 submissions.

    This function validates every label for storage integrity, but it emits no
    class counts and does not create an analysis table.  Development/evaluation
    membership remains governed by the previously frozen wave design.
    """
    output_dir = output_dir or wave_dir / "storage_freeze_400_v1"
    manifest_path = output_dir / "storage_manifest.json"
    frozen_labels = output_dir / "human_labels_all_400.jsonl"
    live_labels = wave_dir / "human_labels.jsonl"
    design_path = wave_dir / "wave_design.parquet"
    codebook_path = root / "config" / "response_validity_codebook_v2.json"
    gate_path = root / "config" / "human_enrichment_review_gate_v2.json"
    previous_manifest_path = (
        wave_dir / "storage_freeze_300_v1" / "storage_manifest.json"
    )
    previous_labels_path = (
        wave_dir / "storage_freeze_300_v1" / "human_labels_first_300.jsonl"
    )
    required = [
        live_labels, design_path, codebook_path, gate_path,
        previous_manifest_path, previous_labels_path,
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)

    input_sha = {
        "human_labels.jsonl": sha_file(live_labels),
        "wave_design.parquet": sha_file(design_path),
        "response_validity_codebook_v2.json": sha_file(codebook_path),
        "human_enrichment_review_gate_v2.json": sha_file(gate_path),
        "storage_freeze_300_v1/storage_manifest.json": sha_file(previous_manifest_path),
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_sha:
            raise RuntimeError("completed 400-row log changed after storage freeze")
        for name, digest in manifest.get("artifact_sha256", {}).items():
            if sha_file(output_dir / name) != digest:
                raise RuntimeError(f"400-row storage artifact changed: {name}")
        return manifest
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"partial 400-row storage directory: {output_dir}")

    design = pd.read_parquet(design_path).sort_values("review_order")
    if (
        len(design) != EXPECTED_LABELS_FULL
        or design.review_id.duplicated().any()
        or design.review_order.tolist() != list(range(1, EXPECTED_LABELS_FULL + 1))
    ):
        raise ValueError("wave design is not exactly review orders 1-400")
    split_counts = design.analysis_split.value_counts().to_dict()
    if split_counts != {
        "development": EXPECTED_DEVELOPMENT_FULL,
        "evaluation": EXPECTED_EVALUATION_FULL,
    }:
        raise ValueError(f"unexpected full-wave split counts: {split_counts}")

    raw_lines = [
        line for line in live_labels.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    line_index = _line_index(live_labels)
    if len(raw_lines) != EXPECTED_LABELS_FULL or set(line_index) != set(
        design.review_id.astype(str)
    ):
        raise ValueError("live labels do not exactly cover the 400-row design")
    order_by_id = dict(zip(design.review_id.astype(str), design.review_order.astype(int)))
    observed_orders = [
        order_by_id[REVIEW_ID_PATTERN.search(line).group(1)] for line in raw_lines
    ]
    if observed_orders != list(range(1, EXPECTED_LABELS_FULL + 1)):
        raise ValueError("live label lines are not in contiguous review order 1-400")

    previous_lines = [
        line for line in previous_labels_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if raw_lines[:EXPECTED_LABELS] != previous_lines:
        raise RuntimeError("the first 300 live records differ from storage_freeze_300_v1")

    codebook = json.loads(codebook_path.read_text(encoding="utf-8"))
    last_submission = None
    for line in raw_lines:
        record = json.loads(line)
        fields = {
            key: record.get(key) for key in [*codebook["fields"], "evidence_span"]
        }
        errors = validate_human_label(fields, codebook)
        if errors:
            raise ValueError(f"invalid completed label {record['review_id']}: {errors}")
        if record.get("status") != "submitted":
            raise ValueError(f"non-submitted completed label {record['review_id']}")
        last_submission = record.get("submitted_at")

    output_dir.mkdir(parents=True, exist_ok=False)
    frozen_labels.write_bytes(live_labels.read_bytes())
    manifest = {
        "freeze_version": "human-enrichment-storage-freeze-400-v1.0",
        "created_at": _now(),
        "purpose": (
            "Durable, byte-identical receipt for completed review orders 1-400 "
            "before the final development/evaluation access step."
        ),
        "status": "complete_storage_freeze; final analytical split not emitted",
        "membership_rule": "exact live append-only log after review orders 1-400 completed",
        "n_records": EXPECTED_LABELS_FULL,
        "n_unique_review_ids": EXPECTED_LABELS_FULL,
        "review_order_min": 1,
        "review_order_max": EXPECTED_LABELS_FULL,
        "review_orders_contiguous": True,
        "all_status_submitted": True,
        "parse_errors": 0,
        "validation_errors": 0,
        "missing_design_joins": 0,
        "first_300_equal_storage_freeze_300_v1": True,
        "final_block_records": 100,
        "codebook_version": codebook.get("codebook_version"),
        "last_submission_at": last_submission,
        "previously_open_development_records": EXPECTED_DEVELOPMENT,
        "final_development_labels_opened_for_analysis": False,
        "final_evaluation_labels_opened_for_analysis": False,
        "population_prevalence_use_authorized": False,
        "dsl_residual_correction_use_authorized": False,
        "artifact_sha256": {frozen_labels.name: sha_file(frozen_labels)},
        "input_sha256": input_sha,
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def freeze_refinement_access_v1(
    root: Path, wave_dir: Path, output_dir: Path | None = None
) -> dict:
    """Freeze 122 development rows and commitments for sealed evaluation rows."""
    output_dir = output_dir or wave_dir / "refinement_v2" / "access_v1"
    manifest_path = output_dir / "access_manifest.json"
    labels_path, input_sha = _verify_storage_inputs(root, wave_dir)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_sha:
            raise RuntimeError("refinement accessor inputs changed after freeze")
        for name, digest in manifest.get("artifact_sha256", {}).items():
            if sha_file(output_dir / name) != digest:
                raise RuntimeError(f"refinement artifact changed: {name}")
        return manifest
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"partial refinement access directory: {output_dir}")

    design = pd.read_parquet(wave_dir / "wave_design.parquet")
    design = design.loc[design.review_order.le(300)].copy()
    if len(design) != EXPECTED_LABELS or design.review_id.duplicated().any():
        raise ValueError("review-order 1-300 design is incomplete or duplicated")
    split_counts = design.analysis_split.value_counts().to_dict()
    if split_counts != {
        "development": EXPECTED_DEVELOPMENT, "evaluation": EXPECTED_EVALUATION
    }:
        raise ValueError(f"unexpected 1-300 split counts: {split_counts}")
    new = design.loc[design.review_order.between(201, 300)]
    new_counts = new.analysis_split.value_counts().to_dict()
    if new_counts != {
        "development": EXPECTED_NEW_DEVELOPMENT,
        "evaluation": EXPECTED_NEW_EVALUATION,
    }:
        raise ValueError(f"unexpected 201-300 split counts: {new_counts}")

    line_index = _line_index(labels_path)
    if set(line_index) != set(design.review_id.astype(str)):
        raise ValueError("storage labels do not exactly cover design orders 1-300")
    development_ids = set(
        design.loc[design.analysis_split.eq("development"), "review_id"].astype(str)
    )
    evaluation_ids = set(
        design.loc[design.analysis_split.eq("evaluation"), "review_id"].astype(str)
    )
    new_evaluation_ids = set(
        new.loc[new.analysis_split.eq("evaluation"), "review_id"].astype(str)
    )
    if development_ids & evaluation_ids:
        raise ValueError("development/evaluation memberships overlap")

    # Outcome JSON is deserialized only for IDs already known to be development.
    codebook = json.loads(
        (root / "config" / "response_validity_codebook_v2.json").read_text(encoding="utf-8")
    )
    development_records: list[dict] = []
    for review_id in sorted(development_ids):
        record = json.loads(line_index[review_id])
        fields = {
            key: record.get(key)
            for key in [*codebook["fields"], "evidence_span"]
        }
        errors = validate_human_label(fields, codebook)
        if errors:
            raise ValueError(f"invalid development label {review_id}: {errors}")
        development_records.append(record)
    labels = pd.DataFrame(development_records)
    packet = pd.read_parquet(wave_dir / "human_review_packet.parquet")
    design_columns = [
        column for column in design.columns
        if column not in packet.columns and column != "analysis_split"
    ]
    cases = packet.merge(
        design.loc[design.analysis_split.eq("development"), [
            "review_id", "analysis_split", *design_columns
        ]],
        on="review_id", validate="one_to_one",
    ).merge(labels, on="review_id", validate="one_to_one", suffixes=("", "_label"))
    if len(cases) != EXPECTED_DEVELOPMENT or not cases.analysis_split.eq("development").all():
        raise ValueError("development case assembly escaped its split")

    output_dir.mkdir(parents=True, exist_ok=False)
    labels_out = output_dir / "development_labels.jsonl"
    cases_out = output_dir / "development_cases.parquet"
    diagnostics_out = output_dir / "development_class_counts.csv"
    commitment_out = output_dir / "sealed_evaluation_commitment.json"
    with labels_out.open("w", encoding="utf-8") as handle:
        for record in sorted(development_records, key=lambda row: row["review_id"]):
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    cases.sort_values("review_order").to_parquet(cases_out, index=False)
    cases.groupby(
        ["prompt_language", "primary_class"], observed=True
    ).size().rename("n").reset_index().sort_values(
        ["prompt_language", "primary_class"]
    ).to_csv(diagnostics_out, index=False)
    commitment = {
        "commitment_version": "surrogate-refinement-sealed-evaluation-v1.0",
        "created_at": _now(),
        "new_evaluation_membership": "review_order 201-300 and analysis_split evaluation",
        "n_new_evaluation": len(new_evaluation_ids),
        "n_all_evaluation_orders_1_300": len(evaluation_ids),
        "new_evaluation_ids_sha256": _canonical_json_sha(sorted(new_evaluation_ids)),
        "new_evaluation_record_commitment_sha256": _record_commitment(
            line_index, new_evaluation_ids
        ),
        "evaluation_outcome_rows_emitted": False,
        "evaluation_outcome_counts_emitted": False,
    }
    commitment_out.write_text(json.dumps(commitment, indent=2), encoding="utf-8")
    artifacts = [labels_out, cases_out, diagnostics_out, commitment_out]
    manifest = {
        "access_version": "surrogate-refinement-development-access-v1.0",
        "created_at": _now(),
        "status": "development_open; new_evaluation_sealed",
        "n_development": len(cases),
        "n_new_development": EXPECTED_NEW_DEVELOPMENT,
        "n_new_evaluation_sealed": EXPECTED_NEW_EVALUATION,
        "development_prompt_groups": int(cases.prompt_id.nunique()),
        "evaluation_fields_in_development_artifacts": False,
        "evaluation_rows_deserialized": False,
        "input_sha256": input_sha,
        "artifact_sha256": {path.name: sha_file(path) for path in artifacts},
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def run_sealed_support_gate_v1(
    root: Path, wave_dir: Path, output_dir: Path | None = None
) -> dict:
    """Emit only predeclared threshold booleans for the 62 new evaluation rows."""
    output_dir = output_dir or wave_dir / "refinement_v2" / "access_v1"
    access = freeze_refinement_access_v1(root, wave_dir, output_dir)
    gate_path = root / "config" / "surrogate_refinement_support_gate_v1.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    result_path = output_dir / "support_gate_result.json"
    if result_path.exists():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if (
            existing.get("gate_config_sha256") != sha_file(gate_path)
            or existing.get("access_manifest_sha256")
            != sha_file(output_dir / "access_manifest.json")
        ):
            raise RuntimeError("support gate inputs changed after execution")
        return existing

    design = pd.read_parquet(wave_dir / "wave_design.parquet")
    membership = design.loc[
        design.review_order.between(201, 300)
        & design.analysis_split.eq("evaluation"),
        ["review_id", "prompt_language"],
    ].copy()
    if len(membership) != EXPECTED_NEW_EVALUATION:
        raise ValueError("support gate membership is not exactly 62 rows")
    labels_path = wave_dir / "storage_freeze_300_v1" / "human_labels_first_300.jsonl"
    lines = _line_index(labels_path)
    rows = []
    for item in membership.itertuples(index=False):
        # This is the only function permitted to deserialize new evaluation
        # outcomes before model scoring, and it returns threshold booleans only.
        label = json.loads(lines[str(item.review_id)])
        rows.append({
            "prompt_language": str(item.prompt_language),
            "primary_class": label["primary_class"],
        })
    frame = pd.DataFrame(rows)
    thresholds = gate["thresholds"]
    actual = {
        "genuine_refusal": int(frame.primary_class.eq("genuine_refusal").sum()),
        "non_english_genuine_refusal": int((
            frame.primary_class.eq("genuine_refusal")
            & frame.prompt_language.ne("en")
        ).sum()),
        "capability_failure": int(frame.primary_class.isin(CAPABILITY_CLASSES).sum()),
    }
    criteria = {
        key: actual[key] >= int(thresholds[key]) for key in thresholds
    }
    commitment = json.loads(
        (output_dir / "sealed_evaluation_commitment.json").read_text(encoding="utf-8")
    )
    result = {
        "result_version": "surrogate-refinement-support-gate-result-v1.0",
        "executed_at": _now(),
        "evaluation_commitment_sha256": commitment[
            "new_evaluation_record_commitment_sha256"
        ],
        "n_evaluation": EXPECTED_NEW_EVALUATION,
        "thresholds": thresholds,
        "criteria_met": criteria,
        "support_pass": all(criteria.values()),
        "failure_action": gate["failure_action"],
        "exact_counts_emitted": False,
        "evaluation_rows_emitted": False,
        "gate_config_sha256": sha_file(gate_path),
        "access_manifest_sha256": sha_file(output_dir / "access_manifest.json"),
        "network_call_made": False,
    }
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _verify_storage_inputs_v2(root: Path, wave_dir: Path) -> tuple[Path, dict]:
    freeze = wave_dir / "storage_freeze_400_v1"
    labels_path = freeze / "human_labels_all_400.jsonl"
    manifest_path = freeze / "storage_manifest.json"
    manifest = freeze_enrichment_storage_400(root, wave_dir, freeze)
    expected = manifest["artifact_sha256"][labels_path.name]
    if sha_file(labels_path) != expected:
        raise RuntimeError("400-row storage freeze differs from its manifest")
    if manifest.get("n_records") != EXPECTED_LABELS_FULL:
        raise ValueError("storage freeze is not exactly 400 records")
    inputs = {
        "wave_design.parquet": wave_dir / "wave_design.parquet",
        "human_review_packet.parquet": wave_dir / "human_review_packet.parquet",
        "response_validity_codebook_v2.json": (
            root / "config" / "response_validity_codebook_v2.json"
        ),
        "storage_freeze_400_v1/storage_manifest.json": manifest_path,
        "storage_freeze_400_v1/human_labels_all_400.jsonl": labels_path,
        "support_gate_config_v2.json": (
            root / "config" / "surrogate_refinement_support_gate_v2.json"
        ),
        "previous_access_manifest.json": (
            wave_dir / "refinement_v2" / "access_v1" / "access_manifest.json"
        ),
        "previous_evaluation_commitment.json": (
            wave_dir / "refinement_v2" / "access_v1"
            / "sealed_evaluation_commitment.json"
        ),
    }
    for path in inputs.values():
        if not path.exists():
            raise FileNotFoundError(path)
    return labels_path, {name: sha_file(path) for name, path in inputs.items()}


def freeze_refinement_access_v2(
    root: Path, wave_dir: Path, output_dir: Path | None = None
) -> dict:
    """Emit all 161 development rows and commit the 123-case sealed reserve."""
    output_dir = output_dir or wave_dir / "refinement_v2" / "access_v2"
    manifest_path = output_dir / "access_manifest.json"
    labels_path, input_sha = _verify_storage_inputs_v2(root, wave_dir)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_sha:
            raise RuntimeError("refinement-v2 accessor inputs changed after freeze")
        for name, digest in manifest.get("artifact_sha256", {}).items():
            if sha_file(output_dir / name) != digest:
                raise RuntimeError(f"refinement-v2 artifact changed: {name}")
        return manifest
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"partial refinement-v2 access directory: {output_dir}")

    design = pd.read_parquet(wave_dir / "wave_design.parquet").copy()
    if len(design) != EXPECTED_LABELS_FULL or design.review_id.duplicated().any():
        raise ValueError("full 400-row design is incomplete or duplicated")
    split_counts = design.analysis_split.value_counts().to_dict()
    if split_counts != {
        "development": EXPECTED_DEVELOPMENT_FULL,
        "evaluation": EXPECTED_EVALUATION_FULL,
    }:
        raise ValueError(f"unexpected full-wave split counts: {split_counts}")
    final = design.loc[design.review_order.between(301, 400)]
    final_counts = final.analysis_split.value_counts().to_dict()
    if final_counts != {
        "development": EXPECTED_FINAL_DEVELOPMENT,
        "evaluation": EXPECTED_FINAL_EVALUATION,
    }:
        raise ValueError(f"unexpected 301-400 split counts: {final_counts}")

    line_index = _line_index(labels_path)
    if set(line_index) != set(design.review_id.astype(str)):
        raise ValueError("storage labels do not exactly cover design orders 1-400")
    development_ids = set(
        design.loc[design.analysis_split.eq("development"), "review_id"].astype(str)
    )
    spent_evaluation_ids = set(
        design.loc[
            design.review_order.le(200) & design.analysis_split.eq("evaluation"),
            "review_id",
        ].astype(str)
    )
    reserve_evaluation_ids = set(
        design.loc[
            design.review_order.between(201, 400)
            & design.analysis_split.eq("evaluation"),
            "review_id",
        ].astype(str)
    )
    if len(spent_evaluation_ids) != EXPECTED_SPENT_EVALUATION:
        raise ValueError("spent evaluation membership is not exactly 116 rows")
    if len(reserve_evaluation_ids) != EXPECTED_REFINEMENT_EVALUATION:
        raise ValueError("refinement evaluation reserve is not exactly 123 rows")
    if development_ids & (spent_evaluation_ids | reserve_evaluation_ids):
        raise ValueError("development/evaluation memberships overlap")

    previous_commitment = json.loads((
        wave_dir / "refinement_v2" / "access_v1"
        / "sealed_evaluation_commitment.json"
    ).read_text(encoding="utf-8"))
    old_reserve_ids = set(
        design.loc[
            design.review_order.between(201, 300)
            & design.analysis_split.eq("evaluation"),
            "review_id",
        ].astype(str)
    )
    old_commitment = _record_commitment(line_index, old_reserve_ids)
    if old_commitment != previous_commitment["new_evaluation_record_commitment_sha256"]:
        raise RuntimeError("orders 201-300 evaluation commitment changed")

    codebook = json.loads(
        (root / "config" / "response_validity_codebook_v2.json").read_text(
            encoding="utf-8"
        )
    )
    development_records: list[dict] = []
    for review_id in sorted(development_ids):
        record = json.loads(line_index[review_id])
        fields = {
            key: record.get(key) for key in [*codebook["fields"], "evidence_span"]
        }
        errors = validate_human_label(fields, codebook)
        if errors:
            raise ValueError(f"invalid development label {review_id}: {errors}")
        development_records.append(record)
    labels = pd.DataFrame(development_records)
    packet = pd.read_parquet(wave_dir / "human_review_packet.parquet")
    design_columns = [
        column for column in design.columns
        if column not in packet.columns and column != "analysis_split"
    ]
    cases = packet.merge(
        design.loc[design.analysis_split.eq("development"), [
            "review_id", "analysis_split", *design_columns
        ]],
        on="review_id", validate="one_to_one",
    ).merge(labels, on="review_id", validate="one_to_one", suffixes=("", "_label"))
    if (
        len(cases) != EXPECTED_DEVELOPMENT_FULL
        or not cases.analysis_split.eq("development").all()
    ):
        raise ValueError("development case assembly escaped its split")

    output_dir.mkdir(parents=True, exist_ok=False)
    labels_out = output_dir / "development_labels.jsonl"
    cases_out = output_dir / "development_cases.parquet"
    diagnostics_out = output_dir / "development_class_counts.csv"
    commitment_out = output_dir / "sealed_evaluation_commitment.json"
    with labels_out.open("w", encoding="utf-8") as handle:
        for record in sorted(development_records, key=lambda row: row["review_id"]):
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    cases.sort_values("review_order").to_parquet(cases_out, index=False)
    cases.groupby(
        ["prompt_language", "primary_class"], observed=True
    ).size().rename("n").reset_index().sort_values(
        ["prompt_language", "primary_class"]
    ).to_csv(diagnostics_out, index=False)
    commitment = {
        "commitment_version": "surrogate-refinement-sealed-evaluation-v2.0",
        "created_at": _now(),
        "evaluation_membership": "review_order 201-400 and analysis_split evaluation",
        "n_sealed_evaluation": len(reserve_evaluation_ids),
        "n_previously_spent_evaluation": len(spent_evaluation_ids),
        "sealed_evaluation_ids_sha256": _canonical_json_sha(
            sorted(reserve_evaluation_ids)
        ),
        "sealed_evaluation_record_commitment_sha256": _record_commitment(
            line_index, reserve_evaluation_ids
        ),
        "orders_201_300_commitment_verified": True,
        "evaluation_outcome_rows_emitted": False,
        "evaluation_outcome_counts_emitted": False,
    }
    commitment_out.write_text(json.dumps(commitment, indent=2), encoding="utf-8")
    artifacts = [labels_out, cases_out, diagnostics_out, commitment_out]
    manifest = {
        "access_version": "surrogate-refinement-development-access-v2.0",
        "created_at": _now(),
        "status": "all_development_open; evaluation_reserve_sealed",
        "n_development": len(cases),
        "n_added_development": EXPECTED_FINAL_DEVELOPMENT,
        "n_evaluation_sealed": EXPECTED_REFINEMENT_EVALUATION,
        "n_added_evaluation_sealed": EXPECTED_FINAL_EVALUATION,
        "development_prompt_groups": int(cases.prompt_id.nunique()),
        "evaluation_fields_in_development_artifacts": False,
        "evaluation_rows_deserialized": False,
        "input_sha256": input_sha,
        "artifact_sha256": {path.name: sha_file(path) for path in artifacts},
        "network_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def run_sealed_support_gate_v2(
    root: Path, wave_dir: Path, output_dir: Path | None = None
) -> dict:
    """Emit threshold booleans, never outcome counts, for the 123-case reserve."""
    output_dir = output_dir or wave_dir / "refinement_v2" / "access_v2"
    freeze_refinement_access_v2(root, wave_dir, output_dir)
    gate_path = root / "config" / "surrogate_refinement_support_gate_v2.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    result_path = output_dir / "support_gate_result.json"
    if result_path.exists():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if (
            existing.get("gate_config_sha256") != sha_file(gate_path)
            or existing.get("access_manifest_sha256")
            != sha_file(output_dir / "access_manifest.json")
        ):
            raise RuntimeError("support-gate-v2 inputs changed after execution")
        return existing

    design = pd.read_parquet(wave_dir / "wave_design.parquet")
    membership = design.loc[
        design.review_order.between(201, 400)
        & design.analysis_split.eq("evaluation"),
        ["review_id", "prompt_language"],
    ].copy()
    if len(membership) != EXPECTED_REFINEMENT_EVALUATION:
        raise ValueError("support-gate-v2 membership is not exactly 123 rows")
    labels_path = (
        wave_dir / "storage_freeze_400_v1" / "human_labels_all_400.jsonl"
    )
    lines = _line_index(labels_path)
    rows = []
    for item in membership.itertuples(index=False):
        # Evaluation outcomes are inspected only inside this function.  The
        # returned and stored result contains threshold booleans, never counts.
        label = json.loads(lines[str(item.review_id)])
        rows.append({
            "prompt_language": str(item.prompt_language),
            "primary_class": label["primary_class"],
        })
    frame = pd.DataFrame(rows)
    thresholds = gate["thresholds"]
    actual = {
        "genuine_refusal": int(frame.primary_class.eq("genuine_refusal").sum()),
        "non_english_genuine_refusal": int((
            frame.primary_class.eq("genuine_refusal")
            & frame.prompt_language.ne("en")
        ).sum()),
        "capability_failure": int(frame.primary_class.isin(CAPABILITY_CLASSES).sum()),
    }
    criteria = {key: actual[key] >= int(thresholds[key]) for key in thresholds}
    commitment = json.loads((
        output_dir / "sealed_evaluation_commitment.json"
    ).read_text(encoding="utf-8"))
    result = {
        "result_version": "surrogate-refinement-support-gate-result-v2.0",
        "executed_at": _now(),
        "evaluation_commitment_sha256": commitment[
            "sealed_evaluation_record_commitment_sha256"
        ],
        "n_evaluation": EXPECTED_REFINEMENT_EVALUATION,
        "thresholds": thresholds,
        "criteria_met": criteria,
        "support_pass": all(criteria.values()),
        "failure_action": gate["failure_action"],
        "success_action": gate["success_action"],
        "exact_counts_emitted": False,
        "evaluation_rows_emitted": False,
        "gate_config_sha256": sha_file(gate_path),
        "access_manifest_sha256": sha_file(output_dir / "access_manifest.json"),
        "network_call_made": False,
    }
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
