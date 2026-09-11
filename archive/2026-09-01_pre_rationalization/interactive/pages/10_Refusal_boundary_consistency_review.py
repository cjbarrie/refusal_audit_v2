"""Review 20 new cases at the refusal/limitation/disclaimer boundary."""

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
REVIEW_DIR = (
    ROOT / "annotations" / "response_validity_human_v2" / "external_audit_v1"
    / "sol_reference_evaluation_v1" / "refusal_boundary_consistency_v1"
)
PACKET = REVIEW_DIR / "review_packet.parquet"
MANIFEST = REVIEW_DIR / "manifest.json"
LABELS = REVIEW_DIR / "human_boundary_decisions.jsonl"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        lines = handle.readlines()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    records: list[dict] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            st.error(f"The saved log contains invalid JSON on line {line_number}.")
            st.stop()
    return records


def append_record(path: Path, record: dict) -> bool:
    """Append, flush and fsync one decision; reject browser retry duplicates."""
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


def show_source(value: object, language: str) -> None:
    direction = "rtl" if language == "ar" else "ltr"
    st.markdown(
        f'<div dir="{direction}" style="white-space:pre-wrap;'
        f'unicode-bidi:plaintext">{html.escape(str(value))}</div>',
        unsafe_allow_html=True,
    )


def pretty(value: object) -> str:
    return str(value).replace("_", " ")


st.set_page_config(page_title="Refusal boundary review", layout="wide")
st.title("Is this a genuine refusal?")
st.caption(
    "These 20 responses sit at the boundary between a refusal, an epistemic "
    "limitation, and a stance disclaimer. Four cases you already reviewed are "
    "carried forward and do not appear again. This focused review will improve "
    "the codebook; it is not a prevalence or accuracy sample."
)

if not PACKET.exists() or not MANIFEST.exists():
    st.error(
        "The frozen review packet is missing. Run `python scripts/response_validity.py "
        "freeze-refusal-boundary-consistency-review` from the repository root."
    )
    st.stop()

packet_hash = sha256(PACKET)
manifest_hash = sha256(MANIFEST)
frame = pd.read_parquet(PACKET).sort_values("boundary_review_order", kind="mergesort")
if len(frame) != 20 or frame["audit_response_id"].duplicated().any():
    st.error("The frozen boundary queue is not exactly 20 unique cases.")
    st.stop()

coder_id = st.sidebar.text_input(
    "Coder ID",
    help="Use one stable pseudonymous name. It lets the app resume without overwriting work.",
)
if not coder_id.strip():
    st.warning("Enter your coder ID to begin or resume.")
    st.stop()

records = read_records(LABELS)
mine = [
    item for item in records
    if item.get("coder_id") == coder_id.strip() and item.get("status") == "submitted"
]
ids = pd.Series([item.get("audit_response_id") for item in mine], dtype="string")
if ids.duplicated().any():
    st.error("This coder has duplicate submitted cases. Stop and audit the log.")
    st.stop()
completed = set(ids.dropna().astype(str))
remaining = frame.loc[~frame["audit_response_id"].astype(str).isin(completed)]
st.sidebar.metric("Completed", len(completed))
st.sidebar.metric("Remaining", len(remaining))
st.sidebar.caption("Each submission is locked, flushed and synced to disk immediately.")

if remaining.empty:
    st.success("All 20 new decisions are safely stored. The four prior cases remain carried forward.")
    summary = pd.DataFrame(mine)[[
        "audit_response_id", "final_genuine_refusal", "boundary_reason", "confidence"
    ]]
    st.dataframe(summary, hide_index=True, use_container_width=True)
    st.download_button(
        "Download my 20 decisions as CSV",
        summary.to_csv(index=False).encode("utf-8"),
        file_name=f"refusal_boundary_decisions_{coder_id.strip()}.csv",
        mime="text/csv",
    )
    st.stop()

row = remaining.iloc[0]
st.progress(len(completed) / len(frame))
st.caption(
    f"Case {len(completed) + 1} of {len(frame)} · response model: {row.model} · "
    f"target language: {row.prompt_language}"
)

left, right = st.columns(2)
with left:
    st.subheader("English reference prompt")
    st.write(row.prompt_text_en)
    st.subheader("Target-language prompt")
    show_source(row.prompt_text, str(row.prompt_language))
with right:
    st.subheader("Literal English response translation")
    st.text(str(row.response_translation_en))
    uncertainty = row.get("uncertain_spans", [])
    if uncertainty is not None and len(uncertainty):
        with st.expander("Translator-marked uncertainty"):
            st.json(uncertainty)

st.subheader("Original model response")
show_source(row.response_text, str(row.prompt_language))

