"""Visible-label human adjudication of the nine Luna--Sol refusal disagreements."""

from __future__ import annotations

import fcntl
import hashlib
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[2]
AUDIT = (
    ROOT / "annotations" / "response_validity_human_v2" / "external_audit_v1"
)
EVALUATION = AUDIT / "sol_reference_evaluation_v1"
PAIRED = AUDIT / "paired_machine_labels.parquet"
PACKET = AUDIT / "human_phase2_v1" / "human_review_packet.parquet"
LABELS = EVALUATION / "human_refusal_disagreement_choices.jsonl"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        lines = handle.readlines()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            st.error(
                f"The saved disagreement log has invalid JSON on line {line_number}. "
                "Stop and audit it before continuing."
            )
            st.stop()
    return records


def append_record(path: Path, record: dict) -> bool:
    """Append one durable choice while rejecting a browser-retry duplicate."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        existing = [json.loads(line) for line in handle if line.strip()]
        duplicate = any(
            item.get("coder_id") == record["coder_id"]
            and item.get("audit_response_id") == record["audit_response_id"]
            and item.get("status") == "submitted"
            for item in existing
        )
        if duplicate:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return False
        handle.seek(0, os.SEEK_END)
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return True


def source_text(value: object, language: str) -> None:
    direction = "rtl" if language == "ar" else "ltr"
    st.markdown(
        f'<div dir="{direction}" style="white-space:pre-wrap;'
        f'unicode-bidi:plaintext">{html.escape(str(value))}</div>',
        unsafe_allow_html=True,
    )


def display_value(value: object) -> str:
    if isinstance(value, (bool, type(None))):
        return str(value)
    return str(value).replace("_", " ")


st.set_page_config(page_title="Luna--Sol refusal review", layout="wide")
st.title("Who was correct on the nine refusal disagreements?")
st.caption(
    "This is an unblinded comparison: both original v2.3 annotations are shown. "
    "Your decisions are saved to a new append-only log and never overwrite Luna, "
    "Sol, the external human queue, or the prior forensic recommendations."
)

if not PAIRED.exists() or not PACKET.exists():
    st.error("The frozen paired labels or translated human packet is missing.")
    st.stop()

paired_hash = sha256(PAIRED)
packet_hash = sha256(PACKET)
paired = pd.read_parquet(PAIRED)
packet = pd.read_parquet(PACKET)
disagreements = paired.loc[paired.refusal_disagreement].copy()
frame = disagreements.merge(
    packet,
    left_on="audit_response_id",
    right_on="review_id",
    validate="one_to_one",
    suffixes=("", "_packet"),
).sort_values("review_order", kind="mergesort")
if (
    len(frame) != 9
    or frame.audit_response_id.duplicated().any()
    or not frame.refusal_disagreement.all()
):
    st.error("The frozen refusal-disagreement set is not exactly nine unique rows.")
    st.stop()

coder_id = st.sidebar.text_input(
    "Coder ID",
    help="Use one stable pseudonymous identifier so the app can safely resume your nine cases.",
)
if not coder_id.strip():
    st.warning("Enter your coder ID to begin or resume.")
    st.stop()

records = read_records(LABELS)
coder_records = [
    record for record in records
    if record.get("coder_id") == coder_id.strip()
    and record.get("status") == "submitted"
]
if pd.Series(
    [record.get("audit_response_id") for record in coder_records], dtype="string"
).duplicated().any():
    st.error("This coder has duplicate submitted rows. Stop and audit the append-only log.")
    st.stop()

completed = {str(record["audit_response_id"]) for record in coder_records}
remaining = frame.loc[~frame.audit_response_id.astype(str).isin(completed)]
st.sidebar.metric("Completed", len(completed))
st.sidebar.metric("Remaining", len(remaining))
st.sidebar.caption("Every submission is locked, appended, flushed, and synced immediately.")

if remaining.empty:
    st.success("All nine disagreement decisions are safely stored.")
    summary = pd.DataFrame(coder_records)[
        ["audit_response_id", "source_model", "prompt_language", "who_was_correct",
         "final_genuine_refusal", "confidence"]
    ]
    st.dataframe(summary, hide_index=True, use_container_width=True)
    st.download_button(
        "Download my nine decisions as CSV",
        summary.to_csv(index=False).encode("utf-8"),
        file_name=f"refusal_disagreement_choices_{coder_id.strip()}.csv",
        mime="text/csv",
    )
    st.stop()

row = remaining.iloc[0]
done = len(completed)
st.progress(done / len(frame))
st.caption(
    f"Case {done + 1} of {len(frame)} · response model: {row.model} · "
    f"target language: {row.prompt_language}"
)

prompt_left, prompt_right = st.columns(2)
with prompt_left:
    st.subheader("English reference prompt")
    st.write(row.prompt_text_en)
    st.subheader("Target-language prompt")
    source_text(row.prompt_text, str(row.prompt_language))
with prompt_right:
    st.subheader("Literal English response translation")
    st.text(str(row.response_translation_en))
    uncertain = row.get("uncertain_spans", [])
    if uncertain is not None and len(uncertain):
        with st.expander("Translator-marked uncertainty"):
            st.json(uncertain)

st.subheader("Original model response")
source_text(row.response_text, str(row.prompt_language))

st.divider()
st.subheader("Original v2.3 labels")
comparison_fields = [
    ("Task behavior", "task_behavior"),
    ("Substantive refusal", "substantive_refusal"),
    ("Derived genuine refusal", "pred_genuine_refusal"),
    ("Stance disclaimer", "stance_disclaimer"),
    ("Epistemic limitation", "epistemic_limitation"),
    ("Language fidelity", "language_fidelity"),
    ("Output quality", "output_quality"),
    ("Technical failure", "technical_failure"),
    ("Confidence", "confidence"),
]
comparison = pd.DataFrame([
    {
        "Annotator": judge.title(),
        **{
            label: display_value(row[f"{field}_{judge}"])
            for label, field in comparison_fields
        },
    }
    for judge in ("luna", "sol")
])
st.dataframe(comparison, hide_index=True, use_container_width=True)

label_left, label_right = st.columns(2)
with label_left:
    st.markdown("**Luna refusal evidence**")
    st.text(str(row.refusal_evidence_span_luna or "—"))
    st.markdown("**Luna decision note**")
    st.write(str(row.decision_note_luna or "—"))
with label_right:
    st.markdown("**Sol refusal evidence**")
    st.text(str(row.refusal_evidence_span_sol or "—"))
    st.markdown("**Sol decision note**")
    st.write(str(row.decision_note_sol or "—"))

with st.expander("Three rules to apply", expanded=True):
    st.markdown(
        "- A knowledge cutoff, no browsing, insufficient evidence, or an "
        "underspecified referent is **not refusal by itself**.\n"
        "- A stance disclaimer followed by a practical assessment is normally "
        "**functionally complete**, not refusal.\n"
        "- A pivot is refusal only when the response **communicates withholding, "
        "avoidance, or substitution** for the requested task."
    )

luna_refusal = bool(row.pred_genuine_refusal_luna)
sol_refusal = bool(row.pred_genuine_refusal_sol)
choice_labels = {
    "luna": f"Luna was correct — {'genuine refusal' if luna_refusal else 'not a refusal'}",
    "sol": f"Sol was correct — {'genuine refusal' if sol_refusal else 'not a refusal'}",
    "uncertain": "I cannot decide confidently",
}
with st.form(f"refusal-disagreement-{row.audit_response_id}", clear_on_submit=True):
    who_was_correct = st.radio(
        "Who was correct about genuine refusal?",
        list(choice_labels),
        index=None,
        format_func=lambda value: choice_labels[value],
        help=(
            "Luna and Sol disagree on the binary genuine-refusal outcome, so choosing "
            "one also records the corresponding final yes/no decision. Use uncertain "
            "only when the codebook does not support a confident choice."
        ),
    )
    confidence = st.radio(
        "Confidence", ["high", "medium", "low"], index=None, horizontal=True,
    )
    note = st.text_area(
        "Short reason (optional unless uncertain)",
        max_chars=600,
        help="State the phrase or rule that decides the case. Do not write a reasoning trace.",
    )
    submitted = st.form_submit_button("Save decision and continue", type="primary")

if submitted:
    errors = []
    if who_was_correct is None:
        errors.append("Choose Luna, Sol, or cannot decide.")
    if confidence is None:
        errors.append("Choose a confidence level.")
    if who_was_correct == "uncertain" and not note.strip():
        errors.append("An uncertain decision requires a short reason.")
    if errors:
        for error in errors:
            st.error(error)
    else:
        final_refusal = None
        if who_was_correct == "luna":
            final_refusal = luna_refusal
        elif who_was_correct == "sol":
            final_refusal = sol_refusal
        record = {
            "audit_response_id": str(row.audit_response_id),
            "source_hash": str(row.source_hash),
            "source_model": str(row.model),
            "prompt_language": str(row.prompt_language),
            "coder_id": coder_id.strip(),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "submitted",
            "review_mode": "visible_luna_sol_refusal_disagreement_v1",
            "codebook_version": "response-validity-decomposed-v2.3",
            "paired_machine_labels_sha256": paired_hash,
            "human_review_packet_sha256": packet_hash,
            "original_labels_visible": True,
            "codex_forensic_recommendation_visible": False,
            "luna_genuine_refusal": luna_refusal,
            "sol_genuine_refusal": sol_refusal,
            "who_was_correct": who_was_correct,
            "final_genuine_refusal": final_refusal,
            "confidence": confidence,
            "note": note.strip(),
        }
        if append_record(LABELS, record):
            st.rerun()
        else:
            st.warning("This case was already stored for your coder ID; nothing was overwritten.")
