#!/usr/bin/env python3
"""Download the exact revision and filename for one frozen GGUF model."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/model_rosters/local_gguf_hpc_v1.json"


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-index", type=int, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG,
        help="Versioned roster path; defaults to the active four-model HPC roster.",
    )
    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    # Standard production rosters use ``models``. Focused comparison rosters
    # may retain multiple subject systems under ``systems``; the caller pins
    # the exact index in either case.
    roster = config.get("models") or config.get("systems")
    if roster is None:
        raise ValueError("roster must contain a models or systems array")
    model = roster[args.model_index]
    for required in ("name", "gguf_repository", "gguf_revision", "gguf_filename"):
        if required not in model:
            raise ValueError(f"selected roster entry is not a downloadable GGUF model: {required}")
    hpc_root = Path(os.environ.get("REFUSAL_HPC_ROOT", f"/scratch/{os.environ['USER']}/refusal_audit_hpc"))
    target_dir = hpc_root / "models" / model["name"]
    target_dir.mkdir(parents=True, exist_ok=True)
    path = Path(hf_hub_download(
        repo_id=model["gguf_repository"], filename=model["gguf_filename"],
        revision=model["gguf_revision"], local_dir=target_dir,
    ))
    record = {
        "model": model["name"], "repository": model["gguf_repository"],
        "revision": model["gguf_revision"], "filename": model["gguf_filename"],
        "bytes": path.stat().st_size, "sha256": sha_file(path),
    }
    lock = hpc_root / "locks" / f"{model['name']}.json"
    lock.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
