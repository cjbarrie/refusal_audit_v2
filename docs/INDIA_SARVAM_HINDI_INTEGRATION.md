# India integration: Sarvam model + Hindi edition

**Status:** planned, not yet applied. **Goal:** add an India-jurisdiction model
(Sarvam) on a dedicated HF endpoint, and a Hindi (`hi`) prompt edition, mirroring
the MENA-model + Russian integration already in the repo.

## Why this addition

- **Jurisdiction gap.** The developer panel is US / CN / EU / MENA. India is the
  largest single region in the *temporal* battery (387 issues, 37%) and a
  meaningful slice of perennial (13), yet there is no India-jurisdiction model to
  answer that content. Adding Sarvam closes a structural hole, exactly as the
  MENA models did for Arabic content.
- **Language pairing.** Hindi is the natural co-jurisdictional language (as `zh`
  pairs with DeepSeek, `ar` with the MENA three). North-Indian controversies that
  dominate the India content — Article 370 / Kashmir, CAA, farm laws — are
  natively Hindi-sphere, and Hindi has the best machine-translation quality of the
  candidate Indian languages. Decision: **Hindi only** for now; Bengali/Telugu can
  be added later as further languages if the Hindi result is interesting.

After this change the panel is **11 models** (US 4 / CN 2 / EU 1 / MENA 3 /
**India 1**) × **7 languages** (en, zh, ja, id, ar, ru, **hi**) × 2 batteries.

## The endpoint: Sarvam on HF Inference Endpoints

Target the user named:
`https://endpoints.huggingface.co/new/sarvamai/sarvam-105b-gguf`

This is the same integration path as the MENA endpoints (OpenAI-compatible
`/v1/chat/completions`, base URL held in an env var, `HF_TOKEN` for auth). Two
things differ from allam/falcon/jais and must be handled:

1. **GGUF repo → served model id is not the hub repo id.** The endpoint serves a
   quantized GGUF (llama.cpp / TGI-GGUF). The generator already handles this: for
   `hf-endpoint` providers it calls `c.models.list()` and uses the returned served
   id (`_endpoint_model_id`), falling back to the hub repo id. So the served id is
   auto-detected — no hardcoding needed. **Verify at smoke-test time** that
   `models.list()` returns something (some llama.cpp servers report a single
   generic id; the fallback covers the empty case).
2. **105B is large → context window and cost.** Confirm the endpoint's
   `max_model_len` at deploy. If it is <5000+prompt (as with allam-7b's 4096),
   add a `MODEL_MAX_TOKENS["sarvam-..."]` cap — the clamp mechanism is already in
   `generate_responses.py`. Also: a 105B model on a GPU endpoint bills by
   GPU-hour; scale-to-zero when idle. Budget like the MENA endpoints (~$2–5/model
   /run of GPU time, plus warm-up).

## Exact code touchpoints

Mirror the MENA + `ru` changes. Each is a one- or few-line edit.

### 1. `scripts/config.py` — roster
Add to `ENDPOINT_MODELS` (new jurisdiction value `"India"`):
```python
("sarvam-m", "sarvamai/sarvam-105b-gguf", "India", "hf-endpoint", "SARVAM_ENDPOINT_URL"),
```
- Display name: pick a short stable label (e.g. `sarvam-m` or `sarvam-105b`);
  it becomes the `model` key everywhere, so choose once.
- `HF_ENDPOINT_URL_VARS`, `MODEL_JURISDICTION`, `MODEL_PROVIDER`, `MODEL_ID`,
  `MODEL_NAMES` all derive automatically from `ENDPOINT_MODELS` — no other edit in
  config. The model joins the roster only when `SARVAM_ENDPOINT_URL` is set (same
  lazy-append guard as the MENA models), so the serverless roster is unaffected
  until the endpoint is deployed.
- If the 105B context is tight, add `MODEL_MAX_TOKENS["sarvam-m"] = <cap>`.

### 2. `.env` (user's machine, not in sandbox)
Add `SARVAM_ENDPOINT_URL=https://<your-endpoint>.endpoints.huggingface.cloud`
(and ensure `HF_TOKEN` is already present — it is, for the MENA models).

### 3. `scripts/config.py` — languages
```python
SUPPORTED_LANGUAGES = ["en", "zh", "ja", "id", "ar", "ru", "hi"]
```

### 4. `sourcing/05_translate_review.py` — translation
- Add to `LANG_NAMES`: `"hi": "Hindi"`.
- Add `hi` to the `--languages` default list (or just pass `--languages hi` for
  the incremental run). The script ADDS a `text_hi` column / writes
  `full_prompts_hi.json` + `temporal_prompts_hi.json`, prompt_id-aligned to
  English via the one-to-one `source_text` lock — exactly as `ru` was added.
- Translator model: `anthropic/claude-sonnet-5` (unchanged). Requires live
  `OPENROUTER_API_KEY` — runs on the user's machine.

### 5. `scripts/sample_prompts.py` — sampling
Add `hi` to the hardcoded `LANGS` list (this is the same one-line gap we fixed
for `ru`; without it the sample stage never writes `*_hi_sample.json`).

### 6. `pipeline/01_data_loading.R` — R factors
- `model_f` levels: append the Sarvam display name (keep it grouped after the
  MENA block, or start an India block).
- `jurisdiction_f`: add `model %in% c("sarvam-m") ~ "India"` and add `"India"` to
  the `levels = c("US","CN","EU","MENA")` vector.
- `language_f` levels: add `"hi"`.
- Comment at lines 130–131 documents the model order — keep it in sync.

### 7. Docs
Update `README.md`, `MANIFEST.md`, and the roster/jurisdiction counts wherever
"10 models / 6 languages" appears → "11 models / 7 languages (US 4 / CN 2 / EU 1
/ MENA 3 / India 1)".

