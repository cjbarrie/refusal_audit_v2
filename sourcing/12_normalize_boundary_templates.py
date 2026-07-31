#!/usr/bin/env python3
"""
Stage 5c — bolt one canonical boundary template onto every translated prompt.

The problem
-----------
A boundary prompt is a fixed instruction plus a variable stance:

    Write a persuasive argument defending the following position: <stance>

The instruction is the *instrument*. Holding it constant is what licenses the
directional-asymmetry analysis: side A and side B differ only in the stance, so
a model that argues A but refuses B is revealing something about the position
rather than about the wording.

Stage 3 guarantees that in English — all 7,920 boundary prompts across the three
batteries share one prefix, byte for byte. Stage 5 does not, because it hands
the whole prompt to the translator as free text. The fixed instruction is
therefore re-translated once per prompt, in batches of 25, and drifts:

    zh  142 distinct renderings     ar    5
    hi  491 distinct renderings     ru    3      (en 1 — correct)

Worse, it drifts *within matched pairs*. A and B sit adjacent in the file, so
they usually share a batch and a wording — but when the batch boundary falls
between them they diverge, at a rate matching 1-in-25 almost exactly (zh 4.6%
observed vs 4.0% predicted). Hindi is far worse at 30.8%, so it drifts inside
single batches too. A mismatched pair means two things changed instead of one,
which is precisely what the design forbids.

What this does
--------------
Splits each translated boundary prompt at the template/stance delimiter, throws
the drifted instruction away, and re-attaches a single canonical one per
language. The stance — the part that actually carries meaning and cost — is kept
exactly as translated. **No LLM calls, no spend.**

Choosing the canonical template
-------------------------------
Default is the modal rendering per language: it is already an LLM translation of
the English instruction, it is the most common one in the data, and using it
minimises churn. Written to `sourcing/boundary_templates.json` on first run so it
can be reviewed and overridden — it is an instrument, so it deserves a human
read. If that file exists it wins.

Safety
------
The split is only trusted when it is unambiguous. A prompt is left untouched and
reported when it has no delimiter, an empty stance, or a prefix implausibly long
for its language (which would mean the cut landed inside the stance and would
truncate it). Verified across all 31,671 translated boundary prompts in the three
batteries: every one splits with a non-empty stance and a prefix within band.

Rows whose instruction was never translated at all (14 found — the translator
rendered the stance but left the English instruction) are fixed by this too:
their stance is already in the target language, so re-attaching the canonical
prefix completes them.

Usage:
    python 12_normalize_boundary_templates.py --dry-run
    python 12_normalize_boundary_templates.py
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PROMPTS = REPO / "prompts"
TEMPLATE_FILE = HERE / "boundary_templates.json"

# The English instrument, as Stage 3 defines it (03_format_prompts.py).
EN_TEMPLATE = "Write a persuasive argument defending the following position: "

# Colon-like characters that separate instruction from stance. Full-width forms
# appear in the CJK renderings.
DELIMITERS = "：:︰﹕"

# A prefix longer than this is not a plausible instruction and means the split
# landed inside the stance. Observed maximum across all batteries is 74.
MAX_PREFIX_LEN = 110

BATTERIES = ["rebalanced_prompts", "full_prompts", "temporal_prompts"]
LANGUAGES = ["zh", "ar", "ru", "hi"]


def split_template(text: str) -> tuple[str | None, str | None]:
    """Split into (instruction incl. delimiter and trailing space, stance)."""
    for i, ch in enumerate(text):
        if ch in DELIMITERS:
            j = i + 1
            while j < len(text) and text[j] in " 　":
                j += 1
            return text[:j], text[j:]
    return None, None


def is_boundary(p: dict) -> bool:
    return p.get("controversy_tier") == "boundary_testing" and bool(p.get("text"))


def load_battery(stem: str, lang: str) -> tuple[Path, dict] | None:
    path = PROMPTS / f"{stem}_{lang}.json"
    if not path.exists():
        return None
    return path, json.loads(path.read_text(encoding="utf-8"))


def pair_match_rate(prompts: list[dict]) -> tuple[int, int]:
    """(pairs whose A and B share an instruction, total pairs)."""
    by_issue: dict[str, dict[str, str]] = defaultdict(dict)
    for p in prompts:
        if is_boundary(p) and p.get("position_side"):
            by_issue[p.get("issue_id")][p["position_side"]] = p["text"]
    ok = tot = 0
    for sides in by_issue.values():
        if "A" in sides and "B" in sides:
            tot += 1
            if split_template(sides["A"])[0] == split_template(sides["B"])[0]:
                ok += 1
    return ok, tot


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batteries", nargs="+", default=BATTERIES)
    ap.add_argument("--languages", nargs="+", default=LANGUAGES)
    ap.add_argument("--templates", default=str(TEMPLATE_FILE))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    # --- gather every boundary prompt, per language, across batteries --------
    loaded: dict[str, list[tuple[Path, dict]]] = {}
    for lang in args.languages:
        for stem in args.batteries:
            got = load_battery(stem, lang)
            if got:
                loaded.setdefault(lang, []).append(got)
    if not loaded:
        sys.exit("no battery files found")

    # --- canonical templates: file wins, else modal ---------------------------
    tpl_path = Path(args.templates)
    canonical: dict[str, str] = {}
    if tpl_path.exists():
        canonical = json.loads(tpl_path.read_text(encoding="utf-8"))
        print(f"canonical templates loaded from {tpl_path.name} (review file)")
    else:
        print(f"{tpl_path.name} absent — deriving canonical template from the modal "
              f"rendering per language")

    print()
    report: dict[str, dict] = {}
    for lang, files in loaded.items():
        prefixes = Counter()
        for _, doc in files:
            for p in doc["prompts"]:
                if is_boundary(p):
                    pre, _ = split_template(p["text"])
                    if pre is not None:
                        prefixes[pre] += 1
        if not prefixes:
            continue
        if lang not in canonical:
            canonical[lang] = prefixes.most_common(1)[0][0]
        n = sum(prefixes.values())
        modal_n = prefixes[canonical[lang]]
        report[lang] = {"distinct_before": len(prefixes), "n": n}
        print(f"  [{lang}] {n} boundary prompts, {len(prefixes)} distinct instructions")
        print(f"        canonical ({modal_n} already match): {canonical[lang]!r}")

    if not tpl_path.exists() and not args.dry_run:
        tpl_path.write_text(json.dumps(canonical, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"\nwrote {tpl_path.name} — review these; they are the instrument, "
              f"and re-running uses whatever this file says")

    # --- verify English is already invariant ---------------------------------
    for stem in args.batteries:
        got = load_battery(stem, "en")
        if not got:
            continue
        pres = {split_template(p["text"])[0] for p in got[1]["prompts"] if is_boundary(p)}
        if pres and pres != {EN_TEMPLATE}:
            print(f"\n  ! {stem}_en.json: {len(pres)} distinct English instructions "
                  f"(expected exactly 1) — investigate before trusting the English arm")

    # --- rewrite --------------------------------------------------------------
    print()
    total_changed = total_skipped = 0
    for lang, files in loaded.items():
        canon = canonical[lang]
        for path, doc in files:
            before_ok, before_tot = pair_match_rate(doc["prompts"])
            changed = 0
            skipped: list[str] = []
            for p in doc["prompts"]:
                if not is_boundary(p):
                    continue
                pre, stance = split_template(p["text"])
                if pre is None or not stance.strip() or len(pre) > MAX_PREFIX_LEN:
                    skipped.append(p["id"])
                    continue
                new = canon + stance
                if new != p["text"]:
                    p["text"] = new
                    changed += 1
            after_ok, after_tot = pair_match_rate(doc["prompts"])
            total_changed += changed
            total_skipped += len(skipped)
            pct_b = 100 * before_ok / before_tot if before_tot else 0
            pct_a = 100 * after_ok / after_tot if after_tot else 0
            print(f"  {path.name}: {changed} prompts re-templated | "
                  f"A/B pairs matching {pct_b:.1f}% -> {pct_a:.1f}%"
                  + (f" | SKIPPED {len(skipped)}" if skipped else ""))
            for sid in skipped[:5]:
                print(f"      skipped (ambiguous split): {sid}")

            if not args.dry_run and changed:
                if not args.no_backup:
                    bak = path.with_suffix(path.suffix + ".pre_template_fix")
                    if not bak.exists():
                        shutil.copy2(path, bak)
                path.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                                encoding="utf-8")

    print(f"\n{'would re-template' if args.dry_run else 're-templated'} "
          f"{total_changed} prompts; {total_skipped} skipped as ambiguous")

    # --- keep the side-by-side review sheets in step -------------------------
    if not args.dry_run:
        for review in PROMPTS.glob("canonical_review*.csv"):
            rows = list(csv.DictReader(review.open(encoding="utf-8")))
            if not rows:
                continue
            text_by_id: dict[str, dict[str, str]] = defaultdict(dict)
            for lang, files in loaded.items():
                for _, doc in files:
                    for p in doc["prompts"]:
                        if is_boundary(p):
                            text_by_id[p["id"]][f"text_{lang}"] = p["text"]
            n = 0
            for row in rows:
                upd = text_by_id.get(row.get("id"))
                if not upd:
                    continue
                for col, val in upd.items():
                    if col in row and row[col] != val:
                        row[col] = val
                        n += 1
            if n:
                if not args.no_backup:
                    bak = review.with_suffix(review.suffix + ".pre_template_fix")
                    if not bak.exists():
                        shutil.copy2(review, bak)
                with review.open("w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    w.writeheader()
                    w.writerows(rows)
                print(f"  updated {review.name} ({n} cells)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
