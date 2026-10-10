import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

AUDIT_PATH = Path(os.environ.get("MCP_AUDIT_PATH") or Path(__file__).parent / "audit.jsonl")
GENESIS = "0" * 64
ALG_PLAIN = "sha256"
ALG_KEYED = "hmac-sha256"


def _key() -> bytes | None:
    value = os.environ.get("MCP_AUDIT_KEY", "")
    return value.encode("utf-8") if value else None


def _digest(key: bytes | None, data: bytes) -> str:
    if key is None:
        return hashlib.sha256(data).hexdigest()
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def _canonical(entry: dict) -> bytes:
    text = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return text.encode("ascii")


def _anchor(legacy: bytes) -> str:
    return hashlib.sha256(legacy).hexdigest() if legacy else GENESIS


def _read_lines() -> list[bytes]:
    if not AUDIT_PATH.exists():
        return []
    return AUDIT_PATH.read_bytes().splitlines(keepends=True)


def _parse(line: bytes) -> dict | None:
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    return entry if isinstance(entry, dict) else None


def _tail(lines: list[bytes]) -> dict | None:
    last = None
    for line in lines:
        entry = _parse(line)
        if entry is not None and "hash" in entry:
            last = entry
    return last


def record(user: str, tool: str, arguments: dict, decision: str, outcome: str) -> None:
    lines = _read_lines()
    last = _tail(lines)
    if last is None:
        prev = _anchor(b"".join(lines))
        seq = 1
    else:
        prev = last["hash"]
        seq = int(last.get("seq", 0)) + 1
    key = _key()
    entry = {
        "seq": seq,
        "ts": time.time(),
        "user": user,
        "tool": tool,
        "arguments": arguments,
        "decision": decision,
        "outcome": outcome,
        "alg": ALG_KEYED if key else ALG_PLAIN,
        "prev": prev,
    }
    entry["hash"] = _digest(key, _canonical(entry))
    line = json.dumps(entry, ensure_ascii=True).encode("ascii") + b"\n"
    with AUDIT_PATH.open("ab") as handle:
        handle.write(line)


def head() -> dict | None:
    last = _tail(_read_lines())
    return {"seq": last["seq"], "hash": last["hash"]} if last else None


def _fail(result: dict, line: int | None, problem: str) -> dict:
    result["ok"] = False
    result["line"] = line
    result["problem"] = problem
    return result


def verify(anchor: str | None = None) -> dict:
    lines = _read_lines()
    key = _key()
    result = {
        "ok": True,
        "legacy_lines": 0,
        "entries": 0,
        "line": None,
        "problem": None,
        "head": None,
    }
    legacy = []
    chained = []
    for number, raw in enumerate(lines, start=1):
        entry = _parse(raw)
        if entry is None:
            return _fail(result, number, "line is not valid JSON")
        if "hash" in entry:
            chained.append((number, entry))
        elif chained:
            return _fail(result, number, "unchained line after the chain started")
        else:
            legacy.append(raw)
    result["legacy_lines"] = len(legacy)
    prev = _anchor(b"".join(legacy))
    seen_keyed = False
    for expected_seq, (number, entry) in enumerate(chained, start=1):
        if entry.get("seq") != expected_seq:
            return _fail(
                result,
                number,
                f"sequence gap or reorder: expected {expected_seq}, found {entry.get('seq')}",
            )
        if entry.get("prev") != prev:
            return _fail(
                result,
                number,
                "previous hash mismatch: an earlier entry was changed, removed or reordered",
            )
        alg = entry.get("alg")
        if alg not in (ALG_PLAIN, ALG_KEYED):
            return _fail(result, number, f"unknown algorithm {alg!r}")
        if alg == ALG_KEYED:
            seen_keyed = True
            if key is None:
                return _fail(result, number, "entry is keyed: set MCP_AUDIT_KEY to verify")
        elif seen_keyed:
            return _fail(result, number, "downgrade: a plain entry follows keyed entries")
        body = {k: v for k, v in entry.items() if k != "hash"}
        expected = _digest(key if alg == ALG_KEYED else None, _canonical(body))
        if not hmac.compare_digest(expected, str(entry.get("hash"))):
            return _fail(result, number, "hash mismatch: this entry was modified")
        prev = entry["hash"]
        result["entries"] += 1
    if chained:
        last = chained[-1][1]
        result["head"] = {"seq": last["seq"], "hash": last["hash"]}
    if anchor:
        seq_text, _, wanted = anchor.partition(":")
        try:
            wanted_seq = int(seq_text)
        except ValueError:
            return _fail(result, None, "anchor must look like SEQ:HASH")
        found = {entry["seq"]: entry for _, entry in chained}.get(wanted_seq)
        if found is None:
            return _fail(
                result, None, f"anchored entry {wanted_seq} is missing: the log was truncated"
            )
        if found["hash"] != wanted:
            return _fail(
                result, None, "anchored entry has a different hash: the log was rewritten"
            )
    return result


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "verify"
    if command == "head":
        print(json.dumps(head()))
        return 0
    anchor = argv[argv.index("--anchor") + 1] if "--anchor" in argv else None
    result = verify(anchor)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
