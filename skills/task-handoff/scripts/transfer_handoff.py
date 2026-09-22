#!/usr/bin/env python3
"""Local transfer journal for one source task. No provider calls are made here."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class TransferError(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _required(value, name):
    if not isinstance(value, str) or not value.strip():
        raise TransferError(f"{name} is required")
    return value.strip()


def _workspace(value):
    path = Path(_required(value, "workspace")).expanduser()
    if not path.is_absolute():
        raise TransferError("workspace must be absolute")
    return str(path.resolve())


def _next_action(packet):
    match = re.search(r"(?ms)^## Exact Next Action[ \t]*\n(.*?)(?=^## |\Z)", packet)
    if not match:
        raise TransferError("packet lacks Exact Next Action")
    action = match.group(1).strip()
    if not action:
        raise TransferError("Exact Next Action is empty")
    return action


def _state_root():
    codex_home = os.environ.get("CODEX_HOME")
    return (Path(codex_home).expanduser() if codex_home else Path.home() / ".codex") / "task-handoffs" / "transfers"


def _state_path(state_root, source_host, source_task):
    key = hashlib.sha256(f"{source_host}\0{source_task}".encode()).hexdigest()
    return state_root / f"{key}.json"


@contextmanager
def _locked(path):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    lock = path.with_suffix(".lock")
    if lock.is_symlink() or path.is_symlink():
        raise TransferError("refusing symlink transfer state")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        if path.is_symlink() or lock.is_symlink():
            raise TransferError("refusing symlink transfer state")
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _read(path):
    if path.is_symlink():
        raise TransferError("refusing symlink transfer state")
    if not path.exists():
        raise TransferError("transfer state does not exist")
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, state):
    data = (json.dumps(state, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    fd, name = tempfile.mkstemp(prefix=".transfer-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        Path(name).unlink(missing_ok=True)


def _bootstrap(state, path):
    helper = shlex.quote(str(Path(__file__).resolve()))
    journal = shlex.quote(str(path))
    prompt = (
        f"Read {state['packet_path']} and verify SHA-256 {state['packet_sha256']}. "
        f"Transfer {state['transfer_id']}. Inspect journal: python3 {helper} inspect --state {journal}. "
        "Check up to 3 times within 30 seconds for ready; if still creating/pending/uncertain, stop. "
        "Verify your actual workspace equals journal expected_workspace, and check packet Git/dirty "
        "facts, exact next action, approvals and Goal limits before work. For a worktree, the "
        "source must first bind expected_workspace from authoritative task readback. "
        "Then ACK using your own actual task/host IDs (replace placeholders): "
        f"python3 {helper} ack --state {journal} "
        f"--transfer-id {shlex.quote(state['transfer_id'])} "
        f"--sha256 {shlex.quote(state['packet_sha256'])} "
        "--workspace YOUR_ACTUAL_WORKSPACE --thread-id YOUR_TASK_ID --host-id YOUR_HOST_ID "
        f"--next-action {shlex.quote(state['next_action'])}. "
        "Do not continue unless ACK succeeds. If files are inaccessible, stop and request a safe copy."
    )
    return prompt


def prepare(*, packet_path, source_host, source_task, source_workspace,
            expected_workspace=None, target_kind="local", project_id=None, starting_ref=None,
            state_root=None):
    packet_path = Path(packet_path).expanduser().resolve(strict=True)
    if not packet_path.is_file():
        raise TransferError("packet path is not a file")
    packet_bytes = packet_path.read_bytes()
    packet = packet_bytes.decode("utf-8")
    digest = hashlib.sha256(packet_bytes).hexdigest()
    host = _required(source_host, "source_host")
    task = _required(source_task, "source_task")
    source = _workspace(source_workspace)
    if target_kind not in ("local", "worktree"):
        raise TransferError("target_kind must be local or worktree")
    if target_kind == "local" and expected_workspace is None:
        raise TransferError("local target needs expected_workspace")
    if target_kind == "worktree":
        _required(project_id, "project_id")
        _required(starting_ref, "starting_ref")
    target = _workspace(expected_workspace) if expected_workspace else None
    transfer_id = hashlib.sha256(f"{host}\0{task}\0{source}\0{digest}".encode()).hexdigest()[:24]
    root = Path(state_root).expanduser().absolute() if state_root else _state_root().absolute()
    path = _state_path(root, host, task)
    proposed = {"transfer_id": transfer_id, "source_host": host, "source_task": task,
                "source_workspace": source, "expected_workspace": target,
                "target_kind": target_kind, "project_id": project_id, "starting_ref": starting_ref,
                "packet_path": str(packet_path), "packet_sha256": digest,
                "next_action": _next_action(packet), "status": "prepared",
                "client_thread_id": None, "thread_id": None, "successor_host": None,
                "ack": None, "error": None, "created_at": _now(),
                "updated_at": None, "acknowledged_at": None}
    proposed["updated_at"] = proposed["created_at"]
    with _locked(path):
        if path.exists():
            state = _read(path)
            for field in ("transfer_id", "source_workspace", "packet_path", "packet_sha256", "next_action", "target_kind", "project_id", "starting_ref"):
                if state[field] != proposed[field]:
                    raise TransferError(f"source already has a different transfer ({field}); reconcile it first")
            if expected_workspace is not None and state["expected_workspace"] != target:
                raise TransferError("source already has a different transfer (expected_workspace); reconcile it first")
        else:
            state = proposed
            _write(path, state)
    return {"state_path": str(path), "state": state, "bootstrap": _bootstrap(state, path),
            "bootstrap_bytes": len(_bootstrap(state, path).encode("utf-8"))}


def change(path, action, *, client_id=None, thread_id=None, host_id=None, error=None,
           transfer_id=None, digest=None, workspace=None, next_action=None):
    path = Path(path).expanduser().absolute()
    with _locked(path):
        state = _read(path)
        old = state["status"]
        if action == "creating":
            if old != "prepared":
                raise TransferError(f"cannot begin creation from {old}; reconcile existing attempt")
            state["status"] = "creating"
        elif action == "pending":
            if old == "pending":
                if client_id == state["client_thread_id"]:
                    return state
                raise TransferError("conflicting queued client ID")
            if old not in ("creating", "uncertain") or not client_id:
                raise TransferError("pending requires creating/uncertain state and client ID")
            state["client_thread_id"] = _required(client_id, "client_id")
            state["status"] = "pending"
        elif action == "ready":
            supplied_thread = _required(thread_id, "thread_id")
            supplied_host = _required(host_id, "host_id")
            supplied_workspace = _workspace(workspace) if workspace else None
            if old == "ready":
                if (supplied_thread == state["thread_id"] and supplied_host == state["successor_host"]
                        and (client_id is None or client_id == state["client_thread_id"])
                        and (supplied_workspace is None or supplied_workspace == state["expected_workspace"])):
                    return state
                raise TransferError("conflicting ready receipt")
            if old not in ("creating", "pending", "uncertain") or not thread_id or not host_id:
                raise TransferError("ready requires creating/pending/uncertain state, real thread ID and host ID")
            if old == "pending" and client_id != state["client_thread_id"]:
                raise TransferError("ready client ID does not match queued transfer")
            if state["expected_workspace"] is None:
                if not supplied_workspace:
                    raise TransferError("worktree ready needs workspace from authoritative readback")
                state["expected_workspace"] = supplied_workspace
            elif supplied_workspace and supplied_workspace != state["expected_workspace"]:
                raise TransferError("ready workspace conflicts with planned target")
            state["thread_id"] = supplied_thread
            state["successor_host"] = supplied_host
            state["status"] = "ready"
        elif action == "uncertain":
            if old != "creating":
                raise TransferError("uncertain requires creating state")
            state["status"] = "uncertain"
            state["error"] = _required(error, "error")
        elif action == "error":
            if old not in ("creating", "pending"):
                raise TransferError("error requires an attempted transfer")
            state["status"] = "error"
            state["error"] = _required(error, "error")
        elif action == "ack":
            if old not in ("ready", "acknowledged"):
                raise TransferError("ACK requires ready state; wait for real thread identity")
            if transfer_id != state["transfer_id"] or digest != state["packet_sha256"]:
                raise TransferError("ACK transfer identity or packet hash mismatch")
            if _required(thread_id, "thread_id") != state["thread_id"] or _required(host_id, "host_id") != state["successor_host"]:
                raise TransferError("ACK caller task or host mismatch")
            if _workspace(workspace) != state["expected_workspace"]:
                raise TransferError("ACK workspace mismatch")
            if _required(next_action, "next_action") != state["next_action"]:
                raise TransferError("ACK next action mismatch")
            actual = hashlib.sha256(Path(state["packet_path"]).read_bytes()).hexdigest()
            if actual != digest:
                raise TransferError("packet changed before ACK")
            ack = {"transfer_id": transfer_id, "packet_sha256": digest,
                   "workspace": _workspace(workspace), "next_action": next_action,
                   "thread_id": thread_id, "host_id": host_id}
            if old == "acknowledged":
                if state["ack"] != ack:
                    raise TransferError("conflicting ACK")
                return state
            state["ack"] = ack
            state["status"] = "acknowledged"
            state["acknowledged_at"] = _now()
        elif action == "verify":
            if old != "acknowledged" or not state.get("ack"):
                raise TransferError("transfer has no validated ACK")
            expected = {"transfer_id": state["transfer_id"], "packet_sha256": state["packet_sha256"],
                        "workspace": state["expected_workspace"], "next_action": state["next_action"],
                        "thread_id": state["thread_id"], "host_id": state["successor_host"]}
            if state["ack"] != expected:
                raise TransferError("ACK fields mismatch")
            if hashlib.sha256(Path(state["packet_path"]).read_bytes()).hexdigest() != state["packet_sha256"]:
                raise TransferError("packet changed after ACK")
            return state
        else:
            raise TransferError(f"unknown action {action}")
        state["updated_at"] = _now()
        _write(path, state)
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prep = sub.add_parser("prepare")
    for arg in ("packet", "source-host", "source-task", "source-workspace"):
        prep.add_argument("--" + arg, required=True)
    prep.add_argument("--expected-workspace")
    prep.add_argument("--target-kind", choices=("local", "worktree"), default="local")
    prep.add_argument("--project-id")
    prep.add_argument("--starting-ref")
    prep.add_argument("--state-root", help="Override stable user-level transfer registry for isolated runs")
    for name in ("inspect", "creating", "pending", "ready", "uncertain", "error", "ack", "verify"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--state", required=True)
        if name == "pending": cmd.add_argument("--client-id", required=True)
        if name == "ready":
            cmd.add_argument("--thread-id", required=True)
            cmd.add_argument("--host-id", required=True)
            cmd.add_argument("--client-id", help="Required to match a pending queued task")
            cmd.add_argument("--workspace", help="Required when an assigned worktree path was unresolved")
        if name in ("uncertain", "error"): cmd.add_argument("--error", required=True)
        if name == "ack":
            for arg in ("transfer-id", "sha256", "workspace", "next-action", "thread-id", "host-id"):
                cmd.add_argument("--" + arg, required=True)
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = prepare(packet_path=args.packet, source_host=args.source_host,
                             source_task=args.source_task, source_workspace=args.source_workspace,
                             expected_workspace=args.expected_workspace, target_kind=args.target_kind,
                             project_id=args.project_id, starting_ref=args.starting_ref,
                             state_root=args.state_root)
        elif args.action == "inspect":
            result = _read(Path(args.state).expanduser().absolute())
        else:
            result = change(args.state, args.action, client_id=getattr(args, "client_id", None),
                            thread_id=getattr(args, "thread_id", None), host_id=getattr(args, "host_id", None),
                            error=getattr(args, "error", None), transfer_id=getattr(args, "transfer_id", None),
                            digest=getattr(args, "sha256", None), workspace=getattr(args, "workspace", None),
                            next_action=getattr(args, "next_action", None))
    except (OSError, UnicodeError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
