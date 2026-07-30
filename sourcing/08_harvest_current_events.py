#!/usr/bin/env python3
"""Topical-breadth temporal route: harvest candidate issues from the English
Wikipedia *Current events* portal, rather than the protection log.

Motivation
----------
The protection-log route (06_harvest_temporal.py) is structurally biased toward
armed/territorial/ethnic conflict, because those are the areas ArbCom places
under contentious-topic protection. The result is a temporal battery that is
~50% security_conflict and near-zero on economic / environmental / social
issues. The Current events portal is a much broader daily digest — legislation,
court rulings, elections, economic and environmental news — so it can recover
the topical breadth the protection log cannot.

Pipeline
--------
1. Pull Portal:Current_events/{YYYY_Month_D} for the last N days; collect linked
   mainspace articles (ns=0).
2. Resolve Wikidata Q-IDs (batched).
3. Controversy pre-filter (cheap, no LLM): fetch each article's edit-protection
   status and talk-page byte size, compute a perennial-style contention score,
   and keep only articles above --min-contention. This drops routine
   sport/schedule/BLP pages before the (LLM) political gate in 07_enrich_temporal.py.
4. Emit candidates in the SAME schema as 06 so downstream enrichment/merge is
   unchanged. `sources` is tagged ["current_events:{date}"] and ct_area is
   "current-events" (the enrichment is_political + region + topic classifier
   adjudicates each one downstream).

This script performs NO LLM calls. --count-only prints the pre-filter yield
without writing candidates.
"""
from __future__ import annotations
import argparse, json, math, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

# perennial contention parts (mirror 02_enrich_issues.py)
PROTECTION_RANK = {"autoconfirmed": 1, "extendedconfirmed": 2,
                   "templateeditor": 3, "sysop": 3, "": 0}


def load_cfg() -> dict:
    return yaml.safe_load(open(HERE / "editions.yaml", encoding="utf-8"))


class Api:
    def __init__(self, lang: str, cfg: dict):
        ed = cfg["editions"][lang]
        d = cfg["defaults"]
        self.lang = lang
        self.wiki = ed["wiki"]
        self.ua = d["user_agent"]
        self.qid_batch = int(d["qid_batch_size"])
        self.sleep = float(d.get("api_sleep", 0.6))
        self.max_retries = int(d.get("max_retries", 6))

    def get(self, params: dict) -> dict:
        params = {**params, "format": "json"}
        url = f"https://{self.wiki}/w/api.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=45) as r:
                    time.sleep(self.sleep)
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                wait = int(e.headers.get("Retry-After", 0)) or (5 * (attempt + 1))
                time.sleep(wait)
            except Exception:
                time.sleep(3 * (attempt + 1))
        raise RuntimeError(f"API failed after {self.max_retries} retries: {params}")

    def current_events_links(self, days: int) -> dict[str, str]:
        """Return {article_title: first_seen_date} from the last `days` daily
        Current events portal pages."""
        out: dict[str, str] = {}
        base = datetime.now(timezone.utc)
        for i in range(days):
            d = base - timedelta(days=i)
            # portal page names use non-zero-padded day: "2026_July_4"
            page = f"Portal:Current_events/{d.year}_{d.strftime('%B')}_{d.day}"
            try:
                r = self.get(dict(action="parse", page=page, prop="links", redirects=1))
            except Exception:
                continue
            for l in r.get("parse", {}).get("links", []):
                if l.get("ns") == 0:
                    t = l.get("*")
                    if t and t not in out:
                        out[t] = d.strftime("%Y-%m-%d")
        return out

    def resolve_qids(self, titles: list[str]) -> dict[str, str | None]:
        out: dict[str, str | None] = {}
        for i in range(0, len(titles), self.qid_batch):
            b = titles[i:i + self.qid_batch]
            d = self.get(dict(action="query", prop="pageprops", ppprop="wikibase_item",
                              titles="|".join(b), redirects=1))
            q = d.get("query", {})
            norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
            red = {r["from"]: r["to"] for r in q.get("redirects", [])}
            pages = {pg.get("title"): pg.get("pageprops", {}).get("wikibase_item")
                     for pg in q.get("pages", {}).values()}
            for t in b:
                key = red.get(norm.get(t, t), norm.get(t, t))
                out[t] = pages.get(key)
        return out

    def contention_signals(self, titles: list[str]) -> dict[str, dict]:
        """Batched perennial contention score for many articles.

        Two batched passes (50 titles/call each):
          1. article edit-protection level (prop=info&inprop=protection)
          2. talk-page byte size (prop=info on Talk: titles)
        score = 0.5*prot_rank/3 + 0.5*min(log10(talk_bytes+1)/6, 1).
        Batching turns ~2*N serial calls into ~2*N/50, the difference between
        a ~30-min run and a ~1-min run for a 2,400-article portal window."""
        prot: dict[str, str] = {t: "" for t in titles}
        talk: dict[str, int] = {t: 0 for t in titles}
        B = self.qid_batch
        # pass 1: article protection
        for i in range(0, len(titles), B):
            b = titles[i:i + B]
            d = self.get(dict(action="query", prop="info", inprop="protection",
                              titles="|".join(b), redirects=1))
            q = d.get("query", {})
            norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
            red = {r["from"]: r["to"] for r in q.get("redirects", [])}
            resolved = {t: red.get(norm.get(t, t), norm.get(t, t)) for t in b}
            bytitle = {pg.get("title"): pg for pg in q.get("pages", {}).values()}
            for t in b:
                pg = bytitle.get(resolved[t], {})
                for pr in pg.get("protection", []):
                    if pr.get("type") == "edit":
                        prot[t] = pr.get("level", "") or ""
        # pass 2: talk-page size
        talk_titles = [f"Talk:{t}" for t in titles]
        back = {f"Talk:{t}": t for t in titles}
        for i in range(0, len(talk_titles), B):
            b = talk_titles[i:i + B]
            d = self.get(dict(action="query", prop="info", titles="|".join(b), redirects=1))
            q = d.get("query", {})
            norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
            red = {r["from"]: r["to"] for r in q.get("redirects", [])}
            bytitle = {pg.get("title"): pg for pg in q.get("pages", {}).values()}
            for tt in b:
                key = red.get(norm.get(tt, tt), norm.get(tt, tt))
                pg = bytitle.get(key, {})
                talk[back[tt]] = int(pg.get("length", 0) or 0)
        out = {}
        for t in titles:
            prot_rank = PROTECTION_RANK.get(prot[t], 0)
            score = round(0.5 * prot_rank / 3
                          + 0.5 * min(math.log10(talk[t] + 1) / 6, 1), 3)
            out[t] = {"edit_protection": prot[t], "talk_bytes": talk[t],
                      "contention_temporal": score}
        return out


