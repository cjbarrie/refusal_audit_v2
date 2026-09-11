"""Read-only view of existing GPT-5.6 Sol labels for the external draw."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
BASE = (
    ROOT / "annotations/response_validity_human_v2/external_audit_v1/"
    "human_phase2_v1"
)
PACKET = BASE / "human_review_packet.parquet"
LABELS = BASE / "sol_reference_labels.parquet"

st.set_page_config(page_title="External Sol reference", layout="wide")
st.title("External Sol reference — complete")
st.caption(
    "These are the existing GPT-5.6 Sol v2.3 annotations for the same 458-case "
    "probability sample. They are model-reference labels, not human gold, and this "
    "read-only page never writes to the blinded human annotation log."
)

if not PACKET.exists() or not LABELS.exists():
    st.error(
        "Assemble the external human packet and Sol reference locally before opening this page."
    )
    st.stop()

packet = pd.read_parquet(PACKET)
labels = pd.read_parquet(LABELS)
frame = packet.merge(labels, on=["review_id", "source_hash"], validate="one_to_one")
if len(frame) != 458 or frame.review_id.duplicated().any():
    st.error("The Sol reference failed its frozen 458-row key check.")
    st.stop()

st.success("458 of 458 Sol reference annotations are complete.")
st.info(
    "Use this track for provisional Sol-based analyses. Leave the separate external "
    "human page untouched until independent human validation resumes."
)

with st.sidebar:
    st.metric("Sol completed", 458)
    language = st.multiselect(
        "Target language", sorted(frame.prompt_language.unique().tolist())
    )
    refusal = st.selectbox(
        "Substantive refusal", ["all", "explicit", "implicit", "none", "unassessable"]
    )
    quality = st.multiselect(
        "Output quality", sorted(frame.output_quality.unique().tolist())
    )
    search = st.text_input("Search prompt or response")

filtered = frame
if language:
    filtered = filtered.loc[filtered.prompt_language.isin(language)]
if refusal != "all":
    filtered = filtered.loc[filtered.substantive_refusal.eq(refusal)]
if quality:
    filtered = filtered.loc[filtered.output_quality.isin(quality)]
if search:
    needle = search.casefold()
    matched = filtered.prompt_text_en.fillna("").str.casefold().str.contains(
        needle, regex=False
    )
    matched |= filtered.response_text.fillna("").str.casefold().str.contains(
        needle, regex=False
    )
    filtered = filtered.loc[matched]

st.caption(f"{len(filtered):,} cases match the current filters.")
if filtered.empty:
    st.warning("No cases match these filters.")
    st.stop()

ordered = filtered.sort_values("review_order", kind="mergesort")
selected_id = st.selectbox(
    "Inspect case",
    ordered.review_id.tolist(),
    format_func=lambda review_id: (
        f"Review {int(ordered.set_index('review_id').loc[review_id, 'review_order'])} · "
        f"{ordered.set_index('review_id').loc[review_id, 'prompt_language']} · {review_id}"
    ),
)
row = ordered.loc[ordered.review_id.eq(selected_id)].iloc[0]


def source_text(value: object, language_code: str) -> None:
    if language_code == "ar":
        st.markdown(
            '<div dir="rtl" style="white-space:pre-wrap;unicode-bidi:plaintext">'
            f"{html.escape(str(value))}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.text(str(value))


left, right = st.columns(2)
with left:
    st.subheader("English reference prompt")
    st.write(row.prompt_text_en)
    st.subheader("Target-language prompt")
    source_text(row.prompt_text, str(row.prompt_language))
    st.subheader("Original model response")
    source_text(row.response_text, str(row.prompt_language))
with right:
    st.subheader("Literal English response translation")
    st.text(str(row.response_translation_en))
    uncertain = row.get("uncertain_spans", [])
    if uncertain is not None and len(uncertain):
        with st.expander("Translator-marked uncertainty"):
            st.json(uncertain)

st.subheader("GPT-5.6 Sol v2.3 annotation")
fields = [
    ("Task behavior", "task_behavior"),
    ("Substantive refusal", "substantive_refusal"),
    ("Stance disclaimer", "stance_disclaimer"),
    ("Epistemic limitation", "epistemic_limitation"),
    ("Language fidelity", "language_fidelity"),
    ("Output quality", "output_quality"),
    ("Technical failure", "technical_failure"),
    ("Confidence", "confidence"),
]
columns = st.columns(4)
for index, (label, field) in enumerate(fields):
    columns[index % 4].metric(label, str(row[field]).replace("_", " "))

st.text_area(
    "Refusal evidence span",
    value=str(row.refusal_evidence_span or ""), disabled=True,
)
st.text_area(
    "Sol decision note",
    value=str(row.decision_note or ""), disabled=True,
)
st.caption(
    f"Annotation source: {row.annotator_id} · codebook: {row.codebook_version} · "
    "human gold: no"
)
