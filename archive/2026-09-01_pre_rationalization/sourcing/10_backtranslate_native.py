#!/usr/bin/env python3
"""
Stage 5b — back-translate natively-sourced prompts so the English master is
actually English, and keep the native original as the authoritative text for its
own language.

The problem this fixes
----------------------
Stage 3 formats prompts by asking an LLM to write questions from an article's
lead paragraph. For an issue harvested from a non-English Wikipedia edition that
lead is in the edition's language, so the LLM wrote the questions in that
language too — nothing ever instructed it to answer in English. The rebalance's
Route A (Chinese Wikipedia, the China injection) therefore put 1,215 Chinese
prompts into `rebalanced_prompts_en.json`.

That breaks the study's core contrast two ways: the "English" condition would
serve Chinese text for those issues (so language is no longer the experimental
knob), and every other language was rendered from Chinese rather than from the
shared English pivot.

What this script does
---------------------
1. Finds prompts in the English master whose text is not predominantly Latin
   script, and infers the language they were actually written in.
2. Back-translates them into English through the same Stage-5 translation path
   (same model, same translate-don't-answer system prompt).
3. Rewrites the English master so `text` is English for every prompt, while
   preserving the original in `text_native`.
4. Stamps `prompt_origin_language` on EVERY prompt ("en" for prompts authored in
   English, otherwise the language the text was originally written in). This is
   the column the analysis groups on to test whether natively-sourced prompts
   behave differently from translated-through ones.
5. Writes the native original into that language's own battery file, so the
   Chinese battery carries the real Chinese question rather than a translation
   of a back-translation.

Prompts that merely came from a non-English *edition* but were already written in
English are left alone and keep `prompt_origin_language = "en"` — the route a
prompt came from and the language it was authored in are different facts, and
only the latter is the confound.

`prompt_origin_language` is deliberately distinct from the existing
`source_language` / `source_edition` fields, which record which Wikipedia
edition flagged the issue.

Downstream: rows whose English changed must be re-translated into the remaining
languages from the corrected pivot. The script writes that id list to
`data/backtranslate_redo_ids.json`, which Stage 11
(`11_retranslate_affected.py`) consumes.

Needs OPENROUTER_API_KEY (read from env only; never written to any artifact).

Usage:
    python 10_backtranslate_native.py --dry-run     # what would change, no spend
    python 10_backtranslate_native.py               # back-translate + rewrite
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"
PROMPTS = REPO / "prompts"

# Reuse Stage 5's translation machinery so there is exactly one translation path.
# Loaded lazily: Stage 5 imports `openai`, which --dry-run has no need of, and
# requiring it would stop anyone from inspecting the plan on a machine without
# the runtime env installed.
_T05 = None
_T05_ERR: Exception | None = None


def t05():
    global _T05, _T05_ERR
    if _T05 is None:
        if _T05_ERR is not None:
            raise SystemExit(
                f"cannot load 05_translate_review.py ({_T05_ERR}). Its `openai` "
                f"dependency is needed to translate; activate the refusal-v2 env."
            )
        try:
            spec = importlib.util.spec_from_file_location(
                "translate05", HERE / "05_translate_review.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _T05 = mod
        except Exception as e:  # noqa: BLE001
            _T05_ERR = e
            return t05()
    return _T05


# Target-language display names, kept here so detection and validation work
# without loading the translator. Verified against Stage 5's LANG_NAMES at run
# time, so the two can never silently drift apart.
LANG_NAMES = {
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "id": "Indonesian",
    "ar": "Arabic",
    "ru": "Russian",
    "hi": "Hindi",
}

# Unicode ranges that identify the script a prompt was written in. Only the
# study languages plus the editions editions.yaml can harvest are covered; a
# prompt in an unlisted script is reported rather than silently mislabelled.
SCRIPT_RANGES: list[tuple[str, list[tuple[int, int]]]] = [
    ("zh", [(0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0xF900, 0xFAFF)]),  # Han
    ("ja", [(0x3040, 0x309F), (0x30A0, 0x30FF)]),                    # kana (Han alone -> zh)
    ("ar", [(0x0600, 0x06FF), (0x0750, 0x077F)]),
    ("ru", [(0x0400, 0x04FF)]),
    ("hi", [(0x0900, 0x097F)]),
]


def _template_prefix_len(text: str) -> int:
    """Length of a leading pure-ASCII template prefix ending in ': ', else 0.

    Boundary prompts are built as
    "Write a persuasive argument defending the following position: <stance>",
    and for a natively-sourced issue only the <stance> is native — Stage 3
    applies the English template regardless of the source edition.
    """
    cut = text.find(": ")
    if cut > 0 and text[:cut].isascii() and len(text) - cut > 2:
        return cut + 2
    return 0


def is_fully_native(text: str) -> bool:
    """True when the whole prompt is in the native language, not just its stance.

    A boundary prompt with an English template around a Chinese stance is a
    HYBRID: back-translating it yields clean English, but handing the original
    back to the Chinese battery would serve the model a mixed-language prompt.
    Hybrids are therefore translated normally into every language (the stance
    round-trips zh->en->zh, exactly the treatment every other prompt in the
    battery already gets), while fully-native prompts keep their original.
    Either way `prompt_origin_language` records where the content came from,
    which is what the analysis groups on.
    """
    return detect_language(text) is not None and _template_prefix_len(text) == 0


def detect_language(text: str, threshold: float = 0.25) -> str | None:
    """Return the language `text` was written in, or None if it is English.

    Measured as non-Latin script characters per Latin letter, NOT as a fraction
    of all characters. A fraction is diluted by punctuation and whitespace, and
    it cannot separate a prompt written in Chinese from an English prompt that
    quotes a Chinese term — e.g. "What are your views on the appropriateness of
    the term '小三通' …", which is English and must not be back-translated.

    On the real battery the two populations separate cleanly under this measure:
    prompts genuinely written in Chinese score >= 0.38, English prompts quoting
    Chinese terms score <= 0.14. The default sits in that gap. The ratio also
    handles the boundary tier, where a Chinese stance is wrapped in an English
    template ("Write a persuasive argument defending …") and so carries a large
    Latin count despite being natively sourced.

    Japanese is checked first because Japanese text also contains Han
    characters; the presence of kana is what distinguishes it from Chinese.
    """
    if not text:
        return None
    # Boundary prompts wrap the native stance in a fixed English template
    # ("Write a persuasive argument defending the following position: <stance>").
    # Measure the stance, not the template, or a short native stance is diluted
    # below the threshold by the English scaffolding around it. Anything before
    # the first ": " is dropped when that prefix is pure ASCII, which leaves a
    # natively-written prompt untouched (it has no ASCII prefix to strip).
    probe = text[_template_prefix_len(text):]

    latin = sum(1 for ch in probe if ch.isascii() and ch.isalpha())
    counts = {
        lang: sum(1 for ch in probe if any(lo <= ord(ch) <= hi for lo, hi in ranges))
        for lang, ranges in SCRIPT_RANGES
    }
    denom = max(latin, 1)
    if counts.get("ja", 0) / denom > threshold:
        return "ja"
    for lang, _ in SCRIPT_RANGES:
        if lang != "ja" and counts.get(lang, 0) / denom > threshold:
            return lang
    return None


def back_translate(cl, model: str, items: list[dict], src_lang: str,
                   batch_size: int, workers: int) -> dict[str, str]:
    """Translate `items` (id/text dicts) from `src_lang` into English."""
    src_name = LANG_NAMES.get(src_lang, src_lang)
    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
    out: dict[str, str] = {}
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(t05().translate_batch, cl, model, "English", b, src_name)
                for b in batches]
        for i, fut in enumerate(as_completed(futs), 1):
            out.update(fut.result())
            print(f"  [{src_lang}->en] {i}/{len(batches)} batches", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default=str(PROMPTS / "rebalanced_prompts_en.json"))
    ap.add_argument("--languages", nargs="+", default=["zh", "ar", "ru", "hi"],
                    help="battery files to stamp prompt_origin_language onto")
    ap.add_argument("--model", default="anthropic/claude-sonnet-5")
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--redo-out", default=str(DATA / "backtranslate_redo_ids.json"))
    ap.add_argument("--merge-redo", nargs="*", default=[str(DATA / "idfix_redo_ids.json")],
                    help="additional redo worklists to union in (same shape). Defaults to "
                         "the id-migration list, whose rows had their translations "
                         "collapsed by the old ambiguous ids.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    en_path = Path(args.prompts)
    doc = json.loads(en_path.read_text(encoding="utf-8"))
    prompts = doc["prompts"]

    ids = [p["id"] for p in prompts]
    if len(ids) != len(set(ids)):
        sys.exit("ABORT — duplicate prompt ids; run 09_migrate_issue_ids.py first.")

    # --- detect ---------------------------------------------------------------
    native: dict[str, list[dict]] = {}
    for p in prompts:
        lang = detect_language(p.get("text", ""))
        if lang:
            native.setdefault(lang, []).append(p)

    total = sum(len(v) for v in native.values())
    print(f"{len(prompts)} prompts in {en_path.name}")
    if not total:
        print("  no non-English prompts found — nothing to do.")
        return 0
    for lang, ps in sorted(native.items()):
        tiers = {}
        for p in ps:
            tiers[p.get("controversy_tier")] = tiers.get(p.get("controversy_tier"), 0) + 1
        print(f"  {lang}: {len(ps)} prompts written in this language  {tiers}")
    unknown = [l for l in native if l not in LANG_NAMES]
    if unknown:
        sys.exit(f"ABORT — detected script(s) with no translator language name: {unknown}")

    if args.dry_run:
        print(f"\n--dry-run: would back-translate {total} prompts into English "
              f"(~{-(-total // args.batch_size)} batched calls), then rewrite "
              f"{en_path.name} and the native-language batteries. Nothing written.")
        for lang, ps in sorted(native.items()):
            print(f"\n  example [{lang}] {ps[0]['id']}")
            print(f"    {ps[0]['text'][:100]}")
        return 0

    # --- back-translate -------------------------------------------------------
    mod = t05()
    if mod.LANG_NAMES != LANG_NAMES:
        sys.exit("ABORT — LANG_NAMES drifted from 05_translate_review.py; reconcile them.")
    cl = mod.client()
    translations: dict[str, str] = {}
    for lang, ps in sorted(native.items()):
        t0 = time.time()
        got = back_translate(cl, args.model, [{"id": p["id"], "text": p["text"]} for p in ps],
                             lang, args.batch_size, args.workers)
        blank = [i for i in (p["id"] for p in ps) if not got.get(i, "").strip()]
        print(f"[{lang}] back-translated {len(ps)-len(blank)}/{len(ps)} "
              f"in {time.time()-t0:.0f}s", flush=True)
        if mod._FIRST_ERR:
            print(f"[{lang}] FIRST ERROR: {mod._FIRST_ERR[0]}", flush=True)
        if len(blank) >= 0.9 * len(ps):
            sys.exit(f"[{lang}] {len(blank)}/{len(ps)} came back empty — aborting before "
                     f"writing. Cause: {mod._FIRST_ERR[0] if mod._FIRST_ERR else 'unknown'}")
        if blank:
            print(f"[{lang}] WARNING: {len(blank)} blank — their native text is kept "
                  f"in place and they are NOT marked back-translated.")
        translations.update({k: v for k, v in got.items() if v.strip()})

    def backup(p: Path) -> None:
        if not args.no_backup:
            bak = p.with_suffix(p.suffix + ".pre_backtranslate")
            if not bak.exists():
                shutil.copy2(p, bak)

    # --- rewrite the English master ------------------------------------------
    changed: list[str] = []
    origin_by_id: dict[str, str] = {}
    form_by_id: dict[str, str] = {}
    native_by_id: dict[str, str] = {}
    complete_ids: set[str] = set()
    for p in prompts:
        lang = detect_language(p.get("text", ""))
        en = translations.get(p["id"], "")
        if lang and en:
            p["text_native"] = p["text"]
            p["text"] = en
            p["prompt_origin_language"] = lang
            p["prompt_origin_form"] = (
                "native" if is_fully_native(p["text_native"]) else "hybrid")
            native_by_id[p["id"]] = p["text_native"]
            if p["prompt_origin_form"] == "native":
                complete_ids.add(p["id"])
            changed.append(p["id"])
        elif lang:
            # Detected as native but the back-translation came back blank; the
            # native text is left in place and the row is NOT marked changed.
            p.setdefault("prompt_origin_language", lang)
            p.setdefault("prompt_origin_form",
                         "native" if is_fully_native(p["text"]) else "hybrid")
        else:
            p.setdefault("prompt_origin_language", "en")
            p.setdefault("prompt_origin_form", "authored_en")
        origin_by_id[p["id"]] = p["prompt_origin_language"]
        form_by_id[p["id"]] = p["prompt_origin_form"]

    backup(en_path)
    en_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {en_path.name}: {len(changed)} prompts back-translated to English")

    # --- stamp origin onto every language battery; slot natives into their own -
    for lang in args.languages:
        p = en_path.with_name(en_path.name.replace("_en.json", f"_{lang}.json"))
        if not p.exists():
            print(f"  [{lang}] {p.name} not found — skipping")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        n_slot = 0
        for q in d["prompts"]:
            q["prompt_origin_language"] = origin_by_id.get(q["id"], "en")
            q["prompt_origin_form"] = form_by_id.get(q["id"], "authored_en")
            if q["id"] in native_by_id:
                q["text_native"] = native_by_id[q["id"]]
                if q["prompt_origin_form"] == "native" and q["prompt_origin_language"] == lang:
                    q["text"] = native_by_id[q["id"]]   # the real original
                    n_slot += 1
        backup(p)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [{lang}] wrote {p.name}"
              + (f"; {n_slot} native originals restored" if n_slot else ""))

    # --- the re-translation worklist -----------------------------------------
    # Rows whose English pivot changed must be re-rendered into every language
    # OTHER than the one they are native to (that one already holds the original).
    # A row needs re-translating into every language except one it is BOTH
    # native to and complete in — hybrids are re-translated into their own
    # language too, since they are not passed through.
    redo: dict[str, set[str]] = {
        lang: {i for i in changed
               if not (origin_by_id.get(i) == lang and i in complete_ids)}
        for lang in args.languages}

    # Union in other worklists (e.g. rows whose translations were collapsed by
    # the old ambiguous ids — those are unreliable in EVERY language, not just
    # the ones back-translated here).
    for extra in args.merge_redo or []:
        ep = Path(extra)
        if not ep.exists():
            print(f"  merge-redo: {ep.name} not found — skipped")
            continue
        other = json.loads(ep.read_text(encoding="utf-8"))["ids"]
        for lang in redo:
            redo[lang] |= set(other.get(lang, []))
        print(f"  merge-redo: unioned {ep.name}")

    # A blank/missing translation always needs redoing, whatever the cause.
    for lang in redo:
        lp = en_path.with_name(en_path.name.replace("_en.json", f"_{lang}.json"))
        if not lp.exists():
            continue
        blanks = {q["id"] for q in json.loads(lp.read_text(encoding="utf-8"))["prompts"]
                  if not str(q.get("text", "")).strip()}
        if blanks:
            redo[lang] |= blanks
            print(f"  [{lang}] +{len(blanks)} blank translations added to the worklist")

    # Never ask for a re-translation of a row that is served by its own native
    # original — there is nothing to translate.
    redo = {lang: sorted(v - {i for i in complete_ids if origin_by_id.get(i) == lang})
            for lang, v in redo.items()}
    Path(args.redo_out).write_text(
        json.dumps({"source": en_path.name,
                    "reason": "english pivot changed by back-translation",
                    "ids": redo}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {Path(args.redo_out).name}: "
          + ", ".join(f"{l}={len(v)}" for l, v in redo.items()))
    print("Next: python 11_retranslate_affected.py   (re-translates exactly these "
          "ids from the corrected English pivot)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
