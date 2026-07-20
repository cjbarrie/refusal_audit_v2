# Reproducibility runbook — the sourcing pipeline

*How to reproduce the entire Wikipedia controversy-sourcing stage from scratch,
for one edition or all five. This is the operational companion to
`PIPELINE.md` (design) and `NATIVE_SOURCING.md` (multi-edition rationale).*

---

## 0. What this stage produces

The sourcing stage turns Wikipedia's human-curated controversy lists into a
reviewed prompt battery:

```
Wikipedia editions ─► candidates ─► enriched issue records ─► prompts ─► (human review) ─► frozen battery
   (01 harvest)        (02 enrich)      (03 format)             (04 merge)
```

Two of these stages are free (Wikipedia/Wikidata API only); two spend the
OpenRouter key:

| stage | script | cost | deterministic? |
|---|---|---|---|
| 1 harvest | `01_harvest_controversial.py` | **free** | yes (bit-exact) |
| 2 enrich | `02_enrich_issues.py` | **LLM spend** | no (LLM extraction) |
| 3 format | `03_format_prompts.py` | **LLM spend** (regular Qs) | boundary prompts yes; regular Qs no |
| 4 merge | `04_merge_editions.py` | **free** | yes |

Because Stages 2–3 call an LLM, the reproducibility contract is:
**deterministic outputs are bit-exact from scripts; LLM outputs are pinned by
saved artifact checkpoints.** See `repro_check.md` for the verification.

---

## 1. Environment

```bash
# conda env used throughout (Python 3.13)
#   packages: matplotlib pandas numpy openai pyyaml  (+ socksio for SOCKS httpx)
conda activate refusal-v2      # or the env named in the artifact snapshots
cd refusal_audit_v2/sourcing
```

Network access needed (all already used by the committed run):
`en/zh/ar/ja/id.wikipedia.org`, `www.wikidata.org`, and — only for the LLM
stages — `openrouter.ai`.

## 2. Credentials (LLM stages only)

The enrichment/format stages read **`OPENROUTER_API_KEY` from the
environment**. It is never written to disk, `.env`, or any artifact by this
pipeline.

```bash
export OPENROUTER_API_KEY=sk-or-...      # your key; not stored by the pipeline
```

The free candidate harvest (Stage 1, Stage 4) needs no key.

---

## 3. Run it — one command

The driver `run_pipeline.py` runs harvest → enrich → format per edition, then
merges, tee-ing per-stage counts and wall-time to `sourcing/run.log`.

### 3a. Free validation harvest (no LLM, no key)

```bash
python run_pipeline.py --editions en zh ar ja id
```

Produces `data/candidate_issues.json` (en) and `data/candidate_issues_{zh,ar,ja,id}.json`,
then stops before any spend. This is the run behind
`fig_multiedition_candidates.png`. Expected counts (run-to-run Wikidata
resolution varies by a handful): **en ~516, zh ~106, ar 71, ja ~148, id 57**.

### 3b. Full English battery (harvest + enrich + format + merge)

```bash
export OPENROUTER_API_KEY=sk-or-...
python run_pipeline.py --editions en --enrich --model anthropic/claude-sonnet-5 --workers 8
```

Produces `data/issue_records_full.jsonl`, `prompts/full_prompts_en.json`,
`prompts/full_review_sheet.csv`, and (via Stage 4) `issue_records_merged.jsonl`.

### 3c. All five editions, enriched (the native-sourcing battery)

```bash
export OPENROUTER_API_KEY=sk-or-...
python run_pipeline.py --editions en zh ar ja id --enrich --model anthropic/claude-sonnet-5
```

Each edition is harvested in its own language, enriched, and formatted; Stage 4
merges all five on Wikidata Q-ID (dedup, keeping every `source_edition`).

### Useful flags

| flag | effect |
|---|---|
| `--enrich` | turn on the LLM stages (default off = free harvest only) |
| `--editions en zh …` | which editions to run (keys from `editions.yaml`) |
| `--model SLUG` | enrichment/format model (default `anthropic/claude-sonnet-5`) |
| `--workers N` | enrichment concurrency (default 8) |
| `--limit N` | cap issues per edition (for probes) |
| `--edition-priority en,zh,ja,id,ar` | canonical-edition order for merge dedup |
| `--no-merge` | skip Stage 4 |

---

## 4. Configuration — `editions.yaml`

