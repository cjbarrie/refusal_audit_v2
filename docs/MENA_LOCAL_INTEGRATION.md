# Integrating non-serverless MENA models via local Ollama

**Status: documented alternative — not the route taken.** The MENA arm shipped on
dedicated HF Inference Endpoints (see `MENA_HF_ENDPOINT_INTEGRATION.md`), which is
the primary route. This file is the **zero-cost local fallback**: running the same
three MENA models — ALLaM, Falcon3, Jais, none of which has a serverless provider
— through a local [Ollama](https://ollama.com) server instead. Use it only if you
prefer local inference to a GPU endpoint; nothing here spends money or requires a
cloud key. (It requires enough local RAM/VRAM to run a 7–10B model.)

---

## 1. Why local at all — serverless availability findings

The three MENA models in the roster (ALLaM, Falcon3, Jais) are **not** available
on any serverless provider, so they must be self-hosted. Verified directly
(July 2026), no key required for the checks:

| Model | Developer | Serverless on OpenRouter? | Serverless on HF router / featherless / Together / Novita / Fireworks? |
|---|---|---|---|
| ALLaM-7B-Instruct | SDAIA (Saudi) | no | no (`inferenceProviderMapping` empty; not in featherless catalog) |
| Falcon3-10B-Instruct | TII (UAE) | no | no |
| Falcon-H1-7B-Instruct | TII (UAE) | no | no (also hybrid Mamba arch — most engines can't serve it) |
| Jais-2 (8B / 70B) | Inception/G42 (UAE) | no | no |

Method: queried the OpenRouter model list, the HF inference-router `/v1/models`,
each repo's HF `inferenceProviderMapping` (aggregates every serverless provider),
and the featherless-ai catalog (22,566 models) directly. All three resolved to no
provider on every source. Conclusion: they require self-hosting — either a
dedicated HF Inference Endpoint (the route taken) or, per this doc, local Ollama.
(The earlier serverless MENA candidates Fanar and SILMA resolved to
`featherless-ai (live)` but were dropped from the roster.) Ollama is the lowest-
friction self-host — OpenAI-compatible API, one binary, GGUF pulls from HF.

## 2. Model availability in Ollama

| Model | How to pull | Source |
|---|---|---|
| Falcon3-10B | `ollama pull falcon3:10b` | official Ollama library |
| ALLaM-7B | `ollama pull hf.co/bartowski/ALLaM-AI_ALLaM-7B-Instruct-preview-GGUF:Q5_K_M` | HF GGUF (bartowski, dl 1046) |
| Jais-2-8B | `ollama pull hf.co/inceptionai/Jais-2-8B-Chat-GGUF:Q5_K_M` | HF GGUF (official Inception build) |
| Fanar-1-9B | `ollama pull hf.co/mradermacher/Fanar-1-9B-Instruct-GGUF:Q5_K_M` | HF GGUF (optional; move off serverless) |
| SILMA-9B | `ollama pull hf.co/bartowski/SILMA-9B-Instruct-v1.0-GGUF:Q5_K_M` | HF GGUF (bartowski, dl 1673) |

Notes:
- Prefer **Falcon3-10B** over Falcon-H1: H1 is a hybrid Mamba/attention model that
  llama.cpp/Ollama support unevenly. Falcon3 is a standard transformer.
- Prefer **Jais-2-8B** over the 70B: the 70B needs ~40GB+ even at Q4 and is slow
  on a single consumer GPU / Apple Silicon; the 8B fits comfortably.
- Quantization `Q5_K_M` is a good accuracy/size balance; use `Q4_K_M` if memory-
  constrained. A 9–10B model at Q5 is ~6–7 GB on disk and RAM/VRAM.
- Pin a specific GGUF **quant tag** (the `:Q5_K_M` suffix) so runs are reproducible.

## 3. Code changes required (small — dispatch already generalizes)

The generation layer routes purely on `provider -> (base_url, key_var)` and builds
one cached client per provider (`scripts/generate_responses.py`, `get_client`).
Adding Ollama is therefore two edits in `scripts/config.py` and **zero** edits to
`generate_responses.py`.

### 3a. Register the provider

In `scripts/config.py`, next to the existing base URLs:

```python
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
HF_ROUTER_BASE_URL  = "https://router.huggingface.co/v1"
OLLAMA_BASE_URL     = "http://localhost:11434/v1"   # local Ollama, OpenAI-compatible
```

and in `PROVIDER_ENDPOINTS`:

```python
PROVIDER_ENDPOINTS = {
    "openrouter":  (OPENROUTER_BASE_URL, "OPENROUTER_API_KEY"),
    "hf-endpoint": (None,                "HF_TOKEN"),   # per-model URL, resolved in get_client
    "ollama":      (OLLAMA_BASE_URL,     "OLLAMA_API_KEY"),
}
```

### 3b. Add the models to the roster

Append to `TEST_MODELS` (the `model_id` is the exact Ollama tag you pulled):

```python
    ("allam-7b",    "hf.co/bartowski/ALLaM-AI_ALLaM-7B-Instruct-preview-GGUF:Q5_K_M", "MENA", "ollama"),  # SDAIA / Saudi
    ("falcon3-10b", "falcon3:10b",                                                     "MENA", "ollama"),  # TII / UAE
    ("jais-2-8b",   "hf.co/inceptionai/Jais-2-8B-Chat-GGUF:Q5_K_M",                    "MENA", "ollama"),  # Inception / UAE
```

That is the whole wiring change. `MODEL_PROVIDER`, `MODEL_ID`, `MODEL_JURISDICTION`,
and the up-front credential check all derive from `TEST_MODELS` automatically.

### 3c. The one gotcha — Ollama needs no real key

`get_client` requires `os.getenv(key_var)` to be truthy and fails fast otherwise.
Ollama ignores the API key but the OpenAI client still sends a header, so just
export a dummy value before running:

```bash
export OLLAMA_API_KEY=ollama    # any non-empty string; Ollama does not check it
```

(Alternatively, add a two-line special-case in `get_client` so `provider ==
"ollama"` passes `api_key="ollama"` without reading the env var. The env-var route
is simpler and keeps `get_client` uniform — recommended.)

## 4. Run procedure

```bash
# 1. Install + start Ollama (once)
#    macOS: download from ollama.com, or `brew install ollama`
ollama serve &                       # background server on :11434

# 2. Pull the models (once; ~6–7 GB each at Q5)
ollama pull falcon3:10b
ollama pull hf.co/bartowski/ALLaM-AI_ALLaM-7B-Instruct-preview-GGUF:Q5_K_M
ollama pull hf.co/inceptionai/Jais-2-8B-Chat-GGUF:Q5_K_M

# 3. Smoke-test the endpoint is OpenAI-compatible
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"falcon3:10b","messages":[{"role":"user","content":"Say hi in Arabic."}]}'

# 4. Export the dummy key and run generation for just the local models
export OLLAMA_API_KEY=ollama
python scripts/run_pilot.py --stages generate annotate assemble \
    --batteries perennial --languages en ar ru --n-issues 2
```

The existing resume logic keys on `(prompt_id, prompt_language, model)`, so local
generations interleave with the serverless ones and re-runs skip completed rows.

## 5. Cost & runtime expectations

- **API cost: $0** for the local models (only local GPU/CPU time). The 7
  commercial models stay on OpenRouter and are billed as before; the judge and
  stance-judge calls (also OpenRouter) are unchanged.
- **Runtime** is the real cost. On Apple Silicon (M-series) or a single 24 GB
  GPU, expect very roughly 20–60 tokens/s per 9–10B model at Q5. For the full
  matrix (~1,920 generations per MENA model per full run at ~400 output tokens),
  budget on the order of a few hours per model, serial. Ollama serves one request
  at a time by default; raise throughput with `OLLAMA_NUM_PARALLEL` and by keeping
  `--workers` modest so you don't thrash memory.
- Disk: ~6–7 GB per model at Q5_K_M.

## 6. Downstream / analysis layer

No changes needed beyond `TEST_MODELS`. The R analysis layer already derives model
and jurisdiction factor levels from the roster (`01_data_loading.R` builds
`model_f` and `jurisdiction_f`), and those levels already include the three MENA
models (`ALLaM 7B`, `Jais 8B`, `Falcon3 10B`). Serving them via Ollama instead of
HF endpoints changes only the `provider`/`model_id` on each response record — the
jurisdiction count stays MENA 3 (full panel 10 models), and no downstream prose
needs to change.

## 7. Reproducibility caveat

Local quantized models are **not bit-identical** to the full-precision or
serverless versions, and different GGUF re-quantizers (bartowski vs mradermacher
vs official) can differ slightly. For a defensible paper:
- Pin the exact GGUF repo **and** quant tag in `TEST_MODELS` (done above).
- Record `ollama --version` and the model digest (`ollama show <model>`) in the
  run manifest.
- State in methods that ALLaM/Falcon/Jais were run locally via Ollama at the named
  quantization, distinct from the serverless-served models.
