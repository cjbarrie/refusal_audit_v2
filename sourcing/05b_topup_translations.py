#!/usr/bin/env python3
"""
Stage 5b — top up missing (blank) translations in a per-language battery.

Stage 5 (05_translate_review.py) translates the whole battery in batches. If a
single batch returns malformed JSON and its per-prompt fallback also fails, a
handful of prompts can land with an empty `text`. Re-running Stage 5 re-translates
all 1548 prompts (~16 min) and may corrupt a *different* batch. This script instead
finds only the blank cells in an existing prompts/<battery>_<lang>.json and
re-translates them ONE PROMPT PER CALL (no batch JSON to corrupt), then patches:

  * prompts/<battery>_<lang>.json          (the `text` field of each fixed prompt)
  * prompts/canonical_review_all_languages.csv  (the text_<lang> column, if present)

Idempotent: prompts that already have a non-empty translation are skipped, so it is
safe to run repeatedly until `remaining blank: 0`.

Reuses the exact SYS prompt, user-message builder, JSON parser, and client() from
05_translate_review.py (imported via importlib, since the module name starts with a
digit) so there is no prompt/parse drift from the main translator.

Needs OPENROUTER_API_KEY in the environment (read from env / repo .env; never written
to disk or any artifact).

Examples:
  python 05b_topup_translations.py --lang hi
  python 05b_topup_translations.py --lang hi --battery full_prompts
  python 05b_topup_translations.py --lang ru --battery temporal_prompts
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PROMPTS = REPO / "prompts"

# Reuse the main translator's machinery verbatim (module name starts with a digit,
# so it cannot be imported with a plain `import` statement).
sys.path.insert(0, str(HERE))
_t = importlib.import_module("05_translate_review")


def _is_blank(v) -> bool:
    return not (str(v or "").strip())


def translate_one(cl, model: str, lang_name: str, rec: dict) -> str:
    """Translate a single prompt, retrying a couple of times. Returns '' on failure."""
    for attempt in range(3):
        try:
            resp = cl.chat.completions.create(
                model=model, temperature=0, max_tokens=1500,
                messages=[
                    {"role": "system", "content": _t.SYS},
                    {"role": "user", "content": _t.build_user_msg(lang_name, [rec])},
                ],
            )
            out = _t.parse_json_obj(resp.choices[0].message.content)
            val = str(out.get(rec["id"], "")).strip()
            if val:
                return val
        except Exception as e:
            if attempt < 2:
                time.sleep(1.5)
            else:
                print(f"    ! {rec['id']}: {type(e).__name__}: {' '.join(str(e).split())[:160]}")
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, help="target language code, e.g. hi")
    ap.add_argument("--battery", default="full_prompts",
                    help="battery stem (full_prompts | temporal_prompts)")
    ap.add_argument("--model", default="anthropic/claude-sonnet-5")
    ap.add_argument("--review-out", default=str(PROMPTS / "canonical_review_all_languages.csv"))
    args = ap.parse_args()

    if args.lang not in _t.LANG_NAMES:
        sys.exit(f"unknown language '{args.lang}'; known: {sorted(_t.LANG_NAMES)}")
    lang_name = _t.LANG_NAMES[args.lang]

    path = PROMPTS / f"{args.battery}_{args.lang}.json"
    if not path.exists():
        sys.exit(f"no such per-language battery: {path}")
    battery = json.load(open(path, encoding="utf-8"))
    prompts = battery["prompts"]

    blanks = [p for p in prompts if _is_blank(p.get("text"))]
    print(f"[{args.lang}] {path.name}: {len(prompts)} prompts, {len(blanks)} blank")
    if not blanks:
        print("nothing to do.")
        return 0

    cl = _t.client()
    fixed: dict[str, str] = {}
    for i, p in enumerate(blanks, 1):
        # translate the ENGLISH source text; per-language records keep it in
        # text_en_source, but fall back to text if that key is absent.
        src = p.get("text_en_source") or p.get("text") or ""
        rec = {"id": p["id"], "text": src}
        val = translate_one(cl, args.model, lang_name, rec)
        if val:
            p["text"] = val
            fixed[p["id"]] = val
        print(f"  [{args.lang}] {i}/{len(blanks)}  {p['id']}  {'OK' if val else 'STILL BLANK'}")

    # Patch the per-language battery in place.
    json.dump(battery, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    remaining = sum(1 for p in prompts if _is_blank(p.get("text")))
    print(f"[{args.lang}] wrote -> {path} | fixed: {len(fixed)} | remaining blank: {remaining}")

    # Patch the review CSV's text_<lang> column for the fixed ids, if the sheet exists.
    review_path = Path(args.review_out)
    col = f"text_{args.lang}"
    if fixed and review_path.exists():
        with open(review_path, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            cols = rd.fieldnames or []
            rows = list(rd)
        if col in cols:
            patched = 0
            for r in rows:
                if r["id"] in fixed:
                    r[col] = fixed[r["id"]]
                    patched += 1
            with open(review_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                w.writerows(rows)
            print(f"[{args.lang}] patched review sheet -> {review_path} ({patched} rows, col {col})")
        else:
            print(f"[{args.lang}] review sheet has no column {col}; skipped CSV patch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
