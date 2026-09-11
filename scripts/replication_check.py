#!/usr/bin/env python3
"""Read-only repository and promoted-release replication checks.

This command makes no provider, Wikipedia, Hugging Face, or Slurm call. It
checks the frozen prompt and outcome hashes, the promoted release pointer,
release acceptance, promoted figure identity, live-script registries, and
secret-tracking boundary declared in ``config/replication_contract.json``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config/replication_contract.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def registered_paths() -> set[str]:
    specs = [
        ("scripts/SCRIPT_REGISTRY.csv", "script"),
        ("pipeline/PIPELINE_REGISTRY.csv", "script"),
        ("sourcing/SOURCING_REGISTRY.csv", "script"),
        ("hpc/HPC_REGISTRY.csv", "script"),
        ("interactive/INTERACTIVE_REGISTRY.csv", "path"),
    ]
    found: set[str] = set()
    for rel, field in specs:
        for row in csv_rows(ROOT / rel):
            found.add(row[field])
            doc = row.get("documentation") or row.get("technical_document") or row.get("authoritative_document")
            if doc and not (ROOT / doc).exists():
                raise AssertionError(f"registered documentation is missing: {doc}")
    return found


def live_scripts() -> set[str]:
    result: set[str] = set()
    for base, suffixes in {
        "scripts": {".py"}, "pipeline": {".R", ".r"},
        "sourcing": {".py", ".sh"}, "hpc": {".py", ".sbatch"},
        "interactive": {".py"},
    }.items():
        for path in (ROOT / base).rglob("*"):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            if any(part in {"archive", "pending", "node_modules", "__pycache__"} for part in path.parts):
                continue
            result.add(path.relative_to(ROOT).as_posix())
    return result


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append((name, bool(passed), detail))

    baseline = contract["promoted_baseline"]
    release_id = baseline["release_id"]
    canonical = ROOT / "pipeline/estimates/canonical"
    release = ROOT / "pipeline/releases" / release_id / "estimates"
    pointer = csv_rows(canonical / "c00_manifest.csv")
    run_ids = {row["canonical_run_id"] for row in pointer}
    check("promoted pointer", run_ids == {release_id}, str(sorted(run_ids)))
    check("promoted manifest identity",
          sha256(canonical / "c00_manifest.csv") == baseline["manifest_sha256"] == sha256(release / "c00_manifest.csv"))

    model_rows = csv_rows(canonical / "00_model_summary.csv")
    n_rows = sum(int(float(row["n"])) for row in model_rows)
    check("promoted analysis size", n_rows == baseline["analysis_rows"], str(n_rows))
    check("promoted model count", len(model_rows) == baseline["models"], str(len(model_rows)))
    acceptance = csv_rows(canonical / "c01b_acceptance_tests.csv")
    check("promoted acceptance", len(acceptance) == baseline["acceptance_checks"] and
          all(row["status"] == "PASS" for row in acceptance), str(len(acceptance)))

    for language, rel in contract["prompt_battery"]["paths"].items():
        actual = sha256(ROOT / rel)
        check(f"prompt hash {language}", actual == contract["prompt_battery"]["sha256"][language], actual)
    outcome = contract["original_panel_outcome"]
    outcome_path = ROOT / outcome["path"]
    check("original-panel outcome exists", outcome_path.exists(), outcome["path"])
    if outcome_path.exists():
        check("original-panel outcome hash", sha256(outcome_path) == outcome["sha256"], sha256(outcome_path))

    for subset in ("main", "extended"):
        live = ROOT / "pipeline/figures" / subset
        frozen = ROOT / "pipeline/releases" / release_id / "figures" / subset
        live_hashes = {p.name: sha256(p) for p in live.glob("*.png")}
        frozen_hashes = {p.name: sha256(p) for p in frozen.glob("*.png")}
        check(f"promoted {subset} figure identity", live_hashes == frozen_hashes,
              f"{len(live_hashes)} PNGs")

    registered = registered_paths()
    live = live_scripts()
    missing = sorted(live - registered)
    stale = sorted(path for path in registered if not (ROOT / path).exists())
    check("all live scripts registered", not missing, ", ".join(missing))
    check("registered paths exist", not stale, ", ".join(stale))

    tracked = set(subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, text=True,
        capture_output=True).stdout.splitlines())
    check("local secrets are not tracked", ".env" not in tracked)

    for name, passed, detail in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    failed = [name for name, passed, _ in checks if not passed]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} replication checks passed")
    if failed:
        print("Failed: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
