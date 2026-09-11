"""Freeze and assemble the external v2.3 human-validation phase.

This module performs local work only. It realizes the predeclared phase-two
Bernoulli design with independent model-language-stratum random streams, keeps
the exact human-review probability, creates a blinded translation payload, and
assembles the review packet after separately authorized translations complete.
It never calls a provider.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import tiktoken

from .human_pilot import sha_file


EXTERNAL_DIR = (
    "annotations/response_validity_human_v2/external_audit_v1"
)
DEFAULT_DIR = f"{EXTERNAL_DIR}/human_phase2_v1"
TRANSLATION_PROMPT = "config/response_translation_prompt_v1.txt"
SEED = 20260828
EXPECTED_EXTERNAL_N = 1197
EXPECTED_STRATA = {
    "priority": (229, 1.0),
    "capability_positive_agreement": (374, 0.5),
    "ordinary_agreement": (594, 0.1),
}
TRANSLATOR_MODEL = "openai/gpt-5.6-luna"
INPUT_PRICE = 0.20
OUTPUT_PRICE = 1.20
RESERVE_INPUT_PRICE = 0.40
RESERVE_OUTPUT_PRICE = 2.40


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_hash(row: pd.Series) -> str:
    value = {
        "audit_response_id": str(row.audit_response_id),
        "prompt_language": str(row.prompt_language),
        "prompt_text_en": str(row.prompt_text_en),
        "prompt_text": str(row.prompt_text),
        "response_text": str(row.response_text),
    }
    return _sha_text(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ))


def _stream_seed(stratum: str, model: str, language: str, seed: int) -> int:
    raw = f"{seed}|{stratum}|{model}|{language}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def select_phase2(frame: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """Apply the frozen Bernoulli probabilities within model-language strata."""
    required = {
        "audit_response_id", "model", "prompt_language", "phase2_stratum",
        "planned_phase2_probability", "phase1_inclusion_probability",
    }
    missing = required - set(frame)
    if missing:
        raise ValueError(f"phase-two source missing {sorted(missing)}")
    if len(frame) != EXPECTED_EXTERNAL_N or frame.audit_response_id.duplicated().any():
        raise ValueError("external phase-one table must contain 1,197 unique rows")
    counts = frame.phase2_stratum.value_counts().to_dict()
    for stratum, (expected_n, probability) in EXPECTED_STRATA.items():
        if counts.get(stratum) != expected_n:
            raise ValueError(f"phase-two stratum count changed: {stratum}")
        observed = frame.loc[
            frame.phase2_stratum.eq(stratum), "planned_phase2_probability"
        ].unique()
        if len(observed) != 1 or float(observed[0]) != probability:
            raise ValueError(f"phase-two probability changed: {stratum}")

    selected_ids: set[str] = set()
    groups = frame.groupby(
        ["phase2_stratum", "model", "prompt_language"], sort=True, observed=True
    )
    for (stratum, model, language), part in groups:
        part = part.sort_values("audit_response_id", kind="mergesort")
        q = float(part.planned_phase2_probability.iloc[0])
        if q == 1:
            chosen = np.ones(len(part), dtype=bool)
        else:
            rng = np.random.default_rng(
                _stream_seed(str(stratum), str(model), str(language), seed)
            )
            chosen = rng.random(len(part)) < q
        selected_ids.update(part.loc[chosen, "audit_response_id"].astype(str))

    selected = frame.loc[
        frame.audit_response_id.astype(str).isin(selected_ids)
    ].copy()
    selected["human_review_probability"] = (
        selected.planned_phase2_probability.astype(float)
    )
    selected["combined_inclusion_probability"] = (
        selected.phase1_inclusion_probability.astype(float)
        * selected.human_review_probability
    )
    if not selected.combined_inclusion_probability.between(
        0, 1, inclusive="right"
    ).all():
        raise ValueError("invalid combined human-review probability")
    selected["combined_sampling_weight"] = (
        1 / selected.combined_inclusion_probability
    )
    if int(selected.phase2_stratum.eq("priority").sum()) != 229:
        raise ValueError("every priority row must enter human review")
    return selected.sort_values("audit_response_id").reset_index(drop=True)


def _input_hashes(root: Path) -> dict[str, str]:
    base = root / EXTERNAL_DIR
    return {
        "external_manifest": sha_file(base / "manifest.json"),
        "paired_machine_labels": sha_file(base / "paired_machine_labels.parquet"),
        "blinded_review_packet": sha_file(base / "blinded_review_packet.parquet"),
        "translation_prompt": sha_file(root / TRANSLATION_PROMPT),
        "v2_3_codebook": sha_file(
            root / "config/response_validity_decomposed_v2_3.json"
        ),
    }


def _verify_existing(root: Path, output_dir: Path, seed: int) -> dict | None:
    path = output_dir / "wave_manifest.json"
    if not path.exists():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if int(manifest.get("seed", -1)) != int(seed):
        raise RuntimeError("frozen external human phase used a different seed")
    if manifest.get("input_sha256") != _input_hashes(root):
        raise RuntimeError("frozen external human phase has different inputs")
    for name, expected in manifest.get("artifact_sha256", {}).items():
        if sha_file(output_dir / name) != expected:
            raise RuntimeError(f"external human artifact changed: {name}")
    return manifest


def freeze_external_human_phase2(
    root: Path, output_dir: Path | None = None, seed: int = SEED
) -> dict:
    """Freeze the realized review rows and non-English translation payload."""
    output_dir = output_dir or root / DEFAULT_DIR
    existing = _verify_existing(root, output_dir, seed)
    if existing is not None:
        return existing
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"nonempty unmanifested directory: {output_dir}")

    base = root / EXTERNAL_DIR
    paired = pd.read_parquet(base / "paired_machine_labels.parquet")
    blinded = pd.read_parquet(base / "blinded_review_packet.parquet")
    if len(blinded) != EXPECTED_EXTERNAL_N or blinded.audit_response_id.duplicated().any():
        raise ValueError("blinded external packet must contain 1,197 unique rows")
    selected = select_phase2(paired, seed)
    selected = selected.merge(
        blinded, on=["audit_response_id", "prompt_language"], validate="one_to_one"
    )

    rng = np.random.default_rng(seed + 1)
    selected["review_order"] = rng.permutation(len(selected)) + 1
    selected["review_id"] = selected.audit_response_id.astype(str)
    selected["source_hash"] = selected.apply(_source_hash, axis=1)
    if selected.source_hash.duplicated().any():
        raise ValueError("external human source hash collision")

    output_dir.mkdir(parents=True, exist_ok=False)
    design_fields = [
        "review_id", "audit_response_id", "review_order", "prompt_id",
        "prompt_language", "model", "issue_id", "routing_stratum",
        "selected_by_cell_component", "selected_by_risk_component",
        "phase1_inclusion_probability", "phase2_stratum",
        "human_review_probability", "combined_inclusion_probability",
        "combined_sampling_weight", "source_hash",
    ]
    selected[design_fields].sort_values("review_order").to_parquet(
        output_dir / "phase2_design.parquet", index=False
    )
    safe_fields = [
        "review_id", "review_order", "source_hash", "prompt_language",
        "prompt_text_en", "prompt_text", "response_text",
    ]
    selected[safe_fields].sort_values("review_order").to_parquet(
        output_dir / "review_source_packet.parquet", index=False
    )

    prompt_hash = sha_file(root / TRANSLATION_PROMPT)
    translations = selected.loc[selected.prompt_language.ne("en")].copy()
    translations["translation_prompt_hash"] = prompt_hash
    translation_fields = [
        "review_id", "source_hash", "translation_prompt_hash",
        "prompt_language", "prompt_text_en", "prompt_text", "response_text",
    ]
    payload_path = output_dir / "translation_requests.jsonl"
    with payload_path.open("w", encoding="utf-8") as handle:
        for row in translations.sort_values("review_order")[
            translation_fields
        ].to_dict("records"):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    encoding = tiktoken.get_encoding("o200k_base")
    prompt = (root / TRANSLATION_PROMPT).read_text(encoding="utf-8")
    payload = [
        json.loads(line) for line in payload_path.read_text(
            encoding="utf-8"
        ).splitlines() if line
    ]
    input_tokens = sum(
        len(encoding.encode(prompt))
        + len(encoding.encode(json.dumps(row, ensure_ascii=False, sort_keys=True)))
        for row in payload
    )
    source_tokens = [
        len(encoding.encode(str(row["response_text"]))) for row in payload
    ]
    planning_output = int(sum(np.ceil(np.asarray(source_tokens) * 1.25 + 120)))
    maximum_output = int(sum(
        min(40_000, max(2_000, int(np.ceil(tokens * 6 + 2_000))))
        for tokens in source_tokens
    ))
    cost = {
        "created_at": _now(),
        "model": TRANSLATOR_MODEL,
        "provider": "OpenRouter/OpenAI",
        "pricing_date": "2026-08-27",
        "n_requests": len(payload),
        "estimated_input_tokens": int(input_tokens),
        "planning_output_tokens": planning_output,
        "maximum_reserved_output_tokens": maximum_output,
        "expected_cost_usd": (
            input_tokens * INPUT_PRICE + planning_output * OUTPUT_PRICE
        ) / 1_000_000,
        "single_attempt_reservation_usd": (
            input_tokens * RESERVE_INPUT_PRICE
            + maximum_output * RESERVE_OUTPUT_PRICE
        ) / 1_000_000,
        "network_call_made": False,
    }
    (output_dir / "translation_cost_estimate.json").write_text(
        json.dumps(cost, indent=2), encoding="utf-8"
    )

    diagnostics = selected.groupby(
        ["phase2_stratum", "prompt_language"], observed=True
    ).size().rename("n").reset_index()
    diagnostics.to_csv(output_dir / "phase2_diagnostics.csv", index=False)
    artifact_names = [
        "phase2_design.parquet", "review_source_packet.parquet",
        "translation_requests.jsonl", "translation_cost_estimate.json",
        "phase2_diagnostics.csv",
    ]
    manifest = {
        "version": "external-human-validation-phase2-v1",
        "created_at": _now(),
        "status": "frozen_translation_not_authorized",
        "seed": seed,
        "sampling_method": (
            "certainty priority plus independent Bernoulli draws within "
            "phase2_stratum x model x prompt_language"
        ),
        "phase2_probabilities": {
            name: probability for name, (_, probability) in EXPECTED_STRATA.items()
        },
        "external_phase1_n": EXPECTED_EXTERNAL_N,
        "realized_human_review_n": len(selected),
        "realized_by_phase2_stratum": {
            name: int((selected.phase2_stratum == name).sum())
            for name in EXPECTED_STRATA
        },
        "translation_request_n": len(payload),
        "english_identity_translation_n": int(
            selected.prompt_language.eq("en").sum()
        ),
        "input_sha256": _input_hashes(root),
        "translation_prompt_path": TRANSLATION_PROMPT,
        "translation_prompt_sha256": prompt_hash,
        "artifact_sha256": {
            name: sha_file(output_dir / name) for name in artifact_names
        },
        "translation_authorized": False,
        "network_call_made": False,
        "human_review_started": False,
    }
    (output_dir / "wave_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def assemble_external_human_review(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Create the final blinded Streamlit packet after translations complete."""
    output_dir = output_dir or root / DEFAULT_DIR
    manifest_path = output_dir / "wave_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _verify_existing(root, output_dir, int(manifest["seed"]))
    source = pd.read_parquet(output_dir / "review_source_packet.parquet")
    raw_path = output_dir / "translations_raw.jsonl"
    if not raw_path.exists():
        raise FileNotFoundError("authorized translations have not run")
    records = [
        json.loads(line) for line in raw_path.read_text(
            encoding="utf-8"
        ).splitlines() if line
    ]
    complete = pd.DataFrame([
        row for row in records if row.get("status") == "ok"
    ])
    if complete.empty or complete.review_id.duplicated().any():
        raise ValueError("translations are missing or duplicated")
    expected_nonenglish = set(
        source.loc[source.prompt_language.ne("en"), "review_id"].astype(str)
    )
    observed = set(complete.review_id.astype(str))
    if observed != expected_nonenglish:
        raise ValueError("translations do not exactly cover non-English reviews")
    translation_fields = [
        "review_id", "source_hash", "response_translation_en",
        "translation_status", "uncertain_spans", "detected_language",
    ]
    packet = source.merge(
        complete[translation_fields],
        on=["review_id", "source_hash"], how="left", validate="one_to_one",
    )
    english = packet.prompt_language.eq("en")
    packet.loc[english, "response_translation_en"] = packet.loc[
        english, "response_text"
    ]
    packet.loc[english, "translation_status"] = "complete"
    packet.loc[english, "detected_language"] = "English"
    packet.loc[english, "uncertain_spans"] = pd.Series(
        [[] for _ in range(int(english.sum()))],
        index=packet.index[english], dtype=object,
    )
    if packet.response_translation_en.isna().any():
        raise ValueError("assembled human packet has missing translations")
    safe = [
        "review_id", "review_order", "source_hash", "prompt_language",
        "prompt_text_en", "prompt_text", "response_text",
        "response_translation_en", "translation_status", "uncertain_spans",
        "detected_language",
    ]
    packet[safe].sort_values("review_order").to_parquet(
        output_dir / "human_review_packet.parquet", index=False
    )
    manifest["status"] = "human_review_ready"
    manifest["translations_complete"] = True
    manifest["human_review_packet_sha256"] = sha_file(
        output_dir / "human_review_packet.parquet"
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "status": "human_review_ready",
        "n_review_tasks": len(packet),
        "human_review_packet_sha256": manifest["human_review_packet_sha256"],
    }


