---
name: task-handoff
description: Create a compact, evidence-backed handoff so the current Codex task can continue in a fresh thread without rereading the full conversation. Use when the user asks to hand off, roll over, refresh, replace, or cleanly continue a long or contaminated task, especially to reduce context or token waste. Do not use for an ordinary summary or a speculative branch that should retain the same history; use a fork for that.
---

# Task Handoff

Move only the minimum sufficient state into a clean continuation. The handoff should let the successor act immediately without replaying the source conversation.

## Non-negotiables

- Do not summarize the whole chat. Include only facts that change the successor's decisions or next action.
- Do not re-read broad source sets merely to make the handoff feel comprehensive. Verify only drift-prone or ambiguous facts that could make the next action wrong.
- Preserve the user's scope, exclusions, approvals, and external-action gates. A handoff never expands authority.
- Never copy credentials, secrets, signed URLs, hidden reasoning, or raw transcripts.
- Use only tools that are actually available. Do not invent project selection, pinning, reasoning-effort, or thread-directive controls.
- Use `fork_thread` when the user wants a parallel branch with inherited history. A fork is not a context reset.
- Never leave two active Goal loops pursuing the same objective.

## Choose the mode

**Artifact only:** Use when the user asks for a handoff packet but has not explicitly asked to create a new task, when task-management tools are unavailable, or when a Goal transfer gate blocks safe successor creation.

**Fresh successor:** Use when the user explicitly asks to replace, roll over, refresh, or continue in a new task; `create_thread` is available; and no Goal transfer gate is active.

**Fork:** Use when the user asks to branch, compare approaches, or preserve the same history. Do not run the clean-handoff workflow unless they also ask for a compact state packet.

## Workflow

1. State the exact objective, completion condition, and one exact next action.
2. Capture current durable state with the fewest useful reads:
   - For repository work, record the absolute workspace path, branch, exact `HEAD`, concise working-tree status, changed files, and validation already run. Reference large diffs instead of copying them.
   - Call `get_goal` once when that tool is available. Record an unfinished Goal's exact objective, status, usage, remaining token budget, and blocker. Do not infer a Goal when none exists.
   - Read external systems only when the active task depends on a fact whose current value materially affects the next action.
3. Classify Goal transfer safety before creating another task:
   - **No Goal or complete:** continue normally.
   - **Active:** write the artifact, but do not call `create_thread` and do not rename the source. Return the exact instruction `/goal pause`, plus a copy-ready rerun request. The source Goal must be paused before transfer so it cannot continue alongside the successor.
   - **Paused or blocked:** transfer is allowed. Add `## Goal Continuity` with the exact objective and status. Preserve the blocker. If the Goal was budgeted, transfer only its positive remaining budget; if unbudgeted, omit `token_budget`.
   - **Budget-limited, usage-limited, or budgeted with no positive remaining budget:** write the artifact, but do not create a successor Goal or silently remove the limit. Stop until the user explicitly authorizes a new/increased budget or the usage limit clears.
   - **Missing or conflicting Goal fields:** use artifact-only mode and name the gap. Do not guess.
4. Write the packet using [references/handoff-template.md](references/handoff-template.md). Omit empty sections. Target 350-900 words; exceed 1,500 words only when exact technical state genuinely requires it.
5. Resolve this skill's directory from the loaded `SKILL.md` path. Create the temporary packet with `mktemp` outside the workspace, store it with `scripts/store_handoff.py`, then remove the temporary file. Do not assume a fixed skill-install location.

   ```bash
   packet="$(mktemp)"
   # Write the completed packet to "$packet".
   python3 "<skill-dir>/scripts/store_handoff.py" \
     --title "<short scope title>" \
     --cwd "$PWD" \
     --input "$packet"
   rm -f "$packet"
   ```

   The script writes atomically to a private per-workspace directory under `$CODEX_HOME/task-handoffs` or `~/.codex/task-handoffs`, validates the packet, and returns JSON containing the absolute path, SHA-256 digest, and a bootstrap prompt. Use `--workspace-local` only when the successor cannot access the user-level store; never stage or commit that local handoff unless the user explicitly asks.
6. Treat the returned bootstrap prompt as the complete successor prompt. Do not paste the full packet into `create_thread`.
7. For a fresh successor:
   - Call `create_thread` exactly once with the bootstrap prompt and a short identifier-first title.
   - Omit `model` unless the user explicitly requested an override. Current Codex task creation inherits the source workspace/project and current model; do not pass unsupported fields such as `thinking`.
   - Do not call nonexistent project-selection or pinning tools.
   - Confirm startup with one bounded `read_thread` call, or one immediate `wait_threads` snapshot when reading is unavailable. Verify the thread ID, title, workspace, status, and that the bootstrap references the exact handoff path. Do not poll unchanged state.
   - Only after confirmation, rename the source task to `ARCHIVE — <short scope>` with `set_thread_title` while omitting `threadId`. Do not app-archive or hide the calling task.
8. When the packet contains `## Goal Continuity`, the bootstrap must tell the successor to call `create_goal` with the exact objective before other task work. Pass `token_budget` only for a previously budgeted Goal with a positive recorded remainder. The handoff file, not ordinary prose memory, is the source of truth for those values.
9. If successor creation fails, do not retry blindly. Leave the source title/archive state unchanged, preserve the handoff artifact, and return the exact failure plus the copy-ready bootstrap prompt.

## Quality bar

A good handoff contains enough evidence to continue, but no generic history. It must distinguish confirmed state from unknowns, identify completed work without claiming unverified success, preserve exact file/commit/test facts, and end with one executable next action.

## Completion receipt

Report only:

- handoff title, absolute path, and SHA-256 prefix
- successor thread ID and startup status, when created
- source rename/archive state, when changed
- Goal continuity or transfer-gate status, when applicable
- material evidence gaps or the exact creation failure
