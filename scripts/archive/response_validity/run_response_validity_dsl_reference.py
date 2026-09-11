#!/usr/bin/env python3
"""Price, run, and assemble the frozen GPT-5.6 Sol DSL reference sample.

``estimate`` is local and free. ``run`` is paid, resumable, requires the explicit
authorization flag, and enforces a provider-cost ceiling using completed usage
plus a worst-case reservation for every in-flight request.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import random
import threading
import time

import pandas as pd
import tiktoken
from openai import OpenAI, AuthenticationError, BadRequestError, PermissionDeniedError

from pilot_response_validity_v11 import (
    KEY, MODEL, SCHEMA, SYSTEM, derive, load_env, now, sha, user_message_template,
    validate_label,
)

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "annotations" / "response_validity_dsl_v1"
PILOT = ROOT / "annotations" / "response_validity_v11_pilot"
RAW = DESIGN / "sol_reference_labels.jsonl"
RUN_VERSION = "response-validity-dsl-reference-v1.0"
# OpenAI endpoint prices verified on the OpenRouter model page on 2026-08-19.
# The discounted endpoint is pinned in ``call``; Azure/Bedrock fallbacks are
# deliberately disabled because they do not share this promotional price.
INPUT_PRICE = 2.50
CACHE_READ_PRICE = 0.25
CACHE_WRITE_PRICE = 3.125
OUTPUT_PRICE = 15.0
# Ceiling reservations remain at the pre-discount OpenAI rates. Thus a price
# change during a resumable run cannot silently defeat the authorized ceiling.
RESERVE_INPUT_PRICE = 6.25
RESERVE_OUTPUT_PRICE = 30.0
MAX_OUTPUT_TOKENS = 700


def completed() -> dict:
    out = {}
    if not RAW.exists():
        return out
    for line_no, line in enumerate(RAW.read_text(encoding="utf-8").splitlines(), 1):
        try:
            rec = json.loads(line)
        except Exception as exc:
            raise ValueError(f"invalid raw record at line {line_no}") from exc
        if rec.get("status") == "ok":
            out[rec["reference_id"]] = rec
    return out


def message_tokens(row, encoding) -> int:
    user = user_message_template().format(
        prompt_language=row.prompt_language, prompt_text_en=row.prompt_text_en,
        prompt_text=row.prompt_text, response_text=row.response_text,
    )
    schema = json.dumps(SCHEMA, ensure_ascii=False, sort_keys=True)
    return len(encoding.encode(SYSTEM)) + len(encoding.encode(user)) + len(encoding.encode(schema))


def estimate() -> dict:
    universe = pd.read_parquet(DESIGN / "reference_universe.parquet")
    pilot = pd.read_parquet(PILOT / "assembled_pilot.parquet")
    encoding = tiktoken.get_encoding("o200k_base")
    reusable = universe[KEY + ["prompt_hash"]].merge(
        pilot[KEY + ["prompt_hash"]], on=KEY, suffixes=("_reference", "_pilot"),
        validate="one_to_one")
    reusable = reusable.loc[reusable.prompt_hash_reference.eq(reusable.prompt_hash_pilot)]
    reuse_keys = pd.MultiIndex.from_frame(reusable[KEY])
    needs_call = ~pd.MultiIndex.from_frame(universe[KEY]).isin(reuse_keys)
    call_frame = universe.loc[needs_call]
    raw_pilot = np_array([message_tokens(r, encoding) for r in pilot.itertuples(index=False)])
    actual_pilot = np_array([
        (u or {}).get("prompt_tokens", 0)
        for u in pilot.usage_run
    ])
    overhead = float((actual_pilot - raw_pilot).mean())
    raw_reference = sum(message_tokens(r, encoding) for r in call_frame.itertuples(index=False))
    expected_input = int(round(raw_reference + overhead * len(call_frame)))
    output_per_row = float(sum((u or {}).get("completion_tokens", 0)
                               for u in pilot.usage_run) / len(pilot))
    expected_output = int(round(output_per_row * len(call_frame)))
    pilot_prompt = sum((u or {}).get("prompt_tokens", 0) for u in pilot.usage_run)
    pilot_cache_write = sum(((u or {}).get("prompt_tokens_details") or {}).get(
        "cache_write_tokens", 0) or 0 for u in pilot.usage_run)
    pilot_cache_read = sum(((u or {}).get("prompt_tokens_details") or {}).get(
        "cached_tokens", 0) or 0 for u in pilot.usage_run)
    write_share = pilot_cache_write / pilot_prompt
    read_share = pilot_cache_read / pilot_prompt
    regular_share = max(0.0, 1.0 - write_share - read_share)
    expected_cache_write = int(round(expected_input * write_share))
    expected_cache_read = int(round(expected_input * read_share))
    expected_regular_input = expected_input - expected_cache_write - expected_cache_read
    expected = (
        expected_regular_input * INPUT_PRICE
        + expected_cache_read * CACHE_READ_PRICE
        + expected_cache_write * CACHE_WRITE_PRICE
        + expected_output * OUTPUT_PRICE
    ) / 1e6
    recommended = math_ceil(expected * 1.20)
    result = {
        "model": MODEL, "n_reference": len(universe),
        "n_reusable_exact_pilot_labels": len(reusable),
        "n_new_paid_calls": len(call_frame),
        "price_verified_2026_08_19_usd_per_million": {
            "provider": "openai", "discount": "50% off",
            "input": INPUT_PRICE, "cache_read": CACHE_READ_PRICE,
            "cache_write": CACHE_WRITE_PRICE, "output": OUTPUT_PRICE},
        "provider_routing": {"only": ["openai"], "allow_fallbacks": False},
        "pilot_calibration_n": len(pilot),
        "mean_prompt_token_overhead_vs_o200k_components": overhead,
        "pilot_mean_completion_tokens": output_per_row,
        "expected_prompt_tokens": expected_input,
        "pilot_prompt_token_billing_shares": {
            "regular_input": regular_share, "cache_read": read_share,
            "cache_write": write_share},
        "expected_regular_input_tokens": expected_regular_input,
        "expected_cache_read_tokens": expected_cache_read,
        "expected_cache_write_tokens": expected_cache_write,
        "expected_completion_tokens": expected_output,
        "expected_provider_cost_usd": expected,
        "recommended_hard_ceiling_usd": recommended,
        "reasoning": "disabled",
        "note": "Exact selected texts; input calibrated to actual pilot provider tokens and pilot cache-write/read shares; output uses actual pilot mean. OpenAI is pinned with fallbacks disabled. The ceiling adds 20% and rounds upward.",
    }
    (DESIGN / "sol_cost_estimate.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


def np_array(values):
    # Local helper avoids making numpy part of the public runner interface.
    import numpy as np
    return np.asarray(values, dtype=float)


def math_ceil(value):
    import math
    return int(math.ceil(value))


def call(client: OpenAI, row) -> dict:
    user = user_message_template().format(
        prompt_language=row.prompt_language, prompt_text_en=row.prompt_text_en,
        prompt_text=row.prompt_text, response_text=row.response_text,
    )
    started = time.time()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}],
        temperature=0, max_tokens=MAX_OUTPUT_TOKENS,
        response_format={"type": "json_schema", "json_schema": SCHEMA},
        extra_body={
            "reasoning": {"enabled": False},
            "provider": {"only": ["openai"], "allow_fallbacks": False},
        }, timeout=120,
    )
    raw_label = json.loads(response.choices[0].message.content)
    validation_repair = None
    try:
        label = validate_label(raw_label)
    except ValueError as exc:
        # The codebook states that unintelligible non-answering is not refusal.
        # Sol occasionally emits the forbidden combination incoherent/
        # unassessable + explicit/implicit even after repeated identical calls.
        # Apply only this predeclared conservative consistency rule, retain the
        # untouched model JSON below, and run the full validator again.
        if (
            str(exc) == "communicated noncompliance requires coherent/partly coherent output"
            and raw_label.get("coherence") in {"incoherent", "unassessable"}
            and raw_label.get("noncompliance_signal") in {"explicit", "implicit"}
        ):
            label = dict(raw_label)
            label["noncompliance_signal"] = (
                "unassessable" if label["coherence"] == "unassessable" else "none"
            )
            label["evidence_span"] = ""
            label = validate_label(label)
            validation_repair = {
                "rule": "v11_incoherent_output_cannot_communicate_noncompliance",
                "original_label": raw_label,
                "validation_error": str(exc),
            }
        else:
            raise
    return {
        "reference_id": row.reference_id,
        **{k: getattr(row, k) for k in KEY}, "prompt_hash": row.prompt_hash,
        "model_id": MODEL, "run_version": RUN_VERSION,
        "label": label, "derived": derive(label),
        "validation_repair": validation_repair,
        "usage": response.usage.model_dump() if response.usage else {},
        "incremental_provider_cost": float(
            (response.usage.model_dump() if response.usage else {}).get("cost") or 0),
        "reused_from_pilot": False,
        "provider_response_id": response.id, "provider_model": response.model,
        "elapsed_seconds": time.time() - started, "created_at": now(),
        "status": "ok",
    }


def seed_pilot() -> None:
    """Import byte-identical paid pilot labels for selected reference rows."""
    universe = pd.read_parquet(DESIGN / "reference_universe.parquet")
    pilot = pd.read_parquet(PILOT / "assembled_pilot.parquet")
    raw_pilot = {}
    for line in (PILOT / "sol_labels.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("status") == "ok":
            raw_pilot[rec["pilot_id"]] = rec
    overlap = universe.merge(
        pilot[["pilot_id", *KEY, "prompt_hash"]], on=KEY, how="inner",
        suffixes=("_reference", "_pilot"), validate="one_to_one")
    overlap = overlap.loc[overlap.prompt_hash_reference.eq(overlap.prompt_hash_pilot)]
    done = completed()
    imported = []
    for row in overlap.itertuples(index=False):
        if row.reference_id in done:
            continue
        old = raw_pilot[row.pilot_id]
        imported.append({
            **old, "reference_id": row.reference_id,
            "prompt_hash": row.prompt_hash_reference,
            "run_version": RUN_VERSION,
            "reused_from_pilot": True,
            "reused_pilot_id": row.pilot_id,
            "incremental_provider_cost": 0.0,
        })
    if imported:
        with RAW.open("a", encoding="utf-8") as handle:
            for rec in imported:
                handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps({"exact_overlap": len(overlap), "imported": len(imported),
                      "complete_after_import": len(completed())}, indent=2))


def run(workers: int, ceiling: float, authorized: bool) -> None:
    if not authorized:
        raise RuntimeError("paid reference run requires --authorize-paid-run")
    pricing = json.loads((DESIGN / "sol_cost_estimate.json").read_text())
    if pricing["expected_provider_cost_usd"] > ceiling:
        raise RuntimeError("expected provider cost exceeds the authorized ceiling")
    manifest_path = DESIGN / "reference_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("paid_run_authorized") is not True:
        # The manifest must be deliberately changed after user authorization;
        # a command-line flag alone cannot authorize a corpus-scale expense.
        raise RuntimeError("reference_manifest.json does not record paid authorization")
    if float(manifest.get("authorized_cost_ceiling_usd", -1)) != float(ceiling):
        raise RuntimeError("command ceiling differs from the recorded authorization")
    load_env()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    universe = pd.read_parquet(DESIGN / "reference_universe.parquet")
    encoding = tiktoken.get_encoding("o200k_base")
    done = completed()
    todo = [r for r in universe.itertuples(index=False) if r.reference_id not in done]
    spent = sum(float(r.get("incremental_provider_cost",
                            (r.get("usage") or {}).get("cost") or 0))
                for r in done.values())
    lock = threading.Lock()

    def one(row):
        for attempt in range(5):
            try:
                return call(client, row)
            except (AuthenticationError, PermissionDeniedError, BadRequestError):
                raise
            except Exception as exc:
                if attempt == 4:
                    return {"reference_id": row.reference_id, "status": "error",
                            "error_type": type(exc).__name__, "error": str(exc)[:500],
                            "created_at": now()}
                time.sleep(min(30, 2 ** attempt + random.random()))

    while todo:
        batch = todo[:workers]
        todo = todo[workers:]
        # Reserve the *undiscounted* cache-write price plus the full output
        # ceiling for every in-flight row. This remains conservative even if
        # the promotion ends while a resumable run is active.
        reserve = sum(
            (message_tokens(r, encoding) + 250) * RESERVE_INPUT_PRICE / 1e6
            + MAX_OUTPUT_TOKENS * RESERVE_OUTPUT_PRICE / 1e6 for r in batch
        )
        if spent + reserve > ceiling:
            raise RuntimeError(f"hard ceiling guard stopped before batch: spent={spent:.4f}")
        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            futures = [pool.submit(one, row) for row in batch]
            for future in as_completed(futures):
                rec = future.result()
                with lock, RAW.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
                spent += float(rec.get("incremental_provider_cost", 0))
        if len(completed()) % 100 == 0:
            print(f"Sol reference: {len(completed())}/{len(universe)}; ${spent:.2f}", flush=True)


def assemble() -> None:
    universe = pd.read_parquet(DESIGN / "reference_universe.parquet")
    records = list(completed().values())
    if len(records) != len(universe):
        raise ValueError(f"incomplete reference coverage: {len(records)}/{len(universe)}")
    rec = pd.DataFrame(records)
    labels = pd.json_normalize(rec.label).add_prefix("sol_")
    derived = pd.json_normalize(rec.derived).add_prefix("sol_")
    rec = pd.concat([rec.drop(columns=["label", "derived"]).reset_index(drop=True),
                     labels, derived], axis=1)
    out = universe.merge(rec, on=["reference_id", *KEY, "prompt_hash"],
                         validate="one_to_one", suffixes=("", "_run"))
    out = out.rename(columns={
        "sol_clean_genuine_refusal": "clean_genuine_refusal",
        "sol_capability_failure": "capability_failure",
        "sol_coherent_pivot": "coherent_pivot",
        "sol_refusal_communicated": "refusal_communicated",
    })
    out.to_parquet(DESIGN / "assembled_reference_labels.parquet", index=False)
    manifest_path = DESIGN / "reference_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["completion"] = {
        "assembled_at": now(), "n": len(out),
        "incremental_provider_reported_cost": sum(float(r.get(
            "incremental_provider_cost", (r.get("usage") or {}).get("cost") or 0))
            for r in records),
        "reused_pilot_rows": sum(bool(r.get("reused_from_pilot")) for r in records),
        "reasoning_tokens": sum(int(((r.get("usage") or {}).get(
            "completion_tokens_details") or {}).get("reasoning_tokens") or 0)
            for r in records),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["seed-pilot", "estimate", "run", "assemble"])
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--cost-ceiling", type=float)
    parser.add_argument("--authorize-paid-run", action="store_true")
    args = parser.parse_args()
    if args.stage == "seed-pilot":
        seed_pilot()
    elif args.stage == "estimate":
        estimate()
    elif args.stage == "run":
        if args.cost_ceiling is None:
            raise RuntimeError("--cost-ceiling is required")
        run(args.workers, args.cost_ceiling, args.authorize_paid_run)
    else:
        assemble()


if __name__ == "__main__":
    main()
