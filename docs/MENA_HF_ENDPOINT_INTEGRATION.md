# Integrating non-serverless MENA models via dedicated HF Inference Endpoints

**Status: wired.** The three MENA models — ALLaM, Falcon3, Jais — are the entire
MENA arm and are served exclusively via dedicated
[HuggingFace Inference Endpoints](https://huggingface.co/docs/inference-endpoints)
(GPU-backed, OpenAI-compatible deployments of any Hub model). They live in
`config.ENDPOINT_MODELS` and are appended to `TEST_MODELS` at import time when
their `*_ENDPOINT_URL` env var is set; `generate_responses.py` dispatches to them
via the `hf-endpoint` provider. The former serverless MENA candidates (Fanar via
featherless, SILMA) were **removed** from the roster. This doc is the complete
deploy + smoke recipe. A zero-cost local fallback via Ollama is documented
separately in `MENA_LOCAL_INTEGRATION.md`.

Nothing here spends money until you actually create an endpoint. Auth reuses the
existing `HF_TOKEN`; no new credential type is introduced.

---

## 1. Why dedicated endpoints — serverless availability findings

The three MENA models in the roster have **no** serverless provider on any
source, so each is served via a dedicated HF Inference Endpoint. Verified
directly (July 2026), no key required:

| Model | Developer | Serverless anywhere? | On the Hub (deployable to an endpoint)? |
|---|---|---|---|
| ALLaM-7B-Instruct | HUMAIN/SDAIA (Saudi) | no | **yes** — `humain-ai/ALLaM-7B-Instruct-preview` |
| Falcon3-10B-Instruct | TII (UAE) | no | **yes** — `tiiuae/Falcon3-10B-Instruct` |
| Jais-2-8B-Chat | Inception/G42 (UAE) | no | yes (gated — accept license first) |

Method: queried OpenRouter's model list, the HF inference-router `/v1/models`, each
repo's HF `inferenceProviderMapping` (which aggregates every serverless provider —
featherless, Together, Novita, Fireworks, etc.), and featherless-ai's own catalog
(22,566 models) directly. All three resolve to **no serverless provider on any
source**. Dedicated endpoints are HF's supported path for exactly this case:
serving a Hub model that no provider hosts serverlessly. (The earlier serverless
MENA candidates Fanar and SILMA did resolve to `featherless-ai (live)`, but were
dropped from the roster in favor of an endpoint-only MENA arm.)

## 2. Models — architecture, GPU sizing, TGI-readiness

Verified from each repo's `config.json`:

| Model | Repo | Arch | Params | dtype | Recommended GPU | TGI-native |
|---|---|---|---|---|---|---|
| ALLaM-7B | `humain-ai/ALLaM-7B-Instruct-preview` | `LlamaForCausalLM` | 7B (hidden 4096, 32 layers, ctx 4096) | bf16 (~14 GB) | **Nvidia L4 24 GB** ×1 | yes |
| Falcon3-10B | `tiiuae/Falcon3-10B-Instruct` | `LlamaForCausalLM` | 10B (hidden 3072, 40 layers, ctx 32768) | bf16 (~20 GB) | **Nvidia L40S 48 GB** ×1 | yes |
| Jais-2-8B | `inceptionai/Jais-2-8B-Chat` | (gated) | 8B | bf16 (~16 GB) | Nvidia L4 24 GB ×1 | yes (Llama-family) |

Key points established from the configs:
- **ALLaM and Falcon3 are both `LlamaForCausalLM`.** They serve on stock
  Text-Generation-Inference (TGI) with no custom container. This is the main
  reason the endpoint route is clean for them.
- **Do NOT use Falcon-H1.** `tiiuae/Falcon-H1-7B-Instruct` is
  `FalconH1ForCausalLM` (hybrid Mamba/attention, `model_type: falcon_h1`); TGI
  support is uneven. Falcon3-10B is the standard-transformer Falcon to deploy.
- **Jais-2-8B is a gated repo** (HTTP 401 on config fetch): before deploying you
  must visit the Hub page while logged in and accept the license, using the same
  account that owns `HF_TOKEN`.
- **Falcon3-10B at bf16 (~20 GB) is tight on a 24 GB card** once the KV cache is
  added; L40S (48 GB) gives headroom for batched throughput. If cost matters more
  than speed, an A10G 24 GB works with a short `MAX_INPUT_LENGTH`.

## 3. Creating an endpoint (three ways — pick one)

