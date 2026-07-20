# Expansion: Russian language + MENA developer arm

This note records the integration of (1) **Russian (`ru`)** as a sixth prompt
language and (2) a **MENA-developer model arm** into the refusal-audit v2
pipeline. It is the authoritative summary of what changed and how to run the
newly-gated steps once credentials are present.

## 1. Roster — up to 10 models, 4 jurisdictions

`scripts/config.py` `TEST_MODELS` is a 7-entry serverless list of 4-tuples
`(display_name, model_id, jurisdiction, provider)`, plus three **endpoint
models** in `ENDPOINT_MODELS` appended to the roster at import time whenever
their `*_ENDPOINT_URL` env var is set:

| model | model_id / hub repo | jurisdiction | provider |
|---|---|---|---|
| gpt-5.1 | `openai/gpt-5.1` | US | openrouter |
| claude-opus-4.5 | `anthropic/claude-opus-4.5` | US | openrouter |
| gpt-4o | `openai/gpt-4o` | US | openrouter |
| grok-4.3 | `x-ai/grok-4.3` | US | openrouter |
| deepseek-chat-v3.1 | `deepseek/deepseek-chat-v3.1` | CN | openrouter |
| qwen3-max | `qwen/qwen3-max` | CN | openrouter |
| mistral-large-2512 | `mistralai/mistral-large-2512` | EU | openrouter |
| allam-7b | `humain-ai/ALLaM-7B-Instruct-preview` | MENA | hf-endpoint |
| falcon3-10b | `tiiuae/Falcon3-10B-Instruct` | MENA | hf-endpoint |
| jais-8b | `inceptionai/Jais-2-8B-Chat` | MENA | hf-endpoint |

Jurisdiction counts with all endpoints deployed: **US 4, CN 2, EU 1, MENA 3**
(10 models total). With no endpoint URLs set the roster is the 7 serverless
models only — an undeployed endpoint never breaks the working roster.

**MENA arm.** The three MENA models — ALLaM (SDAIA/HUMAIN, Saudi), Falcon3
(TII, UAE) and Jais (G42/Inception, UAE) — have **no** serverless inference
provider (verified against OpenRouter, the HF inference router, and
featherless-ai directly). They are served via **dedicated HF Inference
Endpoints**, each a self-hosted TGI deployment with its own base URL. The two
former serverless MENA candidates (Fanar via QCRI, SILMA) were **removed** from
the roster; the MENA arm is now endpoint-only. Deploy recipe + smoke test:
`docs/MENA_HF_ENDPOINT_INTEGRATION.md`, `scripts/smoke_test_endpoint.py`.

## 2. Provider dispatch

The 4th tuple field drives per-model routing in `scripts/generate_responses.py`:

- `PROVIDER_ENDPOINTS = {"openrouter": (https://openrouter.ai/api/v1,
  OPENROUTER_API_KEY), "hf-endpoint": (None, HF_TOKEN)}`. The `hf-endpoint`
  base URL is `None` because it is **per-model**, resolved at client-build time
  from each model's `*_ENDPOINT_URL` env var (`HF_ENDPOINT_URL_VARS`). The old
  `hf-router` (featherless serverless) provider was retired with the Fanar/SILMA
  removal — no current model uses it.
- For endpoint models the served model id is auto-detected once per endpoint via
  `GET /v1/models` (newer TGI rejects a placeholder in the `model` field) and
  cached; it falls back to the hub repo id if the listing is unavailable.
- Transient upstream failures (429/500/502/503/504 + connection/timeout markers,
  incl. HTML error pages) are retried with exponential backoff + jitter (max 4
  attempts). Endpoint replicas scaling up under load are the main source of the
  intermittent 503s this covers; auth / bad-request / content-refusal errors are
  never retried and the stored error is truncated to 500 chars.
- Clients are built lazily and cached (per provider for OpenRouter, per model for
  endpoints), so a run only requires the credentials for the providers its roster
  actually uses. An OpenRouter-only roster does **not** need `HF_TOKEN`.
- Up-front validation: `generate_responses.py` collects the providers named by
  the roster and fails fast with a clear message if any required key env var is
  missing, rather than erroring mid-stream.
- Every response record carries `provider` and the served `model_id`, so a
  refusal is attributable to a known backend.

**Credential requirement for the full 10-model run:** `OPENROUTER_API_KEY`,
`HF_TOKEN`, **and** all three of `ALLAM_ENDPOINT_URL`, `FALCON3_ENDPOINT_URL`,
`JAIS_ENDPOINT_URL` (each pointing at a live HF Inference Endpoint). Verify all
paths with `python sourcing/preflight_providers.py` before a run. None are
present in this workspace yet; add them under Customize -> Credentials (and set
the endpoint URLs in the project `.env`).

## 3. Russian as the 6th language

`config.SUPPORTED_LANGUAGES = ["en", "zh", "ja", "id", "ar", "ru"]`.

