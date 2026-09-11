#!/usr/bin/env python3
"""Guarded CLI for the versioned Apertus v1.5 8B pilot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.model_expansion.apertus_8b_pilot import (
    DEFAULT_DIR,
    authorize_apertus_8b_pilot,
    estimate_apertus_8b_cost,
    prepare_apertus_8b_pilot,
    run_apertus_8b_pilot,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare-pilot", "estimate-pilot-cost"):
        command = sub.add_parser(name)
        command.add_argument("--output-dir", default=str(DEFAULT_DIR))
    authorize = sub.add_parser("authorize-pilot")
    authorize.add_argument("--output-dir", default=str(DEFAULT_DIR))
    authorize.add_argument("--payload-sha", required=True)
    authorize.add_argument("--cost-ceiling", required=True, type=float)
    authorize.add_argument("--confirm-user-authorization", action="store_true")
    run = sub.add_parser("run-pilot")
    run.add_argument("--output-dir", default=str(DEFAULT_DIR))
    run.add_argument("--workers", type=int, default=8)
    run.add_argument("--cost-ceiling", required=True, type=float)
    run.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    output = ROOT / args.output_dir
    if args.command == "prepare-pilot":
        result = prepare_apertus_8b_pilot(ROOT, output)
    elif args.command == "estimate-pilot-cost":
        result = estimate_apertus_8b_cost(ROOT, output)
    elif args.command == "authorize-pilot":
        result = authorize_apertus_8b_pilot(
            output, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
    else:
        result = run_apertus_8b_pilot(
            ROOT, output, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
