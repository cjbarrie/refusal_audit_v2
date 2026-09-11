# Human-pilot translation approval specification

Status: **authorized and completed on 2026-08-19**.

## Authorized operation

Translate the model response for the frozen 300-row human pilot into literal
English using OpenRouter model `openai/gpt-5.6-luna`. Reasoning must be disabled,
temperature must be zero, and structured JSON must follow
`config/response_translation_prompt_v1.txt` (SHA-256
`427dcc37b06a03e5a4b01682ad1a090ba6436b8d56472c58627cf1b6d2deb9be`).
The sorted source-hash-set SHA-256 is
`62c67e7fdafdd84399a8f353966a345e41765d2e9fefe232bbb1c71120835a77`
and the exact JSONL payload SHA-256 is
`20d73dae282a72790dc1e431ba23307bf5103ca5c9167a81b489aa1f70e85426`.

Each request contains only:

- immutable `review_id` and `source_hash`;
- translation-prompt hash;
- target language;
- English reference prompt;
- target-language prompt;
- unchanged model-response text.

It excludes subject-model identity, developer jurisdiction, home status,
sampling stratum, original engagement/refusal code, Sol/machine labels,
justifications, provider/account metadata, and secrets. Results must be
append-only and resumable. Every row must preserve translation status,
untranslated/uncertain spans, detected language, exact model/provider, usage,
cost, source hash, and prompt hash. No hidden reasoning may be requested or
stored.

## Frozen volume and current price snapshot

The local, no-network `o200k_base` estimate is:

- 300 requests;
- 452,001 input tokens if the instruction is never cached;
- 417,521 conservative planning output tokens.

OpenRouter listed GPT-5.6 Luna at $0.10 per million input tokens and $0.60 per
million output tokens, advertised as 50% discounted, when checked on
2026-08-19: <https://openrouter.ai/openai/gpt-5.6-luna-20260709>.
At those list rates the conservative estimate is:

```text
452,001 × $0.10 / 1,000,000 = $0.0452001
417,521 × $0.60 / 1,000,000 = $0.2505126
total                         = $0.2957127
```

The proposed hard provider-cost ceiling is **$3.00**, not a spending target.
It provides room for structured-output retries and unexpectedly verbose literal
translations while remaining an order of magnitude above the conservative
estimate. A runner must stop before launch unless both the frozen manifest and
command line contain this exact authorization and ceiling; it must also stop
before a request whose worst-case reservation could cross the ceiling.

For comparison, the same conservative token volume would cost approximately
$0.212 at the listed Gemini 2.5 Flash-Lite rates ($0.10/$0.40 per million) and
$2.540 at Claude Haiku 4.5 rates ($1/$5 per million), checked on the same date:
<https://openrouter.ai/google/gemini-2.5-flash-lite/api> and
<https://openrouter.ai/anthropic/claude-haiku-4.5/>. Luna is proposed because
the absolute premium over Flash-Lite is about eight cents for this frozen
packet while retaining the stronger-model margin appropriate for malformed and
mixed-language text.

## Execution record

The user authorized the exact payload, prompt, model, purpose, and $3.00 ceiling
in one instruction. The runner recorded that authorization in the frozen pilot
manifest and required a second command-line flag before transmission.

- Unique completed source rows: 300/300.
- Assembled translation SHA-256:
  `54ce25a0df54fde3020f82156815f0275d6e4ed5c444aff0ff02e511196585a6`.
- Append-only raw-log SHA-256:
  `ea41705f9a396db6a38f0f3a376cc8a52d95e5a44a6cb46781fa2e0eb66a1ef4`.
- Blinded 336-task Parquet SHA-256:
  `9b865d437566142e0bf7e74eebf5f9c8f1e8578ad220932a9aede49b084e87da`.
- Provider-reported cumulative cost: **$0.8759864**.
- Authorized ceiling: $3.00.
- Provider model on successful records: `openai/gpt-5.6-luna`.
- Provider allowlist: OpenAI only; fallbacks disabled.
- Reasoning tokens: zero.
- Translation status: 230 complete, 70 partial.
- Rows with explicit uncertainty spans: 104.
- Empty English translations: zero.
- Blinded review packet: 300 unique source tasks plus 36 hidden repeats.

The raw append-only log contains 439 records: 386 full-row successes (including
86 duplicate successes from an overlapping early resume), 22 full-row parse
errors, 24 successful chunk/subchunk translations, and seven chunk parse
errors. Every record contributes to the cumulative cost. A filesystem advisory
lock was added immediately after detecting the overlap, and all subsequent
resumes held that lock.

Three rows initially exhausted their structured-output token allowance. Two
succeeded after a larger allowance. One unusually long, garbled Arabic response
expanded pathologically and still truncated at approximately 9.7k, 19.8k, and
39.6k output tokens. It was translated using deterministic, lossless chunks of
the identical authorized response; only failing chunks were recursively split.
The concatenation assertion guarantees byte-for-byte source coverage, and all
chunk records and hashes are preserved. The final human-facing translation is
marked partial rather than silently treated as unproblematic.

The executed command sequence is retained here as provenance, not as an
instruction to rerun a completed paid operation:

```bash
python scripts/response_validity.py authorize-translation \
  --payload-sha 20d73dae282a72790dc1e431ba23307bf5103ca5c9167a81b489aa1f70e85426 \
  --prompt-sha 427dcc37b06a03e5a4b01682ad1a090ba6436b8d56472c58627cf1b6d2deb9be \
  --model openai/gpt-5.6-luna --cost-ceiling 3.00 \
  --confirm-user-authorization
python scripts/response_validity.py translate \
  --cost-ceiling 3.00 --authorize-paid-translation
python scripts/response_validity.py translate-chunked \
  --review-id 07b260d775a6f3e7931991b7 \
  --cost-ceiling 3.00 --authorize-paid-translation
python scripts/response_validity.py assemble-review \
  --translations annotations/response_validity_human_v2/translations_assembled.jsonl
```

Authorization to translate does not authorize surrogate labeling, population
labeling, adjudication, or any other external transmission.