Each model gets its **own** endpoint with its **own** URL of the form
`https://<random>.<region>.aws.endpoints.huggingface.cloud`.

### 3a. Web console (simplest)
1. https://ui.endpoints.huggingface.co → **New endpoint**.
2. Model repo: `tiiuae/Falcon3-10B-Instruct` (or ALLaM/Jais).
3. Cloud/region: e.g. AWS `us-east-1`. GPU: per the table above.
4. Container: **Text Generation Inference** (auto-selected for Llama arch).
5. Security: **Protected** (requires `HF_TOKEN` on requests) — recommended.
6. Create → wait for **Running** → copy the endpoint URL.

### 3b. Python SDK (`huggingface_hub`) — scriptable
> Requires `pip install huggingface_hub` in your own environment. (It is not
> installed in the analysis env here, and installing it was declined this session;
> run it wherever you deploy.)

```python
from huggingface_hub import create_inference_endpoint

ep = create_inference_endpoint(
    name="falcon3-10b-refusal-audit",
    repository="tiiuae/Falcon3-10B-Instruct",
    framework="pytorch",
    task="text-generation",
    accelerator="gpu",
    vendor="aws", region="us-east-1",
    instance_type="nvidia-l40s", instance_size="x1",   # ALLaM/Jais: "nvidia-l4"
    type="protected",
    custom_image={                                     # TGI container
        "health_route": "/health",
        "url": "ghcr.io/huggingface/text-generation-inference:latest",
        "env": {"MAX_INPUT_LENGTH": "3072", "MAX_TOTAL_TOKENS": "4096",
                "MODEL_ID": "/repository"},
    },
)
ep.wait()                      # block until Running
print(ep.url)                  # -> base for /v1/chat/completions
# ep.pause()  /  ep.delete()   # stop billing when done
```

### 3c. REST API (no extra dependency — uses stdlib only)
`POST https://api.endpoints.huggingface.cloud/v2/endpoint/<namespace>` with a
`Bearer $HF_TOKEN` header and the JSON body mirroring 3b. Poll
`GET .../endpoint/<ns>/<name>` until `status.state == "running"`, then read
`status.url`. Pause/delete via the same endpoint. This is the route to use if you
want deployment scripted from the analysis env without new packages.

## 4. Code changes (SHIPPED)

The `hf-endpoint` provider is now wired into the live pipeline. The generation
layer routes on `provider -> (base_url, key_var)` with cached clients. Dedicated
endpoints differ from a serverless provider in two ways, both handled:
**(1) the base URL is per-model, not per-provider**, and **(2) the served model id
must be sent in the request `model` field** — a placeholder is rejected by newer
TGI (confirmed empirically: a request with `model="tgi"` returns
`404 The model 'tgi' does not exist`). So the client factory resolves the served
id from `GET /v1/models` once per endpoint.

### 4a. `scripts/config.py` — `ENDPOINT_MODELS` block (shipped)

An `ENDPOINT_MODELS` list holds `(display_name, hub_repo, jurisdiction,
"hf-endpoint", url_env_var)` rows. A model is appended to `TEST_MODELS` **only
when its URL env var is set at import time**, so the serverless 7-model roster is
untouched until an endpoint is deployed. The block runs before the derived maps
(`MODEL_PROVIDER`, `MODEL_ID`, `MODEL_JURISDICTION`, `MODEL_NAMES`), so those pick
up any deployed endpoint automatically. `HF_ENDPOINT_URL_VARS` maps each display
name to its URL env var.

Currently defined (all three active): `allam-7b` (`ALLAM_ENDPOINT_URL`),
`falcon3-10b` (`FALCON3_ENDPOINT_URL`), `jais-8b` (`JAIS_ENDPOINT_URL`). Jais is a
gated repo — accept its license on the Hub before deploying its endpoint.

`PROVIDER_ENDPOINTS` **does** get an `hf-endpoint` entry: `(None, "HF_TOKEN")`.
The `None` base URL signals "resolve per-model in `get_client`"; keeping the entry
means the up-front credential-validation loop needs no special case (it only reads
`key_var`). The retired `hf-router` entry was removed once the MENA arm moved
entirely to dedicated endpoints.

### 4b. `scripts/generate_responses.py` — per-model client + id auto-detect (shipped)

- `get_client(provider, model_name=None)` — for `hf-endpoint` the cache is keyed by
  `model_name` (each endpoint gets its own client); the base URL comes from the
  per-model env var via `HF_ENDPOINT_URL_VARS`, `/v1` is appended if absent, and the
  key is `HF_TOKEN`. Immediately after building the client it calls
  `client.models.list()` and caches the first reported id in `_endpoint_model_id`
  (falling back to the hub repo id if the listing is unavailable).
