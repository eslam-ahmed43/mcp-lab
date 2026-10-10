from auth import Principal
from policy import Decision, authorize


def is_visible(principal: Principal | None, tool_name: str) -> bool:
    return authorize(principal, tool_name, {}) != Decision.DENY


def filter_tools(principal: Principal | None, tools):
    return [tool for tool in tools if is_visible(principal, tool.name)]
