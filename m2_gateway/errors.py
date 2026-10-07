from enum import Enum


class ErrorCategory(str, Enum):
    VALIDATION = "VALIDATION"
    NOT_FOUND = "NOT_FOUND"
    PERMISSION = "PERMISSION"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


RETRYABLE = {
    ErrorCategory.RATE_LIMIT,
    ErrorCategory.TIMEOUT,
    ErrorCategory.UNAVAILABLE,
}


class ToolFailure(Exception):
    def __init__(self, category: ErrorCategory, message: str):
        super().__init__(f"{category.value}: {message}")
        self.category = category
        self.message = message

    @property
    def retryable(self) -> bool:
        return self.category in RETRYABLE


def classify(exc: BaseException) -> ToolFailure:
    if isinstance(exc, ToolFailure):
        return exc
    if isinstance(exc, PermissionError):
        return ToolFailure(ErrorCategory.PERMISSION, str(exc))
    if isinstance(exc, TimeoutError):
        return ToolFailure(ErrorCategory.TIMEOUT, str(exc) or "timed out")
    if isinstance(exc, ConnectionError):
        return ToolFailure(ErrorCategory.UNAVAILABLE, str(exc))
    text = str(exc)
    for category in ErrorCategory:
        marker = f"{category.value}:"
        if marker in text:
            return ToolFailure(category, text.split(marker, 1)[1].strip())
    if "failed to connect" in text.lower():
        return ToolFailure(ErrorCategory.UNAVAILABLE, text)
    return ToolFailure(ErrorCategory.UNKNOWN, text)