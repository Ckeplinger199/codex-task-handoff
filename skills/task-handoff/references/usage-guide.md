# Usage and transfer guide

## Cost decision input

Resolve `<skill-dir>` from the loaded SKILL.md location; it must be an absolute path. Run `python3 "<skill-dir>/scripts/decide_handoff.py" example.json`. Supply a short horizon and forecasts in one declared rate unit, using the same model and billing rate basis for both paths. If the successor's model or billing basis is different or unknown, this single-rate comparison cannot support a recommendation. `cached_input_tokens` is a subset of `input_tokens`. Stages let the first resumed turn differ from later turns; do not apply a cold first-turn rate to the entire horizon. Include fixed instructions and tool overhead in each relevant forecast stage, packet generation, bootstrap and packet read in `transfer`, and expected repeated work in `recovery`. `observed` is optional context and does not substitute for a forecast. No model rates or cache lifetime are hardcoded.

```json
{
  "rate_unit": "illustrative units",
  "rates_per_million": {"input": 1, "cached_input": 0.1, "output": 5},
  "boundary": {
    "safe": true, "active_tools": false, "unresolved_writes": false,
    "running_goal": false, "cooldown_active": false, "transfer_status": "none"
  },
  "observed": {"input_tokens": 100000, "cached_input_tokens": 90000, "output_tokens": 2000},
  "forecast": {
    "stay": [
      {"turns": 1, "input_tokens": 100000, "cached_input_tokens": 0, "output_tokens": 2000},
      {"turns": 3, "input_tokens": 100000, "cached_input_tokens": 90000, "output_tokens": 2000}
    ],
    "fresh": [
      {"turns": 1, "input_tokens": 8000, "cached_input_tokens": 0, "output_tokens": 2000},
      {"turns": 3, "input_tokens": 8000, "cached_input_tokens": 6000, "output_tokens": 2000}
    ],
    "transfer": {"input_tokens": 100000, "cached_input_tokens": 90000, "output_tokens": 2000},
    "recovery": {"input_tokens": 13000, "cached_input_tokens": 0, "output_tokens": 0}
  },
  "minimum_savings_percent": 10
}
```

The result is `stay`, `recommend`, or `unknown`, with reasons and a cost breakdown. A recommendation is not permission to create a task. Missing cost inputs remain `unknown`. Boundary checks block transfer even if the cost estimate is attractive. Cooldown can be derived from a prior journal's `acknowledged_at` UTC timestamp and supplied to the evaluator; there is no global monitor. Rate estimates do not describe subscription usage percentage. This three-rate estimator does not separately model cache-write surcharges or tool fees; if those differ between paths and are not represented in the supplied effective rates, do not use its result as a full-cost recommendation.

## Transfer journal

After storing the Markdown packet with `store_handoff.py`, prepare a source-bound journal before calling any task tool. For the explicitly chosen same checkout:

```sh
python3 "<skill-dir>/scripts/transfer_handoff.py" prepare \
  --packet /absolute/packet.md --source-host HOST --source-task TASK \
  --source-workspace /absolute/source --target-kind local \
  --expected-workspace /absolute/source
python3 "<skill-dir>/scripts/transfer_handoff.py" creating --state /absolute/journal.json
```

For a worktree whose path is assigned after creation, prepare with `--target-kind worktree --project-id <exact ID> --starting-ref <exact source ref>` and omit `--expected-workspace`. The source must bind the assigned path from authoritative task readback using `ready --workspace <actual path>` before ACK. If that path cannot be read, leave the transfer pending. The helper keeps one journal per source host/task in `$CODEX_HOME/task-handoffs/transfers` or `~/.codex/task-handoffs/transfers`, regardless of packet directory. `--state-root` is an override for isolated tests.

Use the returned transfer bootstrap in a single authorized `create_thread` call. Record its actual response with `ready --state ... --thread-id ... --host-id ...` or `pending --state ... --client-id ...`. When resolving pending, pass the same `--client-id` to `ready`. If creation's outcome is unclear, record `uncertain --state ... --error ...`; reconcile a later authoritative receipt without a second create call. Identical provider receipts can be replayed safely; conflicting IDs are rejected. A queued client ID cannot be passed to read or wait tools. Resolve it through authoritative app state. A title-only match cannot prove identity.

The bootstrap contains the absolute helper path and a complete `inspect`/`ack` command outline. The successor reads and hashes the packet, verifies Git and dirty state, actual workspace, Goal limits and transfer identity, checks the journal up to three times in 30 seconds for `ready`, then writes `ack --state ... --transfer-id ... --sha256 ... --workspace ... --next-action ... --thread-id <own real ID> --host-id <own host ID>` before carrying out the action. The source checks `verify --state ...`; identical ACK replay is safe. Journal `created_at`, `updated_at`, and `acknowledged_at` are UTC. These are local protocol steps, not provider readback. A remote or cloud successor that cannot read the local packet must stop; copy a safe packet through an explicitly reachable channel instead.

If the successor stopped after its bounded startup wait, first establish `ready` from authoritative readback. Then use the available follow-up-message tool on that same verified task ID to ask it to recheck the journal and perform the existing bootstrap. Send this once only when startup was the blocker; do not create another task or restart completed work. If follow-up tools are unavailable, return a copy-ready continuation for that exact task.

## Compare with native compaction

For a real savings claim, compare equivalent completed work on three runs: ordinary continuation, native compaction where the runtime supports it, and fresh handoff. Record actual input, cached input and output usage per turn, transfer creation/packet-read work, wall time, recovery/repeated work, and final result quality. Keep the same objective and stopping proof. Distinguish measurements from forecast, and include unsuccessful or pending transfers. Native compaction in an owned App Server integration is a possible future route; this desktop skill cannot call private compaction or cache telemetry merely because those APIs exist elsewhere. Do not copy opaque compaction state or hidden reasoning into packets.
