from __future__ import annotations

import random

import pytest

from app.domain.exchange.exceptions import (
    ExchangeAuthenticationError,
    ExchangeConnectionError,
    RateLimitExceededError,
)
from app.infrastructure.binance.retry import RetryPolicy, retry_async


class FakeSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


@pytest.mark.asyncio
async def test_retries_a_retryable_error_until_success() -> None:
    attempts = {"n": 0}

    async def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ExchangeConnectionError("transient")
        return "ok"

    sleep = FakeSleep()
    result = await retry_async(
        flaky, policy=RetryPolicy(max_attempts=5, base_delay_seconds=0.01), sleep=sleep, rng=random.Random(0)
    )

    assert result == "ok"
    assert attempts["n"] == 3
    assert len(sleep.calls) == 2


@pytest.mark.asyncio
async def test_gives_up_after_max_attempts() -> None:
    attempts = {"n": 0}

    async def always_fails() -> None:
        attempts["n"] += 1
        raise ExchangeConnectionError("still broken")

    sleep = FakeSleep()
    with pytest.raises(ExchangeConnectionError):
        await retry_async(always_fails, policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.01), sleep=sleep)

    assert attempts["n"] == 3
    assert len(sleep.calls) == 2  # slept between attempts 1->2 and 2->3, not after the last failure


@pytest.mark.asyncio
async def test_non_retryable_error_is_not_retried() -> None:
    attempts = {"n": 0}

    async def bad_credentials() -> None:
        attempts["n"] += 1
        raise ExchangeAuthenticationError("bad key")

    sleep = FakeSleep()
    with pytest.raises(ExchangeAuthenticationError):
        await retry_async(bad_credentials, policy=RetryPolicy(max_attempts=5), sleep=sleep)

    assert attempts["n"] == 1
    assert sleep.calls == []


@pytest.mark.asyncio
async def test_rate_limit_error_honors_retry_after_instead_of_backoff() -> None:
    attempts = {"n": 0}

    async def rate_limited() -> str:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RateLimitExceededError("slow down", retry_after_seconds=7.5)
        return "ok"

    sleep = FakeSleep()
    result = await retry_async(rate_limited, policy=RetryPolicy(max_attempts=3), sleep=sleep)

    assert result == "ok"
    assert sleep.calls == [7.5]


@pytest.mark.asyncio
async def test_delay_grows_exponentially() -> None:
    async def always_fails() -> None:
        raise ExchangeConnectionError("boom")

    sleep = FakeSleep()
    with pytest.raises(ExchangeConnectionError):
        await retry_async(
            always_fails,
            policy=RetryPolicy(max_attempts=4, base_delay_seconds=1.0, max_delay_seconds=100, jitter_seconds=0),
            sleep=sleep,
            rng=random.Random(0),
        )

    assert sleep.calls == [1.0, 2.0, 4.0]


@pytest.mark.asyncio
async def test_delay_is_capped_at_max_delay() -> None:
    async def always_fails() -> None:
        raise ExchangeConnectionError("boom")

    sleep = FakeSleep()
    with pytest.raises(ExchangeConnectionError):
        await retry_async(
            always_fails,
            policy=RetryPolicy(max_attempts=5, base_delay_seconds=10, max_delay_seconds=15, jitter_seconds=0),
            sleep=sleep,
            rng=random.Random(0),
        )

    assert all(delay <= 15 for delay in sleep.calls)
