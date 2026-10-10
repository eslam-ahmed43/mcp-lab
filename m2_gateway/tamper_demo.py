import json
import sys
from pathlib import Path

REAL = Path(__file__).parent / "audit.jsonl"

path = Path(sys.argv[1])
mode = sys.argv[2]
if path.resolve() == REAL.resolve():
    raise SystemExit("refusing to modify the real audit log")
lines = path.read_bytes().splitlines(keepends=True)
if mode == "truncate":
    lines = lines[:-1]
elif mode == "modify":
    for index, raw in enumerate(lines):
        entry = json.loads(raw)
        if entry.get("seq") == 2:
            entry["outcome"] = "tampered"
            ending = b"\r\n" if raw.endswith(b"\r\n") else b"\n"
            lines[index] = json.dumps(entry).encode("ascii") + ending
else:
    raise SystemExit("mode must be modify or truncate")
path.write_bytes(b"".join(lines))
