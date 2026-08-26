# Compact Handoff Template

Use only sections that affect continuation. Prefer terse bullets, exact identifiers, and command/result pairs over narrative. Do not copy conversation history or large diffs.

# Task Handoff: <short title>

## Objective

- **Outcome:** <exact end state>
- **Done when:** <observable proof or stopping condition>

## Current State

- **Workspace:** <absolute path or named environment>
- **Git:** <branch>; `HEAD <full SHA>`; <clean/dirty and exact changed files>
- **Completed:** <only work supported by evidence>
- **Validation:** `<command>` → <result>; note anything not run
- **Current blocker:** <omit when none>

For non-repository work, replace Git details with the durable system, document, record, or artifact state that controls the next action.

## Decisions and Boundaries

- <decision or convention the successor must preserve>
- <explicit exclusions and out-of-scope work>
- <write/send/deploy/purchase or other external-action authorization boundary>
- <source precedence or currentness rule, only when material>

## Goal Continuity

Include this section only when an unfinished Goal is safe to transfer: the source Goal is paused or blocked and any budgeted Goal has a positive remaining budget, or the user explicitly authorized a positive replacement budget after a budget limit. Do not include it for an active, usage-limited, unauthorized budget-limited, or ambiguous Goal.

- **Status:** <paused, blocked, or explicitly re-budgeted>
- **Objective:** <exact objective>
- **Prior usage:** <reported usage>
- **Remaining token budget:** <positive integer, or unbudgeted>
- **Blocker:** <preserve when blocked>
- **Successor setup:** Call `create_goal` with the exact objective before any other task work. Include `token_budget` only when the source Goal was budgeted, using the positive remaining budget.

## Transfer Gate

Use instead of Goal Continuity when successor creation must stop.

- **Reason:** <active Goal, exhausted budget, usage limit, conflicting state, or unavailable required evidence>
- **Required user action:** <for an active Goal: run `/goal pause`, then rerun `$task-handoff`>
- **Successor created:** no

## Remaining Work

1. <next required step and expected evidence>
2. <later step only if it is already known and material>

## Exact Next Action

<One bounded action or command the successor should perform first. Do not say "review everything" or "continue where we left off.">

## Evidence

- `<stable path, commit, issue, URL, message/document ID, or artifact>` — <what it proves>
- Mark stale or historical evidence explicitly. Never include expiring signed URLs.

## Risks and Unknowns

- **Unverified:** <fact that still needs checking>
- **Risk:** <specific failure mode and stop condition>

## Excluded Context

- <adjacent project, superseded attempt, mistaken chat content, or irrelevant history that must not leak into the successor>
