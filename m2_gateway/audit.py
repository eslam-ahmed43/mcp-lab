import json
import time
from pathlib import Path

AUDIT_PATH = Path(__file__).parent / "audit.jsonl"


def record(user: str, tool: str, arguments: dict, decision: str, outcome: str) -> None:
    entry = {
        "ts": time.time(),
        "user": user,
        "tool": tool,
        "arguments": arguments,
        "decision": decision,
        "outcome": outcome,
    }
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")