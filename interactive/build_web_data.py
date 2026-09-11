#!/usr/bin/env python3
"""Build static, browser-safe assets for the refusal observatory.

The standalone site reuses the current local explorer's manifest-verified
response table and canonical two-dimensional UMAP. It additionally fits one
fixed three-dimensional UMAP to the same frozen English-prompt embeddings.
Outcomes never enter either geometry. The 3-D map is an exploratory locator,
not an estimand, and is never refit after filtering.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTERACTIVE = ROOT / "interactive"
SOURCE = INTERACTIVE / "data"
OUT = INTERACTIVE / "web" / "public" / "data"
EMBEDDINGS = ROOT / "data" / "prompt_embeddings_en.csv.gz"
SEED = 20260809
N_NEIGHBORS = 25
MIN_DIST = 0.15


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fit_three_dimensions(prompt_ids: list[str]) -> pd.DataFrame:
    """Fit a single outcome-blind 3-D UMAP in the supplied prompt order."""
    with tempfile.TemporaryDirectory(prefix="refusal_observatory_") as directory:
        directory = Path(directory)
        order_path = directory / "prompt_order.csv"
        output_path = directory / "umap_3d.csv"
        pd.DataFrame({"prompt_id": prompt_ids}).to_csv(order_path, index=False)
        code = f"""
        suppressPackageStartupMessages(library(readr))
        stopifnot(requireNamespace('uwot', quietly = TRUE))
        E <- read_csv('{EMBEDDINGS}', show_col_types = FALSE)
        O <- read_csv('{order_path}', show_col_types = FALSE)
        stopifnot(!anyDuplicated(E$prompt_id), !anyDuplicated(O$prompt_id),
                  nrow(O) == 2496L, setequal(E$prompt_id, O$prompt_id))
        E <- E[match(O$prompt_id, E$prompt_id), ]
        X <- as.matrix(E[, setdiff(names(E), 'prompt_id'), drop = FALSE])
        stopifnot(ncol(X) == 512L, all(is.finite(X)))
        X <- X / sqrt(rowSums(X^2))
        set.seed({SEED})
        fit <- uwot::umap(X, n_neighbors = {N_NEIGHBORS},
                          min_dist = {MIN_DIST}, metric = 'cosine',
                          n_components = 3, verbose = FALSE)
        write_csv(data.frame(prompt_id = O$prompt_id,
                             umap_3d_x = fit[,1], umap_3d_y = fit[,2],
                             umap_3d_z = fit[,3]), '{output_path}')
        """
        subprocess.run(["Rscript", "-e", code], cwd=ROOT, check=True)
        return pd.read_csv(output_path)


def clean(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def records(frame: pd.DataFrame) -> list[dict]:
    return [
        {key: clean(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def build() -> dict:
    source_manifest_path = SOURCE / "build_metadata.json"
    points_path = SOURCE / "umap_points.parquet"
    responses_path = SOURCE / "responses.parquet"
    for path in (source_manifest_path, points_path, responses_path, EMBEDDINGS):
        if not path.exists():
            raise FileNotFoundError(path)

    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if sha256(points_path) != source_manifest["hashes"]["umap_points"]:
        raise ValueError("source UMAP-point hash differs from build metadata")
    if sha256(responses_path) != source_manifest["hashes"]["responses"]:
        raise ValueError("source response hash differs from build metadata")

    points = pd.read_parquet(points_path)
    responses = pd.read_parquet(responses_path)
    if len(points) != 2496 or points.prompt_id.duplicated().any():
        raise ValueError("expected exactly 2,496 unique prompt points")
    if responses.duplicated(["prompt_id", "prompt_language", "model"]).any():
        raise ValueError("response table contains duplicate canonical keys")

    coords_3d = fit_three_dimensions(points.prompt_id.astype(str).tolist())
    points = points.merge(coords_3d, on="prompt_id", how="left", validate="one_to_one")
    if points[["umap_3d_x", "umap_3d_y", "umap_3d_z"]].isna().any().any():
        raise ValueError("one or more prompts lack 3-D coordinates")

    prompt_columns = [
        "prompt_id", "prompt_text", "issue_id", "domain", "region_focus",
        "tier", "route", "prompt_origin_language", "umap_x", "umap_y",
        "umap_3d_x", "umap_3d_y", "umap_3d_z",
    ]
    prompts = points[prompt_columns].copy()

    refusal_columns = [
        "prompt_id", "prompt_language", "model", "developer_jurisdiction",
        "prompt_text", "prompt_text_en", "response_text", "topic_domain",
        "region_focus", "controversy_tier", "route", "position_side",
        "prompt_origin_language", "prompt_origin_form", "task_behavior",
        "substantive_refusal", "stance_disclaimer", "epistemic_limitation",
        "language_fidelity", "output_quality", "technical_failure",
        "confidence", "refusal_evidence_span", "annotation_source",
    ]
    refusals = responses.loc[responses.genuine_refusal, refusal_columns].copy()
    if len(refusals) != int(responses.genuine_refusal.sum()):
        raise ValueError("refusal export does not match the source outcome")

    OUT.mkdir(parents=True, exist_ok=True)
    prompts_out = OUT / "prompts.json"
    refusals_out = OUT / "refusals.json"
    prompts_out.write_text(
        json.dumps(records(prompts), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    refusals_out.write_text(
        json.dumps(records(refusals), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    metadata = {
        "version": "refusal-observatory-web-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "canonical_release": source_manifest["canonical_release"],
        "counts": {
            "prompts": len(prompts),
            "responses": len(responses),
            "genuine_refusals": len(refusals),
            "models": int(responses.model.nunique()),
            "languages": int(responses.prompt_language.nunique()),
        },
        "geometry_2d": source_manifest["geometry"],
        "geometry_3d": {
            "role": "exploratory locator only; outcomes do not enter the fit",
            "embedding_file": str(EMBEDDINGS.relative_to(ROOT)),
            "embedding_sha256": sha256(EMBEDDINGS),
            "dimensions": 512,
            "implementation": "R uwot",
            "n_components": 3,
            "seed": SEED,
            "n_neighbors": N_NEIGHBORS,
            "min_dist": MIN_DIST,
            "metric": "cosine",
        },
        "source_hashes": {
            "interactive_build_metadata": sha256(source_manifest_path),
            "umap_points_parquet": sha256(points_path),
            "responses_parquet": sha256(responses_path),
        },
        "output_hashes": {
            "prompts_json": sha256(prompts_out),
            "refusals_json": sha256(refusals_out),
        },
        "privacy": "genuine-refusal response text only; no credentials or reasoning traces",
    }
    metadata_out = OUT / "metadata.json"
    metadata_out.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
