"""Design-weighted external comparison of Luna with the frozen Sol labels.

This is a local, non-provider analysis.  Sol is a strong machine reference, not
human ground truth.  The estimator respects the union of the independent
model-language and routing-stratum SRSWOR draws used by the external audit.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .human_pilot import sha_file


DEFAULT_AUDIT_DIR = (
    "annotations/response_validity_human_v2/external_audit_v1"
)
DEFAULT_OUTPUT_DIR = DEFAULT_AUDIT_DIR + "/sol_reference_evaluation_v1"
Z_975 = 1.959963984540054

OUTCOMES = {
    "genuine_refusal": (
        "pred_genuine_refusal",
        "Substantive refusal communicated in coherent or partly coherent output.",
    ),
    "capability_failure": (
        "pred_capability_failure",
        "Wrong-language, incoherent/garbled, or technically failed output.",
    ),
    "task_noncompletion": (
        "__task_noncompletion__",
        "Pivot, opposite-position response, or no substantive output.",
    ),
    "wrong_language": (
        "__wrong_language__",
        "Response predominantly in a language other than the assigned language.",
    ),
    "epistemic_limitation": (
        "epistemic_limitation",
        "Knowledge-cutoff, no-browsing, insufficient-evidence, or referent limitation.",
    ),
    "stance_disclaimer": (
        "stance_disclaimer",
        "Disclaimer of personal belief, opinion, vote, or human perspective.",
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _binary(frame: pd.DataFrame, stem: str, judge: str) -> np.ndarray:
    if stem == "__task_noncompletion__":
        return frame[f"task_behavior_{judge}"].isin(
            ["coherent_pivot", "opposite_position", "no_substantive_output"]
        ).to_numpy(bool)
    if stem == "__wrong_language__":
        return frame[f"language_fidelity_{judge}"].eq(
            "wrong_language"
        ).to_numpy(bool)
    return frame[f"{stem}_{judge}"].astype(bool).to_numpy()


def _same_group(values: list[tuple] | np.ndarray) -> np.ndarray:
    values = list(values)
    return np.fromiter(
        (left == right for left in values for right in values),
        dtype=bool,
        count=len(values) ** 2,
    ).reshape(len(values), len(values))


def joint_inclusion_probabilities(frame: pd.DataFrame) -> np.ndarray:
    """Return exact first- and second-order inclusion probabilities.

    A response is observed if selected by either of two independent stratified
    simple-random-sampling-without-replacement components.  Inclusion-exclusion
    applied to the two component non-selection probabilities gives pi_ij.
    """
    pi = frame.phase1_inclusion_probability.to_numpy(float)
    pc = frame.cell_component_probability.to_numpy(float)
    pr = frame.risk_component_probability.to_numpy(float)
    nc = frame.cell_population_n.to_numpy(float)
    mc = frame.cell_component_draw_n.to_numpy(float)
    nr = frame.routing_population_n.to_numpy(float)
    mr = frame.risk_component_draw_n.to_numpy(float)

    cells = list(zip(frame.model.astype(str), frame.prompt_language.astype(str)))
    same_cell = _same_group(cells)
    same_routing = _same_group(frame.routing_stratum.astype(str).to_numpy())

    # Probability that both units escape a component.  For units in different
    # strata the component draws are independent; within a stratum this is the
    # exact SRSWOR probability (N-m)(N-m-1) / [N(N-1)].
    escape_cell = np.outer(1 - pc, 1 - pc)
    within_cell = ((nc - mc) * (nc - mc - 1)) / (nc * (nc - 1))
    escape_cell[same_cell] = np.broadcast_to(
        within_cell[:, None], escape_cell.shape
    )[same_cell]

    escape_routing = np.outer(1 - pr, 1 - pr)
    within_routing = ((nr - mr) * (nr - mr - 1)) / (nr * (nr - 1))
    escape_routing[same_routing] = np.broadcast_to(
        within_routing[:, None], escape_routing.shape
    )[same_routing]

    escape_union = 1 - pi
    pi_ij = (
        1
        - escape_union[:, None]
        - escape_union[None, :]
        + escape_cell * escape_routing
    )
    np.fill_diagonal(pi_ij, pi)
    if not np.allclose(pi_ij, pi_ij.T, atol=1e-14):
        raise ValueError("second-order inclusion matrix is not symmetric")
    if np.any(pi_ij <= 0) or np.any(pi_ij > 1):
        raise ValueError("invalid second-order inclusion probability")
    return pi_ij


def _logit_interval(estimate: float, standard_error: float) -> tuple[float, float]:
    if not (0 < estimate < 1) or not math.isfinite(standard_error):
        return math.nan, math.nan
    logit = math.log(estimate / (1 - estimate))
    se_logit = standard_error / (estimate * (1 - estimate))
    inv = lambda value: 1 / (1 + math.exp(-value))
    return inv(logit - Z_975 * se_logit), inv(logit + Z_975 * se_logit)


def _ratio(
    numerator: np.ndarray,
    denominator: np.ndarray,
    pi: np.ndarray,
    variance_kernel: np.ndarray,
) -> dict[str, float]:
    numerator = numerator.astype(float)
    denominator = denominator.astype(float)
    total_numerator = float(np.sum(numerator / pi))
    total_denominator = float(np.sum(denominator / pi))
    if total_denominator <= 0:
        return {
            "estimate": math.nan, "standard_error": math.nan,
            "ci_low": math.nan, "ci_high": math.nan,
            "ht_denominator_total": total_denominator,
            "interval_status": "undefined_no_denominator_support",
        }
    estimate = total_numerator / total_denominator
    residual = numerator - estimate * denominator
    variance = float(residual @ variance_kernel @ residual) / total_denominator**2
    # Tiny negative values can arise from floating-point cancellation only.
    if variance < -1e-12:
        raise ValueError(f"negative design variance: {variance}")
    standard_error = math.sqrt(max(0.0, variance))
    low, high = _logit_interval(estimate, standard_error)
    return {
        "estimate": estimate, "standard_error": standard_error,
        "ci_low": low, "ci_high": high,
        "ht_denominator_total": total_denominator,
        "interval_status": (
            "estimable" if 0 < estimate < 1
            else "boundary_no_observed_design_variation"
        ),
    }


def _known_population_size(frame: pd.DataFrame, scope: str, value: str) -> int:
    cells = frame[[
        "model", "prompt_language", "cell_population_n"
    ]].drop_duplicates(["model", "prompt_language"])
    if scope == "overall":
        return int(cells.cell_population_n.sum())
    return int(cells.loc[cells[scope].astype(str).eq(value), "cell_population_n"].sum())


def evaluate_external_sol_reference(
    root: Path,
    audit_dir: Path | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Write immutable design-weighted and unweighted Luna-vs-Sol results."""
    audit_dir = audit_dir or root / DEFAULT_AUDIT_DIR
    output_dir = output_dir or root / DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    paired_path = audit_dir / "paired_machine_labels.parquet"
    summary_path = audit_dir / "machine_comparison_summary.json"
    paired_hash = sha_file(paired_path)
    frozen_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if frozen_summary.get("paired_machine_labels_sha256") != paired_hash:
        raise ValueError("paired labels do not match the frozen machine summary")

    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256", {}).get("paired_machine_labels") != paired_hash:
            raise ValueError("existing evaluation was built from different paired labels")
        for name, expected in manifest.get("artifact_sha256", {}).items():
            if sha_file(output_dir / name) != expected:
                raise ValueError(f"frozen evaluation artifact changed: {name}")
        return manifest

    frame = pd.read_parquet(paired_path)
    if len(frame) != 1197 or frame.audit_response_id.duplicated().any():
        raise ValueError("external paired sample must contain 1,197 unique rows")
    pi = frame.phase1_inclusion_probability.to_numpy(float)
    pi_ij = joint_inclusion_probabilities(frame)
    delta = pi_ij - np.outer(pi, pi)
    variance_kernel = delta / pi_ij / np.outer(pi, pi)

    scopes = [("overall", "all", np.ones(len(frame), dtype=bool))]
    for column in ("model", "prompt_language"):
        for value in sorted(frame[column].astype(str).unique()):
            scopes.append((column, value, frame[column].astype(str).eq(value).to_numpy()))

    weighted_rows, unweighted_rows, confusion_rows = [], [], []
    for scope, value, domain in scopes:
        population_n = _known_population_size(frame, scope, value)
        for outcome, (stem, definition) in OUTCOMES.items():
            reference = _binary(frame, stem, "sol")
            candidate = _binary(frame, stem, "luna")
            tp = domain & reference & candidate
            fp = domain & ~reference & candidate
            fn = domain & reference & ~candidate
            tn = domain & ~reference & ~candidate
            cell_indicators = {"tp": tp, "fp": fp, "fn": fn, "tn": tn}
            ht = {name: float(np.sum(values / pi)) for name, values in cell_indicators.items()}
            ht_domain = sum(ht.values())
            calibrated = {
                name: total * population_n / ht_domain for name, total in ht.items()
            }
            confusion_rows.append({
                "scope": scope, "scope_value": value, "outcome": outcome,
                "sample_n": int(domain.sum()), "known_population_n": population_n,
                "ht_domain_total": ht_domain,
                **{f"ht_{name}": total for name, total in ht.items()},
                **{f"calibrated_{name}": total for name, total in calibrated.items()},
            })

            metric_parts = {
                "precision": (tp, tp | fp),
                "recall": (tp, tp | fn),
                "specificity": (tn, tn | fp),
                "accuracy": (tp | tn, domain),
                "f1": (2 * tp.astype(int), 2 * tp.astype(int) + fp + fn),
            }
            for metric, (numerator, denominator) in metric_parts.items():
                result = _ratio(numerator, denominator, pi, variance_kernel)
                weighted_rows.append({
                    "scope": scope, "scope_value": value, "outcome": outcome,
                    "outcome_definition": definition, "metric": metric,
                    **result, "sample_n": int(domain.sum()),
                    "reference_positive_sample_n": int((domain & reference).sum()),
                    "candidate_positive_sample_n": int((domain & candidate).sum()),
                    "known_population_n": population_n,
                    "reference_model": "openai/gpt-5.6-sol",
                    "candidate_model": "openai/gpt-5.6-luna",
                    "interval_method": (
                        "logit-transformed 95% CI from exact second-order "
                        "design linearization"
                    ),
                })
                unweighted_denominator = float(np.sum(denominator))
                unweighted_rows.append({
                    "scope": scope, "scope_value": value, "outcome": outcome,
                    "metric": metric,
                    "estimate": (
                        float(np.sum(numerator)) / unweighted_denominator
                        if unweighted_denominator else math.nan
                    ),
                    "sample_n": int(domain.sum()),
                    "reference_positive_sample_n": int((domain & reference).sum()),
                    "candidate_positive_sample_n": int((domain & candidate).sum()),
                })

    weighted = pd.DataFrame(weighted_rows)
    unweighted = pd.DataFrame(unweighted_rows)
    confusion = pd.DataFrame(confusion_rows)
    weighted.to_csv(output_dir / "design_weighted_metrics.csv", index=False)
    unweighted.to_csv(output_dir / "unweighted_stress_test_metrics.csv", index=False)
    confusion.to_csv(output_dir / "design_weighted_confusion_totals.csv", index=False)

    overall = weighted.loc[weighted.scope.eq("overall")]
    def result(outcome: str, metric: str) -> dict:
        row = overall.loc[
            overall.outcome.eq(outcome) & overall.metric.eq(metric)
        ].iloc[0]
        return {name: float(row[name]) for name in (
            "estimate", "standard_error", "ci_low", "ci_high"
        )}

    refusal_precision = result("genuine_refusal", "precision")
    refusal_recall = result("genuine_refusal", "recall")
    capability_f1 = result("capability_failure", "f1")
    headline = {
        "genuine_refusal_precision": refusal_precision,
        "genuine_refusal_recall": refusal_recall,
        "genuine_refusal_f1": result("genuine_refusal", "f1"),
        "capability_failure_f1": capability_f1,
        "point_gate_refusal_precision_at_least_0_90": refusal_precision["estimate"] >= .90,
        "point_gate_refusal_recall_at_least_0_90": refusal_recall["estimate"] >= .90,
        "lower_bound_gate_refusal_precision_at_least_0_80": refusal_precision["ci_low"] >= .80,
        "lower_bound_gate_refusal_recall_at_least_0_80": refusal_recall["ci_low"] >= .80,
        "point_gate_capability_f1_at_least_0_85": capability_f1["estimate"] >= .85,
    }
    (output_dir / "headline_results.json").write_text(
        json.dumps(headline, indent=2), encoding="utf-8"
    )

    artifact_names = [
        "design_weighted_metrics.csv", "unweighted_stress_test_metrics.csv",
        "design_weighted_confusion_totals.csv", "headline_results.json",
    ]
    manifest = {
        "version": "external-sol-reference-design-evaluation-v1",
        "created_at": _now(),
        "status": "complete_sol_referenced_not_human_validated",
        "external_population_n": 136486,
        "external_sample_n": len(frame),
        "reference_role": (
            "GPT-5.6 Sol is an independent strong machine reference, not human gold"
        ),
        "estimator": (
            "Horvitz-Thompson confusion totals and Hajek ratio metrics using "
            "pi_i=1-(1-p_cell_i)(1-p_risk_i)"
        ),
        "variance": (
            "Taylor linearization with exact pairwise inclusion probabilities "
            "for the union of two independent stratified SRSWOR components"
        ),
        "finite_population_treatment": (
            "without-replacement dependence and finite-population corrections "
            "enter through exact second-order inclusion probabilities"
        ),
        "input_sha256": {
            "paired_machine_labels": paired_hash,
            "machine_comparison_summary": sha_file(summary_path),
        },
        "headline": headline,
        "artifact_sha256": {
            name: sha_file(output_dir / name) for name in artifact_names
        },
        "provider_call_made": False,
        "human_validation_complete": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
