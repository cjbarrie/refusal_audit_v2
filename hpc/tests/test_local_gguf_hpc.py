#!/usr/bin/env python3
"""Contract tests for the Torch full-corpus run without provider or GPU calls."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hpc"))

from prepare_local_gguf_full import CONFIG_PATH, render_prompt, task_map


class TestHpcContract(unittest.TestCase):
    def test_prompt_wrappers_preserve_user_text(self):
        text = "literal multilingual text العربية 中文 русский हिन्दी"
        for template in ("chatml_single_user", "krutrim_single_user", "gigachat_single_user"):
            prompt, _ = render_prompt(template, text)
            self.assertEqual(prompt.count(text), 1)

    def test_gigachat_template_is_official_single_user_branch(self):
        prompt, stop = render_prompt("gigachat_single_user", "X")
        self.assertEqual(prompt, "user<|role_sep|>\nX<|message_sep|>\n\nassistant<|role_sep|>\n")
        self.assertEqual(stop, ["<|message_sep|>"])

    def test_task_map_has_two_shards_for_every_cell(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        tasks = task_map(config)
        self.assertEqual(len(tasks), 40)
        cells = {(row["model"], row["language"]) for row in tasks}
        self.assertEqual(len(cells), 20)
        for cell in cells:
            self.assertEqual({row["shard"] for row in tasks if (row["model"], row["language"]) == cell}, {0, 1})

    def test_container_loader_path_is_documented_in_runner(self):
        runner = (ROOT / "hpc/run_local_gguf_shard.py").read_text(encoding="utf-8")
        self.assertIn("LD_LIBRARY_PATH=/app:/.singularity.d/libs", runner)


if __name__ == "__main__":
    unittest.main()