- The translator `sourcing/05_translate_review.py` knows `ru` ("Russian") and its
  default `--languages` set includes it. Its canonical-CSV writer is
  **merge-preserving**: translating only `ru` adds a `text_ru` column and does
  **not** re-translate or drop the existing `zh/ja/id/ar` columns (no re-spend).
- Native `ru.wikipedia.org` sourcing was verified viable (179 candidates, 173
  new vs the English battery) but Russian integrates primarily as a
  **translation target** of the frozen English batteries, matching the other
  non-English languages.

**Pending (credential-gated).** Russian prompt files are not yet generated. Run:

```
export OPENROUTER_API_KEY=sk-or-...
python sourcing/05_translate_review.py --languages ru      # perennial battery
python sourcing/05_translate_review.py --languages ru \
       --prompts prompts/temporal_prompts_en.json          # temporal battery
```

This produces `prompts/full_prompts_ru.json` +
`prompts/temporal_prompts_ru.json` and merges `text_ru` into
`canonical_review_all_languages.csv` / `canonical_review_temporal_all_languages.csv`.

## 4. R analysis layer

`pipeline/01_data_loading.R` carries the expansion into the analysis factors:

- `model_f` — up to 10 levels (adds `ALLaM 7B`, `Jais 8B`, `Falcon3 10B`;
  endpoint levels are dropped by ggplot in runs where those models are absent).
- `jurisdiction_f` — canonical US/CN/EU/MENA factor (new; via `case_when`).
- `language_f` — 6 levels (adds `Russian`).
- `boundary_files` gains `annotations_ru_boundary.jsonl`; `all_languages` gains `ru`.

Global enumerations in `08_irr_analysis.R` are 6-language and existence-guarded
(missing per-language boundary files are skipped, not fatal). Study A jurisdiction
factors in `12/14/16` gained a `middle_east` level to match script 10. Scoped
bilingual/trilingual analyses (DeepSeek en-vs-zh; Study A en/zh/ar) were left as
their original scope; ggplot drops unused discrete levels, so the added factor
levels are harmless where a given arm has no MENA/ru rows.

## 5. Budget of the expanded matrix

`scripts/run_pilot.py --dry-run` prints a comparative call+cost table across
three configurations and writes `docs/budget_estimate.json`. Call counts are
exact; USD is estimated from live OpenRouter per-token rates (snapshot in code,
`--refresh-pricing` re-pulls). The three MENA models run on **HF Inference
Endpoints that bill by GPU-hour, not per token**, so their generation calls
carry a **zero per-token rate** and their true cost is endpoint uptime, reported
separately (an indicative ~$1.00/hr per small-GPU replica while deployed).

For the current pilot config (`n_issues=20`, both batteries):

| configuration | gens | judge | stance | ~USD (per-token) |
|---|---|---|---|---|
| baseline (7 OR models x 5 langs) | 5,600 | 14,896 | 2,800 | 19.90 |
| +Russian (7 OR models x 6 langs) | 6,720 | 17,875 | 3,360 | 23.88 |
| +MENA (10 models x 6 langs) | 9,600 | 25,536 | 4,800 | 24.58 |

Marginal per-token cost of Russian (5->6 lang): **+$3.98**; of MENA (7->10
models): **+$0.71** — this is entirely the added judge+stance calls scoring the
MENA responses; the MENA **generations** themselves are $0 per-token (endpoint
GPU-hour billing, tracked separately). Full expanded matrix per run:
**39,936 API calls, ~$24.58 per-token** — of which 6,720 generations bill
OpenRouter and 2,880 hit the three HF endpoints (GPU-hour cost = endpoint uptime
× ~$1.00/hr each, not in the per-token total).

## 6. Validation smoke run (credential-gated — NOT yet run)

Once `OPENROUTER_API_KEY`, `HF_TOKEN` and the four `*_ENDPOINT_URL` vars
(ALLaM, Falcon3, Jais, Sarvam) are set (confirm with
`python sourcing/preflight_providers.py`), a tiny end-to-end smoke over the
expanded matrix (2 issues, perennial only, en+ar+ru+hi, all 11 models):

```
python scripts/run_pilot.py \
  --stages sample generate annotate assemble \
  --batteries perennial --languages en ar ru hi --n-issues 2
```

This exercises HF-endpoint dispatch (allam/falcon3/jais/sarvam), the Russian
and Hindi language columns, and the 5-jurisdiction assembly end-to-end. Verify:
response records carry the right `provider`/`model_id`; `ru` and `hi` rows are
present; assembly routes regular vs boundary tiers; `01_data_loading.R` loads
with up to 11 model levels / 7 language levels / 5 jurisdiction levels.

The smoke above runs **all** annotation passes (incl. stance) on a tiny matrix,
which is the strictest end-to-end exercise. The **production full run** instead
uses Pass-1-only annotation and omits the stance stage — add `--pass1-only` and
drop `stance` from `--stages` (i.e. `--stages generate annotate assemble
--pass1-only`); see `docs/ANNOTATION_TRIM_FULL_RUN.md`. **Status: blocked on
credentials + endpoint deployment.**