def assemble_external_sol_reference(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Extract existing v2.3 Sol labels for the 458-row human-review draw.

    This is a model-reference artifact, never a human-label log. It makes no
    provider call and does not expose Sol decisions through the blinded human
    page.
    """
    output_dir = output_dir or root / DEFAULT_DIR
    manifest_path = output_dir / "wave_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _verify_existing(root, output_dir, int(manifest["seed"]))
    design = pd.read_parquet(
        output_dir / "phase2_design.parquet",
        columns=["review_id", "source_hash"],
    )
    paired = pd.read_parquet(root / EXTERNAL_DIR / "paired_machine_labels.parquet")
    sol_fields = [
        "task_behavior", "substantive_refusal", "stance_disclaimer",
        "epistemic_limitation", "language_fidelity", "output_quality",
        "technical_failure", "confidence", "refusal_evidence_span",
        "decision_note",
    ]
    source_fields = ["audit_response_id"] + [f"{field}_sol" for field in sol_fields]
    labels = design.merge(
        paired[source_fields],
        left_on="review_id", right_on="audit_response_id",
        validate="one_to_one",
    ).drop(columns="audit_response_id")
    labels = labels.rename(columns={f"{field}_sol": field for field in sol_fields})
    labels.insert(2, "annotation_source", "machine_reference")
    labels.insert(3, "annotator_id", "openai/gpt-5.6-sol")
    labels.insert(4, "codebook_version", "response-validity-decomposed-v2.3")
    labels.insert(5, "review_status", "complete")
    if len(labels) != 458 or labels.review_id.duplicated().any():
        raise ValueError("Sol reference must contain 458 unique selected rows")
    if labels[sol_fields].isna().any().any():
        raise ValueError("Sol reference contains a missing v2.3 field")
    path = output_dir / "sol_reference_labels.parquet"
    if path.exists():
        expected = manifest.get("sol_reference_labels_sha256")
        if expected != sha_file(path):
            raise RuntimeError("existing Sol reference differs from its manifest hash")
    else:
        labels.sort_values("review_id").to_parquet(path, index=False)
    manifest["sol_reference_status"] = "complete_existing_external_v2_3_labels"
    manifest["sol_reference_n"] = len(labels)
    manifest["sol_reference_labels_sha256"] = sha_file(path)
    manifest["sol_reference_is_human_gold"] = False
    manifest["additional_provider_call_made"] = False
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "status": manifest["sol_reference_status"],
        "n": len(labels),
        "sha256": manifest["sol_reference_labels_sha256"],
        "human_label_log_modified": False,
        "provider_call_made": False,
    }
