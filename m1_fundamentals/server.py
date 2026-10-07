import sys

from fastmcp import FastMCP

mcp = FastMCP("tasks-server")

TASKS: dict[int, dict] = {}
_next_id = 1


@mcp.tool
def create_task(title: str, priority: str = "medium") -> dict:
    """Create a new task. priority must be low, medium, or high."""
    global _next_id
    if priority not in {"low", "medium", "high"}:
        raise ValueError("priority must be low, medium, or high")
    task = {"id": _next_id, "title": title, "priority": priority, "done": False}
    TASKS[_next_id] = task
    _next_id += 1
    return task


@mcp.tool
def complete_task(task_id: int) -> dict:
    """Mark a task as done."""
    if task_id not in TASKS:
        raise ValueError(f"task {task_id} not found")
    TASKS[task_id]["done"] = True
    return TASKS[task_id]


@mcp.resource("tasks://all")
def all_tasks() -> list[dict]:
    """All tasks, read-only context."""
    return list(TASKS.values())


@mcp.resource("tasks://{task_id}")
def one_task(task_id: int) -> dict:
    """A single task by id."""
    if task_id not in TASKS:
        raise ValueError(f"task {task_id} not found")
    return TASKS[task_id]


@mcp.prompt
def plan_my_day() -> str:
    """Ask the model to prioritize open tasks."""
    return (
        "Read the resource tasks://all, then propose an order for the "
        "open tasks based on priority. Do not modify anything."
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "http":
        mcp.run(transport="http", host="127.0.0.1", port=8000)
    else:
        mcp.run()