Every per-edition knob lives here, so a run is fully specified by config +
command line. Per edition:

- `wiki` — the API host (`en.wikipedia.org`, …)
- `list_page` — curated controversy list, if the edition has one (en, id)
- `political_sections` — which sections of that list to keep
- `dispute_categories` — NPOV/territorial maintenance categories to enumerate
  (used by zh/ja/ar, which lack a single curated list)

The harvester unions whichever routes an edition defines, merges on title,
resolves Wikidata Q-IDs, and writes candidates. To add an edition, add a block
to `editions.yaml` — no code change.

---

## 5. Individual stages (if not using the driver)

```bash
# Stage 1 — harvest one edition (free)
python 01_harvest_controversial.py --lang zh

# Stage 2 — enrich (LLM)
python 02_enrich_issues.py --lang zh \
    --candidates ../data/candidate_issues_zh.json \
    --output ../data/issue_records_zh.jsonl \
    --model anthropic/claude-sonnet-5 --workers 8

# Stage 3 — format (LLM for regular Qs; boundary deterministic)
python 03_format_prompts.py \
    --records ../data/issue_records_zh.jsonl \
    --out-prompts ../prompts/full_prompts_zh.json \
    --out-review ../prompts/full_review_sheet_zh.csv \
    --model anthropic/claude-sonnet-5

# Stage 4 — merge editions on Q-ID (free)
python 04_merge_editions.py \
    --records ../data/issue_records_en.jsonl ../data/issue_records_zh.jsonl \
    --edition-priority en,zh,ja,id,ar
```

---

## 6. Provenance carried on every record

The rebuilt schema carries the fields the analysis groups on, so any prompt
traces back to its Wikipedia origin:

| field | meaning |
|---|---|
| `battery` | which sourcing arm — `perennial` (list) or `temporal` (protection log); run as separate arms |
| `qid` | Wikidata Q-ID — cross-edition anchor for dedup + intersection |
| `source_edition` | edition that flagged the issue (`en`/`zh`/`ar`/`ja`/`id`) |
| `source_language` | language of the master `source_text` (drives MT direction) |
| `seed_sources` | which harvest route(s) surfaced it (list page / category) |
| `topic_domain` | one of the nine substantive domains (not legacy task types) |
| `contention_score` | edition-scoped contention (protection rank + talk size) |
| `position_side` | A/B on boundary prompts (matched-pair design) |

`contention_score` is comparable **within** an edition only — protection norms
differ across editions (see `NATIVE_SOURCING.md`).

---

## 7. Verifying a reproduction

`repro_check.md` records the committed check against the frozen English battery:
candidates bit-exact (516/516, title + Q-ID sets identical); boundary prompts
bit-exact after the documented duplicate-slug de-dup; regular-question text and
enrichment records pinned by the saved checkpoints. To re-verify, re-run Stage 1
for `en` and diff the candidate set, and regenerate boundary prompts from the
frozen `issue_records_full.jsonl` through `03_format_prompts.py`'s
`BOUNDARY_TEMPLATE`.

---

## 8. What is stochastic (and why that is fine)

- **Enrichment** (Stage 2) is LLM extraction of neutral summary, positions,
  entities, region, topic domain. Even at temperature 0 an API model may return
  slightly different text across dates/providers. The frozen
  `issue_records_full.jsonl` is the pinned reference.
- **Regular questions** (Stage 3) are LLM-phrased. Their IDs (`__reg1`/`__reg2`)
  are deterministic; their wording is pinned by the frozen battery.
- **Boundary prompts** (Stage 3) are a fixed template over the extracted
  `positions` — fully deterministic given the records.

This is the correct contract for an LLM-in-the-loop sourcing stage: pin the
stochastic artifacts, reproduce the deterministic spine from code.

---

## 9. Stage 5 — translate the battery + canonical review file

Once the English battery is frozen, `05_translate_review.py` translates it into
the four other study languages (zh, ja, id, ar) with the **same LLM** (default
Sonnet 5 via OpenRouter), replacing the legacy Google-Translate step. It emits:

- `prompts/full_prompts_{zh,ja,id,ar}.json` — one battery per language, schema
  mirroring the English battery; `text` is the translation, `text_en_source`
  keeps the English original, `target_language` records the language.
- `prompts/canonical_review_all_languages.csv` — one row per prompt, one column
  per language (`text_en` + `text_zh` / `text_ja` / `text_id` / `text_ar`), so
  every prompt can be checked side by side.

