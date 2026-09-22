from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/task-handoff/scripts/transfer_handoff.py"
STORE = ROOT / "skills/task-handoff/scripts/store_handoff.py"
spec = importlib.util.spec_from_file_location("transfer_handoff", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PACKET = "# Task Handoff: Importer\n\n## Objective\nFinish importer.\n\n## Current State\nTests pass.\n\n## Exact Next Action\nRun parser check.\n"


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet = self.root / "packet.md"
        self.packet.write_text(PACKET, encoding="utf-8")
        self.source = self.root / "source"
        self.target = self.root / "target"
        self.registry = self.root / "registry"
        self.source.mkdir()
        self.target.mkdir()

    def prepare(self, **overrides):
        kwargs = dict(packet_path=self.packet, source_host="host-1", source_task="task-1",
                      source_workspace=str(self.source), expected_workspace=str(self.target),
                      state_root=self.registry)
        kwargs.update(overrides)
        return module.prepare(**kwargs)

    def cli(self, *args, ok=True):
        proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True)
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 2)
        return json.loads(proc.stderr)

    def test_private_idempotent_intent_and_source_conflict(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.prepare(), range(4)))
        self.assertEqual(len({r["state_path"] for r in results}), 1)
        state = results[0]["state"]
        self.assertEqual(state["status"], "prepared")
        self.assertEqual(state["created_at"], self.prepare()["state"]["created_at"])
        self.assertIn(str(SCRIPT), results[0]["bootstrap"])
        self.assertIn("ack --state", results[0]["bootstrap"])
        path = Path(results[0]["state_path"])
        if os.name == "posix":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        other = self.root / "another-dir" / "packet.md"
        other.parent.mkdir()
        other.write_text(PACKET, encoding="utf-8")
        with self.assertRaisesRegex(module.TransferError, "different transfer"):
            self.prepare(packet_path=other)

    def test_creation_and_uncertain_receipt_reconciliation(self):
        path = self.prepare()["state_path"]
        with self.assertRaisesRegex(module.TransferError, "creating"):
            module.change(path, "ready", thread_id="real", host_id="host-2")
        module.change(path, "creating")
        with self.assertRaisesRegex(module.TransferError, "reconcile"):
            module.change(path, "creating")
        module.change(path, "uncertain", error="timeout after dispatch")
        resolved = module.change(path, "ready", thread_id="real", host_id="host-2")
        self.assertEqual(resolved["status"], "ready")
        self.assertEqual(module.change(path, "ready", thread_id="real", host_id="host-2"), resolved)
        with self.assertRaisesRegex(module.TransferError, "conflicting"):
            module.change(path, "ready", thread_id="other", host_id="host-2")

    def test_pending_receipt_replay_and_ack_wait(self):
        path = self.prepare()["state_path"]
        module.change(path, "creating")
        pending = module.change(path, "pending", client_id="queued-1")
        self.assertEqual(module.change(path, "pending", client_id="queued-1"), pending)
        with self.assertRaisesRegex(module.TransferError, "conflicting"):
            module.change(path, "pending", client_id="queued-2")
        self.assertIsNone(pending["thread_id"])
        with self.assertRaisesRegex(module.TransferError, "ready"):
            module.change(path, "ack", transfer_id=pending["transfer_id"],
                          digest=pending["packet_sha256"], workspace=str(self.target),
                          next_action=pending["next_action"], thread_id="real-1", host_id="host-2")
        with self.assertRaisesRegex(module.TransferError, "client ID"):
            module.change(path, "ready", thread_id="real-1", host_id="host-2", client_id="other")
        ready = module.change(path, "ready", thread_id="real-1", host_id="host-2", client_id="queued-1")
        self.assertEqual(ready["thread_id"], "real-1")

    def test_ack_rejects_wrong_caller_and_verify_checks_every_field(self):
        path = self.prepare()["state_path"]
        module.change(path, "creating")
        state = module.change(path, "ready", thread_id="real-1", host_id="host-2")
        kwargs = {"transfer_id": state["transfer_id"], "digest": state["packet_sha256"],
                  "workspace": str(self.target), "next_action": state["next_action"],
                  "thread_id": "real-1", "host_id": "host-2"}
        for change in ({"transfer_id": "wrong"}, {"digest": "wrong"},
                       {"workspace": str(self.source)}, {"next_action": "Other action"},
                       {"thread_id": "wrong"}, {"host_id": "wrong"}):
            with self.subTest(change=change), self.assertRaises(module.TransferError):
                module.change(path, "ack", **{**kwargs, **change})
        self.packet.write_text(PACKET + "modified\n", encoding="utf-8")
        with self.assertRaisesRegex(module.TransferError, "changed"):
            module.change(path, "ack", **kwargs)
        self.packet.write_text(PACKET, encoding="utf-8")
        ack = module.change(path, "ack", **kwargs)
        self.assertEqual(ack["status"], "acknowledged")
        self.assertEqual(module.change(path, "ack", **kwargs), ack)
        self.assertEqual(module.change(path, "verify")["ack"]["host_id"], "host-2")
        for field, value in (("transfer_id", "bad"), ("packet_sha256", "bad"),
                             ("workspace", "/wrong/workspace"), ("next_action", "bad"),
                             ("thread_id", "bad"), ("host_id", "bad")):
            corrupted = json.loads(Path(path).read_text())
            corrupted["ack"][field] = value
            Path(path).write_text(json.dumps(corrupted))
            with self.subTest(field=field), self.assertRaisesRegex(module.TransferError, "ACK fields mismatch"):
                module.change(path, "verify")
            Path(path).write_text(json.dumps(ack))
        self.packet.write_text(PACKET + "changed\n", encoding="utf-8")
        with self.assertRaisesRegex(module.TransferError, "packet changed"):
            module.change(path, "verify")

    def test_worktree_target_is_bound_from_authoritative_ready_receipt(self):
        state = self.prepare(expected_workspace=None, target_kind="worktree",
                             project_id="project-1", starting_ref="abc123")["state"]
        path = self.prepare(expected_workspace=None, target_kind="worktree",
                            project_id="project-1", starting_ref="abc123")["state_path"]
        self.assertIsNone(state["expected_workspace"])
        module.change(path, "creating")
        with self.assertRaisesRegex(module.TransferError, "needs workspace"):
            module.change(path, "ready", thread_id="real", host_id="host-2")
        ready = module.change(path, "ready", thread_id="real", host_id="host-2",
                              workspace=str(self.target))
        self.assertEqual(ready["expected_workspace"], str(self.target.resolve()))
        self.assertEqual(self.prepare(expected_workspace=None, target_kind="worktree",
                                      project_id="project-1", starting_ref="abc123")["state"], ready)

    def test_symlink_state_is_rejected(self):
        path = Path(self.prepare()["state_path"])
        backing = path.with_name("backing.json")
        path.rename(backing)
        path.symlink_to(backing)
        with self.assertRaisesRegex(module.TransferError, "symlink"):
            module.change(path, "creating")
        self.assertFalse(self.cli("inspect", "--state", path, ok=False)["ok"])

    def test_process_concurrent_creating_has_one_winner(self):
        path = self.prepare()["state_path"]
        command = [sys.executable, str(SCRIPT), "creating", "--state", path]
        first = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        results = [first.communicate(), second.communicate()]
        self.assertEqual(sorted([first.returncode, second.returncode]), [0, 2], results)
        self.assertEqual(module._read(Path(path))["status"], "creating")

    def test_full_cli_flow_with_fake_provider_ids(self):
        stored = subprocess.run([sys.executable, str(STORE), "--title", "Importer",
                                 "--cwd", str(self.source), "--input", str(self.packet),
                                 "--output-dir", str(self.root / "packets")],
                                capture_output=True, text=True)
        self.assertEqual(stored.returncode, 0, stored.stderr)
        packet = json.loads(stored.stdout)["path"]
        prep = self.cli("prepare", "--packet", packet, "--source-host", "host-1",
                        "--source-task", "task-1", "--source-workspace", self.source,
                        "--expected-workspace", self.target, "--state-root", self.registry)
        path = prep["state_path"]
        self.assertEqual(prep["state"]["packet_sha256"], hashlib.sha256(PACKET.encode()).hexdigest())
        self.cli("creating", "--state", path)
        self.cli("pending", "--state", path, "--client-id", "fake-client")
        ready = self.cli("ready", "--state", path, "--client-id", "fake-client",
                         "--thread-id", "fake-real", "--host-id", "fake-host")
        self.assertEqual(ready["status"], "ready")
        ack = self.cli("ack", "--state", path, "--transfer-id", ready["transfer_id"],
                       "--sha256", ready["packet_sha256"], "--workspace", self.target,
                       "--next-action", ready["next_action"], "--thread-id", "fake-real",
                       "--host-id", "fake-host")
        self.assertEqual(ack["status"], "acknowledged")
        self.assertIsNotNone(ack["acknowledged_at"])
        self.assertEqual(self.cli("verify", "--state", path)["ack"], ack["ack"])


if __name__ == "__main__":
    unittest.main()
