#!/usr/bin/env python3
"""Plan and apply the 2026-09-01 provenance-preserving repository cleanup.

``plan`` writes an exact hash-bound ``docs/ARCHIVE_MANIFEST.csv``. ``apply``
refuses changed sources, uses ``git mv`` for tracked paths, moves untracked
historical files into the dated root archive, and sends disposable artifacts
to a recoverable temporary holding tree. It never touches raw responses,
annotation ledgers, human reviews, accepted releases, or the final v2.4 table.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path("archive/2026-09-01_pre_rationalization")
RECOVERY = Path("/tmp/refusal_audit_v2_cleanup_2026-09-01")
MANIFEST = ROOT / "docs/ARCHIVE_MANIFEST.csv"
FIELDS = [
    "original_path", "new_path", "action", "classification", "reason",
    "evidence", "upstream_creator", "downstream_references", "sha256_before",
    "sha256_after", "size_bytes", "reproducible", "contains_unique_evidence",
    "tracked_status", "applied",
]

LIVE_AUDIT_OUTPUTS = {
    "docs/ARCHIVE_MANIFEST.csv",
    "docs/ARTIFACT_REGISTRY.csv",
}

DOCS_TO_ARCHIVE = {
    "docs/ANALYTICAL_AUDIT.md", "docs/CODEBASE_RATIONALIZATION.md",
    "docs/EXPANSION_RU_MENA.md", "docs/EXTERNAL_REFUSAL_DISAGREEMENT_REVIEW.md",
    "docs/EXTERNAL_VALIDATION_DESIGN.md", "docs/FIGURE_ESTIMAND_AUDIT.md",
    "docs/FIGURE_REDESIGN_MEMO.md", "docs/FIGURE_SYSTEM_FINAL_AUDIT.md",
    "docs/FIGURE_SYSTEM_MEMO.md", "docs/FOLD_NESTED_REFUSAL_REFINEMENT.md",
    "docs/GO.md", "docs/HOME_HUMAN_AUGMENTATION_DESIGN.md",
    "docs/HUMAN_DSL_PRECISION_AUDIT.md", "docs/HUMAN_ENRICHMENT_DESIGN.md",
    "docs/HUMAN_ENRICHMENT_DESIGN_V2.md",
    "docs/HUMAN_PILOT_LANGUAGE_CORRECTED_RESULTS.md",
    "docs/HUMAN_PILOT_PRELIMINARY_RESULTS.md", "docs/HUMAN_REFERENCED_DSL.md",
    "docs/HUMAN_TRANSLATION_APPROVAL.md", "docs/INDIA_SARVAM_HINDI_INTEGRATION.md",
    "docs/LUNA_V22_INTERNAL_READINESS_RESULTS.md",
    "docs/LUNA_V22_INTERNAL_READINESS_TEST.md", "docs/MENA_HF_ENDPOINT_INTEGRATION.md",
    "docs/MENA_LOCAL_INTEGRATION.md", "docs/MIGRATION_MAP.md",
    "docs/MULTI_JUDGE_PLAN.md", "docs/NEXT_STEPS.md", "docs/PILOT_V1_REPORT.md",
    "docs/PIPELINE_SCALABILITY_REVIEW.md",
    "docs/PROTECTED_SURROGATE_EVALUATION_RESULTS.md",
    "docs/REPORT_REVISION_PLAN.md", "docs/RESPONSE_VALIDITY_DSL.md",
    "docs/RESPONSE_VALIDITY_DSL_AUGMENTATION.md",
    "docs/RESPONSE_VALIDITY_DSL_DESIGN.md", "docs/RESPONSE_VALIDITY_DSL_RUN.md",
    "docs/RESPONSE_VALIDITY_MODEL_BAKEOFF_V2.md",
    "docs/RESPONSE_VALIDITY_MODEL_BAKEOFF_V2_RESULTS.md",
    "docs/RESPONSE_VALIDITY_RESULTS.md", "docs/RESPONSE_VALIDITY_V11_PILOT.md",
    "docs/RESPONSE_VALIDITY_V11_RESULTS.md", "docs/SCALABLE_ANNOTATION_BAKEOFF.md",
    "docs/SCALABLE_ANNOTATION_BAKEOFF_RESULTS.md",
    "docs/STAGE18_PRELIMINARY_V2_2.md", "docs/STAGE_A_18_DISAGREEMENT_CASES.md",
    "docs/STAGE_A_ADJUDICATION_RESULTS.md",
    "docs/SURROGATE_BAKEOFF_STAGE_A_RESULTS.md", "docs/SURROGATE_BAKEOFF_STAGE_B.md",
    "docs/SURROGATE_BAKEOFF_V1.md", "docs/probe_findings.md",
}

CODE_TO_ARCHIVE = {
    "push_to_github.sh", "scripts/make_sample_review.py",
    "scripts/study_a_jurisdiction_panel.py", "scripts/study_b_runner.py",
    "scripts/translate_prompts.py", "scripts/validate_data.py",
    "sourcing/05b_topup_translations.py", "sourcing/09_migrate_issue_ids.py",
    "sourcing/10_backtranslate_native.py", "sourcing/11_retranslate_affected.py",
    "sourcing/12_normalize_boundary_templates.py", "sourcing/13_recover_qids.py",
    "sourcing/14_recover_provenance.py",
}

INTERACTIVE_TO_ARCHIVE = {
    "interactive/pages/2_Human_validity_review.py",
    "interactive/pages/3_Stage_A_disagreement_adjudication.py",
    "interactive/pages/4_Decomposed_response_review.py",
    "interactive/pages/5_Review_frontier_annotations.py",
    "interactive/pages/6_Final_harmonization_review.py",
    "interactive/pages/7_Final_Luna_v2_4_human_validation.py",
    "interactive/pages/8_External_Sol_reference.py",
    "interactive/pages/9_Refusal_disagreement_review.py",
    "interactive/pages/10_Refusal_boundary_consistency_review.py",
    "interactive/tests/test_frontier_review.py",
    "interactive/tests/test_harmonization_review.py",
    "interactive/tests/test_refusal_boundary_consistency_review.py",
    "interactive/tests/test_refusal_disagreement_review.py",
}

SAFE_DELETE_FILES = {
    ".DS_Store", "data/.DS_Store", "pipeline/.DS_Store", "preview/.DS_Store",
    "Rplots.pdf", "responses", "writeup/pipeline_technical.aux",
    "writeup/pipeline_technical.fdb_latexmk", "writeup/pipeline_technical.fls",
    "writeup/pipeline_technical.log", "writeup/pipeline_technical.out",
    "writeup/pipeline_technical.toc",
}


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def tracked_paths() -> set[str]:
    output = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout
    return {line for line in output.splitlines() if line}


def candidates() -> list[dict]:
    tracked = tracked_paths()
    archive_paths = set(DOCS_TO_ARCHIVE) | set(CODE_TO_ARCHIVE) | set(INTERACTIVE_TO_ARCHIVE)
    archive_paths.add("MANIFEST.md")
    archive_paths.update(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "docs").iterdir()
        if path.is_file() and (
            path.suffix.lower() in {".png", ".csv"} or path.name == "budget_estimate.json"
        )
        and path.relative_to(ROOT).as_posix() not in LIVE_AUDIT_OUTPUTS
    )
    archive_paths.update(
        path.relative_to(ROOT).as_posix()
        for directory in (ROOT / "prompts", ROOT / "data")
        for path in directory.iterdir()
        if path.is_file() and ".pre_" in path.name
    )
    archive_paths.update(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "pipeline/estimates").iterdir()
        if path.is_file()
    )
    archive_paths.update(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "pipeline/tables").iterdir()
        if path.is_file() and not path.name.startswith("00_") and path.name != ".gitkeep"
    )

    delete_paths = set(SAFE_DELETE_FILES)
    for tree in (ROOT / "tmp", ROOT / "preview"):
        if tree.exists():
            delete_paths.update(
                path.relative_to(ROOT).as_posix() for path in tree.rglob("*") if path.is_file()
            )

    rows = []
    for rel in sorted(archive_paths | delete_paths):
        source = ROOT / rel
        if not source.is_file():
            continue
        action = "archive" if rel in archive_paths else "delete_recoverably"
        is_doc = rel.startswith("docs/")
        is_snapshot = ".pre_" in Path(rel).name
        unique = "true" if action == "archive" else "false"
        reason = (
            "Superseded or completed provenance removed from the live interface."
            if action == "archive" else
            "Regenerable or accidental artifact with a preserved canonical/release copy where applicable."
        )
        evidence = (
            "Historical documentation/code or pre-repair artifact; retained by hash in dated archive."
            if action == "archive" else
            "Checkpoint classified as OS cruft, empty placeholder, LaTeX byproduct, temporary render, or duplicate preview."
        )
        destination = (ARCHIVE / rel) if action == "archive" else (RECOVERY / rel)
        rows.append({
            "original_path": rel, "new_path": destination.as_posix(), "action": action,
            "classification": "historical_provenance" if action == "archive" else "accidental_junk",
            "reason": reason, "evidence": evidence,
            "upstream_creator": "documented in artifact registry or file header",
            "downstream_references": "must be repaired after move" if is_doc or action == "archive" else "none material",
            "sha256_before": sha256(source), "sha256_after": "",
            "size_bytes": source.stat().st_size,
            "reproducible": "varies" if is_snapshot else "true",
            "contains_unique_evidence": unique,
            "tracked_status": "tracked" if rel in tracked else "ignored_or_untracked",
            "applied": "false",
        })
    return rows


def write_manifest(rows: list[dict]) -> None:
    with MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def plan() -> None:
    rows = candidates()
    write_manifest(rows)
    print(f"planned {len(rows)} exact actions")
    for action in ("archive", "delete_recoverably"):
        subset = [row for row in rows if row["action"] == action]
        print(f"{action}: {len(subset)} files, {sum((ROOT / row['original_path']).stat().st_size for row in subset)} bytes")


def apply() -> None:
    if not MANIFEST.exists():
        raise FileNotFoundError("run plan before apply")
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        source = ROOT / row["original_path"]
        if not source.is_file() or sha256(source) != row["sha256_before"]:
            raise RuntimeError(f"source absent or changed after plan: {row['original_path']}")
    for row in rows:
        source = ROOT / row["original_path"]
        destination = Path(row["new_path"])
        if row["action"] == "archive":
            destination = ROOT / destination
        if destination.exists():
            raise FileExistsError(f"destination already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if row["tracked_status"] == "tracked" and row["action"] == "archive":
            subprocess.run(
                ["git", "mv", row["original_path"], row["new_path"]], cwd=ROOT, check=True
            )
        else:
            shutil.move(str(source), str(destination))
        row["sha256_after"] = sha256(destination)
        if row["sha256_after"] != row["sha256_before"]:
            raise RuntimeError(f"hash changed while moving {row['original_path']}")
        row["applied"] = "true"
    write_manifest(rows)
    print(f"applied {len(rows)} hash-preserving actions")


def plan_caches() -> None:
    """Append disposable caches, build byproducts and retired app assets."""
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    known = {row["original_path"] for row in rows}
    tracked = tracked_paths()
    additions = []
    candidates = list(ROOT.rglob("*")) + [
        ROOT / "interactive/data/manual_review_packet.parquet",
        ROOT / "Rplots.pdf",
    ]
    for path in sorted(set(candidates)):
        is_cache = {"__pycache__", ".pytest_cache"} & set(path.parts)
        is_retired_asset = path == ROOT / "interactive/data/manual_review_packet.parquet"
        is_accidental_plot = path == ROOT / "Rplots.pdf"
        is_latex_byproduct = (
            path.parent == ROOT / "writeup"
            and path.suffix in {".aux", ".fdb_latexmk", ".fls", ".log", ".out", ".toc"}
        )
        if not path.is_file() or not (
            is_cache or is_retired_asset or is_accidental_plot or is_latex_byproduct
        ):
            continue
        rel = path.relative_to(ROOT).as_posix()
        recurrent = rel in known
        destination = RECOVERY / "final_cleanup" / rel if recurrent else RECOVERY / rel
        if destination.exists():
            continue
        additions.append({
            "original_path": rel,
            "new_path": destination.as_posix(),
            "action": "delete_recoverably",
            "classification": "accidental_junk",
            "reason": "Disposable cache, build byproduct, or retired derived interactive asset.",
            "evidence": (
                "Historical review asset is reproducible from protected annotation inputs and no live page consumes it."
                if is_retired_asset else
                "Unrequested default R graphics device output; no downstream reference."
                if is_accidental_plot else
                "LaTeX build byproduct; the source and successfully rebuilt PDF are retained."
                if is_latex_byproduct else
                "Interpreter/test cache; no scientific content and regenerated automatically."
            ),
            "upstream_creator": (
                "historical interactive builder" if is_retired_asset else
                "R default graphics device" if is_accidental_plot else
                "latexmk" if is_latex_byproduct else
                "Python interpreter or pytest"
            ),
            "downstream_references": "none",
            "sha256_before": sha256(path),
            "sha256_after": "",
            "size_bytes": path.stat().st_size,
            "reproducible": "true",
            "contains_unique_evidence": "false",
            "tracked_status": "tracked" if rel in tracked else "ignored_or_untracked",
            "applied": "false",
        })
    write_manifest(rows + additions)
    print(f"appended {len(additions)} cache files to the manifest")


def apply_pending() -> None:
    """Apply only unapplied rows appended after the main cleanup."""
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    pending = [row for row in rows if row["applied"] != "true"]
    for row in pending:
        source = ROOT / row["original_path"]
        if not source.is_file() or sha256(source) != row["sha256_before"]:
            raise RuntimeError(f"pending source absent or changed: {row['original_path']}")
    for row in pending:
        source = ROOT / row["original_path"]
        destination = Path(row["new_path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(f"destination already exists: {destination}")
        shutil.move(str(source), str(destination))
        row["sha256_after"] = sha256(destination)
        row["applied"] = "true"
    write_manifest(rows)
    print(f"applied {len(pending)} appended actions")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("plan", "apply", "plan-caches", "apply-pending")
    )
    args = parser.parse_args()
    if args.command == "plan":
        plan()
    elif args.command == "apply":
        apply()
    elif args.command == "plan-caches":
        plan_caches()
    else:
        apply_pending()


if __name__ == "__main__":
    main()
