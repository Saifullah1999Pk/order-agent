import asyncio

import pytest

from order_agent.throttle import Throttle, is_rate_limit_error


class FakeClock:
    """Virtual time: sleep() advances now() instantly."""

    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def now(self):
        return self.t

    async def sleep(self, s):
        self.sleeps.append(s)
        self.t += s
        await asyncio.sleep(0)


def make(clock, **kw):
    return Throttle(clock=clock.now, sleep=clock.sleep, **kw)


async def test_concurrency_is_one():
    clock = FakeClock()
    th = make(clock, max_concurrency=1, min_interval_s=0)
    active = peak = 0

    async def call():
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        active -= 1
        return "ok"

    assert await asyncio.gather(*(th.run(call) for _ in range(5))) == ["ok"] * 5
    assert peak == 1


async def test_calls_are_spaced_by_min_interval():
    clock = FakeClock()
    th = make(clock, min_interval_s=4.5)
    starts = []

    async def call():
        starts.append(clock.now())

    await asyncio.gather(*(th.run(call) for _ in range(4)))
    assert all(b - a >= 4.5 for a, b in zip(starts, starts[1:]))


async def test_429_is_retried_with_backoff_then_succeeds():
    clock = FakeClock()
    th = make(clock, min_interval_s=0, max_retries=3, retry_base_s=5)
    attempts = 0

    async def call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("Error code: 429 - RESOURCE_EXHAUSTED")
        return "done"

    assert await th.run(call) == "done"
    assert attempts == 3
    assert clock.sleeps == [5, 10]


async def test_non_429_is_not_retried():
    clock = FakeClock()
    th = make(clock, max_retries=3)
    attempts = 0

    async def call():
        nonlocal attempts
        attempts += 1
        raise ValueError("bad request")

    with pytest.raises(ValueError):
        await th.run(call)
    assert attempts == 1


async def test_error_propagates_after_max_retries():
    clock = FakeClock()
    th = make(clock, min_interval_s=0, max_retries=2, retry_base_s=1)
    attempts = 0

    async def call():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("429 Too Many Requests")

    with pytest.raises(RuntimeError, match="429"):
        await th.run(call)
    assert attempts == 3  # first try + 2 retries


def test_is_rate_limit_error():
    assert is_rate_limit_error(RuntimeError("Error code: 429"))
    assert is_rate_limit_error(RuntimeError("RESOURCE_EXHAUSTED quota"))
    assert not is_rate_limit_error(ValueError("500 internal"))
