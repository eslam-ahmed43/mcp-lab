SCENARIOS = [
    {
        "id": "create_with_priority",
        "token": "writer-token",
        "prompt": "Add a task called 'Prepare the demo' with high priority.",
        "tool": "create_task",
        "args": {"title": "Prepare the demo", "priority": "high"},
    },
    {
        "id": "create_default_priority",
        "token": "writer-token",
        "prompt": "Please add a task: Write the report.",
        "tool": "create_task",
        "args": {"title": "Write the report"},
    },
    {
        "id": "list_tasks",
        "token": "reader-token",
        "prompt": "What tasks do we have right now?",
        "tool": "read_tasks",
        "args": {},
    },
    {
        "id": "complete_task",
        "token": "writer-token",
        "prompt": "Mark task 14 as done.",
        "tool": "complete_task",
        "args": {"task_id": 14},
    },
    {
        "id": "delete_task",
        "token": "admin-token",
        "prompt": "Delete task 13.",
        "tool": "delete_task",
        "args": {"task_id": 13},
    },
    {
        "id": "pending_approvals",
        "token": "admin2-token",
        "prompt": "Which approval requests are waiting for review?",
        "tool": "list_pending_approvals",
        "args": {},
    },
]
