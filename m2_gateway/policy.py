from enum import Enum

from auth import Principal


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


ROLE_PERMISSIONS = {
    "reader": {"read"},
    "writer": {"read", "write"},
    "admin": {"read", "write", "delete", "approve"},
}

TOOL_PERMISSION = {
    "read_tasks": "read",
    "create_task": "write",
    "complete_task": "write",
    "delete_task": "delete",
    "review_approval": "approve",
    "list_pending_approvals": "approve",
    "retry_approval": "approve",
}

APPROVAL_REQUIRED = {"delete_task"}


def authorize(principal: Principal | None, tool: str, arguments: dict) -> Decision:
    if principal is None:
        return Decision.DENY
    required = TOOL_PERMISSION.get(tool)
    if required is None:
        return Decision.DENY
    granted = ROLE_PERMISSIONS.get(principal.role, set())
    if required not in granted:
        return Decision.DENY
    if tool in APPROVAL_REQUIRED:
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW
