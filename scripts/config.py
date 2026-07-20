"""
Shared configuration constants for the refusal audit project.

Centralizes language codes and test models to avoid duplication across scripts.
"""

# Supported languages for prompts and responses
SUPPORTED_LANGUAGES = ["en", "zh", "ja", "id", "ar", "ru", "hi"]

# Models tested in the study.
# Each entry: (display_name, model_id, jurisdiction, provider)
#   provider "openrouter" -> served via OpenRouter (model_id is the OpenRouter slug)
# Serverless roster jurisdiction panel: 4 US developers, 2 Chinese, 1 EU.
# NOTE: The three MENA models — ALLaM (SDAIA/Saudi), Falcon (TII/UAE) and
#       Jais (G42/UAE) — have NO serverless inference provider (verified against
#       OpenRouter, the HF inference router, and featherless-ai directly). They are
#       instead served via dedicated HF Inference Endpoints, configured in
#       ENDPOINT_MODELS below and appended to this roster at import time whenever
#       their endpoint-URL env var is set. A fourth endpoint model — Sarvam
#       (India) — is added the same way. With all endpoints deployed the full
#       panel is 4 US / 2 CN / 1 EU / 3 MENA / 1 India = 11 models. Deploy recipe
#       + smoke test: docs/MENA_HF_ENDPOINT_INTEGRATION.md,
#       docs/INDIA_SARVAM_HINDI_INTEGRATION.md, scripts/smoke_test_endpoint.py.
TEST_MODELS = [
    ("gpt-5.1", "openai/gpt-5.1", "US", "openrouter"),                          # OpenAI
    ("claude-opus-4.5", "anthropic/claude-opus-4.5", "US", "openrouter"),       # Anthropic
    ("gpt-4o", "openai/gpt-4o", "US", "openrouter"),                            # OpenAI (older reference)
    ("grok-4.3", "x-ai/grok-4.3", "US", "openrouter"),                          # xAI (4.5 region-locked for this account)
    ("deepseek-chat-v3.1", "deepseek/deepseek-chat-v3.1", "CN", "openrouter"),  # DeepSeek
    ("qwen3-max", "qwen/qwen3-max", "CN", "openrouter"),                        # Alibaba
    ("mistral-large-2512", "mistralai/mistral-large-2512", "EU", "openrouter"), # Mistral
    # MENA models are served exclusively via dedicated HF Inference Endpoints
    # (see ENDPOINT_MODELS below) and appended at import time when their URL env
    # var is set. No MENA model has a working serverless provider.
]

# --- Dedicated HuggingFace Inference Endpoints (per-model base URL) ----------
# The non-serverless MENA models (ALLaM, Falcon3, Jais) are served via dedicated
# HF Inference Endpoints. Unlike the serverless providers above, each endpoint
# has its OWN base URL, supplied at run time via an env var — so a model is added
# to the roster ONLY when its endpoint-URL env var is set. An undeployed endpoint
# therefore never breaks the working serverless roster.
# Entry: (display_name, hub_repo, jurisdiction, provider, endpoint_url_env_var)
# Deploy recipe + smoke test: docs/MENA_HF_ENDPOINT_INTEGRATION.md,
# scripts/smoke_test_endpoint.py.
ENDPOINT_MODELS = [
    ("allam-7b", "humain-ai/ALLaM-7B-Instruct-preview", "MENA", "hf-endpoint", "ALLAM_ENDPOINT_URL"),
    ("falcon3-10b", "tiiuae/Falcon3-10B-Instruct", "MENA", "hf-endpoint", "FALCON3_ENDPOINT_URL"),
    ("jais-8b", "inceptionai/Jais-2-8B-Chat", "MENA", "hf-endpoint", "JAIS_ENDPOINT_URL"),
    # India: Sarvam (sarvamai), served via a dedicated HF Inference Endpoint like
    # the MENA models. Deployed as a GGUF repo, so the served model id is not the
    # hub repo id — the generator auto-detects it via GET /v1/models (see
    # get_client / _endpoint_model_id in generate_responses.py). Jurisdiction
    # "India"; co-jurisdictional language is Hindi ("hi").
    ("sarvam-30b", "sarvamai/sarvam-30b-gguf", "India", "hf-endpoint", "SARVAM_ENDPOINT_URL"),
]

