# Annotation pilot runbook

How to run the LLM-judge annotation pipeline on a random subsample of both
batteries. All commands run from `scripts/` in the `refusal-v2` conda env.

## What the pipeline does

```
sample_prompts.py   issue-level stratified subsample of a battery
        │           (keeps matched boundary pairs intact; stratified by topic_domain)
        ▼
generate_responses.py   subject-model responses  (7-model jurisdiction panel)
        ▼
annotation_pipeline.py  4-pass LLM judge  (gemini-2.5-flash-lite)
        │   Pass 1 engagement/refusal (gate) · Pass 2 ideology · Pass 3 moral framing
        ▼
run_pilot.py assemble   route to the R-contract file layout + prompt metadata
        ▼
stance_coding.py        (optional) Pass 4 stance on boundary prompts
```

`run_pilot.py` orchestrates all of it. Everything is keyed off one run
directory: `annotations/<run_id>/`.

## Subject-model roster (config.py `TEST_MODELS`)

| model | slug | jurisdiction |
|---|---|---|
| gpt-5.1 | openai/gpt-5.1 | US (OpenAI) |
| claude-opus-4.5 | anthropic/claude-opus-4.5 | US (Anthropic) |
| gpt-4o | openai/gpt-4o | US (OpenAI, older reference) |
| grok-4.3 | x-ai/grok-4.3 | US (xAI) |
| deepseek-chat-v3.1 | deepseek/deepseek-chat-v3.1 | China (DeepSeek) |
| qwen3-max | qwen/qwen3-max | China (Alibaba) |
| mistral-large-2512 | mistralai/mistral-large-2512 | EU (Mistral) |

Judge: `google/gemini-2.5-flash-lite` (temp 0). Generation temp 1.0.

> **grok note:** `x-ai/grok-4.5` is region-locked for the current OpenRouter
> account ("not available in your region"); `grok-4.3` is the newest xAI model
> that account can reach. Swap the slug in `config.py` if the account changes.

## Run it

```bash
export OPENROUTER_API_KEY="sk-or-..."      # env-only; never write to disk

# 1. See the call budget without spending anything
python run_pilot.py --dry-run

# 2. Draw the subsample (free — no API)
python run_pilot.py --stages sample --n-issues 20 --seed 20260712

# 3. Full pilot: generate -> annotate -> assemble
python run_pilot.py --stages generate annotate assemble \
    --n-issues 20 --seed 20260712 --run-id pilot_v1

# optional Pass 4 stance coding
python run_pilot.py --stages stance --run-id pilot_v1
```

Default sample = **20 issues/battery** (perennial + temporal) × 5 languages ×
7 models = **5,600 generations + ~14,900 judge calls** (~2,800 more if stance
runs). Scale with `--n-issues`; narrow with `--batteries` / `--languages`.

Sampling is **reproducible**: `(battery, seed)` fully determine the issue set.
Re-running `--stages sample` with the same seed reproduces the exact files;
the chosen issue IDs are recorded in `prompts/sampled/<battery>_sample_manifest.json`.

## Output surfaces (per run dir)

- `responses/<battery>_<lang>.jsonl` — raw subject-model responses + full provenance
- `ann/<battery>_<lang>.jsonl` — per-cell annotations
- `annotations_all.jsonl` — **regular-tier** rows, `dataset_type="base"`
- `annotations_<lang>_boundary.jsonl` — **boundary-tier** rows, `dataset_type="boundary"`
- `prompts_meta/test_prompts_<lang>.json` — R-shape metadata (`id`, `category`
  ← topic_domain, `controversy_tier`)

Each annotation row carries the provenance the R pipeline needs without a
rejoin: `battery, controversy_tier, qid, issue_id, region_focus,
position_side, contention_score, topic_domain`.

## R data-loader changes (done — `pipeline/01_data_loading.R`)

`01_data_loading.R` has been updated and validated against a synthetic run dir
in the exact pilot output layout. Four changes were made:

1. **Portable working dir.** The hardcoded `setwd("/Users/solomonmessing/...")`
   is replaced by `setwd(here::here())` (adds a `library(here)` dependency —
   `install.packages("here")` if missing).
2. **Run-dir inputs.** Instead of a fixed `annotations/` path, the loader reads
   from a run dir set by env var:
   ```bash
   REFUSAL_RUN_DIR=annotations/pilot_v1 Rscript pipeline/01_data_loading.R
   ```
   Defaults to `annotations/pilot_v1`. Prompt metadata is read from
   `<run_dir>/prompts_meta/test_prompts_<lang>.json` (override with
   `REFUSAL_PROMPTS_DIR`).
3. **Model factor levels** updated to the new 7-model roster:
   ```r
   levels = c("gpt-5.1", "claude-opus-4.5", "gpt-4o", "grok-4.3",
              "deepseek-chat-v3.1", "qwen3-max", "mistral-large-2512")
   ```
4. **Join-collision fix.** In the v2 schema the annotation records now carry
   `controversy_tier` (via provenance passthrough), which also exists in the
   prompt metadata. The metadata tier is brought in as `meta_controversy_tier`
   to avoid a `.x/.y` join collision; the annotation's `controversy_tier`
   stays authoritative, and the drop-unmatched filter keys off `category`
   (metadata-only). Without this fix the final `filter()` errors with
   `object 'controversy_tier' not found`.

The `battery`, `qid`, and `issue_id` provenance survives the join, so
downstream scripts can split by battery with no extra work. No other R logic
changed — the annotation schema matches the contract field-for-field (see
`docs/ANNOTATION_CONTRACT.md`).

## Environment note

This environment sets `PYTHONSAFEPATH=1`, so a script's own directory is not
auto-added to `sys.path`. Every entry script bootstraps its own dir onto
`sys.path` (two lines near the top) so sibling imports (`config`, `env_utils`)
resolve regardless of launch method.
