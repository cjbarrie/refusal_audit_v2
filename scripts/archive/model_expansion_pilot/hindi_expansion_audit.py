#!/usr/bin/env python3
"""Guarded CLI for the complete Hindi expansion-pilot cell audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.model_expansion.hindi_cell_audit import (
    DEFAULT_DIR,
    authorize_hindi_cell_audit,
    estimate_hindi_cell_audit_cost,
    prepare_hindi_cell_audit,
    run_hindi_cell_audit,
    summarize_hindi_cell_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "cost", "summarize"):
        p = sub.add_parser(name)
        p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p = sub.add_parser("authorize")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.add_argument("--payload-sha", required=True)
    p.add_argument("--cost-ceiling", required=True, type=float)
    p.add_argument("--confirm-user-authorization", action="store_true")
    p = sub.add_parser("run")
    p.add_argument("--output-dir", default=str(DEFAULT_DIR))
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--cost-ceiling", required=True, type=float)
    p.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    output = ROOT / args.output_dir
    if args.command == "prepare":
        result = prepare_hindi_cell_audit(ROOT, output)
    elif args.command == "cost":
        result = estimate_hindi_cell_audit_cost(ROOT, output)
    elif args.command == "authorize":
        result = authorize_hindi_cell_audit(
            output, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
    elif args.command == "run":
        sys.path.insert(0, str(ROOT / "scripts"))
        from env_utils import load_env_from_file

        load_env_from_file()
        result = run_hindi_cell_audit(
            ROOT, output, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
    else:
        result = summarize_hindi_cell_audit(ROOT, output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
