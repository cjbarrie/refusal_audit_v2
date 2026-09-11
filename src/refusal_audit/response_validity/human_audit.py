"""Freeze and audit the completed non-repeat human response-validity pilot.

All functions are local and make no network calls.  The freeze reads only IDs
belonging to ``pilot_design.parquet``; silent-repeat IDs are neither joined nor
analyzed.  Preliminary estimates use the pilot's exact union inclusion
probabilities and label their one-coder status explicitly.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .human_pilot import KEY, PRIMARY_CLASSES, sha_file, sha_text, validate_human_label


DERIVED_OUTCOMES = {
    "genuine_refusal": {"genuine_refusal"},
    "capability_failure": {
        "incoherent_garbled", "wrong_language", "technical_degeneration",
    },
    "coherent_pivot": {"coherent_pivot"},
    "coherent_noncompliance": {"genuine_refusal", "coherent_pivot"},
    "coherent_answer": {"coherent_answer"},
    "ambiguous": {"ambiguous"},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: invalid JSON on line {line_no}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}: line {line_no} is not a JSON object")
        rows.append(value)
    return rows


def _canonical_records_hash(records: Iterable[dict]) -> str:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in records]
    return sha_text("\n".join(sorted(lines)))


def _write_jsonl(path: Path, records: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def build_language_corrected_base_labels(
    root: Path,
    pilot_dir: Path,
    output_dir: Path | None = None,
) -> dict:
    """Apply coder-confirmed language amendments without altering v1 labels.

    The amendment file is an append-only audit trail. Each record declares
    exact before/after values, so application fails if either the frozen base
    or the amendment history differs from what the coder reviewed.
    """
    base_dir = pilot_dir / "base_freeze_v1"
    base_path = base_dir / "base_labels.parquet"
    base_manifest_path = base_dir / "freeze_manifest.json"
    amendments_path = pilot_dir / "human_language_amendments_v1.jsonl"
    codebook_path = root / "config" / "response_validity_codebook_v2.json"
    output_dir = output_dir or pilot_dir / "base_freeze_v2_language_corrected"
    for path in [base_path, base_manifest_path, amendments_path, codebook_path]:
        if not path.exists():
            raise FileNotFoundError(path)

    base_manifest = json.loads(base_manifest_path.read_text(encoding="utf-8"))
    if sha_file(base_path) != base_manifest["artifact_sha256"]["base_labels.parquet"]:
        raise RuntimeError("v1 base labels differ from their immutable manifest")
    amendments = _read_jsonl(amendments_path)
    if not amendments:
        raise ValueError("language-amendment file is empty")
    amendment_ids = [str(row.get("review_id")) for row in amendments]
    if len(set(amendment_ids)) != len(amendment_ids):
        raise ValueError("duplicate review_id in language amendments")

    manifest_path = output_dir / "freeze_manifest.json"
    input_hashes = {
        "v1_freeze_manifest_sha256": sha_file(base_manifest_path),
        "v1_base_labels_sha256": sha_file(base_path),
        "language_amendments_sha256": sha_file(amendments_path),
        "codebook_sha256": sha_file(codebook_path),
    }
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("input_sha256") != input_hashes:
            raise RuntimeError("existing corrected freeze was built from different inputs")
        for name, expected in existing.get("artifact_sha256", {}).items():
            path = output_dir / name
            if not path.exists() or sha_file(path) != expected:
                raise RuntimeError(f"corrected artifact missing or changed: {path}")
        return existing
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested corrected-freeze directory: {output_dir}")

    labels = pd.read_parquet(base_path).copy()
    if labels.review_id.duplicated().any() or len(labels) != 300:
        raise ValueError("v1 base must contain 300 unique review IDs")
    labels = labels.set_index("review_id", drop=False)
    applied_rows: list[dict] = []
    for amendment in amendments:
        review_id = str(amendment.get("review_id"))
        if review_id not in labels.index:
            raise ValueError(f"amendment references unknown review_id: {review_id}")
        if amendment.get("status") != "coder_confirmed":
            raise ValueError(f"amendment is not coder-confirmed: {review_id}")
        if str(amendment.get("coder_id")) != str(labels.at[review_id, "coder_id"]):
            raise ValueError(f"coder mismatch for amendment: {review_id}")
        before = amendment.get("before")
        after = amendment.get("after")
        if not isinstance(before, dict) or not isinstance(after, dict) or set(before) != set(after):
            raise ValueError(f"amendment must have matched before/after fields: {review_id}")
        for field, expected in before.items():
            if field not in labels.columns or labels.at[review_id, field] != expected:
                raise ValueError(f"before value does not match v1 for {review_id}.{field}")
        for field, value in after.items():
            labels.at[review_id, field] = value
        applied_rows.append({
            "review_id": review_id,
            "changed_fields": sorted(after),
            "reviewed_against_original_response": bool(
                amendment.get("reviewed_against_original_response")
            ),
        })

    labels = labels.reset_index(drop=True).sort_values("review_order").reset_index(drop=True)
    codebook = json.loads(codebook_path.read_text(encoding="utf-8"))
    for row in labels.to_dict("records"):
        errors = validate_human_label(row, codebook)
        if errors:
            raise ValueError(f"invalid corrected label {row['review_id']}: {errors}")
    if labels.language_fidelity.eq("wrong_language").sum() != 15:
        raise ValueError("corrected freeze must contain exactly 15 wrong-language labels")
    if labels.language_fidelity.eq("mixed").sum() != 2:
        raise ValueError("corrected freeze must contain exactly two mixed-language labels")

    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "base_labels.jsonl"
    parquet_path = output_dir / "base_labels.parquet"
    records = labels.sort_values("review_id").drop(columns=["review_order"]).to_dict("records")
    _write_jsonl(jsonl_path, records)
    labels.to_parquet(parquet_path, index=False)
    manifest = {
        "freeze_version": "human-base-freeze-v2.0-language-corrected",
        "created_at": _utc_now(),
        "status": "coder_confirmed_language_review; repeat reliability pending",
        "base_v1_preserved": True,
        "repeat_records_read": False,
        "n_base_labels": len(labels),
        "n_amendments": len(amendments),
        "n_wrong_language": int(labels.language_fidelity.eq("wrong_language").sum()),
        "n_mixed_language": int(labels.language_fidelity.eq("mixed").sum()),
        "codebook_version": codebook["codebook_version"],
        "primary_class_counts_unweighted": labels.primary_class.value_counts().sort_index().astype(int).to_dict(),
        "input_sha256": input_hashes,
        "applied_amendments": applied_rows,
        "canonical_base_labels_sha256": _canonical_records_hash(records),
        "artifact_sha256": {
            "base_labels.jsonl": sha_file(jsonl_path),
            "base_labels.parquet": sha_file(parquet_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def build_complete_language_review_labels(
    root: Path,
    pilot_dir: Path,
    output_dir: Path | None = None,
) -> dict:
    """Materialize complete language fidelity after the coder reviewed all 300.

    The v2 exception coding remains immutable.  A compact coder declaration
    identifies the exact reviewed universe by hash and declares target-language
    fidelity for every nonexception row.  The resulting Parquet contains an
    explicit row-level value for all 300 responses.
    """
    source_dir = pilot_dir / "base_freeze_v2_language_corrected"
    source_path = source_dir / "base_labels.parquet"
    source_manifest_path = source_dir / "freeze_manifest.json"
    declaration_path = pilot_dir / "human_language_complete_review_v1.json"
    output_dir = output_dir or pilot_dir / "base_freeze_v3_complete_language_review"
    for path in [source_path, source_manifest_path, declaration_path]:
        if not path.exists():
            raise FileNotFoundError(path)
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if sha_file(source_path) != source_manifest["artifact_sha256"]["base_labels.parquet"]:
        raise RuntimeError("v2 corrected labels differ from their manifest")
    declaration = json.loads(declaration_path.read_text(encoding="utf-8"))
    if declaration.get("status") != "coder_confirmed" or declaration.get("n_reviewed") != 300:
        raise ValueError("complete language review is not coder-confirmed for 300 rows")

    labels = pd.read_parquet(source_path).copy()
    reviewed_hash = sha_text("\n".join(sorted(labels.review_id.astype(str))))
    if reviewed_hash != declaration.get("review_ids_sha256"):
        raise ValueError("complete-review universe hash does not match v2 labels")
    if labels.coder_id.nunique() != 1 or str(labels.coder_id.iloc[0]) != declaration.get("coder_id"):
        raise ValueError("complete-review coder does not match the frozen pilot")
    exception = labels.language_fidelity.isin(["wrong_language", "mixed"])
    if int(labels.loc[exception, "language_fidelity"].eq("wrong_language").sum()) != declaration["n_wrong_language"]:
        raise ValueError("wrong-language exception count differs from declaration")
    if int(labels.loc[exception, "language_fidelity"].eq("mixed").sum()) != declaration["n_mixed_language"]:
        raise ValueError("mixed-language exception count differs from declaration")
    labels.loc[~exception, "language_fidelity"] = declaration["default_for_all_nonexception_rows"]
    if labels.language_fidelity.isna().any() or set(labels.language_fidelity) != {"target", "mixed", "wrong_language"}:
        raise ValueError("language fidelity is not complete and exhaustive")

    manifest_path = output_dir / "freeze_manifest.json"
    input_hashes = {
        "v2_freeze_manifest_sha256": sha_file(source_manifest_path),
        "v2_base_labels_sha256": sha_file(source_path),
        "complete_review_declaration_sha256": sha_file(declaration_path),
    }
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("input_sha256") != input_hashes:
            raise RuntimeError("existing complete-review freeze uses different inputs")
        for name, expected in existing.get("artifact_sha256", {}).items():
            path = output_dir / name
            if not path.exists() or sha_file(path) != expected:
                raise RuntimeError(f"complete-review artifact missing or changed: {path}")
        return existing
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested complete-review directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "base_labels.jsonl"
    parquet_path = output_dir / "base_labels.parquet"
    records = labels.sort_values("review_id").drop(columns=["review_order"]).to_dict("records")
    _write_jsonl(jsonl_path, records)
    labels.to_parquet(parquet_path, index=False)
    manifest = {
        "freeze_version": "human-base-freeze-v3.0-complete-language-review",
        "created_at": _utc_now(),
        "status": "all_300_language_fidelity_coder_confirmed; repeats pending",
        "v1_and_v2_preserved": True,
        "repeat_records_read": False,
        "n_base_labels": len(labels),
        "language_fidelity_counts": labels.language_fidelity.value_counts().sort_index().astype(int).to_dict(),
        "primary_class_counts": labels.primary_class.value_counts().sort_index().astype(int).to_dict(),
        "input_sha256": input_hashes,
        "canonical_base_labels_sha256": _canonical_records_hash(records),
        "artifact_sha256": {
            "base_labels.jsonl": sha_file(jsonl_path),
            "base_labels.parquet": sha_file(parquet_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def freeze_completed_base_labels(
    root: Path,
    pilot_dir: Path,
    output_dir: Path | None = None,
) -> dict:
    """Create or verify an immutable snapshot of the 300 original judgments.

    The append-only live log may later acquire repeat judgments.  Membership in
    the base snapshot is determined solely by the frozen 300-row design, never
    by inspecting the repeat map or packet suffixes.
    """
    output_dir = output_dir or pilot_dir / "base_freeze_v1"
    labels_path = pilot_dir / "human_labels.jsonl"
    design_path = pilot_dir / "pilot_design.parquet"
    pilot_manifest_path = pilot_dir / "pilot_manifest.json"
    codebook_path = root / "config" / "response_validity_codebook_v2.json"
    for path in [labels_path, design_path, pilot_manifest_path, codebook_path]:
        if not path.exists():
            raise FileNotFoundError(path)

    pilot_manifest = json.loads(pilot_manifest_path.read_text(encoding="utf-8"))
    codebook = json.loads(codebook_path.read_text(encoding="utf-8"))
    design = pd.read_parquet(design_path)
    if len(design) != pilot_manifest["realized_unique_rows"] or design.review_id.duplicated().any():
        raise ValueError("pilot design is not the frozen unique-row frame")
    expected_design_hash = pilot_manifest.get("artifact_sha256", {}).get("pilot_design.parquet")
    if expected_design_hash and sha_file(design_path) != expected_design_hash:
        raise ValueError("pilot design hash differs from the frozen manifest")

    manifest_path = output_dir / "freeze_manifest.json"
    if manifest_path.exists():
        # Once frozen, the snapshot is authoritative.  Return without opening
        # the live append-only label log so later repeat judgments remain
        # entirely outside base-audit execution.
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("pilot_design_sha256") != sha_file(design_path):
            raise RuntimeError("existing base freeze points to a different pilot design")
        if existing.get("codebook_sha256") != sha_file(codebook_path):
            raise RuntimeError("existing base freeze points to a different codebook")
        for name, expected in existing.get("artifact_sha256", {}).items():
            path = output_dir / name
            if not path.exists() or sha_file(path) != expected:
                raise RuntimeError(f"frozen artifact missing or changed: {path}")
        return existing

    all_records = _read_jsonl(labels_path)
    base_ids = set(design.review_id.astype(str))
    base_records = [row for row in all_records if str(row.get("review_id")) in base_ids]
    if len(base_records) != len(design):
        observed = {str(row.get("review_id")) for row in base_records}
        missing = sorted(base_ids - observed)
        raise ValueError(f"base coding is incomplete: {len(base_records)}/{len(design)}; missing {missing[:5]}")
    keys = [(str(row.get("coder_id")), str(row.get("review_id"))) for row in base_records]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate coder/review key in base labels")
    if len({row.get("coder_id") for row in base_records}) != 1:
        raise ValueError("the frozen pilot requires exactly one stable coder ID")
    for row in base_records:
        if row.get("status") != "submitted":
            raise ValueError(f"non-submitted base record {row.get('review_id')}")
        if row.get("codebook_version") != codebook["codebook_version"]:
            raise ValueError(f"codebook mismatch for {row.get('review_id')}")
        errors = validate_human_label(row, codebook)
        if row.get("primary_class") == "genuine_refusal" and not str(row.get("evidence_span", "")).strip():
            errors.append("genuine_refusal lacks evidence span")
        if row.get("primary_class") == "ambiguous" and not str(row.get("note", "")).strip():
            errors.append("ambiguous lacks explanation")
        if errors:
            raise ValueError(f"invalid base record {row.get('review_id')}: {errors}")

    order = design[["review_id", "review_order", *KEY, "source_hash"]]
    labels = pd.DataFrame(base_records).merge(order, on="review_id", validate="one_to_one")
    labels = labels.sort_values("review_order").reset_index(drop=True)
    canonical_records = labels.drop(columns=["review_order"]).sort_values("review_id").to_dict("records")
    canonical_hash = _canonical_records_hash(canonical_records)

    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested freeze directory: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    frozen_jsonl = output_dir / "base_labels.jsonl"
    frozen_parquet = output_dir / "base_labels.parquet"
    _write_jsonl(frozen_jsonl, canonical_records)
    labels.to_parquet(frozen_parquet, index=False)
    class_counts = labels.primary_class.value_counts().sort_index().astype(int).to_dict()
    manifest = {
        "freeze_version": "human-base-freeze-v1.0",
        "created_at": _utc_now(),
        "status": "complete_nonrepeat_base; repeat reliability pending",
        "repeat_records_read": False,
        "base_membership_rule": "review_id in frozen pilot_design.parquet",
        "n_base_labels": len(labels),
        "n_live_log_records_at_freeze": len(all_records),
        "n_nonbase_live_records_ignored": len(all_records) - len(base_records),
        "coder_id_sha256": sha_text(str(labels.coder_id.iloc[0])),
        "codebook_version": codebook["codebook_version"],
        "codebook_sha256": sha_file(codebook_path),
        "pilot_design_sha256": sha_file(design_path),
        "pilot_manifest_sha256": sha_file(pilot_manifest_path),
        "live_label_log_sha256_at_freeze": sha_file(labels_path),
        "canonical_base_labels_sha256": canonical_hash,
        "first_submission_at": str(labels.submitted_at.min()),
        "last_submission_at": str(labels.submitted_at.max()),
        "primary_class_counts_unweighted": class_counts,
        "artifact_sha256": {
            "base_labels.jsonl": sha_file(frozen_jsonl),
            "base_labels.parquet": sha_file(frozen_parquet),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _component_neither_matrix(
    probabilities: np.ndarray,
    groups: np.ndarray,
    group_sizes: dict[str, int],
    group_draws: dict[str, int],
) -> np.ndarray:
    """Probability that neither of two distinct rows enters one component."""
    q = np.outer(1 - probabilities, 1 - probabilities)
    for group in pd.unique(groups):
        idx = np.flatnonzero(groups == group)
        if len(idx) < 2:
            continue
        N = int(group_sizes[str(group)])
        n = int(group_draws[str(group)])
        if N < 2:
            continue
        neither = ((N - n) * (N - n - 1)) / (N * (N - 1))
        q[np.ix_(idx, idx)] = neither
    return q


def exact_union_pairwise_inclusion(
    design: pd.DataFrame,
    population: pd.DataFrame,
    pilot_manifest: dict,
) -> np.ndarray:
    """Return exact pairwise inclusion probabilities for sampled base rows."""
    n_population = len(population)
    global_n = int(pilot_manifest["components"]["global_srs"])
    n = len(design)
    global_p = np.full(n, global_n / n_population, dtype=float)
    all_group = np.repeat("all", n)
    q_global = _component_neither_matrix(
        global_p, all_group, {"all": n_population}, {"all": global_n}
    )

    cell_key = design.model.astype(str) + "\0" + design.prompt_language.astype(str)
    population_cell = population.model.astype(str) + "\0" + population.prompt_language.astype(str)
    cell_sizes = population_cell.value_counts().astype(int).to_dict()
    cell_draws: dict[str, int] = {}
    for group, rows in design.groupby(cell_key, sort=False):
        p = float(rows.pi_model_language.iloc[0])
        if not np.allclose(rows.pi_model_language, p):
            raise ValueError(f"nonconstant cell probability in {group}")
        draw = int(round(p * cell_sizes[str(group)]))
        if not math.isclose(p, draw / cell_sizes[str(group)], rel_tol=0, abs_tol=1e-12):
            raise ValueError(f"cell probability cannot be reconstructed for {group}")
        cell_draws[str(group)] = draw
    q_cell = _component_neither_matrix(
        design.pi_model_language.to_numpy(float), cell_key.to_numpy(str), cell_sizes, cell_draws
    )

    priority_key = design.pilot_priority_class.astype(str)
    priority_sizes: dict[str, int] = {}
    priority_draws: dict[str, int] = {}
    for group, rows in design.groupby("pilot_priority_class", sort=False):
        draw = int(rows.selected_priority.sum())
        p = float(rows.pi_priority.iloc[0])
        size = int(round(draw / p))
        if draw < 1 or not math.isclose(p, draw / size, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f"priority probability cannot be reconstructed for {group}")
        priority_sizes[str(group)] = size
        priority_draws[str(group)] = draw
    q_priority = _component_neither_matrix(
        design.pi_priority.to_numpy(float), priority_key.to_numpy(str),
        priority_sizes, priority_draws,
    )

    p_components = np.column_stack([
        global_p,
        design.pi_model_language.to_numpy(float),
        design.pi_priority.to_numpy(float),
    ])
    q_single = np.prod(1 - p_components, axis=1)
    pairwise = 1 - q_single[:, None] - q_single[None, :] + q_global * q_cell * q_priority
    pi = design.inclusion_probability.to_numpy(float)
    np.fill_diagonal(pairwise, pi)
    if not np.allclose(pairwise, pairwise.T) or np.any(pairwise <= 0):
        raise ValueError("invalid reconstructed pairwise inclusion matrix")
    if not np.allclose(pi, 1 - q_single, atol=1e-12):
        raise ValueError("stored first-order probabilities do not match component union")
    return pairwise


class DesignEstimator:
    """HT and Hájek binary/continuous means under the frozen union design."""

    def __init__(self, design: pd.DataFrame, population: pd.DataFrame, pairwise: np.ndarray):
        self.design = design.reset_index(drop=True)
        self.population = population
        self.pi = self.design.inclusion_probability.to_numpy(float)
        delta = pairwise - np.outer(self.pi, self.pi)
        self.variance_coefficient = delta / pairwise

    def mean(self, values: np.ndarray, sample_mask: np.ndarray, population_n: int) -> dict:
        values = np.asarray(values, dtype=float)
        mask = np.asarray(sample_mask, dtype=bool)
        if len(values) != len(self.design) or len(mask) != len(self.design):
            raise ValueError("estimator vectors must align to the sampled design")
        if population_n < 1 or not mask.any():
            raise ValueError("empty target population or sample domain")
        weighted_domain_n = float(np.sum(mask / self.pi))
        ht = float(np.sum(mask * values / self.pi) / population_n)
        z_ht = mask * values / self.pi
        var_ht_raw = float(z_ht @ self.variance_coefficient @ z_ht / (population_n**2))
        hajek = float(np.sum(mask * values / self.pi) / weighted_domain_n)
        z_ratio = mask * (values - hajek) / self.pi
        var_hajek_raw = float(z_ratio @ self.variance_coefficient @ z_ratio / (weighted_domain_n**2))
        var_ht = max(0.0, var_ht_raw)
        var_hajek = max(0.0, var_hajek_raw)
        se_ht, se_hajek = math.sqrt(var_ht), math.sqrt(var_hajek)
        weights = mask / self.pi
        effective_n = float(weights.sum() ** 2 / np.square(weights).sum())
        return {
            "population_n": int(population_n),
            "sample_n": int(mask.sum()),
            "sample_events": int(np.sum(mask & (values > 0.5))),
            "effective_sample_n": effective_n,
            "weighted_domain_n_ht": weighted_domain_n,
            "estimate_ht": ht,
            "se_ht": se_ht,
            "ci_low_ht_unbounded": ht - 1.96 * se_ht,
            "ci_high_ht_unbounded": ht + 1.96 * se_ht,
            "ci_low_ht": max(0.0, ht - 1.96 * se_ht),
            "ci_high_ht": min(1.0, ht + 1.96 * se_ht),
            "estimate_hajek": hajek,
            "se_hajek_linearized": se_hajek,
            "ci_low_hajek": max(0.0, hajek - 1.96 * se_hajek),
            "ci_high_hajek": min(1.0, hajek + 1.96 * se_hajek),
            "negative_raw_variance_ht": var_ht_raw < -1e-12,
            "negative_raw_variance_hajek": var_hajek_raw < -1e-12,
        }


def _add_human_outcomes(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if not set(out.primary_class).issubset(PRIMARY_CLASSES):
        raise ValueError("unknown human primary class")
    for name, classes in DERIVED_OUTCOMES.items():
        out[f"human_{name}"] = out.primary_class.isin(classes).astype(int)
    out["original_nonengagement"] = out.engagement_code.ge(4).astype(int)
    return out


def _population_mask(frame: pd.DataFrame, dimension: str, level: str) -> np.ndarray:
    if dimension == "overall":
        return np.ones(len(frame), dtype=bool)
    if dimension == "original_nonengagement":
        desired = level == "yes"
        return frame.engagement_code.ge(4).to_numpy() == desired
    return frame[dimension].astype(str).fillna("<missing>").to_numpy() == level


def _levels(frame: pd.DataFrame, dimension: str) -> list[str]:
    if dimension == "overall":
        return ["all"]
    if dimension == "original_nonengagement":
        return ["yes", "no"]
    return sorted(frame[dimension].astype(str).fillna("<missing>").unique())


def _pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def _write_preliminary_report(
    path: Path,
    freeze_manifest: dict,
    prevalence: pd.DataFrame,
    original_audit: pd.DataFrame,
    qa: dict,
    readiness: pd.DataFrame,
    readiness_gate: dict,
) -> None:
    """Render a compact paper-development report directly from audit tables."""
    overall = prevalence.loc[prevalence.dimension.eq("overall")].set_index("outcome")
    original_positive = original_audit.loc[
        original_audit.domain.eq("original_nonengagement")
    ].set_index("human_outcome")
    original_negative = original_audit.loc[
        original_audit.domain.eq("original_engaged_control")
    ].set_index("human_outcome")
    language = prevalence.loc[
        prevalence.dimension.eq("prompt_language")
        & prevalence.outcome.isin(["genuine_refusal", "capability_failure"])
    ]
    home = prevalence.loc[
        prevalence.dimension.eq("home_status")
        & prevalence.outcome.isin(["genuine_refusal", "capability_failure"])
    ]

    def interval(row: pd.Series) -> str:
        return f"{_pct(row.estimate_ht)} [{_pct(row.ci_low_ht)}, {_pct(row.ci_high_ht)}]"

    language_corrected = "language-corrected" in freeze_manifest.get("freeze_version", "")
    freeze_path = (
        "annotations/response_validity_human_v2/base_freeze_v2_language_corrected/"
        if language_corrected else
        "annotations/response_validity_human_v2/base_freeze_v1/"
    )
    audit_path = (
        "annotations/response_validity_human_v2/preliminary_audit_v2_language_corrected/"
        if language_corrected else
        "annotations/response_validity_human_v2/preliminary_audit_v1/"
    )
    reproduce = (
        "python scripts/response_validity.py apply-human-language-review"
        if language_corrected else
        "python scripts/response_validity.py freeze-human-base followed by "
        "python scripts/response_validity.py audit-human-base"
    )

    lines = [
        "# Preliminary human response-validity pilot results",
        "",
        "> **Status: provisional.** These estimates use one coder's 300 unique judgments. "
        "The 36 blinded repeats remain locked and were not read or analyzed. This is not yet "
        "a human gold standard, an accepted canonical analysis, or a substitute for the planned "
        "human-referenced DSL stage.",
        "",
        "## Frozen inputs and estimator",
        "",
        f"The immutable base freeze contains {freeze_manifest['n_base_labels']} submitted judgments "
        f"under codebook `{freeze_manifest['codebook_version']}`. Its canonical base-label hash is "
        f"`{freeze_manifest['canonical_base_labels_sha256']}`. The audit targets the frozen 137,186-response "
        "population and uses the exact first- and pairwise inclusion probabilities implied by the union "
        "of the global, model × language, and priority-stratified SRSWOR components.",
        "",
        "The primary column is the Horvitz–Thompson (HT) domain mean with an exact union-design variance "
        "estimator and a normal 95% interval. The Hájek ratio estimate is retained as a calibrated "
        "sensitivity. Intervals do not yet incorporate repeat-coding reliability or model-training uncertainty.",
        "",
        "## Headline prevalence",
        "",
        "| Human outcome | HT estimate [95% CI] | Hájek sensitivity | Sample events |",
        "|---|---:|---:|---:|",
    ]
    for outcome in [
        "genuine_refusal", "capability_failure", "coherent_pivot",
        "coherent_noncompliance", "coherent_answer", "ambiguous",
    ]:
        row = overall.loc[outcome]
        lines.append(
            f"| {outcome.replace('_', ' ').title()} | {interval(row)} | "
            f"{_pct(row.estimate_hajek)} | {int(row.sample_events)} |"
        )
    wrong_row = readiness.loc[readiness.primary_class.eq("wrong_language")].iloc[0]
    deficient = readiness.loc[readiness.additional_rows_required.gt(0), "primary_class"].tolist()
    deficiency_text = ", ".join(name.replace("_", " ") for name in deficient)
    lines.extend([
        "",
        "## What the original judge-coded non-engagement label captured",
        "",
        "The original outcome is called **judge-coded non-engagement**, not refusal. Among the population "
        "domain carrying that original code:",
        "",
        "| Human outcome within original non-engagement | HT estimate [95% CI] | Hájek sensitivity | Sample events / rows |",
        "|---|---:|---:|---:|",
    ])
    for outcome in [
        "genuine_refusal", "capability_failure", "coherent_pivot",
        "coherent_answer", "ambiguous",
        "not_genuine_refusal_false_positive_for_refusal",
    ]:
        row = original_positive.loc[outcome]
        label = (
            "Not genuine refusal (measurement false positive)"
            if outcome.startswith("not_genuine") else outcome.replace("_", " ").title()
        )
        lines.append(
            f"| {label} | {interval(row)} | {_pct(row.estimate_hajek)} | "
            f"{int(row.sample_events)} / {int(row.sample_n)} |"
        )
    control_refusal = original_negative.loc["genuine_refusal"]
    control_capability = original_negative.loc["capability_failure"]
    lines.extend([
        "",
        f"Among original engaged controls, the estimated genuine-refusal rate is {interval(control_refusal)} "
        f"and the capability-failure rate is {interval(control_capability)}. Thus the original instrument "
        "has both a severe construct-validity problem among its positives and a smaller but nonzero missed-refusal problem.",
        "",
        "## Language diagnostics",
        "",
        "| Language | Genuine refusal HT [95% CI] | Capability failure HT [95% CI] | Human rows |",
        "|---|---:|---:|---:|",
    ])
    for level in ["en", "zh", "ar", "ru", "hi"]:
        refusal = language.loc[(language.level == level) & (language.outcome == "genuine_refusal")].iloc[0]
        capability = language.loc[(language.level == level) & (language.outcome == "capability_failure")].iloc[0]
        lines.append(
            f"| {level} | {interval(refusal)} | {interval(capability)} | {int(refusal.sample_n)} |"
        )
    lines.extend([
        "",
        "These are marginal design-weighted diagnostics, not prompt-paired language effects. Hindi's large "
        "capability-failure estimate is the clearest provisional measurement warning; formal language contrasts "
        "must use the planned prompt-paired human-reference DSL estimator.",
        "",
        "## Home-topic diagnostic",
        "",
        "| Home status | Genuine refusal HT [95% CI] | Capability failure HT [95% CI] | Human rows |",
        "|---|---:|---:|---:|",
    ])
    for level in ["home", "away", "general"]:
        refusal = home.loc[(home.level == level) & (home.outcome == "genuine_refusal")].iloc[0]
        capability = home.loc[(home.level == level) & (home.outcome == "capability_failure")].iloc[0]
        lines.append(
            f"| {level.title()} | {interval(refusal)} | {interval(capability)} | {int(refusal.sample_n)} |"
        )
    lines.extend([
        "",
        "These are unstandardized domain descriptions. They do **not** estimate the canonical home-minus-away "
        "contrast and cannot resolve the home finding with only 45 sampled home rows and two observed home refusals. "
        "The eventual analysis must apply a human-referenced cross-fitted DSL outcome inside the declared nested "
        "standardization used for the home estimand.",
        "",
        "## System comparison boundary",
        "",
        f"Only {qa['n_sol_exact_overlap']} of the 300 human rows overlap exact GPT-5.6 Sol reference judgments. "
        "Those confusion counts are reported as unweighted overlap descriptions only. Wall-to-wall Sol-derived "
        "prediction comparisons are surrogate diagnostics, not independent frontier-model judgments and not human truth.",
        "",
        "Overall accuracy is misleading for rare refusal: a system can appear accurate by predicting almost every "
        "response as non-refusal. Precision, recall, refusal–pivot confusion, capability-failure performance, calibration, "
        "and model/language heterogeneity must govern the surrogate bake-off.",
        "",
        "## Surrogate readiness gate",
        "",
        f"The frozen bake-off readiness gate is **{'PASS' if readiness_gate['pass'] else 'FAIL'}**. "
        "It requires at least four high-confidence exemplar candidates and ten independent held-out judgments "
        "per primary class; a row cannot serve both roles.",
        "",
        "| Primary class | Total human rows | High confidence | Languages represented | Required additional rows |",
        "|---|---:|---:|---:|---:|",
    ])
    for row in readiness.itertuples(index=False):
        lines.append(
            f"| {row.primary_class.replace('_', ' ').title()} | {int(row.n_total)} | "
            f"{int(row.n_high_confidence)} | {int(row.n_languages)} | {int(row.additional_rows_required)} |"
        )
    lines.extend([
        "",
        f"The pilot contains {int(wrong_row.n_total)} coder-confirmed wrong-language cases. "
        f"The classes still below the frozen readiness requirements are: {deficiency_text}. "
        "`exemplar_candidates.csv` is therefore "
        "a deterministic candidate inventory only—not a frozen few-shot prompt, training set, or test set. "
        "No model bake-off or population annotation should begin until a label-blind enrichment sample repairs "
        "these deficits and the development/evaluation split is frozen by `prompt_id`.",
        "",
        "## Files and reproducibility",
        "",
        f"- Immutable base: `{freeze_path}`.",
        f"- Preliminary estimates: `{audit_path}`.",
        "- `measurement_error_by_cell.csv` reports provisional original-label error composition by "
        "language, model, jurisdiction, and response-length band; zero-sample domains are explicit rather than imputed.",
        "- Deterministically selected disagreement rows remain local in `deterministic_disagreement_examples.csv`; "
        "they were selected by category and source hash, not rhetorical convenience.",
        "- `exemplar_candidates.csv` and `surrogate_readiness.json` enforce the pre-bake-off gate and must not "
        "be treated as an authorized model payload.",
        f"- Reproduce locally with `{reproduce}`.",
        "- No network or paid model call is made by either command.",
        "",
        "## Decision gate",
        "",
        "Use these results to design the exemplar bank, surrogate bake-off, and final human-reference precision simulation. "
        "Do not promote them to the paper's main results until repeat reliability is available and the final human-reference "
        "DSL stage passes its predeclared acceptance gates.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def run_preliminary_human_audit(
    root: Path,
    pilot_dir: Path,
    output_dir: Path | None = None,
    freeze_dir: Path | None = None,
    report_path: Path | None = None,
    audit_version: str = "human-pilot-preliminary-audit-v1.0",
) -> dict:
    """Produce provisional one-coder, design-weighted audit outputs."""
    freeze_dir = freeze_dir or pilot_dir / "base_freeze_v1"
    if freeze_dir.name == "base_freeze_v1":
        freeze_manifest = freeze_completed_base_labels(root, pilot_dir, freeze_dir)
    else:
        freeze_manifest_path = freeze_dir / "freeze_manifest.json"
        if not freeze_manifest_path.exists():
            raise FileNotFoundError(freeze_manifest_path)
        freeze_manifest = json.loads(freeze_manifest_path.read_text(encoding="utf-8"))
    output_dir = output_dir or pilot_dir / "preliminary_audit_v1"
    manifest_path = output_dir / "audit_manifest.json"
    labels_path = freeze_dir / "base_labels.parquet"
    design_path = pilot_dir / "pilot_design.parquet"
    pilot_manifest_path = pilot_dir / "pilot_manifest.json"
    pilot_manifest = json.loads(pilot_manifest_path.read_text(encoding="utf-8"))
    population_path = root / pilot_manifest["population_path"]
    if sha_file(population_path) != pilot_manifest["population_sha256"]:
        raise ValueError("population hash differs from frozen pilot manifest")

    labels = pd.read_parquet(labels_path)
    design = pd.read_parquet(design_path).sort_values("review_order").reset_index(drop=True)
    population = pd.read_parquet(population_path)
    if len(population) != 137_186 or population.duplicated(KEY).any():
        raise ValueError("canonical audit population is not 137,186 unique response keys")
    label_fields = [c for c in labels.columns if c not in {*KEY, "source_hash", "review_order"}]
    sample = design.merge(labels[label_fields], on="review_id", validate="one_to_one")
    sample = _add_human_outcomes(sample)
    pairwise = exact_union_pairwise_inclusion(sample, population, pilot_manifest)
    estimator = DesignEstimator(sample, population, pairwise)

    current_inputs = {
        "base_freeze_manifest_sha256": sha_file(freeze_dir / "freeze_manifest.json"),
        "base_labels_sha256": sha_file(labels_path),
        "pilot_design_sha256": sha_file(design_path),
        "population_sha256": sha_file(population_path),
    }
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("input_sha256") == current_inputs:
            for name, expected in existing.get("artifact_sha256", {}).items():
                path = output_dir / name
                if not path.exists() or sha_file(path) != expected:
                    raise RuntimeError(f"preliminary audit artifact missing or changed: {path}")
            documentation = existing.get("documentation", {})
            if documentation:
                documentation_path = root / documentation["path"]
                if not documentation_path.exists() or sha_file(documentation_path) != documentation["sha256"]:
                    raise RuntimeError("preliminary audit documentation is missing or changed")
            return existing
        raise RuntimeError("existing preliminary audit was built from different frozen inputs")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested audit directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    outcomes = list(DERIVED_OUTCOMES)
    dimensions = [
        "overall", "original_nonengagement", "prompt_language", "model",
        "jurisdiction", "home_status", "topic_domain", "region_focus",
        "controversy_tier",
    ]
    prevalence_rows: list[dict] = []
    for dimension in dimensions:
        for level in _levels(population, dimension):
            pop_mask = _population_mask(population, dimension, level)
            sample_mask = _population_mask(sample, dimension, level)
            for outcome in outcomes:
                result = estimator.mean(
                    sample[f"human_{outcome}"].to_numpy(float), sample_mask, int(pop_mask.sum())
                )
                prevalence_rows.append({
                    "dimension": dimension, "level": level, "outcome": outcome,
                    "status": "provisional_one_coder_repeat_reliability_pending", **result,
                })
    prevalence = pd.DataFrame(prevalence_rows)
    prevalence_path = output_dir / "design_weighted_prevalence.csv"
    prevalence.to_csv(prevalence_path, index=False)

    original_rows: list[dict] = []
    original_domains = {
        "all_responses": np.ones(len(sample), dtype=bool),
        "original_nonengagement": sample.original_nonengagement.eq(1).to_numpy(),
        "original_engaged_control": sample.original_nonengagement.eq(0).to_numpy(),
    }
    population_domain_n = {
        "all_responses": len(population),
        "original_nonengagement": int(population.engagement_code.ge(4).sum()),
        "original_engaged_control": int(population.engagement_code.lt(4).sum()),
    }
    for domain, sample_mask in original_domains.items():
        for outcome in outcomes:
            result = estimator.mean(
                sample[f"human_{outcome}"].to_numpy(float), sample_mask,
                population_domain_n[domain],
            )
            original_rows.append({"domain": domain, "human_outcome": outcome, **result})
    # A false positive is defined relative to the human genuine-refusal target,
    # not as evidence that the original judge made a logically invalid call.
    pos_refusal = next(
        row for row in original_rows
        if row["domain"] == "original_nonengagement" and row["human_outcome"] == "genuine_refusal"
    )
    false_positive = dict(pos_refusal)
    false_positive.update({
        "domain": "original_nonengagement",
        "human_outcome": "not_genuine_refusal_false_positive_for_refusal",
        "sample_events": int(pos_refusal["sample_n"] - pos_refusal["sample_events"]),
        # The original-positive population size is known exactly.  Using the
        # calibrated complement 1-HT(Y) is both design-unbiased and enforces
        # the logical partition, unlike separately estimating HT(1-Y).
        "estimate_ht": 1 - pos_refusal["estimate_ht"],
        "ci_low_ht_unbounded": 1 - pos_refusal["ci_high_ht_unbounded"],
        "ci_high_ht_unbounded": 1 - pos_refusal["ci_low_ht_unbounded"],
        "ci_low_ht": max(0.0, 1 - pos_refusal["ci_high_ht_unbounded"]),
        "ci_high_ht": min(1.0, 1 - pos_refusal["ci_low_ht_unbounded"]),
        "estimate_hajek": 1 - pos_refusal["estimate_hajek"],
        "ci_low_hajek": max(0.0, 1 - pos_refusal["ci_high_hajek"]),
        "ci_high_hajek": min(1.0, 1 - pos_refusal["ci_low_hajek"]),
    })
    original_rows.append(false_positive)
    original_audit = pd.DataFrame(original_rows)
    original_path = output_dir / "original_label_audit.csv"
    original_audit.to_csv(original_path, index=False)

    error_cell_rows: list[dict] = []
    for dimension in ["prompt_language", "model", "jurisdiction", "control_length_band"]:
        for level in _levels(population, dimension):
            base_population_mask = _population_mask(population, dimension, level)
            base_sample_mask = _population_mask(sample, dimension, level)
            for original_value, original_label in [(1, "nonengagement"), (0, "engaged_control")]:
                population_mask = base_population_mask & (
                    population.engagement_code.ge(4).to_numpy() == bool(original_value)
                )
                sample_mask = base_sample_mask & sample.original_nonengagement.eq(original_value).to_numpy()
                for outcome in [
                    "genuine_refusal", "capability_failure", "coherent_pivot", "coherent_answer",
                ]:
                    base = {
                        "dimension": dimension,
                        "level": level,
                        "original_label_domain": original_label,
                        "human_outcome": outcome,
                        "population_n": int(population_mask.sum()),
                        "sample_n": int(sample_mask.sum()),
                    }
                    if not sample_mask.any():
                        error_cell_rows.append({
                            **base,
                            "status": "no_human_sample_in_domain",
                            "estimate_ht": np.nan,
                            "se_ht": np.nan,
                            "ci_low_ht": np.nan,
                            "ci_high_ht": np.nan,
                            "estimate_hajek": np.nan,
                            "se_hajek_linearized": np.nan,
                        })
                    else:
                        error_cell_rows.append({
                            **base,
                            "status": "provisional_sparse_cell_repeat_reliability_pending",
                            **estimator.mean(
                                sample[f"human_{outcome}"].to_numpy(float),
                                sample_mask,
                                int(population_mask.sum()),
                            ),
                        })
    error_cells = pd.DataFrame(error_cell_rows)
    error_cells_path = output_dir / "measurement_error_by_cell.csv"
    error_cells.to_csv(error_cells_path, index=False)

    pseudo_path = root / pilot_manifest["pseudo_path"]
    if sha_file(pseudo_path) != pilot_manifest["pseudo_sha256"]:
        raise ValueError("Sol pseudo-outcome hash differs from frozen pilot manifest")
    prediction_columns = [
        "dsl_prediction_clean_genuine_refusal",
        "dsl_prediction_capability_failure",
        "dsl_prediction_coherent_pivot",
    ]
    pseudo = pd.read_parquet(pseudo_path)[KEY + prediction_columns]
    if set(prediction_columns).issubset(sample.columns):
        prediction_check = sample[KEY + prediction_columns].merge(
            pseudo, on=KEY, validate="one_to_one", suffixes=("_design", "_pseudo")
        )
        for column in prediction_columns:
            if not np.allclose(
                prediction_check[f"{column}_design"],
                prediction_check[f"{column}_pseudo"],
                equal_nan=True,
            ):
                raise ValueError(f"stored pilot prediction differs from frozen pseudo-outcome: {column}")
        compared = sample.copy()
    else:
        compared = sample.merge(pseudo, on=KEY, validate="one_to_one")
    sol_exact_path = root / "annotations" / "response_validity_dsl_v1_1" / "assembled_reference_labels.parquet"
    sol_exact = pd.read_parquet(sol_exact_path)[KEY + [
        "clean_genuine_refusal", "capability_failure", "coherent_pivot",
    ]]
    compared = compared.merge(sol_exact, on=KEY, how="left", validate="one_to_one", indicator="sol_exact_merge")
    if compared.review_id.tolist() != sample.review_id.tolist():
        raise ValueError("comparison joins changed the frozen sample order")

    metrics: list[dict] = []
    predictor_specs = [
        ("original_judge_nonengagement", compared.original_nonengagement.to_numpy(float), "genuine_refusal"),
        ("sol_surrogate_genuine_refusal_p50", compared.dsl_prediction_clean_genuine_refusal.ge(.5).to_numpy(float), "genuine_refusal"),
        ("sol_surrogate_capability_failure_p50", compared.dsl_prediction_capability_failure.ge(.5).to_numpy(float), "capability_failure"),
        ("sol_surrogate_coherent_pivot_p50", compared.dsl_prediction_coherent_pivot.ge(.5).to_numpy(float), "coherent_pivot"),
    ]
    all_mask = np.ones(len(compared), dtype=bool)
    for system, prediction, human_outcome in predictor_specs:
        truth = compared[f"human_{human_outcome}"].to_numpy(float)
        for metric, values in {
            "accuracy": (prediction == truth).astype(float),
            "error_rate": (prediction != truth).astype(float),
        }.items():
            metrics.append({
                "system": system, "human_outcome": human_outcome, "metric": metric,
                **estimator.mean(values, all_mask, len(population)),
            })
        predicted_positive = prediction > .5
        truth_positive = truth > .5
        if predicted_positive.any():
            positive_result = estimator.mean(
                truth, predicted_positive,
                int(np.sum(population.engagement_code.ge(4)))
                if system == "original_judge_nonengagement" else len(population),
            )
            if system != "original_judge_nonengagement":
                for column in [
                    "population_n", "estimate_ht", "se_ht", "ci_low_ht_unbounded",
                    "ci_high_ht_unbounded", "ci_low_ht", "ci_high_ht",
                ]:
                    positive_result[column] = np.nan
            metrics.append({
                "system": system, "human_outcome": human_outcome, "metric": "positive_predictive_value",
                **positive_result,
                "domain_denominator_note": (
                    "exact known original-positive domain; HT primary and Hajek sensitivity"
                    if system == "original_judge_nonengagement"
                    else "surrogate-positive population size unknown; Hajek domain estimate only"
                ),
            })
        if truth_positive.any():
            # The human-positive population size is unknown, so this is a
            # Hájek-domain sensitivity estimate; the HT column is not used.
            sensitivity_result = estimator.mean(prediction, truth_positive, len(population))
            for column in [
                "population_n", "estimate_ht", "se_ht", "ci_low_ht_unbounded",
                "ci_high_ht_unbounded", "ci_low_ht", "ci_high_ht",
            ]:
                sensitivity_result[column] = np.nan
            metrics.append({
                "system": system, "human_outcome": human_outcome, "metric": "sensitivity_hajek_domain",
                **sensitivity_result,
                "domain_denominator_note": "human-positive domain size unknown; report estimate_hajek only",
            })
    metric_frame = pd.DataFrame(metrics)
    metrics_path = output_dir / "system_metrics.csv"
    metric_frame.to_csv(metrics_path, index=False)

    confusion_rows: list[dict] = []
    for original_value in [0, 1]:
        domain_mask = compared.original_nonengagement.eq(original_value).to_numpy()
        domain_n = int((population.engagement_code.ge(4) == bool(original_value)).sum())
        for human_class in sorted(PRIMARY_CLASSES):
            result = estimator.mean(
                compared.primary_class.eq(human_class).to_numpy(float), domain_mask, domain_n
            )
            confusion_rows.append({
                "comparison": "original_nonengagement_vs_human_primary",
                "system_value": original_value,
                "human_value": human_class,
                "coverage_note": "known-probability human pilot; design-weighted",
                **result,
            })
    exact = compared.loc[compared.sol_exact_merge.eq("both")].copy()
    exact_specs = {
        "genuine_refusal": "clean_genuine_refusal",
        "capability_failure": "capability_failure",
        "coherent_pivot": "coherent_pivot",
    }
    for outcome, sol_col in exact_specs.items():
        for sol_value in [0, 1]:
            for human_value in [0, 1]:
                count = int(((exact[sol_col].astype(int) == sol_value) & (exact[f"human_{outcome}"] == human_value)).sum())
                confusion_rows.append({
                    "comparison": f"sol_exact_vs_human_{outcome}",
                    "system_value": sol_value,
                    "human_value": human_value,
                    "sample_n": len(exact),
                    "cell_n": count,
                    "coverage_note": "overlap only; unweighted descriptive; not population representative",
                })
    confusion = pd.DataFrame(confusion_rows)
    confusion_path = output_dir / "system_confusion.csv"
    confusion.to_csv(confusion_path, index=False)

    compared["comparison_category"] = np.select(
        [
            compared.original_nonengagement.eq(1) & compared.primary_class.eq("coherent_answer"),
            compared.original_nonengagement.eq(1) & compared.human_capability_failure.eq(1),
            compared.original_nonengagement.eq(0) & compared.human_genuine_refusal.eq(1),
            compared.sol_exact_merge.eq("both")
            & compared.clean_genuine_refusal.astype("boolean").fillna(False).astype(bool).ne(
                compared.human_genuine_refusal.astype(bool)
            ),
        ],
        [
            "original_nonengagement_human_answer",
            "original_nonengagement_human_capability_failure",
            "original_engaged_human_genuine_refusal",
            "sol_exact_human_refusal_disagreement",
        ],
        default="",
    )
    examples = (
        compared.loc[compared.comparison_category.ne("")]
        .sort_values(["comparison_category", "source_hash"])
        .groupby("comparison_category", as_index=False, group_keys=False)
        .head(3)
    )
    example_cols = [
        "comparison_category", "review_id", *KEY, "issue_id", "prompt_language",
        "engagement_code", "primary_class", "confidence", "prompt_text_en",
        "prompt_text", "response_text", "evidence_span", "source_hash",
    ]
    examples_path = output_dir / "deterministic_disagreement_examples.csv"
    examples[[c for c in example_cols if c in examples]].to_csv(examples_path, index=False)

    readiness_rows: list[dict] = []
    candidate_parts: list[pd.DataFrame] = []
    translation_path = pilot_dir / "translations_assembled.jsonl"
    translations = pd.DataFrame(_read_jsonl(translation_path))
    translation_columns = [
        "review_id", "response_translation_en", "translation_status", "uncertain_spans",
    ]
    candidate_source = sample.merge(
        translations[translation_columns], on="review_id", validate="one_to_one"
    )
    for primary_class in sorted(PRIMARY_CLASSES):
        class_rows = candidate_source.loc[candidate_source.primary_class.eq(primary_class)].copy()
        high = class_rows.loc[class_rows.confidence.eq("high")].copy()
        n_total = len(class_rows)
        n_high = len(high)
        n_languages = int(class_rows.prompt_language.nunique())
        required_total = 14  # four development exemplars plus ten held-out cases
        additional = max(0, required_total - n_total, 4 - n_high)
        readiness_rows.append({
            "primary_class": primary_class,
            "n_total": n_total,
            "n_high_confidence": n_high,
            "n_languages": n_languages,
            "n_models": int(class_rows.model.nunique()),
            "minimum_exemplar_candidates": 4,
            "minimum_independent_evaluation": 10,
            "minimum_languages": 3,
            "count_gate_pass": n_total >= required_total and n_high >= 4,
            "language_gate_pass": n_languages >= 3,
            "additional_rows_required": additional,
        })
        # Candidate inventory only: take one deterministic high-confidence row
        # per represented language, then fill to 12 by source hash.  No row is
        # assigned to a prompt or held-out split at this stage.
        high = high.sort_values(["prompt_language", "source_hash"])
        diverse = high.groupby("prompt_language", sort=True, as_index=False, group_keys=False).head(1)
        remaining_high = high.loc[~high.review_id.isin(diverse.review_id)].sort_values("source_hash")
        chosen = pd.concat([diverse, remaining_high], ignore_index=True).head(12)
        candidate_parts.append(chosen)
    readiness = pd.DataFrame(readiness_rows)
    readiness_path = output_dir / "surrogate_readiness.csv"
    readiness.to_csv(readiness_path, index=False)
    readiness_gate = {
        "gate_version": "human-surrogate-readiness-v1.0",
        "created_at": _utc_now(),
        "pass": bool((readiness.count_gate_pass & readiness.language_gate_pass).all()),
        "development_exemplar_minimum_per_class": 4,
        "independent_evaluation_minimum_per_class": 10,
        "language_minimum_per_class": 3,
        "split_rule_when_ready": "grouped by prompt_id; no prompt_id may cross development and evaluation",
        "candidate_inventory_is_authorized_payload": False,
        "paid_or_network_call_authorized": False,
        "failed_classes": readiness.loc[
            ~(readiness.count_gate_pass & readiness.language_gate_pass), "primary_class"
        ].tolist(),
    }
    readiness_json_path = output_dir / "surrogate_readiness.json"
    readiness_json_path.write_text(json.dumps(readiness_gate, indent=2), encoding="utf-8")
    candidates = pd.concat(candidate_parts, ignore_index=True)
    candidate_columns = [
        "review_id", *KEY, "issue_id", "primary_class", "confidence",
        "noncompliance_signal", "technical_failure", "evidence_span", "note",
        "prompt_text_en", "prompt_text", "response_text", "response_translation_en",
        "translation_status", "source_hash",
    ]
    candidates_path = output_dir / "exemplar_candidates.csv"
    candidates[[c for c in candidate_columns if c in candidates]].to_csv(candidates_path, index=False)

    qa = {
        "status": "PASS",
        "interpretation_status": "provisional; one coder; repeat reliability pending",
        "n_population": len(population),
        "n_base_labels": len(sample),
        "n_repeat_labels_analyzed": 0,
        "n_unique_review_ids": int(sample.review_id.nunique()),
        "n_unique_response_keys": int(sample[KEY].drop_duplicates().shape[0]),
        "n_coders": int(sample.coder_id.nunique()),
        "n_sol_exact_overlap": int(compared.sol_exact_merge.eq("both").sum()),
        "primary_class_counts_unweighted": sample.primary_class.value_counts().sort_index().astype(int).to_dict(),
        "confidence_counts_unweighted": sample.confidence.value_counts().sort_index().astype(int).to_dict(),
        "pairwise_min": float(pairwise.min()),
        "pairwise_max": float(pairwise.max()),
        "negative_variance_rows": int(
            prevalence.negative_raw_variance_ht.sum() + prevalence.negative_raw_variance_hajek.sum()
        ),
    }
    qa_path = output_dir / "qa_summary.json"
    qa_path.write_text(json.dumps(qa, indent=2), encoding="utf-8")

    report_path = report_path or root / "docs" / "HUMAN_PILOT_PRELIMINARY_RESULTS.md"
    _write_preliminary_report(
        report_path, freeze_manifest, prevalence, original_audit, qa, readiness, readiness_gate
    )

    artifact_paths = [
        prevalence_path, original_path, error_cells_path, metrics_path, confusion_path,
        examples_path, readiness_path, readiness_json_path, candidates_path, qa_path,
    ]
    manifest = {
        "audit_version": audit_version,
        "created_at": _utc_now(),
        "status": "provisional_one_coder_repeat_reliability_pending",
        "repeat_records_read_or_analyzed": False,
        "network_call_made": False,
        "input_sha256": current_inputs,
        "estimators": {
            "primary": "Horvitz-Thompson domain mean with exact first- and pairwise union-design inclusion probabilities",
            "sensitivity": "Hajek ratio mean with pairwise linearized variance",
            "interval": "normal 95%; bounded display and unbounded HT endpoints both retained",
        },
        "n_sol_exact_overlap": int(compared.sol_exact_merge.eq("both").sum()),
        "artifact_sha256": {path.name: sha_file(path) for path in artifact_paths},
        "documentation": {
            "path": report_path.relative_to(root).as_posix(),
            "sha256": sha_file(report_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
