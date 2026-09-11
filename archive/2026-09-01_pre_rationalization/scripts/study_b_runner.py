"""
Study B runner: generates responses for B-refined (entity-swap) and B-orig
(native vs MT) from refusal_audit/data/study_b_variant_pairs.yaml.

Outputs:
  responses/responses_study_b_refined.jsonl
  responses/responses_study_b_orig.jsonl

Annotate afterwards via:
  python scripts/annotation_pipeline.py \
    --responses responses/responses_study_b_refined.jsonl \
    --output annotations/annotations_study_b_refined.jsonl \
    --judge-model google/gemini-2.5-flash-lite
  (similarly for study_b_orig)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from deep_translator import GoogleTranslator
from openai import OpenAI

from env_utils import load_env_from_file


REPO_ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = REPO_ROOT / "data" / "study_b_variant_pairs.yaml"
REFINED_OUT = REPO_ROOT / "responses" / "responses_study_b_refined.jsonl"
ORIG_OUT = REPO_ROOT / "responses" / "responses_study_b_orig.jsonl"


# Treatment + placebo model arms.
MODELS_REFINED = [
    ("deepseek-chat-v3.1", "deepseek/deepseek-chat-v3.1", "china"),
    ("qwen3-235b",         "qwen/qwen3-235b-a22b-2507",   "china"),
    ("glm-4.6",            "z-ai/glm-4.6",                "china"),
    ("gpt-5.1",            "openai/gpt-5.1",              "us"),
]

MODELS_ORIG = [
    ("deepseek-chat-v3.1", "deepseek/deepseek-chat-v3.1", "china"),
    ("qwen3-235b",         "qwen/qwen3-235b-a22b-2507",   "china"),
    ("gpt-5.1",            "openai/gpt-5.1",              "us"),
    ("claude-opus-4.5",    "anthropic/claude-opus-4.5",   "us"),
]

# MT for Study B-orig uses Google Translate via deep-translator (free).
# deep-translator uses Google's public translate endpoint; no API key.
_TRANSLATOR_EN_TO_ZH = GoogleTranslator(source="en", target="zh-CN")
_TRANSLATOR_ZH_TO_EN = GoogleTranslator(source="zh-CN", target="en")


def load_existing_keys(path: Path, key_fields: tuple[str, ...]) -> set[tuple]:
    """Records present (non-error) in an output file, keyed by key_fields."""
    keys: set[tuple] = set()
    if not path.exists():
        return keys
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("response_text") is None:
                continue
            keys.add(tuple(rec[k] for k in key_fields))
    return keys


def generate(client: OpenAI, model_id: str, text: str, temperature: float = 1.0) -> str:
    r = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": text}],
        temperature=temperature,
    )
    # Some providers return message.content = None on refusal/empty output;
    # normalize to an empty string so callers can len() it safely.
    return r.choices[0].message.content or ""


def translate_en_to_zh(text: str) -> str:
    return _TRANSLATOR_EN_TO_ZH.translate(text)


def translate_zh_to_en(text: str) -> str:
    return _TRANSLATOR_ZH_TO_EN.translate(text)


def run_entity_swap(client: OpenAI, variants: list[dict]) -> None:
    REFINED_OUT.parent.mkdir(parents=True, exist_ok=True)
    # Resume-safe key: (pair_id, model, language)
    existing = load_existing_keys(REFINED_OUT, ("pair_id", "model", "prompt_language"))
    total = len(variants) * len(MODELS_REFINED) * 2
    done = 0
    with open(REFINED_OUT, "a", encoding="utf-8") as f:
        for var in variants:
            for model_name, model_id, jurisdiction in MODELS_REFINED:
                for lang, prompt_text in (("en", var["prompt_en"]),
                                           ("zh", var["prompt_zh"])):
                    done += 1
                    key = (var["pair_id"], model_name, lang)
                    if key in existing:
                        continue
                    print(f"[refined {done}/{total}] {var['pair_id']} {lang} {model_name}...",
                          end=" ", flush=True)
                    rec = {
                        "study_arm": "b_refined",
                        "pair_id": var["pair_id"],
                        "template_id": var["template_id"],
                        "entity_type": var["entity_type"],
                        "entity_en": var["entity_en"],
                        "entity_cn": var["entity_cn"],
                        "entity_country": var["country"],
                        "prompt_id": var["pair_id"],      # compat with annotation_pipeline
                        "prompt_category": f"b_refined_{var['entity_type']}_{var['template_id']}",
                        "prompt_text": prompt_text,
                        "prompt_language": lang,
                        "model": model_name,
                        "model_id": model_id,
                        "model_jurisdiction": jurisdiction,
                        "response_text": None,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    try:
                        rec["response_text"] = generate(client, model_id, prompt_text)
                        print(f"ok ({len(rec['response_text'])} chars)")
                    except Exception as e:  # noqa: BLE001
                        rec["error"] = str(e)
                        print(f"ERR: {e}")
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    f.flush()


def run_native_mt(client: OpenAI, pairs: list[dict]) -> None:
    ORIG_OUT.parent.mkdir(parents=True, exist_ok=True)
    # Resume-safe key: (pair_id, model, variant)
    existing = load_existing_keys(ORIG_OUT, ("pair_id", "model", "variant"))
    total = len(pairs) * len(MODELS_ORIG) * 4
    done = 0

    # Translate pairs first (per pair_id, cache MT outputs in-memory).
    # Uses free Google Translate via deep-translator.
    print(f"Translating {len(pairs)} pairs for MT variants (Google Translate)...")
    for i, p in enumerate(pairs, start=1):
        if "mt_zh" not in p:
            p["mt_zh"] = translate_en_to_zh(p["native_en"])
        if "mt_en" not in p:
            p["mt_en"] = translate_zh_to_en(p["native_zh"])
        if i % 5 == 0:
            print(f"  MT {i}/{len(pairs)}")

    with open(ORIG_OUT, "a", encoding="utf-8") as f:
        for p in pairs:
            variants = [
                ("native_en", "en", p["native_en"]),
                ("mt_en",     "en", p["mt_en"]),
                ("native_zh", "zh", p["native_zh"]),
                ("mt_zh",     "zh", p["mt_zh"]),
            ]
            for model_name, model_id, jurisdiction in MODELS_ORIG:
                for variant, lang, text in variants:
                    done += 1
                    key = (p["pair_id"], model_name, variant)
                    if key in existing:
                        continue
                    print(f"[orig {done}/{total}] {p['pair_id']} {variant} {model_name}...",
                          end=" ", flush=True)
                    rec = {
                        "study_arm": "b_orig",
                        "pair_id": p["pair_id"],
                        "variant": variant,
                        "qn_type": p["qn_type"],
                        "entity_country": p["country"],
                        "native_en": p["native_en"],
                        "native_zh": p["native_zh"],
                        "mt_en": p["mt_en"],
                        "mt_zh": p["mt_zh"],
                        "prompt_id": f"{p['pair_id']}_{variant}",  # compat
                        "prompt_category": f"b_orig_{p['qn_type']}",
                        "prompt_text": text,
                        "prompt_language": lang,
                        "model": model_name,
                        "model_id": model_id,
                        "model_jurisdiction": jurisdiction,
                        "response_text": None,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    try:
                        rec["response_text"] = generate(client, model_id, text)
                        print(f"ok ({len(rec['response_text'])} chars)")
                    except Exception as e:  # noqa: BLE001
                        rec["error"] = str(e)
                        print(f"ERR: {e}")
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    f.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["refined", "orig", "both"], default="both")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    variants_refined = data["entity_swap"]
    pairs_orig = data["native_mt"]

    if args.dry_run:
        print(f"B-refined planned: {len(variants_refined)} pairs x "
              f"{len(MODELS_REFINED)} models x 2 languages = "
              f"{len(variants_refined) * len(MODELS_REFINED) * 2}")
        print(f"B-orig planned:    {len(pairs_orig)} pairs x "
              f"{len(MODELS_ORIG)} models x 4 variants = "
              f"{len(pairs_orig) * len(MODELS_ORIG) * 4}")
        return

    load_env_from_file()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    if args.arm in ("refined", "both"):
        run_entity_swap(client, variants_refined)
    if args.arm in ("orig", "both"):
        run_native_mt(client, pairs_orig)


if __name__ == "__main__":
    main()
