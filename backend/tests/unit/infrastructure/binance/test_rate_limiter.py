from __future__ import annotations

import pytest

from app.infrastructure.binance.rate_limiter import InMemoryTokenBucketRateLimiter


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeSleep:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        self.clock.advance(seconds)


@pytest.mark.asyncio
async def test_consumes_up_to_capacity_without_waiting() -> None:
    clock = FakeClock()
    sleep = FakeSleep(clock)
    limiter = InMemoryTokenBucketRateLimiter({"X": (5, 1.0)}, clock=clock, sleep=sleep)

    for _ in range(5):
        await limiter.acquire("X")

    assert sleep.calls == []


@pytest.mark.asyncio
async def test_blocks_and_advances_clock_when_bucket_is_exhausted() -> None:
    clock = FakeClock()
    sleep = FakeSleep(clock)
    limiter = InMemoryTokenBucketRateLimiter({"X": (2, 1.0)}, clock=clock, sleep=sleep)

    await limiter.acquire("X")
    await limiter.acquire("X")
    await limiter.acquire("X")  # bucket empty: must wait for a refill

    assert len(sleep.calls) == 1
    assert sleep.calls[0] > 0


@pytest.mark.asyncio
async def test_refills_continuously_over_time() -> None:
    clock = FakeClock()
    sleep = FakeSleep(clock)
    limiter = InMemoryTokenBucketRateLimiter({"X": (10, 10.0)}, clock=clock, sleep=sleep)

    for _ in range(10):
        await limiter.acquire("X")
    assert sleep.calls == []

    clock.advance(5.0)  # half the refill window: 5 tokens back
    for _ in range(5):
        await limiter.acquire("X")
    assert sleep.calls == []  # still didn't need to wait

    await limiter.acquire("X")  # now truly exhausted
    assert len(sleep.calls) == 1


@pytest.mark.asyncio
async def test_unconfigured_bucket_is_unlimited() -> None:
    clock = FakeClock()
    sleep = FakeSleep(clock)
    limiter = InMemoryTokenBucketRateLimiter({}, clock=clock, sleep=sleep)

    for _ in range(1000):
        await limiter.acquire("ANYTHING")

    assert sleep.calls == []


@pytest.mark.asyncio
async def test_buckets_are_independent() -> None:
    clock = FakeClock()
    sleep = FakeSleep(clock)
    limiter = InMemoryTokenBucketRateLimiter({"A": (1, 1.0), "B": (1, 1.0)}, clock=clock, sleep=sleep)

    await limiter.acquire("A")
    await limiter.acquire("B")  # separate bucket — must not be blocked by A's exhaustion

    assert sleep.calls == []


@pytest.mark.asyncio
async def test_acquire_respects_weight_greater_than_one() -> None:
    clock = FakeClock()
    sleep = FakeSleep(clock)
    limiter = InMemoryTokenBucketRateLimiter({"X": (10, 1.0)}, clock=clock, sleep=sleep)

    await limiter.acquire("X", weight=8)
    await limiter.acquire("X", weight=2)
    assert sleep.calls == []

    await limiter.acquire("X", weight=1)  # exhausted now
    assert len(sleep.calls) == 1
