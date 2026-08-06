# The annotation → R-analysis contract

The R analysis pipeline (`pipeline/*.R`) stays in R. Our job is to make the
Python annotation pipeline emit files whose **columns, value encodings, file
layout, and join keys** exactly satisfy what `01_data_loading.R` reads. This
document is that contract.

## How `01_data_loading.R` assembles its table (so we match it)

It merges **two** things:

1. **Annotation records** (one row per model response), read from:
   - `annotations/annotations_all.jsonl` → tagged `dataset_type = "base"` (the regular-tier responses)
   - `annotations/annotations_<lang>_boundary.jsonl` (en/zh/ja/id/ar) → tagged `dataset_type = "boundary"`
   - error records (`"error"` key present) are excluded from boundary files.
2. **Prompt metadata**, read from `prompts/test_prompts_<lang>.json` → uses only
   `id → prompt_id`, `category`, `controversy_tier`.

Join key: **`(prompt_id, prompt_language, dataset_type)`**. Then it drops base
rows whose tier is `boundary_testing`, and rows with no metadata match.

So there are **two output surfaces we must produce**: the annotation JSONL
files *and* prompt-metadata JSON files, in this exact layout, with these keys.

## Column contract — annotation records

The legacy `scripts/annotation_pipeline.py` already emits this. ✓ = already produced.

| column | type / values | produced by | R uses it for |
|---|---|---|---|
| `prompt_id` | string | ✓ Pass metadata | join key |
| `prompt_language` | `en/zh/ar/ru/hi` | ✓ | join key, language effects (`ja`/`id` were dropped as study languages in 2026-07) |
| `response_language` | detected string | ✓ | language-match checks |
| `model` | model slug | ✓ | the model factor (levels set in R) |
| `prompt_category` | string | ✓ | category tables |
| `engagement_code` | **int 1–5** | ✓ Pass 1 | `engaged=(≤3)`, `refused=(≥4)`, 5-pt scale |
| `refusal_justification` | `A`–`G` or null | ✓ Pass 1 | refusal-reason tables (script 05) |
| `refusal_justification_other` | string/null | ✓ Pass 1 | free-text overflow |
| `economic_left_right` | int −2..+2 (null if refused) | ✓ Pass 2 | ideology (script 03) |
| `social_left_right` | int −2..+2 (null if refused) | ✓ Pass 2 | ideology |
| `authoritarian_libertarian` | int −2..+2 | ✓ Pass 2 | ideology (extended) |
| `populist_elitist` | int −2..+2 | ✓ Pass 2 | ideology (extended) |
| `care_harm` … `liberty_oppression` (6) | 0/1 (null if refused) | ✓ Pass 3 | moral foundations (script 03/03c) |
| `dominant_foundation` | string/null | ✓ Pass 3 | moral foundations |
| `judge_model` | model slug | ✓ (added 2026-08) | **which judge produced this verdict** |
| `judge_prompt_version` | 12-char hash | ✓ (added 2026-08) | guards reliability statistics against codebook drift |
| `annotation_run_id` | string | ✓ (added 2026-08) | ties a multi-judge panel run together |

### Judge identity (added 2026-08-04, for the multi-judge panel)

Before this, an annotation record had **no way to say which judge produced it** —
the `model` column is the SUBJECT model, not the judge. That made a panel
unreadable: two judges' verdicts on the same response were indistinguishable.

`judge_prompt_version` is a hash of the Pass 1–3 template text, computed at
import time. Editing a codebook changes it automatically, and
`pipeline/24_measurement.R` **refuses to pool** verdicts carrying different
versions — otherwise an agreement statistic would be measuring template drift
rather than rater disagreement.

**These fields are additive.** `annotations_all.jsonl` keeps its exact previous
shape, so `01_data_loading.R` and scripts `02`–`30` are unaffected whether or not
a panel exists. The panel is consumed only through the separate long-format
surface below.

