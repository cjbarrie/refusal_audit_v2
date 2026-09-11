import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.response_validity.inventory import build_inventory, validate_registry


def test_active_pipeline_registry_is_complete():
    errors = validate_registry(ROOT, ROOT / "pipeline" / "PIPELINE_REGISTRY.csv")
    assert not errors, "\n".join(errors)


def test_migration_inventory_has_unique_hash_addressed_files():
    rows = build_inventory(ROOT, ROOT / "config" / "response_validity_migration.csv")
    assert rows
    assert len({row.path for row in rows}) == len(rows)
    assert all(len(row.sha256) == 64 and row.bytes > 0 for row in rows)


def test_registry_marks_external_calls_explicitly():
    with (ROOT / "pipeline" / "PIPELINE_REGISTRY.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(row["paid_external_call"] in {"true", "false", "guarded by subcommand"} for row in rows)
    assert next(row for row in rows if row["script"] == "pipeline/make_release.R")[
        "paid_external_call"
    ] == "false"
