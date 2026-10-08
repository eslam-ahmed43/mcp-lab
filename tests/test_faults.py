import pytest

from errors import ErrorCategory, ToolFailure
from faults import FaultInjector
from retry import call_with_retry


async def no_sleep(_):
    return None


def test_empty_spec_injects_nothing():
    FaultInjector("").maybe_fail("complete_task")


def test_fails_exactly_n_times():
    injector = FaultInjector("complete_task:timeout:2")
    with pytest.raises(TimeoutError):
        injector.maybe_fail("complete_task")
    with pytest.raises(TimeoutError):
        injector.maybe_fail("complete_task")
    injector.maybe_fail("complete_task")


def test_other_tools_unaffected():
    injector = FaultInjector("complete_task:timeout:5")
    injector.maybe_fail("delete_task")


@pytest.mark.asyncio
async def test_retry_recovers_from_injected_transient_faults():
    injector = FaultInjector("complete_task:rate_limit:2")
    calls = []

    async def backend():
        injector.maybe_fail("complete_task")
        calls.append(1)
        return "done"

    assert await call_with_retry(backend, sleep=no_sleep) == "done"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_retry_gives_up_when_faults_outlast_attempts():
    injector = FaultInjector("complete_task:unavailable:10")

    async def backend():
        injector.maybe_fail("complete_task")

    with pytest.raises(ToolFailure) as info:
        await call_with_retry(backend, max_attempts=3, sleep=no_sleep)
    assert info.value.category == ErrorCategory.UNAVAILABLE


@pytest.mark.asyncio
async def test_validation_fault_is_not_retried():
    injector = FaultInjector("create_task:validation:5")
    attempts = []

    async def backend():
        attempts.append(1)
        injector.maybe_fail("create_task")

    with pytest.raises(ToolFailure):
        await call_with_retry(backend, sleep=no_sleep)
    assert len(attempts) == 1