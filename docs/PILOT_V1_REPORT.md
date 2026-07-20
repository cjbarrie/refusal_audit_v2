# Pilot v1 — Multilingual Refusal Audit: Run Report

**Run:** `pilot_v1` · **Date completed:** 2026-07-18
**Design:** 2 batteries (perennial, temporal) × 20 issues each × 4 prompts/issue × 5 languages (en, zh, ja, id, ar) × 7 subject models
**Judge:** `google/gemini-2.5-flash-lite` (temp 0) · **Stance judge:** `openai/gpt-oss-120b`

---

## 1. Completion status — clean

All five stages finished. After last-wins dedup on `(prompt_id, prompt_language, model)`:

| Stage | Unique | Clean | Errors |
|---|---|---|---|
| Responses | 5,600 | 5,598 | 2 |
| Annotations | 5,598 | 5,596 | 2 |
| Stance | 5,598 | 5,598 | 0 |
| Assembled | — | 2,798 regular + 2,798 boundary | — |

The 2 errors are provider-side empty content blocks (temporal_ar, temporal_ja — one each). They cannot be judged, so they drop out of the analysis frame; everything else is complete. Raw line counts on disk were inflated by append-mode resume across multiple launches — this is expected and the dedup key collapses them correctly.

## 2. Data-integrity fix applied during this review

While assembling the analysis frame I found that **every record's `prompt_language` field was stamped `"en"`**, regardless of the prompt's actual language. Root cause: `load_prompts()` in `generate_responses.py` read a top-level `language` key, but the translated prompt files store it under `target_language`, so the field silently defaulted to `'en'`.

- **The prompt _text_ was correctly translated and correctly routed by filename** (verified: `temporal_zh.jsonl` records contain Chinese prompt text). The findings below are therefore accurate — language was recovered from the filename, not the corrupt field.
- **Fixed** the generator to accept either key (`language or target_language`).
- **Repaired all leaf files in place** — corrected `prompt_language` from the filename, removed append-duplicates — and re-ran assemble. The assembled files are now balanced across all five languages.

Without this repair the R pipeline would have collapsed all five languages into "en" and the central cross-language finding would have been invisible.

## 3. Headline finding — language-conditional refusal is a China-model effect

Overall refusal is low (**2.6%**), as expected now that the CSAM-adjacent issues are removed from the battery. But the refusals are not uniform:

**Refusal % by prompt language × developer jurisdiction:**

| language | China | EU | US |
|---|---|---|---|
| ar | 2.8 | 0.0 | 2.2 |
| en | 0.9 | 0.0 | 3.4 |
| id | 2.8 | 0.0 | 2.7 |
| ja | 2.8 | 0.0 | 3.3 |
| **zh** | **9.1** | 0.0 | 2.2 |

US and EU models are flat across languages. **Chinese models jump to 9.1% refusal on Chinese-language prompts** — a 10× increase over their English rate (0.9%).

The effect is entirely **DeepSeek**:

| model | en | zh | ja | id | ar |
|---|---|---|---|---|---|
| deepseek-chat-v3.1 | 0.6 | **16.2** | 5.0 | 5.0 | 5.6 |
| qwen3-max | 1.2 | 1.9 | 0.6 | 0.6 | 0.0 |
| mistral-large-2512 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| (US models) | 0.6–6.9 | 3.1–3.8 | 1.3–5.7 | 0.6–5.6 | 0.0–5.6 |

## 4. The DeepSeek Chinese effect is domain-specific

DeepSeek's Chinese-language refusals concentrate in exactly the politically sensitive domains, and are near-zero elsewhere:

| domain | DeepSeek EN | DeepSeek ZH |
|---|---|---|
| territorial_sovereignty | 0.0 | **37.5** |
| security_conflict | 0.0 | **28.8** |
| governance_democracy | 4.2 | **20.8** |
| civil_rights, economic, religion, social, migration, environment | 0.0 | 0.0 |

Broken down by battery, the effect is driven by the **temporal** battery (28.7% zh refusal) vs perennial (3.8%) — i.e. recent, live geopolitical flashpoints. The specific issues refused in Chinese are India–Pakistan military-conflict pages (Siege of Mirpur, Operation Trident 1971, Battle of Point 4875) and Israel/Palestine-related pages — territorial and security topics where a China-aligned position is politically constrained.

## 5. Secondary signals

- **Tier:** refusal is essentially equal for regular (2.75%) and boundary_testing (2.50%) prompts — the persuasive-defense framing did not itself drive refusals at this sample size.
- **Battery:** temporal (4.0%) refuses more than perennial (1.2%), consistent with live-conflict sensitivity.
- **Refusal justification codes** (among 147 refusals): A (53) dominates, then G (29), C (25), D (25), F (15).
- **Ideology axes** (engaged responses, −2..+2): all jurisdictions sit near-centrist (|mean| < 0.16 on every axis); no strong directional slant is detectable at n≈5,450. This is a null at pilot scale, not evidence of no effect.
- **Stance:** mean |stance| ≈ 1.3 across all jurisdictions — models take substantive positions when they engage; no jurisdiction is systematically more equivocal.

## 6. Deliverables

- `fig_pilot_refusal.png` — two-panel: refusal heatmap (model × language) + DeepSeek EN-vs-ZH domain gap
- `pilot_v1_annotations_tidy.csv` — 5,596 rows, one per prompt×model, deduped + language-corrected, with engagement/refusal/ideology/domain/provenance
- `pilot_v1_combined.csv` — same, with stance_score merged (5,596 matched)
- All leaf files under `annotations/pilot_v1/` repaired in place

## 7. Recommended next steps

1. **Re-run the R loader** (`01_data_loading.R`) against the repaired data to confirm the language field now flows through — the loader keyed off `prompt_language`, so this fix is a prerequisite for every downstream R script.
2. **Significance test** the DeepSeek zh effect (the legacy analysis found deepseek zh vs en significant at p≈0.001; this pilot should reproduce that with a proportion test on the temporal territorial/security cells).
3. **Scale decision:** the zh territorial/security signal is strong enough to see at 20 issues/battery. Scaling temporal depth (more security_conflict issues) would tighten the domain-level estimate.
4. **Investigate the 2 empty-content errors** — check whether they are moderation blocks (a substantive refusal signal) rather than transient failures.
