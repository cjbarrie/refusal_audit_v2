#!/usr/bin/env python3
"""Build expansion cell decisions and run the minimal borderline Sol audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.model_expansion.cell_viability_registry import (
    AUDIT_DIR, DEFAULT_DIR, authorize_borderline_audit,
    estimate_approved_expansion_cost, estimate_borderline_cost,
    prepare_borderline_audit, prepare_cell_registry,
    run_borderline_audit, summarize_borderline_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("registry").add_argument("--output-dir", default=str(DEFAULT_DIR))
    sub.add_parser("cost-approved-expansion").add_argument(
        "--output-dir", default=str(DEFAULT_DIR)
    )
    for name in ("prepare-audit", "cost-audit", "summarize-audit"):
        sub.add_parser(name).add_argument("--output-dir", default=str(AUDIT_DIR))
    p = sub.add_parser("authorize-audit")
    p.add_argument("--output-dir", default=str(AUDIT_DIR))
    p.add_argument("--payload-sha", required=True)
    p.add_argument("--cost-ceiling", required=True, type=float)
    p.add_argument("--confirm-user-authorization", action="store_true")
    p = sub.add_parser("run-audit")
    p.add_argument("--output-dir", default=str(AUDIT_DIR))
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--cost-ceiling", required=True, type=float)
    p.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args(); output = ROOT / args.output_dir
    if args.command == "registry": result = prepare_cell_registry(ROOT, output)
    elif args.command == "cost-approved-expansion":
        result = estimate_approved_expansion_cost(ROOT, output)
    elif args.command == "prepare-audit": result = prepare_borderline_audit(ROOT, output)
    elif args.command == "cost-audit": result = estimate_borderline_cost(ROOT, output)
    elif args.command == "authorize-audit":
        result = authorize_borderline_audit(output, args.payload_sha, args.cost_ceiling, args.confirm_user_authorization)
    elif args.command == "run-audit":
        sys.path.insert(0, str(ROOT / "scripts"))
        from env_utils import load_env_from_file
        load_env_from_file()
        result = run_borderline_audit(ROOT, output, args.workers, args.cost_ceiling, args.authorize_paid_run)
    else: result = summarize_borderline_audit(ROOT, output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
