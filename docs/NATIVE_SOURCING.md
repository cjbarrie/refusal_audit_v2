# Native-language issue sourcing — design

*Extends the Wikipedia sourcing pipeline so issues are seeded from each
language's own Wikipedia edition, not only from English. The cross-lingual
**language knob is fully preserved**; native sourcing adds a second, crossed
factor. This doc records the design, a live probe (zh + ar), and the schema
changes it needs.*

---

## The problem it fixes

The frozen battery seeds from **English** Wikipedia's *List of controversial
issues* and translates into zh/ja/id/ar. That makes the *asking* multilingual
but leaves *issue selection* Anglophone: a "controversy" is one that English
Wikipedia editors flagged. For an audit whose whole point is cross-jurisdiction
political behavior, letting one language pick the issues is a selection
confound sitting upstream of everything.

**Native sourcing** lets each edition nominate the issues its own community
fights over. The battery becomes the *union* of every edition's contentious
issues.

## The key correction: the language knob is not lost

Sourcing an issue natively and asking it in multiple languages are independent.
Once an issue is identified — in whatever edition — it is **translated into all
five languages** exactly as today. The one-to-one `source_text` lock still
holds; it just points at (say) a Chinese master string for a natively-Chinese
issue instead of an English one. So en-vs-zh on a fixed issue remains a clean
isolated knob. Native sourcing changes only *which issues enter the battery*, not
*how many languages each is asked in*.

## What this unlocks: a crossed 2-factor design

Every issue now carries two things:

- **`source_edition`** — which community flagged it as contentious
- **`prompt_language`** — which language we are currently asking in

These are crossed. The interaction is the new research question:

> Does a model refuse an issue more when asked in the language of the community
> that finds it contentious (**native-match**: a zh-sourced issue asked in zh)
> than in a foreign language (**cross-language**: the same issue asked in en)?

This is strictly more powerful than English-only sourcing, and it dovetails with
the legacy repo's Study B *native-vs-MT* mechanism work.

---

## Probe: how much do native issues differ from the English battery?

Ran the harvest live on **Arabic** and **Chinese** (probe scale), resolved every
native issue to a Wikidata Q-ID, and intersected with the 387-issue English
battery. Overlap by Q-ID:

| edition | native issues | already in EN battery | **new** |
|---|---|---|---|
| Arabic | 71 | 3 (4%) | **68 (96%)** |
| Chinese | 104 | 0 (0%) | **104 (100%)** |
| ar ∩ zh | — | — | 0 shared between the two |

**The overlap is almost nil.** Native editions surface issues the English list
never contained — e.g. Chinese brings Zhenbao Island, the South China Sea
Declaration on Conduct, the Demchok sector, the "Chinese claim on Palawan";
Arabic brings state capture, the Conference of Lausanne, disputed territories of
Northern Iraq, electoral reform framings. This is direct evidence that
English-only sourcing was leaving most of each community's contentious space
unsampled.

![Native sourcing probe]({{artifact:art_8c6883f6-1428-434d-bef7-50a408f44802}})

**Honest caveat on the probe.** The categories I enumerated skew **territorial**
(disputed islands, borders, South China Sea) because those were the cleanest
substantive controversy categories to find quickly. That inflates the raw "new"
count toward `territorial_sovereignty` and undersamples social/moral/governance
issues. A production harvest would union each edition's **NPOV/POV-dispute
maintenance categories** (which tag disputed articles across all domains) with
its curated project lists, lifting topical diversity well beyond what this probe
shows. The 96–100% novelty figure is therefore a floor on distinctiveness, not
an artifact of cherry-picking overlap-free categories — zero of 175 native
issues appearing in the English battery is the load-bearing result.

### Scaled-up validation: all five editions harvested

The committed pipeline (`run_pipeline.py --editions en zh ar ja id`, free
candidate harvest, no LLM) confirms the probe at full harvest scale across all
five editions:

![Five-edition candidate harvest]({{artifact:art_dcb9928e-fea3-499f-93ee-1e11b0566039}})

Of **868 distinct issues** surfaced across the five editions, **852 (98%) appear
in only one edition**; just 16 are shared by two or three. Chinese is **fully
disjoint** — zero Q-ID overlap with any other edition. The overlap that does
exist is almost all with English (en↔id 7, en↔ja 4, en↔ar 3). This is the design
premise made concrete: native-language sourcing surfaces a substantively
different issue set per jurisdiction, which is exactly why the language knob is
worth preserving. Counts: en 516, zh 106, ar 71, ja 148, id 57 (see
`data/multiedition_overlap.json`).

