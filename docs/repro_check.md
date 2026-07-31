# Reproducibility check — committed pipeline vs. frozen English battery

*Verifies that the committed sourcing scripts reproduce the frozen English
battery (`full_prompts_en.json`, `issue_records_full.jsonl`) that was actually
produced in-session, and documents exactly where reproduction is bit-exact vs.
pinned-by-artifact.*

## What was checked

The sourcing stage has one deterministic spine and one stochastic step:

| stage | determinism | how it is verified |
|---|---|---|
| **Stage 1 harvest** (candidates) | deterministic (Wikipedia API) | re-run and diff against frozen `candidate_issues.json` |
| **Stage 3 boundary prompts** | deterministic (fixed template over `positions`) | regenerate from frozen records, diff IDs + text |
| **Stage 3 regular prompts** | **stochastic** (LLM-phrased, temp 0 but not guaranteed identical) | ID scheme verified; text pinned by the frozen artifact, not re-generated |
| **Stage 2 enrichment** | stochastic (LLM extraction) | pinned by the saved `issue_records_full.jsonl`; not re-spent |

Enrichment and regular-question phrasing are LLM calls. Even at temperature 0 an
API model is not guaranteed to return byte-identical text across dates/providers,
and re-running would spend the OpenRouter key. The reproducibility contract is
therefore: **the deterministic spine is bit-exact reproducible from scripts; the
stochastic outputs are pinned by the saved artifacts**, which is why those
artifacts are versioned checkpoints.

## Results

### Stage 1 — candidates (bit-exact)

| | frozen | re-harvested | identical |
|---|---|---|---|
| candidate count | 516 | 516 | ✓ |
| title set | 516 | 516 | ✓ (0 differ) |
| Q-ID set | — | — | ✓ (0 differ) |

The committed `01_harvest_controversial.py --lang en` reproduces the frozen
candidate list exactly on the load-bearing fields (`title`, `qid`). The v2 schema
adds `sources` (route provenance) and `source_edition`; these are additive.

### Stage 3 — boundary prompts (bit-exact modulo a known data artifact)

| | frozen | regenerated | identical |
|---|---|---|---|
| boundary prompts | 774 | 774 | ✓ IDs identical (0 differ) |
| boundary text | — | — | 12 of 774 differ |

The 12 text differences are **entirely explained by 6 duplicated issues**
(`crime_in_the_united_states`, `antisemitism`, `communist_state`,
`lgbtq_rights_by_country_or_territory`, `same_sex_marriage`, `homophobia`). Each
is the *same* article (identical title **and** identical Q-ID) harvested twice
from two sections of the list, so it was enriched twice and the *pre-dedup*
records file carries two different position sets for it; the frozen battery kept
one after de-duplication on Q-ID (the documented "24 dup IDs removed" step). A
7th duplicate, `gnosticism`, is non-political (`is_political=false`) so it never
emitted a boundary prompt.

> **Correction (2026-07-28).** An earlier version of this note described these
> as "two distinct Wikipedia articles slugified to the same `issue_id`" and
> called it a resolved data artifact. That was wrong on the mechanism — they are
> duplicate harvests of one article, which dedup on Q-ID handles correctly. A
> genuine slug collision did exist separately (the ASCII-only slugifier emitted
> an empty slug for non-Latin titles) and is now fixed at source; see
> `docs/REBALANCE.md` §8. It never affected this English-only perennial check,
> which is why the two were conflated.

**After de-duplication the boundary spine is bit-exact.**

### Stage 3 — regular prompts (ID-exact, text pinned)

All 774 frozen regular prompt IDs follow the deterministic `__reg1`/`__reg2`
scheme (verified). The question *text* is LLM-phrased and is pinned by the frozen
`full_prompts_en.json`; it is not re-generated here, to avoid re-spending the key
and because temp-0 phrasing is not guaranteed reproducible.

### Field propagation

Every frozen boundary prompt carries the provenance fields the analysis groups
on: `qid`, `topic_domain`, `contention_score`, `position_side` (A/B). Spot-checked
across a random sample — all present and correct (e.g.
`issue_ireland__bndA`: qid=Q22890, domain=territorial_sovereignty, side=A,
contention=0.495).

## Conclusion

The committed pipeline reproduces the frozen English battery on its full
deterministic spine (candidates bit-exact; boundary prompts bit-exact after the
documented de-dup). Stochastic outputs (enrichment records, regular-question
phrasing) are pinned by the saved artifact checkpoints, which is the correct
reproducibility contract for an LLM-in-the-loop sourcing stage. No unexplained
divergence was found.

*Check data: `data/_repro_check.json`. Reproduce:
`python sourcing/01_harvest_controversial.py --lang en` then compare candidate
sets; regenerate boundary prompts from `issue_records_full.jsonl` via
`sourcing/03_format_prompts.py`'s `BOUNDARY_TEMPLATE`.*