def harvest(lang: str, days: int, min_contention: float,
            count_only: bool, cfg: dict) -> dict:
    api = Api(lang, cfg)
    print(f"Current-events harvest '{lang}' ({api.wiki}), last {days} days ...", flush=True)
    links = api.current_events_links(days)
    print(f"  {len(links)} distinct linked mainspace articles; scoring contention "
          f"(batched) ...", flush=True)
    titles = list(links)
    sigs = api.contention_signals(titles)
    kept = [t for t in titles if sigs[t]["contention_temporal"] >= min_contention]
    print(f"  {len(kept)}/{len(titles)} pass min_contention={min_contention}", flush=True)

    if count_only:
        return {"route": "current_events", "source_edition": lang, "window_days": days,
                "min_contention": min_contention, "n_linked": len(titles),
                "n_pass_prefilter": len(kept),
                "sample_kept": sorted(kept)[:40]}

    print(f"  resolving Q-IDs for {len(kept)} kept articles ...", flush=True)
    qids = api.resolve_qids(kept)
    candidates = []
    for t in kept:
        s = sigs[t]
        candidates.append({
            "title": t,
            "sources": [f"current_events:{links[t]}"],
            "qid": qids.get(t),
            "source_edition": lang,
            "url": f"https://{api.wiki}/wiki/" + urllib.parse.quote(t.replace(" ", "_")),
            "ct_area": "current-events",
            "protection_reason": "",
            "n_protections": 0,
            "last_protection": None,
            "first_seen": links[t],
            "edit_protection": s["edit_protection"],
            "talk_bytes": s["talk_bytes"],
            "talk_edits_window": 0,
            "contention_temporal": s["contention_temporal"],
        })
    candidates.sort(key=lambda c: -c["contention_temporal"])
    return {
        "route": "current_events",
        "source_edition": lang,
        "wiki": api.wiki,
        "window_days": days,
        "harvested_at": datetime.now(timezone.utc).isoformat(),
        "min_contention": min_contention,
        "n_linked": len(titles),
        "n_candidates": len(candidates),
        "n_with_qid": sum(1 for c in candidates if c["qid"]),
        "candidates": candidates,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", default="en", help="edition key (only en has a Current events portal harvester)")
    ap.add_argument("--days", type=int, default=45, help="how many daily portal pages back")
    ap.add_argument("--min-contention", type=float, default=0.45,
                    help="drop articles below this perennial-style contention score. "
                         "0.45 balances yield vs. breadth: at 0.45 ~69%% of the kept pool "
                         "is non-conflict; raising to 0.55 pushes conflict share to ~52%% "
                         "(the most-protected pages in any window are the conflict pages). "
                         "Sports/BLP noise that survives is dropped downstream by the "
                         "enrichment is_political gate (07_enrich_temporal.py).")
    ap.add_argument("--count-only", action="store_true",
                    help="print pre-filter yield and sample titles; write nothing")
    ap.add_argument("--out", default=None, help="output path (default data/candidate_issues_current_events_{lang}.json)")
    args = ap.parse_args()

    cfg = load_cfg()
    res = harvest(args.lang, args.days, args.min_contention,
                  args.count_only, cfg)
    if args.count_only:
        print("\n=== count-only ===")
        print(json.dumps({k: v for k, v in res.items() if k != "sample_kept"}, indent=2))
        print("sample kept titles:")
        for t in res["sample_kept"]:
            print("  ", t)
        return 0
    out = Path(args.out) if args.out else DATA / f"candidate_issues_current_events_{args.lang}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=2)
    print(f"wrote {out}  ({res['n_candidates']} candidates, {res['n_with_qid']} with Q-ID)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
