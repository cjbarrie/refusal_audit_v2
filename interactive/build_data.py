#!/usr/bin/env python3
"""Build reproducible, local-only Parquet assets for the fixed-geometry UMAP.

The default build resolves the formally promoted release. An explicit
``--release`` may select one of the recorded, accepted website candidates below
without changing the analysis promotion pointer. Every build verifies the
release files and intersects raw response records with the exact R analysis
keys. It never fits embeddings or UMAP and never exports reasoning content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from schemas import KEY, MODEL_JURISDICTION

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "interactive" / "data"
PROMOTED_MANIFEST = ROOT / "pipeline" / "estimates" / "canonical" / "c00_manifest.csv"
RUN_DIR = ROOT / "annotations" / "full_v1"
EXPANSION_RUN_DIR = ROOT / "annotations" / "model_expansion_v3" / "full_run_v1"
HUNYUAN_RUN_DIR = (
    ROOT / "annotations" / "model_expansion_v3" / "hunyuan_all_languages_v3_1"
)
V4_FULL_DIR = ROOT / "annotations" / "model_expansion_v4" / "full_generation_v1"
TORCH_FULL = (
    ROOT / "annotations" / "model_expansion_v4" / "local_gguf_full_hpc_v1"
    / "responses.jsonl"
)
RELEASE_CONTRACTS = {
    "canon_024": {
        "release_status": "promoted",
        "responses": 224_544,
        "models": 18,
        "extra_sources": [],
    },
    "canon_031": {
        "release_status": "accepted_candidate",
        "responses": 299_080,
        "models": 24,
        "extra_sources": [
            V4_FULL_DIR / "sarvam-105b" / "results.jsonl",
            V4_FULL_DIR / "bielik-11b-v3.0" / "results.jsonl",
            TORCH_FULL,
        ],
    },
}
EXPANSION_LABEL_DIRS = [
    ROOT / "annotations" / "model_expansion_v3" / "luna_v2_4_completed_batch1",
    ROOT / "annotations" / "model_expansion_v3" / "luna_v2_4_completed_batch2",
    ROOT / "annotations" / "model_expansion_v3" / "luna_v2_4_kimi_batch3",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_release(requested_release: str | None) -> tuple[str, str, Path, pd.DataFrame, Path]:
    if not PROMOTED_MANIFEST.exists():
        raise FileNotFoundError("promoted canonical manifest is missing")
    manifest = pd.read_csv(PROMOTED_MANIFEST)
    ids = manifest["canonical_run_id"].dropna().astype(str).unique()
    if len(ids) != 1:
        raise ValueError(f"manifest must name exactly one release, found {ids.tolist()}")
    promoted_id = ids[0]
    release_id = requested_release or promoted_id
    if release_id not in RELEASE_CONTRACTS:
        raise ValueError(
            f"website release {release_id!r} is not an approved build contract; "
            f"choose one of {sorted(RELEASE_CONTRACTS)}"
        )
    release = ROOT / "pipeline" / "releases" / release_id
    release_manifest = release / "estimates" / "c00_manifest.csv"
    if not release_manifest.exists():
        raise FileNotFoundError(f"release {release_id} has no manifest")
    if release_id == promoted_id and sha256(release_manifest) != sha256(PROMOTED_MANIFEST):
        raise ValueError("promoted manifest differs from the release manifest")
    selected_manifest = pd.read_csv(release_manifest)
    selected_ids = selected_manifest["canonical_run_id"].dropna().astype(str).unique()
    if selected_ids.tolist() != [release_id]:
        raise ValueError(f"release manifest does not uniquely identify {release_id}")
    status = RELEASE_CONTRACTS[release_id]["release_status"]
    return release_id, status, release, selected_manifest, release_manifest


def verify_manifest_file(manifest: pd.DataFrame, path: Path) -> None:
    rel = str(path.relative_to(ROOT))
    rows = manifest.loc[manifest["path"].astype(str) == rel]
    if len(rows) != 1:
        raise ValueError(f"manifest does not uniquely identify {rel}")
    observed = sha256(path)
    expected = str(rows.iloc[0]["sha256"])
    if observed != expected:
        raise ValueError(f"hash mismatch for {rel}: {observed} != {expected}")


def last_clean_jsonl(paths: list[Path], kind: str) -> dict[tuple, dict]:
    """Return the last clean record for each canonical key.

    A generation record is clean iff response_text is nonempty and error absent;
    an annotation is clean iff engagement_code is present and error absent.
    Later errors never erase an earlier clean record.
    """
    out: dict[tuple, dict] = {}
    for path in paths:
        with path.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = tuple(row.get(k) for k in KEY)
                if any(v is None for v in key) or row.get("error"):
                    continue
                clean = bool(row.get("response_text")) if kind == "response" else row.get("engagement_code") is not None
                if clean:
                    try:
                        row["_source_file"] = str(path.relative_to(ROOT))
                    except ValueError:  # permits isolated temporary-file tests
                        row["_source_file"] = str(path)
                    row["_source_line"] = lineno
                    out[key] = row
    return out


def verify_expansion_generation(paths: list[Path]) -> None:
    """Tie every displayed expansion answer to the frozen annotation input."""
    expected: dict[str, str] = {}
    for directory in EXPANSION_LABEL_DIRS:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        for name, digest_value in manifest["input_sha256"].items():
            if name.endswith("_results"):
                expected[name.removesuffix("_results")] = digest_value
    observed_models: set[str] = set()
    for path in paths:
        with path.open(encoding="utf-8") as fh:
            first = json.loads(next(line for line in fh if line.strip()))
        model = str(first["model"])
        if model not in expected:
            raise ValueError(f"no frozen annotation-input hash for {model}")
        observed = sha256(path)
        if observed != expected[model]:
            raise ValueError(f"generation result hash mismatch for {model}")
        observed_models.add(model)
    if observed_models != set(expected):
        raise ValueError(f"expansion generation files incomplete: {sorted(set(expected) - observed_models)}")


def exact_analysis_keys(data_path: Path) -> pd.DataFrame:
    """Export the release-frozen response frame, including its v2.4 labels."""
    cols = [
        *KEY, "issue_id", "topic_domain", "region_focus", "controversy_tier",
        "route", "position_side", "prompt_origin_language", "prompt_origin_form",
        "engagement_code", "refusal_justification", "refusal_justification_other",
        "response_language", "judge_model", "judge_prompt_version", "annotation_run_id",
        "rv_task_behavior", "rv_substantive_refusal", "rv_stance_disclaimer",
        "rv_epistemic_limitation", "rv_language_fidelity", "rv_output_quality",
        "rv_technical_failure", "rv_confidence", "rv_refusal_evidence_span",
        "rv_decision_note", "rv_annotation_source", "rv_provider_request_id",
        "rv_created_at", "genuine_refusal", "capability_failure",
        "original_nonengagement", "corpus", "generation_response_sha256",
    ]
    with tempfile.TemporaryDirectory(prefix="refusal_umap_") as td:
        target = Path(td) / "keys.csv"
        quoted = ",".join(f'"{c}"' for c in cols)
        expr = (
            f'load("{data_path}"); '
            f'x <- data_clean[,c({quoted})]; '
            f'write.csv(x,"{target}",row.names=FALSE,na="")'
        )
        subprocess.run(["Rscript", "-e", expr], cwd=ROOT, check=True)
        frame = pd.read_csv(target, keep_default_na=True, low_memory=False)
    if frame.duplicated(KEY).any():
        raise ValueError("data_clean contains duplicate canonical keys")
    return frame


def build(requested_release: str | None = None) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    release_id, release_status, release, manifest, release_manifest = resolve_release(
        requested_release
    )
    contract = RELEASE_CONTRACTS[release_id]
    coords_path = release / "estimates" / "c22_prompt_umap_coordinates.csv"
    verify_manifest_file(manifest, coords_path)
    data_path = release / "estimates" / "data_clean.RData"
    verify_manifest_file(manifest, data_path)
    coords = pd.read_csv(coords_path)
    if len(coords) != 2496 or coords["prompt_id"].duplicated().any():
        raise ValueError(f"expected 2,496 unique UMAP prompts, found {len(coords)}")

    keys = exact_analysis_keys(data_path)
    source_paths = sorted((RUN_DIR / "responses").glob("rebalanced_*.jsonl"))
    expansion_paths = sorted(EXPANSION_RUN_DIR.glob("stage_*/results.jsonl"))
    expansion_paths += sorted(HUNYUAN_RUN_DIR.glob("stage_*/results.jsonl"))
    verify_expansion_generation(expansion_paths)
    source_paths += expansion_paths
    extra_sources = contract["extra_sources"]
    missing_sources = [path for path in extra_sources if not path.exists()]
    if missing_sources:
        raise FileNotFoundError(f"candidate response sources are missing: {missing_sources}")
    source_paths += extra_sources
    responses = last_clean_jsonl(source_paths, "response")
    raw = pd.DataFrame([{**{k: key[i] for i, k in enumerate(KEY)}, **row} for key, row in responses.items()])
    keep = [*KEY, "prompt_text", "response_text", "provider", "model_id", "battery", "prompt_category", "qid", "timestamp", "_source_file", "_source_line"]
    raw = raw[[c for c in keep if c in raw.columns]].drop_duplicates(KEY, keep="last")
    merged = keys.merge(raw, on=KEY, how="left", validate="one_to_one", indicator=True)
    missing = merged.loc[merged["_merge"] != "both", KEY]
    if len(missing):
        raise ValueError(f"{len(missing)} canonical responses lack recoverable text")
    merged = merged.drop(columns="_merge")
    if len(merged) != contract["responses"] or merged.model.nunique() != contract["models"]:
        raise ValueError(
            f"unexpected canonical shape: {len(merged)} responses and "
            f"{merged.model.nunique()} models"
        )
    frozen_response_hash = merged.get("generation_response_sha256")
    if frozen_response_hash is not None:
        check = frozen_response_hash.notna()
        observed_hash = merged.loc[check, "response_text"].map(
            lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
        )
        mismatch = observed_hash.ne(frozen_response_hash.loc[check].astype(str))
        if mismatch.any():
            raise ValueError(
                f"{int(mismatch.sum())} response texts differ from the hashes "
                "used by the accepted annotations"
            )
    merged["developer_jurisdiction"] = merged["model"].map(MODEL_JURISDICTION)
    if merged["developer_jurisdiction"].isna().any():
        raise ValueError("one or more models lack a jurisdiction mapping")
    rename = {c: c.removeprefix("rv_") for c in merged.columns if c.startswith("rv_")}
    merged = merged.rename(columns=rename)
    merged["genuine_refusal"] = merged["genuine_refusal"].astype(bool)
    merged["capability_failure"] = merged["capability_failure"].astype(bool)

    # Expansion result records contain the answer but not a redundant copy of
    # the delivered prompt. Recover that text from the identical frozen prompt
    # key in the original panel, and reject any contradictory copies.
    prompt_key = ["prompt_id", "prompt_language"]
    prompt_source = raw.dropna(subset=["prompt_text"])
    conflicts = prompt_source.groupby(prompt_key)["prompt_text"].nunique()
    if conflicts.gt(1).any():
        raise ValueError("conflicting prompt text for one prompt-language key")
    prompt_lookup = prompt_source.drop_duplicates(prompt_key)[prompt_key + ["prompt_text"]]
    merged = merged.merge(prompt_lookup, on=prompt_key, how="left",
                          suffixes=("", "_lookup"), validate="many_to_one")
    merged["prompt_text"] = merged["prompt_text"].fillna(merged.pop("prompt_text_lookup"))
    if merged["prompt_text"].isna().any():
        raise ValueError("one or more canonical rows lack delivered prompt text")

    # English prompt is a stable reference even when inspecting another language.
    en = merged.loc[merged.prompt_language.eq("en"), ["prompt_id", "prompt_text"]].drop_duplicates("prompt_id")
    en = en.rename(columns={"prompt_text": "prompt_text_en"})
    merged = merged.merge(en, on="prompt_id", how="left", validate="many_to_one")

    # Per-prompt summaries use complete wall-to-wall v2.4 coverage.
    agg_fields = {
        "genuine_refusal": "genuine_refusal_propensity",
        "capability_failure": "capability_failure_propensity",
    }
    point_prompts = en.rename(columns={"prompt_text_en": "prompt_text"})
    points = coords.merge(
        point_prompts, on="prompt_id", how="left", validate="one_to_one"
    )
    if points["prompt_text"].isna().any():
        raise ValueError("one or more UMAP points lack English prompt text")
    for source, dest in agg_fields.items():
        if source in merged:
            a = merged.groupby("prompt_id", as_index=False)[source].mean().rename(columns={source: dest})
            points = points.merge(a, on="prompt_id", how="left", validate="one_to_one")
        else:
            points[dest] = pd.NA

    forbidden = [c for c in merged.columns if "reasoning" in c.lower() or "account" in c.lower() or "api_key" in c.lower()]
    if forbidden:
        raise ValueError(f"forbidden columns in app asset: {forbidden}")
    points.to_parquet(OUT / "umap_points.parquet", index=False)
    merged.to_parquet(OUT / "responses.parquet", index=False)
    meta = {
        "canonical_release": release_id,
        "release_status": release_status,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "row_counts": {"umap_points": len(points), "responses": len(merged),
                       "models": int(merged.model.nunique())},
        "hashes": {
            "release_manifest": sha256(release_manifest),
            "promoted_manifest": sha256(PROMOTED_MANIFEST),
            "umap_coordinates": sha256(coords_path),
            "data_clean": sha256(data_path),
            "umap_points": sha256(OUT / "umap_points.parquet"),
            "responses": sha256(OUT / "responses.parquet"),
        },
        "join_diagnostics": {"missing_response_text": 0, "duplicate_keys": 0,
                             "source_jsonl_files": len(source_paths)},
        "geometry": "fixed English-prompt c22 coordinates; never refitted",
    }
    (OUT / "build_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release",
        choices=sorted(RELEASE_CONTRACTS),
        help="build an explicitly approved release; defaults to the promoted release",
    )
    args = parser.parse_args()
    print(json.dumps(build(args.release), indent=2))
