import json, collections, sys, glob, os
# Usage: check_annotation.py [run_dir_or_jsonl]   default: annotations/smoke
arg = sys.argv[1] if len(sys.argv) > 1 else "annotations/smoke"
if arg.endswith(".jsonl"):
    paths = [arg]
else:
    paths = sorted(glob.glob(os.path.join(arg, "ann", "*.jsonl")))
if not paths:
    sys.exit("no .jsonl found under %s" % arg)
print("reading:", ", ".join(os.path.basename(x) for x in paths), "\n")
rows = [json.loads(l) for p in paths for l in open(p) if l.strip()]
print(f"{len(rows)} annotations\n")
bad = [r for r in rows if not isinstance(r.get("engagement_code"), int)
       or isinstance(r.get("engagement_code"), bool)
       or not 1 <= r["engagement_code"] <= 5]
print(f"engagement_code invalid : {len(bad)}   <-- MUST be 0")
dist = collections.Counter(r.get("engagement_code") for r in rows)
print("engagement distribution :", dict(sorted(dist.items(), key=lambda kv: str(kv[0]))))
print("refusal_justification   :",
      dict(collections.Counter(r.get("refusal_justification") for r in rows)))
mism = [r for r in rows if r.get("response_language") not in (None, r.get("prompt_language"))]
print(f"lang mismatch (en run)  : {len(mism)}")
for r in mism[:5]:
    print(f"    {r.get('model'):20s} detected={r.get('response_language')}")
missing = [f for f in ("prompt_id","prompt_language","model","prompt_category",
                       "engagement_code") if f not in rows[0]]
print("missing contract fields :", missing or "none")
