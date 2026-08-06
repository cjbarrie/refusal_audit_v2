"""What annotation work is outstanding, without calling the judge.

Usage: check_pending.py [run_dir]        default: annotations/full_v1

Replicates the resume computation in annotation_pipeline.py exactly -- same
key, same clean-row definition -- so the TODO printed here is the number that
run would attempt. Costs nothing.
"""
import json, os, sys, glob, collections

run = sys.argv[1] if len(sys.argv) > 1 else "annotations/full_v1"
tot = 0
print(f"run dir: {run}\n")
print(f"{'lang':5s} {'responses':>10s} {'annotated':>10s} {'TO ANNOTATE':>12s}   by model")
print("-" * 78)
for rp in sorted(glob.glob(os.path.join(run, "responses", "*.jsonl"))):
    lang = os.path.basename(rp).rsplit("_", 1)[-1].replace(".jsonl", "")
    ap = os.path.join(run, "ann", os.path.basename(rp))
    valid = [r for r in map(json.loads, (l for l in open(rp) if l.strip()))
             if r.get("response_text")]
    clean = set()
    if os.path.exists(ap):
        latest = {}
        for l in open(ap):
            if not l.strip():
                continue
            r = json.loads(l)
            latest[(r.get("prompt_id"), r.get("prompt_language"), r.get("model"))] = r
        clean = {k for k, r in latest.items()
                 if r.get("engagement_code") is not None and not r.get("error")}
    todo = [r for r in valid
            if (r["prompt_id"], r.get("prompt_language", "en"), r["model"]) not in clean]
    tot += len(todo)
    by = collections.Counter(r["model"] for r in todo)
    top = "  ".join(f"{m}:{n}" for m, n in by.most_common(4)) if by else "-"
    print(f"{lang:5s} {len(valid):10d} {len(clean):10d} {len(todo):12d}   {top}")
print("-" * 78)
print(f"TOTAL OUTSTANDING: {tot}    (~${tot * 0.00012:.2f} in judge calls)")
