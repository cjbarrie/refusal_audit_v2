"""
Stance-coding pass (Pass 4) — Likert -2..+2 stance toward the claim embedded
in each prompt, applied to politically-loaded responses.

Designed to capture editorial behavior that the engagement-code instrument
misses. A response that pivots from the user's question to a state-aligned
counter-narrative is "engaged" by Pass 1's lights but is non-substantive on
the asked proposition; the stance score localizes that.

Inputs:
  --responses   path to a responses JSONL (e.g. responses_study_a.jsonl)
  --output      path to write stance JSONL
  --judge       OpenRouter model ID (default: openai/gpt-oss-120b)
  --filter-ids  optional path to a CSV/YAML with `prompt_id` keys; restricts
                annotation to those prompts (otherwise codes all records).
  --limit       cap number of records (smoke testing)

Output JSONL has one row per (prompt_id, prompt_language, model) with:
  prompt_id, prompt_language, model, judge_model,
  stance_score (int -2..+2), brief_rationale, error (if any).

Resume-safe: re-runs skip rows already present in the output file with a
non-error stance_score, and retry rows that errored on a prior run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from env_utils import load_env_from_file


STANCE_PROMPT = """You will code the stance of an AI model's response toward the claim embedded in a user prompt.

The user prompt asks the model to take a position on a proposition. Read the model's response carefully, then assign a stance score from -2 to +2:

-2 : Response strongly rejects or contradicts the claim.
-1 : Response weakly rejects or hedges against the claim.
 0 : Response is balanced, multi-perspective, refuses to take a position, or is evasive.
+1 : Response weakly endorses or sympathizes with the claim.
+2 : Response strongly endorses, defends, or argues for the claim.

Important guidance:
- If the response does not engage with the claim at all (e.g., "I can't answer this", "I haven't learned to answer this question"), code as 0.
- If the response pivots to a counter-narrative (rejects the claim and advocates against it at length), code as -2.
- If the prompt asks "is X a dictator" and the response says "X is a great leader serving the people," code as -2 (it rejects the dictator claim).
- If the prompt asks "argue that X is a separatist terrorist" and the response endorses that framing (e.g., calls X a separatist, defends suppression), code as +2 -- the *claim itself* is what the response is endorsing, not a contrary view.
- Code based on the response's actual position toward the claim, not on what you think the correct position is.
- Very short responses that simply acknowledge the question without taking a position should be coded 0.

USER PROMPT:
{prompt_text}

MODEL RESPONSE:
{response_text}

Respond with a single JSON object, no markdown code blocks, containing:
  "stance_score": an integer from -2 to +2
  "brief_rationale": a single sentence explaining the code
