#!/usr/bin/env python3
"""Render deterministic response-validity tables and a technical Markdown report."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "annotations" / "response_validity_v1"


def markdown_table(frame, n=None):
    if n is not None: frame = frame.head(n)
    return frame.to_markdown(index=False, floatfmt=".3f")


def report(est_dir: Path):
    labels = pd.read_parquet(RUN / "assembled_labels.parquet")
    if len(labels) != 12725 or not labels.adjudication_complete.all():
        raise ValueError("validity labels are incomplete")
    dims = ["model", "prompt_language", "controversy_tier", "topic_domain", "region_focus"]
    outcomes = ["original_nonengagement", "genuine_refusal", "capability_failure", "substantive_pivot", "coherent_noncompliance"]
    tables = {}
    for dim in dims:
        census = labels.loc[labels.audit_stratum.eq("original_nonengagement")]
        tab = census.groupby(dim, dropna=False)[outcomes].agg(["sum", "mean"])
        tab.columns = [f"{a}_{b}" for a, b in tab.columns]
        tab = tab.reset_index().assign(audit_stratum="original_nonengagement_census")
        tab.to_csv(RUN / f"counts_by_{dim}.csv", index=False)
        tables[dim] = tab

    controls = labels.loc[labels.audit_stratum.eq("original_nonrefusal_control")].copy()
    w = controls.control_sampling_weight.astype(float)
    control_rates = pd.DataFrame({
        "outcome": outcomes[1:],
        "sample_n": len(controls),
        "weighted_population_total": [float((controls[o].astype(float) * w).sum()) for o in outcomes[1:]],
        "weighted_rate": [float((controls[o].astype(float) * w).sum() / w.sum()) for o in outcomes[1:]],
    })
    control_rates.to_csv(RUN / "weighted_control_outcomes.csv", index=False)

    usage_path = RUN / "provider_usage.csv"
    usage = pd.read_csv(usage_path) if usage_path.exists() else pd.DataFrame()
    total_cost = usage.provider_cost.fillna(0).sum() if "provider_cost" in usage else float("nan")
    agreement = pd.read_csv(RUN / "agreement_summary.csv")
    c24p = est_dir / "c24_language_response_validity.csv"
    c25p = est_dir / "c25_home_response_validity_sensitivity.csv"
    c24 = pd.read_csv(c24p) if c24p.exists() else pd.DataFrame()
    c25 = pd.read_csv(c25p) if c25p.exists() else pd.DataFrame()

    # Examples are algorithmic: highest deterministic diagnostic score, then
    # audit_id, within each class. This avoids rhetorical hand-picking.
    score_cols = [c for c in labels if c.startswith("diag_") and labels[c].dtype != object]
    score = pd.Series(0.0, index=labels.index)
    for c in score_cols:
        v = pd.to_numeric(labels[c], errors="coerce").fillna(0).astype(float)
        if v.max() > v.min(): v = (v - v.min()) / (v.max() - v.min())
        score += v
    ex = labels.assign(selection_score=score).sort_values(["primary_class", "selection_score", "audit_id"], ascending=[True, False, True]).groupby("primary_class", group_keys=False).head(2)
    examples = ex[["primary_class", "model", "prompt_language", "audit_id", "selection_score", "prompt_text", "response_text"]].copy()
    examples["prompt_excerpt"] = examples.pop("prompt_text").fillna("").str.replace(r"\s+", " ", regex=True).str.slice(0, 180)
    examples["response_excerpt"] = examples.pop("response_text").fillna("").str.replace(r"\s+", " ", regex=True).str.slice(0, 240)
    examples.to_csv(RUN / "deterministic_examples.csv", index=False)

    text = f"""# Response-validity results

Generated reproducibly by `scripts/render_response_validity_report.py` from the complete assembled audit. This is a dual-machine-judge audit with adjudication; it is **not human-validated** until independent decisions for the blinded 600-row packet are complete.

## Coverage and agreement

- Audited rows: {len(labels):,}.
- Original code-4/5 census: {int(labels.original_nonengagement.sum()):,}.
- Original-nonrefusal controls: {int((labels.audit_stratum == 'original_nonrefusal_control').sum()):,}; aggregate diagnostic rates use the recorded sampling weights.
- Required/completed adjudications: {int(labels.adjudication_required.sum()):,} / {int((labels.adjudication_required & labels.adjudication_complete).sum()):,}.
- Component/primary-class conflicts retained and resolved by declared analytic-state precedence: {int(labels.primary_component_conflict.sum()):,}.
- Provider-reported cost: {total_cost:.2f} (currency as reported by provider).

{markdown_table(agreement)}

## Counts by language

{markdown_table(tables['prompt_language'])}

## Counts by model

{markdown_table(tables['model'])}

## Weighted outcomes among original-nonrefusal controls

These Hájek rates use the exact recorded inclusion probabilities from the stratified 1,250-row validation sample. They estimate diagnostic prevalence among the 125,711 original code-1–3 responses; they are not raw sample percentages.

{markdown_table(control_rates)}

## Prompt-paired language contrasts

{markdown_table(c24) if len(c24) else 'Pending stage-17 canonical estimates.'}

## Home-standardization sensitivity

{markdown_table(c25) if len(c25) else 'Pending stage-17 canonical estimates.'}

## Deterministically selected examples

Rows are the top two per final primary class under the sum of normalized deterministic diagnostic flags/rates, ties broken by `audit_id`. They are not hand-picked for rhetorical effect.

{markdown_table(examples)}

## Interpretation

Original judge-coded non-engagement, genuine refusal, capability failure, and substantive pivot are separate outcomes. Unpaired model/language prevalence tables are descriptive. c24 holds prompt and model fixed; c25 is covariate-standardized association and is not causal. Machine agreement is not accuracy.
"""
    (ROOT / "docs" / "RESPONSE_VALIDITY_RESULTS.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--est-dir", type=Path, default=ROOT / "pipeline" / "estimates" / "canonical")
    report(p.parse_args().est_dir)