- **Call site:** passes `task["model_name"]` to `get_client`, and for
  `hf-endpoint` sends the auto-detected id (`_endpoint_model_id[...]`) as
  `model_id` instead of the hub repo string.
- **Validation loop:** unchanged — because an endpoint model only enters the
  roster when its URL var is set, and `hf-endpoint` is in `PROVIDER_ENDPOINTS`, the
  existing loop already validates `HF_TOKEN` correctly with no `KeyError`.

Verified: with no endpoint URL set the roster is the clean 9 serverless models;
with `ALLAM_ENDPOINT_URL` set it becomes 10 models including `allam-7b`
(MENA/hf-endpoint); both scripts byte-compile.

### 4c. Reproducibility note on the served id
The `model` field carries the endpoint's actual served id (auto-detected), which
for a single-model TGI endpoint is typically the hub repo id or `/repository`.
This is recorded on every response row via `model_id`, so runs are traceable to
the exact served model.

## 5. Run procedure

```bash
# 1. Deploy the endpoint(s) — console (3a) or SDK/REST (3b/3c). Wait for Running.
# 2. Export each endpoint URL + the HF token
export HF_TOKEN=hf_xxx
export FALCON3_ENDPOINT_URL=https://xxxx.us-east-1.aws.endpoints.huggingface.cloud
export ALLAM_ENDPOINT_URL=https://yyyy.us-east-1.aws.endpoints.huggingface.cloud
# (unset vars simply keep that model out of the roster)

# 3. Smoke-test one endpoint is OpenAI-compatible
curl "$FALCON3_ENDPOINT_URL/v1/chat/completions" \
  -H "Authorization: Bearer $HF_TOKEN" -H "Content-Type: application/json" \
  -d '{"model":"tgi","messages":[{"role":"user","content":"Say hi in Arabic."}]}'

# 4. Run generation (only the deployed endpoint models join the matrix)
python scripts/run_pilot.py --stages generate annotate assemble \
    --batteries perennial --languages en ar ru --n-issues 2

# 5. Stop billing when finished
#    console: Pause/Delete, or SDK: ep.pause() / ep.delete()
```

The resume key `(prompt_id, prompt_language, model)` lets endpoint generations
interleave with serverless ones; re-runs skip completed rows.

## 6. Cost & runtime

- **Billing is per GPU-hour while the endpoint is Running** (not per token). Rough
  current HF rates: L4 ≈ $0.8/hr, A10G ≈ $1/hr, L40S ≈ $1.8–2.5/hr, A100 80 GB ≈
  $4/hr — **check the live pricing page**, these move.
- TGI **batches** requests, so throughput is far higher than a local single-stream
  Ollama. A 10B on an L40S handles one MENA model's ~960 generations/run
  (n_issues=20, both batteries, 6 languages; ~0.5M tokens) in well under
  **1–2 GPU-hours** → on the order of **$1–3 per model per full run**. Keep the
  endpoint paused between runs; enable **scale-to-zero** to auto-pause on idle
  (cold start ~1–3 min on next request).
- The 7 commercial models stay on OpenRouter; judge + stance-judge calls unchanged.

## 7. Downstream / analysis layer

Only `TEST_MODELS` changes. The R layer derives model and jurisdiction factor
levels from the roster (`01_data_loading.R` → `model_f`, `jurisdiction_f`), and
those levels have been updated to the three endpoint models (`ALLaM 7B`,
`Jais 8B`, `Falcon3 10B`). With all three deployed the MENA jurisdiction count is
**3** and the full panel is 10 models (US 4 / CN 2 / EU 1 / MENA 3); `README.md`,
`docs/EXPANSION_RU_MENA.md`, and `NEXT_STEPS.md` reflect this.

## 8. Reproducibility caveat

Dedicated endpoints run the **full-precision** Hub weights (bf16), so — unlike the
Ollama/GGUF fallback — there is no quantization gap; results are as close to the
official model as any hosted serving gets. For the methods section, record: the
exact repo revision (pin `revision=` in `create_inference_endpoint`, or note the
commit SHA), the TGI container tag, the GPU type, and the generation params
(temperature 1.0, as configured). Note that ALLaM/Falcon3/Jais were served via
dedicated HF Inference Endpoints (TGI, full-precision bf16 weights), the sole
MENA arm — no serverless MENA model is in the roster.
