import asyncio
import json
import sys
import time
from pathlib import Path

from agent import model_name, run_agent
from eval_scenarios import SCENARIOS

SYSTEM = (
    "You manage a shared task list for a team. Use the provided tools to do what "
    "the user asks, then answer briefly."
)
RESULTS = Path(__file__).parent.parent / "docs" / "eval_results.json"


def args_match(expected: dict, actual: dict) -> bool:
    for key, value in expected.items():
        got = actual.get(key)
        if isinstance(value, str):
            if value.lower() not in str(got or "").lower():
                return False
        elif got != value:
            return False
    return True


async def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    model = model_name()
    records = []
    for scenario in SCENARIOS:
        for index in range(runs):
            try:
                outcome = await run_agent(scenario["token"], scenario["prompt"], SYSTEM)
            except Exception as exc:
                outcome = {"calls": [], "final": f"[agent error: {exc}]"}
            calls = outcome["calls"]
            first = calls[0] if calls else None
            tool_ok = first is not None and first["tool"] == scenario["tool"]
            args_ok = tool_ok and args_match(scenario["args"], first["args"])
            records.append(
                {
                    "scenario": scenario["id"],
                    "run": index + 1,
                    "expected_tool": scenario["tool"],
                    "first_tool": first["tool"] if first else None,
                    "tool_ok": tool_ok,
                    "args_ok": args_ok,
                    "steps": len(calls),
                    "first_call_ok": bool(first and first["ok"]),
                    "calls": [
                        {"tool": c["tool"], "args": c["args"], "ok": c["ok"]} for c in calls
                    ],
                    "final": outcome["final"][:300],
                }
            )
            mark = "PASS" if args_ok else "FAIL"
            print(
                f"{mark} {scenario['id']} run {index + 1}: expected {scenario['tool']}, "
                f"got {records[-1]['first_tool']}, steps {len(calls)}"
            )
            if not args_ok:
                print("   final:", records[-1]["final"])
            await asyncio.sleep(2)
    total = len(records)
    summary = {
        "model": model,
        "runs_per_scenario": runs,
        "total": total,
        "tool_selection_accuracy": sum(r["tool_ok"] for r in records) / total,
        "argument_accuracy": sum(r["args_ok"] for r in records) / total,
    }
    print()
    print(json.dumps(summary, indent=2))
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(
        json.dumps(
            {"summary": summary, "records": records, "ts": time.time()}, indent=2
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
