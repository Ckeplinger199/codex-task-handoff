from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/task-handoff/scripts/decide_handoff.py"
spec = importlib.util.spec_from_file_location("decide_handoff", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def usage(input_tokens, cached=0, output=0, turns=1):
    return {"turns": turns, "input_tokens": input_tokens,
            "cached_input_tokens": cached, "output_tokens": output}


def sample():
    return {"rate_unit": "test units", "rates_per_million": {"input": 1, "cached_input": .1, "output": 5},
            "boundary": {"safe": True, "active_tools": False, "unresolved_writes": False,
                         "running_goal": False, "cooldown_active": False, "transfer_status": "none"},
            "forecast": {"stay": [usage(100000, 90000, 2000)],
                         "fresh": [usage(8000, 0, 2000)],
                         "transfer": usage(100000, 90000, 2000),
                         "recovery": usage(13000)}}


class DecisionTests(unittest.TestCase):
    def test_warm_cache_and_transfer_overhead_favor_stay(self):
        result = module.evaluate(sample())
        self.assertEqual(result["decision"], "stay")
        self.assertGreater(result["estimated"]["fresh_total"], result["estimated"]["stay"])

    def test_cold_first_turn_and_warm_later_can_favor_fresh(self):
        data = sample()
        data["forecast"]["stay"] = [usage(100000, 0, 2000), usage(100000, 90000, 2000, 11)]
        data["forecast"]["fresh"] = [usage(8000, 0, 2000), usage(8000, 6000, 2000, 11)]
        result = module.evaluate(data)
        self.assertEqual(result["decision"], "recommend")
        self.assertEqual(result["estimated"]["horizon_turns"], 12)
        self.assertGreater(result["estimated"]["savings"], result["estimated"]["required_savings"])

    def test_missing_forecast_is_unknown_and_invalid_cache_is_rejected(self):
        data = sample()
        del data["forecast"]
        self.assertEqual(module.evaluate(data)["decision"], "unknown")
        data = sample()
        del data["rates_per_million"]["cached_input"]
        self.assertEqual(module.evaluate(data)["decision"], "unknown")
        data = sample()
        del data["forecast"]["transfer"]["output_tokens"]
        self.assertEqual(module.evaluate(data)["decision"], "unknown")
        data = sample()
        data["forecast"]["stay"][0]["cached_input_tokens"] = 100001
        with self.assertRaisesRegex(module.DecisionError, "exceeds"):
            module.evaluate(data)

    def test_recovery_can_reverse_recommendation(self):
        data = sample()
        data["forecast"]["stay"] = [usage(100000, 0, 2000), usage(100000, 90000, 2000, 11)]
        data["forecast"]["fresh"] = [usage(8000, 0, 2000), usage(8000, 6000, 2000, 11)]
        self.assertEqual(module.evaluate(data)["decision"], "recommend")
        data["forecast"]["recovery"] = usage(5000000)
        self.assertEqual(module.evaluate(data)["decision"], "stay")

    def test_boundary_blocks_even_attractive_cost(self):
        data = sample()
        data["forecast"]["stay"] = [usage(1000000)]
        for field in ("safe", "active_tools", "unresolved_writes", "running_goal", "cooldown_active"):
            case = deepcopy(data)
            case["boundary"][field] = False if field == "safe" else True
            self.assertEqual(module.evaluate(case)["decision"], "stay", field)
        data["boundary"]["transfer_status"] = "pending"
        self.assertEqual(module.evaluate(data)["decision"], "stay")

    def test_cli_emits_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            path.write_text(json.dumps(sample()), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("decision", json.loads(proc.stdout))


if __name__ == "__main__":
    unittest.main()
