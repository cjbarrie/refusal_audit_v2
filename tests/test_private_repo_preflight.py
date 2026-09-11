from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_private_repository_preflight_passes_without_printing_secrets():
    completed = subprocess.run(
        [sys.executable, "scripts/private_repo_preflight.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "[PASS]" in completed.stdout
    assert "sk-or-v1-" not in completed.stdout
    assert "hf_" not in completed.stdout
