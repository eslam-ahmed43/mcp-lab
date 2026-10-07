from dataclasses import asdict
from pathlib import Path

from fastmcp import Client, FastMCP
from fastmcp.server.dependencies import get_http_headers

import audit
from approvals import ApprovalError, ApprovalStore
from auth import authenticate
from policy import Decision, authorize

BACKEND = Path(__file__).parent / "tasks_server.py"

mcp = FastMCP("gateway")
approvals = ApprovalStore()


def _principal():
    headers = get_http_headers(include_all=True)
    value = headers.get("authorization", "")
    token = value.removeprefix("Bearer ").strip() or None
    return authenticate(token)


def _check(tool: str, arguments: dict):
    principal = _principal()
    decision = authorize(principal, tool, arguments)
    if decision == Decision.DENY:
        user = principal.name if principal else "anonymous"
        audit.record(user, tool, arguments, decision.value, "blocked")
        raise PermissionError(f"{tool} denied")
    return principal, decision


async def _run(user: str, tool: str, arguments: dict, decision: str):
    try:
        async with Client(BACKEND) as backend:
            result = await backend.call_tool(tool, arguments)
    except Exception as exc:
        audit.record(user, tool, arguments, decision, f"error: {exc}")
        raise
    audit.record(user, tool, arguments, decision, "executed")
    return result.data


@mcp.tool
async def create_task(title: str, priority: str = "medium") -> dict:
    """Create a new task. priority must be low, medium, or high."""
    arguments = {"title": title, "priority": priority}
    principal, decision = _check("create_task", arguments)
    return await _run(principal.name, "create_task", arguments, decision.value)


@mcp.tool
async def complete_task(task_id: int) -> dict:
    """Mark a task as done."""
    arguments = {"task_id": task_id}
    principal, decision = _check("complete_task", arguments)
    return await _run(principal.name, "complete_task", arguments, decision.value)


@mcp.tool
async def delete_task(task_id: int) -> dict:
    """Permanently delete a task. Requires approval from a second admin."""
    arguments = {"task_id": task_id}
    principal, decision = _check("delete_task", arguments)
    if decision == Decision.REQUIRE_APPROVAL:
        item = approvals.submit(principal.name, "delete_task", arguments)
        audit.record(
            principal.name, "delete_task", arguments, decision.value,
            f"queued approval {item.id}",
        )
        return {"status": "pending_approval", "approval_id": item.id}
    return await _run(principal.name, "delete_task", arguments, decision.value)


@mcp.tool
async def list_pending_approvals() -> list[dict]:
    """List approval requests waiting for review."""
    _check("list_pending_approvals", {})
    return [asdict(i) for i in approvals.pending()]


@mcp.tool
async def review_approval(approval_id: int, approve: bool) -> dict:
    """Approve or reject a pending request. Requester cannot review their own."""
    arguments = {"approval_id": approval_id, "approve": approve}
    principal, decision = _check("review_approval", arguments)
    try:
        item = approvals.decide(approval_id, principal.name, principal.role, approve)
    except ApprovalError as exc:
        audit.record(principal.name, "review_approval", arguments, decision.value, f"refused: {exc}")
        raise
    audit.record(principal.name, "review_approval", arguments, decision.value, item.status)
    if item.status != "approved":
        return {"status": "rejected"}
    result = await _run(
        item.requester, item.tool, item.arguments, f"APPROVED_BY:{principal.name}"
    )
    return {"status": "approved", "result": result}


@mcp.resource("tasks://all")
async def all_tasks() -> str:
    """All tasks, read-only context."""
    principal, decision = _check("read_tasks", {})
    async with Client(BACKEND) as backend:
        contents = await backend.read_resource("tasks://all")
    audit.record(principal.name, "read_tasks", {}, decision.value, "executed")
    return contents[0].text


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)