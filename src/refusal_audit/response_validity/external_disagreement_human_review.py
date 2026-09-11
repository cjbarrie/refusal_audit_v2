"""Validate and summarize the visible-label nine-case human adjudication."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .human_pilot import sha_file


DEFAULT_DIR = (
    "annotations/response_validity_human_v2/external_audit_v1/"
    "sol_reference_evaluation_v1"
)


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_number}") from exc
    return rows


def summarize_external_disagreement_human_review(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Assemble the completed review without rewriting its append-only log."""
    output_dir = output_dir or root / DEFAULT_DIR
    labels_path = output_dir / "human_refusal_disagreement_choices.jsonl"
    paired_path = output_dir.parent / "paired_machine_labels.parquet"
    forensic_path = output_dir / "refusal_disagreement_forensic_review.csv"
    summary_path = output_dir / "human_refusal_disagreement_review_summary.json"
    cases_path = output_dir / "human_refusal_disagreement_review_cases.csv"

    input_hashes = {
        "human_refusal_disagreement_choices.jsonl": sha_file(labels_path),
        "paired_machine_labels.parquet": sha_file(paired_path),
        "refusal_disagreement_forensic_review.csv": sha_file(forensic_path),
    }
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("input_sha256") != input_hashes:
            raise ValueError("completed disagreement summary no longer matches its inputs")
        if not cases_path.exists() or summary.get("cases_sha256") != sha_file(cases_path):
            raise ValueError("completed disagreement case table changed")
        return summary

    labels = pd.DataFrame(_read_jsonl(labels_path))
    paired = pd.read_parquet(paired_path)
    paired = paired.loc[paired.refusal_disagreement].copy()
    forensic = pd.read_csv(forensic_path)
    if len(labels) != 9 or labels.audit_response_id.duplicated().any():
        raise ValueError("human disagreement log must contain nine unique rows")
    if set(labels.audit_response_id) != set(paired.audit_response_id):
        raise ValueError("human disagreement IDs do not match the frozen nine")
    if labels.coder_id.nunique() != 1 or labels.coder_id.iloc[0] != "live-render-check":
        raise ValueError("unexpected recorded coder ID in completed review")
    if not labels.status.eq("submitted").all():
        raise ValueError("all human disagreement rows must be submitted")
    if not labels.original_labels_visible.eq(True).all():
        raise ValueError("review must be recorded as visible-label adjudication")
    if not labels.codex_forensic_recommendation_visible.eq(False).all():
        raise ValueError("Codex forensic recommendations were unexpectedly visible")
    if labels.paired_machine_labels_sha256.nunique() != 1 or (
        labels.paired_machine_labels_sha256.iloc[0] != sha_file(paired_path)
    ):
        raise ValueError("saved choices are not bound to the paired-label file")

    keep = [
        "audit_response_id", "model", "prompt_language",
        "pred_genuine_refusal_luna", "pred_genuine_refusal_sol",
    ]
    cases = labels.merge(paired[keep], on="audit_response_id", validate="one_to_one")
    cases = cases.merge(
        forensic[["audit_response_id", "forensic_genuine_refusal", "review_confidence"]],
        on="audit_response_id", validate="one_to_one",
    )
    decided = cases.final_genuine_refusal.notna()
    cases["agrees_with_luna"] = pd.NA
    cases["agrees_with_sol"] = pd.NA
    cases["agrees_with_codex_forensic"] = pd.NA
    cases.loc[decided, "agrees_with_luna"] = (
        cases.loc[decided, "final_genuine_refusal"].astype(bool).to_numpy()
        == cases.loc[decided, "pred_genuine_refusal_luna"].astype(bool).to_numpy()
    )
    cases.loc[decided, "agrees_with_sol"] = (
        cases.loc[decided, "final_genuine_refusal"].astype(bool).to_numpy()
        == cases.loc[decided, "pred_genuine_refusal_sol"].astype(bool).to_numpy()
    )
    cases.loc[decided, "agrees_with_codex_forensic"] = (
        cases.loc[decided, "final_genuine_refusal"].astype(bool).to_numpy()
        == cases.loc[decided, "forensic_genuine_refusal"].astype(bool).to_numpy()
    )
    cases = cases.sort_values("submitted_at", kind="mergesort")
    output_columns = [
        "audit_response_id", "source_model", "prompt_language_x",
        "who_was_correct", "final_genuine_refusal", "confidence", "note",
        "luna_genuine_refusal", "sol_genuine_refusal",
        "agrees_with_luna", "agrees_with_sol", "forensic_genuine_refusal",
        "agrees_with_codex_forensic", "submitted_at",
    ]
    cases[output_columns].rename(columns={
        "prompt_language_x": "prompt_language"
    }).to_csv(cases_path, index=False)

    summary = {
        "version": "visible-luna-sol-refusal-disagreement-human-review-v1",
        "assembled_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete_single_reviewer_visible_label_adjudication",
        "n_rows": 9,
        "n_decided": int(decided.sum()),
        "n_uncertain": int((~decided).sum()),
        "final_genuine_refusal_n": int(
            cases.loc[decided, "final_genuine_refusal"].astype(bool).sum()
        ),
        "final_nonrefusal_n": int(
            (~cases.loc[decided, "final_genuine_refusal"].astype(bool)).sum()
        ),
        "who_was_correct_n": {
            key: int(value) for key, value in
            cases.who_was_correct.value_counts().to_dict().items()
        },
        "confidence_n": {
            key: int(value) for key, value in
            cases.confidence.value_counts().to_dict().items()
        },
        "agreement_on_eight_decided": {
            "luna": int(cases.loc[decided, "agrees_with_luna"].astype(bool).sum()),
            "sol": int(cases.loc[decided, "agrees_with_sol"].astype(bool).sum()),
            "codex_forensic": int(
                cases.loc[decided, "agrees_with_codex_forensic"].astype(bool).sum()
            ),
        },
        "recorded_coder_id": "live-render-check",
        "reviewer_role": "user_primary_reviewer",
        "coder_id_provenance_correction": (
            "The assistant entered live-render-check during read-only browser QA and "
            "the value remained in the handed-off tab. The user then reported completion "
            "immediately after exactly nine submissions. No QA submission was made. The "
            "append-only source log is preserved unchanged."
        ),
        "first_submission_at": str(cases.submitted_at.min()),
        "last_submission_at": str(cases.submitted_at.max()),
        "method_note": (
            "One unblinded reviewer chose between visible Luna and Sol labels. This "
            "adjudicates the disagreement set but is not the probability-sampled blinded "
            "human validation of all external cases."
        ),
        "input_sha256": input_hashes,
        "cases_sha256": sha_file(cases_path),
        "source_log_overwritten": False,
        "provider_call_made": False,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
