"""
Translate political prompts to target language using Google Translate.

This script translates English prompts to target languages.
"""

import json
import os
import time
from typing import Dict
from deep_translator import GoogleTranslator
from datetime import datetime


# Language configurations
LANGUAGE_CONFIGS = {
    "zh-CN": {
        "code": "zh-CN",
        "name": "Chinese (Simplified)",
        "native_name": "简体中文",
    },
    "ja": {
        "code": "ja",
        "name": "Japanese",
        "native_name": "日本語",
    },
    "id": {
        "code": "id",
        "name": "Indonesian",
        "native_name": "Bahasa Indonesia",
    },
    "ar": {
        "code": "ar",
        "name": "Arabic",
        "native_name": "العربية",
    },
}


def translate_text(
    text: str,
    target_lang: str,
) -> str:
    """
    Translate a single text using Google Translate.

    Args:
        text: Source text to translate
        target_lang: Target language code (zh-CN, ja, id, ar)

    Returns:
        Translated text
    """
    lang_config = LANGUAGE_CONFIGS[target_lang]

    translator = GoogleTranslator(source='en', target=lang_config['code'])
    translated = translator.translate(text)

    # Add small delay to avoid rate limiting
    time.sleep(0.1)

    return translated


def translate_prompts(
    source_file: str,
    target_language: str,
    output_file: str,
    limit: int = None,
    verbose: bool = True
):
    """
    Translate all prompts from source file to target language.

    Args:
        source_file: Path to source JSON (English prompts)
        target_language: Target language code (zh-CN, ja, id, ar)
        output_file: Path to save translated prompts
        limit: Optional limit on number of prompts to translate (for testing)
        verbose: Print progress information
    """
    # Validate language
    if target_language not in LANGUAGE_CONFIGS:
        raise ValueError(f"Unsupported language: {target_language}. Must be one of: {list(LANGUAGE_CONFIGS.keys())}")

    lang_config = LANGUAGE_CONFIGS[target_language]

    # Load source prompts
    with open(source_file, 'r', encoding='utf-8') as f:
        source_data = json.load(f)

    source_prompts = source_data['prompts']
    if limit:
        source_prompts = source_prompts[:limit]

    if verbose:
        print("=" * 80)
        print(f"TRANSLATING PROMPTS TO {lang_config['name'].upper()}")
        print("=" * 80)
        print(f"Source: {source_file}")
        print(f"Target language: {lang_config['name']} ({lang_config['native_name']})")
        print(f"Total prompts: {len(source_prompts)}")
        print(f"Output: {output_file}")
        print()

    # Translate prompts
    translated_prompts = []
    completed = 0
    errors = 0

    for source_prompt in source_prompts:
        completed += 1

        if verbose:
            print(f"[{completed}/{len(source_prompts)}] Translating {source_prompt['id']}...", end=" ")

        try:
            translated_text = translate_text(
                text=source_prompt['text'],
                target_lang=target_language,
            )

            # Create translated prompt record
            translated_prompt = {
                "id": source_prompt['id'],
                "category": source_prompt['category'],
                "controversy_tier": source_prompt['controversy_tier'],
                "text": translated_text,
                "source_language": "en",
                "source_text": source_prompt['source_text'],
                "region_focus": source_prompt.get('region_focus'),
            }

            translated_prompts.append(translated_prompt)

            if verbose:
                print(f"✓ ({len(translated_text)} chars)")

        except Exception as e:
            errors += 1
            if verbose:
                print(f"✗ Error: {e}")

            # Add placeholder for failed translation
            translated_prompt = {
                "id": source_prompt['id'],
                "category": source_prompt['category'],
                "controversy_tier": source_prompt['controversy_tier'],
                "text": f"[TRANSLATION FAILED: {source_prompt['text']}]",
                "source_language": "en",
                "source_text": source_prompt['source_text'],
                "region_focus": source_prompt.get('region_focus'),
                "translation_error": str(e),
            }
            translated_prompts.append(translated_prompt)

    # Count prompts per category
    category_counts = {}
    for prompt in translated_prompts:
        cat = prompt['category']
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Create output structure
    # Map language code for output (zh-CN -> zh)
    output_lang_code = "zh" if target_language == "zh-CN" else target_language

    output_data = {
        "version": "2.0",
        "language": output_lang_code,
        "language_name": lang_config['name'],
        "total_prompts": len(translated_prompts),
        "prompts_per_category": category_counts,
        "categories": source_data['categories'],
        "translated_at": datetime.utcnow().isoformat(),
        "source_file": source_file,
        "prompts": translated_prompts,
    }

    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    if verbose:
        print()
        print("=" * 80)
        print("TRANSLATION COMPLETE")
        print("=" * 80)
        print(f"Total: {len(translated_prompts)}")
        print(f"Success: {len(translated_prompts) - errors}")
        print(f"Errors: {errors}")
        print(f"Output saved to: {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Translate political prompts to target language")
    parser.add_argument(
        "--source",
        default="../prompts/test_prompts_en.json",
        help="Path to source prompts JSON (default: ../prompts/test_prompts_en.json)"
    )
    parser.add_argument(
        "--target-language",
        required=True,
        choices=["zh-CN", "ja", "id", "ar"],
        help="Target language code (zh-CN=Chinese, ja=Japanese, id=Indonesian, ar=Arabic)"
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: ../prompts/test_prompts_{lang}.json)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of prompts to translate (for testing)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    # Set default output path if not provided
    if not args.output:
        # Map zh-CN to zh for filename
        lang_code = "zh" if args.target_language == "zh-CN" else args.target_language
        args.output = f"../prompts/test_prompts_{lang_code}.json"

    # Create output directory if needed
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    translate_prompts(
        source_file=args.source,
        target_language=args.target_language,
        output_file=args.output,
        limit=args.limit,
        verbose=not args.quiet
    )