| surface | shape | read by |
|---|---|---|
| `annotations_all.jsonl` | one row per response (**anchor judge**) | `01_data_loading.R` — UNCHANGED contract |
| `annotations_<lang>_boundary.jsonl` | boundary tier, anchor judge | `01_data_loading.R` — UNCHANGED |
| `annotations_panel.jsonl` | **long: one row per (response × judge)** | `24_measurement.R` only |

**`engagement_code` is the single load-bearing field** — every engagement/refusal
number in the paper derives from it. The 1–5 scale and the `≤3 engaged / ≥4
refused` cut must not drift.

## Column contract — prompt-metadata files (`prompts/test_prompts_<lang>.json`)

R reads exactly three fields from each prompt: `id`, `category`,
`controversy_tier`. Structure R expects: `{ "prompts": [ {id, category,
controversy_tier, ...} ] }`.

- **`controversy_tier`** must contain the literal string **`"boundary_testing"`**
  for boundary prompts (R filters on that exact value). Regular prompts: any
  other value (legacy used `"regular"`).
- **`category`** is what feeds the by-category tables.

## Gaps / decisions (the whole job is here)

Everything above is already produced by the legacy annotator. The real work is
these five items:

1. **Run on the *new* v2 batteries, not the old ones.** The annotator must read
   `prompts/full_prompts_<lang>.json` (perennial arm, 1,548/lang) and
   `prompts/temporal_prompts_<lang>.json` (temporal arm, 3,199/lang) and generate
   model responses, then judge them. Both arms now exist in all five study
   languages (en/zh/ja/id/ar), so the annotator iterates over language as well
   as battery. Our prompt files already use the tier values R expects —
   `regular` / `boundary_testing` — plus a `battery` tag, so no tier rename is
   needed. The assemble stage writes the `prompts_meta/` metadata files in R's
   expected shape directly (verified against `01_data_loading.R`).
2. **`category` ← `topic_domain`.** Our new scheme replaced legacy task-type
   categories with 9 `topic_domain` values. Map `topic_domain → category` in
   the metadata files so R's category tables populate. (Keep `battery`,
   `qid`, `region`, `topic_domain` as extra columns — R ignores unknowns.)
3. **Model set.** The OpenRouter roster is now 7 models — gpt-5.1 /
   claude-opus-4.5 / gpt-4o / grok-4.3 / deepseek-chat-v3.1 / qwen3-max /
   mistral-large-2512 (US / China / EU jurisdiction panel). The model factor
   levels in `01_data_loading.R` have been updated to match. (Two other R edits
   landed alongside: portable `here::here()` working dir, and a join-collision
   fix for the provenance `controversy_tier` — see `ANNOTATION_RUNBOOK.md`.)
4. **File layout.** Write regular-tier annotations to `annotations_all.jsonl`
   and boundary-tier to `annotations_<lang>_boundary.jsonl`. Both arms now have
   translated batteries (zh/ja/id/ar) in addition to English, so the `<lang>`
   dimension is live — plan for one annotation stream per (battery × language).
   The `source_language` field on each prompt records which edition it is.
5. **Optional stance / alignment passes.** `stance_score` (script 12) comes from
   `stance_coding.py`; `stance_primary`/`stance_secondary` are two judges;
   `ccp_aligned`/`state_aligned` feed the DeepSeek deep-dive (06/07). Port these
   only if we run those specific analyses — decide alongside item 3 in
   `R_PIPELINE_WALKTHROUGH.md`.

## Bottom line

We are **not designing a schema** — the legacy annotator already matches
R's contract field-for-field. This work is now **built and validated**:
(a) the annotator points at the v2 prompt batteries, (b) the assemble stage
writes prompt-metadata in R's expected shape with `topic_domain→category`
(the `boundary_testing` tier already matches — no rename), (c) the 7-model
roster is set and `01_data_loading.R` is patched (model levels + portable
path + provenance join-collision fix), and (d) outputs are written into the
`annotations_all.jsonl` + `annotations_<lang>_boundary.jsonl` layout. The end
-to-end chain (sample → generate → annotate → assemble → R load) has been run
against a synthetic run dir. See `ANNOTATION_RUNBOOK.md` for the run commands.
