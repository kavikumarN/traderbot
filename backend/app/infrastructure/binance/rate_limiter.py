"""In-process token-bucket rate limiter.

One bucket per name (Binance separates ``REQUEST_WEIGHT`` from ``ORDERS``,
each with its own capacity and refill window), refilling continuously
rather than in discrete steps so bursty-then-idle traffic isn't penalized
more than steady traffic carrying the same total weight.

Correct for a single process holding one Binance API key. A deployment
running multiple instances against the same key would need a Redis-backed
``RateLimiter`` instead — callers depend on the ``RateLimiter`` port, not
this class, so that swap wouldn't touch anything else.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.domain.exchange.ports.rate_limiter import RateLimiter


@dataclass
class _BucketState:
    capacity: float
    refill_period_seconds: float
    tokens: float
    updated_at: float


class InMemoryTokenBucketRateLimiter(RateLimiter):
    def __init__(
        self,
        limits: dict[str, tuple[int, float]],
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """`limits` maps bucket name -> (capacity, refill_period_seconds).
        A bucket not present in `limits` is treated as unlimited."""
        self._limits = limits
        self._clock = clock
        self._sleep = sleep
        self._buckets: dict[str, _BucketState] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, bucket: str, weight: int = 1) -> None:
        limit = self._limits.get(bucket)
        if limit is None:
            return
        capacity, period = limit

        while True:
            async with self._lock:
                state = self._buckets.get(bucket)
                if state is None:
                    state = _BucketState(
                        capacity=capacity,
                        refill_period_seconds=period,
                        tokens=capacity,
                        updated_at=self._clock(),
                    )
                    self._buckets[bucket] = state

                self._refill(state)

                if state.tokens >= weight:
                    state.tokens -= weight
                    return

                deficit = weight - state.tokens
                wait_seconds = deficit * (state.refill_period_seconds / state.capacity)

            await self._sleep(wait_seconds)

    def _refill(self, state: _BucketState) -> None:
        now = self._clock()
        elapsed = max(now - state.updated_at, 0.0)
        refill_rate = state.capacity / state.refill_period_seconds
        state.tokens = min(state.capacity, state.tokens + elapsed * refill_rate)
        state.updated_at = now
