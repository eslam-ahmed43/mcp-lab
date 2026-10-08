from dataclasses import dataclass
from itertools import count


class ApprovalError(Exception):
    pass


@dataclass
class Approval:
    id: int
    requester: str
    tool: str
    arguments: dict
    status: str = "pending"
    reviewer: str | None = None
    execution: str = "not_run"
    error: str | None = None


class ApprovalStore:
    def __init__(self):
        self._items: dict[int, Approval] = {}
        self._ids = count(1)

    def submit(self, requester: str, tool: str, arguments: dict) -> Approval:
        item = Approval(next(self._ids), requester, tool, dict(arguments))
        self._items[item.id] = item
        return item

    def pending(self) -> list[Approval]:
        return [i for i in self._items.values() if i.status == "pending"]

    def decide(self, approval_id: int, reviewer: str, role: str, approve: bool) -> Approval:
        item = self._items.get(approval_id)
        if item is None:
            raise ApprovalError(f"approval {approval_id} not found")
        if item.status != "pending":
            raise ApprovalError(f"approval {approval_id} already {item.status}")
        if role != "admin":
            raise ApprovalError("reviewer must be an admin")
        if reviewer == item.requester:
            raise ApprovalError("requester cannot review their own request")
        item.status = "approved" if approve else "rejected"
        item.reviewer = reviewer
        return item

    def record_execution(self, approval_id: int, ok: bool, error: str | None = None) -> Approval:
        item = self._items.get(approval_id)
        if item is None:
            raise ApprovalError(f"approval {approval_id} not found")
        if item.status != "approved":
            raise ApprovalError("only approved requests can be executed")
        item.execution = "executed" if ok else "failed"
        item.error = error
        return item
    def get_retryable(self, approval_id: int) -> Approval:
        item = self._items.get(approval_id)
        if item is None:
            raise ApprovalError(f"approval {approval_id} not found")
        if item.status != "approved" or item.execution != "failed":
            raise ApprovalError(
                "only approved requests whose execution failed can be retried"
            )
        return item
