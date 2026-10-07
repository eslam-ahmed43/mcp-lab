import sys

from fastmcp import FastMCP

import store

mcp = FastMCP("tasks-server")

VALID_PRIORITIES = {"low", "medium", "high"}


@mcp.tool
def create_task(title: str, priority: str = "medium") -> dict:
    """Create a new task. priority must be low, medium, or high."""
    if priority not in VALID_PRIORITIES:
        raise ValueError("priority must be low, medium, or high")
    return store.create_task(title, priority)


@mcp.tool
def complete_task(task_id: int) -> dict:
    """Mark a task as done."""
    task = store.complete_task(task_id)
    if task is None:
        raise ValueError(f"task {task_id} not found")
    return task


@mcp.resource("tasks://all")
def all_tasks() -> list[dict]:
    """All tasks, read-only context."""
    return store.list_tasks()


@mcp.resource("tasks://{task_id}")
def one_task(task_id: int) -> dict:
    """A single task by id."""
    task = store.get_task(task_id)
    if task is None:
        raise ValueError(f"task {task_id} not found")
    return task


@mcp.prompt
def plan_my_day() -> str:
    """Ask the model to prioritize open tasks."""
    return (
        "Read the resource tasks://all, then propose an order for the "
        "open tasks based on priority. Do not modify anything."
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "http":
        mcp.run(transport="http", host="127.0.0.1", port=9000)
    else:
        mcp.run()