#!/usr/bin/env python3
"""
Stage 14 — restore the provenance guarantee: source revision id + article status.

The problem
-----------
`PIPELINE.md` §3 states that every issue record carries a `rev_id` and snapshot
date "so the battery is reproducible and its currency relative to model training
cutoffs is documented". That held for the perennial route (808/808) but NOT for
the two temporal routes, whose enricher hardcoded `rev_id: None`:

    perennial        808/808  carry a rev_id
    temporal           0/1462
    current-events     0/503

So 1,965 of 2,773 records — 71% of the frame — had no citable source revision.
That is not a bookkeeping nicety: 18 of the harvested articles were **deleted
from Wikipedia within weeks**, and without a revision id their source text
cannot be recovered or quoted at all.

What this does
--------------
1. **Article status** for every record (batched, 50 titles/call): `live` or
   `deleted`. Recorded as `source_article_status`, so analysis can exclude
   issues whose source no longer exists — and so the count is auditable rather
   than discovered later.
2. **Revision id as of the snapshot date** for every live record missing one.
   `rvstart=<snapshot>&rvdir=older&rvlimit=1` returns the revision that was
   current when the article was harvested — the revision the prompt was actually
   derived from — not merely today's. That distinction is the whole point:
   citing today's revision would misrepresent what the model was asked about.

Recovered ids are marked `rev_id_recovered: true` so they are never mistaken for
ids captured at harvest time. Deleted articles cannot be recovered; they are
flagged instead.

`07_enrich_temporal.py` now captures the revision id in the same call as the
lead extract, so future runs do not need this.

Read-only Wikipedia. No API key, no spend.

Usage:
    python 14_recover_provenance.py --dry-run
    python 14_recover_provenance.py
"""
from __future__ import annotations

import argparse
import collections
import json
import shutil
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"

UA = "refusal-audit-research/0.1 (academic LLM political-behavior audit)"
BATCH = 50

_THROTTLE = threading.Lock()


def api(host: str, params: dict, tries: int = 8) -> dict:
    """MediaWiki GET with rate-limit-aware backoff.

    An earlier version retried 5 times with ~15s of total backoff and ignored
    the `Retry-After` header; a 429 partway through a 2,351-title pass killed
    the run and lost every lookup already done. This honours `Retry-After`,
    backs off exponentially up to a minute, and sends `maxlag` so the server can
    tell us to slow down before it starts refusing.
    """
    params = {**params, "format": "json", "formatversion": "2", "maxlag": "5"}
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                d = json.load(r)
            # maxlag / ratelimit surface as a normal 200 with an error block
            err = (d.get("error") or {}).get("code")
            if err in ("maxlag", "ratelimited"):
                raise urllib.error.HTTPError(url, 429, str(err), None, None)
            return d
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == tries - 1:
                raise
            wait = 0
            try:
                wait = int((e.headers or {}).get("Retry-After") or 0)
            except (TypeError, ValueError):
                wait = 0
            wait = max(wait, min(60, 3 * (2 ** attempt)))
            print(f"    [{host}] {e.code} — backing off {wait}s "
                  f"(attempt {attempt+1}/{tries})", flush=True)
            # Hold the lock so concurrent workers pause too rather than piling on.
            with _THROTTLE:
                time.sleep(wait)
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(min(30, 2.0 * (attempt + 1)))
    return {}


class Checkpoint:
    """Resumable progress store.

    This pass makes ~2,400 batched status calls plus ~1,950 single-page revision
    calls. Losing all of it to one 429 near the end is unacceptable, so every
    result is written to disk as it arrives and a re-run skips what is already
    known. Delete the file to force a full refresh.
    """

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.data = {"status": {}, "revid": {}}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
                self.data.setdefault("status", {})
                self.data.setdefault("revid", {})
            except Exception:
                pass
        self._dirty = 0

    def get(self, kind: str, key: str):
        return self.data[kind].get(key)

    def put(self, kind: str, key: str, value) -> None:
        with self.lock:
            self.data[kind][key] = value
            self._dirty += 1
            if self._dirty >= 25:
                self._flush()

    def _flush(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)          # atomic; a crash never truncates it
        self._dirty = 0

    def flush(self) -> None:
        with self.lock:
            self._flush()


def _unalias(q: dict) -> dict:
    """returned title -> the title we asked for (through normalize + redirect)."""
    back = {}
    for n in q.get("normalized", []):
        back[n["to"]] = n["from"]
    for rd in q.get("redirects", []):
        back[rd["to"]] = back.get(rd["from"], rd["from"])
    return back


def article_status(titles: list[str], host: str, ck: "Checkpoint",
                   sleep: float = 0.5) -> dict:
    """title -> 'live' | 'deleted'. Batched, checkpointed, resumable."""
    out: dict = {}
    todo = []
    for t in titles:
        cached = ck.get("status", f"{host}|{t}")
        if cached:
            out[t] = cached
        else:
            todo.append(t)
    if len(todo) != len(titles):
        print(f"  [{host}] {len(titles)-len(todo)} already known, {len(todo)} to fetch")
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        d = api(host, {"action": "query", "titles": "|".join(chunk),
                       "prop": "info", "redirects": "1"})
        q = d.get("query", {})
        back = _unalias(q)
        seen = set()
        for page in q.get("pages", []):
            asked = back.get(page.get("title"), page.get("title"))
            out[asked] = "deleted" if page.get("missing") else "live"
            seen.add(asked)
        for t in chunk:                      # anything the API never mentioned
            out.setdefault(t, "deleted")
        for t in chunk:
            ck.put("status", f"{host}|{t}", out[t])
        print(f"  [{host}] status {min(i+BATCH, len(todo))}/{len(todo)}", flush=True)
        time.sleep(sleep)
    ck.flush()
    return out


