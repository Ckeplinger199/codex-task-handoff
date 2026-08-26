from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "task-handoff" / "scripts" / "store_handoff.py"

spec = importlib.util.spec_from_file_location("store_handoff", SCRIPT)
assert spec and spec.loader
store_handoff = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = store_handoff
spec.loader.exec_module(store_handoff)

VALID_PACKET = """# Task Handoff: Fix importer

## Objective

- Finish the importer and pass its focused tests.

## Current State

- HEAD is recorded and one file is dirty.

## Exact Next Action

Run the focused parser test, then inspect the first failure.
"""


class StoreHandoffTests(unittest.TestCase):
    def test_stores_private_content_and_returns_small_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / "workspace"
            out = root / "handoffs"
            cwd.mkdir()

            receipt = store_handoff.store_handoff(
                title="Fix importer", cwd=cwd, raw_packet=VALID_PACKET, output_dir=out
            )

            path = Path(receipt.path)
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_text(encoding="utf-8"), VALID_PACKET)
            self.assertEqual(
                receipt.sha256, hashlib.sha256(VALID_PACKET.encode("utf-8")).hexdigest()
            )
            self.assertLessEqual(receipt.bootstrap_bytes, 1_000)
            self.assertIn(str(path), receipt.bootstrap)
            self.assertFalse(receipt.reused)
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_identical_packet_reuses_content_addressed_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / "workspace"
            out = root / "handoffs"
            cwd.mkdir()
            first = store_handoff.store_handoff(
                title="Fix importer", cwd=cwd, raw_packet=VALID_PACKET, output_dir=out
            )
            second = store_handoff.store_handoff(
                title="Fix importer", cwd=cwd, raw_packet=VALID_PACKET, output_dir=out
            )
            self.assertEqual(first.path, second.path)
            self.assertTrue(second.reused)
            if os.name == "posix":
                path = Path(second.path)
                path.chmod(0o644)
                third = store_handoff.store_handoff(
                    title="Fix importer", cwd=cwd, raw_packet=VALID_PACKET, output_dir=out
                )
                self.assertTrue(third.reused)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_goal_section_adds_goal_bootstrap_instruction(self) -> None:
        packet = VALID_PACKET.replace(
            "## Exact Next Action",
            "## Goal Continuity\n\n- Objective: Finish importer\n\n## Exact Next Action",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / "workspace"
            cwd.mkdir()
            receipt = store_handoff.store_handoff(
                title="Fix importer",
                cwd=cwd,
                raw_packet=packet,
                output_dir=root / "handoffs",
            )
            self.assertIn("recreate the unfinished Goal", receipt.bootstrap)

    def test_missing_required_heading_is_rejected(self) -> None:
        with self.assertRaisesRegex(store_handoff.HandoffError, "Exact Next Action"):
            store_handoff.normalize_packet(
                "# Task Handoff\n\n## Objective\nX\n\n## Current State\nY\n"
            )

    def test_required_heading_must_be_an_exact_heading_line(self) -> None:
        packet = VALID_PACKET.replace("## Objective", "## Objective appendix")
        with self.assertRaisesRegex(store_handoff.HandoffError, "Objective"):
            store_handoff.normalize_packet(packet)

    @unittest.skipUnless(os.name == "posix", "symlink semantics are POSIX-specific")
    def test_existing_symlink_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / "workspace"
            out = root / "handoffs"
            cwd.mkdir()
            out.mkdir()

            normalized = store_handoff.normalize_packet(VALID_PACKET)
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            target = root / "unrelated.txt"
            target.write_text(normalized, encoding="utf-8")
            handoff_path = out / f"fix-importer-{digest[:12]}.md"
            handoff_path.symlink_to(target)

            with self.assertRaisesRegex(store_handoff.HandoffError, "symlink"):
                store_handoff.store_handoff(
                    title="Fix importer",
                    cwd=cwd,
                    raw_packet=VALID_PACKET,
                    output_dir=out,
                )

    def test_goal_heading_detection_is_exact(self) -> None:
        packet = VALID_PACKET.replace(
            "## Exact Next Action",
            "## Goal Continuity notes\n\nNo transferable goal.\n\n## Exact Next Action",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / "workspace"
            cwd.mkdir()
            receipt = store_handoff.store_handoff(
                title="Fix importer",
                cwd=cwd,
                raw_packet=packet,
                output_dir=root / "handoffs",
            )
            self.assertNotIn("recreate the unfinished Goal", receipt.bootstrap)

    def test_bootstrap_compacts_for_a_long_storage_path(self) -> None:
        long_path = Path("/" + "/".join(["x" * 90] * 6))
        bootstrap = store_handoff.build_bootstrap(
            title="T" * 200,
            path=long_path,
            digest="a" * 64,
            has_goal=True,
        )
        self.assertTrue(bootstrap.startswith("Read handoff file"))
        self.assertLessEqual(len(bootstrap.encode("utf-8")), 1_000)

    def test_oversized_packet_is_rejected(self) -> None:
        packet = VALID_PACKET + ("x" * store_handoff.MAX_PACKET_BYTES)
        with self.assertRaisesRegex(store_handoff.HandoffError, "compress it"):
            store_handoff.normalize_packet(packet)

    def test_cli_returns_machine_readable_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / "workspace"
            cwd.mkdir()
            packet_path = root / "packet.md"
            packet_path.write_text(VALID_PACKET, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--title",
                    "Fix importer",
                    "--cwd",
                    str(cwd),
                    "--input",
                    str(packet_path),
                    "--output-dir",
                    str(root / "handoffs"),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertLessEqual(payload["bootstrap_bytes"], 1_000)


if __name__ == "__main__":
    unittest.main()
