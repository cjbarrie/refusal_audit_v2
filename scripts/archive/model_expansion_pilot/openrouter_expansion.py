#!/usr/bin/env python3
"""Guarded command line for the OpenRouter subject-model expansion pilot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.model_expansion.openrouter_pilot import (
    DEFAULT_DIR,
    authorize_pilot,
    estimate_pilot_cost,
    prepare_pilot,
    run_pilot,
)
from refusal_audit.model_expansion.pilot_annotation import (
    DEFAULT_DIR as ANNOTATION_DIR,
    authorize_pilot_annotations,
    estimate_pilot_annotation_cost,
    prepare_pilot_annotations,
    run_pilot_annotations,
    summarize_pilot_annotations,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare-pilot", "estimate-pilot-cost"):
        command = sub.add_parser(name)
        command.add_argument("--output-dir", default=str(DEFAULT_DIR))
    for name in (
        "prepare-annotations", "estimate-annotation-cost", "summarize-annotations"
    ):
        command = sub.add_parser(name)
        command.add_argument("--output-dir", default=str(ANNOTATION_DIR))
    authorize = sub.add_parser("authorize-pilot")
    authorize.add_argument("--output-dir", default=str(DEFAULT_DIR))
    authorize.add_argument("--payload-sha", required=True)
    authorize.add_argument("--cost-ceiling", required=True, type=float)
    authorize.add_argument("--confirm-user-authorization", action="store_true")
    run = sub.add_parser("run-pilot")
    run.add_argument("--output-dir", default=str(DEFAULT_DIR))
    run.add_argument("--workers", type=int, default=16)
    run.add_argument("--cost-ceiling", required=True, type=float)
    run.add_argument("--authorize-paid-run", action="store_true")
    authorize_annotations = sub.add_parser("authorize-annotations")
    authorize_annotations.add_argument("--output-dir", default=str(ANNOTATION_DIR))
    authorize_annotations.add_argument("--payload-sha", required=True)
    authorize_annotations.add_argument("--cost-ceiling", required=True, type=float)
    authorize_annotations.add_argument(
        "--confirm-user-authorization", action="store_true"
    )
    run_annotations = sub.add_parser("run-annotations")
    run_annotations.add_argument("--output-dir", default=str(ANNOTATION_DIR))
    run_annotations.add_argument("--workers", type=int, default=16)
    run_annotations.add_argument("--cost-ceiling", required=True, type=float)
    run_annotations.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    output = ROOT / args.output_dir
    if args.command == "prepare-pilot":
        result = prepare_pilot(ROOT, output)
    elif args.command == "estimate-pilot-cost":
        result = estimate_pilot_cost(ROOT, output)
    elif args.command == "prepare-annotations":
        result = prepare_pilot_annotations(ROOT, output)
    elif args.command == "estimate-annotation-cost":
        result = estimate_pilot_annotation_cost(ROOT, output)
    elif args.command == "summarize-annotations":
        result = summarize_pilot_annotations(ROOT, output)
    elif args.command == "authorize-pilot":
        result = authorize_pilot(
            output, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
    elif args.command == "authorize-annotations":
        result = authorize_pilot_annotations(
            output, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
    elif args.command == "run-annotations":
        # The shared v2.4 runner reads the existing root .env directly.
        sys.path.insert(0, str(ROOT / "scripts"))
        from env_utils import load_env_from_file

        load_env_from_file()
        result = run_pilot_annotations(
            ROOT, output, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
    else:
        result = run_pilot(
            ROOT, output, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
