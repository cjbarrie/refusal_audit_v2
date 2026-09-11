# Ten-model expansion plan

Status: earlier multi-provider planning document, retained for the non-OpenRouter
routes. The current OpenRouter-first expansion supersedes the OpenRouter model
list below and is specified in `docs/OPENROUTER_MODEL_EXPANSION_V1.md`. Neither
plan is part of the current analysis release or authorized for paid execution.

## Frozen panel

| Jurisdiction | Study model | Provider route | Exact provider identifier | Input / output price per 1M tokens | Operational notes |
|---|---|---|---|---:|---|
| China | GLM 4.7 | OpenRouter | `z-ai/glm-4.7` | $0.40 / $1.75 | 204,800-token context |
| China | Kimi K2.6 | OpenRouter | `moonshotai/kimi-k2.6` | $0.95 / $4.00 | 262,144-token context |
| US | Gemini 3.5 Flash-Lite | OpenRouter | `google/gemini-3.5-flash-lite` | $0.30 / $2.50 | Use non-reasoning structured output where supported |
| US | Claude Haiku 4.5 | OpenRouter | `anthropic/claude-haiku-4.5` | $1.00 / $5.00 | Lower-cost Anthropic comparator |
| US | GPT-5.6 Luna | OpenRouter | `openai/gpt-5.6-luna` | $0.10 / $0.60 | Lower-cost OpenAI comparator |
| US | Grok 4.20 | OpenRouter | `x-ai/grok-4.20` | $1.25 / $2.50 | Disable reasoning explicitly. Do not use obsolete `x-ai/grok-4.20-0309-non-reasoning`. |
| US | Command R | OpenRouter | `cohere/command-r-08-2024` | $0.15 / $0.60 | Cohere comparator |
| Europe | Apertus 70B Instruct | EURouter | `apertus-70b` | EUR 0.40 / EUR 2.10 | 65,536-token context; currently routed through European providers AKI.IO/Regolo |
| Europe | EuroLLM 9B Instruct | Hugging Face Inference Endpoint | `utter-project/EuroLLM-9B-Instruct` | endpoint billing | Frozen revision `f7ae2bc3bcbb538c0b93fa6cfbf388d9898b1ace`; vLLM 0.23.0, AWS `us-east-1`, L40S x1, TP=1, max model length 4,096, min/max replicas 0/1, 60-second scale-to-zero |
| Russia | GigaChat 20B A3B Instruct | Friendli dedicated endpoint | `ai-sage/GigaChat-20B-A3B-instruct` | endpoint billing | H100 x1, autoscale 0–1, batch 128, 131K context, approximately 21B total/3B active parameters, MIT license |

Provider prices and availability are planning facts verified at the time the panel was frozen. Re-run preflight and record a dated provider snapshot immediately before generation; do not silently substitute a model when an identifier disappears.

## Credentials and endpoint configuration

Secrets belong only in the root `.env`, which is gitignored and should be mode `0600`. Required variable names are:

```text
OPENROUTER_API_KEY
EUROUTER_API_KEY
HF_TOKEN
EUROLLM_ENDPOINT_URL
FRIENDLI_API_KEY
GIGACHAT_FRIENDLI_ENDPOINT_ID
GIGACHAT_FRIENDLI_ENDPOINT_URL
```

Never put secret values, private endpoint URLs, endpoint IDs, account identifiers, or response reasoning traces in manifests, logs committed to Git, documentation, or interactive assets. EURouter chat requests use `https://api.eurouter.ai/api/v1/chat/completions`. Friendli's dedicated OpenAI-compatible base is `https://api.friendli.ai/dedicated/v1`; the request `model` is the private endpoint ID read from the environment.

## Reproducible execution contract

1. Freeze model identifiers, provider, revision, context limit, decoding parameters, and price snapshot in a dated run manifest.
2. Preflight every route with one harmless request in every study language. Record HTTP status, model-reported identifier, token accounting, and hashes—not response reasoning.
3. Preserve the existing prompt IDs and prompt-language pairing. A provider-specific retry may change transport but never prompt text or decoding policy.
4. Use idempotent keys `(prompt_id, prompt_language, model)` and append-only raw JSONL. Resume with canonical last-valid-record rules.
5. Set reasoning off wherever the API exposes that control; never store hidden reasoning content.
6. Keep generation and annotation as separate costed stages. Validate expected row counts before annotation.
7. Do not add this expansion to `pipeline/make_release.R` until generation and annotation are complete and separately accepted.

## Budget

The planning estimate for full generation is **$381.50**. Generation plus annotation and a 10% contingency is **$552.23**. These are budgeting estimates rather than spend caps; the execution manifest must record actual prompt/completion tokens and provider-reported cost for every request.

## Acceptance gates before integration

- Exactly one valid assembled response per intended key, with missing and terminal-error keys enumerated.
- Provider/model identity agrees with the frozen panel; substitutions require a new plan version.
- Prompt hashes agree with the current frozen battery and translation lock.
- Language/script diagnostics run before substantive annotation.
- No credentials, endpoint identifiers, private URLs, or hidden reasoning appear in tracked files.
- An expansion-specific analysis release is created only after the enlarged sample and changed estimands are documented.
