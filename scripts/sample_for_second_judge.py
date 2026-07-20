"""
Build a stratified 20% sample of already-annotated records for second-judge
inter-rater reliability (IRR).

The sample stratifies on (prompt_language x prompt_category x model x dataset_type)
so each cell is proportionally represented. We emit a responses JSONL (not
annotations) because annotation_pipeline.py consumes response records and
produces fresh annotations when given a different --judge-model.

Inputs:
  refusal_audit/annotations/annotations_all.jsonl
  refusal_audit/annotations/annotations_{lang}_boundary.jsonl  (5 languages)
  refusal_audit/responses/responses_{lang}.jsonl               (5 languages)
  refusal_audit/prompts/test_prompts_{lang}.json               (for controversy_tier)

Output:
  refusal_audit/responses/responses_second_judge_sample.jsonl

The output preserves whatever fields the original response records had so that
annotation_pipeline.py can ingest it unmodified.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

# Fixed seed for reproducibility.
SEED = 42
# 20% stratified sample per cell.
SAMPLE_FRACTION = 0.20

LANGUAGES = ["en", "zh", "ja", "id", "ar"]

REPO_ROOT = Path(__file__).resolve().parent.parent
ANNOTATIONS_DIR = REPO_ROOT / "annotations"
RESPONSES_DIR = REPO_ROOT / "responses"
PROMPTS_DIR = REPO_ROOT / "prompts"
OUTPUT_PATH = RESPONSES_DIR / "responses_second_judge_sample.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_controversy_tier_map() -> dict[tuple[str, str], str]:
    """
    Build {(prompt_id, prompt_language): controversy_tier} from the prompt
    metadata files. Prompts are parallel across languages with the same IDs.
    """
    tier_map: dict[tuple[str, str], str] = {}
    for lang in LANGUAGES:
        with open(PROMPTS_DIR / f"test_prompts_{lang}.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        for p in data["prompts"]:
            tier_map[(p["id"], lang)] = p["controversy_tier"]
    return tier_map


def dataset_type_from_tier(tier: str) -> str:
    return "boundary" if tier == "boundary_testing" else "base"


def load_all_annotated_keys() -> set[tuple[str, str, str, str]]:
    """
    Return the set of (prompt_id, prompt_language, model, dataset_type) keys
    that have been annotated with the primary (Gemini) judge. We sample from
    this set so the second-judge annotations align one-to-one with the
    existing primary annotations.
    """
    keys: set[tuple[str, str, str, str]] = set()

    regular = load_jsonl(ANNOTATIONS_DIR / "annotations_all.jsonl")
    tier_map = load_controversy_tier_map()

    for rec in regular:
        if rec.get("engagement_code") is None:
            continue
        tier = tier_map.get((rec["prompt_id"], rec["prompt_language"]))
        if tier is None:
            continue
        # annotations_all.jsonl may contain boundary rows per CLAUDE.md notes
        # about mixed content; treat the tier field as authoritative.
        dataset_type = dataset_type_from_tier(tier)
        if dataset_type != "base":
            continue
        keys.add((rec["prompt_id"], rec["prompt_language"], rec["model"], "base"))

    for lang in LANGUAGES:
        boundary_path = ANNOTATIONS_DIR / f"annotations_{lang}_boundary.jsonl"
        if not boundary_path.exists():
            continue
        for rec in load_jsonl(boundary_path):
            if rec.get("engagement_code") is None:
                continue
            tier = tier_map.get((rec["prompt_id"], rec["prompt_language"]))
            if tier != "boundary_testing":
                continue
            keys.add((rec["prompt_id"], rec["prompt_language"], rec["model"], "boundary"))

    return keys


def load_response_index() -> dict[tuple[str, str, str, str], dict]:
    """
    Build {(prompt_id, language, model, dataset_type): response_record}
    from the canonical responses_{lang}.jsonl files.
    """
    tier_map = load_controversy_tier_map()
    index: dict[tuple[str, str, str, str], dict] = {}
    for lang in LANGUAGES:
        path = RESPONSES_DIR / f"responses_{lang}.jsonl"
        for rec in load_jsonl(path):
            tier = tier_map.get((rec["prompt_id"], rec["prompt_language"]))
            if tier is None:
                continue
            dataset_type = dataset_type_from_tier(tier)
            key = (rec["prompt_id"], rec["prompt_language"], rec["model"], dataset_type)
            index[key] = rec
    return index


def stratified_sample(
    keys: set[tuple[str, str, str, str]],
    fraction: float,
    seed: int,
) -> list[tuple[str, str, str, str]]:
    """
    Stratify by (prompt_language x prompt_category_inferred-via-prompt_id x model
    x dataset_type). prompt_id encodes the category as a prefix (e.g., "strategy_12"
    -> category "strategic_advice"); we use a conservative prefix-to-category map
    rather than re-joining prompt metadata, since we only need a stratification key.
    """
    prefix_to_category = {
        "candidate": "candidate_comparison",
        "domestic": "domestic_government",
        "factual": "factual_opinion",
        "image_gen": "image_generation",
        "moral": "moral_dilemma",
        "policy": "policy_tradeoff",
        "strategy": "strategic_advice",
        "trust": "participation_trust",
    }

    def category_of(prompt_id: str) -> str:
        for prefix, cat in prefix_to_category.items():
            if prompt_id.startswith(prefix + "_"):
                return cat
        return "unknown"

    buckets: dict[tuple[str, str, str, str], list] = defaultdict(list)
    for key in keys:
        prompt_id, lang, model, tier = key
        stratum = (lang, category_of(prompt_id), model, tier)
        buckets[stratum].append(key)

    rng = random.Random(seed)
    sampled: list[tuple[str, str, str, str]] = []
    for stratum, items in sorted(buckets.items()):
        # At least one record per non-empty stratum; round to nearest proportional.
        take = max(1, round(len(items) * fraction))
        sampled.extend(rng.sample(items, k=min(take, len(items))))
    return sampled


def main() -> None:
    print("Loading annotated keys...")
    keys = load_all_annotated_keys()
    print(f"  Annotated records with known controversy tier: {len(keys)}")

    print("\nBuilding response index...")
    response_index = load_response_index()
    print(f"  Response records indexed: {len(response_index)}")

    print(f"\nStratified sampling at {SAMPLE_FRACTION:.0%}...")
    sampled_keys = stratified_sample(keys, SAMPLE_FRACTION, SEED)
    print(f"  Sampled: {len(sampled_keys)} records")

    missing = [k for k in sampled_keys if k not in response_index]
    if missing:
        print(f"  WARNING: {len(missing)} sampled records have no matching response.")
        for k in missing[:10]:
            print(f"    missing: {k}")

    sampled_records = [response_index[k] for k in sampled_keys if k in response_index]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for rec in sampled_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(sampled_records)} records to {OUTPUT_PATH}")

    # Diagnostics: distribution by language, model, dataset_type.
    from collections import Counter

    lang_dist = Counter(r["prompt_language"] for r in sampled_records)
    model_dist = Counter(r["model"] for r in sampled_records)
    print("\nLanguage distribution:")
    for lang, n in sorted(lang_dist.items()):
        print(f"  {lang}: {n}")
    print("\nModel distribution:")
    for model, n in sorted(model_dist.items()):
        print(f"  {model}: {n}")


if __name__ == "__main__":
    main()
