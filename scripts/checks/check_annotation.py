"""Gate check for an annotation run.

Usage: check_annotation.py [run_dir_or_jsonl]     default: annotations/smoke

Mirrors what run_pilot's assemble stage does before reporting, so the numbers
here are the numbers that reach R. Annotation files are append-mode and
resume-safe: a transient judge failure leaves an error row, and a later retry
appends a clean row under the SAME (prompt_id, prompt_language, model) key.
Assemble collapses those last-wins and drops any remaining error rows
(run_pilot.py), and 01_data_loading.R independently filters is.na(engagement_code).
Counting raw lines instead would report every healed row as a defect.
"""
import json, collections, sys, glob, os

arg = sys.argv[1] if len(sys.argv) > 1 else "annotations/smoke"
paths = [arg] if arg.endswith(".jsonl") else sorted(
    glob.glob(os.path.join(arg, "ann", "*.jsonl")))
if not paths:
    sys.exit("no .jsonl found under %s" % arg)
print("reading:", ", ".join(os.path.basename(x) for x in paths), "\n")

raw = [json.loads(l) for p in paths for l in open(p) if l.strip()]

# Collapse last-wins on the resume key, exactly as assemble does.
latest = {}
for r in raw:
    latest[(r.get("prompt_id"), r.get("prompt_language"), r.get("model"))] = r
rows = [r for r in latest.values() if not r.get("error")]
unhealed = [r for r in latest.values() if r.get("error")]

print(f"raw lines            : {len(raw)}")
print(f"unique keys          : {len(latest)}   ({len(raw)-len(latest)} superseded by a retry)")
print(f"clean annotations    : {len(rows)}")
print(f"UNHEALED errors      : {len(unhealed)}   <-- rerun with --resume to retry these")
if unhealed:
    by_model = collections.Counter(r.get("model") for r in unhealed)
    print("   by model:", dict(by_model.most_common(5)))
    print("   example :", (unhealed[0].get("error") or "")[:200])
print()

if not rows:
    sys.exit("no clean annotations to check")

bad = [r for r in rows
       if not isinstance(r.get("engagement_code"), int)
       or isinstance(r.get("engagement_code"), bool)
       or not 1 <= r["engagement_code"] <= 5]
print(f"engagement_code invalid : {len(bad)}   <-- MUST be 0")

dist = collections.Counter(r.get("engagement_code") for r in rows)
print("engagement distribution :", dict(sorted(dist.items(), key=lambda kv: str(kv[0]))))
print("refusal_justification   :",
      dict(collections.Counter(r.get("refusal_justification") for r in rows)))

# A justification should appear only on codes >=3, and always on 4/5.
odd = [r for r in rows
       if (r.get("engagement_code", 0) <= 2) != (r.get("refusal_justification") is None)]
print(f"justification/code mismatch : {len(odd)}   (set on code<=2, or absent on code>=3)")

mism = [r for r in rows
        if r.get("response_language") not in (None, r.get("prompt_language"))]
print(f"response/prompt lang mismatch : {len(mism)}")
for m, n in collections.Counter(
        (r.get("prompt_language"), r.get("response_language")) for r in mism).most_common(5):
    print(f"    prompt={m[0]} -> detected={m[1]}: {n}")

print("per-language clean counts :",
      dict(collections.Counter(r.get("prompt_language") for r in rows)))
print("per-model clean counts    :",
      len(collections.Counter(r.get("model") for r in rows)), "models")

missing = [f for f in ("prompt_id", "prompt_language", "model", "prompt_category",
                       "engagement_code") if f not in rows[0]]
print("missing contract fields :", missing or "none")
