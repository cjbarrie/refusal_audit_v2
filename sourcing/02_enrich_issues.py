#!/usr/bin/env python3
"""
Stage 2 - Enrich each issue into a structured record.

For each candidate issue (from Stage 1) gather a FIXED schema so every issue
is treated identically:

  neutral_summary   article lead (MediaWiki API extract, intro only)
  positions {A,B}   the two opposing sides of the controversy (LLM-extracted,
                    flagged for human review)
  key_entities      people / parties / countries named (LLM-extracted)
  region            country / polity salience (LLM-assigned from a fixed list)
  topic_domain      substantive domain the controversy is ABOUT (LLM-assigned
                    from TOPIC_DOMAINS; replaces the legacy task-type category)
  contention_score  composite of page-protection level + talk-page size
  provenance        title, qid, rev_id, snapshot date, source url

The neutral_summary and all contention signals are PURE API (no key needed).
Only positions/key_entities/region/topic_domain require an LLM. The LLM call is
injected via `llm_fn` so the same code drives either OpenRouter (default, for
the user) or an in-session model (for the probe).

Output:
  data/issue_records.jsonl   one JSON object per issue
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
UA = "refusal-audit-research/0.1 (academic LLM political-behavior audit)"

# Substantive TOPIC DOMAINS: what the controversy is fundamentally ABOUT.
# This replaces the legacy 8-category *task-type* taxonomy. The old scheme
# (candidate_comparison, image_generation, strategic_advice, ...) described the
# task you asked the model to perform; those buckets do not arise from a list of
# controversial topics, so forcing issues into them meant shoehorning. Here the
# label is a readout of the seed controversy, not a target to hit.
TOPIC_DOMAINS = {
    "territorial_sovereignty": "statehood, secession, independence, border and territorial disputes",
    "governance_democracy": "political systems, regime legitimacy, elections, corruption, state institutions",
    "civil_rights_liberties": "free expression, privacy/surveillance, discrimination, minority and LGBTQ rights",
    "social_moral": "abortion, capital punishment, drugs, sexuality, bioethics, marriage and family",
    "economic_policy": "taxation, trade, labor, welfare, regulation, inequality",
    "religion_state": "secularism, religious freedom, blasphemy, church-state relations",
    "security_conflict": "war, terrorism, military intervention, nuclear weapons, armed conflict",
    "environment_energy": "climate change, energy, pollution, conservation",
    "migration_nationalism": "immigration, refugees, nationalism, ethnic and national identity",
}
TOPIC_DOMAIN_KEYS = list(TOPIC_DOMAINS)

# Fixed region vocabulary for salience tagging (mirrors the legacy regional
# balance targets: US, China, Europe, Japan, Indonesia, Arab, General).
REGIONS = ["US", "China", "Europe", "Japan", "Indonesia", "Arab", "Russia", "India", "General"]

# Ordinal weight for the most restrictive edit-protection level on a page.
PROTECTION_RANK = {
    "": 0,
    "autoconfirmed": 1,
    "extendedconfirmed": 2,
    "templateeditor": 3,
    "sysop": 3,
}


def api(params: dict, wiki: str = "en.wikipedia.org") -> dict:
    params = {**params, "format": "json"}
    url = f"https://{wiki}/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 5:
                wait = int(e.headers.get("Retry-After", 0)) or (5 * (attempt + 1))
                time.sleep(wait)
                continue
            if attempt == 5:
                raise
            time.sleep(2.0 * (attempt + 1))
        except Exception:  # noqa: BLE001
            if attempt == 5:
                raise
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError("unreachable")


def fetch_issue_data(title: str, wiki: str = "en.wikipedia.org", talk_prefix: str = "Talk:") -> dict:
    """Pure-API portion: lead extract + contention signals + provenance.

    wiki        : MediaWiki host for this edition (contention signals are
                  edition-scoped and NOT comparable across editions).
    talk_prefix : localized Talk-namespace prefix for the edition.
    """
    # Lead extract (intro only, plaintext)
    d = api(dict(action="query", prop="extracts", exintro=1, explaintext=1,
                 titles=title, redirects=1), wiki=wiki)
    page = list(d["query"]["pages"].values())[0]
    resolved_title = page.get("title", title)
    summary = page.get("extract", "").strip()

    # Article info: protection level, byte length, latest revid
    di = api(dict(action="query", prop="info|revisions", inprop="protection",
                  rvprop="ids|timestamp", titles=resolved_title, redirects=1), wiki=wiki)
    pi = list(di["query"]["pages"].values())[0]
    protections = pi.get("protection", [])
    edit_prot = ""
    for pr in protections:
        if pr.get("type") == "edit":
            edit_prot = pr.get("level", "")
    prot_rank = PROTECTION_RANK.get(edit_prot, 1)
    art_len = pi.get("length", 0)
    revs = pi.get("revisions", [{}])
    rev_id = revs[0].get("revid") if revs else None

    # Talk-page size (proxy for volume of dispute)
    dt = api(dict(action="query", prop="info", titles=talk_prefix + resolved_title, redirects=1), wiki=wiki)
    pt = list(dt["query"]["pages"].values())[0]
    talk_len = pt.get("length", 0)

    # Composite contention score: normalized protection rank (0-1) averaged with
    # normalized log talk-page size. Coarse, but reproducible and monotone.
    prot_norm = prot_rank / 3.0
    talk_norm = min(math.log10(talk_len + 1) / 6.0, 1.0)  # ~1.0 at 1MB talk page
    contention = round(0.5 * prot_norm + 0.5 * talk_norm, 3)

    return {
        "title": resolved_title,
        "neutral_summary": summary,
        "contention_score": contention,
        "contention_signals": {
            "edit_protection": edit_prot or "none",
            "protection_rank": prot_rank,
            "article_bytes": art_len,
            "talk_bytes": talk_len,
        },
        "provenance": {
            "rev_id": rev_id,
            "snapshot": date.today().isoformat(),
            "url": f"https://{wiki}/wiki/" + urllib.parse.quote(resolved_title.replace(" ", "_")),
        },
    }


EXTRACTION_SYSTEM = (
    "You are a political-science research assistant helping build an audit of how "
    "language models handle politically contentious topics. You extract structured, "
    "NEUTRAL metadata about a controversy. You never take a side; you report the "
    "sides as they exist in public debate."
)


def build_extraction_prompt(title: str, summary: str) -> str:
    doms = "\n".join(f"    - {k}: {v}" for k, v in TOPIC_DOMAINS.items())
    regs = ", ".join(REGIONS)
    return f"""Below is the lead section of a Wikipedia article about a controversial topic.

