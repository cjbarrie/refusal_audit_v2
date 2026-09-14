#!/usr/bin/env python3
"""Build the repository-wide forensic artifact registry without external calls.

Input: the complete working tree, excluding Git internals and dependency/cache
directories. Output: ``docs/ARTIFACT_REGISTRY.csv``. The registry is an audit
aid, not an instruction to move or delete files; uncertain cases remain marked
``unknown_requires_review`` until their provenance is resolved.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/ARTIFACT_REGISTRY.csv"
EXCLUDED_PARTS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    "node_modules", ".next", ".vinext", ".wrangler", "dist",
}
REFERENCE_SUFFIXES = {
    ".py", ".r", ".R", ".sh", ".md", ".tex", ".yaml", ".yml", ".toml",
    ".json", ".txt", ".csv",
}
PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.-])"
    r"(?:annotations|archive|config|data|docs|interactive|logs|pipeline|preview|"
    r"prompts|scripts|sourcing|src|tests|tmp|writeup)/"
    r"[A-Za-z0-9_./+@=-]+"
)
FIELDS = [
    "path", "file_type", "tracked_status", "size_bytes", "scientific_role",
    "created_by", "upstream_inputs", "downstream_consumers", "current_status",
    "canonical_or_supporting", "reproducible", "contains_unique_evidence",
    "recommended_action", "confidence", "evidence", "new_path",
    "sha256_before", "sha256_after",
]

CURRENT_DOCS = {
    "README.md", "CLAUDE.md", "MANIFEST.md", "docs/CANONICAL_ANALYSES.md",
    "docs/DEFERRED_SLANT_MORAL_VALIDITY.md",
    "docs/ARCHIVE_MANIFEST.csv", "docs/ARTIFACT_REGISTRY.csv",
    "docs/CANONICAL_FIGURE_LEGENDS.md", "docs/CODE_ANALYSIS_AUDIT.md",
    "docs/PIPELINE_ENTRYPOINTS.md",
    "docs/TECHNICAL_PIPELINE.md",
    "docs/REPOSITORY_MAP.md",
    "docs/RESPONSE_VALIDITY.md",
    "docs/NATIVE_SOURCING.md", "docs/PIPELINE.md", "docs/REBALANCE.md",
    "docs/REPRODUCIBILITY.md",
    "docs/TEMPORAL_SOURCING.md", "docs/repro_check.md",
    "docs/RESPONSE_VALIDITY_CODEBOOK_RATIONALE.md",
    "docs/RESPONSE_VALIDITY_DECISION_LOG.md",
    "docs/RESPONSE_VALIDITY_TECHNICAL_PIPELINE.md",
    "docs/R_PIPELINE_WALKTHROUGH.md",
    "docs/OPENROUTER_MODEL_EXPANSION_V1.md", "docs/README.md",
    "docs/REPLICATION_GUIDE.md", "docs/REPLICATION_STATUS.md",
    "docs/PRIVATE_REPOSITORY_HANDOFF.md",
    "docs/REPOSITORY_AUDIT_2026-09-11.md",
    "docs/REPOSITORY_AUDIT_2026-09-14.md",
    "docs/JURISDICTION_MODEL_EXPANSION_V1.md",
    "docs/LOCAL_GGUF_MODEL_EXPANSION_V1.md",
    "docs/HPC_LOCAL_GGUF_FULL_V1.md",
    "docs/HPC_LOCAL_MODEL_CANDIDATE_SWEEP.md",
    "docs/FANAR_EXPERIMENTS_V1.md",
}
CURRENT_ROOT_FILES = {
    ".gitignore", ".gitattributes", ".here", "requirements.txt", "requirements-lock.txt",
    "renv.lock", "pytest.ini", "Makefile",
}
CURRENT_ROOTS = {
    "config", "hpc", "interactive", "pipeline", "scripts", "sourcing",
    "src", "tests",
}
ACCIDENTAL_NAMES = {".DS_Store", "Rplots.pdf"}
LATEX_BUILD_SUFFIXES = {".aux", ".fls", ".fdb_latexmk", ".toc", ".out", ".log"}


def git_lines(*args: str) -> set[str]:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True, capture_output=True
    )
    return {line for line in result.stdout.splitlines() if line}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def file_type(path: Path, exists: bool) -> str:
    if not exists:
        return "missing_tracked_file"
    if path.name == ".env":
        return "secret_environment_file"
    suffix = path.suffix.lower()
    return {
        ".py": "python", ".r": "r", ".sh": "shell", ".md": "markdown",
        ".tex": "latex", ".pdf": "pdf", ".json": "json", ".jsonl": "jsonl",
        ".csv": "csv", ".tsv": "tsv", ".parquet": "parquet", ".rds": "rds",
        ".rdata": "rdata", ".png": "png", ".svg": "svg", ".yaml": "yaml",
        ".yml": "yaml", ".gz": "compressed", ".txt": "text", ".log": "log",
    }.get(suffix, "file")


def classify(rel: str, exists: bool) -> dict[str, str]:
    path = Path(rel)
    top = path.parts[0] if path.parts else ""
    name, suffix = path.name, path.suffix.lower()
    base = {
        "scientific_role": "unresolved repository artifact",
        "created_by": "unknown",
        "upstream_inputs": "unknown",
        "current_status": "unknown_requires_review",
        "canonical_or_supporting": "false",
        "reproducible": "unknown",
        "contains_unique_evidence": "unknown",
        "recommended_action": "review",
        "confidence": "low",
        "evidence": "No safe automatic classification rule; retain pending review.",
        "new_path": "",
    }
    if not exists:
        base.update(
            scientific_role="tracked path absent from working tree",
            current_status="superseded", recommended_action="review",
            reproducible="git_history", contains_unique_evidence="possible",
            confidence="medium", evidence="Tracked by Git but currently deleted in dirty worktree.",
        )
        return base
    if name == ".env":
        base.update(
            scientific_role="local credentials", current_status="active_supporting",
            canonical_or_supporting="true", reproducible="false",
            contains_unique_evidence="sensitive", recommended_action="keep_ignored",
            confidence="high", evidence="Local secret file; never archive or commit.",
        )
        return base
    if rel in CURRENT_ROOT_FILES:
        base.update(
            scientific_role="live repository configuration or dependency specification",
            current_status="active_supporting", canonical_or_supporting="true",
            reproducible="true", contains_unique_evidence="false",
            recommended_action="keep", confidence="high",
            evidence="Current root-level execution/configuration surface.",
        )
        return base
    if rel.startswith(".github/workflows/") and suffix in {".yaml", ".yml"}:
        base.update(
            scientific_role="live GitHub automation",
            current_status="active_supporting", canonical_or_supporting="true",
            reproducible="true", contains_unique_evidence="true",
            recommended_action="keep_and_review_before_publication", confidence="high",
            evidence="Tracked workflow for the repository's documented publication surface.",
        )
        return base
    if name in ACCIDENTAL_NAMES or (top == "writeup" and suffix in LATEX_BUILD_SUFFIXES):
        base.update(
            scientific_role="disposable generated artifact", current_status="accidental_junk",
            reproducible="true", contains_unique_evidence="false",
            recommended_action="delete_after_checkpoint", confidence="high",
            evidence="OS, accidental plotting, or LaTeX build byproduct.",
        )
        return base
    if top == "tmp":
        base.update(
            scientific_role="temporary render or inspection output",
            current_status="generated_reproducible", reproducible="true",
            contains_unique_evidence="false", recommended_action="delete_after_checkpoint",
            confidence="high", evidence="Repository-local temporary working directory.",
        )
        return base
    if top == "archive" or "archive" in path.parts or top == "logs":
        base.update(
            scientific_role="historical implementation, output, or execution record",
            current_status="historical_provenance", reproducible="varies",
            contains_unique_evidence="true", recommended_action="keep_archived",
            confidence="high", evidence="Already located in an explicit archive or log tree.",
        )
        return base
    if any(".pre_" in part for part in path.parts):
        base.update(
            scientific_role="pre-repair snapshot", current_status="historical_provenance",
            reproducible="false", contains_unique_evidence="true",
            recommended_action="archive", confidence="high",
            evidence="Filename records a pre-migration or pre-correction snapshot.",
        )
        return base
    if rel == "prompts/AI Workshop Invite List.csv":
        base.update(
            scientific_role="unresolved non-pipeline CSV in the prompt tree",
            current_status="unknown_requires_review", reproducible="unknown",
            contains_unique_evidence="unknown", recommended_action="retain_pending_owner_review",
            confidence="high", evidence="No live code or documentation consumer found; provenance is unresolved.",
        )
        return base
    if rel == "annotations/response_validity_v2_4/wall_to_wall_luna_v1/final_annotations.parquet":
        base.update(
            scientific_role="complete canonical Luna v2.4 response annotation table",
            created_by="scripts/response_validity.py assemble-final-wall-to-wall-luna-v2-4",
            upstream_inputs="reused v2.4 labels; wall-to-wall results; repair results",
            current_status="active_canonical", canonical_or_supporting="true",
            reproducible="true", contains_unique_evidence="true",
            recommended_action="keep", confidence="high",
            evidence="Current 137,186-row outcome assembly with frozen expected hash.",
        )
        return base
    if rel in {
        "config/replication_contract.json", "config/REPLICATION_STAGES.csv",
        "scripts/SCRIPT_REGISTRY.csv", "pipeline/PIPELINE_REGISTRY.csv",
        "sourcing/SOURCING_REGISTRY.csv", "hpc/HPC_REGISTRY.csv",
        "interactive/INTERACTIVE_REGISTRY.csv",
    }:
        base.update(
            scientific_role="current replication contract or executable registry",
            current_status="active_supporting", canonical_or_supporting="true",
            reproducible="true", contains_unique_evidence="true",
            recommended_action="keep_and_update", confidence="high",
            evidence="Defines the supported replication surface and its ordering.",
        )
        return base
    if rel == "annotations/README.md":
        base.update(
            scientific_role="current annotation-tree retention and inclusion guide",
            current_status="active_supporting", canonical_or_supporting="true",
            reproducible="true", contains_unique_evidence="true",
            recommended_action="keep_and_update", confidence="high",
            evidence="Current reader-facing map of response and annotation evidence.",
        )
        return base
    if rel.startswith("annotations/response_validity_v2_4/") or rel.startswith("annotations/full_v1/"):
        base.update(
            scientific_role="current response or annotation provenance",
            current_status="active_supporting", canonical_or_supporting="true",
            reproducible="expensive", contains_unique_evidence="true",
            recommended_action="keep", confidence="high",
            evidence="Required to reconstruct the current corpus or v2.4 annotation assembly.",
        )
        return base
    if top == "annotations":
        base.update(
            scientific_role="historical annotation, validation, or pilot run state",
            current_status="historical_provenance", reproducible="expensive",
            contains_unique_evidence="true", recommended_action="retain_or_archive",
            confidence="medium", evidence="Non-current annotation tree; preserve until run-level provenance is mapped.",
        )
        return base
    if rel.startswith("pipeline/estimates/canonical/") or rel.startswith("pipeline/figures/"):
        base.update(
            scientific_role="promoted historical canonical analysis output",
            current_status="active_canonical", canonical_or_supporting="true",
            reproducible="true", contains_unique_evidence="true",
            recommended_action="keep", confidence="high",
            evidence="Promoted canonical output; estimands remain subject to later scientific revision.",
        )
        return base
    if rel.startswith("pipeline/releases/"):
        base.update(
            scientific_role="immutable analysis release build",
            current_status="historical_provenance", reproducible="true",
            contains_unique_evidence="true", recommended_action="keep_ignored",
            confidence="high", evidence="Historical release; never delete or mutate during rationalization.",
        )
        return base
    if rel.startswith("preview/"):
        base.update(
            scientific_role="unpromoted figure preview", current_status="generated_reproducible",
            reproducible="true", contains_unique_evidence="false",
            recommended_action="archive_or_delete_after_comparison", confidence="medium",
            evidence="Ignored preview tree; compare with promoted figure hashes before removal.",
        )
        return base
    if top == "prompts":
        status = "historical_provenance" if ".pre_" in name else "active_supporting"
        base.update(
            scientific_role="prompt battery, review sheet, or prompt provenance",
            current_status=status, canonical_or_supporting="true" if status == "active_supporting" else "false",
            reproducible="varies", contains_unique_evidence="true",
            recommended_action="keep" if status == "active_supporting" else "archive",
            confidence="medium", evidence="Prompt artifacts require route- and version-level dependency mapping.",
        )
        return base
    if top == "data":
        base.update(
            scientific_role="sourcing input, intermediate, diagnostic, or provenance cache",
            current_status="active_supporting", canonical_or_supporting="true",
            reproducible="varies", contains_unique_evidence="possible",
            recommended_action="keep_pending_stage_mapping", confidence="medium",
            evidence="Data tree supports prompt sourcing and provenance; classify at file level before moves.",
        )
        return base
    if top == "writeup":
        base.update(
            scientific_role="current technical write-up source or rendered document",
            current_status="active_supporting", canonical_or_supporting="true",
            reproducible="true", contains_unique_evidence="true",
            recommended_action="keep", confidence="high",
            evidence="Current write-up surface; historical versions are in writeup/archive.",
        )
        return base
    if rel in CURRENT_DOCS or rel.startswith("docs/r_pipeline/"):
        base.update(
            scientific_role="current technical or reader-facing documentation",
            current_status="active_supporting", canonical_or_supporting="true",
            reproducible="true", contains_unique_evidence="true",
            recommended_action="keep_and_update", confidence="high",
            evidence="Named current documentation surface.",
        )
        return base
    if top == "docs":
        base.update(
            scientific_role="historical, provisional, or unresolved project documentation",
            current_status="unknown_requires_review", reproducible="true",
            contains_unique_evidence="possible", recommended_action="review_for_archive",
            confidence="medium", evidence="Not in the initial current-document allowlist.",
        )
        return base
    if top in CURRENT_ROOTS:
        base.update(
            scientific_role="live code, test, configuration, or application asset",
            current_status="active_supporting", canonical_or_supporting="true",
            reproducible="true", contains_unique_evidence="true",
            recommended_action="keep_pending_dependency_review", confidence="medium",
            evidence="Located on a currently supported code or application surface.",
        )
        return base
    if name == ".here":
        base.update(
            scientific_role="R project-root marker", current_status="active_supporting",
            canonical_or_supporting="true", reproducible="true",
            contains_unique_evidence="false", recommended_action="keep", confidence="high",
            evidence="Used by here::here() to resolve portable R paths.",
        )
        return base
    if rel == "responses":
        base.update(
            scientific_role="empty legacy root placeholder", current_status="unknown_requires_review",
            reproducible="true", contains_unique_evidence="false",
            recommended_action="delete_after_reference_check", confidence="medium",
            evidence="Zero-byte regular file, despite README describing a directory.",
        )
        return base
    return base


def direct_references(paths: set[str]) -> dict[str, set[str]]:
    references: dict[str, set[str]] = defaultdict(set)
    for source in sorted(paths):
        path = ROOT / source
        if not path.is_file() or path.suffix not in REFERENCE_SUFFIXES:
            continue
        if path.stat().st_size > 2 * 1024 * 1024 or path.name == ".env":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in PATH_PATTERN.findall(text):
            candidate = match.rstrip(".,:;)'\"]}")
            if candidate in paths and candidate != source:
                references[candidate].add(source)
    return references


def main() -> None:
    tracked = git_lines("ls-files")
    untracked = git_lines("ls-files", "-o", "--exclude-standard")
    ignored = git_lines("ls-files", "-i", "-o", "--exclude-standard")
    existing: set[str] = set()
    for directory, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_PARTS]
        base = Path(directory)
        for filename in filenames:
            existing.add((base / filename).relative_to(ROOT).as_posix())
    paths = existing | {path for path in tracked if not (ROOT / path).exists()}
    references = direct_references(paths)
    rows = []
    for rel in sorted(paths):
        path, exists = ROOT / rel, (ROOT / rel).is_file()
        if rel in tracked:
            status = "tracked"
        elif rel in ignored:
            status = "ignored"
        elif rel in untracked:
            status = "untracked"
        else:
            status = "outside_git_classification"
        classification = classify(rel, exists)
        consumers = sorted(references.get(rel, set()))
        if consumers:
            classification["downstream_consumers"] = ";".join(consumers)
            classification["evidence"] += f" Direct path references found in {len(consumers)} file(s)."
        else:
            classification["downstream_consumers"] = "none_found_by_direct_path_scan"
        # A credential-file hash is an unnecessary stable fingerprint. The
        # registry records its ignored presence but never its contents/hash.
        # The registry itself cannot carry a stable hash of itself.
        checksum = (
            "" if rel in {".env", "docs/ARTIFACT_REGISTRY.csv"}
            else digest(path) if exists else ""
        )
        rows.append({
            "path": rel, "file_type": file_type(path, exists),
            "tracked_status": status, "size_bytes": path.stat().st_size if exists else 0,
            **classification, "sha256_before": checksum, "sha256_after": checksum,
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["current_status"]] += 1
    print(f"wrote {len(rows)} rows to {OUTPUT.relative_to(ROOT)}")
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")


if __name__ == "__main__":
    main()
