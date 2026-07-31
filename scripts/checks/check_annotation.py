import json, collections
p = "annotations/smoke/ann/rebalanced_en.jsonl"
rows = [json.loads(l) for l in open(p)]
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
