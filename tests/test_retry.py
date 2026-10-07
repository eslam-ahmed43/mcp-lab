import pytest

from errors import ErrorCategory, ToolFailure, classify
from retry import call_with_retry


async def no_sleep(_):
    return None


class Flaky:
    def __init__(self, failures, error):
        self.failures = failures
        self.error = error
        self.calls = 0

    async def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return "ok"


@pytest.mark.asyncio
async def test_retries_transient_then_succeeds():
    flaky = Flaky(2, ToolFailure(ErrorCategory.RATE_LIMIT, "slow down"))
    assert await call_with_retry(flaky, sleep=no_sleep) == "ok"
    assert flaky.calls == 3


@pytest.mark.asyncio
async def test_does_not_retry_validation_error():
    flaky = Flaky(5, ToolFailure(ErrorCategory.VALIDATION, "bad priority"))
    with pytest.raises(ToolFailure):
        await call_with_retry(flaky, sleep=no_sleep)
    assert flaky.calls == 1


@pytest.mark.asyncio
async def test_does_not_retry_permission_error():
    flaky = Flaky(5, PermissionError("denied"))
    with pytest.raises(ToolFailure) as info:
        await call_with_retry(flaky, sleep=no_sleep)
    assert info.value.category == ErrorCategory.PERMISSION
    assert flaky.calls == 1


@pytest.mark.asyncio
async def test_gives_up_after_max_attempts():
    flaky = Flaky(10, TimeoutError("slow"))
    with pytest.raises(ToolFailure) as info:
        await call_with_retry(flaky, max_attempts=3, sleep=no_sleep)
    assert info.value.category == ErrorCategory.TIMEOUT
    assert flaky.calls == 3


@pytest.mark.asyncio
async def test_backoff_stays_within_exponential_bounds():
    delays = []

    async def record(delay):
        delays.append(delay)

    flaky = Flaky(3, ToolFailure(ErrorCategory.UNAVAILABLE, "down"))
    await call_with_retry(flaky, base_delay=1.0, sleep=record)
    assert len(delays) == 3
    for index, delay in enumerate(delays):
        ceiling = 1.0 * 2**index
        assert ceiling * 0.5 <= delay <= ceiling


def test_classify_reads_backend_code_prefix():
    failure = classify(
        ValueError("Error calling tool 'delete_task': NOT_FOUND: task 1 not found")
    )
    assert failure.category == ErrorCategory.NOT_FOUND
    assert failure.message == "task 1 not found"
    assert not failure.retryable


def test_classify_connection_failure_is_retryable():
    failure = classify(RuntimeError("Client failed to connect: All connection attempts failed"))
    assert failure.category == ErrorCategory.UNAVAILABLE
    assert failure.retryable


def test_classify_unknown_is_not_retried():
    failure = classify(ValueError("something odd"))
    assert failure.category == ErrorCategory.UNKNOWN
    assert not failure.retryable