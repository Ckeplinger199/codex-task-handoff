from __future__ import annotations

import re
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "task-handoff"


class SkillContractTests(unittest.TestCase):
    def test_installed_skill_contains_runnable_usage_example(self):
        with tempfile.TemporaryDirectory() as temporary:
            installed = Path(temporary) / "installed skill"
            shutil.copytree(SKILL_DIR, installed, ignore=shutil.ignore_patterns("__pycache__"))
            skill = (installed / "SKILL.md").read_text()
            for relative in re.findall(r"\]\((references/[^)]+)\)", skill):
                self.assertTrue((installed / relative).is_file(), relative)
            guide = (installed / "references/usage-guide.md").read_text()
            example = re.search(r"```json\n(.*?)\n```", guide, re.DOTALL)
            self.assertIsNotNone(example)
            result = subprocess.run(
                [sys.executable, str(installed / "scripts/decide_handoff.py")],
                input=example.group(1), capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["decision"], "recommend")

    def test_skill_is_discoverable_and_current_contract_is_documented(self):
        content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        self.assertIsNotNone(match)
        self.assertIn("name: task-handoff", match.group(1))
        for term in ("list_projects", "projectId", "clientThreadId", "::created-thread",
                     "update_goal", "ACK", "transfer_handoff.py", "decide_handoff.py"):
            with self.subTest(term=term):
                self.assertIn(term, content)
        self.assertNotIn("ARCHIVE —", content)
        self.assertNotIn("inherits the source workspace", content)
        self.assertNotIn("cannot safely pause", content)

    def test_metadata_keeps_skill_invocable(self):
        content = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Task Handoff"', content)
        self.assertIn("$task-handoff", content)


if __name__ == "__main__":
    unittest.main()
