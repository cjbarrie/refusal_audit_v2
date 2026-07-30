"""
Draw a reproducible issue-level stratified subsample from a frozen battery.

Sampling is at the ISSUE level: every prompt sharing an `issue_id` is kept or
dropped together, so a matched boundary pair (defend-side-A / defend-side-B)
and its regular questions are never split. Issues are stratified across the
9-domain `topic_domain` taxonomy via largest-remainder allocation, so domain
proportions in the sample track the battery.

For each language edition the script writes a sampled prompt file preserving
the original {version, language, ..., prompts} envelope, restricted to the
chosen issues. The sampled English file is the reference; the other language
editions are filtered to the same `issue_id` set so the multilingual arm stays
aligned prompt-for-prompt.

Two strategies:

  proportional (default, legacy) — draw --n-issues issues, allocated across the
      9 topic domains in proportion to the battery.

  balanced — draw a region x topic balanced study battery. Region marginals are
      made exactly equal and topic marginals are capped, because the frame is
      badly skewed on both axes (security_conflict 909 issues vs social_moral
      43; Arab 774 vs Europe 204) AND the two are collinear — Arab is 66%
      security_conflict, China is 62% territorial_sovereignty. Sampling cannot
      undo that collinearity (China simply has 18 security issues), but it can
      stop the dominant cells driving every marginal comparison.

Usage:
    python sample_prompts.py \
        --battery perennial --n-issues 20 --seed 20260712 \
        --prompts-dir ../prompts --out-dir ../prompts/sampled

    python sample_prompts.py \
        --battery rebalanced --strategy balanced --seed 20260728 \
        --prompts-dir ../prompts --out-dir ../prompts/sampled
"""
import argparse
import collections
import json
import os
import random
import re
from typing import Dict, List, Set

try:
    import yaml
except ImportError:  # yaml is only needed if a denylist is supplied
    yaml = None

LANGS = ["en", "zh", "ja", "id", "ar", "ru", "hi"]

# Prompt-file stem per battery (the language code is appended: <stem>_<lang>.json)
BATTERY_STEM = {
    "perennial": "full_prompts",
    "temporal": "temporal_prompts",
    "rebalanced": "rebalanced_prompts",
}

# Regions that have a matching model jurisdiction in the subject panel
# (MENA/India/CN/US/EU, plus General as the no-region baseline). Russia, Japan,
# Indonesia and Taiwan have no home-jurisdiction model and are thin in the
# frame, so the balanced design excludes them by default — the same reasoning
# that dropped ja/id as study languages.
MODEL_MATCHED_REGIONS = ["Arab", "India", "General", "China", "US", "Europe"]

# Default caps for the balanced draw. Chosen from the frame's actual supply:
# within the six regions above the thinnest topics hold only 43-82 issues, so a
# cap of 80 takes every one of them entire while trimming the dominant topics
# (security_conflict 909, territorial 532). That lands topic imbalance at ~1.9x
# versus 21.7x in the raw frame, for 633 issues. Insisting on exact 1.0x costs
# 255 issues (633 -> 378) to buy a property a mixed model does not need.
DEFAULT_TOPIC_CAP = 80
DEFAULT_REGION_CAP = 150