def revid_at(title: str, host: str, snapshot: str) -> int | None:
    """Revision current at `snapshot` (YYYY-MM-DD). One page per call — rvlimit
    cannot be combined with multiple titles."""
    try:
        d = api(host, {"action": "query", "titles": title, "prop": "revisions",
                       "rvprop": "ids|timestamp", "rvlimit": "1", "rvdir": "older",
                       "rvstart": f"{snapshot}T23:59:59Z", "redirects": "1"})
        pages = d.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing"):
            return None
        revs = pages[0].get("revisions") or []
        return revs[0]["revid"] if revs else None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", default=str(DATA / "issue_records_rebalanced.jsonl"))
    ap.add_argument("--workers", type=int, default=4,
                    help="concurrent revision lookups. Wikipedia rate-limits "
                         "anonymous clients; 4 is comfortable, 8 draws 429s.")
    ap.add_argument("--sleep", type=float, default=0.5,
                    help="pause between batched status calls")
    ap.add_argument("--checkpoint", default=str(DATA / "_provenance_cache.json"),
                    help="resumable progress store; delete to force a refresh")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    ck = Checkpoint(Path(args.checkpoint))
    known = len(ck.data["status"]) + len(ck.data["revid"])
    if known:
        print(f"resuming from {Path(args.checkpoint).name}: {known} lookups already done")

    path = Path(args.records)
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"{len(recs)} records")

    have = sum(1 for r in recs if (r.get("provenance") or {}).get("rev_id"))
    print(f"  carry a rev_id : {have}")
    print(f"  missing        : {len(recs) - have}")
    by_route = collections.defaultdict(lambda: [0, 0])
    for r in recs:
        route = (r.get("contention_signals") or {}).get("route") or "perennial"
        by_route[route][0] += 1
        if (r.get("provenance") or {}).get("rev_id"):
            by_route[route][1] += 1
    for k, (n, w) in sorted(by_route.items()):
        print(f"    {k:16s} {w:5d}/{n:5d}")

    # ---- 1. article status, for every record ------------------------------
    by_ed = collections.defaultdict(list)
    for r in recs:
        by_ed[r.get("source_edition") or "en"].append(r)
    print("\nchecking article status...")
    status: dict = {}
    for ed, rs in sorted(by_ed.items()):
        got = article_status([r["title"] for r in rs], f"{ed}.wikipedia.org",
                             ck, sleep=args.sleep)
        for r in rs:
            status[r["issue_id"]] = got.get(r["title"], "deleted")
    counts = collections.Counter(status.values())
    print(f"  {dict(counts)}")
    dead = [r for r in recs if status.get(r["issue_id"]) == "deleted"]
    if dead:
        print(f"  articles no longer on Wikipedia ({len(dead)}):")
        for r in dead[:8]:
            print(f"     [{r.get('source_edition')}] {r['title'][:56]}")
        if len(dead) > 8:
            print(f"     ... {len(dead)} total")

    # ---- 2. rev_id as of the snapshot, for live records missing one --------
    todo = [r for r in recs
            if not (r.get("provenance") or {}).get("rev_id")
            and status.get(r["issue_id"]) == "live"]
    print(f"\nrecovering rev_id for {len(todo)} live records "
          f"(as of each record's snapshot date)...")
    if args.dry_run:
        print("--dry-run: nothing queried further, nothing written.")
        return 0

    found: dict = {}
    pending = []
    for r in todo:
        cached = ck.get("revid", r["issue_id"])
        if cached:
            found[r["issue_id"]] = cached
        else:
            pending.append(r)
    if found:
        print(f"  {len(found)} already in the checkpoint; {len(pending)} to fetch")

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {}
        for r in pending:
            prov = r.get("provenance") or {}
            snap = prov.get("snapshot") or "2026-07-27"
            host = f"{r.get('source_edition') or 'en'}.wikipedia.org"
            futs[ex.submit(revid_at, r["title"], host, snap)] = r["issue_id"]
        for fut in as_completed(futs):
            iid = futs[fut]
            try:
                rid = fut.result()
            except Exception as e:      # one bad title must not lose the pass
                print(f"    ! {iid}: {type(e).__name__}", flush=True)
                rid = None
            if rid:
                found[iid] = rid
                ck.put("revid", iid, rid)
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(pending)}", flush=True)
    ck.flush()
    print(f"  recovered {len(found)}/{len(todo)}")

    # ---- write ------------------------------------------------------------
    if not args.no_backup:
        bak = path.with_suffix(path.suffix + ".pre_provenance_recovery")
        if not bak.exists():
            shutil.copy2(path, bak)
    for r in recs:
        r["source_article_status"] = status.get(r["issue_id"], "unknown")
        prov = r.get("provenance")
        if not isinstance(prov, dict):
            prov = {}
            r["provenance"] = prov
        if r["issue_id"] in found:
            prov["rev_id"] = found[r["issue_id"]]
            # Marked so a recovered id is never mistaken for one captured at
            # harvest time — it is the revision as of the snapshot date, which
            # is correct, but it was reconstructed after the fact.
            prov["rev_id_recovered"] = True
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
                    encoding="utf-8")
    print(f"\nwrote {path.name}")

    now = sum(1 for r in recs if (r.get("provenance") or {}).get("rev_id"))
    print(f"  rev_id coverage: {have} -> {now} / {len(recs)}")
    still = [r for r in recs if not (r.get("provenance") or {}).get("rev_id")]
    print(f"  still without a rev_id: {len(still)} "
          f"({sum(1 for r in still if r.get('source_article_status') == 'deleted')} "
          f"because the article is gone)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
