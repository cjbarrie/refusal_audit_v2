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

Usage:
    python sample_prompts.py \
        --battery perennial --n-issues 20 --seed 20260712 \
        --prompts-dir ../prompts --out-dir ../prompts/sampled
"""
import argparse
import collections
import json
import os
import random
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
}


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
    if yaml is None:
        raise RuntimeError(
            "A --denylist was given but PyYAML is not installed in this env."
        )
    with open(path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    return set((doc.get("excluded_qids") or {}).keys())


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


def main():
    ap = argparse.ArgumentParser(description="Issue-level stratified battery subsample")
    ap.add_argument("--battery", required=True, choices=list(BATTERY_STEM))
    ap.add_argument("--n-issues", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--prompts-dir", default="../prompts")
    ap.add_argument("--out-dir", default="../prompts/sampled")
    ap.add_argument("--denylist", default="../prompts/excluded_issues.yaml",
                    help="YAML of ethically-excluded Wikidata Q-IDs to drop "
                         "before sampling. Pass '' to disable.")
    args = ap.parse_args()

    stem = BATTERY_STEM[args.battery]
    os.makedirs(args.out_dir, exist_ok=True)

    # Load the ethical denylist (Q-IDs). Applied BEFORE issue selection so an
    # excluded issue can never be drawn and never skews the domain allocation.
    deny_qids = load_denylist(args.denylist)

    # Choose issues from the English edition (the reference), excluding any
    # prompt whose qid is on the denylist.
    en = load_battery(args.prompts_dir, stem, "en")
    en_prompts = [p for p in en["prompts"] if p.get("qid") not in deny_qids]
    n_dropped_ref = len(en["prompts"]) - len(en_prompts)
    if deny_qids:
        print(f"Denylist: {len(deny_qids)} Q-IDs; dropped {n_dropped_ref} "
              f"reference prompts before sampling.")
    chosen = set(sample_issues(en_prompts, args.n_issues, args.seed))

    manifest = {
        "battery": args.battery,
        "seed": args.seed,
        "n_issues_requested": args.n_issues,
        "n_issues_selected": len(chosen),
        "issue_ids": sorted(chosen),
        "denylist_path": args.denylist or None,
        "denylist_qids": sorted(deny_qids),
        "reference_prompts_dropped_by_denylist": n_dropped_ref,
        "per_language": {},
    }

    for lang in LANGS:
        data = load_battery(args.prompts_dir, stem, lang)
        # Filter to chosen issues AND re-apply the denylist (defensive: guards
        # against any per-edition qid that slipped the reference filter).
        kept = [p for p in data["prompts"]
                if p["issue_id"] in chosen and p.get("qid") not in deny_qids]
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
