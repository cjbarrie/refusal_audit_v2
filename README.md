# refusal_audit_v2

A fresh build of the LLM political-refusal audit, rebuilt around a
**disciplined, externally-anchored question-sourcing pipeline**.

## What is different from the legacy repo

The legacy project (`../refusal_audit`) sourced its prompt battery by
drafting questions with GPT-4o. This version replaces the *sourcing* stage
with a pipeline that seeds from **Wikipedia's human-curated
`List of controversial issues`**, enriches each issue with structured
information, and formats issues into matched regular + boundary prompts.
Everything downstream of sourcing — model generation, the LLM-as-judge
annotation passes, and the R analysis pipeline — is carried over unchanged
so results remain comparable.

Two seed routes feed the identical enrich → format → translate stages:

- **Perennial route** (main) — `Wikipedia:List of controversial issues`, a
  curated list of long-contested topics. Frozen English battery: **387 issues
  → 1,548 prompts**.
- **Temporal route** (`docs/TEMPORAL_SOURCING.md`) — the MediaWiki *protection
  log*, which surfaces what is being politically fought over *right now*.
  English-only **at the seed stage** (the route does not transfer to other
  editions — see the doc). Run: **799 political issues → 3,199 prompts**, fully
  disjoint from the perennial battery on Wikidata Q-ID.

Both batteries are English-sourced and then **translated into the study
languages** via `sourcing/05_translate_review.py` (sonnet-5), so the
cross-language refusal contrast runs on both. Six languages are supported
(`en/zh/ja/id/ar/ru`); five are frozen and **Russian (`ru`) is wired but not yet
generated** (`--languages ru`, needs `OPENROUTER_API_KEY`).

Subject panel: up to a **10-model jurisdiction panel** (US 4 / CN 2 / EU 1 /
MENA 3). Seven models route via OpenRouter (`OPENROUTER_API_KEY`); the three MENA
models (`allam-7b`, `falcon3-10b`, `jais-8b`) are each served on a **dedicated HF
Inference Endpoint** (`HF_TOKEN` + per-model `*_ENDPOINT_URL`), joining the roster
only when their endpoint URL is set. See `docs/NEXT_STEPS.md` for the roster and
`docs/MENA_HF_ENDPOINT_INTEGRATION.md` for the deploy recipe.

The legacy repo is treated as **reference-only**. We copy the reusable
machinery here once and do not refashion it in place. See `MANIFEST.md`
for exactly what was copied, built fresh, or deliberately left behind.

## Layout

```
sourcing/    NEW: Wikipedia seed -> enrich -> format -> translate pipeline (Stages 1-5, + 1b/2b temporal)
prompts/     frozen prompt batteries: {full,temporal}_prompts_{en,zh,ja,id,ar}.json + canonical review CSVs
responses/   model outputs (written under annotations/<run_id>/responses/)
annotations/ judge scores, one run dir per pilot/run (annotations/<run_id>/)
pipeline/    R analysis (01_data_loading.R ... 16_*.R); 01 patched for v2, 02-16 pending setwd fix
scripts/     Python machinery: sampling, generation, 4-pass judge, stance, config, pilot driver
data/        intermediate sourcing artifacts (candidate lists, issue records)
docs/        design docs, sourcing rationale, reproducibility + annotation runbooks
```

## Pipeline in one line

```
Wikipedia controversy lists (en / zh / ar / ja / id)
  -> harvest (Stage 1) -> enrich (Stage 2) -> format (Stage 3) -> merge on Q-ID (Stage 4)
  -> human review -> freeze full_prompts_{lang}.json
  -> [UNCHANGED] generate responses -> LLM-as-judge -> R analysis -> papers
```

Reproduce the whole sourcing stage with one command:

```bash
cd sourcing
python run_pipeline.py --editions en zh ar ja id            # free candidate harvest (no key)
python run_pipeline.py --editions en --enrich               # full English battery (needs OPENROUTER_API_KEY)

# temporal route (English seed): harvest -> batched enrich -> format
python 06_harvest_temporal.py --days 90 --lang en
python 07_enrich_temporal.py --workers 8                    # batched enricher (needs OPENROUTER_API_KEY)
python 03_format_prompts.py --records ../data/issue_records_temporal_en.jsonl \
       --out-prompts ../prompts/temporal_prompts_en.json \
       --out-review ../prompts/temporal_review_en.csv --workers 8

# translate either battery into zh/ja/id/ar (needs OPENROUTER_API_KEY)
python 05_translate_review.py --prompts ../prompts/full_prompts_en.json
python 05_translate_review.py --prompts ../prompts/temporal_prompts_en.json
```

Docs — sourcing:
- `docs/PIPELINE.md` — full design
- `docs/REPRODUCIBILITY.md` — step-by-step runbook (env, keys, every flag)
- `docs/NATIVE_SOURCING.md` — why/how of native-language multi-edition sourcing
- `docs/TEMPORAL_SOURCING.md` — the contemporary protection-log route (English seed, translated to all five languages)
- `docs/repro_check.md` — verification against the frozen English battery

Docs — downstream (generation → judge → R):
- `docs/NEXT_STEPS.md` — downstream runbook (sample → generate → judge → R)
- `docs/ANNOTATION_CONTRACT.md` — the R pipeline's input contract the annotation stage satisfies
- `docs/ANNOTATION_RUNBOOK.md` — how to run the annotation pipeline (roster, stages, R-loader changes)
- `docs/R_PIPELINE_WALKTHROUGH.md` — the 23-script R analysis layer
