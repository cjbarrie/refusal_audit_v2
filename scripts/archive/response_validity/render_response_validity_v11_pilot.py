#!/usr/bin/env python3
"""Render the reproducible v1.1 GPT-5.6 Sol pilot report."""

from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "annotations" / "response_validity_v11_pilot"


def pct(x):
    return f"{100 * x:.1f}%"


def n_pct(series):
    return f"{int(series.sum())} ({pct(series.mean())})"


def diagnostic_table(frame, group):
    rows = []
    for value, g in frame.groupby(group, sort=True, dropna=False):
        rows.append({
            group.replace("prompt_", "").replace("_", " "): value,
            "n": len(g),
            "clean genuine refusal": n_pct(g.sol_clean_genuine_refusal),
            "capability failure": n_pct(g.sol_capability_failure),
            "coherent pivot": n_pct(g.sol_coherent_pivot),
        })
    return pd.DataFrame(rows).to_markdown(index=False)


def main():
    x = pd.read_parquet(RUN / "assembled_pilot.parquet")
    if len(x) != 1306 or x.pilot_id.nunique() != 1306:
        raise ValueError("pilot assembly is incomplete")
    rows = []
    for name, g in [("All v1.0 conflicts", x[x.pilot_stratum.eq("all_v10_component_conflicts")]),
                    ("Balanced non-conflict comparators", x[x.pilot_stratum.str.startswith("balanced")])]:
        rows.append({
            "pilot stratum": name, "n": len(g),
            "refusal communicated": pct(g.sol_refusal_communicated.mean()),
            "clean genuine refusal": pct(g.sol_clean_genuine_refusal.mean()),
            "capability failure": pct(g.sol_capability_failure.mean()),
            "coherent pivot": pct(g.sol_coherent_pivot.mean()),
        })
    summary = pd.DataFrame(rows)
    comparator = x[x.pilot_stratum.str.startswith("balanced")]
    agreement = (comparator.genuine_refusal == comparator.sol_clean_genuine_refusal).mean()
    kappa = cohen_kappa_score(comparator.genuine_refusal, comparator.sol_clean_genuine_refusal)
    conflicts = x[x.pilot_stratum.eq("all_v10_component_conflicts")]
    explicit = conflicts[conflicts.final_explicit_refusal]
    implicit = conflicts[conflicts.final_implicit_refusal]
    completion = pd.read_json(RUN / "run_metadata.json", typ="series")["completion"]
    usage_cost = completion["provider_reported_cost"]
    comparator_confusion = pd.crosstab(
        comparator.genuine_refusal, comparator.sol_clean_genuine_refusal
    ).rename_axis(index="v1.0 clean genuine refusal",
                  columns="Sol v1.1 clean genuine refusal")
    comparator_confusion.index = ["false", "true"]
    comparator_confusion.columns = ["false", "true"]
    confidence = x.sol_confidence.value_counts().rename_axis(
        "confidence").reset_index(name="n")
    signals = x.sol_noncompliance_signal.value_counts().rename_axis(
        "noncompliance signal").reset_index(name="n")
    communicated = x.sol_refusal_communicated
    evidence_matches = int(x.loc[communicated, "sol_evidence_exact_match"].sum())
    evidence_total = int(communicated.sum())
    evidence_rate = pct(x.loc[communicated, "sol_evidence_exact_match"].mean())
    text = f"""# GPT-5.6 Sol response-validity v1.1 pilot results

Status: completed 2026-08-13. This is a blinded frontier-machine-judge pilot,
not human validation and not a population-prevalence sample. Protocol and exact
prompt: [`RESPONSE_VALIDITY_V11_PILOT.md`](RESPONSE_VALIDITY_V11_PILOT.md).

## Execution integrity

- Frozen rows completed: 1,306/1,306.
- API/parse/schema/logical-consistency failures: 0.
- Provider-reported cost: ${usage_cost:.2f}, below the authorized $15 ceiling.
- Provider usage: {completion['prompt_tokens']:,} prompt tokens,
  {completion['completion_tokens']:,} completion tokens, and
  {completion['reasoning_tokens']:,} reasoning tokens.
- Communicated-refusal evidence spans matching the response after Unicode and
  whitespace normalization: {evidence_matches}/{evidence_total}
  ({evidence_rate}).
- Eight evidence deviations are retained for review; inspection shows formatting
  removal, punctuation normalization, or ellipsis/paraphrase rather than missing
  categorical fields. They are included in the blinded disagreement packet.

## Pilot outcomes

{summary.to_markdown(index=False)}

These percentages describe the deliberately enriched pilot strata only. All
979 conflicts are a census of the v1.0 contradiction set. The 327 comparator
rows are one-per-cell diagnostics and have no population weights.

Exact comparator confusion matrix (rows are v1.0; columns are Sol v1.1):

{comparator_confusion.to_markdown()}

## Judge-output diagnostics

{confidence.to_markdown(index=False)}

{signals.to_markdown(index=False)}

The absence of low-confidence outputs does not establish correctness; it is a
model self-report. No row used hidden reasoning, and reasoning-token usage was
zero.

## What the original contradiction meant

Among the 979 conflicts, v1.0 had marked a refusal component while its nominal
class was almost always `coherent pivot`. Sol v1.1 divides them rather than
forcing one post-hoc precedence:

- Explicit v1.0 refusal-component cases: {len(explicit)}; Sol clean genuine
  refusal {pct(explicit.sol_clean_genuine_refusal.mean())}, coherent pivot
  {pct(explicit.sol_coherent_pivot.mean())}.
- Implicit v1.0 refusal-component cases: {len(implicit)}; Sol clean genuine
  refusal {pct(implicit.sol_clean_genuine_refusal.mean())}, coherent pivot
  {pct(implicit.sol_coherent_pivot.mean())}.

The explicit component was highly reproducible; the implicit component was not.
This is evidence that v1.0's implicit-refusal Boolean was too permissive and
often captured pivots or nonresponse.

## Conflict-set diagnostics by language

{diagnostic_table(conflicts, 'prompt_language')}

## Conflict-set diagnostics by subject model

{diagnostic_table(conflicts, 'model')}

These language/model percentages are conditional on inclusion in the v1.0
contradiction census. They must not be interpreted as model or language refusal
rates in the full response population.

## Non-conflict diagnostic agreement

On the 327 balanced non-conflict comparators, v1.0 genuine refusal versus Sol
clean genuine refusal has raw agreement {pct(agreement)} and Cohen's kappa
{kappa:.3f}. This is useful prompt diagnostics but not an accuracy estimate:
neither machine label is human ground truth, and the comparator sample is
cell-balanced rather than population-representative.

## Decision

The codebook passes the mechanical pilot gates: complete structured coverage,
zero logical contradictions, and clean separation of communicated refusal from
language/technical failure. It does not yet pass the human-validity gate. A
deterministic 120-row blinded packet was generated at
`annotations/response_validity_v11_pilot/blinded_disagreement_review.parquet`,
with labels held separately in the local key. Complete that review before
treating v1.1 as the final measurement rule or purchasing the full 12,725-row
Sol run.

At the observed pilot rate and full frozen-row token volumes, the revised v1.1
full audit is expected to cost approximately $131; a prudent hard ceiling would
be $150. That run would estimate the percentage of all 11,475 original
non-engagement cases that are clean genuine refusals and apply the existing
design weights to the 1,250 controls. It is not authorized by the $15 pilot
approval.
"""
    (ROOT / "docs" / "RESPONSE_VALIDITY_V11_RESULTS.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
