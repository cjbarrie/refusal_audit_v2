#!/usr/bin/env python3
"""Single guarded operational entry point for response-validity work.

Local builders and scorers make no provider calls. Paid commands fail closed
unless an exact payload authorization and an explicit execution flag exist.
Release construction never invokes a paid command.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from env_utils import load_env_from_file

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from refusal_audit.response_validity.inventory import (  # noqa: E402
    validate_registry,
    write_inventory,
)
from refusal_audit.response_validity.human_pilot import (  # noqa: E402
    assemble_review_packet,
    build_pilot_design,
    estimate_translation_volume,
)
from refusal_audit.response_validity.human_audit import (  # noqa: E402
    build_complete_language_review_labels,
    build_language_corrected_base_labels,
    freeze_completed_base_labels,
    run_preliminary_human_audit,
)
from refusal_audit.response_validity.surrogate_bakeoff import (  # noqa: E402
    build_surrogate_bakeoff,
    build_stage_a_adjudication_packet,
    estimate_surrogate_bakeoff_cost,
    freeze_and_score_stage_a_adjudications,
    record_bakeoff_authorization,
    run_bakeoff_stage_a,
    score_surrogate_results,
)
from refusal_audit.response_validity.enrichment_design_v2 import (  # noqa: E402
    simulate_enrichment_design_v2,
)
from refusal_audit.response_validity.enrichment_wave_v2 import (  # noqa: E402
    assemble_enrichment_review_packet,
    freeze_enrichment_wave_v2,
)
from refusal_audit.response_validity.enrichment_checkpoint import (  # noqa: E402
    build_protected_surrogate_evaluation,
    estimate_protected_evaluation_cost,
    freeze_enrichment_checkpoint_200,
    record_protected_evaluation_authorization,
    run_protected_surrogate_evaluation,
    score_protected_surrogate_evaluation,
)
from refusal_audit.response_validity.refinement_access import (  # noqa: E402
    freeze_enrichment_storage_400,
    freeze_refinement_access_v1,
    freeze_refinement_access_v2,
    run_sealed_support_gate_v1,
    run_sealed_support_gate_v2,
)
from refusal_audit.response_validity.prompt_refinement import (  # noqa: E402
    build_partial_refusal_prompt_drafts,
)
from refusal_audit.response_validity.estimand_precision import (  # noqa: E402
    run_estimand_precision_audit,
)
from refusal_audit.response_validity.home_augmentation import (  # noqa: E402
    plan_home_augmentation,
)
from refusal_audit.response_validity.scalable_bakeoff import (  # noqa: E402
    build_scalable_bakeoff,
    estimate_scalable_bakeoff_cost,
    record_scalable_bakeoff_authorization,
    run_scalable_bakeoff,
    score_scalable_bakeoff,
    validate_response_validity_documentation,
)
from refusal_audit.response_validity.fold_nested_refinement import (  # noqa: E402
    build_fold_nested_refinement,
    estimate_fold_nested_refinement_cost,
    record_fold_nested_refinement_authorization,
    run_fold_nested_refinement,
    score_fold_nested_refinement,
)
from refusal_audit.response_validity.decomposed_review import (  # noqa: E402
    assemble_decomposed_review,
    build_harmonized_decomposed_gold,
    build_decomposed_review,
    rescore_decomposed_review,
)
from refusal_audit.response_validity.frontier_decomposed import (  # noqa: E402
    authorize_frontier_decomposed,
    estimate_frontier_decomposed,
    prepare_frontier_decomposed,
    record_frontier_bulk_agreement,
    run_frontier_decomposed,
)
from refusal_audit.response_validity.stage18_preliminary import (  # noqa: E402
    run_preliminary_stage18,
)
from refusal_audit.response_validity.luna_v22_test import (  # noqa: E402
    authorize_luna_v22_test,
    estimate_luna_v22_cost,
    prepare_luna_v22_test,
    run_luna_v22_test,
    score_luna_v22_test,
)
from refusal_audit.response_validity.luna_v23_repair import (  # noqa: E402
    authorize_luna_v23_repair,
    estimate_luna_v23_repair_cost,
    prepare_luna_v23_repair,
    run_luna_v23_repair,
    score_luna_v23_repair,
)
from refusal_audit.response_validity.external_audit_design import (  # noqa: E402
    simulate_external_audit_design,
)
from refusal_audit.response_validity.external_audit_freeze import (  # noqa: E402
    freeze_external_audit,
)
from refusal_audit.response_validity.external_audit_run import (  # noqa: E402
    authorize_external_audit,
    run_external_audit,
    summarize_external_audit,
)
from refusal_audit.response_validity.external_sol_reference_evaluation import (  # noqa: E402
    DEFAULT_OUTPUT_DIR as EXTERNAL_SOL_EVALUATION_DEFAULT_DIR,
    evaluate_external_sol_reference,
)
from refusal_audit.response_validity.external_disagreement_human_review import (  # noqa: E402
    DEFAULT_DIR as EXTERNAL_DISAGREEMENT_REVIEW_DEFAULT_DIR,
    summarize_external_disagreement_human_review,
)
from refusal_audit.response_validity.refusal_boundary_consistency import (  # noqa: E402
    DEFAULT_DIR as REFUSAL_BOUNDARY_REVIEW_DEFAULT_DIR,
    freeze_refusal_boundary_consistency,
    summarize_refusal_boundary_consistency,
)
from refusal_audit.response_validity.luna_v24_evaluation import (  # noqa: E402
    DEFAULT_DIR as LUNA_V24_EVALUATION_DEFAULT_DIR,
    authorize_luna_v24,
    estimate_luna_v24_cost,
    prepare_luna_v24_evaluation,
    run_luna_v24,
    score_luna_v24,
)
from refusal_audit.response_validity.sol_v24_evaluation import (  # noqa: E402
    DEFAULT_DIR as SOL_V24_EVALUATION_DEFAULT_DIR,
    authorize_sol_v24,
    estimate_sol_v24_cost,
    prepare_sol_v24_evaluation,
    run_sol_v24,
    score_sol_v24,
)
from refusal_audit.response_validity.model_bakeoff_v2 import (  # noqa: E402
    DEFAULT_DIR as MODEL_BAKEOFF_V2_DEFAULT_DIR,
    authorize_model_bakeoff_v2,
    estimate_model_bakeoff_v2_cost,
    prepare_model_bakeoff_v2,
    run_model_bakeoff_v2,
    score_model_bakeoff_v2,
)
from refusal_audit.response_validity.luna_v24_human_certification import (  # noqa: E402
    DEFAULT_DIR as LUNA_V24_HUMAN_CERT_DEFAULT_DIR,
    authorize_luna_v24_human_certification,
    authorize_fresh_sol_v24_reference,
    estimate_fresh_sol_v24_reference_cost,
    estimate_luna_v24_human_certification_cost,
    freeze_luna_v24_human_phase2,
    prepare_fresh_sol_v24_reference,
    score_fresh_sol_v24_reference,
    prepare_luna_v24_human_certification,
)
from refusal_audit.response_validity.wall_to_wall_v24 import (  # noqa: E402
    DEFAULT_DIR as WALL_TO_WALL_V24_DEFAULT_DIR,
    authorize_wall_to_wall_luna_v24,
    estimate_wall_to_wall_luna_v24_cost,
    prepare_wall_to_wall_luna_v24,
    run_wall_to_wall_luna_v24,
)
from refusal_audit.response_validity.wall_to_wall_repair_v24 import (  # noqa: E402
    DEFAULT_DIR as WALL_TO_WALL_REPAIR_V24_DEFAULT_DIR,
    authorize_wall_to_wall_repair_v24,
    assemble_final_wall_to_wall_v24,
    estimate_wall_to_wall_repair_v24_cost,
    prepare_wall_to_wall_repair_v24,
    run_wall_to_wall_repair_v24,
)
from refusal_audit.response_validity.external_human_validation import (  # noqa: E402
    DEFAULT_DIR as EXTERNAL_HUMAN_DEFAULT_DIR,
    SEED as EXTERNAL_HUMAN_SEED,
    assemble_external_human_review,
    assemble_external_sol_reference,
    freeze_external_human_phase2,
)
from refusal_audit.response_validity.stage_b_bakeoff import (  # noqa: E402
    build_stage_b_bakeoff,
    estimate_stage_b_cost,
    record_stage_b_authorization,
    run_stage_b,
    score_stage_b,
)
from refusal_audit.response_validity.translation_runner import (  # noqa: E402
    finalize_ceiling_guarded_loops,
    record_authorization,
    record_chunked_fallback_authorization,
    run_chunked_fallback,
    run_translations,
)


def parser() -> argparse.ArgumentParser:
    out = argparse.ArgumentParser(description=__doc__)
    commands = out.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory", help="hash the migration baseline")
    inventory.add_argument(
        "--spec", type=Path, default=ROOT / "config" / "response_validity_migration.csv"
    )
    inventory.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "archive" / "RESPONSE_VALIDITY_MIGRATION_MANIFEST.csv",
    )
    inventory.add_argument(
        "--metadata",
        type=Path,
        default=ROOT / "docs" / "archive" / "RESPONSE_VALIDITY_MIGRATION_BASELINE.json",
    )
    registry = commands.add_parser("validate-registry", help="validate active paths")
    registry.add_argument(
        "--registry", type=Path, default=ROOT / "pipeline" / "PIPELINE_REGISTRY.csv"
    )
    pilot = commands.add_parser(
        "pilot-design", help="build the local human-pilot probability sample"
    )
    pilot.add_argument(
        "--population", type=Path,
        default=ROOT / "annotations" / "response_validity_dsl_v1_1" / "wall_to_wall_features.parquet",
    )
    pilot.add_argument(
        "--pseudo-outcomes", type=Path,
        default=ROOT / "annotations" / "response_validity_dsl_v1_1" / "dsl_pseudo_outcomes.parquet",
    )
    pilot.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    pilot.add_argument("--budget", type=int, default=300)
    pilot.add_argument("--repeat-fraction", type=float, default=0.12)
    pilot.add_argument("--seed", type=int, default=20260819)
    pilot.add_argument(
        "--translation-prompt", type=Path,
        default=ROOT / "config" / "response_translation_prompt_v1.txt",
    )
    pilot.add_argument(
        "--overwrite", action="store_true",
        help="replace local pilot artifacts; prohibited after translation or coding begins",
    )
    review = commands.add_parser(
        "assemble-review", help="assemble a blinded human packet from completed translations"
    )
    review.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    review.add_argument("--translations", type=Path, required=True)
    volume = commands.add_parser(
        "translation-volume", help="estimate the frozen translation payload locally"
    )
    volume.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    authorize_translation = commands.add_parser(
        "authorize-translation", help="record an exact user-paid-translation authorization"
    )
    authorize_translation.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    authorize_translation.add_argument("--payload-sha", required=True)
    authorize_translation.add_argument("--prompt-sha", required=True)
    authorize_translation.add_argument("--model", required=True)
    authorize_translation.add_argument("--cost-ceiling", type=float, required=True)
    authorize_translation.add_argument("--confirm-user-authorization", action="store_true")
    translate = commands.add_parser(
        "translate", help="run the authorized, resumable literal-English translations"
    )
    translate.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    translate.add_argument(
        "--translation-prompt", type=Path,
        default=ROOT / "config" / "response_translation_prompt_v1.txt",
    )
    translate.add_argument("--workers", type=int, default=8)
    translate.add_argument("--cost-ceiling", type=float, required=True)
    translate.add_argument("--authorize-paid-translation", action="store_true")
    chunked = commands.add_parser(
        "translate-chunked", help="losslessly chunk one exhausted authorized translation"
    )
    chunked.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    chunked.add_argument(
        "--translation-prompt", type=Path,
        default=ROOT / "config" / "response_translation_prompt_v1.txt",
    )
    chunked.add_argument("--review-id", required=True)
    chunked.add_argument("--cost-ceiling", type=float, required=True)
    chunked.add_argument("--authorize-paid-translation", action="store_true")
    authorize_chunked = commands.add_parser(
        "authorize-translation-chunked",
        help="record exact user authorization for exhausted lossless chunk fallbacks",
    )
    authorize_chunked.add_argument("--output-dir", type=Path, required=True)
    authorize_chunked.add_argument(
        "--review-id", action="append", required=True,
        help="repeat once for every exactly authorized exhausted row",
    )
    authorize_chunked.add_argument("--cost-ceiling", type=float, required=True)
    authorize_chunked.add_argument("--confirm-user-authorization", action="store_true")
    finalize_loops = commands.add_parser(
        "finalize-ceiling-guarded-loops",
        help="locally mark unresolved deterministic loops unassessable after the authorized cap",
    )
    finalize_loops.add_argument("--output-dir", type=Path, required=True)
    finalize_loops.add_argument("--cost-ceiling", type=float, required=True)
    volume.add_argument(
        "--translation-prompt", type=Path,
        default=ROOT / "config" / "response_translation_prompt_v1.txt",
    )
    freeze = commands.add_parser(
        "freeze-human-base",
        help="freeze the completed 300 non-repeat human judgments without reading repeats",
    )
    freeze.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
        help="frozen pilot directory containing the live append-only label log",
    )
    audit = commands.add_parser(
        "audit-human-base",
        help="run the provisional design-weighted one-coder audit without repeat records",
    )
    audit.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
        help="frozen pilot directory containing the immutable base freeze",
    )
    correct_language = commands.add_parser(
        "apply-human-language-review",
        help="apply coder-confirmed language amendments and rebuild the provisional audit",
    )
    correct_language.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
        help="frozen human-pilot directory containing the v1 base and amendment log",
    )
    complete_language = commands.add_parser(
        "freeze-complete-language-review",
        help="materialize explicit language fidelity for the coder-reviewed 300-row universe",
    )
    complete_language.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    bakeoff = commands.add_parser(
        "build-surrogate-bakeoff",
        help="freeze prompt-grouped holdout and unpaid model-neutral bake-off requests",
    )
    bakeoff.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    bakeoff.add_argument("--seed", type=int, default=20260821)
    score_bakeoff = commands.add_parser(
        "score-surrogate-bakeoff",
        help="score externally produced surrogate results against the frozen holdout",
    )
    score_bakeoff.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2" / "surrogate_bakeoff_v1",
    )
    score_bakeoff.add_argument("--results", type=Path, required=True)
    estimate_bakeoff = commands.add_parser(
        "estimate-surrogate-bakeoff-cost",
        help="apply the frozen local price snapshot to bake-off token volume",
    )
    estimate_bakeoff.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2" / "surrogate_bakeoff_v1",
    )
    authorize_bakeoff = commands.add_parser(
        "authorize-surrogate-bakeoff",
        help="record the exact user-authorized Stage A payload, model, and ceiling",
    )
    authorize_bakeoff.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2" / "surrogate_bakeoff_v1",
    )
    authorize_bakeoff.add_argument("--payload-sha", required=True)
    authorize_bakeoff.add_argument("--model", required=True)
    authorize_bakeoff.add_argument("--cost-ceiling", type=float, required=True)
    authorize_bakeoff.add_argument("--confirm-user-authorization", action="store_true")
    run_bakeoff = commands.add_parser(
        "run-surrogate-bakeoff-stage-a",
        help="run the authorized resumable 420-request GPT-5.6 Luna experiment",
    )
    run_bakeoff.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2" / "surrogate_bakeoff_v1",
    )
    run_bakeoff.add_argument("--workers", type=int, default=8)
    run_bakeoff.add_argument("--cost-ceiling", type=float, required=True)
    run_bakeoff.add_argument("--authorize-paid-run", action="store_true")
    adjudication = commands.add_parser(
        "build-stage-a-adjudication",
        help="freeze the 18 Stage A disagreement rows for blinded Streamlit relabeling",
    )
    adjudication.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    freeze_adjudication = commands.add_parser(
        "freeze-stage-a-adjudication",
        help="freeze 18 completed blinded judgments and rescore all Stage A configurations",
    )
    freeze_adjudication.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    stage_b_build = commands.add_parser(
        "build-surrogate-bakeoff-stage-b",
        help="freeze the unpaid 504-request Gemini/Claude Stage B payload",
    )
    stage_b_build.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    stage_b_cost = commands.add_parser(
        "estimate-surrogate-bakeoff-stage-b-cost",
        help="estimate the frozen Stage B payload from its dated price snapshot",
    )
    stage_b_cost.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "surrogate_bakeoff_stage_b_v1"),
    )
    stage_b_authorize = commands.add_parser(
        "authorize-surrogate-bakeoff-stage-b",
        help="record an exact user authorization for the frozen Stage B payload",
    )
    stage_b_authorize.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "surrogate_bakeoff_stage_b_v1"),
    )
    stage_b_authorize.add_argument("--payload-sha", required=True)
    stage_b_authorize.add_argument("--cost-ceiling", type=float, required=True)
    stage_b_authorize.add_argument("--confirm-user-authorization", action="store_true")
    stage_b_run = commands.add_parser(
        "run-surrogate-bakeoff-stage-b",
        help="run the exact authorized 504-request Stage B experiment resumably",
    )
    stage_b_run.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "surrogate_bakeoff_stage_b_v1"),
    )
    stage_b_run.add_argument("--workers", type=int, default=8)
    stage_b_run.add_argument("--cost-ceiling", type=float, required=True)
    stage_b_run.add_argument("--authorize-paid-run", action="store_true")
    stage_b_score = commands.add_parser(
        "score-surrogate-bakeoff-stage-b",
        help="score completed Luna/Gemini/Claude results against both human label versions",
    )
    stage_b_score.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    enrich = commands.add_parser(
        "simulate-human-enrichment",
        help="compare 150/250/400/600-row v2 enrichment workloads without drawing a sample",
    )
    enrich.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
        help="frozen human-pilot directory; repeat and live-label files are not read",
    )
    enrich.add_argument("--seed", type=int, default=20260823)
    enrich.add_argument("--simulations", type=int, default=10_000)
    freeze_enrich = commands.add_parser(
        "freeze-human-enrichment-wave",
        help="draw and hash the approved 400-row v2 wave without a provider call",
    )
    freeze_enrich.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
        help="frozen human-pilot directory",
    )
    freeze_enrich.add_argument("--routing-seed", type=int, default=20260823)
    freeze_enrich.add_argument("--draw-seed", type=int, default=20260824)
    freeze_enrich.add_argument("--confirm-design-approval", action="store_true")
    assemble_enrich = commands.add_parser(
        "assemble-human-enrichment-review",
        help="assemble the blinded 400-row queue from completed translations",
    )
    assemble_enrich.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400"),
    )
    assemble_enrich.add_argument("--translations", type=Path, required=True)
    checkpoint = commands.add_parser(
        "freeze-enrichment-checkpoint-200",
        help="freeze completed enrichment review orders 1--200 without changing the live log",
    )
    checkpoint.add_argument(
        "--wave-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400"),
    )
    protected = commands.add_parser(
        "build-protected-surrogate-evaluation",
        help="build the unpaid 232-request payload over the protected 116-row evaluation",
    )
    protected.add_argument(
        "--wave-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400"),
    )
    protected_cost = commands.add_parser(
        "estimate-protected-surrogate-evaluation-cost",
        help="price the exact frozen protected-evaluation payload locally",
    )
    protected_cost.add_argument(
        "--wave-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400"),
    )
    protected_authorize = commands.add_parser(
        "authorize-protected-surrogate-evaluation",
        help="record the exact user authorization for the frozen 232-request evaluation",
    )
    protected_authorize.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400" / "checkpoint_200_v1"
                 / "surrogate_evaluation_v1"),
    )
    protected_authorize.add_argument("--payload-sha", required=True)
    protected_authorize.add_argument("--model", required=True)
    protected_authorize.add_argument("--provider", required=True)
    protected_authorize.add_argument("--cost-ceiling", type=float, required=True)
    protected_authorize.add_argument("--confirm-user-authorization", action="store_true")
    protected_run = commands.add_parser(
        "run-protected-surrogate-evaluation",
        help="run the exact authorized 232-request evaluation resumably",
    )
    protected_run.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400" / "checkpoint_200_v1"
                 / "surrogate_evaluation_v1"),
    )
    protected_run.add_argument("--workers", type=int, default=8)
    protected_run.add_argument("--cost-ceiling", type=float, required=True)
    protected_run.add_argument("--authorize-paid-run", action="store_true")
    protected_score = commands.add_parser(
        "score-protected-surrogate-evaluation",
        help="score the completed protected comparison against its frozen human labels",
    )
    protected_score.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400" / "checkpoint_200_v1"
                 / "surrogate_evaluation_v1"),
    )
    refinement_access = commands.add_parser(
        "freeze-surrogate-refinement-access",
        help="emit development-only labels and hash-commit the sealed evaluation rows",
    )
    refinement_access.add_argument(
        "--wave-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400"),
    )
    refinement_support = commands.add_parser(
        "run-surrogate-refinement-support-gate",
        help="return only predeclared pass/fail support flags for the sealed evaluation arm",
    )
    refinement_support.add_argument(
        "--wave-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400"),
    )
    storage_400 = commands.add_parser(
        "freeze-enrichment-storage-400",
        help="freeze all 400 completed human labels without exposing either split",
    )
    storage_400.add_argument(
        "--wave-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400"),
    )
    refinement_access_v2 = commands.add_parser(
        "freeze-surrogate-refinement-access-v2",
        help="emit all development labels and hash-commit the enlarged evaluation reserve",
    )
    refinement_access_v2.add_argument(
        "--wave-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400"),
    )
    refinement_support_v2 = commands.add_parser(
        "run-surrogate-refinement-support-gate-v2",
        help="return only pass/fail support flags for the enlarged evaluation reserve",
    )
    refinement_support_v2.add_argument(
        "--wave-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400"),
    )
    prompt_refinement = commands.add_parser(
        "build-partial-refusal-prompt-drafts",
        help="build development-only component-first prompt drafts without provider requests",
    )
    prompt_refinement.add_argument(
        "--wave-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "enrichment_wave_v2_400"),
    )
    precision_audit = commands.add_parser(
        "audit-human-estimand-precision",
        help="audit every refusal estimand using the frozen 300-row probability sample",
    )
    precision_audit.add_argument(
        "--pilot-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    precision_audit.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "estimand_precision_audit_v1"),
    )
    home_plan = commands.add_parser(
        "plan-home-human-augmentation",
        help="size the home-focused human sample without drawing any row IDs",
    )
    home_plan.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "home_augmentation_planning_v1"),
    )
    scalable_build = commands.add_parser(
        "build-scalable-annotation-bakeoff",
        help="freeze the 700-label issue-grouped translation-ablation payload",
    )
    scalable_build.add_argument(
        "--pilot-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    scalable_build.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "scalable_annotation_bakeoff_v1"),
    )
    scalable_build.add_argument("--seed", type=int, default=20260825)
    scalable_cost = commands.add_parser(
        "estimate-scalable-annotation-bakeoff-cost",
        help="price the exact frozen 700-label provider payload locally",
    )
    scalable_cost.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "scalable_annotation_bakeoff_v1"),
    )
    scalable_authorize = commands.add_parser(
        "authorize-scalable-annotation-bakeoff",
        help="record exact user authorization for the frozen provider payload",
    )
    scalable_authorize.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "scalable_annotation_bakeoff_v1"),
    )
    scalable_authorize.add_argument("--payload-sha", required=True)
    scalable_authorize.add_argument("--cost-ceiling", type=float, required=True)
    scalable_authorize.add_argument("--confirm-user-authorization", action="store_true")
    scalable_run = commands.add_parser(
        "run-scalable-annotation-bakeoff",
        help="run the exact authorized 8,400-request bake-off resumably",
    )
    scalable_run.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "scalable_annotation_bakeoff_v1"),
    )
    scalable_run.add_argument("--workers", type=int, default=8)
    scalable_run.add_argument("--cost-ceiling", type=float, required=True)
    scalable_run.add_argument("--authorize-paid-run", action="store_true")
    scalable_score = commands.add_parser(
        "score-scalable-annotation-bakeoff",
        help="score completed out-of-fold predictions and apply frozen gates",
    )
    scalable_score.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "scalable_annotation_bakeoff_v1"),
    )
    commands.add_parser(
        "validate-response-validity-docs",
        help="check current technical-document status against frozen manifests",
    )
    nested_build = commands.add_parser(
        "build-fold-nested-refusal-refinement",
        help="freeze the error-targeted 700-label Luna refinement without provider calls",
    )
    nested_build.add_argument(
        "--pilot-dir", type=Path,
        default=ROOT / "annotations" / "response_validity_human_v2",
    )
    nested_build.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "fold_nested_refusal_refinement_v2"),
    )
    nested_cost = commands.add_parser(
        "estimate-fold-nested-refusal-refinement-cost",
        help="price the exact frozen refinement payload locally",
    )
    nested_cost.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "fold_nested_refusal_refinement_v2"),
    )
    nested_authorize = commands.add_parser(
        "authorize-fold-nested-refusal-refinement",
        help="record exact user authorization for the frozen refinement payload",
    )
    nested_authorize.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "fold_nested_refusal_refinement_v2"),
    )
    nested_authorize.add_argument("--payload-sha", required=True)
    nested_authorize.add_argument("--cost-ceiling", type=float, required=True)
    nested_authorize.add_argument("--confirm-user-authorization", action="store_true")
    nested_run = commands.add_parser(
        "run-fold-nested-refusal-refinement",
        help="run the exact authorized refinement payload resumably",
    )
    nested_run.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "fold_nested_refusal_refinement_v2"),
    )
    nested_run.add_argument("--workers", type=int, default=8)
    nested_run.add_argument("--cost-ceiling", type=float, required=True)
    nested_run.add_argument("--authorize-paid-run", action="store_true")
    nested_score = commands.add_parser(
        "score-fold-nested-refusal-refinement",
        help="score the completed refinement with the pre-run fold thresholds",
    )
    nested_score.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "fold_nested_refusal_refinement_v2"),
    )
    decomposed_build = commands.add_parser(
        "build-decomposed-validity-review",
        help="freeze the blinded v2.2 refusal-boundary review without provider calls",
    )
    decomposed_build.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "decomposed_review_v2_2"),
    )
    decomposed_assemble = commands.add_parser(
        "assemble-decomposed-validity-review",
        help="validate and assemble the completed v2.2 human review locally",
    )
    decomposed_assemble.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "decomposed_review_v2_2"),
    )
    decomposed_rescore = commands.add_parser(
        "rescore-decomposed-validity-review",
        help="rescore immutable student predictions after the v2.2 review is complete",
    )
    decomposed_rescore.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "decomposed_review_v2_2"),
    )
    harmonize = commands.add_parser(
        "harmonize-decomposed-validity-gold",
        help="build the 700-row v2.2 gold table and unresolved review packet locally",
    )
    harmonize.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "decomposed_review_v2_2"),
    )
    preliminary_stage18 = commands.add_parser(
        "run-preliminary-stage18",
        help="estimate direct probability-weighted v2.2 quantities locally",
    )
    preliminary_stage18.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "stage18_preliminary_v2_2"),
    )
    luna_v22_build = commands.add_parser(
        "prepare-luna-v22-internal-test",
        help="freeze the 1,400-request exact-v2.2 Luna test without a provider call",
    )
    luna_v22_build.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "luna_exact_v2_2_internal_test_v1"),
    )
    luna_v22_cost = commands.add_parser(
        "estimate-luna-v22-internal-test-cost",
        help="price the exact frozen Luna v2.2 payload locally",
    )
    luna_v22_cost.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "luna_exact_v2_2_internal_test_v1"),
    )
    luna_v22_authorize = commands.add_parser(
        "authorize-luna-v22-internal-test",
        help="record exact user authorization for the Luna v2.2 payload",
    )
    luna_v22_authorize.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "luna_exact_v2_2_internal_test_v1"),
    )
    luna_v22_authorize.add_argument("--payload-sha", required=True)
    luna_v22_authorize.add_argument("--cost-ceiling", type=float, required=True)
    luna_v22_authorize.add_argument("--confirm-user-authorization", action="store_true")
    luna_v22_run = commands.add_parser(
        "run-luna-v22-internal-test",
        help="run the exact authorized Luna v2.2 payload resumably",
    )
    luna_v22_run.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "luna_exact_v2_2_internal_test_v1"),
    )
    luna_v22_run.add_argument("--workers", type=int, default=8)
    luna_v22_run.add_argument("--cost-ceiling", type=float, required=True)
    luna_v22_run.add_argument("--authorize-paid-run", action="store_true")
    luna_v22_score = commands.add_parser(
        "score-luna-v22-internal-test",
        help="score the complete exact-v2.2 Luna run against harmonized gold",
    )
    luna_v22_score.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "luna_exact_v2_2_internal_test_v1"),
    )
    luna_v23_build = commands.add_parser(
        "prepare-luna-v23-repair-test",
        help="freeze paired v2.3 requests for all unique v2.2 failures",
    )
    luna_v23_build.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "luna_v2_3_repair_test_v1"),
    )
    luna_v23_cost = commands.add_parser(
        "estimate-luna-v23-repair-test-cost",
        help="price the exact frozen v2.3 repair payload locally",
    )
    luna_v23_cost.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "luna_v2_3_repair_test_v1"),
    )
    luna_v23_authorize = commands.add_parser(
        "authorize-luna-v23-repair-test",
        help="record exact user authorization for the v2.3 repair payload",
    )
    luna_v23_authorize.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "luna_v2_3_repair_test_v1"),
    )
    luna_v23_authorize.add_argument("--payload-sha", required=True)
    luna_v23_authorize.add_argument("--cost-ceiling", type=float, required=True)
    luna_v23_authorize.add_argument("--confirm-user-authorization", action="store_true")
    luna_v23_run = commands.add_parser(
        "run-luna-v23-repair-test",
        help="run the exact authorized v2.3 repair payload resumably",
    )
    luna_v23_run.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "luna_v2_3_repair_test_v1"),
    )
    luna_v23_run.add_argument("--workers", type=int, default=8)
    luna_v23_run.add_argument("--cost-ceiling", type=float, required=True)
    luna_v23_run.add_argument("--authorize-paid-run", action="store_true")
    luna_v23_score = commands.add_parser(
        "score-luna-v23-repair-test",
        help="score repair rows and the provenance-explicit patched all-700 diagnostic",
    )
    luna_v23_score.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "luna_v2_3_repair_test_v1"),
    )
    external_plan = commands.add_parser(
        "plan-external-validity-audit",
        help="compare fresh-audit designs without selecting response IDs",
    )
    external_plan.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "external_audit_planning_v1"),
    )
    external_plan.add_argument("--seed", type=int, default=20260827)
    external_plan.add_argument("--simulations", type=int, default=10_000)
    external_freeze = commands.add_parser(
        "freeze-external-validity-audit",
        help="draw the approved external sample and freeze unpaid blinded payloads",
    )
    external_freeze.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "external_audit_v1"),
    )
    external_authorize = commands.add_parser(
        "authorize-external-validity-audit",
        help="bind user authorization to both external payload hashes and ceiling",
    )
    external_authorize.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "external_audit_v1"),
    )
    external_authorize.add_argument("--luna-payload-sha", required=True)
    external_authorize.add_argument("--sol-payload-sha", required=True)
    external_authorize.add_argument("--cost-ceiling", type=float, required=True)
    external_authorize.add_argument(
        "--confirm-user-authorization", action="store_true"
    )
    external_run = commands.add_parser(
        "run-external-validity-audit",
        help="run the exact authorized paired external payload resumably",
    )
    external_run.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "external_audit_v1"),
    )
    external_run.add_argument("--workers", type=int, default=12)
    external_run.add_argument("--cost-ceiling", type=float, required=True)
    external_run.add_argument("--authorize-paid-run", action="store_true")
    external_summary = commands.add_parser(
        "summarize-external-validity-audit",
        help="validate and pair completed external labels for phase-two planning",
    )
    external_summary.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "external_audit_v1"),
    )
    external_sol_score = commands.add_parser(
        "score-external-sol-reference",
        help=(
            "calculate design-weighted Luna performance using Sol as a "
            "machine reference; local only and not human certification"
        ),
    )
    external_sol_score.add_argument(
        "--output-dir", type=Path,
        default=ROOT / EXTERNAL_SOL_EVALUATION_DEFAULT_DIR,
    )
    external_disagreement_summary = commands.add_parser(
        "summarize-external-refusal-disagreement-review",
        help="validate and summarize the completed visible-label nine-case review",
    )
    external_disagreement_summary.add_argument(
        "--output-dir", type=Path,
        default=ROOT / EXTERNAL_DISAGREEMENT_REVIEW_DEFAULT_DIR,
    )
    boundary_freeze = commands.add_parser(
        "freeze-refusal-boundary-consistency-review",
        help="freeze the local 24-case audit and 20-case new review queue",
    )
    boundary_freeze.add_argument(
        "--output-dir", type=Path,
        default=ROOT / REFUSAL_BOUNDARY_REVIEW_DEFAULT_DIR,
    )
    boundary_summary = commands.add_parser(
        "summarize-refusal-boundary-consistency-review",
        help="assemble the completed targeted boundary review locally",
    )
    boundary_summary.add_argument(
        "--output-dir", type=Path,
        default=ROOT / REFUSAL_BOUNDARY_REVIEW_DEFAULT_DIR,
    )
    v24_prepare = commands.add_parser(
        "prepare-luna-v2-4-evaluation",
        help="freeze the 1,197-request v2.4 Luna evaluation locally",
    )
    v24_prepare.add_argument(
        "--output-dir", type=Path,
        default=ROOT / LUNA_V24_EVALUATION_DEFAULT_DIR,
    )
    v24_cost = commands.add_parser(
        "estimate-luna-v2-4-evaluation-cost",
        help="price the exact frozen v2.4 payload locally",
    )
    v24_cost.add_argument(
        "--output-dir", type=Path,
        default=ROOT / LUNA_V24_EVALUATION_DEFAULT_DIR,
    )
    v24_authorize = commands.add_parser(
        "authorize-luna-v2-4-evaluation",
        help="record exact user authorization for the frozen v2.4 payload",
    )
    v24_authorize.add_argument(
        "--output-dir", type=Path,
        default=ROOT / LUNA_V24_EVALUATION_DEFAULT_DIR,
    )
    v24_authorize.add_argument("--payload-sha", required=True)
    v24_authorize.add_argument("--cost-ceiling", type=float, required=True)
    v24_authorize.add_argument("--confirm-user-authorization", action="store_true")
    v24_run = commands.add_parser(
        "run-luna-v2-4-evaluation",
        help="run the exact authorized v2.4 payload resumably",
    )
    v24_run.add_argument(
        "--output-dir", type=Path,
        default=ROOT / LUNA_V24_EVALUATION_DEFAULT_DIR,
    )
    v24_run.add_argument("--workers", type=int, default=12)
    v24_run.add_argument("--cost-ceiling", type=float, required=True)
    v24_run.add_argument("--authorize-paid-run", action="store_true")
    v24_score = commands.add_parser(
        "score-luna-v2-4-evaluation",
        help="score protected Sol agreement and separate boundary diagnostics",
    )
    v24_score.add_argument(
        "--output-dir", type=Path,
        default=ROOT / LUNA_V24_EVALUATION_DEFAULT_DIR,
    )
    sol24_prepare = commands.add_parser(
        "prepare-sol-v2-4-evaluation",
        help="freeze the same-codebook 1,197-request Sol payload locally",
    )
    sol24_prepare.add_argument(
        "--output-dir", type=Path,
        default=ROOT / SOL_V24_EVALUATION_DEFAULT_DIR,
    )
    sol24_cost = commands.add_parser(
        "estimate-sol-v2-4-evaluation-cost",
        help="price the exact frozen Sol v2.4 payload locally",
    )
    sol24_cost.add_argument(
        "--output-dir", type=Path,
        default=ROOT / SOL_V24_EVALUATION_DEFAULT_DIR,
    )
    sol24_authorize = commands.add_parser(
        "authorize-sol-v2-4-evaluation",
        help="record exact user authorization for the Sol v2.4 payload",
    )
    sol24_authorize.add_argument(
        "--output-dir", type=Path,
        default=ROOT / SOL_V24_EVALUATION_DEFAULT_DIR,
    )
    sol24_authorize.add_argument("--payload-sha", required=True)
    sol24_authorize.add_argument("--cost-ceiling", type=float, required=True)
    sol24_authorize.add_argument("--confirm-user-authorization", action="store_true")
    sol24_run = commands.add_parser(
        "run-sol-v2-4-evaluation",
        help="run the exact authorized Sol v2.4 payload resumably",
    )
    sol24_run.add_argument(
        "--output-dir", type=Path,
        default=ROOT / SOL_V24_EVALUATION_DEFAULT_DIR,
    )
    sol24_run.add_argument("--workers", type=int, default=12)
    sol24_run.add_argument("--cost-ceiling", type=float, required=True)
    sol24_run.add_argument("--authorize-paid-run", action="store_true")
    sol24_score = commands.add_parser(
        "score-sol-v2-4-evaluation",
        help="score Luna against the same-codebook Sol machine reference",
    )
    sol24_score.add_argument(
        "--output-dir", type=Path,
        default=ROOT / SOL_V24_EVALUATION_DEFAULT_DIR,
    )
    model_bakeoff_prepare = commands.add_parser(
        "prepare-model-bakeoff-v2",
        help="freeze the API-only v2.4 model bake-off locally",
    )
    model_bakeoff_prepare.add_argument(
        "--output-dir", type=Path,
        default=ROOT / MODEL_BAKEOFF_V2_DEFAULT_DIR,
    )
    model_bakeoff_cost = commands.add_parser(
        "estimate-model-bakeoff-v2-cost",
        help="price the exact maximum bake-off payload locally",
    )
    model_bakeoff_cost.add_argument(
        "--output-dir", type=Path,
        default=ROOT / MODEL_BAKEOFF_V2_DEFAULT_DIR,
    )
    model_bakeoff_authorize = commands.add_parser(
        "authorize-model-bakeoff-v2",
        help="record exact user authorization for the frozen bake-off",
    )
    model_bakeoff_authorize.add_argument(
        "--output-dir", type=Path,
        default=ROOT / MODEL_BAKEOFF_V2_DEFAULT_DIR,
    )
    model_bakeoff_authorize.add_argument("--payload-sha", required=True)
    model_bakeoff_authorize.add_argument(
        "--cost-ceiling", type=float, required=True
    )
    model_bakeoff_authorize.add_argument(
        "--confirm-user-authorization", action="store_true"
    )
    model_bakeoff_run = commands.add_parser(
        "run-model-bakeoff-v2",
        help="run the authorized preflight-gated bake-off resumably",
    )
    model_bakeoff_run.add_argument(
        "--output-dir", type=Path,
        default=ROOT / MODEL_BAKEOFF_V2_DEFAULT_DIR,
    )
    model_bakeoff_run.add_argument("--workers", type=int, default=12)
    model_bakeoff_run.add_argument("--cost-ceiling", type=float, required=True)
    model_bakeoff_run.add_argument("--authorize-paid-run", action="store_true")
    model_bakeoff_score = commands.add_parser(
        "score-model-bakeoff-v2",
        help="score surviving candidates against the Sol v2.4 machine reference",
    )
    model_bakeoff_score.add_argument(
        "--output-dir", type=Path,
        default=ROOT / MODEL_BAKEOFF_V2_DEFAULT_DIR,
    )
    human_cert_prepare = commands.add_parser(
        "prepare-luna-v2-4-human-certification",
        help="freeze the fresh probability sample and unpaid Luna payload",
    )
    human_cert_prepare.add_argument(
        "--output-dir", type=Path,
        default=ROOT / LUNA_V24_HUMAN_CERT_DEFAULT_DIR,
    )
    human_cert_cost = commands.add_parser(
        "estimate-luna-v2-4-human-certification-cost",
        help="price the exact fresh certification payload locally",
    )
    human_cert_cost.add_argument(
        "--output-dir", type=Path,
        default=ROOT / LUNA_V24_HUMAN_CERT_DEFAULT_DIR,
    )
    human_cert_authorize = commands.add_parser(
        "authorize-luna-v2-4-human-certification",
        help="record exact authorization for the fresh certification payload",
    )
    human_cert_authorize.add_argument(
        "--output-dir", type=Path,
        default=ROOT / LUNA_V24_HUMAN_CERT_DEFAULT_DIR,
    )
    human_cert_authorize.add_argument("--payload-sha", required=True)
    human_cert_authorize.add_argument("--cost-ceiling", type=float, required=True)
    human_cert_authorize.add_argument(
        "--confirm-user-authorization", action="store_true"
    )
    human_cert_run = commands.add_parser(
        "run-luna-v2-4-human-certification",
        help="run the authorized fresh Luna certification payload resumably",
    )
    human_cert_run.add_argument(
        "--output-dir", type=Path,
        default=ROOT / LUNA_V24_HUMAN_CERT_DEFAULT_DIR,
    )
    human_cert_run.add_argument("--workers", type=int, default=12)
    human_cert_run.add_argument("--cost-ceiling", type=float, required=True)
    human_cert_run.add_argument("--authorize-paid-run", action="store_true")
    human_cert_phase2 = commands.add_parser(
        "freeze-luna-v2-4-human-certification-phase2",
        help="freeze the probability-sampled human workload and translation payload",
    )
    human_cert_phase2.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations/response_validity_human_v2/"
                 "luna_v2_4_human_certification_v1/human_phase2"),
    )
    fresh_sol_prepare = commands.add_parser(
        "prepare-fresh-sol-v2-4-reference",
        help="freeze Sol on all fresh Phase 1 cases without a provider call",
    )
    fresh_sol_prepare.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations/response_validity_human_v2/"
                 "luna_v2_4_human_certification_v1/sol_reference"),
    )
    fresh_sol_cost = commands.add_parser(
        "estimate-fresh-sol-v2-4-reference-cost",
        help="price the exact fresh Sol reference payload locally",
    )
    fresh_sol_cost.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations/response_validity_human_v2/"
                 "luna_v2_4_human_certification_v1/sol_reference"),
    )
    fresh_sol_authorize = commands.add_parser(
        "authorize-fresh-sol-v2-4-reference",
        help="record exact authorization for the frozen fresh Sol reference",
    )
    fresh_sol_authorize.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations/response_validity_human_v2/"
                 "luna_v2_4_human_certification_v1/sol_reference"),
    )
    fresh_sol_authorize.add_argument("--payload-sha", required=True)
    fresh_sol_authorize.add_argument("--cost-ceiling", type=float, required=True)
    fresh_sol_authorize.add_argument(
        "--confirm-user-authorization", action="store_true"
    )
    fresh_sol_run = commands.add_parser(
        "run-fresh-sol-v2-4-reference",
        help="run the authorized fresh Sol reference payload resumably",
    )
    fresh_sol_run.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations/response_validity_human_v2/"
                 "luna_v2_4_human_certification_v1/sol_reference"),
    )
    fresh_sol_run.add_argument("--workers", type=int, default=12)
    fresh_sol_run.add_argument("--cost-ceiling", type=float, required=True)
    fresh_sol_run.add_argument("--authorize-paid-run", action="store_true")
    fresh_sol_score = commands.add_parser(
        "score-fresh-sol-v2-4-reference",
        help="score Luna against Sol using the fresh Phase 1 weights",
    )
    fresh_sol_score.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations/response_validity_human_v2/"
                 "luna_v2_4_human_certification_v1/sol_reference"),
    )
    fresh_sol_score.add_argument("--bootstrap-draws", type=int, default=2000)
    wall_v24_prepare = commands.add_parser(
        "prepare-wall-to-wall-luna-v2-4",
        help="freeze the compact unpaid Luna v2.4 full-corpus request index",
    )
    wall_v24_prepare.add_argument(
        "--output-dir", type=Path, default=ROOT / WALL_TO_WALL_V24_DEFAULT_DIR,
    )
    wall_v24_cost = commands.add_parser(
        "estimate-wall-to-wall-luna-v2-4-cost",
        help="price the frozen full-corpus Luna v2.4 stage locally",
    )
    wall_v24_cost.add_argument(
        "--output-dir", type=Path, default=ROOT / WALL_TO_WALL_V24_DEFAULT_DIR,
    )
    wall_v24_authorize = commands.add_parser(
        "authorize-wall-to-wall-luna-v2-4",
        help="record exact authorization for the frozen full-corpus stage",
    )
    wall_v24_authorize.add_argument(
        "--output-dir", type=Path, default=ROOT / WALL_TO_WALL_V24_DEFAULT_DIR,
    )
    wall_v24_authorize.add_argument("--payload-sha", required=True)
    wall_v24_authorize.add_argument("--cost-ceiling", type=float, required=True)
    wall_v24_authorize.add_argument(
        "--confirm-user-authorization", action="store_true"
    )
    wall_v24_run = commands.add_parser(
        "run-wall-to-wall-luna-v2-4",
        help="run the authorized full-corpus Luna v2.4 stage resumably",
    )
    wall_v24_run.add_argument(
        "--output-dir", type=Path, default=ROOT / WALL_TO_WALL_V24_DEFAULT_DIR,
    )
    wall_v24_run.add_argument("--workers", type=int, default=24)
    wall_v24_run.add_argument("--cost-ceiling", type=float, required=True)
    wall_v24_run.add_argument("--authorize-paid-run", action="store_true")
    wall_repair_prepare = commands.add_parser(
        "prepare-wall-to-wall-luna-v2-4-repair",
        help="freeze the unpaid 129-case Luna v2.4 schema-repair payload",
    )
    wall_repair_prepare.add_argument(
        "--output-dir", type=Path, default=ROOT / WALL_TO_WALL_REPAIR_V24_DEFAULT_DIR,
    )
    wall_repair_cost = commands.add_parser(
        "estimate-wall-to-wall-luna-v2-4-repair-cost",
        help="price the frozen adaptive Luna v2.4 repair protocol locally",
    )
    wall_repair_cost.add_argument(
        "--output-dir", type=Path, default=ROOT / WALL_TO_WALL_REPAIR_V24_DEFAULT_DIR,
    )
    wall_repair_authorize = commands.add_parser(
        "authorize-wall-to-wall-luna-v2-4-repair",
        help="record exact authorization for the frozen schema-repair protocol",
    )
    wall_repair_authorize.add_argument(
        "--output-dir", type=Path, default=ROOT / WALL_TO_WALL_REPAIR_V24_DEFAULT_DIR,
    )
    wall_repair_authorize.add_argument("--payload-sha", required=True)
    wall_repair_authorize.add_argument("--protocol-sha", required=True)
    wall_repair_authorize.add_argument("--cost-ceiling", type=float, required=True)
    wall_repair_authorize.add_argument(
        "--confirm-user-authorization", action="store_true"
    )
    wall_repair_run = commands.add_parser(
        "run-wall-to-wall-luna-v2-4-repair",
        help="run the authorized adaptive Luna v2.4 schema repair resumably",
    )
    wall_repair_run.add_argument(
        "--output-dir", type=Path, default=ROOT / WALL_TO_WALL_REPAIR_V24_DEFAULT_DIR,
    )
    wall_repair_run.add_argument("--workers", type=int, default=12)
    wall_repair_run.add_argument("--cost-ceiling", type=float, required=True)
    wall_repair_run.add_argument("--authorize-paid-run", action="store_true")
    wall_repair_assemble = commands.add_parser(
        "assemble-final-wall-to-wall-luna-v2-4",
        help="assemble one provenance-explicit final v2.4 label per corpus response",
    )
    wall_repair_assemble.add_argument(
        "--output-dir", type=Path, default=ROOT / WALL_TO_WALL_REPAIR_V24_DEFAULT_DIR,
    )
    external_human_freeze = commands.add_parser(
        "freeze-external-human-phase2",
        help=(
            "realize the approved phase-two probability sample and freeze its "
            "unpaid translation payload"
        ),
    )
    external_human_freeze.add_argument(
        "--output-dir", type=Path, default=ROOT / EXTERNAL_HUMAN_DEFAULT_DIR,
    )
    external_human_freeze.add_argument(
        "--seed", type=int, default=EXTERNAL_HUMAN_SEED,
    )
    external_human_assemble = commands.add_parser(
        "assemble-external-human-review",
        help="assemble the blinded v2.3 review packet after translations finish",
    )
    external_human_assemble.add_argument(
        "--output-dir", type=Path, default=ROOT / EXTERNAL_HUMAN_DEFAULT_DIR,
    )
    external_sol_assemble = commands.add_parser(
        "assemble-external-sol-reference",
        help="extract the already-completed Sol v2.3 labels for the 458 review rows",
    )
    external_sol_assemble.add_argument(
        "--output-dir", type=Path, default=ROOT / EXTERNAL_HUMAN_DEFAULT_DIR,
    )
    frontier_prepare = commands.add_parser(
        "prepare-frontier-decomposed-annotations",
        help="freeze the blinded 158-request GPT-5.6 Sol payload locally",
    )
    frontier_prepare.add_argument(
        "--run-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "decomposed_review_v2_2" / "frontier_sol_v2_2"),
    )
    frontier_estimate = commands.add_parser(
        "estimate-frontier-decomposed-cost",
        help="price the exact frozen Sol payload without a provider call",
    )
    frontier_estimate.add_argument(
        "--run-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "decomposed_review_v2_2" / "frontier_sol_v2_2"),
    )
    frontier_authorize = commands.add_parser(
        "authorize-frontier-decomposed-annotations",
        help="record exact user authorization for the frozen Sol payload",
    )
    frontier_authorize.add_argument(
        "--run-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "decomposed_review_v2_2" / "frontier_sol_v2_2"),
    )
    frontier_authorize.add_argument("--payload-sha", required=True)
    frontier_authorize.add_argument("--cost-ceiling", type=float, required=True)
    frontier_authorize.add_argument("--confirm-user-authorization", action="store_true")
    frontier_run = commands.add_parser(
        "run-frontier-decomposed-annotations",
        help="run the exact authorized Sol payload resumably",
    )
    frontier_run.add_argument(
        "--run-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "decomposed_review_v2_2" / "frontier_sol_v2_2"),
    )
    frontier_run.add_argument("--workers", type=int, default=6)
    frontier_run.add_argument("--cost-ceiling", type=float, required=True)
    frontier_run.add_argument("--authorize-paid-run", action="store_true")
    frontier_confirm = commands.add_parser(
        "confirm-frontier-decomposed-agreement",
        help="append missing reviews after explicit human all-case agreement",
    )
    frontier_confirm.add_argument("--coder-id", required=True)
    frontier_confirm.add_argument("--confirm-all-reviewed", action="store_true")
    frontier_confirm.add_argument(
        "--output-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "decomposed_review_v2_2"),
    )
    frontier_confirm.add_argument(
        "--run-dir", type=Path,
        default=(ROOT / "annotations" / "response_validity_human_v2"
                 / "decomposed_review_v2_2" / "frontier_sol_v2_2"),
    )

    # Keep completed experimental commands executable for provenance, but do
    # not present them as the current operating interface. The full historical
    # command record is indexed in docs/RESPONSE_VALIDITY_DECISION_LOG.md.
    current_commands = {
        "validate-registry",
        "validate-response-validity-docs",
        "assemble-final-wall-to-wall-luna-v2-4",
    }
    commands.metavar = "{" + ",".join(sorted(current_commands)) + "}"
    commands._choices_actions = [
        action for action in commands._choices_actions
        if action.dest in current_commands
    ]
    return out


def main() -> int:
    args = parser().parse_args()
    if args.command == "inventory":
        write_inventory(ROOT, args.spec, args.output, args.metadata)
        print(f"wrote {args.output.relative_to(ROOT)}")
        print(f"wrote {args.metadata.relative_to(ROOT)}")
        return 0
    if args.command == "validate-registry":
        errors = validate_registry(ROOT, args.registry)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("pipeline registry: PASS")
        return 0
    if args.command == "pilot-design":
        result = build_pilot_design(
            args.population, args.pseudo_outcomes, args.output_dir,
            budget=args.budget, repeat_fraction=args.repeat_fraction, seed=args.seed,
            translation_prompt_path=args.translation_prompt, overwrite=args.overwrite,
        )
        print(__import__("json").dumps(result, indent=2))
        print("No translation or model API call was made.")
        return 0
    if args.command == "assemble-review":
        result = assemble_review_packet(args.output_dir, args.translations)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "translation-volume":
        result = estimate_translation_volume(args.output_dir, args.translation_prompt)
        print(__import__("json").dumps(result, indent=2))
        print("No translation or model API call was made.")
        return 0
    if args.command == "authorize-translation":
        result = record_authorization(
            args.output_dir, args.payload_sha, args.prompt_sha, args.model,
            args.cost_ceiling, args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "translate":
        result = run_translations(
            ROOT, args.output_dir, args.translation_prompt, args.workers,
            args.cost_ceiling, args.authorize_paid_translation,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "translate-chunked":
        result = run_chunked_fallback(
            ROOT, args.output_dir, args.translation_prompt, args.review_id,
            args.cost_ceiling, args.authorize_paid_translation,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "authorize-translation-chunked":
        result = record_chunked_fallback_authorization(
            args.output_dir, args.review_id, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "finalize-ceiling-guarded-loops":
        result = finalize_ceiling_guarded_loops(args.output_dir, args.cost_ceiling)
        print(__import__("json").dumps(result, indent=2))
        print("No provider call was made and no behavioral label was assigned.")
        return 0
    if args.command == "freeze-human-base":
        result = freeze_completed_base_labels(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Silent-repeat records were not read or analyzed.")
        return 0
    if args.command == "audit-human-base":
        result = run_preliminary_human_audit(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Results are provisional: one coder; repeat reliability pending.")
        return 0
    if args.command == "apply-human-language-review":
        freeze = build_language_corrected_base_labels(ROOT, args.output_dir)
        audit = run_preliminary_human_audit(
            ROOT,
            args.output_dir,
            output_dir=args.output_dir / "preliminary_audit_v2_language_corrected",
            freeze_dir=args.output_dir / "base_freeze_v2_language_corrected",
            report_path=ROOT / "docs" / "HUMAN_PILOT_LANGUAGE_CORRECTED_RESULTS.md",
            audit_version="human-pilot-preliminary-audit-v2.0-language-corrected",
        )
        print(__import__("json").dumps({"freeze": freeze, "audit": audit}, indent=2))
        print("Original submissions and v1 freeze were preserved; no network call was made.")
        return 0
    if args.command == "freeze-complete-language-review":
        result = build_complete_language_review_labels(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("All 300 language-fidelity values are explicit; no network call was made.")
        return 0
    if args.command == "build-surrogate-bakeoff":
        result = build_surrogate_bakeoff(ROOT, args.output_dir, seed=args.seed)
        print(__import__("json").dumps(result, indent=2))
        print("No provider call was made; the payload remains unauthorized and model-neutral.")
        return 0
    if args.command == "score-surrogate-bakeoff":
        result = score_surrogate_results(args.output_dir, args.results)
        print(result.to_string(index=False))
        return 0
    if args.command == "estimate-surrogate-bakeoff-cost":
        result = estimate_surrogate_bakeoff_cost(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("No provider call was made and no paid run was authorized.")
        return 0
    if args.command == "authorize-surrogate-bakeoff":
        result = record_bakeoff_authorization(
            args.output_dir, args.payload_sha, args.model, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-surrogate-bakeoff-stage-a":
        result = run_bakeoff_stage_a(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "build-stage-a-adjudication":
        result = build_stage_a_adjudication_packet(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("No provider call was made; prior labels and Luna outputs are absent from the packet.")
        return 0
    if args.command == "freeze-stage-a-adjudication":
        result = freeze_and_score_stage_a_adjudications(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Original labels were preserved and no provider call was made.")
        return 0
    if args.command == "build-surrogate-bakeoff-stage-b":
        result = build_stage_b_bakeoff(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("No provider call was made; Stage B remains unauthorized.")
        return 0
    if args.command == "estimate-surrogate-bakeoff-stage-b-cost":
        result = estimate_stage_b_cost(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("No provider call was made and no paid run was authorized.")
        return 0
    if args.command == "authorize-surrogate-bakeoff-stage-b":
        result = record_stage_b_authorization(
            args.output_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-surrogate-bakeoff-stage-b":
        result = run_stage_b(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "score-surrogate-bakeoff-stage-b":
        result = score_stage_b(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "simulate-human-enrichment":
        result = simulate_enrichment_design_v2(
            ROOT, args.output_dir, seed=args.seed, simulations=args.simulations
        )
        print(__import__("json").dumps(result, indent=2))
        print("No sample, review packet, model payload, network request, or paid call was created.")
        return 0
    if args.command == "freeze-human-enrichment-wave":
        result = freeze_enrichment_wave_v2(
            ROOT, args.output_dir, routing_seed=args.routing_seed,
            draw_seed=args.draw_seed,
            confirm_design_approval=args.confirm_design_approval,
        )
        print(__import__("json").dumps(result, indent=2))
        print("The row IDs and translation payload were frozen; no network or paid call was made.")
        return 0
    if args.command == "assemble-human-enrichment-review":
        result = assemble_enrichment_review_packet(args.output_dir, args.translations)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "freeze-enrichment-checkpoint-200":
        result = freeze_enrichment_checkpoint_200(ROOT, args.wave_dir)
        print(__import__("json").dumps(result, indent=2))
        print("The live append-only label log was not modified; no network call was made.")
        return 0
    if args.command == "build-protected-surrogate-evaluation":
        result = build_protected_surrogate_evaluation(ROOT, args.wave_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Human outcomes are absent from the request payload; no network call was made.")
        return 0
    if args.command == "estimate-protected-surrogate-evaluation-cost":
        result = estimate_protected_evaluation_cost(ROOT, args.wave_dir)
        print(__import__("json").dumps(result, indent=2))
        print("This is a local estimate; no paid run was authorized or started.")
        return 0
    if args.command == "authorize-protected-surrogate-evaluation":
        result = record_protected_evaluation_authorization(
            args.output_dir, args.payload_sha, args.model, args.provider,
            args.cost_ceiling, args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-protected-surrogate-evaluation":
        result = run_protected_surrogate_evaluation(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "score-protected-surrogate-evaluation":
        result = score_protected_surrogate_evaluation(args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "freeze-surrogate-refinement-access":
        result = freeze_refinement_access_v1(ROOT, args.wave_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Only development outcomes were emitted; evaluation rows remain hash-committed.")
        return 0
    if args.command == "run-surrogate-refinement-support-gate":
        result = run_sealed_support_gate_v1(ROOT, args.wave_dir)
        print(__import__("json").dumps(result, indent=2))
        print("No evaluation count, row, example, or provider payload was emitted.")
        return 0
    if args.command == "freeze-enrichment-storage-400":
        result = freeze_enrichment_storage_400(ROOT, args.wave_dir)
        print(__import__("json").dumps(result, indent=2))
        print("All 400 submissions were frozen byte-for-byte; no split outcome was emitted.")
        return 0
    if args.command == "freeze-surrogate-refinement-access-v2":
        result = freeze_refinement_access_v2(ROOT, args.wave_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Only development outcomes were emitted; the enlarged evaluation reserve remains hash-committed.")
        return 0
    if args.command == "run-surrogate-refinement-support-gate-v2":
        result = run_sealed_support_gate_v2(ROOT, args.wave_dir)
        print(__import__("json").dumps(result, indent=2))
        print("No evaluation outcome count, row, example, or provider payload was emitted.")
        return 0
    if args.command == "build-partial-refusal-prompt-drafts":
        result = build_partial_refusal_prompt_drafts(ROOT, args.wave_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Development drafts only: no protected label was read and no provider request was built.")
        return 0
    if args.command == "audit-human-estimand-precision":
        result = run_estimand_precision_audit(ROOT, args.pilot_dir, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("No sealed evaluation label, provider API, or network resource was read.")
        return 0
    if args.command == "plan-home-human-augmentation":
        result = plan_home_augmentation(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Planning only: no row ID was drawn and no sealed outcome or network resource was read.")
        return 0
    if args.command == "build-scalable-annotation-bakeoff":
        result = build_scalable_bakeoff(
            ROOT, args.pilot_dir, args.output_dir, seed=args.seed
        )
        print(__import__("json").dumps(result, indent=2))
        print("All 700 labels were used under issue-grouped folds; no provider call was made.")
        return 0
    if args.command == "estimate-scalable-annotation-bakeoff-cost":
        result = estimate_scalable_bakeoff_cost(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("No provider call was made and no paid run was authorized.")
        return 0
    if args.command == "authorize-scalable-annotation-bakeoff":
        result = record_scalable_bakeoff_authorization(
            args.output_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-scalable-annotation-bakeoff":
        # The repository .env is authoritative for secrets. This prevents a
        # stale shell export from shadowing the current OpenRouter credential.
        # Loading occurs only at the explicitly paid command boundary.
        load_env_from_file(ROOT / ".env", override=True)
        result = run_scalable_bakeoff(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "score-scalable-annotation-bakeoff":
        result = score_scalable_bakeoff(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "validate-response-validity-docs":
        result = validate_response_validity_documentation(ROOT)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "build-fold-nested-refusal-refinement":
        result = build_fold_nested_refinement(ROOT, args.pilot_dir, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no provider call was made and no paid run was authorized.")
        return 0
    if args.command == "estimate-fold-nested-refusal-refinement-cost":
        result = estimate_fold_nested_refinement_cost(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("No provider call was made and no paid run was authorized.")
        return 0
    if args.command == "authorize-fold-nested-refusal-refinement":
        result = record_fold_nested_refinement_authorization(
            args.output_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-fold-nested-refusal-refinement":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_fold_nested_refinement(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "score-fold-nested-refusal-refinement":
        result = score_fold_nested_refinement(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "build-decomposed-validity-review":
        result = build_decomposed_review(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no provider call was made and no paid run was authorized.")
        return 0
    if args.command == "assemble-decomposed-validity-review":
        result = assemble_decomposed_review(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Assembled locally: no provider call was made.")
        return 0
    if args.command == "rescore-decomposed-validity-review":
        result = rescore_decomposed_review(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2, default=str))
        print("Rescored immutable predictions locally: no provider call was made.")
        return 0
    if args.command == "harmonize-decomposed-validity-gold":
        result = build_harmonized_decomposed_gold(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Harmonized locally: no provider call was made.")
        return 0
    if args.command == "run-preliminary-stage18":
        result = run_preliminary_stage18(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Estimated locally from the probability sample: no provider call was made.")
        return 0
    if args.command == "prepare-luna-v22-internal-test":
        result = prepare_luna_v22_test(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no provider call was made and no paid run was authorized.")
        return 0
    if args.command == "estimate-luna-v22-internal-test-cost":
        result = estimate_luna_v22_cost(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Estimated locally: no provider call was made and no paid run was authorized.")
        return 0
    if args.command == "authorize-luna-v22-internal-test":
        result = authorize_luna_v22_test(
            args.output_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-luna-v22-internal-test":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_luna_v22_test(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "score-luna-v22-internal-test":
        result = score_luna_v22_test(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "prepare-luna-v23-repair-test":
        result = prepare_luna_v23_repair(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no provider call was made and no paid run was authorized.")
        return 0
    if args.command == "estimate-luna-v23-repair-test-cost":
        result = estimate_luna_v23_repair_cost(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Estimated locally: no provider call was made and no paid run was authorized.")
        return 0
    if args.command == "authorize-luna-v23-repair-test":
        result = authorize_luna_v23_repair(
            args.output_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-luna-v23-repair-test":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_luna_v23_repair(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "score-luna-v23-repair-test":
        result = score_luna_v23_repair(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "plan-external-validity-audit":
        result = simulate_external_audit_design(
            ROOT, args.output_dir, seed=args.seed, simulations=args.simulations
        )
        print(__import__("json").dumps(result, indent=2))
        print("Planning only: no response ID, provider payload, authorization, or network call was created.")
        return 0
    if args.command == "freeze-external-validity-audit":
        result = freeze_external_audit(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no paid run was authorized and no network call was made.")
        return 0
    if args.command == "authorize-external-validity-audit":
        result = authorize_external_audit(
            args.output_dir, args.luna_payload_sha, args.sol_payload_sha,
            args.cost_ceiling, args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-external-validity-audit":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_external_audit(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "summarize-external-validity-audit":
        result = summarize_external_audit(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "score-external-sol-reference":
        result = evaluate_external_sol_reference(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Calculated locally: Sol is a machine reference, not human gold.")
        return 0
    if args.command == "summarize-external-refusal-disagreement-review":
        result = summarize_external_disagreement_human_review(
            ROOT, output_dir=args.output_dir
        )
        print(__import__("json").dumps(result, indent=2))
        print("Assembled locally: the append-only source log was not changed.")
        return 0
    if args.command == "freeze-refusal-boundary-consistency-review":
        result = freeze_refusal_boundary_consistency(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: four prior decisions were preserved and no provider was called.")
        return 0
    if args.command == "summarize-refusal-boundary-consistency-review":
        result = summarize_refusal_boundary_consistency(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Assembled locally: neither append-only source log was changed.")
        return 0
    if args.command == "prepare-luna-v2-4-evaluation":
        result = prepare_luna_v24_evaluation(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no reference label entered the payload and no provider was called.")
        return 0
    if args.command == "estimate-luna-v2-4-evaluation-cost":
        result = estimate_luna_v24_cost(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "authorize-luna-v2-4-evaluation":
        result = authorize_luna_v24(
            args.output_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-luna-v2-4-evaluation":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_luna_v24(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "score-luna-v2-4-evaluation":
        result = score_luna_v24(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "prepare-sol-v2-4-evaluation":
        result = prepare_sol_v24_evaluation(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: Luna and Sol receive byte-identical prompt content.")
        return 0
    if args.command == "estimate-sol-v2-4-evaluation-cost":
        result = estimate_sol_v24_cost(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "authorize-sol-v2-4-evaluation":
        result = authorize_sol_v24(
            args.output_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-sol-v2-4-evaluation":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_sol_v24(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "score-sol-v2-4-evaluation":
        result = score_sol_v24(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "prepare-model-bakeoff-v2":
        result = prepare_model_bakeoff_v2(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no provider was called and no reference label entered a request.")
        return 0
    if args.command == "estimate-model-bakeoff-v2-cost":
        result = estimate_model_bakeoff_v2_cost(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "authorize-model-bakeoff-v2":
        result = authorize_model_bakeoff_v2(
            args.output_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-model-bakeoff-v2":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_model_bakeoff_v2(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "score-model-bakeoff-v2":
        result = score_model_bakeoff_v2(ROOT, output_dir=args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "prepare-luna-v2-4-human-certification":
        result = prepare_luna_v24_human_certification(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no provider was called.")
        return 0
    if args.command == "estimate-luna-v2-4-human-certification-cost":
        result = estimate_luna_v24_human_certification_cost(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "authorize-luna-v2-4-human-certification":
        result = authorize_luna_v24_human_certification(
            args.output_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-luna-v2-4-human-certification":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_luna_v24(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "freeze-luna-v2-4-human-certification-phase2":
        result = freeze_luna_v24_human_phase2(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no translation was authorized or sent.")
        return 0
    if args.command == "prepare-fresh-sol-v2-4-reference":
        result = prepare_fresh_sol_v24_reference(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no provider was called.")
        return 0
    if args.command == "estimate-fresh-sol-v2-4-reference-cost":
        result = estimate_fresh_sol_v24_reference_cost(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "authorize-fresh-sol-v2-4-reference":
        result = authorize_fresh_sol_v24_reference(
            args.output_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-fresh-sol-v2-4-reference":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_sol_v24(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "score-fresh-sol-v2-4-reference":
        result = score_fresh_sol_v24_reference(
            ROOT, args.output_dir, args.bootstrap_draws
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "prepare-wall-to-wall-luna-v2-4":
        result = prepare_wall_to_wall_luna_v24(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no provider was called.")
        return 0
    if args.command == "estimate-wall-to-wall-luna-v2-4-cost":
        result = estimate_wall_to_wall_luna_v24_cost(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "authorize-wall-to-wall-luna-v2-4":
        result = authorize_wall_to_wall_luna_v24(
            args.output_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-wall-to-wall-luna-v2-4":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_wall_to_wall_luna_v24(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "prepare-wall-to-wall-luna-v2-4-repair":
        result = prepare_wall_to_wall_repair_v24(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no provider was called.")
        return 0
    if args.command == "estimate-wall-to-wall-luna-v2-4-repair-cost":
        result = estimate_wall_to_wall_repair_v24_cost(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "authorize-wall-to-wall-luna-v2-4-repair":
        result = authorize_wall_to_wall_repair_v24(
            args.output_dir, args.payload_sha, args.protocol_sha,
            args.cost_ceiling, args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-wall-to-wall-luna-v2-4-repair":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_wall_to_wall_repair_v24(
            ROOT, args.output_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "assemble-final-wall-to-wall-luna-v2-4":
        result = assemble_final_wall_to_wall_v24(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Assembled locally: no provider was called.")
        return 0
    if args.command == "freeze-external-human-phase2":
        result = freeze_external_human_phase2(
            ROOT, args.output_dir, seed=args.seed
        )
        print(__import__("json").dumps(result, indent=2))
        print(
            "Frozen locally: no translation was authorized and no network call was made."
        )
        return 0
    if args.command == "assemble-external-human-review":
        result = assemble_external_human_review(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Assembled locally: no provider call was made.")
        return 0
    if args.command == "assemble-external-sol-reference":
        result = assemble_external_sol_reference(ROOT, args.output_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Reused existing Sol labels: no provider call and no human-log write.")
        return 0
    if args.command == "prepare-frontier-decomposed-annotations":
        result = prepare_frontier_decomposed(ROOT, args.run_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Frozen locally: no provider call was made and no paid run was authorized.")
        return 0
    if args.command == "estimate-frontier-decomposed-cost":
        result = estimate_frontier_decomposed(ROOT, args.run_dir)
        print(__import__("json").dumps(result, indent=2))
        print("Estimated locally: no provider call was made and no paid run was authorized.")
        return 0
    if args.command == "authorize-frontier-decomposed-annotations":
        result = authorize_frontier_decomposed(
            args.run_dir, args.payload_sha, args.cost_ceiling,
            args.confirm_user_authorization,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "run-frontier-decomposed-annotations":
        load_env_from_file(ROOT / ".env", override=True)
        result = run_frontier_decomposed(
            ROOT, args.run_dir, args.workers, args.cost_ceiling,
            args.authorize_paid_run,
        )
        print(__import__("json").dumps(result, indent=2))
        return 0
    if args.command == "confirm-frontier-decomposed-agreement":
        result = record_frontier_bulk_agreement(
            ROOT, args.coder_id, args.confirm_all_reviewed,
            args.output_dir, args.run_dir,
        )
        print(__import__("json").dumps(result, indent=2))
        print("Human agreement appended locally: no provider call was made.")
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
