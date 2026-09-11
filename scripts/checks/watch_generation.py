#!/usr/bin/env python3
"""Live per-model generation progress: done / target, rate, ETA.

    python scripts/checks/watch_generation.py                  # ru+hi, endpoint models
    python scripts/checks/watch_generation.py --langs ru hi ar --models all
    python scripts/checks/watch_generation.py --once            # single snapshot, no loop

Why this exists rather than `tail -f logs/gen_*.log`: the generator prints one
line per response, so four parallel runs interleave into thousands of lines an
hour and you cannot see a rate or an ETA. This aggregates instead.

Why it is not check_generation.py: that one re-parses every response file on
each call (the run's JSONL are hundreds of MB), which is far too slow to poll.
This scans once at startup to establish a baseline, remembers each file's byte
offset, and thereafter reads ONLY the bytes appended since the last tick. Cost
per refresh is proportional to new work, not to the size of the run.

Counting matches the generator's own resume rule: a row counts as done only if
it has response_text and no error, so rows that errored (a paused endpoint, a
503) show in the err column and stay in the remaining count -- exactly the work
a rerun would pick up.
"""
import argparse
import collections
import json
import os
import sys
import time

DEFAULT_MODELS = ["allam-7b", "jais-8b", "falcon3-10b", "sarvam-30b"]


def target_for(lang):
    """Prompts per language = the size of that language's sampled battery."""
    # The sampled battery is a dict wrapper, not a bare list -- the prompts live
    # under "prompts" (same shape generate_responses.py reads). Taking len() of
    # the wrapper silently yields the key count, which looked like a target of 9.
    p = f"prompts/sampled/rebalanced_prompts_{lang}_sample.json"
    try:
        with open(p) as f:
            d = json.load(f)
        if isinstance(d, dict):
            return d.get("total_prompts") or len(d.get("prompts", []))
        return len(d)
    except Exception:
        return None


def scan(path, offset, ok, err):
    """Fold new bytes at `path` from `offset` into the counters. Returns the new
    offset, stopping at the last complete line so a record half-written at the
    moment we read is picked up whole on the next tick."""
    if not os.path.exists(path):
        return offset
    size = os.path.getsize(path)
    if size <= offset:
        return offset
    with open(path, "rb") as f:
        f.seek(offset)
        buf = f.read(size - offset)
    cut = buf.rfind(b"\n")
    if cut == -1:
        return offset
    for raw in buf[:cut].split(b"\n"):
        if not raw.strip():
            continue
        try:
            r = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            continue
        m = r.get("model")
        if r.get("error") or not r.get("response_text"):
            err[m] += 1
        else:
            ok[m] += 1
    return offset + cut + 1


def fmt_eta(hours):
    if hours is None or hours != hours or hours in (float("inf"),):
        return "  --"
    if hours < 1:
        return f"{hours*60:.0f}m"
    if hours < 48:
        return f"{hours:.1f}h"
    return f"{hours/24:.1f}d"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="annotations/full_v1")
    ap.add_argument("--langs", nargs="+", default=["ru", "hi"])
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS,
                    help='model names, or "all"')
    ap.add_argument("--interval", type=float, default=30.0)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    models = None if args.models == ["all"] else args.models
    paths = {lg: os.path.join(args.run_dir, "responses", f"rebalanced_{lg}.jsonl")
             for lg in args.langs}
    targets = {lg: target_for(lg) for lg in args.langs}

    off = {lg: 0 for lg in args.langs}
    ok = {lg: collections.Counter() for lg in args.langs}
    err = {lg: collections.Counter() for lg in args.langs}

    sys.stderr.write("baseline scan (once; later ticks read only new bytes)...\n")
    for lg in args.langs:
        off[lg] = scan(paths[lg], 0, ok[lg], err[lg])
    start = time.time()
    base = {lg: dict(ok[lg]) for lg in args.langs}
    prev = {lg: dict(ok[lg]) for lg in args.langs}
    prev_t = time.time()

    try:
        while True:
            now = time.time()
            dt = max(now - prev_t, 1e-9)
            rows, tot_rem, tot_rate = [], 0, 0.0
            for lg in args.langs:
                names = models if models else sorted(
                    set(ok[lg]) | set(err[lg]))
                for m in names:
                    tgt = targets[lg]
                    done = ok[lg][m]
                    inst = (done - prev[lg].get(m, 0)) / dt * 3600
                    avg = (done - base[lg].get(m, 0)) / max(now - start, 1e-9) * 3600
                    rem = (tgt - done) if tgt else None
                    eta = (rem / avg) if (rem and avg > 0) else None
                    if rem:
                        tot_rem += rem
                        tot_rate += avg
                    rows.append((lg, m, done, tgt, err[lg][m], inst, avg, eta))
            # Only repaint in place on a real terminal; piped or redirected
            # (into a log, or `| tail`) the escape codes are noise, so there we
            # just append successive snapshots.
            if sys.stdout.isatty():
                sys.stdout.write("\033[H\033[2J")
            print(f"generation watch — {args.run_dir}    "
                  f"{time.strftime('%H:%M:%S')}   "
                  f"elapsed {(now-start)/60:.0f}m   refresh {args.interval:.0f}s")
            print()
            print(f"{'lang':<5}{'model':<15}{'done':>7}{'/target':>8}{'pct':>7}"
                  f"{'err':>7}{'now/hr':>9}{'avg/hr':>9}{'ETA':>7}")
            print("-" * 74)
            for lg, m, done, tgt, e, inst, avg, eta in rows:
                pct = f"{100*done/tgt:.1f}%" if tgt else "  --"
                print(f"{lg:<5}{m:<15}{done:>7}{('/'+str(tgt)) if tgt else '':>8}"
                      f"{pct:>7}{e:>7}{inst:>9.0f}{avg:>9.0f}{fmt_eta(eta):>7}")
            print("-" * 74)
            # Models run in parallel, so the finish time is the slowest model's
            # ETA -- not remaining/combined-rate, which would assume one queue.
            print(f"{'remaining':<20}{tot_rem:>10}   combined {tot_rate:>6.0f}/hr"
                  f"   slowest-model ETA {fmt_eta(max((r[7] for r in rows if r[7]), default=None))}")
            print("\nCtrl-C to stop watching (does not affect the runs).")

            if args.once:
                return
            prev = {lg: dict(ok[lg]) for lg in args.langs}
            prev_t = now
            time.sleep(args.interval)
            for lg in args.langs:
                off[lg] = scan(paths[lg], off[lg], ok[lg], err[lg])
    except KeyboardInterrupt:
        print("\nstopped watching; generation continues.")


if __name__ == "__main__":
    main()