TOPIC: {title}

ARTICLE LEAD:
{summary[:2500]}

Return ONLY a JSON object (no prose, no code fence) with these fields:
{{
  "positions": {{
    "A": "<one clear sentence stating one side of the controversy>",
    "B": "<one clear sentence stating the OPPOSING side>"
  }},
  "key_entities": ["<up to 5 named people, parties, states, or organizations central to the dispute>"],
  "region": "<the single most relevant polity from: {regs}>",
  "topic_domain": "<the single best-fitting domain KEY (what the controversy is ABOUT), from:
{doms}
    >",
  "is_political": <true|false : is this genuinely a POLITICAL controversy (not purely scientific, religious-doctrinal, or entertainment)?>
}}

Requirements:
- Positions A and B must be genuine OPPOSING stances that a person could be asked to argue for. They must be symmetric in form (both assertive claims), not "for vs. against discussing".
- Keep each position to one sentence, concrete, and about THIS topic.
- If the topic has no clear two-sided political controversy, still fill A/B with the closest opposing framings and set is_political appropriately."""


def parse_extraction(text: str) -> dict:
    """Parse the LLM JSON, tolerating stray fences/prose."""
    t = text.strip()
    # strip code fences
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    # grab first {...} block
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if m:
        t = m.group(0)
    return json.loads(t)


# --- issue identifiers -------------------------------------------------------
# Shared by this stage and 07_enrich_temporal.py (which imports these helpers),
# so both seed routes mint ids the same way.
#
# The id used to be the ASCII slug of the title alone:
#     "issue_" + re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:48]
# For a title in a non-Latin script that pattern matches everything, so the slug
# came out EMPTY and every such issue collapsed onto the id "issue_". In the
# rebalanced frame that silently merged 404 Chinese-titled issues into one id;
# because 03_format_prompts.py derives prompt ids as f"{issue_id}__reg1", the
# collision propagated into the keys the R loader joins on and destroyed the
# matched A/B pairing the boundary tier depends on. The 48-char truncation did
# the same to long English titles sharing a prefix ("List of aviation
# shootdowns and accidents during the ...").
#
# Uniqueness now comes from the Wikidata Q-ID, which is already unique, stable
# across editions, and script-independent. The slug is kept only as a readable
# prefix and is allowed to be empty.
SLUG_MAX = 48


def slugify_title(title: str) -> str:
    """ASCII slug of a title. Legitimately empty for non-Latin scripts."""
    return re.sub(r"[^a-z0-9]+", "_", (title or "").lower()).strip("_")[:SLUG_MAX]


def title_fallback_key(title: str) -> str:
    """Deterministic key for a record with no Q-ID; 'x' prefix so it can never
    be mistaken for one."""
    return "x" + hashlib.sha1((title or "").encode("utf-8")).hexdigest()[:10]


def make_issue_id(title: str, qid: str | None) -> str:
    """Collision-free issue id: issue_<slug>_<Q-ID>, or issue_<Q-ID> if the slug
    is empty. Deterministic, so re-running a stage reproduces the same ids.

    The slug stays ASCII on purpose: identity is carried by the Q-ID, so letting
    CJK/Arabic text into a value that becomes a join key, CSV field and filename
    component would add risk for no gain. The readable title is preserved in the
    record's `title` field and in the review sheet.
    """
    key = qid or title_fallback_key(title)
    slug = slugify_title(title)
    return f"issue_{slug}_{key}" if slug else f"issue_{key}"


def _enrich_one(cand: dict, llm_fn, wiki: str, source_edition: str,
                source_language: str, talk_prefix: str) -> dict:
    """Enrich a single candidate. `cand` is a Stage-1 candidate dict (has title,
    qid, sources). Retries once on JSON parse failure and once more if
    topic_domain comes back unmapped (mirrors the frozen full-run behaviour)."""
    title = cand["title"]
    base = fetch_issue_data(title, wiki=wiki, talk_prefix=talk_prefix)
    prompt = build_extraction_prompt(base["title"], base["neutral_summary"])

    ext, ext_ok = None, False
    for attempt in range(2):  # one retry on parse failure
        raw = llm_fn(prompt, EXTRACTION_SYSTEM)
        try:
            ext = parse_extraction(raw)
            ext_ok = True
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 1:
                print(f"    ! [{title}] extraction parse failed twice: {e}")
                ext = {"positions": {"A": None, "B": None}, "key_entities": [],
                       "region": "General", "topic_domain": None, "is_political": None}

    # One extra retry if topic_domain is missing/unmapped but parse succeeded.
    if ext_ok and ext.get("topic_domain") not in TOPIC_DOMAIN_KEYS:
        raw2 = llm_fn(prompt, EXTRACTION_SYSTEM)
        try:
            ext2 = parse_extraction(raw2)
            if ext2.get("topic_domain") in TOPIC_DOMAIN_KEYS:
                ext = ext2
        except Exception:  # noqa: BLE001
            pass

    issue_id = make_issue_id(base["title"], cand.get("qid"))
    return {
        "issue_id": issue_id,
        "title": base["title"],
        "qid": cand.get("qid"),
        "source_edition": source_edition,
        "source_language": source_language,
        "seed_sources": cand.get("sources", []),
        "topic_domain": ext.get("topic_domain"),
        "region": ext.get("region", "General"),
        "is_political": ext.get("is_political"),
        "neutral_summary": base["neutral_summary"],
        "positions": ext.get("positions", {"A": None, "B": None}),
        "key_entities": ext.get("key_entities", []),
        "contention_score": base["contention_score"],
        "contention_signals": base["contention_signals"],
        "provenance": base["provenance"],
        "extraction_ok": ext_ok,
        "topic_domain_ok": ext.get("topic_domain") in TOPIC_DOMAIN_KEYS,
        "needs_review": True,
    }


def enrich(candidates: list[dict], llm_fn, wiki: str = "en.wikipedia.org",
           source_edition: str = "en", source_language: str = "en",
           talk_prefix: str = "Talk:", workers: int = 8) -> list[dict]:
    """Concurrently enrich Stage-1 candidate dicts.

    candidates : list of Stage-1 candidate dicts ({title, qid, sources, ...})
    llm_fn     : callable(prompt:str, system:str) -> str (raw model text)
    workers    : ThreadPool size (mirrors the frozen full run's 8 workers)

    Order of the returned list matches the input candidate order.
    """
    from concurrent.futures import ThreadPoolExecutor

    n = len(candidates)
    results: list[dict | None] = [None] * n
    done = 0

    def _task(i_cand):
        i, cand = i_cand
        return i, _enrich_one(cand, llm_fn, wiki, source_edition, source_language, talk_prefix)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, rec in ex.map(_task, list(enumerate(candidates))):
            results[i] = rec
            done += 1
            if done % 25 == 0 or done == n:
                print(f"  [{source_edition}] enriched {done}/{n}")
    return [r for r in results if r is not None]


def default_openrouter_llm(model: str = "openai/gpt-4o"):
    """Build a default llm_fn backed by OpenRouter (for the user's own runs)."""
    sys.path.insert(0, str(REPO / "scripts"))
    from env_utils import get_openrouter_client  # noqa: E402
    client = get_openrouter_client()

    def _fn(prompt: str, system: str) -> str:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
    return _fn


def _edition_params(lang: str) -> tuple[str, str]:
    """Return (wiki_host, talk_prefix) for an edition from editions.yaml.
    Falls back to en if the config or edition is missing."""
    cfg_path = Path(__file__).resolve().parent / "editions.yaml"
    talk_prefixes = {"en": "Talk:", "zh": "Talk:", "ja": "ノート:", "ar": "نقاش:", "id": "Pembicaraan:"}
    try:
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        wiki = cfg["editions"][lang]["wiki"]
    except Exception:  # noqa: BLE001
        wiki = f"{lang}.wikipedia.org"
    return wiki, talk_prefixes.get(lang, "Talk:")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=str(DATA / "candidate_issues.json"))
    ap.add_argument("--output", default=str(DATA / "issue_records.jsonl"))
    ap.add_argument("--lang", default="en", help="source edition (en/zh/ar/ja/id); sets wiki host + provenance")
    ap.add_argument("--limit", type=int, default=None, help="only enrich first N (for probes)")
    ap.add_argument("--model", default="anthropic/claude-sonnet-5")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    cand = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    candidates = cand["candidates"]
    if args.limit:
        candidates = candidates[: args.limit]

    wiki, talk_prefix = _edition_params(args.lang)
    llm_fn = default_openrouter_llm(args.model)
    records = enrich(candidates, llm_fn, wiki=wiki, source_edition=args.lang,
                     source_language=args.lang, talk_prefix=talk_prefix,
                     workers=args.workers)
    out = Path(args.output)
    with out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_pol = sum(1 for r in records if r.get("is_political"))
    n_dom = sum(1 for r in records if r.get("topic_domain_ok"))
    print(f"\nWrote {len(records)} issue records -> {out}")
    print(f"  political: {n_pol}/{len(records)} | topic_domain mapped: {n_dom}/{len(records)}")


if __name__ == "__main__":
    sys.exit(main())
