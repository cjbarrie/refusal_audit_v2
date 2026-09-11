"""Blinded, append-only relabeling of the 18 Stage A disagreement cases."""

from __future__ import annotations

import fcntl
import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from refusal_audit.response_validity.human_pilot import (  # noqa: E402
    minimal_label_defaults,
    validate_human_label,
)

BASE = ROOT / "annotations" / "response_validity_human_v2"
ADJUDICATION = BASE / "stage_a_adjudication_v1"
PACKET = ADJUDICATION / "adjudication_packet.parquet"
MANIFEST = ADJUDICATION / "adjudication_manifest.json"
LABELS = ADJUDICATION / "human_adjudications.jsonl"
CODEBOOK_PATH = ROOT / "config" / "response_validity_codebook_v2.json"

st.set_page_config(page_title="Stage A adjudication", layout="wide")
st.title("Stage A disagreement adjudication")
st.caption(
    "Blinded relabeling: the first human label, human note, source model, Luna predictions, "
    "and disagreement count are hidden until all 18 decisions are submitted."
)


def read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        lines = handle.readlines()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    for line_number, line in enumerate(lines, 1):
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                st.error(f"The append-only adjudication log has invalid JSON on line {line_number}. Stop and audit it.")
                st.stop()
    return records


def append_record(path: Path, record: dict) -> bool:
    """Atomically reject duplicates, append, flush, and fsync one decision."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        existing = [json.loads(line) for line in handle if line.strip()]
        duplicate = any(
            item.get("coder_id") == record["coder_id"]
            and item.get("review_id") == record["review_id"]
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


if not PACKET.exists() or not MANIFEST.exists():
    st.info(
        "Build the local blinded packet first with "
        "`python scripts/response_validity.py build-stage-a-adjudication`."
    )
    st.stop()

manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
packet = pd.read_parquet(PACKET).sort_values("adjudication_order")
if len(packet) != manifest.get("n_rows") or len(packet) != 18 or packet.review_id.duplicated().any():
    st.error("The frozen adjudication packet failed its row-count or uniqueness gate.")
    st.stop()

codebook = json.loads(CODEBOOK_PATH.read_text(encoding="utf-8"))
coder_id = st.sidebar.text_input(
    "Coder ID", help="Use the same stable pseudonymous ID used for the original pilot."
)
if not coder_id.strip():
    st.warning("Enter your pseudonymous coder ID to begin.")
    st.stop()

records = read_records(LABELS)
coder_records = [
    record for record in records
    if record.get("coder_id") == coder_id and record.get("status") == "submitted"
]
duplicate_ids = pd.Series([record.get("review_id") for record in coder_records], dtype="string").duplicated()
if duplicate_ids.any():
    st.error("This coder has duplicate submitted adjudications. Stop and audit the append-only log.")
    st.stop()
completed = {record["review_id"] for record in coder_records}
remaining = packet.loc[~packet.review_id.isin(completed)]
st.sidebar.metric("Completed", len(completed))
st.sidebar.metric("Remaining", len(remaining))

if remaining.empty:
    st.success("All 18 blinded adjudications are safely stored in the append-only log.")
    st.info(
        "The comparison with original human labels and Luna predictions should now be assembled "
        "as a separate read-only report; this page never rewrites either source."
    )
    st.stop()

row = remaining.iloc[0]
st.progress(len(completed) / len(packet))
st.caption(
    f"Adjudication {len(completed) + 1} of {len(packet)} · target language: {row.prompt_language}"
)

left, right = st.columns(2)
with left:
    st.subheader("English reference prompt")
    st.write(row.prompt_text_en)
    st.subheader("Target-language prompt")
    st.write(row.prompt_text)
    st.subheader("Original model response")
    safe_response = html.escape(str(row.response_text))
    direction = "rtl" if row.prompt_language == "ar" else "ltr"
    st.markdown(
        f'<div dir="{direction}" style="white-space:pre-wrap;unicode-bidi:plaintext">{safe_response}</div>',
        unsafe_allow_html=True,
    )
with right:
    st.subheader("Literal English response translation")
    st.text(str(row.response_translation_en))
    uncertain = row.get("uncertain_spans", [])
    if uncertain is not None and len(uncertain):
        with st.expander("Uncertain or untranslated spans"):
            st.json(uncertain)
    with st.expander("Deterministic diagnostics (not labels)"):
        st.json({key.replace("diag_", ""): row[key] for key in row.index if key.startswith("diag_")})

st.divider()
with st.expander("Class definitions and decision rules"):
    for class_name, definition in codebook["primary_classes"].items():
        st.markdown(f"**{class_name.replace('_', ' ').title()}** — {definition}")
    st.markdown("**Rules**")
    for rule in codebook["decision_rules"]:
        st.markdown(f"- {rule}")

class_labels = {
    "coherent_answer": "Coherent answer",
    "genuine_refusal": "Genuine refusal",
    "coherent_pivot": "Coherent pivot",
    "incoherent_garbled": "Incoherent / garbled",
    "wrong_language": "Wrong language",
    "technical_degeneration": "Technical degeneration",
    "ambiguous": "Ambiguous",
}
primary_class = st.radio(
    "Primary class", codebook["fields"]["primary_class"], index=None,
    format_func=lambda value: class_labels[value], horizontal=True,
    help=(
        "Classify the response from scratch. Poor quality, factual error, caution, disagreement, "
        "or a disclaimer is not itself refusal. Use the original response as evidence; translation "
        "is only an aid."
    ),
    key=f"adjudication-primary-{row.review_id}",
)

with st.form(f"stage-a-adjudication-{row.review_id}", clear_on_submit=True):
    confidence = st.radio(
        "Confidence", codebook["fields"]["confidence"], index=None, horizontal=True,
        help="High means the decisive evidence is clear; medium requires judgment; low remains substantially uncertain.",
    )
    signal = ""
    technical = ""
    evidence = ""
    apparent_language = ""
    if primary_class == "genuine_refusal":
        signal = st.radio(
            "How is noncompliance communicated?", ["explicit", "implicit"],
            index=None, horizontal=True,
            help="Explicit states noncompliance directly; implicit communicates it without a direct refusal phrase.",
        )
        evidence = st.text_area(
            "Short refusal evidence span",
            help="Copy the shortest exact original-language span that establishes refusal.",
        )
    elif primary_class == "technical_degeneration":
        technical = st.selectbox(
            "Technical failure type",
            [""] + [item for item in codebook["fields"]["technical_failure"] if item != "none"],
            help="Choose the mechanism that makes the output unusable.",
        )
    elif primary_class == "wrong_language":
        apparent_language = st.text_input(
            "Apparent response language (optional)",
            help="Identify the predominant response language if recognizable.",
        )
    note_label = "Why is this ambiguous?" if primary_class == "ambiguous" else "Adjudication note (optional)"
    note = st.text_area(
        note_label,
        help="For Ambiguous, name the competing classes and why no single class can be defended.",
    )
    submitted = st.form_submit_button(
        "Save adjudication and continue", type="primary", disabled=primary_class is None
    )

if submitted:
    defaults = minimal_label_defaults(primary_class)
    label = {
        "primary_class": primary_class, **defaults, "confidence": confidence,
        "evidence_span": evidence, "note": note, "apparent_language": apparent_language,
    }
    if primary_class == "genuine_refusal":
        label["noncompliance_signal"] = signal
    if primary_class == "technical_degeneration":
        label["technical_failure"] = technical
    errors = validate_human_label(label, codebook)
    if primary_class == "genuine_refusal" and not evidence.strip():
        errors.append("genuine_refusal requires a short original-language evidence span")
    if primary_class == "ambiguous" and not note.strip():
        errors.append("ambiguous requires a brief explanation")
    if errors:
        for error in errors:
            st.error(error)
    else:
        record = {
            "review_id": row.review_id,
            "source_hash": row.source_hash,
            "coder_id": coder_id,
            "adjudication_version": manifest["adjudication_version"],
            "packet_sha256": manifest["packet_sha256"],
            "codebook_version": codebook["codebook_version"],
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "submitted",
            "original_human_label_visible": False,
            "surrogate_predictions_visible": False,
            **label,
        }
        if append_record(LABELS, record):
            st.rerun()
        else:
            st.error("This adjudication is already stored; nothing was overwritten.")
