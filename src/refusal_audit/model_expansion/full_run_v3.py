"""Freeze and cost the approved-cell OpenRouter expansion.

This module makes no network calls. It turns the final cell registry into seven
separately authorizable provider payloads while enforcing the original prompt
files, one-user-message request structure, route pins, and generation settings.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import fcntl
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from .openrouter_pilot import (
    _call, _is_transient, _load_prompts, read_jsonl, sha_file, sha_object,
    write_jsonl,
)


ROSTER_PATH = Path("config/model_rosters/openrouter_expansion_v3_cell_approved.json")
DEFAULT_DIR = Path("annotations/model_expansion_v3/full_run_v1")
V31_ROSTER_PATH = Path("config/model_rosters/openrouter_expansion_v3_1_all_languages.json")
V31_HUNYUAN_DIR = Path("annotations/model_expansion_v3/hunyuan_all_languages_v3_1")
LANGUAGES = ("en", "zh", "ar", "ru", "hi")
EXPECTED_CELLS = 33
PROMPTS_PER_CELL = 2496
EXPECTED_REQUESTS = EXPECTED_CELLS * PROMPTS_PER_CELL


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_jsonl(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _planning_token_count(text: str) -> int:
    """Fixed o200k planning count; provider billing remains authoritative."""
    try:
        import tiktoken
    except ImportError as exc:
        raise RuntimeError("tiktoken is required to reproduce the frozen v3 payload") from exc
    return len(tiktoken.get_encoding("o200k_base").encode(text))


def _load_design(root: Path) -> tuple[dict, dict, Dict[str, Dict[str, dict]]]:
    spec_path = root / ROSTER_PATH
    spec = _read_json(spec_path)
    if spec.get("provider_calls_authorized") is not False:
        raise ValueError("v3 roster must remain setup-only")
    base_ref = spec["base_route_roster"]
    base_path = root / base_ref["path"]
    if sha_file(base_path) != base_ref["sha256"]:
        raise ValueError("base route roster hash mismatch")
    base = _read_json(base_path)
    registry_ref = spec["cell_registry"]
    registry_path = root / registry_ref["path"]
    if sha_file(registry_path) != registry_ref["sha256"]:
        raise ValueError("final cell registry hash mismatch")

    model_by_name = {m["name"]: m for m in base["models"]}
    approved = spec["approved_cells"]
    if set(approved) != set(spec["stage_order"]):
        raise ValueError("stage order and approved model set differ")
    for name, languages in approved.items():
        if name not in model_by_name:
            raise ValueError(f"approved model absent from base roster: {name}")
        if len(languages) != len(set(languages)) or not set(languages) <= set(LANGUAGES):
            raise ValueError(f"invalid language list for {name}")
        model = model_by_name[name]
        if model.get("provider") != "openrouter":
            raise ValueError(f"non-OpenRouter model entered v3: {name}")
        route = model["provider_routing"]
        if route.get("allow_fallbacks") is not False:
            raise ValueError(f"fallbacks enabled for {name}")
        if route.get("only") != [model.get("selected_provider_tag")]:
            raise ValueError(f"route is not singly pinned for {name}")
        if float(model["temperature"]) != 1.0 or int(model["max_tokens"]) != 5000:
            raise ValueError(f"generation settings changed for {name}")

    registry = pd.read_csv(registry_path)
    observed = {
        (str(r.subject_model), str(r.prompt_language))
        for r in registry.itertuples() if r.cell_decision == "approved"
    }
    declared = {(name, lang) for name, langs in approved.items() for lang in langs}
    if observed != declared or len(declared) != EXPECTED_CELLS:
        raise ValueError("v3 approved cells do not exactly match final registry")

    # _load_prompts verifies all five file hashes, counts, and shared prompt IDs.
    prompts = _load_prompts(root, base)
    spec["_sha256"] = sha_file(spec_path)
    base["_sha256"] = sha_file(base_path)
    return spec, base, prompts


def _request(model: dict, prompt: dict, language: str) -> dict:
    logical = {
        "run_version": "openrouter-expansion-v3-full-run-v1",
        "prompt_id": prompt["id"],
        "prompt_language": language,
        "model": model["name"],
    }
    text = prompt["text"]
    return {
        **logical,
        "provider_request_id": sha_object(logical)[:24],
        "messages": [{"role": "user", "content": text}],
        "prompt_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "estimated_input_tokens": _planning_token_count(text),
        "model_id": model["model_id"],
        "canonical_slug": model["canonical_slug"],
        "developer": model["developer"],
        "developer_jurisdiction": model["developer_jurisdiction"],
        "provider_name": model["selected_provider_name"],
        "provider_tag": model["selected_provider_tag"],
        "provider": model["provider_routing"],
        "reasoning": model["reasoning"],
        "temperature": model["temperature"],
        "max_output_tokens": model["max_tokens"],
        "input_usd_per_million": model["input_usd_per_million"],
        "output_usd_per_million": model["output_usd_per_million"],
        "prompt_metadata": {
            key: prompt.get(key) for key in (
                "issue_id", "qid", "topic_domain", "controversy_tier",
                "region_focus", "position_side", "route", "battery",
                "prompt_origin_language", "prompt_origin_form",
            )
        },
    }


def prepare_full_run(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    spec, base, prompts = _load_design(root)
    input_hashes = {
        "v3_roster": spec["_sha256"],
        "base_route_roster": base["_sha256"],
        "final_cell_registry": spec["cell_registry"]["sha256"],
        **{
            f"prompt_{lang}": base["design"]["prompt_files"][lang]["sha256"]
            for lang in LANGUAGES
        },
    }
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen v3 run no longer matches its inputs")
        for stage in manifest["stages"]:
            path = output_dir / stage["payload_path"]
            if not path.exists() or sha_file(path) != stage["payload_sha256"]:
                raise ValueError(f"frozen stage changed: {stage['model']}")
        return manifest

    model_by_name = {m["name"]: m for m in base["models"]}
    output_dir.mkdir(parents=True, exist_ok=False)
    stages = []
    all_ids: set[str] = set()
    total = 0
    for order, name in enumerate(spec["stage_order"], start=1):
        model = model_by_name[name]
        rows = []
        languages = spec["approved_cells"][name]
        for language in LANGUAGES:
            if language not in languages:
                continue
            for prompt_id in sorted(prompts[language]):
                rows.append(_request(model, prompts[language][prompt_id], language))
        expected = PROMPTS_PER_CELL * len(languages)
        if len(rows) != expected:
            raise ValueError(f"wrong request count for {name}")
        ids = {r["provider_request_id"] for r in rows}
        if len(ids) != expected or all_ids.intersection(ids):
            raise ValueError("provider request IDs are not globally unique")
        all_ids.update(ids)
        payload_name = f"stage_{order:02d}_{name}_provider_requests.jsonl"
        payload_path = output_dir / payload_name
        _write_jsonl(payload_path, rows)
        stages.append({
            "stage": order,
            "model": name,
            "languages": languages,
            "n_cells": len(languages),
            "n_requests": expected,
            "payload_path": payload_name,
            "payload_sha256": sha_file(payload_path),
            "paid_run_authorized": False,
            "network_inference_call_made": False,
        })
        total += expected
    if total != EXPECTED_REQUESTS or len(all_ids) != EXPECTED_REQUESTS:
        raise ValueError("v3 full-run request universe is not exactly 82,368")

    manifest = {
        "version": "openrouter-expansion-v3-full-run-v1",
        "created_at": _now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": "primary expansion of approved model-language cells",
        "generation_contract": spec["generation_contract"],
        "n_models": len(stages),
        "n_cells": EXPECTED_CELLS,
        "prompts_per_cell": PROMPTS_PER_CELL,
        "n_requests": total,
        "input_sha256": input_hashes,
        "stages": stages,
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_full_run_cost(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare_full_run(root, output_dir)
    planning_output = int(manifest["generation_contract"]["planning_output_tokens"])
    stages = []
    for stage in manifest["stages"]:
        # A prior cost pass may have attached a nested cost record to the
        # manifest. Strip it before recomputation so repeated checks are stable.
        stage = {key: value for key, value in stage.items() if key != "cost"}
        path = output_dir / stage["payload_path"]
        n = input_tokens = 0
        planning = reserved = 0.0
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                n += 1
                input_tokens += int(row["estimated_input_tokens"])
                planning += (
                    row["estimated_input_tokens"] * row["input_usd_per_million"]
                    + planning_output * row["output_usd_per_million"]
                ) / 1_000_000
                reserved += (
                    row["estimated_input_tokens"] * row["input_usd_per_million"]
                    + row["max_output_tokens"] * row["output_usd_per_million"]
                ) / 1_000_000
        if n != stage["n_requests"]:
            raise ValueError(f"cost pass count mismatch for {stage['model']}")
        # The ceiling is a stop-loss, not a prediction: 50% above the exact
        # 1,500-output-token plan, rounded upward to the next 50 cents.
        ceiling = math.ceil(planning * 1.5 * 2) / 2
        stages.append({
            **stage,
            "estimated_input_tokens": input_tokens,
            "planning_output_tokens_per_request": planning_output,
            "planning_cost_usd": planning,
            "single_attempt_5000_token_reservation_usd": reserved,
            "suggested_hard_ceiling_usd": ceiling,
        })
    result = {
        "version": "openrouter-expansion-v3-full-run-cost-v1",
        "created_at": _now(),
        "pricing_verified_at": "2026-09-02",
        "pricing_source": "hash-locked base roster routes used by the completed pilot",
        "n_requests": sum(s["n_requests"] for s in stages),
        "estimated_input_tokens": sum(s["estimated_input_tokens"] for s in stages),
        "planning_cost_usd": sum(s["planning_cost_usd"] for s in stages),
        "single_attempt_5000_token_reservation_usd": sum(
            s["single_attempt_5000_token_reservation_usd"] for s in stages
        ),
        "sum_of_stage_hard_ceilings_usd": sum(
            s["suggested_hard_ceiling_usd"] for s in stages
        ),
        "ceiling_rule": "ceil_to_$0.50(1.5 * exact-input-plus-1500-output-token planning cost)",
        "stages": stages,
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    cost_path = output_dir / "cost_estimate.json"
    cost_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    latest = _read_json(output_dir / "manifest.json")
    latest["status"] = "frozen_costed_not_authorized"
    latest["cost_estimate_sha256"] = sha_file(cost_path)
    latest["stages"] = [
        {**stage, "cost": next(s for s in stages if s["model"] == stage["model"])}
        for stage in latest["stages"]
    ]
    (output_dir / "manifest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")
    return result


def prepare_hunyuan_all_languages_revision(
    root: Path, output_dir: Path | None = None
) -> dict:
    """Freeze the five-language Hunyuan replacement for the unrun v3 stage 4."""
    output_dir = output_dir or root / V31_HUNYUAN_DIR
    spec_path = root / V31_ROSTER_PATH
    spec = _read_json(spec_path)
    if spec.get("provider_calls_authorized") is not False:
        raise ValueError("v3.1 roster must remain setup-only")
    base_ref = spec["base_route_roster"]
    base_path = root / base_ref["path"]
    registry_ref = spec["cell_registry"]
    registry_path = root / registry_ref["path"]
    if sha_file(base_path) != base_ref["sha256"]:
        raise ValueError("v3.1 base route roster hash mismatch")
    if sha_file(registry_path) != registry_ref["sha256"]:
        raise ValueError("v3.1 final registry hash mismatch")
    registry = pd.read_csv(registry_path)
    retained = registry.loc[registry.cell_decision.isin(["approved", "conditional"])]
    if len(retained) != 35:
        raise ValueError("v3.1 registry does not contain 35 retained cells")
    conditional = set(
        zip(
            registry.loc[registry.cell_decision.eq("conditional"), "subject_model"],
            registry.loc[registry.cell_decision.eq("conditional"), "prompt_language"],
        )
    )
    if conditional != {("hunyuan-a13b", "en"), ("hunyuan-a13b", "ru")}:
        raise ValueError("unexpected conditional-cell set")
    base = _read_json(base_path)
    prompts = _load_prompts(root, base)
    model_matches = [m for m in base["models"] if m["name"] == "hunyuan-a13b"]
    if len(model_matches) != 1:
        raise ValueError("Hunyuan route is absent or duplicated")
    model = model_matches[0]
    route = model["provider_routing"]
    if (
        model.get("provider") != "openrouter"
        or route.get("allow_fallbacks") is not False
        or route.get("only") != [model.get("selected_provider_tag")]
        or float(model["temperature"]) != 1.0
        or int(model["max_tokens"]) != 5000
    ):
        raise ValueError("Hunyuan route or generation contract changed")

    input_hashes = {
        "v3_1_roster": sha_file(spec_path),
        "base_route_roster": sha_file(base_path),
        "final_cell_registry": sha_file(registry_path),
        **{
            f"prompt_{lang}": base["design"]["prompt_files"][lang]["sha256"]
            for lang in LANGUAGES
        },
    }
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen Hunyuan revision no longer matches its inputs")
        stage = manifest["stages"][0]
        if sha_file(output_dir / stage["payload_path"]) != stage["payload_sha256"]:
            raise ValueError("frozen Hunyuan revision payload changed")
        return manifest

    rows = []
    for language in LANGUAGES:
        for prompt_id in sorted(prompts[language]):
            rows.append(_request(model, prompts[language][prompt_id], language))
    expected = len(LANGUAGES) * PROMPTS_PER_CELL
    if len(rows) != expected or len({r["provider_request_id"] for r in rows}) != expected:
        raise ValueError("Hunyuan v3.1 payload is not 12,480 unique requests")
    output_dir.mkdir(parents=True, exist_ok=False)
    payload_name = "stage_04_hunyuan-a13b_all_languages_provider_requests.jsonl"
    payload_path = output_dir / payload_name
    _write_jsonl(payload_path, rows)
    manifest = {
        "version": "openrouter-expansion-v3.1-hunyuan-all-languages",
        "created_at": _now(),
        "status": "frozen_unpriced_not_authorized",
        "scientific_role": (
            "replacement for unrun v3 stage 4; adds conditional English and "
            "Russian cells without changing prompts or generation settings"
        ),
        "overall_expansion_after_revision": {
            "n_models": 7, "n_cells": 35, "n_requests": 87360,
        },
        "generation_contract": spec["generation_contract"],
        "input_sha256": input_hashes,
        "stages": [{
            "stage": 4,
            "model": "hunyuan-a13b",
            "languages": list(LANGUAGES),
            "cell_status": {
                "en": "conditional_retained", "zh": "approved",
                "ar": "approved", "ru": "conditional_retained", "hi": "approved",
            },
            "n_cells": 5,
            "n_requests": expected,
            "payload_path": payload_name,
            "payload_sha256": sha_file(payload_path),
            "paid_run_authorized": False,
            "network_inference_call_made": False,
        }],
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_hunyuan_revision_cost(
    root: Path, output_dir: Path | None = None
) -> dict:
    output_dir = output_dir or root / V31_HUNYUAN_DIR
    manifest = prepare_hunyuan_all_languages_revision(root, output_dir)
    stage = {k: v for k, v in manifest["stages"][0].items() if k != "cost"}
    planning_output = int(manifest["generation_contract"]["planning_output_tokens"])
    input_tokens = n = 0
    planning = reserved = 0.0
    with (output_dir / stage["payload_path"]).open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line); n += 1
            input_tokens += int(row["estimated_input_tokens"])
            planning += (
                row["estimated_input_tokens"] * row["input_usd_per_million"]
                + planning_output * row["output_usd_per_million"]
            ) / 1_000_000
            reserved += (
                row["estimated_input_tokens"] * row["input_usd_per_million"]
                + row["max_output_tokens"] * row["output_usd_per_million"]
            ) / 1_000_000
    if n != 5 * PROMPTS_PER_CELL:
        raise ValueError("Hunyuan revision cost pass count mismatch")
    ceiling = math.ceil(planning * 1.5 * 2) / 2
    cost = {
        **stage,
        "estimated_input_tokens": input_tokens,
        "planning_output_tokens_per_request": planning_output,
        "planning_cost_usd": planning,
        "single_attempt_5000_token_reservation_usd": reserved,
        "suggested_hard_ceiling_usd": ceiling,
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    cost_path = output_dir / "cost_estimate.json"
    cost_path.write_text(json.dumps(cost, indent=2), encoding="utf-8")
    latest = _read_json(output_dir / "manifest.json")
    latest["status"] = "frozen_costed_not_authorized"
    latest["cost_estimate_sha256"] = sha_file(cost_path)
    latest["stages"][0]["cost"] = cost
    (output_dir / "manifest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")
    return cost


def _find_stage(manifest: dict, stage_number: int) -> dict:
    matches = [stage for stage in manifest["stages"] if stage["stage"] == stage_number]
    if len(matches) != 1:
        raise ValueError(f"stage {stage_number} is absent or duplicated")
    return matches[0]


def authorize_stage(
    output_dir: Path,
    stage_number: int,
    payload_sha: str,
    ceiling: float,
    confirmed: bool,
) -> dict:
    """Record an exact user authorization without making a provider call."""
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = _read_json(manifest_path)
    stage = _find_stage(manifest, stage_number)
    payload_path = output_dir / stage["payload_path"]
    observed = sha_file(payload_path)
    expected_ceiling = float(stage["cost"]["suggested_hard_ceiling_usd"])
    if payload_sha != observed or payload_sha != stage["payload_sha256"]:
        raise ValueError("authorized payload hash does not match frozen stage")
    if float(ceiling) != expected_ceiling:
        raise ValueError("authorized ceiling does not match frozen stage estimate")
    authorization = {
        "recorded_at": _now(),
        "user_authorized": True,
        "authorization_scope": "openrouter_expansion_v3_model_stage",
        "stage": stage_number,
        "model": stage["model"],
        "n_requests": stage["n_requests"],
        "provider_payload_sha256": payload_sha,
        "fallbacks_disabled": True,
        "max_attempts_per_request": 2,
        "cost_ceiling_usd": float(ceiling),
    }
    stage["authorization"] = authorization
    stage["paid_run_authorized"] = True
    stage["status"] = "authorized_not_started"
    manifest["status"] = "one_or_more_stages_authorized"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def run_stage(
    root: Path,
    output_dir: Path,
    stage_number: int,
    workers: int,
    ceiling: float,
    authorized: bool,
) -> dict:
    """Run one authorized stage append-only, with resumability and a hard cap."""
    if not authorized:
        raise RuntimeError("paid run requires --authorize-paid-run")
    if workers < 1 or workers > 64:
        raise ValueError("workers must be between 1 and 64")
    manifest_path = output_dir / "manifest.json"
    manifest = _read_json(manifest_path)
    stage = _find_stage(manifest, stage_number)
    payload_path = output_dir / stage["payload_path"]
    auth = stage.get("authorization", {})
    observed_hash = sha_file(payload_path)
    if not (
        auth.get("user_authorized") is True
        and auth.get("stage") == stage_number
        and auth.get("model") == stage["model"]
        and auth.get("n_requests") == stage["n_requests"]
        and auth.get("provider_payload_sha256") == observed_hash
        and observed_hash == stage["payload_sha256"]
        and auth.get("fallbacks_disabled") is True
        and auth.get("max_attempts_per_request") == 2
        and float(auth.get("cost_ceiling_usd", -1)) == float(ceiling)
    ):
        raise RuntimeError("authorization does not match exact stage payload and ceiling")

    from openai import OpenAI
    import sys

    sys.path.insert(0, str(root / "scripts"))
    from env_utils import load_env_from_file

    load_env_from_file()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    requests = read_jsonl(payload_path)
    if len(requests) != int(stage["n_requests"]):
        raise ValueError("stage payload row count changed")

    run_dir = output_dir / f"stage_{stage_number:02d}_{stage['model']}"
    run_dir.mkdir(parents=True, exist_ok=True)
    attempts_path = run_dir / "attempts.jsonl"
    completed: Dict[str, dict] = {}
    attempts: Dict[str, int] = {}
    spent = 0.0
    for record in read_jsonl(attempts_path):
        spent += float(record.get("incremental_provider_cost", 0))
        request_id = record["provider_request_id"]
        attempts[request_id] = attempts.get(request_id, 0) + 1
        if record.get("status") == "complete":
            completed[request_id] = record
    pending = [row for row in requests if row["provider_request_id"] not in completed]
    lock_path = run_dir / ".run.lock"
    lock_path.touch(exist_ok=True)
    started_at = _now()
    with lock_path.open("r+") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with attempts_path.open("a", encoding="utf-8") as handle:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {}
                cursor = 0
                reserved = 0.0
                while cursor < len(pending) or futures:
                    while cursor < len(pending) and len(futures) < workers:
                        request = pending[cursor]
                        request_id = request["provider_request_id"]
                        if attempts.get(request_id, 0) >= 2:
                            cursor += 1
                            continue
                        hold = (
                            request["estimated_input_tokens"] * request["input_usd_per_million"]
                            + request["max_output_tokens"] * request["output_usd_per_million"]
                        ) / 1_000_000
                        if spent + reserved + hold > ceiling + 1e-9:
                            break
                        cursor += 1
                        future = pool.submit(_call, client, request)
                        futures[future] = (request, hold)
                        reserved += hold
                    if not futures:
                        break
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        request, hold = futures.pop(future)
                        reserved -= hold
                        try:
                            record = future.result()
                        except Exception as exc:
                            record = {
                                "provider_request_id": request["provider_request_id"],
                                "prompt_id": request["prompt_id"],
                                "prompt_language": request["prompt_language"],
                                "model": request["model"],
                                "provider_tag_requested": request["provider_tag"],
                                "status": "error",
                                "error_type": type(exc).__name__,
                                "error": str(exc)[:1000],
                                "transient": _is_transient(exc),
                                "incremental_provider_cost": 0.0,
                                "created_at": _now(),
                            }
                        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                        request_id = request["provider_request_id"]
                        attempts[request_id] = attempts.get(request_id, 0) + 1
                        spent += float(record.get("incremental_provider_cost", 0))
                        if spent > ceiling + 1e-9:
                            raise RuntimeError("hard provider-cost ceiling exceeded")
                        if record.get("status") == "complete":
                            completed[request_id] = record
                        elif attempts[request_id] < 2 and record.get("transient", False):
                            pending.append(request)

    ordered = [
        completed[row["provider_request_id"]]
        for row in requests if row["provider_request_id"] in completed
    ]
    results_path = run_dir / "results.jsonl"
    write_jsonl(results_path, ordered)
    expected = int(stage["n_requests"])
    summary = {
        "started_at": started_at,
        "completed_at": _now(),
        "stage": stage_number,
        "model": stage["model"],
        "n_expected": expected,
        "n_completed": len(ordered),
        "n_incomplete": expected - len(ordered),
        "completion_rate": len(ordered) / expected,
        "n_attempt_records": len(read_jsonl(attempts_path)),
        "provider_cost_usd": spent,
        "authorized_ceiling_usd": float(ceiling),
        "workers": workers,
        "provider_payload_sha256": observed_hash,
        "attempts_sha256": sha_file(attempts_path),
        "results_sha256": sha_file(results_path),
        "network_inference_call_made": True,
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    latest = _read_json(manifest_path)
    latest_stage = _find_stage(latest, stage_number)
    latest_stage["status"] = "completed" if len(ordered) == expected else "incomplete"
    latest_stage["network_inference_call_made"] = True
    latest_stage["run_summary"] = summary
    latest["network_inference_call_made"] = True
    manifest_path.write_text(json.dumps(latest, indent=2), encoding="utf-8")
    return summary
