import csv
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hpc"))

import fanar_filter_retest
import fanar_system_audit
import prepare_fanar_local_pilot


class TestFanarExperiments(unittest.TestCase):
    def test_offline_audit_reconciles_native_outcomes(self):
        manifest = fanar_system_audit.audit()
        self.assertEqual(manifest["native_pilot"]["delivered"], 171)
        self.assertEqual(manifest["native_pilot"]["provider_filtered"], 29)
        self.assertEqual(manifest["native_pilot"]["technical_failures"], 0)
        self.assertEqual(manifest["native_probability_route_audit"]["delivered"], 356)
        self.assertEqual(manifest["native_probability_route_audit"]["provider_filtered"], 44)
        self.assertEqual(manifest["native_probability_route_audit"]["technical_failures"], 0)
        self.assertEqual(manifest["native_filter_retest"]["newly_delivered"], 16)
        self.assertEqual(manifest["native_filter_retest"]["repeated_provider_filters"], 13)
        self.assertEqual(manifest["native_filter_retest"]["newly_delivered_sol_genuine_refusals"], 5)
        self.assertEqual(manifest["native_filter_retest"]["newly_delivered_sol_capability_failures"], 2)

    def test_filter_retest_is_exactly_the_29_original_filters(self):
        manifest = fanar_filter_retest.prepare()
        self.assertEqual(manifest["n_requests"], 29)
        original = {
            row["provider_request_id"]: row
            for row in fanar_filter_retest.read_jsonl(fanar_filter_retest.SOURCE_DIR / "provider_requests.jsonl")
        }
        repeats = fanar_filter_retest.read_jsonl(fanar_filter_retest.OUTPUT_DIR / "provider_requests.jsonl")
        provider_fields = (
            "model", "messages", "temperature", "max_tokens", "enable_thinking",
            "repetition_penalty", "n", "stream",
        )
        for row in repeats:
            source = original[row["source_provider_request_id"]]
            self.assertEqual(
                {key: row[key] for key in provider_fields},
                {key: source[key] for key in provider_fields},
            )

    def test_local_pilot_is_matched_and_prompt_occurs_once(self):
        manifest = prepare_fanar_local_pilot.prepare()
        self.assertEqual(manifest["n_requests"], 200)
        requests = prepare_fanar_local_pilot.read_jsonl(
            prepare_fanar_local_pilot.OUTPUT_DIR / "requests.jsonl"
        )
        self.assertEqual(len({(row["prompt_id"], row["prompt_language"]) for row in requests}), 200)
        native = fanar_filter_retest.read_jsonl(fanar_filter_retest.SOURCE_DIR / "provider_requests.jsonl")
        self.assertEqual({row["prompt_id"] for row in requests}, {row["prompt_id"] for row in native})
        for row in requests:
            prefix = "<bos><start_of_turn>user\n"
            suffix = "<end_of_turn>\n<start_of_turn>model\n"
            self.assertTrue(row["raw_prompt"].startswith(prefix))
            self.assertTrue(row["raw_prompt"].endswith(suffix))
            text = row["raw_prompt"][len(prefix):-len(suffix)]
            self.assertEqual(row["raw_prompt"].count(text), 1)

    def test_bounds_have_one_row_per_language(self):
        path = fanar_system_audit.OUTPUT_DIR / "native_pilot_language_bounds.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual({row["prompt_language"] for row in rows}, set(fanar_system_audit.LANGUAGES))
        for row in rows:
            self.assertLessEqual(
                float(row["textual_refusal_lower_bound"]),
                float(row["textual_refusal_upper_bound"]),
            )


if __name__ == "__main__":
    unittest.main()