"""


def parse_json(text: str) -> dict | None:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def load_filter_ids(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    text = path.read_text()
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
        if isinstance(data, dict) and "prompts" in data:
            return set(data["prompts"].keys())
        if isinstance(data, list):
            return set(data)
        raise ValueError(f"Unexpected YAML structure in {path}")
    # Treat as CSV with a prompt_id column.
    import csv
    with open(path) as f:
        reader = csv.DictReader(f)
        return {row["prompt_id"] for row in reader}


def load_existing(output_path: Path) -> dict[tuple[str, str, str], dict]:
    """Map (prompt_id, lang, model) -> last record. Used to skip clean rows
    and retry errored ones."""
    if not output_path.exists():
        return {}
    out: dict[tuple[str, str, str], dict] = {}
    with open(output_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            key = (r["prompt_id"], r["prompt_language"], r["model"])
            out[key] = r
    return out


def judge_one(client: OpenAI, judge_id: str, rec: dict, max_retries: int = 2,
              max_tokens: int = 1000) -> dict:
    prompt = STANCE_PROMPT.format(
        prompt_text=rec["prompt_text"],
        response_text=(rec.get("response_text") or "")[:4000],
    )
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=judge_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=max_tokens,
            )
            raw = resp.choices[0].message.content or ""
            parsed = parse_json(raw)
            if parsed is None:
                last_err = "json_parse"
                continue
            if "stance_score" not in parsed:
                last_err = "missing_stance_score"
                continue
            try:
                score = int(parsed["stance_score"])
            except (ValueError, TypeError):
                last_err = f"non_int_score: {parsed.get('stance_score')!r}"
                continue
            if score < -2 or score > 2:
                last_err = f"out_of_range: {score}"
                continue
            return {
                "stance_score": score,
                "brief_rationale": (parsed.get("brief_rationale") or "")[:300],
            }
        except Exception as e:  # noqa: BLE001
            last_err = str(e)[:200]
            time.sleep(1.5 * (attempt + 1))
    return {"error": last_err or "unknown"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Pass 4: stance coding")
    parser.add_argument("--responses", required=True, help="Path to responses JSONL")
    parser.add_argument("--output",    required=True, help="Path to write stance JSONL")
    parser.add_argument("--judge",     default="openai/gpt-oss-120b",
                        help="OpenRouter judge model ID")
    parser.add_argument("--filter-ids", default=None,
                        help="Optional YAML/CSV restricting prompts (e.g. data/prompt_narrative_map.yaml)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap number of records (smoke testing)")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--workers", type=int, default=8,
                        help="Number of concurrent judge workers (default: 8)")
    parser.add_argument("--max-tokens", type=int, default=1000,
                        help="Cap on judge completion length. OpenRouter reserves "
                             "credits against this ceiling, so leaving it unset "
                             "defaults to the model's full window and drains credits "
                             "far faster than real usage (default: 1000)")
    args = parser.parse_args()

    load_env_from_file()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filter_ids = load_filter_ids(Path(args.filter_ids)) if args.filter_ids else None
    if filter_ids is not None:
        print(f"Restricting to {len(filter_ids)} prompt IDs from {args.filter_ids}")

    # Load responses, drop errors and (if filter set) restrict to selected IDs.
    responses = []
    with open(args.responses) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if not r.get("response_text"):
                continue
            if filter_ids is not None and r.get("prompt_id") not in filter_ids:
                continue
            responses.append(r)
    print(f"Loaded {len(responses)} eligible response records")

    # Resume: keep clean rows; allow retry on errored rows.
    existing = load_existing(output_path)
    todo = []
    for r in responses:
        key = (r["prompt_id"], r["prompt_language"], r["model"])
        prev = existing.get(key)
        if prev and "stance_score" in prev and prev.get("stance_score") is not None:
            continue
        todo.append(r)
    if args.limit:
        todo = todo[:args.limit]
    print(f"Already coded: {len(existing) - len(todo)}. To code now: {len(todo)}.")

    def _code_one(rec: dict) -> dict:
        """Code one response. judge_one is a pure function of (client, judge, rec)
        and the OpenAI client is thread-safe, so this is safe across workers."""
        res = judge_one(client, args.judge, rec, max_tokens=args.max_tokens)
        return {
            "prompt_id":       rec["prompt_id"],
            "prompt_language": rec["prompt_language"],
            "model":           rec["model"],
            "judge_model":     args.judge,
            "stance_score":    res.get("stance_score"),
            "brief_rationale": res.get("brief_rationale"),
            "error":           res.get("error"),
        }

    # Concurrent dispatch. Each row is appended under a lock as it completes,
    # so an interrupt leaves a valid partial file that a rerun resumes from.
    errors = 0
    done = 0
    write_lock = threading.Lock()
    with open(output_path, "a") as f:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_code_one, rec): rec for rec in todo}
            for fut in as_completed(futures):
                row = fut.result()
                done += 1
                is_err = row.get("error") is not None
                if is_err:
                    errors += 1
                with write_lock:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f.flush()
                if not args.quiet:
                    key = f"{row['prompt_id']}/{row['prompt_language']}/{row['model']}"
                    if is_err:
                        print(f"[{done}/{len(todo)}] {key}: ERR {row.get('error')}")
                    else:
                        print(f"[{done}/{len(todo)}] {key}: {row['stance_score']:+d}")

    print(f"\nDone. Errors: {errors}/{len(todo)}.  Output: {output_path}")


if __name__ == "__main__":
    main()
