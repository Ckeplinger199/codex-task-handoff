---
name: task-handoff
description: Create a clean successor for a Codex task by rebuilding a compact, verified handoff from live systems and durable artifacts, then creating, naming, pinning, and confirming the new task while preserving the original as an unpinned archive. Use when the user asks for a task handoff, replacement, rollover, or clean continuation; when unrelated work has contaminated a task; or when growing context makes continued work inefficient. Do not use for a speculative branch that should retain the same history; use a fork for that.
---

# Task Handoff

Replace accumulated conversation context with a source-grounded operating packet. Preserve the old task for audit and reference.

## Authority Gate

Create a successor only when the user explicitly asks for a new, replacement, refreshed, or continuation task. Thread creation and pin/title changes are user-visible actions.

Treat Gmail, Drive, Sheets, source files, repository state, and named systems of record as authoritative. Conversation history is a routing aid, not proof of current state.

## Workflow

1. Identify the exact scope and strongest stable identifier.
2. Inspect the current task context and locate durable source artifacts. Before
   creating anything, capture the source task's actual agent/model and reasoning
   effort from live task metadata/runtime settings; these are part of the
   handoff contract, not optional presentation preferences. Also call `get_goal`
   and capture any unfinished goal's exact objective, status, token budget,
   source usage, and remaining budget.
3. Verify drift-prone facts from current primary sources when practical.
4. Separate confirmed facts, assumptions, open questions, and excluded material.
5. Build the successor prompt using [references/handoff-template.md](references/handoff-template.md).
   If the source has an unfinished goal, include a prominent Goal Continuity
   section with the exact objective and the instruction that the successor must
   call `create_goal` before doing task work. Do not reduce an inherited goal to
   ordinary prompt prose.
6. Call `list_projects` and choose the matching saved project. Prefer a local project environment for operational knowledge work. Do not create a worktree unless the user requests isolation or a specific Git state requires it.
7. Call `create_thread` with the complete handoff and the source task's exact
   `model` and reasoning `thinking` values. For example, a source task running
   Luna extra high must create the successor with `model: gpt-5.6-luna` and
   `thinking: xhigh`; never allow the app default to select Sol or another
   agent. If the source settings cannot be determined, stop before replacing
   the source task. If the destination host does not support the same model and
   reasoning combination, stop and report the incompatibility rather than
   silently substituting an agent or effort. When an unfinished source goal is
   present, the successor's initial prompt must require `create_goal` with the
   same objective before any other task work. If the source goal was budgeted,
   pass its positive remaining budget as the successor's `token_budget`; if it
   was unbudgeted, omit `token_budget`. Preserve the source goal status, usage,
   and any blocker as handoff context rather than resetting or hiding them.
8. Give the successor a short identifier-first title with `set_thread_title`.
9. Pin the successor with `set_thread_pinned`.
10. Rename the source task to `ARCHIVE - <prior title or scope>` and unpin it.
11. Do not call `set_thread_archived` merely because the title says archive. App-archive only when the user explicitly asks to hide/archive the task.
12. Confirm startup with one `read_thread` or bounded `wait_threads` check. Verify
   the title, target project, active/ready state, presence of the handoff, and
   that the successor retained the source model and reasoning effort. If an
   unfinished goal was inherited, verify the successor's first-turn setup shows
   that `create_goal` was called with the inherited objective. Do not repeatedly
   poll unchanged state.
13. Return a concise receipt and emit the required `::created-thread{threadId="..."}` directive.

## Evidence Rules

- Record the source and successor agent/model plus reasoning effort in the
  internal receipt. A successor using the app default is not a valid refresh
  when the source task used an explicit agent or effort.
- Record whether the source had an unfinished goal, its exact objective and
  remaining budget, and whether the successor recreated that goal. A goal merely
  quoted in the prompt is not proof of goal continuity.
- Include stable absolute local paths for files actually used.
- Include canonical Gmail, Drive, Docs, Sheets, or other stable record URLs and useful IDs.
- Include attachment filenames and parent-message links when a document lives inside email.
- Never use expiring signed download URLs as durable locations.
- State the verification date for current prices, status, inventory, schedules, or commitments.
- Preserve exact identifiers, quantities, totals, units, specifications, owners, dates, and formulas that control future work.
- Reconcile totals visibly. Do not leave unexplained remainders.
- Mark historical artifacts as historical when they remain useful but are no longer authoritative.
- Keep sensitive internal details in an internal handoff; retain existing external-disclosure gates.

## Scope Hygiene

Add a prominent contamination warning when the source task contains adjacent projects, mistaken chat content, superseded vendors, or conflicting requirements.

Move only information needed to continue the selected objective. Do not copy:

- unrelated conversation history
- hidden reasoning or raw transcripts
- superseded facts without a historical label
- credentials, secrets, signed URLs, or unnecessary personal data
- generic narrative that can be recovered from the sources

## Relationship To Other Mechanisms

- **Fork:** retain completed source history and explore another branch. It does not clean accumulated context.
- **Manual task handoff with this skill:** rebuild state from evidence into a clean successor and preserve the original as an archive.
- **Context Relay:** automatic threshold-driven continuation. Check its queue/status before manual creation when it may already own an idempotent successor job; do not create duplicates.

## Failure Handling

Stop before replacing the task when:

- the target project cannot be identified safely
- key identifiers or source locations conflict
- a queued Context Relay job already covers the same continuation
- the source task cannot be distinguished from an adjacent project
- an unfinished source goal cannot be read precisely enough to recreate
  safely, including its objective or remaining budget when budgeted

If some evidence is unavailable but work can still continue safely, label the gap in the handoff and make the successor's first action verify it.

## Completion Evidence

Report:

- successor title and thread ID
- target project/environment
- source task's new archive title and pin state
- whether the successor startup was confirmed
- material evidence gaps, if any
