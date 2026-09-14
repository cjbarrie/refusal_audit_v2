from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_replication_contract_is_parseable_and_profiles_do_not_collapse():
    contract = json.loads((ROOT / "config/replication_contract.json").read_text())
    promoted = contract["promoted_baseline"]
    candidate = contract["current_candidate"]
    assert promoted["release_id"] == "canon_024"
    assert promoted["analysis_rows"] == 224_544
    assert promoted["models"] == 18
    assert candidate["release_id"] == "canon_031"
    assert candidate["analysis_rows"] == 299_080
    assert candidate["models"] == 24
    assert candidate["promoted"] is False


def test_ordered_stage_registry_has_unique_monotone_stage_ids():
    with (ROOT / "config/REPLICATION_STAGES.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    stages = [int(row["stage"]) for row in rows]
    assert stages == sorted(stages)
    assert len(stages) == len(set(stages))
    assert rows[-1]["name"] == "model expansion workbench"


def test_master_pipeline_is_linked_and_covers_every_global_stage():
    master = (ROOT / "docs" / "TECHNICAL_PIPELINE.md").read_text()
    with (ROOT / "config" / "REPLICATION_STAGES.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["stage"] == "90":
            continue
        assert f"## {int(row['stage']):02d}." in master, row["stage"]
    for rel in ["README.md", "docs/README.md", "docs/REPLICATION_GUIDE.md"]:
        assert "TECHNICAL_PIPELINE.md" in (ROOT / rel).read_text()


def test_historical_correction_entrypoint_cannot_execute_repairs():
    wrapper = (ROOT / "sourcing" / "run_corrections.sh").read_text()
    assert "historical, non-executing recipe" in wrapper
    assert "exit 2" in wrapper
    assert "python 09_migrate_issue_ids.py" not in wrapper


def test_read_only_replication_check_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/replication_check.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "17/17 replication checks passed" in completed.stdout
