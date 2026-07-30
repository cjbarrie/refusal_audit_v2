#!/usr/bin/env python3
"""Stage 2b — enrich TEMPORAL-route candidates (batched, rate-limit-safe).

Why a separate enricher from `02_enrich_issues.py`:

  * The temporal candidate file (`candidate_issues_temporal_{lang}.json`) already
    carries the protection signals (`n_protections`, `contention_temporal`,
    `ct_area`, `last_protection`) harvested from the protection log. We do NOT
    re-derive contention from talk-page size here — for a *contemporary* issue the
    talk page is often young, so protection frequency is the honest signal. The
    route's `contention_temporal` is written straight into `contention_score`.

  * Enrichment only needs one extra thing per candidate: the article's lead
    extract (for the LLM position/domain extraction). `02` fetches that with 3
    serial API calls PER candidate; at ~1000 temporal candidates × 8 workers that
    triggers a 429 back-off storm on the Wikipedia API and never finishes. Here we
    BATCH the lead-extract fetch (up to 20 titles per API call, ~50 calls total),
    cache it, then run the LLM extraction concurrently. LLM calls don't touch the
    wiki API, so there is no throttling.

Output schema is byte-identical to `02_enrich_issues.py` so Stage 3
(`03_format_prompts.py`) consumes it unchanged.

Usage:
    OPENROUTER_API_KEY=... python 07_enrich_temporal.py \
        --candidates ../data/candidate_issues_temporal_en.json \
        --output     ../data/issue_records_temporal_en.jsonl \
        --workers 8
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"
sys.path.insert(0, str(HERE))

# Reuse the proven enrichment helpers (prompt, system, parser, domains, llm).
import importlib.util
_spec = importlib.util.spec_from_file_location("enrich02", HERE / "02_enrich_issues.py")
enrich02 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(enrich02)

EXTRACTION_SYSTEM     = enrich02.EXTRACTION_SYSTEM
build_extraction_prompt = enrich02.build_extraction_prompt
parse_extraction      = enrich02.parse_extraction
TOPIC_DOMAIN_KEYS     = enrich02.TOPIC_DOMAIN_KEYS
default_openrouter_llm = enrich02.default_openrouter_llm
# Shared so both seed routes mint identical, collision-free ids (see 02).
make_issue_id         = enrich02.make_issue_id

UA = "refusal-audit-research/0.1 (academic LLM political-behavior audit)"


def _api(wiki: str, params: dict, tries: int = 6) -> dict:
    params = {**params, "format": "json"}
    url = f"https://{wiki}/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for a in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and a < tries - 1:
                wait = int(e.headers.get("Retry-After", 0)) or (5 * (a + 1))
                time.sleep(wait); continue
            raise
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(2.0 * (a + 1))
    raise RuntimeError("unreachable")


def batch_fetch_extracts(titles: list[str], wiki: str, batch: int = 20,
                         sleep: float = 0.5) -> dict[str, dict]:
    """Return {input_title: {"extract": str, "revid": int|None}}.

    The revision id is fetched in the SAME call as the extract, and this matters:
    it is the revision the prompt is actually derived from. Earlier versions
    wrote `rev_id: None`, which left 1,965 of 2,773 records with no citable
    source revision — and 18 of those articles were deleted within weeks, making
    their source text unrecoverable. `prop=revisions&rvprop=ids` returns the
    current revision per page when several titles are queried at once, so this
    costs nothing extra.

    `redirects=1` + `normalized`/`redirects` maps let us recover the input title
    each returned page corresponds to, so the cache keys match the candidate list.
    """
    out: dict[str, dict] = {}
    for i in range(0, len(titles), batch):
        chunk = titles[i:i + batch]
        d = _api(wiki, dict(action="query", prop="extracts|revisions", exintro=1,
                            explaintext=1, rvprop="ids", redirects=1,
                            titles="|".join(chunk)))
        q = d.get("query", {})
        # map any normalization / redirect back to the original input title
        alias = {}
        for n in q.get("normalized", []):
            alias[n["to"]] = n["from"]
        for rd in q.get("redirects", []):
            src = alias.get(rd["from"], rd["from"])
            alias[rd["to"]] = src
        for page in q.get("pages", {}).values():
            resolved = page.get("title", "")
            original = alias.get(resolved, resolved)
            revs = page.get("revisions") or []
            out[original] = {
                "extract": (page.get("extract") or "").strip(),
                "revid": (revs[0].get("revid") if revs else None),
            }
        print(f"  fetched extracts {i + len(chunk)}/{len(titles)}", flush=True)
        time.sleep(sleep)
    return out


def enrich_one(cand: dict, summary: str, llm_fn, source_edition: str,
               source_language: str, route: str = "temporal",
               rev_id: int | None = None) -> dict:
    """LLM extraction for one candidate, using the pre-fetched `summary`.

    Preserves the temporal contention score and provenance from the candidate.
    Retries once on JSON parse failure, once more if topic_domain is unmapped.
    """
    title = cand["title"]
    prompt = build_extraction_prompt(title, summary)

    ext, ext_ok = {}, False
    try:
        ext = parse_extraction(llm_fn(prompt, EXTRACTION_SYSTEM)); ext_ok = True
    except Exception:
        try:
            ext = parse_extraction(llm_fn(prompt, EXTRACTION_SYSTEM)); ext_ok = True
        except Exception:
            ext = {}
    if ext_ok and ext.get("topic_domain") not in TOPIC_DOMAIN_KEYS:
        try:
            ext2 = parse_extraction(llm_fn(prompt, EXTRACTION_SYSTEM))
            if ext2.get("topic_domain") in TOPIC_DOMAIN_KEYS:
                ext = ext2
        except Exception:
            pass

    issue_id = make_issue_id(title, cand.get("qid"))
    contention = cand.get("contention_temporal")
    return {
        "issue_id": issue_id,
        "title": title,
        "qid": cand.get("qid"),
        "source_edition": source_edition,
        "source_language": source_language,
        "seed_sources": cand.get("sources", []),
        "topic_domain": ext.get("topic_domain"),
        "region": ext.get("region", "General"),
        "is_political": ext.get("is_political"),
        "neutral_summary": summary,
        "positions": ext.get("positions", {"A": None, "B": None}),
        "key_entities": ext.get("key_entities", []),
        "contention_score": contention,
        "contention_signals": {
            "route": route,
            "ct_area": cand.get("ct_area"),
            "n_protections": cand.get("n_protections"),
            "last_protection": cand.get("last_protection"),
            "talk_edits_window": cand.get("talk_edits_window"),
            "contention_temporal": contention,
        },
        "provenance": {
            "rev_id": rev_id,
            "snapshot": date.today().isoformat(),
            "url": cand.get("url"),
            "route": route,
        },
        "extraction_ok": ext_ok,
        "topic_domain_ok": ext.get("topic_domain") in TOPIC_DOMAIN_KEYS,
        "needs_review": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=str(DATA / "candidate_issues_temporal_en.json"))
    ap.add_argument("--output", default=str(DATA / "issue_records_temporal_en.jsonl"))
    ap.add_argument("--lang", default="en", help="source edition; sets wiki host + provenance")
    ap.add_argument("--limit", type=int, default=None, help="only enrich first N (probes)")
    ap.add_argument("--model", default="anthropic/claude-sonnet-5")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--batch", type=int, default=20, help="titles per extract API call")
    ap.add_argument("--route", default="temporal",
                    help="provenance tag written to each record "
                         "(e.g. 'temporal', 'current-events', 'zh-dispute-category')")
    args = ap.parse_args()

    payload = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    candidates = payload["candidates"]
    if args.limit:
        candidates = candidates[: args.limit]
    wiki = f"{args.lang}.wikipedia.org"

    print(f"Temporal enrichment: {len(candidates)} candidates from {wiki}")
    print("Phase 1 — batch-fetching lead extracts ...")
    titles = [c["title"] for c in candidates]
    extracts = batch_fetch_extracts(titles, wiki, batch=args.batch)
    got = sum(1 for t in titles if extracts.get(t))
    print(f"  got {got}/{len(titles)} non-empty extracts")

    print(f"Phase 2 — LLM extraction ({args.workers} workers, model {args.model}) ...")
    llm_fn = default_openrouter_llm(args.model)

    def _task(cand):
        got = extracts.get(cand["title"]) or {}
        return enrich_one(cand, got.get("extract", ""), llm_fn,
                          source_edition=args.lang, source_language=args.lang,
                          route=args.route, rev_id=got.get("revid"))

    records = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, rec in enumerate(ex.map(_task, candidates), 1):
            records.append(rec)
            if i % 50 == 0:
                print(f"  enriched {i}/{len(candidates)}  ({round(time.time()-t0)}s)", flush=True)

    out = Path(args.output)
    with out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    pol = sum(1 for r in records if r.get("is_political"))
    ok = sum(1 for r in records if r.get("extraction_ok"))
    print(f"\nWrote {len(records)} records -> {out}")
    print(f"  extraction_ok: {ok}/{len(records)} | is_political: {pol}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
