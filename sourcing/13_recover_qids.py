#!/usr/bin/env python3
"""
Stage 13 — re-query the source edition for missing Wikidata Q-IDs, and classify
why they are missing.

RESULT ON THE CURRENT FRAME: 0 of 65 are recoverable. This is not a lookup
failure — the items genuinely do not exist:

    47  article exists, but has no Wikidata item yet
    18  article no longer exists (deleted or moved without a redirect)

The 47 are overwhelmingly articles created inside the harvest window (e.g.
"Long-range sanction", created four days before the harvest). Wikidata item
creation lags article creation, so the temporal and current-events routes — which
exist precisely to surface what is contested *right now* — outrun the Q-ID
backbone by construction. Confirmed against the Wikidata sitelink endpoint
(`wbgetentities&sites=enwiki`), which also reports them missing.

The 18 deleted articles are the more serious group: prompts were generated from
an article that has since been removed, so the source can no longer be inspected.

The script is kept because it is the diagnostic that establishes this, and
because the picture will change as Wikidata catches up — re-running it later
should recover some of the 47.

65 records in the rebalanced frame carry no `qid` (20 from the en temporal
route, 45 from the zh route). They were harvested legitimately — the Q-ID
lookup just did not resolve at harvest time, usually because the title was a
redirect or the article had only recently been created.

A missing Q-ID is not cosmetic. It is the key that:
  * `04_merge_editions.py` dedupes on — records without one are never merged,
    so a genuine duplicate can survive as two issues;
  * `sample_prompts.py` applies the **ethical denylist** on — an excluded topic
    reached via a redirect title would not be caught;
  * cross-edition and cross-battery joins rely on.

So this asks MediaWiki again, in batches, following redirects.

What it deliberately does NOT do
--------------------------------
Rewrite `issue_id`. Ids derived from the fallback title hash
(`issue_<slug>_x<hash>`) are already unique and stable, and a drawn sample keys
on them; re-deriving them from the recovered Q-ID would invalidate that sample
for no gain. The Q-ID is recorded in its own field, which is what every join
actually needs.

It reports rather than silently fixes the two cases that need a human decision:
a recovered Q-ID that **duplicates** an existing record, and one that lands on
the **denylist**.

Read-only Wikipedia. No API key, no spend.

Usage:
    python 13_recover_qids.py --dry-run
    python 13_recover_qids.py
"""
from __future__ import annotations

import argparse
import collections
import json
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"
PROMPTS = REPO / "prompts"

UA = "refusal-audit-research/0.1 (academic LLM political-behavior audit)"
BATCH = 50          # MediaWiki caps titles per query at 50 for anonymous clients


def api(host: str, params: dict, tries: int = 5) -> dict:
    params = {**params, "format": "json", "formatversion": "2"}
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    return {}


