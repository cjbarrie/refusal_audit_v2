#!/usr/bin/env python3
"""
Stage 1 - Harvest the seed list (per-edition).

Seeds a candidate list of controversial issues from ONE Wikipedia language
edition, via any combination of three discovery routes (configured per edition
in sourcing/editions.yaml):

  1. list_page          parse the political sections of a curated project list
                        (e.g. en 'List of controversial issues', id 'Daftar
                        isu kontroversial')
  2. dispute_categories enumerate mainspace members of substantive controversy
                        / territorial-dispute categories (used where no curated
                        list exists, e.g. zh/ja/ar)
  3. contention_rank    (reserved) rank political articles by talk-size +
                        protection; not enabled by default

The routes are unioned, every title is resolved to a Wikidata Q-ID (the
cross-edition anchor), duplicates are dropped, and the result is written to:

  data/candidate_issues.json         (for --lang en; byte-compatible w/ v1)
  data/candidate_issues_{lang}.json  (for any other edition)

Each candidate records which route(s) surfaced it, so provenance is auditable.

This is the SOURCING stage only. It does not query subject models.
No API key required (public MediaWiki API). Requires PyYAML.

Usage:
  python 01_harvest_controversial.py --lang en
  python 01_harvest_controversial.py --lang zh
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
CONFIG = Path(__file__).resolve().parent / "editions.yaml"

# Match the FIRST [[wikilink]] in a bullet line. Handles piped links
# [[Target|Display]] by taking Target.
BULLET_RE = re.compile(r"^\*+\s*\[\[([^\]\|#]+)(?:\|[^\]]+)?\]\]")
NAMESPACE_PREFIXES = ("File", "Category", "Image", "Template", "Wikipedia", "Help", "Portal")


def load_config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


class Edition:
    """Thin MediaWiki API client bound to one language edition."""

    def __init__(self, lang: str, cfg: dict):
        self.lang = lang
        ed = cfg["editions"][lang]
        d = cfg["defaults"]
        self.wiki = ed["wiki"]
        self.list_page = ed.get("list_page")
        self.political_sections = ed.get("political_sections") or []
        self.dispute_categories = ed.get("dispute_categories") or []
        self.talk_categories = ed.get("talk_categories") or []
        self.ua = d["user_agent"]
        self.qid_batch = int(d["qid_batch_size"])
        self.sleep = float(d["api_sleep"])
        self.max_retries = int(d["max_retries"])

    def api(self, params: dict) -> dict:
        params = {**params, "format": "json"}
        url = f"https://{self.wiki}/w/api.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:  # noqa: PERF203
                if e.code == 429 and attempt < self.max_retries - 1:
                    wait = int(e.headers.get("Retry-After", 0)) or (5 * (attempt + 1))
                    time.sleep(wait)
                    continue
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2.0 * (attempt + 1))
            except Exception:  # noqa: BLE001
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2.0 * (attempt + 1))
        raise RuntimeError("unreachable")

    # ----- route 1: curated list page -----
    def harvest_list_page(self) -> list[tuple[str, str]]:
        """Return [(title, section)] from the political sections of the list page."""
        if not self.list_page:
            return []
        d = self.api(dict(action="parse", page=self.list_page, prop="sections"))
        sections = d["parse"]["sections"]
        idx_by_line = {s["line"]: s["index"] for s in sections}
        out: list[tuple[str, str]] = []
        wanted = self.political_sections or list(idx_by_line)
        for sec_name in wanted:
            idx = idx_by_line.get(sec_name)
            if idx is None:
                print(f"  ! [{self.lang}] section not found: {sec_name}")
                continue
            time.sleep(self.sleep)
            dd = self.api(dict(action="parse", page=self.list_page, prop="wikitext", section=idx))
            wt = dd["parse"]["wikitext"]["*"]
            n = 0
            for line in wt.splitlines():
                m = BULLET_RE.match(line.strip())
                if not m:
                    continue
                title = m.group(1).strip()
                if not title or title.split(":")[0] in NAMESPACE_PREFIXES:
                    continue
                out.append((title, f"list:{sec_name}"))
                n += 1
            print(f"  [{self.lang}] list section '{sec_name}': {n} entries")
        return out

    # ----- route 2: dispute categories -----
    def harvest_categories(self) -> list[tuple[str, str]]:
        """Return [(title, section)] from mainspace members of dispute categories."""
        out: list[tuple[str, str]] = []
        for cat in self.dispute_categories:
            members: list[str] = []
            cont: dict = {}
            while True:
                d = self.api(dict(action="query", list="categorymembers", cmtitle=cat,
                                  cmnamespace=0, cmlimit="max", **cont))
                members += [m["title"] for m in d["query"]["categorymembers"]]
                if "continue" in d:
                    cont = d["continue"]
                    time.sleep(self.sleep)
                else:
                    break
            for t in members:
                out.append((t, f"cat:{cat}"))
            print(f"  [{self.lang}] category '{cat}': {len(members)} members")
            time.sleep(self.sleep)
        return out

    # ----- route 3: talk-page categories (NPOV / disputed-article tags) -----
    def harvest_talk_categories(self) -> list[tuple[str, str]]:
        """Return [(article_title, section)] from ns=1 members of talk categories.

        Some editions tag contested articles via a category applied to the
        *talk* page (e.g. ru 'Обсуждение наиболее спорных статей'). We pull the
        ns=1 members and strip the localized talk prefix to recover the article.
        """
        out: list[tuple[str, str]] = []
        for cat in self.talk_categories:
            members: list[str] = []
            cont: dict = {}
            while True:
                d = self.api(dict(action="query", list="categorymembers", cmtitle=cat,
                                  cmnamespace=1, cmlimit="max", **cont))
                members += [m["title"] for m in d["query"]["categorymembers"]]
                if "continue" in d:
                    cont = d["continue"]
                    time.sleep(self.sleep)
                else:
                    break
            n = 0
            for talk_title in members:
                # "<TalkPrefix>:Article" -> "Article"; skip subpage talk (e.g. /Archive)
                if ":" not in talk_title:
                    continue
                article = talk_title.split(":", 1)[1].strip()
                if not article or "/" in article:
                    continue
                out.append((article, f"talkcat:{cat}"))
                n += 1
            print(f"  [{self.lang}] talk category '{cat}': {n} articles")
            time.sleep(self.sleep)
        return out

    # ----- Q-ID resolution -----
    def resolve_qids(self, titles: list[str]) -> dict[str, str | None]:
        out: dict[str, str | None] = {}
        for i in range(0, len(titles), self.qid_batch):
            batch = titles[i : i + self.qid_batch]
            d = self.api(dict(action="query", prop="pageprops", ppprop="wikibase_item",
                              titles="|".join(batch), redirects=1))
            query = d.get("query", {})
            norm = {n["from"]: n["to"] for n in query.get("normalized", [])}
            redir = {r["from"]: r["to"] for r in query.get("redirects", [])}
            pages = {p["title"]: p for p in query.get("pages", {}).values()}
            for orig in batch:
                t = redir.get(norm.get(orig, orig), norm.get(orig, orig))
                page = pages.get(t)
                out[orig] = page.get("pageprops", {}).get("wikibase_item") if page else None
            time.sleep(self.sleep)
        return out


def harvest_edition(lang: str, cfg: dict) -> dict:
    ed = Edition(lang, cfg)
    print(f"Harvesting edition '{lang}' ({ed.wiki}) ...")
    raw = ed.harvest_list_page() + ed.harvest_categories() + ed.harvest_talk_categories()

    # Merge routes on title, collecting all sections/routes that surfaced it.
    by_title: dict[str, set[str]] = {}
    for title, section in raw:
        by_title.setdefault(title, set()).add(section)

    titles = list(by_title)
    print(f"  [{lang}] {len(titles)} unique titles across routes; resolving Q-IDs ...")
    qids = ed.resolve_qids(titles)

    candidates = [
        {
            "title": t,
            "sources": sorted(by_title[t]),
            "qid": qids.get(t),
            "source_edition": lang,
            "url": f"https://{ed.wiki}/wiki/" + urllib.parse.quote(t.replace(" ", "_")),
        }
        for t in titles
    ]
    return {
        "source_edition": lang,
        "wiki": ed.wiki,
        "list_page": ed.list_page,
        "dispute_categories": ed.dispute_categories,
        "talk_categories": ed.talk_categories,
        "n_candidates": len(candidates),
        "n_with_qid": sum(1 for c in candidates if c["qid"]),
        "candidates": candidates,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, help="edition key from editions.yaml (en/zh/ar/ja/id)")
    ap.add_argument("--output", default=None, help="override output path")
    args = ap.parse_args()

    cfg = load_config()
    if args.lang not in cfg["editions"]:
        raise SystemExit(f"unknown edition '{args.lang}'; known: {list(cfg['editions'])}")

    DATA.mkdir(parents=True, exist_ok=True)
    payload = harvest_edition(args.lang, cfg)

    if args.output:
        out_path = Path(args.output)
    elif args.lang == "en":
        out_path = DATA / "candidate_issues.json"   # byte-compatible with v1
    else:
        out_path = DATA / f"candidate_issues_{args.lang}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {payload['n_candidates']} candidate issues -> {out_path}")
    print(f"  with Q-ID: {payload['n_with_qid']}/{payload['n_candidates']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