def load_battery(prompts_dir: str, stem: str, lang: str) -> Dict:
    path = os.path.join(prompts_dir, f"{stem}_{lang}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_denylist(path: str) -> Set[str]:
    """Return the set of excluded Wikidata Q-IDs from a denylist YAML.

    The file maps `excluded_qids: {Qxxxx: {issue, reason}, ...}`. Any prompt
    whose `qid` is in this set is dropped from the sample. Returns an empty set
    if `path` is falsy. Excluding at the Q-ID (not issue_id) level is robust to
    slug truncation/renaming across editions.
    """
    if not path:
        return set()
    if yaml is not None:
        with open(path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        return set((doc.get("excluded_qids") or {}).keys())

    # PyYAML absent. Only the KEYS matter here, and they are Q-IDs on their own
    # indented lines under `excluded_qids:`, so a strict line scan recovers them
    # exactly. Falling back rather than raising matters because the denylist is
    # an ethical exclusion — silently sampling without it because a dependency
    # is missing is the worst outcome. Anything that does not match the expected
    # shape raises instead of being skipped.
    qids, in_block = set(), False
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            if not line[0].isspace():
                in_block = line.strip().startswith("excluded_qids:")
                continue
            if in_block:
                key = line.strip().split(":", 1)[0].strip()
                if not re.fullmatch(r"Q\d+", key):
                    raise RuntimeError(
                        f"{path}: cannot parse entry {key!r} without PyYAML. "
                        f"Install PyYAML or fix the entry."
                    )
                qids.add(key)
    if not qids:
        raise RuntimeError(f"{path}: no excluded_qids found (parsed without PyYAML).")
    return qids


def largest_remainder(counts: Dict[str, int], total: int) -> Dict[str, int]:
    """Allocate `total` slots across strata proportional to `counts`."""
    grand = sum(counts.values())
    if grand == 0:
        return {k: 0 for k in counts}
    raw = {k: total * v / grand for k, v in counts.items()}
    floor = {k: int(v) for k, v in raw.items()}
    remainder = total - sum(floor.values())
    # Hand out the leftover slots to the largest fractional parts.
    frac_order = sorted(counts, key=lambda k: (raw[k] - floor[k]), reverse=True)
    for k in frac_order[:remainder]:
        floor[k] += 1
    return floor


def sample_issues(prompts: List[Dict], n_issues: int, seed: int) -> List[str]:
    """Return a stratified sample of issue_ids."""
    # issue_id -> its topic_domain (constant within an issue)
    issue_domain: Dict[str, str] = {}
    domain_issues: Dict[str, List[str]] = collections.defaultdict(list)
    for p in prompts:
        iid = p["issue_id"]
        if iid not in issue_domain:
            dom = p.get("topic_domain") or "unknown"
            issue_domain[iid] = dom
            domain_issues[dom].append(iid)

    total_issues = len(issue_domain)
    n_issues = min(n_issues, total_issues)

    domain_counts = {d: len(v) for d, v in domain_issues.items()}
    alloc = largest_remainder(domain_counts, n_issues)

    rng = random.Random(seed)
    chosen: List[str] = []
    for dom in sorted(domain_issues):
        pool = sorted(domain_issues[dom])  # deterministic order before shuffling
        rng.shuffle(pool)
        take = min(alloc.get(dom, 0), len(pool))
        chosen.extend(pool[:take])

    # If rounding left us short/over (e.g. a domain lacked issues), fix up.
    if len(chosen) < n_issues:
        remaining = [i for i in sorted(issue_domain) if i not in set(chosen)]
        rng.shuffle(remaining)
        chosen.extend(remaining[: n_issues - len(chosen)])
    chosen = chosen[:n_issues]
    return sorted(chosen)


class _MaxFlow:
    """Dinic max-flow. Small graph (regions + topics + 2), so speed is moot;
    what matters is that it is exact and deterministic for a fixed input order,
    which is what makes the draw reproducible."""

    def __init__(self, n: int):
        self.n = n
        self.g: List[List[List[int]]] = [[] for _ in range(n)]

    def add(self, u: int, v: int, cap: int) -> tuple:
        self.g[u].append([v, cap, len(self.g[v])])
        self.g[v].append([u, 0, len(self.g[u]) - 1])
        return (u, len(self.g[u]) - 1, cap)          # handle for reading flow back

    def flow_on(self, handle) -> int:
        u, idx, cap = handle
        return cap - self.g[u][idx][1]

    def _bfs(self, t: int) -> bool:
        self.lv = [-1] * self.n
        self.lv[0] = 0
        q = [0]
        for u in q:
            for e in self.g[u]:
                if e[1] > 0 and self.lv[e[0]] < 0:
                    self.lv[e[0]] = self.lv[u] + 1
                    q.append(e[0])
        return self.lv[t] >= 0

    def _dfs(self, u: int, t: int, f: int) -> int:
        if u == t:
            return f
        while self.it[u] < len(self.g[u]):
            e = self.g[u][self.it[u]]
            if e[1] > 0 and self.lv[e[0]] == self.lv[u] + 1:
                d = self._dfs(e[0], t, min(f, e[1]))
                if d > 0:
                    e[1] -= d
                    self.g[e[0]][e[2]][1] += d
                    return d
            self.it[u] += 1
        return 0

    def run(self, t: int) -> int:
        total = 0
        while self._bfs(t):
            self.it = [0] * self.n
            while True:
                f = self._dfs(0, t, 10 ** 9)
                if f == 0:
                    break
                total += f
        return total


def _largest_balanced_quota(supply: Dict[tuple, int], regions: List[str],
                            topics: List[str], topic_cap: int) -> int:
    """Largest per-region quota q for which every region can supply exactly q
    without any topic exceeding `topic_cap`.

    Max-flow is the right tool for this feasibility question: a region can only
    fill its quota from the topics it actually has, and taking from a shared
    topic uses up quota another region may have been depending on.
    """
    q = 0
    while True:
        nxt = q + 1
        n = 1 + len(regions) + len(topics) + 1
        snk = n - 1
        mf = _MaxFlow(n)
        for i, _ in enumerate(regions):
            mf.add(0, 1 + i, nxt)
        for j, _ in enumerate(topics):
            mf.add(1 + len(regions) + j, snk, topic_cap)
        for i, r in enumerate(regions):
            for j, t in enumerate(topics):
                if supply.get((r, t)):
                    mf.add(1 + i, 1 + len(regions) + j, supply[(r, t)])
        if mf.run(snk) != nxt * len(regions):
            return q
        q = nxt


def _ipf_allocate(supply: Dict[tuple, int], regions: List[str], topics: List[str],
                  region_target: int, topic_cap: int, iters: int = 500) -> Dict[tuple, int]:
    """Spread each region's quota across topics *proportionally to what that
    region actually has*, subject to the topic cap.

    Why not just use the max-flow solution directly: max-flow returns SOME
    optimal vertex, and is indifferent between them. On this frame it happily
    returned an allocation with Arab x security_conflict = 0 — dropping the
    single most substantively important cell in the study (MENA models on MENA
    conflicts) purely because other regions could fill the security quota. The
    margins were right and the interior was nonsense.

    Iterative proportional fitting gives a smooth interior instead: alternately
    scale rows to the region quota and shrink any topic column that exceeds the
    cap, clamping at available supply throughout. Cells stay proportional to
    supply, so no cell is zeroed unless it is genuinely empty.
    """
    a = {(r, t): float(supply.get((r, t), 0)) for r in regions for t in topics}
    for _ in range(iters):
        for r in regions:
            s = sum(a[(r, t)] for t in topics)
            if s > 0:
                f = region_target / s
                for t in topics:
                    a[(r, t)] = min(a[(r, t)] * f, float(supply.get((r, t), 0)))
        for t in topics:
            s = sum(a[(r, t)] for r in regions)
            if s > topic_cap and s > 0:
                f = topic_cap / s
                for r in regions:
                    a[(r, t)] *= f

    # Integer rounding: floor, then hand leftover region quota to the largest
    # fractional parts that still have supply headroom.
    out = {k: int(v) for k, v in a.items()}
    for r in regions:
        short = region_target - sum(out[(r, t)] for t in topics)
        if short <= 0:
            continue
        order = sorted(topics, key=lambda t: (a[(r, t)] - int(a[(r, t)])), reverse=True)
        for t in order:
            if short == 0:
                break
            head = supply.get((r, t), 0) - out[(r, t)]
            cap_head = topic_cap - sum(out[(rr, t)] for rr in regions)
            add = min(short, head, cap_head)
            if add > 0:
                out[(r, t)] += add
                short -= add
    return out


def sample_issues_capped(prompts: List[Dict], topic_cap: int, region_cap: int,
                         regions: List[str], seed: int) -> tuple:
    """Draw the largest issue set with no topic over `topic_cap` and no region
    over `region_cap`.

    This is a transportation problem, not a proportional allocation: how many
    issues each region x topic cell contributes is decided jointly, because
    trimming an over-supplied cell in one region frees quota that another region
    can only fill from the cells it actually has. Max-flow solves it exactly —
    source -> region (region_cap), region -> topic (issues available in that
    cell), topic -> sink (topic_cap). The resulting flow IS the per-cell draw.

    Greedy per-topic or per-region allocation gets this wrong: it will happily
    exhaust a topic's quota on the one region that has plenty, leaving other
    regions unable to reach their own quota.

    Returns (chosen_issue_ids, allocation_table).
    """
    issue_cell: Dict[str, tuple] = {}
    cell_issues: Dict[tuple, List[str]] = collections.defaultdict(list)
    for p in prompts:
        iid = p["issue_id"]
        if iid in issue_cell:
            continue
        reg = p.get("region_focus") or "unknown"
        top = p.get("topic_domain") or "unknown"
        issue_cell[iid] = (reg, top)
        cell_issues[(reg, top)].append(iid)

    regs = [r for r in regions if any(k[0] == r for k in cell_issues)]
    tops = sorted({t for (r, t) in cell_issues if r in regs})
    supply = {(r, t): len(cell_issues.get((r, t), [])) for r in regs for t in tops}

    # Largest quota every region can actually meet, then cap it at --region-cap.
    q = min(_largest_balanced_quota(supply, regs, tops, topic_cap), region_cap)
    alloc = _ipf_allocate(supply, regs, tops, q, topic_cap)

    rng = random.Random(seed)
    chosen: List[str] = []
    for (r, t), take in sorted(alloc.items()):
        if take <= 0:
            continue
        pool = sorted(cell_issues[(r, t)])   # deterministic before shuffling
        rng.shuffle(pool)
        chosen.extend(pool[:take])
    return sorted(chosen), alloc


def report_allocation(alloc: Dict[tuple, int], regions: List[str]) -> None:
    tops = sorted({t for (_, t) in alloc})
    regs = [r for r in regions if any(k[0] == r for k in alloc)]
    w = max(10, max((len(t[:11]) for t in tops), default=10) + 1)
    print()
    print("region".ljust(10) + "".join(t[:11].rjust(w) for t in tops) + "TOTAL".rjust(8))
    for r in regs:
        row = [alloc.get((r, t), 0) for t in tops]
        print(r.ljust(10) + "".join(str(v).rjust(w) for v in row) + str(sum(row)).rjust(8))
    col = [sum(alloc.get((r, t), 0) for r in regs) for t in tops]
    print("TOTAL".ljust(10) + "".join(str(v).rjust(w) for v in col) + str(sum(col)).rjust(8))
    if col and min(col) > 0:
        print(f"\n  topic imbalance (max/min): {max(col) / min(col):.2f}x")
    rowsums = [sum(alloc.get((r, t), 0) for t in tops) for r in regs]
    if rowsums and min(rowsums) > 0:
        print(f"  region imbalance (max/min): {max(rowsums) / min(rowsums):.2f}x")


def main():
    ap = argparse.ArgumentParser(description="Issue-level stratified battery subsample")
    ap.add_argument("--battery", required=True, choices=list(BATTERY_STEM))
    ap.add_argument("--strategy", choices=["proportional", "balanced"],
                    default="proportional",
                    help="proportional: legacy topic-proportional draw of --n-issues. "
                         "balanced: region x topic draw under --topic-cap/--region-cap, "
                         "which sets its own size (--n-issues is ignored).")
    ap.add_argument("--n-issues", type=int, default=None,
                    help="required for --strategy proportional")
    ap.add_argument("--topic-cap", type=int, default=DEFAULT_TOPIC_CAP)
    ap.add_argument("--region-cap", type=int, default=DEFAULT_REGION_CAP)
    ap.add_argument("--regions", nargs="+", default=MODEL_MATCHED_REGIONS,
                    help="regions eligible for the balanced draw")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--prompts-dir", default="../prompts")
    ap.add_argument("--out-dir", default="../prompts/sampled")
    ap.add_argument("--exclude-deleted", action="store_true",
                    help="drop issues whose source Wikipedia article no longer "
                         "exists (source_article_status == 'deleted', stamped by "
                         "sourcing/14_recover_provenance.py). Their prompt text is "
                         "still well-formed, but the source cannot be inspected or "
                         "cited, and deletion usually means the topic failed "
                         "notability or was a POV fork.")
    ap.add_argument("--require-revid", action="store_true",
                    help="drop issues whose record carries no provenance.rev_id, so "
                         "every drawn prompt traces to a citable source revision. On "
                         "the current frame this is implied by --exclude-deleted (the "
                         "two sets coincide), but that is a property of this frame, "
                         "not a guarantee.")
    ap.add_argument("--records", default="../data/issue_records_rebalanced.jsonl",
                    help="issue records, read only for --exclude-deleted. Status is "
                         "read from here rather than copied into the prompt files "
                         "because whether an article still exists changes over time.")
    ap.add_argument("--denylist", default="../prompts/excluded_issues.yaml",
                    help="YAML of ethically-excluded Wikidata Q-IDs to drop "
                         "before sampling. Pass '' to disable.")
    args = ap.parse_args()

    stem = BATTERY_STEM[args.battery]
    os.makedirs(args.out_dir, exist_ok=True)

    # Load the ethical denylist (Q-IDs). Applied BEFORE issue selection so an
    # excluded issue can never be drawn and never skews the domain allocation.
    deny_qids = load_denylist(args.denylist)

    # Issues whose source article has been deleted from Wikipedia. Applied
    # BEFORE allocation, like the denylist, so a dropped issue never occupies a
    # region x topic slot that a live issue could have filled.
    deleted_issues: Set[str] = set()
    norevid_issues: Set[str] = set()
    if args.exclude_deleted or args.require_revid:
        if not os.path.exists(args.records):
            raise SystemExit(
                f"This needs {args.records}, which does not exist. Run "
                f"sourcing/14_recover_provenance.py first — it stamps both "
                f"source_article_status and provenance.rev_id.")
        seen_status = False
        with open(args.records, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                if "source_article_status" in r:
                    seen_status = True
                    if r["source_article_status"] == "deleted":
                        deleted_issues.add(r["issue_id"])
                if not (r.get("provenance") or {}).get("rev_id"):
                    norevid_issues.add(r["issue_id"])
        if args.exclude_deleted and not seen_status:
            raise SystemExit(
                f"--exclude-deleted: no record in {args.records} carries "
                f"source_article_status. Run sourcing/14_recover_provenance.py first.")
        if not args.exclude_deleted:
            deleted_issues = set()
        if not args.require_revid:
            norevid_issues = set()
        if args.exclude_deleted:
            print(f"Excluding {len(deleted_issues)} issues whose source article "
                  f"is deleted.")
        if args.require_revid:
            extra = norevid_issues - deleted_issues
            print(f"Requiring a source rev_id: {len(norevid_issues)} issues lack one "
                  f"({len(extra)} not already excluded as deleted).")

    # Choose issues from the English edition (the reference), excluding any
    # prompt whose qid is on the denylist.
    en = load_battery(args.prompts_dir, stem, "en")
    # Report the two exclusions separately. Lumping them together under
    # "denylist" made an 18-issue deleted-source exclusion look like the ethical
    # denylist had tripled in reach.
    n_deny = sum(1 for p in en["prompts"] if p.get("qid") in deny_qids)
    n_del = sum(1 for p in en["prompts"]
                if p.get("qid") not in deny_qids
                and p.get("issue_id") in (deleted_issues | norevid_issues))
    drop_issues = deleted_issues | norevid_issues
    en_prompts = [p for p in en["prompts"]
                  if p.get("qid") not in deny_qids
                  and p.get("issue_id") not in drop_issues]
    n_dropped_ref = len(en["prompts"]) - len(en_prompts)
    if deny_qids:
        print(f"Denylist: {len(deny_qids)} Q-IDs; dropped {n_deny} reference prompts.")
    if deleted_issues:
        print(f"Deleted-source: dropped {n_del} further reference prompts.")
    alloc = None
    if args.strategy == "balanced":
        chosen_list, alloc = sample_issues_capped(
            en_prompts, args.topic_cap, args.region_cap, args.regions, args.seed)
        chosen = set(chosen_list)
        print(f"Balanced draw: topic cap {args.topic_cap}, region cap "
              f"{args.region_cap}, regions {args.regions}")
        report_allocation(alloc, args.regions)
        print(f"\n{len(chosen)} issues selected")
    else:
        if args.n_issues is None:
            ap.error("--n-issues is required with --strategy proportional")
        chosen = set(sample_issues(en_prompts, args.n_issues, args.seed))

    manifest = {
        "battery": args.battery,
        "strategy": args.strategy,
        "seed": args.seed,
        "n_issues_requested": args.n_issues,
        "n_issues_selected": len(chosen),
        "topic_cap": args.topic_cap if args.strategy == "balanced" else None,
        "region_cap": args.region_cap if args.strategy == "balanced" else None,
        "regions": args.regions if args.strategy == "balanced" else None,
        "allocation": ({f"{r}|{t}": v for (r, t), v in sorted(alloc.items()) if v}
                       if alloc else None),
        "issue_ids": sorted(chosen),
        "excluded_deleted_issues": sorted(deleted_issues) if args.exclude_deleted else None,
        "excluded_no_revid_issues": sorted(norevid_issues) if args.require_revid else None,
        "denylist_path": args.denylist or None,
        "denylist_qids": sorted(deny_qids),
        "reference_prompts_dropped_by_denylist": n_dropped_ref,
        "per_language": {},
    }

    for lang in LANGS:
        # Not every battery exists in every language (ja/id were dropped as
        # study languages and were never produced for the rebalanced frame).
        if not os.path.exists(os.path.join(args.prompts_dir, f"{stem}_{lang}.json")):
            print(f"{lang}: no {stem}_{lang}.json — skipping")
            continue
        data = load_battery(args.prompts_dir, stem, lang)
        # Filter to chosen issues AND re-apply the denylist (defensive: guards
        # against any per-edition qid that slipped the reference filter).
        kept = [p for p in data["prompts"]
                if p["issue_id"] in chosen and p.get("qid") not in deny_qids
                and p["issue_id"] not in drop_issues]
        out = dict(data)
        out["prompts"] = kept
        out["total_prompts"] = len(kept)
        out["n_issues"] = len(chosen)
        out["sample_of"] = f"{stem}_{lang}.json"
        out["sample_seed"] = args.seed
        by_tier = collections.Counter(p["controversy_tier"] for p in kept)
        out["sample_tier_counts"] = dict(by_tier)
        out_path = os.path.join(args.out_dir, f"{stem}_{lang}_sample.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        manifest["per_language"][lang] = {
            "path": out_path,
            "n_prompts": len(kept),
            "tier_counts": dict(by_tier),
        }
        print(f"{lang}: {len(kept)} prompts -> {out_path}")

    man_path = os.path.join(args.out_dir, f"{args.battery}_sample_manifest.json")
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"manifest -> {man_path}  ({len(chosen)} issues)")


if __name__ == "__main__":
    main()