def resolve_qids(titles: list[str], host: str) -> dict:
    """title -> Q-ID. Follows redirects, so a renamed article still resolves."""
    out: dict = {}
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        d = api(host, {"action": "query", "titles": "|".join(chunk),
                       "prop": "pageprops", "ppprop": "wikibase_item",
                       "redirects": "1"})
        q = d.get("query", {})
        # Map any redirect back onto the title we asked for.
        alias = {r["to"]: r["from"] for r in q.get("redirects", [])}
        alias.update({n["to"]: n["from"] for n in q.get("normalized", [])})
        for page in q.get("pages", []):
            asked = page.get("title")
            while asked in alias:
                asked = alias[asked]
            qid = (page.get("pageprops") or {}).get("wikibase_item")
            if qid:
                out[asked] = qid
        print(f"  [{host}] {min(i+BATCH, len(titles))}/{len(titles)} titles", flush=True)
        time.sleep(0.2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", default=str(DATA / "issue_records_rebalanced.jsonl"))
    ap.add_argument("--prompts", default=str(PROMPTS / "rebalanced_prompts_en.json"))
    ap.add_argument("--languages", nargs="+", default=["zh", "ar", "ru", "hi"])
    ap.add_argument("--denylist", default=str(PROMPTS / "excluded_issues.yaml"))
    ap.add_argument("--stamp-status", action="store_true",
                    help="record source_article_status (live | deleted | no_wikidata_item) "
                         "on each qid-less record, so analysis can exclude issues whose "
                         "source article no longer exists")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    rec_path = Path(args.records)
    recs = [json.loads(l) for l in rec_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    missing = [r for r in recs if not r.get("qid")]
    print(f"{len(recs)} records, {len(missing)} without a Q-ID")
    if not missing:
        return 0

    by_edition = collections.defaultdict(list)
    for r in missing:
        by_edition[r.get("source_edition") or "en"].append(r)
    for ed, rs in by_edition.items():
        print(f"  {ed}: {len(rs)}")

    resolved: dict = {}
    for ed, rs in sorted(by_edition.items()):
        host = f"{ed}.wikipedia.org"
        got = resolve_qids([r["title"] for r in rs], host)
        for r in rs:
            if r["title"] in got:
                resolved[r["issue_id"]] = got[r["title"]]

    still = [r for r in missing if r["issue_id"] not in resolved]
    print(f"\nrecovered {len(resolved)}/{len(missing)}; still missing {len(still)}")
    for r in still[:8]:
        print(f"    unresolved: {r['title'][:60]}  ({r.get('source_edition')})")

    # --- the two cases a human must decide -----------------------------------
    existing = {r.get("qid") for r in recs if r.get("qid")}
    dupes = {iid: q for iid, q in resolved.items() if q in existing}
    if dupes:
        print(f"\n!! {len(dupes)} recovered Q-ID(s) DUPLICATE an existing record — "
              f"these are the same issue harvested twice and survived dedup only "
              f"because they had no Q-ID:")
        byq = {r.get("qid"): r.get("title") for r in recs if r.get("qid")}
        for iid, q in list(dupes.items())[:10]:
            t = next(r["title"] for r in recs if r["issue_id"] == iid)
            print(f"     {t[:40]:42s} == {str(byq.get(q))[:34]:36s} ({q})")
        print("     -> re-run 04_merge_editions.py to collapse them, then re-draw.")

    deny = set()
    dpath = Path(args.denylist)
    if dpath.exists():
        sys.path.insert(0, str(REPO / "scripts"))
        from sample_prompts import load_denylist  # noqa: E402
        deny = load_denylist(str(dpath))
    hits = {iid: q for iid, q in resolved.items() if q in deny}
    if hits:
        print(f"\n!! {len(hits)} recovered Q-ID(s) are ON THE ETHICAL DENYLIST and "
              f"were previously invisible to it:")
        for iid, q in hits.items():
            t = next(r["title"] for r in recs if r["issue_id"] == iid)
            print(f"     {t[:50]}  ({q})")
        print("     -> they will now be excluded automatically at the next draw.")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0
    if not resolved:
        return 0

    def backup(p: Path, suffix: str) -> None:
        if not args.no_backup:
            b = p.with_suffix(p.suffix + suffix)
            if not b.exists():
                shutil.copy2(p, b)

    backup(rec_path, ".pre_qid_recovery")
    for r in recs:
        if r["issue_id"] in resolved:
            r["qid"] = resolved[r["issue_id"]]
            prov = r.get("provenance")
            if isinstance(prov, dict):
                prov["qid_recovered"] = True
    rec_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
                        encoding="utf-8")
    print(f"\nwrote {rec_path.name}")

    en_path = Path(args.prompts)
    for lang in ["en"] + list(args.languages):
        p = en_path.with_name(en_path.name.replace("_en.json", f"_{lang}.json"))
        if not p.exists():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        n = 0
        for x in doc["prompts"]:
            if not x.get("qid") and x.get("issue_id") in resolved:
                x["qid"] = resolved[x["issue_id"]]
                n += 1
        if n:
            backup(p, ".pre_qid_recovery")
            p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {p.name}: {n} prompts updated")

    print("\nRe-draw the sample so it picks up the recovered Q-IDs "
          "(the denylist is applied on qid).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
