#!/usr/bin/env python3
"""
Preflight check for the two inference paths used by the audit.

Verifies, WITHOUT printing any secret values:
  1. OpenRouter        -- https://openrouter.ai/api/v1    (env OPENROUTER_API_KEY)
     used by all US/CN/EU subject models, the judge, and the stance coder.
  2. HF Inference Endpoints -- per-model dedicated URLs    (env HF_TOKEN + each
     model's *_ENDPOINT_URL) used by the three MENA subject models
     (ALLaM, Falcon3, Jais). Each is a self-hosted TGI endpoint, only reachable
     while deployed; an endpoint whose URL env var is unset is reported ABSENT.

For each target it (a) reports whether the credential/URL is present and
(b) if present, makes ONE cheap chat-completion call and reports PASS/FAIL.
For each endpoint the served model id is auto-detected from GET /v1/models
(newer TGI rejects a placeholder in the `model` field), matching how
scripts/generate_responses.py talks to the endpoints.

Exit code is always 0 -- this is a diagnostic, not a gate. Read the table.

Usage:
    python preflight_providers.py            # test both paths
    python preflight_providers.py --openrouter-only
    python preflight_providers.py --hf-only  # only the MENA endpoints
"""
import argparse
import os
import sys

# Provider endpoints
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Cheap probe targets
OPENROUTER_TEST_MODEL = "openai/gpt-4o-mini"

# MENA subject models served via dedicated HF Inference Endpoints, sourced from
# config.ENDPOINT_MODELS so this stays in sync with the roster. Each entry is
# (display_name, endpoint_url_env_var).
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    from config import ENDPOINT_MODELS as _ENDPOINT_MODELS  # type: ignore
    HF_ENDPOINTS = [(name, url_var) for name, _repo, _juris, _prov, url_var in _ENDPOINT_MODELS]
except Exception:
    # Fallback so the preflight still runs if config import fails.
    HF_ENDPOINTS = [
        ("allam-7b", "ALLAM_ENDPOINT_URL"),
        ("falcon3-10b", "FALCON3_ENDPOINT_URL"),
        ("jais-8b", "JAIS_ENDPOINT_URL"),
    ]

# HF token is looked up under any of these standard names.
HF_TOKEN_ENV_NAMES = ["HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HUGGING_FACE_HUB_TOKEN"]


def _get_hf_token():
    for name in HF_TOKEN_ENV_NAMES:
        v = os.getenv(name)
        if v:
            return v, name
    return None, None


def _probe(base_url, api_key, model, label):
    """Make one tiny chat call. Return (ok: bool, detail: str)."""
    try:
        from openai import OpenAI
    except ImportError:
        return False, "openai package not importable"
    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            max_tokens=5,
            temperature=0,
        )
        txt = (resp.choices[0].message.content or "").strip()
        return True, f"reply={txt!r}"
    except Exception as e:  # noqa: BLE001 -- diagnostic, surface any failure
        # Keep the message compact; never echo the key.
        msg = str(e).splitlines()[0][:200]
        return False, msg


def check_openrouter():
    key = os.getenv("OPENROUTER_API_KEY")
    print("-" * 68)
    print("OpenRouter  (https://openrouter.ai/api/v1)")
    if not key:
        print("  credential OPENROUTER_API_KEY : ABSENT")
        print("  status                        : SKIP (set the key to run subject/judge/stance stages)")
        return False
    print("  credential OPENROUTER_API_KEY : present")
    ok, detail = _probe(OPENROUTER_BASE_URL, key, OPENROUTER_TEST_MODEL, "openrouter")
    print(f"  test call ({OPENROUTER_TEST_MODEL}) : {'PASS' if ok else 'FAIL'}  [{detail}]")
    return ok


def _resolve_endpoint_model(base_url, api_key):
    """Return the served model id from GET /v1/models, or 'tgi' as a fallback."""
    try:
        from openai import OpenAI
        c = OpenAI(base_url=base_url, api_key=api_key)
        ids = [m.id for m in c.models.list().data]
        if ids:
            return ids[0]
    except Exception:
        pass
    return "tgi"


def check_hf_endpoints():
    token, src = _get_hf_token()
    print("-" * 68)
    print("HF Inference Endpoints (per-model dedicated URLs)  -- MENA models")
    if not token:
        print(f"  credential ({'/'.join(HF_TOKEN_ENV_NAMES)}) : ABSENT")
        print("  status                        : SKIP (set HF_TOKEN to run the MENA arm)")
        return False
    print(f"  credential {src} : present")
    any_deployed = False
    all_ok = True
    for name, url_var in HF_ENDPOINTS:
        raw = os.getenv(url_var)
        if not raw:
            print(f"  {name:12s} ({url_var}) : ABSENT (endpoint not deployed -> model skipped)")
            continue
        any_deployed = True
        base_url = raw.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        model_id = _resolve_endpoint_model(base_url, token)
        ok, detail = _probe(base_url, token, model_id, name)
        all_ok = all_ok and ok
        print(f"  {name:12s} (model={model_id}) : {'PASS' if ok else 'FAIL'}  [{detail}]")
    if not any_deployed:
        print("  status                        : no endpoint URLs set (MENA arm will be skipped)")
        return False
    return all_ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--openrouter-only", action="store_true")
    ap.add_argument("--hf-only", action="store_true")
    args = ap.parse_args()

    # Try to load a .env if the project loader is available (never writes anything).
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        from env_utils import load_env_from_file  # type: ignore
        load_env_from_file()
    except Exception:
        pass

    print("=" * 68)
    print("PROVIDER PREFLIGHT")
    print("=" * 68)

    results = {}
    if not args.hf_only:
        results["openrouter"] = check_openrouter()
    if not args.openrouter_only:
        results["hf-endpoints"] = check_hf_endpoints()

    print("-" * 68)
    print("SUMMARY")
    for prov, ok in results.items():
        print(f"  {prov:12s} : {'READY' if ok else 'NOT READY'}")
    print("=" * 68)
    # Always exit 0 -- diagnostic only.
    return 0


if __name__ == "__main__":
    sys.exit(main())