# display_name -> env var holding that model's dedicated endpoint base URL.
HF_ENDPOINT_URL_VARS = {name: url_var for name, _, _, _, url_var in ENDPOINT_MODELS}

# Append any endpoint model whose URL env var is set at import time. This keeps
# the serverless roster unaffected until an endpoint is actually deployed, and
# means the derived lookups below automatically include deployed endpoints.
import os as _os

# Load .env so the endpoint-URL vars (which live in the user's .env, not the
# shell) are visible when the roster is built below. Every script imports this
# module BEFORE it calls load_env_from_file(), so without this the import-time
# loop would run with the URL vars unset and silently drop every deployed
# endpoint model (symptom: a run reports "9 models" instead of 11). The loader
# is idempotent and never overrides a var already set in the shell. Wrapped in
# try/except so config stays importable even if env_utils is unavailable.
try:
    from env_utils import load_env_from_file as _load_env_from_file
    _load_env_from_file()
except Exception:
    pass

for _name, _repo, _juris, _prov, _url_var in ENDPOINT_MODELS:
    if _os.getenv(_url_var):
        TEST_MODELS.append((_name, _repo, _juris, _prov))

# (display_name, model_id) pairs for scripts that only need those two.
TEST_MODEL_PAIRS = [(name, mid) for name, mid, _, _ in TEST_MODELS]

# Developer jurisdiction lookup by display name.
MODEL_JURISDICTION = {name: juris for name, _, juris, _ in TEST_MODELS}

# Provider lookup by display name ("openrouter" | "hf-endpoint").
MODEL_PROVIDER = {name: provider for name, _, _, provider in TEST_MODELS}

# Model-id lookup by display name (OpenRouter slug or HF "<repo>:<provider>").
MODEL_ID = {name: mid for name, mid, _, _ in TEST_MODELS}

# Model names only (for iteration)
MODEL_NAMES = [name for name, _, _, _ in TEST_MODELS]

# Per-model completion-token ceiling, keyed by display name. Overrides the
# generator's default max_tokens when a model's endpoint has a smaller context
# window than that default. allam-7b is served with max_model_len=4096
# (prompt + completion combined), so a 5000-token completion request is rejected
# outright with HTTP 400 (max_tokens > max_model_len). Capping the completion at
# 3000 leaves ~1000 tokens of headroom for the prompt, which comfortably covers
# every prompt in the batteries (single questions, well under that even in
# Arabic, which tokenizes heavier). Models absent from this map use the
# generator default unchanged.
# Explicit per-model completion-budget override, applied INSTEAD of the global
# --max-tokens default when a model is listed here (see generate_responses.py).
# Two reasons a model needs an override:
#   * Small context window -> cap DOWN. allam-7b is served with
#     max_model_len=4096 (prompt + completion combined), so a 5000-token
#     completion request is rejected outright with HTTP 400. 3000 leaves ~1000
#     tokens of headroom for the prompt, comfortable for every prompt in the
#     batteries (single questions, well under that even in Arabic).
#   * Reasoning ("think") model -> raise UP. sarvam-30b (Sarvam-M, a hybrid
#     think model) always emits a <think>...</think> chain-of-thought before its
#     answer; the reasoning alone can run to a few thousand tokens, so the
#     budget must cover thinking PLUS the answer or .content comes back empty
#     (all budget spent thinking). 8000 leaves ample room; Sarvam's 32K context
#     easily accommodates it. The <think> block is stripped before annotation
#     (see _strip_reasoning in generate_responses.py) so the judge never scores
#     the chain-of-thought.
MODEL_MAX_TOKENS = {
    "allam-7b": 3000,
    "sarvam-30b": 8000,
}

# Provider API base URLs
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Provider -> (base_url, env var holding the API key). Used by the generation
# client factory to bind each subject model to the correct endpoint.
# NOTE: the "hf-router" (featherless-ai serverless) provider was retired once the
# MENA roster moved entirely to dedicated HF Inference Endpoints; no current model
# uses it. Re-add it here if a serverless HF-router model is ever brought back.
PROVIDER_ENDPOINTS = {
    "openrouter": (OPENROUTER_BASE_URL, "OPENROUTER_API_KEY"),
    # Dedicated endpoints share the HF_TOKEN key; base_url is None here because it
    # is per-model (resolved from HF_ENDPOINT_URL_VARS at client-build time).
    "hf-endpoint": (None, "HF_TOKEN"),
}