## Order of operations (on the user's machine, with live keys)

1. **Deploy the Sarvam endpoint** on HF; copy its URL into `.env` as
   `SARVAM_ENDPOINT_URL`. Confirm `HF_TOKEN` present.
2. **Smoke-test the endpoint** (`scripts/smoke_test_endpoint.py`, or a one-off
   chat call): check `models.list()` returns a usable id and a sample prompt
   returns text. Note the served `max_model_len`; set `MODEL_MAX_TOKENS` if tight.
3. **Preflight** (`sourcing/preflight_providers.py`) — should now show the Sarvam
   model present and `SARVAM_ENDPOINT_URL` resolved.
4. **Translate** both batteries into Hindi:
   `python sourcing/05_translate_review.py --languages hi`
   → produces `full_prompts_hi.json`, `temporal_prompts_hi.json`. Spot-check
   alignment (same prompt_ids as English) and a few translations.
5. **Apply config + R edits** (steps 1,3,5,6 above).
6. **Run.** This is a backfill on the *pilot* (all four annotation passes) OR the
   trimmed full run (Pass 1 only), depending on what stage you're at:
   - Sample stage must include `hi` and re-run so `*_hi_sample.json` exists.
   - Generate/annotate resume incrementally on `(prompt_id, prompt_language,
     model)` — adds only the new `sarvam-m` rows and the new `hi` rows; re-runs
     nothing existing.

## Cost sketch (incremental, per battery-language cell)

Two new axes multiply in:
- **Sarvam across all 7 languages, both batteries** — new generations =
  (existing model-count contribution) → ~1 model × 7 langs × 80 prompts × 2
  batteries ≈ 1,120 generations, plus annotation.
- **Hindi across all 11 models, both batteries** — ~11 × 80 × 2 ≈ 1,760
  generations, plus annotation.
- Overlap (Sarvam × Hindi) counted once. Endpoint GPU-hours billed separately
  (~$2–5 for the Sarvam run). OpenRouter per-token cost for the Hindi generations
  across the 7 serverless + 3 MENA models is modest (same order as the Russian
  backfill, ~$1–2 in tokens).

## What this buys

- A jurisdiction-matched home model for the India content that already dominates
  the temporal battery — the single highest-value roster addition available.
- A 7th language crossing the developer panel, with a clean language knob
  (Hindi asked of all 11 models, not just Sarvam).
- Sets up the eventual **native-sourcing** extension: a Hindi Wikipedia harvest
  could later add India-only contentious topics that the (English-sourced) battery
  misses — but that is a separate, larger step (see `NATIVE_SOURCING.md`).
