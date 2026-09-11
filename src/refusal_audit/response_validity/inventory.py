"""Forensic inventory and active-pipeline registry validation.

This module is deliberately standard-library only so the provenance baseline
does not depend on the annotation environment being installed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


MIGRATION_STATUSES = {
    "tracked_legacy",
    "superseded",
    "completed_provenance",
    "consolidate",
    "superseded_generated",
}
# ``pending`` is a deliberate live classification for analyses retained outside
# the canonical execution path until their outcomes/estimands are adopted. It
# is distinct from ``planned`` (not yet implemented) and ``retired`` (historical).
REGISTRY_STATUSES = {"active", "pending", "planned", "retired"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


@dataclass(frozen=True)
class InventoryRow:
    path: str
    sha256: str
    bytes: int
    status: str
    replacement: str
    rationale: str
    git_tracked: bool


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_inventory(root: Path, spec_path: Path) -> list[InventoryRow]:
    rows: list[InventoryRow] = []
    seen: set[Path] = set()
    tracked = set(git_output(root, "ls-files").splitlines())
    for rule in _read_csv(spec_path):
        status = rule["status"]
        if status not in MIGRATION_STATUSES:
            raise ValueError(f"unknown migration status: {status}")
        matches = sorted(root.glob(rule["pattern"]))
        if not matches:
            raise FileNotFoundError(f"migration pattern matched nothing: {rule['pattern']}")
        for path in matches:
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            rel = path.relative_to(root).as_posix()
            rows.append(
                InventoryRow(
                    path=rel,
                    sha256=sha256(path),
                    bytes=path.stat().st_size,
                    status=status,
                    replacement=rule["replacement"],
                    rationale=rule["rationale"],
                    git_tracked=rel in tracked,
                )
            )
    return sorted(rows, key=lambda row: row.path)


def write_inventory(
    root: Path, spec_path: Path, csv_path: Path, metadata_path: Path
) -> None:
    rows = build_inventory(root, spec_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0])))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git_output(root, "rev-parse", "HEAD"),
        "git_branch": git_output(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": bool(git_output(root, "status", "--porcelain")),
        "spec_path": spec_path.relative_to(root).as_posix(),
        "spec_sha256": sha256(spec_path),
        "inventory_csv": csv_path.relative_to(root).as_posix(),
        "inventory_sha256": sha256(csv_path),
        "n_files": len(rows),
        "n_untracked": sum(not row.git_tracked for row in rows),
        "status_counts": {
            status: sum(row.status == status for row in rows)
            for status in sorted({row.status for row in rows})
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def validate_registry(root: Path, registry_path: Path) -> list[str]:
    rows = _read_csv(registry_path)
    errors: list[str] = []
    scripts = [row["script"] for row in rows]
    if len(scripts) != len(set(scripts)):
        errors.append("registry contains duplicate script paths")
    for row in rows:
        status = row["status"]
        if status not in REGISTRY_STATUSES:
            errors.append(f"{row['script']}: unknown status {status}")
            continue
        script = root / row["script"]
        document = root / row["technical_document"]
        if status == "active" and not script.exists():
            errors.append(f"active script missing: {row['script']}")
        if status in {"active", "planned"} and not document.exists():
            errors.append(f"technical document missing: {row['technical_document']}")
        if row["paid_external_call"] not in {"true", "false", "guarded by subcommand"}:
            errors.append(f"{row['script']}: invalid paid_external_call value")
    registered_r = {
        row["script"]
        for row in rows
        if row["status"] == "active" and row["script"].startswith("pipeline/")
        and row["script"].endswith(".R")
    }
    actual_r = {path.relative_to(root).as_posix() for path in (root / "pipeline").glob("*.R")}
    for path in sorted(actual_r - registered_r):
        errors.append(f"unregistered active R script: {path}")
    for path in sorted(registered_r - actual_r):
        errors.append(f"registered active R script absent: {path}")
    return errors
