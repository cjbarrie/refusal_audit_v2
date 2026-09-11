"""Read-only explorer for Luna v2.4 genuine refusals on fixed UMAP geometry.

Inputs come from ``interactive/build_data.py``. The app makes no provider calls
and writes no annotation or review data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

DATA = HERE / "data"

st.set_page_config(page_title="Refusal explorer", layout="wide")


@st.cache_data(show_spinner=False)
def load_assets():
    points = pd.read_parquet(DATA / "umap_points.parquet")
    responses = pd.read_parquet(DATA / "responses.parquet")
    metadata = json.loads((DATA / "build_metadata.json").read_text())
    return points, responses, metadata


def values(frame: pd.DataFrame, column: str) -> list[str]:
    return sorted(frame[column].dropna().astype(str).unique().tolist())


def rtl_text(text: object, language: str) -> None:
    direction = "rtl" if language == "ar" else "ltr"
    escaped = (str(text).replace("&", "&amp;").replace("<", "&lt;")
               .replace(">", "&gt;"))
    st.markdown(
        f'<div dir="{direction}" style="white-space:pre-wrap;unicode-bidi:plaintext">{escaped}</div>',
        unsafe_allow_html=True,
    )


def apply_filters(frame: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        st.header("Filter genuine refusals")
        selected_models = st.multiselect("Model", values(frame, "model"))
        selected_languages = st.multiselect("Language", values(frame, "prompt_language"))
        selected_domains = st.multiselect("Topic domain", values(frame, "topic_domain"))
        selected_regions = st.multiselect("Issue region", values(frame, "region_focus"))
        selected_tiers = st.multiselect("Prompt tier", values(frame, "controversy_tier"))
        selected_modes = st.multiselect("Refusal mode", values(frame, "substantive_refusal"))
        search = st.text_input("Search prompt or response")
        if st.button("Reset filters", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    selections = {
        "model": selected_models,
        "prompt_language": selected_languages,
        "topic_domain": selected_domains,
        "region_focus": selected_regions,
        "controversy_tier": selected_tiers,
        "substantive_refusal": selected_modes,
    }
    out = frame
    for column, selected in selections.items():
        if selected:
            out = out[out[column].astype(str).isin(selected)]
    if search:
        needle = search.casefold()
        match = out.prompt_text.fillna("").str.casefold().str.contains(needle, regex=False)
        match |= out.response_text.fillna("").str.casefold().str.contains(needle, regex=False)
        out = out[match]
    return out


def prompt_map(points: pd.DataFrame, refusals: pd.DataFrame):
    summary = refusals.groupby("prompt_id", as_index=False).agg(
        refusal_count=("genuine_refusal", "size"),
        refusing_models=("model", "nunique"),
        refusing_languages=("prompt_language", "nunique"),
    )
    mapped = points[["prompt_id", "umap_x", "umap_y", "prompt_text"]].merge(
        summary, on="prompt_id", how="left", validate="one_to_one"
    )
    for column in ["refusal_count", "refusing_models", "refusing_languages"]:
        mapped[column] = mapped[column].fillna(0).astype(int)
    # One single-view dataset with two rows per refused prompt avoids
    # Streamlit's unsupported layered-chart selection while still drawing the
    # entire geometry as an unconditional gray background. Background marks are
    # deliberately larger than the LARGEST red overlay, leaving a visible gray
    # halo at every coordinate, including in pooled views with many refusals.
    base = mapped.assign(layer_role="background", draw_order=0)
    overlay = mapped[mapped.refusal_count.gt(0)].assign(
        layer_role="refusal", draw_order=1
    )
    plot_data = pd.concat([base, overlay], ignore_index=True)
    selection = alt.selection_point(fields=["prompt_id"], name="prompt", clear="dblclick")
    chart = alt.Chart(plot_data).mark_circle().encode(
        x=alt.X("umap_x:Q", axis=None),
        y=alt.Y("umap_y:Q", axis=None),
        size=alt.condition(
            "datum.layer_role === 'refusal'",
            alt.Size("refusal_count:Q", title="Genuine refusals",
                     scale=alt.Scale(range=[10, 42])),
            alt.value(76),
        ),
        color=alt.condition(
            "datum.layer_role === 'refusal'",
            alt.Color("refusal_count:Q", title="Genuine refusals",
                      scale=alt.Scale(scheme="reds")),
            alt.value("#7A7A7A"),
        ),
        opacity=alt.condition("datum.layer_role === 'refusal'", alt.value(.84), alt.value(.28)),
        order=alt.Order("draw_order:Q"),
        tooltip=[
            alt.Tooltip("prompt_text:N", title="English prompt"),
            alt.Tooltip("refusal_count:Q", title="Responses"),
            alt.Tooltip("refusing_models:Q", title="Models"),
            alt.Tooltip("refusing_languages:Q", title="Languages"),
        ],
        stroke=alt.condition(selection, alt.value("#111111"), alt.value(None)),
        strokeWidth=alt.condition(selection, alt.value(2), alt.value(0)),
    ).add_params(selection).properties(height=610)
    event = st.altair_chart(
        chart, use_container_width=True, on_select="rerun", selection_mode="prompt"
    )
    chosen = event.selection.get("prompt", []) if event and event.selection else []
    return mapped, chosen


def show_refusal(prompt_id: str, refusals: pd.DataFrame) -> None:
    detail = refusals[refusals.prompt_id.eq(prompt_id)].copy()
    if detail.empty:
        return
    first = detail.iloc[0]
    st.subheader("Prompt")
    st.write(first.prompt_text_en)
    st.caption(
        " · ".join(str(first.get(k, "")) for k in
                   ["topic_domain", "region_focus", "controversy_tier", "route"])
    )

    table_columns = [
        "model", "prompt_language", "substantive_refusal", "task_behavior",
        "language_fidelity", "output_quality", "technical_failure", "confidence",
    ]
    st.subheader(f"Genuine refusals ({len(detail)})")
    st.dataframe(
        detail[table_columns].sort_values(["prompt_language", "model"]),
        hide_index=True, use_container_width=True,
        column_config={
            "model": "Model", "prompt_language": "Prompt language",
            "substantive_refusal": "Refusal", "task_behavior": "Task behaviour",
            "language_fidelity": "Response language", "output_quality": "Quality",
            "technical_failure": "Technical failure", "confidence": "Confidence",
        },
    )

    keys = detail.apply(
        lambda r: f"{r['prompt_language']} · {r['model']} · {r['substantive_refusal']}",
        axis=1,
    ).tolist()
    selected = st.selectbox("Inspect one response", keys)
    row = detail.iloc[keys.index(selected)]

    left, right = st.columns([1, 1])
    with left:
        st.markdown("**Prompt in the selected language**")
        rtl_text(row.prompt_text, row.prompt_language)
    with right:
        st.markdown("**Coding**")
        coding = {
            "model": row.model,
            "language": row.prompt_language,
            "task_behavior": row.task_behavior,
            "substantive_refusal": row.substantive_refusal,
            "stance_disclaimer": row.stance_disclaimer,
            "epistemic_limitation": row.epistemic_limitation,
            "language_fidelity": row.language_fidelity,
            "output_quality": row.output_quality,
            "technical_failure": row.technical_failure,
            "confidence": row.confidence,
            "refusal_evidence_span": row.refusal_evidence_span,
            "annotation_source": row.annotation_source,
        }
        st.json(coding)

    st.markdown("**Full model response**")
    rtl_text(row.response_text, row.prompt_language)


def main() -> None:
    try:
        points, responses, metadata = load_assets()
    except FileNotFoundError:
        st.error("Assets are absent. Run `python3 interactive/build_data.py` first.")
        st.stop()

    refusals = responses[responses.genuine_refusal].copy()
    filtered = apply_filters(refusals)

    st.header("Refusal explorer")
    st.caption(
        f"{len(filtered):,} Luna v2.4 genuine refusals across "
        f"{filtered.prompt_id.nunique():,} prompts · canonical release "
        f"{metadata['canonical_release']}. All other prompts remain visible in gray; "
        "select a red point to inspect its response and v2.4 fields."
    )
    if filtered.empty:
        st.warning("No genuine refusals match these filters.")
        return

    mapped, chosen = prompt_map(points, filtered)
    if not chosen:
        st.info(
            f"Showing all {len(mapped):,} prompts in gray; "
            f"{mapped.refusal_count.gt(0).sum():,} have matching refusals in red. "
            "Select a red point to inspect its refusals."
        )
        return
    show_refusal(chosen[0]["prompt_id"], filtered)


if __name__ == "__main__":
    main()
