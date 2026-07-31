import json, collections, sys, glob, os
# Usage: check_generation.py [run_dir_or_jsonl]   default: annotations/smoke
arg = sys.argv[1] if len(sys.argv) > 1 else "annotations/smoke"
if arg.endswith(".jsonl"):
    paths = [arg]
else:
    paths = sorted(glob.glob(os.path.join(arg, "responses", "*.jsonl")))
if not paths:
    sys.exit("no .jsonl found under %s" % arg)
print("reading:", ", ".join(os.path.basename(x) for x in paths), "\n")
rows = [json.loads(l) for p in paths for l in open(p) if l.strip()]
by = collections.defaultdict(list)
for r in rows: by[r.get("model")].append(r)
print(f"{len(rows)} responses, {len(by)} models\n")
print(f"{'model':22s} {'n':>4s} {'empty':>6s} {'err':>4s} {'min':>6s} {'med':>6s}")
for m, rs in sorted(by.items()):
    L = sorted(len((r.get("response_text") or "").strip()) for r in rs)
    print(f"{m:22s} {len(rs):4d} {sum(1 for x in L if x==0):6d} "
          f"{sum(1 for r in rs if r.get('error')):4d} {L[0]:6d} {L[len(L)//2]:6d}")
ROSTER = ["gpt-5.1","claude-opus-4.5","gpt-4o","grok-4.3","deepseek-chat-v3.1",
          "qwen3-max","mistral-large-2512","allam-7b","falcon3-10b","jais-8b","sarvam-30b"]
missing = [m for m in ROSTER if m not in by]
print("\nnot yet seen:", missing or "none - all 11 covered")
