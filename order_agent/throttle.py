"""Serialise and pace LLM calls, and retry rate-limit (429) errors with backoff."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


def is_rate_limit_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}"
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "RateLimit" in text


class Throttle:
    """At most ``max_concurrency`` calls at once, calls started ``min_interval_s`` apart.

    A 429 is retried up to ``max_retries`` times, sleeping ``retry_base_s * 2**n``
    between tries; any other error, or the last 429, propagates.
    """

    def __init__(
        self,
        *,
        max_concurrency: int = 1,
        min_interval_s: float = 0.0,
        max_retries: int = 0,
        retry_base_s: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._max_concurrency = max_concurrency
        self._min_interval_s = min_interval_s
        self._max_retries = max_retries
        self._retry_base_s = retry_base_s
        self._clock = clock
        self._sleep = sleep
        self._sem: asyncio.Semaphore | None = None
        self._pace_lock: asyncio.Lock | None = None
        self._next_start = float("-inf")

    async def _pace(self) -> None:
        if self._pace_lock is None:
            self._pace_lock = asyncio.Lock()
        async with self._pace_lock:
            wait = self._next_start - self._clock()
            if wait > 0:
                await self._sleep(wait)
            self._next_start = self._clock() + self._min_interval_s

    async def run(self, call: Callable[[], Awaitable[T]]) -> T:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self._max_concurrency)
        attempt = 0
        while True:
            async with self._sem:
                await self._pace()
                try:
                    return await call()
                except Exception as e:
                    if attempt >= self._max_retries or not is_rate_limit_error(e):
                        raise
            await self._sleep(self._retry_base_s * 2**attempt)
            attempt += 1