---

## Per-edition harvest routes (verified live)

No single method covers all editions, so the harvester unions three:

1. **Curated project lists** — Indonesian has a direct equivalent
   (`Wikipedia:Daftar isu kontroversial`); Chinese and Japanese have
   "disputed articles" project pages (`有争议条目` / `論争のある記事`); Arabic
   has none. Partial coverage.
2. **Dispute/NPOV maintenance categories** — every edition tags disputed
   articles, but the category *names* are language-specific and must be
   discovered per edition (read the categories on a known-hot seed article, then
   enumerate members). Most complete, language-agnostic route. This is what the
   probe used.
3. **Within-edition contention ranking** — rank each edition's political
   articles by talk-page size + protection level and take the top-N. Needs no
   curated list at all.

Union all three per edition → resolve to Q-IDs → dedupe → political filter.

## Contention signals: within-edition only

Protection level, article length, and talk-page size all return per-edition
through the same API. **But they are not comparable across editions.** For the
Taiwan article: English is extended-confirmed protected, Chinese only
autoconfirmed, Arabic and Japanese unprotected — each community sets its own
protection norms. So `contention_score` is valid for ranking *within* an edition,
not as an absolute cross-edition scale. Store the edition alongside the score.

---

## Caveats that survive (document, don't fix)

- **Translation direction becomes bidirectional.** Today English is always the
  master. With native sourcing a zh-sourced issue's master is Chinese and English
  becomes the MT target — so MT quality now runs both ways. This is not a bug; it
  is precisely the native-vs-MT axis Study B studies. Record `source_language`
  per issue so direction is a known covariate.
- **zh Wikipedia's editor base** is diaspora / Hong Kong / Taiwan / overseas
  (the site is blocked in mainland China). "Contentious on zh.wikipedia" ≠
  "contentious in the PRC" — and this is largest for the jurisdiction the audit
  cares most about. Native sourcing buys *linguistic* authenticity, not
  *national* representativeness. State plainly.
- **Territorial skew in a naive harvest** (see probe caveat) — mitigated by
  unioning NPOV-maintenance categories, but worth checking the topic-domain
  distribution of any native harvest before freezing.

---

## Schema additions

Per issue record (`issue_records_*.jsonl`) and per prompt:

| field | meaning |
|---|---|
| `source_edition` | edition that flagged the issue (`en`/`zh`/`ar`/`ja`/`id`); may be a list if multiple editions flag the same Q-ID |
| `source_language` | language of the master `source_text` (drives MT direction) |
| `qid` | Wikidata Q-ID — the cross-edition anchor for dedup and for the shared-issue intersection |
| `contention_score` | unchanged, but now **edition-scoped** (valid within `source_edition` only) |

`prompt_language` already exists implicitly (the per-language prompt files).
Crossing it with `source_edition` is the new analysis axis.

---

## Two ways to run it (both preserve the language knob)

1. **Parallel batteries.** Keep the translate-through English battery as the
   controlled language-knob experiment; add native batteries as a second study
   ("what does each community find contentious, and do models refuse it?"), then
   analyze the `source_edition × prompt_language` interaction. Cleanest.
2. **Wikidata-anchored intersection arm.** Take issues that appear on *multiple*
   editions' lists (same Q-ID), source the framing natively in each language but
   anchor to one entity. Preserves tight comparability while letting wording be
   native. The probe shows this intersection is currently **tiny** (ar∩zh = 0 at
   probe scale), so this arm would need a broader harvest to be viable — it is a
   refinement, not the main route.

**Recommendation:** parallel batteries as the primary design, with the Q-ID
anchor recorded on every issue so an intersection arm can be built later if the
full harvest produces enough shared issues.

---

## Build steps (when approved)

1. Generalize `01_harvest_controversial.py` → per-edition harvester (three routes
   above), parameterized by `lang`.
2. Add `source_edition` / `source_language` to the enrich + format stages.
3. Run harvest on all five editions; resolve to Q-IDs; dedupe; political filter;
   check topic-domain distribution per edition.
4. Translate every native issue into all five languages (existing
   `translate_prompts.py`, direction-aware).
5. Human-review gate on positions, as now.
6. Downstream generate → judge → R unchanged; add
   `source_edition × prompt_language` to the analysis (new R script).

Probe data: `data/native_sourcing_probe.json`. Figure:
`docs/fig_native_sourcing_probe.png`.