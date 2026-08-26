# Codex Task Handoff

A compact Codex skill for moving a long or contaminated task into a clean successor without replaying the entire conversation.

The skill records the minimum sufficient state in a private, content-addressed handoff file, starts a successor with a sub-1,000-byte bootstrap prompt when Codex task tools are available, verifies startup once, and leaves the original task available as an audit trail.

## Why this version works

The earlier version tried to pass the full handoff directly into task creation and depended on task controls that current Codex does not expose. This version follows the current task-tool contract:

- `create_thread` receives only a compact bootstrap and inherits the current workspace/project and model by default.
- The full handoff lives in a durable local file, so successor creation stays below the prompt-size limit.
- There is no dependency on project-selection, pin/unpin, or reasoning-effort arguments.
- Thread creation happens once, startup verification happens once, and failures do not trigger blind duplicate retries.
- An active Goal must be paused before transfer, preventing the source and successor from burning tokens on the same objective at once.
- Budget- or usage-limited Goals are never silently restarted without their limit.

## Install

In Codex, invoke `$skill-installer` and ask it to install:

- repository: `Ckeplinger199/codex-task-handoff`
- path: `skills/task-handoff`

Codex discovers newly installed skills automatically. Restart Codex only if the skill does not appear.

## Use

```text
$task-handoff Roll this task into a clean successor and continue from the exact next action.
```

For a packet without creating a new task:

```text
$task-handoff Create a compact handoff artifact only; do not create or rename any task.
```

For a parallel branch that should retain the same history, use a fork instead of this skill.

When the source task has an active Goal, the skill intentionally stops after creating the durable artifact. Run `/goal pause`, then invoke `$task-handoff` again. This is a safety feature: current Goal tools can read or complete/block a Goal, but they cannot safely pause the calling Goal on the user's behalf.

## Behavior

- Captures objective, current state, exact Git/workspace facts, completed work, validation, boundaries, remaining work, and one exact next action.
- Reads live systems only when a drift-prone fact would materially change the continuation.
- Preserves safely transferable unfinished Goal state when Goal tools are available.
- Stores handoffs under `$CODEX_HOME/task-handoffs` or `~/.codex/task-handoffs` with private file permissions.
- Falls back to a copy-ready bootstrap prompt when task-management tools are unavailable or a transfer gate is active.
- Never archives/hides the calling task and never renames it before the successor is confirmed.

## Repository layout

- `skills/task-handoff/SKILL.md` — operating instructions and safety gates
- `skills/task-handoff/references/handoff-template.md` — minimum-sufficient state template
- `skills/task-handoff/scripts/store_handoff.py` — atomic private storage and bootstrap generation
- `skills/task-handoff/agents/openai.yaml` — Codex UI metadata and invocation policy
- `tests/` — helper and runtime-contract regression tests
