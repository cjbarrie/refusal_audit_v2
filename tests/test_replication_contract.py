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
    assert candidate["release_id"] == "canon_029"
    assert candidate["analysis_rows"] == 249_201
    assert candidate["models"] == 20
    assert candidate["promoted"] is False


def test_ordered_stage_registry_has_unique_monotone_stage_ids():
    with (ROOT / "config/REPLICATION_STAGES.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    stages = [int(row["stage"]) for row in rows]
    assert stages == sorted(stages)
    assert len(stages) == len(set(stages))
    assert rows[-1]["name"] == "model expansion workbench"


def test_read_only_replication_check_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/replication_check.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "17/17 replication checks passed" in completed.stdout
