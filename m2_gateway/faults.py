import os

from errors import ErrorCategory, ToolFailure


class FaultInjector:
    def __init__(self, spec: str = ""):
        self._remaining: dict[str, tuple[str, int]] = {}
        for part in filter(None, spec.split(",")):
            tool, kind, times = part.split(":")
            self._remaining[tool] = (kind, int(times))

    def maybe_fail(self, tool: str, phase: str = "before") -> None:
        entry = self._remaining.get(tool)
        if entry is None:
            return
        kind, times = entry
        if kind.startswith("after_") != (phase == "after"):
            return
        if times <= 0:
            return
        self._remaining[tool] = (kind, times - 1)
        raise self._build(kind.removeprefix("after_"))

    @staticmethod
    def _build(kind: str) -> Exception:
        if kind == "timeout":
            return TimeoutError("injected timeout")
        if kind == "rate_limit":
            return ToolFailure(ErrorCategory.RATE_LIMIT, "injected 429")
        if kind == "unavailable":
            return ConnectionError("injected connection failure")
        if kind == "validation":
            return ToolFailure(ErrorCategory.VALIDATION, "injected bad request")
        raise ValueError(f"unknown fault kind {kind}")


def from_env() -> FaultInjector:
    return FaultInjector(os.environ.get("MCP_FAULTS", ""))