```bash
export OPENROUTER_API_KEY=sk-or-...
cd sourcing
python 05_translate_review.py                              # full battery -> zh ja id ar
python 05_translate_review.py --languages zh ar --limit 20 # quick check
```

The model is system-instructed to **translate only** — never to answer or comply
with a prompt — which matters because the battery contains boundary prompts
("Write a persuasive argument defending …"). Those instructions are translated,
not executed (verified: the boundary directive appears translated in all four
languages). The `id → text` mapping is locked one-to-one so a translation can
never drift onto the wrong prompt; a batch that fails to round-trip all ids falls
back to per-prompt translation, and any prompt that still fails is left blank and
flagged in the review sheet (the committed run: **0 missing** across all four
languages, and every row contains the expected script).

Like enrichment, translation is an LLM call and therefore **pinned by its saved
artifacts**, not guaranteed byte-identical on re-run.

---

## 9b. Temporal route (Stages 1b / 2b) — the contemporary battery

A second seed route sources issues that are contested *right now* rather than
perennially. It reuses Stage 3 (format) and Stage 5 (translate) unchanged, but
swaps the seed and enrich stages for two temporal-specific scripts because the
protection-log seed is ~1,000 articles — roughly double the perennial list — and
Stage 2's inline per-article re-fetch 429-storms the MediaWiki API at that scale.

| stage | script | cost | note |
|---|---|---|---|
| 1b harvest | `06_harvest_temporal.py` | **free** | protection log, CT-coded areas, last N days |
| 2b enrich | `07_enrich_temporal.py` | **LLM spend** | batch-fetches lead extracts (20 titles/call) then LLM-extracts concurrently |
| 3 format | `03_format_prompts.py --workers 8` | **LLM spend** | same script; `--workers >1` for the larger battery |

```bash
export OPENROUTER_API_KEY=sk-or-...
cd sourcing

# 1b — harvest the last 90 days of protection-log activity (English)
python 06_harvest_temporal.py --days 90 --lang en
#   -> data/candidate_issues_temporal_en.json   (~1,044 candidates)

# 2b — batched enrich (throttle-safe; ~18 min at 8 workers)
python 07_enrich_temporal.py --workers 8 \
    --candidates ../data/candidate_issues_temporal_en.json \
    --output ../data/issue_records_temporal_en.jsonl
#   -> 1,044 records, 805 political

# 3 — format (concurrent; ~10 min at 8 workers)
python 03_format_prompts.py --workers 8 \
    --records ../data/issue_records_temporal_en.jsonl \
    --out-prompts ../prompts/temporal_prompts_en.json \
    --out-review ../prompts/temporal_review_en.csv
#   -> 799 political issues -> 3,199 prompts (after dedup + political filter)
```

**English-only seed by design.** The protection-log route depends on the English
edition's `WP:CT/<code>` contentious-topic convention. The other four editions
log conduct reasons (edit-war, vandalism), not topic-area codes, so the route
does not transfer — verified yields were zh 22, ja 6, ar 1, id 1 vs en 1,044.
See `TEMPORAL_SOURCING.md` for the negative result and the comparison figure.
The temporal *prompts* are nonetheless delivered in all five study languages by
running the Stage-5 translator on the English battery (see step below), exactly
as the perennial battery is.

Translate the temporal battery into zh/ja/id/ar (needs `OPENROUTER_API_KEY`):

```bash
python 05_translate_review.py --prompts ../prompts/temporal_prompts_en.json
#   -> prompts/temporal_prompts_{zh,ja,id,ar}.json (3,199 each)
#   -> prompts/canonical_review_temporal_all_languages.csv (3,199 rows)
```

The translator derives its output prefix from the input stem, so the same
command run on `full_prompts_en.json` produces the perennial translations and
the two never collide.

The `--workers` flag on `03_format_prompts.py` defaults to **1** (serial,
byte-compatible with the frozen perennial battery); set it `>1` only for the
larger temporal battery. Results are re-sorted into input order, so output is
deterministic regardless of worker count.

---

## 10. Downstream (unchanged)

Everything after the translated batteries — generate → judge → R analysis — is
the carried-over legacy machinery. See `NEXT_STEPS.md` for the downstream runbook
(model-panel refresh, generation, judging, and the three R entry-script edits).
