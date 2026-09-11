#!/usr/bin/env python3
"""Guarded preparation, authorization and execution for expansion stages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refusal_audit.model_expansion.full_run_v3 import (
    DEFAULT_DIR, authorize_stage, estimate_full_run_cost, prepare_full_run,
    run_stage, V31_HUNYUAN_DIR, estimate_hunyuan_revision_cost,
    prepare_hunyuan_all_languages_revision,
)
from refusal_audit.model_expansion.full_run_annotation_v3 import (
    DEFAULT_DIR as ANNOTATION_BATCH_DIR, KIMI_DIR as ANNOTATION_BATCH3_DIR,
    NEXT_DIR as ANNOTATION_BATCH2_DIR,
    authorize_completed_batch_annotations,
    authorize_next_batch_annotations,
    estimate_completed_batch_annotation_cost,
    estimate_next_batch_annotation_cost,
    prepare_completed_batch_annotations,
    prepare_next_batch_annotations,
    prepare_kimi_batch_annotations, estimate_kimi_batch_annotation_cost,
    authorize_kimi_batch_annotations,
    run_completed_batch_annotations,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=(
            "prepare", "cost", "authorize-stage", "run-stage",
            "prepare-hunyuan-revision", "cost-hunyuan-revision",
            "prepare-completed-annotations", "cost-completed-annotations",
            "authorize-completed-annotations", "run-completed-annotations",
            "prepare-next-annotations", "cost-next-annotations",
            "authorize-next-annotations", "run-next-annotations",
            "prepare-kimi-annotations", "cost-kimi-annotations",
            "authorize-kimi-annotations", "run-kimi-annotations",
        )
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_DIR))
    parser.add_argument("--stage", type=int)
    parser.add_argument("--payload-sha")
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--confirm-user-authorization", action="store_true")
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    annotation_commands = {
        "prepare-completed-annotations", "cost-completed-annotations",
        "authorize-completed-annotations", "run-completed-annotations",
        "prepare-next-annotations", "cost-next-annotations",
        "authorize-next-annotations", "run-next-annotations",
    }
    next_annotation_commands = {
        "prepare-next-annotations", "cost-next-annotations",
        "authorize-next-annotations", "run-next-annotations",
    }
    kimi_annotation_commands = {
        "prepare-kimi-annotations", "cost-kimi-annotations",
        "authorize-kimi-annotations", "run-kimi-annotations",
    }
    output = ROOT / (
        ANNOTATION_BATCH3_DIR
        if args.command in kimi_annotation_commands and args.output_dir == str(DEFAULT_DIR)
        else
        ANNOTATION_BATCH2_DIR
        if args.command in next_annotation_commands and args.output_dir == str(DEFAULT_DIR)
        else ANNOTATION_BATCH_DIR
        if args.command in annotation_commands and args.output_dir == str(DEFAULT_DIR)
        else
        V31_HUNYUAN_DIR
        if args.command in {"prepare-hunyuan-revision", "cost-hunyuan-revision"}
        and args.output_dir == str(DEFAULT_DIR)
        else Path(args.output_dir)
    )
    if args.command == "prepare":
        result = prepare_full_run(ROOT, output)
    elif args.command == "cost":
        result = estimate_full_run_cost(ROOT, output)
    elif args.command == "prepare-hunyuan-revision":
        result = prepare_hunyuan_all_languages_revision(ROOT, output)
    elif args.command == "cost-hunyuan-revision":
        result = estimate_hunyuan_revision_cost(ROOT, output)
    elif args.command == "prepare-completed-annotations":
        result = prepare_completed_batch_annotations(ROOT, output)
    elif args.command == "cost-completed-annotations":
        result = estimate_completed_batch_annotation_cost(ROOT, output)
    elif args.command == "prepare-next-annotations":
        result = prepare_next_batch_annotations(ROOT, output)
    elif args.command == "cost-next-annotations":
        result = estimate_next_batch_annotation_cost(ROOT, output)
    elif args.command == "prepare-kimi-annotations":
        result = prepare_kimi_batch_annotations(ROOT, output)
    elif args.command == "cost-kimi-annotations":
        result = estimate_kimi_batch_annotation_cost(ROOT, output)
    elif args.command == "authorize-completed-annotations":
        if args.payload_sha is None or args.cost_ceiling is None:
            parser.error("authorize-completed-annotations requires --payload-sha and --cost-ceiling")
        result = authorize_completed_batch_annotations(
            output, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
    elif args.command == "run-completed-annotations":
        if args.cost_ceiling is None:
            parser.error("run-completed-annotations requires --cost-ceiling")
        sys.path.insert(0, str(ROOT / "scripts"))
        from env_utils import load_env_from_file

        load_env_from_file()
        result = run_completed_batch_annotations(
            ROOT, output, min(args.workers, 32), args.cost_ceiling,
            args.authorize_paid_run,
        )
    elif args.command == "authorize-next-annotations":
        if args.payload_sha is None or args.cost_ceiling is None:
            parser.error("authorize-next-annotations requires --payload-sha and --cost-ceiling")
        result = authorize_next_batch_annotations(
            output, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
    elif args.command == "run-next-annotations":
        if args.cost_ceiling is None:
            parser.error("run-next-annotations requires --cost-ceiling")
        sys.path.insert(0, str(ROOT / "scripts"))
        from env_utils import load_env_from_file

        load_env_from_file()
        result = run_completed_batch_annotations(
            ROOT, output, min(args.workers, 32), args.cost_ceiling,
            args.authorize_paid_run,
        )
    elif args.command == "authorize-kimi-annotations":
        if args.payload_sha is None or args.cost_ceiling is None:
            parser.error("authorize-kimi-annotations requires --payload-sha and --cost-ceiling")
        result = authorize_kimi_batch_annotations(
            output, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
    elif args.command == "run-kimi-annotations":
        if args.cost_ceiling is None:
            parser.error("run-kimi-annotations requires --cost-ceiling")
        sys.path.insert(0, str(ROOT / "scripts"))
        from env_utils import load_env_from_file

        load_env_from_file()
        result = run_completed_batch_annotations(
            ROOT, output, min(args.workers, 32), args.cost_ceiling,
            args.authorize_paid_run,
        )
    elif args.command == "authorize-stage":
        if args.stage is None or args.payload_sha is None or args.cost_ceiling is None:
            parser.error("authorize-stage requires --stage, --payload-sha and --cost-ceiling")
        result = authorize_stage(
            output, args.stage, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
    else:
        if args.stage is None or args.cost_ceiling is None:
            parser.error("run-stage requires --stage and --cost-ceiling")
        result = run_stage(
            ROOT, output, args.stage, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
