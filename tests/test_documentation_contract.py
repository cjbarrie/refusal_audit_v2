import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def active_r_scripts():
    return sorted((ROOT / "pipeline").glob("*.R"))


def test_every_active_r_script_has_linked_companion_document():
    for script in active_r_scripts():
        companion = ROOT / "docs" / "r_pipeline" / f"{script.stem}.md"
        assert companion.exists(), f"missing {companion}"
        expected = f"Technical reference: docs/r_pipeline/{script.stem}.md"
        assert expected in script.read_text(encoding="utf-8")


def test_current_walkthrough_does_not_run_obsolete_driver():
    text = (ROOT / "docs" / "R_PIPELINE_WALKTHROUGH.md").read_text(encoding="utf-8")
    assert "pipeline/run_all.R" not in text
    assert "pipeline/make_release.R" in text


def test_every_live_python_command_is_numbered_in_registry():
    registry_path = ROOT / "scripts" / "SCRIPT_REGISTRY.csv"
    with registry_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    registered = [row["script"] for row in rows]
    expected = sorted([
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "scripts").glob("*.py")
    ] + [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "scripts" / "checks").glob("*.py")
    ])
    assert sorted(registered) == expected
    assert len({row["stage"] for row in rows}) == len(rows)
    assert all(row["stage"] and row["status"] and row["purpose"] for row in rows)


def test_retired_skip_data_release_mode_is_rejected_in_source_and_docs():
    source = (ROOT / "pipeline" / "make_release.R").read_text(encoding="utf-8")
    reference = (ROOT / "docs" / "r_pipeline" / "make_release.md").read_text(
        encoding="utf-8"
    )
    assert 'if (has("--skip-data"))' in source
    assert "was retired" in source
    assert "retired `--skip-data`" in reference
