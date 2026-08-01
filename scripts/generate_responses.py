"""
Generate responses from test models to political prompts.

This script loads test prompts and generates responses from multiple LLMs.
Responses are saved to JSONL format with metadata.
"""

import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from datetime import datetime, timezone

# PYTHONSAFEPATH is set in this environment, so the script's own directory is
# not auto-added to sys.path. Bootstrap it so sibling imports resolve.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from env_utils import load_env_from_file
from config import TEST_MODELS, MODEL_PROVIDER, PROVIDER_ENDPOINTS, HF_ENDPOINT_URL_VARS, MODEL_MAX_TOKENS

# topic_domain (v2 batteries) -> legacy prompt_category expected by the R pipeline.
# Carried metadata only; never feeds any judge prompt. See docs/ANNOTATION_CONTRACT.md.
TOPIC_DOMAIN_TO_CATEGORY = {
    "territorial_sovereignty": "territorial_sovereignty",
    "governance_democracy": "governance_democracy",
    "civil_rights_liberties": "civil_rights_liberties",
    "social_moral": "social_moral",
    "economic_policy": "economic_policy",
    "religion_state": "religion_state",
    "security_conflict": "security_conflict",
    "environment_energy": "environment_energy",
    "migration_nationalism": "migration_nationalism",
}


