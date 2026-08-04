# Codex Task Handoff

A standalone Codex skill for moving a large or contaminated task into a clean successor task with a compact, verified handoff.

## Install

Install the skill from this repository with Codex's skill installer:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo Ckeplinger199/codex-task-handoff \
  --path skills/task-handoff
```

Then invoke it with:

```text
Use $task-handoff to replace this task with a verified fresh handoff.
```

## What it does

- Rebuilds the active state from live systems and durable artifacts.
- Separates confirmed facts, assumptions, open questions, and exclusions.
- Creates, names, pins, and verifies a clean successor task.
- Preserves the original task as an unpinned archive for reference.

The skill is intentionally read-only until the user explicitly authorizes the successor-task action. It does not replace a fork when the goal is to preserve the same history for a separate branch of work.

## Contents

The installable skill lives at [`skills/task-handoff/`](skills/task-handoff/):

- `SKILL.md` — operating instructions and safety gates
- `agents/openai.yaml` — Codex UI metadata
- `references/handoff-template.md` — compact successor handoff template
