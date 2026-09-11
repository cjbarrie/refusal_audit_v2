#!/usr/bin/env python3
"""Repair singleton phase-two strata without altering the frozen v1.0 design.

The completed v1.0 reference design is immutable. This script creates v1.1 by
drawing one additional control uniformly from the remaining units in every
noncensus stratum whose original sample size was one. Sequential SRS(1) then
SRS(1) from the remainder is exactly SRS(2), so final inclusion is 2/N.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import random
import threading
import time

import pandas as pd
import tiktoken
from openai import OpenAI, AuthenticationError, BadRequestError, PermissionDeniedError

from pilot_response_validity_v11 import KEY, load_env, now
from response_validity_dsl import OUTCOMES, SEED as V10_SEED, frame_hash
from run_response_validity_dsl_reference import (
    CACHE_READ_PRICE, CACHE_WRITE_PRICE, INPUT_PRICE, MAX_OUTPUT_TOKENS, MODEL,
    OUTPUT_PRICE, RESERVE_INPUT_PRICE, RESERVE_OUTPUT_PRICE, call as sol_call,
    message_tokens,
)

ROOT = Path(__file__).resolve().parents[1]
V10 = ROOT / "annotations" / "response_validity_dsl_v1"
OUT = ROOT / "annotations" / "response_validity_dsl_v1_1"
RAW = OUT / "sol_augmentation_labels.jsonl"
SEED = 20260820
RUN_VERSION = "response-validity-dsl-reference-v1.1-singleton-repair"
STRATA = ["model", "prompt_language", "home_status", "engagement_code"]


def sha_bytes(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def completed() -> dict:
    out = {}
    if not RAW.exists():
        return out
    for line_no, line in enumerate(RAW.read_text(encoding="utf-8").splitlines(), 1):
        try:
            rec = json.loads(line)
        except Exception as exc:
            raise ValueError(f"invalid augmentation record at line {line_no}") from exc
        if rec.get("status") == "ok":
            out[rec["reference_id"]] = rec
    return out


def prepare() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(V10 / "wall_to_wall_features.parquet")
    original = pd.read_parquet(V10 / "reference_universe.parquet")
    alloc = pd.read_csv(V10 / "reference_allocation.csv")
    target = alloc.loc[alloc.n.eq(1) & alloc.N.gt(1), STRATA + ["N"]].copy()
    target = target.rename(columns={"N": "repair_N"})
    if len(target) != 207:
        raise ValueError(f"expected 207 noncensus singleton strata, found {len(target)}")

    candidates = frame.loc[frame.engagement_code.lt(4)].merge(
        target, on=STRATA, how="inner", validate="many_to_one")
    used = pd.MultiIndex.from_frame(original[KEY])
    candidates = candidates.loc[~pd.MultiIndex.from_frame(candidates[KEY]).isin(used)]
    rng = random.Random(SEED)
    rows = []
    for stratum, group in candidates.sort_values(KEY).groupby(STRATA, sort=True, dropna=False):
        if len(group) != int(group.repair_N.iloc[0]) - 1:
            raise ValueError(f"remaining-frame mismatch for {stratum}")
        rows.append(group.iloc[rng.randrange(len(group))])
    augmentation = pd.DataFrame(rows)
    augmentation["N"] = augmentation["repair_N"]
    augmentation = augmentation.drop(columns=["repair_N"])
    if len(augmentation) != 207 or augmentation.duplicated(KEY).any():
        raise ValueError("augmentation must contain 207 unique response keys")
    augmentation["reference_id"] = [
        hashlib.sha256("\0".join(map(str, k)).encode()).hexdigest()[:24]
        for k in augmentation[KEY].itertuples(index=False, name=None)
    ]
    augmentation["reference_stratum"] = "singleton_variance_repair_control"
    # These two allocation-only scores were used to choose v1.0 sample sizes,
    # not to draw the label-blind singleton repair. They are intentionally NA
    # for added rows and never enter the reference outcome.
    augmentation["provisional_risk"] = float("nan")
    augmentation["allocation_leverage"] = float("nan")
    augmentation["n"] = 2
    augmentation["inclusion_probability"] = 2 / augmentation["N"]
    augmentation["sampling_weight"] = augmentation["N"] / 2

    combined = pd.concat([original, augmentation[original.columns]], ignore_index=True)
    target_key = target.assign(_repair=True)
    combined = combined.merge(target_key[STRATA + ["_repair"]], on=STRATA, how="left")
    repaired = combined._repair.fillna(False)
    combined.loc[repaired, "n"] = 2
    combined.loc[repaired, "inclusion_probability"] = 2 / combined.loc[repaired, "N"]
    combined.loc[repaired, "sampling_weight"] = combined.loc[repaired, "N"] / 2
    combined = combined.drop(columns="_repair")
    if len(combined) != 14182 or combined.duplicated(KEY).any():
        raise ValueError("augmented reference must contain 14,182 unique keys")
    if ((combined.N > 1) & (combined.n < 2)).any():
        raise ValueError("noncensus singleton remains after repair")

    augmentation.to_parquet(OUT / "augmentation_universe.parquet", index=False)
    combined.to_parquet(OUT / "reference_universe.parquet", index=False)
    original_manifest = json.loads((V10 / "reference_manifest.json").read_text())
    manifest = {
        "version": "response-validity-dsl-v1.1-singleton-variance-repair",
        "created_at": now(), "seed": SEED,
        "parent_version": original_manifest["version"],
        "parent_reference_key_sha256": original_manifest["reference_key_sha256"],
        "selection": "one uniform remaining control in every v1.0 noncensus stratum with n=1",
        "selection_uses_labels": False,
        "strata": STRATA,
        "n_parent_reference": len(original), "n_added": len(augmentation),
        "n_reference_total": len(combined), "n_population": original_manifest["n_population"],
        "frame_key_sha256": original_manifest["frame_key_sha256"],
        "reference_key_sha256": frame_hash(combined),
        "augmentation_key_sha256": frame_hash(augmentation),
        "parent_reference_artifact_sha256": sha_bytes(V10 / "reference_universe.parquet"),
        "paid_run_authorized": True,
        "authorized_cumulative_cost_ceiling_usd": 95.0,
        "parent_incremental_cost_usd": original_manifest["completion"]["incremental_provider_reported_cost"],
        "provider_restriction": {"only": ["openai"], "allow_fallbacks": False},
    }
    (OUT / "reference_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


def estimate() -> None:
    aug = pd.read_parquet(OUT / "augmentation_universe.parquet")
    encoding = tiktoken.get_encoding("o200k_base")
    prompt = sum(message_tokens(r, encoding) for r in aug.itertuples(index=False))
    # Pilot/provider accounting shows most tokens are cache writes. Charging
    # every prompt token at the higher cache-write price is conservative.
    expected = prompt * CACHE_WRITE_PRICE / 1e6 + len(aug) * 72 * OUTPUT_PRICE / 1e6
    result = {
        "model": MODEL, "n_new_paid_calls": len(aug),
        "expected_prompt_tokens": prompt, "assumed_completion_tokens_per_row": 72,
        "conservative_expected_incremental_cost_usd": expected,
        "prices_usd_per_million": {"input": INPUT_PRICE, "cache_read": CACHE_READ_PRICE,
                                   "cache_write": CACHE_WRITE_PRICE, "output": OUTPUT_PRICE},
        "provider_routing": {"only": ["openai"], "allow_fallbacks": False},
    }
    (OUT / "sol_cost_estimate.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def run(workers: int, ceiling: float, authorized: bool) -> None:
    if not authorized:
        raise RuntimeError("paid augmentation requires --authorize-paid-run")
    manifest = json.loads((OUT / "reference_manifest.json").read_text())
    if not manifest.get("paid_run_authorized"):
        raise RuntimeError("augmentation manifest lacks paid authorization")
    if float(manifest["authorized_cumulative_cost_ceiling_usd"]) != float(ceiling):
        raise RuntimeError("command ceiling differs from augmentation manifest")
    load_env()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    aug = pd.read_parquet(OUT / "augmentation_universe.parquet")
    done = completed()
    todo = [r for r in aug.itertuples(index=False) if r.reference_id not in done]
    spent = float(manifest["parent_incremental_cost_usd"]) + sum(
        float(r.get("incremental_provider_cost", 0)) for r in done.values())
    encoding = tiktoken.get_encoding("o200k_base")
    lock = threading.Lock()

    def one(row):
        for attempt in range(5):
            try:
                rec = sol_call(client, row)
                rec["run_version"] = RUN_VERSION
                return rec
            except (AuthenticationError, PermissionDeniedError, BadRequestError):
                raise
            except Exception as exc:
                if attempt == 4:
                    return {"reference_id": row.reference_id, "status": "error",
                            "error_type": type(exc).__name__, "error": str(exc)[:500],
                            "created_at": now()}
                time.sleep(min(30, 2 ** attempt + random.random()))

    while todo:
        batch, todo = todo[:workers], todo[workers:]
        reserve = sum((message_tokens(r, encoding) + 250) * RESERVE_INPUT_PRICE / 1e6
                      + MAX_OUTPUT_TOKENS * RESERVE_OUTPUT_PRICE / 1e6 for r in batch)
        if spent + reserve > ceiling:
            raise RuntimeError(f"cumulative hard ceiling stopped augmentation: spent={spent:.4f}")
        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            futures = [pool.submit(one, row) for row in batch]
            for future in as_completed(futures):
                rec = future.result()
                with lock, RAW.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
                spent += float(rec.get("incremental_provider_cost", 0))
        print(f"Sol augmentation: {len(completed())}/{len(aug)}; cumulative ${spent:.2f}", flush=True)


def assemble() -> None:
    combined = pd.read_parquet(OUT / "reference_universe.parquet")
    original = pd.read_parquet(V10 / "assembled_reference_labels.parquet")
    records = list(completed().values())
    if len(records) != 207:
        raise ValueError(f"augmentation coverage incomplete: {len(records)}/207")
    rec = pd.DataFrame(records)
    labels = pd.json_normalize(rec.label).add_prefix("sol_")
    derived = pd.json_normalize(rec.derived).add_prefix("sol_")
    rec = pd.concat([rec.drop(columns=["label", "derived"]).reset_index(drop=True),
                     labels, derived], axis=1)
    new = rec.rename(columns={
        "sol_clean_genuine_refusal": "clean_genuine_refusal",
        "sol_capability_failure": "capability_failure",
        "sol_coherent_pivot": "coherent_pivot",
        "sol_refusal_communicated": "refusal_communicated",
    })
    outcome_cols = [*OUTCOMES, "refusal_communicated"]
    all_labels = pd.concat([original[KEY + outcome_cols], new[KEY + outcome_cols]], ignore_index=True)
    if all_labels.duplicated(KEY).any():
        raise ValueError("duplicate combined reference label key")
    assembled = combined.merge(all_labels, on=KEY, validate="one_to_one")
    assembled.to_parquet(OUT / "assembled_reference_labels.parquet", index=False)
    manifest_path = OUT / "reference_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["completion"] = {
        "assembled_at": now(), "n_added": len(records), "n_total": len(assembled),
        "augmentation_incremental_provider_cost": sum(float(r.get("incremental_provider_cost", 0)) for r in records),
        "cumulative_incremental_provider_cost": manifest["parent_incremental_cost_usd"] + sum(float(r.get("incremental_provider_cost", 0)) for r in records),
        "reasoning_tokens": sum(int(((r.get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens") or 0) for r in records),
        "validation_repairs": sum(r.get("validation_repair") is not None for r in records),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest["completion"], indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "estimate", "run", "assemble"])
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--cost-ceiling", type=float, default=95.0)
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.stage == "prepare": prepare()
    elif args.stage == "estimate": estimate()
    elif args.stage == "run": run(args.workers, args.cost_ceiling, args.authorize_paid_run)
    else: assemble()


if __name__ == "__main__":
    main()
