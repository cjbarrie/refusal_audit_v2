"""Freeze, cost, authorize, and run the OpenRouter expansion pilot.

The pilot is deliberately enriched for operational and behavioral variety. It
is not a probability sample and must not be used to estimate refusal prevalence.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import random
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd


DEFAULT_DIR = Path("annotations/model_expansion_v1/openrouter_pilot_v1")
ROSTER_PATH = Path("config/model_rosters/openrouter_expansion_v1.json")
VALIDITY_PATH = Path(
    "annotations/response_validity_v2_4/wall_to_wall_luna_v1/"
    "final_annotations.parquet"
)
LANGUAGES = ("en", "zh", "ar", "ru", "hi")
N_PROMPT_MEANINGS = 40
N_PER_BAND_TIER = 5
SEED = 20260902
PLANNING_OUTPUT_TOKENS = 1_500
MAX_ATTEMPTS = 2


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha_object(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            )


def _token_count(text: str) -> int:
    """Planning count using one fixed tokenizer; provider billing remains final."""
    try:
        import tiktoken

        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except Exception:
        return max(1, math.ceil(len(text.encode("utf-8")) / 4))


def _load_roster(root: Path) -> Dict[str, Any]:
    path = root / ROSTER_PATH
    roster = json.loads(path.read_text(encoding="utf-8"))
    if roster.get("provider_calls_authorized") is not False:
        raise ValueError("base expansion roster must remain setup-only")
    if len(roster.get("models", [])) != 8:
        raise ValueError("pilot requires exactly eight expansion models")
    for model in roster["models"]:
        route = model.get("provider_routing", {})
        if route.get("allow_fallbacks") is not False:
            raise ValueError(f"fallbacks not disabled for {model['name']}")
        if route.get("only") != [model.get("selected_provider_tag")]:
            raise ValueError(f"provider route is not singly pinned for {model['name']}")
    roster["_sha256"] = sha_file(path)
    return roster


def _load_prompts(root: Path, roster: Dict[str, Any]) -> Dict[str, Dict[str, dict]]:
    by_language: Dict[str, Dict[str, dict]] = {}
    expected_ids = None
    for language in LANGUAGES:
        spec = roster["design"]["prompt_files"][language]
        path = root / spec["path"]
        if sha_file(path) != spec["sha256"]:
            raise ValueError(f"frozen prompt hash mismatch for {language}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        prompts = {row["id"]: row for row in raw["prompts"]}
        if len(prompts) != int(spec["n_prompts"]):
            raise ValueError(f"prompt count mismatch for {language}")
        ids = set(prompts)
        if expected_ids is None:
            expected_ids = ids
        elif ids != expected_ids:
            raise ValueError(f"prompt IDs differ in {language}")
        by_language[language] = prompts
    return by_language


def _greedy_select(
    candidates: pd.DataFrame,
    n: int,
    selected_issue_ids: set,
    global_counts: Dict[str, Dict[str, int]],
    priority_column: str,
    descending: bool,
    seed: int,
) -> List[dict]:
    """Choose diverse prompts deterministically while respecting band priority."""
    frame = candidates[~candidates["issue_id"].isin(selected_issue_ids)].copy()
    if len(frame) < n:
        raise ValueError("too few unique issues for pilot stratum")
    rng = random.Random(seed)
    frame["tie"] = [rng.random() for _ in range(len(frame))]
    chosen: List[dict] = []
    for _ in range(n):
        scored = []
        for _, row in frame.iterrows():
            direction = float(row[priority_column])
            if not descending:
                direction = -direction
            diversity = sum(
                1.0 / (1.0 + global_counts[field].get(str(row[field]), 0))
                for field in ("region_focus", "topic_domain", "route")
            )
            scored.append((direction * 4.0 + diversity + row["tie"] * 1e-6, row))
        _, best = max(scored, key=lambda item: item[0])
        record = best.to_dict()
        chosen.append(record)
        selected_issue_ids.add(str(best["issue_id"]))
        for field in global_counts:
            value = str(best[field])
            global_counts[field][value] = global_counts[field].get(value, 0) + 1
        frame = frame[frame["id"] != best["id"]]
        frame = frame[~frame["issue_id"].isin(selected_issue_ids)]
    return chosen


def select_pilot_prompts(root: Path, english_prompts: Dict[str, dict]) -> pd.DataFrame:
    """Select 40 meanings: four bands × two tiers × five unique issues."""
    validity = pd.read_parquet(root / VALIDITY_PATH)
    required = {
        "prompt_id", "model", "prompt_language",
        "pred_genuine_refusal", "pred_capability_failure",
    }
    if not required.issubset(validity.columns):
        raise ValueError("final v2.4 annotations lack required pilot fields")
    summary = validity.groupby("prompt_id", as_index=False).agg(
        prior_n_responses=("model", "size"),
        prior_refusal_prop=("pred_genuine_refusal", "mean"),
        prior_capability_failure_prop=("pred_capability_failure", "mean"),
    )
    metadata = pd.DataFrame(english_prompts.values()).rename(columns={"id": "prompt_id"})
    frame = metadata.merge(summary, on="prompt_id", validate="one_to_one")
    frame["id"] = frame["prompt_id"]
    q90 = float(frame["prior_refusal_prop"].quantile(0.90))
    selected: List[dict] = []
    selected_issue_ids: set = set()
    counts = {field: {} for field in ("region_focus", "topic_domain", "route")}

    for tier_index, tier in enumerate(("regular", "boundary_testing")):
        part = frame[frame["controversy_tier"] == tier]
        bands = [
            (
                "high_prior_refusal",
                part[part["prior_refusal_prop"] >= q90],
                "prior_refusal_prop", True,
            ),
            (
                "moderate_prior_refusal",
                part[(part["prior_refusal_prop"] > 0) &
                     (part["prior_refusal_prop"] < q90)],
                "prior_refusal_prop", True,
            ),
            (
                "zero_prior_refusal",
                part[part["prior_refusal_prop"] == 0],
                "prior_capability_failure_prop", False,
            ),
            (
                "diverse_reference",
                part,
                "random_priority", True,
            ),
        ]
        for band_index, (band, candidates, priority, descending) in enumerate(bands):
            candidates = candidates.copy()
            if priority == "random_priority":
                candidates[priority] = candidates["prompt_id"].map(
                    lambda value: int(
                        hashlib.sha256(
                            f"{SEED}|{tier}|{value}".encode("utf-8")
                        ).hexdigest()[:16], 16
                    ) / 16**16
                )
            picks = _greedy_select(
                candidates, N_PER_BAND_TIER, selected_issue_ids, counts,
                priority, descending, SEED + tier_index * 100 + band_index,
            )
            for pick in picks:
                pick["pilot_band"] = band
                selected.append(pick)

    result = pd.DataFrame(selected)
    if len(result) != N_PROMPT_MEANINGS or result["prompt_id"].nunique() != N_PROMPT_MEANINGS:
        raise ValueError("pilot selection is not 40 unique prompt meanings")
    if result["issue_id"].nunique() != N_PROMPT_MEANINGS:
        raise ValueError("pilot selection repeats an issue")
    expected_cells = set(
        (tier, band)
        for tier in ("regular", "boundary_testing")
        for band in (
            "high_prior_refusal", "moderate_prior_refusal",
            "zero_prior_refusal", "diverse_reference",
        )
    )
    observed = result.groupby(["controversy_tier", "pilot_band"]).size().to_dict()
    if any(observed.get(cell) != N_PER_BAND_TIER for cell in expected_cells):
        raise ValueError("pilot band × tier allocation is not 5 per cell")
    return result.sort_values(["controversy_tier", "pilot_band", "prompt_id"])


def prepare_pilot(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    roster = _load_roster(root)
    prompts = _load_prompts(root, roster)
    roster_path = root / ROSTER_PATH
    validity_path = root / VALIDITY_PATH
    input_hashes = {
        "roster": sha_file(roster_path),
        "final_v2_4_annotations": sha_file(validity_path),
        **{
            f"prompt_{language}": roster["design"]["prompt_files"][language]["sha256"]
            for language in LANGUAGES
        },
    }
    manifest_path = output_dir / "manifest.json"
    artifacts = {
        "pilot_prompt_index.csv": output_dir / "pilot_prompt_index.csv",
        "provider_requests.jsonl": output_dir / "provider_requests.jsonl",
    }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("input_sha256") != input_hashes:
            raise ValueError("frozen pilot no longer matches its inputs")
        for name, expected in manifest["artifact_sha256"].items():
            if not artifacts[name].exists() or sha_file(artifacts[name]) != expected:
                raise ValueError(f"frozen pilot artifact changed: {name}")
        return manifest

    selected = select_pilot_prompts(root, prompts["en"])
    requests = []
    selected_by_id = selected.set_index("prompt_id").to_dict("index")
    for prompt_id in sorted(selected_by_id):
        selection = selected_by_id[prompt_id]
        for language in LANGUAGES:
            prompt = prompts[language][prompt_id]
            for model in roster["models"]:
                logical = {
                    "pilot_version": "openrouter-expansion-pilot-v1",
                    "prompt_id": prompt_id,
                    "prompt_language": language,
                    "model": model["name"],
                }
                requests.append({
                    **logical,
                    "provider_request_id": sha_object(logical)[:24],
                    "messages": [{"role": "user", "content": prompt["text"]}],
                    "estimated_input_tokens": _token_count(prompt["text"]),
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
                    "pilot_band": selection["pilot_band"],
                    "prior_refusal_prop": selection["prior_refusal_prop"],
                    "prior_capability_failure_prop": selection[
                        "prior_capability_failure_prop"
                    ],
                })
    expected_n = N_PROMPT_MEANINGS * len(LANGUAGES) * len(roster["models"])
    if len(requests) != expected_n:
        raise ValueError(f"expected {expected_n} pilot requests, got {len(requests)}")
    if len({row["provider_request_id"] for row in requests}) != expected_n:
        raise ValueError("pilot request IDs are not unique")

    output_dir.mkdir(parents=True, exist_ok=False)
    selected.to_csv(artifacts["pilot_prompt_index.csv"], index=False)
    write_jsonl(artifacts["provider_requests.jsonl"], requests)
    manifest = {
        "version": "openrouter-expansion-pilot-v1",
        "created_at": now(),
        "status": "frozen_unpriced",
        "scientific_role": (
            "enriched operational and measurement pilot; not a probability "
            "sample and not valid for prevalence estimation"
        ),
        "selection": {
            "seed": SEED,
            "n_prompt_meanings": N_PROMPT_MEANINGS,
            "unique_issue_required": True,
            "bands": [
                "high_prior_refusal", "moderate_prior_refusal",
                "zero_prior_refusal", "diverse_reference",
            ],
            "tiers": ["regular", "boundary_testing"],
            "n_per_band_tier": N_PER_BAND_TIER,
            "prior_outcomes": "final Luna v2.4 across the existing panel",
        },
        "languages": list(LANGUAGES),
        "models": [model["name"] for model in roster["models"]],
        "n_requests": expected_n,
        "max_attempts": MAX_ATTEMPTS,
        "fallbacks_disabled": True,
        "reasoning_disabled_where_supported": True,
        "input_sha256": input_hashes,
        "artifact_sha256": {
            name: sha_file(path) for name, path in artifacts.items()
        },
        "provider_payload_sha256": sha_file(artifacts["provider_requests.jsonl"]),
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def estimate_pilot_cost(root: Path, output_dir: Path | None = None) -> dict:
    output_dir = output_dir or root / DEFAULT_DIR
    manifest = prepare_pilot(root, output_dir)
    requests = read_jsonl(output_dir / "provider_requests.jsonl")
    planning = sum(
        (
            row["estimated_input_tokens"] * row["input_usd_per_million"]
            + PLANNING_OUTPUT_TOKENS * row["output_usd_per_million"]
        ) / 1_000_000
        for row in requests
    )
    reserved = sum(
        (
            row["estimated_input_tokens"] * row["input_usd_per_million"]
            + row["max_output_tokens"] * row["output_usd_per_million"]
        ) / 1_000_000
        for row in requests
    )
    ceiling = math.ceil(max(planning * 1.5, reserved * 1.25) * 2) / 2
    by_model = {}
    for row in requests:
        target = by_model.setdefault(row["model"], {
            "n_requests": 0, "estimated_input_tokens": 0,
            "planning_cost_usd": 0.0, "single_attempt_reserved_cost_usd": 0.0,
        })
        target["n_requests"] += 1
        target["estimated_input_tokens"] += row["estimated_input_tokens"]
        target["planning_cost_usd"] += (
            row["estimated_input_tokens"] * row["input_usd_per_million"]
            + PLANNING_OUTPUT_TOKENS * row["output_usd_per_million"]
        ) / 1_000_000
        target["single_attempt_reserved_cost_usd"] += (
            row["estimated_input_tokens"] * row["input_usd_per_million"]
            + row["max_output_tokens"] * row["output_usd_per_million"]
        ) / 1_000_000
    result = {
        "version": "openrouter-expansion-pilot-cost-v1",
        "created_at": now(),
        "pricing_verified_at": "2026-09-02",
        "requests": len(requests),
        "estimated_input_tokens": sum(r["estimated_input_tokens"] for r in requests),
        "planning_output_tokens_per_request": PLANNING_OUTPUT_TOKENS,
        "planning_cost_usd": planning,
        "single_attempt_reserved_cost_usd": reserved,
        "suggested_hard_ceiling_usd": ceiling,
        "by_model": by_model,
        "provider_payload_sha256": manifest["provider_payload_sha256"],
        "paid_run_authorized": False,
        "network_inference_call_made": False,
    }
    (output_dir / "cost_estimate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    manifest_path = output_dir / "manifest.json"
    latest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Re-estimation is safe after authorization or completion, but it must never
    # roll the run state backwards to "unpaid". This matters because cost checks
    # are part of routine post-run validation.
    if not latest.get("paid_run_authorized") and not latest.get(
        "network_inference_call_made"
    ):
        latest["status"] = "frozen_unpaid"
    latest["cost_estimate"] = result
    manifest_path.write_text(json.dumps(latest, indent=2), encoding="utf-8")
    return result


def authorize_pilot(
    output_dir: Path, payload_sha: str, ceiling: float, confirmed: bool
) -> dict:
    if not confirmed:
        raise RuntimeError("explicit user authorization confirmation is required")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cost = json.loads((output_dir / "cost_estimate.json").read_text(encoding="utf-8"))
    observed = sha_file(output_dir / "provider_requests.jsonl")
    if payload_sha != observed or payload_sha != manifest["provider_payload_sha256"]:
        raise ValueError("authorized payload hash does not match frozen bytes")
    if float(ceiling) != float(cost["suggested_hard_ceiling_usd"]):
        raise ValueError("authorized ceiling does not match frozen estimate")
    authorization = {
        "recorded_at": now(),
        "user_authorized": True,
        "authorization_scope": "openrouter_expansion_pilot_v1",
        "provider_payload_sha256": payload_sha,
        "n_requests": manifest["n_requests"],
        "models": manifest["models"],
        "fallbacks_disabled": True,
        "cost_ceiling_usd": float(ceiling),
    }
    manifest["authorization"] = authorization
    manifest["paid_run_authorized"] = True
    manifest["status"] = "authorized_not_started"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return authorization


def _is_transient(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status in {429, 500, 502, 503, 504}:
        return True
    text = str(exc).lower()
    return any(marker in text for marker in (
        "rate limit", "timeout", "timed out", "connection", "overloaded",
        "service unavailable", "bad gateway", "gateway timeout",
    ))


def _call(client, request: dict) -> dict:
    started = time.time()
    extra_body = {"provider": request["provider"]}
    if request.get("reasoning") is not None:
        extra_body["reasoning"] = request["reasoning"]
    response = client.chat.completions.create(
        model=request["model_id"],
        messages=request["messages"],
        temperature=request["temperature"],
        max_tokens=request["max_output_tokens"],
        extra_body=extra_body,
        timeout=180,
    )
    message = response.choices[0].message
    content = message.content or ""
    reasoning = (
        getattr(message, "reasoning_content", None)
        or getattr(message, "reasoning", None)
    )
    # Never retain hidden reasoning. Inline <think> blocks are also removed.
    import re
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.I | re.S).strip()
    if not content:
        raise ValueError("empty response content")
    usage = response.usage.model_dump() if response.usage else {}
    cost = usage.get("cost")
    if cost is None:
        cost = (
            float(usage.get("prompt_tokens", 0)) * request["input_usd_per_million"]
            + float(usage.get("completion_tokens", 0)) * request["output_usd_per_million"]
        ) / 1_000_000
    return {
        "provider_request_id": request["provider_request_id"],
        "prompt_id": request["prompt_id"],
        "prompt_language": request["prompt_language"],
        "model": request["model"],
        "model_id_requested": request["model_id"],
        "provider_tag_requested": request["provider_tag"],
        "provider_response_id": response.id,
        "provider_model": response.model,
        "provider_returned": getattr(response, "provider", None),
        "response_text": content,
        "response_text_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "reasoning_returned_unexpectedly": bool(reasoning),
        "usage": usage,
        "incremental_provider_cost": float(cost),
        "elapsed_seconds": time.time() - started,
        "created_at": now(),
        "status": "complete",
        "prompt_metadata": request["prompt_metadata"],
        "pilot_band": request.get("pilot_band"),
    }


def run_pilot(
    root: Path, output_dir: Path, workers: int, ceiling: float, authorized: bool
) -> dict:
    if not authorized:
        raise RuntimeError("paid run requires --authorize-paid-run")
    if workers < 1 or workers > 32:
        raise ValueError("workers must be between 1 and 32")
    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload_path = output_dir / "provider_requests.jsonl"
    auth = manifest.get("authorization", {})
    if not (
        auth.get("user_authorized") is True
        and auth.get("provider_payload_sha256") == sha_file(payload_path)
        and auth.get("provider_payload_sha256") == manifest["provider_payload_sha256"]
        and auth.get("models") == manifest["models"]
        and auth.get("fallbacks_disabled") is True
        and float(auth.get("cost_ceiling_usd", -1)) == float(ceiling)
    ):
        raise RuntimeError("authorization does not match exact pilot payload and ceiling")

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
    attempts_path = output_dir / "attempts.jsonl"
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
    lock_path = output_dir / ".run.lock"
    lock_path.touch(exist_ok=True)
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
                        if attempts.get(request_id, 0) >= MAX_ATTEMPTS:
                            cursor += 1
                            continue
                        hold = (
                            request["estimated_input_tokens"] *
                            request["input_usd_per_million"]
                            + request["max_output_tokens"] *
                            request["output_usd_per_million"]
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
                                "created_at": now(),
                            }
                        handle.write(
                            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                        )
                        handle.flush()
                        os.fsync(handle.fileno())
                        request_id = request["provider_request_id"]
                        attempts[request_id] = attempts.get(request_id, 0) + 1
                        spent += float(record.get("incremental_provider_cost", 0))
                        if spent > ceiling + 1e-9:
                            raise RuntimeError("hard provider-cost ceiling exceeded")
                        if record.get("status") == "complete":
                            completed[request_id] = record
                        elif attempts[request_id] < MAX_ATTEMPTS:
                            pending.append(request)

    ordered = [
        completed[row["provider_request_id"]]
        for row in requests if row["provider_request_id"] in completed
    ]
    results_path = output_dir / "results.jsonl"
    write_jsonl(results_path, ordered)
    expected = int(manifest["n_requests"])
    summary = {
        "completed_at": now(),
        "n_expected": expected,
        "n_completed": len(ordered),
        "n_incomplete": expected - len(ordered),
        "completion_rate": len(ordered) / expected,
        "provider_cost_usd": spent,
        "authorized_ceiling_usd": float(ceiling),
        "provider_payload_sha256": sha_file(payload_path),
        "attempts_sha256": sha_file(attempts_path),
        "results_sha256": sha_file(results_path),
        "network_inference_call_made": True,
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    manifest["status"] = "completed" if len(ordered) == expected else "incomplete"
    manifest["network_inference_call_made"] = True
    manifest["run_summary"] = summary
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary
