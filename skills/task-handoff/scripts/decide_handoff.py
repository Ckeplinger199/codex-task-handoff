#!/usr/bin/env python3
"""Conservative, deterministic comparison of staying versus a fresh task.

All token counts are caller forecasts, not Codex telemetry. Rates are optional;
without them the helper cannot make a monetary/unit-cost recommendation.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


class DecisionError(ValueError):
    pass


class MissingData(DecisionError):
    pass


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise DecisionError(f"{label} must be a finite nonnegative number")
    return value


def _usage(value, label):
    if value is None:
        raise MissingData(f"{label} unavailable")
    if not isinstance(value, dict):
        raise DecisionError(f"{label} must be an object")
    fields = ("input_tokens", "cached_input_tokens", "output_tokens")
    if any(field not in value for field in fields):
        raise MissingData(f"{label} needs {', '.join(fields)}")
    result = {field: _number(value[field], f"{label}.{field}") for field in fields}
    if result["cached_input_tokens"] > result["input_tokens"]:
        raise DecisionError(f"{label}.cached_input_tokens exceeds input_tokens")
    return result


def _stages(value, label):
    if value is None or value == []:
        raise MissingData(f"{label} needs forecast stages")
    if not isinstance(value, list):
        raise DecisionError(f"{label} must be a list")
    result = []
    for index, stage in enumerate(value):
        if not isinstance(stage, dict) or "turns" not in stage:
            raise MissingData(f"{label}[{index}] needs turns")
        turns = stage["turns"]
        if isinstance(turns, bool) or not isinstance(turns, int) or turns < 1:
            raise DecisionError(f"{label}[{index}].turns must be a positive integer")
        result.append((turns, _usage(stage, f"{label}[{index}]")))
    return result


def evaluate(data):
    """Return stay/recommend/unknown with explicit breakdown and reasons."""
    if not isinstance(data, dict):
        raise DecisionError("input must be an object")
    boundary = data.get("boundary")
    if not isinstance(boundary, dict):
        raise DecisionError("boundary must be an object")
    required = ("safe", "active_tools", "unresolved_writes", "running_goal", "cooldown_active")
    for field in required:
        if not isinstance(boundary.get(field), bool):
            raise DecisionError(f"boundary.{field} must be boolean")
    status = boundary.get("transfer_status")
    if status not in ("none", "prepared", "creating", "pending", "ready", "acknowledged", "uncertain", "error"):
        raise DecisionError("boundary.transfer_status must be a known state")
    reasons = []
    if not boundary["safe"]:
        reasons.append("No natural safe boundary")
    for field, reason in (("active_tools", "Active tools"), ("unresolved_writes", "Unresolved writes"), ("running_goal", "Running goal"), ("cooldown_active", "Cooldown active")):
        if boundary[field]:
            reasons.append(reason)
    if status != "none":
        reasons.append(f"Existing transfer: {status}")

    observed = data.get("observed")
    if observed is not None:
        try:
            _usage(observed, "observed")
        except MissingData:
            return {"decision": "stay" if reasons else "unknown", "reasons": reasons or ["Observed usage incomplete"], "estimated": None}
    forecast = data.get("forecast")
    rates = data.get("rates_per_million")
    if forecast is None or rates is None:
        return {"decision": "stay" if reasons else "unknown", "reasons": reasons or ["Forecast or rates unavailable"], "estimated": None}
    if not isinstance(forecast, dict) or not isinstance(rates, dict):
        raise DecisionError("forecast and rates_per_million must be objects")
    for field in ("input", "cached_input", "output"):
        if field not in rates:
            return {"decision": "stay" if reasons else "unknown", "reasons": reasons or [f"rates_per_million.{field} unavailable"], "estimated": None}
        _number(rates[field], f"rates_per_million.{field}")
    if not isinstance(data.get("rate_unit"), str) or not data["rate_unit"].strip():
        return {"decision": "stay" if reasons else "unknown", "reasons": reasons or ["Rate unit unavailable"], "estimated": None}
    try:
        stay = _stages(forecast.get("stay"), "forecast.stay")
        fresh = _stages(forecast.get("fresh"), "forecast.fresh")
        transfer = _usage(forecast.get("transfer"), "forecast.transfer")
        recovery = _usage(forecast.get("recovery"), "forecast.recovery")
    except MissingData as exc:
        return {"decision": "stay" if reasons else "unknown", "reasons": reasons or [str(exc)], "estimated": None}
    if sum(n for n, _ in stay) != sum(n for n, _ in fresh):
        raise DecisionError("stay and fresh must forecast the same number of turns")
    def cost(usage):
        return ((usage["input_tokens"] - usage["cached_input_tokens"]) * rates["input"]
                + usage["cached_input_tokens"] * rates["cached_input"]
                + usage["output_tokens"] * rates["output"]) / 1_000_000
    stay_cost = sum(n * cost(u) for n, u in stay)
    fresh_work = sum(n * cost(u) for n, u in fresh)
    transfer_cost = cost(transfer)
    recovery_cost = cost(recovery)
    fresh_cost = fresh_work + transfer_cost + recovery_cost
    savings = stay_cost - fresh_cost
    margin = _number(data.get("minimum_savings_percent", 10), "minimum_savings_percent")
    min_units = _number(data.get("minimum_savings_units", 0), "minimum_savings_units")
    threshold = max(min_units, stay_cost * margin / 100)
    estimated = {"rate_unit": data["rate_unit"], "horizon_turns": sum(n for n, _ in stay),
                 "stay": stay_cost, "fresh_work": fresh_work, "transfer": transfer_cost,
                 "recovery": recovery_cost, "fresh_total": fresh_cost, "savings": savings,
                 "required_savings": threshold}
    if reasons:
        decision = "stay"
    elif savings <= threshold:
        decision = "stay"
        reasons.append("Estimated savings do not exceed margin")
    else:
        decision = "recommend"
        reasons.append("Estimated savings exceed margin at a safe boundary")
    return {"decision": decision, "reasons": reasons, "estimated": estimated,
            "note": "Forecast comparison only; no measured savings or subscription usage percentage"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="-", help="JSON file or - for stdin")
    args = parser.parse_args()
    try:
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        result = evaluate(json.loads(raw))
    except (OSError, ValueError, DecisionError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
