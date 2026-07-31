#!/usr/bin/env python3
"""
Temporal harvest route — contemporary contested issues from Wikipedia's
protection log.

Where Stage 1 (`01_harvest_controversial.py`) seeds from a static, perennial list
(`Wikipedia:List of controversial issues`), this route seeds from *recent events*:
articles that editors have had to lock down in the last N days because of an
active political dispute. It answers "what is being fought over right now?"
rather than "what has been controversial for decades?".

Signal
------
The MediaWiki protection log (`letype=protect`, article namespace) is noisy —
most protections are vandalism / spam / BLP locks. The political signal is the
subset protected under an **arbitration / contentious-topic (CT) designation**:
Wikipedia's own formal marking of a politically contested area (Palestine-Israel,
American politics, Eastern Europe, South Asia, …), plus explicit
"edit warring / content dispute" locks. We keep only those.

Contention (velocity, not accumulation)
---------------------------------------
The Stage-2 `contention_score` rewards *accumulated* talk-page size, which
structurally penalises new issues. For temporal candidates we instead record a
**velocity** signal — talk-page edits within the window — and a normalized
`contention_temporal` in [0,1]. This travels on the candidate so a temporal
battery can be scored on recency of conflict, not age of conflict.

Output
------
`data/candidate_issues_temporal_{lang}.json`, schema-compatible with Stage 1
(so it feeds the identical enrich → format → translate stages), with extra
provenance fields per candidate: `ct_area`, `protection_reason`, `n_protections`,
`last_protection`, `talk_edits_window`, `contention_temporal`.

Examples:
  python 06_harvest_temporal.py --lang en --days 90
  python 06_harvest_temporal.py --lang en --days 90 --with-velocity
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"

# Wikipedia's formal contentious-topic (CT) / general-sanctions (GS) area codes
# that mark a *politically or topically contested* area (as opposed to a conduct
# area like BLP). Codes appear in the protection-log comment as WP:CT/<CODE>,
# WP:CTOP/<CODE>, or WP:GS/<CODE>. Legacy and current spellings of the same area
# are mapped to one label (e.g. A-I / PIA -> Palestine-Israel) so they merge.
POLITICAL_CT = {
    "PIA": "Palestine-Israel", "A-I": "Palestine-Israel", "I-A": "Palestine-Israel",
    "AA": "Armenia-Azerbaijan", "A-A": "Armenia-Azerbaijan",
    "AP": "American politics",
    "EE": "Eastern Europe",
    "RUSUKR": "Russia-Ukraine",
    "KURD": "Kurds/Kurdistan", "KURDS": "Kurds/Kurdistan",
    "IPA": "India-Pakistan-Afghanistan", "IMH": "India-Pakistan military history",
    "SA": "South Asia", "SASG": "South Asian social groups", "CASTE": "Caste",
    "GG": "Gender/sexuality",
    "IRP": "Iran politics",
    "HORN": "Horn of Africa",
    "ISIL": "Syria/ISIL",
    "R-I": "Race/intelligence",
}
# Extract the raw CT/GS/CTOP area code(s) verbatim from a protection-log comment.
CT_CODE_RE = re.compile(r"(?:WP:)?(?:CT|CTOP|GS)/([A-Z0-9\-]+)")
# Fallback signal: an explicit edit-war / content-dispute lock carrying no CT code.
DISPUTE_RE = re.compile(r"Edit warring\s*/\s*[Cc]ontent dispute|WP:PP#Content disputes"
                        r"|WP:CTOP\|Contentious topic", re.I)


def classify(comment: str, include_dispute: bool) -> str | None:
    """Return a political area label for a protection comment, or None to drop it.
    Political CT-coded areas are always kept; generic edit-war/content-dispute
    locks (no CT code) are kept only when include_dispute is True and tagged
    'content-dispute' for the enrichment is_political gate to adjudicate."""
    for code in CT_CODE_RE.findall(comment):
        if code in POLITICAL_CT:
            return POLITICAL_CT[code]
    if include_dispute and DISPUTE_RE.search(comment):
        return "content-dispute"
    return None


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
                with urllib.request.urlopen(req, timeout=40) as r:
                    time.sleep(self.sleep)
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                wait = int(e.headers.get("Retry-After", 0)) or (5 * (attempt + 1))
                time.sleep(wait)
            except Exception:
                time.sleep(3 * (attempt + 1))
        raise RuntimeError(f"API failed after {self.max_retries} retries: {params}")

    def harvest_protections(self, days: int, include_dispute: bool) -> dict[str, dict]:
        """Return {title: {n, reason, ct_area, last_ts}} for politically CT-coded
        (and, if include_dispute, generic content-dispute) article protections."""
        end = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        out: dict[str, dict] = {}
        cont = None
        while True:
            p = dict(action="query", list="logevents", letype="protect", lelimit=500,
                     lenamespace=0, leend=end, ledir="older",
                     leprop="title|type|comment|timestamp")
            if cont:
                p["lecontinue"] = cont
            d = self.get(p)
            for ev in d.get("query", {}).get("logevents", []):
                if ev.get("action") == "unprotect":
                    continue
                t = ev.get("title")
                cm = ev.get("comment", "") or ""
                if not t:
                    continue
                area = classify(cm, include_dispute)
                if area is None:
                    continue
                rec = out.setdefault(t, {"n": 0, "reason": cm[:160], "ct_area": area,
                                         "last_ts": ev.get("timestamp")})
                rec["n"] += 1
                # prefer a specific political area label over generic dispute
                if rec["ct_area"] == "content-dispute" and area != "content-dispute":
                    rec["ct_area"] = area
            cont = d.get("continue", {}).get("lecontinue")
            if not cont:
                break
        return out

    def resolve_qids(self, titles: list[str]) -> dict[str, str | None]:
        out: dict[str, str | None] = {}
        for i in range(0, len(titles), self.qid_batch):
            b = titles[i : i + self.qid_batch]
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

    def talk_velocity(self, title: str, days: int) -> int:
        """Count talk-page revisions within the window (one capped call = enough
        to separate hot from cold)."""
        start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        talk = title if title.startswith("Talk:") else f"Talk:{title}"
        try:
            d = self.get(dict(action="query", prop="revisions", titles=talk,
                              rvlimit=500, rvstart=start, rvend=end, rvprop="ids"))
            for pg in d.get("query", {}).get("pages", {}).values():
                return len(pg.get("revisions", []))
        except Exception:
            pass
        return 0


def harvest(lang: str, days: int, min_prot: int, with_velocity: bool,
            include_dispute: bool, workers: int, cfg: dict) -> dict:
    api = Api(lang, cfg)
    print(f"Temporal harvest '{lang}' ({api.wiki}), last {days} days ...", flush=True)
    prot = api.harvest_protections(days, include_dispute)
    prot = {t: v for t, v in prot.items() if v["n"] >= min_prot}
    titles = list(prot)
    print(f"  {len(titles)} political-CT / dispute-protected articles; resolving Q-IDs ...",
          flush=True)
    qids = api.resolve_qids(titles)

    vel = {}
    if with_velocity:
        print(f"  fetching talk-page velocity for {len(titles)} articles "
              f"({workers} workers) ...", flush=True)
        from concurrent.futures import ThreadPoolExecutor
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for t, v in zip(titles, ex.map(lambda x: api.talk_velocity(x, days), titles)):
                vel[t] = v
                done += 1
                if done % 50 == 0:
                    print(f"    velocity {done}/{len(titles)}", flush=True)
    max_vel = max(vel.values()) if vel else 0

    candidates = []
    for t in titles:
        p = prot[t]
        v = vel.get(t, 0)
        # temporal contention: protection weight + normalized velocity (log-scaled)
        prot_w = min(p["n"] / 3.0, 1.0)
        vel_w = (math.log10(v + 1) / math.log10(max_vel + 1)) if max_vel > 0 else 0.0
        cont = round(0.5 * prot_w + 0.5 * vel_w, 3) if with_velocity else round(prot_w, 3)
        candidates.append({
            "title": t,
            "sources": [f"protection_log:{p['ct_area']}"],
            "qid": qids.get(t),
            "source_edition": lang,
            "url": f"https://{api.wiki}/wiki/" + urllib.parse.quote(t.replace(" ", "_")),
            # temporal provenance
            "ct_area": p["ct_area"],
            "protection_reason": p["reason"],
            "n_protections": p["n"],
            "last_protection": p["last_ts"],
            "talk_edits_window": v,
            "contention_temporal": cont,
        })
    candidates.sort(key=lambda c: -c["contention_temporal"])
    return {
        "route": "temporal_protection_log",
        "source_edition": lang,
        "wiki": api.wiki,
        "window_days": days,
        "harvested_at": datetime.now(timezone.utc).isoformat(),
        "with_velocity": with_velocity,
        "include_dispute": include_dispute,
        "min_protections": min_prot,
        "n_candidates": len(candidates),
        "n_with_qid": sum(1 for c in candidates if c["qid"]),
        "candidates": candidates,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en", help="edition key from editions.yaml")
    ap.add_argument("--days", type=int, default=180, help="protection-log window "
                    "(widened from 90 to 180d 2026-07 to ~double US/Europe/Russia CT yield)")
    ap.add_argument("--min-protections", type=int, default=1)
    ap.add_argument("--with-velocity", action="store_true",
                    help="fetch talk-page edit velocity (extra API calls, concurrent)")
    ap.add_argument("--include-dispute", action="store_true",
                    help="also keep generic edit-war/content-dispute locks that carry "
                         "no CT area code (higher recall, more noise for the is_political "
                         "gate to remove downstream)")
    ap.add_argument("--velocity-workers", type=int, default=8)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    cfg = load_cfg()
    if args.lang not in cfg["editions"]:
        sys.exit(f"unknown edition '{args.lang}'; known: {sorted(cfg['editions'])}")

    payload = harvest(args.lang, args.days, args.min_protections, args.with_velocity,
                      args.include_dispute, args.velocity_workers, cfg)
    out = Path(args.output) if args.output else DATA / f"candidate_issues_temporal_{args.lang}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(payload, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nWrote {payload['n_candidates']} candidates "
          f"({payload['n_with_qid']} with Q-ID) -> {out}")
    # brief area breakdown
    from collections import Counter
    areas = Counter(c["ct_area"] for c in payload["candidates"])
    for a, n in areas.most_common():
        print(f"  {n:>3}  {a}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
