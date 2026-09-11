"""
Validate data completeness and quality across all languages and models.

This script checks:
1. All prompt IDs have responses across all models and languages
2. All valid responses have corresponding annotations
3. No data corruption in JSONL files
4. Coverage statistics and error analysis
"""

import json
import os
from typing import Dict, List, Set, Tuple
from collections import defaultdict


def load_jsonl(file_path: str) -> List[Dict]:
    """Load JSONL file and return list of records."""
    records = []
    if not os.path.exists(file_path):
        print(f"Warning: File not found: {file_path}")
        return records

    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line.strip())
                records.append(record)
            except json.JSONDecodeError as e:
                print(f"  ERROR: Line {line_num} in {file_path}: {e}")

    return records


def validate_prompts(prompts_dir: str, languages: List[str]) -> Dict:
    """Validate prompt files across all languages."""
    print("=" * 80)
    print("VALIDATING PROMPT FILES")
    print("=" * 80)

    results = {}

    for lang in languages:
        prompt_file = f"{prompts_dir}/test_prompts_{lang}.json"

        if not os.path.exists(prompt_file):
            print(f"\n{lang.upper()}: ✗ File not found")
            results[lang] = {"status": "missing", "count": 0, "ids": set()}
            continue

        with open(prompt_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        prompts = data.get('prompts', [])
        prompt_ids = {p['id'] for p in prompts}

        # Check structure (dynamic: read declared total_prompts if present)
        declared_total = data.get("total_prompts")
        actual_count = len(prompts)
        expected_count = declared_total if isinstance(declared_total, int) else actual_count

        status = "✓" if actual_count == expected_count else "⚠️"
        expected_label = expected_count if isinstance(expected_count, int) else "?"
        print(f"\n{lang.upper()}: {status} {actual_count}/{expected_label} prompts")

        # Check category distribution
        category_counts = defaultdict(int)
        controversy_counts = defaultdict(int)

        for prompt in prompts:
            category_counts[prompt['category']] += 1
            controversy_counts[prompt.get('controversy_tier', 'unknown')] += 1

        print(f"  Categories: {dict(category_counts)}")
        print(f"  Controversy tiers: {dict(controversy_counts)}")

        results[lang] = {
            "status": "valid" if actual_count == expected_count else "incomplete",
            "count": actual_count,
            "ids": list(prompt_ids),  # Convert set to list for JSON serialization
            "categories": dict(category_counts),
            "controversy": dict(controversy_counts),
        }

    return results


def validate_responses(responses_dir: str, languages: List[str], models: List[str], prompt_results: Dict) -> Dict:
    """Validate response files across all languages."""
    print("\n" + "=" * 80)
    print("VALIDATING RESPONSE FILES")
    print("=" * 80)

    results = {}

    for lang in languages:
        response_file = f"{responses_dir}/responses_{lang}.jsonl"

        if not os.path.exists(response_file):
            print(f"\n{lang.upper()}: ✗ File not found")
            results[lang] = {"status": "missing", "responses": []}
            continue

        responses = load_jsonl(response_file)

        # Group by model and prompt_id
        by_model = defaultdict(set)
        by_prompt = defaultdict(set)
        errors = []

        for resp in responses:
            prompt_id = resp.get('prompt_id')
            model = resp.get('model')
            response_text = resp.get('response_text', '')

            if not response_text or 'error' in resp:
                errors.append({
                    "prompt_id": prompt_id,
                    "model": model,
                    "error": resp.get('error', 'Empty response')
                })
            else:
                by_model[model].add(prompt_id)
                by_prompt[prompt_id].add(model)

        # Calculate expected vs actual
        expected_prompts = prompt_results[lang]['count']
        expected_total = expected_prompts * len(models)
        actual_total = len(responses)
        success_total = actual_total - len(errors)

        print(f"\n{lang.upper()}:")
        print(f"  Total responses: {actual_total}/{expected_total}")
        print(f"  Successful: {success_total} ({success_total/expected_total*100:.1f}%)")
        print(f"  Errors: {len(errors)} ({len(errors)/expected_total*100:.1f}%)")

        # Check coverage by model
        print(f"  Coverage by model:")
        for model in models:
            count = len(by_model[model])
            print(f"    {model}: {count}/{expected_prompts} ({count/expected_prompts*100:.1f}%)")

        # Find missing prompt-model combinations
        missing = []
        for prompt_id in prompt_results[lang]['ids']:
            for model in models:
                if prompt_id not in by_model[model]:
                    missing.append((prompt_id, model))

        if missing:
            print(f"  Missing combinations: {len(missing)}")
            if len(missing) <= 10:
                for pid, mod in missing[:10]:
                    print(f"    - {pid} × {mod}")

        results[lang] = {
            "status": "complete" if len(missing) == 0 else "incomplete",
            "total": actual_total,
            "expected": expected_total,
            "successful": success_total,
            "errors": len(errors),
            "error_details": errors[:20],  # First 20 errors
            "missing_combinations": len(missing),
            "by_model": {model: len(ids) for model, ids in by_model.items()},
            "responses": responses,
        }

    return results


def validate_annotations(annotations_dir: str, languages: List[str], response_results: Dict) -> Dict:
    """Validate annotation files against responses."""
    print("\n" + "=" * 80)
    print("VALIDATING ANNOTATION FILES")
    print("=" * 80)

    results = {}

    for lang in languages:
        annotation_file = f"{annotations_dir}/annotations_{lang}.jsonl"

        if not os.path.exists(annotation_file):
            print(f"\n{lang.upper()}: ✗ File not found")
            results[lang] = {"status": "missing", "count": 0}
            continue

        annotations = load_jsonl(annotation_file)

        # Get successful responses for this language
        successful_responses = response_results[lang]['successful']

        # Count annotation errors
        annotation_errors = sum(1 for ann in annotations if 'error' in ann or not ann.get('engagement_code'))
        successful_annotations = len(annotations) - annotation_errors

        coverage = successful_annotations / successful_responses * 100 if successful_responses > 0 else 0

        print(f"\n{lang.upper()}:")
        print(f"  Total annotations: {len(annotations)}")
        print(f"  Successful: {successful_annotations} ({successful_annotations/len(annotations)*100:.1f}%)")
        print(f"  Errors: {annotation_errors}")
        print(f"  Coverage: {successful_annotations}/{successful_responses} ({coverage:.1f}%)")

        # Check annotation distribution
        engagement_dist = defaultdict(int)
        for ann in annotations:
            if 'engagement_code' in ann:
                engagement_dist[ann['engagement_code']] += 1

        print(f"  Engagement distribution: {dict(engagement_dist)}")

        results[lang] = {
            "status": "complete" if coverage > 95 else "incomplete",
            "total": len(annotations),
            "successful": successful_annotations,
            "errors": annotation_errors,
            "coverage_pct": coverage,
            "engagement_dist": dict(engagement_dist),
        }

    return results


def generate_summary(prompt_results: Dict, response_results: Dict, annotation_results: Dict) -> Dict:
    """Generate overall summary statistics."""
    print("\n" + "=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)

    total_prompts = sum(r['count'] for r in prompt_results.values())
    total_responses = sum(r['total'] for r in response_results.values())
    total_successful_responses = sum(r['successful'] for r in response_results.values())
    total_annotations = sum(r['total'] for r in annotation_results.values())
    total_successful_annotations = sum(r['successful'] for r in annotation_results.values())

    print(f"\nPrompts: {total_prompts} across {len(prompt_results)} languages")
    print(f"Responses: {total_successful_responses}/{total_responses} successful ({total_successful_responses/total_responses*100:.1f}%)")
    print(f"Annotations: {total_successful_annotations}/{total_annotations} successful ({total_successful_annotations/total_annotations*100:.1f}%)")

    # Data pipeline efficiency
    print(f"\nData pipeline:")
    print(f"  Prompts → Responses: {total_successful_responses/total_prompts:.1f}x (expected 4x for 4 models)")
    print(f"  Responses → Annotations: {total_successful_annotations/total_successful_responses*100:.1f}% coverage")

    summary = {
        "total_prompts": total_prompts,
        "total_responses": total_responses,
        "successful_responses": total_successful_responses,
        "response_success_rate": total_successful_responses / total_responses if total_responses > 0 else 0,
        "total_annotations": total_annotations,
        "successful_annotations": total_successful_annotations,
        "annotation_success_rate": total_successful_annotations / total_annotations if total_annotations > 0 else 0,
        "annotation_coverage": total_successful_annotations / total_successful_responses if total_successful_responses > 0 else 0,
    }

    return summary


def main():
    # Configuration
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompts_dir = os.path.join(base_dir, "prompts")
    responses_dir = os.path.join(base_dir, "responses")
    annotations_dir = os.path.join(base_dir, "annotations")

    languages = ["en", "zh", "ja", "id", "ar"]
    models = ["gpt-5.1", "claude-opus-4.5", "gpt-4o", "deepseek-chat-v3.1"]

    # Run validations
    prompt_results = validate_prompts(prompts_dir, languages)
    response_results = validate_responses(responses_dir, languages, models, prompt_results)
    annotation_results = validate_annotations(annotations_dir, languages, response_results)
    summary = generate_summary(prompt_results, response_results, annotation_results)

    # Save validation report
    report = {
        "prompts": prompt_results,
        "responses": {k: {**v, "responses": None} for k, v in response_results.items()},  # Exclude full responses
        "annotations": annotation_results,
        "summary": summary,
    }

    report_file = os.path.join(base_dir, "data", "validation_report.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 80}")
    print(f"Validation report saved to: {report_file}")
    print(f"{'=' * 80}")

    # Return status code
    all_valid = (
        all(r['status'] == 'valid' for r in prompt_results.values()) and
        summary['response_success_rate'] > 0.90 and
        summary['annotation_coverage'] > 0.95
    )

    return 0 if all_valid else 1


if __name__ == "__main__":
    exit(main())
