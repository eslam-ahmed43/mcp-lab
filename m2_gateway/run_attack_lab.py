import asyncio
from pathlib import Path

from fastmcp import Client

import audit
from security import (
    PathEscape,
    inspect_text,
    safe_resolve,
    scan_description,
    verdict,
    wrap_untrusted,
)

LAB = Path(__file__).parent.parent / "attack_lab"
SERVER = LAB / "vulnerable_server.py"
NOTES_ROOT = LAB / "data" / "notes"


def banner(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def describe(findings):
    return ", ".join(f"{f.severity}:{f.rule}" for f in findings) or "none"


async def attack_tool_poisoning(client):
    banner("ATTACK 1: tool poisoning through the tool description")
    for tool in await client.list_tools():
        description = tool.description or ""
        findings = scan_description(description)
        result = verdict(findings)
        print(f"- {tool.name}: {result.upper()} ({describe(findings)})")
        if result == "block":
            print("  UNGUARDED: the model would read this hidden text:")
            for line in description.strip().splitlines():
                print("    " + line)
            print("  GUARDED: tool hidden from the model")
        audit.record(
            "attack-lab", "scan_tool", {"tool": tool.name}, result.upper(), describe(findings)
        )


async def attack_path_traversal(client):
    banner("ATTACK 2: path traversal through a tool argument")
    for payload in ("welcome.txt", "../secret.txt"):
        print(f"- argument: {payload!r}")
        try:
            safe_resolve(NOTES_ROOT, payload)
            decision = "ALLOW"
            print("  GUARDED: allowed")
        except PathEscape as exc:
            decision = "DENY"
            print(f"  GUARDED: blocked ({exc})")
        audit.record("attack-lab", "read_note", {"name": payload}, decision, "path check")
        if decision == "DENY":
            leaked = await client.call_tool("read_note", {"name": payload})
            print("  UNGUARDED: the server returns:", leaked.content[0].text.strip())


async def attack_result_injection(client):
    banner("ATTACK 3: prompt injection hidden in a tool result")
    for ticket_id in (1, 2):
        result = await client.call_tool("get_ticket", {"ticket_id": ticket_id})
        text = result.content[0].text
        findings = inspect_text(text)
        outcome = verdict(findings)
        print(f"- ticket {ticket_id}: {outcome.upper()} ({describe(findings)})")
        print("  UNGUARDED: the model would read:", repr(text))
        if outcome == "block":
            print("  GUARDED: content withheld, the model gets a refusal notice")
        else:
            print("  GUARDED:", repr(wrap_untrusted(text, "get_ticket")))
        audit.record(
            "attack-lab", "get_ticket", {"ticket_id": ticket_id}, outcome.upper(), describe(findings)
        )


async def main():
    async with Client(SERVER) as client:
        await attack_tool_poisoning(client)
        await attack_path_traversal(client)
        await attack_result_injection(client)


asyncio.run(main())
