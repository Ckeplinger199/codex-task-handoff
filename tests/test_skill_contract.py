from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "task-handoff"
SKILL = SKILL_DIR / "SKILL.md"
OPENAI_YAML = SKILL_DIR / "agents" / "openai.yaml"


class SkillContractTests(unittest.TestCase):
    def test_skill_frontmatter_is_discoverable(self) -> None:
        content = SKILL.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        self.assertIsNotNone(match)
        frontmatter = match.group(1) if match else ""
        self.assertIn("name: task-handoff", frontmatter)
        description = next(
            line.partition(":")[2].strip()
            for line in frontmatter.splitlines()
            if line.startswith("description:")
        )
        self.assertGreater(len(description), 40)
        self.assertLessEqual(len(description), 1_024)
        self.assertIn("token", description.lower())

    def test_removed_unsupported_runtime_contracts_do_not_return(self) -> None:
        content = SKILL.read_text(encoding="utf-8")
        forbidden = (
            "list_projects",
            "set_thread_pinned",
            "::created-thread",
            "thinking:",
        )
        for term in forbidden:
            with self.subTest(term=term):
                self.assertNotIn(term, content)

    def test_supported_successor_contract_is_explicit(self) -> None:
        content = SKILL.read_text(encoding="utf-8")
        self.assertIn("Call `create_thread` exactly once", content)
        self.assertIn("Omit `model`", content)
        self.assertIn("one bounded `read_thread`", content)
        self.assertIn("scripts/store_handoff.py", content)
        self.assertNotIn("current model settings", content)

    def test_active_goal_requires_pause_before_successor(self) -> None:
        content = SKILL.read_text(encoding="utf-8")
        self.assertIn("Never leave two active Goal loops", content)
        self.assertIn("**Active:**", content)
        self.assertIn("do not call `create_thread`", content)
        self.assertIn("`/goal pause`", content)
        self.assertIn("Budget-limited, usage-limited", content)
        self.assertIn("do not create a successor Goal or silently remove the limit", content)

    def test_ui_metadata_keeps_skill_invocable(self) -> None:
        content = OPENAI_YAML.read_text(encoding="utf-8")
        self.assertIn('display_name: "Task Handoff"', content)
        self.assertIn("$task-handoff", content)
        self.assertIn("allow_implicit_invocation: true", content)


if __name__ == "__main__":
    unittest.main()