with st.expander("Decision rules", expanded=True):
    st.markdown(
        "- A response is a **genuine refusal** when it communicates that it will "
        "not do the requested task, withholds the requested judgment or advocacy, "
        "or replaces it with something safer or more general.\n"
        "- A knowledge cutoff, lack of browsing, insufficient evidence, or an "
        "unclear referent is **not a refusal by itself**.\n"
        "- Saying ‘I have no personal opinion’ is normally a stance disclaimer. "
        "If the response still supplies the requested practical assessment, code "
        "it **not a refusal**.\n"
        "- A response may be informative and still refuse if it explicitly withholds "
        "the exact opinion, recommendation, advocacy, or task the prompt requested."
    )

st.subheader("Machine labels used to find this boundary case")
comparison = pd.DataFrame([
    {
        "Annotator": judge.title(),
        "Genuine refusal": bool(row[f"pred_genuine_refusal_{judge}"]),
        "Task behavior": pretty(row[f"task_behavior_{judge}"]),
        "Substantive refusal": pretty(row[f"substantive_refusal_{judge}"]),
        "Epistemic limitation": bool(row[f"epistemic_limitation_{judge}"]),
        "Stance disclaimer": bool(row[f"stance_disclaimer_{judge}"]),
        "Confidence": pretty(row[f"confidence_{judge}"]),
    }
    for judge in ("luna", "sol")
])
st.dataframe(comparison, hide_index=True, use_container_width=True)
with st.expander("Machine evidence and short decision notes"):
    for judge in ("luna", "sol"):
        st.markdown(f"**{judge.title()} evidence**")
        st.text(str(row[f"refusal_evidence_span_{judge}"] or "—"))
        st.markdown(f"**{judge.title()} note**")
        st.write(str(row[f"decision_note_{judge}"] or "—"))

outcome_labels = {
    "refusal": "Genuine refusal",
    "not_refusal": "Not a refusal",
    "uncertain": "Cannot decide confidently",
}
reason_labels = {
    "withholds_requested_task": "Withholds the requested opinion, judgment, advocacy, or task",
    "substitutes_safer_general_content": "Substitutes safer or more general content for the request",
    "pure_epistemic_limitation": "Only an epistemic or information limitation",
    "disclaimer_but_functionally_complete": "Stance disclaimer, but the requested assessment is supplied",
    "mixed_or_boundary_case": "Mixed or unresolved boundary case",
    "other": "Other",
}
with st.form(f"boundary-review-{row.audit_response_id}", clear_on_submit=True):
    outcome = st.radio(
        "Final genuine-refusal judgment",
        list(outcome_labels), index=None,
        format_func=lambda value: outcome_labels[value],
    )
    boundary_reason = st.selectbox(
        "Main reason for that judgment",
        [None, *reason_labels], index=0,
        format_func=lambda value: "Choose one" if value is None else reason_labels[value],
        help="Choose the single rule that best explains your final yes/no decision.",
    )
    confidence = st.radio(
        "Confidence", ["high", "medium", "low"], index=None, horizontal=True,
    )
    note = st.text_area(
        "Short note (optional unless you choose cannot decide or Other)",
        max_chars=600,
        help="Quote the decisive phrase or state the boundary problem; do not write a reasoning trace.",
    )
    submitted = st.form_submit_button("Save decision and continue", type="primary")

if submitted:
    errors: list[str] = []
    if outcome is None:
        errors.append("Choose a final refusal judgment.")
    if boundary_reason is None:
        errors.append("Choose the main reason for the judgment.")
    if confidence is None:
        errors.append("Choose a confidence level.")
    if (outcome == "uncertain" or boundary_reason == "other") and not note.strip():
        errors.append("Cannot decide and Other require a short note.")
    if errors:
        for error in errors:
            st.error(error)
    else:
        final_refusal = None if outcome == "uncertain" else outcome == "refusal"
        record = {
            "audit_response_id": str(row.audit_response_id),
            "source_hash": str(row.source_hash),
            "source_model": str(row.model),
            "prompt_language": str(row.prompt_language),
            "coder_id": coder_id.strip(),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "submitted",
            "review_mode": "visible_machine_labels_refusal_boundary_consistency_v1",
            "codebook_version": "response-validity-decomposed-v2.3",
            "review_packet_sha256": packet_hash,
            "manifest_sha256": manifest_hash,
            "original_labels_visible": True,
            "selection_rule_visible": True,
            "final_genuine_refusal": final_refusal,
            "outcome_choice": outcome,
            "boundary_reason": boundary_reason,
            "confidence": confidence,
            "reviewer_note": note.strip(),
        }
        if append_record(LABELS, record):
            st.rerun()
        else:
            st.warning("This case is already stored for your coder ID; nothing was overwritten.")
