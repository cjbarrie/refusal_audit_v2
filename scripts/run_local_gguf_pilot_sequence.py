#!/usr/bin/env python3
"""Resume the local admission pilots sequentially without paid API calls."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    [sys.executable, str(ROOT / "scripts/gigachat_local_pilot.py"), "run"],
    [sys.executable, str(ROOT / "scripts/local_gguf_expansion_pilot.py"), "run", "--model", "krutrim-2-instruct-local-q8"],
    [sys.executable, str(ROOT / "scripts/local_gguf_expansion_pilot.py"), "run", "--model", "salamandra-7b-instruct-2606-local-q8"],
)


def main() -> None:
    for command in COMMANDS:
        print(f"Starting: {' '.join(command)}", flush=True)
        subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