def load_prompts(prompts_file: str) -> Tuple[List[Dict], str]:
    """Load test prompts from JSON file and detect language."""
    with open(prompts_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Translated prompt files (from 05_translate_review.py) carry the language
    # under 'target_language'; the English reference file uses 'language'.
    # Accept either, so every edition is stamped with its true language rather
    # than silently defaulting to 'en'.
    language = data.get('language') or data.get('target_language') or 'en'
    return data['prompts'], language


# Transient upstream failures worth retrying: gateway/service-unavailable/
# rate-limit HTTP statuses, plus connection/timeout errors. Self-hosted HF
# Inference Endpoints in particular can return intermittent 503 "Service
# Unavailable" pages while a replica is scaling or under load; a short backoff
# clears almost all of them.
_TRANSIENT_STATUS = (429, 500, 502, 503, 504)
_TRANSIENT_MARKERS = (
    "service unavailable", "temporarily unavailable", "bad gateway",
    "gateway timeout", "too many requests", "rate limit", "overloaded",
    "timeout", "timed out", "connection reset", "connection error",
    "econnreset", "read timed out",
)


def _is_transient(exc: Exception) -> bool:
    """True if this exception looks like a retryable upstream blip."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status, int) and status in _TRANSIENT_STATUS:
        return True
    msg = str(exc).lower()
    if any(m in msg for m in _TRANSIENT_MARKERS):
        return True
    # HF 503 pages arrive as a raw HTML body ("<h1>503</h1>") rather than a
    # typed status on the exception; catch that shape too.
    if "<html" in msg and re.search(r"\b(429|50[0234])\b", msg):
        return True
    return False


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_reasoning(content: str) -> str:
    """
    Remove a hybrid reasoning model's chain-of-thought from the answer text.

    Reasoning ("think") models such as sarvam-30b (Sarvam-M) emit a
    <think>...</think> block before their actual answer. When the serving stack
    routes that block to a separate reasoning_content field, .content is already
    clean and this is a no-op. When it leaves the block INLINE in .content
    (llama.cpp/TGI often do), we strip it here so the downstream judge scores the
    answer, not the English chain-of-thought.

    Handles the common truncation case too: if generation was cut off mid-think
    the closing </think> may be missing, leaving a dangling "<think>...". We drop
    everything from an unmatched opening <think> to end-of-string, which yields an
    empty answer -> flagged as an empty-content error upstream and retried (better
    than annotating a raw reasoning fragment).
    """
    if not content:
        return content
    if "<think>" not in content.lower():
        return content
    cleaned = _THINK_RE.sub("", content)
    # Drop any dangling unmatched <think> (truncated mid-reasoning).
    lower = cleaned.lower()
    idx = lower.find("<think>")
    if idx != -1:
        cleaned = cleaned[:idx]
    return cleaned.strip()


def generate_response(
    client: OpenAI,
    model_id: str,
    prompt_text: str,
    temperature: float = 1.0,
    max_tokens: int = 5000,
    max_retries: int = 4,
    base_delay: float = 2.0,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Generate a response from a model via its OpenAI-compatible endpoint.

    Args:
        client: OpenAI client configured for the model's provider
        model_id: Model identifier (e.g., "openai/gpt-5.1")
        prompt_text: The prompt to send
        temperature: Sampling temperature (default 1.0 for natural responses)
        max_tokens: Cap on completion length. OpenRouter RESERVES credits
            against this ceiling (not actual usage), so leaving it unset defaults
            to each model's full window (e.g. 65,535) and drains credit balance
            far faster than real usage. 2,000 comfortably covers a
            refusal-audit answer; raise only if responses are being truncated.
        max_retries: Number of retries on transient upstream errors
            (503/502/429/timeout etc.) before giving up. Non-transient errors
            (auth, bad request, content refusal) are raised immediately.
        base_delay: Seconds for the first backoff; doubles each retry.

    Returns:
        (response_text, reasoning_text). response_text is the model's answer
        (message.content, with any inline <think> block stripped). reasoning_text
        is the chain-of-thought a hybrid reasoning model (e.g. sarvam-30b) routes
        to a separate reasoning_content / reasoning field, or None if the model
        emits no separate reasoning field. Stored as provenance; never annotated.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            msg = response.choices[0].message
            # Strip any inline <think>...</think> reasoning block (hybrid
            # reasoning models like sarvam-30b). No-op for models that don't
            # emit one, or that route reasoning to a separate field.
            content = _strip_reasoning(msg.content)
            # Hybrid reasoning models served via llama.cpp / vLLM route the
            # chain-of-thought to a separate field (reasoning_content, or
            # reasoning on some routers) rather than inlining it in .content.
            # Capture it as provenance; it is never fed to any judge.
            reasoning = (getattr(msg, "reasoning_content", None)
                         or getattr(msg, "reasoning", None) or None)
            return content, reasoning
        except Exception as e:
            last_exc = e
            if attempt < max_retries and _is_transient(e):
                # Exponential backoff with a little jitter.
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue
            raise
    raise last_exc


def load_existing_responses(output_file: str) -> dict:
    """Map (prompt_id, prompt_language, model) -> last record in an existing
    output file. Used to skip already-generated (clean) responses on resume and
    to retry errored ones. Returns {} if the file does not exist.

    A record is 'clean' iff it has a non-null response_text and no error.
    """
    import os as _os
    if not _os.path.exists(output_file):
        return {}
    out = {}
    with open(output_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (r.get("prompt_id"), r.get("prompt_language"), r.get("model"))
            out[key] = r
    return out


def generate_all_responses(
    prompts_file: str,
    output_file: str,
    limit: Optional[int] = None,
    verbose: bool = True,
    max_workers: int = 8,
    only_models: Optional[List[str]] = None,
    exclude_models: Optional[List[str]] = None,
    max_tokens: int = 5000,
):
    """
    Generate responses from all test models for all prompts.

    Args:
        prompts_file: Path to test_prompts.json
        output_file: Path to save responses (JSONL format)
        limit: Optional limit on number of prompts to process
        verbose: Print progress information
    """
    # Per-provider client factory. Each subject model names a provider
    # ("openrouter" | "hf-endpoint"); PROVIDER_ENDPOINTS maps that to a
    # (base_url, key_env_var) pair. Clients are built lazily and cached, so we
    # only require a credential for the providers actually used by the roster
    # being run (e.g. an OpenRouter-only run does not need HF_TOKEN).
    load_env_from_file()
    _client_cache: Dict[str, OpenAI] = {}
    # For "hf-endpoint" models the served model id must be sent in the OpenAI
    # `model` field (a placeholder like "tgi" is rejected by newer TGI), so we
    # auto-detect it from GET /v1/models once per endpoint and cache it here,
    # keyed by display name.
    _endpoint_model_id: Dict[str, str] = {}
    _client_lock = threading.Lock()

    def get_client(provider: str, model_name: str = None) -> OpenAI:
        # Shared providers (openrouter) cache one client per provider.
        # Dedicated endpoints (hf-endpoint) have a per-model base URL, so they
        # cache one client per model_name instead.
        cache_key = model_name if provider == "hf-endpoint" else provider
        with _client_lock:
            if cache_key in _client_cache:
                return _client_cache[cache_key]
            if provider not in PROVIDER_ENDPOINTS:
                raise ValueError(f"Unknown provider {provider!r}")
            base_url, key_var = PROVIDER_ENDPOINTS[provider]
            api_key = os.getenv(key_var)
            if not api_key:
                raise ValueError(
                    f"{key_var} environment variable not set "
                    f"(required for provider '{provider}')"
                )
            if provider == "hf-endpoint":
                url_var = HF_ENDPOINT_URL_VARS.get(model_name)
                base_url = os.getenv(url_var) if url_var else None
                if not base_url:
                    raise ValueError(
                        f"{url_var} environment variable not set "
                        f"(required for endpoint model '{model_name}')"
                    )
                base_url = base_url.rstrip("/")
                if not base_url.endswith("/v1"):
                    base_url += "/v1"
            c = OpenAI(base_url=base_url, api_key=api_key)
            _client_cache[cache_key] = c
            # Resolve the served model id for dedicated endpoints (single-model
            # endpoints report exactly one). Fall back to the hub repo id if the
            # listing is unavailable.
            if provider == "hf-endpoint":
                try:
                    ids = [m.id for m in c.models.list().data]
                    if ids:
                        _endpoint_model_id[model_name] = ids[0]
                except Exception:
                    pass
            return c

    # Validate up front that every provider needed by the roster has a
    # credential, so a run fails fast rather than mid-stream.
    needed_providers = {MODEL_PROVIDER[name] for name, *_ in TEST_MODELS}
    missing = []
    for prov in sorted(needed_providers):
        _, key_var = PROVIDER_ENDPOINTS[prov]
        if not os.getenv(key_var):
            missing.append(f"{key_var} (provider '{prov}')")
    if missing:
        raise ValueError(
            "Missing credentials for the model roster: " + ", ".join(missing)
        )

    # Roster filter. Throughput across a shared worker pool is set by the
    # SLOWEST model, not the average: workers pile up on it and the whole roster
    # degrades to its service rate. sarvam-30b (30B Q4 on one endpoint, an 8000
    # token budget for its <think> block) ran ~25x slower than the others and
    # pinned the full-run rate to its own. Splitting it into a separate process
    # lets the fast models run at their own pace.
    roster = list(TEST_MODELS)
    if only_models:
        roster = [m for m in roster if m[0] in set(only_models)]
    if exclude_models:
        roster = [m for m in roster if m[0] not in set(exclude_models)]
    if not roster:
        raise SystemExit("No models left after --models/--exclude-models filter.")
    if only_models or exclude_models:
        print(f"Roster filtered to {len(roster)} model(s): "
              f"{', '.join(m[0] for m in roster)}")

    # Load prompts
    prompts, language = load_prompts(prompts_file)
    if limit:
        prompts = prompts[:limit]

    if verbose:
        print(f"Loaded {len(prompts)} prompts (language: {language})")
        print(f"Testing {len(roster)} models")
        print(f"Total responses to generate: {len(prompts) * len(roster)}")
        print(f"Output: {output_file}")
        print()

    # Resume support: keep clean rows from any prior run, retry errored/missing.
    existing = load_existing_responses(output_file)
    clean_keys = {
        k for k, r in existing.items()
        if r.get("response_text") and not r.get("error")
    }
    if verbose and clean_keys:
        print(f"Resume: {len(clean_keys)} clean responses already present; "
              f"skipping those and (re)generating the rest.")
        print()

    # Build the todo list: one task per (prompt, model) slot not already clean.
    total = len(prompts) * len(TEST_MODELS)
    tasks = []
    skipped = 0
    for prompt in prompts:
        prompt_id = prompt['id']
        # v2 batteries carry topic_domain; map to the legacy category label.
        topic_domain = prompt.get('topic_domain')
        prompt_category = TOPIC_DOMAIN_TO_CATEGORY.get(
            topic_domain, prompt.get('category', topic_domain)
        )
        prompt_text = prompt['text']
        # Provenance carried through to the response record for the R pipeline.
        provenance = {
            "topic_domain": topic_domain,
            "battery": prompt.get('battery'),
            "controversy_tier": prompt.get('controversy_tier'),
            "qid": prompt.get('qid'),
            "issue_id": prompt.get('issue_id'),
            "region_focus": prompt.get('region_focus'),
            "position_side": prompt.get('position_side'),
            "contention_score": prompt.get('contention_score'),
            # Language the prompt was originally AUTHORED in ("en", or e.g. "zh"
            # for issues sourced from Chinese Wikipedia and back-translated —
            # see sourcing/10_backtranslate_native.py). Distinct from
            # source_language/source_edition, which record which Wikipedia
            # edition flagged the issue. Carried so the analysis can test
            # whether natively-sourced prompts behave differently from
            # translated-through ones. Defaults to "en" for batteries predating
            # the field.
            "prompt_origin_language": prompt.get('prompt_origin_language', 'en'),
            # How that origin text reached the English master:
            #   authored_en - written in English in the first place
            #   native      - written wholly in the origin language, back-translated
            #   hybrid      - native stance inside Stage 3's English boundary
            #                 template, back-translated
            # Hybrids are translated like any other prompt; the tag is carried so
            # they can be isolated in a robustness check.
            "prompt_origin_form": prompt.get('prompt_origin_form', 'authored_en'),
            # Harvest route: perennial | temporal | current-events. The
            # rebalanced frame merges all three, so this is what makes the
            # perennial-vs-contested-right-now contrast runnable from one arm.
            "route": prompt.get('route'),
        }
        for model_name, model_id, _jurisdiction, provider in roster:
            if (prompt_id, language, model_name) in clean_keys:
                skipped += 1
                continue
            tasks.append({
                "prompt_id": prompt_id,
                "prompt_category": prompt_category,
                "prompt_text": prompt_text,
                "model_name": model_name,
                "model_id": model_id,
                "provider": provider,
                "provenance": provenance,
            })

    if verbose:
        print(f"Slots: {total}  skipped(done): {skipped}  to generate now: {len(tasks)}")
        print(f"Concurrency: {max_workers} workers")
        print()

    def _do_one(task: Dict) -> Dict:
        """Run one generation; return the record to write (success or error)."""
        base = {
            "prompt_id": task["prompt_id"],
            "prompt_category": task["prompt_category"],
            "prompt_text": task["prompt_text"],
            "prompt_language": language,
            "model": task["model_name"],
            "model_id": task["model_id"],
            "provider": task["provider"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reasoning_content": None,
            **task["provenance"],
        }
        try:
            client = get_client(task["provider"], task["model_name"])
            # For dedicated endpoints, use the auto-detected served model id
            # (falls back to the hub repo id if the listing was unavailable).
            call_model_id = task["model_id"]
            if task["provider"] == "hf-endpoint":
                call_model_id = _endpoint_model_id.get(task["model_name"], task["model_id"])
            # A model listed in MODEL_MAX_TOKENS uses its explicit budget instead
            # of the global default -- either capped DOWN for a small context
            # window (allam-7b: max_model_len=4096, else HTTP 400) or raised UP
            # for a reasoning model that must fit its <think> block plus the answer
            # (sarvam-30b: 8000). Models absent from the map use the global default.
            call_max_tokens = MODEL_MAX_TOKENS.get(task["model_name"], max_tokens)
            response_text, reasoning_text = generate_response(
                client=client,
                model_id=call_model_id,
                prompt_text=task["prompt_text"],
                temperature=1.0,
                max_tokens=call_max_tokens,
            )
            base["timestamp"] = datetime.now(timezone.utc).isoformat()
            # Chain-of-thought provenance for hybrid reasoning models (sarvam-30b
            # routes it to a separate reasoning_content field). None for every
            # non-reasoning model. Carried for later auditing; never annotated.
            base["reasoning_content"] = reasoning_text
            # A "successful" API call can still return null/empty content — e.g. a
            # provider-side moderation block or a null-content refusal. Treat that
            # as an error so it is flagged (not written as a silent clean row) and
            # retried on a rerun, and so the resume loader never mistakes it for
            # completed work.
            if not response_text:
                base["response_text"] = None
                base["error"] = "empty response content (model returned no text)"
            else:
                base["response_text"] = response_text
            return base
        except Exception as e:
            base["response_text"] = None
            # Some upstreams (HF router 503) return a full HTML error page as the
            # message; storing it verbatim bloats the JSONL and buries the cause.
            # Collapse whitespace and cap length; note if it was an HTML body.
            msg = " ".join(str(e).split())
            if "<html" in msg.lower():
                m = re.search(r"\b(429|50[0234])\b", msg)
                code = m.group(1) if m else "?"
                msg = f"upstream HTTP {code} (HTML error page)"
            base["error"] = msg[:500]
            base["timestamp"] = datetime.now(timezone.utc).isoformat()
            return base

    # Concurrent dispatch. Each result is appended under a lock as it completes,
    # so an interrupt leaves a valid partial file that a rerun resumes from.
    errors = 0
    done = 0
    write_lock = threading.Lock()
    with open(output_file, 'a') as f:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_do_one, t): t for t in tasks}
            for fut in as_completed(futures):
                record = fut.result()
                done += 1
                is_err = record.get("error") is not None
                if is_err:
                    errors += 1
                with write_lock:
                    f.write(json.dumps(record) + "\n")
                    f.flush()
                if verbose:
                    tag = f"✗ {record['error']}" if is_err else \
                          f"✓ ({len(record['response_text'] or '')} chars)"
                    print(f"[{done}/{len(tasks)}] {record['prompt_id']} "
                          f"+ {record['model']}: {tag}")

    if verbose:
        print()
        print("=" * 80)
        print("GENERATION COMPLETE")
        print("=" * 80)
        print(f"Total slots: {total}")
        print(f"Skipped (already done): {skipped}")
        print(f"Attempted this run: {len(tasks)}")
        print(f"Success this run: {len(tasks) - errors}")
        print(f"Errors this run: {errors}")
        print(f"Output saved to: {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate responses from test models")
    parser.add_argument(
        "--prompts",
        default="../prompts/test_prompts_en.json",
        help="Path to the prompt set JSON"
    )
    parser.add_argument(
        "--output",
        default="../responses/responses_en.jsonl",
        help="Output file for responses (JSONL)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of prompts (for testing)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of concurrent API workers (default: 8)"
    )
    parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated model names to generate for (default: the full "
             "roster). Use to give a slow model its own process so it does not "
             "gate the others, e.g. --models sarvam-30b."
    )
    parser.add_argument(
        "--exclude-models",
        default=None,
        help="Comma-separated model names to skip, e.g. --exclude-models sarvam-30b."
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=5000,
        help="Max completion tokens per response (default: 5000). OpenRouter "
             "reserves credits against this ceiling; keep it near real usage."
    )

    args = parser.parse_args()

    generate_all_responses(
        prompts_file=args.prompts,
        output_file=args.output,
        limit=args.limit,
        verbose=not args.quiet,
        max_workers=args.workers,
        max_tokens=args.max_tokens,
        only_models=[m.strip() for m in args.models.split(",")] if args.models else None,
        exclude_models=([m.strip() for m in args.exclude_models.split(",")]
                        if args.exclude_models else None),
    )
