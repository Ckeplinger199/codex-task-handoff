# Codex Task Handoff

A local, skill-assisted way to compare a fresh Codex task with staying in the current one, then prepare a compact continuation when the user asks for it. It is a skill and three standard-library Python helpers; it does not monitor the desktop, intercept compaction, create tasks in the background, or guarantee cache visibility. The transfer journal uses POSIX `fcntl` locking on macOS and Linux.

The packet holds a small current-state capsule and stable references. A private journal records one transfer per source task before creation, distinguishes queued client IDs from real task IDs, and requires a successor ACK before the source calls the transfer complete. Original tasks remain intact. The skill uses the current task API schema and checks destination access and Git state before task creation.

## Install and invoke

Install `skills/task-handoff` with Codex's skill installer. To request a fresh task:

```text
$task-handoff Roll this task into a clean successor and continue from the exact next action.
```

For a successor in this exact saved project checkout, say so explicitly:

```text
$task-handoff Continue this task in a fresh task using this same saved project checkout and its current dirty files.
```

For just the packet:

```text
$task-handoff Create a compact handoff artifact only.
```

The skill's 1,000-byte bootstrap target is a local concision choice, not a platform prompt limit. Packet byte counts are real; token counts are estimates. Local files are not assumed accessible from another host or cloud task. No hidden reasoning, secrets, raw transcripts, or expiring signed URLs belong in a packet.

## Usage and verification

See the [installable usage guide](skills/task-handoff/references/usage-guide.md) for the decision JSON format, transfer commands, recovery procedure, and comparison protocol. The guide ships with the skill.

## Development

No third-party packages are required. Run `python3 -m unittest discover -s tests -v`. CI uses the same discovery command on Python 3.12.
