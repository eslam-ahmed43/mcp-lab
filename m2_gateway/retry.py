import asyncio
import random
from collections.abc import Awaitable, Callable

from errors import ToolFailure, classify


async def call_with_retry[T](
    fn: Callable[[], Awaitable[T]],
    max_attempts: int = 4,
    base_delay: float = 0.2,
    max_delay: float = 5.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    on_attempt: Callable[[int, ToolFailure], None] | None = None,
) -> T:
    attempt = 0
    while True:
        attempt += 1
        try:
            return await fn()
        except Exception as exc:
            failure = classify(exc)
            if on_attempt:
                on_attempt(attempt, failure)
            if not failure.retryable or attempt >= max_attempts:
                raise failure from exc
            delay = min(max_delay, base_delay * 2 ** (attempt - 1))
            await sleep(delay * random.uniform(0.5, 1.0))