#!/usr/bin/env python3
"""Embed the English study prompts once, and cache the result.

WHY THIS IS NOT PART OF THE RELEASE. It calls an API, and `make_release.R`
must never spend money: a release has to be reproducible from a clean checkout
by anyone, and an API call is neither free nor deterministic. This is a one-off
cache step, in the same class as generation and annotation. `16_prompt_umap.R`
reads the cache and SKIPS cleanly if it is absent, so the release still builds
on a machine that has never run this.

WHAT IS EMBEDDED. The English prompt text, which is the canonical statement of
what the prompt MEANS. Not the model's response -- concatenating responses would
make the map a picture of what models said, and the question here is which
regions of prompt space attract refusal.

BOILERPLATE IS STRIPPED. Every one of the 1,248 boundary prompts opens with the
identical directive "Write a persuasive argument defending the following
position:". Left in, those eight words are the strongest shared signal in half
the corpus, and the map separates boundary from regular prompts on template
wording rather than on subject matter -- a figure about the prompt generator,
not about the issues. The prefix is removed and its removal is recorded.

DUPLICATES are embedded once and the vector reused, with the duplicate count
carried into the output so a reader can see how much of the cloud is distinct.

Writes:
  data/prompt_embeddings_en.csv.gz    prompt_id + e000..eNNN
  data/prompt_embeddings_en.json      provenance: model, dims, preprocessing,
                                      hashes, token usage, cost

Usage (from the repository root):
  python scripts/embed_prompts.py --dry-run     # cost estimate, no spend
  python scripts/embed_prompts.py
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_utils import load_env_from_file  # noqa: E402

ENDPOINT = "https://openrouter.ai/api/v1/embeddings"
DEFAULT_MODEL = "openai/text-embedding-3-small"
# 512 of the model's 1,536 dimensions. text-embedding-3-small is trained with
# Matryoshka representation learning, so a truncated prefix is a valid embedding
# rather than an arbitrary projection, and 512 keeps the artefact a 3 MB file
# instead of a 15 MB one. The choice is recorded in the sidecar.
DEFAULT_DIMS = 512
BOILERPLATE = re.compile(
    r"^\s*Write a persuasive argument defending the following position:\s*",
    re.IGNORECASE)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def normalise(text: str) -> tuple[str, bool]:
    """Strip the boundary directive and collapse whitespace."""
    stripped = BOILERPLATE.sub("", text)
    had = stripped != text
    return re.sub(r"\s+", " ", stripped).strip(), had


def embed_batch(texts, model, dims, key, retries=5):
    payload = {"model": model, "input": texts}
    if dims:
        payload["dimensions"] = dims
    body = json.dumps(payload).encode()
    for attempt in range(retries):
        req = urllib.request.Request(
            ENDPOINT, data=body,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
            # The API does not promise input order; index is authoritative.
            rows = sorted(d["data"], key=lambda z: z["index"])
            return [z["embedding"] for z in rows], d.get("usage", {})
        except urllib.error.HTTPError as e:
            if e.code in (408, 429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = 2 ** attempt
                print(f"    HTTP {e.code}; retrying in {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts",
                    default="prompts/sampled/rebalanced_prompts_en_sample.json")
    ap.add_argument("--out", default="data/prompt_embeddings_en.csv.gz")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--dimensions", type=int, default=DEFAULT_DIMS)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be sent and exit without spending")
    args = ap.parse_args()

    src = Path(args.prompts)
    doc = json.loads(src.read_text())
    rows = doc["prompts"] if isinstance(doc, dict) else doc
    if doc.get("language") not in (None, "en"):
        print(f"ERROR: {src} is language {doc.get('language')!r}, expected en")
        return 2

    recs = []
    for r in rows:
        txt, had = normalise(r["text"])
        recs.append({"prompt_id": r["id"], "issue_id": r["issue_id"],
                     "tier": r["controversy_tier"],
                     "topic_domain": r["topic_domain"],
                     "region_focus": r["region_focus"],
                     "text": txt, "boilerplate_stripped": had})
    print(f"prompts: {len(recs):,} from {src}")
    print(f"  boilerplate stripped on {sum(r['boilerplate_stripped'] for r in recs):,}")

    # Embed each distinct text once.
    uniq: dict[str, int] = {}
    for r in recs:
        uniq.setdefault(r["text"], 0)
        uniq[r["text"]] += 1
    texts = list(uniq)
    dup = sum(v - 1 for v in uniq.values())
    print(f"  distinct texts: {len(texts):,}  (duplicate prompts: {dup:,})")
    approx_tokens = sum(len(t) // 4 + 1 for t in texts)
    print(f"  approx tokens: {approx_tokens:,}")

    if args.dry_run:
        print(f"DRY RUN: would send {len(texts):,} texts in "
              f"{(len(texts) + args.batch - 1) // args.batch} batches "
              f"to {args.model} at {args.dimensions} dims. No spend.")
        return 0

    load_env_from_file()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("ERROR: OPENROUTER_API_KEY not set")
        return 2

    vecs: dict[str, list[float]] = {}
    tok = 0
    cost = 0.0
    t0 = time.time()
    for i in range(0, len(texts), args.batch):
        chunk = texts[i:i + args.batch]
        out, usage = embed_batch(chunk, args.model, args.dimensions, key)
        if len(out) != len(chunk):
            print(f"ERROR: asked for {len(chunk)} vectors, got {len(out)}")
            return 3
        for t, v in zip(chunk, out):
            vecs[t] = v
        tok += usage.get("total_tokens", 0) or 0
        cost += usage.get("cost", 0.0) or 0.0
        print(f"  {min(i + args.batch, len(texts)):>5,}/{len(texts):,}"
              f"  ({time.time() - t0:5.1f}s)", flush=True)

    dims = len(next(iter(vecs.values())))
    if any(len(v) != dims for v in vecs.values()):
        print("ERROR: ragged embedding dimensions")
        return 3
    print(f"  embedded: {len(vecs):,} x {dims}   tokens {tok:,}   cost ${cost:.4f}")

    out_p = Path(args.out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    cols = [f"e{j:04d}" for j in range(dims)]
    with gzip.open(out_p, "wt", newline="") as fh:
        fh.write("prompt_id," + ",".join(cols) + "\n")
        for r in recs:
            v = vecs[r["text"]]
            fh.write(r["prompt_id"] + "," + ",".join(f"{x:.6g}" for x in v) + "\n")

    meta = {
        "embedding_model": args.model,
        "requested_dimensions": args.dimensions,
        "actual_dimensions": dims,
        "dimension_note": ("text-embedding-3-small is Matryoshka-trained, so a "
                           "truncated prefix is a valid embedding, not an "
                           "arbitrary projection"),
        "endpoint": ENDPOINT,
        "text_field": "text (English prompt as delivered to the models)",
        "preprocessing": [
            "strip the boundary directive prefix "
            "'Write a persuasive argument defending the following position:'",
            "collapse all whitespace runs to a single space",
            "trim"],
        "normalization": "server-side L2 normalisation by the embedding model",
        "n_prompts": len(recs),
        "n_distinct_texts": len(texts),
        "n_duplicate_prompts": dup,
        "duplicate_handling": "embed each distinct text once, reuse the vector",
        "boilerplate_stripped_count": sum(r["boilerplate_stripped"] for r in recs),
        "total_tokens": tok,
        "cost_usd": round(cost, 6),
        "batch_size": args.batch,
        "deterministic": ("the embedding endpoint is not guaranteed "
                          "bit-reproducible; the cached file is the artefact of "
                          "record and its hash is in the release manifest"),
        "source_prompts": str(src),
        "source_sha256": sha256_file(src),
        "output": str(out_p),
        "output_sha256": sha256_file(out_p),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    meta_p = out_p.with_suffix("").with_suffix(".json")
    meta_p.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {out_p} ({out_p.stat().st_size / 1e6:.1f} MB)")
    print(f"wrote {meta_p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
