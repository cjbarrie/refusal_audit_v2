"""
Study A: Jurisdiction-panel generalization.

Runs the frozen 30-prompt subset (data/study_a_prompt_subset.csv) against a
panel of 12 models spanning US / China / EU / Middle East developer
jurisdictions, in en / zh / ar. Emits responses/responses_study_a.jsonl ready
for annotation_pipeline.py.

Design:
  * Prompts: 30 from data/study_a_prompt_subset.csv (prompt_ids frozen).
  * Languages: en, zh, ar (primary). Prompt text for each language is pulled
    from the existing prompts/test_prompts_{lang}.json files so translations
    match the main dataset one-to-one.
  * Models: MODEL_PANEL below. Add or remove entries to adjust the panel.
  * Temperature: 1.0 to match the main dataset's generation conventions
    (see scripts/generate_responses.py).
  * Resumable: already-generated (prompt_id, language, model) tuples are
    skipped on subsequent runs.

Baseline cost estimate: 30 prompts x 12 models x 3 languages = 1,080
generations. At ~2K input + ~500 output tokens per call, midrange model
pricing yields ~$20-30 generation + ~$5 annotation.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from openai import OpenAI

from env_utils import load_env_from_file


REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_SUBSET_CSV = REPO_ROOT / "data" / "study_a_prompt_subset.csv"
DEFAULT_OUTPUT = REPO_ROOT / "responses" / "responses_study_a.jsonl"


# Jurisdiction x model panel. Each entry is (display_name, openrouter_id).
# The analysis script groups by jurisdiction via this dict's top-level keys.
#
# Middle East intentionally omitted: verified in Nov 2026 that OpenRouter does
# not serve Jais or Falcon (the plan's primary + backup options). Dropping ME
# from the panel is acknowledged in the Discussion as an access limitation
# rather than a design choice.
MODEL_PANEL: dict[str, list[tuple[str, str]]] = {
    "us": [
        ("gpt-5.1", "openai/gpt-5.1"),
        ("claude-opus-4.5", "anthropic/claude-opus-4.5"),
        ("gpt-4o", "openai/gpt-4o"),
        ("gemini-2.5-pro", "google/gemini-2.5-pro"),
        ("llama-4-maverick", "meta-llama/llama-4-maverick"),
    ],
    "china": [
        ("deepseek-chat-v3.1", "deepseek/deepseek-chat-v3.1"),
        ("qwen3-235b", "qwen/qwen3-235b-a22b-2507"),
        ("glm-4.6", "z-ai/glm-4.6"),
        ("kimi-k2", "moonshotai/kimi-k2"),
    ],
    "eu": [
        ("mistral-large", "mistralai/mistral-large-2411"),
        ("mixtral-8x22b", "mistralai/mixtral-8x22b-instruct"),
    ],
}

LANGUAGES = ["en", "zh", "ar"]


def load_prompts_from_subset_csv(path: Path = PROMPT_SUBSET_CSV) -> list[dict]:
    """Load a frozen prompt subset. Returns list of dicts with prompt_id, prompt_category."""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def load_prompt_text_by_language(prompt_ids: Iterable[str], language: str) -> dict[str, str]:
    """
    For a given language, read prompts/test_prompts_{language}.json and return
    {prompt_id: prompt_text} restricted to the requested prompt_ids. Raises
    if any prompt_id is not found.
    """
    path = REPO_ROOT / "prompts" / f"test_prompts_{language}.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    text_by_id = {p["id"]: p["text"] for p in data["prompts"]}
    wanted = list(prompt_ids)
    missing = [pid for pid in wanted if pid not in text_by_id]
    if missing:
        raise KeyError(
            f"{len(missing)} prompt IDs missing from {path}: {missing[:5]}..."
        )
    return {pid: text_by_id[pid] for pid in wanted}


def load_existing_keys(output_path: Path) -> set[tuple[str, str, str]]:
    """
    Return the set of (prompt_id, prompt_language, model) keys already present
    in the output JSONL. Used to resume runs without re-generating.
    """
    keys: set[tuple[str, str, str]] = set()
    if not output_path.exists():
        return keys
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("response_text") is None:
                # Error records are retried on resume.
                continue
            keys.add((rec["prompt_id"], rec["prompt_language"], rec["model"]))
    return keys


@dataclass
class GenerationJob:
    prompt_id: str
    prompt_category: str
    prompt_text: str
    prompt_language: str
    model_name: str
    model_id: str
    jurisdiction: str


def build_jobs(
    prompts: list[dict],
    languages: list[str],
    model_panel: dict[str, list[tuple[str, str]]],
) -> list[GenerationJob]:
    jobs: list[GenerationJob] = []
    for language in languages:
        text_by_id = load_prompt_text_by_language((p["prompt_id"] for p in prompts), language)
        for prompt in prompts:
            pid = prompt["prompt_id"]
            for jurisdiction, models in model_panel.items():
                for model_name, model_id in models:
                    jobs.append(
                        GenerationJob(
                            prompt_id=pid,
                            prompt_category=prompt["prompt_category"],
                            prompt_text=text_by_id[pid],
                            prompt_language=language,
                            model_name=model_name,
                            model_id=model_id,
                            jurisdiction=jurisdiction,
                        )
                    )
    return jobs


def generate_one(client: OpenAI, job: GenerationJob, temperature: float) -> str:
    response = client.chat.completions.create(
        model=job.model_id,
        messages=[{"role": "user", "content": job.prompt_text}],
        temperature=temperature,
    )
    # Some providers (e.g. GLM-4.6) return None content instead of an empty
    # string on silent refusals. Treat that as an empty response rather than
    # letting `len(None)` bubble up as a generation error.
    return response.choices[0].message.content or ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Study A: jurisdiction-panel generation")
    parser.add_argument(
        "--subset",
        default=str(PROMPT_SUBSET_CSV),
        help="Path to the frozen prompt-subset CSV",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSONL path",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        help="Sampling temperature (default 1.0 to match main dataset)",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=LANGUAGES,
        help="Languages to run (default: en zh ar)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of (prompt x model x lang) jobs (smoke testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the job plan without calling the API",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    subset_path = Path(args.subset)
    prompts = load_prompts_from_subset_csv(subset_path)
    print(f"Loaded {len(prompts)} prompts from {subset_path.name}")

    jobs = build_jobs(prompts, args.languages, MODEL_PANEL)
    print(
        f"Planned {len(jobs)} generations "
        f"({len(prompts)} prompts x {sum(len(v) for v in MODEL_PANEL.values())} "
        f"models x {len(args.languages)} languages)"
    )

    if args.limit:
        jobs = jobs[: args.limit]
        print(f"  --limit: truncating to {len(jobs)} jobs")

    existing_keys = load_existing_keys(output_path)
    jobs_to_run = [
        j for j in jobs if (j.prompt_id, j.prompt_language, j.model_name) not in existing_keys
    ]
    print(f"Already generated: {len(existing_keys)}. Remaining: {len(jobs_to_run)}.")

    if args.dry_run:
        print("\nDry run. Model x jurisdiction breakdown of remaining jobs:")
        from collections import Counter

        by_jurisdiction = Counter((j.jurisdiction, j.model_name) for j in jobs_to_run)
        for (jur, model), n in sorted(by_jurisdiction.items()):
            print(f"  {jur:<12} {model:<22} {n:4d}")
        return

    load_env_from_file()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    errors = 0
    with open(output_path, "a", encoding="utf-8") as f:
        for i, job in enumerate(jobs_to_run, start=1):
            print(
                f"[{i}/{len(jobs_to_run)}] {job.prompt_language}/{job.prompt_id} + {job.model_name}...",
                end=" ",
                flush=True,
            )
            record = {
                "prompt_id": job.prompt_id,
                "prompt_category": job.prompt_category,
                "prompt_text": job.prompt_text,
                "prompt_language": job.prompt_language,
                "model": job.model_name,
                "model_id": job.model_id,
                "jurisdiction": job.jurisdiction,
                "response_text": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            try:
                record["response_text"] = generate_one(client, job, args.temperature)
                print(f"ok ({len(record['response_text'])} chars)")
            except Exception as e:  # noqa: BLE001 — OpenRouter errors vary
                errors += 1
                record["error"] = str(e)
                print(f"ERR: {e}")

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()

    print(f"\nDone. Generated: {len(jobs_to_run) - errors}. Errors: {errors}.")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
