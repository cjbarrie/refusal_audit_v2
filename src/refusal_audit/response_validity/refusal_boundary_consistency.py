"""Freeze and assemble the targeted refusal-boundary consistency review.

This is a local instrument audit, not a probability sample. It isolates Luna
genuine-refusal positives that also carry an epistemic-limitation or
stance-disclaimer flag. Four rows already received a visible-label human
decision in the nine-case Luna--Sol disagreement review; those decisions are
carried forward without asking the reviewer to repeat them. The remaining 20
rows form the Streamlit queue.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .human_pilot import sha_file


DEFAULT_DIR = (
    "annotations/response_validity_human_v2/external_audit_v1/"
    "sol_reference_evaluation_v1/refusal_boundary_consistency_v1"
)
EXTERNAL_DIR = "annotations/response_validity_human_v2/external_audit_v1"
VERSION = "refusal-boundary-consistency-review-v1"
CODEBOOK_VERSION = "response-validity-decomposed-v2.3"


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_number} of {path}") from exc
    return records


def _candidate_mask(frame: pd.DataFrame) -> pd.Series:
    """Implement the frozen, label-only selection rule exactly once."""
    return (
        frame["pred_genuine_refusal_luna"].astype(bool)
        & (
            frame["epistemic_limitation_luna"].astype(bool)
            | frame["stance_disclaimer_luna"].astype(bool)
        )
    )


def freeze_refusal_boundary_consistency(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Freeze the 24-case audit and its 20-row new-review queue locally."""
    output_dir = output_dir or root / DEFAULT_DIR
    external_dir = root / EXTERNAL_DIR
    paired_path = external_dir / "paired_machine_labels.parquet"
    packet_path = external_dir / "human_phase2_v1" / "human_review_packet.parquet"
    prior_path = (
        external_dir / "sol_reference_evaluation_v1"
        / "human_refusal_disagreement_choices.jsonl"
    )
    manifest_path = output_dir / "manifest.json"
    candidate_path = output_dir / "candidate_design.parquet"
    review_path = output_dir / "review_packet.parquet"
    carry_path = output_dir / "carried_forward_decisions.csv"

    input_hashes = {
        "paired_machine_labels.parquet": sha_file(paired_path),
        "human_review_packet.parquet": sha_file(packet_path),
        "human_refusal_disagreement_choices.jsonl": sha_file(prior_path),
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen boundary review no longer matches its source files")
        for name, path in {
            "candidate_design.parquet": candidate_path,
            "review_packet.parquet": review_path,
            "carried_forward_decisions.csv": carry_path,
        }.items():
            if not path.exists() or manifest["output_sha256"].get(name) != sha_file(path):
                raise ValueError(f"frozen boundary-review artifact changed: {name}")
        return manifest

    paired = pd.read_parquet(paired_path)
    packet = pd.read_parquet(packet_path)
    if paired["audit_response_id"].duplicated().any():
        raise ValueError("paired machine-label keys are not unique")
    if packet["review_id"].duplicated().any():
        raise ValueError("translated review-packet keys are not unique")

    candidates = paired.loc[_candidate_mask(paired)].copy()
    if len(candidates) != 24:
        raise ValueError(f"expected 24 boundary candidates, found {len(candidates)}")
    candidates = candidates.merge(
        packet,
        left_on="audit_response_id",
        right_on="review_id",
        how="left",
        validate="one_to_one",
        suffixes=("", "_packet"),
    )
    if candidates["response_text"].isna().any():
        raise ValueError("one or more boundary candidates lack translated review data")

    prior = pd.DataFrame(_read_jsonl(prior_path))
    prior = prior.loc[
        prior["audit_response_id"].astype(str).isin(candidates["audit_response_id"].astype(str))
    ].copy()
    if len(prior) != 4 or prior["audit_response_id"].duplicated().any():
        raise ValueError("expected four unique previously reviewed boundary cases")
    if not prior["status"].eq("submitted").all():
        raise ValueError("a carried-forward review is not submitted")
    if prior["final_genuine_refusal"].isna().any():
        raise ValueError("a carried-forward boundary decision is uncertain")

    prior_ids = set(prior["audit_response_id"].astype(str))
    candidates["review_status"] = candidates["audit_response_id"].astype(str).map(
        lambda value: "carried_forward" if value in prior_ids else "new_review"
    )
    candidates["selection_rule"] = (
        "luna_genuine_refusal_and_(luna_epistemic_limitation_or_luna_stance_disclaimer)"
    )
    candidates = candidates.sort_values(
        ["review_status", "prompt_language", "model", "audit_response_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    new = candidates.loc[candidates["review_status"].eq("new_review")].copy()
    if len(new) != 20:
        raise ValueError(f"expected 20 new review rows, found {len(new)}")
    # Stable pseudo-random order based only on the immutable response identifier.
    new["boundary_review_order"] = new["audit_response_id"].map(
        lambda value: int(__import__("hashlib").sha256(
            f"{VERSION}:{value}".encode("utf-8")
        ).hexdigest()[:16], 16)
    )
    new = new.sort_values("boundary_review_order", kind="mergesort").reset_index(drop=True)
    new["boundary_review_order"] = range(1, len(new) + 1)

    carry_columns = [
        "audit_response_id", "final_genuine_refusal", "confidence", "note",
        "who_was_correct", "submitted_at", "coder_id", "review_mode",
    ]
    carry = prior[carry_columns].sort_values("audit_response_id", kind="mergesort")

    output_dir.mkdir(parents=True, exist_ok=False)
    candidates.to_parquet(candidate_path, index=False)
    new.to_parquet(review_path, index=False)
    carry.to_csv(carry_path, index=False)
    manifest = {
        "version": VERSION,
        "codebook_version": CODEBOOK_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_awaiting_20_new_human_reviews",
        "selection_rule": (
            "pred_genuine_refusal_luna == TRUE and "
            "(epistemic_limitation_luna == TRUE or stance_disclaimer_luna == TRUE)"
        ),
        "n_candidates": 24,
        "n_carried_forward": 4,
        "n_new_review": 20,
        "languages_n": {
            str(k): int(v) for k, v in
            candidates["prompt_language"].value_counts().sort_index().items()
        },
        "input_sha256": input_hashes,
        "output_sha256": {
            "candidate_design.parquet": sha_file(candidate_path),
            "review_packet.parquet": sha_file(review_path),
            "carried_forward_decisions.csv": sha_file(carry_path),
        },
        "prior_decision_provenance": (
            "Four final binary decisions are copied without alteration from the "
            "completed visible-label nine-case review. The original append-only log "
            "remains the source of record."
        ),
        "sampling_interpretation": (
            "Targeted codebook consistency audit; not a probability sample and not "
            "valid for estimating corpus prevalence or population accuracy."
        ),
        "provider_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def summarize_refusal_boundary_consistency(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Validate and assemble all 24 decisions without altering either source log."""
    output_dir = output_dir or root / DEFAULT_DIR
    freeze_refusal_boundary_consistency(root, output_dir)
    review_path = output_dir / "review_packet.parquet"
    carry_path = output_dir / "carried_forward_decisions.csv"
    labels_path = output_dir / "human_boundary_decisions.jsonl"
    cases_path = output_dir / "assembled_boundary_decisions.csv"
    summary_path = output_dir / "review_summary.json"
    if not labels_path.exists():
        raise ValueError("no new boundary-review decisions exist yet")

    input_hashes = {
        "review_packet.parquet": sha_file(review_path),
        "carried_forward_decisions.csv": sha_file(carry_path),
        "human_boundary_decisions.jsonl": sha_file(labels_path),
    }
    labels = pd.DataFrame(_read_jsonl(labels_path))
    if len(labels) != 20 or labels["audit_response_id"].duplicated().any():
        raise ValueError("boundary log must contain 20 unique submitted rows")
    if not labels["status"].eq("submitted").all():
        raise ValueError("all boundary-review rows must be submitted")
    if labels["coder_id"].nunique() != 1:
        raise ValueError("the completed boundary review must have one stable coder ID")
    if not labels["original_labels_visible"].eq(True).all():
        raise ValueError("boundary review must be recorded as visible-label review")
    if not labels["codebook_version"].eq(CODEBOOK_VERSION).all():
        raise ValueError("boundary decisions do not use the frozen codebook version")
    review = pd.read_parquet(review_path)
    if set(labels["audit_response_id"].astype(str)) != set(review["audit_response_id"].astype(str)):
        raise ValueError("boundary decisions do not match the frozen 20-row queue")
    if labels["review_packet_sha256"].nunique() != 1 or (
        labels["review_packet_sha256"].iloc[0] != sha_file(review_path)
    ):
        raise ValueError("boundary decisions are not bound to the frozen review packet")
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("input_sha256") != input_hashes:
            raise ValueError("completed boundary summary no longer matches its inputs")
        if not cases_path.exists() or summary.get("cases_sha256") != sha_file(cases_path):
            raise ValueError("completed boundary decision table changed")
        return summary

    review_metadata = review.set_index("audit_response_id")[["model", "prompt_language"]]
    labels_by_id = labels.set_index("audit_response_id")
    if not labels_by_id["source_model"].astype(str).eq(
        review_metadata.loc[labels_by_id.index, "model"].astype(str)
    ).all():
        raise ValueError("saved source-model metadata does not match the frozen queue")
    if not labels_by_id["prompt_language"].astype(str).eq(
        review_metadata.loc[labels_by_id.index, "prompt_language"].astype(str)
    ).all():
        raise ValueError("saved language metadata does not match the frozen queue")
    new = labels.rename(columns={"source_model": "model"}).copy()
    new["decision_provenance"] = "new_boundary_review_v1"
    carry = pd.read_csv(carry_path)
    carry["decision_provenance"] = "carried_from_nine_case_review"
    carry["boundary_reason"] = "not_collected_in_prior_review"
    carry["reviewer_note"] = carry.pop("note")
    carry = carry.merge(
        pd.read_parquet(output_dir / "candidate_design.parquet")[[
            "audit_response_id", "model", "prompt_language"
        ]], on="audit_response_id", validate="one_to_one",
    )
    assembled = pd.concat([
        carry[["audit_response_id", "model", "prompt_language",
               "final_genuine_refusal", "confidence", "boundary_reason",
               "reviewer_note", "decision_provenance", "submitted_at"]],
        new[["audit_response_id", "model", "prompt_language",
             "final_genuine_refusal", "confidence", "boundary_reason",
             "reviewer_note", "decision_provenance", "submitted_at"]],
    ], ignore_index=True).sort_values("audit_response_id", kind="mergesort")
    assembled.to_csv(cases_path, index=False)
    decided = assembled["final_genuine_refusal"].notna()
    summary = {
        "version": VERSION,
        "assembled_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete_targeted_single_reviewer_consistency_audit",
        "n_rows": 24,
        "n_carried_forward": 4,
        "n_newly_reviewed": 20,
        "n_decided": int(decided.sum()),
        "n_uncertain": int((~decided).sum()),
        "final_genuine_refusal_n": int(
            assembled.loc[decided, "final_genuine_refusal"].astype(bool).sum()
        ),
        "boundary_reason_n": {
            str(k): int(v) for k, v in assembled["boundary_reason"].value_counts().items()
        },
        "input_sha256": input_hashes,
        "cases_sha256": sha_file(cases_path),
        "method_note": (
            "Targeted visible-label consistency audit. It informs codebook wording but "
            "does not estimate prevalence or replace probability-sampled validation."
        ),
        "source_logs_overwritten": False,
        "provider_call_made": False,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
