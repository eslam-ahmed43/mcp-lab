import json
import os
from dataclasses import asdict
from pathlib import Path

from fastmcp import Client, FastMCP
from fastmcp.client.transports import PythonStdioTransport
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext

import audit
from approvals import ApprovalError, ApprovalStore
from auth import authenticate
from errors import ErrorCategory, ToolFailure, classify
from policy import Decision, authorize
from retry import call_with_retry
from security import inspect_text, sanitize_task, verdict
from visibility import filter_tools
from faults import from_env

BACKEND = Path(__file__).parent / "tasks_server.py"
SAFE_TO_RETRY = {"complete_task", "delete_task"}
SCAN_ENABLED = os.environ.get("MCP_CONTENT_SCAN", "on") != "off"

mcp = FastMCP("gateway")
approvals = ApprovalStore()
faults = from_env()

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

class RoleToolFilter(Middleware):
    async def on_list_tools(self, context: MiddlewareContext, call_next):
        tools = await call_next(context)
        return filter_tools(_principal(), tools)


mcp.add_middleware(RoleToolFilter())


def backend_transport():
    env = {"MCP_DB": os.environ["MCP_DB"]} if os.environ.get("MCP_DB") else None
    return PythonStdioTransport(script_path=BACKEND, env=env)


async def _call_backend(tool: str, arguments: dict):
    faults.maybe_fail(tool)
    async with Client(backend_transport()) as backend:
        result = await backend.call_tool(tool, arguments)
    faults.maybe_fail(tool, "after")
    return result.data


async def _task_exists(task_id: int) -> bool:
    async with Client(backend_transport()) as backend:
        try:
            await backend.read_resource(f"tasks://{task_id}")
        except Exception as exc:
            if classify(exc).category == ErrorCategory.NOT_FOUND:
                return False
            raise
    return True


async def _run(user: str, tool: str, arguments: dict, decision: str):
    def log_retry(attempt: int, failure: ToolFailure) -> None:
        if failure.retryable:
            audit.record(user, tool, arguments, decision, f"attempt {attempt} failed: {failure}")

    attempts = 4 if tool in SAFE_TO_RETRY or arguments.get("idempotency_key") else 1
    try:
        data = await call_with_retry(
            lambda: _call_backend(tool, arguments),
            max_attempts=attempts,
            on_attempt=log_retry,
        )
    except ToolFailure as failure:
        audit.record(user, tool, arguments, decision, f"failed: {failure}")
        raise
    audit.record(user, tool, arguments, decision, "executed")
    return data


@mcp.tool
async def create_task(
    title: str, priority: str = "medium", idempotency_key: str | None = None
) -> dict:
    """Create a new task. priority must be low, medium, or high."""
    arguments = {"title": title, "priority": priority}
    principal, decision = _check("create_task", arguments)
    if SCAN_ENABLED and verdict(inspect_text(title)) == "block":
        audit.record(
            principal.name, "create_task", arguments, "DENY", "blocked: suspicious title content"
        )
        raise ToolFailure(ErrorCategory.VALIDATION, "title rejected by content policy")
    if idempotency_key:
        arguments["idempotency_key"] = f"{principal.name}:{idempotency_key}"
    return await _run(principal.name, "create_task", arguments, decision.value)


@mcp.tool
async def complete_task(task_id: int) -> dict:
    """Mark a task as done."""
    arguments = {"task_id": task_id}
    principal, decision = _check("complete_task", arguments)
    return await _run(principal.name, "complete_task", arguments, decision.value)


@mcp.tool
async def delete_task(task_id: int) -> dict:
    """Delete a task. Requires approval from a second admin."""
    arguments = {"task_id": task_id}
    principal, decision = _check("delete_task", arguments)
    if not await _task_exists(task_id):
        audit.record(
            principal.name, "delete_task", arguments, decision.value, "rejected: task not found"
        )
        raise ToolFailure(ErrorCategory.NOT_FOUND, f"task {task_id} not found")
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
        audit.record(
            principal.name, "review_approval", arguments, decision.value, f"refused: {exc}"
        )
        raise
    audit.record(principal.name, "review_approval", arguments, decision.value, item.status)
    if item.status != "approved":
        return {"status": "rejected"}
    try:
        result = await _run(
            item.requester, item.tool, item.arguments, f"APPROVED_BY:{principal.name}"
        )
    except ToolFailure as failure:
        approvals.record_execution(item.id, False, str(failure))
        return {"status": "approved", "execution": "failed", "error": str(failure)}
    approvals.record_execution(item.id, True)
    return {"status": "approved", "execution": "executed", "result": result}


@mcp.tool
async def retry_approval(approval_id: int) -> dict:
    """Re-run an approved request whose execution failed."""
    arguments = {"approval_id": approval_id}
    principal, decision = _check("retry_approval", arguments)
    try:
        item = approvals.get_retryable(approval_id)
    except ApprovalError as exc:
        audit.record(
            principal.name, "retry_approval", arguments, decision.value, f"refused: {exc}"
        )
        raise
    audit.record(principal.name, "retry_approval", arguments, decision.value, "retrying")
    try:
        result = await _run(
            item.requester, item.tool, item.arguments, f"APPROVED_BY:{item.reviewer}"
        )
    except ToolFailure as failure:
        approvals.record_execution(item.id, False, str(failure))
        return {"status": "approved", "execution": "failed", "error": str(failure)}
    approvals.record_execution(item.id, True)
    return {"status": "approved", "execution": "executed", "result": result}


@mcp.resource("tasks://all")
async def all_tasks() -> str:
    """All tasks, read-only context."""
    principal, decision = _check("read_tasks", {})
    async with Client(backend_transport()) as backend:
        contents = await backend.read_resource("tasks://all")
    cleaned = []
    withheld = 0
    for task in json.loads(contents[0].text):
        safe_task, _ = sanitize_task(task) if SCAN_ENABLED else (task, [])
        withheld += 1 if safe_task.get("flagged") else 0
        cleaned.append(safe_task)
    outcome = "executed" if withheld == 0 else f"executed, {withheld} title(s) withheld"
    audit.record(principal.name, "read_tasks", {}, decision.value, outcome)
    return json.dumps(cleaned)


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)





