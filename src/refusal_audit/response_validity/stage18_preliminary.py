"""Direct design-weighted v2.2 estimates before population student prediction.

This local diagnostic uses only the frozen 300-case probability sample for
estimation. The enrichment sample contributes no population weight. Exact
first- and second-order inclusion probabilities from the three-component union
design provide the human-sampling variance. Estimates condition on the frozen
137,186-response population and do not yet include whole-issue or student-fit
uncertainty required for a final canonical release.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .estimand_precision import _variance, build_estimand_coefficients
from .human_audit import exact_union_pairwise_inclusion
from .human_pilot import KEY, sha_file


PILOT = "annotations/response_validity_human_v2"
HARMONIZED = (
    "annotations/response_validity_human_v2/decomposed_review_v2_2/"
    "harmonized_evaluation_gold_v2_2.parquet"
)
POPULATION = "annotations/response_validity_dsl_v1_1/wall_to_wall_features.parquet"
OUTPUT = "annotations/response_validity_human_v2/stage18_preliminary_v2_2"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_preliminary_stage18(root: Path, output_dir: Path | None = None) -> dict:
    """Estimate direct HT v2.2 quantities and diagnose home-event support."""
    output_dir = output_dir or root / OUTPUT
    population_path = root / POPULATION
    design_path = root / PILOT / "pilot_design.parquet"
    pilot_manifest_path = root / PILOT / "pilot_manifest.json"
    harmonized_path = root / HARMONIZED
    inputs = [population_path, design_path, pilot_manifest_path, harmonized_path]
    for path in inputs:
        if not path.exists():
            raise FileNotFoundError(path)
    input_hashes = {str(path.relative_to(root)): sha_file(path) for path in inputs}
    input_hashes["implementation:stage18_preliminary.py"] = sha_file(Path(__file__))

    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("input_sha256") != input_hashes:
            raise RuntimeError("existing Stage 18 diagnostic uses different inputs")
        for name, expected in existing.get("artifact_sha256", {}).items():
            path = output_dir / name
            if not path.exists() or sha_file(path) != expected:
                raise RuntimeError(f"Stage 18 diagnostic artifact changed: {path}")
        return existing
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested output directory: {output_dir}")

    population = pd.read_parquet(population_path)
    design = pd.read_parquet(design_path).sort_values("review_order").reset_index(drop=True)
    gold = pd.read_parquet(harmonized_path)
    if len(population) != 137_186 or population.duplicated(KEY).any():
        raise ValueError("Stage 18 diagnostic requires 137,186 unique population rows")
    if len(design) != 300 or design.review_id.duplicated().any():
        raise ValueError("Stage 18 diagnostic requires the frozen 300-case design")
    if len(gold) != 700 or gold.review_id.duplicated().any():
        raise ValueError("harmonized gold must contain 700 unique human rows")
    if gold.headline_label_status.eq("unresolved").any():
        raise ValueError("harmonized gold still contains unresolved headline labels")

    labels = gold.loc[gold.human_sample_source.eq("probability_300"), [
        "review_id", *KEY, "human_genuine_refusal_v2_2",
        "human_capability_failure_v2_2", "headline_label_status",
    ]]
    sample = design.merge(labels, on=["review_id", *KEY], validate="one_to_one")
    if len(sample) != 300:
        raise ValueError("all 300 probability-sample labels must be harmonized")
    if sample[["human_genuine_refusal_v2_2", "human_capability_failure_v2_2"]].isna().any().any():
        raise ValueError("probability sample contains missing v2.2 outcomes")

    pilot_manifest = json.loads(pilot_manifest_path.read_text(encoding="utf-8"))
    pairwise = exact_union_pairwise_inclusion(sample, population, pilot_manifest)
    pi = sample.inclusion_probability.to_numpy(float)
    variance_coefficient = (pairwise - np.outer(pi, pi)) / pairwise
    pop_index = pd.MultiIndex.from_frame(population[KEY])
    sample_positions = pop_index.get_indexer(pd.MultiIndex.from_frame(sample[KEY]))
    if (sample_positions < 0).any():
        raise ValueError("probability-sample key absent from population")

    outcomes = {
        "genuine_refusal": sample.human_genuine_refusal_v2_2.astype(float).to_numpy(),
        "capability_failure": sample.human_capability_failure_v2_2.astype(float).to_numpy(),
    }
    rows: list[dict] = []
    for spec in build_estimand_coefficients(population):
        a = spec["coefficients"]
        a_s = a[sample_positions]
        active = np.abs(a_s) > 1e-15
        for outcome, y in outcomes.items():
            contribution = a_s * y / pi
            estimate = float(contribution.sum())
            se = math.sqrt(_variance(contribution, variance_coefficient))
            event = y > 0.5
            positive_events = int(np.sum(event & (a_s > 1e-15)))
            negative_events = int(np.sum(event & (a_s < -1e-15)))
            is_contrast = bool(np.any(a > 0) and np.any(a < 0))
            support_ok = int(active.sum()) >= 20 and int(np.sum(active & event)) >= 5
            if is_contrast:
                support_ok = support_ok and positive_events >= 2 and negative_events >= 2
            half_width_pp = 1.96 * se * 100
            width_ok = half_width_pp <= spec["target_half_width_pp"]
            rows.append({
                "family": spec["family"],
                "cell": spec["cell"],
                "paper_role": spec["paper_role"],
                "outcome": outcome,
                "estimator": "direct_horvitz_thompson",
                "estimate": estimate,
                "std_error_human_design": se,
                "conf_low_unbounded": estimate - 1.96 * se,
                "conf_high_unbounded": estimate + 1.96 * se,
                "sample_contributing_rows": int(active.sum()),
                "sample_events": int(np.sum(active & event)),
                "positive_arm_events": positive_events,
                "negative_arm_events": negative_events,
                "support_adequate": support_ok,
                "target_half_width_pp": spec["target_half_width_pp"],
                "observed_half_width_pp": half_width_pp,
                "width_target_met": width_ok,
                "ready_on_direct_human_labels": support_ok and width_ok,
            })
    estimates = pd.DataFrame(rows)
    main = estimates.loc[
        estimates.paper_role.eq("main")
        & estimates.family.isin(["prevalence", "paired_language", "standardized_home"])
    ].copy()
    home = estimates.loc[
        estimates.family.isin(["standardized_home", "home_by_model_descriptive"])
    ].copy()
    home["recommendation"] = np.where(
        home.ready_on_direct_human_labels,
        "provisional estimate supported by current human events",
        "do not treat as settled; add targeted probability-sample labels if retained",
    )

    output_dir.mkdir(parents=True, exist_ok=False)
    estimates_path = output_dir / "direct_estimates.csv"
    main_path = output_dir / "main_estimands.csv"
    home_path = output_dir / "home_support.csv"
    estimates.to_csv(estimates_path, index=False)
    main.to_csv(main_path, index=False)
    home.to_csv(home_path, index=False)
    summary = {
        "version": "stage18-preliminary-direct-v2.2",
        "created_at": _now(),
        "status": "complete_provisional_diagnostic",
        "n_population": len(population),
        "n_probability_sample": len(sample),
        "n_direct_v2_2_in_probability_sample": int(
            sample.headline_label_status.eq("direct_v2_2").sum()
        ),
        "n_mapped_v2_1_clear_in_probability_sample": int(
            sample.headline_label_status.eq("mapped_v2_1_clear").sum()
        ),
        "outcomes": list(outcomes),
        "variance": "exact pairwise inclusion variance for the frozen three-component human sample",
        "conditioning": (
            "conditions on the delivered 137,186-response population; whole-issue and "
            "student-fit uncertainty are not included"
        ),
        "network_call_made": False,
        "input_sha256": input_hashes,
        "artifact_sha256": {
            estimates_path.name: sha_file(estimates_path),
            main_path.name: sha_file(main_path),
            home_path.name: sha_file(home_path),
        },
    }
    manifest_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
