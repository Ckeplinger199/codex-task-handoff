# Successor Handoff Template

Use only sections relevant to the work. Prefer compact tables or flat bullets over narrative.

## Objective

State the exact outcome the successor owns and what completion means.

## Goal Continuity (only when the source task has an unfinished goal)

- Exact source goal objective
- Source goal status, prior usage, and remaining token budget
- The successor must call `create_goal` with the inherited objective before doing task work
- If budgeted, use the positive remaining budget as `token_budget`; if unbudgeted, omit it
- Preserve any source blocker or status transition as context; do not claim the goal is complete

## Scope And Boundaries

- Included work
- Explicit exclusions
- External-action permissions and gates
- Critical contamination warning

## Confirmed Current State

For each fact, retain the exact identifier, owner, date, status, quantity, specification, value, or location needed to continue. Include the verification date for drift-prone facts.

## Decisions And Conventions

Capture choices that future work must preserve, such as:

- formulas and calculation conventions
- naming or customer-facing wording
- approved substitutions
- source precedence
- delivery, pricing, or margin treatment
- read-only versus authorized writes

## Workstreams

For each active workstream or counterparty:

- current confirmed state
- last material action
- owner/contact
- committed or target date
- exact next action
- blocker or uncertainty

## Numbers And Reconciliation

List itemized quantities, unit values, extended values, subtotals, freight, fees, margin treatment, and final total. Explain every difference from an earlier version.

## Authoritative Sources

List each source used:

1. Stable absolute local path or canonical live URL
2. File/message/document ID and title
3. What the source proves
4. Whether it is current or historical

For email attachments, include both the attachment filename and stable parent-message URL.

## Open Actions

Order by urgency and dependency. Each action should identify the actor, expected evidence, and stop condition.

## Risks And Unknowns

Separate unverified, stale, disputed, and blocked facts. Do not phrase them as confirmed.

## Starting Check

Give the successor one bounded first action that refreshes the most important current state. Keep external systems read-only unless the user already authorized a specific write.
